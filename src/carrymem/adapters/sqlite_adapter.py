"""Backward-compatible re-export: SQLiteAdapter is now in carrymem.adapters.sqlite."""

from carrymem.adapters.sqlite import SQLiteAdapter

# Re-export module-level constants for backward compatibility
try:
    from carrymem.adapters.sqlite import (
        PYSQLITE3_AVAILABLE,
        SENTENCE_TRANSFORMERS_AVAILABLE,
        SQLITE_VEC_AVAILABLE,
    )
except ImportError:
    SQLITE_VEC_AVAILABLE = False
    PYSQLITE3_AVAILABLE = False
    SENTENCE_TRANSFORMERS_AVAILABLE = False

__all__ = [
    "SQLiteAdapter",
    "SQLITE_VEC_AVAILABLE",
    "PYSQLITE3_AVAILABLE",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]
