"""SQLite configuration constants for PRAGMA tuning.

These numeric constants are used in ``PRAGMA`` statements to configure
SQLite connection behavior. Extracting them as named constants improves
readability and centralizes tuning knobs for easy adjustment.
"""

import os

# Busy timeout in milliseconds for lock contention handling.
# Sets how long SQLite waits when encountering a lock before returning
# SQLITE_BUSY. Used in: PRAGMA busy_timeout=N
# 10s, deliberately NOT higher: a single statement may legitimately block for
# the full timeout, and e2e concurrency tests join their worker threads with
# a 30s window — a 30s busy_timeout let one stalled statement outlive the
# join, and fixture teardown then closed the connection under the leaked
# thread (use-after-free segfault). Transient WAL read-side busy is absorbed
# by the operation-level retry in core/_memory_crud._retry_on_busy instead.
SQLITE_BUSY_TIMEOUT_MS = 10000

# WAL auto-checkpoint threshold in pages. The SQLite default (1000 pages,
# ~4MB) is crossed every few writes when FTS + vector-blob writes inflate the
# WAL, so a checkpoint+reset runs on nearly every commit under load. Readers
# that try to begin a read during a WAL reset hit transient SQLITE_BUSY (the
# wal-index shm lock path does not honor busy_timeout). Raising the threshold
# reduces checkpoint churn and the width of that window. Tunable via env so
# heavy-workload deployments can adjust without code changes.
SQLITE_WAL_AUTOCHECKPOINT_PAGES = int(os.environ.get("CARRYMEM_WAL_AUTOCHECKPOINT_PAGES", "4000"))

# Cache size in KiB for the in-memory page cache.
# Negative value tells SQLite to treat the number as KiB (not pages).
# 20000 KiB ≈ 20 MB, which improves query performance on large datasets.
# Used in: PRAGMA cache_size=-N
SQLITE_CACHE_SIZE_KIB = 20000

# Default connection timeout in seconds for sqlite3.connect(timeout=N).
# How long sqlite3 waits when acquiring a write lock before raising
# sqlite3.OperationalError. Distinct from SQLITE_BUSY_TIMEOUT_MS (PRAGMA-level)
# because sqlite3.connect(timeout=N) operates at the Python driver level.
SQLITE_DB_TIMEOUT_SECONDS = 30.0
