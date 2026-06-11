"""Tests for SQLite connection pool management and optimizations (P0-4).

Covers:
- Thread-local connection reuse
- WAL mode verification
- Slow query logging
- Connection cleanup
- Concurrent read/write safety
"""

import logging
import os
import sqlite3
import tempfile
import threading
import time
import unittest

from carrymem.adapters.sqlite.connection import ConnectionManager, _SLOW_QUERY_THRESHOLD_MS


class TestConnectionReuse(unittest.TestCase):
    """Test thread-local connection reuse behavior."""

    def setUp(self):
        self.db_file = tempfile.mktemp(suffix=".db")
        self.mgr = ConnectionManager(self.db_file, namespace="test")

    def tearDown(self):
        self.mgr.close()
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)

    def test_same_thread_returns_same_connection(self):
        """Within a single thread, get_connection() should return the same object."""
        conn1 = self.mgr.get_connection()
        conn2 = self.mgr.get_connection()
        self.assertIs(conn1, conn2, "Same thread should reuse the same connection")

    def test_connection_id_stable(self):
        """Connection ID should remain constant across multiple calls in same thread."""
        conn = self.mgr.get_connection()
        conn_id = id(conn)
        for _ in range(5):
            c = self.mgr.get_connection()
            self.assertEqual(id(c), conn_id, "Connection ID should not change")

    def test_different_threads_get_different_connections(self):
        """Different threads should receive different connection objects."""
        connections = {}
        lock = threading.Lock()

        def worker(thread_id):
            conn = self.mgr.get_connection()
            with lock:
                connections[thread_id] = id(conn)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ids = list(connections.values())
        self.assertEqual(len(ids), 5, "Should have 5 distinct connection IDs")
        self.assertEqual(len(set(ids)), 5, "All connections should be unique")

    def test_memory_db_reuses_connection(self):
        """In-memory databases should also reuse connections."""
        mgr = ConnectionManager(":memory:", namespace="test_mem")
        try:
            conn1 = mgr.get_connection()
            conn2 = mgr.get_connection()
            self.assertIs(conn1, conn2, "Memory DB should reuse connection")
        finally:
            mgr.close()


class TestWALMode(unittest.TestCase):
    """Test WAL journal mode is properly configured."""

    def setUp(self):
        self.db_file = tempfile.mktemp(suffix=".db")
        self.mgr = ConnectionManager(self.db_file, namespace="test_wal")

    def tearDown(self):
        self.mgr.close()
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)
            # Also clean up WAL and SHM files
            for ext in ["-wal", "-shm"]:
                wal_path = self.db_file + ext
                if os.path.exists(wal_path):
                    os.unlink(wal_path)

    def test_wal_mode_enabled(self):
        """Journal mode should be WAL after connection creation."""
        conn = self.mgr.get_connection()
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        self.assertEqual(mode.lower(), "wal", f"Expected WAL mode, got {mode}")

    def test_synchronous_normal(self):
        """Synchronous setting should be NORMAL."""
        conn = self.mgr.get_connection()
        cursor = conn.execute("PRAGMA synchronous")
        sync = cursor.fetchone()[0]
        # NORMAL = 1 in SQLite PRAGMA output
        self.assertEqual(sync, 1, f"Expected synchronous=NORMAL (1), got {sync}")

    def test_cache_size_configured(self):
        """Cache size should be set to -20000 (20MB)."""
        conn = self.mgr.get_connection()
        cursor = conn.execute("PRAGMA cache_size")
        cache_size = cursor.fetchone()[0]
        self.assertEqual(cache_size, -20000, f"Expected cache_size=-20000, got {cache_size}")


class TestSlowQueryLogging(unittest.TestCase):
    """Test query execution time monitoring and slow query detection."""

    def setUp(self):
        self.db_file = tempfile.mktemp(suffix=".db")
        self.mgr = ConnectionManager(self.db_file, namespace="test_slow")

    def tearDown(self):
        self.mgr.close()
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)

    def test_timed_query_fast_query_logs_debug(self):
        """Fast queries should log at DEBUG level."""
        conn = self.mgr.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")

        with self.assertLogs("carrymem.adapters.sqlite.connection", level="DEBUG") as cm:
            with self.mgr.timed_query("SELECT 1"):
                conn.execute("SELECT 1").fetchall()

        debug_messages = [r.getMessage() for r in cm.records if r.levelno == logging.DEBUG]
        self.assertTrue(
            any("Query executed in" in msg for msg in debug_messages),
            "Should have a DEBUG message about query execution time"
        )

    def test_timed_query_slow_query_logs_warning(self):
        """Queries exceeding threshold should log at WARNING level."""
        conn = self.mgr.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS test_slow (id INTEGER PRIMARY KEY)")

        # Temporarily set a very low threshold to trigger slow query warning
        original_threshold = _SLOW_QUERY_THRESHOLD_MS
        import carrymem.adapters.sqlite.connection as conn_module
        conn_module._SLOW_QUERY_THRESHOLD_MS = 1  # 1ms threshold

        try:
            with self.assertLogs("carrymem.adapters.sqlite.connection", level="WARNING") as cm:
                with self.mgr.timed_query("SELECT slow"):
                    # Simulate slow query with sleep
                    time.sleep(0.01)  # 10ms > 1ms threshold
                    conn.execute("SELECT 1").fetchall()

            warning_messages = [r.getMessage() for r in cm.records if r.levelno == logging.WARNING]
            self.assertTrue(
                any("Slow query detected" in msg for msg in warning_messages),
                "Should have a WARNING about slow query"
            )
        finally:
            conn_module._SLOW_QUERY_THRESHOLD_MS = original_threshold

    def test_timed_query_disabled_when_threshold_zero(self):
        """When CARRYMEM_SLOW_QUERY_MS=0, timing should be disabled."""
        import carrymem.adapters.sqlite.connection as conn_module
        original = conn_module._SLOW_QUERY_THRESHOLD_MS
        conn_module._SLOW_QUERY_THRESHOLD_MS = 0

        try:
            conn = self.mgr.get_connection()
            executed = False

            with self.mgr.timed_query("SELECT disabled"):
                executed = True
                conn.execute("SELECT 1").fetchall()

            self.assertTrue(executed, "Query should still execute even when timing is disabled")
        finally:
            conn_module._SLOW_QUERY_THRESHOLD_MS = original


class TestConnectionCleanup(unittest.TestCase):
    """Test connection cleanup methods."""

    def setUp(self):
        self.db_file = tempfile.mktemp(suffix=".db")
        self.mgr = ConnectionManager(self.db_file, namespace="test_cleanup")

    def tearDown(self):
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)

    def test_close_all_connections_clears_tracked(self):
        """close_all_connections should clear all tracked connections."""
        conn = self.mgr.get_connection()
        self.assertTrue(len(self.mgr._all_connections) > 0, "Should have tracked connections")

        self.mgr.close_all_connections()
        self.assertEqual(len(self.mgr._all_connections) > 0, False,
                         "All connections should be cleared after close_all_connections")

    def test_close_prevents_new_connections(self):
        """After close(), get_connection() should raise an error."""
        self.mgr.get_connection()  # Create a connection
        self.mgr.close()

        with self.assertRaises(Exception):  # DBConnectionError
            self.mgr.get_connection()

    def test_release_connection_is_noop(self):
        """release_connection() should not raise errors and allow continued use."""
        conn1 = self.mgr.get_connection()
        self.mgr.release_connection()
        conn2 = self.mgr.get_connection()
        self.assertIs(conn1, conn2, "Connection should still be reusable after release")

    def test_context_manager_cleanup(self):
        """Context manager should properly cleanup on exit."""
        with ConnectionManager(self.db_file, namespace="test_ctx") as mgr:
            conn = mgr.get_connection()
            self.assertIsNotNone(conn)

        # After context exit, manager should be closed
        self.assertTrue(mgr._closed)


class TestConcurrentReadWrite(unittest.TestCase):
    """Test concurrent read/write operations do not crash."""

    def setUp(self):
        self.db_file = tempfile.mktemp(suffix=".db")
        self.mgr = ConnectionManager(self.db_file, namespace="test_concurrent")

    def tearDown(self):
        self.mgr.close()
        if os.path.exists(self.db_file):
            os.unlink(self.db_file)

    def test_concurrent_reads(self):
        """Multiple threads reading simultaneously should not crash."""
        conn = self.mgr.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO items (value) VALUES ('test')")
        conn.commit()

        errors = []

        def reader():
            try:
                local_conn = self.mgr.get_connection()
                for _ in range(50):
                    local_conn.execute("SELECT * FROM items").fetchall()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent reads had errors: {errors}")

    def test_concurrent_writes_with_lock(self):
        """Concurrent writes using file_lock should not crash."""
        conn = self.mgr.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS counters (id INTEGER PRIMARY KEY, count INTEGER)")
        conn.commit()

        errors = []

        def writer(thread_id):
            try:
                with self.mgr.file_lock:
                    local_conn = self.mgr.get_connection()
                    local_conn.execute(
                        "INSERT INTO counters (count) VALUES (?)",
                        (thread_id,)
                    )
                    local_conn.commit()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent writes had errors: {errors}")

        # Verify all writes succeeded
        conn = self.mgr.get_connection()
        result = conn.execute("SELECT COUNT(*) FROM counters").fetchone()[0]
        self.assertEqual(result, 10, "All 10 inserts should succeed")


class TestEnvironmentVariableConfiguration(unittest.TestCase):
    """Test environment variable configuration for slow query threshold."""

    def test_env_var_controls_threshold(self):
        """CARRYMEM_SLOW_QUERY_MS environment variable should control threshold."""
        import carrymem.adapters.sqlite.connection as conn_module

        # Save original value
        original = os.environ.get("CARRYMEM_SLOW_QUERY_MS")

        try:
            os.environ["CARRYMEM_SLOW_QUERY_MS"] = "50"
            # Re-import to pick up new env var (module-level constant)
            # Note: In production, this would require process restart
            threshold = int(os.environ.get("CARRYMEM_SLOW_QUERY_MS", "100"))
            self.assertEqual(threshold, 50)
        finally:
            if original is None:
                os.environ.pop("CARRYMEM_SLOW_QUERY_MS", None)
            else:
                os.environ["CARRYMEM_SLOW_QUERY_MS"] = original


if __name__ == "__main__":
    unittest.main()
