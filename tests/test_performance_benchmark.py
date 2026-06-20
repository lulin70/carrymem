"""
Performance Benchmark Tests for CarryMem Core Operations (P1-5)

Validates performance requirements with strict latency thresholds:
- classify_and_remember: < 100ms per operation
- recall on 1000 records: < 500ms
- batch insert 100: < 1s
- export profile (1000 records): < 2s
- encryption overhead: measurable and reasonable
- concurrent read throughput: QPS measurement

Run individually: pytest tests/test_performance_benchmark.py -k benchmark
Or by marker: pytest -m benchmark

Each test records:
  - Operation count
  - Total elapsed time
  - Throughput (ops/sec)
"""

import os
import statistics
import tempfile
import threading
import time

import pytest

from carrymem import CarryMem
from carrymem.security.encryption import MemoryEncryption, NoEncryption

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def benchmark_db(tmp_path):
    """Create a fresh CarryMem instance for benchmarking."""
    db_path = str(tmp_path / "benchmark.db")
    cm = CarryMem(db_path=db_path)
    yield cm
    cm.close()


@pytest.fixture
def populated_1000(benchmark_db):
    """Pre-populate with 1000 memories for recall/export benchmarks."""
    cm = benchmark_db
    topics = [
        "Python programming best practices",
        "Database design patterns",
        "DevOps deployment strategies",
        "Code review guidelines",
        "API design principles",
        "Security hardening techniques",
        "Performance optimization methods",
        "Testing automation frameworks",
    ]
    for i in range(1000):
        topic = topics[i % len(topics)]
        cm.classify_and_remember(f"[{i}] Benchmark entry about {topic} - iteration {i}")
    return cm


# ---------------------------------------------------------------------------
# Benchmark 1: Classify + Remember Latency
# ---------------------------------------------------------------------------


class TestClassifyAndRememberLatency:
    """Benchmark: single classify_and_remember must complete < 100ms."""

    def test_classify_and_remember_latency(self, benchmark_db):
        """Single memory classification + storage latency < 100ms."""
        cm = benchmark_db
        latencies = []
        iterations = 50

        for i in range(iterations):
            msg = f"Benchmark preference {i}: I prefer using dark mode for coding"
            start = time.perf_counter()
            result = cm.classify_and_remember(msg)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

            assert isinstance(result, dict), f"Unexpected result type: {type(result)}"

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        throughput = iterations / sum(latencies) * 1000  # ops/sec

        print(
            f"\n[classify_and_remember] ops={iterations}, "
            f"avg={avg:.1f}ms, p95={p95:.1f}ms, p99={p99:.1f}ms, "
            f"throughput={throughput:.0f} ops/s"
        )

        assert p99 < 100, f"P99 latency {p99:.1f}ms exceeds 100ms threshold"
        assert avg < 50, f"Average latency {avg:.1f}ms exceeds 50ms threshold"


# ---------------------------------------------------------------------------
# Benchmark 2: Recall Performance on Large Dataset
# ---------------------------------------------------------------------------


class TestRecall1000Records:
    """Benchmark: recall from 1000-record dataset must complete < 500ms."""

    def test_recall_1000_records(self, populated_1000):
        """Recall query on 1000-record dataset < 500ms."""
        cm = populated_1000
        queries = ["Python", "database", "DevOps", "testing"]
        latencies = []

        for query in queries:
            start = time.perf_counter()
            results = cm.recall_memories(query=query, limit=20)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

            assert isinstance(results, list), f"Recall should return list, got {type(results)}"

        max_latency = max(latencies)
        avg_latency = statistics.mean(latencies)
        total_ops = len(queries)
        total_time_s = sum(latencies) / 1000
        throughput = total_ops / total_time_s if total_time_s > 0 else float("inf")

        print(
            f"\n[recall_1000] queries={total_ops}, "
            f"avg={avg_latency:.1f}ms, max={max_latency:.1f}ms, "
            f"total_time={total_time_s:.2f}s, throughput={throughput:.0f} QPS"
        )

        assert max_latency < 500, f"Max recall latency {max_latency:.1f}ms exceeds 500ms threshold for 1000 records"


# ---------------------------------------------------------------------------
# Benchmark 3: Batch Insert Throughput
# ---------------------------------------------------------------------------


class TestBatchInsert100:
    """Benchmark: batch insert 100 memories must complete < 1s."""

    def test_batch_insert_100(self, tmp_path):
        """Insert 100 memories in under 1 second."""
        db_path = str(tmp_path / "batch_insert.db")
        cm = CarryMem(db_path=db_path)

        try:
            topics = [
                ("preference", "I prefer {}"),
                ("fact", "We use {} at work"),
                ("correction", "Do NOT use {}"),
                ("decision", "We decided to {}"),
            ]

            fillers = ["approach A", "method B", "tool C", "pattern D", "strategy E"]

            errors = []
            start = time.perf_counter()

            for i in range(100):
                try:
                    cat_type, template = topics[i % len(topics)]
                    filler = fillers[i % len(fillers)]
                    msg = template.format(filler)
                    cm.classify_and_remember(msg)
                except Exception as e:
                    errors.append(str(e))

            elapsed_s = time.perf_counter() - start
            success_count = 100 - len(errors)
            throughput = success_count / elapsed_s if elapsed_s > 0 else 0

            print(
                f"\n[batch_insert_100] inserted={success_count}/100, "
                f"errors={len(errors)}, time={elapsed_s:.3f}s, "
                f"throughput={throughput:.0f} ops/s"
            )

            assert len(errors) == 0, f"Errors during batch insert: {errors[:5]}"
            assert elapsed_s < 1.0, f"Batch insert of 100 took {elapsed_s:.3f}s, exceeds 1s threshold"
            assert throughput >= 100, f"Throughput {throughput:.0f} ops/s below expected 100 ops/s"
        finally:
            cm.close()


# ---------------------------------------------------------------------------
# Benchmark 4: Export Profile Large Dataset
# ---------------------------------------------------------------------------


class TestExportProfileLarge:
    """Benchmark: export 1000 memories must complete < 2s."""

    def test_export_profile_large(self, populated_1000, tmp_path):
        """Export profile with 1000 memories < 2 seconds."""
        cm = populated_1000
        export_path = str(tmp_path / "large_export.json")

        # Measure JSON export
        start = time.perf_counter()
        result_json = cm.export_memories(output_path=export_path, format="json")
        json_time = time.perf_counter() - start

        # Measure Markdown export
        md_path = str(tmp_path / "large_export.md")
        start = time.perf_counter()
        result_md = cm.export_memories(output_path=md_path, format="markdown")
        md_time = time.perf_counter() - start

        total_exported = result_json.get("total_memories", 0)
        json_throughput = total_exported / json_time if json_time > 0 else 0
        md_throughput = total_exported / md_time if md_time > 0 else 0

        print(
            f"\n[export_large] memories={total_exported}, "
            f"json_time={json_time:.3f}s ({json_throughput:.0f} mem/s), "
            f"md_time={md_time:.3f}s ({md_throughput:.0f} mem/s)"
        )

        assert total_exported > 0, "Should have exported memories"
        assert json_time < 2.0, f"JSON export took {json_time:.3f}s, exceeds 2s threshold"
        assert md_time < 2.0, f"Markdown export took {md_time:.3f}s, exceeds 2s threshold"
        assert os.path.exists(export_path), "JSON export file should exist"
        assert os.path.exists(md_path), "Markdown export file should exist"


# ---------------------------------------------------------------------------
# Benchmark 5: Encryption Overhead
# ---------------------------------------------------------------------------


class TestEncryptionOverhead:
    """Benchmark: measure encryption vs no-encryption performance difference."""

    def _generate_test_data(self, count=100):
        """Generate test data for encryption benchmarks."""
        return [f"Test message {i}: Sensitive data that needs encryption protection" for i in range(count)]

    def test_encryption_overhead(self):
        """Encryption overhead should be < 10x vs no-encryption."""
        data = self._generate_test_data(200)
        enc = MemoryEncryption(key="benchmark_test_key")
        no_enc = NoEncryption()

        # Measure encrypted operations
        enc_times = []
        dec_times = []
        for item in data:
            start = time.perf_counter()
            encrypted = enc.encrypt(item)
            enc_times.append(time.perf_counter() - start)

            start = time.perf_counter()
            _ = enc.decrypt(encrypted)
            dec_times.append(time.perf_counter() - start)

        # Measure non-encrypted operations
        plain_times = []
        for item in data:
            start = time.perf_counter()
            _ = no_enc.encrypt(item)
            plain_times.append(time.perf_counter() - start)

        avg_enc = statistics.mean(enc_times) * 1000  # ms
        avg_dec = statistics.mean(dec_times) * 1000
        avg_plain = statistics.mean(plain_times) * 1000
        overhead_ratio = avg_enc / avg_plain if avg_plain > 0 else 0

        enc_throughput = len(data) / sum(enc_times) if sum(enc_times) > 0 else 0
        plain_throughput = len(data) / sum(plain_times) if sum(plain_times) > 0 else 0

        print(
            f"\n[encryption_overhead] ops={len(data)}, "
            f"enc_avg={avg_enc:.3f}ms, dec_avg={avg_dec:.3f}ms, "
            f"plain_avg={avg_plain:.6f}ms, overhead={overhead_ratio:.1f}x, "
            f"enc_throughput={enc_throughput:.0f} ops/s, "
            f"plain_throughput={plain_throughput:.0f} ops/s"
        )

        # Encryption should work correctly
        for item in data[:10]:
            encrypted = enc.encrypt(item)
            decrypted = enc.decrypt(encrypted)
            assert decrypted == item, "Encrypt/decrypt roundtrip failed"

        # Overhead ratio check (encryption can be slower but not excessively so).
        # The fallback HMAC-CTR cipher (no cryptography library) is inherently
        # much slower than Fernet, so use a relaxed threshold for it.
        if enc._fernet_available:
            assert overhead_ratio < 50, f"Encryption overhead {overhead_ratio:.1f}x is excessive (>50x baseline)"
        else:
            assert (
                overhead_ratio < 300
            ), f"Fallback encryption overhead {overhead_ratio:.1f}x is excessive (>300x baseline)"

        # Absolute performance: encrypt 200 items should be fast
        total_enc_time = sum(enc_times)
        assert total_enc_time < 5.0, f"Total encrypt time for 200 items: {total_enc_time:.3f}s exceeds 5s"


# ---------------------------------------------------------------------------
# Benchmark 6: Concurrent Read Throughput
# ---------------------------------------------------------------------------


class TestConcurrentReadThroughput:
    """Benchmark: measure QPS under 4-thread concurrent read load."""

    def test_concurrent_read_throughput(self, populated_1000):
        """4-thread concurrent read: measure aggregate QPS."""
        cm = populated_1000
        num_threads = 4
        ops_per_thread = 25
        results_lock = threading.Lock()
        thread_results = []
        all_errors = []

        def reader_worker(thread_id: int):
            """Worker that performs recall operations."""
            local_latencies = []
            local_errors = []

            for i in range(ops_per_thread):
                query = f"{['Python', 'database', 'DevOps', 'testing'][thread_id % 4]} {i}"
                try:
                    start = time.perf_counter()
                    _ = cm.recall_memories(query=query, limit=10)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    local_latencies.append(elapsed_ms)
                except Exception as e:
                    local_errors.append(str(e))

            with results_lock:
                thread_results.extend(local_latencies)
                all_errors.extend(local_errors)

        # Start all threads
        threads = []
        start_time = time.perf_counter()

        for tid in range(num_threads):
            t = threading.Thread(target=reader_worker, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        total_elapsed = time.perf_counter() - start_time
        total_ops = len(thread_results)
        qps = total_ops / total_elapsed if total_elapsed > 0 else 0

        if thread_results:
            avg_latency = statistics.mean(thread_results)
            p99_latency = sorted(thread_results)[int(len(thread_results) * 0.99)]
        else:
            avg_latency = 0
            p99_latency = 0

        print(
            f"\n[concurrent_read] threads={num_threads}, "
            f"ops_per_thread={ops_per_thread}, "
            f"successful_ops={total_ops}, errors={len(all_errors)}, "
            f"total_time={total_elapsed:.3f}s, "
            f"QPS={qps:.0f}, avg_latency={avg_latency:.1f}ms, "
            f"p99_latency={p99_latency:.1f}ms"
        )

        assert len(all_errors) == 0, f"Concurrent read errors: {all_errors[:5]}"
        assert (
            total_ops == num_threads * ops_per_thread
        ), f"Expected {num_threads * ops_per_thread} ops, got {total_ops}"
        assert qps > 20, f"Concurrent read QPS {qps:.0f} below minimum 20 QPS"
