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

from typing import Any, Dict, List, Optional
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import warnings

from carrymem.engine import MemoryClassificationEngine
from carrymem.adapters.base import MemoryEntry, StorageAdapter
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.domain import infer_domains_from_memories, get_domain_description


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


from carrymem.adapters.loader import load_adapter
from carrymem.rules.candidate_generator import RuleCandidateGenerator
from carrymem.utils.logger import logger
from carrymem.utils.validators import (
    validate_message,
    validate_context,
    validate_language,
    validate_limit,
    validate_storage_key,
    validate_query,
)
from carrymem.__version__ import __version__ as _version
from carrymem.exceptions import (
    StorageNotConfiguredError as _StorageNotConfiguredError,
    KnowledgeNotConfiguredError as _KnowledgeNotConfiguredError,
)

from carrymem.security.input_validator import InputValidator

_import_validator = InputValidator(strict_mode=True)


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


class CarryMem:
    """CarryMem — Portable AI Memory Layer.

    Makes AI agents remember users. Classification is core, storage is swappable,
    works out of the box. Knowledge base is read-only, memories are read-write.
    Recall priority: memories > knowledge base.
    """

    def __init__(
        self,
        storage: Optional[Any] = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict] = None,
        encryption_key: Optional[str] = None,
        auto_backup_interval: int = 20,
    ):
        self._engine = MemoryClassificationEngine()
        self._namespace = namespace

        if db_path is None:
            db_path = os.environ.get("CARRYMEM_DB_PATH")

        if storage is None:
            self._adapter: Optional[StorageAdapter] = None
        elif storage == "sqlite":
            self._adapter = SQLiteAdapter(
                db_path=db_path,
                namespace=namespace,
                encryption_key=encryption_key,
                enable_vector_search=config.get("enable_vector_search", True) if config else True,
                embedding_model=(
                    config.get("embedding_model", "all-MiniLM-L6-v2")
                    if config
                    else "all-MiniLM-L6-v2"
                ),
            )
        elif isinstance(storage, StorageAdapter):
            self._adapter = storage
        elif isinstance(storage, str):
            adapter_cls = load_adapter(storage)
            if adapter_cls is None:
                raise ValueError(
                    f"Unknown adapter: {storage!r}. "
                    "Use 'sqlite', 'obsidian', a StorageAdapter instance, "
                    "or install a plugin that registers this adapter name."
                )
            if storage == "obsidian":
                raise ValueError(
                    "ObsidianAdapter requires a vault_path. "
                    "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path/to/vault')) instead."
                )
            else:
                self._adapter = adapter_cls()
        else:
            raise ValueError(
                f"Invalid storage type: {storage!r}. "
                "Use None, 'sqlite', or a StorageAdapter instance."
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

        # Perform initial backup on first creation with SQLite
        if self._adapter and isinstance(self._adapter, SQLiteAdapter):
            db_file = self._adapter.db_path
            if db_file and db_file != ":memory:" and os.path.exists(db_file):
                try:
                    self._do_initial_backup()
                except Exception as e:
                    logger.debug(f"Initial backup skipped: {e}")

    @property
    def rule_engine(self):
        if self._rule_engine is None:
            from .rules import RuleEngine

            db_path = (
                self._adapter.db_path
                if self._adapter and hasattr(self._adapter, "db_path")
                else None
            )
            self._rule_engine = RuleEngine(db_path=db_path)
        return self._rule_engine

    @property
    def prompt_builder(self):
        if self._prompt_builder is None:
            from .prompt_builder import PromptBuilder

            self._prompt_builder = PromptBuilder(self)
        return self._prompt_builder

    def close(self):
        if self._rule_engine:
            self._rule_engine = None
        if self._adapter and hasattr(self._adapter, "close"):
            self._adapter.close()
        if self._knowledge_adapter and hasattr(self._knowledge_adapter, "close"):
            self._knowledge_adapter.close()

    def _do_initial_backup(self) -> None:
        """Create initial backup when CarryMem first opens an existing database."""
        if self._initial_backup_done:
            return
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return
        db_path = self._adapter.db_path
        if db_path == ":memory:":
            return

        from carrymem.backup import BackupManager

        manager = BackupManager(db_path, backup_dir=self._backup_dir)
        backups = manager.list_backups()
        if not backups:
            try:
                manager.create_backup()
                logger.info("Initial backup created")
            except Exception as e:
                logger.debug(f"Initial backup failed: {e}")
        self._initial_backup_done = True

    def _auto_backup(self) -> None:
        """Check if auto-backup should run based on write count, and execute if needed."""
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return
        if self._auto_backup_interval <= 0:
            return

        self._write_count += 1
        if self._write_count >= self._auto_backup_interval:
            self._write_count = 0
            try:
                db_path = self._adapter.db_path
                if db_path and db_path != ":memory:":
                    from carrymem.backup import BackupManager

                    manager = BackupManager(db_path, backup_dir=self._backup_dir)
                    manager.create_backup()
                    logger.debug(f"Auto-backup triggered after {self._auto_backup_interval} writes")
            except Exception as e:
                logger.debug(f"Auto-backup failed: {e}")

    def clear_cache(self) -> None:
        if self._adapter and hasattr(self._adapter, "_cache") and self._adapter._cache:
            self._adapter._cache.clear()

    def backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Backup only supported with SQLiteAdapter"}

        from carrymem.backup import BackupManager

        db_path = self._adapter.db_path
        if db_path == ":memory:":
            return {"error": "Cannot backup in-memory database"}

        manager = BackupManager(db_path, backup_dir=backup_dir)
        try:
            path = manager.create_backup()
            return {"backed_up": True, "path": path}
        except Exception as e:
            return {"backed_up": False, "error": str(e)}

    def list_backups(self, backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return []

        from carrymem.backup import BackupManager

        db_path = self._adapter.db_path
        manager = BackupManager(db_path, backup_dir=backup_dir)
        return manager.list_backups()

    def restore_backup(self, backup_path: str, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Restore only supported with SQLiteAdapter"}

        from carrymem.backup import BackupManager

        db_path = self._adapter.db_path
        if db_path == ":memory:":
            return {"error": "Cannot restore to in-memory database"}

        if backup_dir is None:
            backup_dir = os.path.dirname(backup_path)
        manager = BackupManager(db_path, backup_dir=backup_dir)
        try:
            manager.restore_backup(backup_path)
            return {"restored": True, "backup_path": backup_path}
        except Exception as e:
            return {"restored": False, "error": str(e)}

    def get_audit_log(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return []

        if not self._adapter._audit:
            return []

        return self._adapter._audit.query(
            operation=operation,
            namespace=self._namespace,
            since=since,
            until=until,
            source=source,
            limit=limit,
        )

    def merge_memories(
        self,
        namespaces: Optional[List[str]] = None,
        strategy: str = "latest_wins",
        conflict_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        from carrymem.merge import merge_memories as _merge

        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Merge only supported with SQLiteAdapter"}

        ns_list = namespaces or [self._namespace]
        all_memories = []
        for ns in ns_list:
            results = self._adapter.recall("", limit=10000, namespaces=[ns])
            all_memories.extend([r.to_dict() for r in results])

        conflicts_before = len(all_memories)
        merged = _merge(
            memories=all_memories,
            strategy=strategy,
            conflict_callback=conflict_callback,
        )
        duplicates_removed = conflicts_before - len(merged)

        return {
            "total_input": conflicts_before,
            "total_output": len(merged),
            "duplicates_removed": duplicates_removed,
            "strategy": strategy,
            "namespaces": ns_list,
            "memories": merged,
        }

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        result = self._adapter.update_memory(storage_key, new_content, reason)
        if result is None:
            return {"updated": False, "error": f"Memory not found: {storage_key}"}

        if self._adapter._cache:
            self._adapter._cache.invalidate()

        self._auto_backup()

        return {
            "updated": True,
            "storage_key": result.storage_key,
            "version": result.version,
            "content": result.content,
        }

    def get_memory_history(
        self,
        storage_key: str,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        return self._adapter.get_memory_history(storage_key)

    def rollback_memory(
        self,
        storage_key: str,
        version: int,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        result = self._adapter.rollback_memory(storage_key, version)
        if result is None:
            return {"rolled_back": False, "error": "Memory or version not found"}

        if self._adapter._cache:
            self._adapter._cache.invalidate()

        self._auto_backup()

        return {
            "rolled_back": True,
            "storage_key": result.storage_key,
            "version": result.version,
            "content": result.content,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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

    def index_knowledge(self) -> Dict[str, Any]:
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        if isinstance(self._knowledge_adapter, ObsidianAdapter):
            return self._knowledge_adapter.index_vault()

        return {"error": "Knowledge adapter does not support indexing"}

    def recall_from_knowledge(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        results = self._knowledge_adapter.recall(query, filters=filters, limit=limit)
        if isinstance(results, list) and results and isinstance(results[0], dict):
            return results  # type: ignore[return-value]
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in results]  # type: ignore[misc]

    def recall_all(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        memory_results = []
        knowledge_results = []
        rule_results = []

        if include_rules:
            try:
                rule_engine = self.rule_engine
                matches = rule_engine.match(query, limit=min(limit, 5), increment_count=False)
                rule_results = [
                    {
                        "rule_id": m.rule.id,
                        "trigger": m.rule.trigger,
                        "action": m.rule.action,
                        "rule_type": m.rule.rule_type,
                        "override": m.rule.override,
                        "score": m.score,
                        "match_type": m.match_type,
                    }
                    for m in matches
                ]
            except Exception as e:
                logger.warning(f"Rule engine failed for recall_all: {e}")
                rule_results = []

        if self._adapter:
            try:
                memory_results = self.recall_memories(
                    query=query, filters=filters, limit=limit, namespaces=namespaces
                )
            except Exception as e:
                logger.warning(f"Failed to recall memories for prompt: {e}")
                memory_results = []

        if self._knowledge_adapter:
            try:
                knowledge_results = self.recall_from_knowledge(
                    query=query, filters=filters, limit=limit
                )
            except Exception as e:
                logger.warning(f"Failed to recall from knowledge base: {e}")
                knowledge_results = []

        return {
            "rules": rule_results,
            "memories": memory_results,
            "knowledge": knowledge_results,
            "rule_count": len(rule_results),
            "memory_count": len(memory_results),
            "knowledge_count": len(knowledge_results),
            "total_count": len(rule_results) + len(memory_results) + len(knowledge_results),
            "namespace": self._namespace,
            "priority": "rules > memory > knowledge",
        }

    def classify_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        validate_message(message)
        validate_context(context)
        validate_language(language)
        result = self._engine.process_message(message, context=context, language=language)

        matches = result.get("matches", [])
        entries = []
        for m in matches:
            entry = MemoryEntry(
                id=m.get("id", ""),
                type=m.get("memory_type") or m.get("type", "unknown"),
                content=m.get("content", ""),
                raw_text=message,
                confidence=m.get("confidence", 0.0),
                tier=m.get("tier", 2),
                source_layer=m.get("source_layer", "unknown"),
                reasoning=m.get("reasoning", ""),
                suggested_action=m.get("suggested_action", "store"),
                recall_hint=m.get("recall_hint"),
                metadata=m.get("metadata", {}),
            )
            # Auto-infer memory_nature from type
            entry.memory_nature = entry.infer_memory_nature()
            entries.append(entry)

        return {
            "should_remember": len(entries) > 0,
            "entries": [e.to_dict() for e in entries],
            "summary": {
                "total_entries": len(entries),
                "by_type": self._count_by_type(entries),
            },
        }

    def _validate_and_resolve(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> tuple:
        """Validate input, inject session_id, resolve coreferences, check redaction.

        Returns:
            (resolved_message, should_continue, redact_result, coreference_resolved)
            - resolved_message: message after coreference resolution
            - should_continue: False if auto-redaction blocked storage
            - redact_result: full result dict if blocked, else None
            - coreference_resolved: whether coreference resolution modified the message
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        if len(message) > 50000:
            raise ValueError(f"Message too long: {len(message)} chars (max 50000)")

        # Inject session_id into context
        if session_id and context is None:
            context = {}
        if session_id and isinstance(context, dict):
            context["session_id"] = session_id

        # Coreference resolution: resolve pronouns before classification
        resolved_message = message
        coreference_resolved = False

        # Skip expensive recall+coreference for messages without pronouns.
        _PRONOUNS = {"it", "this", "that", "these", "those",
                      "he", "she", "they", "him", "her", "them",
                      "his", "its", "their", "my", "your", "our"}
        _has_pronoun = bool(
            set(message.lower().split()) & _PRONOUNS
            or any(p in message.lower() for p in ("it's", "that's", "he's", "she's"))
        )

        if _has_pronoun:
            try:
                from carrymem.coreference import resolve_coreference

                context_str = ""
                if context and isinstance(context, dict):
                    context_str = context.get("ai_reply", "") or context.get("previous_message", "")
                recent_mems = []
                try:
                    recent_mems = self.recall_memories(query="", limit=5, update_access=False)
                except Exception as e:
                    logger.debug(f"Coreference recall skipped (non-critical): {e}")
                resolved_message, coreference_resolved = resolve_coreference(
                    message,
                    context=context_str,
                    recent_memories=recent_mems,
                )
                if coreference_resolved:
                    logger.debug(f"Coreference resolved: '{message}' → '{resolved_message}'")
            except Exception as e:
                logger.debug(f"Coreference resolution failed (non-critical), using original message: {e}")

        # Auto-redaction: block sensitive content from storage
        if not force_type:  # force_type allows user to override redaction
            try:
                from carrymem.security.redaction import should_redact

                should_block, redact_reason = should_redact(resolved_message)
                if should_block:
                    logger.warning(f"Auto-redact blocked memory storage: {redact_reason}")
                    redact_result = {
                        "should_remember": False,
                        "type": "auto_redacted",
                        "content": resolved_message,
                        "entries": [],
                        "stored": False,
                        "storage_keys": [],
                        "rule_suggestions": [],
                        "auto_rules": [],
                        "updated_memories": [],
                        "summary": {
                            "total_entries": 0,
                            "by_type": {},
                            "redacted": True,
                            "redact_reason": redact_reason,
                        },
                    }
                    return (resolved_message, False, redact_result, coreference_resolved)
            except Exception as e:
                logger.warning(f"Auto-redaction check failed, allowing storage as precaution: {e}")

        return (resolved_message, True, None, coreference_resolved)

    def _classify_message(
        self,
        resolved_message: str,
        context: Optional[Dict[str, Any]],
        language: Optional[str],
        force_type: Optional[str],
        message: str,
    ) -> List[Dict[str, Any]]:
        """Classify the message and apply force_type override.

        Returns:
            entries list (may be empty for noise), or None if should not remember
            (without force_type). The caller should check classify_result structure.
        """
        # Use resolved message for classification, but keep original as raw_text
        classify_result = self.classify_message(
            resolved_message, context=context, language=language
        )

        if not classify_result["should_remember"] and not force_type:
            return []  # Signal: noise, no entries to store

        # force_type overrides classification: ensure entry exists and action is store
        if force_type and not classify_result["should_remember"]:
            classify_result["should_remember"] = True
            if not classify_result["entries"]:
                classify_result["entries"] = [
                    {
                        "content": message,
                        "type": force_type,
                        "suggested_action": "store",
                        "confidence": 0.8,
                    }
                ]

        return classify_result

    def _store_entries(
        self,
        classify_result: Dict[str, Any],
        resolved_message: str,
        message: str,
        context: Optional[Dict[str, Any]],
        coreference_resolved: bool,
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Store classified entries, handle corrections, suggest rules, backup.

        Returns:
            Final result dict with stored memories metadata.
        """
        stored_memories = []
        storage_keys = []
        updated_memories = []
        for entry_dict in classify_result["entries"]:
            entry = MemoryEntry.from_dict(entry_dict)
            if force_type:
                entry.type = force_type
            # Preserve original message as raw_text when coreference was resolved
            if coreference_resolved:
                entry.raw_text = message
            if session_id and isinstance(entry.metadata, dict):
                entry.metadata["session_id"] = session_id
            elif session_id and not entry.metadata:
                entry.metadata = {"session_id": session_id}
            if entry.suggested_action == "store":
                try:
                    if entry.type == "correction":
                        updated = self._handle_correction(entry)
                        if updated:
                            updated_memories.append(updated)

                    stored = self._adapter.remember(entry)
                    stored_memories.append(stored.to_dict())
                    storage_keys.append(stored.storage_key)
                except Exception as e:
                    logger.warning(f"Failed to store memory: {e}")
                    continue

        auto_rules = []
        try:
            auto_rules = self._auto_suggest_rules(stored_memories)
        except Exception as e:
            logger.debug(f"Auto rule suggestion skipped: {e}")

        self._auto_backup()

        return {
            "should_remember": True,
            "type": stored_memories[0].get("type", "unknown") if stored_memories else "unknown",
            "content": stored_memories[0].get("content", message) if stored_memories else message,
            "entries": stored_memories,
            "stored": len(stored_memories) > 0,
            "storage_keys": storage_keys,
            "rule_suggestions": auto_rules,
            "auto_rules": auto_rules,
            "updated_memories": updated_memories,
            "summary": classify_result["summary"],
        }

    def classify_and_remember(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        session_id: Optional[str] = None,
        force_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        # 1. Validate & resolve (coreference + redaction check)
        resolved_message, should_continue, redact_result, coreference_resolved = self._validate_and_resolve(
            message, context, force_type, session_id
        )
        if not should_continue:
            return redact_result  # type: ignore[return-value]

        # 2. Classify
        classify_result = self._classify_message(
            resolved_message, context, language, force_type, message
        )
        if isinstance(classify_result, list) and len(classify_result) == 0:
            # Noise path: _classify_message returns empty list for non-rememberable
            base_result = self.classify_message(resolved_message, context=context, language=language)
            return {
                **base_result,
                "stored": False,
                "storage_keys": [],
            }

        # 3. Store & post-process
        result = self._store_entries(
            classify_result,  # type: ignore[arg-type]
            resolved_message,
            message,
            context,
            coreference_resolved,
            force_type,
            session_id,
        )

        return result

    def _handle_correction(self, correction_entry: MemoryEntry) -> Optional[Dict[str, Any]]:
        if not self._adapter:
            return None

        content = correction_entry.content
        if not content or len(content.strip()) < 3:
            return None

        updated_info = None

        try:
            keywords = content.lower().split()
            related = self.recall_memories(limit=10)
            for mem in related:
                mem_content = mem.get("content", "").lower()
                mem_type = mem.get("type", "")
                if mem_type in ("user_preference", "decision", "fact_declaration"):
                    overlap = sum(1 for kw in keywords if kw in mem_content and len(kw) > 1)
                    if overlap >= 2:
                        storage_key = mem.get("storage_key", "")
                        if storage_key and hasattr(self._adapter, "update_memory"):
                            try:
                                reason = f"Corrected by: {content[:100]}"
                                self._adapter.update_memory(storage_key, content, reason)
                                updated_info = {
                                    "storage_key": storage_key,
                                    "old_content": mem.get("content", "")[:100],
                                    "new_content": content[:100],
                                    "reason": reason,
                                }
                            except Exception as e:
                                logger.warning(f"Correction update failed: {e}")
                        break
        except Exception as e:
            logger.warning(f"Correction handling failed: {e}")

        try:
            engine = self.rule_engine
            rules = engine.list_rules(status="active", limit=50)
            for rule in rules:
                rule_content = (rule.trigger + " " + rule.action).lower()
                overlap = sum(1 for kw in keywords if kw in rule_content and len(kw) > 1)
                if overlap >= 2:
                    try:
                        safe_action = self._sanitize_rule_content(content[:200])
                        engine.update_rule(rule.id, action=safe_action)
                        if updated_info is None:
                            updated_info = {
                                "rule_updated": rule.id,
                                "new_action": safe_action[:100],
                            }
                        else:
                            updated_info["rule_updated"] = rule.id
                    except Exception as e:
                        logger.warning(f"Rule update in correction handling failed: {e}")
                    break
        except Exception as e:
            logger.warning(f"Rule correction handling failed: {e}")

        return updated_info

    def _auto_suggest_rules(self, stored_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._candidate_generator.auto_suggest_rules(stored_memories)

    def _detect_implicit_preferences(self) -> List[Dict[str, Any]]:
        return self._candidate_generator.detect_implicit_preferences()

    def _sanitize_rule_content(self, text: str) -> str:
        return self._candidate_generator.sanitize_rule_content(text)

    def _extract_trigger(self, content: str, mem_type: str) -> str:
        return self._candidate_generator.extract_trigger(content, mem_type)

    def _extract_condition(self, content: str) -> str:
        return self._candidate_generator.extract_condition(content)

    def _extract_action(self, content: str, mem_type: str) -> str:
        return self._candidate_generator.extract_action(content, mem_type)

    def _infer_rule_type(self, mem_type: str, content: str = "") -> str:
        return self._candidate_generator.infer_rule_type(mem_type, content)

    def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_query(query or "")
        validate_limit(limit)
        if isinstance(self._adapter, SQLiteAdapter) and namespaces:
            results = self._adapter.recall(
                query or "",
                filters=filters,
                limit=limit,
                namespaces=namespaces,
                update_access=update_access,
            )
        else:
            results = self._adapter.recall(
                query or "", filters=filters, limit=limit, update_access=update_access
            )
        return [r.to_dict() for r in results]

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not hasattr(self._adapter, "recall_aggregated"):
            raise NotImplementedError("Adapter does not support recall_aggregated")

        result = self._adapter.recall_aggregated(
            memory_type=memory_type, limit_per_type=limit_per_type
        )
        return {k: [r.to_dict() for r in v] for k, v in result.items()}

    def recall_timeline(
        self,
        topic: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not hasattr(self._adapter, "recall_timeline"):
            raise NotImplementedError("Adapter does not support recall_timeline")

        results = self._adapter.recall_timeline(topic=topic, limit=limit)
        return [r.to_dict() for r in results]

    def summarize_session(
        self,
        session_id: str,
        language: str = "en",
        store: bool = True,
    ) -> Optional[Dict[str, Any]]:
        warnings.warn(
            "summarize_session() is experimental and requires LLM client. "
            "It will be integrated into CLI/MCP in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._adapter:
            raise StorageNotConfiguredError()

        from carrymem.layers.session_summarizer import SessionSummarizer

        if not hasattr(self, "_llm_client"):
            from carrymem.llm import LLMClient

            self._llm_client = LLMClient(config=self._config or {})
        summarizer = SessionSummarizer(llm_client=self._llm_client)

        session_memories = self.recall_memories(
            query="",
            limit=200,
            filters={"session_id": session_id, "include_superseded": True},
        )
        if not session_memories:
            return None

        summary_entry = summarizer.summarize_session(
            memories=session_memories,
            session_id=session_id,
            language=language,
        )
        if not summary_entry:
            return None

        if store:
            entry = MemoryEntry.from_dict(summary_entry)
            stored = self._adapter.remember(entry)
            return stored.to_dict()

        return summary_entry

    def aggregate_memories(
        self,
        memory_type: Optional[str] = None,
        language: str = "en",
        store: bool = True,
    ) -> List[Dict[str, Any]]:
        warnings.warn(
            "aggregate_memories() is experimental and requires LLM client. "
            "It will be integrated into CLI/MCP in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._adapter:
            raise StorageNotConfiguredError()

        from carrymem.layers.semantic_aggregator import SemanticAggregator

        if not hasattr(self, "_llm_client"):
            from carrymem.llm import LLMClient

            self._llm_client = LLMClient(config=self._config or {})
        embedding_fn = None
        if hasattr(self._adapter, "_embedding_model") and self._adapter._embedding_model:
            embedding_fn = lambda text: self._adapter._embedding_model.encode(text).tolist()

        if not embedding_fn:
            logger.warning(
                "aggregate_memories requires vector search to be enabled (no embedding model found)"
            )
            return []

        aggregator = SemanticAggregator(llm_client=self._llm_client, embedding_fn=embedding_fn)

        filters: Dict[str, Any] = {"include_superseded": False}
        if memory_type:
            filters["type"] = memory_type
        memories = self.recall_memories(query="", limit=500, filters=filters)

        if not memories:
            return []

        results = aggregator.aggregate(memories=memories, language=language)

        if store:
            stored_results = []
            for r in results:
                try:
                    entry = MemoryEntry.from_dict(r)
                    stored = self._adapter.remember(entry)
                    stored_results.append(stored.to_dict())
                except Exception as e:
                    logger.warning(f"Failed to store aggregated memory: {e}")
            return stored_results

        return results

    def forget_memory(self, memory_id: str) -> bool:
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_storage_key(memory_id)
        result = self._adapter.forget(memory_id)
        self._auto_backup()
        return result

    def get_stats(self) -> Dict[str, Any]:
        if not self._adapter:
            return {"adapter": None, "total_count": 0}

        return self._adapter.get_stats()

    def declare(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validate_message(message)
        validate_context(context)
        if not self._adapter:
            raise StorageNotConfiguredError()

        result = self._engine.process_message(message, context=context)
        matches = result.get("matches", [])

        if not matches:
            entry = MemoryEntry(
                id="",
                type="user_preference",
                content=message,
                confidence=1.0,
                tier=2,
                source_layer="declaration",
                reasoning="User explicit declaration",
                suggested_action="store",
                metadata={"original_message": message, "source": "declaration"},
            )
            matches = [entry]
        else:
            entries = []
            for m in matches:
                entry = MemoryEntry(
                    id=m.get("id", ""),
                    type=m.get("memory_type") or m.get("type", "unknown"),
                    content=m.get("content", ""),
                    confidence=1.0,
                    tier=m.get("tier", 2),
                    source_layer="declaration",
                    reasoning=(m.get("reasoning") or "") + " (explicit declaration)",
                    suggested_action="store",
                    recall_hint=m.get("recall_hint"),
                    metadata={**m.get("metadata", {}), "source": "declaration"},
                )
                entries.append(entry)
            matches = entries

        stored_memories = []
        storage_keys = []
        for entry in matches:
            stored = self._adapter.remember(entry)
            stored_memories.append(stored.to_dict())
            storage_keys.append(stored.storage_key)

        self._auto_backup()

        return {
            "declared": True,
            "entries": stored_memories,
            "storage_keys": storage_keys,
            "source": "declaration",
            "summary": {
                "total_entries": len(stored_memories),
                "by_type": self._count_by_type(matches),
            },
        }

    def declare_preference(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.declare(message, context)

    def get_memory_profile(self) -> Dict[str, Any]:
        if not self._adapter:
            return {
                "summary": "No storage configured",
                "total_memories": 0,
                "highlights": {},
                "stats": {},
            }

        profile = self._adapter.get_profile()
        return profile

    def whoami(self) -> Dict[str, Any]:
        if not self._adapter:
            return {"identity": "unknown", "summary": "No storage configured"}

        stats = self._adapter.get_stats()
        profile = self._adapter.get_profile()
        total = stats.get("total_count", 0) if isinstance(stats, dict) else 0

        if total == 0:
            return {
                "identity": "new_user",
                "summary": "No memories yet. Start by telling me about yourself.",
                "total_memories": 0,
            }

        by_type = stats.get("by_type", {}) if isinstance(stats, dict) else {}
        profile_stats = profile.get("stats", {}) if isinstance(profile, dict) else {}

        preferences = self.recall_memories(query="", filters={"type": "user_preference"}, limit=10)
        decisions = self.recall_memories(query="", filters={"type": "decision"}, limit=5)
        corrections = self.recall_memories(query="", filters={"type": "correction"}, limit=5)

        pref_list = [m.get("content", "") for m in preferences[:5]]
        decision_list = [m.get("content", "") for m in decisions[:3]]
        correction_list = [m.get("content", "") for m in corrections[:3]]

        top_type = max(by_type, key=by_type.get) if by_type else "unknown"
        conf_avg = profile_stats.get("confidence_avg", 0)

        identity_parts = []
        if pref_list:
            identity_parts.append("Preferences: " + "; ".join(pref_list[:3]))
        if decision_list:
            identity_parts.append("Decisions: " + "; ".join(decision_list[:2]))
        if correction_list:
            identity_parts.append("Corrections: " + "; ".join(correction_list[:2]))

        summary = " | ".join(identity_parts) if identity_parts else f"User with {total} memories"

        # Auto-infer domains from all memories
        all_memories = preferences + decisions + corrections
        domains = infer_domains_from_memories(all_memories)

        return {
            "identity": "known_user",
            "summary": summary,
            "total_memories": total,
            "top_type": top_type,
            "confidence_avg": conf_avg,
            "preferences": pref_list,
            "decisions": decision_list,
            "corrections": correction_list,
            "by_type": by_type,
            "domains": [get_domain_description(d) for d in domains],
        }

    def export_profile(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        whoami = self.whoami()
        profile = self.get_memory_profile()

        export = {
            "schema_version": "1.0.0",
            "format": "carrymem_identity",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "identity": whoami.get("identity", "unknown"),
            "summary": whoami.get("summary", ""),
            "preferences": whoami.get("preferences", []),
            "decisions": whoami.get("decisions", []),
            "corrections": whoami.get("corrections", []),
            "stats": {
                "total_memories": whoami.get("total_memories", 0),
                "top_type": whoami.get("top_type", ""),
                "confidence_avg": whoami.get("confidence_avg", 0),
                "by_type": whoami.get("by_type", {}),
            },
            "profile": profile,
        }

        if output_path:
            output_path = _validate_file_path(output_path)
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=2)

        return export

    def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export memories to a portable format.

        Args:
            output_path: File path to write. If None, returns dict without writing.
            format: Export format ('json' or 'markdown').
            namespace: Export only this namespace. If None, export current namespace.

        Returns:
            Dict with export metadata and data.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()

        if output_path:
            output_path = _validate_file_path(output_path)

        ns = namespace or self._namespace
        stats = self._adapter.get_stats()
        total_count = stats.get("total_count", 0) if isinstance(stats, dict) else 0
        export_limit = max(total_count, 1)

        all_memories = self._adapter.recall("", limit=export_limit)

        if ns != "default" and isinstance(self._adapter, SQLiteAdapter):
            all_memories = self._adapter.recall("", limit=export_limit, namespaces=[ns])

        export_data = {
            "schema_version": "1.0.0",
            "export_format": "carrymem_portable",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "version": _version,
                "namespace": ns,
                "total_memories": len(all_memories),
            },
            "memories": [m.to_dict() for m in all_memories],
        }

        if format == "markdown":
            md_lines = [
                "# CarryMem Memory Export",
                "",
                f"- **Exported**: {export_data['exported_at']}",
                f"- **Namespace**: {ns}",
                f"- **Total memories**: {len(all_memories)}",
                "",
            ]
            by_type: Dict[str, list] = {}
            for m in all_memories:
                d = m.to_dict()
                t = d.get("type", "unknown")
                by_type.setdefault(t, []).append(d)

            for mem_type, items in sorted(by_type.items()):
                md_lines.append(f"## {mem_type}")
                md_lines.append("")
                for item in items:
                    content = item.get("content", "")
                    conf = item.get("confidence", 0)
                    tier = item.get("tier", "?")
                    md_lines.append(f"- [{tier}] {content} (confidence: {conf:.0%})")
                md_lines.append("")

            md_content = "\n".join(md_lines)
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
            return {
                "exported": True,
                "format": "markdown",
                "path": output_path,
                "total_memories": len(all_memories),
                "namespace": ns,
                "content": md_content if not output_path else None,
            }

        json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_content)

        return {
            "exported": True,
            "format": "json",
            "path": output_path,
            "total_memories": len(all_memories),
            "namespace": ns,
            "data": export_data if not output_path else None,
        }

    def import_memories(
        self,
        input_path: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        merge_strategy: str = "skip_existing",
    ) -> Dict[str, Any]:
        """Import memories from a portable format.

        Args:
            input_path: File path to read. If None, uses data parameter.
            data: Direct dict data (alternative to file).
            namespace: Import into this namespace. If None, uses current.
            merge_strategy: 'skip_existing' or 'overwrite'.

        Returns:
            Dict with import results.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()

        if input_path:
            input_path = _validate_file_path(input_path)

        if input_path:
            with open(input_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        elif data:
            import_data = data
        else:
            raise ValueError("Either input_path or data must be provided")

        target_ns = namespace or self._namespace
        memories = import_data.get("memories", [])

        imported = 0
        skipped = 0
        errors = 0

        for mem_dict in memories:
            try:
                content = mem_dict.get("content", "")
                if content:
                    content = _import_validator.validate_content(content, "imported_content")
                content_hash = mem_dict.get("content_hash", "")
                if merge_strategy == "skip_existing" and content_hash:
                    existing = self._adapter.recall(mem_dict.get("content", "")[:50], limit=5)
                    if any(
                        (
                            getattr(e, "content_hash", None) == content_hash
                            or (isinstance(e, dict) and e.get("content_hash") == content_hash)
                            or (
                                hasattr(e, "metadata")
                                and isinstance(e.metadata, dict)
                                and e.metadata.get("content_hash") == content_hash
                            )
                        )
                        for e in existing
                    ):
                        skipped += 1
                        continue

                entry = MemoryEntry(
                    id=mem_dict.get("id", ""),
                    type=mem_dict.get("type", "unknown"),
                    content=content,
                    confidence=mem_dict.get("confidence", 0.5),
                    tier=mem_dict.get("tier", 2),
                    source_layer=mem_dict.get("source_layer", "import"),
                    reasoning=mem_dict.get("reasoning", ""),
                    suggested_action="store",
                    recall_hint=mem_dict.get("recall_hint"),
                    metadata={
                        **mem_dict.get("metadata", {}),
                        "imported_from": import_data.get("source", {}).get("namespace", "unknown"),
                        "imported_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self._adapter.remember(entry)
                imported += 1
            except Exception as e:
                logger.warning(f"Failed to import memory entry: {e}")
                errors += 1

        self._auto_backup()

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "total_processed": len(memories),
            "namespace": target_ns,
            "merge_strategy": merge_strategy,
        }

    def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> Dict[str, Any]:
        return self.prompt_builder.build_context(
            context=context,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_rules=max_rules,
            max_tokens=max_tokens,
            language=language,
        )

    def build_system_prompt(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 4000,
        language: str = "en",
    ) -> str:
        return self.prompt_builder.build_system_prompt(
            context=context,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_rules=max_rules,
            max_tokens=max_tokens,
            language=language,
        )

    def build_qa_prompt(
        self,
        question: str,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
        budget: Optional[Any] = None,
        include_question: bool = True,
    ) -> str:
        return self.prompt_builder.build_qa_prompt(
            question=question,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_tokens=max_tokens,
            language=language,
            budget=budget,
            include_question=include_question,
        )

    def check_conflicts(self) -> List[Dict[str, Any]]:
        from carrymem.conflict_detector import ConflictDetector

        if not self._adapter:
            raise StorageNotConfiguredError()

        all_conflicts: List[Dict[str, Any]] = []

        all_memories = self._adapter.recall("", limit=10000)
        if all_memories:
            detector = ConflictDetector()
            memory_conflicts = detector.detect_conflicts(all_memories)
            all_conflicts.extend(c.to_dict() for c in memory_conflicts)

        if self._rule_engine:
            rule_conflicts = self._rule_engine.check_conflicts()
            for rc in rule_conflicts:
                all_conflicts.append(
                    {
                        "conflict_type": rc.conflict_type.value,
                        "severity": rc.severity.value,
                        "reason": rc.reason,
                        "suggestion": rc.suggestion,
                        "rules": [
                            {"id": r.id, "trigger": r.trigger, "action": r.action, "scope": r.scope}
                            for r in rc.rules
                        ],
                        "source": "rule_engine",
                    }
                )

        return all_conflicts

    def check_quality(self, min_score: float = 0.3) -> List[Dict[str, Any]]:
        from carrymem.quality_scorer import QualityAnalyzer

        if not self._adapter:
            raise StorageNotConfiguredError()

        all_memories = self._adapter.recall("", limit=10000)
        if not all_memories:
            return []

        analyzer = QualityAnalyzer()
        low_quality = analyzer.identify_low_quality(all_memories, threshold=min_score)
        result = []
        for item in low_quality:
            result.append(
                {
                    "storage_key": item["storage_key"],
                    "score": item["score"],
                    "reasons": item["reasons"],
                    "content": item["memory"].content[:80],
                    "type": item["memory"].type,
                }
            )
        return result

    def list_expired(self) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            return []

        from datetime import datetime, timezone

        conn = self._adapter._get_connection()
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = conn.execute(
            "SELECT storage_key, content, type, expires_at FROM memories "
            "WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at < ?",
            (self._namespace, now_iso),
        ).fetchall()

        result = []
        for row in rows:
            content = row["content"]
            if self._adapter._encryption and self._adapter._encryption.is_active:
                content = self._adapter._decrypt_field(content)
            result.append(
                {
                    "storage_key": row["storage_key"],
                    "content": (content or "")[:80],
                    "type": row["type"],
                    "expires_at": row["expires_at"],
                }
            )
        return result

    def consolidate(
        self, dry_run: bool = True, run_p1: bool = True, run_p2: bool = True
    ) -> Dict[str, Any]:
        """Run memory consolidation: dedup, decay, and cleanup.

        Args:
            dry_run: If True, only report what would be done without making changes.
            run_p1: If True, also run P1 pattern recognition + auto-promotion.
            run_p2: If True, also run P2 semantic consolidation (borrow-host LLM).

        Returns:
            Consolidation report with to_supersede, to_decay, to_forget lists,
            and optionally p1_promotion and p2_consolidation results.
        """
        from carrymem.consolidation import consolidate, consolidate_p1, consolidate_p2

        if not self._adapter:
            raise StorageNotConfiguredError()
        adapter = self._adapter

        all_entries = adapter.recall(
            query="",
            limit=10000,
            filters={"include_superseded": True},
        )
        all_memories = []
        for entry in all_entries:
            if hasattr(entry, "__dict__"):
                all_memories.append(
                    {
                        "storage_key": getattr(entry, "storage_key", ""),
                        "type": getattr(entry, "memory_type", ""),
                        "content": getattr(entry, "content", ""),
                        "confidence": getattr(entry, "confidence", 0.5),
                        "created_at": getattr(entry, "created_at", ""),
                        "superseded_at": getattr(entry, "superseded_at", None),
                        "access_count": getattr(entry, "access_count", 0),
                    }
                )
            elif isinstance(entry, dict):
                all_memories.append(entry)

        report = consolidate(all_memories)

        if dry_run:
            report["dry_run"] = True
            return report

        superseded_count = 0
        for item in report["to_supersede"]:
            older_key = item.get("older_key")
            if older_key:
                try:
                    if hasattr(adapter, "supersede"):
                        adapter.supersede(older_key)
                        superseded_count += 1
                except Exception as e:
                    logger.warning(f"Failed to supersede {older_key}: {e}")

        forgotten_count = 0
        for item in report["to_forget"]:
            key = item.get("storage_key")
            if key:
                try:
                    adapter.forget(key)
                    forgotten_count += 1
                except Exception as e:
                    logger.warning(f"Failed to forget {key}: {e}")

        for item in report["to_decay"]:
            key = item.get("storage_key")
            decay = item.get("decay", 1.0)
            current_conf = item.get("current_confidence", 0.5)
            new_conf = round(current_conf * decay, 3)
            if new_conf < 0.1:
                try:
                    adapter.forget(key)
                    forgotten_count += 1
                except Exception as e:
                    logger.warning(f"Failed to forget decayed {key}: {e}")

        report["dry_run"] = False
        report["superseded_count"] = superseded_count
        report["forgotten_count"] = forgotten_count

        logger.info(
            f"Consolidation complete: {superseded_count} superseded, "
            f"{forgotten_count} forgotten, {len(report['to_decay'])} decayed"
        )

        if run_p1:
            rule_storage = None
            try:
                from carrymem.rules.storage import RuleStorage

                db_path = getattr(self._adapter, "db_path", None)
                rule_storage = RuleStorage(db_path=db_path) if db_path else None
            except Exception as e:
                logger.warning(f"P1 skipped: RuleStorage init failed: {e}")

            p1_result = consolidate_p1(
                memories=all_memories,
                rule_storage=rule_storage,
                auto_accept=False,
            )
            report["p1_promotion"] = p1_result

        if run_p2:
            p2_result = consolidate_p2(
                memories=all_memories,
                p0_report=report,
            )
            report["p2_consolidation"] = p2_result

        return report

    # --- Scheduled Consolidation ---

    _consolidation_timer: Optional[Any] = None  # class-level timer reference

    def schedule_consolidation(
        self,
        interval_hours: float = 1.0,
        dry_run: bool = False,
        run_p1: bool = True,
        run_p2: bool = False,
    ) -> Dict[str, Any]:
        """Start periodic memory consolidation on a background timer.

        Uses threading.Timer for lightweight scheduling (no external dependencies).
        Only one scheduled consolidation can run at a time; calling again replaces
        the previous schedule.

        Args:
            interval_hours: Hours between consolidation runs (minimum 0.1 = 6 min).
            dry_run: If True, consolidation only reports without making changes.
            run_p1: If True, also run P1 pattern recognition.
            run_p2: If True, also run P2 semantic consolidation.

        Returns:
            Dict with schedule status.
        """
        import threading

        min_interval = 0.1  # 6 minutes minimum
        if interval_hours < min_interval:
            interval_hours = min_interval

        # Stop existing timer if any
        self.stop_consolidation()

        interval_sec = interval_hours * 3600
        status = {
            "scheduled": True,
            "interval_hours": interval_hours,
            "dry_run": dry_run,
            "run_p1": run_p1,
            "run_p2": run_p2,
        }

        def _run_consolidation():
            try:
                logger.info(f"Scheduled consolidation starting (interval={interval_hours}h)")
                result = self.consolidate(dry_run=dry_run, run_p1=run_p1, run_p2=run_p2)
                logger.info(
                    f"Scheduled consolidation complete: "
                    f"{result.get('superseded_count', 0)} superseded, "
                    f"{result.get('forgotten_count', 0)} forgotten"
                )
            except Exception as e:
                logger.error(f"Scheduled consolidation failed: {e}")
            finally:
                # Schedule next run
                if self._consolidation_timer is not None:
                    self._consolidation_timer = threading.Timer(interval_sec, _run_consolidation)
                    self._consolidation_timer.daemon = True
                    self._consolidation_timer.start()

        # Start first timer
        self._consolidation_timer = threading.Timer(interval_sec, _run_consolidation)
        self._consolidation_timer.daemon = True
        self._consolidation_timer.start()

        logger.info(f"Consolidation scheduled every {interval_hours}h")
        return status

    def stop_consolidation(self) -> Dict[str, Any]:
        """Stop the scheduled consolidation timer.

        Returns:
            Dict with stopped status.
        """
        if self._consolidation_timer is not None:
            self._consolidation_timer.cancel()
            self._consolidation_timer = None
            logger.info("Consolidation schedule stopped")
            return {"stopped": True}
        return {"stopped": False, "reason": "no_active_schedule"}

    def _count_by_type(self, entries: List[MemoryEntry]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in entries:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts
