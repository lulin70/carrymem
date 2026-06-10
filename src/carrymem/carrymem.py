"""CarryMem — Main entry point for the portable AI memory layer.

Usage:
    # Mode 1: Classify + Store (default SQLite)
    from carrymem import CarryMem
    cm = CarryMem()
    result = cm.classify_and_remember("I prefer dark mode")

    # Mode 2: Pure classification (no storage)
    cm = CarryMem(storage=None)
    result = cm.classify_message("I prefer dark mode")

    # Mode 3: Custom storage adapter
    from carrymem.adapters import SQLiteAdapter
    cm = CarryMem(storage=SQLiteAdapter("/path/to/custom.db"))

    # Mode 4: With knowledge base (Obsidian)
    from carrymem.adapters import ObsidianAdapter
    cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
    cm.index_knowledge()
    results = cm.recall_from_knowledge("Python design patterns")
"""

"""Backward-compatible re-export — delegates to carrymem.core.CarryMem."""

from carrymem.core import (
    CarryMem,
    KnowledgeNotConfiguredError,
    StorageNotConfiguredError,
    _validate_file_path,
)

__all__ = ["CarryMem", "StorageNotConfiguredError", "KnowledgeNotConfiguredError", "_validate_file_path"]
