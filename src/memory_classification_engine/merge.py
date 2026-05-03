"""Memory merge and conflict resolution for multi-agent scenarios.

v0.5.0: Detect and resolve conflicts when multiple agents/namespaces
store overlapping or contradictory memories.

Conflict detection:
- Same content_hash across different namespaces → hash conflict
- Same type + high text similarity (Levenshtein ratio > 0.8) → semantic conflict

Merge strategies:
- latest_wins: Keep the most recently updated memory
- highest_confidence: Keep the highest confidence memory
- merge_all: Keep all, mark duplicates with metadata
"""

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Tuple


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def detect_conflicts(
    memories: List[Dict[str, Any]],
    similarity_threshold: float = 0.8,
) -> List[List[Dict[str, Any]]]:
    if not memories:
        return []

    by_hash: Dict[str, List[Dict[str, Any]]] = {}
    for m in memories:
        ch = m.get("content_hash", "")
        if ch:
            by_hash.setdefault(ch, []).append(m)

    conflicts = [group for group in by_hash.values() if len(group) > 1]

    seen_ids: set = set()
    for group in conflicts:
        for m in group:
            seen_ids.add(m.get("storage_key", m.get("id", "")))

    remaining = [m for m in memories if m.get("storage_key", m.get("id", "")) not in seen_ids]

    semantic_groups: List[List[Dict[str, Any]]] = []
    used_indices: set = set()

    for i, m1 in enumerate(remaining):
        if i in used_indices:
            continue
        group = [m1]
        for j in range(i + 1, len(remaining)):
            if j in used_indices:
                continue
            m2 = remaining[j]
            if m1.get("type") == m2.get("type"):
                sim = _similarity(m1.get("content", ""), m2.get("content", ""))
                if sim >= similarity_threshold:
                    group.append(m2)
                    used_indices.add(j)
        if len(group) > 1:
            semantic_groups.append(group)
            used_indices.add(i)

    conflicts.extend(semantic_groups)
    return conflicts


def merge_memories(
    memories: List[Dict[str, Any]],
    strategy: str = "latest_wins",
    conflict_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    if not memories:
        return []

    conflicts = detect_conflicts(memories)

    if conflict_callback:
        for group in conflicts:
            conflict_callback(group)

    conflict_keys: set = set()
    for group in conflicts:
        for m in group:
            conflict_keys.add(m.get("storage_key", m.get("id", "")))

    non_conflict = [
        m for m in memories
        if m.get("storage_key", m.get("id", "")) not in conflict_keys
    ]

    resolved = []
    for group in conflicts:
        if strategy == "latest_wins":
            winner = max(
                group,
                key=lambda m: m.get("updated_at", m.get("created_at", "")),
            )
            resolved.append(winner)

        elif strategy == "highest_confidence":
            winner = max(group, key=lambda m: m.get("confidence", 0.0))
            resolved.append(winner)

        elif strategy == "merge_all":
            for m in group:
                m_copy = dict(m)
                duplicates = [
                    other.get("storage_key", other.get("id", ""))
                    for other in group
                    if other is not m
                ]
                m_copy["_duplicates"] = duplicates
                m_copy["_conflict_resolved"] = False
                resolved.append(m_copy)
        else:
            resolved.append(group[0])

    return non_conflict + resolved
