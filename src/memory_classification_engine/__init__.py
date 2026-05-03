"""CarryMem — Your Portable AI Memory Layer.

CarryMem = MCE Classification Engine + SQLite Default Storage + Replaceable Adapters

v0.1.5: Version reset — Security hardening, thread safety, documentation reorganization

Quick Start:
    from memory_classification_engine import CarryMem

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

from memory_classification_engine.carrymem import CarryMem, StorageNotConfiguredError, KnowledgeNotConfiguredError
from memory_classification_engine.engine import MemoryClassificationEngine
from memory_classification_engine.adapters.base import MemoryEntry, StorageAdapter, StoredMemory
from memory_classification_engine.adapters.sqlite_adapter import SQLiteAdapter
from memory_classification_engine.adapters.obsidian_adapter import ObsidianAdapter
from memory_classification_engine.adapters.json_adapter import JSONAdapter


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
                f"Install required dependencies with: pip install memory-classification-engine[full]"
            ) from e
    _import.__name__ = class_name
    _import.__qualname__ = class_name
    return _import


try:
    from memory_classification_engine.semantic.expander import SemanticExpander
except ImportError:
    SemanticExpander = _make_lazy_import("memory_classification_engine.semantic.expander", "SemanticExpander")

try:
    from memory_classification_engine.semantic.merger import ResultMerger
except ImportError:
    ResultMerger = _make_lazy_import("memory_classification_engine.semantic.merger", "ResultMerger")

try:
    from memory_classification_engine.security import InputValidator
except ImportError:
    InputValidator = _make_lazy_import("memory_classification_engine.security", "InputValidator")

try:
    from memory_classification_engine.security import ValidationError
except ImportError:
    ValidationError = _make_lazy_import("memory_classification_engine.security", "ValidationError")

try:
    from memory_classification_engine.security import validate_content
except ImportError:
    validate_content = _make_lazy_import("memory_classification_engine.security", "validate_content")

try:
    from memory_classification_engine.security import validate_query
except ImportError:
    validate_query = _make_lazy_import("memory_classification_engine.security", "validate_query")

try:
    from memory_classification_engine.security import validate_namespace
except ImportError:
    validate_namespace = _make_lazy_import("memory_classification_engine.security", "validate_namespace")

try:
    from memory_classification_engine.async_carrymem import AsyncCarryMem
except ImportError:
    AsyncCarryMem = _make_lazy_import("memory_classification_engine.async_carrymem", "AsyncCarryMem")

from memory_classification_engine.__version__ import __version__
from memory_classification_engine.api_types import (
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
