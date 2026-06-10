"""Memory CRUD: classify_and_remember, declare, forget, update, merge, etc."""

from typing import Any, Dict, List, Optional

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.core._lifecycle import StorageNotConfiguredError
from carrymem.utils.validators import (
    validate_context,
    validate_language,
    validate_message,
    validate_storage_key,
)


class MemoryCRUDMixin:
    """Core CRUD operations for memories: remember, declare, forget, update, history, merge."""

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
        classify_result = self._classify_message(resolved_message, context, language, force_type, message)
        if isinstance(classify_result, list) and len(classify_result) == 0:
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

    def forget_memory(self, memory_id: str) -> bool:
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_storage_key(memory_id)
        result = self._adapter.forget(memory_id)
        self._auto_backup()
        return result

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
