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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


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

ACCESS_SCALE = 0.1


@dataclass
class RecallBudget:
    max_results: int = 20
    min_confidence: float = 0.0
    min_importance: float = 0.0
    max_tokens: int = 4000
    type_quotas: Dict[str, int] = field(default_factory=lambda: {
        "correction": 5,
        "decision": 5,
        "user_preference": 10,
        "fact_declaration": 15,
        "relationship": 5,
        "task_pattern": 3,
        "sentiment_marker": 2,
        "session_summary": 3,
    })

    def allows(self, memory_type: str, confidence: float, importance: float) -> bool:
        if confidence < self.min_confidence:
            return False
        if importance < self.min_importance:
            return False
        return True

    def quota_for(self, memory_type: str) -> int:
        return self.type_quotas.get(memory_type, self.max_results)


def type_weight(memory_type: str) -> float:
    return TYPE_WEIGHTS.get(memory_type, DEFAULT_TYPE_WEIGHT)


def recency_factor(created_at, now: datetime = None) -> float:
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(created_at, str):
        try:
            from datetime import datetime as _dt
            created_at = _dt.fromisoformat(created_at)
        except (ValueError, TypeError):
            return 1.0

    if not isinstance(created_at, datetime):
        return 1.0

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_days = max(0, (now - created_at).total_seconds() / 86400)
    return RECENCY_FLOOR + (1.0 - RECENCY_FLOOR) * (0.5 ** (age_days / HALF_LIFE_DAYS))


def access_factor(access_count: int) -> float:
    return 1.0 + math.log(1 + max(0, access_count)) * ACCESS_SCALE


def calculate_importance(
    confidence: float,
    memory_type: str,
    created_at: datetime,
    access_count: int = 0,
    now: datetime = None,
) -> float:
    tw = type_weight(memory_type)
    rf = recency_factor(created_at, now)
    af = access_factor(access_count)
    score = confidence * tw * rf * af
    return round(score, 6)


def recalculate_confidence(
    base_confidence: float,
    fts_rank: float = 0.0,
    access_count: int = 0,
    created_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> float:
    if now is None:
        now = datetime.now(timezone.utc)

    rank_signal = min(1.0, fts_rank / 10.0) if fts_rank > 0 else 0.0

    access_signal = min(1.0, math.log(1 + access_count) * 0.2) if access_count > 0 else 0.0

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

    confidence = (
        base_confidence * 0.5
        + rank_signal * 0.3
        + access_signal * 0.1
        + recency_signal * 0.1
    )
    return round(max(0.0, min(1.0, confidence)), 6)


def recalculate_importance(
    confidence: float,
    memory_type: str,
    created_at: datetime,
    access_count: int,
    now: datetime = None,
) -> float:
    return calculate_importance(
        confidence=confidence,
        memory_type=memory_type,
        created_at=created_at,
        access_count=access_count,
        now=now,
    )
