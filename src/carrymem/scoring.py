"""Memory importance scoring — decay, reinforcement, and ranking.

Importance-based memory lifecycle management.

Every memory gets an importance_score that determines:
- Ranking order in recall results
- Selection priority for context injection
- Natural decay over time (old unused memories fade)
- Reinforcement on access (frequently used memories strengthen)

Formula:
    importance_score = confidence * type_weight * recency_factor * access_factor
"""

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Union

TYPE_WEIGHTS: Dict[str, float] = {
    "correction": 1.3,
    "decision": 1.2,
    "user_preference": 1.1,
    "fact_declaration": 1.0,
    "relationship": 1.0,
    "task_pattern": 0.9,
    "sentiment_marker": 0.3,
}

DEFAULT_TYPE_WEIGHT = 1.0

HALF_LIFE_DAYS = 30

RECENCY_FLOOR = 0.3


def _env_float(name: str, default: float) -> float:
    """Read a float from an env var, falling back to default on parse error."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


ACCESS_SCALE = _env_float("CARRYMEM_ACCESS_SCALE", 0.1)

ACCESS_SIGNAL_SCALE = _env_float("CARRYMEM_ACCESS_SIGNAL_SCALE", 0.2)

ACCESS_SIGNAL_WEIGHT = _env_float("CARRYMEM_ACCESS_SIGNAL_WEIGHT", 0.1)


@dataclass
class RecallBudget:
    """Constraints (count, confidence, importance, tokens, per-type quotas) for recall."""

    max_results: int = 20
    min_confidence: float = 0.0
    min_importance: float = 0.0
    max_tokens: int = 4000
    type_quotas: Dict[str, int] = field(
        default_factory=lambda: {
            "correction": 5,
            "decision": 5,
            "user_preference": 10,
            "fact_declaration": 15,
            "relationship": 5,
            "task_pattern": 3,
            "sentiment_marker": 2,
            "session_summary": 3,
        }
    )

    def allows(self, memory_type: str, confidence: float, importance: float) -> bool:
        """Return whether a memory meets the minimum confidence and importance."""
        if confidence < self.min_confidence:
            return False
        if importance < self.min_importance:
            return False
        return True

    def quota_for(self, memory_type: str) -> int:
        """Return the per-type result quota, falling back to ``max_results``."""
        return self.type_quotas.get(memory_type, self.max_results)


def type_weight(memory_type: str) -> float:
    """Return the type-based weight multiplier for a memory type."""
    return TYPE_WEIGHTS.get(memory_type, DEFAULT_TYPE_WEIGHT)


def recency_factor(created_at: Union[str, datetime], now: Optional[datetime] = None) -> float:
    """Return a 0.3–1.0 recency multiplier based on age since ``created_at``."""
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(created_at, str):
        try:
            from datetime import datetime as _dt

            created_at = _dt.fromisoformat(created_at)
        except (ValueError, TypeError):
            return 1.0

    if not isinstance(created_at, datetime):
        return 1.0  # type: ignore[unreachable]

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_days = max(0, (now - created_at).total_seconds() / 86400)
    return RECENCY_FLOOR + (1.0 - RECENCY_FLOOR) * (0.5 ** (age_days / HALF_LIFE_DAYS))  # type: ignore[no-any-return]


def access_factor(access_count: int) -> float:
    """Return a logarithmic access-reinforcement multiplier for the access count."""
    return 1.0 + math.log(1 + max(0, access_count)) * ACCESS_SCALE


def calculate_importance(
    confidence: float,
    memory_type: str,
    created_at: datetime,
    access_count: int = 0,
    now: Optional[datetime] = None,
) -> float:
    """Compute an importance score from confidence, type, recency, and access."""
    tw = type_weight(memory_type)
    rf = recency_factor(created_at, now)
    af = access_factor(access_count)
    score = confidence * tw * rf * af
    return round(score, 6)


def recalculate_confidence(
    base_confidence: float,
    fts_rank: float = 0.0,
    access_count: int = 0,
    created_at: Optional[Union[str, datetime]] = None,
    now: Optional[datetime] = None,
) -> float:
    """Blend base confidence with FTS rank, access, and recency signals."""
    if now is None:
        now = datetime.now(timezone.utc)

    rank_signal = min(1.0, fts_rank / 10.0) if fts_rank > 0 else 0.0

    access_signal = min(1.0, math.log(1 + access_count) * ACCESS_SIGNAL_SCALE) if access_count > 0 else 0.0

    recency_signal = 0.0
    if created_at:
        if isinstance(created_at, str):
            try:
                from datetime import datetime as _dt

                created_at = _dt.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = None
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at:
            age_days = max(0, (now - created_at).total_seconds() / 86400)
            recency_signal = max(0.0, 1.0 - age_days / 365.0)

    confidence = base_confidence * 0.5 + rank_signal * 0.3 + access_signal * ACCESS_SIGNAL_WEIGHT + recency_signal * 0.1
    return round(max(0.0, min(1.0, confidence)), 6)


def recalculate_importance(
    confidence: float,
    memory_type: str,
    created_at: datetime,
    access_count: int,
    now: Optional[datetime] = None,
) -> float:
    """Recompute importance after confidence/access updates."""
    return calculate_importance(
        confidence=confidence,
        memory_type=memory_type,
        created_at=created_at,
        access_count=access_count,
        now=now,
    )
