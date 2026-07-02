"""Memory formatting — format memory entries for AI prompt injection.

Extracted from context.py for modularity.

v0.5.2: Added `depth` parameter to format_memory_entry() for progressive
disclosure. depth=3 (default) preserves v0.5.1 behavior; depth=2/1 use
cached summary or rule-based fallback for token-efficient rendering.
"""

import re
from typing import Any, Dict, List

from carrymem.layers.summary_layer import RuleBasedSummarizer

_RULE_SUMMARIZER = RuleBasedSummarizer()

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
        r"\b((?:January|February|March|April|May|June|July|August"
        r"|September|October|November|December)\s+\d{1,2}"
        r"(?:,?\s*\d{4})?)\b",
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


def format_memory_entry(m: Dict[str, Any], language: str = "en", depth: int = 3) -> str:
    """Render a single memory entry as a human-readable string.

    Args:
        m: Memory dict with raw_text/content, type, and optionally cached summary.
        language: Language code for type labels ("en"/"zh"/"ja").
        depth: Rendering depth for progressive disclosure (v0.5.2).
            3 (default): full content — preserves v0.5.1 behavior.
            2: short summary — uses cached `summary` if available, else rule-based.
            1: ultra-short keywords — extracted from cached summary or raw_text.
    """
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
        # Outdated memories always show the NOTE prefix regardless of depth
        return f'- NOTE: "{content[:80]}" is outdated{time_tag}'

    # v0.5.2: Progressive disclosure — depth < 3 uses summary-based rendering
    if depth < 3:
        return _format_progressive(m, label, depth)

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


def _format_progressive(m: Dict[str, Any], label: str, depth: int) -> str:
    """Render a memory entry using progressive disclosure (v0.5.2).

    Uses cached `summary` field if available; otherwise generates a rule-based
    summary on-the-fly. No LLM calls — LLM summaries are pre-cached by
    SummaryLayer.summarize() at recall time.

    Args:
        m: Memory dict.
        label: Pre-resolved type label for the current language.
        depth: 1=keywords, 2=short summary.
    """
    cached_summary = m.get("summary")
    if cached_summary and depth >= 2:
        return f"- [{label}] {cached_summary}"
    if cached_summary and depth == 1:
        # Extract keywords from cached summary
        keywords = _RULE_SUMMARIZER._extract_keywords(cached_summary)
        if keywords:
            return f"- [{label}] {' '.join(keywords)}"
        return f"- [{label}] {cached_summary[:30].strip()}"
    # No cache — generate rule-based summary on-the-fly
    return f"- {_RULE_SUMMARIZER.summarize(m, level=depth)}"


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
    """Render a single knowledge entry as a human-readable string."""
    title = k.get("title", "Untitled")
    content = k.get("content", "")[:200]
    tags = k.get("tags", [])
    tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
    return f"- {title}{tag_str}: {content}"
