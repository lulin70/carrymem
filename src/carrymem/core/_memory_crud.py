"""Memory CRUD: classify_and_remember, declare, forget, update, merge, etc."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.constants import BATCH_RECALL_LIMIT, MAX_MESSAGE_LENGTH
from carrymem.core._lifecycle import StorageNotConfiguredError
from carrymem.exceptions import ClassificationError, ValidationError
from carrymem.types import (
    ClassificationResult,
    DeclareResult,
    MergeMemoriesResult,
    RollbackMemoryResult,
    UpdateMemoryResult,
)
from carrymem.utils.validators import (
    validate_context,
    validate_language,
    validate_message,
    validate_storage_key,
)

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter
    from carrymem.engine import MemoryClassificationEngine

logger = logging.getLogger(__name__)


class MemoryCRUDMixin:
    """Core CRUD operations for memories: remember, declare, forget, update, history, merge."""

    # Shared instance state provided by LifecycleMixin.__init__.
    _adapter: Optional[StorageAdapter]
    _engine: MemoryClassificationEngine
    _namespace: str

    # ── Permission helpers (P1-8 MVP) ──────────────────────────────

    def _check_write_permission(self, user_id: Optional[str] = None) -> None:
        """Raise SecurityError(CM-403) if user lacks WRITE permission."""
        policy = self._access_policy  # type: ignore[attr-defined]
        if policy is not None and user_id is not None:
            from carrymem.security.permissions import Permission

            policy.require(user_id, Permission.WRITE, resource="memory write")

    def _check_delete_permission(self, user_id: Optional[str] = None) -> None:
        """Raise SecurityError(CM-403) if user lacks DELETE permission."""
        policy = self._access_policy  # type: ignore[attr-defined]
        if policy is not None and user_id is not None:
            from carrymem.security.permissions import Permission

            policy.require(user_id, Permission.DELETE, resource="memory delete")

    def classify_and_remember(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        session_id: Optional[str] = None,
        force_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a message and persist the resulting memory entries."""
        self._check_write_permission(user_id)

        # Validate input BEFORE checking storage adapter so that invalid
        # messages (empty / too long) raise ValidationError regardless of
        # whether a storage adapter is configured.
        validate_message(message, max_length=MAX_MESSAGE_LENGTH)

        if not self._adapter:
            raise StorageNotConfiguredError()

        # 1. Validate & resolve (coreference + redaction check)
        resolved_message, should_continue, redact_result, coreference_resolved = (
            self._validate_and_resolve(  # type: ignore[attr-defined]
                message, context, force_type, session_id
            )
        )
        if not should_continue:
            return {
                "stored": False,
                "should_remember": False,
                "entries": [],
                "storage_keys": [],
                "type": "auto_redacted",
                "content": str(message)[:100] if message else "",
                "error": redact_result or "Blocked by redaction",  # type: ignore[typeddict-unknown-key]
                "summary": {  # type: ignore[typeddict-item]
                    "redacted": True,
                    "redact_reason": redact_result or "Sensitive content detected",
                },
            }

        # 2. Classify
        try:
            classify_result = self._classify_message(  # type: ignore[attr-defined]
                resolved_message, context, language, force_type, message
            )
        except ClassificationError as e:
            logger.warning("Classification failed: %s", e)
            return {
                "stored": False,
                "should_remember": False,
                "entries": [],
                "storage_keys": [],
                "type": "unknown",
                "content": message,
                "error": str(e),  # type: ignore[typeddict-unknown-key]
            }
        if isinstance(classify_result, list) and len(classify_result) == 0:
            base_result = self.classify_message(resolved_message, context=context, language=language)
            return {
                **base_result,
                "stored": False,
                "storage_keys": [],
            }

        # 3. Store & post-process (with audit logging)
        try:
            result = self._store_entries(  # type: ignore[attr-defined]
                classify_result,
                resolved_message,
                message,
                context,
                coreference_resolved,
                force_type,
                session_id,
            )
            if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
                self._adapter._audit.log_operation(
                    "remember",
                    storage_key=result.get("storage_keys", [None])[0] if result.get("storage_keys") else None,
                    memory_type=classify_result.get("memory_type") if isinstance(classify_result, dict) else None,
                    success=True,
                    details={"message_preview": message[:100]},
                )
            return result  # type: ignore[no-any-return]
        except Exception as exc:
            if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
                self._adapter._audit.log_operation(
                    "remember",
                    success=False,
                    details={"error": str(exc), "message_preview": message[:100]},
                )
            raise

    def classify_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify a message into memory entries without persisting."""
        validate_message(message, max_length=MAX_MESSAGE_LENGTH)
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
            entry.memory_nature = entry.infer_memory_nature()
            entries.append(entry)

        return {
            "should_remember": len(entries) > 0,
            "entries": [e.to_dict() for e in entries],  # type: ignore[misc]
            "summary": {
                "total_entries": len(entries),
                "by_type": self._count_by_type(entries),  # type: ignore[attr-defined]
            },
        }

    def declare(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> DeclareResult:
        """Explicitly declare and store a message as a memory."""
        self._check_write_permission(user_id)

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

        self._auto_backup()  # type: ignore[attr-defined]

        if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
            self._adapter._audit.log_operation(
                "declare",
                storage_key=storage_keys[0] if storage_keys else None,
                success=True,
                details={"storage_keys": storage_keys},
            )

        return {
            "declared": True,
            "entries": stored_memories,  # type: ignore[typeddict-item]
            "storage_keys": storage_keys,
            "source": "declaration",
            "summary": {
                "total_entries": len(stored_memories),
                "by_type": self._count_by_type(matches),  # type: ignore[attr-defined]
            },
        }

    def declare_preference(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> DeclareResult:
        """Alias for :meth:`declare` storing a user preference."""
        return self.declare(message, context, user_id=user_id)

    def forget_memory(self, memory_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a memory by its storage key."""
        self._check_delete_permission(user_id)

        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_storage_key(memory_id)
        result = self._adapter.forget(memory_id)
        self._auto_backup()  # type: ignore[attr-defined]

        if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
            self._adapter._audit.log_operation(
                "forget",
                storage_key=memory_id,
                success=result,
            )
        return result

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> UpdateMemoryResult:
        """Update a memory's content, creating a new version."""
        self._check_write_permission(user_id)

        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        result = self._adapter.update_memory(storage_key, new_content, reason)
        if result is None:
            if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
                self._adapter._audit.log_operation(
                    "update",
                    storage_key=storage_key,
                    success=False,
                    details={"error": "not found"},
                )
            return {"updated": False, "error": f"Memory not found: {storage_key}"}

        if self._adapter._cache:
            self._adapter._cache.invalidate()

        self._auto_backup()  # type: ignore[attr-defined]

        if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
            self._adapter._audit.log_operation(
                "update",
                storage_key=storage_key,
                success=True,
                details={"version": result.version},
            )

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
        """Return the version history for a memory."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        return self._adapter.get_memory_history(storage_key)

    def rollback_memory(
        self,
        storage_key: str,
        version: int,
    ) -> RollbackMemoryResult:
        """Roll a memory back to a previous version."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        result = self._adapter.rollback_memory(storage_key, version)
        if result is None:
            return {"rolled_back": False, "error": "Memory or version not found"}

        if self._adapter._cache:
            self._adapter._cache.invalidate()

        self._auto_backup()  # type: ignore[attr-defined]

        return {
            "rolled_back": True,
            "storage_key": result.storage_key,
            "version": result.version,
            "content": result.content,
        }

    def merge_memories(
        self,
        namespaces: Optional[List[str]] = None,
        strategy: str = "latest_wins",
        conflict_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> MergeMemoriesResult:
        """Merge memories across namespaces, removing duplicates."""
        from carrymem.merge import merge_memories as _merge

        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Merge only supported with SQLiteAdapter"}

        ns_list = namespaces or [self._namespace]
        all_memories = []
        for ns in ns_list:
            results = self._adapter.recall("", limit=BATCH_RECALL_LIMIT, namespaces=[ns])
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
