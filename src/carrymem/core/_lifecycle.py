"""Lifecycle: __init__, close, context-manager, properties."""

import logging
import os
import sqlite3
from typing import Any, Dict, Optional, Union

from carrymem.adapters.base import MemoryEntry, StorageAdapter
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.engine import MemoryClassificationEngine
from carrymem.errors import CarryMemError
from carrymem.exceptions import KnowledgeNotConfiguredError as _KnowledgeNotConfiguredError
from carrymem.exceptions import StorageNotConfiguredError as _StorageNotConfiguredError
from carrymem.rules.candidate_generator import RuleCandidateGenerator

logger = logging.getLogger(__name__)

# Type alias for storage parameter
StorageType = Optional[Union[str, StorageAdapter]]


def _validate_file_path(path: str, allowed_base: Optional[str] = None) -> str:
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
    def __init__(self):
        super().__init__(
            "Storage adapter not configured. "
            "Use CarryMem(storage='sqlite') or CarryMem(storage=YourAdapter()) "
            "to enable storage features."
        )


class KnowledgeNotConfiguredError(_KnowledgeNotConfiguredError):
    def __init__(self):
        super().__init__(
            "Knowledge adapter not configured. "
            "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path/to/vault')) "
            "to enable knowledge base features."
        )


class LifecycleMixin:
    """Handles object lifecycle: init, close, context-manager, and shared-state properties."""

    # Class-level attribute used by MaintenanceMixin
    _consolidation_timer: Optional[Any] = None

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
        self._engine = MemoryClassificationEngine()
        self._namespace = namespace

        if db_path is None:
            db_path = os.environ.get("CARRYMEM_DB_PATH")

        if storage is None:
            self._adapter: Optional[StorageAdapter] = None
        elif storage == "sqlite":
            try:
                self._adapter = SQLiteAdapter(
                    db_path=db_path,
                    namespace=namespace,
                    encryption_key=encryption_key,
                    enable_vector_search=config.get("enable_vector_search", True) if config else True,
                    embedding_model=(config.get("embedding_model", "all-MiniLM-L6-v2") if config else "all-MiniLM-L6-v2"),
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
                    message=f"未知的存储适配器类型: {storage!r}",
                    hint="使用 'sqlite'、'obsidian'、StorageAdapter 实例，或安装注册此名称的插件。",
                    cause=ValueError(f"Unknown adapter: {storage!r}"),
                )
            if storage == "obsidian":
                raise CarryMemError(
                    code="CM-100",
                    message="Obsidian 适配器需要指定 vault_path 参数。",
                    hint="请使用 CarryMem(knowledge_adapter=ObsidianAdapter('/path/to/vault')) 的方式配置。",
                    cause=ValueError("ObsidianAdapter requires a vault_path."),
                )
            else:
                self._adapter = adapter_cls()
        else:
            raise CarryMemError(
                code="CM-202",
                message=f"无效的存储类型参数: {storage!r}",
                hint="支持 None、'sqlite' 或 StorageAdapter 实例。",
                cause=ValueError(f"Invalid storage type: {storage!r}"),
            )

        self._knowledge_adapter = knowledge_adapter
        self._rule_engine: Optional[Any] = None
        self._config = config
        self._prompt_builder: Optional[Any] = None
        self._candidate_generator = RuleCandidateGenerator(
            rule_engine_getter=lambda: self.rule_engine,
            recall_memories=self.recall_memories,
        )

        # Auto-backup state
        self._write_count = 0
        self._auto_backup_interval = auto_backup_interval
        self._initial_backup_done = False
        self._backup_dir = config.get("backup_dir") if config else None

        # Access control (P1-8 MVP) — set via CarryMem.access_policy property
        self._access_policy: Optional[Any] = None

        # Perform initial backup on first creation with SQLite
        if self._adapter and isinstance(self._adapter, SQLiteAdapter):
            db_file = self._adapter.db_path
            if db_file and db_file != ":memory:" and os.path.exists(db_file):
                try:
                    self._do_initial_backup()
                except (OSError, ValueError, RuntimeError) as e:
                    logger.debug("Initial backup skipped: %s", e)

    @property
    def rule_engine(self) -> Any:  # RuleEngine (lazy import to avoid circular dependency)
        if self._rule_engine is None:
            from carrymem.rules import RuleEngine

            db_path = self._adapter.db_path if self._adapter and hasattr(self._adapter, "db_path") else None
            self._rule_engine = RuleEngine(db_path=db_path)
        return self._rule_engine

    @property
    def prompt_builder(self) -> Any:  # PromptBuilder (lazy import to avoid circular dependency)
        if self._prompt_builder is None:
            from carrymem.prompt_builder import PromptBuilder

            self._prompt_builder = PromptBuilder(self)
        return self._prompt_builder

    def close(self) -> None:
        if self._rule_engine:
            self._rule_engine = None
        if self._adapter and hasattr(self._adapter, "close"):
            self._adapter.close()
        if self._knowledge_adapter and hasattr(self._knowledge_adapter, "close"):
            self._knowledge_adapter.close()

    def __enter__(self) -> "LifecycleMixin":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.close()
        return False

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def engine(self) -> MemoryClassificationEngine:
        return self._engine

    @property
    def adapter(self) -> Optional[StorageAdapter]:
        return self._adapter

    @property
    def storage(self) -> Optional[StorageAdapter]:
        return self._adapter

    @property
    def knowledge_adapter(self) -> Optional[StorageAdapter]:
        return self._knowledge_adapter
