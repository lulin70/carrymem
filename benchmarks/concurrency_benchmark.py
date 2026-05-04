#!/usr/bin/env python3
"""
CarryMem 并发性能测试

测试多线程/多进程环境下的线程安全性和性能

Usage:
    python benchmarks/concurrency_benchmark.py
    python benchmarks/concurrency_benchmark.py --threads 20 --ops 100
"""

import concurrent.futures
import time
import argparse
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_concurrent_writes(num_threads=10, operations_per_thread=100):
    """测试并发写入性能"""
    print(f"\n🔄 Concurrent Write Test")
    print(f"   Threads: {num_threads}")
    print(f"   Operations/thread: {operations_per_thread}")
    print(f"   Total operations: {num_threads * operations_per_thread}")
    
    try:
        from memory_classification_engine import CarryMem
        
        cm = CarryMem()
        
        def write_memories(thread_id):
            """每个线程的写入操作"""
            local_errors = []
            for i in range(operations_per_thread):
                try:
                    cm.classify_and_remember(
                        f"Thread-{thread_id} Memory-{i}: "
                        f"This is a test memory about option {i % 10} "
                        f"for concurrent testing"
                    )
                except Exception as e:
                    local_errors.append(str(e))
            return len(local_errors) == 0, operations_per_thread
        
        start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_memories, i) for i in range(num_threads)]
            results = concurrent.futures.wait(futures, timeout=120)
        
        duration = time.time() - start
        total_ops = num_threads * operations_per_thread
        
        # 统计结果
        success_count = sum(1 for f in futures if f.result()[0])
        total_time = sum(f.result()[1] for f in futures)
        
        print(f"\n✅ Results:")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Throughput: {total_ops/duration:.0f} ops/sec")
        print(f"   Success rate: {success_count}/{num_threads} ({success_count/num_threads*100:.0f}%)")
        print(f"   Avg time/op: {duration/total_ops*1000:.2f}ms")
        
        # 验证数据完整性
        memories = cm.recall_memories("Thread", limit=100)
        print(f"   Sampled memories: {len(memories)}")
        
        cm.close()
        
        return {
            "test": "concurrent_writes",
            "threads": num_threads,
            "ops_per_thread": operations_per_thread,
            "total_ops": total_ops,
            "duration_seconds": duration,
            "throughput_ops_sec": total_ops / duration,
            "success_rate": success_count / num_threads,
        }
        
    except ImportError:
        print("❌ Cannot import CarryMem. Is it installed?")
        return None
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_concurrent_reads(num_threads=10, operations_per_thread=100):
    """测试并发读取性能"""
    print(f"\n📖 Concurrent Read Test")
    print(f"   Threads: {num_threads}")
    print(f"   Operations/thread: {operations_per_thread}")
    
    try:
        from memory_classification_engine import CarryMem
        
        cm = CarryMem()
        
        # 预填充数据
        print("   Pre-filling data...")
        for i in range(500):
            cm.classify_and_remember(f"Pre-fill data {i} for testing concurrency")
        
        def read_memories(thread_id):
            """每个线程的读取操作"""
            local_errors = []
            for i in range(operations_per_thread):
                try:
                    results = cm.recall_memories(f"data {i % 50}", limit=10)
                except Exception as e:
                    local_errors.append(str(e))
            return len(local_errors) == 0, operations_per_thread
        
        start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_memories, i) for i in range(num_threads)]
            results = concurrent.futures.wait(futures, timeout=60)
        
        duration = time.time() - start
        total_ops = num_threads * operations_per_thread
        
        success_count = sum(1 for f in futures if f.result()[0])
        
        print(f"\n✅ Results:")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Throughput: {total_ops/duration:.0f} reads/sec")
        print(f"   Success rate: {success_count}/{num_threads} ({success_count/num_threads*100:.0f}%)")
        print(f"   Avg time/read: {duration/total_ops*1000:.2f}ms")
        
        cm.close()
        
        return {
            "test": "concurrent_reads",
            "threads": num_threads,
            "ops_per_thread": operations_per_thread,
            "total_ops": total_ops,
            "duration_seconds": duration,
            "throughput_ops_sec": total_ops / duration,
            "success_rate": success_count / num_threads,
        }
        
    except ImportError:
        print("❌ Cannot import CarryMem.")
        return None


def test_mixed_workload(num_threads=5, ops_per_thread=50):
    """测试混合读写负载"""
    print(f"\n🔀 Mixed Workload Test (Read/Write)")
    print(f"   Threads: {num_threads}")
    print(f"   Ops per thread: {ops_per_thread}")
    
    try:
        from memory_classification_engine import CarryMem
        
        cm = CarryMem()
        
        def mixed_operations(thread_id):
            """混合读写操作"""
            errors = []
            
            # 70% 写入
            writes = int(ops_per_thread * 0.7)
            for i in range(writes):
                try:
                    cm.classify_and_remember(f"Mixed-{thread_id}-W{i}: Option {i%5}")
                except Exception as e:
                    errors.append(f"W:{e}")
            
            # 30% 读取
            reads = ops_per_thread - writes
            for i in range(reads):
                try:
                    cm.recall_memories(f"Option {i%20}", limit=5)
                except Exception as e:
                    errors.append(f"R:{e}")
            
            return len(errors) == 0, ops_per_thread
        
        start = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(num_threads)]
            results = concurrent.futures.wait(futures, timeout=90)
        
        duration = time.time() - start
        total_ops = num_threads * ops_per_thread
        
        success_count = sum(1 for f in futures if f.result()[0])
        
        print(f"\n✅ Results:")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Throughput: {total_ops/duration:.0f} ops/sec")
        print(f"   Success rate: {success_count}/{num_threads} ({success_count/num_threads*100:.0f}%)")
        
        cm.close()
        
        return {
            "test": "mixed_workload",
            "threads": num_threads,
            "ops_per_thread": ops_per_thread,
            "total_ops": total_ops,
            "duration_seconds": duration,
            "throughput_ops_sec": total_ops / duration,
            "success_rate": success_count / num_threads,
        }
        
    except ImportError:
        print("❌ Cannot import CarryMem.")
        return None


def main():
    parser = argparse.ArgumentParser(description='CarryMem Concurrency Benchmark')
    parser.add_argument('--threads', type=int, default=10,
                        help='Number of threads (default: 10)')
    parser.add_argument('--ops', type=int, default=100,
                        help='Operations per thread (default: 100)')
    parser.add_argument('--all', action='store_true',
                        help='Run all concurrency tests')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 CarryMem Concurrency Performance Tests")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Threads: {args.threads}")
    print(f"  Operations/thread: {args.ops}")
    
    all_results = []
    
    # 运行写入测试
    result1 = test_concurrent_writes(args.threads, args.ops)
    if result1:
        all_results.append(result1)
    
    if args.all:
        # 运行读取测试
        result2 = test_concurrent_reads(args.threads, args.ops)
        if result2:
            all_results.append(result2)
        
        # 运行混合负载测试
        result3 = test_mixed_workload(args.threads, args.ops // 2)
        if result3:
            all_results.append(result3)
    
    # 输出总结
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    for r in all_results:
        status = "✅" if r["success_rate"] > 0.9 else "⚠️"
        print(f"{status} {r['test']}: {r['throughput_ops_sec']:.0f} ops/sec ({r['success_rate']*100:.0f}% success)")
    
    print("\n✨ All concurrency tests completed!")
    
    # 保存结果
    output_file = f"benchmarks/concurrency_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "configuration": {"threads": args.threads, "ops": args.ops},
            "results": all_results,
        }, f, indent=2)
    
    print(f"📄 Results saved to: {output_file}")


if __name__ == "__main__":
    import json
    main()
