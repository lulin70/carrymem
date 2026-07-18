"""SQLite configuration constants for PRAGMA tuning.

These numeric constants are used in ``PRAGMA`` statements to configure
SQLite connection behavior. Extracting them as named constants improves
readability and centralizes tuning knobs for easy adjustment.
"""

# Busy timeout in milliseconds for lock contention handling.
# Sets how long SQLite waits when encountering a lock before returning
# SQLITE_BUSY. Used in: PRAGMA busy_timeout=N
SQLITE_BUSY_TIMEOUT_MS = 10000

# Cache size in KiB for the in-memory page cache.
# Negative value tells SQLite to treat the number as KiB (not pages).
# 20000 KiB ≈ 20 MB, which improves query performance on large datasets.
# Used in: PRAGMA cache_size=-N
SQLITE_CACHE_SIZE_KIB = 20000
