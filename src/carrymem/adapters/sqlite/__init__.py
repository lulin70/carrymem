"""SQLite Storage Adapter — CarryMem default storage backend (Facade).

This module re-exports SQLiteAdapter which composes the following sub-components:
- ConnectionManager: connection lifecycle and thread safety
- SchemaManager: schema creation and migrations
- CRUDOperations: remember, forget, update operations
- RecallEngine: multi-phase recall (FTS, vector, semantic, RRF)
- RowSerializer: row/dict <-> StoredMemory conversion
- SupersedeManager: auto-supersede and contradiction detection
- VersionManager: memory history and rollback
- StatsManager: statistics, profiles, aggregated/timeline recall
- QueryBuilder: query expansion, time parsing, FTS sanitization
- SecurityOps: field-level encryption/decryption

Public API is fully backward compatible with the monolithic sqlite_adapter.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base import MemoryEntry, StorageAdapter, StoredMemory
from .connection import ConnectionManager
from .crud import CRUDOperations
from .query_builder import QueryBuilderWithContext
from .recall_engine import RecallEngine
from .schema import SchemaManager
from .security import SecurityOps
from .serializer import RowSerializer
from .stats import StatsManager
from .supersede import SupersedeManager
from .versioning import VersionManager

# Module-level capability flags (re-exported for backward compatibility)
try:
    import sqlite_vec  # noqa: F401

    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False

try:
    import pysqlite3  # noqa: F401

    PYSQLITE3_AVAILABLE = True
except ImportError:
    PYSQLITE3_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

_EMBEDDING_MODEL_CACHE: Dict[str, Any] = {}
_EMBEDDING_MODEL_LOCK = __import__("threading").Lock()


def _get_or_load_embedding_model(model_name: str):
    """Get cached SentenceTransformer model, loading on first access.

    Avoids repeated model weight loading (103 weights) when multiple
    SQLiteAdapter instances are created in the same process (e.g. benchmarks).
    """
    if model_name in _EMBEDDING_MODEL_CACHE:
        return _EMBEDDING_MODEL_CACHE[model_name]
    with _EMBEDDING_MODEL_LOCK:
        if model_name in _EMBEDDING_MODEL_CACHE:
            return _EMBEDDING_MODEL_CACHE[model_name]
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        model = SentenceTransformer(model_name)
        _EMBEDDING_MODEL_CACHE[model_name] = model
        return model


def _default_db_path() -> str:
    home = os.path.expanduser("~")
    carrymem_dir = os.path.join(home, ".carrymem")
    os.makedirs(carrymem_dir, exist_ok=True)
    return os.path.join(carrymem_dir, "memories.db")


class SQLiteAdapter(StorageAdapter):
    """SQLite-based storage adapter — CarryMem's default backend (Facade).

    Usage:
        adapter = SQLiteAdapter()  # auto-creates ~/.carrymem/memories.db
        adapter = SQLiteAdapter(":memory:")  # in-memory for testing
        adapter = SQLiteAdapter("/path/to/custom.db")  # custom path
        adapter = SQLiteAdapter(namespace="project-alpha")  # namespace isolation
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        namespace: str = "default",
        enable_semantic_recall: bool = True,
        semantic_config: Optional[Dict[str, Any]] = None,
        enable_cache: bool = True,
        cache_config: Optional[Dict[str, Any]] = None,
        encryption_key: Optional[str] = None,
        enable_vector_search: bool = True,
        embedding_model: str = "all-MiniLM-L6-v2",
        _external_embedding_model: Optional[object] = None,
        rrf_config: Optional[Dict[str, Any]] = None,
    ):
        # --- Connection management ---
        self._conn_mgr = ConnectionManager(
            db_path=db_path or _default_db_path(),
            namespace=namespace,
            enable_vector=False,
        )

        # --- Security ---
        self._security = SecurityOps()
        if encryption_key is not None:
            try:
                from ...security.encryption import MemoryEncryption

                self._security.set_encryption(MemoryEncryption(key=encryption_key))
            except (ImportError, ValueError, TypeError) as e:
                from ...utils.logger import logger

                logger.error("Encryption initialization failed: %s", e)
                raise RuntimeError(
                    f"Encryption initialization failed with provided key. "
                    f"Refusing to fall back to plaintext storage. Error: {e}"
                ) from e

        # --- Serializer (depends on security for decrypt) ---
        self._serializer = RowSerializer(self)

        # --- Schema (depends on connection) ---
        self._schema = SchemaManager(self._conn_mgr)

        # --- Supersede (depends on adapter for namespace) ---
        self._supersede = SupersedeManager(self)

        # --- CRUD (depends on serializer, supersede, conn_mgr) ---
        self._crud = CRUDOperations(self)

        # --- Versioning (depends on serializer, crud) ---
        self._version = VersionManager(self)

        # --- Stats (depends on serializer) ---
        self._stats = StatsManager(self)

        # --- Query builder with context ---
        self._query_builder = QueryBuilderWithContext(self)

        # --- Audit logger (in-memory, P2-5 refactor) ---
        self._audit = None
        try:
            from ...security.audit import AuditLogger

            # Note: AuditLogger refactored to in-memory only (P2-5).
            # Old signature: AuditLogger(get_connection_fn, namespace=...)
            # New signature: AuditLogger(max_events=10000)
            self._audit = AuditLogger()
        except (ImportError, OSError) as e:
            from ...utils.logger import logger

            logger.warning("Audit logger initialization failed: %s", e)

        # --- RRF configuration ---
        _rc = rrf_config or {}
        self._rrf_k = int(os.environ.get("CARRYMEM_RRF_K", _rc.get("k", 60)))
        self._rrf_fts_weight = float(os.environ.get("CARRYMEM_RRF_FTS_WEIGHT", _rc.get("fts_weight", 0.6)))
        self._rrf_vec_weight = float(os.environ.get("CARRYMEM_RRF_VEC_WEIGHT", _rc.get("vec_weight", 0.4)))
        self._rrf_type_boosts = _rc.get(
            "type_boosts",
            {
                "fact_declaration": 1.2,
                "decision": 1.2,
                "user_preference": 1.1,
                "task_pattern": 1.05,
                "relationship": 1.0,
                "correction": 1.15,
                "sentiment_marker": 0.5,
            },
        )

        # --- Initialize schema ---
        self._conn_mgr.get_connection()
        self._schema.init_schema()

        # --- Vector search setup (may switch connection) ---
        self._enable_vector = False
        self._embedding_model = None
        self._embedding_dim = 384
        self._embedding_model_name = embedding_model

        self._enable_vector = (
            enable_vector_search and SQLITE_VEC_AVAILABLE and PYSQLITE3_AVAILABLE and SENTENCE_TRANSFORMERS_AVAILABLE
        )

        if self._enable_vector:
            try:
                if _external_embedding_model is not None:
                    self._embedding_model = _external_embedding_model
                else:
                    self._embedding_model = _get_or_load_embedding_model(embedding_model)
                self._embedding_dim = self._embedding_model.get_embedding_dimension()  # type: ignore[attr-defined]
                # Close existing connection and switch to pysqlite3 with vec0
                self._conn_mgr.close_memory_conn_for_vector_switch()
                self._conn_mgr.set_enable_vector(True)
                # Now get_connection will create a pysqlite3 connection with vec0
                self._schema.init_vec_schema(self._embedding_dim)
                from ...utils.logger import logger

                logger.info("Vector search enabled: model=%s, dim=%d", embedding_model, self._embedding_dim)
            except (ImportError, OSError, ValueError, RuntimeError) as e:
                from ...utils.logger import logger

                self._enable_vector = False
                logger.warning("Vector search initialization failed: %s", e)

        # --- Run migrations (vector schema first if enabled) ---
        self._schema.migrate_all(enable_vector=self._enable_vector)

        # --- Semantic recall components ---
        self._enable_semantic = enable_semantic_recall
        self._expander = None
        self._merger = None

        try:
            from ...semantic.expander import SemanticExpander
            from ...semantic.merger import ResultMerger

            SEMANTIC_AVAILABLE = True
        except ImportError:
            SEMANTIC_AVAILABLE = False

        self._enable_semantic = enable_semantic_recall and SEMANTIC_AVAILABLE

        if self._enable_semantic:
            config = semantic_config or {}
            try:
                self._expander = SemanticExpander(
                    custom_synonym_files=config.get("custom_synonym_files"),
                    enable_spell_correction=config.get("enable_spell_correction", True),
                    max_expansions=config.get("max_expansions", 50),
                    edit_distance_threshold=config.get("edit_distance_threshold", 2),
                )
                self._merger = ResultMerger(
                    min_relevance=config.get("min_relevance", 0.3),
                )
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                from ...utils.logger import logger

                self._enable_semantic = False
                logger.warning("Semantic recall initialization failed: %s", e)

        # --- Recall cache ---
        self._enable_cache = enable_cache
        self._cache = None
        if enable_cache:
            try:
                from ...cache import RecallCache

                cc = cache_config or {}
                self._cache = RecallCache(
                    max_size=cc.get("max_size", 256),
                    ttl_seconds=cc.get("ttl_seconds", 300),
                )
            except ImportError:
                self._enable_cache = False

        # --- Recall engine (depends on all above) ---
        self._recall_engine = RecallEngine(self)

        # --- Knowledge graph (v0.7.0: lazy init on first access) ---
        self._knowledge_graph: Optional[Any] = None
        self._memify: Optional[Any] = None  # v0.7.2: lazy init MemifyEngine

    # ── Properties ──────────────────────────────────────────────

    @property
    def db_path(self) -> str:
        """Return the filesystem path to the SQLite database file."""
        return self._conn_mgr.db_path

    @property
    def namespace(self) -> str:
        """Return the namespace this adapter is scoped to."""
        return self._conn_mgr.namespace

    @property
    def name(self) -> str:
        """Return the adapter name ("sqlite")."""
        return "sqlite"

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Return a dict of supported backend capabilities."""
        return {
            "vector_search": self._enable_vector,
            "fts": True,
            "ttl": True,
            "batch": True,
            "graph": True,
            "semantic_recall": self._enable_semantic,
            "versioning": True,
            "backup": True,
            "audit": True,
            "namespace_filtering": True,
        }

    @property
    def semantic_enabled(self) -> bool:
        """Return whether semantic recall is enabled."""
        return self._enable_semantic

    @property
    def expander(self):
        """Return the configured semantic expander (or None)."""
        return self._expander

    # ── Public API: delegated to components ─────────────────────

    def enable_semantic_recall(self, enabled: bool = True):
        """Enable or disable semantic recall, gated on availability of the expander."""
        try:
            from ...semantic.expander import SemanticExpander  # noqa: F401
            from ...semantic.merger import ResultMerger  # noqa: F401

            SEMANTIC_AVAIL = True
        except ImportError:
            SEMANTIC_AVAIL = False
        self._enable_semantic = enabled and SEMANTIC_AVAIL and (self._expander is not None)

    def enable_vector_search(self, enabled: bool = True):
        """Enable or disable vector search, gated on dependencies and model."""
        try:
            import pysqlite3  # noqa: F401, F811
            import sqlite_vec  # noqa: F401, F811
            from sentence_transformers import SentenceTransformer  # noqa: F401, F811

            deps_ok = True
        except ImportError:
            deps_ok = False
        if enabled and not (deps_ok and self._embedding_model is not None):
            from ...utils.logger import logger

            logger.warning("Cannot enable vector search: dependencies not available or model not loaded")
            return
        self._enable_vector = enabled

    # ── Connection management ───────────────────────────────────

    def _get_connection(self):
        return self._conn_mgr.get_connection()

    def initialize(self, config: dict) -> None:
        """Initialize (re-initialize) the SQLite adapter with new config.

        Since SQLiteAdapter is fully initialized in __init__, this method
        validates that the adapter is operational and optionally applies
        runtime configuration changes.

        Args:
            config: Optional config dict. Supported keys:
                    - ``enable_vector`` (bool): Toggle vector search at runtime
                    - ``enable_semantic`` (bool): Toggle semantic recall
        """
        if config.get("enable_vector") is not None:
            self.enable_vector_search(config["enable_vector"])
        if config.get("enable_semantic") is not None:
            self.enable_semantic_recall(config["enable_semantic"])

    def store(self, entry: dict) -> str:
        """Store a memory entry from a plain dict and return its storage_key.

        Args:
            entry: Dict with ``content``, ``type`` and other MemoryEntry fields.

        Returns:
            The storage_key of the stored memory.
        """
        mem_entry = MemoryEntry.from_dict(entry)
        return self.store_entry(mem_entry).storage_key

    def store_entry(self, entry: MemoryEntry) -> StoredMemory:
        """Store a MemoryEntry and return the complete StoredMemory with metadata.

        Args:
            entry: The MemoryEntry object to persist.

        Returns:
            StoredMemory with storage_key, importance_score, version, and
            other metadata populated by the storage layer.
        """
        return self._crud.remember(entry)

    def store_batch(self, entries: list) -> list:
        """Store multiple MemoryEntry objects in a single atomic transaction.

        Args:
            entries: List of MemoryEntry objects to persist.

        Returns:
            List of StoredMemory objects (same order as input) with full
            storage metadata populated by the adapter.
        """
        return self._crud.store_batch(entries)

    def delete(self, entry_id: str) -> bool:
        """Delete a memory by its storage_key."""
        return self._crud.forget(entry_id)

    def delete_batch(self, storage_keys: list) -> dict:
        """Delete multiple memories by storage_key in a single atomic transaction.

        Args:
            storage_keys: List of storage_key strings to delete.

        Returns:
            Dict mapping each storage_key to its deletion result (True if
            deleted, False if not found).
        """
        return self._crud.delete_batch(storage_keys)

    def count(self, filter_: Optional[dict] = None) -> int:
        """Count stored memories with optional filtering.

        Args:
            filter_: Filter criteria. Supports ``type``, ``namespace`` keys.

        Returns:
            Number of matching memories.
        """
        conn = self._conn_mgr.get_connection()
        cursor = conn.cursor()
        if filter_:
            conditions: list[str] = []
            params: list = []
            if "type" in filter_:
                conditions.append("type = ?")
                params.append(filter_["type"])
            if "namespace" in filter_:
                conditions.append("namespace = ?")
                params.append(filter_["namespace"])
            if conditions:
                cursor.execute(
                    "SELECT COUNT(*) FROM memories WHERE " + " AND ".join(conditions),
                    params,
                )
                return int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM memories")
        return int(cursor.fetchone()[0])

    def health_check(self) -> dict:
        """Run a health check on the SQLite backend.

        Returns:
            Dict with status, latency_ms, and backend-specific metrics.
        """
        import time as _time

        start = _time.monotonic()
        status_detail = "healthy"
        try:
            conn = self._conn_mgr.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            row_count = cursor.fetchone()[0]
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
        except Exception as e:
            from ...utils.logger import logger

            logger.warning("SQLiteAdapter health check failed: %s", e)
            status_detail = "unhealthy"
            row_count = -1
            tables = []
        elapsed_ms = (_time.monotonic() - start) * 1000.0

        return {
            "status": status_detail,
            "latency_ms": round(elapsed_ms, 3),
            "backend": "sqlite",
            "db_path": self.db_path,
            "namespace": self.namespace,
            "row_count": row_count,
            "tables": tables,
            "vector_enabled": self._enable_vector,
            "semantic_enabled": self._enable_semantic,
        }

    def export_data(self) -> str:
        """Export all data as JSON string.

        Returns:
            JSON-serialized string of all stored memories.
        """
        import json as _json

        results = self.recall("*", limit=100000, update_access=False)
        entries = [r.to_dict() for r in results]
        return _json.dumps(entries, ensure_ascii=False, default=str)

    def import_data(self, data: str) -> int:
        """Import data from an exported JSON string.

        Args:
            data: JSON string produced by :meth:`export_data`.

        Returns:
            Number of entries imported.
        """
        import json as _json

        entries = _json.loads(data)
        count = 0
        for entry_dict in entries:
            mem_entry = MemoryEntry.from_dict(entry_dict)
            self.store_entry(mem_entry)
            count += 1
        return count

    def close(self):
        """Close the underlying connection manager and release resources."""
        self._conn_mgr.close()

    # ── Cache Management (overrides base no-op) ──────────────────────

    @property
    def has_cache(self) -> bool:
        """Whether this adapter has an active recall cache."""
        return bool(self._enable_cache and self._cache)

    def clear_cache(self) -> None:
        """Clear the entire recall cache."""
        if self._enable_cache and self._cache:
            self._cache.clear()

    def invalidate_cache(self, keys: Optional[set] = None) -> None:
        """Invalidate cache entries for given keys, or all if None."""
        if not self._enable_cache or not self._cache:
            return
        if keys is None:
            self._cache.invalidate()
        else:
            self._cache.invalidate_keys(self.namespace, keys)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        # NOTE: Broad exception in __del__ is intentional to prevent exceptions
        # from propagating during garbage collection, which can cause crashes.
        except Exception as e:
            from ...utils.logger import logger

            logger.debug("SQLiteAdapter.__del__ close failed: %s", e)

    # ── CRUD operations ─────────────────────────────────────────

    def forget_expired(self) -> int:
        """Delete all expired memories and return the count removed."""
        return self._crud.forget_expired()

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Optional[StoredMemory]:
        """Update an existing memory's content, recording the change reason."""
        return self._crud.update_memory(storage_key, new_content, reason)

    def get_by_key(self, storage_key: str):
        """Retrieve a stored memory by its storage_key (or None if missing)."""
        return self._crud.get_by_key(storage_key)

    # ── Recall operations ───────────────────────────────────────

    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[list] = None,
        update_access: bool = False,
    ) -> list:
        """Retrieve memories matching a query with optional filters."""
        return self._recall_engine.recall(query, filters, limit, namespaces, update_access)

    def recall_aggregated(
        self, memory_type: Optional[str] = None, namespaces: Optional[list] = None, limit_per_type: int = 50
    ) -> Dict[str, list]:
        """Return memories grouped by type, aggregated across namespaces."""
        return self._stats.recall_aggregated(memory_type, namespaces, limit_per_type)

    def recall_timeline(self, topic: str, namespaces: Optional[list] = None, limit: int = 20) -> list:
        """Return a chronological timeline of memories for a topic."""
        return self._stats.recall_timeline(topic, namespaces, limit)

    # ── Knowledge graph (v0.7.0) ────────────────────────────────

    def _get_knowledge_graph(self):
        """Lazily initialize the KnowledgeGraph instance.

        Reuses the EntityNormalizer from the classification layer if
        available; otherwise creates a standalone EntityNormalizer.
        """
        if self._knowledge_graph is not None:
            return self._knowledge_graph
        from ...layers.knowledge_graph import KnowledgeGraph

        entity_normalizer = None
        try:
            from ...layers.entity_normalizer import EntityNormalizer

            entity_normalizer = EntityNormalizer(
                conn_mgr=self._conn_mgr,
                input_validator=None,
            )
        except (ImportError, TypeError) as e:
            from ...utils.logger import logger

            logger.debug("KnowledgeGraph EntityNormalizer init failed: %s", e)

        self._knowledge_graph = KnowledgeGraph(
            conn_mgr=self._conn_mgr,
            entity_normalizer=entity_normalizer,
        )
        return self._knowledge_graph

    def _get_memify(self):
        """Lazily initialize the MemifyEngine instance (v0.7.2)."""
        if self._memify is not None:
            return self._memify
        from ...layers.memify import MemifyEngine

        self._memify = MemifyEngine(adapter=self)
        return self._memify

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
            namespace: Namespace scope (default: adapter's namespace).
            min_co_occurrence: Minimum co-occurrence for derive/reinforce (default 3).
            max_derived: Maximum derived facts per run (default 10).
            stale_days: Days without access for decay (default 90).
            min_importance: Importance threshold for decay (default 0.3).

        Returns:
            Dict with derived_facts, edges_reinforced, decayed counts.
        """
        ns = namespace or self.namespace
        memify = self._get_memify()
        return {
            "derived_facts": memify.derive_facts(
                namespace=ns, min_co_occurrence=min_co_occurrence, max_derived=max_derived
            ),
            "edges_reinforced": memify.reinforce_edges(namespace=ns, min_co_occurrence=min_co_occurrence),
            "decayed": memify.auto_decay(namespace=ns, stale_days=stale_days, min_importance=min_importance),
        }

    def recall_by_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """Find memories mentioning a specific entity (v0.7.0).

        Args:
            entity_text: The entity text to search for.
            entity_type: Optional entity type filter.
            namespace: Optional namespace filter (defaults to adapter's).
            limit: Maximum results.

        Returns:
            List of memory dicts.
        """
        ns = namespace or self.namespace
        return list(self._get_knowledge_graph().recall_by_entity(entity_text, entity_type, ns, limit))

    def recall_by_relation(
        self,
        entity_text: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> list:
        """Find memories connected to an entity via relations (v0.7.0).

        Args:
            entity_text: The entity to find relations for.
            relation_type: Optional relation type filter.
            direction: "outgoing", "incoming", or "both".
            namespace: Optional namespace filter.
            limit: Maximum results.

        Returns:
            List of memory dicts.
        """
        ns = namespace or self.namespace
        return list(self._get_knowledge_graph().recall_by_relation(entity_text, relation_type, direction, ns, limit))

    def recall_graph(
        self,
        entity_text: str,
        max_hops: int = 2,
        namespace: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Multi-hop graph traversal from an entity (v0.7.0).

        Args:
            entity_text: The starting entity.
            max_hops: Maximum traversal depth.
            namespace: Optional namespace filter.
            limit: Maximum memories to return.

        Returns:
            Dict with "entities" and "memories" lists.
        """
        ns = namespace or self.namespace
        return dict(self._get_knowledge_graph().recall_graph(entity_text, max_hops, ns, limit))

    def shortest_path(
        self,
        src_entity: str,
        dst_entity: str,
        max_hops: int = 4,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find the shortest path between two entities via bidirectional BFS (v0.8.0).

        Args:
            src_entity: The source entity text.
            dst_entity: The destination entity text.
            max_hops: Maximum path length to search (default 4, hard cap 10).
            namespace: Optional namespace filter (defaults to adapter's).

        Returns:
            Dict with "path" (list of entity texts), "length" (edge count),
            and "found" (bool).
        """
        ns = namespace or self.namespace
        return dict(self._get_knowledge_graph().shortest_path(src_entity, dst_entity, max_hops, ns))

    def get_memory_impact(
        self,
        memory_key: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute the graph impact of a memory (v0.8.0).

        impact_score = entity_count * 0.4 + relation_count * 0.4 + cross_namespace * 0.2

        Args:
            memory_key: The memory's storage_key.
            namespace: Optional namespace filter (defaults to adapter's).

        Returns:
            Dict with "memory_id", "entity_count", "relation_count",
            "cross_namespace", and "impact_score".
        """
        ns = namespace or self.namespace
        return dict(self._get_knowledge_graph().get_memory_impact(memory_key, ns))

    def add_graph_relation(
        self,
        src_entity_text: str,
        dst_entity_text: str,
        relation_type: str,
        source_memory_key: Optional[str] = None,
        weight: float = 1.0,
        namespace: Optional[str] = None,
        confidence: str = "EXTRACTED",
    ) -> bool:
        """Add a relation between two entities in the knowledge graph (v0.7.0).

        Args:
            src_entity_text: Source entity text.
            dst_entity_text: Destination entity text.
            relation_type: Relation type (e.g. "prefers", "works_on").
            source_memory_key: Optional evidence memory key.
            weight: Relation strength (default 1.0).
            namespace: Optional namespace (defaults to adapter's).
            confidence: Edge confidence label (v0.8.0). One of
                "EXTRACTED" (default), "INFERRED", "AMBIGUOUS".

        Returns:
            True if relation was added.
        """
        ns = namespace or self.namespace
        return bool(
            self._get_knowledge_graph().add_relation(
                src_entity_text,
                dst_entity_text,
                relation_type,
                source_memory_key,
                weight,
                ns,
                confidence,
            )
        )

    def list_graph_entities(
        self, namespace: Optional[str] = None, entity_type: Optional[str] = None, limit: int = 100
    ) -> list:
        """List entities in the knowledge graph (v0.7.0)."""
        ns = namespace or self.namespace
        return list(self._get_knowledge_graph().list_entities(ns, entity_type, limit))

    def list_graph_relations(
        self, namespace: Optional[str] = None, relation_type: Optional[str] = None, limit: int = 100
    ) -> list:
        """List relations in the knowledge graph (v0.7.0)."""
        ns = namespace or self.namespace
        return list(self._get_knowledge_graph().list_relations(ns, relation_type, limit))

    def get_graph_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get knowledge graph statistics (v0.7.0)."""
        ns = namespace or self.namespace
        return dict(self._get_knowledge_graph().get_stats(ns))

    def store_graph_entities(self, storage_key: str, text: str, namespace: Optional[str] = None) -> int:
        """Extract entities from text and store them in the knowledge graph (v0.7.0).

        Called automatically after store_entry() to populate the graph.
        Uses EntityNormalizer (pattern-based, zero LLM).

        Args:
            storage_key: The memory's storage_key.
            text: Text to extract entities from.
            namespace: Optional namespace (defaults to adapter's).

        Returns:
            Number of entities stored.
        """
        ns = namespace or self.namespace
        return int(self._get_knowledge_graph().extract_and_store_entities(storage_key, text, ns))

    # ── Multi-Mode Retrieval (v0.7.1) ──────────────────────────

    def recall_by_time(
        self,
        start: datetime,
        end: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        namespaces: Optional[list] = None,
    ) -> list:
        """Retrieve memories within a time range (v0.7.1).

        Args:
            start: Start datetime (inclusive).
            end: End datetime (exclusive). Defaults to now.
            filters: Optional metadata filters.
            limit: Maximum results.
            namespaces: Optional namespace filter.

        Returns:
            List of memory dicts ordered by created_at descending.
        """
        results = self._recall_engine.search_by_time(start, end, filters, limit, namespaces)
        return [r.to_dict() for r in results if r]

    def recall_semantic(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespaces: Optional[list] = None,
    ) -> list:
        """Pure vector similarity search (v0.7.1).

        Bypasses FTS5 and RRF fusion — returns raw vector similarity results.
        Requires vector search enabled (capabilities["vector_search"] == True).

        Args:
            query: Natural language query.
            top_k: Number of results.
            filters: Optional metadata filters.
            namespaces: Optional namespace filter.

        Returns:
            List of memory dicts ordered by vector similarity descending.
        """
        if not self._enable_vector:
            from ...utils.logger import logger

            logger.warning("recall_semantic called but vector search is not enabled")
            return []
        results = self._recall_engine.vector_search_only(query, filters, top_k, namespaces)
        return [r.to_dict() for r in results if r]

    def recall_hybrid(
        self,
        query: str,
        fts_weight: Optional[float] = None,
        vec_weight: Optional[float] = None,
        rrf_k: Optional[int] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        namespaces: Optional[list] = None,
    ) -> list:
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
            namespaces: Optional namespace filter.

        Returns:
            List of memory dicts ordered by fused RRF score descending.
        """
        results = self._recall_engine.hybrid_search(query, fts_weight, vec_weight, rrf_k, filters, limit, namespaces)
        return [r.to_dict() for r in results if r]

    def recall_multi_mode(
        self,
        query: str,
        modes: Optional[List[str]] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        namespaces: Optional[list] = None,
        time_range: Optional[tuple] = None,
        entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unified multi-mode retrieval interface (v0.7.1).

        Args:
            query: Search query (used for fts/vector/hybrid modes).
            modes: Retrieval modes. Default: ["fts", "vector"].
                   Options: "fts", "vector", "hybrid", "graph", "time", "entity".
            limit: Maximum results per mode.
            filters: Optional metadata filters.
            namespaces: Optional namespace filter.
            time_range: (start, end) for "time" mode.
            entity: Entity text for "entity"/"graph" modes.

        Returns:
            Dict with "modes", "merged", "mode_count", "total_count".
        """
        if modes is None:
            modes = ["fts", "vector"] if self._enable_vector else ["fts"]

        mode_results: Dict[str, list] = {}
        for mode in modes:
            # Initialize every requested mode with empty list to ensure it appears in results
            mode_results[mode] = []
            try:
                if mode == "fts":
                    rows = self._recall_engine.recall(
                        query, filters=filters, limit=limit, namespaces=namespaces, update_access=False
                    )
                    mode_results["fts"] = [r.to_dict() for r in rows if r]
                elif mode == "vector":
                    if self._enable_vector:
                        rows = self._recall_engine.vector_search_only(query, filters, limit, namespaces)
                        mode_results["vector"] = [r.to_dict() for r in rows if r]
                elif mode == "hybrid":
                    rows = self._recall_engine.hybrid_search(query, None, None, None, filters, limit, namespaces)
                    mode_results["hybrid"] = [r.to_dict() for r in rows if r]
                elif mode == "graph":
                    if entity:
                        graph_result = self.recall_graph(entity, limit=limit, namespace=self.namespace)
                        mode_results["graph"] = list(graph_result.get("memories", []))
                elif mode == "time":
                    if time_range:
                        start_dt, end_dt = time_range[0], time_range[1]
                        rows = self._recall_engine.search_by_time(start_dt, end_dt, filters, limit, namespaces)
                        mode_results["time"] = [r.to_dict() for r in rows if r]
                elif mode == "entity":
                    if entity:
                        mode_results["entity"] = list(
                            self.recall_by_entity(entity, limit=limit, namespace=self.namespace)
                        )
            except (ValueError, KeyError, TypeError, RuntimeError) as e:
                from ...utils.logger import logger

                logger.warning("recall_multi_mode mode '%s' failed: %s", mode, e)
                mode_results[mode] = []

        # Merge and deduplicate by storage_key
        seen_keys: set = set()
        merged: list = []
        for mode_name, mems in mode_results.items():
            for m in mems:
                if isinstance(m, dict):
                    key = m.get("storage_key", "")
                    if key and key not in seen_keys:
                        seen_keys.add(key)
                        merged.append(m)

        return {
            "modes": mode_results,
            "merged": merged[:limit],
            "mode_count": len(mode_results),
            "total_count": len(merged),
        }

    # ── Version management ──────────────────────────────────────

    def get_memory_history(self, storage_key: str) -> list:
        """Return the version history of a memory entry."""
        return self._version.get_memory_history(storage_key)

    def rollback_memory(self, storage_key: str, version: int) -> Optional[StoredMemory]:
        """Roll back a memory entry to a specific version."""
        return self._version.rollback_memory(storage_key, version)

    # ── Statistics ───────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics for stored memories."""
        return self._stats.get_stats()

    def get_profile(self) -> Dict[str, Any]:
        """Return the consolidated memory profile."""
        return self._stats.get_profile()

    def recalculate_importance(self) -> int:
        """Recalculate importance scores for all memories; return count updated."""
        with self._conn_mgr.file_lock:
            return self._schema.recalculate_all_importance()  # type: ignore[no-any-return]

    # ── Internal helpers exposed for sub-component access ───────

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt a plaintext field value for storage."""
        return self._security.encrypt_field(plaintext)

    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt a stored ciphertext field value."""
        return self._security.decrypt_field(ciphertext)
