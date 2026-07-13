"""Recall operations: memories, aggregated, timeline, knowledge, all."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.constants import DEFAULT_RECALL_LIMIT, RULE_MATCH_LIMIT_CAP
from carrymem.core._lifecycle import KnowledgeNotConfiguredError, StorageNotConfiguredError
from carrymem.types import StoredMemoryDict
from carrymem.utils.validators import validate_limit, validate_query

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter

logger = logging.getLogger(__name__)


class RecallMixin:
    """Recall / search operations across memories, knowledge base, and rules."""

    # Shared instance state provided by LifecycleMixin.__init__.
    _adapter: Optional[StorageAdapter]
    _knowledge_adapter: Optional[StorageAdapter]
    _namespace: str
    _session_id: Optional[str]

    def index_knowledge(self) -> Dict[str, Any]:
        """Index the configured knowledge base and return summary stats."""
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        if isinstance(self._knowledge_adapter, ObsidianAdapter):
            return self._knowledge_adapter.index_vault()

        return {"error": "Knowledge adapter does not support indexing"}

    def recall_from_knowledge(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Recall notes from the knowledge base matching the query."""
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        results = self._knowledge_adapter.recall(query, filters=filters, limit=limit)
        if isinstance(results, list) and results and isinstance(results[0], dict):
            return results  # type: ignore[return-value]
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in results]  # type: ignore[misc]

    def recall_all(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        """Recall rules, memories, and knowledge matching a query."""
        memory_results = []
        knowledge_results = []
        rule_results = []

        if include_rules:
            try:
                rule_engine = self.rule_engine  # type: ignore[attr-defined]
                matches = rule_engine.match(query, limit=min(limit, RULE_MATCH_LIMIT_CAP), increment_count=False)
                rule_results = [
                    {
                        "rule_id": m.rule.id,
                        "trigger": m.rule.trigger,
                        "action": m.rule.action,
                        "rule_type": m.rule.rule_type,
                        "override": m.rule.override,
                        "score": m.score,
                        "match_type": m.match_type,
                    }
                    for m in matches
                ]
            except (ImportError, KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Rule engine failed for recall_all: %s", e)
                rule_results = []

        if self._adapter:
            try:
                memory_results = self.recall_memories(query=query, filters=filters, limit=limit, namespaces=namespaces)
            except (KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to recall memories for prompt: %s", e)
                memory_results = []

        if self._knowledge_adapter:
            try:
                knowledge_results = self.recall_from_knowledge(query=query, filters=filters, limit=limit)
            except (KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to recall from knowledge base: %s", e)
                knowledge_results = []

        return {
            "rules": rule_results,
            "memories": memory_results,
            "knowledge": knowledge_results,
            "rule_count": len(rule_results),
            "memory_count": len(memory_results),
            "knowledge_count": len(knowledge_results),
            "total_count": len(rule_results) + len(memory_results) + len(knowledge_results),
            "namespace": self._namespace,
            "priority": "rules > memory > knowledge",
        }

    def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[Dict[str, Any]]:
        """Recall stored memories matching the query."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_query(query or "")
        validate_limit(limit)
        results = self._adapter.recall(
            query or "",
            filters=filters,
            limit=limit,
            namespaces=namespaces,
            update_access=update_access,
        )
        return [r.to_dict() for r in results]

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemoryDict]]:
        """Recall memories grouped by type."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not hasattr(self._adapter, "recall_aggregated"):
            raise NotImplementedError("Adapter does not support recall_aggregated")

        result = self._adapter.recall_aggregated(memory_type=memory_type, limit_per_type=limit_per_type)
        return {k: [r.to_dict() for r in v] for k, v in result.items()}

    def recall_timeline(
        self,
        topic: str,
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Recall memories for a topic ordered as a timeline."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not hasattr(self._adapter, "recall_timeline"):
            raise NotImplementedError("Adapter does not support recall_timeline")

        results = self._adapter.recall_timeline(topic=topic, limit=limit)
        return [r.to_dict() for r in results]

    # ── Knowledge Graph (v0.7.0) ────────────────────────────────

    def recall_by_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories mentioning a specific entity (v0.7.0).

        Uses the knowledge graph to find all memories that mention the
        given entity. Requires an adapter with ``graph: True`` capability.

        Args:
            entity_text: The entity text to search for.
            entity_type: Optional entity type filter (acronym/concept/tool).
            limit: Maximum results (default 10).

        Returns:
            List of memory dicts containing the entity.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return []
        return self._adapter.recall_by_entity(entity_text, entity_type, self._namespace, limit)

    def recall_by_relation(
        self,
        entity_text: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories connected to an entity via relations (v0.7.0).

        Traverses the knowledge graph to find memories linked to the given
        entity through explicit relations (e.g., "prefers", "works_on").

        Args:
            entity_text: The entity to find relations for.
            relation_type: Optional relation type filter.
            direction: "outgoing", "incoming", or "both" (default).
            limit: Maximum results.

        Returns:
            List of memory dicts connected via relations.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return []
        return self._adapter.recall_by_relation(entity_text, relation_type, direction, self._namespace, limit)

    def recall_graph(
        self,
        entity_text: str,
        max_hops: int = 2,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Multi-hop graph traversal from an entity (v0.7.0).

        Performs BFS traversal of the knowledge graph starting from the
        given entity, collecting all connected entities and memories
        within ``max_hops`` hops.

        Args:
            entity_text: The starting entity.
            max_hops: Maximum traversal depth (default 2).
            limit: Maximum memories to return.

        Returns:
            Dict with "entities" (list of connected entities) and
            "memories" (list of connected memories).
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return {"entities": [], "memories": []}
        return self._adapter.recall_graph(entity_text, max_hops, self._namespace, limit)

    def recall_shortest_path(
        self,
        src_entity: str,
        dst_entity: str,
        max_hops: int = 4,
    ) -> Dict[str, Any]:
        """Find the shortest path between two entities (v0.8.0).

        Uses bidirectional BFS to find the shortest path in the knowledge
        graph between two entities. Useful for understanding how concepts
        are connected.

        Args:
            src_entity: The source entity text.
            dst_entity: The destination entity text.
            max_hops: Maximum path length to search (default 4, hard cap 10).

        Returns:
            Dict with "path" (list of entity texts from src to dst),
            "length" (number of edges, 0 if src==dst, -1 if no path),
            and "found" (bool).
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return {"path": [], "length": -1, "found": False}
        return self._adapter.shortest_path(src_entity, dst_entity, max_hops, self._namespace)

    def recall_memory_impact(
        self,
        memory_id: str,
    ) -> Dict[str, Any]:
        """Compute the graph impact of a memory (v0.8.0).

        Calculates how influential a memory is in the knowledge graph.
        impact_score = entity_count * 0.4 + relation_count * 0.4 + cross_namespace * 0.2

        Args:
            memory_id: The memory's storage_key.

        Returns:
            Dict with "memory_id", "entity_count", "relation_count",
            "cross_namespace" (bool), and "impact_score" (float).
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return {
                "memory_id": memory_id,
                "entity_count": 0,
                "relation_count": 0,
                "cross_namespace": False,
                "impact_score": 0.0,
            }
        return self._adapter.get_memory_impact(memory_id, self._namespace)

    def add_graph_relation(
        self,
        src_entity: str,
        dst_entity: str,
        relation_type: str,
        source_memory_key: Optional[str] = None,
        weight: float = 1.0,
        confidence: str = "EXTRACTED",
    ) -> bool:
        """Add a relation between two entities in the knowledge graph (v0.7.0).

        Args:
            src_entity: Source entity text.
            dst_entity: Destination entity text.
            relation_type: Relation type (e.g. "prefers", "works_on").
            source_memory_key: Optional memory key that evidences this relation.
            weight: Relation strength (default 1.0).
            confidence: Edge confidence label (v0.8.0). One of
                "EXTRACTED" (default), "INFERRED", "AMBIGUOUS".

        Returns:
            True if relation was added successfully.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return False
        return self._adapter.add_graph_relation(
            src_entity,
            dst_entity,
            relation_type,
            source_memory_key,
            weight,
            self._namespace,
            confidence,
        )

    # ── Session Dual-Layer Memory (v0.7.0) ──────────────────────

    def set_session(self, session_id: str) -> None:
        """Set the current session for dual-layer memory (v0.7.0).

        When a session is active, recall operations check the session cache
        first (O(1)) before falling back to the persistent layer (FTS5).
        New memories stored during the session are also added to the session
        cache for fast subsequent retrieval.

        Args:
            session_id: Unique session identifier.
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        self._session_id = session_id

    def end_session(self) -> None:
        """End the current session and clear session cache (v0.7.0)."""
        session_id = getattr(self, "_session_id", None)
        if session_id and self._adapter and hasattr(self._adapter, "_cache"):
            cache = getattr(self._adapter, "_cache", None)
            if cache:
                try:
                    cache.invalidate_session(session_id)
                except (AttributeError, TypeError) as e:
                    logger.debug("Session cache invalidation skipped: %s", e)
        self._session_id = None

    def preload_session(self, limit: int = 50) -> int:
        """Pre-load high-frequency memories into the session cache (v0.7.0).

        Loads the top-N memories by importance_score from the persistent
        layer into the session cache for O(1) recall within the session.

        Args:
            limit: Maximum memories to pre-load (default 50).

        Returns:
            Number of memories pre-loaded.
        """
        session_id = getattr(self, "_session_id", None)
        if not session_id or not self._adapter:
            return 0
        if not self._adapter.has_cache:
            return 0

        # Recall top memories by importance (broad query to get diverse set)
        try:
            results = self._adapter.recall(
                "",
                filters=None,
                limit=limit,
                namespaces=[self._namespace],
                update_access=False,
            )
            memories = [r.to_dict() if hasattr(r, "to_dict") else r for r in results]
            if memories:
                cache = getattr(self._adapter, "_cache", None)
                if cache:
                    return int(cache.session_preload(session_id, memories))
        except (KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.warning("Session preload failed: %s", e)
        return 0

    def promote_to_permanent(self, memory_key: str) -> bool:
        """Boost a memory's importance for permanent retention (v0.7.0).

        Increases the access_count and importance_score of a memory so it
        survives longer in the cache and ranks higher in recall results.

        Args:
            memory_key: The storage_key of the memory to promote.

        Returns:
            True if the memory was promoted.
        """
        if not self._adapter or not memory_key:
            return False
        try:
            conn = self._adapter._get_connection()  # type: ignore[attr-defined]
            cursor = conn.execute(
                "UPDATE memories SET "
                "access_count = access_count + 1, "
                "importance_score = MIN(importance_score + 0.05, 1.0), "
                "last_accessed_at = ? "
                "WHERE storage_key = ?",
                (datetime.now(timezone.utc).isoformat(), memory_key),
            )
            conn.commit()
            return bool(cursor.rowcount > 0)
        except (AttributeError, TypeError, RuntimeError) as e:
            logger.warning("promote_to_permanent failed: %s", e)
            return False

    # ── Memify Consolidation (v0.7.2) ───────────────────────────

    def consolidate_memories(
        self,
        namespace: Optional[str] = None,
        min_co_occurrence: int = 3,
        max_derived: int = 10,
        stale_days: int = 90,
        min_importance: float = 0.3,
    ) -> Dict[str, Any]:
        """Consolidate memories via Memify three-phase refinement (v0.7.2).

        Phase 1: derive_facts — create derived memories from co-occurring entities.
        Phase 2: reinforce_edges — strengthen graph relations for co-occurring entities.
        Phase 3: auto_decay — reduce importance of stale, low-access memories.

        Args:
            namespace: Namespace scope (default: current namespace).
            min_co_occurrence: Minimum co-occurrence for derive/reinforce.
            max_derived: Maximum derived facts per run.
            stale_days: Days without access for decay.
            min_importance: Importance threshold for decay.

        Returns:
            Dict with derived_facts, edges_reinforced, decayed.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        ns = namespace or self._namespace
        return self._adapter.consolidate_memories(
            namespace=ns,
            min_co_occurrence=min_co_occurrence,
            max_derived=max_derived,
            stale_days=stale_days,
            min_importance=min_importance,
        )

    # ── Multi-Mode Retrieval (v0.7.1) ────────────────────────────

    def recall_by_time(
        self,
        start: datetime,
        end: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories within a time range (v0.7.1).

        Args:
            start: Start datetime (inclusive). Timezone-aware recommended.
            end: End datetime (exclusive). Defaults to now.
            filters: Optional metadata filters (same as recall()).
            limit: Maximum results (default 50).

        Returns:
            List of memory dicts ordered by created_at descending.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not start:
            raise ValueError("start datetime is required")
        results = self._adapter.recall_by_time(start, end, filters, limit, [self._namespace])
        return list(results)

    def recall_semantic(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Pure vector similarity search (v0.7.1).

        Bypasses FTS5 and RRF fusion — returns raw vector similarity results.
        Requires vector search enabled (capabilities["vector_search"] == True).

        Args:
            query: Natural language query.
            top_k: Number of results (default 10).
            filters: Optional metadata filters.

        Returns:
            List of memory dicts ordered by vector similarity descending.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not self._adapter.capabilities.get("vector_search", False):
            return []
        return list(self._adapter.recall_semantic(query, top_k, filters, [self._namespace]))

    def recall_hybrid(
        self,
        query: str,
        fts_weight: Optional[float] = None,
        vec_weight: Optional[float] = None,
        rrf_k: Optional[int] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Explicit hybrid search with configurable RRF weights (v0.7.1).

        Exposes the existing RRF fusion with per-call weight override.
        If weights are None, uses adapter defaults.

        Args:
            query: Search query.
            fts_weight: FTS rank weight (default: adapter config).
            vec_weight: Vector rank weight (default: adapter config).
            rrf_k: RRF constant k (default: adapter config).
            limit: Maximum results.
            filters: Optional metadata filters.

        Returns:
            List of memory dicts ordered by fused RRF score descending.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        validate_query(query or "")
        validate_limit(limit)
        return list(
            self._adapter.recall_hybrid(query, fts_weight, vec_weight, rrf_k, limit, filters, [self._namespace])
        )

    def recall_multi_mode(
        self,
        query: str,
        modes: Optional[List[str]] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
        entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unified multi-mode retrieval interface (v0.7.1).

        Executes multiple retrieval modes and returns results grouped by mode,
        plus a merged "best" list deduplicated by storage_key.

        Args:
            query: Search query (used for fts/vector/hybrid modes).
            modes: Retrieval modes. Default: ["fts", "vector"] or ["fts"].
                   Options: "fts", "vector", "hybrid", "graph", "time", "entity".
            limit: Maximum results per mode.
            filters: Optional metadata filters.
            time_range: (start, end) for "time" mode.
            entity: Entity text for "entity"/"graph" modes.

        Returns:
            Dict with "modes", "merged", "mode_count", "total_count".
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        validate_limit(limit)
        result = self._adapter.recall_multi_mode(
            query,
            modes,
            limit,
            filters,
            [self._namespace],
            time_range,
            entity,
        )
        return dict(result)
