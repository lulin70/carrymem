"""Tests for enhanced audit logging system (P2-5).

Covers:
- AuditEvent data class
- AuditLogger core operations (log, query, export, clear)
- AuditFilter functionality
- Thread safety
- Convenience helper functions
- Global singleton
- Edge cases
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from carrymem.security.audit import (
    AuditEvent,
    AuditFilter,
    AuditLogger,
    get_audit_logger,
    log_config,
    log_delete,
    log_denied,
    log_read,
    log_write,
    reset_audit_logger,
)

# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_global_logger():
    """Reset global audit logger before each test to ensure isolation."""
    reset_audit_logger()
    yield
    reset_audit_logger()


@pytest.fixture
def logger() -> AuditLogger:
    """Fresh AuditLogger instance for each test."""
    return AuditLogger()


@pytest.fixture
def sample_event() -> AuditEvent:
    """Sample audit event for testing."""
    return AuditEvent(
        user_id="test_user",
        action="WRITE",
        resource="memory",
        result="SUCCESS",
        details={"storage_key": "mem_001"},
    )


# ── Test: AuditEvent Data Class ────────────────────────────────────


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        event = AuditEvent()
        assert event.timestamp is not None
        assert event.user_id is None
        assert event.action == "READ"
        assert event.resource == ""
        assert event.result == "SUCCESS"
        assert event.details == {}
        assert event.ip_address is None

    def test_custom_values(self):
        """Test that custom values are stored correctly."""
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            timestamp=now,
            user_id="user123",
            action="DELETE",
            resource="memory",
            result="FAILURE",
            details={"error": "not found"},
            ip_address="192.168.1.1",
        )
        assert event.timestamp == now
        assert event.user_id == "user123"
        assert event.action == "DELETE"
        assert event.resource == "memory"
        assert event.result == "FAILURE"
        assert event.details == {"error": "not found"}
        assert event.ip_address == "192.168.1.1"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            timestamp=now,
            user_id="user1",
            action="WRITE",
            resource="test",
            result="SUCCESS",
            details={"key": "value"},
        )
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["timestamp"] == now.isoformat()
        assert d["user_id"] == "user1"
        assert d["action"] == "WRITE"
        assert d["resource"] == "test"
        assert d["result"] == "SUCCESS"
        assert d["details"] == {"key": "value"}
        assert d["ip_address"] is None


# ── Test: AuditLogger Core Operations ──────────────────────────────


class TestAuditLoggerLog:
    """Tests for AuditLogger.log() method."""

    def test_log_single_event(self, logger, sample_event):
        """Test logging a single event."""
        logger.log(sample_event)
        assert logger.event_count == 1

    def test_log_multiple_events(self, logger):
        """Test logging multiple events."""
        for i in range(5):
            logger.log(AuditEvent(action="WRITE", resource=f"resource_{i}"))
        assert logger.event_count == 5

    def test_log_auto_pruning(self):
        """Test that events are automatically pruned when exceeding max_events."""
        small_logger = AuditLogger(max_events=3)
        for i in range(5):
            small_logger.log(AuditEvent(action="WRITE", resource=f"res_{i}"))
        # Should only keep the last 3 events
        assert small_logger.event_count == 3
        # Oldest events should be pruned
        events = small_logger.query(AuditFilter(limit=10))
        resources = [e.resource for e in events]
        assert "res_0" not in resources
        assert "res_1" not in resources
        assert "res_4" in resources

    def test_log_preserves_order(self, logger):
        """Test that events are stored in chronological order."""
        event1 = AuditEvent(action="READ", resource="a")
        time.sleep(0.01)  # Ensure different timestamps
        event2 = AuditEvent(action="WRITE", resource="b")
        logger.log(event1)
        logger.log(event2)
        events = logger._events
        assert events[0].timestamp <= events[1].timestamp


# ── Test: Query Functionality ──────────────────────────────────────


class TestAuditLoggerQuery:
    """Tests for AuditLogger.query() with filters."""

    def setup_method(self):
        """Set up test data for query tests."""
        self.logger = AuditLogger()
        # Add various events
        self.logger.log(AuditEvent(user_id="alice", action="WRITE", resource="memory", result="SUCCESS"))
        self.logger.log(AuditEvent(user_id="bob", action="READ", resource="memory", result="SUCCESS"))
        self.logger.log(AuditEvent(user_id="alice", action="DELETE", resource="memory", result="FAILURE"))
        self.logger.log(AuditEvent(user_id="charlie", action="WRITE", resource="config", result="DENIED"))
        self.logger.log(AuditEvent(user_id="alice", action="CONFIG", resource="encryption", result="SUCCESS"))

    def test_query_all_with_default_limit(self):
        """Test querying all events respects default limit."""
        results = self.logger.query()
        assert len(results) <= 100

    def test_query_filter_by_action(self):
        """Test filtering by action type."""
        results = self.logger.query(AuditFilter(action="WRITE"))
        assert all(e.action == "WRITE" for e in results)
        assert len(results) == 2  # alice WRITE + charlie WRITE

    def test_query_filter_by_user_id(self):
        """Test filtering by user ID."""
        results = self.logger.query(AuditFilter(user_id="alice"))
        assert all(e.user_id == "alice" for e in results)
        assert len(results) == 3  # alice has 3 events

    def test_query_filter_by_resource(self):
        """Test filtering by resource."""
        results = self.logger.query(AuditFilter(resource="memory"))
        assert all(e.resource == "memory" for e in results)

    def test_query_filter_by_result(self):
        """Test filtering by result type."""
        results = self.logger.query(AuditFilter(result="DENIED"))
        assert len(results) == 1
        assert results[0].result == "DENIED"

    def test_query_filter_by_time_range(self):
        """Test filtering by time range."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        results = self.logger.query(AuditFilter(since=past, until=future))
        assert len(results) == 5  # All events should be within range

    def test_query_combined_filters(self):
        """Test combining multiple filters."""
        results = self.logger.query(
            AuditFilter(
                action="WRITE",
                user_id="alice",
            )
        )
        assert len(results) == 1
        assert results[0].user_id == "alice"
        assert results[0].action == "WRITE"

    def test_query_respects_limit(self):
        """Test that query respects the limit parameter."""
        results = self.logger.query(AuditFilter(limit=2))
        assert len(results) <= 2

    def test_query_returns_newest_first(self):
        """Test that query results are sorted newest first."""
        results = self.logger.query(AuditFilter(limit=5))
        if len(results) >= 2:
            assert results[0].timestamp >= results[1].timestamp

    def test_query_empty_results(self):
        """Test query returns empty list when no matches."""
        results = self.logger.query(AuditFilter(action="NONEXISTENT"))
        assert results == []


# ── Test: Export Functionality ─────────────────────────────────────


class TestAuditLoggerExport:
    """Tests for AuditLogger.export() method."""

    def test_export_json(self, logger, sample_event):
        """Test JSON export format."""
        logger.log(sample_event)
        json_str = logger.export("json")
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["action"] == "WRITE"
        assert data[0]["resource"] == "memory"

    def test_export_csv(self, logger, sample_event):
        """Test CSV export format."""
        logger.log(sample_event)
        csv_str = logger.export("csv")
        lines = csv_str.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row
        assert "timestamp" in lines[0]  # Header contains field names
        assert "WRITE" in lines[1]  # Data contains action

    def test_export_empty_logger(self, logger):
        """Test exporting empty logger."""
        json_str = logger.export("json")
        assert json.loads(json_str) == []
        csv_str = logger.export("csv")
        assert csv_str == ""

    def test_export_invalid_format_raises_error(self, logger):
        """Test that invalid export format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported export format"):
            logger.export("xml")

    def test_export_multiple_events(self, logger):
        """Test exporting multiple events."""
        for i in range(3):
            logger.log(AuditEvent(action="WRITE", resource=f"res_{i}"))
        json_str = logger.export("json")
        data = json.loads(json_str)
        assert len(data) == 3


# ── Test: Clear Functionality ──────────────────────────────────────


class TestAuditLoggerClear:
    """Tests for AuditLogger.clear() method."""

    def test_clear_all(self, logger):
        """Test clearing all events."""
        for i in range(5):
            logger.log(AuditEvent())
        assert logger.event_count == 5
        removed = logger.clear()
        assert removed == 5
        assert logger.event_count == 0

    def test_clear_older_than(self, logger):
        """Test clearing events older than specified duration."""
        # Add an old event by manipulating timestamp
        old_event = AuditEvent(
            action="WRITE",
            resource="old",
            timestamp=datetime.now(timezone.utc) - timedelta(days=2),
        )
        new_event = AuditEvent(action="WRITE", resource="new")
        logger.log(old_event)
        logger.log(new_event)
        assert logger.event_count == 2

        # Clear events older than 1 day
        removed = logger.clear(older_than=timedelta(days=1))
        assert removed == 1
        assert logger.event_count == 1
        remaining = logger.query(AuditFilter(limit=10))
        assert remaining[0].resource == "new"

    def test_clear_empty_logger(self, logger):
        """Test clearing empty logger returns 0."""
        removed = logger.clear()
        assert removed == 0


# ── Test: Statistics ───────────────────────────────────────────────


class TestAuditLoggerStats:
    """Tests for AuditLogger.get_stats() method."""

    def test_stats_empty(self, logger):
        """Test stats on empty logger."""
        stats = logger.get_stats()
        assert stats["total_events"] == 0
        assert stats["by_action"] == {}
        assert stats["by_result"] == {}
        assert stats["last_event"] is None

    def test_stats_with_events(self, logger):
        """Test stats with events logged."""
        logger.log(AuditEvent(action="WRITE", result="SUCCESS"))
        logger.log(AuditEvent(action="READ", result="SUCCESS"))
        logger.log(AuditEvent(action="DELETE", result="FAILURE"))
        stats = logger.get_stats()
        assert stats["total_events"] == 3
        assert stats["by_action"]["WRITE"] == 1
        assert stats["by_action"]["READ"] == 1
        assert stats["by_action"]["DELETE"] == 1
        assert stats["by_result"]["SUCCESS"] == 2
        assert stats["by_result"]["FAILURE"] == 1
        assert stats["last_event"] is not None

    def test_stats_utilization(self, logger):
        """Test utilization percentage calculation."""
        small_logger = AuditLogger(max_events=100)
        for i in range(25):
            small_logger.log(AuditEvent())
        stats = small_logger.get_stats()
        assert stats["max_capacity"] == 100
        assert stats["utilization_pct"] == 25.0


# ── Test: Thread Safety ────────────────────────────────────────────


class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_logging(self):
        """Test that concurrent logging doesn't corrupt state."""
        logger = AuditLogger(max_events=10000)
        num_threads = 10
        events_per_thread = 50

        def worker(thread_id):
            for i in range(events_per_thread):
                logger.log(
                    AuditEvent(
                        user_id=f"user_{thread_id}",
                        action="WRITE",
                        resource=f"resource_{thread_id}_{i}",
                    )
                )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_total = num_threads * events_per_thread
        assert logger.event_count == expected_total

    def test_concurrent_log_and_query(self):
        """Test concurrent logging and querying."""
        logger = AuditLogger()
        stop_flag = threading.Event()

        def writer():
            i = 0
            while not stop_flag.is_set():
                logger.log(AuditEvent(action="WRITE", resource=f"res_{i}"))
                i += 1

        def reader():
            while not stop_flag.is_set():
                _ = logger.query(AuditFilter(limit=10))

        t_writer = threading.Thread(target=writer)
        t_reader = threading.Thread(target=reader)
        t_writer.start()
        t_reader.start()

        time.sleep(0.1)  # Run briefly
        stop_flag.set()
        t_writer.join(timeout=1)
        t_reader.join(timeout=1)

        # If we get here without exceptions, thread safety is working
        assert logger.event_count > 0


# ── Test: Convenience Helpers ──────────────────────────────────────


class TestConvenienceHelpers:
    """Tests for convenience helper functions."""

    def test_log_write(self):
        """Test log_write helper function."""
        log_write(resource="memory", user_id="user1", details={"key": "val"})
        logger = get_audit_logger()
        events = logger.query(AuditFilter(limit=1))
        assert len(events) == 1
        assert events[0].action == "WRITE"
        assert events[0].resource == "memory"
        assert events[0].user_id == "user1"

    def test_log_read(self):
        """Test log_read helper function."""
        log_read(resource="memory")
        logger = get_audit_logger()
        events = logger.query(AuditFilter(limit=1))
        assert events[0].action == "READ"

    def test_log_delete(self):
        """Test log_delete helper function."""
        log_delete(resource="memory", user_id="admin")
        logger = get_audit_logger()
        events = logger.query(AuditFilter(limit=1))
        assert events[0].action == "DELETE"

    def test_log_denied(self):
        """Test log_denied helper function."""
        log_denied(resource="secret", user_id="intruder", action="WRITE")
        logger = get_audit_logger()
        events = logger.query(AuditFilter(limit=1))
        assert events[0].result == "DENIED"
        assert events[0].user_id == "intruder"

    def test_log_config(self):
        """Test log_config helper function."""
        log_config(resource="encryption_key", details={"backend": "fernet"})
        logger = get_audit_logger()
        events = logger.query(AuditFilter(limit=1))
        assert events[0].action == "CONFIG"
        assert events[0].resource == "encryption_key"


# ── Test: Global Singleton ─────────────────────────────────────────


class TestGlobalSingleton:
    """Tests for the global AuditLogger singleton."""

    def test_get_audit_logger_returns_instance(self):
        """Test that get_audit_logger returns an AuditLogger instance."""
        logger = get_audit_logger()
        assert isinstance(logger, AuditLogger)

    def test_get_audit_logger_same_instance(self):
        """Test that multiple calls return same singleton."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2

    def test_reset_audit_logger(self):
        """Test that reset creates new instance."""
        logger1 = get_audit_logger()
        reset_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is not logger2


# ── Test: Edge Cases ───────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_large_details_dict(self, logger):
        """Test logging event with large details dictionary."""
        large_details = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}
        event = AuditEvent(details=large_details)
        logger.log(event)
        assert logger.event_count == 1
        exported = logger.export("json")
        data = json.loads(exported)
        assert len(data[0]["details"]) == 100

    def test_unicode_content(self, logger):
        """Test handling of unicode characters in event fields."""
        event = AuditEvent(
            user_id="用户",
            resource="记忆",
            details={"content": "你好世界 🌍"},
        )
        logger.log(event)
        exported = logger.export("json")
        data = json.loads(exported)
        assert data[0]["user_id"] == "用户"
        assert "🌍" in data[0]["details"]["content"]

    def test_none_user_id(self, logger):
        """Test that None user_id is handled correctly (system/anonymous)."""
        event = AuditEvent(user_id=None, action="CONFIG", resource="system")
        logger.log(event)
        events = logger.query(AuditFilter(limit=1))
        assert events[0].user_id is None
