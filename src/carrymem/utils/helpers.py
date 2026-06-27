import hashlib
import json
import logging
import re
import secrets
import time
from datetime import timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MEMORY_TYPES = {
    "user_preference": "User Preference",
    "correction": "Correction",
    "fact_declaration": "Fact Declaration",
    "decision": "Decision",
    "relationship": "Relationship",
    "task_pattern": "Task Pattern",
    "sentiment_marker": "Sentiment Marker",
    "session_summary": "Session Summary",
}

MEMORY_TIERS = {
    1: "Working Memory",
    2: "Procedural Memory",
    3: "Episodic Memory",
    4: "Semantic Memory",
}


def generate_memory_id() -> str:
    """Generate a unique memory ID using cryptographically secure random."""
    timestamp = int(time.time() * 1000)
    random_suffix = secrets.randbelow(9000) + 1000
    return f"mem_{timestamp}_{random_suffix}"


def get_current_time() -> str:
    """Get the current time in ISO format.

    Returns:
        The current time as an ISO string.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def extract_content(text: str, pattern: str, action: str) -> Optional[str]:
    """Extract content from text based on pattern and action.

    Args:
        text: The text to extract from.
        pattern: The regex pattern to match.
        action: The action to perform.

    Returns:
        The extracted content or None.
    """
    match = re.search(pattern, text)
    if not match:
        return None

    if action == "extract_following_content":
        start = match.end()
        content = text[start:].strip()
        content = re.sub(r"[.!?]+$", "", content)
        return content

    elif action == "extract_surrounding_context":
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 100)
        content = text[start:end].strip()
        return content

    elif action == "extract_entity_and_relation":
        content = text.strip()
        return content

    elif action == "extract_preceding_proposal":
        end = match.start()
        content = text[:end].strip()
        content = re.sub(r"[.!?]+$", "", content)
        return content

    elif action == "extract":
        content = match.group(0)
        return content

    return None


def calculate_memory_weight(confidence: float, days_since_last_access: int, access_count: int) -> float:
    """Calculate memory weight based on confidence, recency, and frequency.

    Args:
        confidence: Confidence score (0.0-1.0).
        days_since_last_access: Days since last access.
        access_count: Number of times the memory has been accessed.

    Returns:
        The calculated memory weight.
    """
    recency_score = 2 ** (-0.1 * days_since_last_access)

    frequency_score = 1 + 0.5 * (access_count**0.5)

    weight = confidence * recency_score * frequency_score

    return weight  # type: ignore[no-any-return]


def format_memory(memory: Dict[str, Any]) -> str:
    """Format memory as a string for display.

    Args:
        memory: The memory dictionary.

    Returns:
        The formatted memory string.
    """
    memory_type = MEMORY_TYPES.get(memory.get("type", "unknown"), "unknown")
    tier = MEMORY_TIERS.get(memory.get("tier", 1), "unknown")

    return f"[{tier}] {memory_type}: {memory.get('content', '')} (confidence: {memory.get('confidence', 0.0):.2f})"


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON data from file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        The loaded JSON data as a dictionary.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data  # type: ignore[no-any-return]
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError, ValueError, TypeError) as e:
        logger.warning("Error loading JSON file %s: %s", file_path, e)
        return {}


def save_json_file(file_path: str, data: Dict[str, Any]):
    """Save JSON data to file.

    Args:
        file_path: Path to the JSON file.
        data: The data to save.
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as e:
        logger.warning("Error saving JSON file %s: %s", file_path, e)


def escape_like(value: str) -> str:
    """Escape special characters in LIKE pattern for SQL queries."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def content_hash(content: str, prefix: str = "") -> str:
    """Generate a SHA-256 content hash.

    Args:
        content: The content to hash.
        prefix: Optional prefix to include in the hash.
            - For memory deduplication (SQLite/JSON adapters): pass entry type
              so that same content with different types produces different hashes.
            - For file change detection (Obsidian adapter): omit prefix so that
              same file content always produces the same hash regardless of type.

    Returns:
        The first 16 characters of the hex digest.
    """
    data = f"{prefix}:{content}" if prefix else content
    return hashlib.sha256(data.encode()).hexdigest()[:16]


TIER_TTL = {
    1: timedelta(hours=24),
    2: timedelta(days=90),
    3: timedelta(days=365),
    4: None,
}
