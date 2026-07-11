"""Memify engine — dynamic memory refinement (v0.7.2).

Three-phase memory consolidation inspired by Cognee's Memify:
  1. derive_facts — find frequently co-occurring entity pairs, create derived memories
  2. reinforce_edges — increment graph relation weights for co-occurring entities
  3. auto_decay — reduce importance of stale, low-access memories

Design principles (per V071_V072_PLAN.md §4.2):
  - Zero LLM: pure SQL analysis of entity co-occurrence
  - Conservative: three-way gate for decay (stale + low importance + zero access)
  - Surgical: uses metadata JSON for decay marking, does not alter tier column
  - Namespace isolated: all operations scoped per namespace
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List

from carrymem.utils.logger import logger

if TYPE_CHECKING:
    from carrymem.adapters.sqlite import SQLiteAdapter


class MemifyEngine:
    """Dynamic memory refinement engine (v0.7.2).

    Analyzes entity co-occurrence patterns and memory access patterns to
    derive new facts, reinforce graph edges, and decay stale memories.
    Requires SQLite adapter with knowledge graph tables (v0.7.0+).
    """

    def __init__(self, adapter: "SQLiteAdapter"):
        """Initialize the Memify engine.

        Args:
            adapter: SQLiteAdapter instance with knowledge graph support.
        """
        self._adapter = adapter

    # ── Phase 1: Derive Facts ──────────────────────────────────────

    def derive_facts(
        self,
        namespace: str = "default",
        min_co_occurrence: int = 3,
        max_derived: int = 10,
    ) -> List[Dict[str, Any]]:
        """Derive new facts from frequently co-occurring entities.

        Analyzes memory_entities to find entity pairs that co-occur in
        >=min_co_occurrence memories. For each pair, creates a derived
        "relationship" memory via store_entry.

        Args:
            namespace: Namespace scope.
            min_co_occurrence: Minimum co-occurrence count (default 3).
            max_derived: Maximum derived facts per run (default 10).

        Returns:
            List of derived memory dicts with type="relationship".
        """
        from carrymem.adapters.base import MemoryEntry

        pairs = self._find_co_occurring_pairs(namespace, min_co_occurrence, max_derived)
        if not pairs:
            return []

        derived: List[Dict[str, Any]] = []
        for e1, e2, count in pairs:
            content = f"{e1} and {e2} frequently co-occur ({count} times)"
            entry = MemoryEntry(
                id=f"derived_{e1}_{e2}_{count}",
                type="relationship",
                content=content,
                raw_text=content,
                confidence=min(0.6, 0.3 + count * 0.05),
                metadata={"derived": True, "co_occurrence": count, "entities": [e1, e2]},
            )
            try:
                stored = self._adapter.store_entry(entry)
                derived.append(stored.to_dict())
            except (ValueError, RuntimeError, sqlite3.Error) as e:
                logger.warning("derive_facts: failed to store derived fact for %s+%s: %s", e1, e2, e)

        logger.info("derive_facts: created %d derived facts (namespace=%s)", len(derived), namespace)
        return derived

    # ── Phase 2: Reinforce Edges ──────────────────────────────────

    def reinforce_edges(
        self,
        namespace: str = "default",
        min_co_occurrence: int = 3,
        weight_increment: float = 0.1,
        max_weight: float = 2.0,
    ) -> int:
        """Reinforce graph edges based on entity co-occurrence.

        For entity pairs that co-occur in >=min_co_occurrence memories,
        increments the weight of their relation in memory_relations.
        Creates a "co_occurs" relation if none exists.

        Args:
            namespace: Namespace scope.
            min_co_occurrence: Minimum co-occurrence to trigger reinforcement.
            weight_increment: Weight increment per reinforcement (default 0.1).
            max_weight: Maximum weight cap (default 2.0).

        Returns:
            Number of edges reinforced or created.
        """
        pairs = self._find_co_occurring_pairs(namespace, min_co_occurrence, max_derived=100)
        if not pairs:
            return 0

        conn = self._adapter._get_connection()
        reinforced = 0

        for e1, e2, count in pairs:
            e1_ids = conn.execute(
                "SELECT id FROM memory_entities WHERE entity_text = ? AND namespace = ?",
                (e1, namespace),
            ).fetchall()
            e2_ids = conn.execute(
                "SELECT id FROM memory_entities WHERE entity_text = ? AND namespace = ?",
                (e2, namespace),
            ).fetchall()

            if not e1_ids or not e2_ids:
                continue

            e1_id = e1_ids[0]["id"]
            e2_id = e2_ids[0]["id"]

            existing = conn.execute(
                """SELECT id, weight FROM memory_relations
                   WHERE src_entity_id = ? AND dst_entity_id = ?
                     AND relation_type = 'co_occurs' AND namespace = ?""",
                (e1_id, e2_id, namespace),
            ).fetchone()

            if existing:
                new_weight = min(max_weight, existing["weight"] + weight_increment)
                conn.execute(
                    "UPDATE memory_relations SET weight = ? WHERE id = ?",
                    (new_weight, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO memory_relations
                       (src_entity_id, dst_entity_id, relation_type, weight, namespace)
                       VALUES (?, ?, 'co_occurs', ?, ?)""",
                    (e1_id, e2_id, min(max_weight, weight_increment * count), namespace),
                )
            reinforced += 1

        conn.commit()
        logger.info("reinforce_edges: reinforced %d edges (namespace=%s)", reinforced, namespace)
        return reinforced

    # ── Phase 3: Auto Decay ───────────────────────────────────────

    def auto_decay(
        self,
        namespace: str = "default",
        stale_days: int = 90,
        min_importance: float = 0.3,
        batch_size: int = 100,
    ) -> int:
        """Auto-decay stale, low-importance memories.

        Reduces importance_score by half and marks metadata.decayed=true
        for memories that meet ALL three conditions:
        - last_accessed_at older than stale_days (or never accessed)
        - importance_score < min_importance
        - access_count == 0 (never recalled)

        Decayed memories are not deleted — they're naturally deprioritized
        in recall ranking due to lower importance_score.

        Args:
            namespace: Namespace scope.
            stale_days: Days without access to be considered stale (default 90).
            min_importance: Importance threshold (default 0.3).
            batch_size: Batch size for processing (default 100).

        Returns:
            Number of memories decayed.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).isoformat()
        conn = self._adapter._get_connection()

        stale_keys = conn.execute(
            """SELECT storage_key FROM memories
               WHERE namespace = ?
                 AND superseded_at IS NULL
                 AND (last_accessed_at IS NULL OR last_accessed_at < ?)
                 AND importance_score < ?
                 AND access_count = 0
                 AND (metadata IS NULL
                      OR json_extract(metadata, '$.decayed') IS NULL
                      OR json_extract(metadata, '$.decayed') != 1)
               LIMIT ?""",
            (namespace, cutoff, min_importance, batch_size),
        ).fetchall()

        if not stale_keys:
            return 0

        decayed = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for row in stale_keys:
            key = row["storage_key"]
            conn.execute(
                """UPDATE memories
                   SET importance_score = importance_score * 0.5,
                       metadata = json_set(
                           COALESCE(metadata, '{}'),
                           '$.decayed', 1,
                           '$.decayed_at', ?
                       )
                   WHERE storage_key = ?""",
                (now_iso, key),
            )
            decayed += 1

        conn.commit()
        logger.info("auto_decay: decayed %d memories (namespace=%s)", decayed, namespace)
        return decayed

    # ── Internal helpers ──────────────────────────────────────────

    def _find_co_occurring_pairs(
        self,
        namespace: str,
        min_co_occurrence: int,
        max_derived: int,
    ) -> List[tuple]:
        """Find entity pairs that co-occur in >=min_co_occurrence memories.

        Returns:
            List of (entity1, entity2, count) tuples sorted by count descending.
        """
        conn = self._adapter._get_connection()
        try:
            rows = conn.execute(
                """SELECT e1.entity_text AS e1, e2.entity_text AS e2, COUNT(*) AS co
                   FROM memory_entities e1
                   JOIN memory_entities e2
                     ON e1.memory_key = e2.memory_key
                     AND e1.id < e2.id
                     AND e1.namespace = e2.namespace
                   WHERE e1.namespace = ?
                     AND e1.memory_key IS NOT NULL
                   GROUP BY e1.entity_text, e2.entity_text
                   HAVING co >= ?
                   ORDER BY co DESC
                   LIMIT ?""",
                (namespace, min_co_occurrence, max_derived),
            ).fetchall()
        except Exception as e:
            logger.warning("_find_co_occurring_pairs: query failed: %s", e)
            return []

        return [(row["e1"], row["e2"], row["co"]) for row in rows]
