"""Test suite for AsyncSQLiteAdapter (v0.7.2 native async I/O).

Covers all test dimensions per DevSquad Iron Rules:
  - Happy Path: connect, store_entry, recall, forget_memory, count, close
  - Boundary: empty results, nonexistent namespace, duplicate keys, large content
  - Error Cases: not connected, operations before connect, close idempotent
  - Performance: bulk store, bulk recall
  - Configuration: custom namespace, custom db_path, in-memory mode
  - Integration: AsyncCarryMem executor wrapper, async context manager

Uses real aiosqlite (in-memory) per testing philosophy.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import time
from datetime import timezone

import pytest

# Skip entire module if aiosqlite is not installed (e.g., CI without [async] extra)
pytest.importorskip("aiosqlite")

from carrymem.adapters.async_sqlite import AsyncSQLiteAdapter  # noqa: E402
from carrymem.adapters.base import MemoryEntry  # noqa: E402
from carrymem.adapters.sqlite.schema import _V200_MIGRATION_ID, _V210_MIGRATION_ID
from carrymem.exceptions import DatabaseError

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


class TestAsyncMigrationFailClosed:
    @pytest.mark.parametrize("migration_id", [_V200_MIGRATION_ID, _V210_MIGRATION_ID])
    @pytest.mark.parametrize("status", ["failed", "started"])
    async def test_non_success_ledger_status_fails_closed(self, tmp_path, migration_id, status):
        db_path = str(tmp_path / f"migration-{migration_id}-{status}.db")
        adapter = AsyncSQLiteAdapter(db_path)
        await adapter.connect()
        await adapter.close()

        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE carrymem_migrations SET status = ? WHERE migration_id = ?",
            (status, migration_id),
        )
        conn.commit()
        conn.close()

        with pytest.raises(DatabaseError, match="fail-closed"):
            await AsyncSQLiteAdapter(db_path).connect()


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


# ── Provenance parity ─────────────────────────────────────────────────────


async def _store_async_memory(adapter: AsyncSQLiteAdapter, id_: str, content: str):
    return await adapter.store_entry(
        MemoryEntry(
            id=id_,
            type="fact_declaration",
            content=content,
            raw_text=content,
            confidence=0.8,
        )
    )


async def _add_async_link(adapter: AsyncSQLiteAdapter, source_id: str, target_id: str, **kwargs):
    return await adapter.add_evidence_link(
        namespace=kwargs.pop("namespace", adapter.namespace),
        source_kind=kwargs.pop("source_kind", "memory"),
        source_id=source_id,
        source_snapshot_hash=kwargs.pop("source_snapshot_hash", "h"),
        target_kind=kwargs.pop("target_kind", "memory"),
        target_id=target_id,
        relation_type=kwargs.pop("relation_type", "derived_from"),
        support_weight=kwargs.pop("support_weight", 1.0),
    )


class TestAsyncProvenanceParity:
    async def test_add_evidence_link_validation(self, connected_adapter):
        base = {
            "namespace": "default",
            "source_kind": "memory",
            "source_id": "s1",
            "source_snapshot_hash": "h",
            "target_kind": "memory",
            "target_id": "t1",
            "relation_type": "derived_from",
        }
        for field, value in (
            ("relation_type", "invalid"),
            ("source_kind", "invalid"),
            ("target_kind", "invalid"),
        ):
            args = {**base, field: value}
            with pytest.raises(ValueError, match=field):
                await connected_adapter.add_evidence_link(**args)
        with pytest.raises(ValueError, match="support_weight"):
            await connected_adapter.add_evidence_link(**base, support_weight=0)
        empty_source = {**base, "source_id": ""}
        with pytest.raises(ValueError, match="non-empty"):
            await connected_adapter.add_evidence_link(**empty_source)
        empty_hash = {**base, "source_snapshot_hash": ""}
        with pytest.raises(ValueError, match="source_snapshot_hash"):
            await connected_adapter.add_evidence_link(**empty_hash)

    async def test_add_evidence_link_before_connect_raises(self, async_adapter):
        with pytest.raises(RuntimeError, match="not connected"):
            await async_adapter.add_evidence_link("default", "memory", "s", "h", "memory", "t", "derived_from")

    async def test_duplicate_idempotency_and_support_weight(self, connected_adapter):
        first = await _add_async_link(connected_adapter, "s1", "t1", support_weight=1.5)
        second = await _add_async_link(connected_adapter, "s1", "t1", support_weight=1.5)
        assert first is not None
        assert second is None
        links = await connected_adapter.list_evidence_links("default", target_id="t1")
        assert len(links) == 1
        assert links[0]["support_weight"] == 1.5

    async def test_namespace_isolation(self, connected_adapter):
        await _add_async_link(connected_adapter, "s1", "t1", namespace="ns_a")
        await _add_async_link(connected_adapter, "s1", "t1", namespace="ns_b")
        assert len(await connected_adapter.list_evidence_links("ns_a")) == 1
        assert len(await connected_adapter.list_evidence_links("ns_b")) == 1
        assert await connected_adapter.list_evidence_links("ns_c") == []

    async def test_stale_filtering_and_unsupported_targets(self, connected_adapter):
        target = await _store_async_memory(connected_adapter, "target", "target")
        source = await _store_async_memory(connected_adapter, "source", "source")
        await _add_async_link(connected_adapter, source.storage_key, target.storage_key)
        assert (
            len(
                await connected_adapter.list_evidence_links(
                    "default", target_id=target.storage_key, include_stale=False
                )
            )
            == 1
        )
        assert await connected_adapter.get_unsupported_targets("default", [target.storage_key]) == []
        assert await connected_adapter.forget_memory(source.storage_key) is True
        assert (
            len(
                await connected_adapter.list_evidence_links("default", target_id=target.storage_key, include_stale=True)
            )
            == 1
        )
        assert (
            await connected_adapter.list_evidence_links("default", target_id=target.storage_key, include_stale=False)
            == []
        )
        assert await connected_adapter.get_unsupported_targets("default", [target.storage_key]) == [target.storage_key]

    async def test_single_source_cascade_marks_unsupported(self, connected_adapter):
        source = await _store_async_memory(connected_adapter, "source", "source")
        target = await _store_async_memory(connected_adapter, "target", "target")
        await _add_async_link(connected_adapter, source.storage_key, target.storage_key)
        assert await connected_adapter.forget_memory(source.storage_key) is True
        row = await (
            await connected_adapter._conn.execute(
                "SELECT metadata FROM memories WHERE storage_key = ?", (target.storage_key,)
            )
        ).fetchone()
        metadata = json.loads(row["metadata"])
        assert metadata["provenance_unsupported"] == 1
        assert metadata["provenance_unsupported_at"]

    async def test_multi_source_and_ordinary_memory_preservation(self, connected_adapter):
        source_one = await _store_async_memory(connected_adapter, "source1", "source1")
        source_two = await _store_async_memory(connected_adapter, "source2", "source2")
        target = await _store_async_memory(connected_adapter, "target", "target")
        ordinary = await _store_async_memory(connected_adapter, "ordinary", "ordinary")
        await _add_async_link(connected_adapter, source_one.storage_key, target.storage_key)
        await _add_async_link(connected_adapter, source_two.storage_key, target.storage_key)
        assert await connected_adapter.forget_memory(source_one.storage_key) is True
        row = await (
            await connected_adapter._conn.execute(
                "SELECT metadata FROM memories WHERE storage_key = ?", (target.storage_key,)
            )
        ).fetchone()
        assert json.loads(row["metadata"]).get("provenance_unsupported") is None
        assert await connected_adapter.forget_memory(source_two.storage_key) is True
        row = await (
            await connected_adapter._conn.execute(
                "SELECT metadata FROM memories WHERE storage_key = ?", (target.storage_key,)
            )
        ).fetchone()
        assert json.loads(row["metadata"])["provenance_unsupported"] == 1
        row = await (
            await connected_adapter._conn.execute(
                "SELECT metadata FROM memories WHERE storage_key = ?", (ordinary.storage_key,)
            )
        ).fetchone()
        assert json.loads(row["metadata"]).get("provenance_unsupported") is None

    async def test_delete_marks_source_observation_unsupported(self, connected_adapter):
        source = await _store_async_memory(connected_adapter, "source-observation", "source observation")
        await connected_adapter._conn.execute(
            """INSERT INTO memory_observations
               (id, namespace, subject, predicate, value_json, source_kind, source_ref,
                confidence, observed_at, expires_at, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid')""",
            (
                "obs-1",
                "default",
                "subject",
                "preference_detected",
                "{}",
                "explicit_api",
                source.storage_key,
                0.9,
                "2026-01-01T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        await connected_adapter._conn.commit()
        assert await connected_adapter.forget_memory(source.storage_key) is True
        row = await (
            await connected_adapter._conn.execute("SELECT status FROM memory_observations WHERE id = 'obs-1'")
        ).fetchone()
        assert row["status"] == "unsupported"
        visible = await (
            await connected_adapter._conn.execute(
                "SELECT id FROM memory_observations WHERE namespace = ? AND status = 'valid'", ("default",)
            )
        ).fetchall()
        assert visible == []
        all_rows = await (
            await connected_adapter._conn.execute(
                "SELECT id FROM memory_observations WHERE namespace = ?", ("default",)
            )
        ).fetchall()
        assert [row["id"] for row in all_rows] == ["obs-1"]

    async def test_delete_nonexistent_key_does_not_update_observation(self, connected_adapter):
        await connected_adapter._conn.execute(
            """INSERT INTO memory_observations
               (id, namespace, subject, predicate, value_json, source_kind, source_ref,
                confidence, observed_at, expires_at, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid')""",
            (
                "obs-missing",
                "default",
                "subject",
                "preference_detected",
                "{}",
                "explicit_api",
                "missing",
                0.9,
                "2026-01-01T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        await connected_adapter._conn.commit()
        assert await connected_adapter.forget_memory("missing") is False
        row = await (
            await connected_adapter._conn.execute("SELECT status FROM memory_observations WHERE id = 'obs-missing'")
        ).fetchone()
        assert row["status"] == "valid"

    async def test_delete_nonexistent_key_does_not_cascade(self, connected_adapter):
        source = await _store_async_memory(connected_adapter, "source", "source")
        target = await _store_async_memory(connected_adapter, "target", "target")
        await _add_async_link(connected_adapter, source.storage_key, target.storage_key)
        assert await connected_adapter.forget_memory("missing") is False
        row = await (
            await connected_adapter._conn.execute(
                "SELECT metadata FROM memories WHERE storage_key = ?", (target.storage_key,)
            )
        ).fetchone()
        assert json.loads(row["metadata"]).get("provenance_unsupported") is None

    async def test_file_backed_reopen_and_recovery_parity(self, tmp_path):
        db_path = str(tmp_path / "provenance.db")
        adapter = AsyncSQLiteAdapter(db_path, namespace="default")
        await adapter.connect()
        source = await _store_async_memory(adapter, "source", "source")
        target = await _store_async_memory(adapter, "target", "target")
        await _add_async_link(adapter, source.storage_key, target.storage_key)
        await adapter.close()

        reopened = AsyncSQLiteAdapter(db_path, namespace="default")
        await reopened.connect()
        assert len(await reopened.list_evidence_links("default", target_id=target.storage_key)) == 1
        assert await reopened.forget_memory(source.storage_key) is True
        assert await reopened.list_evidence_links("default", target_id=target.storage_key, include_stale=False) == []
        row = await (
            await reopened._conn.execute("SELECT metadata FROM memories WHERE storage_key = ?", (target.storage_key,))
        ).fetchone()
        assert json.loads(row["metadata"])["provenance_unsupported"] == 1
        await reopened.close()


# ── Integration (4 tests) ────────────────────────────────────────────────


class TestIntegration:
    """Verify: integration with AsyncCarryMem and async patterns."""

    async def test_async_carrymem_executor_wrapper_smoke(self, tmp_path):
        """Verify: AsyncCarryMem (executor-wrapped mode) stores and recalls.

        Uses a file-backed DB: SQLiteAdapter's :memory: connection is
        thread-bound and cannot cross the executor thread boundary
        (pre-existing constraint, unrelated to the native_async removal).
        The native_async mode was removed after v0.10.1 (2026-09-07, ships in
        v0.11.0) — 16/20 of its methods
        raised RuntimeError unconditionally); the executor wrapper is the
        one and only AsyncCarryMem surface.
        """
        from carrymem.async_carrymem import AsyncCarryMem

        acm = AsyncCarryMem(storage="sqlite", db_path=str(tmp_path / "acm_smoke.db"), namespace="default")
        try:
            result = await acm.classify_and_remember("I prefer dark mode for coding")
            assert result.get("stored") is True, result

            results = await acm.recall_memories(query="dark mode")
            assert len(results) >= 1
        finally:
            await acm.close()

    async def test_adapter_encryption_key_fail_closed(self):
        """Verify: encryption_key raises NotImplementedError (fail-closed).

        Silently ignoring the key would store plaintext where the caller
        expects encryption at rest (P1-A4 fix).
        """
        with pytest.raises(NotImplementedError, match="encryption_key"):
            AsyncSQLiteAdapter(":memory:", namespace="default", encryption_key="some-key")

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
