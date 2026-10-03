"""Schema initialization and migration for SQLiteAdapter."""

import hashlib
import sqlite3
from datetime import datetime, timezone

try:
    import pysqlite3.dbapi2 as _pysqlite3

    _OpError: tuple = (sqlite3.OperationalError, _pysqlite3.OperationalError)
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

# v0.8.0 release: add confidence column to memory_relations for edge
# confidence labels (EXTRACTED / INFERRED / AMBIGUOUS). Uses migrate_v100
# because migrate_v080/v090 were already taken by superseded_at and
# memory_nature columns respectively.
_V100_GRAPH_CONFIDENCE_SQL = [
    "ALTER TABLE memory_relations ADD COLUMN confidence TEXT NOT NULL DEFAULT 'EXTRACTED'",
]

_V100_GRAPH_CONFIDENCE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_relations_confidence ON memory_relations(confidence)",
]

_V051_ENTITY_ALIASES_SQL = """
CREATE TABLE IF NOT EXISTS entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_form TEXT NOT NULL,
    alias_form TEXT NOT NULL,
    entity_type TEXT,
    namespace TEXT NOT NULL,
    similarity_score REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    UNIQUE(canonical_form, alias_form, namespace)
);
"""

_V051_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_entity_aliases_namespace ON entity_aliases(namespace)",
    "CREATE INDEX IF NOT EXISTS idx_entity_aliases_canonical ON entity_aliases(canonical_form)",
]

_V051_MIGRATION_SQL = [
    "ALTER TABLE memories ADD COLUMN entity_normalized TEXT",
    "ALTER TABLE memories ADD COLUMN entity_id TEXT",
]

_V052_MIGRATION_SQL = [
    "ALTER TABLE memories ADD COLUMN summary TEXT",
    "ALTER TABLE memories ADD COLUMN summary_level INTEGER",
]

_V062_GRAPH_SQL = """
CREATE TABLE IF NOT EXISTS memory_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_key TEXT,
    entity_type TEXT NOT NULL,
    entity_text TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    namespace TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (memory_key) REFERENCES memories(storage_key) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS memory_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_entity_id INTEGER NOT NULL,
    dst_entity_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    source_memory_key TEXT,
    weight REAL NOT NULL DEFAULT 1.0,
    namespace TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (src_entity_id) REFERENCES memory_entities(id),
    FOREIGN KEY (dst_entity_id) REFERENCES memory_entities(id)
);
"""

_V062_GRAPH_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_entities_text ON memory_entities(entity_text)",
    "CREATE INDEX IF NOT EXISTS idx_entities_type ON memory_entities(entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_entities_memory ON memory_entities(memory_key)",
    "CREATE INDEX IF NOT EXISTS idx_entities_namespace ON memory_entities(namespace)",
    "CREATE INDEX IF NOT EXISTS idx_relations_src ON memory_relations(src_entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_relations_dst ON memory_relations(dst_entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_relations_type ON memory_relations(relation_type)",
    "CREATE INDEX IF NOT EXISTS idx_relations_namespace ON memory_relations(namespace)",
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

# v2.x evolution foundation (Phase 1 Provenance, ADR-015/ADR-018):
# migration ledger (fail-closed bookkeeping) + evidence links (provenance).
_V200_EVOLUTION_SQL = [
    """CREATE TABLE IF NOT EXISTS carrymem_migrations (
    migration_id TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_text TEXT
)""",
    """CREATE TABLE IF NOT EXISTS memory_evidence_links (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_snapshot_hash TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    support_weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (namespace, source_kind, source_id, target_kind, target_id, relation_type)
)""",
    "CREATE INDEX IF NOT EXISTS idx_evidence_target ON memory_evidence_links(namespace, target_kind, target_id)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_source ON memory_evidence_links(namespace, source_kind, source_id)",
]

_V200_MIGRATION_ID = "v200_evolution_foundation"

# Phase 2 observation/conflict ledger. Keep v200 SQL and checksum immutable.
_V210_PHASE2_SQL = [
    """CREATE TABLE IF NOT EXISTS memory_observations (
        id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        subject TEXT NOT NULL,
        predicate TEXT NOT NULL,
        value_json TEXT NOT NULL,
        source_kind TEXT NOT NULL,
        source_ref TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.5 CHECK (confidence >= 0.0 AND confidence <= 1.0),
        observed_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'valid' CHECK (status IN ('valid', 'unsupported')),
        UNIQUE (namespace, subject, predicate, source_kind, source_ref, observed_at)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_observations_subject ON memory_observations(namespace, subject, predicate)",
    "CREATE INDEX IF NOT EXISTS idx_observations_expires ON memory_observations(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_observations_source ON memory_observations(namespace, source_kind)",
    """CREATE TABLE IF NOT EXISTS memory_conflicts (
        conflict_id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        subject_key TEXT NOT NULL,
        candidate_ids TEXT NOT NULL,
        conflict_type TEXT NOT NULL,
        resolution_status TEXT NOT NULL,
        resolution_policy TEXT NOT NULL,
        selected_id TEXT,
        reasoning TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        CHECK (resolution_status IN ('unresolved', 'resolved', 'user_decided', 'expired')),
        CHECK ((resolution_status = 'unresolved' AND selected_id IS NULL) OR
               (resolution_status IN ('resolved', 'user_decided') AND selected_id IS NOT NULL) OR
               resolution_status = 'expired')
    )""",
    "CREATE INDEX IF NOT EXISTS idx_conflicts_subject ON memory_conflicts(namespace, subject_key, resolution_status)",
]

_V210_MIGRATION_ID = "v210_phase2_observation_conflict"

# Phase 4 reflection run/proposal ledger (ADR-016, contract
# MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md §2/§3). Keep v210 SQL and checksum immutable.
_V220_PHASE4_SQL = [
    """CREATE TABLE IF NOT EXISTS memory_reflection_runs (
    run_id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    reflection_type TEXT NOT NULL CHECK (reflection_type IN (
        'dedup', 'conflict_scan', 'decay', 'fact_derivation',
        'profile_rebuild', 'aggregation', 'graph_maintenance')),
    strategy_version TEXT NOT NULL,
    input_cursor TEXT,
    input_snapshot TEXT NOT NULL,
    config_snapshot TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'running', 'completed', 'failed', 'cancelled', 'interrupted')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_text TEXT,
    idempotency_key TEXT NOT NULL,
    UNIQUE (namespace, reflection_type, input_snapshot, config_snapshot)
)""",
    "CREATE INDEX IF NOT EXISTS idx_reflection_runs_status ON memory_reflection_runs(namespace, status)",
    "CREATE INDEX IF NOT EXISTS idx_reflection_runs_idem ON memory_reflection_runs(idempotency_key)",
    """CREATE TABLE IF NOT EXISTS memory_reflection_outputs (
    proposal_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    proposal_type TEXT NOT NULL CHECK (proposal_type IN (
        'fact_candidate', 'profile_rebuild', 'model_claim', 'rule_candidate',
        'graph_update', 'dedup_merge', 'supersede', 'expire_projection')),
    target_kind TEXT,
    target_id TEXT,
    payload_json TEXT NOT NULL,
    source_observation_ids TEXT NOT NULL,
    source_evidence_ids TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    reasoning TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'high')),
    status TEXT NOT NULL CHECK (status IN (
        'proposed', 'approved', 'rejected', 'applied', 'failed',
        'rolled_back', 'expired')),
    approved_by TEXT,
    applied_at TEXT,
    rollback_ref TEXT,
    error_text TEXT,
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (namespace, proposal_type, idempotency_key),
    CHECK ((status = 'applied' AND rollback_ref IS NOT NULL AND applied_at IS NOT NULL)
           OR status != 'applied'),
    CHECK ((status = 'rejected' AND approved_by IS NOT NULL) OR status != 'rejected')
)""",
    "CREATE INDEX IF NOT EXISTS idx_reflection_outputs_status ON memory_reflection_outputs(namespace, status)",
    "CREATE INDEX IF NOT EXISTS idx_reflection_outputs_run ON memory_reflection_outputs(run_id)",
]

_V220_MIGRATION_ID = "v220_phase4_reflection_proposal"


class SchemaManager:
    """Manages database schema creation and migrations."""

    def __init__(self, conn_manager):
        self._conn_mgr = conn_manager

    def init_schema(self):
        """Create the core tables and version schema."""
        with self._conn_mgr.file_lock:
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
        with self._conn_mgr.file_lock:
            self.migrate_namespace()
            self.migrate_v050()
            self.migrate_v060()
            self.migrate_v062()
            if enable_vector:
                self.init_vec_schema()
                self.migrate_v070()
            self.migrate_v080()
            self.migrate_v090()
            self.migrate_v100()
            self.migrate_v051()
            self.migrate_v052()
            self.migrate_v200()
            self.migrate_v210()
            self.migrate_v220()

    def migrate_namespace(self):
        """Add the namespace column to the memories table if missing."""
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT namespace FROM memories LIMIT 1")
        except _OpError as check_error:
            if "no such column" not in str(check_error).lower():
                raise
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
            logger.debug("FTS5 tokenizer migration skipped: %s", e)

    def migrate_v050(self):
        """Add v0.5.0 importance columns and rebuild indexes."""
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
                logger.warning("Failed to migrate v0.5.0 columns: %s", e)

        for sql in _V050_INDEX_SQL:
            try:
                conn.execute(sql)
            except _OpError:
                pass
        conn.commit()

        if needs_recalculate:
            self.recalculate_all_importance()

    def recalculate_all_importance(self):
        """Recompute importance_score for every stored memory."""
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
            logger.warning("Failed to recalculate importance scores: %s", e)
            return 0
        return len(updates)

    def migrate_v060(self):
        """Add the raw_text column and rebuild FTS5 if needed."""
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
                logger.warning("Failed to migrate v0.6.0 raw_text column: %s", e)

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
                logger.warning("Failed to rebuild FTS5: %s", e)

    def migrate_v062(self):
        """Create knowledge graph tables (memory_entities + memory_relations) for v0.7.0."""
        conn = self._conn_mgr.get_connection()
        try:
            conn.executescript(_V062_GRAPH_SQL)
            for sql in _V062_GRAPH_INDEX_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            conn.commit()
        except sqlite3.Error as e:
            logger.warning("Failed to create knowledge graph tables: %s", e)

    def init_vec_schema(self, embedding_dim: int = 384):
        """Create the vector search virtual table."""
        with self._conn_mgr.file_lock:
            conn = self._conn_mgr.get_connection()
            try:
                conn.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
                        memory_id TEXT PRIMARY KEY,
                        embedding float[{embedding_dim}]
                    )
                """)
                conn.commit()
            except sqlite3.Error as e:
                logger.warning("Failed to create memory_vectors table: %s", e)

    def migrate_v070(self):
        """Ensure the vector table exists for v0.7.0."""
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT memory_id FROM memory_vectors LIMIT 1")
        except _OpError:
            self.init_vec_schema()

    def migrate_v080(self):
        """Add the superseded_at column for v0.8.0."""
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

    def migrate_v100(self):
        """Add confidence column to memory_relations for edge labels (v0.8.0).

        Adds a TEXT column ``confidence`` with DEFAULT 'EXTRACTED' to the
        ``memory_relations`` table. Valid values: EXTRACTED (deterministic
        extraction), INFERRED (LLM inference), AMBIGUOUS (needs confirmation).
        Idempotent — checks column existence before altering.
        """
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT confidence FROM memory_relations LIMIT 1")
        except _OpError:
            for sql in _V100_GRAPH_CONFIDENCE_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            for sql in _V100_GRAPH_CONFIDENCE_INDEX_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            conn.commit()

    def migrate_v051(self):
        """Add entity_aliases table and entity_normalized/entity_id columns (v0.5.1)."""
        conn = self._conn_mgr.get_connection()
        # entity_aliases table (idempotent — CREATE IF NOT EXISTS)
        try:
            conn.executescript(_V051_ENTITY_ALIASES_SQL)
            for sql in _V051_INDEX_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            conn.commit()
        except sqlite3.Error as e:
            logger.warning("Failed to create entity_aliases table: %s", e)

        # memories table: entity_normalized + entity_id columns
        try:
            conn.execute("SELECT entity_normalized FROM memories LIMIT 1")
        except _OpError:
            for sql in _V051_MIGRATION_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            conn.commit()

    def migrate_v052(self):
        """Add summary and summary_level columns to memories table (v0.5.2)."""
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute("SELECT summary FROM memories LIMIT 1")
        except _OpError:
            for sql in _V052_MIGRATION_SQL:
                try:
                    conn.execute(sql)
                except _OpError:
                    pass
            conn.commit()

    def migrate_v200(self):
        """Create the evolution foundation: migration ledger + evidence links.

        Phase 1 Provenance (ADR-015/ADR-018). Fail-closed semantics:

        - DDL and ledger insert run in a single transaction; any failure
          rolls back and raises :class:`DatabaseError` (the service must not
          start with a half-migrated schema).
        - On re-run, a successful ledger row short-circuits the migration.
        - A ledger row whose checksum no longer matches the migration SQL
          aborts with ``DatabaseError`` (tamper detection, MIG-9).
        """
        conn = self._conn_mgr.get_connection()
        checksum = hashlib.sha256("\n".join(_V200_EVOLUTION_SQL).encode("utf-8")).hexdigest()
        try:
            row = conn.execute(
                "SELECT checksum, status FROM carrymem_migrations WHERE migration_id = ?",
                (_V200_MIGRATION_ID,),
            ).fetchone()
        except _OpError:
            row = None  # ledger table missing — first run
        if row is not None:
            recorded_checksum, recorded_status = str(row["checksum"]), str(row["status"])
            if recorded_checksum != checksum:
                raise DatabaseError(
                    f"Migration {_V200_MIGRATION_ID} checksum mismatch "
                    f"(ledger={recorded_checksum[:12]}, expected={checksum[:12]}). "
                    "Refusing to proceed (fail-closed)."
                )
            if recorded_status != "success":
                raise DatabaseError(
                    f"Migration {_V200_MIGRATION_ID} has ledger status "
                    f"{recorded_status!r}; refusing to proceed (fail-closed)."
                )
            return  # already applied — idempotent short-circuit

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            for sql in _V200_EVOLUTION_SQL:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO carrymem_migrations (migration_id, checksum, status, started_at, completed_at) "
                "VALUES (?, ?, 'success', ?, ?) "
                "ON CONFLICT(migration_id) DO UPDATE SET "
                "checksum = excluded.checksum, status = 'success', "
                "completed_at = excluded.completed_at, error_text = NULL",
                (_V200_MIGRATION_ID, checksum, now_iso, now_iso),
            )
            conn.commit()
        except sqlite3.Error as e:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise DatabaseError(f"Migration {_V200_MIGRATION_ID} failed (fail-closed): {e}") from e

    def migrate_v210(self):
        """Create Phase 2 observation/conflict tables with a tamper-evident ledger."""
        conn = self._conn_mgr.get_connection()
        checksum = hashlib.sha256("\n".join(_V210_PHASE2_SQL).encode("utf-8")).hexdigest()
        row = conn.execute(
            "SELECT checksum, status FROM carrymem_migrations WHERE migration_id = ?",
            (_V210_MIGRATION_ID,),
        ).fetchone()
        if row is not None:
            if row["checksum"] != checksum:
                raise DatabaseError(f"Migration {_V210_MIGRATION_ID} checksum mismatch (fail-closed)")
            if row["status"] != "success":
                raise DatabaseError(
                    f"Migration {_V210_MIGRATION_ID} has ledger status "
                    f"{row['status']!r}; refusing to proceed (fail-closed)."
                )
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            for sql in _V210_PHASE2_SQL:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO carrymem_migrations (migration_id, checksum, status, started_at, completed_at) "
                "VALUES (?, ?, 'success', ?, ?) ON CONFLICT(migration_id) DO UPDATE SET "
                "checksum=excluded.checksum, status='success', completed_at=excluded.completed_at, error_text=NULL",
                (_V210_MIGRATION_ID, checksum, now_iso, now_iso),
            )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Migration {_V210_MIGRATION_ID} failed (fail-closed): {e}") from e

    def migrate_v220(self):
        """Create Phase 4 reflection run/proposal tables with a tamper-evident ledger."""
        conn = self._conn_mgr.get_connection()
        checksum = hashlib.sha256("\n".join(_V220_PHASE4_SQL).encode("utf-8")).hexdigest()
        row = conn.execute(
            "SELECT checksum, status FROM carrymem_migrations WHERE migration_id = ?",
            (_V220_MIGRATION_ID,),
        ).fetchone()
        if row is not None:
            if row["checksum"] != checksum:
                raise DatabaseError(f"Migration {_V220_MIGRATION_ID} checksum mismatch (fail-closed)")
            if row["status"] != "success":
                raise DatabaseError(
                    f"Migration {_V220_MIGRATION_ID} has ledger status "
                    f"{row['status']!r}; refusing to proceed (fail-closed)."
                )
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            for sql in _V220_PHASE4_SQL:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO carrymem_migrations (migration_id, checksum, status, started_at, completed_at) "
                "VALUES (?, ?, 'success', ?, ?) ON CONFLICT(migration_id) DO UPDATE SET "
                "checksum=excluded.checksum, status='success', completed_at=excluded.completed_at, error_text=NULL",
                (_V220_MIGRATION_ID, checksum, now_iso, now_iso),
            )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Migration {_V220_MIGRATION_ID} failed (fail-closed): {e}") from e
