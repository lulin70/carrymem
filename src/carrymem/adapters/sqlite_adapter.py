"""SQLite Storage Adapter — CarryMem default storage backend.

Features:
- Zero-config: auto-creates database at ~/.carrymem/memories.db
- FTS5 full-text search for content and original_message
- Content deduplication via content_hash
- Tier-based TTL expiry
- Atomic batch operations via transactions
- Semantic recall with synonym expansion, spell correction,
  cross-language mapping, and result fusion (zero external dependencies)
- Thread-safe with ThreadLocal connections and proper resource management
- Vector search with sqlite-vec + sentence-transformers (optional dependency)
"""

import json
import os
import sqlite3
import struct
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import MemoryEntry, StorageAdapter, StoredMemory
from ..exceptions import DatabaseError, DBConnectionError, QueryError
from ..scoring import calculate_importance
from ..utils.helpers import escape_like, content_hash, TIER_TTL


try:
    from ..semantic.expander import SemanticExpander
    from ..semantic.merger import ResultMerger
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False

try:
    import pysqlite3 as _pysqlite3
    PYSQLITE3_AVAILABLE = True
except ImportError:
    PYSQLITE3_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    original_message TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    tier INTEGER NOT NULL DEFAULT 2,
    source_layer TEXT NOT NULL DEFAULT 'unknown',
    reasoning TEXT,
    suggested_action TEXT NOT NULL DEFAULT 'store',
    recall_hint TEXT,
    metadata TEXT,
    storage_key TEXT UNIQUE NOT NULL,
    namespace TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    importance_score REAL NOT NULL DEFAULT 0.0,
    last_accessed_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    raw_text,
    original_message,
    content='memories',
    content_rowid='rowid',
    tokenize='trigram'
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(tier);
CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(confidence);
CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at);
CREATE INDEX IF NOT EXISTS idx_memories_content_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_memories_type_confidence ON memories(type, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_memories_namespace_tier ON memories(namespace, tier);
CREATE INDEX IF NOT EXISTS idx_memories_namespace_type ON memories(namespace, type);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_namespace_created ON memories(namespace, created_at DESC);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, raw_text, original_message)
    VALUES (new.rowid, new.content, new.raw_text, new.original_message);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, raw_text, original_message)
    VALUES ('delete', old.rowid, old.content, old.raw_text, old.original_message);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, raw_text, original_message)
    VALUES ('delete', old.rowid, old.content, old.raw_text, old.original_message);
    INSERT INTO memories_fts(rowid, content, raw_text, original_message)
    VALUES (new.rowid, new.content, new.raw_text, new.original_message);
END;
"""

_MIGRATION_SQL = """
ALTER TABLE memories ADD COLUMN namespace TEXT NOT NULL DEFAULT 'default';
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);
"""

_V050_MIGRATION_SQL = [
    "ALTER TABLE memories ADD COLUMN importance_score REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE memories ADD COLUMN last_accessed_at TEXT",
    "ALTER TABLE memories ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
]

_V050_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memories_namespace_importance ON memories(namespace, importance_score DESC)",
]

_V060_MIGRATION_SQL = [
    "ALTER TABLE memories ADD COLUMN raw_text TEXT NOT NULL DEFAULT ''",
]

_V080_MIGRATION_SQL = [
    "ALTER TABLE memories ADD COLUMN superseded_at TEXT",
    "ALTER TABLE memories ADD COLUMN supersedes TEXT",
]

_V080_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_memories_superseded ON memories(superseded_at)",
    "CREATE INDEX IF NOT EXISTS idx_memories_supersedes ON memories(supersedes)",
]

_V090_MIGRATION_SQL = [
    "ALTER TABLE memories ADD COLUMN memory_nature TEXT NOT NULL DEFAULT 'state'",
    "ALTER TABLE memories ADD COLUMN version_chain_id TEXT",
    "ALTER TABLE memories ADD COLUMN version_number INTEGER NOT NULL DEFAULT 1",
]

_V090_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_memories_nature ON memories(memory_nature)",
    "CREATE INDEX IF NOT EXISTS idx_memories_chain ON memories(version_chain_id)",
    "CREATE INDEX IF NOT EXISTS idx_memories_chain_version ON memories(version_chain_id, version_number)",
]

_V060_FTS_REBUILD_SQL = [
    "DROP TABLE IF EXISTS memories_fts",
    """CREATE VIRTUAL TABLE memories_fts USING fts5(
        content,
        raw_text,
        original_message,
        content='memories',
        content_rowid='rowid',
        tokenize='trigram'
    )""",
    "INSERT INTO memories_fts(memories_fts) VALUES('rebuild')",
    "DROP TRIGGER IF EXISTS memories_ai",
    "DROP TRIGGER IF EXISTS memories_ad",
    "DROP TRIGGER IF EXISTS memories_au",
    """CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
        INSERT INTO memories_fts(rowid, content, raw_text, original_message)
        VALUES (new.rowid, new.content, new.raw_text, new.original_message);
    END""",
    """CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, content, raw_text, original_message)
        VALUES ('delete', old.rowid, old.content, old.raw_text, old.original_message);
    END""",
    """CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, content, raw_text, original_message)
        VALUES ('delete', old.rowid, old.content, old.raw_text, old.original_message);
        INSERT INTO memories_fts(rowid, content, raw_text, original_message)
        VALUES (new.rowid, new.content, new.raw_text, new.original_message);
    END""",
]

_VERSION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memory_versions (
    version_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    confidence REAL NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    change_reason TEXT,
    namespace TEXT NOT NULL DEFAULT 'default'
);

CREATE INDEX IF NOT EXISTS idx_mv_memory_id ON memory_versions(memory_id);
CREATE INDEX IF NOT EXISTS idx_mv_memory_version ON memory_versions(memory_id, version);
"""


def _default_db_path() -> str:
    home = os.path.expanduser("~")
    carrymem_dir = os.path.join(home, ".carrymem")
    os.makedirs(carrymem_dir, exist_ok=True)
    return os.path.join(carrymem_dir, "memories.db")


class SQLiteAdapter(StorageAdapter):
    """SQLite-based storage adapter — CarryMem's default backend.

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
        _external_embedding_model: Any = None,
        rrf_config: Optional[Dict[str, Any]] = None,
    ):
        self._namespace = namespace
        self._db_path = db_path or _default_db_path()
        self._lock = threading.Lock()

        self._local = threading.local()
        self._closed = False
        self._all_connections: Dict[int, sqlite3.Connection] = {}
        self._conn_lock = threading.Lock()

        # Initialize encryption
        self._encryption = None
        if encryption_key is not None:
            try:
                from ..security.encryption import MemoryEncryption
                self._encryption = MemoryEncryption(key=encryption_key)
            except Exception as e:
                from carrymem.utils.logger import logger
                logger.warning(f"Encryption initialization failed, using plaintext: {e}")
                self._encryption = None

        # Initialize audit logger
        self._audit = None
        try:
            from ..security.audit import AuditLogger
            self._audit = AuditLogger(self._get_connection, namespace=namespace)
        except Exception:
            pass

        # Pre-set vector search flag before _get_connection() is called
        self._enable_vector = False
        self._embedding_model = None
        self._embedding_dim = 384
        self._embedding_model_name = embedding_model

        # RRF configuration (extractable to config file)
        _rc = rrf_config or {}
        self._rrf_k = int(os.environ.get('CARRYMEM_RRF_K', _rc.get('k', 60)))
        self._rrf_fts_weight = float(os.environ.get('CARRYMEM_RRF_FTS_WEIGHT', _rc.get('fts_weight', 0.6)))
        self._rrf_vec_weight = float(os.environ.get('CARRYMEM_RRF_VEC_WEIGHT', _rc.get('vec_weight', 0.4)))
        self._rrf_type_boosts = _rc.get('type_boosts', {
            "fact_declaration": 1.2,
            "decision": 1.2,
            "user_preference": 1.1,
            "task_pattern": 1.05,
            "relationship": 1.0,
            "correction": 1.15,
            "sentiment_marker": 0.5,
        })
        
        # Initialize schema with main connection
        conn = self._get_connection()
        self._init_schema()
        self._migrate_namespace()
        self._migrate_v050()
        self._migrate_v060()
        self._migrate_v080()
        self._migrate_v090()

        # Initialize semantic recall components
        self._enable_semantic = enable_semantic_recall and SEMANTIC_AVAILABLE
        self._expander = None
        self._merger = None

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
            except Exception as e:
                self._enable_semantic = False
                from carrymem.utils.logger import logger
                logger.warning(f"Semantic recall initialization failed: {e}")

        # Initialize recall cache
        self._enable_cache = enable_cache
        self._cache = None
        if enable_cache:
            try:
                from ..cache import RecallCache
                cc = cache_config or {}
                self._cache = RecallCache(
                    max_size=cc.get("max_size", 256),
                    ttl_seconds=cc.get("ttl_seconds", 300),
                )
            except ImportError:
                self._enable_cache = False

        # Initialize vector search
        self._enable_vector = (
            enable_vector_search
            and SQLITE_VEC_AVAILABLE
            and PYSQLITE3_AVAILABLE
            and SENTENCE_TRANSFORMERS_AVAILABLE
        )

        if self._enable_vector:
            try:
                if _external_embedding_model is not None:
                    self._embedding_model = _external_embedding_model
                else:
                    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
                    self._embedding_model = SentenceTransformer(embedding_model)
                self._embedding_dim = self._embedding_model.get_embedding_dimension()
                # Close existing sqlite3 connection and switch to pysqlite3 with vec0
                if hasattr(self._local, 'conn') and self._local.conn is not None:
                    try:
                        self._local.conn.close()
                    except Exception:
                        pass
                    with self._conn_lock:
                        self._all_connections.pop(id(self._local.conn), None)
                    self._local.conn = None
                # Now _get_connection() will create a pysqlite3 connection with vec0
                self._init_vec_schema()
                self._migrate_v070()
                from carrymem.utils.logger import logger
                logger.info(
                    f"Vector search enabled: model={embedding_model}, dim={self._embedding_dim}"
                )
            except Exception as e:
                self._enable_vector = False
                from carrymem.utils.logger import logger
                logger.warning(f"Vector search initialization failed: {e}")

    @property
    def db_path(self) -> str:
        return self._db_path

    def _get_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise DBConnectionError("Adapter has been closed")
        
        is_memory = self._db_path == ":memory:"
        
        if is_memory:
            if not hasattr(self, '_memory_conn') or self._memory_conn is None:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys=ON")
                self._memory_conn = conn
                with self._conn_lock:
                    self._all_connections[id(conn)] = conn
            return self._memory_conn
        
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            try:
                use_pysqlite3 = self._enable_vector and PYSQLITE3_AVAILABLE
                if use_pysqlite3:
                    conn = _pysqlite3.connect(self._db_path)
                    conn.row_factory = _pysqlite3.Row
                else:
                    conn = sqlite3.connect(self._db_path)
                    conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                if use_pysqlite3 and SQLITE_VEC_AVAILABLE:
                    try:
                        conn.enable_load_extension(True)
                        sqlite_vec.load(conn)
                    except Exception:
                        pass
                self._local.conn = conn
                with self._conn_lock:
                    self._all_connections[id(conn)] = conn
            except sqlite3.Error as e:
                raise DBConnectionError(f"Failed to connect to database: {e}") from e
        
        return self._local.conn

    def _init_schema(self):
        conn = self._get_connection()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.executescript(_VERSION_SCHEMA_SQL)
            conn.commit()
            self._migrate_fts_tokenizer()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize schema: {e}") from e

    def _get_by_key(self, storage_key: str):
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM memories WHERE storage_key = ?",
                (storage_key,),
            ).fetchone()
            if row:
                return self._row_to_stored(row)
            return None
        except sqlite3.Error:
            return None

    def _migrate_namespace(self):
        conn = self._get_connection()
        try:
            conn.execute("SELECT namespace FROM memories LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.executescript(_MIGRATION_SQL)
                conn.executescript(_CREATE_INDEX_SQL)
                conn.commit()
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to migrate namespace: {e}") from e

    def _migrate_fts_tokenizer(self):
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='memories_fts'"
            ).fetchone()
            if row and 'unicode61' in (row[0] or ''):
                conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
                conn.commit()
        except sqlite3.OperationalError:
            pass

    def _migrate_v050(self):
        conn = self._get_connection()
        needs_recalculate = False
        try:
            conn.execute("SELECT importance_score FROM memories LIMIT 1")
        except sqlite3.OperationalError:
            needs_recalculate = True
            try:
                for sql in _V050_MIGRATION_SQL:
                    try:
                        conn.execute(sql)
                    except sqlite3.OperationalError:
                        pass
                conn.commit()
            except sqlite3.Error as e:
                from carrymem.utils.logger import logger
                logger.warning(f"Failed to migrate v0.5.0 columns: {e}")

        for sql in _V050_INDEX_SQL:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        conn.commit()

        if needs_recalculate:
            self._recalculate_all_importance()

    def _recalculate_all_importance(self):
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT storage_key, confidence, type, created_at, access_count FROM memories"
            ).fetchall()
            now = datetime.now(timezone.utc)
            for row in rows:
                try:
                    created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else now
                    score = calculate_importance(
                        confidence=row["confidence"],
                        memory_type=row["type"],
                        created_at=created_at,
                        access_count=row["access_count"],
                        now=now,
                    )
                    conn.execute(
                        "UPDATE memories SET importance_score = ? WHERE storage_key = ?",
                        (score, row["storage_key"]),
                    )
                except (ValueError, TypeError):
                    continue
            conn.commit()
        except sqlite3.Error as e:
            from carrymem.utils.logger import logger
            logger.warning(f"Failed to recalculate importance scores: {e}")

    def _migrate_v060(self):
        conn = self._get_connection()
        needs_fts_rebuild = False
        try:
            conn.execute("SELECT raw_text FROM memories LIMIT 1")
        except sqlite3.OperationalError:
            needs_fts_rebuild = True
            try:
                for sql in _V060_MIGRATION_SQL:
                    try:
                        conn.execute(sql)
                    except sqlite3.OperationalError:
                        pass
                conn.commit()
            except sqlite3.Error as e:
                from carrymem.utils.logger import logger
                logger.warning(f"Failed to migrate v0.6.0 raw_text column: {e}")

        fts_needs_raw_text = False
        try:
            conn.execute("SELECT raw_text FROM memories_fts LIMIT 0")
        except sqlite3.OperationalError:
            fts_needs_raw_text = True

        if needs_fts_rebuild or fts_needs_raw_text:
            try:
                for sql in _V060_FTS_REBUILD_SQL:
                    try:
                        conn.execute(sql)
                    except sqlite3.OperationalError:
                        pass
                conn.commit()
                from carrymem.utils.logger import logger
                logger.info("FTS5 rebuilt with raw_text column")
            except sqlite3.Error as e:
                from carrymem.utils.logger import logger
                logger.warning(f"Failed to rebuild FTS5: {e}")

    def _init_vec_schema(self):
        if not self._enable_vector:
            return
        conn = self._get_connection()
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
                    memory_id TEXT PRIMARY KEY,
                    embedding float[{self._embedding_dim}]
                )
            """)
            conn.commit()
        except Exception as e:
            from carrymem.utils.logger import logger
            logger.warning(f"Failed to create memory_vectors table: {e}")

    def _migrate_v070(self):
        if not self._enable_vector:
            return
        conn = self._get_connection()
        try:
            conn.execute("SELECT memory_id FROM memory_vectors LIMIT 1")
        except sqlite3.OperationalError:
            self._init_vec_schema()

    def _migrate_v080(self):
        conn = self._get_connection()
        try:
            conn.execute("SELECT superseded_at FROM memories LIMIT 1")
        except sqlite3.OperationalError:
            for sql in _V080_MIGRATION_SQL:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass
            for sql in _V080_INDEX_SQL:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass

    def _migrate_v090(self):
        """Add memory_nature, version_chain_id, version_number columns."""
        conn = self._get_connection()
        try:
            conn.execute("SELECT memory_nature FROM memories LIMIT 1")
        except sqlite3.OperationalError:
            for sql in _V090_MIGRATION_SQL:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass
            for sql in _V090_INDEX_SQL:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass
            # Backfill: infer memory_nature from type
            conn.execute(
                "UPDATE memories SET memory_nature = 'event' "
                "WHERE type IN ('session_summary', 'task_pattern')"
            )
            conn.commit()

    def close(self):
        self._closed = True
        with self._conn_lock:
            for conn_id, conn in self._all_connections.items():
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        if hasattr(self._local, 'conn'):
            self._local.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def __del__(self):
        """Destructor to ensure connections are closed."""
        try:
            self.close()
        except Exception:
            pass

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def name(self) -> str:
        return "sqlite"

    @property
    def capabilities(self) -> Dict[str, bool]:
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
        """Return the SemanticExpander instance (for custom synonym management)."""
        return self._expander

    def enable_semantic_recall(self, enabled: bool = True):
        """Enable or disable semantic recall at runtime."""
        self._enable_semantic = enabled and SEMANTIC_AVAILABLE and (self._expander is not None)

    def enable_vector_search(self, enabled: bool = True):
        """Enable or disable vector search at runtime."""
        if enabled and not (SQLITE_VEC_AVAILABLE and PYSQLITE3_AVAILABLE and SENTENCE_TRANSFORMERS_AVAILABLE and self._embedding_model is not None):
            from carrymem.utils.logger import logger
            logger.warning("Cannot enable vector search: dependencies not available or model not loaded")
            return
        self._enable_vector = enabled

    def remember(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        with self._lock:
            result = self._remember_impl(entry, _skip_commit)
        if self._enable_cache and self._cache:
            self._cache.invalidate()
        return result

    def _remember_impl(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        conn = self._get_connection()
        c_hash = content_hash(entry.content, entry.type)

        existing = conn.execute(
            "SELECT storage_key, raw_text FROM memories WHERE content_hash = ? AND namespace = ?",
            (c_hash, self._namespace),
        ).fetchone()
        if existing:
            if not existing["raw_text"] and entry.raw_text:
                try:
                    conn.execute(
                        "UPDATE memories SET raw_text = ? WHERE storage_key = ?",
                        (self._encrypt_field(entry.raw_text), existing["storage_key"]),
                    )
                    conn.commit()
                except sqlite3.Error:
                    pass
            stored = self._row_to_stored(
                conn.execute(
                    "SELECT * FROM memories WHERE content_hash = ? AND namespace = ?",
                    (c_hash, self._namespace),
                ).fetchone()
            )
            return stored

        storage_key = f"cm_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{c_hash[:8]}"
        now = datetime.now(timezone.utc)

        ttl = TIER_TTL.get(entry.tier)
        expires_at = (now + ttl).isoformat() if ttl else None

        metadata_json = json.dumps(entry.metadata) if entry.metadata else "{}"
        recall_hint_json = json.dumps(entry.recall_hint) if entry.recall_hint else None
        original_message = entry.metadata.get("original_message", "") if entry.metadata else ""

        imp_score = calculate_importance(
            confidence=entry.confidence,
            memory_type=entry.type,
            created_at=now,
            access_count=0,
            now=now,
        )

        store_content = self._encrypt_field(entry.content)
        store_original = self._encrypt_field(original_message)
        store_raw_text = self._encrypt_field(entry.raw_text)

        conn.execute(
            """INSERT INTO memories
               (id, type, content, raw_text, original_message, confidence, tier,
                source_layer, reasoning, suggested_action, recall_hint,
                metadata, storage_key, namespace, created_at, updated_at, expires_at,
                access_count, content_hash, importance_score, last_accessed_at, version,
                memory_nature, version_chain_id, version_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, 1, ?, ?, ?)""",
            (
                entry.id or storage_key,
                entry.type,
                store_content,
                store_raw_text,
                store_original,
                entry.confidence,
                entry.tier,
                entry.source_layer,
                entry.reasoning,
                entry.suggested_action,
                recall_hint_json,
                metadata_json,
                storage_key,
                self._namespace,
                now.isoformat(),
                now.isoformat(),
                expires_at,
                c_hash,
                imp_score,
                entry.memory_nature,
                entry.version_chain_id,
                entry.version_number,
            ),
        )
        if not _skip_commit:
            conn.commit()

        if self._enable_vector and self._embedding_model:
            text_to_embed = entry.raw_text or entry.content
            if text_to_embed:
                try:
                    embedding = self._embedding_model.encode(text_to_embed)
                    memory_id = entry.id or storage_key
                    conn.execute(
                        "INSERT OR REPLACE INTO memory_vectors(memory_id, embedding) VALUES(?, ?)",
                        (memory_id, struct.pack(f'{self._embedding_dim}f', *embedding.tolist())),
                    )
                    if not _skip_commit:
                        conn.commit()
                except Exception as e:
                    from carrymem.utils.logger import logger
                    logger.warning(f"Failed to store embedding: {e}")

        if self._audit:
            self._audit.log_operation(
                operation="remember",
                storage_key=storage_key,
                memory_type=entry.type,
                success=True,
                details={"confidence": entry.confidence, "tier": entry.tier},
            )

        self._auto_supersede(conn, storage_key, entry, self._namespace)

        # Set initial version_chain_id for state memories (if not set by supersede)
        if entry.memory_nature == "state" and not entry.version_chain_id:
            try:
                conn.execute(
                    "UPDATE memories SET version_chain_id = ? WHERE storage_key = ? AND version_chain_id IS NULL",
                    (storage_key, storage_key),
                )
            except sqlite3.Error:
                pass

        stored = StoredMemory.from_memory_entry(entry, storage_key=storage_key, created_at=now)
        stored.importance_score = imp_score
        stored.version = 1
        return stored

    def remember_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
        with self._lock:
            conn = self._get_connection()
            results = []
            try:
                conn.execute("BEGIN")
                for entry in entries:
                    result = self._remember_impl(entry, _skip_commit=True)
                    results.append(result)
                conn.commit()
            except Exception as e:
                conn.rollback()
                from carrymem.utils.logger import logger
                logger.warning(f"Batch remember failed, rolled back: {e}")
                raise
        if self._enable_cache and self._cache:
            self._cache.invalidate()
        return results

    _SUPERSEDE_TYPES = {"user_preference", "decision", "fact_declaration", "correction"}
    _CONTRADICTION_PAIRS = [
        ("like", "dislike"), ("prefer", "avoid"), ("love", "hate"),
        ("use", "stop using"), ("switched", "no longer"), ("moved", "left"),
        ("changed", "previous"), ("updated", "old"), ("now", "previously"),
        ("currently", "formerly"), ("new", "old"), ("current", "previous"),
        ("dark", "light"), ("yes", "no"), ("true", "false"),
        ("enabled", "disabled"), ("always", "never"),
    ]
    _UPDATE_MARKERS = [
        "now", "currently", "switched", "changed", "moved", "updated",
        "no longer", "instead", "replaced", "new", "currently prefer",
        "now prefer", "now use", "now live", "now work",
    ]

    def _auto_supersede(self, conn, new_storage_key: str, entry: MemoryEntry, namespace: str):
        if entry.type not in self._SUPERSEDE_TYPES:
            return
        if entry.type == "correction":
            return

        try:
            rows = conn.execute(
                "SELECT id, content, raw_text, type, created_at, superseded_at, storage_key "
                "FROM memories WHERE type = ? AND namespace = ? AND superseded_at IS NULL "
                "AND storage_key != ? "
                "ORDER BY created_at DESC LIMIT 20",
                (entry.type, namespace, new_storage_key),
            ).fetchall()
        except sqlite3.OperationalError:
            return

        if not rows:
            return

        entry_words = set(entry.content.lower().split())
        entry_lower = entry.content.lower()
        has_update_marker = any(f" {m} " in f" {entry_lower} " or entry_lower.startswith(f"{m} ") for m in self._UPDATE_MARKERS)

        _PREFERENCE_KEYWORDS = {
            "prefer", "偏好", "喜欢", "选用", "recommend", "avoid",
            "不用", "别用", "不要用", "dislike", "hate", "never",
            "always", "switched", "changed", "replaced", "instead",
        }
        entry_has_pref_kw = any(kw in entry_lower for kw in _PREFERENCE_KEYWORDS)

        for row in rows:
            old_content = row["content"] or ""
            if old_content.startswith("Correction:") or old_content.startswith("Decision:"):
                continue
            if old_content.lower().startswith(("[assistant said]", "[ai said]", "[bot said]")):
                continue

            old_words = set(old_content.lower().split())
            if not old_words:
                continue
            jaccard = len(entry_words & old_words) / max(len(entry_words | old_words), 1)

            should_supersede = False
            if self._is_contradictory(entry.content, old_content):
                should_supersede = True
            elif has_update_marker and jaccard >= 0.40:
                should_supersede = True
            elif (
                entry.type == "user_preference"
                and entry_has_pref_kw
            ):
                old_lower = old_content.lower()
                old_has_pref_kw = any(kw in old_lower for kw in _PREFERENCE_KEYWORDS)
                if old_has_pref_kw:
                    should_supersede = True

            if not should_supersede:
                if jaccard < 0.25:
                    continue
                continue

            if entry.content.startswith("Correction:") or entry.content.startswith("Decision:"):
                continue
            if entry.content.lower().startswith(("[assistant said]", "[ai said]", "[bot said]")):
                continue

            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                # Get old memory's version chain info
                old_chain_id = None
                old_version = 1
                try:
                    chain_row = conn.execute(
                        "SELECT version_chain_id, version_number FROM memories WHERE id = ?",
                        (row["id"],),
                    ).fetchone()
                    if chain_row:
                        old_chain_id = chain_row["version_chain_id"]
                        old_version = chain_row["version_number"] or 1
                except sqlite3.OperationalError:
                    pass

                # Determine chain_id: reuse old if exists, otherwise use new storage_key
                chain_id = old_chain_id or new_storage_key
                new_version = old_version + 1

                # Mark old memory as superseded and link to chain
                conn.execute(
                    "UPDATE memories SET superseded_at = ?, supersedes = ?, "
                    "version_chain_id = ? WHERE id = ?",
                    (now_iso, new_storage_key, chain_id, row["id"]),
                )

                # Update new memory's version chain info
                conn.execute(
                    "UPDATE memories SET version_chain_id = ?, version_number = ? "
                    "WHERE storage_key = ?",
                    (chain_id, new_version, new_storage_key),
                )
            except sqlite3.Error:
                pass
            from carrymem.utils.logger import logger
            logger.debug(
                f"Auto-superseded memory {row['id'][:16]} with new {entry.type} "
                f"(jaccard={jaccard:.2f}, update_marker={has_update_marker})"
            )
            break

    def _is_contradictory(self, new_content: str, old_content: str) -> bool:
        import re
        new_lower = new_content.lower()
        old_lower = old_content.lower()
        for pos_word, neg_word in self._CONTRADICTION_PAIRS:
            pos_pat = rf'\b{re.escape(pos_word)}\b'
            neg_pat = rf'\b{re.escape(neg_word)}\b'
            if (re.search(pos_pat, new_lower) and re.search(neg_pat, old_lower)) or \
               (re.search(neg_pat, new_lower) and re.search(pos_pat, old_lower)):
                return True
        return False

    _ALLOWED_FILTER_KEYS = {
        "type", "tier", "confidence_min", "created_after",
        "created_before", "session_id", "include_superseded",
        "_order_oldest", "include_session_summary",
    }

    _TIME_EXPRESSIONS = [
        (r'\b(recently|lately|just)\b', 7, False),
        (r'\b(this\s+week|past\s+week|last\s+week)\b', 7, False),
        (r'\b(this\s+month|past\s+month|last\s+month)\b', 30, False),
        (r'\b(recent|latest|newest|current)\b', 14, False),
        (r'\b(today|yesterday)\b', 2, False),
        (r'\b(first|initial|earliest|original)\b', None, True),
        (r'\b(before|prior\s+to|earlier)\b', None, False),
        (r'\b(after|since|following)\b', None, False),
        (r'\b(last\s+year|previous\s+year)\b', 365, False),
        (r'\b(\d+)\s+(days?|weeks?|months?)\s+ago\b', None, False),
    ]

    def _parse_time_expressions(self, query: str) -> Dict[str, Any]:
        import re
        from datetime import timedelta

        if not query:
            return {}

        result = {}
        query_lower = query.lower()

        for pattern, days, is_oldest in self._TIME_EXPRESSIONS:
            m = re.search(pattern, query_lower)
            if not m:
                continue

            if is_oldest:
                result["order_oldest"] = True
                continue

            if days is not None:
                result["created_after"] = (
                    datetime.now(timezone.utc) - timedelta(days=days)
                ).isoformat()
                continue

            ago_match = re.search(r'(\d+)\s+(days?|weeks?|months?)\s+ago', query_lower)
            if ago_match:
                n = int(ago_match.group(1))
                unit = ago_match.group(2)
                if 'day' in unit:
                    delta = timedelta(days=n)
                elif 'week' in unit:
                    delta = timedelta(weeks=n)
                elif 'month' in unit:
                    delta = timedelta(days=n * 30)
                else:
                    delta = timedelta(days=n)
                result["created_after"] = (
                    datetime.now(timezone.utc) - delta
                ).isoformat()
                continue

        return result

    def _rebuild_context(self, original_query: str, keywords: str) -> str:
        if not keywords:
            return original_query

        try:
            conn = self._get_connection()
            profile_rows = conn.execute(
                "SELECT content, type FROM memories "
                "WHERE namespace = ? AND type IN ('user_preference', 'decision', 'fact_declaration') "
                "AND (superseded_at IS NULL OR superseded_at = '') "
                "ORDER BY importance_score DESC LIMIT 5",
                (self._namespace,),
            ).fetchall()
        except sqlite3.Error:
            return original_query

        if not profile_rows:
            return original_query

        query_words = set(keywords.lower().split())
        context_words = set()
        for row in profile_rows:
            content = (row["content"] or "").lower()
            content_words = set(content.split())
            overlap = query_words & content_words
            if overlap:
                context_words.update(content_words - query_words)

        if not context_words:
            return original_query

        extra = " ".join(w for w in list(context_words)[:5] if len(w) > 2)
        if extra:
            return f"{keywords} {extra}"
        return original_query

    _VALID_MEMORY_TYPES = {
        "user_preference", "correction", "fact_declaration",
        "decision", "relationship", "task_pattern", "sentiment_marker",
        "session_summary",
    }

    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[StoredMemory]:
        if self._enable_cache and self._cache:
            cached = self._cache.get(self._namespace, query, filters, limit)
            if cached is not None:
                return [self._dict_to_stored(d) or StoredMemory() for d in cached]

        with self._lock:
            results = self._recall_impl(query, filters, limit, namespaces, update_access=update_access)

        if self._enable_cache and self._cache and results:
            self._cache.put(
                self._namespace, query, filters, limit,
                [r.to_dict() for r in results],
            )

        return results

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemory]]:
        with self._lock:
            return self._recall_aggregated_impl(memory_type, namespaces, limit_per_type)

    def _recall_aggregated_impl(
        self,
        memory_type: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemory]]:
        ns = namespaces or [self._namespace]
        placeholders = ",".join(["?"] * len(ns))
        params = list(ns)

        conditions = [f"namespace IN ({placeholders})"]
        conditions.append("(superseded_at IS NULL OR superseded_at = '')")

        if memory_type:
            conditions.append("type = ?")
            params.append(memory_type)

        where_clause = "WHERE " + " AND ".join(conditions)

        conn = self._get_connection()
        if memory_type:
            sql = f"SELECT * FROM memories {where_clause} ORDER BY importance_score DESC, created_at DESC LIMIT ?"
            params.append(limit_per_type)
            rows = conn.execute(sql, params).fetchall()
            return {memory_type: [self._row_to_stored(r) for r in rows if self._row_to_stored(r)]}

        result = {}
        for mtype in self._VALID_MEMORY_TYPES:
            type_conditions = conditions + ["type = ?"]
            type_where = "WHERE " + " AND ".join(type_conditions)
            sql = f"SELECT * FROM memories {type_where} ORDER BY importance_score DESC, created_at DESC LIMIT ?"
            type_params = list(ns) + [mtype, limit_per_type]
            rows = conn.execute(sql, type_params).fetchall()
            typed = [self._row_to_stored(r) for r in rows if self._row_to_stored(r)]
            if typed:
                result[mtype] = typed
        return result

    def recall_timeline(
        self,
        topic: str,
        namespaces: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[StoredMemory]:
        with self._lock:
            return self._recall_timeline_impl(topic, namespaces, limit)

    def _recall_timeline_impl(
        self,
        topic: str,
        namespaces: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[StoredMemory]:
        ns = namespaces or [self._namespace]
        placeholders = ",".join(["?"] * len(ns))
        params = list(ns)

        conditions = [f"namespace IN ({placeholders})"]

        words = [w for w in topic.lower().split() if len(w) > 1]
        if words:
            like_parts = []
            for w in words:
                like_parts.append("(content LIKE ? OR raw_text LIKE ?)")
                params.extend([f"%{w}%", f"%{w}%"])
            conditions.append(f"({' OR '.join(like_parts)})")

        where_clause = "WHERE " + " AND ".join(conditions)

        conn = self._get_connection()
        sql = f"SELECT * FROM memories {where_clause} ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_stored(r) for r in rows if self._row_to_stored(r)]

    def _recall_impl(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ):
        filters = filters or {}

        for key in filters:
            if key not in self._ALLOWED_FILTER_KEYS:
                raise ValueError(
                    f"Invalid filter key: '{key}'. "
                    f"Allowed keys: {self._ALLOWED_FILTER_KEYS}"
                )

        if filters.get("type") and filters["type"] not in self._VALID_MEMORY_TYPES:
            raise ValueError(
                f"Invalid memory type: '{filters['type']}'. "
                f"Valid types: {self._VALID_MEMORY_TYPES}"
            )

        if limit < 0 or limit > 100000:
            raise ValueError(f"Limit must be between 0 and 100000, got {limit}")

        if namespaces:
            for ns in namespaces:
                if not ns or not isinstance(ns, str) or len(ns) > 128:
                    raise ValueError(
                        f"Invalid namespace: '{ns}'. "
                        "Must be non-empty string, max 128 chars."
                    )

        if query and len(query) > 10000:
            raise ValueError(f"Query too long: {len(query)} chars (max 10000)")

        time_constraints = self._parse_time_expressions(query or "")
        if time_constraints:
            if time_constraints.get("created_after") and not filters.get("created_after"):
                filters["created_after"] = time_constraints["created_after"]
            if time_constraints.get("created_before") and not filters.get("created_before"):
                filters["created_before"] = time_constraints["created_before"]
            if time_constraints.get("order_oldest"):
                filters["_order_oldest"] = True

        ns = namespaces or [self._namespace]
        placeholders = ",".join(["?"] * len(ns))
        conditions = [f"namespace IN ({placeholders})"]
        params = list(ns)

        if filters.get("type"):
            conditions.append("type = ?")
            params.append(filters["type"])
        elif not filters.get("include_session_summary", False):
            conditions.append("type != ?")
            params.append("session_summary")

        if filters.get("tier") is not None:
            conditions.append("tier = ?")
            params.append(filters["tier"])

        if filters.get("confidence_min") is not None:
            conditions.append("confidence >= ?")
            params.append(filters["confidence_min"])

        if filters.get("created_after"):
            conditions.append("created_at >= ?")
            params.append(filters["created_after"])

        if filters.get("created_before"):
            conditions.append("created_at <= ?")
            params.append(filters["created_before"])

        if not filters.get("include_superseded", False):
            conditions.append("(superseded_at IS NULL OR superseded_at = '')")

        if filters.get("session_id"):
            safe_sid = filters["session_id"].replace("%", "\\%").replace("_", "\\_")
            conditions.append("metadata LIKE ? ESCAPE '\\'")
            params.append(f'%session_id": "{safe_sid}%')

        where_clause = "WHERE " + " AND ".join(conditions)

        if query and query.strip():
            stop_words = {"what", "is", "the", "did", "does", "do", "a", "an", "how",
                           "who", "which", "when", "where", "why", "can", "could", "would",
                           "should", "team", "user", "use", "used", "using", "for", "of",
                           "in", "on", "to", "and", "or", "that", "this", "it", "be", "are",
                           "was", "were", "been", "has", "have", "had", "will", "would"}
            keywords = " ".join(
                w for w in query.lower().split()
                if w not in stop_words and len(w) > 1
            )

            if keywords and keywords != query.strip().lower():
                rows = self._fts_search(keywords, where_clause, params, limit)
            else:
                rows = self._fts_search(query, where_clause, params, limit)

            if not rows and self._has_cjk(query):
                rows = self._like_search(query, where_clause, params, limit)

            if not rows or len(rows) < max(3, limit // 4):
                rebuilt_query = self._rebuild_context(query, keywords)
                if rebuilt_query and rebuilt_query != query and rebuilt_query != keywords:
                    extra_rows = self._fts_search(rebuilt_query, where_clause, params, limit)
                    if extra_rows:
                        seen_ids = {r[0] for r in rows if r}
                        for r in extra_rows:
                            if r and r[0] not in seen_ids:
                                rows.append(r)
                                seen_ids.add(r[0])

            if self._enable_vector:
                vec_rows = self._vector_search(query, where_clause, params, limit)
                if vec_rows:
                    rows = self._rrf_fuse(rows, vec_rows, limit)

            expanded_queries = self._expand_query(query)
            if expanded_queries:
                seen_ids = set()
                for r in rows:
                    rid = r[0] if r else None
                    if rid:
                        seen_ids.add(rid)

                for eq in expanded_queries:
                    eq_rows = self._fts_search(eq, where_clause, params, limit)
                    for r in eq_rows:
                        rid = r[0] if r else None
                        if rid and rid not in seen_ids:
                            rows.append(r)
                            seen_ids.add(rid)
                    if len(rows) >= limit:
                        break

                if len(rows) < limit:
                    for eq in expanded_queries:
                        eq_rows = self._like_search(eq, where_clause, params, limit)
                        for r in eq_rows:
                            rid = r[0] if r else None
                            if rid and rid not in seen_ids:
                                rows.append(r)
                                seen_ids.add(rid)
                        if len(rows) >= limit:
                            break

            # Phase 2: Semantic expansion if results insufficient
            if self._enable_semantic and len(rows) < limit and self._expander and self._merger:
                original_results = [self._row_to_stored(r) for r in rows if r]
                expanded_rows = self._semantic_recall(query, where_clause, params, limit)
                expanded_results = [self._row_to_stored(r) for r in expanded_rows if r]

                # Only use semantic results if we got new matches
                if expanded_results:
                    merged = self._merger.merge(
                        original_results=original_results,
                        expanded_results=expanded_results,
                        query=query,
                        limit=limit,
                        source="synonym",
                    )
                    # Convert merged dicts back to StoredMemory objects
                    final_results = []
                    for item in merged:
                        if isinstance(item, StoredMemory):
                            final_results.append(item)
                        elif isinstance(item, dict):
                            stored = self._dict_to_stored(item)
                            if stored:
                                final_results.append(stored)

                    # Update access counts and return
                    conn = self._get_connection()
                    now_iso = datetime.now(timezone.utc).isoformat()
                    seen_keys = set()
                    results = []
                    batch_updates = []
                    for stored in final_results:
                        if stored.storage_key not in seen_keys:
                            seen_keys.add(stored.storage_key)
                            if update_access:
                                new_count = stored.access_count + 1
                                new_score = calculate_importance(
                                    confidence=stored.confidence,
                                    memory_type=stored.type,
                                    created_at=stored.created_at or datetime.now(timezone.utc),
                                    access_count=new_count,
                                )
                                batch_updates.append((new_count, new_score, now_iso, stored.storage_key))
                                stored.access_count = new_count
                                stored.importance_score = new_score
                                stored.last_accessed_at = datetime.now(timezone.utc)
                            results.append(stored)
                    if update_access and batch_updates:
                        conn.executemany(
                            "UPDATE memories SET access_count = ?, importance_score = ?, last_accessed_at = ? WHERE storage_key = ?",
                            batch_updates,
                        )
                    conn.commit()
                    return results
        else:
            conn = self._get_connection()
            sql = f"""
                SELECT * FROM memories
                {where_clause}
                ORDER BY importance_score DESC, confidence DESC
                LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()

        conn = self._get_connection()
        now_iso = datetime.now(timezone.utc).isoformat()
        results = []
        seen_keys = set()
        batch_updates = []

        # P1-2: Diversity filtering - limit same-type dominance
        type_counts = {}
        max_per_type = max(3, limit // 3)

        for row in rows:
            stored = self._row_to_stored(row)
            if stored and stored.storage_key not in seen_keys:
                mtype = stored.type or "unknown"
                type_counts[mtype] = type_counts.get(mtype, 0) + 1

                if type_counts[mtype] > max_per_type and mtype == "sentiment_marker":
                    continue

                seen_keys.add(stored.storage_key)
                if update_access:
                    new_count = stored.access_count + 1
                    new_score = calculate_importance(
                        confidence=stored.confidence,
                        memory_type=stored.type,
                        created_at=stored.created_at or datetime.now(timezone.utc),
                        access_count=new_count,
                    )
                    batch_updates.append((new_count, new_score, now_iso, stored.storage_key))
                    stored.access_count = new_count
                    stored.importance_score = new_score
                    stored.last_accessed_at = datetime.now(timezone.utc)
                results.append(stored)
        if update_access and batch_updates:
            conn.executemany(
                "UPDATE memories SET access_count = access_count + 1, importance_score = ?, last_accessed_at = ? WHERE storage_key = ?",
                [(score, ts, key) for (_, score, ts, key) in batch_updates],
            )
        conn.commit()

        if filters.get("_order_oldest") and results:
            results.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))

        return results

    def _semantic_recall(self, query: str, where_clause: str, params: List, limit: int):
        """Perform semantic expansion search.

        Expands query using synonym graph, spell correction, cross-language mapping,
        then re-searches FTS5 with expanded terms. Uses batched queries to avoid N+1.
        """
        if not self._expander:
            return []

        try:
            expansions = self._expander.expand(query)

            all_expanded_rows = []
            seen_row_ids = set()

            valid_expansions = [e for e in expansions[1:] if e and e.strip()]

            if not valid_expansions:
                return []

            conn = self._get_connection()
            try:
                combined_query = " OR ".join(f'"{e}"' for e in valid_expansions)
                all_expanded_rows = self._fts_search(combined_query, where_clause, params, limit)
                seen_row_ids = set()
                deduped = []
                for row in all_expanded_rows:
                    row_id = row["id"] if hasattr(row, "__getitem__") else None
                    if row_id and row_id not in seen_row_ids:
                        seen_row_ids.add(row_id)
                        deduped.append(row)
                        if len(deduped) >= limit:
                            break
                all_expanded_rows = deduped

                if len(all_expanded_rows) < limit:
                    for exp_query in valid_expansions:
                        if self._has_cjk(exp_query):
                            like_rows = self._like_search(exp_query, where_clause, params, limit)
                            for row in like_rows:
                                row_id = row["id"] if hasattr(row, "__getitem__") else None
                                if row_id and row_id not in seen_row_ids:
                                    seen_row_ids.add(row_id)
                                    all_expanded_rows.append(row)
                                    if len(all_expanded_rows) >= limit:
                                        break
            finally:
                pass

            return all_expanded_rows[:limit]

        except Exception as e:
            from carrymem.utils.logger import logger
            logger.warning(f"Semantic recall search failed: {e}")
            return []

    def _vector_search(self, query: str, where_clause: str, params: List, limit: int):
        if not self._embedding_model:
            return []
        try:
            query_embedding = self._embedding_model.encode(query)
            conn = self._get_connection()
            vec_sql = """
                SELECT m.*, v.distance
                FROM memories m
                JOIN memory_vectors v ON v.memory_id = m.id
                {where_clause}
                AND v.embedding MATCH ?
                AND k = ?
                ORDER BY v.distance
            """.format(where_clause=where_clause)
            vec_params = params + [
                struct.pack(f'{self._embedding_dim}f', *query_embedding.tolist()),
                limit,
            ]
            return conn.execute(vec_sql, vec_params).fetchall()
        except Exception as e:
            from carrymem.utils.logger import logger
            logger.warning(f"Vector search failed: {e}")
            return []

    def _rrf_fuse(self, fts_rows: list, vec_rows: list, limit: int) -> list:
        """P1-1: Reciprocal Rank Fusion of FTS5 and vector search results.

        RRF formula: score(d) = w_fts * 1/(k + rank_fts) + w_vec * 1/(k + rank_vec)
        Where k, weights, and type boosts are configurable via rrf_config or env vars.

        Args:
            fts_rows: FTS5 search results (already ranked by importance_score).
            vec_rows: Vector search results (ranked by distance).
            limit: Maximum number of results to return.

        Returns:
            Fused and re-ranked list of rows.
        """
        rrf_scores = {}
        row_data = {}

        for rank, row in enumerate(fts_rows, start=1):
            rid = row["id"] if row and "id" in row.keys() else None
            if not rid:
                continue
            base_score = self._rrf_fts_weight / (self._rrf_k + rank)
            type_boost = self._type_boost(row)
            rrf_scores[rid] = rrf_scores.get(rid, 0.0) + base_score * type_boost
            row_data[rid] = row

        for rank, row in enumerate(vec_rows, start=1):
            rid = row["id"] if row and "id" in row.keys() else None
            if not rid:
                continue
            base_score = self._rrf_vec_weight / (self._rrf_k + rank)
            type_boost = self._type_boost(row)
            rrf_scores[rid] = rrf_scores.get(rid, 0.0) + base_score * type_boost
            if rid not in row_data:
                row_data[rid] = row

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        return [row_data[rid] for rid in sorted_ids[:limit]]

    def _type_boost(self, row) -> float:
        """P1-1: Apply type-based score boost/penalty.

        Configurable via rrf_config.type_boosts or CARRYMEM_RRF_TYPE_BOOSTS env var.
        Default: fact/decision +20%, sentiment -50%.
        """
        mtype = row["type"] if row and "type" in row.keys() else ""
        return self._rrf_type_boosts.get(mtype, 1.0)

    def _has_cjk(self, text: str) -> bool:
        return any(
            "\u4e00" <= char <= "\u9fff"
            or "\u3040" <= char <= "\u309f"
            or "\u30a0" <= char <= "\u30ff"
            for char in text
        )

    @staticmethod
    def _expand_query(query: str) -> List[str]:
        """Expand a short query with related terms for better recall.

        Args:
            query: The original search query.

        Returns:
            List of expanded query strings.
        """
        expansions = {
            "theme": ["dark mode", "light mode", "theme preference"],
            "database": ["postgresql", "mysql", "database selection", "database choice", "decided to use", "sqlite"],
            "db": ["database", "sqlite", "postgresql", "mysql"],
            "api": ["api rate", "api design", "graphql", "rest", "rate limit"],
            "typescript": ["typescript strict", "typescript configuration"],
            "cloud": ["aws", "gcp", "cloud hosting", "cloud provider", "chose aws"],
            "deployment": ["deploy", "friday", "deployment rules", "never deploy"],
            "server": ["server address", "server port", "staging server", "ip", "staging"],
            "cache": ["redis", "cache ttl", "cache settings"],
            "workflow": ["trunk-based", "development workflow", "git workflow", "trunk"],
            "design": ["composition", "inheritance", "design pattern", "class design"],
            "editor": ["vscode", "intellij", "ide", "vim"],
            "language": ["python", "programming language"],
            "indentation": ["spaces", "tabs", "indentation style"],
            "version": ["git", "version control", "github"],
            "security": ["oauth", "jwt", "authentication", "tls"],
            "framework": ["react", "vue", "angular", "django", "flask", "frontend", "backend"],
            "preference": ["prefer", "like", "always use", "never"],
            "ip": ["staging server", "server address", "10.0"],
            "port": ["server port", "9090", "8080"],
            "数据库": ["postgresql", "mysql", "database"],
            "偏好": ["prefer", "like", "preference"],
            "深色": ["dark mode", "dark theme"],
            "主题": ["theme", "theme preference"],
            "ダークモード": ["dark mode", "dark theme"],
            "データベース": ["database", "postgresql", "mysql"],
        }

        stop_words = {"what", "is", "the", "did", "does", "do", "a", "an", "how",
                       "who", "which", "when", "where", "why", "can", "could", "would",
                       "should", "team", "user", "use", "used", "using", "for", "of",
                       "in", "on", "to", "and", "or", "that", "this", "it", "be", "are",
                       "was", "were", "been", "has", "have", "had", "will", "would"}

        query_lower = query.lower().strip()
        words = [w for w in query_lower.split() if w not in stop_words and len(w) > 1]
        expanded = []

        for word in words:
            for key, terms in expansions.items():
                if key == word or key in word or word in key:
                    expanded.extend(terms)

        if not expanded:
            for word in words:
                if len(word) > 2:
                    expanded.append(word)

        return expanded

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Sanitize a query string for FTS5 MATCH.

        FTS5 treats ", *, OR, AND, NOT, NEAR as special operators.
        For ASCII tokens, wrap in quotes to treat as literal phrases.
        For CJK tokens, leave unquoted (trigram tokenizer needs free matching).
        """
        tokens = query.strip().split()
        sanitized = []
        for token in tokens:
            clean = token.replace('"', '').strip()
            if not clean:
                continue
            has_cjk = any(
                "\u4e00" <= c <= "\u9fff"
                or "\u3040" <= c <= "\u309f"
                or "\u30a0" <= c <= "\u30ff"
                for c in clean
            )
            if has_cjk:
                sanitized.append(clean)
            else:
                sanitized.append(f'"{clean}"')
        return " ".join(sanitized)

    def _fts_search(self, query, where_clause, params, limit):
        try:
            conn = self._get_connection()
            safe_query = self._sanitize_fts_query(query)
            if not safe_query:
                return []
            fts_sql = f"""
                SELECT m.* FROM memories m
                JOIN memories_fts f ON m.rowid = f.rowid
                {where_clause}
                AND m.rowid IN (
                    SELECT rowid FROM memories_fts WHERE memories_fts MATCH ?
                )
                ORDER BY m.importance_score DESC, m.confidence DESC
                LIMIT ?
            """
            params_with_query = params + [safe_query, limit]
            return conn.execute(fts_sql, params_with_query).fetchall()
        except sqlite3.OperationalError:
            return []

    def _like_search(self, query, where_clause, params, limit):
        conn = self._get_connection()
        escaped = escape_like(query)
        like_clause = " AND (content LIKE ? ESCAPE '\\' OR raw_text LIKE ? ESCAPE '\\' OR original_message LIKE ? ESCAPE '\\')"
        like_params = [f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"]
        sql = f"""
            SELECT * FROM memories
            {where_clause}
            {like_clause}
            ORDER BY importance_score DESC, confidence DESC
            LIMIT ?
        """
        all_params = params + like_params + [limit]
        return conn.execute(sql, all_params).fetchall()

    def forget(self, storage_key: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            memory_id = None
            row = conn.execute(
                "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._namespace),
            ).fetchone()
            if row:
                memory_id = row["id"]
            cursor = conn.execute(
                "DELETE FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._namespace),
            )
            if memory_id and self._enable_vector:
                try:
                    conn.execute(
                        "DELETE FROM memory_vectors WHERE memory_id = ?",
                        (memory_id,),
                    )
                except Exception as e:
                    from carrymem.utils.logger import logger
                    logger.warning(f"Failed to delete vector for memory {memory_id}: {e}")
            conn.commit()
            result = cursor.rowcount > 0
        if self._enable_cache and self._cache:
            self._cache.invalidate()
        if self._audit:
            self._audit.log_operation(
                operation="forget",
                storage_key=storage_key,
                success=result,
            )
        return result

    def forget_expired(self) -> int:
        with self._lock:
            conn = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                "DELETE FROM memories WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at < ?",
                (self._namespace, now),
            )
            conn.commit()
            count = cursor.rowcount
        if self._enable_cache and self._cache and count > 0:
            self._cache.invalidate()
        return count

    def recalculate_importance(self) -> int:
        with self._lock:
            self._recalculate_all_importance()
            conn = self._get_connection()
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE namespace = ?",
                (self._namespace,),
            ).fetchone()[0]
            return total

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Optional[StoredMemory]:
        with self._lock:
            return self._update_memory_impl(storage_key, new_content, reason)

    def _update_memory_impl(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Optional[StoredMemory]:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._namespace),
        ).fetchone()
        if not row:
            return None

        stored = self._row_to_stored(row)
        if not stored:
            return None

        old_version = stored.version
        new_version = old_version + 1

        version_id = f"v_{storage_key}_{new_version}"
        now = datetime.now(timezone.utc)
        conn.execute(
            """INSERT INTO memory_versions (version_id, memory_id, version, content, confidence, changed_at, change_reason, namespace)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (version_id, stored.id, old_version, stored.content, stored.confidence,
             now.isoformat(), reason or f"Update to version {new_version}", self._namespace),
        )

        new_c_hash = content_hash(new_content, stored.type)
        new_imp_score = calculate_importance(
            confidence=stored.confidence,
            memory_type=stored.type,
            created_at=stored.created_at or now,
            access_count=stored.access_count,
            now=now,
        )

        encrypted_content = self._encrypt_field(new_content)

        conn.execute(
            """UPDATE memories SET content = ?, content_hash = ?, version = ?,
               importance_score = ?, updated_at = ? WHERE storage_key = ? AND namespace = ?""",
            (encrypted_content, new_c_hash, new_version, new_imp_score, now.isoformat(),
             storage_key, self._namespace),
        )
        conn.commit()

        updated_row = conn.execute(
            "SELECT * FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._namespace),
        ).fetchone()
        return self._row_to_stored(updated_row)

    def get_memory_history(
        self,
        storage_key: str,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._namespace),
        ).fetchone()
        if not row:
            return []

        memory_id = row["id"]
        versions = conn.execute(
            "SELECT * FROM memory_versions WHERE memory_id = ? ORDER BY version DESC",
            (memory_id,),
        ).fetchall()

        current_row = conn.execute(
            "SELECT * FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._namespace),
        ).fetchone()
        current = self._row_to_stored(current_row)

        history = []
        if current:
            history.append({
                "version": current.version,
                "content": current.content,
                "confidence": current.confidence,
                "changed_at": current.updated_at.isoformat() if current.updated_at else None,
                "change_reason": "Current version",
                "is_current": True,
            })

        for v in versions:
            history.append({
                "version": v["version"],
                "content": v["content"],
                "confidence": v["confidence"],
                "changed_at": v["changed_at"],
                "change_reason": v["change_reason"],
                "is_current": False,
            })

        return history

    def rollback_memory(
        self,
        storage_key: str,
        version: int,
    ) -> Optional[StoredMemory]:
        with self._lock:
            conn = self._get_connection()
            row = conn.execute(
                "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._namespace),
            ).fetchone()
            if not row:
                return None

            memory_id = row["id"]
            version_row = conn.execute(
                "SELECT * FROM memory_versions WHERE memory_id = ? AND version = ?",
                (memory_id, version),
            ).fetchone()
            if not version_row:
                return None

            old_content = version_row["content"]
            if self._encryption and self._encryption.is_active:
                old_content = self._decrypt_field(old_content)
            old_original = version_row["original_message"] if "original_message" in version_row.keys() else None
            if old_original and self._encryption and self._encryption.is_active:
                old_original = self._decrypt_field(old_original)
            return self._update_memory_impl(
                storage_key=storage_key,
                new_content=old_content,
                reason=f"Rollback to version {version}",
            )

    def get_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE namespace = ?",
            (self._namespace,),
        ).fetchone()[0]
        by_type_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM memories WHERE namespace = ? GROUP BY type",
            (self._namespace,),
        ).fetchall()
        by_type = {row["type"]: row["cnt"] for row in by_type_rows}

        return {
            "adapter": self.name,
            "namespace": self._namespace,
            "total_count": total,
            "by_type": by_type,
            "capabilities": self.capabilities,
            "db_path": self._db_path,
        }

    def get_profile(self) -> Dict[str, Any]:
        conn = self._get_connection()
        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE namespace = ?",
            (self._namespace,),
        ).fetchone()[0]

        if total == 0:
            return {
                "summary": "No memories yet",
                "total_memories": 0,
                "highlights": {},
                "stats": {"by_type": {}, "by_tier": {}, "confidence_avg": 0.0},
                "namespace": self._namespace,
                "last_updated": None,
            }

        by_type_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM memories WHERE namespace = ? GROUP BY type",
            (self._namespace,),
        ).fetchall()
        by_type = {row["type"]: row["cnt"] for row in by_type_rows}

        by_tier_rows = conn.execute(
            "SELECT tier, COUNT(*) as cnt FROM memories WHERE namespace = ? GROUP BY tier",
            (self._namespace,),
        ).fetchall()
        by_tier = {str(row["tier"]): row["cnt"] for row in by_tier_rows}

        avg_conf = conn.execute(
            "SELECT AVG(confidence) FROM memories WHERE namespace = ?",
            (self._namespace,),
        ).fetchone()[0] or 0.0

        highlight_types = [
            "user_preference",
            "correction",
            "decision",
            "fact_declaration",
        ]
        highlights: Dict[str, List[str]] = {}
        for mem_type in highlight_types:
            rows = conn.execute(
                "SELECT content FROM memories WHERE namespace = ? AND type = ? ORDER BY confidence DESC LIMIT 5",
                (self._namespace, mem_type),
            ).fetchall()
            items = [row["content"][:100] for row in rows]
            if items:
                highlights[mem_type] = items

        last_updated_row = conn.execute(
            "SELECT MAX(updated_at) FROM memories WHERE namespace = ?",
            (self._namespace,),
        ).fetchone()
        last_updated = last_updated_row[0] if last_updated_row else None

        type_parts = []
        type_labels = {
            "user_preference": "preferences",
            "correction": "corrections",
            "decision": "decisions",
            "fact_declaration": "facts",
            "relationship": "relationships",
            "task_pattern": "task patterns",
            "sentiment_marker": "sentiments",
        }
        for t, cnt in by_type.items():
            label = type_labels.get(t, t)
            type_parts.append(f"{cnt} {label}")

        summary = f"AI remembers {total} things about you: " + ", ".join(type_parts)

        return {
            "summary": summary,
            "total_memories": total,
            "highlights": highlights,
            "stats": {
                "by_type": by_type,
                "by_tier": by_tier,
                "confidence_avg": round(avg_conf, 4),
            },
            "namespace": self._namespace,
            "last_updated": last_updated,
        }

    def _encrypt_field(self, plaintext: str) -> str:
        if not self._encryption or not plaintext:
            return plaintext
        return self._encryption.encrypt(plaintext)

    def _decrypt_field(self, ciphertext: str) -> str:
        if not self._encryption or not ciphertext:
            return ciphertext
        try:
            return self._encryption.decrypt(ciphertext)
        except Exception:
            return ciphertext

    def _row_to_stored(self, row: Optional[sqlite3.Row]) -> Optional[StoredMemory]:
        if not row:
            return None

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        recall_hint = None
        if row["recall_hint"]:
            try:
                recall_hint = json.loads(row["recall_hint"])
            except (json.JSONDecodeError, TypeError):
                recall_hint = None

        expires_at = None
        if row["expires_at"]:
            try:
                expires_at = datetime.fromisoformat(row["expires_at"])
            except (ValueError, TypeError):
                expires_at = None

        created_at = None
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                created_at = None

        updated_at = None
        if row["updated_at"]:
            try:
                updated_at = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                updated_at = None

        last_accessed_at = None
        last_accessed_val = None
        try:
            last_accessed_val = row["last_accessed_at"]
        except (IndexError, KeyError):
            pass
        if last_accessed_val:
            try:
                last_accessed_at = datetime.fromisoformat(last_accessed_val)
            except (ValueError, TypeError):
                last_accessed_at = None

        importance_score = 0.0
        try:
            importance_score = row["importance_score"] or 0.0
        except (IndexError, KeyError):
            pass

        version = 1
        try:
            version = row["version"] or 1
        except (IndexError, KeyError):
            pass

        superseded_at = None
        try:
            sa_val = row["superseded_at"]
            if sa_val:
                superseded_at = datetime.fromisoformat(sa_val)
        except (IndexError, KeyError, ValueError, TypeError):
            pass

        supersedes = None
        try:
            supersedes = row["supersedes"]
        except (IndexError, KeyError):
            pass

        return StoredMemory(
            id=row["id"],
            type=row["type"],
            content=self._decrypt_field(row["content"]),
            raw_text=self._decrypt_field(row["raw_text"]) if "raw_text" in row.keys() else "",
            confidence=row["confidence"],
            tier=row["tier"],
            source_layer=row["source_layer"] or "unknown",
            reasoning=row["reasoning"] or "",
            suggested_action=row["suggested_action"] or "store",
            recall_hint=recall_hint,
            metadata=metadata,
            storage_key=row["storage_key"],
            namespace=row["namespace"] if "namespace" in row.keys() else self._namespace,
            created_at=created_at,
            updated_at=updated_at,
            expires_at=expires_at,
            access_count=row["access_count"] or 0,
            importance_score=importance_score,
            last_accessed_at=last_accessed_at,
            version=version,
            superseded_at=superseded_at,
            supersedes=supersedes,
            memory_nature=row["memory_nature"] if "memory_nature" in row.keys() else "state",
            version_chain_id=row["version_chain_id"] if "version_chain_id" in row.keys() else None,
            version_number=row["version_number"] if "version_number" in row.keys() else 1,
        )

    def _dict_to_stored(self, d: Dict) -> Optional[StoredMemory]:
        """Convert a dict back to StoredMemory (for merged results)."""
        if not d or not isinstance(d, dict):
            return None

        try:
            metadata = {}
            if d.get("metadata"):
                if isinstance(d["metadata"], str):
                    metadata = json.loads(d["metadata"])
                elif isinstance(d["metadata"], dict):
                    metadata = d["metadata"]

            recall_hint = None
            if d.get("recall_hint"):
                if isinstance(d["recall_hint"], str):
                    recall_hint = json.loads(d["recall_hint"])
                else:
                    recall_hint = d["recall_hint"]

            expires_at = None
            if d.get("expires_at"):
                if isinstance(d["expires_at"], str):
                    expires_at = datetime.fromisoformat(d["expires_at"])
                else:
                    expires_at = d["expires_at"]

            created_at = None
            if d.get("created_at"):
                if isinstance(d["created_at"], str):
                    created_at = datetime.fromisoformat(d["created_at"])
                else:
                    created_at = d["created_at"]

            updated_at = None
            if d.get("updated_at"):
                if isinstance(d["updated_at"], str):
                    updated_at = datetime.fromisoformat(d["updated_at"])
                else:
                    updated_at = d["updated_at"]

            last_accessed_at = None
            if d.get("last_accessed_at"):
                if isinstance(d["last_accessed_at"], str):
                    last_accessed_at = datetime.fromisoformat(d["last_accessed_at"])
                else:
                    last_accessed_at = d["last_accessed_at"]

            return StoredMemory(
                id=d.get("id"),
                type=d.get("type", "unknown"),
                content=d.get("content", ""),
                raw_text=d.get("raw_text", ""),
                confidence=d.get("confidence", 0.0),
                tier=d.get("tier", 2),
                source_layer=d.get("source_layer", "unknown"),
                reasoning=d.get("reasoning", ""),
                suggested_action=d.get("suggested_action", "store"),
                recall_hint=recall_hint,
                metadata=metadata,
                storage_key=d.get("storage_key"),
                created_at=created_at,
                updated_at=updated_at,
                expires_at=expires_at,
                access_count=d.get("access_count", 0),
                importance_score=d.get("importance_score", 0.0),
                last_accessed_at=last_accessed_at,
                version=d.get("version", 1),
                memory_nature=d.get("memory_nature", "state"),
                version_chain_id=d.get("version_chain_id"),
                version_number=d.get("version_number", 1),
            )
        except Exception as e:
            from carrymem.utils.logger import logger
            logger.debug(f"Failed to convert dict to StoredMemory: {e}")
            return None

