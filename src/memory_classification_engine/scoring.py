"""Memory importance scoring — decay, reinforcement, and ranking.

v0.5.0: Importance-based memory lifecycle management.

Every memory gets an importance_score that determines:
- Ranking order in recall results
- Selection priority for context injection
- Natural decay over time (old unused memories fade)
- Reinforcement on access (frequently used memories strengthen)

Formula:
    importance_score = confidence * type_weight * recency_factor * access_factor
"""

import math
from datetime import datetime, timezone
from typing import Dict

TYPE_WEIGHTS: Dict[str, float] = {
    "correction": 1.3,
    "decision": 1.2,
    "user_preference": 1.1,
    "fact_declaration": 1.0,
    "relationship": 1.0,
    "task_pattern": 0.9,
    "sentiment_marker": 0.8,
}

DEFAULT_TYPE_WEIGHT = 1.0

HALF_LIFE_DAYS = 30

RECENCY_FLOOR = 0.3

ACCESS_SCALE = 0.1


def type_weight(memory_type: str) -> float:
    return TYPE_WEIGHTS.get(memory_type, DEFAULT_TYPE_WEIGHT)


def recency_factor(created_at: datetime, now: datetime = None) -> float:
    if now is None:
        now = datetime.now(timezone.utc)

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
