"""CarryMem — Your Portable AI Memory Layer.

CarryMem = MCE Classification Engine + SQLite Default Storage + Replaceable Adapters

v0.2.0: Consolidation scheduling + PrefEval standardization + Context modularization + Security hardening

Quick Start:
    from carrymem import CarryMem

    cm = CarryMem()
    result = cm.classify_and_remember("I prefer dark mode")
    memories = cm.recall_memories("dark mode")  # Also finds "深色模式", "ダークモード", etc.

CLI:
    carrymem add "I prefer dark mode"
    carrymem list
    carrymem search "theme"
    carrymem setup-mcp --tool cursor
    carrymem doctor
"""

import os as _os

_os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
_os.environ.setdefault("HF_HUB_OFFLINE", "1")

from carrymem.carrymem import CarryMem, StorageNotConfiguredError, KnowledgeNotConfiguredError
from carrymem.engine import MemoryClassificationEngine
from carrymem.adapters.base import MemoryEntry, StorageAdapter, StoredMemory
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.adapters.json_adapter import JSONAdapter


def _make_lazy_import(module_path, class_name):
    def _import(*args, **kwargs):
        try:
            import importlib

            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            return cls(*args, **kwargs) if args or kwargs else cls
        except ImportError as e:
            raise ImportError(
                f"Optional dependency not available for {class_name}: {e}. "
                f"Install required dependencies with: pip install carrymem[full]"
            ) from e

    _import.__name__ = class_name
    _import.__qualname__ = class_name
    return _import


try:
    from carrymem.semantic.expander import SemanticExpander
except ImportError:
    SemanticExpander = _make_lazy_import("carrymem.semantic.expander", "SemanticExpander")

try:
    from carrymem.semantic.merger import ResultMerger
except ImportError:
    ResultMerger = _make_lazy_import("carrymem.semantic.merger", "ResultMerger")

try:
    from carrymem.security import InputValidator
except ImportError:
    InputValidator = _make_lazy_import("carrymem.security", "InputValidator")

try:
    from carrymem.security import ValidationError
except ImportError:
    ValidationError = _make_lazy_import("carrymem.security", "ValidationError")

try:
    from carrymem.security import validate_content
except ImportError:
    validate_content = _make_lazy_import("carrymem.security", "validate_content")

try:
    from carrymem.security import validate_query
except ImportError:
    validate_query = _make_lazy_import("carrymem.security", "validate_query")

try:
    from carrymem.security import validate_namespace
except ImportError:
    validate_namespace = _make_lazy_import("carrymem.security", "validate_namespace")

try:
    from carrymem.async_carrymem import AsyncCarryMem
except ImportError:
    AsyncCarryMem = _make_lazy_import("carrymem.async_carrymem", "AsyncCarryMem")

from carrymem.__version__ import __version__  # noqa: F401
from carrymem.api_types import (
    RuleDict,
    MatchResultDict,
    EffectivenessReportDict,
    SourceMemoryValidationDict,
    KnowledgeNoteDict,
    RecallAllResultDict,
    BuildContextResultDict,
)

__all__ = [
    "CarryMem",
    "MemoryClassificationEngine",
    "MemoryEntry",
    "StorageAdapter",
    "StoredMemory",
    "SQLiteAdapter",
    "ObsidianAdapter",
    "JSONAdapter",
    "StorageNotConfiguredError",
    "KnowledgeNotConfiguredError",
    "SemanticExpander",
    "ResultMerger",
    "InputValidator",
    "ValidationError",
    "validate_content",
    "validate_query",
    "validate_namespace",
    "AsyncCarryMem",
    "RuleDict",
    "MatchResultDict",
    "EffectivenessReportDict",
    "SourceMemoryValidationDict",
    "KnowledgeNoteDict",
    "RecallAllResultDict",
    "BuildContextResultDict",
]
