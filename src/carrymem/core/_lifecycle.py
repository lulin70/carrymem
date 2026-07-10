"""Lifecycle: __init__, close, context-manager, properties."""

from __future__ import annotations

import logging
import os
import sqlite3
from threading import Timer
from types import TracebackType
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

from carrymem.adapters.base import StorageAdapter
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.engine import MemoryClassificationEngine
from carrymem.error_messages import get_hint, get_message
from carrymem.errors import CarryMemError
from carrymem.exceptions import KnowledgeNotConfiguredError as _KnowledgeNotConfiguredError
from carrymem.exceptions import StorageNotConfiguredError as _StorageNotConfiguredError
from carrymem.rules.candidate_generator import RuleCandidateGenerator

if TYPE_CHECKING:
    from carrymem.prompt_builder import PromptBuilder
    from carrymem.rules import RuleEngine
    from carrymem.security.permissions import AccessPolicy

logger = logging.getLogger(__name__)

# Type alias for storage parameter
StorageType = Optional[Union[str, StorageAdapter]]


def _validate_file_path(path: str, allowed_base: Optional[str] = None) -> str:
    # Reject path traversal patterns in the raw input
    if ".." in path.split(os.sep) or ".." in path.split("/"):
        raise ValueError(f"Path traversal not allowed: {path}")
    resolved = os.path.realpath(os.path.expanduser(path))
    if allowed_base:
        allowed = os.path.realpath(allowed_base)
        if not resolved.startswith(allowed + os.sep) and resolved != allowed:
            raise ValueError(f"Path escapes allowed directory: {path}")
    else:
        from carrymem.constants import DANGEROUS_SYSTEM_DIRS

        for d in DANGEROUS_SYSTEM_DIRS:
            if resolved == str(d) or resolved.startswith(str(d) + os.sep):
                raise ValueError(f"Path traversal: system directory not allowed: {resolved}")
    return resolved


class StorageNotConfiguredError(_StorageNotConfiguredError):
    """Raised when no storage adapter is configured, with a setup hint."""

    def __init__(self):
        super().__init__(
            "Storage adapter not configured. "
            "Use CarryMem(storage='sqlite') or CarryMem(storage=YourAdapter()) "
            "to enable storage features."
        )


class KnowledgeNotConfiguredError(_KnowledgeNotConfiguredError):
    """Raised when no knowledge adapter is configured, with a setup hint."""

    def __init__(self):
        super().__init__(
            "Knowledge adapter not configured. "
            "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path/to/vault')) "
            "to enable knowledge base features."
        )


class LifecycleMixin:
    """Handles object lifecycle: init, close, context-manager, and shared-state properties."""

    # Class-level attribute used by MaintenanceMixin
    _consolidation_timer: Optional[Timer] = None

    def __init__(
        self,
        storage: StorageType = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict[str, Any]] = None,
        encryption_key: Optional[str] = None,
        auto_backup_interval: int = 20,
    ) -> None:
        """Initialize storage adapter, engine, and shared lifecycle state."""
        self._engine = MemoryClassificationEngine()
        self._namespace = namespace

        if db_path is None:
            db_path = os.environ.get("CARRYMEM_DB_PATH")

        if db_path is not None and db_path != ":memory:":
            try:
                _validate_file_path(db_path)
            except ValueError:
                raise

        if storage is None:
            self._adapter: Optional[StorageAdapter] = None
        elif storage == "sqlite":
            try:
                self._adapter = SQLiteAdapter(
                    db_path=db_path,
                    namespace=namespace,
                    encryption_key=encryption_key,
                    enable_vector_search=config.get("enable_vector_search", True) if config else True,
                    embedding_model=(
                        config.get("embedding_model", "all-MiniLM-L6-v2") if config else "all-MiniLM-L6-v2"
                    ),
                )
            except (OSError, ValueError, TypeError, sqlite3.Error) as e:
                raise CarryMemError.from_cause(e) from e
        elif isinstance(storage, StorageAdapter):
            self._adapter = storage
        elif isinstance(storage, str):
            from carrymem.adapters.loader import load_adapter

            try:
                adapter_cls = load_adapter(storage)
            except (ImportError, ValueError, TypeError) as e:
                raise CarryMemError.from_cause(e) from e
            if adapter_cls is None:
                raise CarryMemError(
                    code="CM-100",
                    message=get_message("CM-100"),
                    hint=get_hint("CM-100"),
                    cause=ValueError(f"Unknown adapter: {storage!r}"),
                )
            if storage == "obsidian":
                raise CarryMemError(
                    code="CM-100",
                    message=get_message("CM-100"),
                    hint=get_hint("CM-110"),
                    cause=ValueError("ObsidianAdapter requires a vault_path."),
                )
            else:
                self._adapter = adapter_cls()
        else:
            raise CarryMemError(
                code="CM-202",
                message=get_message("CM-202"),
                hint=get_hint("CM-202"),
                cause=ValueError(f"Invalid storage type: {storage!r}"),
            )

        self._knowledge_adapter = knowledge_adapter
        self._rule_engine: Optional[RuleEngine] = None
        self._config = config
        self._prompt_builder: Optional[PromptBuilder] = None
        self._candidate_generator = RuleCandidateGenerator(
            rule_engine_getter=lambda: self.rule_engine,
            recall_memories=self.recall_memories,  # type: ignore[attr-defined]
        )

        # Eagerly initialize the rule engine schema before any concurrent
        # access. RuleStorage._ensure_schema() creates the rules_fts vtable
        # and triggers, which increments the SQLite schema cookie. If this
        # runs lazily during a concurrent INSERT (via classify_and_remember
        # → rule_engine access), the memories_fts vtable on other
        # connections becomes invalid, producing intermittent
        # "vtable constructor failed: memories_fts" (SQLITE_SCHEMA) errors.
        # Eager init ensures all schema changes complete before worker
        # threads can access the database.
        if self._adapter is not None and hasattr(self._adapter, "db_path"):
            try:
                _ = self.rule_engine
            except Exception:
                pass

        # Auto-backup state
        self._write_count = 0
        self._auto_backup_interval = auto_backup_interval
        self._initial_backup_done = False
        self._backup_dir = config.get("backup_dir") if config else None

        # Access control (P1-8 MVP) — set via CarryMem.access_policy property
        self._access_policy: Optional[AccessPolicy] = None

        # v0.5.1: Entity normalization lazy-init state (ClassificationMixin owns the property)
        self._entity_normalizer: Optional[Any] = None
        self._input_validator: Optional[Any] = None

        # Perform initial backup on first creation with SQLite
        if self._adapter and self._adapter.capabilities.get("backup", False):
            db_file = getattr(self._adapter, "db_path", None)
            if db_file and db_file != ":memory:" and os.path.exists(db_file):
                try:
                    self._do_initial_backup()  # type: ignore[attr-defined]
                except (OSError, ValueError, RuntimeError) as e:
                    logger.debug("Initial backup skipped: %s", e)

    @property
    def rule_engine(self) -> RuleEngine:  # lazy init; uses TYPE_CHECKING import
        """Lazily-initialized rule engine bound to the storage backend."""
        if self._rule_engine is None:
            from carrymem.rules import RuleEngine

            db_path = self._adapter.db_path if self._adapter and hasattr(self._adapter, "db_path") else None
            self._rule_engine = RuleEngine(db_path=db_path)
        return self._rule_engine

    @property
    def prompt_builder(self) -> PromptBuilder:  # lazy init; uses TYPE_CHECKING import
        """Lazily-initialized prompt builder bound to this instance."""
        if self._prompt_builder is None:
            from carrymem.prompt_builder import PromptBuilder

            self._prompt_builder = PromptBuilder(self)
        return self._prompt_builder

    def close(self) -> None:
        """Release the engine, rule engine, adapters, and cached helpers."""
        if self._rule_engine:
            self._rule_engine = None
        if self._engine:
            self._engine = None  # type: ignore[assignment]
        if self._prompt_builder:
            self._prompt_builder = None
        if self._candidate_generator:
            self._candidate_generator = None  # type: ignore[assignment]
        if self._adapter and hasattr(self._adapter, "close"):
            self._adapter.close()
        if self._knowledge_adapter and hasattr(self._knowledge_adapter, "close"):
            self._knowledge_adapter.close()

    def __enter__(self) -> "LifecycleMixin":
        return self

    def __exit__(  # type: ignore[exit-return]
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> bool:
        self.close()
        return False

    @property
    def namespace(self) -> str:
        """Active namespace for this instance."""
        return self._namespace

    @property
    def engine(self) -> MemoryClassificationEngine:
        """Underlying memory classification engine."""
        return self._engine

    @property
    def adapter(self) -> Optional[StorageAdapter]:
        """Configured storage adapter, if any."""
        return self._adapter

    @property
    def storage(self) -> Optional[StorageAdapter]:
        """Configured storage adapter, if any."""
        return self._adapter

    @property
    def knowledge_adapter(self) -> Optional[StorageAdapter]:
        """Configured knowledge adapter, if any."""
        return self._knowledge_adapter
