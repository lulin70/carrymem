"""CarryMem - Compatible import path.

Usage:
    from carrymem import CarryMem

This is equivalent to:
    from memory_classification_engine import CarryMem
"""

from memory_classification_engine import CarryMem, MemoryEntry
from memory_classification_engine import __version__

__all__ = [
    "CarryMem",
    "MemoryEntry",
    "__version__",
]
