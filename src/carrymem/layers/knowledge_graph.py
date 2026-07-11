"""Knowledge graph layer — SQLite-native entity and relation storage.

Stores entities extracted from memory content in ``memory_entities`` table,
and relations between entities in ``memory_relations`` table. Enables multi-hop
reasoning over memory connections without introducing Neo4j or other external
graph databases.

Design principles (per CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md §2.1):
  - Zero LLM: entity extraction reuses EntityNormalizer's pattern-based approach
  - SQLite native: single-file graph via two tables + indexes
  - Backward-compatible: new API methods, existing recall() unchanged
  - Namespace isolated: entities and relations are scoped per namespace
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from carrymem.utils.logger import logger


class KnowledgeGraph:
    """SQLite-native knowledge graph for memory entities and relations.

    Uses ``memory_entities`` and ``memory_relations`` tables (created by
    schema migration ``migrate_v062``). Entity extraction delegates to
    ``EntityNormalizer`` (pattern-based, zero LLM).
    """

    def __init__(
        self,
        conn_mgr: Any,
        entity_normalizer: Optional[Any] = None,
        input_validator: Optional[Any] = None,
    ):
        """Initialize the knowledge graph.

        Args:
            conn_mgr: ConnectionManager providing sqlite3 connections.
            entity_normalizer: EntityNormalizer instance for entity extraction.
                If None, extraction methods will return empty results.
            input_validator: InputValidator for sanitization (optional).
        """
        self._conn_mgr = conn_mgr
        self._entity_normalizer = entity_normalizer
        self._input_validator = input_validator

    # ── Entity extraction & storage ───────────────────────────────

    def extract_and_store_entities(
        self,
        storage_key: str,
        text: str,
        namespace: str = "default",
    ) -> int:
        """Extract entities from text and store them linked to a memory.

        Uses EntityNormalizer.normalize() for extraction (pattern-based,
        zero LLM). Each extracted entity is inserted into memory_entities
        with a foreign key to the memory's storage_key.

        Args:
            storage_key: The memory's storage_key (FK to memories table).
            text: The text to extract entities from.
            namespace: Trusted namespace from adapter (C18).

        Returns:
            Number of entities stored (0 if extraction disabled or failed).
        """
        if not storage_key or not text or not text.strip():
            return 0

        safe_ns = self._validate_namespace(namespace)
        if not safe_ns:
            return 0

        if self._entity_normalizer is None:
            return 0

        try:
            result = self._entity_normalizer.normalize(text, safe_ns)
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.debug("KnowledgeGraph entity extraction skipped: %s", e)
            return 0

        if not result.entities:
            return 0

        conn = self._conn_mgr.get_connection()
        stored = 0
        now = datetime.now(timezone.utc).isoformat()
        for entity in result.entities:
            canonical = self._sanitize(entity.get("canonical", ""))
            if not canonical:
                continue
            entity_type = entity.get("type", "concept")
            score = float(entity.get("score", 0.5))
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO memory_entities "
                    "(memory_key, entity_type, entity_text, confidence, namespace, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (storage_key, entity_type, canonical, score, safe_ns, now),
                )
                stored += 1
            except sqlite3.Error as e:
                logger.debug("KnowledgeGraph entity insert skipped: %s", e)
        if stored > 0:
            conn.commit()
        return stored

    # ── Graph query APIs ──────────────────────────────────────────

    def recall_by_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories mentioning a specific entity.

        Args:
            entity_text: The entity text to search for (exact match).
            entity_type: Optional entity type filter (acronym/concept/tool).
            namespace: Optional namespace filter. If None, searches all.
            limit: Maximum number of memories to return.

        Returns:
            List of memory dicts with all columns from the memories table.
        """
        safe_entity = self._sanitize(entity_text)
        if not safe_entity:
            return []

        conn = self._conn_mgr.get_connection()
        conditions = ["me.entity_text = ?"]
        params: list = [safe_entity]

        if entity_type:
            conditions.append("me.entity_type = ?")
            params.append(entity_type)
        if namespace:
            conditions.append("me.namespace = ?")
            params.append(namespace)

        query = (
            "SELECT m.* FROM memories m "
            "INNER JOIN memory_entities me ON me.memory_key = m.storage_key "
            "WHERE " + " AND ".join(conditions) + " "
            "ORDER BY m.importance_score DESC "
            "LIMIT ?"
        )
        params.append(limit)

        try:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.warning("recall_by_entity failed: %s", e)
            return []

    def recall_by_relation(
        self,
        entity_text: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories connected to an entity via relations.

        Args:
            entity_text: The entity to find relations for.
            relation_type: Optional relation type filter (e.g. "prefers",
                "works_on", "knows").
            direction: "outgoing" (entity is source), "incoming" (entity is
                destination), or "both" (default).
            namespace: Optional namespace filter.
            limit: Maximum number of memories to return.

        Returns:
            List of memory dicts connected to the entity via relations.
        """
        safe_entity = self._sanitize(entity_text)
        if not safe_entity:
            return []

        if direction not in ("outgoing", "incoming", "both"):
            direction = "both"

        conn = self._conn_mgr.get_connection()
        conditions: list[str] = []
        params: list = []

        if direction in ("outgoing", "both"):
            conditions.append("(src.entity_text = ? AND mr.src_entity_id = src.id)")
            params.append(safe_entity)
        if direction in ("incoming", "both"):
            conditions.append("(dst.entity_text = ? AND mr.dst_entity_id = dst.id)")
            params.append(safe_entity)

        where_clause = " OR ".join(conditions) if len(conditions) > 1 else conditions[0]

        extra_conditions = ""
        if relation_type:
            extra_conditions += " AND mr.relation_type = ?"
            params.append(relation_type)
        if namespace:
            extra_conditions += " AND mr.namespace = ?"
            params.append(namespace)

        query = (
            "SELECT DISTINCT m.* FROM memories m "
            "INNER JOIN memory_relations mr ON mr.source_memory_key = m.storage_key "
            "INNER JOIN memory_entities src ON mr.src_entity_id = src.id "
            "INNER JOIN memory_entities dst ON mr.dst_entity_id = dst.id "
            f"WHERE ({where_clause}){extra_conditions} "
            "ORDER BY mr.weight DESC, m.importance_score DESC "
            "LIMIT ?"
        )
        params.append(limit)

        try:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.warning("recall_by_relation failed: %s", e)
            return []

    def recall_graph(
        self,
        entity_text: str,
        max_hops: int = 2,
        namespace: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Multi-hop graph traversal from an entity.

        Performs BFS traversal of memory_relations starting from the given
        entity, collecting all connected entities and memories within
        ``max_hops`` hops.

        Args:
            entity_text: The starting entity.
            max_hops: Maximum traversal depth (default 2).
            namespace: Optional namespace filter.
            limit: Maximum number of memories to return.

        Returns:
            Dict with "entities" (list of connected entities) and
            "memories" (list of connected memories).
        """
        safe_entity = self._sanitize(entity_text)
        if not safe_entity or max_hops < 1:
            return {"entities": [], "memories": []}

        conn = self._conn_mgr.get_connection()
        ns_filter = "AND namespace = ?" if namespace else ""
        ns_params: list = [namespace] if namespace else []

        # Find starting entity IDs
        try:
            entity_ids = [
                row["id"]
                for row in conn.execute(
                    f"SELECT id FROM memory_entities WHERE entity_text = ? {ns_filter}",
                    [safe_entity] + ns_params,
                ).fetchall()
            ]
        except sqlite3.Error as e:
            logger.warning("recall_graph entity lookup failed: %s", e)
            return {"entities": [], "memories": []}

        if not entity_ids:
            return {"entities": [], "memories": []}

        # BFS traversal
        visited_entities: set[int] = set(entity_ids)
        visited_memories: set[str] = set()
        current_frontier = list(entity_ids)

        for hop in range(max_hops):
            if not current_frontier:
                break
            next_frontier: list[int] = []
            placeholders = ",".join("?" * len(current_frontier))

            try:
                # Find relations from current frontier
                rows = conn.execute(
                    f"SELECT src_entity_id, dst_entity_id, source_memory_key "
                    f"FROM memory_relations "
                    f"WHERE src_entity_id IN ({placeholders}) {ns_filter}",
                    current_frontier + ns_params,
                ).fetchall()

                for row in rows:
                    dst_id = row["dst_entity_id"]
                    if dst_id not in visited_entities:
                        visited_entities.add(dst_id)
                        next_frontier.append(dst_id)
                    mem_key = row["source_memory_key"]
                    if mem_key:
                        visited_memories.add(mem_key)

                # Also check reverse direction
                rows = conn.execute(
                    f"SELECT src_entity_id, dst_entity_id, source_memory_key "
                    f"FROM memory_relations "
                    f"WHERE dst_entity_id IN ({placeholders}) {ns_filter}",
                    current_frontier + ns_params,
                ).fetchall()

                for row in rows:
                    src_id = row["src_entity_id"]
                    if src_id not in visited_entities:
                        visited_entities.add(src_id)
                        next_frontier.append(src_id)
                    mem_key = row["source_memory_key"]
                    if mem_key:
                        visited_memories.add(mem_key)
            except sqlite3.Error as e:
                logger.warning("recall_graph hop %d failed: %s", hop, e)
                break

            current_frontier = next_frontier

        # Fetch entity details
        entity_placeholders = ",".join("?" * len(visited_entities))
        entities_data: List[Dict[str, Any]] = []
        memories_data: List[Dict[str, Any]] = []

        try:
            entity_rows = conn.execute(
                f"SELECT DISTINCT entity_text, entity_type FROM memory_entities "
                f"WHERE id IN ({entity_placeholders})",
                list(visited_entities),
            ).fetchall()
            entities_data = [
                {"entity_text": row["entity_text"], "entity_type": row["entity_type"]} for row in entity_rows
            ]
        except sqlite3.Error as e:
            logger.warning("recall_graph entity fetch failed: %s", e)

        # Fetch memories (limited)
        if visited_memories:
            mem_keys = list(visited_memories)[:limit]
            mem_placeholders = ",".join("?" * len(mem_keys))
            try:
                mem_rows = conn.execute(
                    f"SELECT * FROM memories WHERE storage_key IN ({mem_placeholders}) "
                    f"ORDER BY importance_score DESC",
                    mem_keys,
                ).fetchall()
                memories_data = [self._row_to_dict(row) for row in mem_rows]
            except sqlite3.Error as e:
                logger.warning("recall_graph memory fetch failed: %s", e)

        return {"entities": entities_data, "memories": memories_data}

    # ── Relation management ───────────────────────────────────────

    def add_relation(
        self,
        src_entity_text: str,
        dst_entity_text: str,
        relation_type: str,
        source_memory_key: Optional[str] = None,
        weight: float = 1.0,
        namespace: str = "default",
    ) -> bool:
        """Add a relation between two entities.

        Entities are looked up by text (exact match within namespace).
        If either entity doesn't exist in the graph, it is created.

        Args:
            src_entity_text: Source entity text.
            dst_entity_text: Destination entity text.
            relation_type: Relation type (e.g. "prefers", "works_on").
            source_memory_key: Optional memory that evidence this relation.
            weight: Relation strength (default 1.0).
            namespace: Trusted namespace from adapter.

        Returns:
            True if relation was added, False on failure.
        """
        safe_src = self._sanitize(src_entity_text)
        safe_dst = self._sanitize(dst_entity_text)
        if not safe_src or not safe_dst or not relation_type:
            return False
        if safe_src == safe_dst:
            return False

        safe_ns = self._validate_namespace(namespace)
        if not safe_ns:
            return False

        conn = self._conn_mgr.get_connection()
        now = datetime.now(timezone.utc).isoformat()

        try:
            src_id = self._find_or_create_entity(safe_src, safe_ns, conn, now)
            dst_id = self._find_or_create_entity(safe_dst, safe_ns, conn, now)
            if src_id is None or dst_id is None:
                return False

            conn.execute(
                "INSERT OR IGNORE INTO memory_relations "
                "(src_entity_id, dst_entity_id, relation_type, source_memory_key, "
                "weight, namespace, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (src_id, dst_id, relation_type, source_memory_key, weight, safe_ns, now),
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.warning("add_relation failed: %s", e)
            return False

    def _find_or_create_entity(
        self,
        entity_text: str,
        namespace: str,
        conn: sqlite3.Connection,
        now: str,
    ) -> Optional[int]:
        """Find an entity by text+namespace, or create it if missing.

        Returns entity ID or None on failure.
        """
        try:
            row = conn.execute(
                "SELECT id FROM memory_entities WHERE entity_text = ? AND namespace = ? LIMIT 1",
                (entity_text, namespace),
            ).fetchone()
            if row:
                return int(row["id"])
            # Standalone entity (not linked to a specific memory) — memory_key is NULL
            cursor = conn.execute(
                "INSERT INTO memory_entities "
                "(memory_key, entity_type, entity_text, confidence, namespace, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (None, "concept", entity_text, 0.5, namespace, now),
            )
            return int(cursor.lastrowid) if cursor.lastrowid is not None else None
        except sqlite3.Error as e:
            logger.debug("find_or_create_entity failed: %s", e)
            return None

    # ── Listing & stats ───────────────────────────────────────────

    def list_entities(
        self,
        namespace: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List entities in the graph with optional filters."""
        conn = self._conn_mgr.get_connection()
        conditions: list[str] = []
        params: list = []

        if namespace:
            conditions.append("namespace = ?")
            params.append(namespace)
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = (
            f"SELECT entity_text, entity_type, COUNT(*) as memory_count, "
            f"MAX(confidence) as max_confidence "
            f"FROM memory_entities {where} "
            f"GROUP BY entity_text, entity_type "
            f"ORDER BY memory_count DESC, max_confidence DESC "
            f"LIMIT ?"
        )
        params.append(limit)

        try:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "entity_text": row["entity_text"],
                    "entity_type": row["entity_type"],
                    "memory_count": row["memory_count"],
                    "max_confidence": row["max_confidence"],
                }
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.warning("list_entities failed: %s", e)
            return []

    def list_relations(
        self,
        namespace: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List relations in the graph with optional filters."""
        conn = self._conn_mgr.get_connection()
        conditions: list[str] = []
        params: list = []

        if namespace:
            conditions.append("mr.namespace = ?")
            params.append(namespace)
        if relation_type:
            conditions.append("mr.relation_type = ?")
            params.append(relation_type)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = (
            "SELECT src.entity_text as src_entity, dst.entity_text as dst_entity, "
            "mr.relation_type, mr.weight, mr.source_memory_key "
            "FROM memory_relations mr "
            "INNER JOIN memory_entities src ON mr.src_entity_id = src.id "
            "INNER JOIN memory_entities dst ON mr.dst_entity_id = dst.id "
            f"{where} "
            "ORDER BY mr.weight DESC "
            "LIMIT ?"
        )
        params.append(limit)

        try:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "src_entity": row["src_entity"],
                    "dst_entity": row["dst_entity"],
                    "relation_type": row["relation_type"],
                    "weight": row["weight"],
                    "source_memory_key": row["source_memory_key"],
                }
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.warning("list_relations failed: %s", e)
            return []

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get knowledge graph statistics."""
        conn = self._conn_mgr.get_connection()
        ns_filter = "WHERE namespace = ?" if namespace else ""
        ns_params: list = [namespace] if namespace else []

        try:
            entity_count = conn.execute(
                f"SELECT COUNT(DISTINCT entity_text) FROM memory_entities {ns_filter}",
                ns_params,
            ).fetchone()[0]
            relation_count = conn.execute(
                f"SELECT COUNT(*) FROM memory_relations {ns_filter}",
                ns_params,
            ).fetchone()[0]
            memory_linked = conn.execute(
                f"SELECT COUNT(DISTINCT memory_key) FROM memory_entities "
                f"WHERE memory_key IS NOT NULL" + (f" AND namespace = ?" if namespace else ""),
                ns_params,
            ).fetchone()[0]
            return {
                "entity_count": entity_count,
                "relation_count": relation_count,
                "memory_linked": memory_linked,
            }
        except sqlite3.Error as e:
            logger.warning("get_stats failed: %s", e)
            return {"entity_count": 0, "relation_count": 0, "memory_linked": 0}

    # ── Internal helpers ──────────────────────────────────────────

    def _sanitize(self, value: str) -> str:
        """Sanitize input text to prevent injection."""
        if not value or not isinstance(value, str):
            return ""
        if self._input_validator is not None:
            try:
                result = self._input_validator.sanitize_content(value)
                return str(result) if result else ""
            except Exception as e:  # pragma: no cover — defensive
                logger.debug("KnowledgeGraph sanitize failed: %s", e)
        return value.replace("\x00", "").strip()

    @staticmethod
    def _validate_namespace(namespace: str) -> str:
        """Validate namespace format. Returns sanitized namespace or empty string."""
        if not namespace or not isinstance(namespace, str):
            return ""
        ns = namespace.strip().lower()
        if not ns or not ns.replace("-", "").replace("_", "").isalnum():
            return ""
        return ns

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict."""
        try:
            return {k: row[k] for k in row.keys()}
        except (KeyError, IndexError):
            return {}
