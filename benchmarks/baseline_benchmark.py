#!/usr/bin/env python3
"""MCE Performance Baseline Benchmark - T1.1

Establishes performance baseline for Phase 1 optimization.
Measures: retrieve_memories, process_message, cache efficiency, memory usage.

Usage:
    python benchmarks/baseline_benchmark.py [--iterations 1000] [--output baseline_results.json]
"""

import argparse
import json
import os
import statistics
import sys
import time
import tracemalloc
from datetime import datetime
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class PerformanceBaselineBenchmark:
    """Performance baseline benchmark for MCE optimization tracking."""

    def __init__(self, iterations: int = 1000):
        self.iterations = iterations
        self.results: Dict[str, Any] = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'iterations': iterations,
                'python_version': sys.version.split()[0],
            },
            'retrieve_memories': {},
            'process_message': {},
            'cache_efficiency': {},
            'memory_usage': {},
            'summary': {}
        }
        self.engine = None

    def setup(self):
        """Initialize engine and seed test data."""
        from memory_classification_engine import MemoryClassificationEngine

        print("[Setup] Initializing MemoryClassificationEngine...")
        start = time.time()
        self.engine = MemoryClassificationEngine()
        init_time = time.time() - start
        print(f"[Setup] Engine initialized in {init_time*1000:.2f}ms")

        self.results['metadata']['engine_init_ms'] = round(init_time * 1000, 2)

        print("[Setup] Seeding test data...")
        self._seed_test_data()

    def _seed_test_data(self):
        """Seed memories for benchmark testing."""
        test_messages = [
            ("user preference", "I prefer using double quotes for all string literals"),
            ("technical decision", "We chose PostgreSQL over MongoDB for our primary database"),
            ("correction", "That last approach was too complex, let's go simpler"),
            ("task", "Implement the user authentication module with JWT tokens"),
            ("preference", "Always use TypeScript strict mode in new projects"),
            ("decision", "Deploying to AWS us-east-1 region for lower latency"),
            ("fact", "The API rate limit is 100 requests per minute per user"),
            ("preference", "I like dark mode themes for all development tools"),
            ("correction", "Actually let's use Redis for caching instead of Memcached"),
            ("task", "Set up CI/CD pipeline with GitHub Actions"),
            ("decision", "Using FastAPI for the REST API backend"),
            ("preference", "Prefer async/await over callbacks for all I/O operations"),
            ("fact", "Database connection pool size is set to 20 connections"),
            ("correction", "Reverting the schema change, it broke the migration"),
            ("task", "Add unit tests for the payment processing module"),
            ("decision", "Migrating from JavaScript to TypeScript gradually"),
            ("preference", "Use environment variables for all configuration"),
            ("fact", "Session timeout is set to 30 minutes of inactivity"),
            ("correction", "The previous estimate was wrong, need 2 more weeks"),
            ("task", "Optimize the database queries on the dashboard page"),
            ("decision", "Adopting Event-Driven Architecture for microservices"),
            ("preference", "Always write docstrings for public functions"),
            ("fact", "Maximum file upload size is limited to 10MB"),
            ("correction", "Changing the API endpoint from /v1/users to /v2/accounts"),
            ("task", "Implement real-time notifications with WebSocket"),
            ("decision", "Using Docker Compose for local development environment"),
            ("preference", "Follow PEP 8 style guide for Python code"),
            ("fact", "Production runs on Ubuntu 22.04 LTS servers"),
            ("correction", "Removing the deprecated legacy authentication system"),
            ("task", "Create API documentation with OpenAPI/Swagger spec"),
            ("decision", "Switching from REST to GraphQL for mobile clients"),
            ("preference", "Prefer composition over inheritance in class design"),
        ]

        seeded_count = 0
        for category, message in test_messages:
            try:
                self.engine.process_message(message)
                seeded_count += 1
            except Exception as e:
                pass

        print(f"[Setup] Seeded {seeded_count} test memories")
        self.results['metadata']['seeded_memories'] = seeded_count

    def benchmark_retrieve_memories(self) -> Dict[str, Any]:
        """Benchmark retrieve_memories with various query patterns."""
        print("\n[Benchmark] retrieve_memories...")

        query_patterns = [
            ('empty_query', None),
            ('short_keyword', 'database'),
            ('medium_phrase', 'user preference'),
            ('long_sentence', 'What decisions did we make about the database'),
            ('type_filter_pref', 'preference', 'preference'),
            ('type_filter_decision', 'decision', 'decision'),
            ('with_limit_10', 'test', None, 10),
            ('with_limit_50', 'test', None, 50),
        ]

        latencies: List[float] = []
        pattern_results: Dict[str, Dict[str, float]] = {}

        for pattern_name in [p[0] for p in query_patterns]:
            pattern_results[pattern_name] = {'latencies': []}

        for i in range(self.iterations):
            pattern_idx = i % len(query_patterns)
            pattern = query_patterns[pattern_idx]
            name = pattern[0]
            query = pattern[1]
            mtype = pattern[2] if len(pattern) > 2 else None
            limit = pattern[3] if len(pattern) > 3 else 5

            start = time.perf_counter()
            try:
                if mtype:
                    result = self.engine.retrieve_memories(query=query, limit=limit, memory_type=mtype)
                else:
                    result = self.engine.retrieve_memories(query=query, limit=limit)
            except Exception as e:
                result = []
            elapsed = (time.perf_counter() - start) * 1000

            latencies.append(elapsed)
            pattern_results[name]['latencies'].append(elapsed)

        latencies.sort()
        self.results['retrieve_memories'] = {
            'total_calls': self.iterations,
            'p50_ms': round(statistics.median(latencies), 4),
            'p90_ms': round(latencies[int(len(latencies) * 0.9)], 4),
            'p95_ms': round(latencies[int(len(latencies) * 0.95)], 4),
            'p99_ms': round(latencies[int(len(latencies) * 0.99)], 4),
            'avg_ms': round(statistics.mean(latencies), 4),
            'min_ms': round(min(latencies), 4),
            'max_ms': round(max(latencies), 4),
            'std_ms': round(statistics.stdev(latencies) if len(latencies) > 1 else 0, 4),
            'total_ms': round(sum(latencies), 4),
        }

        pattern_summary = {}
        for name, data in pattern_results.items():
            data['latencies'].sort()
            n = len(data['latencies'])
            pattern_summary[name] = {
                'calls': n,
                'p50_ms': round(statistics.median(data['latencies']), 4),
                'p99_ms': round(data['latencies'][int(n * 0.99)] if n > 0 else 0, 4),
                'avg_ms': round(statistics.mean(data['latencies']), 4),
            }

        self.results['retrieve_memories']['by_pattern'] = pattern_summary

        r = self.results['retrieve_memories']
        print(f"  Total calls: {r['total_calls']}")
        print(f"  P50: {r['p50_ms']}ms | P95: {r['p95_ms']}ms | P99: {r['p99_ms']}ms")
        print(f"  Avg: {r['avg_ms']}ms | Min: {r['min_ms']}ms | Max: {r['max_ms']}ms")
        return self.results['retrieve_memories']

    def benchmark_process_message(self) -> Dict[str, Any]:
        """Benchmark process_message with various message types."""
        print("\n[Benchmark] process_message...")

        messages = [
            "I prefer using dark mode",
            "Let's switch to PostgreSQL",
            "The last approach was wrong",
            "Implement user login feature",
            "Remember to use TypeScript strict mode",
            "Deploy to production server",
            "Cache the API responses",
            "Fix the authentication bug",
            "Add unit tests for payment module",
            "Set up monitoring alerts",
        ]

        latencies: List[float] = []

        for i in range(self.iterations):
            msg = messages[i % len(messages)]
            start = time.perf_counter()
            try:
                result = self.engine.process_message(msg)
            except Exception as e:
                result = {}
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        self.results['process_message'] = {
            'total_calls': self.iterations,
            'p50_ms': round(statistics.median(latencies), 4),
            'p90_ms': round(latencies[int(len(latencies) * 0.9)], 4),
            'p95_ms': round(latencies[int(len(latencies) * 0.95)], 4),
            'p99_ms': round(latencies[int(len(latencies) * 0.99)], 4),
            'avg_ms': round(statistics.mean(latencies), 4),
            'min_ms': round(min(latencies), 4),
            'max_ms': round(max(latencies), 4),
            'std_ms': round(statistics.stdev(latencies) if len(latencies) > 1 else 0, 4),
            'total_ms': round(sum(latencies), 4),
        }

        r = self.results['process_message']
        print(f"  Total calls: {r['total_calls']}")
        print(f"  P50: {r['p50_ms']}ms | P95: {r['p95_ms']}ms | P99: {r['p99_ms']}ms")
        print(f"  Avg: {r['avg_ms']}ms | Min: {r['min_ms']}ms | Max: {r['max_ms']}ms")
        return self.results['process_message']

    def benchmark_cache_efficiency(self) -> Dict[str, Any]:
        """Measure cache hit/miss rates."""
        print("\n[Benchmark] Cache efficiency...")

        cache = getattr(self.engine, 'cache', None)
        if cache is None:
            print("  No cache found on engine instance")
            self.results['cache_efficiency'] = {'status': 'no_cache'}
            return self.results['cache_efficiency']

        queries = ['database', 'user', 'preference', 'decision', 'test']

        hits = 0
        misses = 0

        for _ in range(200):
            q = queries[_ % len(queries)]
            self.engine.retrieve_memories(query=q, limit=5)

        for _ in range(200):
            q = queries[_ % len(queries)]
            self.engine.retrieve_memories(query=q, limit=5)

        if hasattr(cache, 'get_stats'):
            stats = cache.get_stats()
            self.results['cache_efficiency'] = {
                'hit_count': stats.get('hit_count', 0),
                'miss_count': stats.get('miss_count', 0),
                'hit_rate_pct': round(stats.get('hit_rate', 0) * 100, 2),
                'size': stats.get('size', 0),
            }
        elif hasattr(cache, '_hit_count') and hasattr(cache, '_miss_count'):
            total = cache._hit_count + cache._miss_count
            hit_rate = (cache._hit_count / total * 100) if total > 0 else 0
            self.results['cache_efficiency'] = {
                'hit_count': cache._hit_count,
                'miss_count': cache._miss_count,
                'hit_rate_pct': round(hit_rate, 2),
                'size': getattr(cache, 'size', 0) or getattr(cache, '_size', 0),
            }
        else:
            self.results['cache_efficiency'] = {'status': 'unavailable'}

        c = self.results['cache_efficiency']
        if 'hit_rate_pct' in c:
            print(f"  Hit rate: {c['hit_rate_pct']}% | Hits: {c.get('hit_count', 'N/A')} | Misses: {c.get('miss_count', 'N/A')}")
        else:
            print(f"  Status: {c.get('status', 'unknown')}")
        return self.results['cache_efficiency']

    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """Measure memory usage during operations."""
        print("\n[Benchmark] Memory usage...")

        tracemalloc.start()

        snapshot_before = tracemalloc.take_snapshot()

        for _ in range(100):
            self.engine.retrieve_memories(query='test', limit=5)
            self.engine.process_message('Test message for memory benchmark')

        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')

        tracemalloc.stop()

        current = top_stats[0] if top_stats else None
        self.results['memory_usage'] = {
            'peak_kb': round(tracemalloc.get_traced_memory()[0] / 1024, 2) if tracemalloc.get_traced_memory()[0] > 0 else 0,
            'top_allocation_kb': round(current.size_diff / 1024, 2) if current else 0,
            'top_allocation_location': str(current) if current else 'N/A',
        }

        m = self.results['memory_usage']
        print(f"  Peak: {m['peak_kb']}KB")
        print(f"  Top allocation: {m['top_allocation_kb']}KB")
        return self.results['memory_usage']

    def generate_summary(self) -> Dict[str, Any]:
        """Generate overall summary and optimization targets."""
        rm = self.results.get('retrieve_memories', {})
        pm = self.results.get('process_message', {})

        p99_retrieve = rm.get('p99_ms', 0)
        target_p99_retrieve = p99_retrieve * 0.70
        improvement_pct = 30.0

        self.results['summary'] = {
            'baseline_date': datetime.now().isoformat(),
            'optimization_target': '+30% query efficiency',
            'retrieve_memories_baseline': {
                'p99_ms': p99_retrieve,
                'target_p99_ms': round(target_p99_retrieve, 4),
                'improvement_needed_ms': round(p99_retrieve - target_p99_retrieve, 4),
                'improvement_pct': improvement_pct,
            },
            'process_message_baseline': {
                'p99_ms': pm.get('p99_ms', 0),
                'avg_ms': pm.get('avg_ms', 0),
            },
            'cache_baseline': self.results.get('cache_efficiency', {}),
            'next_steps': [
                'T1.2: SmartCache预热机制实现',
                'T1.3: LRU缓存参数动态调整',
                'T1.4: 多级缓存穿透优化',
                'T1.5: 记忆ID哈希索引实现',
                'T1.6: 类型+时间复合索引',
                'T1.7: 关联关系预构建',
                'T1.8: 批量查询并行化改造',
                'T1.9: 性能回归验证（对比本基线）',
            ],
        }

        s = self.results['summary']
        rb = s['retrieve_memories_baseline']
        print(f"\n{'='*60}")
        print(f"BASELINE SUMMARY")
        print(f"{'='*60}")
        print(f"  retrieve_memories P99: {rb['p99_ms']}ms → Target: {rb['target_p99_ms']}ms ({rb['improvement_pct']}% improvement)")
        print(f"  Improvement needed: {rb['improvement_needed_ms']}ms reduction")
        print(f"  process_message P99: {pm.get('p99_ms', 'N/A')}ms")
        print(f"{'='*60}")
        return self.results['summary']

    def run_all(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        print("=" * 60)
        print("MCE Performance Baseline Benchmark")
        print(f"Iterations: {self.iterations}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 60)

        self.setup()
        self.benchmark_retrieve_memories()
        self.benchmark_process_message()
        self.benchmark_cache_efficiency()
        self.benchmark_memory_usage()
        self.generate_summary()

        return self.results

    def save_results(self, output_path: str):
        """Save results to JSON file."""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n[Done] Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='MCE Performance Baseline Benchmark')
    parser.add_argument('--iterations', type=int, default=1000, help='Number of iterations per benchmark (default: 1000)')
    parser.add_argument('--output', type=str, default='benchmarks/baseline_results.json', help='Output JSON file path')
    args = parser.parse_args()

    benchmark = PerformanceBaselineBenchmark(iterations=args.iterations)
    benchmark.run_all()
    benchmark.save_results(args.output)


if __name__ == '__main__':
    main()
