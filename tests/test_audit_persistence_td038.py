"""Tests for TD-038: SQLiteAdapter-driven AuditLogger persistence.

Verifies that audit events logged through the SQLiteAdapter's audit logger
survive process restarts (close → reopen → query). The default in-memory
mode (:memory: main DB) is also covered to ensure backward compatibility.
"""

import os

import pytest

from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.security.audit import AuditEvent, AuditFilter


@pytest.fixture
def file_db_path(tmp_path) -> str:
    """Return a filesystem path for a file-backed SQLite DB."""
    return str(tmp_path / "td038_memories.db")


def _log_sample_events(adapter: SQLiteAdapter) -> None:
    """Log a small set of audit events through the adapter's audit logger."""
    assert adapter._audit is not None
    adapter._audit.log_operation(
        operation="remember",
        storage_key="mem_001",
        memory_type="user_preference",
        success=True,
        details={"note": "first event"},
    )
    adapter._audit.log_operation(
        operation="forget",
        storage_key="mem_002",
        memory_type="decision",
        success=False,
        details={"reason": "not found"},
    )
    adapter._audit.log(
        AuditEvent(
            user_id="tester",
            action="WRITE",
            resource="memory",
            result="SUCCESS",
            details={"storage_key": "mem_003"},
        )
    )


class TestSQLiteAdapterAuditPersistence:
    """TD-038: AuditLogger backed by SQLite survives adapter restart."""

    def test_audit_events_persist_across_restart(self, file_db_path):
        # Phase 1: create adapter, log events, close.
        adapter1 = SQLiteAdapter(db_path=file_db_path)
        try:
            assert adapter1._audit is not None
            assert adapter1._audit._db_conn is not None, (
                "File-backed SQLiteAdapter should create a persistent AuditLogger"
            )
            assert adapter1._audit._persist_path == file_db_path + ".audit.db"
            _log_sample_events(adapter1)
            assert len(adapter1._audit.query()) == 3
        finally:
            adapter1.close()

        # Sanity: the sidecar audit.db file exists on disk.
        assert os.path.exists(file_db_path + ".audit.db")

        # Phase 2: reopen with the same db_path and query — events must survive.
        adapter2 = SQLiteAdapter(db_path=file_db_path)
        try:
            assert adapter2._audit is not None
            assert adapter2._audit._db_conn is not None
            # In-memory list starts empty on a fresh instance, so query()
            # falls back to SQLite (this is the restart-resilience path).
            results = adapter2._audit.query()
            assert len(results) == 3, (
                f"Expected 3 persisted audit events after restart, got {len(results)}"
            )
            actions = {r.action for r in results}
            assert actions == {"remember", "forget", "WRITE"}
        finally:
            adapter2.close()

    def test_audit_query_with_filter_after_restart(self, file_db_path):
        adapter1 = SQLiteAdapter(db_path=file_db_path)
        try:
            _log_sample_events(adapter1)
        finally:
            adapter1.close()

        adapter2 = SQLiteAdapter(db_path=file_db_path)
        try:
            # Filter by action — only "remember" events should match.
            results = adapter2._audit.query(AuditFilter(action="remember"))
            assert len(results) == 1
            assert results[0].action == "remember"
            assert results[0].resource == "mem_001"
            assert results[0].details["note"] == "first event"

            # Filter by user_id — only the WRITE event has user_id="tester".
            results_user = adapter2._audit.query(AuditFilter(user_id="tester"))
            assert len(results_user) == 1
            assert results_user[0].action == "WRITE"

            # Filter by result — two SUCCESS + one FAILURE.
            success_results = adapter2._audit.query(AuditFilter(result="SUCCESS"))
            assert len(success_results) == 2
            failure_results = adapter2._audit.query(AuditFilter(result="FAILURE"))
            assert len(failure_results) == 1
            assert failure_results[0].action == "forget"
        finally:
            adapter2.close()

    def test_audit_stats_after_restart(self, file_db_path):
        adapter1 = SQLiteAdapter(db_path=file_db_path)
        try:
            _log_sample_events(adapter1)
        finally:
            adapter1.close()

        adapter2 = SQLiteAdapter(db_path=file_db_path)
        try:
            stats = adapter2._audit.get_stats()
            assert stats["total_events"] == 3
            assert stats["by_action"]["remember"] == 1
            assert stats["by_action"]["forget"] == 1
            assert stats["by_action"]["WRITE"] == 1
            assert stats["by_result"]["SUCCESS"] == 2
            assert stats["by_result"]["FAILURE"] == 1
            assert stats["last_event"] is not None
        finally:
            adapter2.close()

    def test_audit_export_after_restart(self, file_db_path):
        import json

        adapter1 = SQLiteAdapter(db_path=file_db_path)
        try:
            _log_sample_events(adapter1)
        finally:
            adapter1.close()

        adapter2 = SQLiteAdapter(db_path=file_db_path)
        try:
            json_str = adapter2._audit.export("json")
            data = json.loads(json_str)
            assert len(data) == 3
            exported_actions = {e["action"] for e in data}
            assert exported_actions == {"remember", "forget", "WRITE"}
        finally:
            adapter2.close()


class TestSQLiteAdapterInMemoryAuditBackwardCompat:
    """TD-038: :memory: main DB keeps AuditLogger in-memory (backward compat)."""

    def test_in_memory_adapter_uses_in_memory_audit(self):
        adapter = SQLiteAdapter(db_path=":memory:")
        try:
            assert adapter._audit is not None
            assert adapter._audit._db_conn is None, (
                "In-memory SQLiteAdapter should keep AuditLogger in memory"
            )
            assert adapter._audit._persist_path is None

            # Audit logging still works in-memory.
            adapter._audit.log_operation("remember", storage_key="mem_001")
            results = adapter._audit.query()
            assert len(results) == 1
            assert results[0].action == "remember"
        finally:
            adapter.close()

    def test_in_memory_audit_does_not_leak_sidecar_file(self, tmp_path):
        # Even when the adapter is created inside a tmp_path, the in-memory
        # mode must NOT create a sidecar audit.db file on disk.
        adapter = SQLiteAdapter(db_path=":memory:")
        try:
            adapter._audit.log_operation("remember")
        finally:
            adapter.close()
        # No sidecar audit.db should exist anywhere in tmp_path.
        sidecar_files = list(tmp_path.glob("*.audit.db"))
        assert sidecar_files == [], f"Unexpected sidecar audit.db files: {sidecar_files}"
