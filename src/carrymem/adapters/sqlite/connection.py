"""Connection management for SQLiteAdapter."""

import os
import sqlite3
import threading
from typing import Dict

from ...exceptions import DBConnectionError

# Global write locks per database file
_db_write_locks: Dict[str, threading.Lock] = {}
_db_write_locks_guard = threading.Lock()

try:
    import pysqlite3 as _pysqlite3
    PYSQLITE3_AVAILABLE = True
except ImportError:
    PYSQLITE3_AVAILABLE = False

try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False


class ConnectionManager:
    """Manages SQLite connections with thread-local storage and write locking."""

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
        self._enable_vector = enable_vector

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def lock(self):
        return self._lock

    @property
    def file_lock(self):
        return self._file_lock

    def set_enable_vector(self, enable: bool):
        self._enable_vector = enable

    def get_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise DBConnectionError("Adapter has been closed")

        is_memory = self._db_path == ":memory:"

        if is_memory:
            if not hasattr(self, '_memory_conn') or self._memory_conn is None:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys=ON")
                self._memory_conn = conn
                with self._conn_lock:
                    self._all_connections[id(conn)] = conn
            return self._memory_conn

        if not hasattr(self._local, 'conn') or self._local.conn is None:
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
                    conn.execute("PRAGMA busy_timeout=10000")
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA foreign_keys=ON")
                    if use_pysqlite3 and SQLITE_VEC_AVAILABLE:
                        try:
                            conn.enable_load_extension(True)
                            sqlite_vec.load(conn)
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).debug(f"sqlite_vec extension loading failed: {e}")
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

        return self._local.conn

    def close(self):
        self._closed = True
        logger = __import__('logging').getLogger(__name__)
        with self._conn_lock:
            for conn_id, conn in self._all_connections.items():
                try:
                    conn.close()
                except Exception as e:
                    logger.debug(f"Failed to close connection {conn_id}: {e}")
            self._all_connections.clear()
        if hasattr(self._local, 'conn'):
            self._local.conn = None

    def close_memory_conn_for_vector_switch(self):
        """Close existing connection before switching to pysqlite3 for vector support."""
        logger = __import__('logging').getLogger(__name__)
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as e:
                logger.debug(f"Failed to close existing connection for vector switch: {e}")
            with self._conn_lock:
                self._all_connections.pop(id(self._local.conn), None)
            self._local.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
