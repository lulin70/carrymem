"""Cross-process SQLite write-lock regression tests."""

import multiprocessing
import sqlite3
from pathlib import Path


def _write_rows(db_path: str, start: int, count: int) -> None:
    from carrymem.adapters.sqlite.connection import ConnectionManager

    manager = ConnectionManager(db_path, namespace="lock-test")
    try:
        conn = manager.get_connection()
        for index in range(start, start + count):
            with manager.file_lock:
                conn.execute("INSERT INTO lock_test (value) VALUES (?)", (index,))
                conn.commit()
    finally:
        manager.close()


def test_cross_process_writes_are_serialized(tmp_path: Path) -> None:
    db_path = str(tmp_path / "carrymem.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE lock_test (value INTEGER NOT NULL)")

    processes = [multiprocessing.Process(target=_write_rows, args=(db_path, start, 20)) for start in (0, 20, 40, 60)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)

    assert all(process.exitcode == 0 for process in processes)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lock_test").fetchone()[0] == 80
