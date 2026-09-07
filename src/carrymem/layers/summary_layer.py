"""Summary Layer — field-level memory summaries + progressive disclosure.

v0.5.2 feature: generates per-memory summary caches for token-efficient
prompt injection. Rule-based by default (zero LLM), LLM optional.

Design: spec/v0.5.2_spec.md
"""

import os
import re
from typing import Any, Dict

# ── Config switches ───────────────────────────────────────────────

_SUMMARY_ENABLED_ENV = "CARRYMEM_SUMMARY_ENABLED"
_LLM_SUMMARY_ENV = "CARRYMEM_LLM_SUMMARY"
_TRAE_ENV_ENV = "CARRYMEM_ENV"
_TRAE_SESSION_ENV = "TRAE_SESSION_ID"

_MAX_SUMMARY_LENGTH = 500  # C22: prevent oversized LLM output
_MAX_KEYWORDS = 3  # level=1 keyword count
_MAX_SHORT_CHARS = 120  # level=2 max chars before truncation
_MAX_FIRST_SENTENCE_CHARS = 200  # first sentence extraction limit


def is_summary_enabled() -> bool:
    """Whether the summary layer is enabled (default: enabled)."""
    return os.environ.get(_SUMMARY_ENABLED_ENV, "1") != "0"


def is_llm_summary_enabled() -> bool:
    """Whether LLM summarization is enabled (default: disabled).

    Priority: CARRYMEM_LLM_SUMMARY env > TRAE env detection > False.
    """
    explicit = os.environ.get(_LLM_SUMMARY_ENV, "")
    if explicit == "1":
        return True
    if explicit == "0":
        return False
    # TRAE environment auto-detection
    if os.environ.get(_TRAE_ENV_ENV, "").lower() == "trae":
        return True
    if os.environ.get(_TRAE_SESSION_ENV):
        return True
    return False


# ── Rule-based summarizer (zero LLM) ──────────────────────────────

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "your",
        "his",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "and",
        "or",
        "but",
        "if",
        "because",
        "while",
        "although",
        "though",
        "unless",
        "until",
    }
)

_SENTENCE_END_RE = re.compile(r"[.!?。！？]\s*")
_TYPE_LABELS = {
    "user_preference": "Preference",
    "correction": "Correction",
    "decision": "Decision",
    "fact_declaration": "Fact",
    "relationship": "Relationship",
    "task_pattern": "Pattern",
    "sentiment_marker": "Sentiment",
    "session_summary": "Summary",
}


class RuleBasedSummarizer:
    """Zero-LLM summarizer with type-specific strategies.

    Level 1 (ultra-short): "[Label] keyword1 keyword2 keyword3"
    Level 2 (short):       "[Label] first sentence (truncated at 120 chars)"
    Level 3 (full):        returns raw_text unchanged
    """

    def summarize(self, memory: Dict[str, Any], level: int = 2) -> str:
        """Generate a rule-based summary.

        Args:
            memory: Memory dict with at least 'raw_text'/'content' and 'type'.
            level: 1=ultra-short, 2=short, 3=full.

        Returns:
            Summary string.
        """
        raw_text = memory.get("raw_text", "") or memory.get("content", "") or ""
        mtype = memory.get("type", "unknown")
        label = _TYPE_LABELS.get(mtype, mtype.title() if mtype else "Info")

        if level >= 3:
            return raw_text

        if not raw_text.strip():
            return f"[{label}]"

        if level == 1:
            keywords = self._extract_keywords(raw_text)
            if keywords:
                return f"[{label}] {' '.join(keywords)}"
            return f"[{label}] {raw_text[:_MAX_KEYWORDS * 10].strip()}"

        # level == 2: first sentence
        first_sentence = self._extract_first_sentence(raw_text, mtype)
        if len(first_sentence) > _MAX_SHORT_CHARS:
            first_sentence = first_sentence[:_MAX_SHORT_CHARS].rstrip() + "..."
        return f"[{label}] {first_sentence}"

    def _extract_first_sentence(self, text: str, mtype: str) -> str:
        """Extract the first meaningful sentence from text."""
        # Type-specific extraction
        if mtype == "decision":
            # Try to find content after "决定:" or "decided:"
            match = re.search(r"(?:决定|decided?)\s*[:：]\s*(.+)", text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Split by sentence endings
        parts = _SENTENCE_END_RE.split(text, maxsplit=1)
        first = parts[0].strip() if parts else text.strip()

        if len(first) > _MAX_FIRST_SENTENCE_CHARS:
            first = first[:_MAX_FIRST_SENTENCE_CHARS].rstrip() + "..."
        return first

    def _extract_keywords(self, text: str) -> list:
        """Extract top 3 content words (non-stopwords)."""
        words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", text.lower())
        keywords = []
        seen = set()
        for w in words:
            if w in _STOPWORDS or w in seen:
                continue
            seen.add(w)
            keywords.append(w)
            if len(keywords) >= _MAX_KEYWORDS:
                break
        return keywords
