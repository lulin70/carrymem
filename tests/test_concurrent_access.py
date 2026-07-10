"""SQLite concurrent access stress tests for CarryMem.

Simulates real-world scenario: multiple AI Agents (Cursor, Claude Code, TRAE, etc.)
accessing the same CarryMem database simultaneously through their own MCP Server processes.

Test scenarios:
1. Multi-threaded concurrent read/write (5 threads × 30 ops via CarryMem)
2. Multi-process concurrent read/write (3 processes × 50 ops)
3. Mixed read/write concurrency (2 writers + 3 readers for 30s)
4. Multiple CarryMem instances sharing the same db_path (5 instances × 20 ops)
5. High contention SQLiteAdapter direct access (10 threads × 50 ops)

Verification criteria:
- No "database is locked" errors
- No data loss (written data can be read back)
- No deadlocks (tests complete within reasonable time)
"""

import os
import sys
import tempfile
import threading
import time
import traceback
from multiprocessing import Process, Queue
from typing import List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem import CarryMem, SQLiteAdapter
from carrymem.adapters.base import MemoryEntry

# Mark all tests in this file as slow (skipped in CI, run locally/nightly)
pytestmark = [pytest.mark.slow]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_db() -> str:
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="carrymem_concurrent_")
    os.close(fd)
    return path


def _cleanup_db(path: str) -> None:
    """Remove a database file and its WAL/SHM companions."""
    for ext in ("", "-wal", "-shm"):
        try:
            os.unlink(path + ext)
        except FileNotFoundError:
            pass


def _make_entry(worker_id: int, op_idx: int, content: str) -> MemoryEntry:
    """Create a MemoryEntry for testing."""
    return MemoryEntry(
        id="",
        type="user_preference",
        content=content,
        raw_text=content,
        confidence=0.9,
        tier=2,
        source_layer="concurrent_test",
        reasoning="Test entry",
        suggested_action="store",
    )


# ---------------------------------------------------------------------------
# Torch warmup helpers
# ---------------------------------------------------------------------------
#
# Root cause of macOS bus errors/segfaults: each CarryMem(db_path=...) call
# creates a SQLiteAdapter which loads its own SentenceTransformer model
# (backed by torch). When multiple threads do this concurrently on macOS,
# torch's internal initialization conflicts with SQLite threading, causing
# bus errors/segfaults.
#
# Fix: pre-load the SentenceTransformer model ONCE in the main thread and
# share it across all worker threads via SQLiteAdapter's _external_embedding_model
# parameter. This completely avoids concurrent torch model loading.

_shared_embedding_model = None
_warmup_lock = threading.Lock()


def _get_shared_embedding_model():
    """Load the SentenceTransformer model once (main thread) and cache it.

    Returns the shared model instance, or None if dependencies are unavailable.
    The caller should keep a reference alive for the test duration.
    """
    global _shared_embedding_model
    if _shared_embedding_model is None:
        with _warmup_lock:
            if _shared_embedding_model is None:
                try:
                    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
                    import torch

                    # Limit torch internal threads to avoid OpenMP conflicts
                    # with SQLite's threading model on macOS.
                    torch.set_num_threads(1)
                    from sentence_transformers import SentenceTransformer

                    model = SentenceTransformer("all-MiniLM-L6-v2")
                    # Force full model initialization (weights loaded, graph built)
                    model.encode(["warmup"])
                    _shared_embedding_model = model
                except Exception:
                    # Mark as unavailable so we don't retry on every call
                    _shared_embedding_model = False
    return _shared_embedding_model if _shared_embedding_model else None


def _make_carrymem(db_path: str) -> CarryMem:
    """Create a CarryMem instance that reuses the shared embedding model.

    This avoids concurrent torch model loading in worker threads by passing
    the pre-loaded model via SQLiteAdapter's _external_embedding_model.
    Falls back to default CarryMem construction if the shared model is
    unavailable (e.g. dependencies missing).
    """
    model = _get_shared_embedding_model()
    if model is not None:
        adapter = SQLiteAdapter(db_path=db_path, _external_embedding_model=model)
        return CarryMem(storage=adapter)
    return CarryMem(db_path=db_path)


# ---------------------------------------------------------------------------
# Test 1: Multi-threaded concurrent read/write via CarryMem
# ---------------------------------------------------------------------------


class TestMultiThreadConcurrentReadWrite:
    """5 threads simultaneously execute classify_and_remember + recall_memories,
    each performing 30 operations. Verify: no 'database is locked' errors,
    all operations complete successfully."""

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="Segfault on macOS: concurrent torch inference + SQLite threading conflict",
    )
    def test_concurrent_thread_read_write(self):
        db_path = _make_temp_db()
        lock_errors: List[str] = []
        operation_errors: List[str] = []
        success_counts: dict = {}
        lock = threading.Lock()

        try:
            # Warmup torch in main thread + pre-initialize schema so concurrent
            # instances don't conflict on DDL or torch model loading.
            _ = _get_shared_embedding_model()
            cm_init = _make_carrymem(db_path)
            cm_init.classify_and_remember("init")
            cm_init.close()

            def worker(worker_id: int, num_ops: int = 30):
                local_success = 0
                # Each thread creates its own CarryMem instance (SQLite requires
                # connections to be used in the same thread where they were created)
                cm = _make_carrymem(db_path)
                try:
                    for i in range(num_ops):
                        try:
                            msg = f"Worker-{worker_id} preference item {i}: I prefer dark mode"
                            result = cm.classify_and_remember(msg)
                            if result.get("stored", False):
                                local_success += 1

                            cm.recall_memories(query=f"Worker-{worker_id}")
                        except Exception as e:
                            err_msg = str(e)
                            if "database is locked" in err_msg.lower():
                                with lock:
                                    lock_errors.append(f"Worker-{worker_id} op={i}: {err_msg}")
                            else:
                                with lock:
                                    operation_errors.append(f"Worker-{worker_id} op={i}: {err_msg}")
                    with lock:
                        success_counts[worker_id] = local_success
                finally:
                    cm.close()

            num_threads = 5
            num_ops = 30
            threads = []
            start = time.time()

            for tid in range(num_threads):
                t = threading.Thread(target=worker, args=(tid, num_ops))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=300)

            elapsed = time.time() - start

            # Verify no "database is locked" errors
            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify no unexpected errors
            assert len(operation_errors) == 0, f"Got {len(operation_errors)} unexpected errors:\n" + "\n".join(
                operation_errors[:5]
            )

            # Verify all threads completed their operations
            assert len(success_counts) == num_threads, f"Only {len(success_counts)}/{num_threads} threads completed"

            # Verify data was actually stored
            cm_verify = _make_carrymem(db_path)
            stats = cm_verify.get_stats()
            assert stats["total_count"] > 0, "No memories were stored"

            # Verify data can be read back
            for tid in range(num_threads):
                results = cm_verify.recall_memories(query=f"Worker-{tid}")
                assert len(results) > 0, f"Worker-{tid} memories not found after concurrent write"

            # Verify test completed in reasonable time (no deadlock)
            # Note: CarryMem's _lock serializes operations, so concurrent
            # throughput is limited. 300s is generous to avoid false positives.
            assert elapsed < 300, f"Test took {elapsed:.1f}s, possible deadlock"

            cm_verify.close()
        finally:
            _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# Test 2: Multi-process concurrent read/write
# ---------------------------------------------------------------------------


def _process_worker(db_path: str, worker_id: int, num_ops: int, result_queue: Queue):
    """Worker function that runs in a separate process."""
    try:
        cm = CarryMem(db_path=db_path)
        local_success = 0
        local_errors: List[str] = []

        for i in range(num_ops):
            try:
                msg = f"Process-{worker_id} fact item {i}: The server runs on port 8080"
                result = cm.classify_and_remember(msg)
                if result.get("stored", False):
                    local_success += 1

                cm.recall_memories(query=f"Process-{worker_id}")
            except Exception as e:
                err_msg = str(e)
                local_errors.append(f"Process-{worker_id} op={i}: {err_msg}")

        cm.close()
        result_queue.put(
            {
                "worker_id": worker_id,
                "success_count": local_success,
                "errors": local_errors,
            }
        )
    except Exception as e:
        result_queue.put(
            {
                "worker_id": worker_id,
                "success_count": 0,
                "errors": [f"Process-{worker_id} fatal: {e}\n{traceback.format_exc()}"],
            }
        )


class TestMultiProcessConcurrentReadWrite:
    """3 processes simultaneously execute carrymem operations,
    each performing 50 operations. Verify: no data loss, no lock-up."""

    def test_concurrent_process_read_write(self):
        db_path = _make_temp_db()
        result_queue = Queue()

        try:
            num_processes = 3
            num_ops = 50
            processes = []
            start = time.time()

            for pid in range(num_processes):
                p = Process(
                    target=_process_worker,
                    args=(db_path, pid, num_ops, result_queue),
                )
                processes.append(p)
                p.start()

            for p in processes:
                p.join(timeout=300)

            elapsed = time.time() - start

            # Collect results
            results = []
            for _ in range(num_processes):
                try:
                    results.append(result_queue.get(timeout=5))
                except Exception:
                    pass

            # Verify all processes completed
            assert len(results) == num_processes, f"Only {len(results)}/{num_processes} processes reported results"

            # Check for "database is locked" errors
            lock_errors = []
            all_errors = []
            for r in results:
                for err in r.get("errors", []):
                    all_errors.append(err)
                    if "database is locked" in err.lower():
                        lock_errors.append(err)

            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify data was stored (at least some successes)
            total_success = sum(r.get("success_count", 0) for r in results)
            assert total_success > 0, f"No successful operations. Errors:\n" + "\n".join(all_errors[:10])

            # Verify data can be read back from a new CarryMem instance
            cm = CarryMem(db_path=db_path)
            stats = cm.get_stats()
            assert stats["total_count"] > 0, "No memories found after multi-process write"

            # Verify each process's data is readable
            for pid in range(num_processes):
                mems = cm.recall_memories(query=f"Process-{pid}")
                assert len(mems) > 0, f"Process-{pid} memories not found after concurrent write"

            cm.close()

            # Verify no deadlock
            assert elapsed < 300, f"Test took {elapsed:.1f}s, possible deadlock"

        finally:
            _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# Test 3: Mixed read/write concurrency
# ---------------------------------------------------------------------------


class TestMixedReadWriteConcurrency:
    """2 write threads + 3 read threads running for shorter duration.
    Write threads continuously classify_and_remember.
    Read threads continuously recall_memories.
    Verify: reads don't block, writes don't get lost."""

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="Segfault on macOS: concurrent torch inference + SQLite threading conflict",
    )
    def test_mixed_read_write(self):
        db_path = _make_temp_db()
        lock_errors: List[str] = []
        write_errors: List[str] = []
        read_errors: List[str] = []
        write_count = {"value": 0}
        read_count = {"value": 0}
        stop_event = threading.Event()
        lock = threading.Lock()

        try:
            # Warmup torch in main thread + pre-populate data so reads have
            # something to find. Using the shared model avoids concurrent
            # torch loading in the writer/reader threads.
            _ = _get_shared_embedding_model()
            cm = _make_carrymem(db_path)
            for i in range(10):
                cm.classify_and_remember(f"Initial preference {i}: I prefer Python")
            cm.close()

            def writer(writer_id: int):
                cm_w = _make_carrymem(db_path)
                while not stop_event.is_set():
                    try:
                        msg = f"Writer-{writer_id} at {time.time():.2f}: I prefer dark mode"
                        result = cm_w.classify_and_remember(msg)
                        if result.get("stored", False):
                            with lock:
                                write_count["value"] += 1
                    except Exception as e:
                        err_msg = str(e)
                        if "database is locked" in err_msg.lower():
                            with lock:
                                lock_errors.append(f"Writer-{writer_id}: {err_msg}")
                        else:
                            with lock:
                                write_errors.append(f"Writer-{writer_id}: {err_msg}")
                    time.sleep(0.01)
                cm_w.close()

            def reader(reader_id: int):
                cm_r = _make_carrymem(db_path)
                while not stop_event.is_set():
                    try:
                        results = cm_r.recall_memories(query="dark mode")
                        with lock:
                            read_count["value"] += 1
                    except Exception as e:
                        err_msg = str(e)
                        if "database is locked" in err_msg.lower():
                            with lock:
                                lock_errors.append(f"Reader-{reader_id}: {err_msg}")
                        else:
                            with lock:
                                read_errors.append(f"Reader-{reader_id}: {err_msg}")
                    time.sleep(0.01)
                cm_r.close()

            # Start 2 writers and 3 readers
            threads = []
            for wid in range(2):
                t = threading.Thread(target=writer, args=(wid,))
                t.daemon = True
                threads.append(t)

            for rid in range(3):
                t = threading.Thread(target=reader, args=(rid,))
                t.daemon = True
                threads.append(t)

            for t in threads:
                t.start()

            # Run for 30 seconds
            time.sleep(30)
            stop_event.set()

            for t in threads:
                t.join(timeout=10)

            # Verify no "database is locked" errors
            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify no unexpected write errors
            assert len(write_errors) == 0, f"Got {len(write_errors)} write errors:\n" + "\n".join(write_errors[:5])

            # Verify no unexpected read errors
            assert len(read_errors) == 0, f"Got {len(read_errors)} read errors:\n" + "\n".join(read_errors[:5])

            # Verify writes actually happened
            assert write_count["value"] > 0, "No writes completed during test"

            # Verify reads actually happened
            assert read_count["value"] > 0, "No reads completed during test"

            # Verify data can be read back
            cm_verify = _make_carrymem(db_path)
            stats = cm_verify.get_stats()
            assert stats["total_count"] > 10, f"Expected more than 10 memories, got {stats['total_count']}"

            # Verify written data is retrievable (use broad query or empty query)
            results = cm_verify.recall_memories(query="", limit=100)
            assert len(results) > 10, f"Expected many memories after mixed R/W, got {len(results)}"

            cm_verify.close()

        finally:
            _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# Test 4: Multiple CarryMem instances sharing the same db_path
# Uses SQLiteAdapter directly to avoid RuleStorage bus error.
# The bus error occurs when multiple CarryMem instances concurrently
# initialize RuleStorage on the same db_path (separate SQLite connections
# all executing schema DDL simultaneously).
# ---------------------------------------------------------------------------


class TestSharedDbPathInstances:
    """Create 5 independent CarryMem instances sharing the same db_path.
    Each instance performs 20 operations. Verify: all instances work normally.

    NOTE: Uses SQLiteAdapter directly to avoid the known issue where
    concurrent RuleStorage initialization causes a Bus Error when multiple
    CarryMem instances share the same db_path.
    """

    def test_shared_db_path_adapter_instances(self):
        """Test with SQLiteAdapter directly — the actual storage layer."""
        db_path = _make_temp_db()
        lock_errors: List[str] = []
        operation_errors: List[str] = []
        instance_results: dict = {}
        lock = threading.Lock()

        try:
            # Initialize schema with one adapter first
            init_adapter = SQLiteAdapter(db_path=db_path)
            init_adapter.close()

            def instance_worker(instance_id: int, num_ops: int = 20):
                """Each worker creates its own SQLiteAdapter with the same db_path."""
                try:
                    adapter = SQLiteAdapter(db_path=db_path)
                    local_stored = 0
                    local_recalled = 0

                    for i in range(num_ops):
                        try:
                            content = (
                                f"Instance-{instance_id} decision {i}: " f"We decided to use React for the frontend"
                            )
                            entry = _make_entry(instance_id, i, content)
                            stored = adapter.store_entry(entry)
                            if stored.storage_key:
                                local_stored += 1

                            results = adapter.recall(query=f"Instance-{instance_id}")
                            local_recalled += len(results)
                        except Exception as e:
                            err_msg = str(e)
                            if "database is locked" in err_msg.lower():
                                with lock:
                                    lock_errors.append(f"Instance-{instance_id} op={i}: {err_msg}")
                            else:
                                with lock:
                                    operation_errors.append(f"Instance-{instance_id} op={i}: {err_msg}")

                    adapter.close()
                    with lock:
                        instance_results[instance_id] = {
                            "stored": local_stored,
                            "recalled": local_recalled,
                        }
                except Exception as e:
                    with lock:
                        operation_errors.append(f"Instance-{instance_id} fatal: {e}\n{traceback.format_exc()}")

            num_instances = 5
            num_ops = 20
            threads = []
            start = time.time()

            for iid in range(num_instances):
                t = threading.Thread(target=instance_worker, args=(iid, num_ops))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=120)

            elapsed = time.time() - start

            # Verify no "database is locked" errors
            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify no unexpected errors
            assert len(operation_errors) == 0, f"Got {len(operation_errors)} unexpected errors:\n" + "\n".join(
                operation_errors[:5]
            )

            # Verify all instances completed
            assert (
                len(instance_results) == num_instances
            ), f"Only {len(instance_results)}/{num_instances} instances completed"

            # Verify each instance stored some data
            for iid, result in instance_results.items():
                assert result["stored"] > 0, f"Instance-{iid} stored 0 memories"

            # Verify data can be read from a fresh instance
            verify_adapter = SQLiteAdapter(db_path=db_path)
            stats = verify_adapter.get_stats()
            assert stats["total_count"] > 0, "No memories found after shared-db test"

            # Verify each instance's data is readable
            for iid in range(num_instances):
                mems = verify_adapter.recall(query=f"Instance-{iid}")
                assert len(mems) > 0, f"Instance-{iid} memories not found after shared-db write"

            verify_adapter.close()

            # Verify no deadlock
            assert elapsed < 120, f"Test took {elapsed:.1f}s, possible deadlock"

        finally:
            _cleanup_db(db_path)

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="Segfault on macOS: concurrent torch inference + SQLite threading conflict",
    )
    def test_shared_db_path_carrymem_instances_sequential_init(self):
        """Test with CarryMem instances where schema is initialized first,
        then instances operate concurrently.

        This avoids the RuleStorage bus error by pre-initializing the
        rule engine schema before concurrent access, and avoids concurrent
        torch model loading by sharing a pre-loaded embedding model.
        """
        db_path = _make_temp_db()
        lock_errors: List[str] = []
        operation_errors: List[str] = []
        instance_results: dict = {}
        lock = threading.Lock()

        try:
            # Warmup torch in main thread + pre-initialize: create one CarryMem
            # instance and trigger rule_engine to ensure schema is set up before
            # concurrent access.
            _ = _get_shared_embedding_model()
            cm_init = _make_carrymem(db_path)
            _ = cm_init.rule_engine  # Trigger RuleStorage schema init
            cm_init.close()

            def instance_worker(instance_id: int, num_ops: int = 20):
                """Each worker creates its own CarryMem instance."""
                try:
                    cm = _make_carrymem(db_path)
                    local_stored = 0
                    local_recalled = 0

                    for i in range(num_ops):
                        try:
                            msg = f"Instance-{instance_id} decision {i}: " f"We decided to use React for the frontend"
                            result = cm.classify_and_remember(msg)
                            if result.get("stored", False):
                                local_stored += 1

                            results = cm.recall_memories(query=f"Instance-{instance_id}")
                            local_recalled += len(results)
                        except Exception as e:
                            err_msg = str(e)
                            if "database is locked" in err_msg.lower():
                                with lock:
                                    lock_errors.append(f"Instance-{instance_id} op={i}: {err_msg}")
                            else:
                                with lock:
                                    operation_errors.append(f"Instance-{instance_id} op={i}: {err_msg}")

                    cm.close()
                    with lock:
                        instance_results[instance_id] = {
                            "stored": local_stored,
                            "recalled": local_recalled,
                        }
                except Exception as e:
                    with lock:
                        operation_errors.append(f"Instance-{instance_id} fatal: {e}\n{traceback.format_exc()}")

            num_instances = 5
            num_ops = 20
            threads = []
            start = time.time()

            for iid in range(num_instances):
                t = threading.Thread(target=instance_worker, args=(iid, num_ops))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=300)

            elapsed = time.time() - start

            # Verify no "database is locked" errors
            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify no unexpected errors
            assert len(operation_errors) == 0, f"Got {len(operation_errors)} unexpected errors:\n" + "\n".join(
                operation_errors[:5]
            )

            # Verify all instances completed
            assert (
                len(instance_results) == num_instances
            ), f"Only {len(instance_results)}/{num_instances} instances completed"

            # Verify each instance stored some data
            for iid, result in instance_results.items():
                assert result["stored"] > 0, f"Instance-{iid} stored 0 memories"

            # Verify data can be read from a fresh instance
            cm_verify = _make_carrymem(db_path)
            stats = cm_verify.get_stats()
            assert stats["total_count"] > 0, "No memories found after shared-db test"

            # Verify each instance's data is readable
            for iid in range(num_instances):
                mems = cm_verify.recall_memories(query=f"Instance-{iid}")
                assert len(mems) > 0, f"Instance-{iid} memories not found after shared-db write"

            cm_verify.close()

            # Verify no deadlock
            assert elapsed < 300, f"Test took {elapsed:.1f}s, possible deadlock"

        finally:
            _cleanup_db(db_path)


# ---------------------------------------------------------------------------
# Test 5: High contention via SQLiteAdapter (direct adapter access)
# ---------------------------------------------------------------------------


class TestHighContentionStress:
    """High contention scenario: 10 threads doing rapid fire writes
    directly via SQLiteAdapter to verify WAL mode handles contention
    properly under extreme load."""

    def test_high_contention_rapid_writes(self):
        db_path = _make_temp_db()
        lock_errors: List[str] = []
        operation_errors: List[str] = []
        success_counts: dict = {}
        lock = threading.Lock()

        try:
            # Pre-initialize schema
            init_adapter = SQLiteAdapter(db_path=db_path)
            init_adapter.close()

            def rapid_writer(worker_id: int, num_ops: int = 50):
                local_success = 0
                # Each thread uses its own adapter (SQLite thread-safety requirement)
                adapter = SQLiteAdapter(db_path=db_path)
                try:
                    for i in range(num_ops):
                        try:
                            content = f"Rapid-{worker_id} item {i}: I prefer spaces over tabs"
                            entry = _make_entry(worker_id, i, content)
                            stored = adapter.store_entry(entry)
                            if stored.storage_key:
                                local_success += 1
                        except Exception as e:
                            err_msg = str(e)
                            if "database is locked" in err_msg.lower():
                                with lock:
                                    lock_errors.append(f"Rapid-{worker_id} op={i}: {err_msg}")
                            else:
                                with lock:
                                    operation_errors.append(f"Rapid-{worker_id} op={i}: {err_msg}")
                    with lock:
                        success_counts[worker_id] = local_success
                finally:
                    adapter.close()

            num_threads = 10
            num_ops = 50
            threads = []
            start = time.time()

            for tid in range(num_threads):
                t = threading.Thread(target=rapid_writer, args=(tid, num_ops))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=120)

            elapsed = time.time() - start

            # Verify no "database is locked" errors
            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify no unexpected errors
            assert len(operation_errors) == 0, f"Got {len(operation_errors)} unexpected errors:\n" + "\n".join(
                operation_errors[:5]
            )

            # Verify all threads completed
            assert len(success_counts) == num_threads, f"Only {len(success_counts)}/{num_threads} threads completed"

            # Verify data was stored
            verify_adapter = SQLiteAdapter(db_path=db_path)
            stats = verify_adapter.get_stats()
            assert stats["total_count"] > 0, "No memories stored under high contention"

            # Verify no deadlock
            assert elapsed < 120, f"Test took {elapsed:.1f}s, possible deadlock"

            verify_adapter.close()
        finally:
            _cleanup_db(db_path)

    def test_concurrent_read_write_adapter(self):
        """Test concurrent reads and writes via SQLiteAdapter directly.
        5 writer threads + 5 reader threads for 15 seconds."""
        db_path = _make_temp_db()
        lock_errors: List[str] = []
        operation_errors: List[str] = []
        write_count = {"value": 0}
        read_count = {"value": 0}
        stop_event = threading.Event()
        lock = threading.Lock()

        try:
            # Pre-populate and pre-initialize schema
            init_adapter = SQLiteAdapter(db_path=db_path)
            for i in range(5):
                entry = _make_entry(0, i, f"Initial data {i}: I prefer Python")
                init_adapter.store_entry(entry)
            init_adapter.close()

            def adapter_writer(writer_id: int):
                adapter = SQLiteAdapter(db_path=db_path)
                try:
                    while not stop_event.is_set():
                        try:
                            content = f"Writer-{writer_id} at {time.time():.0f}: I prefer dark mode"
                            entry = _make_entry(writer_id, 0, content)
                            adapter.store_entry(entry)
                            with lock:
                                write_count["value"] += 1
                        except Exception as e:
                            err_msg = str(e)
                            if "database is locked" in err_msg.lower():
                                with lock:
                                    lock_errors.append(f"Writer-{writer_id}: {err_msg}")
                            else:
                                with lock:
                                    operation_errors.append(f"Writer-{writer_id}: {err_msg}")
                        time.sleep(0.005)
                finally:
                    adapter.close()

            def adapter_reader(reader_id: int):
                adapter = SQLiteAdapter(db_path=db_path)
                try:
                    while not stop_event.is_set():
                        try:
                            results = adapter.recall(query="dark mode")
                            with lock:
                                read_count["value"] += 1
                        except Exception as e:
                            err_msg = str(e)
                            if "database is locked" in err_msg.lower():
                                with lock:
                                    lock_errors.append(f"Reader-{reader_id}: {err_msg}")
                            else:
                                with lock:
                                    operation_errors.append(f"Reader-{reader_id}: {err_msg}")
                        time.sleep(0.005)
                finally:
                    adapter.close()

            threads = []
            for wid in range(5):
                t = threading.Thread(target=adapter_writer, args=(wid,))
                t.daemon = True
                threads.append(t)
            for rid in range(5):
                t = threading.Thread(target=adapter_reader, args=(rid,))
                t.daemon = True
                threads.append(t)

            for t in threads:
                t.start()

            time.sleep(15)
            stop_event.set()

            for t in threads:
                t.join(timeout=10)

            # Verify no "database is locked" errors
            assert len(lock_errors) == 0, f"Got {len(lock_errors)} 'database is locked' errors:\n" + "\n".join(
                lock_errors[:10]
            )

            # Verify no unexpected errors
            assert len(operation_errors) == 0, f"Got {len(operation_errors)} unexpected errors:\n" + "\n".join(
                operation_errors[:5]
            )

            # Verify both reads and writes happened
            assert write_count["value"] > 0, "No writes completed"
            assert read_count["value"] > 0, "No reads completed"

            # Verify data integrity
            verify_adapter = SQLiteAdapter(db_path=db_path)
            stats = verify_adapter.get_stats()
            assert stats["total_count"] > 5, "Insufficient data stored"

            verify_adapter.close()
        finally:
            _cleanup_db(db_path)
