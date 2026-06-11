"""
Memory Optimization Verification Tests (P1-6)

Validates memory behavior under various scenarios to detect:
- Memory leaks during repeated operations
- Excessive memory allocation during bulk inserts
- Garbage collection effectiveness for large result sets
- Connection pool resource management
- Encryption buffer cleanup

Uses tracemalloc for precise memory tracking.
Run: pytest tests/test_memory_optimization.py -v
"""

import gc
import os
import tempfile
import threading
import time
import tracemalloc

import pytest

from carrymem import CarryMem
from carrymem.security.encryption import MemoryEncryption


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mem_opt_db(tmp_path):
    """Create a CarryMem instance for memory optimization tests."""
    db_path = str(tmp_path / "mem_opt.db")
    cm = CarryMem(db_path=db_path)
    yield cm
    cm.close()


# ---------------------------------------------------------------------------
# Test 1: No Memory Leak on Repeated Recall
# ---------------------------------------------------------------------------


class TestNoMemoryLeakOnRepeatedRecall:
    """Verify: 100 consecutive recall operations don't cause unbounded memory growth."""

    def test_no_memory_leak_on_repeated_recall(self, mem_opt_db):
        """Memory should not grow continuously across 100 recall operations."""
        cm = mem_opt_db

        # Pre-populate with some data
        for i in range(100):
            cm.classify_and_remember(f"Memory leak test entry {i} about Python programming")

        tracemalloc.start()

        # Take baseline after population
        gc.collect()
        baseline_current, _ = tracemalloc.get_traced_memory()

        # Perform repeated recalls and track memory at intervals
        snapshots = []
        num_iterations = 100

        for batch in range(10):  # 10 batches of 10 recalls each
            for _ in range(10):
                cm.recall_memories(query=f"entry {batch}", limit=20)

            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            snapshots.append({
                "batch": batch,
                "current_mb": current / (1024 * 1024),
                "peak_mb": peak / (1024 * 1024),
            })

        final_current, final_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Calculate growth metrics
        initial_snapshot = snapshots[0]["current_mb"] if snapshots else 0
        final_snapshot = snapshots[-1]["current_mb"] if snapshots else 0
        total_growth_mb = final_current / (1024 * 1024) - baseline_current / (1024 * 1024)

        # Check that later half doesn't show significantly more growth than first half
        if len(snapshots) >= 4:
            first_half_avg = sum(s["current_mb"] for s in snapshots[:5]) / 5
            second_half_avg = sum(s["current_mb"] for s in snapshots[5:]) / 5
            growth_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1.0
        else:
            growth_ratio = 1.0

        print(
            f"\n[no_memory_leak_recall] iterations={num_iterations}, "
            f"baseline={baseline_current/1024/1024:.2f}MB, "
            f"final_current={final_current/1024/1024:.2f}MB, "
            f"final_peak={final_peak/1024/1024:.2f}MB, "
            f"total_growth={total_growth_mb:.2f}MB, "
            f"growth_ratio={growth_ratio:.2f}x"
        )

        # Memory should not more than triple (allowing for caching)
        assert growth_ratio < 3.0, (
            f"Possible memory leak detected: memory grew by {growth_ratio:.2f}x "
            f"across {num_iterations} recall operations"
        )


# ---------------------------------------------------------------------------
# Test 2: Bulk Insert Memory Growth Linearity
# ---------------------------------------------------------------------------


class TestBulkInsertMemoryGrowthLinear:
    """Verify: inserting 1000 memories results in reasonable (<50MB) memory growth."""

    def test_bulk_insert_memory_growth_linear(self, tmp_path):
        """1000 inserts should not cause excessive (>50MB) memory growth."""
        db_path = str(tmp_path / "bulk_mem.db")
        cm = CarryMem(db_path=db_path)

        try:
            tracemalloc.start()
            gc.collect()
            baseline_current, baseline_peak = tracemalloc.get_traced_memory()

            # Insert 1000 memories in batches, tracking memory at checkpoints
            checkpoints = [100, 300, 500, 700, 1000]
            checkpoint_data = []

            topics = [
                "Python development patterns",
                "Database optimization",
                "DevOps automation",
                "Code review standards",
                "API design principles",
                "Security hardening",
                "Performance tuning",
                "Testing frameworks",
            ]

            inserted = 0
            for i in range(1000):
                topic = topics[i % len(topics)]
                cm.classify_and_remember(f"[{i}] Memory growth test: {topic} entry number {i}")
                inserted += 1

                if inserted in checkpoints:
                    gc.collect()
                    current, peak = tracemalloc.get_traced_memory()
                    checkpoint_data.append({
                        "count": inserted,
                        "current_mb": current / (1024 * 1024),
                        "peak_mb": peak / (1024 * 1024),
                    })

            gc.collect()
            final_current, final_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            total_growth_mb = (final_current - baseline_current) / (1024 * 1024)
            per_entry_kb = (final_current - baseline_current) / 1000 / 1024 if inserted > 0 else 0

            # Check linearity: last half growth shouldn't be disproportionately larger
            if len(checkpoint_data) >= 3:
                first_half_growth = (
                    checkpoint_data[1]["current_mb"] - checkpoint_data[0]["current_mb"]
                )
                second_half_growth = (
                    checkpoint_data[-1]["current_mb"] - checkpoint_data[-2]["current_mb"]
                )
                # Allow up to 2x non-linearity (caching effects)
                linearity_ratio = (
                    second_half_growth / first_half_growth if first_half_growth > 0 else 1.0
                )
            else:
                linearity_ratio = 1.0

            print(
                f"\n[bulk_insert_memory] inserted={inserted}, "
                f"baseline={baseline_current/1024/1024:.2f}MB, "
                f"final={final_current/1024/1024:.2f}MB, "
                f"peak={final_peak/1024/1024:.2f}MB, "
                f"total_growth={total_growth_mb:.2f}MB, "
                f"per_entry={per_entry_kb:.1f}KB, "
                f"linearity_ratio={linearity_ratio:.2f}x"
            )

            for cp in checkpoint_data:
                print(f"  checkpoint@{cp['count']}: {cp['current_mb']:.2f}MB")

            # Primary assertion: total growth under 50MB
            assert total_growth_mb < 50, (
                f"Memory growth {total_growth_mb:.2f}MB exceeds 50MB threshold for 1000 inserts"
            )

            # Secondary check: reasonable per-entry overhead
            assert per_entry_kb < 50, (
                f"Per-entry memory overhead {per_entry_kb:.1f}KB exceeds 50KB threshold"
            )

            # Tertiary check: roughly linear growth pattern
            assert linearity_ratio < 5.0, (
                f"Growth is non-linear ({linearity_ratio:.2f}x), possible memory accumulation issue"
            )
        finally:
            cm.close()


# ---------------------------------------------------------------------------
# Test 3: Large Result Set GC
# ---------------------------------------------------------------------------


class TestLargeResultSetGC:
    """Verify: large result sets can be garbage collected properly."""

    def test_large_result_set_gc(self, populated_db_fn):
        """Large recall results should be reclaimable by GC."""
        cm, _ = populated_db_fn

        tracemalloc.start()
        gc.collect()
        baseline, _ = tracemalloc.get_traced_memory()

        # Create a large result set
        large_results = cm.recall_memories(query="", limit=5000)
        result_count = len(large_results) if isinstance(large_results, list) else 0

        gc.collect()
        after_create, peak_after_create = tracemalloc.get_traced_memory()

        # Delete reference and force GC
        del large_results
        gc.collect()
        time.sleep(0.1)  # Brief pause to allow GC to complete
        gc.collect()  # Double collect for thoroughness

        after_gc, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        created_mb = (after_create - baseline) / (1024 * 1024)
        reclaimed_mb = (after_create - after_gc) / (1024 * 1024)
        reclaim_pct = (reclaimed_mb / created_mb * 100) if created_mb > 0 else 0

        print(
            f"\n[large_result_set_gc] results={result_count}, "
            f"memory_created={created_mb:.2f}MB, "
            f"memory_reclaimed={reclaimed_mb:.2f}MB ({reclaim_pct:.0f}%), "
            f"remaining={after_gc/1024/1024:.2f}MB above baseline"
        )

        # At least 50% of the result set memory should be reclaimable
        assert reclaim_pct > 50 or created_mb < 1.0, (
            f"GC ineffective: only {reclaim_pct:.0f}% of {created_mb:.2f}MB was reclaimed. "
            f"Possible reference retention in large result sets."
        )


# ---------------------------------------------------------------------------
# Test 4: Connection Pool Memory
# ---------------------------------------------------------------------------


class TestConnectionPoolMemory:
    """Verify: connection pool does not accumulate unclosed connections."""

    @pytest.fixture
    def populated_db_fn(self, tmp_path):
        """Create a populated database for connection pool testing."""
        db_path = str(tmp_path / "conn_pool.db")
        cm = CarryMem(db_path=db_path)

        # Populate with data
        for i in range(200):
            cm.classify_and_remember(f"Connection pool test entry {i}")

        return cm, db_path

    def test_connection_pool_memory(self, populated_db_fn):
        """Multiple open/close cycles should not accumulate connections."""
        cm, db_path = populated_db_fn

        # Close the initial instance
        cm.close()

        tracemalloc.start()
        gc.collect()
        baseline, _ = tracemalloc.get_traced_memory()

        # Perform multiple open/close cycles
        num_cycles = 20
        instances = []

        for cycle in range(num_cycles):
            cm_new = CarryMem(db_path=db_path)
            # Do some work
            cm_new.recall_memories(query="entry", limit=10)
            instances.append(cm_new)

            # Close every other instance to simulate mixed usage
            if cycle % 2 == 1:
                cm_new.close()

        gc.collect()
        during_cycles, peak_during = tracemalloc.get_traced_memory()

        # Close all remaining instances
        for inst in instances:
            try:
                inst.close()
            except Exception:
                pass  # Already closed

        instances.clear()
        gc.collect()
        time.sleep(0.1)
        gc.collect()

        after_close, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        growth_during = (during_cycles - baseline) / (1024 * 1024)
        growth_after = (after_close - baseline) / (1024 * 1024)
        reclaimed_pct = ((growth_during - growth_after) / growth_during * 100) if growth_during > 0 else 0

        print(
            f"\n[connection_pool_memory] cycles={num_cycles}, "
            f"during_cycles={growth_during:.2f}MB, "
            f"after_close={growth_after:.2f}MB, "
            f"reclaimed={reclaimed_pct:.0f}%"
        )

        # After closing all instances, memory should return close to baseline
        assert growth_after < 10, (
            f"Connection pool leaked ~{growth_after:.2f}MB after closing {num_cycles} instances. "
            f"Connections may not be properly released."
        )

        # Most of the allocated memory should be reclaimable
        assert reclaimed_pct > 70 or growth_during < 2.0, (
            f"Only {reclaimed_pct:.0f}% of connection pool memory was reclaimed. "
            f"Possible connection handle leak."
        )


# ---------------------------------------------------------------------------
# Test 5: Encryption Buffer Cleanup
# ---------------------------------------------------------------------------


class TestEncryptionBufferCleanup:
    """Verify: encryption buffers are released promptly after use."""

    def test_encryption_buffer_cleanup(self):
        """Repeated encrypt/decrypt cycles should not accumulate buffers."""
        enc = MemoryEncryption(key="buffer_cleanup_test_key")

        tracemalloc.start()
        gc.collect()
        baseline, _ = tracemalloc.get_traced_memory()

        # Generate test data
        test_messages = [
            f"Sensitive buffer cleanup test message {i}: Contains data requiring encryption"
            for i in range(500)
        ]

        # Perform many encrypt/decrypt cycles
        encrypted_items = []
        snapshots = []

        for batch in range(10):  # 10 batches of 50 ops each
            batch_start = len(encrypted_items)
            for i in range(50):
                idx = batch * 50 + i
                msg = test_messages[idx]
                encrypted = enc.encrypt(msg)
                encrypted_items.append(encrypted)

            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            snapshots.append({
                "batch": batch,
                "items": (batch + 1) * 50,
                "current_mb": current / (1024 * 1024),
                "peak_mb": peak / (1024 * 1024),
            })

        # Decrypt all items
        for item in encrypted_items:
            _ = enc.decrypt(item)

        gc.collect()
        after_ops, _ = tracemalloc.get_traced_memory()

        # Clear references
        encrypted_items.clear()
        del test_messages
        gc.collect()
        time.sleep(0.1)
        gc.collect()

        after_cleanup, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        ops_growth = (after_ops - baseline) / (1024 * 1024)
        cleanup_growth = (after_cleanup - baseline) / (1024 * 1024)
        reclaimable = ops_growth - cleanup_growth
        reclaim_pct = (reclaimable / ops_growth * 100) if ops_growth > 0 else 0

        # Check for linear growth pattern
        if len(snapshots) >= 4:
            first_half_growth = (
                snapshots[2]["current_mb"] - snapshots[0]["current_mb"]
            )
            second_half_growth = (
                snapshots[-1]["current_mb"] - snapshots[-3]["current_mb"]
            )
            buffer_ratio = (
                second_half_growth / first_half_growth if first_half_growth > 0 else 1.0
            )
        else:
            buffer_ratio = 1.0

        print(
            f"\n[encryption_buffer] encrypt_ops=500, decrypt_ops=500, "
            f"ops_memory={ops_growth:.2f}MB, "
            f"cleanup_memory={cleanup_growth:.2f}MB, "
            f"reclaimable={reclaimable:.2f}MB ({reclaim_pct:.0f}%), "
            f"buffer_accumulation_ratio={buffer_ratio:.2f}x"
        )

        for snap in snapshots:
            print(
                f"  batch{snap['batch']}@{snap['items']}items: "
                f"{snap['current_mb']:.2f}MB (peak:{snap['peak_mb']:.2f}MB)"
            )

        # Buffers should not accumulate excessively
        assert buffer_ratio < 5.0, (
            f"Encryption buffer accumulation detected: ratio {buffer_ratio:.2f}x. "
            f"Buffers may not be released promptly."
        )

        # Most encryption memory should be reclaimable after dereferencing
        assert reclaim_pct > 60 or ops_growth < 2.0, (
            f"Only {reclaim_pct:.0f}% of encryption memory was reclaimable. "
            f"Possible buffer retention issue in encryption module."
        )

        # Total memory use should remain reasonable for 500 encrypt+decrypt ops
        assert ops_growth < 25, (
            f"Total memory for 500 encrypt/decrypt ops: {ops_growth:.2f}MB exceeds 25MB threshold"
        )
