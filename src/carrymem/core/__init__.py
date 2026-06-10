"""CarryMem AI Memory System — Facade with Mixin composition.

This module composes CarryMem from 7 focused Mixin classes plus a LifecycleMixin
that holds __init__ / close / properties.  Every public API is identical to the
original monolithic class — `cm.method()` calls work without changes.
"""

from carrymem.core._backup import BackupMixin
from carrymem.core._classification import ClassificationMixin
from carrymem.core._lifecycle import (
    KnowledgeNotConfiguredError,
    LifecycleMixin,
    StorageNotConfiguredError,
    _validate_file_path,
)
from carrymem.core._maintenance import MaintenanceMixin
from carrymem.core._memory_crud import MemoryCRUDMixin
from carrymem.core._profile_export import ProfileExportMixin
from carrymem.core._prompt_delegate import PromptDelegateMixin
from carrymem.core._recall import RecallMixin


class CarryMem(
    LifecycleMixin,
    BackupMixin,
    MemoryCRUDMixin,
    ClassificationMixin,
    RecallMixin,
    ProfileExportMixin,
    MaintenanceMixin,
    PromptDelegateMixin,
):
    """CarryMem — Portable AI Memory Layer (Facade).

    Makes AI agents remember users. Classification is core, storage is swappable,
    works out of the box. Knowledge base is read-only, memories are read-write.
    Recall priority: memories > knowledge base.

    Composed from 7 Mixin classes + LifecycleMixin via multiple inheritance.
    All public methods retain their original signatures for full backward compat.
    """

    # Ensure MRO puts LifecycleMixin first so __init__ resolves correctly
    pass


__all__ = [
    "CarryMem",
    "StorageNotConfiguredError",
    "KnowledgeNotConfiguredError",
    "_validate_file_path",
]
