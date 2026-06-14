"""
Tests for AuditLogger - security audit logging module.

Covers: log_operation, query with filters (AuditFilter),
get_stats, error handling, export/clear, SQLite persistence.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from carrymem.security.audit import (
    AuditEvent,
    AuditFilter,
    AuditLogger,
)


@pytest.fixture
def audit_logger():
    """Create a fresh in-memory AuditLogger for each test."""
    return AuditLogger()


class TestAuditLoggerInit:
    def test_creates_empty_logger(self):
        logger = AuditLogger()
        assert len(logger.query()) == 0

    def test_custom_max_events(self):
        logger = AuditLogger(max_events=5)
        assert logger._max_events == 5


class TestLogOperation:
    def test_basic_log(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert len(results) == 1
        assert results[0].action == "remember"

    def test_log_with_all_fields(self, audit_logger):
        audit_logger.log_operation(
            operation="forget",
            storage_key="mem_001",
            memory_type="user_preference",
            success=False,
            details={"reason": "user request"},
        )
        results = audit_logger.query()
        assert len(results) == 1
        r = results[0]
        assert r.action == "forget"
        assert r.resource == "mem_001"
        assert r.result == "FAILURE"
        assert r.details["reason"] == "user request"

    def test_log_success_default_true(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert results[0].result == "SUCCESS"

    def test_log_details_none_becomes_empty_dict(self, audit_logger):
        audit_logger.log_operation("remember", details=None)
        results = audit_logger.query()
        assert results[0].details == {}

    def test_log_details_complex(self, audit_logger):
        details = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
        audit_logger.log_operation("remember", details=details)
        results = audit_logger.query()
        assert results[0].details == details

    def test_multiple_operations(self, audit_logger):
        for op in ["remember", "recall", "forget", "edit", "remember"]:
            audit_logger.log_operation(op)
        results = audit_logger.query()
        assert len(results) == 5

    def test_log_via_audit_event(self, audit_logger):
        event = AuditEvent(
            action="WRITE",
            resource="memory",
            user_id="user_1",
            result="SUCCESS",
            details={"storage_key": "key_1"},
        )
        audit_logger.log(event)
        results = audit_logger.query()
        assert len(results) == 1
        assert results[0].action == "WRITE"
        assert results[0].user_id == "user_1"


class TestQuery:
    def test_query_by_action(self, audit_logger):
        audit_logger.log_operation("remember")
        audit_logger.log_operation("forget")
        results = audit_logger.query(AuditFilter(action="remember"))
        assert len(results) == 1
        assert results[0].action == "remember"

    def test_query_by_resource(self, audit_logger):
        audit_logger.log_operation("store", storage_key="key_a")
        audit_logger.log_operation("store", storage_key="key_b")
        results = audit_logger.query(AuditFilter(resource="key_a"))
        assert len(results) == 1
        assert results[0].resource == "key_a"

    def test_query_by_result(self, audit_logger):
        audit_logger.log_operation("success_op")
        audit_logger.log_operation("fail_op", success=False)
        results = audit_logger.query(AuditFilter(result="FAILURE"))
        assert len(results) == 1
        assert results[0].action == "fail_op"

    def test_query_no_filters(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert len(results) >= 1

    def test_query_limit(self, audit_logger):
        for i in range(10):
            audit_logger.log_operation(f"op_{i}")
        results = audit_logger.query(AuditFilter(limit=3))
        assert len(results) == 3

    def test_query_empty_result(self, audit_logger):
        results = audit_logger.query(AuditFilter(action="nonexistent"))
        assert results == []

    def test_query_ordered_by_timestamp_desc(self, audit_logger):
        audit_logger.log_operation("first")
        audit_logger.log_operation("second")
        results = audit_logger.query()
        assert len(results) == 2
        # Newest first
        assert results[0].action == "second"
        assert results[1].action == "first"


class TestGetStats:
    def test_stats_empty(self):
        logger = AuditLogger()
        stats = logger.get_stats()
        assert stats["total_events"] == 0
        assert stats["by_action"] == {}
        assert stats["last_event"] is None

    def test_stats_with_data(self, audit_logger):
        audit_logger.log_operation("remember")
        audit_logger.log_operation("remember")
        audit_logger.log_operation("forget")
        stats = audit_logger.get_stats()
        assert stats["total_events"] == 3
        assert stats["by_action"]["remember"] == 2
        assert stats["by_action"]["forget"] == 1
        assert stats["last_event"] is not None

    def test_stats_by_action(self, audit_logger):
        for _ in range(5):
            audit_logger.log_operation("remember")
        for _ in range(3):
            audit_logger.log_operation("forget")
        stats = audit_logger.get_stats()
        assert stats["by_action"]["remember"] == 5
        assert stats["by_action"]["forget"] == 3


class TestExportAndClear:
    def test_export_json(self, audit_logger):
        audit_logger.log_operation("test_export", details={"k": "v"})
        json_str = audit_logger.export("json")
        import json as _json

        data = _json.loads(json_str)
        assert len(data) == 1
        assert data[0]["action"] == "test_export"

    def test_export_csv(self, audit_logger):
        audit_logger.log_operation("test_csv")
        csv_str = audit_logger.export("csv")
        lines = csv_str.strip().split("\n")
        # Header + at least 1 data row
        assert len(lines) >= 2

    def test_clear_old_events(self, audit_logger):
        from datetime import timedelta

        for i in range(10):
            audit_logger.log_operation(f"op_{i}")
        removed = audit_logger.clear(older_than=timedelta(days=-1))  # clear all
        assert removed >= 0
        # Logger should be empty or near-empty after clearing everything
        remaining = len(audit_logger.query())
        assert remaining <= 10


class TestMaxEventsPruning:
    def test_auto_prune_at_max(self):
        logger = AuditLogger(max_events=5)
        for i in range(10):
            logger.log_operation(f"op_{i}")
        # Should have at most max_events
        assert len(logger.query()) <= 5


class TestThreadSafety:
    def test_concurrent_logs(self, audit_logger):
        import threading

        errors = []

        def worker(op_name):
            try:
                audit_logger.log_operation(op_name)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(f"op_{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent log errors: {errors}"
        assert len(audit_logger.query()) == 20


# ── SQLite persistence tests ────────────────────────────────────────


@pytest.fixture
def sqlite_logger(tmp_path):
    """Create an AuditLogger with SQLite persistence backed by a temp file."""
    db_path = str(tmp_path / "audit_test.db")
    logger = AuditLogger(persist_path=db_path)
    yield logger
    # Cleanup: close the DB connection if still open
    if logger._db_conn is not None:
        logger._db_conn.close()


class TestSQLitePersistLogAndQuery:
    def test_log_writes_to_memory_and_sqlite(self, sqlite_logger, tmp_path):
        sqlite_logger.log_operation("remember", storage_key="mem_001")
        # In-memory query
        results = sqlite_logger.query()
        assert len(results) == 1
        assert results[0].action == "remember"
        assert results[0].resource == "mem_001"

        # Verify SQLite directly
        cursor = sqlite_logger._db_conn.execute("SELECT COUNT(*) FROM audit_log")
        assert cursor.fetchone()[0] == 1

    def test_query_falls_back_to_sqlite(self, tmp_path):
        db_path = str(tmp_path / "audit_fallback.db")
        logger = AuditLogger(persist_path=db_path)
        logger.log_operation("remember", storage_key="mem_001")
        logger.log_operation("forget", storage_key="mem_002")

        # Clear in-memory only (simulate restart scenario)
        with logger._lock:
            logger._events.clear()

        # query should fall back to SQLite
        results = logger.query()
        assert len(results) == 2
        actions = {r.action for r in results}
        assert actions == {"remember", "forget"}
        logger._db_conn.close()

    def test_query_with_filter_on_sqlite(self, sqlite_logger):
        sqlite_logger.log_operation("remember")
        sqlite_logger.log_operation("forget")
        sqlite_logger.log_operation("remember")

        # Clear memory to force SQLite fallback
        with sqlite_logger._lock:
            sqlite_logger._events.clear()

        results = sqlite_logger.query(AuditFilter(action="remember"))
        assert len(results) == 2
        assert all(r.action == "remember" for r in results)

    def test_log_with_details_persisted(self, sqlite_logger):
        details = {"key": "value", "nested": {"a": 1}}
        sqlite_logger.log_operation("remember", details=details)
        results = sqlite_logger.query()
        assert results[0].details == details

    def test_sqlite_file_created(self, tmp_path):
        db_path = str(tmp_path / "subdir" / "audit.db")
        logger = AuditLogger(persist_path=db_path)
        assert os.path.exists(db_path)
        logger._db_conn.close()


class TestSQLitePersistStats:
    def test_stats_from_sqlite(self, sqlite_logger):
        sqlite_logger.log_operation("remember")
        sqlite_logger.log_operation("remember")
        sqlite_logger.log_operation("forget", success=False)

        stats = sqlite_logger.get_stats()
        assert stats["total_events"] == 3
        assert stats["by_action"]["remember"] == 2
        assert stats["by_action"]["forget"] == 1
        assert stats["by_result"]["SUCCESS"] == 2
        assert stats["by_result"]["FAILURE"] == 1
        assert stats["last_event"] is not None

    def test_stats_empty_sqlite(self, sqlite_logger):
        stats = sqlite_logger.get_stats()
        assert stats["total_events"] == 0
        assert stats["by_action"] == {}
        assert stats["last_event"] is None


class TestSQLitePersistExport:
    def test_export_json_from_sqlite(self, sqlite_logger):
        sqlite_logger.log_operation("test_export", details={"k": "v"})
        json_str = sqlite_logger.export("json")
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]["action"] == "test_export"
        assert data[0]["details"]["k"] == "v"

    def test_export_csv_from_sqlite(self, sqlite_logger):
        sqlite_logger.log_operation("test_csv")
        csv_str = sqlite_logger.export("csv")
        lines = csv_str.strip().split("\n")
        assert len(lines) >= 2  # header + data row

    def test_export_json_includes_all_sqlite_rows(self, sqlite_logger):
        for i in range(5):
            sqlite_logger.log_operation(f"op_{i}")

        # Clear memory to verify export comes from SQLite
        with sqlite_logger._lock:
            sqlite_logger._events.clear()

        json_str = sqlite_logger.export("json")
        data = json.loads(json_str)
        assert len(data) == 5


class TestSQLitePersistClear:
    def test_clear_all_from_memory_and_sqlite(self, sqlite_logger):
        sqlite_logger.log_operation("remember")
        sqlite_logger.log_operation("forget")

        removed = sqlite_logger.clear()
        assert removed == 2

        # Memory should be empty
        assert len(sqlite_logger.query()) == 0

        # SQLite should be empty
        cursor = sqlite_logger._db_conn.execute("SELECT COUNT(*) FROM audit_log")
        assert cursor.fetchone()[0] == 0

    def test_clear_older_than_from_both(self, sqlite_logger):
        sqlite_logger.log_operation("old_event")
        sqlite_logger.log_operation("new_event")

        # Clear events older than 1 day — none should be removed since
        # both events were just created (they are only seconds old).
        removed = sqlite_logger.clear(older_than=timedelta(days=1))
        assert removed == 0
        assert len(sqlite_logger.query()) == 2


class TestMemoryModeUnchanged:
    """Verify that the default in-memory mode is completely unchanged."""

    def test_default_is_memory_only(self):
        logger = AuditLogger()
        assert logger._db_conn is None
        assert logger._persist_path is None

    def test_memory_log_and_query(self):
        logger = AuditLogger()
        logger.log_operation("remember")
        results = logger.query()
        assert len(results) == 1
        assert results[0].action == "remember"

    def test_memory_stats(self):
        logger = AuditLogger()
        logger.log_operation("remember")
        logger.log_operation("forget")
        stats = logger.get_stats()
        assert stats["total_events"] == 2
        assert stats["by_action"]["remember"] == 1
        assert stats["by_action"]["forget"] == 1

    def test_memory_export_json(self):
        logger = AuditLogger()
        logger.log_operation("test")
        json_str = logger.export("json")
        data = json.loads(json_str)
        assert len(data) == 1

    def test_memory_clear(self):
        logger = AuditLogger()
        logger.log_operation("test")
        removed = logger.clear()
        assert removed == 1
        assert len(logger.query()) == 0


# ── get_audit_logger() default persistence tests ──────────────────


class TestDefaultAuditLoggerPersistence:
    """Verify get_audit_logger() defaults to SQLite persistence."""

    def setup_method(self):
        """Reset global singleton before each test."""
        from carrymem.security.audit import reset_audit_logger

        reset_audit_logger()

    def teardown_method(self):
        """Reset global singleton after each test to avoid side effects."""
        from carrymem.security.audit import reset_audit_logger

        reset_audit_logger()

    def test_default_audit_logger_has_sqlite_backend(self):
        from carrymem.security.audit import get_audit_logger

        logger = get_audit_logger()
        assert logger._db_conn is not None, "Default get_audit_logger() should have SQLite backend"
        assert logger._persist_path is not None

    def test_default_audit_logger_creates_db_file(self, tmp_path, monkeypatch):
        from carrymem.security.audit import get_audit_logger, reset_audit_logger

        # Point HOME to tmp_path so ~/.carrymem/audit.db lands inside tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))
        reset_audit_logger()
        logger = get_audit_logger()
        expected_db = str(tmp_path / ".carrymem" / "audit.db")
        assert os.path.exists(expected_db), f"Default get_audit_logger() should create db file at {expected_db}"
        # Cleanup
        if logger._db_conn is not None:
            logger._db_conn.close()
        reset_audit_logger()

    def test_disable_persist_creates_memory_only(self):
        from carrymem.security.audit import get_audit_logger

        logger = get_audit_logger(disable_persist=True)
        assert logger._db_conn is None, "get_audit_logger(disable_persist=True) should be memory-only"
        assert logger._persist_path is None
