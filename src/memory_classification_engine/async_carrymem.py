"""Async API wrapper for CarryMem.

v0.7.0: Async interface for high-concurrency scenarios.

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
from typing import Any, Dict, List, Optional

from .carrymem import CarryMem
from .adapters.base import StorageAdapter


class AsyncCarryMem:
    """Async wrapper around CarryMem."""

    def __init__(
        self,
        storage: Optional[Any] = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict] = None,
        encryption_key: Optional[str] = None,
    ):
        self._sync = CarryMem(
            storage=storage,
            db_path=db_path,
            knowledge_adapter=knowledge_adapter,
            namespace=namespace,
            config=config,
            encryption_key=encryption_key,
        )
        self._loop = asyncio.get_event_loop()

    async def _run(self, func, *args, **kwargs):
        return await self._loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def classify_message(
        self,
        message: str,
        context: Optional[Dict] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run(self._sync.classify_message, message, context, language)

    async def classify_and_remember(
        self,
        message: str,
        context: Optional[Dict] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run(self._sync.classify_and_remember, message, context, language)

    async def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return await self._run(self._sync.recall_memories, query, filters, limit)

    async def forget_memory(self, memory_id: str) -> bool:
        return await self._run(self._sync.forget_memory, memory_id)

    async def get_stats(self) -> Dict[str, Any]:
        return await self._run(self._sync.get_stats)

    async def declare(
        self,
        message: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        return await self._run(self._sync.declare, message, context)

    async def get_memory_profile(self) -> Dict[str, Any]:
        return await self._run(self._sync.get_memory_profile)

    async def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> Dict[str, Any]:
        return await self._run(
            self._sync.build_context, context, max_memories, max_knowledge, max_rules, max_tokens, language
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
        return await self._run(
            self._sync.build_system_prompt, context, max_memories, max_knowledge, max_tokens, language
        )

    async def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run(self._sync.export_memories, output_path, format, namespace)

    async def import_memories(
        self,
        input_path: Optional[str] = None,
        data: Optional[Dict] = None,
        namespace: Optional[str] = None,
        merge_strategy: str = "skip_existing",
    ) -> Dict[str, Any]:
        return await self._run(self._sync.import_memories, input_path, data, namespace, merge_strategy)

    async def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run(self._sync.update_memory, storage_key, new_content, reason)

    async def get_memory_history(self, storage_key: str) -> List[Dict[str, Any]]:
        return await self._run(self._sync.get_memory_history, storage_key)

    async def rollback_memory(self, storage_key: str, version: int) -> Dict[str, Any]:
        return await self._run(self._sync.rollback_memory, storage_key, version)

    async def backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        return await self._run(self._sync.backup, backup_dir)

    async def get_audit_log(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self._run(self._sync.get_audit_log, operation, since, until, source, limit)

    async def close(self):
        await self._run(self._sync.close)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
