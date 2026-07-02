"""Summary Layer — field-level memory summaries + progressive disclosure.

v0.5.2 feature: generates per-memory summary caches for token-efficient
prompt injection. Rule-based by default (zero LLM), LLM optional.

Design: spec/v0.5.2_spec.md
"""

import os
import re
from typing import Any, Dict, Optional, cast

from carrymem.utils.logger import logger

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
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after",
        "above", "below", "up", "down", "out", "off", "over", "under",
        "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "each", "every", "both", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "just",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their",
        "this", "that", "these", "those", "and", "or", "but", "if",
        "because", "while", "although", "though", "unless", "until",
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


# ── Summary layer (LLM optional, caching) ─────────────────────────

_LLM_PROMPT_TEMPLATE = """Summarize the following memory in one concise sentence (max 50 words).
Keep key facts, preferences, or decisions. Remove filler words.

<memory_data>
{raw_text}
</memory_data>

Output only the summary, no preamble."""


class SummaryLayer:
    """Summary layer with LLM support + caching.

    Rule-based by default. LLM enabled via CARRYMEM_LLM_SUMMARY=1 or TRAE env.
    Caches to memories.summary field. No TTL — invalidated on raw_text update.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        input_validator: Optional[Any] = None,
    ):
        self._llm = llm_client
        self._input_validator = input_validator
        self._rule_summarizer = RuleBasedSummarizer()

    def summarize(
        self,
        memory: Dict[str, Any],
        level: int = 2,
        force: bool = False,
    ) -> str:
        """Generate or retrieve cached summary.

        Args:
            memory: Memory dict with raw_text/content, type, and optionally
                    cached summary/summary_level.
            level: 1=ultra-short, 2=short, 3=full(returns raw_text).
            force: Regenerate even if cache exists.

        Returns:
            Summary string.
        """
        if level >= 3:
            return memory.get("raw_text", "") or memory.get("content", "") or ""

        if not is_summary_enabled():
            return self._rule_summarizer.summarize(memory, level)

        # Check cache (level 2 cache serves level 1 too)
        cached_summary = memory.get("summary")
        cached_level = memory.get("summary_level")
        if cached_summary and cached_level and cached_level >= level and not force:
            return self._format_cached(cached_summary, memory, level)

        # Generate new summary at level 2 (most useful for caching)
        summary = self._generate(memory, target_level=2)
        return self._format_for_level(summary, memory, level)

    def render_for_bucket(self, memory: Dict[str, Any], bucket: str) -> str:
        """Render memory for a prompt bucket using progressive disclosure.

        Args:
            memory: Memory dict.
            bucket: "mandatory", "important", "context", or "outdated".

        Returns:
            Rendered string for prompt injection.
        """
        depth_map = {
            "mandatory": 3,
            "important": 2,
            "context": 2,
            "outdated": 1,
        }
        depth = depth_map.get(bucket, 3)
        return self.summarize(memory, level=depth)

    def _generate(self, memory: Dict[str, Any], target_level: int = 2) -> str:
        """Generate summary: LLM if available, else rule-based."""
        raw_text = memory.get("raw_text", "") or memory.get("content", "") or ""

        if not raw_text.strip():
            return ""

        # Try LLM first (if enabled and available)
        if is_llm_summary_enabled() and self._llm and self._llm.is_available():
            try:
                llm_summary = self._llm_summarize(raw_text)
                if llm_summary:
                    return self._sanitize(llm_summary)[:_MAX_SUMMARY_LENGTH]
            except (ValueError, RuntimeError, AttributeError, ConnectionError) as e:
                logger.debug("LLM summary failed, falling back to rule-based: %s", e)

        # Rule-based fallback
        return self._rule_summarizer.summarize(memory, target_level)

    def _llm_summarize(self, raw_text: str) -> Optional[str]:
        """Call LLM to generate summary. C21: wrap in <memory_data> tags."""
        if self._llm is None:
            return None
        prompt = _LLM_PROMPT_TEMPLATE.format(raw_text=raw_text[:2000])
        result = cast(Optional[str], self._llm.chat(prompt))
        if result:
            return result.strip()
        return None

    def _sanitize(self, text: str) -> str:
        """C20: sanitize summary via InputValidator."""
        if self._input_validator is not None:
            try:
                return cast(str, self._input_validator.sanitize_content(text))
            except (ValueError, AttributeError, RuntimeError) as e:
                logger.debug("sanitize_content failed: %s", e)
        # Fallback: null-byte strip + whitespace strip
        return text.replace("\x00", "").strip()

    def _format_cached(self, cached: str, memory: Dict[str, Any], level: int) -> str:
        """Format a cached level-2 summary for the requested level."""
        if level >= 2:
            label = _TYPE_LABELS.get(memory.get("type", ""), "Info")
            return f"[{label}] {cached}"
        # level 1: extract keywords from cached summary
        return self._format_for_level(cached, memory, level)

    def _format_for_level(self, summary: str, memory: Dict[str, Any], level: int) -> str:
        """Format a level-2 summary for the requested level."""
        label = _TYPE_LABELS.get(memory.get("type", ""), "Info")
        if level >= 2:
            return f"[{label}] {summary}"
        # level 1: extract keywords from summary
        keywords = self._rule_summarizer._extract_keywords(summary)
        if keywords:
            return f"[{label}] {' '.join(keywords)}"
        return f"[{label}] {summary[:30].strip()}"


# ── Bucket depth mapping (for prompt.py integration) ──────────────

BUCKET_DEPTH = {
    "mandatory": 3,
    "important": 2,
    "context": 2,
    "outdated": 1,
}


def get_depth_for_bucket(bucket: str) -> int:
    """Get rendering depth for a prompt bucket.

    Args:
        bucket: "mandatory", "important", "context", or "outdated".

    Returns:
        3 for mandatory, 2 for important/context, 1 for outdated.
    """
    return BUCKET_DEPTH.get(bucket, 3)
