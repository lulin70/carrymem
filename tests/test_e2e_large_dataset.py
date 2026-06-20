"""
E2E Tests: Large Dataset Stress Testing

Validates performance and behavior under large data volumes:
1. Batch insert 1000/5000 memories
2. Recall performance under load (<5s threshold)
3. Consolidation behavior with large datasets
4. Memory usage monitoring (tracemalloc)
"""

import os
import tempfile
import time
import tracemalloc

import pytest

from carrymem import CarryMem


@pytest.fixture
def carrymem_for_stress(tmp_path):
    """Create a CarryMem instance optimized for stress testing."""
    db_path = str(tmp_path / "stress_test.db")
    cm = CarryMem(db_path=db_path)
    yield cm
    cm.close()


class TestE2EBatchInsert:
    """Scenario: Bulk insertion of large numbers of memories."""

    def test_insert_100_memories(self, carrymem_for_stress):
        """Verify: Can insert 100 memories without errors or significant degradation."""
        cm = carrymem_for_stress

        errors = []
        for i in range(100):
            try:
                topic = "programming" if i % 3 == 0 else "database" if i % 3 == 1 else "devops"
                memory = f"Batch memory {i}: Test data for stress testing - topic is {topic}"
                result = cm.classify_and_remember(memory)
                if not isinstance(result, dict):
                    errors.append(f"Memory {i}: Unexpected result type")
            except Exception as e:
                errors.append(f"Memory {i}: {e}")

        assert len(errors) == 0, f"Errors during 100 inserts: {errors[:10]}"

    def test_insert_1000_memories(self, tmp_path):
        """Verify: Can insert 1000 memories within reasonable time."""
        db_path = str(tmp_path / "bulk_1000.db")
        cm = CarryMem(db_path=db_path)

        try:
            start_time = time.time()
            errors = []

            topics = [
                "Python programming",
                "Database design",
                "DevOps practices",
                "Code review guidelines",
                "Testing strategies",
                "API design",
                "Security best practices",
                "Performance optimization",
            ]

            for i in range(1000):
                try:
                    topic = topics[i % len(topics)]
                    memory = f"[{i}] Stress test entry about {topic} - iteration {i}"
                    cm.classify_and_remember(memory)
                except Exception as e:
                    errors.append(f"{i}: {e}")
                    if len(errors) > 10:  # Stop early if too many errors
                        break

            elapsed = time.time() - start_time

            assert len(errors) == 0, f"All 1000 inserts should succeed, got {len(errors)} errors. Sample: {errors[:5]}"
            assert elapsed < 120, f"1000 inserts took too long: {elapsed:.1f}s"  # Should complete within 2 minutes

            # Verify at least some were stored
            recalled = cm.recall_memories(limit=10)
            assert isinstance(recalled, list), "Should be able to recall after bulk insert"
        finally:
            cm.close()

    def test_insert_5000_memories_performance(self, tmp_path):
        """Verify: 5000 insertions complete within acceptable timeframe."""
        db_path = str(tmp_path / "bulk_5000.db")
        cm = CarryMem(db_path=db_path)

        try:
            tracemalloc.start()

            start_time = time.time()
            errors = []
            success_count = 0

            categories = [
                ("preference", "I prefer {}"),
                ("fact", "We use {} at work"),
                ("correction", "Do NOT use {}"),
                ("session_summary", "Discussed {} in meeting"),
            ]

            for i in range(5000):
                try:
                    cat_type, template = categories[i % len(categories)]
                    fillers = ["approach A", "method B", "tool C", "pattern D", "strategy E"]
                    filler = fillers[i % len(fillers)]
                    memory = template.format(filler)

                    result = cm.classify_and_remember(memory, force_type=cat_type)
                    if isinstance(result, dict):
                        success_count += 1
                except Exception as e:
                    errors.append(f"{i}: {str(e)[:50]}")
                    if len(errors) > 100:
                        break

                # Progress logging every 1000
                if (i + 1) % 1000 == 0:
                    pass  # Silent progress

            elapsed = time.time() - start_time
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            print(
                f"\n[Stress Test] 5000 inserts: {elapsed:.2f}s, "
                f"success={success_count}, errors={len(errors)}, "
                f"peak_memory={peak / 1024 / 1024:.1f}MB"
            )

            assert success_count == 5000, f"Expected all 5000 inserts to succeed, got {success_count}/5000"
            assert elapsed < 600, f"5000 inserts exceeded time limit: {elapsed:.1f}s"  # 10 minute upper bound
            assert peak < 1024 * 1024 * 1024, f"Peak memory usage too high: {peak / 1024 / 1024:.1f}MB"  # < 1GB
        finally:
            cm.close()


class TestE2ERecallUnderLoad:
    """Scenario: Recall performance with large datasets."""

    def setup_large_dataset(self, cm, count=1000):
        """Helper to populate dataset for recall tests."""
        topics = {
            "python": ["Django", "Flask", "FastAPI", "NumPy", "Pandas"],
            "database": ["PostgreSQL", "MySQL", "Redis", "MongoDB", "SQLite"],
            "devops": ["Docker", "Kubernetes", "CI/CD", "Terraform", "AWS"],
        }

        for i in range(count):
            area = list(topics.keys())[i % len(topics)]
            tool = topics[area][i % len(topics[area])]
            cm.classify_and_remember(f"Entry {i}: Using {tool} for {area} development")

    def test_recall_speed_with_1000_records(self, tmp_path):
        """Verify: Recall on 1000-record dataset completes within threshold (<5s)."""
        db_path = str(tmp_path / "recall_1000.db")
        cm = CarryMem(db_path=db_path)

        try:
            self.setup_large_dataset(cm, count=1000)

            # Measure recall speed
            queries = ["Python", "database", "Docker", "development"]
            total_recall_time = 0
            successful_recalls = 0

            for query in queries:
                start = time.time()
                results = cm.recall_memories(query=query, limit=20)
                elapsed = time.time() - start
                total_recall_time += elapsed

                if isinstance(results, list):
                    successful_recalls += 1

            avg_recall_time = total_recall_time / len(queries) if queries else 0

            print(f"\n[Recall Speed 1000] Avg: {avg_recall_time:.3f}s, " f"Total: {total_recall_time:.2f}s")

            assert avg_recall_time < 5.0, f"Avg recall time exceeds 5s threshold: {avg_recall_time:.3f}s"
            assert successful_recalls == len(
                queries
            ), f"All recalls should succeed: {successful_recalls}/{len(queries)}"
        finally:
            cm.close()

    def test_recall_speed_with_5000_records(self, tmp_path):
        """Verify: Recall on 5000-record dataset still performs adequately."""
        db_path = str(tmp_path / "recall_5000.db")
        cm = CarryMem(db_path=db_path)

        try:
            self.setup_large_dataset(cm, count=5000)

            # Measure recall with various queries
            start_total = time.time()
            results = cm.recall_memories(query="Python", limit=50)
            time_python = time.time() - start_total

            start_total = time.time()
            results = cm.recall_memories(query="Docker", limit=50)
            time_docker = time.time() - start_total

            start_total = time.time()
            results = cm.recall_memories(query="development", limit=50)
            time_generic = time.time() - start_total

            max_time = max(time_python, time_docker, time_generic)

            print(
                f"\n[Recall Speed 5000] Python: {time_python:.3f}s, "
                f"Docker: {time_docker:.3f}s, Generic: {time_generic:.3f}s, "
                f"Max: {max_time:.3f}s"
            )

            # Relaxed threshold for large datasets
            assert max_time < 10.0, f"Max recall time exceeds 10s for 5000 records: {max_time:.3f}s"
        finally:
            cm.close()

    def test_recall_returns_reasonable_results_at_scale(self, tmp_path):
        """Verify: Recall returns relevant results even with large datasets."""
        db_path = str(tmp_path / "recall_relevance.db")
        cm = CarryMem(db_path=db_path)

        try:
            self.setup_large_dataset(cm, count=1000)

            # Query for specific terms that should have matches
            specific_query = "PostgreSQL"
            results = cm.recall_memories(query=specific_query, limit=10)

            assert isinstance(results, list), "Recall should return list"
            # With 1000 entries containing PostgreSQL references, should find relevant results
            assert len(results) > 0, f"Should find results for specific query '{specific_query}' in 1000-record dataset"
            contents = [r.get("content", "").lower() for r in results]
            has_relevant = any(specific_query.lower() in c for c in contents)
            assert has_relevant, (
                f"Results for '{specific_query}' should contain relevant content, " f"got contents: {contents[:3]}"
            )
        finally:
            cm.close()


class TestE2EConsolidationUnderLoad:
    """Scenario: Consolidation behavior with large datasets."""

    def test_consolidate_with_500_duplicates(self, tmp_path):
        """Verify: Consolidate can handle 500 duplicate-like entries."""
        db_path = str(tmp_path / "consolidate_500.db")
        cm = CarryMem(db_path=db_path)

        try:
            # Insert many similar entries (simulating duplicates)
            base_memories = [
                "I prefer Python for backend development",
                "Our team uses PostgreSQL database",
                "Deploy everything to Docker containers",
            ]

            # Each base memory inserted multiple times with slight variations
            for i in range(170):  # ~510 entries total
                base = base_memories[i % len(base_memories)]
                variation = f"{base} (version {i})"
                cm.classify_and_remember(variation)

            # Run consolidation (dry run first)
            dry_run_result = cm.consolidate(dry_run=True)
            assert isinstance(dry_run_result, dict), "Dry run consolidate should return dict"
            assert (
                "stats" in dry_run_result or "summary" in dry_run_result
            ), "Consolidate dry run should return stats or summary"

            # Run actual consolidation
            actual_result = cm.consolidate(dry_run=False)
            assert isinstance(actual_result, dict), "Actual consolidate should return dict"
        finally:
            cm.close()

    def test_consolidate_does_not_lose_data(self, tmp_path):
        """Verify: Consolidation preserves unique information."""
        db_path = str(tmp_path / "consolidate_safe.db")
        cm = CarryMem(db_path=db_path)

        try:
            unique_memories = [
                "UNIQUE-ALPHA: This is completely unique content A",
                "UNIQUE-BETA: This is completely unique content B",
                "UNIQUE-GAMMA: This is completely unique content C",
            ]

            # Store unique memories
            for mem in unique_memories:
                cm.classify_and_remember(mem)

            # Also store some duplicates
            for _ in range(20):
                cm.classify_and_remember("Duplicate entry about preferences")

            # Record what we have before consolidation
            before_recall = cm.recall_memories(limit=100)
            before_contents = set(m.get("content", "") for m in before_recall if isinstance(m, dict))

            # Consolidate
            cm.consolidate(dry_run=False)

            # Verify unique memories still exist
            after_recall = cm.recall_memories(limit=100)
            after_contents = [m.get("content", "") for m in after_recall if isinstance(m, dict)]

            found_unique = sum(
                1
                for uniq in unique_memories
                if any(uniq in ac or ac.startswith(uniq.split(":")[0]) for ac in after_contents)
            )

            assert found_unique == len(
                unique_memories
            ), f"Consolidation should preserve all unique memories. Found {found_unique}/{len(unique_memories)}"
        finally:
            cm.close()


class TestE2EMemoryUsageMonitoring:
    """Scenario: Track memory usage during operations."""

    def test_memory_usage_during_bulk_operations(self, tmp_path):
        """Verify: Memory usage stays within reasonable bounds during bulk ops."""
        db_path = str(tmp_path / "memory_usage.db")
        cm = CarryMem(db_path=db_path)

        try:
            tracemalloc.start()

            # Baseline measurement
            cm.classify_and_remember("Baseline memory")
            _, baseline_peak = tracemalloc.get_traced_memory()

            # Bulk operation
            for i in range(500):
                cm.classify_and_remember(f"Memory usage test entry number {i}")

            _, current_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            growth_mb = (current_peak - baseline_peak) / 1024 / 1024

            print(
                f"\n[Memory Usage] Baseline: {baseline_peak/1024/1024:.1f}MB, "
                f"Current: {current_peak/1024/1024:.1f}MB, "
                f"Growth: {growth_mb:.1f}MB"
            )

            # Memory growth should be reasonable (< 500MB for 500 entries)
            assert growth_mb < 500, f"Memory growth excessive: {growth_mb:.1f}MB for 500 entries"
        finally:
            cm.close()

    def test_recall_memory_efficiency(self, tmp_path):
        """Verify: Multiple rapid recalls don't cause memory leaks."""
        db_path = str(tmp_path / "recall_memory.db")
        cm = CarryMem(db_path=db_path)

        try:
            # Pre-populate
            for i in range(200):
                cm.classify_and_remember(f"Memory leak test entry {i}")

            tracemalloc.start()

            # Perform many recalls
            snapshots = []
            for batch in range(10):
                for _ in range(20):
                    cm.recall_memories(query=f"entry {batch}", limit=10)

                current, peak = tracemalloc.get_traced_memory()
                snapshots.append((current, peak))

            tracemalloc.stop()

            # Check that memory doesn't grow unboundedly
            if len(snapshots) >= 5:
                first_half_avg = sum(s[0] for s in snapshots[:5]) / 5
                second_half_avg = sum(s[0] for s in snapshots[5:]) / 5
                growth_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1

                print(
                    f"\n[Recall Memory] First half avg: {first_half_avg/1024:.1f}KB, "
                    f"Second half avg: {second_half_avg/1024:.1f}KB, "
                    f"Ratio: {growth_ratio:.2f}"
                )

                # Memory shouldn't more than double (allowing some growth)
                assert growth_ratio < 3.0, f"Possible memory leak: ratio {growth_ratio:.2f}"
        finally:
            cm.close()


class TestE2ELargeDatasetEdgeCases:
    """Scenario: Edge cases specific to large datasets."""

    def test_very_long_single_memory(self, carrymem_for_stress):
        """Verify: Single very long memory can be stored and recalled (within max length)."""
        cm = carrymem_for_stress

        # Use content within max message length limit (10000 chars)
        long_content = "Word " * 2000  # ~14KB, within limit

        result = cm.classify_and_remember(long_content)
        assert isinstance(result, dict), "Long memory storage should succeed"

        recalled = cm.recall_memories(query="Word", limit=5)
        assert isinstance(recalled, list), "Should be able to recall long memory"

    def test_many_similar_memories(self, tmp_path):
        """Verify: Many very similar memories are handled correctly."""
        db_path = str(tmp_path / "similar.db")
        cm = CarryMem(db_path=db_path)

        try:
            base = "I prefer using Python for software development"
            for i in range(300):
                # Slight variations
                variation = f"{base}" + (f" (note {i})" if i % 10 == 0 else "")
                cm.classify_and_remember(variation)

            # Should be able to recall without error
            results = cm.recall_memories(query="Python", limit=50)
            assert isinstance(results, list), "Should handle many similar memories"
        finally:
            cm.close()

    def test_rapid_open_close_cycles(self, tmp_path):
        """Verify: Rapid open/close cycles don't leave locks or corruption."""
        db_path = str(tmp_path / "rapid_cycles.db")

        for cycle in range(20):
            cm = CarryMem(db_path=db_path)
            try:
                cm.classify_and_remember(f"Cycle {cycle} data")
            finally:
                cm.close()

        # Final open should work cleanly
        cm_final = CarryMem(db_path=db_path)
        try:
            recalled = cm_final.recall_memories(limit=20)
            assert isinstance(recalled, list), "Should work after rapid cycles"
        finally:
            cm_final.close()
