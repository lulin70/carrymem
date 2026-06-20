"""Input validation utilities for CarryMem.

Provides validation functions to ensure data integrity and prevent
invalid inputs from causing errors.

Includes enhanced security features:
- Unicode safety checks (control characters, bidi override detection)
- ReDoS protection for regex matching
- SQL injection pattern detection (audit-only)
- Path traversal / symlink safety
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Match, Optional, Tuple

from carrymem.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────

# Control character ranges (C0 + C1), excluding allowed \t (0x09) \n (0x0A) \r (0x0D)
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Unicode bidi override / isolation characters (Trojan Source attacks)
_BIDI_DANGER_CHARS = {
    "\u202a",  # LEFT-TO-RIGHT EMBEDDING
    "\u202b",  # RIGHT-TO-LEFT EMBEDDING
    "\u202c",  # POP DIRECTIONAL FORMATTING
    "\u202d",  # LEFT-TO-RIGHT OVERRIDE
    "\u202e",  # RIGHT-TO-LEFT OVERRIDE
    "\u2066",  # LEFT-TO-RIGHT ISOLATE
    "\u2067",  # RIGHT-TO-LEFT ISOLATE
    "\u2068",  # FIRST STRONG ISOLATE
    "\u2069",  # POP DIRECTIONAL ISOLATE
}
_BIDI_PATTERN = re.compile("[" + "".join(_BIDI_DANGER_CHARS) + "]")

# Dangerous regex patterns known to cause ReDoS (nested quantifiers, etc.)
_REDOS_WARNING_PATTERNS = [
    re.compile(r"\([^)]*[+*][^)]*\)[+*]"),  # nested quantifiers like (a+)+
    re.compile(r"\([^)]*\|[^\)]*\)[+*]{2,}"),  # alternation with greedy quantifier
    re.compile(r"[+*]\?[+*]"),  # optional followed by quantifier
]

# Common SQL injection patterns (case-insensitive, audit-only)
_SQL_INJECTION_PATTERNS = [
    re.compile(
        r"(\b(union|select|insert|update|delete|drop|alter|create|exec|execute)\b\s+.+\b(from|into|table|where|set)\b)",
        re.IGNORECASE,
    ),
    re.compile(r"(\bor\b\s+\d+\s*=\s*\d+)", re.IGNORECASE),
    re.compile(r"(--\s*$|#\s*$)", re.MULTILINE),
    re.compile(r"(;\s*(drop|alter|delete|update|insert)\b)", re.IGNORECASE),
    re.compile(r"('\s*(or|and)\s+')", re.IGNORECASE),
    re.compile(r"(\b(waitfor|delay|benchmark|sleep)\s*\()", re.IGNORECASE),
    re.compile(r"(0x[0-9a-f]+)", re.IGNORECASE),  # hex-encoded payloads
]

# Max text length for regex matching (ReDoS mitigation)
_SAFE_MATCH_MAX_TEXT_LENGTH = 1_000_000


# ══════════════════════════════════════════════════════════════════
#  Original validators (unchanged)
# ══════════════════════════════════════════════════════════════════


def validate_message(message: str, max_length: int = 10000) -> None:
    """Validate a message string.

    Args:
        message: The message to validate
        max_length: Maximum allowed length (default: 10000)

    Raises:
        ValidationError: If validation fails
    """
    if not message:
        raise ValidationError("Message cannot be empty")

    if not isinstance(message, str):
        raise ValidationError(f"Message must be a string, got {type(message).__name__}")

    if len(message) > max_length:
        raise ValidationError(f"Message too long: {len(message)} characters (max {max_length})")


def validate_context(context: Optional[Dict[str, Any]]) -> None:
    """Validate a context dictionary.

    Args:
        context: The context to validate

    Raises:
        ValidationError: If validation fails
    """
    if context is None:
        return

    if not isinstance(context, dict):
        raise ValidationError(f"Context must be a dictionary, got {type(context).__name__}")

    # Check for reasonable size
    if len(str(context)) > 50000:
        raise ValidationError("Context too large (max 50000 characters when serialized)")


def validate_language(language: Optional[str]) -> None:
    """Validate a language code.

    Args:
        language: The language code to validate (e.g., 'en', 'zh', 'ja')

    Raises:
        ValidationError: If validation fails
    """
    if language is None:
        return

    if not isinstance(language, str):
        raise ValidationError(f"Language must be a string, got {type(language).__name__}")

    if len(language) > 10:
        raise ValidationError(f"Language code too long: {len(language)} (max 10)")

    # Basic format check (2-3 letter codes, or locale like 'en-US')
    if not language.replace("-", "").replace("_", "").isalnum():
        raise ValidationError(f"Invalid language code format: {language}")


def validate_namespace(namespace: str) -> None:
    """Validate a namespace string.

    Args:
        namespace: The namespace to validate

    Raises:
        ValidationError: If validation fails
    """
    if not namespace:
        raise ValidationError("Namespace cannot be empty")

    if not isinstance(namespace, str):
        raise ValidationError(f"Namespace must be a string, got {type(namespace).__name__}")

    if len(namespace) > 128:
        raise ValidationError(f"Namespace too long: {len(namespace)} (max 128)")

    # Check for valid characters (alphanumeric, dash, underscore)
    if not all(c.isalnum() or c in "-_" for c in namespace):
        raise ValidationError(
            f"Namespace contains invalid characters: {namespace}. " "Only alphanumeric, dash, and underscore allowed."
        )


def validate_limit(limit: int, max_limit: int = 100000) -> None:
    """Validate a limit parameter.

    Args:
        limit: The limit to validate
        max_limit: Maximum allowed limit (default: 100000)

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(limit, int):
        raise ValidationError(f"Limit must be an integer, got {type(limit).__name__}")

    if limit < 0:
        raise ValidationError(f"Limit cannot be negative: {limit}")

    if limit > max_limit:
        raise ValidationError(f"Limit too large: {limit} (max {max_limit})")


_DEFAULT_ALLOWED_FILTER_KEYS = {"type", "tier", "confidence_min", "created_after", "namespace"}


def validate_filters(filters: Optional[Dict[str, Any]], allowed_keys: set = None) -> None:
    if filters is None:
        return

    if not isinstance(filters, dict):
        raise ValidationError(f"Filters must be a dictionary, got {type(filters).__name__}")

    keys = allowed_keys or _DEFAULT_ALLOWED_FILTER_KEYS
    invalid_keys = set(filters.keys()) - keys
    if invalid_keys:
        raise ValidationError(f"Invalid filter keys: {invalid_keys}. " f"Allowed keys: {keys}")


def validate_memory_type(memory_type: str, valid_types: set) -> None:
    """Validate a memo type.

    Args:
        memory_the memory type to validate
        valid_types: Set of valid memory types

    Raises:
        ValidationError: If validation fails
    """
    if not memory_type:
        raise ValidationError("Memory type cannot be empty")

    if not isinstance(memory_type, str):
        raise ValidationError(f"Memory type must be a string, got {type(memory_type).__name__}")

    if memory_type not in valid_types:
        raise ValidationError(f"Invalid memory type: '{memory_type}'. " f"Valid types: {valid_types}")


def validate_confidence(confidence: float) -> None:
    """Validate a confidence score.

    Args:
        confidence: The confidence score to validate (0.0 to 1.0)

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(confidence, (int, float)):
        raise ValidationError(f"Confidence must be a number, got {type(confidence).__name__}")

    if not 0.0 <= confidence <= 1.0:
        raise ValidationError(f"Confidence must be between 0.0 and 1.0, got {confidence}")


def validate_tier(tier: int) -> None:
    """Validate a memory tier.

    Args:
        tier: The tier to validate (1-4)
       Raises:
        ValidationError: If validation fails
    """
    if not isinstance(tier, int):
        raise ValidationError(f"Tier must be an integer, got {type(tier).__name__}")

    if tier not in {1, 2, 3, 4}:
        raise ValidationError(f"Tier must be 1, 2, 3, or 4, got {tier}")


def validate_storage_key(storage_key: str) -> None:
    """Validate a storage key.

    Args:
        storage_key: The storage key to validate

    Raises:
        ValidationError: If validation fails
    """
    if not storage_key:
        raise ValidationError("Storage key cannot be empty")

    if not isinstance(storage_key, str):
        raise ValidationError(f"Storage key must be a string, got {type(storage_key).__name__}")

    if len(storage_key) > 256:
        raise ValidationError(f"Storage key too long: {len(storage_key)} (max 256)")


def validate_query(query: str, max_length: int = 10000) -> None:
    """Validate a search query.

    Args:
        query: The query to valid max_length: Maximum allowed length (default: 10000)

    Raises:
        ValidationError: If validation fails
    """
    if query is None:
        return  # Empty query is allowed for some operations

    if not isinstance(query, str):
        raise ValidationError(f"Query must be a string, got {type(query).__name__}")

    if len(query) > max_length:
        raise ValidationError(f"Query too long: {len(query)} characters (max {max_length})")


def validate_namespaces(namespaces: Optional[List[str]]) -> None:
    """Validate a list of namespaces.

    Args:
        nae list of namespaces to validate

    Raises:
        ValidationError: If validation fails
    """
    if namespaces is None:
        return

    if not isinstance(namespaces, list):
        raise ValidationError(f"Namespaces must be a list, got {type(namespaces).__name__}")

    if len(namespaces) > 100:
        raise ValidationError(f"Too many namespaces: {len(namespaces)} (max 100)")

    for ns in namespaces:
        validate_namespace(ns)


# ══════════════════════════════════════════════════════════════════
#  Enhanced security validators (P1-7)
# ══════════════════════════════════════════════════════════════════


def validate_unicode_safe(text: str) -> str:
    """Check text for dangerous Unicode characters and return cleaned text.

    Detects and rejects:
    - Control characters (U+0000-U+001F, U+007F-U+009F) except
      legitimate ``\\t`` (U+0009), ``\\n`` (U+000A), ``\\r`` (U+000D).
    - Unicode bidirectional override / isolation characters (Trojan Source).

    Args:
        text: The input string to validate.

    Returns:
        The original text if safe.

    Raises:
        ValidationError: If dangerous characters are detected.
    """
    if not isinstance(text, str):
        raise ValidationError(f"validate_unicode_safe expects a string, got {type(text).__name__}")

    # 1. Check control characters (excluding \t \n \r)
    ctrl_match = _CONTROL_CHAR_PATTERN.search(text)
    if ctrl_match:
        pos = ctrl_match.start()
        char = text[pos]
        char_code = ord(char)
        raise ValidationError(
            f"Dangerous control character U+{char_code:04X} found at position {pos}. "
            "Control characters (except TAB/LF/CR) are not allowed."
        )

    # 2. Check bidi override / isolation characters
    bidi_match = _BIDI_PATTERN.search(text)
    if bidi_match:
        pos = bidi_match.start()
        char = text[pos]
        char_name = _bidi_char_name(char)
        raise ValidationError(
            f"Unicode bidirectional override character ({char_name}, "
            f"U+{ord(char):04X}) found at position {pos}. "
            "These characters can be used for source-code spoofing attacks."
        )

    return text


def _bidi_char_name(char: str) -> str:
    """Return a human-readable name for a bidi danger character."""
    names = {
        "\u202a": "LEFT-TO-RIGHT EMBEDDING",
        "\u202b": "RIGHT-TO-LEFT EMBEDDING",
        "\u202c": "POP DIRECTIONAL FORMATTING",
        "\u202d": "LEFT-TO-RIGHT OVERRIDE",
        "\u202e": "RIGHT-TO-LEFT OVERRIDE",
        "\u2066": "LEFT-TO-RIGHT ISOLATE",
        "\u2067": "RIGHT-TO-LEFT ISOLATE",
        "\u2068": "FIRST STRONG ISOLATE",
        "\u2069": "POP DIRECTIONAL ISOLATE",
    }
    return names.get(char, "UNKNOWN")


def safe_text_match(
    pattern: str,
    text: str,
    timeout_ms: int = 1000,
) -> Optional[Match[str]]:
    """Safely match a regex pattern against text with ReDoS protection.

    Safety measures:
    - Warns on known-dangerous regex patterns (nested quantifiers etc.).
    - Truncates overly long text before matching.
    - Uses Python 3.11+ ``re.timeout`` when available; otherwise relies
      on length truncation as primary defense.

    Args:
        pattern: The regex pattern string.
        text: The text to search within.
        timeout_ms: Timeout in milliseconds (Python 3.11+, default 1000ms).

    Returns:
        A :class:`re.Match` object if a match is found, else ``None``.
    """
    # 1. Warn on dangerous patterns
    for idx, danger_re in enumerate(_REDOS_WARNING_PATTERNS):
        if danger_re.search(pattern):
            logger.warning(
                "ReDoS warning: pattern %r matches known-dangerous pattern #%d. "
                "Consider simplifying the regex to avoid catastrophic backtracking.",
                pattern[:80],
                idx,
            )

    # 2. Truncate long text
    original_len = len(text)
    if original_len > _SAFE_MATCH_MAX_TEXT_LENGTH:
        logger.warning(
            "Text truncated from %d to %d characters for safe matching.",
            original_len,
            _SAFE_MATCH_MAX_TEXT_LENGTH,
        )
        text = text[:_SAFE_MATCH_MAX_TEXT_LENGTH]

    # 3. Compile with timeout (Python 3.11+) or plain compile
    flags = re.DOTALL
    compiled = None
    if sys.version_info >= (3, 11):
        try:
            compiled = re.compile(pattern, flags, timeout=timeout_ms / 1000.0)
        except TypeError:
            pass  # fallback below
        except re.error as e:
            raise ValidationError(f"Invalid regex pattern: {e}") from e
    if compiled is None:
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            raise ValidationError(f"Invalid regex pattern: {e}") from e

    # 4. Execute match
    try:
        return compiled.search(text)
    except TimeoutError:
        logger.error("Regex match timed out after %d ms for pattern: %s", timeout_ms, pattern[:80])
        raise ValidationError(f"Regex match exceeded {timeout_ms}ms timeout. Pattern may cause ReDoS.") from None
    except RecursionError:
        logger.error("Recursion depth exceeded during regex match for pattern: %s", pattern[:80])
        raise ValidationError("Regex match caused recursion overflow. Simplify the pattern.") from None


def detect_sql_injection(text: str) -> bool:
    """Detect common SQL injection patterns in text (audit-only helper).

    This function is **intended for logging / auditing only**. It does **not**
    replace parameterized queries or ORM usage. A ``True`` result means the
    text *looks like* it may contain SQL injection attempts — use this signal
    to trigger additional review or audit logging, never as a sole gatekeeper.

    Args:
        text: The input text to scan.

    Returns:
        ``True`` if any known SQL injection pattern is detected, else ``False``.
    """
    if not isinstance(text, str) or not text.strip():
        return False

    for pat in _SQL_INJECTION_PATTERNS:
        if pat.search(text):
            return True
    return False


def validate_path_safe(path: str) -> Path:
    """Validate that a file path is safe (no traversal, resolve symlinks).

    Checks:
    - Path traversal via ``..`` components.
    - Resolves symbolic links to their real target.
    - Returns the absolute, resolved path.

    Args:
        path: The path string to validate.

    Returns:
        A resolved :class:`pathlib.Path` object (absolute, no symlinks).

    Raises:
        ValidationError: If path traversal or other safety issues detected.
    """
    if not isinstance(path, str):
        raise ValidationError(f"validate_path_safe expects a string, got {type(path).__name__}")

    if not path.strip():
        raise ValidationError("Path cannot be empty.")

    # Check for null bytes (potential C-based injection)
    if "\x00" in path:
        raise ValidationError("Path contains null byte, which is not allowed.")

    # Convert to Path and expand user ~
    p = Path(path).expanduser()

    # Resolve to absolute path (follows symlinks)
    try:
        resolved = p.resolve(strict=False)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Cannot resolve path '{path}': {exc}") from exc

    # Check for path traversal: after resolution, detect if any component
    # tried to escape using .. by comparing with naive expansion
    parts = Path(path).expanduser().parts
    for part in parts:
        if part == "..":
            raise ValidationError(f"Path traversal detected in '{path}': '..' component is not allowed.")

    return resolved
