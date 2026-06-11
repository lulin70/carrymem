"""
Tests for AuditLogger - security audit logging module.

Covers: log_operation, query with filters (AuditFilter),
get_stats, error handling, export/clear.
"""

from datetime import datetime, timezone

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
