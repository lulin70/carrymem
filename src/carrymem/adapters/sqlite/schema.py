"""Schema initialization and migration for SQLiteAdapter."""

import sqlite3
from datetime import datetime, timezone

try:
    import pysqlite3.dbapi2 as _pysqlite3

    _OpError = (sqlite3.OperationalError, _pysqlite3.OperationalError)
except ImportError:
    _OpError = (sqlite3.OperationalError,)

from ...exceptions import DatabaseError
from ...scoring import calculate_importance
from ...utils.logger import logger

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


class SchemaManager:
    """Manages database schema creation and migrations."""

    def __init__(self, conn_manager):
        self._conn_mgr = conn_manager

    def init_schema(self):
        conn = self._conn_mgr.get_connection()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.executescript(_VERSION_SCHEMA_SQL)
            conn.commit()
            self._migrate_fts_tokenizer()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize schema: {e}") from e

    def migrate_all(self, enable_vector: bool = False):
        """Run all migrations in order."""
        self.migrate_namespace()
        self.migrate_v050()
        self.migrate_v060()
        if enable_vector:
            self.init_vec_schema()
            self.migrate_v070()
        self.migrate_v080()
        self.migrate_v090()

    def migrate_namespace(self):
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT namespace FROM memories LIMIT 1")
        except _OpError:
            try:
                conn.executescript(_MIGRATION_SQL)
                conn.executescript(_CREATE_INDEX_SQL)
                conn.commit()
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to migrate namespace: {e}") from e

    def _migrate_fts_tokenizer(self):
        conn = self._conn_mgr.get_connection()
        try:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='memories_fts'").fetchone()
            if row and "unicode61" in (row[0] or ""):
                conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
                conn.commit()
        except _OpError as e:
            logger.debug(f"FTS5 tokenizer migration skipped: {e}")

    def migrate_v050(self):
        conn = self._conn_mgr.get_connection()
        needs_recalculate = False
        try:
            conn.execute("SELECT importance_score FROM memories LIMIT 1")
        except _OpError:
            needs_recalculate = True
            try:
                for sql in _V050_MIGRATION_SQL:
                    try:
                        conn.execute(sql)
                    except _OpError:
                        pass
                conn.commit()
            except sqlite3.Error as e:
                logger.warning(f"Failed to migrate v0.5.0 columns: {e}")

        for sql in _V050_INDEX_SQL:
            try:
                conn.execute(sql)
            except _OpError:
                pass
        conn.commit()

        if needs_recalculate:
            self.recalculate_all_importance()

    def recalculate_all_importance(self):
        conn = self._conn_mgr.get_connection()
        try:
            rows = conn.execute(
                "SELECT storage_key, confidence, type, created_at, access_count FROM memories"
            ).fetchall()
            now = datetime.now(timezone.utc)
            updates = []
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
                    updates.append((score, row["storage_key"]))
                except (ValueError, TypeError):
                    continue
            if updates:
                conn.executemany(
                    "UPDATE memories SET importance_score = ? WHERE storage_key = ?",
                    updates,
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Failed to recalculate importance scores: {e}")
            return 0
        return len(updates)

    def migrate_v060(self):
        conn = self._conn_mgr.get_connection()
        needs_fts_rebuild = False
        try:
            conn.execute("SELECT raw_text FROM memories LIMIT 1")
        except _OpError:
            needs_fts_rebuild = True
            try:
                for sql in _V060_MIGRATION_SQL:
                    try:
                        conn.execute(sql)
                    except _OpError:
                        pass
                conn.commit()
            except sqlite3.Error as e:
                logger.warning(f"Failed to migrate v0.6.0 raw_text column: {e}")

        fts_needs_raw_text = False
        try:
            conn.execute("SELECT raw_text FROM memories_fts LIMIT 0")
        except _OpError:
            fts_needs_raw_text = True

        if needs_fts_rebuild or fts_needs_raw_text:
            try:
                for sql in _V060_FTS_REBUILD_SQL:
                    try:
                        conn.execute(sql)
                    except _OpError:
                        pass
                conn.commit()
                logger.info("FTS5 rebuilt with raw_text column")
            except sqlite3.Error as e:
                logger.warning(f"Failed to rebuild FTS5: {e}")

    def init_vec_schema(self, embedding_dim: int = 384):
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
                    memory_id TEXT PRIMARY KEY,
                    embedding float[{embedding_dim}]
                )
            """)
            conn.commit()
        except Exception as e:
            logger.warning(f"Failed to create memory_vectors table: {e}")

    def migrate_v070(self):
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT memory_id FROM memory_vectors LIMIT 1")
        except _OpError:
            self.init_vec_schema()

    def migrate_v080(self):
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT superseded_at FROM memories LIMIT 1")
        except _OpError:
            for sql in _V080_MIGRATION_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            for sql in _V080_INDEX_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass

    def migrate_v090(self):
        """Add memory_nature, version_chain_id, version_number columns."""
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT memory_nature FROM memories LIMIT 1")
        except _OpError:
            for sql in _V090_MIGRATION_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            for sql in _V090_INDEX_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            # Backfill: infer memory_nature from type
            conn.execute(
                "UPDATE memories SET memory_nature = 'event' " "WHERE type IN ('session_summary', 'task_pattern')"
            )
            conn.commit()
