"""Async API wrapper for CarryMem.

Async interface for high-concurrency scenarios.

Design:
- Wraps synchronous CarryMem methods with asyncio.run_in_executor
- Same API signatures, but all methods are async
- Zero additional dependencies (uses only asyncio standard library)

Usage:
    async_carrymem = AsyncCarryMem(storage="sqlite")
    result = await async_carrymem.classify_and_remember("I prefer dark mode")
    memories = await async_carrymem.recall_memories(query="dark mode")
"""

import asyncio
from typing import Any, Dict, List, Optional, Union

from .adapters.base import StorageAdapter
from .carrymem import CarryMem


class AsyncCarryMem:
    """Async CarryMem with native async adapter support (v0.7.2).

    Mode 1 (default): Wraps sync CarryMem with run_in_executor (zero deps).
    Mode 2 (native): Uses AsyncSQLiteAdapter for true async I/O (requires [async]).
    """

    def __init__(
        self,
        storage: Optional[Union[str, StorageAdapter]] = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict] = None,
        encryption_key: Optional[str] = None,
        native_async: bool = False,
    ):
        self._native_async = native_async
        self._async_adapter = None

        if native_async:
            from .adapters.async_sqlite import AsyncSQLiteAdapter

            self._async_adapter = AsyncSQLiteAdapter(
                db_path=db_path,
                namespace=namespace,
                encryption_key=encryption_key,
            )
            self._sync = None
        else:
            self._sync = CarryMem(
                storage=storage,
                db_path=db_path,
                knowledge_adapter=knowledge_adapter,
                namespace=namespace,
                config=config,
                encryption_key=encryption_key,
            )

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _require_sync(self) -> CarryMem:
        """Return the sync CarryMem instance, raising if native_async mode is active."""
        if self._sync is None:
            raise RuntimeError("Sync methods require native_async=False mode")
        return self._sync

    async def connect(self) -> None:
        """Connect the async adapter (native_async mode only, v0.7.2)."""
        if self._native_async and self._async_adapter:
            await self._async_adapter.connect()

    async def store_entry(self, entry) -> Any:
        """Store a MemoryEntry directly via async adapter (v0.7.2 native_async mode)."""
        if not self._native_async or not self._async_adapter:
            raise RuntimeError("store_entry requires native_async=True mode")
        return await self._async_adapter.store_entry(entry)

    async def recall_async(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Recall via async adapter (v0.7.2 native_async mode)."""
        if not self._native_async or not self._async_adapter:
            raise RuntimeError("recall_async requires native_async=True mode")
        return await self._async_adapter.recall(query, limit=limit)

    async def count_async(self) -> int:
        """Count memories via async adapter (v0.7.2 native_async mode)."""
        if not self._native_async or not self._async_adapter:
            raise RuntimeError("count_async requires native_async=True mode")
        return await self._async_adapter.count()

    async def classify_message(
        self,
        message: str,
        context: Optional[Dict] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a message into memory type (noise/preference/fact/etc.)."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().classify_message, message, context, language
        )

    async def classify_and_remember(
        self,
        message: str,
        context: Optional[Dict] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a message and persist the result as a memory."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().classify_and_remember, message, context, language
        )

    async def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories matching the query and optional filters."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().recall_memories, query, filters, limit
        )

    async def forget_memory(self, memory_id: str) -> bool:
        """Delete a memory entry by its ID."""
        return await self._run(self._require_sync().forget_memory, memory_id)  # type: ignore[no-any-return]

    async def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics for stored memories."""
        return await self._run(self._require_sync().get_stats)  # type: ignore[no-any-return]

    async def declare(
        self,
        message: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Explicitly declare a preference/fact/decision from the message."""
        return await self._run(self._require_sync().declare, message, context)  # type: ignore[no-any-return]

    async def get_memory_profile(self) -> Dict[str, Any]:
        """Return the user's consolidated memory profile."""
        return await self._run(self._require_sync().get_memory_profile)  # type: ignore[no-any-return]

    async def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Build a structured context payload from memories, knowledge, and rules."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().build_context,
            context,
            max_memories,
            max_knowledge,
            max_rules,
            max_tokens,
            language,
        )

    async def build_system_prompt(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> str:
        """Build a ready-to-use system prompt string from memories and knowledge."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().build_system_prompt,
            context,
            max_memories,
            max_knowledge,
            max_tokens,
            language,
        )

    async def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export memories to a file or return them as a dict."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().export_memories, output_path, format, namespace
        )

    async def import_memories(
        self,
        input_path: Optional[str] = None,
        data: Optional[Dict] = None,
        namespace: Optional[str] = None,
        merge_strategy: str = "skip_existing",
    ) -> Dict[str, Any]:
        """Import memories from a file or dict using a merge strategy."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().import_memories, input_path, data, namespace, merge_strategy
        )

    async def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing memory entry, recording the reason."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().update_memory, storage_key, new_content, reason
        )

    async def get_memory_history(self, storage_key: str) -> List[Dict[str, Any]]:
        """Return the version history of a memory entry."""
        return await self._run(self._require_sync().get_memory_history, storage_key)  # type: ignore[no-any-return]

    async def rollback_memory(self, storage_key: str, version: int) -> Dict[str, Any]:
        """Roll back a memory entry to a specific version."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().rollback_memory, storage_key, version
        )

    async def backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """Create a backup of the memory store to a directory."""
        return await self._run(self._require_sync().backup, backup_dir)  # type: ignore[no-any-return]

    async def get_audit_log(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve filtered audit log entries."""
        return await self._run(  # type: ignore[no-any-return]
            self._require_sync().get_audit_log, operation, since, until, source, limit
        )

    async def close(self):
        """Close the underlying CarryMem or async adapter."""
        if self._native_async and self._async_adapter:
            await self._async_adapter.close()
        elif self._sync:
            await self._run(self._require_sync().close)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
