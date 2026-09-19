"""Backward-compatible re-export: SQLiteAdapter is now in carrymem.adapters.sqlite."""

from typing import TYPE_CHECKING

# The two capability flags below only probe lightweight C extensions, so they
# stay eager. `SENTENCE_TRANSFORMERS_AVAILABLE` needs `sentence_transformers`
# (which loads torch, ~16s), so it is resolved lazily via PEP 562 delegation
# (P1#10).
from carrymem.adapters.sqlite import PYSQLITE3_AVAILABLE, SQLITE_VEC_AVAILABLE, SQLiteAdapter

_LAZY_FLAGS = ("SENTENCE_TRANSFORMERS_AVAILABLE",)

__all__ = [
    "SQLiteAdapter",
    "SQLITE_VEC_AVAILABLE",
    "PYSQLITE3_AVAILABLE",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]

if TYPE_CHECKING:  # pragma: no cover — static binding only; resolved lazily at runtime
    SENTENCE_TRANSFORMERS_AVAILABLE: bool


def __getattr__(name):
    """PEP 562: delegate lazy capability flags to carrymem.adapters.sqlite."""
    if name in _LAZY_FLAGS:
        from carrymem.adapters import sqlite

        return getattr(sqlite, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
