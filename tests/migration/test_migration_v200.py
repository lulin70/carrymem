"""Migration v200 evolution foundation tests (Phase 1, ADR-018).

Covers test plan items:
  - MIG-1: empty database migration succeeds
  - MIG-2: repeated migration is idempotent (ledger short-circuit)
  - MIG-9: ledger checksum tampering is detected (fail-closed)
  - Ledger bookkeeping: rows recorded with success status and checksum

Uses real SQLiteAdapter (in-memory) per testing philosophy — no mocks.
"""

from __future__ import annotations

import sqlite3

import pytest

from carrymem.adapters.sqlite.schema import _V200_MIGRATION_ID, SchemaManager
from carrymem.exceptions import DatabaseError


class _FakeConnManager:
    """Minimal connection manager matching SchemaManager's expectations."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_connection(self) -> sqlite3.Connection:
        return self._conn


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    # memories table with the columns legacy migrations query (type for the
    # v090 backfill) — keeps migrate_all honest on this fixture.
    connection.execute("""CREATE TABLE memories (
        id TEXT PRIMARY KEY, type TEXT, content TEXT, raw_text TEXT NOT NULL DEFAULT '',
        original_message TEXT, confidence REAL NOT NULL DEFAULT 0.5,
        storage_key TEXT UNIQUE, namespace TEXT NOT NULL DEFAULT 'default',
        content_hash TEXT, created_at TEXT, updated_at TEXT
    )""")
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def schema(conn):
    return SchemaManager(_FakeConnManager(conn))


class TestMigrationV200EmptyDatabase:
    """MIG-1: empty database migration succeeds."""

    def test_creates_ledger_and_evidence_tables(self, schema, conn):
        schema.migrate_v200()

        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "carrymem_migrations" in tables
        assert "memory_evidence_links" in tables

    def test_records_success_row_with_checksum(self, schema, conn):
        schema.migrate_v200()

        row = conn.execute(
            "SELECT migration_id, status, checksum, completed_at FROM carrymem_migrations WHERE migration_id = ?",
            (_V200_MIGRATION_ID,),
        ).fetchone()
        assert row is not None
        assert row["status"] == "success"
        assert len(row["checksum"]) == 64  # sha256 hex
        assert row["completed_at"] is not None

    def test_evidence_table_unique_constraint_present(self, schema, conn):
        schema.migrate_v200()

        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='memory_evidence_links'"
        ).fetchone()["sql"]
        assert "UNIQUE" in ddl


class TestMigrationV200Idempotent:
    """MIG-2: repeated migration is idempotent."""

    def test_rerun_short_circuits_without_error(self, schema, conn):
        schema.migrate_v200()
        before = conn.execute("SELECT checksum, completed_at FROM carrymem_migrations").fetchone()

        schema.migrate_v200()  # must not raise and must not re-execute

        after = conn.execute("SELECT checksum, completed_at FROM carrymem_migrations").fetchone()
        assert after["checksum"] == before["checksum"]
        assert after["completed_at"] == before["completed_at"]

    def test_migrate_all_runs_v200(self, schema, conn):
        schema.migrate_all()
        row = conn.execute(
            "SELECT status FROM carrymem_migrations WHERE migration_id = ?", (_V200_MIGRATION_ID,)
        ).fetchone()
        assert row is not None and row["status"] == "success"


class TestMigrationV200FailClosed:
    """MIG-9 / ADR-018: checksum tampering and DDL failure are fail-closed."""

    def test_checksum_tamper_detected(self, schema, conn):
        schema.migrate_v200()
        conn.execute(
            "UPDATE carrymem_migrations SET checksum = ? WHERE migration_id = ?",
            ("0" * 64, _V200_MIGRATION_ID),
        )
        conn.commit()

        with pytest.raises(DatabaseError, match="checksum mismatch"):
            schema.migrate_v200()

    def test_ddl_failure_rolls_back_and_raises(self, schema, conn, monkeypatch):
        from carrymem.adapters.sqlite import schema as schema_mod

        broken_sql = list(schema_mod._V200_EVOLUTION_SQL) + ["INSERT INTO nonexistent_table VALUES (1)"]
        monkeypatch.setattr(schema_mod, "_V200_EVOLUTION_SQL", broken_sql)

        with pytest.raises(DatabaseError, match="fail-closed"):
            schema.migrate_v200()

        # Rollback guarantee: the ledger table itself is rolled back with the
        # transaction (or, if present, carries no success row for v200).
        ledger = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='carrymem_migrations'"
        ).fetchone()
        if ledger is not None:
            row = conn.execute(
                "SELECT status FROM carrymem_migrations WHERE migration_id = ?", (_V200_MIGRATION_ID,)
            ).fetchone()
            assert row is None


class TestEvidenceSchemaConstraints:
    """INV-E3: the UNIQUE constraint rejects duplicate links at the SQL level."""

    def test_duplicate_link_rejected_by_unique(self, schema, conn):
        schema.migrate_v200()

        insert = (
            "INSERT INTO memory_evidence_links "
            "(id, namespace, source_kind, source_id, source_snapshot_hash, "
            "target_kind, target_id, relation_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        conn.execute(insert, ("a1", "default", "memory", "s1", "h1", "memory", "t1", "derived_from"))
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert, ("a2", "default", "memory", "s1", "h1", "memory", "t1", "derived_from"))
