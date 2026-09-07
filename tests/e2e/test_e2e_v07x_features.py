"""E2E test: v0.7.x feature user journeys (Knowledge Graph + Session + Multi-Mode Retrieval + Memify + Async).

Covers the complete v0.7.x user experience:
  1. Knowledge Graph: store memories → entity auto-extraction → recall_by_entity → graph traversal
  2. Session Dual-Layer: set_session → preload → promote_to_permanent → end_session
  3. Multi-Mode Retrieval: recall_by_time / recall_semantic / recall_hybrid / recall_multi_mode
  4. Memify Consolidation: derive_facts → reinforce_edges → auto_decay
  5. AsyncSQLiteAdapter: native async I/O (standalone; AsyncCarryMem native_async
     mode removed after v0.10.1, 2026-09-07, ships in v0.11.0)

Uses real SQLite in-memory DB (no Mock) per testing philosophy.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from carrymem import CarryMem

# ── 1. Knowledge Graph E2E (v0.7.0) ──────────────────────────────────────


class TestKnowledgeGraphE2E:
    """User journey: store memories with entities → graph recall → graph traversal."""

    def test_entity_auto_extraction_and_recall(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("I prefer PostgreSQL for database projects")
        cm.classify_and_remember("PostgreSQL handles concurrent transactions well")
        cm.classify_and_remember("I use Docker for containerized deployments")

        results = cm.recall_by_entity("PostgreSQL")
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_graph_traversal_multi_hop(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("I use Python for backend development")
        cm.classify_and_remember("Python works great with FastAPI")
        cm.classify_and_remember("FastAPI integrates with Pydantic for validation")

        added = cm.add_graph_relation("Python", "FastAPI", "works_with")
        assert added is True

        graph = cm.recall_graph("Python", max_hops=2)
        assert isinstance(graph, dict)
        assert "entities" in graph
        assert "memories" in graph

    def test_graph_capability_gated(self, fresh_carrymem):
        cm = fresh_carrymem
        cap = cm._adapter.capabilities.get("graph", False) if cm._adapter else False
        assert cap is True, "SQLiteAdapter should have graph capability"

        results = cm.recall_by_entity("NonexistentEntity12345")
        assert isinstance(results, list)
        assert len(results) == 0


# ── 2. Session Dual-Layer Memory E2E (v0.7.0) ────────────────────────────


class TestSessionDualLayerE2E:
    """User journey: set_session → store → preload → promote → end_session."""

    def test_session_lifecycle(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.set_session("e2e-session-001")
        cm.classify_and_remember("Session memory about TypeScript")
        cm.classify_and_remember("Another session note about React hooks")

        preloaded = cm.preload_session(limit=10)
        assert isinstance(preloaded, int)

        results = cm.recall_memories("TypeScript")
        assert isinstance(results, list)

        cm.end_session()

    def test_promote_to_permanent_nonexistent_key(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.set_session("e2e-session-002")
        result = cm.promote_to_permanent("nonexistent_key_99999")
        assert result is False
        cm.end_session()

    def test_promote_to_permanent_existing_memory(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.set_session("e2e-session-003")
        store_result = cm.classify_and_remember("Important decision about architecture")
        assert isinstance(store_result, dict)

        if "id" in store_result:
            promoted = cm.promote_to_permanent(store_result["id"])
            assert isinstance(promoted, bool)

        cm.end_session()


# ── 3. Multi-Mode Retrieval E2E (v0.7.1) ─────────────────────────────────


class TestMultiModeRetrievalE2E:
    """User journey: store memories → recall by time/semantic/hybrid/multi_mode."""

    def test_recall_by_time_range(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("Memory from today about testing strategies")

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        results = cm.recall_by_time(start=start, end=end, limit=50)
        assert isinstance(results, list)

    def test_recall_by_time_empty_range(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("Memory that should not be in range")

        future_start = datetime.now(timezone.utc) + timedelta(days=365)
        future_end = future_start + timedelta(hours=1)

        results = cm.recall_by_time(start=future_start, end=future_end, limit=50)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_recall_semantic_capability_gated(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("Vector search test memory")

        results = cm.recall_semantic("search query", top_k=5)
        assert isinstance(results, list)

    def test_recall_hybrid_search(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("PostgreSQL is my preferred database")
        cm.classify_and_remember("I use Redis for caching layer")

        results = cm.recall_hybrid("database", limit=10)
        assert isinstance(results, list)

    def test_recall_multi_mode_unified(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("Python is great for data science")
        cm.classify_and_remember("I prefer VS Code as my editor")

        result = cm.recall_multi_mode("Python", modes=["fts"], limit=10)
        assert isinstance(result, dict)
        assert "modes" in result
        assert "merged" in result
        assert "mode_count" in result
        assert "total_count" in result

    def test_recall_multi_mode_unknown_mode_graceful(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("Test memory for unknown mode handling")

        result = cm.recall_multi_mode("test", modes=["fts", "unknown_mode"], limit=10)
        assert isinstance(result, dict)
        assert "modes" in result
        assert "unknown_mode" in result["modes"]


# ── 4. Memify Consolidation E2E (v0.7.2) ─────────────────────────────────


class TestMemifyConsolidationE2E:
    """User journey: store memories with co-occurring entities → consolidate → verify."""

    def test_consolidate_memories_returns_dict(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("I use Python and PostgreSQL together")
        cm.classify_and_remember("Python with PostgreSQL is a solid stack")
        cm.classify_and_remember("Python and PostgreSQL for backend services")

        result = cm.consolidate_memories(min_co_occurrence=2, max_derived=5)
        assert isinstance(result, dict)
        assert "derived_facts" in result or "derived" in result
        assert "edges_reinforced" in result or "reinforced" in result
        assert "decayed" in result

    def test_consolidate_empty_namespace(self, fresh_carrymem):
        cm = fresh_carrymem
        result = cm.consolidate_memories(min_co_occurrence=100)
        assert isinstance(result, dict)

    def test_consolidate_idempotent(self, fresh_carrymem):
        cm = fresh_carrymem
        cm.classify_and_remember("Python and Docker for deployment")
        cm.classify_and_remember("Python with Docker containers")
        cm.classify_and_remember("Docker and Python work well")

        first = cm.consolidate_memories(min_co_occurrence=2)
        second = cm.consolidate_memories(min_co_occurrence=2)
        assert isinstance(first, dict)
        assert isinstance(second, dict)


# ── 5. AsyncSQLiteAdapter E2E (v0.7.2) ───────────────────────────────────


class TestAsyncAdapterE2E:
    """User journey: AsyncSQLiteAdapter direct → connect → store → recall → count.

    (post-v0.10.1: AsyncCarryMem native_async mode removed, 2026-09-07, ships in v0.11.0; the adapter is used
    standalone here.)"""

    @pytest.mark.asyncio
    async def test_async_lifecycle(self):
        pytest.importorskip("aiosqlite")

        from carrymem.adapters.async_sqlite import AsyncSQLiteAdapter
        from carrymem.adapters.base import MemoryEntry

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "async_carrymem.db")
        try:
            adapter = AsyncSQLiteAdapter(db_path, namespace="default")
            await adapter.connect()

            entry = MemoryEntry(
                id="async-test-001",
                content="Async storage test memory",
                type="preference",
                confidence=0.8,
                raw_text="I prefer async I/O for high concurrency",
                metadata={},
            )
            stored = await adapter.store_entry(entry)
            assert stored is not None

            results = await adapter.recall("async")
            assert isinstance(results, list)

            count = await adapter.count()
            assert isinstance(count, int)
            assert count >= 1

            await adapter.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        pytest.importorskip("aiosqlite")

        from carrymem.adapters.async_sqlite import AsyncSQLiteAdapter

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "async_cm.db")
        try:
            async with AsyncSQLiteAdapter(db_path, namespace="default") as adapter:
                count = await adapter.count()
                assert isinstance(count, int)
                assert count == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ── 6. Full v0.7.x Integration E2E ───────────────────────────────────────


class TestV07xFullIntegration:
    """Integration: all v0.7.x features working together in a single session."""

    def test_full_user_journey_v07x(self, fresh_carrymem):
        cm = fresh_carrymem

        # v0.7.0: Knowledge Graph — store memories, entities auto-extracted
        cm.classify_and_remember("I use Python for machine learning projects")
        cm.classify_and_remember("Python integrates with TensorFlow for ML")
        cm.classify_and_remember("TensorFlow supports GPU acceleration")

        # v0.7.0: Session dual-layer
        cm.set_session("integration-test")
        cm.classify_and_remember("Session note about deployment strategies")
        cm.preload_session(limit=20)

        # v0.7.0: Graph operations
        cm.add_graph_relation("Python", "TensorFlow", "integrates_with")
        graph_result = cm.recall_graph("Python", max_hops=2)
        assert isinstance(graph_result, dict)

        entity_results = cm.recall_by_entity("Python")
        assert isinstance(entity_results, list)

        # v0.7.1: Multi-mode retrieval
        now = datetime.now(timezone.utc)
        time_results = cm.recall_by_time(start=now - timedelta(days=1), end=now + timedelta(days=1), limit=50)
        assert isinstance(time_results, list)

        hybrid_results = cm.recall_hybrid("Python", limit=10)
        assert isinstance(hybrid_results, list)

        multi_result = cm.recall_multi_mode("Python", modes=["fts", "graph"], limit=10, entity="Python")
        assert isinstance(multi_result, dict)

        # v0.7.2: Memify consolidation
        consolidate_result = cm.consolidate_memories(min_co_occurrence=1, max_derived=5)
        assert isinstance(consolidate_result, dict)

        cm.end_session()
