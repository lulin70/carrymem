"""Test suite for AsyncSQLiteAdapter (v0.7.2 native async I/O).

Covers all test dimensions per DevSquad Iron Rules:
  - Happy Path: connect, store_entry, recall, forget_memory, count, close
  - Boundary: empty results, nonexistent namespace, duplicate keys, large content
  - Error Cases: not connected, operations before connect, close idempotent
  - Performance: bulk store, bulk recall
  - Configuration: custom namespace, custom db_path, in-memory mode
  - Integration: AsyncCarryMem native_async mode, async context manager

Uses real aiosqlite (in-memory) per testing philosophy.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from datetime import timezone

import pytest

from carrymem.adapters.async_sqlite import AsyncSQLiteAdapter
from carrymem.adapters.base import MemoryEntry

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def async_adapter() -> AsyncSQLiteAdapter:
    """In-memory AsyncSQLiteAdapter (not yet connected)."""
    return AsyncSQLiteAdapter(":memory:", namespace="default")


@pytest.fixture
async def connected_adapter(async_adapter: AsyncSQLiteAdapter) -> AsyncSQLiteAdapter:
    """Connected in-memory AsyncSQLiteAdapter."""
    await async_adapter.connect()
    return async_adapter


@pytest.fixture
def sample_entry() -> MemoryEntry:
    """Sample MemoryEntry for testing."""
    return MemoryEntry(
        id="test1",
        type="user_preference",
        content="I prefer dark mode",
        raw_text="I prefer dark mode",
        confidence=0.9,
    )


# ── Happy Path (6 tests) ──────────────────────────────────────────────────


class TestHappyPath:
    """Verify: normal usage of AsyncSQLiteAdapter."""

    async def test_connect_succeeds(self, async_adapter):
        """Verify: connect opens connection and initializes schema."""
        await async_adapter.connect()
        assert async_adapter._connected is True
        assert async_adapter._conn is not None

    async def test_store_entry_returns_stored_memory(self, connected_adapter, sample_entry):
        """Verify: store_entry returns StoredMemory with storage_key."""
        stored = await connected_adapter.store_entry(sample_entry)
        assert stored is not None
        assert stored.storage_key is not None
        assert stored.id == "test1"
        assert stored.content == "I prefer dark mode"

    async def test_recall_returns_matching_memories(self, connected_adapter, sample_entry):
        """Verify: recall retrieves stored memories by FTS5."""
        await connected_adapter.store_entry(sample_entry)
        results = await connected_adapter.recall("dark mode")
        assert isinstance(results, list)
        assert len(results) >= 1
        assert any(r["content"] == "I prefer dark mode" for r in results)

    async def test_forget_memory_deletes_entry(self, connected_adapter, sample_entry):
        """Verify: forget_memory removes a memory by storage_key."""
        stored = await connected_adapter.store_entry(sample_entry)
        deleted = await connected_adapter.forget_memory(stored.storage_key)
        assert deleted is True
        count = await connected_adapter.count()
        assert count == 0

    async def test_count_returns_correct_number(self, connected_adapter):
        """Verify: count returns the number of stored memories."""
        for i in range(3):
            entry = MemoryEntry(
                id=f"c{i}",
                type="fact_declaration",
                content=f"Fact number {i}",
                raw_text=f"Fact number {i}",
                confidence=0.5,
            )
            await connected_adapter.store_entry(entry)
        count = await connected_adapter.count()
        assert count == 3

    async def test_close_releases_connection(self, connected_adapter):
        """Verify: close releases the database connection."""
        await connected_adapter.close()
        assert connected_adapter._conn is None
        assert connected_adapter._connected is False


# ── Boundary (6 tests) ───────────────────────────────────────────────────


class TestBoundary:
    """Verify: edge cases and boundary conditions."""

    async def test_recall_empty_database_returns_empty_list(self, connected_adapter):
        """Verify: recall on empty database returns empty list."""
        results = await connected_adapter.recall("anything")
        assert results == []

    async def test_count_nonexistent_namespace_returns_zero(self, connected_adapter, sample_entry):
        """Verify: count on nonexistent namespace returns 0."""
        await connected_adapter.store_entry(sample_entry)
        count = await connected_adapter.count(namespace="other_namespace")
        assert count == 0

    async def test_recall_nonexistent_namespace_returns_empty(self, connected_adapter, sample_entry):
        """Verify: recall on nonexistent namespace returns empty list."""
        await connected_adapter.store_entry(sample_entry)
        results = await connected_adapter.recall("dark", namespaces=["other_namespace"])
        assert results == []

    async def test_forget_memory_nonexistent_key_returns_false(self, connected_adapter):
        """Verify: forget_memory with nonexistent key returns False."""
        deleted = await connected_adapter.forget_memory("nonexistent_key_12345")
        assert deleted is False

    async def test_store_entry_large_content(self, connected_adapter):
        """Verify: store_entry handles large content."""
        large_content = "A" * 10000
        entry = MemoryEntry(
            id="large1",
            type="fact_declaration",
            content=large_content,
            raw_text=large_content,
            confidence=0.5,
        )
        stored = await connected_adapter.store_entry(entry)
        assert stored.storage_key is not None
        count = await connected_adapter.count()
        assert count == 1

    async def test_multiple_namespaces_isolated(self, async_adapter):
        """Verify: memories in different namespaces are isolated."""
        await async_adapter.connect()
        entry1 = MemoryEntry(
            id="ns1_1", type="fact_declaration", content="Alpha fact", raw_text="Alpha fact", confidence=0.5
        )
        entry2 = MemoryEntry(
            id="ns2_1", type="fact_declaration", content="Beta fact", raw_text="Beta fact", confidence=0.5
        )
        await async_adapter.store_entry(entry1)
        async_adapter._namespace = "ns2"
        await async_adapter.store_entry(entry2)

        assert await async_adapter.count(namespace="default") == 1
        assert await async_adapter.count(namespace="ns2") == 1


# ── Error Cases (6 tests) ────────────────────────────────────────────────


class TestErrorCases:
    """Verify: error handling and invalid inputs."""

    async def test_store_entry_before_connect_raises(self, async_adapter, sample_entry):
        """Verify: store_entry without connect raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            await async_adapter.store_entry(sample_entry)

    async def test_recall_before_connect_raises(self, async_adapter):
        """Verify: recall without connect raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            await async_adapter.recall("query")

    async def test_forget_memory_before_connect_raises(self, async_adapter):
        """Verify: forget_memory without connect raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            await async_adapter.forget_memory("key")

    async def test_count_before_connect_raises(self, async_adapter):
        """Verify: count without connect raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            await async_adapter.count()

    async def test_close_idempotent(self, async_adapter):
        """Verify: closing an already-closed adapter does not raise."""
        await async_adapter.connect()
        await async_adapter.close()
        # Second close should be safe
        await async_adapter.close()
        assert async_adapter._conn is None

    async def test_connect_idempotent(self, async_adapter):
        """Verify: calling connect twice does not reopen connection."""
        await async_adapter.connect()
        first_conn = async_adapter._conn
        await async_adapter.connect()
        assert async_adapter._conn is first_conn


# ── Performance (2 tests) ────────────────────────────────────────────────


class TestPerformance:
    """Verify: performance baselines for async operations."""

    async def test_bulk_store_performance(self, connected_adapter):
        """Verify: storing 100 entries completes under 2 seconds."""
        t0 = time.perf_counter()
        for i in range(100):
            entry = MemoryEntry(
                id=f"bulk_{i}",
                type="fact_declaration",
                content=f"Bulk fact number {i}",
                raw_text=f"Bulk fact number {i}",
                confidence=0.5,
            )
            await connected_adapter.store_entry(entry)
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"Bulk store took {elapsed:.2f}s (>2s)"
        count = await connected_adapter.count()
        assert count == 100

    async def test_bulk_recall_performance(self, connected_adapter):
        """Verify: recall on 100-entry database completes under 500ms."""
        for i in range(100):
            entry = MemoryEntry(
                id=f"recall_{i}",
                type="fact_declaration",
                content=f"Searchable fact {i}",
                raw_text=f"Searchable fact {i}",
                confidence=0.5,
            )
            await connected_adapter.store_entry(entry)

        t0 = time.perf_counter()
        results = await connected_adapter.recall("searchable")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 500, f"Bulk recall took {elapsed_ms:.1f}ms (>500ms)"
        assert len(results) > 0


# ── Configuration (2 tests) ──────────────────────────────────────────────


class TestConfiguration:
    """Verify: configuration options."""

    async def test_custom_namespace(self):
        """Verify: adapter uses custom namespace."""
        adapter = AsyncSQLiteAdapter(":memory:", namespace="custom_ns")
        assert adapter.namespace == "custom_ns"
        await adapter.connect()
        entry = MemoryEntry(
            id="ns_test", type="fact_declaration", content="Namespaced", raw_text="Namespaced", confidence=0.5
        )
        await adapter.store_entry(entry)
        assert await adapter.count() == 1
        assert await adapter.count(namespace="default") == 0
        await adapter.close()

    async def test_file_based_db_path(self):
        """Verify: adapter works with file-based database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            adapter = AsyncSQLiteAdapter(db_path, namespace="default")
            await adapter.connect()
            entry = MemoryEntry(
                id="file_test", type="fact_declaration", content="File based", raw_text="File based", confidence=0.5
            )
            await adapter.store_entry(entry)
            assert await adapter.count() == 1
            await adapter.close()
            assert os.path.exists(db_path)


# ── Integration (4 tests) ────────────────────────────────────────────────


class TestIntegration:
    """Verify: integration with AsyncCarryMem and async patterns."""

    async def test_async_carrymem_native_async_mode(self):
        """Verify: AsyncCarryMem native_async mode uses AsyncSQLiteAdapter."""
        from carrymem.async_carrymem import AsyncCarryMem

        acm = AsyncCarryMem(storage="sqlite", db_path=":memory:", namespace="default", native_async=True)
        assert acm._native_async is True
        assert acm._async_adapter is not None
        assert acm._sync is None

        await acm.connect()
        entry = MemoryEntry(
            id="acm_test", type="fact_declaration", content="Async CarryMem", raw_text="Async CarryMem", confidence=0.5
        )
        stored = await acm.store_entry(entry)
        assert stored.storage_key is not None

        count = await acm.count_async()
        assert count == 1

        results = await acm.recall_async("Async")
        assert len(results) >= 1
        await acm.close()

    async def test_async_carrymem_native_async_requires_flag(self):
        """Verify: native async methods raise without native_async=True."""
        from carrymem.async_carrymem import AsyncCarryMem

        acm = AsyncCarryMem(storage="sqlite", db_path=":memory:", namespace="default", native_async=False)
        with pytest.raises(RuntimeError, match="native_async"):
            await acm.store_entry(
                MemoryEntry(id="x", type="fact_declaration", content="x", raw_text="x", confidence=0.5)
            )

    async def test_async_context_manager(self):
        """Verify: async context manager protocol works."""
        adapter = AsyncSQLiteAdapter(":memory:", namespace="default")
        async with adapter as a:
            assert a._connected is True
            entry = MemoryEntry(
                id="ctx_test", type="fact_declaration", content="Context", raw_text="Context", confidence=0.5
            )
            await a.store_entry(entry)
            assert await a.count() == 1
        # After context exit, adapter should be closed
        assert adapter._conn is None

    async def test_capabilities_property(self, async_adapter):
        """Verify: capabilities property returns expected dict."""
        caps = async_adapter.capabilities
        assert isinstance(caps, dict)
        assert caps.get("async") is True
        assert caps.get("fts") is True
        assert caps.get("vector_search") is False
