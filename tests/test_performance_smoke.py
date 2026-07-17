"""Smoke performance tests for CI (not marked slow).

These tests run on every PR via ``-m "not slow"`` and catch catastrophic
performance regressions with very loose thresholds. They are NOT a substitute
for the full benchmark suite in ``test_performance_benchmark.py`` (which is
marked ``slow`` and runs nightly/locally).

Design principles:
- **Fast**: each test < 15s on CI VMs (CI_FACTOR=50 environment)
- **Loose thresholds**: 10-100x looser than benchmark thresholds to avoid
  CI flakiness from noisy-neighbor contention
- **Catches catastrophic regressions only**: e.g., O(n²) accidentally
  introduced into a hot path, or model loading failure causing 30s+ stalls
"""

import os
import time

import pytest

from carrymem import CarryMem

# CI VMs are 20-50x slower than dev machines. Smoke thresholds use 10x the
# dev-machine cold-start budget to avoid false positives while still catching
# catastrophic regressions (e.g., 60s+ stalls indicate a real problem).
_CI_ENV = bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))
CI_FACTOR = 10 if _CI_ENV else 1

# Smoke thresholds (very loose — only catch catastrophic regressions)
CLASSIFY_SMOKE_S = 15.0 * CI_FACTOR  # single classify_and_remember < 150s on CI
RECALL_SMOKE_S = 5.0 * CI_FACTOR  # recall from 20 records < 50s on CI
FORGET_SMOKE_S = 5.0 * CI_FACTOR  # forget operation < 50s on CI
BATCH_10_SMOKE_S = 10.0 * CI_FACTOR  # batch insert 10 memories < 100s on CI


@pytest.fixture
def smoke_db(tmp_path):
    """Create a fresh CarryMem instance for smoke testing."""
    db_path = str(tmp_path / "smoke.db")
    cm = CarryMem(db_path=db_path)
    yield cm
    cm.close()


class TestClassifySmoke:
    """Smoke: single classify_and_remember completes within loose threshold."""

    def test_classify_and_remember_smoke(self, smoke_db):
        """Single classify_and_remember must complete < CLASSIFY_SMOKE_S.

        This catches catastrophic regressions (model loading failure,
        accidental O(n²), deadlocks) without measuring steady-state perf.
        """
        cm = smoke_db
        start = time.perf_counter()
        result = cm.classify_and_remember("I prefer Python over Java for backend services")
        elapsed = time.perf_counter() - start

        assert isinstance(result, dict), f"Unexpected result type: {type(result)}"
        assert elapsed < CLASSIFY_SMOKE_S, (
            f"Classify+remember took {elapsed:.2f}s (threshold {CLASSIFY_SMOKE_S}s). "
            f"This indicates a catastrophic performance regression."
        )


class TestRecallSmoke:
    """Smoke: recall from 20 memories completes within loose threshold."""

    def test_recall_smoke(self, smoke_db):
        """Recall from 20 records must complete < RECALL_SMOKE_S."""
        cm = smoke_db
        # Populate 20 memories (small dataset — smoke only)
        for i in range(20):
            cm.classify_and_remember(f"Preference {i}: I prefer using Python for data analysis")

        start = time.perf_counter()
        result = cm.recall_memories(query="Python", limit=10)
        elapsed = time.perf_counter() - start

        assert isinstance(result, dict) or isinstance(result, list), (
            f"Unexpected result type: {type(result)}"
        )
        assert elapsed < RECALL_SMOKE_S, (
            f"Recall took {elapsed:.2f}s (threshold {RECALL_SMOKE_S}s). "
            f"This indicates a catastrophic performance regression."
        )


class TestForgetSmoke:
    """Smoke: forget operation completes within loose threshold."""

    def test_forget_smoke(self, smoke_db):
        """Forget operation must complete < FORGET_SMOKE_S."""
        cm = smoke_db
        store_result = cm.classify_and_remember("I prefer Vim over Emacs")
        storage_keys = store_result.get("storage_keys", []) if isinstance(store_result, dict) else []
        if not storage_keys:
            pytest.skip("No storage key returned — skip forget smoke test")

        memory_id = storage_keys[0]
        start = time.perf_counter()
        result = cm.forget_memory(memory_id)
        elapsed = time.perf_counter() - start

        assert elapsed < FORGET_SMOKE_S, (
            f"Forget took {elapsed:.2f}s (threshold {FORGET_SMOKE_S}s). "
            f"This indicates a catastrophic performance regression."
        )


class TestBatchInsertSmoke:
    """Smoke: batch insert of 10 memories completes within loose threshold."""

    def test_batch_insert_10_smoke(self, smoke_db):
        """Batch insert 10 memories must complete < BATCH_10_SMOKE_S."""
        cm = smoke_db
        messages = [f"Smoke entry {i}: preference for tool {i}" for i in range(10)]

        start = time.perf_counter()
        result = cm.store_messages(messages)
        elapsed = time.perf_counter() - start

        assert elapsed < BATCH_10_SMOKE_S, (
            f"Batch insert 10 took {elapsed:.2f}s (threshold {BATCH_10_SMOKE_S}s). "
            f"This indicates a catastrophic performance regression."
        )
