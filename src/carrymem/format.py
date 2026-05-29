"""Memory formatting — format memory entries for AI prompt injection.

Extracted from context.py for modularity.
"""

import re
from typing import Any, Dict, List


TYPE_LABELS = {
    "en": {
        "user_preference": "Preference",
        "correction": "Correction",
        "decision": "Decision",
        "fact_declaration": "Fact",
        "relationship": "Relationship",
        "task_pattern": "Pattern",
        "sentiment_marker": "Sentiment",
    },
    "zh": {
        "user_preference": "偏好",
        "correction": "纠正",
        "decision": "决策",
        "fact_declaration": "事实",
        "relationship": "关系",
        "task_pattern": "模式",
        "sentiment_marker": "情感",
    },
    "ja": {
        "user_preference": "好み",
        "correction": "訂正",
        "decision": "決定",
        "fact_declaration": "事実",
        "relationship": "関係",
        "task_pattern": "パターン",
        "sentiment_marker": "感情",
    },
}


def _extract_event_dates(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s*\d{4})?)\b",
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}(?:,?\s*\d{4})?)\b",
        r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b",
    ]
    found = []
    for p in patterns:
        for match in re.finditer(p, text, re.IGNORECASE):
            date_str = match.group(1)
            if date_str not in found:
                found.append(date_str)
    return ", ".join(found) if found else ""


def format_memory_entry(m: Dict[str, Any], language: str = "en") -> str:
    labels = TYPE_LABELS.get(language, TYPE_LABELS["en"])
    label = labels.get(m.get("type", ""), m.get("type", "Info"))
    content = m.get("raw_text", "") or m.get("content", "")
    superseded_at = m.get("superseded_at")
    mtype = m.get("type", "")
    auto_rule = m.get("auto_rule", "")
    confidence = m.get("confidence", 0)

    time_tag = ""
    event_dates = _extract_event_dates(content)
    if event_dates:
        time_tag = f" (event: {event_dates})"
    else:
        created = m.get("created_at", "")
        if created:
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(created)
                time_tag = f" ({dt.strftime('%Y-%m-%d')})"
            except (ValueError, TypeError):
                pass

    if superseded_at:
        return f'- NOTE: "{content[:80]}" is outdated{time_tag}'

    if mtype == "user_preference" and auto_rule == "avoid":
        return f"- [IMPORTANT] The user does NOT want: {content}"
    if mtype == "user_preference" and auto_rule == "prefer":
        return f"- [IMPORTANT] The user prefers: {content}"
    if mtype == "user_preference":
        return f"- [IMPORTANT] The user prefers: {content}"
    if mtype == "correction":
        return f"- Do NOT repeat: {content} — the user has corrected this before{time_tag}"
    if mtype == "decision":
        return f"- Always follow: {content} — this is the user's confirmed decision{time_tag}"
    if mtype == "session_summary":
        return f"- Based on previous conversations: {content}{time_tag}"

    tag = ""
    if mtype in ("correction", "decision"):
        tag = " [MANDATORY]"
    elif mtype == "user_preference" and confidence >= 0.8:
        tag = " [IMPORTANT]"

    return f"- [{label}{tag}] {content}{time_tag}"


def _build_superseded_notes(memories: List[Dict[str, Any]], language: str = "en") -> List[str]:
    notes = []
    seen_pairs = set()
    for m in memories:
        supersedes = m.get("supersedes")
        if not supersedes:
            continue
        old_content = m.get("raw_text", "") or m.get("content", "")
        for new_m in memories:
            if new_m.get("storage_key") == supersedes or new_m.get("id") == supersedes:
                new_content = new_m.get("raw_text", "") or new_m.get("content", "")
                pair_key = (m.get("storage_key", ""), new_m.get("storage_key", ""))
                if pair_key in seen_pairs:
                    break
                seen_pairs.add(pair_key)
                if language == "zh":
                    notes.append(f'- 更新："{old_content[:60]}" → "{new_content[:60]}"')
                else:
                    notes.append(f'- Updated: "{old_content[:60]}" → "{new_content[:60]}"')
                break
    return notes


def format_knowledge_entry(k: Dict[str, Any]) -> str:
    title = k.get("title", "Untitled")
    content = k.get("content", "")[:200]
    tags = k.get("tags", [])
    tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
    return f"- {title}{tag_str}: {content}"
