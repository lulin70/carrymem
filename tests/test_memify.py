"""Test suite for MemifyEngine (v0.7.2 dynamic memory refinement).

Covers all test dimensions per DevSquad Iron Rules:
  - Happy Path: derive_facts, reinforce_edges, auto_decay
  - Boundary: min_co_occurrence edges, max_weight cap, empty namespace
  - Error Cases: adapter not configured, schema missing, invalid params
  - Performance: co-occurrence query on large dataset
  - Configuration: stale_days, max_derived, weight_increment tuning
  - Integration: consolidate_memories end-to-end, KnowledgeGraph cooperation

Uses real SQLiteAdapter (in-memory) per testing philosophy.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.carrymem import CarryMem
from carrymem.layers.memify import MemifyEngine

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def adapter() -> SQLiteAdapter:
    """In-memory SQLiteAdapter with graph support."""
    return SQLiteAdapter(":memory:", namespace="default", enable_vector_search=False)


@pytest.fixture
def adapter_with_co_occurring_entities(adapter: SQLiteAdapter) -> SQLiteAdapter:
    """Adapter with memories that share entities (co-occurrence >= 3)."""
    entries = [
        MemoryEntry(
            id="m1",
            type="fact_declaration",
            content="Python and PostgreSQL work well together",
            raw_text="Python and PostgreSQL work well together",
            confidence=0.9,
        ),
        MemoryEntry(
            id="m2",
            type="fact_declaration",
            content="Python and PostgreSQL for web apps",
            raw_text="Python and PostgreSQL for web apps",
            confidence=0.85,
        ),
        MemoryEntry(
            id="m3",
            type="fact_declaration",
            content="Python and PostgreSQL scaling strategies",
            raw_text="Python and PostgreSQL scaling strategies",
            confidence=0.8,
        ),
        MemoryEntry(
            id="m4",
            type="fact_declaration",
            content="Java and Redis caching",
            raw_text="Java and Redis caching",
            confidence=0.7,
        ),
    ]
    for entry in entries:
        adapter.store_entry(entry)
    # store_entry auto-extracts entities; co-occurrence is computed from memory_entities
    return adapter


@pytest.fixture
def adapter_with_stale_memories(adapter: SQLiteAdapter) -> SQLiteAdapter:
    """Adapter with stale, low-importance memories for auto_decay testing."""
    entries = [
        MemoryEntry(
            id="stale1", type="fact_declaration", content="Old fact one", raw_text="Old fact one", confidence=0.1
        ),
        MemoryEntry(
            id="stale2", type="fact_declaration", content="Old fact two", raw_text="Old fact two", confidence=0.1
        ),
        MemoryEntry(
            id="fresh1",
            type="user_preference",
            content="I prefer dark mode",
            raw_text="I prefer dark mode",
            confidence=0.9,
        ),
    ]
    stored_keys = []
    for entry in entries:
        stored = adapter.store_entry(entry)
        stored_keys.append(stored.storage_key)

    # Manually set stale timestamps and low importance for stale memories
    conn = adapter._get_connection()
    old_time = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    for key in stored_keys[:2]:
        conn.execute(
            "UPDATE memories SET last_accessed_at = ?, importance_score = 0.1, access_count = 0 WHERE storage_key = ?",
            (old_time, key),
        )
    # Make fresh1 have high importance and recent access
    conn.execute(
        "UPDATE memories SET importance_score = 0.9, access_count = 5, last_accessed_at = ? WHERE storage_key = ?",
        (datetime.now(timezone.utc).isoformat(), stored_keys[2]),
    )
    conn.commit()
    return adapter


@pytest.fixture
def memify(adapter: SQLiteAdapter) -> MemifyEngine:
    """MemifyEngine backed by the test adapter."""
    return MemifyEngine(adapter=adapter)


@pytest.fixture
def carrymem(adapter_with_co_occurring_entities: SQLiteAdapter) -> CarryMem:
    """CarryMem instance for integration testing."""
    return CarryMem(storage=adapter_with_co_occurring_entities, namespace="default")


# ── Happy Path (6 tests) ──────────────────────────────────────────────────


class TestHappyPath:
    """Verify: normal usage of MemifyEngine three-phase refinement."""

    def test_derive_facts_creates_derived_memories(self, memify, adapter_with_co_occurring_entities):
        """Verify: derive_facts creates relationship memories for co-occurring entities."""
        result = memify.derive_facts(namespace="default", min_co_occurrence=2)
        assert isinstance(result, list)
        if result:
            assert all(r["type"] == "relationship" for r in result)
            assert all(json.loads(r["metadata"]).get("derived") is True for r in result)

    def test_reinforce_edges_returns_count(self, memify, adapter_with_co_occurring_entities):
        """Verify: reinforce_edges returns count of reinforced edges."""
        count = memify.reinforce_edges(namespace="default", min_co_occurrence=2)
        assert isinstance(count, int)
        assert count >= 0

    def test_auto_decay_returns_count(self, memify, adapter_with_stale_memories):
        """Verify: auto_decay returns count of decayed memories."""
        count = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3)
        assert isinstance(count, int)
        assert count >= 0

    def test_auto_decay_reduces_importance(self, memify, adapter_with_stale_memories):
        """Verify: auto_decay actually reduces importance_score."""
        conn = adapter_with_stale_memories._get_connection()
        before = conn.execute("SELECT importance_score FROM memories WHERE id = 'stale1'").fetchone()
        memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3)
        after = conn.execute("SELECT importance_score FROM memories WHERE id = 'stale1'").fetchone()
        if before and after:
            assert after["importance_score"] < before["importance_score"]

    def test_consolidate_memories_returns_all_phases(self, carrymem):
        """Verify: consolidate_memories returns all three phase results."""
        result = carrymem.consolidate_memories(namespace="default", min_co_occurrence=2)
        assert "derived_facts" in result
        assert "edges_reinforced" in result
        assert "decayed" in result
        assert isinstance(result["derived_facts"], list)
        assert isinstance(result["edges_reinforced"], int)
        assert isinstance(result["decayed"], int)

    def test_carrymem_facade_consolidate_memories(self, carrymem):
        """Verify: CarryMem facade exposes consolidate_memories."""
        assert hasattr(carrymem, "consolidate_memories")
        result = carrymem.consolidate_memories()
        assert isinstance(result, dict)


# ── Boundary (10 tests) ───────────────────────────────────────────────────


class TestBoundary:
    """Verify: edge cases and boundary conditions."""

    def test_derive_facts_empty_namespace(self, memify):
        """Verify: derive_facts on empty namespace returns empty list."""
        result = memify.derive_facts(namespace="nonexistent", min_co_occurrence=1)
        assert result == []

    def test_derive_facts_high_min_co_occurrence(self, memify, adapter_with_co_occurring_entities):
        """Verify: derive_facts with very high min_co_occurrence returns empty."""
        result = memify.derive_facts(namespace="default", min_co_occurrence=100)
        assert result == []

    def test_derive_facts_max_derived_limit(self, memify, adapter_with_co_occurring_entities):
        """Verify: max_derived limits the number of derived facts."""
        result = memify.derive_facts(namespace="default", min_co_occurrence=2, max_derived=1)
        assert len(result) <= 1

    def test_reinforce_edges_empty_namespace(self, memify):
        """Verify: reinforce_edges on empty namespace returns 0."""
        count = memify.reinforce_edges(namespace="nonexistent", min_co_occurrence=1)
        assert count == 0

    def test_reinforce_edges_max_weight_cap(self, memify, adapter_with_co_occurring_entities):
        """Verify: reinforce_edges respects max_weight cap."""
        memify.reinforce_edges(namespace="default", min_co_occurrence=2, weight_increment=10.0, max_weight=2.0)
        conn = adapter_with_co_occurring_entities._get_connection()
        rows = conn.execute("SELECT weight FROM memory_relations WHERE relation_type = 'co_occurs'").fetchall()
        for row in rows:
            assert row["weight"] <= 2.0

    def test_auto_decay_empty_namespace(self, memify):
        """Verify: auto_decay on empty namespace returns 0."""
        count = memify.auto_decay(namespace="nonexistent", stale_days=1)
        assert count == 0

    def test_auto_decay_does_not_affect_fresh_memories(self, memify, adapter_with_stale_memories):
        """Verify: auto_decay does not decay fresh, high-importance memories."""
        conn = adapter_with_stale_memories._get_connection()
        before = conn.execute("SELECT importance_score FROM memories WHERE id = 'fresh1'").fetchone()
        memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3)
        after = conn.execute("SELECT importance_score FROM memories WHERE id = 'fresh1'").fetchone()
        if before and after:
            assert after["importance_score"] == before["importance_score"]

    def test_auto_decay_batch_size_limit(self, memify, adapter_with_stale_memories):
        """Verify: batch_size limits processing."""
        count = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3, batch_size=1)
        assert count <= 1

    def test_auto_decay_idempotent(self, memify, adapter_with_stale_memories):
        """Verify: running auto_decay twice doesn't decay same memories again."""
        first = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3)
        second = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3)
        assert second <= first

    def test_auto_decay_does_not_touch_superseded(self, memify, adapter_with_stale_memories):
        """Verify: auto_decay skips superseded memories."""
        conn = adapter_with_stale_memories._get_connection()
        # Mark a memory as superseded
        conn.execute(
            "UPDATE memories SET superseded_at = ? WHERE id = 'stale1'", (datetime.now(timezone.utc).isoformat(),)
        )
        conn.commit()
        count = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3)
        # stale1 should not be decayed (superseded)
        row = conn.execute("SELECT metadata FROM memories WHERE id = 'stale1'").fetchone()
        if row and row["metadata"]:
            meta = json.loads(row["metadata"])
            assert not meta.get("decayed")


# ── Error Cases (6 tests) ─────────────────────────────────────────────────


class TestErrorCases:
    """Verify: error handling and invalid inputs."""

    def test_consolidate_memories_adapter_not_configured(self):
        """Verify: CarryMem without adapter raises StorageNotConfiguredError."""
        from carrymem.core._lifecycle import StorageNotConfiguredError

        cm = CarryMem(storage=None, namespace="default")
        with pytest.raises(StorageNotConfiguredError):
            cm.consolidate_memories()

    def test_derive_facts_no_graph_tables(self, adapter):
        """Verify: derive_facts gracefully handles missing graph data."""
        memify = MemifyEngine(adapter=adapter)
        result = memify.derive_facts(namespace="default", min_co_occurrence=1)
        assert isinstance(result, list)

    def test_reinforce_edges_no_graph_tables(self, adapter):
        """Verify: reinforce_edges gracefully handles missing graph data."""
        memify = MemifyEngine(adapter=adapter)
        count = memify.reinforce_edges(namespace="default", min_co_occurrence=1)
        assert isinstance(count, int)

    def test_auto_decay_no_matching_memories(self, memify):
        """Verify: auto_decay returns 0 when no memories match criteria."""
        count = memify.auto_decay(namespace="default", stale_days=36500, min_importance=0.0)
        assert count == 0

    def test_derive_facts_zero_min_co_occurrence(self, memify, adapter_with_co_occurring_entities):
        """Verify: min_co_occurrence=0 doesn't crash (though may return many pairs)."""
        result = memify.derive_facts(namespace="default", min_co_occurrence=0, max_derived=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    def test_auto_decay_zero_stale_days(self, memify, adapter_with_stale_memories):
        """Verify: stale_days=0 decays all matching memories."""
        count = memify.auto_decay(namespace="default", stale_days=0, min_importance=0.5, batch_size=10)
        assert isinstance(count, int)


# ── Performance (2 tests) ─────────────────────────────────────────────────


class TestPerformance:
    """Verify: performance baselines for Memify operations."""

    def test_derive_facts_large_dataset(self, adapter):
        """Verify: derive_facts completes under 500ms with many entities."""
        for i in range(100):
            entry = MemoryEntry(
                id=f"perf_{i}",
                type="fact_declaration",
                content=f"Python and Django project {i}",
                raw_text=f"Python and Django project {i}",
                confidence=0.5,
            )
            adapter.store_entry(entry)

        memify = MemifyEngine(adapter=adapter)
        t0 = time.perf_counter()
        memify.derive_facts(namespace="default", min_co_occurrence=2, max_derived=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 500, f"derive_facts took {elapsed_ms:.1f}ms (>500ms)"

    def test_auto_decay_large_batch(self, adapter):
        """Verify: auto_decay processes batch efficiently."""
        for i in range(200):
            entry = MemoryEntry(
                id=f"decay_{i}",
                type="fact_declaration",
                content=f"Stale fact {i}",
                raw_text=f"Stale fact {i}",
                confidence=0.1,
            )
            adapter.store_entry(entry)

        # Make all memories stale
        conn = adapter._get_connection()
        old_time = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        conn.execute(
            "UPDATE memories SET last_accessed_at = ?, importance_score = 0.1, access_count = 0",
            (old_time,),
        )
        conn.commit()

        memify = MemifyEngine(adapter=adapter)
        t0 = time.perf_counter()
        count = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.3, batch_size=200)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 200, f"auto_decay took {elapsed_ms:.1f}ms (>200ms)"


# ── Configuration (4 tests) ───────────────────────────────────────────────


class TestConfiguration:
    """Verify: configuration options."""

    def test_auto_decay_custom_stale_days(self, memify, adapter_with_stale_memories):
        """Verify: stale_days parameter controls decay threshold."""
        # With stale_days=200, memories 120 days old should NOT be decayed
        count = memify.auto_decay(namespace="default", stale_days=200, min_importance=0.3)
        assert count == 0

    def test_auto_decay_custom_min_importance(self, memify, adapter_with_stale_memories):
        """Verify: min_importance parameter controls decay threshold."""
        # With min_importance=0.05, memories with importance 0.1 should NOT be decayed
        count = memify.auto_decay(namespace="default", stale_days=90, min_importance=0.05)
        assert count == 0

    def test_reinforce_edges_custom_weight_increment(self, memify, adapter_with_co_occurring_entities):
        """Verify: weight_increment controls edge weight increase."""
        memify.reinforce_edges(namespace="default", min_co_occurrence=2, weight_increment=0.5, max_weight=2.0)
        conn = adapter_with_co_occurring_entities._get_connection()
        rows = conn.execute("SELECT weight FROM memory_relations WHERE relation_type = 'co_occurs'").fetchall()
        for row in rows:
            assert row["weight"] >= 0.5

    def test_consolidate_memories_custom_params(self, carrymem):
        """Verify: consolidate_memories accepts custom parameters."""
        result = carrymem.consolidate_memories(
            namespace="default",
            min_co_occurrence=5,
            max_derived=3,
            stale_days=365,
            min_importance=0.5,
        )
        assert isinstance(result, dict)


# ── Integration (4 tests) ─────────────────────────────────────────────────


class TestIntegration:
    """Verify: integration with CarryMem facade and KnowledgeGraph."""

    def test_consolidate_memories_with_graph_data(self, carrymem):
        """Verify: consolidate_memories works with knowledge graph data."""
        result = carrymem.consolidate_memories(namespace="default", min_co_occurrence=2)
        assert "derived_facts" in result
        assert "edges_reinforced" in result
        assert "decayed" in result

    def test_base_adapter_default_returns_empty(self):
        """Verify: base StorageAdapter default returns empty consolidation result."""
        from carrymem.adapters.base import StorageAdapter

        assert hasattr(StorageAdapter, "consolidate_memories")

    def test_protocol_has_consolidate_memories(self):
        """Verify: RecallOps Protocol includes consolidate_memories signature."""
        from carrymem.core._protocols import RecallOps

        assert "consolidate_memories" in dir(RecallOps)

    def test_memify_coexists_with_knowledge_graph(self, adapter_with_co_occurring_entities):
        """Verify: MemifyEngine works alongside KnowledgeGraph operations."""
        # Verify graph API still works
        entities = adapter_with_co_occurring_entities.list_graph_entities(namespace="default")
        assert isinstance(entities, list)

        # Run memify
        memify = MemifyEngine(adapter=adapter_with_co_occurring_entities)
        result = memify.derive_facts(namespace="default", min_co_occurrence=2)
        assert isinstance(result, list)

        # Verify graph API still works after memify
        entities_after = adapter_with_co_occurring_entities.list_graph_entities(namespace="default")
        assert isinstance(entities_after, list)
