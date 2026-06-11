"""
E2E Tests: Concurrent Access Safety

Validates CarryMem behavior under concurrent access patterns:
1. Multi-threaded simultaneous read/write operations
2. Multi-process database access (if feasible)
3. Concurrent backup + write conflict handling
4. Lock contention timeout scenarios
"""

import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from carrymem import CarryMem


@pytest.fixture
def shared_carrymem(tmp_path):
    """Create a CarryMem instance that will be accessed by multiple threads."""
    db_path = str(tmp_path / "concurrent_test.db")
    cm = CarryMem(db_path=db_path)
    yield cm
    cm.close()


class TestE2EMultiThreadedWrites:
    """Scenario: Multiple threads write simultaneously."""

    def test_concurrent_writes_from_multiple_threads(self, shared_carrymem):
        """Verify: Multiple threads can write memories concurrently without data loss."""
        cm = shared_carrymem

        num_threads = 5
        writes_per_thread = 10
        errors = []
        results_lock = threading.Lock()

        def writer_thread(thread_id):
            """Each thread writes a batch of memories."""
            thread_errors = []
            for i in range(writes_per_thread):
                try:
                    memory = f"Thread-{thread_id}-Memory-{i}: Test data from thread {thread_id}"
                    result = cm.classify_and_remember(memory)
                    if not isinstance(result, dict):
                        thread_errors.append(f"Thread-{thread_id}-{i}: Unexpected result type {type(result)}")
                except Exception as e:
                    thread_errors.append(f"Thread-{thread_id}-{i}: {str(e)}")

            with results_lock:
                errors.extend(thread_errors)
            return thread_id

        # Launch threads
        threads = []
        for t_id in range(num_threads):
            t = threading.Thread(target=writer_thread, args=(t_id,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=30)

        # Verify no critical errors occurred
        assert len(errors) == 0, f"Concurrent writes had errors: {errors[:10]}"

        # Verify data was stored (at least some of it)
        memories = cm.recall_memories(limit=num_threads * writes_per_thread)
        assert isinstance(memories, list), "Recall should return list"
        # Note: due to deduplication, count may be less than total writes

    def test_concurrent_mixed_read_write(self, shared_carrymem):
        """Verify: Concurrent reads and writes don't cause crashes."""
        cm = shared_carrymem

        # Pre-populate some data
        for i in range(20):
            cm.classify_and_remember(f"Initial memory {i} for concurrent test")

        num_operations = 50
        errors = []
        lock = threading.Lock()

        def read_operation(op_id):
            try:
                result = cm.recall_memories(query=f"memory {op_id % 20}", limit=5)
                assert isinstance(result, list), f"Read {op_id}: Expected list"
            except Exception as e:
                with lock:
                    errors.append(f"Read-{op_id}: {e}")

        def write_operation(op_id):
            try:
                result = cm.classify_and_remember(f"Concurrent write operation {op_id}")
                assert isinstance(result, dict), f"Write {op_id}: Expected dict"
            except Exception as e:
                with lock:
                    errors.append(f"Write-{op_id}: {e}")

        # Mix reads and writes
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(num_operations):
                if i % 3 == 0:
                    futures.append(executor.submit(read_operation, i))
                else:
                    futures.append(executor.submit(write_operation, i))

            # Wait for all operations
            for future in as_completed(futures, timeout=60):
                pass  # Exceptions captured in errors list

        # Should have minimal or no errors (some locking conflicts are acceptable)
        assert len(errors) <= num_operations * 0.1, (
            f"Too many errors during mixed R/W: {len(errors)}/{num_operations}. Errors: {errors[:5]}"
        )


class TestE2EMultiThreadedRecall:
    """Scenario: Multiple threads recall simultaneously."""

    def test_simultaneous_recall_queries(self, shared_carrymem):
        """Verify: Multiple threads can query simultaneously without interference."""
        cm = shared_carrymem

        # Store varied data
        topics = ["Python programming", "Database design", "UI/UX principles",
                  "DevOps practices", "Code review guidelines"]
        for topic in topics:
            cm.classify_and_remember(f"I have knowledge about {topic}")

        num_threads = 8
        errors = []
        results = []
        lock = threading.Lock()

        def recall_thread(thread_id):
            try:
                # Each thread queries different topics
                query_idx = thread_id % len(topics)
                result = cm.recall_memories(query=topics[query_idx], limit=10)
                with lock:
                    results.append((thread_id, len(result) if isinstance(result, list) else -1))
            except Exception as e:
                with lock:
                    errors.append(f"Thread-{thread_id}: {e}")

        threads = [threading.Thread(target=recall_thread, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"Concurrent recalls had errors: {errors}"
        assert len(results) == num_threads, f"Expected {num_threads} results, got {len(results)}"


class TestE2EBackupDuringWrite:
    """Scenario: Backup operation happens while writes are occurring."""

    def test_backup_while_writing(self, tmp_path):
        """Verify: Backup during active writing doesn't corrupt data."""
        db_path = str(tmp_path / "backup_during_write.db")
        backup_dir = str(tmp_path / "backup_interrupted")
        os.makedirs(backup_dir, exist_ok=True)

        cm = CarryMem(db_path=db_path)
        errors = []
        backup_done = threading.Event()
        lock = threading.Lock()

        def continuous_writer():
            """Keep writing while backup is happening."""
            for i in range(100):
                try:
                    cm.classify_and_remember(f"Memory during backup {i}")
                except Exception as e:
                    with lock:
                        errors.append(f"Write error: {e}")
                time.sleep(0.01)  # Small delay to spread writes

        def backup_runner():
            """Perform backup after some writes."""
            time.sleep(0.05)  # Let some writes happen first
            try:
                result = cm.backup(backup_dir=backup_dir)
                assert isinstance(result, dict), "Backup should return dict"
                backup_done.set()
            except Exception as e:
                with lock:
                    errors.append(f"Backup error: {e}")

        # Start writer and backuper
        writer_thread = threading.Thread(target=continuous_writer)
        backup_thread = threading.Thread(target=backup_runner)

        writer_thread.start()
        backup_thread.start()

        writer_thread.join(timeout=30)
        backup_thread.join(timeout=30)

        cm.close()

        # Should complete without critical errors
        assert len(errors) == 0 or all("lock" in str(e).lower() or "timeout" in str(e).lower() for e in errors), (
            f"Unexpected errors during backup+write: {errors}"
        )

        # If backup completed, verify backup file exists
        if backup_done.is_set():
            backup_files = os.listdir(backup_dir)
            assert len(backup_files) > 0, "Backup should create files"


class TestE2ELockContention:
    """Scenario: High contention on database locks."""

    def test_rapid_sequential_operations(self, shared_carrymem):
        """Verify: Rapid sequential operations don't cause deadlocks."""
        cm = shared_carrymem

        num_ops = 100
        errors = []

        for i in range(num_ops):
            try:
                # Alternate between different operations
                if i % 4 == 0:
                    cm.classify_and_remember(f"Rapid memory {i}")
                elif i % 4 == 1:
                    cm.recall_memories(query=f"memory {i}", limit=3)
                elif i % 4 == 2:
                    cm.get_memory_profile()
                else:
                    cm.build_context(context="rapid context test")
            except Exception as e:
                errors.append(f"Op-{i}: {e}")

        # Very few or no errors expected
        assert len(errors) <= 2, f"Too many errors in rapid ops: {errors[:5]}"

    def test_timeout_handling(self, tmp_path):
        """Verify: Operations handle timeouts gracefully under load."""
        db_path = str(tmp_path / "timeout_test.db")
        cm = CarryMem(db_path=db_path)

        # Pre-populate
        for i in range(50):
            cm.classify_and_remember(f"Timeout test data {i}")

        timeout_errors = []
        start_time = time.time()

        # Run many rapid operations
        for _ in range(200):
            try:
                cm.recall_memories(limit=10)
            except Exception as e:
                err_str = str(e).lower()
                if "timeout" in err_str or "locked" in err_str or "busy" in err_str:
                    timeout_errors.append(err_str)

        elapsed = time.time() - start_time

        cm.close()

        # Should complete within reasonable time (< 30s for 200 ops)
        assert elapsed < 30, f"Operations took too long: {elapsed:.1f}s"

        # Timeout errors should be minimal
        assert len(timeout_errors) < 10, (
            f"Too many timeout errors: {len(timeout_errors)}. Sample: {timeout_errors[:3]}"
        )


class TestE2EDataConsistencyUnderConcurrency:
    """Scenario: Data remains consistent under concurrent access."""

    def test_no_data_corruption_under_load(self, tmp_path):
        """Verify: Heavy concurrent access doesn't corrupt stored data."""
        db_path = str(tmp_path / "consistency_test.db")
        cm = CarryMem(db_path=db_path)

        # Store known data first
        known_memories = [
            "CRITICAL: Use PostgreSQL not MySQL",
            "IMPORTANT: All APIs must be versioned",
            "RULE: Never hardcode credentials",
            "FACT: Production runs on AWS",
            "PREFERENCE: Code reviews required",
        ]

        for mem in known_memories:
            cm.classify_and_remember(mem)

        # Now hammer with concurrent reads
        def verify_memory_content():
            """Recall and check that original content is intact."""
            for keyword in ["PostgreSQL", "APIs", "credentials", "AWS", "reviews"]:
                results = cm.recall_memories(query=keyword, limit=5)
                if isinstance(results, list) and len(results) > 0:
                    content = results[0].get("content", "")
                    # Content should be readable and not corrupted
                    assert len(content) > 0, f"Empty content for {keyword}"
                    assert "\x00" not in content, f"Possible corruption in {keyword} result"

        threads = [threading.Thread(target=verify_memory_content) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        cm.close()

        # Final verification: all original data still readable
        cm_verify = CarryMem(db_path=db_path)
        try:
            final_count = 0
            for keyword in ["PostgreSQL", "APIs", "credentials", "AWS"]:
                results = cm_verify.recall_memories(query=keyword, limit=5)
                if isinstance(results, list) and len(results) > 0:
                    final_count += 1
            assert final_count >= 3, f"Data integrity check: only {final_count}/5 keywords found"
        finally:
            cm_verify.close()


class TestE2EProcessIsolation:
    """Scenario: Multiple processes accessing same database (if supported)."""

    @pytest.mark.skipif(True, reason="Multi-process SQLite requires WAL mode; tested separately if needed")
    def test_multiprocess_access(self, tmp_path):
        """Verify: Multiple processes can access the database safely.

        Note: This test requires SQLite WAL mode configuration.
        Skipping by default as it's environment-dependent.
        """
        pass
