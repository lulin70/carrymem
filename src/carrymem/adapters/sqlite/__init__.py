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
import warnings
from typing import Any, Dict, Optional

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
    import sqlite_vec  # type: ignore[import-not-found]  # noqa: F401

    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False

try:
    import pysqlite3  # type: ignore[import-not-found]  # noqa: F401

    PYSQLITE3_AVAILABLE = True
except ImportError:
    PYSQLITE3_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


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
                    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                    self._embedding_model = SentenceTransformer(embedding_model)
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
            "graph": False,
            "semantic_recall": self._enable_semantic,
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
        stored = self._crud.remember(mem_entry)
        return stored.storage_key

    def delete(self, entry_id: str) -> bool:
        """Delete a memory by its storage_key."""
        return self._crud.forget(entry_id)

    def count(self, filter_: Optional[dict] = None) -> int:
        """Count stored memories with optional filtering.

        Args:
            filter_: Filter criteria. Supports ``type``, ``namespace`` keys.

        Returns:
            Number of matching memories.
        """
        stats = self.get_stats()
        if filter_ and "type" in filter_:
            by_type = stats.get("by_type", {})
            return by_type.get(filter_["type"], 0)  # type: ignore[no-any-return]
        return stats.get("total_count", 0)  # type: ignore[no-any-return]

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
            self._crud.remember(mem_entry)
            count += 1
        return count

    def search_fulltext(self, query: str) -> list[dict]:
        """Full-text search across all stored entries.

        Args:
            query: Free-text search string.

        Returns:
            List of matching entry dicts.
        """
        results = self.recall(query, update_access=False)
        return [r.to_dict() for r in results]

    def close(self):
        """Close the underlying connection manager and release resources."""
        self._conn_mgr.close()

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

    def remember(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        """Store a memory entry (deprecated, use store() instead)."""
        warnings.warn(
            "remember() is deprecated, use store() instead. " "Will be removed in v0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._crud.remember(entry, _skip_commit)

    def remember_batch(self, entries: list) -> list:
        """Store multiple memory entries in a single batch."""
        return self._crud.remember_batch(entries)

    def forget(self, storage_key: str) -> bool:
        """Delete a memory by storage_key (deprecated, use delete() instead)."""
        warnings.warn(
            "forget() is deprecated, use delete() instead. " "Will be removed in v0.5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._crud.forget(storage_key)

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

    def recall(  # type: ignore[override]
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[list] = None,
        update_access: bool = True,
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
