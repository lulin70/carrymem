"""Consolidation engine for CarryMem.

Implements memory lifecycle management:
- P0: Simple deduplication + time-based decay (pure rules, no LLM)
- P1: Pattern recognition + auto-promotion (integrates PromotionPipeline)

Inspired by AgentMemory's hourly consolidation, but adapted for
CarryMem's identity-layer focus (preferences, decisions, corrections).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from carrymem.utils.logger import Logger

logger = Logger("carrymem.consolidation")

DEDUP_WINDOW_HOURS = 24
DECAY_HALF_LIFE_DAYS = 90
MIN_CONFIDENCE_FOR_DECAY = 0.3
PREFERENCE_DECAY_MULTIPLIER = 3.0
FACT_DECAY_MULTIPLIER = 1.0
SENTIMENT_DECAY_MULTIPLIER = 0.5
SESSION_SUMMARY_DECAY_MULTIPLIER = 0.7
MAX_DUPLICATE_CONTENT_LENGTH = 200

TYPE_DECAY_MULTIPLIERS = {
    "user_preference": PREFERENCE_DECAY_MULTIPLIER,
    "personal_fact": FACT_DECAY_MULTIPLIER,
    "decision": FACT_DECAY_MULTIPLIER,
    "correction": FACT_DECAY_MULTIPLIER,
    "relationship": FACT_DECAY_MULTIPLIER,
    "task_pattern": FACT_DECAY_MULTIPLIER,
    "sentiment_marker": SENTIMENT_DECAY_MULTIPLIER,
    "session_summary": SESSION_SUMMARY_DECAY_MULTIPLIER,
}


def _content_hash(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content.lower().strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_words = set(re.findall(r"\b\w+\b", a.lower()))
    b_words = set(re.findall(r"\b\w+\b", b.lower()))
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    union = a_words | b_words
    return len(intersection) / len(union)


def compute_decay_factor(
    created_at: Any,
    memory_type: str,
    confidence: float,
    access_count: int = 0,
    now: Optional[datetime] = None,
) -> float:
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            return 1.0

    if not isinstance(created_at, datetime):
        return 1.0

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_days = max(0, (now - created_at).total_seconds() / 86400)

    multiplier = TYPE_DECAY_MULTIPLIERS.get(memory_type, FACT_DECAY_MULTIPLIER)
    effective_half_life = DECAY_HALF_LIFE_DAYS * multiplier

    import math

    decay = math.pow(0.5, age_days / effective_half_life)

    access_boost = min(0.2, access_count * 0.02)
    decay = min(1.0, decay + access_boost)

    if confidence < MIN_CONFIDENCE_FOR_DECAY:
        decay *= 0.7

    return round(max(0.0, min(1.0, decay)), 4)


def find_duplicates(
    memories: List[Dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
    if len(memories) < 2:
        return []

    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for m in memories:
        mtype = m.get("type", "unknown")
        by_type.setdefault(mtype, []).append(m)

    duplicates = []
    for mtype, group in by_type.items():
        if mtype == "session_summary":
            continue

        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a = group[i]
                b = group[j]

                if a.get("superseded_at") or b.get("superseded_at"):
                    continue

                content_a = a.get("content", "")[:MAX_DUPLICATE_CONTENT_LENGTH]
                content_b = b.get("content", "")[:MAX_DUPLICATE_CONTENT_LENGTH]

                if not content_a or not content_b:
                    continue

                sim = _similarity(content_a, content_b)
                if sim >= similarity_threshold:
                    duplicates.append((a, b, sim))

    return duplicates


def find_superseded_pairs(
    memories: List[Dict[str, Any]],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    by_key_prefix: Dict[str, List[Dict[str, Any]]] = {}
    for m in memories:
        if m.get("superseded_at"):
            continue
        content = m.get("content", "")
        mtype = m.get("type", "unknown")
        prefix = f"{mtype}:{_content_hash(content[:100])}"
        by_key_prefix.setdefault(prefix, []).append(m)

    pairs = []
    for prefix, group in by_key_prefix.items():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda m: m.get("created_at", ""))
        for i in range(len(sorted_group) - 1):
            older = sorted_group[i]
            newer = sorted_group[i + 1]
            if older.get("type") == newer.get("type"):
                sim = _similarity(
                    older.get("content", ""),
                    newer.get("content", ""),
                )
                if sim >= 0.7:
                    pairs.append((older, newer))

    return pairs


def consolidate(
    memories: List[Dict[str, Any]],
    now: Optional[datetime] = None,
    similarity_threshold: float = 0.85,
) -> Dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    result = {
        "timestamp": now.isoformat(),
        "input_count": len(memories),
        "to_supersede": [],
        "to_decay": [],
        "to_forget": [],
        "stats": {
            "duplicates_found": 0,
            "superseded_pairs": 0,
            "decayed_below_threshold": 0,
            "preferences_preserved": 0,
        },
    }

    active = [m for m in memories if not m.get("superseded_at")]

    duplicates = find_duplicates(active, similarity_threshold)
    result["stats"]["duplicates_found"] = len(duplicates)

    for older, newer, sim in duplicates:
        if older.get("type") == "user_preference":
            result["stats"]["preferences_preserved"] += 1
            continue
        result["to_supersede"].append(
            {
                "older_key": older.get("storage_key"),
                "newer_key": newer.get("storage_key"),
                "similarity": round(sim, 3),
                "type": older.get("type"),
                "reason": "duplicate_content",
            }
        )

    superseded_pairs = find_superseded_pairs(active)
    result["stats"]["superseded_pairs"] = len(superseded_pairs)
    for older, newer in superseded_pairs:
        already_listed = any(s["older_key"] == older.get("storage_key") for s in result["to_supersede"])
        if not already_listed:
            result["to_supersede"].append(
                {
                    "older_key": older.get("storage_key"),
                    "newer_key": newer.get("storage_key"),
                    "type": older.get("type"),
                    "reason": "updated_content",
                }
            )

    for m in active:
        mtype = m.get("type", "unknown")
        if mtype == "user_preference":
            continue

        created_at = m.get("created_at")
        confidence = m.get("confidence", 0.5)
        access_count = m.get("access_count", 0)

        decay = compute_decay_factor(created_at, mtype, confidence, access_count, now)

        if decay < 0.1:
            result["to_forget"].append(
                {
                    "storage_key": m.get("storage_key"),
                    "type": mtype,
                    "decay": decay,
                    "reason": "decay_below_threshold",
                }
            )
            result["stats"]["decayed_below_threshold"] += 1
        elif decay < 0.5:
            result["to_decay"].append(
                {
                    "storage_key": m.get("storage_key"),
                    "type": mtype,
                    "decay": decay,
                    "current_confidence": confidence,
                }
            )

    return result


def consolidate_p1(
    memories: List[Dict[str, Any]],
    rule_storage: Any = None,
    auto_accept: bool = False,
) -> Dict[str, Any]:
    """P1: Pattern recognition + auto-promotion.

    Detects repeated patterns in memories and generates rule candidates
    via the PromotionPipeline. Requires a RuleStorage instance for
    persisting candidates.

    Args:
        memories: List of memory dicts (same format as P0 input).
        rule_storage: RuleStorage instance. If None, P1 is skipped.
        auto_accept: If True, auto-accept all generated candidates.

    Returns:
        Dictionary with P1 promotion results.
    """
    result: Dict[str, Any] = {
        "p1_enabled": rule_storage is not None,
        "patterns_found": 0,
        "candidates_generated": 0,
        "candidates_queued": 0,
        "candidates_auto_accepted": 0,
    }

    if rule_storage is None:
        result["p1_skipped_reason"] = "no_rule_storage"
        return result

    if not memories:
        return result

    try:
        from carrymem.rules.promotion_pipeline import PromotionPipeline

        pipeline = PromotionPipeline(storage=rule_storage)
        p1_result = pipeline.run_pipeline(
            memories=memories,
            auto_accept=auto_accept,
        )
        result.update(p1_result)
    except Exception as e:
        result["p1_error"] = str(e)
        logger.warning(f"P1 consolidation failed: {e}")

    return result


def consolidate_p2(
    memories: List[Dict[str, Any]],
    p0_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """P2: Semantic consolidation via host LLM (borrow-host pattern).

    When P0 detects duplicate or superseded memories, P2 prepares
    consolidation requests for the host LLM. The host LLM generates
    merged summaries, which are then stored via classify_and_remember.

    This follows the "borrow host LLM" pattern: CarryMem returns the
    content that needs merging, the host AI generates a consolidated
    summary, then calls classify_and_remember to store it.

    Args:
        memories: List of memory dicts (same format as P0 input).
        p0_report: P0 consolidation report (from consolidate()).
            If None, P2 will run its own duplicate detection.

    Returns:
        Dictionary with P2 consolidation requests for the host LLM.
    """
    result: Dict[str, Any] = {
        "p2_enabled": True,
        "consolidation_requests": [],
        "stats": {
            "clusters_found": 0,
            "memories_to_consolidate": 0,
            "preferences_preserved": 0,
        },
    }

    if not memories:
        return result

    active = [m for m in memories if not m.get("superseded_at")]

    clusters = _find_semantic_clusters(active)

    result["stats"]["clusters_found"] = len(clusters)

    for cluster in clusters:
        has_preference = any(m.get("type") == "user_preference" for m in cluster)
        if has_preference:
            result["stats"]["preferences_preserved"] += 1
            continue

        content_parts = []
        for m in cluster:
            text = m.get("content", "") or m.get("raw_text", "")
            mtype = m.get("type", "unknown")
            created = m.get("created_at", "")
            content_parts.append(f"[{mtype}] ({created[:10] if created else 'unknown'}) {text}")

        source_keys = [m.get("storage_key", "") for m in cluster]
        dominant_type = max(
            set(m.get("type", "") for m in cluster),
            key=lambda t: sum(1 for m in cluster if m.get("type") == t),
        )

        request = {
            "action": "consolidate",
            "source_keys": source_keys,
            "dominant_type": dominant_type,
            "content": "\n".join(content_parts),
            "memory_count": len(cluster),
            "instruction": (
                "The above are related memories about the same topic. "
                "Merge them into a single concise statement that captures "
                "all key information, noting any changes over time. "
                "Then call classify_and_remember with the merged content, "
                f"setting the type to '{dominant_type}'."
            ),
        }
        result["consolidation_requests"].append(request)
        result["stats"]["memories_to_consolidate"] += len(cluster)

    if p0_report:
        for item in p0_report.get("to_supersede", []):
            older_key = item.get("older_key")
            newer_key = item.get("newer_key")
            if not older_key or not newer_key:
                continue

            older_mem = next((m for m in active if m.get("storage_key") == older_key), None)
            newer_mem = next((m for m in active if m.get("storage_key") == newer_key), None)

            if not older_mem or not newer_mem:
                continue

            if older_mem.get("type") == "user_preference":
                result["stats"]["preferences_preserved"] += 1
                continue

            already_requested = any(older_key in req.get("source_keys", []) for req in result["consolidation_requests"])
            if already_requested:
                continue

            content_parts = [
                f"[{older_mem.get('type', 'unknown')}] ({older_mem.get('created_at', '')[:10]}) {older_mem.get('content', '')}",
                f"[{newer_mem.get('type', 'unknown')}] ({newer_mem.get('created_at', '')[:10]}) {newer_mem.get('content', '')}",
            ]

            request = {
                "action": "consolidate_superseded",
                "source_keys": [older_key, newer_key],
                "dominant_type": newer_mem.get("type", "personal_fact"),
                "content": "\n".join(content_parts),
                "memory_count": 2,
                "instruction": (
                    "The above shows an older memory and its newer version. "
                    "Merge them into a single statement that reflects the "
                    "current state, noting the change. "
                    "Then call classify_and_remember with the merged content, "
                    f"setting the type to '{newer_mem.get('type', 'personal_fact')}'."
                ),
            }
            result["consolidation_requests"].append(request)
            result["stats"]["memories_to_consolidate"] += 2

    return result


def _find_semantic_clusters(
    memories: List[Dict[str, Any]],
    similarity_threshold: float = 0.65,
    min_cluster_size: int = 2,
    max_clusters: int = 10,
) -> List[List[Dict[str, Any]]]:
    """Find clusters of semantically similar memories using Jaccard similarity.

    This is a lightweight alternative to embedding-based clustering,
    suitable for P2 where we don't require an embedding model.
    """
    if len(memories) < min_cluster_size:
        return []

    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for m in memories:
        mtype = m.get("type", "unknown")
        if mtype in ("session_summary", "user_preference"):
            continue
        by_type.setdefault(mtype, []).append(m)

    all_clusters = []

    for mtype, group in by_type.items():
        if len(group) < min_cluster_size:
            continue

        n = len(group)
        adj: List[List[int]] = [[] for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                a_text = group[i].get("content", "")[:MAX_DUPLICATE_CONTENT_LENGTH]
                b_text = group[j].get("content", "")[:MAX_DUPLICATE_CONTENT_LENGTH]
                sim = _similarity(a_text, b_text)
                if sim >= similarity_threshold:
                    adj[i].append(j)
                    adj[j].append(i)

        visited = [False] * n
        for i in range(n):
            if visited[i]:
                continue
            component: List[int] = []
            stack = [i]
            while stack:
                node = stack.pop()
                if visited[node]:
                    continue
                visited[node] = True
                component.append(node)
                for neighbor in adj[node]:
                    if not visited[neighbor]:
                        stack.append(neighbor)

            if len(component) >= min_cluster_size:
                cluster = [group[idx] for idx in component]
                all_clusters.append(cluster)

        if len(all_clusters) >= max_clusters:
            break

    return all_clusters[:max_clusters]
