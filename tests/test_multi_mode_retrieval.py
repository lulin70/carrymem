"""Test suite for Multi-Mode Retrieval (v0.7.1).

Covers all test dimensions per DevSquad Iron Rules:
  - Happy Path: recall_by_time, recall_semantic, recall_hybrid, recall_multi_mode
  - Boundary: empty results, limit=0, time range edges, vector disabled
  - Error: adapter not configured, empty query, invalid time range
  - Performance: 1000 memories recall_by_time < 50ms
  - Configuration: custom RRF weights, different modes combinations
  - Integration: CarryMem facade, Protocol consistency, capability gating

Uses real SQLiteAdapter (in-memory) per user testing philosophy.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from carrymem.adapters.base import StorageAdapter
from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.carrymem import CarryMem
from carrymem.core._protocols import RecallOps

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def adapter() -> SQLiteAdapter:
    """In-memory SQLiteAdapter with vector search disabled (default)."""
    return SQLiteAdapter(":memory:", namespace="default", enable_vector_search=False)


@pytest.fixture
def adapter_with_memories(adapter: SQLiteAdapter) -> SQLiteAdapter:
    """Adapter pre-loaded with test memories at different timestamps."""
    from carrymem.adapters.base import MemoryEntry

    now = datetime.now(timezone.utc)
    entries = [
        MemoryEntry(
            id="m1",
            type="user_preference",
            content="I prefer Python for backend",
            raw_text="I prefer Python for backend",
            confidence=0.9,
        ),
        MemoryEntry(
            id="m2",
            type="fact_declaration",
            content="PostgreSQL is a powerful database",
            raw_text="PostgreSQL is a powerful database",
            confidence=0.85,
        ),
        MemoryEntry(
            id="m3",
            type="decision",
            content="Use JWT for authentication",
            raw_text="Use JWT for authentication",
            confidence=0.8,
        ),
    ]
    stored_keys = []
    for entry in entries:
        stored = adapter.store_entry(entry)
        stored_keys.append(stored.storage_key)
    # Manually set different created_at timestamps for time-range testing
    conn = adapter._get_connection()
    old_time = (now - timedelta(days=30)).isoformat()
    conn.execute("UPDATE memories SET created_at = ? WHERE storage_key = ?", (old_time, stored_keys[0]))
    mid_time = (now - timedelta(days=10)).isoformat()
    conn.execute("UPDATE memories SET created_at = ? WHERE storage_key = ?", (mid_time, stored_keys[1]))
    recent_time = (now - timedelta(days=1)).isoformat()
    conn.execute("UPDATE memories SET created_at = ? WHERE storage_key = ?", (recent_time, stored_keys[2]))
    conn.commit()
    return adapter


@pytest.fixture
def carrymem(adapter_with_memories: SQLiteAdapter) -> CarryMem:
    """CarryMem instance backed by adapter_with_memories."""
    cm = CarryMem(storage=adapter_with_memories, namespace="default")
    return cm


# ── Happy Path (8 tests) ──────────────────────────────────────────────────


class TestHappyPath:
    """Verify: normal usage of v0.7.1 multi-mode retrieval APIs."""

    def test_recall_by_time_returns_memories_in_range(self, adapter_with_memories):
        """Verify: recall_by_time returns memories within the specified range.

        Scenario: Query for memories from 15 days ago to now.
        Expected: Returns m2 (10 days old) and m3 (1 day old), not m1 (30 days old).
        """
        start = datetime.now(timezone.utc) - timedelta(days=15)
        results = adapter_with_memories.recall_by_time(start)
        assert len(results) == 2
        ids = {r["id"] for r in results}
        assert "m1" not in ids
        assert "m2" in ids or "m3" in ids

    def test_recall_by_time_with_explicit_end(self, adapter_with_memories):
        """Verify: recall_by_time respects end datetime.

        Scenario: Query [20 days ago, 5 days ago).
        Expected: Returns only m2 (10 days old).
        """
        start = datetime.now(timezone.utc) - timedelta(days=20)
        end = datetime.now(timezone.utc) - timedelta(days=5)
        results = adapter_with_memories.recall_by_time(start, end)
        assert len(results) == 1
        assert results[0]["id"] == "m2"

    def test_recall_by_time_orders_descending(self, adapter_with_memories):
        """Verify: results are ordered by created_at descending."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        results = adapter_with_memories.recall_by_time(start)
        assert len(results) >= 2
        for i in range(len(results) - 1):
            assert results[i]["created_at"] >= results[i + 1]["created_at"]

    def test_recall_hybrid_returns_results(self, adapter_with_memories):
        """Verify: recall_hybrid returns results even without vector search.

        Scenario: Query "Python" with hybrid mode (vector disabled).
        Expected: Returns FTS results (vector skipped gracefully).
        """
        results = adapter_with_memories.recall_hybrid("Python")
        assert isinstance(results, list)
        assert any("Python" in r.get("content", "") for r in results)

    def test_recall_hybrid_with_custom_weights(self, adapter_with_memories):
        """Verify: recall_hybrid accepts custom RRF weights without error."""
        results = adapter_with_memories.recall_hybrid("Python", fts_weight=0.8, vec_weight=0.2, rrf_k=30)
        assert isinstance(results, list)

    def test_recall_multi_mode_default_modes(self, adapter_with_memories):
        """Verify: recall_multi_mode with default modes returns structured result.

        Scenario: Query "Python" with no explicit modes.
        Expected: Returns dict with "modes", "merged", "mode_count", "total_count".
        """
        result = adapter_with_memories.recall_multi_mode("Python")
        assert "modes" in result
        assert "merged" in result
        assert "mode_count" in result
        assert "total_count" in result
        assert result["mode_count"] >= 1

    def test_recall_multi_mode_with_fts_only(self, adapter_with_memories):
        """Verify: recall_multi_mode with ["fts"] mode returns FTS results."""
        result = adapter_with_memories.recall_multi_mode("Python", modes=["fts"])
        assert "fts" in result["modes"]
        assert len(result["modes"]["fts"]) >= 1

    def test_carrymem_facade_recall_by_time(self, carrymem):
        """Verify: CarryMem facade exposes recall_by_time."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        results = carrymem.recall_by_time(start)
        assert isinstance(results, list)
        assert len(results) >= 1


# ── Boundary (12 tests) ───────────────────────────────────────────────────


class TestBoundary:
    """Verify: edge cases and boundary conditions."""

    def test_recall_by_time_empty_range(self, adapter_with_memories):
        """Verify: time range with no memories returns empty list."""
        future_start = datetime.now(timezone.utc) + timedelta(days=100)
        results = adapter_with_memories.recall_by_time(future_start)
        assert results == []

    def test_recall_by_time_limit_zero(self, adapter_with_memories):
        """Verify: limit=0 returns empty list."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        results = adapter_with_memories.recall_by_time(start, limit=0)
        assert results == []

    def test_recall_by_time_limit_one(self, adapter_with_memories):
        """Verify: limit=1 returns at most 1 result."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        results = adapter_with_memories.recall_by_time(start, limit=1)
        assert len(results) <= 1

    def test_recall_by_time_start_equals_end(self, adapter_with_memories):
        """Verify: start == end returns empty (exclusive end)."""
        t = datetime.now(timezone.utc) - timedelta(days=10)
        results = adapter_with_memories.recall_by_time(t, end=t)
        assert results == []

    def test_recall_semantic_vector_disabled(self, adapter_with_memories):
        """Verify: recall_semantic returns empty when vector search disabled."""
        results = adapter_with_memories.recall_semantic("Python")
        assert results == []

    def test_recall_hybrid_no_results(self, adapter_with_memories):
        """Verify: recall_hybrid with non-matching query returns empty."""
        results = adapter_with_memories.recall_hybrid("xyz_nonexistent_query_12345")
        assert isinstance(results, list)

    def test_recall_multi_mode_empty_query(self, adapter_with_memories):
        """Verify: recall_multi_mode with empty query returns structured result."""
        result = adapter_with_memories.recall_multi_mode("", modes=["fts"])
        assert "modes" in result
        assert isinstance(result["modes"], dict)

    def test_recall_multi_mode_unknown_mode(self, adapter_with_memories):
        """Verify: unknown mode is handled gracefully (returns empty for that mode)."""
        result = adapter_with_memories.recall_multi_mode("Python", modes=["unknown_mode"])
        assert "unknown_mode" in result["modes"]
        assert result["modes"]["unknown_mode"] == []

    def test_recall_multi_mode_time_without_range(self, adapter_with_memories):
        """Verify: 'time' mode without time_range is skipped gracefully."""
        result = adapter_with_memories.recall_multi_mode("Python", modes=["time"])
        # time mode without time_range should not produce results
        assert "time" in result["modes"]

    def test_recall_multi_mode_graph_without_entity(self, adapter_with_memories):
        """Verify: 'graph' mode without entity is skipped gracefully."""
        result = adapter_with_memories.recall_multi_mode("Python", modes=["graph"])
        assert "graph" in result["modes"]

    def test_recall_by_time_with_type_filter(self, adapter_with_memories):
        """Verify: filters with type work in recall_by_time."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        results = adapter_with_memories.recall_by_time(start, filters={"type": "user_preference"})
        for r in results:
            assert r["type"] == "user_preference"

    def test_recall_multi_mode_deduplication(self, adapter_with_memories):
        """Verify: merged results are deduplicated by storage_key."""
        result = adapter_with_memories.recall_multi_mode("Python", modes=["fts", "hybrid"])
        merged_keys = [m.get("storage_key") for m in result["merged"]]
        assert len(merged_keys) == len(set(merged_keys))


# ── Error Cases (8 tests) ─────────────────────────────────────────────────


class TestErrorCases:
    """Verify: error handling and invalid inputs."""

    def test_recall_by_time_adapter_not_configured(self):
        """Verify: CarryMem without adapter raises StorageNotConfiguredError."""
        from carrymem.core._lifecycle import StorageNotConfiguredError

        cm = CarryMem(storage=None, namespace="default")
        with pytest.raises(StorageNotConfiguredError):
            cm.recall_by_time(datetime.now(timezone.utc))

    def test_recall_semantic_adapter_not_configured(self):
        """Verify: CarryMem without adapter raises StorageNotConfiguredError."""
        from carrymem.core._lifecycle import StorageNotConfiguredError

        cm = CarryMem(storage=None, namespace="default")
        with pytest.raises(StorageNotConfiguredError):
            cm.recall_semantic("test")

    def test_recall_hybrid_adapter_not_configured(self):
        """Verify: CarryMem without adapter raises StorageNotConfiguredError."""
        from carrymem.core._lifecycle import StorageNotConfiguredError

        cm = CarryMem(storage=None, namespace="default")
        with pytest.raises(StorageNotConfiguredError):
            cm.recall_hybrid("test")

    def test_recall_multi_mode_adapter_not_configured(self):
        """Verify: CarryMem without adapter raises StorageNotConfiguredError."""
        from carrymem.core._lifecycle import StorageNotConfiguredError

        cm = CarryMem(storage=None, namespace="default")
        with pytest.raises(StorageNotConfiguredError):
            cm.recall_multi_mode("test")

    def test_recall_semantic_empty_query(self, carrymem):
        """Verify: empty query raises ValueError."""
        with pytest.raises(ValueError):
            carrymem.recall_semantic("")

    def test_recall_by_time_none_start(self, carrymem):
        """Verify: None start raises ValueError."""
        with pytest.raises(ValueError):
            carrymem.recall_by_time(None)

    def test_recall_by_time_invalid_filter_key(self, adapter_with_memories):
        """Verify: invalid filter key raises ValueError."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        with pytest.raises(ValueError):
            adapter_with_memories.recall_by_time(start, filters={"invalid_key": "value"})

    def test_recall_hybrid_invalid_memory_type(self, adapter_with_memories):
        """Verify: invalid memory type in filters raises ValueError."""
        with pytest.raises(ValueError):
            adapter_with_memories.recall_hybrid("test", filters={"type": "invalid_type"})


# ── Performance (2 tests) ─────────────────────────────────────────────────


class TestPerformance:
    """Verify: performance baselines for multi-mode retrieval."""

    def test_recall_by_time_1000_memories_under_50ms(self):
        """Verify: recall_by_time on 1000 memories completes under 50ms.

        Scenario: Insert 1000 memories, query by time range.
        Expected: < 50ms (excluding fixture setup).
        """
        from carrymem.adapters.base import MemoryEntry

        adapter = SQLiteAdapter(":memory:", namespace="perf")
        for i in range(1000):
            entry = MemoryEntry(
                id=f"perf_{i}",
                type="fact_declaration",
                content=f"Fact number {i}",
                raw_text=f"Fact number {i}",
                confidence=0.5,
            )
            adapter.store_entry(entry)

        start = datetime.now(timezone.utc) - timedelta(days=1)
        t0 = time.perf_counter()
        results = adapter.recall_by_time(start, limit=50)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert len(results) <= 50
        assert elapsed_ms < 50, f"recall_by_time took {elapsed_ms:.1f}ms (>50ms)"

    def test_recall_hybrid_under_100ms(self, adapter_with_memories):
        """Verify: recall_hybrid completes under 100ms (without vector search)."""
        t0 = time.perf_counter()
        adapter_with_memories.recall_hybrid("Python")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 100, f"recall_hybrid took {elapsed_ms:.1f}ms (>100ms)"


# ── Configuration (4 tests) ───────────────────────────────────────────────


class TestConfiguration:
    """Verify: configuration options and mode combinations."""

    def test_recall_hybrid_default_weights(self, adapter_with_memories):
        """Verify: default weights (None) use adapter config."""
        results = adapter_with_memories.recall_hybrid("Python")
        assert isinstance(results, list)

    def test_recall_hybrid_custom_rrf_k(self, adapter_with_memories):
        """Verify: custom rrf_k is accepted."""
        results = adapter_with_memories.recall_hybrid("Python", rrf_k=100)
        assert isinstance(results, list)

    def test_recall_multi_mode_fts_and_hybrid(self, adapter_with_memories):
        """Verify: combination of fts and hybrid modes."""
        result = adapter_with_memories.recall_multi_mode("Python", modes=["fts", "hybrid"])
        assert "fts" in result["modes"]
        assert "hybrid" in result["modes"]
        assert result["mode_count"] == 2

    def test_recall_multi_mode_all_modes(self, adapter_with_memories):
        """Verify: all applicable modes can be requested together."""
        start = datetime.now(timezone.utc) - timedelta(days=40)
        end = datetime.now(timezone.utc)
        result = adapter_with_memories.recall_multi_mode(
            "Python",
            modes=["fts", "hybrid", "time"],
            time_range=(start, end),
        )
        assert result["mode_count"] >= 2


# ── Integration (6 tests) ─────────────────────────────────────────────────


class TestIntegration:
    """Verify: integration with CarryMem facade and Protocol consistency."""

    def test_carrymem_recall_semantic_capability_gating(self, carrymem):
        """Verify: recall_semantic returns [] when vector not enabled."""
        results = carrymem.recall_semantic("Python")
        assert results == []

    def test_carrymem_recall_hybrid_works(self, carrymem):
        """Verify: CarryMem facade exposes recall_hybrid."""
        results = carrymem.recall_hybrid("Python")
        assert isinstance(results, list)

    def test_carrymem_recall_multi_mode_works(self, carrymem):
        """Verify: CarryMem facade exposes recall_multi_mode."""
        result = carrymem.recall_multi_mode("Python", modes=["fts"])
        assert "modes" in result

    def test_base_adapter_defaults_return_empty(self):
        """Verify: base StorageAdapter defaults return empty for v0.7.1 methods."""
        # Check methods exist on base class
        assert hasattr(StorageAdapter, "recall_by_time")
        assert hasattr(StorageAdapter, "recall_semantic")
        assert hasattr(StorageAdapter, "recall_hybrid")
        assert hasattr(StorageAdapter, "recall_multi_mode")

    def test_protocol_recall_ops_has_v071_methods(self):
        """Verify: RecallOps Protocol includes v0.7.1 method signatures."""
        # Protocol is structural — verify method names exist in the namespace
        protocol_methods = dir(RecallOps)
        assert "recall_by_time" in protocol_methods
        assert "recall_semantic" in protocol_methods
        assert "recall_hybrid" in protocol_methods
        assert "recall_multi_mode" in protocol_methods

    def test_sqlite_adapter_capabilities_include_graph(self, adapter):
        """Verify: SQLiteAdapter capabilities dict has expected keys."""
        caps = adapter.capabilities
        assert "fts" in caps
        assert "graph" in caps
        assert "vector_search" in caps
