#!/usr/bin/env python3
"""
Performance Benchmark for CarryMem

Measures performance metrics for various operations.

Usage:
    python performance_benchmark.py
    python performance_benchmark.py --scale 10000
    python performance_benchmark.py --output report.json
"""

import sys
import time
import json
import argparse
import tempfile
from pathlib import Path
from typing import Dict, List
import statistics

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory_classification_engine import CarryMem


class PerformanceBenchmark:
    """Performance benchmark suite for CarryMem"""
    
    def __init__(self, scale: int = 1000):
        """
        Initialize benchmark
        
        Args:
            scale: Number of operations to test
        """
        self.scale = scale
        self.results = {}
        
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "benchmark.db"
        
        # Initialize CarryMem
        self.cm = CarryMem(storage_path=str(self.db_path))
        
        print(f"🚀 Performance Benchmark")
        print(f"Scale: {scale} operations")
        print(f"Database: {self.db_path}\n")
    
    def benchmark_store(self) -> Dict:
        """Benchmark store operations"""
        print("📝 Benchmarking store operations...")
        
        test_contents = [
            "I prefer dark mode",
            "Use PostgreSQL for database",
            "Python is my favorite language",
            "Deploy on AWS",
            "Use React for frontend",
        ]
        
        times = []
        
        for i in range(self.scale):
            content = test_contents[i % len(test_contents)] + f" #{i}"
            
            start = time.perf_counter()
            self.cm.classify_and_remember(content)
            end = time.perf_counter()
            
            times.append((end - start) * 1000)  # Convert to ms
            
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{self.scale}")
        
        result = {
            "operation": "store",
            "count": self.scale,
            "total_time_ms": sum(times),
            "avg_time_ms": statistics.mean(times),
            "median_time_ms": statistics.median(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
        }
        
        self.results["store"] = result
        
        print(f"  ✅ Average: {result['avg_time_ms']:.2f}ms")
        print(f"  ✅ Median: {result['median_time_ms']:.2f}ms\n")
        
        return result
    
    def benchmark_recall(self) -> Dict:
        """Benchmark recall operations"""
        print("🔍 Benchmarking recall operations...")
        
        test_queries = [
            "dark mode",
            "PostgreSQL",
            "Python",
            "AWS",
            "React",
        ]
        
        times = []
        result_counts = []
        
        for i in range(min(self.scale, 1000)):  # Limit recall tests
            query = test_queries[i % len(test_queries)]
            
            start = time.perf_counter()
            results = self.cm.recall_memories(query, limit=10)
            end = time.perf_counter()
            
            times.append((end - start) * 1000)
            result_counts.append(len(results))
            
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{min(self.scale, 1000)}")
        
        result = {
            "operation": "recall",
            "count": len(times),
            "total_time_ms": sum(times),
            "avg_time_ms": statistics.mean(times),
            "median_time_ms": statistics.median(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "avg_results": statistics.mean(result_counts),
        }
        
        self.results["recall"] = result
        
        print(f"  ✅ Average: {result['avg_time_ms']:.2f}ms")
        print(f"  ✅ Median: {result['median_time_ms']:.2f}ms")
        print(f"  ✅ Avg Results: {result['avg_results']:.1f}\n")
        
        return result
    
    def benchmark_semantic_recall(self) -> Dict:
        """Benchmark semantic recall with expansion"""
        print("🌐 Benchmarking semantic recall...")
        
        test_queries = [
            "dark theme",  # Should find "dark mode"
            "database",    # Should find "PostgreSQL"
            "programming", # Should find "Python"
            "cloud",       # Should find "AWS"
            "UI framework", # Should find "React"
        ]
        
        times = []
        result_counts = []
        
        for i in range(min(self.scale // 2, 500)):
            query = test_queries[i % len(test_queries)]
            
            start = time.perf_counter()
            results = self.cm.recall_memories(query, limit=10)
            end = time.perf_counter()
            
            times.append((end - start) * 1000)
            result_counts.append(len(results))
            
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{min(self.scale // 2, 500)}")
        
        result = {
            "operation": "semantic_recall",
            "count": len(times),
            "total_time_ms": sum(times),
            "avg_time_ms": statistics.mean(times),
            "median_time_ms": statistics.median(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "avg_results": statistics.mean(result_counts),
        }
        
        self.results["semantic_recall"] = result
        
        print(f"  ✅ Average: {result['avg_time_ms']:.2f}ms")
        print(f"  ✅ Median: {result['median_time_ms']:.2f}ms\n")
        
        return result
    
    def benchmark_database_size(self) -> Dict:
        """Measure database size"""
        print("💾 Measuring database size...")
        
        db_size = self.db_path.stat().st_size
        memory_count = len(self.cm.recall_memories("", limit=100000))
        
        result = {
            "operation": "database",
            "size_bytes": db_size,
            "size_kb": db_size / 1024,
            "size_mb": db_size / (1024 * 1024),
            "memory_count": memory_count,
            "bytes_per_memory": db_size / memory_count if memory_count > 0 else 0,
        }
        
        self.results["database"] = result
        
        print(f"  ✅ Size: {result['size_mb']:.2f}MB")
        print(f"  ✅ Memories: {result['memory_count']}")
        print(f"  ✅ Bytes/Memory: {result['bytes_per_memory']:.0f}\n")
        
        return result
    
    def run_all(self) -> Dict:
        """Run all benchmarks"""
        print("="*60)
        print("Starting Performance Benchmark Suite")
        print("="*60 + "\n")
        
        start_time = time.time()
        
        # Run benchmarks
        self.benchmark_store()
        self.benchmark_recall()
        self.benchmark_semantic_recall()
        self.benchmark_database_size()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Summary
        self.results["summary"] = {
            "total_time_seconds": total_time,
            "scale": self.scale,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        print("="*60)
        print("Benchmark Complete!")
        print("="*60)
        print(f"Total Time: {total_time:.2f}s\n")
        
        return self.results
    
    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60 + "\n")
        
        if "store" in self.results:
            store = self.results["store"]
            print(f"📝 Store Operations:")
            print(f"   Average: {store['avg_time_ms']:.2f}ms")
            print(f"   Median:  {store['median_time_ms']:.2f}ms")
            print(f"   Range:   {store['min_time_ms']:.2f}ms - {store['max_time_ms']:.2f}ms\n")
        
        if "recall" in self.results:
            recall = self.results["recall"]
            print(f"🔍 Recall Operations:")
            print(f"   Average: {recall['avg_time_ms']:.2f}ms")
            print(f"   Median:  {recall['median_time_ms']:.2f}ms")
            print(f"   Range:   {recall['min_time_ms']:.2f}ms - {recall['max_time_ms']:.2f}ms\n")
        
        if "semantic_recall" in self.results:
            semantic = self.results["semantic_recall"]
            print(f"🌐 Semantic Recall:")
            print(f"   Average: {semantic['avg_time_ms']:.2f}ms")
            print(f"   Median:  {semantic['median_time_ms']:.2f}ms\n")
        
        if "database" in self.results:
            db = self.results["database"]
            print(f"💾 Database:")
            print(f"   Size:     {db['size_mb']:.2f}MB")
            print(f"   Memories: {db['memory_count']}")
            print(f"   Efficiency: {db['bytes_per_memory']:.0f} bytes/memory\n")
        
        print("="*60 + "\n")
    
    def save_results(self, output_path: str):
        """Save results to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"📊 Results saved to: {output_path}\n")
    
    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Performance Benchmark for CarryMem"
    )
    
    parser.add_argument(
        "--scale",
        type=int,
        default=1000,
        help="Number of operations to test (default: 1000)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON)"
    )
    
    args = parser.parse_args()
    
    # Run benchmark
    benchmark = PerformanceBenchmark(scale=args.scale)
    
    try:
        benchmark.run_all()
        benchmark.print_summary()
        
        if args.output:
            benchmark.save_results(args.output)
    
    finally:
        benchmark.cleanup()


if __name__ == "__main__":
    main()
