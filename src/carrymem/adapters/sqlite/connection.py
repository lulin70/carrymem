"""Connection management for SQLiteAdapter."""

import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Dict, Optional

from ...exceptions import DBConnectionError

logger = logging.getLogger(__name__)

# Global write locks per database file
_db_write_locks: Dict[str, threading.Lock] = {}
_db_write_locks_guard = threading.Lock()

# Slow query threshold (ms), 0 = disabled. Configurable via CARRYMEM_SLOW_QUERY_MS env var
_SLOW_QUERY_THRESHOLD_MS = int(os.environ.get("CARRYMEM_SLOW_QUERY_MS", "100"))

try:
    import pysqlite3 as _pysqlite3  # type: ignore[import-not-found]

    PYSQLITE3_AVAILABLE = True
except ImportError:
    PYSQLITE3_AVAILABLE = False

try:
    import sqlite_vec  # type: ignore[import-not-found]

    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False


class ConnectionManager:
    """Manages SQLite connections with thread-local storage and write locking.

    Features:
    - Thread-local connection reuse (connections are not shared across threads)
    - WAL mode for better concurrent read performance
    - Query execution time monitoring with slow query detection
    - Configurable PRAGMAs for performance tuning
    """

    def __init__(self, db_path: str, namespace: str, enable_vector: bool = False):
        self._namespace = namespace
        self._db_path = db_path
        self._lock = threading.Lock()

        resolved = str(os.path.realpath(self._db_path))
        with _db_write_locks_guard:
            if resolved not in _db_write_locks:
                _db_write_locks[resolved] = threading.Lock()
            self._file_lock = _db_write_locks[resolved]

        self._local = threading.local()
        self._closed = False
        self._all_connections: Dict[int, sqlite3.Connection] = {}
        self._conn_lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._enable_vector = enable_vector
        self._memory_conn: Optional[sqlite3.Connection] = None

    @property
    def db_path(self) -> str:
        """Path to the SQLite database file."""
        return self._db_path

    @property
    def namespace(self) -> str:
        """Active namespace for this connection manager."""
        return self._namespace

    @property
    def lock(self):
        """In-memory threading lock guarding connection state."""
        return self._lock

    @property
    def file_lock(self):
        """Cross-process file lock guarding the database file."""
        return self._file_lock

    def set_enable_vector(self, enable: bool):
        """Enable or disable vector storage."""
        self._enable_vector = enable

    def get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local connection to the database.

        Connections are reused within the same thread. New connections are created
        for different threads to ensure thread safety (sqlite3 connections should
        not be shared across threads).

        Returns:
            sqlite3.Connection: A thread-local database connection

        Raises:
            DBConnectionError: If the adapter has been closed or connection fails
        """
        if self._closed:
            raise DBConnectionError("Adapter has been closed")

        is_memory = self._db_path == ":memory:"

        if is_memory:
            if not hasattr(self, "_memory_conn") or self._memory_conn is None:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                self._apply_pragmas(conn)
                self._memory_conn = conn
                with self._conn_lock:
                    self._all_connections[id(conn)] = conn
            return self._memory_conn

        if not hasattr(self._local, "conn") or self._local.conn is None:
            with self._init_lock:
                if hasattr(self._local, "conn") and self._local.conn is not None:
                    return self._local.conn  # type: ignore[no-any-return]
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        use_pysqlite3 = self._enable_vector and PYSQLITE3_AVAILABLE
                        if use_pysqlite3:
                            conn = _pysqlite3.connect(self._db_path, timeout=30.0)
                            conn.row_factory = _pysqlite3.Row
                        else:
                            conn = sqlite3.connect(self._db_path, timeout=30.0)
                            conn.row_factory = sqlite3.Row
                        self._apply_pragmas(conn)
                        if use_pysqlite3 and SQLITE_VEC_AVAILABLE:
                            try:
                                conn.enable_load_extension(True)
                                sqlite_vec.load(conn)
                            except (OSError, AttributeError, ImportError, RuntimeError) as e:
                                logger.debug("sqlite_vec extension loading failed: %s", e)
                        self._prime_fts5_vtable(conn)
                        self._local.conn = conn
                        with self._conn_lock:
                            self._all_connections[id(conn)] = conn
                        break
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                            import time as _time

                            _time.sleep(0.5 * (attempt + 1))
                            continue
                        raise DBConnectionError(f"Failed to connect to database: {e}") from e
                    except sqlite3.Error as e:
                        raise DBConnectionError(f"Failed to connect to database: {e}") from e

        return self._local.conn  # type: ignore[no-any-return]

    def _prime_fts5_vtable(self, conn: sqlite3.Connection) -> None:
        """Trigger FTS5 vtable xConnect on a new connection.

        When multiple threads create new SQLite connections concurrently,
        the FTS5 vtable constructor can race, producing intermittent
        "vtable constructor failed: memories_fts" errors when an INSERT
        trigger first touches the vtable. Running a trivial SELECT against
        memories_fts forces xConnect to complete on this connection before
        any trigger fires. Held under _init_lock so only one thread
        constructs the vtable at a time.

        Safe to call before init_schema() runs (returns silently when the
        vtable does not yet exist).
        """
        last_err: Optional[sqlite3.OperationalError] = None
        for attempt in range(5):
            try:
                conn.execute("SELECT 1 FROM memories_fts LIMIT 1").fetchone()
                return
            except sqlite3.OperationalError as e:
                last_err = e
                msg_lower = str(e).lower()
                err_code = getattr(e, "sqlite_errorcode", None)
                err_name = getattr(e, "sqlite_errorname", None)
                logger.warning(
                    "FTS5 prime attempt %d failed: %s (code=%s, name=%s)",
                    attempt + 1,
                    e,
                    err_code,
                    err_name,
                )
                if "no such table" in msg_lower:
                    return
                import time as _time

                _time.sleep(0.05 * (attempt + 1))
        if last_err is not None:
            logger.warning("FTS5 vtable priming failed after retries: %s", last_err)

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Apply performance and safety PRAGMAs to a new connection.

        Configures:
        - WAL journal mode for better concurrent read performance
        - NORMAL synchronous level (balance between safety and performance)
        - 20MB page cache for better query performance on large datasets
        - Foreign key enforcement
        - Busy timeout for lock contention handling
        """
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-20000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")

    def release_connection(self) -> None:
        """Mark the current thread's connection as releasable.

        The connection is not actually closed; it remains in the thread-local
        storage for reuse by subsequent get_connection() calls in the same thread.
        This method exists for API symmetry and future pool management extensions.
        """
        pass  # Thread-local connections are inherently reusable

    def close_all_connections(self) -> None:
        """Close all tracked connections across all threads.

        This method is intended for cleanup scenarios (e.g., shutdown,
        testing teardown). It closes all connections that were created through
        this ConnectionManager instance.
        """
        self.close()

    @contextmanager
    def timed_query(self, sql: Optional[str] = None):
        """Context manager for measuring and logging query execution time.

        Usage:
            with mgr.timed_query("SELECT ..."):
                cursor = conn.execute(...)
                results = cursor.fetchall()

        Args:
            sql: Optional SQL string for logging purposes

        Yields:
            None
        """
        if _SLOW_QUERY_THRESHOLD_MS <= 0:
            yield
            return

        start = time.perf_counter()
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000

        sql_display = sql[:80] + "..." if sql and len(sql) > 80 else sql
        logger.debug("Query executed in %.2fms | %s", elapsed_ms, sql_display)

        if elapsed_ms > _SLOW_QUERY_THRESHOLD_MS:
            logger.warning(
                "Slow query detected (%.2fms > %dms): " "%s", elapsed_ms, _SLOW_QUERY_THRESHOLD_MS, sql_display
            )

    def close(self):
        """Close all connections and mark this manager as closed."""
        self._closed = True
        with self._conn_lock:
            for conn_id, conn in self._all_connections.items():
                try:
                    conn.close()
                except Exception as e:
                    # Catch all exceptions during cleanup, including pysqlite3
                    # thread-safety errors (pysqlite3.dbapi2.ProgrammingError is
                    # a different class than sqlite3.ProgrammingError).
                    logger.debug("Failed to close connection %s: %s", conn_id, e)
            self._all_connections.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None
        if hasattr(self, "_memory_conn"):
            self._memory_conn = None

    def close_memory_conn_for_vector_switch(self):
        """Close existing connection before switching to pysqlite3 for vector support."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except (sqlite3.ProgrammingError, sqlite3.InterfaceError) as e:
                logger.debug("Failed to close existing connection for vector switch: %s", e)
            with self._conn_lock:
                self._all_connections.pop(id(self._local.conn), None)
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
