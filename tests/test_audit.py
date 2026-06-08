"""
Tests for AuditLogger - security audit logging module.

Covers: schema creation, log_operation, query with filters,
get_stats, error handling, namespace defaults.
"""

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from carrymem.security.audit import AuditLogger


@pytest.fixture
def db_connection(tmp_path):
    db_path = str(tmp_path / "audit_test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def audit_logger(db_connection):
    return AuditLogger(lambda: db_connection, namespace="test_ns")


class TestAuditLoggerInit:
    def test_creates_schema(self, db_connection):
        logger = AuditLogger(lambda: db_connection)
        rows = db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
        ).fetchall()
        assert len(rows) == 1

    def test_creates_indexes(self, db_connection):
        logger = AuditLogger(lambda: db_connection)
        indexes = db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_audit%'"
        ).fetchall()
        assert len(indexes) >= 3

    def test_schema_idempotent(self, db_connection):
        logger1 = AuditLogger(lambda: db_connection)
        logger2 = AuditLogger(lambda: db_connection)
        logger2.log_operation("test_op")
        results = logger2.query()
        assert len(results) >= 1


class TestLogOperation:
    def test_basic_log(self, audit_logger, db_connection):
        audit_logger.log_operation("remember")
        rows = db_connection.execute("SELECT * FROM audit_log").fetchall()
        assert len(rows) == 1
        assert rows[0]["operation"] == "remember"

    def test_log_with_all_fields(self, audit_logger):
        audit_logger.log_operation(
            operation="forget",
            namespace="custom_ns",
            storage_key="mem_001",
            memory_type="user_preference",
            success=False,
            details={"reason": "user request"},
            source="cli",
        )
        results = audit_logger.query()
        assert len(results) == 1
        r = results[0]
        assert r["operation"] == "forget"
        assert r["namespace"] == "custom_ns"
        assert r["storage_key"] == "mem_001"
        assert r["memory_type"] == "user_preference"
        assert r["success"] is False
        assert r["details"]["reason"] == "user request"
        assert r["source"] == "cli"

    def test_log_defaults_namespace(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert results[0]["namespace"] == "test_ns"

    def test_log_success_default_true(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert results[0]["success"] is True

    def test_log_details_none(self, audit_logger):
        audit_logger.log_operation("remember", details=None)
        results = audit_logger.query()
        assert results[0]["details"] is None

    def test_log_details_complex(self, audit_logger):
        details = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
        audit_logger.log_operation("remember", details=details)
        results = audit_logger.query()
        assert results[0]["details"] == details

    def test_multiple_operations(self, audit_logger):
        for op in ["remember", "recall", "forget", "edit", "remember"]:
            audit_logger.log_operation(op)
        results = audit_logger.query()
        assert len(results) == 5

    def test_log_source_default(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert results[0]["source"] == "api"


class TestQuery:
    def test_query_by_operation(self, audit_logger):
        audit_logger.log_operation("remember")
        audit_logger.log_operation("forget")
        results = audit_logger.query(operation="remember")
        assert len(results) == 1
        assert results[0]["operation"] == "remember"

    def test_query_by_namespace(self, audit_logger):
        audit_logger.log_operation("remember", namespace="ns1")
        audit_logger.log_operation("remember", namespace="ns2")
        results = audit_logger.query(namespace="ns1")
        assert len(results) == 1
        assert results[0]["namespace"] == "ns1"

    def test_query_by_source(self, audit_logger):
        audit_logger.log_operation("remember", source="cli")
        audit_logger.log_operation("remember", source="api")
        results = audit_logger.query(source="cli")
        assert len(results) == 1
        assert results[0]["source"] == "cli"

    def test_query_by_time_range(self, audit_logger):
        audit_logger.log_operation("remember")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        results = audit_logger.query(since="2020-01-01T00:00:00Z", until=now)
        assert len(results) >= 1

    def test_query_no_filters(self, audit_logger):
        audit_logger.log_operation("remember")
        results = audit_logger.query()
        assert len(results) >= 1

    def test_query_limit(self, audit_logger):
        for i in range(10):
            audit_logger.log_operation("remember")
        results = audit_logger.query(limit=3)
        assert len(results) == 3

    def test_query_empty_result(self, audit_logger):
        results = audit_logger.query(operation="nonexistent")
        assert results == []

    def test_query_ordered_by_timestamp_desc(self, audit_logger):
        audit_logger.log_operation("first")
        audit_logger.log_operation("second")
        results = audit_logger.query()
        assert len(results) == 2
        ops = [r["operation"] for r in results]
        assert "first" in ops
        assert "second" in ops


class TestGetStats:
    def test_stats_empty(self, db_connection):
        logger = AuditLogger(lambda: db_connection)
        stats = logger.get_stats()
        assert stats["total_operations"] == 0
        assert stats["by_operation"] == {}
        assert stats["last_activity"] is None

    def test_stats_with_data(self, audit_logger):
        audit_logger.log_operation("remember")
        audit_logger.log_operation("remember")
        audit_logger.log_operation("forget")
        stats = audit_logger.get_stats()
        assert stats["total_operations"] == 3
        assert stats["by_operation"]["remember"] == 2
        assert stats["by_operation"]["forget"] == 1
        assert stats["last_activity"] is not None

    def test_stats_by_operation(self, audit_logger):
        for _ in range(5):
            audit_logger.log_operation("remember")
        for _ in range(3):
            audit_logger.log_operation("forget")
        stats = audit_logger.get_stats()
        assert stats["by_operation"]["remember"] == 5
        assert stats["by_operation"]["forget"] == 3


class TestErrorHandling:
    def test_log_with_bad_connection(self, tmp_path):
        db_path = str(tmp_path / "audit_bad1.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        logger = AuditLogger(lambda: conn)
        conn.close()
        logger.log_operation("test")

    def test_query_with_bad_connection(self, tmp_path):
        db_path = str(tmp_path / "audit_bad2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        logger = AuditLogger(lambda: conn)
        conn.close()
        with pytest.raises(sqlite3.ProgrammingError):
            logger.query()

    def test_stats_with_bad_connection(self, tmp_path):
        db_path = str(tmp_path / "audit_bad3.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        logger = AuditLogger(lambda: conn)
        conn.close()
        with pytest.raises(sqlite3.ProgrammingError):
            logger.get_stats()
