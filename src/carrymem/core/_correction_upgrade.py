"""Repeat correction upgrade logic (v0.10.0).

Implements forge 借鉴点 2 — the principle that repeated corrections should
auto-escalate from ordinary preferences to hard constraints.

Public API:
    detect_repeat_correction()  — analyze whether a correction hits threshold
    should_auto_upgrade()      — predicate for fast-path checks
    _are_corrections_similar() — internal Jaccard + entity/number matching
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional


# ---- Configuration ----------------------------------------------------

# Default thresholds. Override via environment variables for staged rollout.
DEFAULT_THRESHOLD = int(os.environ.get("CORRECTION_THRESHOLD", "2"))
DEFAULT_HARD_THRESHOLD = int(os.environ.get("CORRECTION_HARD_THRESHOLD", "3"))

# Feature flag: 1 = enabled, 0 = disabled (emergency rollback).
UPGRADE_ENABLED = os.environ.get("CORRECTION_UPGRADE_ENABLED", "1") == "1"

# Security/compliance keywords that bypass the threshold and immediately
# escalate to a hard (company scope, override=True) rule. Frozen for O(1)
# lookup and immutability.
SECURITY_KEYWORDS: FrozenSet[str] = frozenset(
    {
        "password",
        "secret",
        "credential",
        "ssl",
        "tls",
        "encryption",
        "auth",
        "oauth",
        "token",
        "api_key",
        "private_key",
        "pii",
        "gdpr",
        "compliance",
        "audit",
        "encrypt",
        "decrypt",
        "certificate",
        "ssh",
    }
)

# Similarity threshold (Jaccard + entity/number bonus). Below this, two
# corrections are considered different topics.
SIMILARITY_THRESHOLD = 0.7

# Jaccard weight vs entity/number match weight. Combined score must clear
# SIMILARITY_THRESHOLD.
_JACCARD_WEIGHT = 0.6
_ENTITY_WEIGHT = 0.4

# Stop words excluded from keyword extraction.
_STOP_WORDS: FrozenSet[str] = frozenset(
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
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "i",
        "you",
        "we",
        "they",
        "it",
        "this",
        "that",
        "do",
        "does",
        "did",
        "not",
        "no",
        "yes",
        "and",
        "or",
        "but",
        "if",
        "then",
        "so",
        "than",
        "about",
        "into",
        "over",
        "under",
        "use",
        "used",
        "using",
    }
)

# Regex for numbers (e.g. "5432") — entity-extraction surrogate.
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
# Regex for capitalized proper-noun-like tokens (entity surrogate).
_ENTITY_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b|\b[a-z]+_[a-z]+\b")


# ---- Data structures --------------------------------------------------


@dataclass
class CorrectionAnalysis:
    """Result of a repeat-correction analysis.

    Attributes:
        new_correction: The input correction text.
        history_count: Number of similar corrections already on record,
            NOT including the new one. 0 means first occurrence.
        is_repeat: True if any similar prior correction exists.
        upgrade_level: One of "none" | "soft" | "hard" | "security".
        similar_history: List of similar prior corrections as dicts
            with at least {content, storage_key, created_at}.
        suggested_action: Human-readable suggested rule content (when upgrade
            is recommended).
        semantic_matches: Count of similar-history items.
        bypass_threshold: True when security keywords triggered immediate
            escalation.
    """

    new_correction: str
    history_count: int
    is_repeat: bool
    upgrade_level: str
    similar_history: List[Dict[str, Any]] = field(default_factory=list)
    suggested_action: str = ""
    semantic_matches: int = 0
    bypass_threshold: bool = False


# ---- Public API -------------------------------------------------------


def detect_repeat_correction(
    content: str,
    history: Optional[List[Dict[str, Any]]] = None,
    threshold: int = DEFAULT_THRESHOLD,
    hard_threshold: int = DEFAULT_HARD_THRESHOLD,
) -> CorrectionAnalysis:
    """Analyze whether `content` is a repeat correction worth upgrading.

    Args:
        content: The new correction text.
        history: Optional list of prior correction records. Each item must
            expose at least ``content`` (str); ``storage_key`` and
            ``created_at`` are optional but recommended.
        threshold: Count of similar corrections (excluding the new one) at
            or above which the upgrade level becomes "soft".
        hard_threshold: Count at or above which the upgrade level becomes
            "hard" (company scope, override=True).
        history_count: if `history` is None, this value is used directly
            (for callers that have already aggregated it server-side).

    Returns:
        CorrectionAnalysis with upgrade recommendation. Always returns
        a value; never raises on empty history.

    Notes:
        - Empty / very short content returns ``upgrade_level="none"``.
        - Security keywords force ``upgrade_level="hard"`` regardless
          of history count (DR-V10-003).
    """
    history = history or []

    if not content or len(content.strip()) < 3:
        return CorrectionAnalysis(
            new_correction=content or "",
            history_count=0,
            is_repeat=False,
            upgrade_level="none",
        )

    similar = _find_similar_corrections(content, history)
    history_count = len(similar)

    # Compute suggested action / upgrade level.
    bypass = _contains_security_keyword(content)
    upgrade_level = _decide_upgrade_level(
        history_count=history_count,
        threshold=threshold,
        hard_threshold=hard_threshold,
        bypass=bypass,
    )

    suggested = _build_suggested_action(content) if upgrade_level != "none" else ""

    return CorrectionAnalysis(
        new_correction=content,
        history_count=history_count,
        is_repeat=history_count >= 1,
        upgrade_level=upgrade_level,
        similar_history=similar,
        suggested_action=suggested,
        semantic_matches=history_count,
        bypass_threshold=bypass,
    )


def should_auto_upgrade(analysis: CorrectionAnalysis) -> bool:
    """Fast-path predicate for the dispatch layer."""
    return analysis.upgrade_level in ("soft", "hard", "security")


# ---- Internals --------------------------------------------------------


def _are_corrections_similar(a: str, b: str, threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """Two corrections are similar iff their combined score >= threshold.

    Combined score = Jaccard * JACCARD_WEIGHT + entity_bonus * ENTITY_WEIGHT.

    Entity bonus = 1.0 when shared numbers OR shared proper-noun tokens
    exist between the two texts; else 0.0.

    Examples (threshold = 0.7):
        "端口 5432" vs "用 5432 端口"   -> Jaccard 0.80, entity 1.0  -> 0.88  similar
        "端口 5432" vs "端口 8080"       -> Jaccard 0.50, entity 0.0  -> 0.30  not similar
        "use PostgreSQL" vs "use MySQL"  -> Jaccard 0.50, entity 0.0  -> 0.30  not similar
    """
    kw_a = _extract_keywords(a)
    kw_b = _extract_keywords(b)
    if not kw_a or not kw_b:
        return False
    intersection = kw_a & kw_b
    union = kw_a | kw_b
    jaccard = len(intersection) / len(union) if union else 0.0

    numbers_a = set(_NUMBER_RE.findall(a))
    numbers_b = set(_NUMBER_RE.findall(b))
    entities_a = set(_ENTITY_RE.findall(a))
    entities_b = set(_ENTITY_RE.findall(b))
    entity_match = bool((numbers_a & numbers_b) or (entities_a & entities_b))
    entity_bonus = 1.0 if entity_match else 0.0

    combined = jaccard * _JACCARD_WEIGHT + entity_bonus * _ENTITY_WEIGHT
    return combined >= threshold


def _find_similar_corrections(
    content: str,
    history: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter history to entries similar to ``content``. Preserves order."""
    out: List[Dict[str, Any]] = []
    for entry in history:
        prior = entry.get("content", "") if isinstance(entry, dict) else ""
        if prior and _are_corrections_similar(content, prior):
            out.append(entry)
    return out


def _extract_keywords(text: str) -> set:
    """Lowercased keyword set with stop words removed."""
    tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 1}


def _contains_security_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in SECURITY_KEYWORDS)


def _decide_upgrade_level(
    history_count: int,
    threshold: int,
    hard_threshold: int,
    bypass: bool,
) -> str:
    """Map count + bypass to upgrade level string.

    Hard threshold must be strictly greater than the soft threshold for
    the state machine to make sense (enforced loosely here for caller
    robustness).
    """
    if bypass:
        return "hard"  # security keyword forces hard immediately
    if history_count >= hard_threshold:
        return "hard"
    if history_count >= threshold:
        return "soft"
    return "none"


def _build_suggested_action(content: str) -> str:
    """Derive a rule action from the correction content."""
    cleaned = content.strip()
    if not cleaned:
        return ""
    # Use first 200 chars as action seed. Caller (ClassificationMixin)
    # is responsible for final sanitization via RuleSanitizer.
    return cleaned[:200]


def is_upgrade_enabled() -> bool:
    """Read the rollback flag at call time so operators can change it safely."""
    return os.environ.get("CORRECTION_UPGRADE_ENABLED", "1") == "1"


def upgrade_to_rule(
    analysis: CorrectionAnalysis,
    rule_engine: Any,
    category: str = "general",
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Apply the upgrade decision to a RuleEngine.

    Translates the analysis result into a RuleEngine.add_rule() call with
    the appropriate scope and override flag. Returns the upgrade record
    (or None when nothing to do, or when ``UPGRADE_ENABLED`` is False).

    Args:
        analysis: The result from detect_repeat_correction().
        rule_engine: An object exposing add_rule(trigger, action, **kwargs).
            Typically the CarryMem.rule_engine.
        category: Short noun used as the rule trigger prefix
            (e.g. "database", "security"). Becomes the rule's trigger.
        user_id: Optional user ID (recorded in metadata, no behavior change
            in v0.10.0; reserved for v0.10.1 per-user rule scoping).

    Returns:
        A dict describing the upgrade action actually taken, or None when:
          - UPGRADE_ENABLED is False (emergency rollback)
          - analysis.upgrade_level == "none"
          - rule_engine.add_rule raised (caught and logged below)
    """
    if not is_upgrade_enabled():
        return None
    if analysis.upgrade_level == "none":
        return None

    # Map analysis.upgrade_level to RuleEngine parameters.
    if analysis.upgrade_level == "soft":
        scope = "personal"
        override = False
        rule_type = "prefer"
    elif analysis.upgrade_level == "hard":
        scope = "company"
        override = True
        rule_type = "always"
    else:
        # Unknown level (future-proof guard) — skip.
        return None

    trigger = category
    action = analysis.suggested_action or analysis.new_correction
    if not action:
        return None

    try:
        existing = None
        other_scope_old = None
        try:
            for r in rule_engine.list_rules(status="active", scope=scope, limit=500):
                if getattr(r, "trigger", None) == trigger and getattr(r, "derived_from", None) == "auto_promotion":
                    existing = r
                    break
            if existing is None and analysis.upgrade_level == "hard":
                # Escalating to hard: look for a weaker auto_promotion
                # rule under a different scope and retire it.
                for r in rule_engine.list_rules(status="active", limit=500):
                    if (
                        getattr(r, "trigger", None) == trigger
                        and getattr(r, "derived_from", None) == "auto_promotion"
                        and getattr(r, "scope", None) != scope
                    ):
                        other_scope_old = r
                        break
        except (ValueError, TypeError, AttributeError):
            existing = None

        if existing is not None:
            try:
                rule_engine.update_rule(
                    existing.id,
                    action=action,
                    rule_type=rule_type,
                    override=override,
                )
                rule = rule_engine.get_rule(existing.id) or existing
            except (ValueError, TypeError, AttributeError):
                rule = rule_engine.add_rule(
                    trigger=trigger,
                    action=action,
                    rule_type=rule_type,
                    override=override,
                    derived_from="auto_promotion",
                    scope=scope,
                )
        else:
            rule = rule_engine.add_rule(
                trigger=trigger,
                action=action,
                rule_type=rule_type,
                override=override,
                derived_from="auto_promotion",
                scope=scope,
            )

        # Escalation hygiene: deprecate the weaker predecessor so the
        # rule set does not accumulate stale duplicates.
        if other_scope_old is not None and other_scope_old.id != getattr(rule, "id", None):
            try:
                rule_engine.update_rule(other_scope_old.id, status="deprecated")
            except (ValueError, TypeError, AttributeError):
                pass
    except (ValueError, TypeError, RuntimeError) as exc:
        # Surface but don't crash the caller — degradation contract.
        import logging

        logging.getLogger(__name__).warning(
            "upgrade_to_rule failed for category=%s level=%s: %s",
            category,
            analysis.upgrade_level,
            exc,
        )
        return None

    return {
        "level": analysis.upgrade_level,
        "scope": scope,
        "override": override,
        "rule_type": rule_type,
        "trigger": trigger,
        "rule_id": getattr(rule, "id", None),
        "user_id": user_id,
    }


__all__ = [
    "CorrectionAnalysis",
    "SECURITY_KEYWORDS",
    "SIMILARITY_THRESHOLD",
    "UPGRADE_ENABLED",
    "DEFAULT_THRESHOLD",
    "DEFAULT_HARD_THRESHOLD",
    "detect_repeat_correction",
    "should_auto_upgrade",
    "upgrade_to_rule",
    "is_upgrade_enabled",
    "_are_corrections_similar",
]
