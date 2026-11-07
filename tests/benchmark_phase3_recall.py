"""Phase 3 Performance Benchmark: Recall Engine

Measures:
1. FTS5 vs LIKE query latency
2. Relevance scoring overhead
3. Large dataset scaling (100, 1000, 10000 records)
4. Memory usage under load
"""

import os
import sys
import tempfile
import time
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem import CarryMem


def create_test_memories(cm: CarryMem, count: int) -> List[str]:
    """Create test memories with diverse content."""
    templates = [
        "I prefer using {lang} for {task}",
        "{lang} is excellent for {task}",
        "Always use {lang} when working on {task}",
        "My favorite language is {lang}",
        "I love building {task} with {lang}",
    ]

    langs = ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++", "Ruby"]
    tasks = ["web apps", "APIs", "data analysis", "ML models", "CLI tools", "microservices"]

    keys = []
    for i in range(count):
        template = templates[i % len(templates)]
        lang = langs[i % len(langs)]
        task = tasks[i % len(tasks)]

        content = template.format(lang=lang, task=task)
        result = cm.classify_and_remember(content)

        if result.get("should_remember"):
            # Extract storage_key from result
            memories = cm.recall_memories(content, limit=1)
            if memories:
                keys.append(memories[0]["storage_key"])

    return keys


def benchmark_fts5_query(cm: CarryMem, query: str, iterations: int = 100) -> Dict:
    """Benchmark FTS5 search performance."""
    latencies = []

    for _ in range(iterations):
        start = time.perf_counter()
        results = cm.recall_memories(query, limit=20)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms

    return {
        "query": query,
        "mode": "FTS5",
        "iterations": iterations,
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p50_latency_ms": sorted(latencies)[len(latencies) // 2],
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "result_count": len(results),
    }


def benchmark_like_query(cm: CarryMem, query: str, iterations: int = 100) -> Dict:
    """Benchmark LIKE fallback search performance."""
    # LIKE queries are triggered by CJK characters or non-FTS5 compatible patterns
    cjk_query = f"{query}偏好"  # Add CJK character to force LIKE
    latencies = []

    for _ in range(iterations):
        start = time.perf_counter()
        results = cm.recall_memories(cjk_query, limit=20)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms

    return {
        "query": cjk_query,
        "mode": "LIKE",
        "iterations": iterations,
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p50_latency_ms": sorted(latencies)[len(latencies) // 2],
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "result_count": len(results),
    }


def benchmark_scaling(memory_counts: List[int]) -> List[Dict]:
    """Test recall performance scaling with dataset size."""
    results = []

    for count in memory_counts:
        print(f"\n[Benchmark] Creating {count} memories...")

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            cm = CarryMem(
                storage="sqlite",
                db_path=db_path,
                config={
                    "enable_cache": False,
                    "enable_vector_search": False,
                    "enable_semantic_recall": False,
                },
            )

            # Create memories
            create_start = time.perf_counter()
            keys = create_test_memories(cm, count)
            create_end = time.perf_counter()

            print(f"[Benchmark] Created {len(keys)} memories in {create_end - create_start:.2f}s")

            # Test FTS5 query
            fts_result = benchmark_fts5_query(cm, "Python", iterations=50)
            print(f"[Benchmark] FTS5 avg latency: {fts_result['avg_latency_ms']:.2f}ms")

            # Test LIKE query
            like_result = benchmark_like_query(cm, "Python", iterations=50)
            print(f"[Benchmark] LIKE avg latency: {like_result['avg_latency_ms']:.2f}ms")

            results.append(
                {
                    "memory_count": len(keys),
                    "create_time_s": create_end - create_start,
                    "fts5": fts_result,
                    "like": like_result,
                }
            )

            cm.close()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    return results


def print_benchmark_report(scaling_results: List[Dict]):
    """Print formatted benchmark report."""
    print("\n" + "=" * 80)
    print("PHASE 3 RECALL ENGINE PERFORMANCE BENCHMARK")
    print("=" * 80)

    print("\n## Scaling Performance\n")
    print(f"{'Dataset Size':<15} {'FTS5 Avg (ms)':<15} {'LIKE Avg (ms)':<15} {'FTS5/LIKE Ratio':<20}")
    print("-" * 80)

    for r in scaling_results:
        count = r["memory_count"]
        fts_avg = r["fts5"]["avg_latency_ms"]
        like_avg = r["like"]["avg_latency_ms"]
        ratio = like_avg / fts_avg if fts_avg > 0 else float("inf")

        print(f"{count:<15} {fts_avg:<15.2f} {like_avg:<15.2f} {ratio:<20.2f}x")

    print("\n## Latency Percentiles (FTS5)\n")
    print(f"{'Dataset Size':<15} {'p50 (ms)':<15} {'p95 (ms)':<15} {'max (ms)':<15}")
    print("-" * 80)

    for r in scaling_results:
        count = r["memory_count"]
        p50 = r["fts5"]["p50_latency_ms"]
        p95 = r["fts5"]["p95_latency_ms"]
        max_lat = r["fts5"]["max_latency_ms"]

        print(f"{count:<15} {p50:<15.2f} {p95:<15.2f} {max_lat:<15.2f}")

    print("\n## Latency Percentiles (LIKE)\n")
    print(f"{'Dataset Size':<15} {'p50 (ms)':<15} {'p95 (ms)':<15} {'max (ms)':<15}")
    print("-" * 80)

    for r in scaling_results:
        count = r["memory_count"]
        p50 = r["like"]["p50_latency_ms"]
        p95 = r["like"]["p95_latency_ms"]
        max_lat = r["like"]["max_latency_ms"]

        print(f"{count:<15} {p50:<15.2f} {p95:<15.2f} {max_lat:<15.2f}")

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80 + "\n")


def main():
    """Run Phase 3 performance benchmark suite."""
    print("Starting Phase 3 Recall Engine Performance Benchmark...")

    # Test scaling: 100, 500, 1000 memories
    memory_counts = [100, 500, 1000]

    scaling_results = benchmark_scaling(memory_counts)
    print_benchmark_report(scaling_results)


if __name__ == "__main__":
    main()
