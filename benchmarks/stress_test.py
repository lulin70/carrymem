#!/usr/bin/env python3
"""
CarryMem 压力测试 - 极限负载测试

测试大规模数据集下的性能表现，包括：
- 大规模写入性能
- 大规模读取性能
- 数据库大小增长
- 内存使用情况

Usage:
    python benchmarks/stress_test.py
    python benchmarks/stress_test.py --size 50000
    python benchmarks/stress_test.py --size 100000 --output results/stress.json
"""

import time
import argparse
import sys
import os
import json
import tracemalloc

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def stress_test_large_dataset(size=100000, output_file=None):
    """
    测试大规模数据集的性能

    Args:
        size: 测试数据量（默认10万条）
        output_file: 结果输出文件路径
    """
    print(f"\n📊 Stress Test: Large Dataset ({size:,} memories)")
    print("=" * 60)

    try:
        from memory_classification_engine import CarryMem

        # 开始内存追踪
        tracemalloc.start()

        cm = CarryMem()
        results = {}

        # ========== 写入测试 ==========
        print("\n1️⃣  Write Phase")
        print(f"   Writing {size:,} memories...")

        write_errors = []
        start_time = time.time()
        start_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

        for i in range(size):
            try:
                cm.classify_and_remember(
                    f"Memory-{i}: This is a stress test memory about "
                    f"option {i % 10} for performance testing under heavy load"
                )
            except Exception as e:
                write_errors.append((i, str(e)))

            # 进度报告
            if (i + 1) % 10000 == 0:
                elapsed = time.time() - start_time
                current_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
                print(f"   Progress: {i+1:>6,}/{size:,} "
                      f"({(i+1)/size*100:.1f}%) - "
                      f"{elapsed:.1f}s - {current_mem:.1f}MB")

        write_duration = time.time() - start_time
        end_write_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

        print(f"\n✅ Write Complete:")
        print(f"   Duration: {write_duration:.2f}s")
        print(f"   Throughput: {size/write_duration:.0f} memories/sec")
        print(f"   Avg time: {write_duration/size*1000:.3f}ms/memory")
        print(f"   Errors: {len(write_errors)} ({len(write_errors)/size*100:.2f}%)")
        print(f"   Memory growth: {end_write_mem-start_mem:.1f}MB")

        if write_errors:
            print(f"\n⚠️  Sample errors:")
            for idx, err in write_errors[:5]:
                print(f"   [{idx}] {err}")

        results["write"] = {
            "total": size,
            "errors": len(write_errors),
            "error_rate": len(write_errors) / size,
            "duration_seconds": write_duration,
            "throughput_per_sec": size / write_duration,
            "avg_time_ms": write_duration / size * 1000,
            "memory_growth_mb": end_write_mem - start_mem,
        }

        # ========== 读取测试 ==========
        print("\n\n2️⃣  Read Phase")
        print(f"   Running 1,000 recall operations...")

        read_errors = []
        read_start = time.time()
        total_results = 0

        for i in range(1000):
            try:
                query = f"option {i % 10}"
                memories = cm.recall_memories(query, limit=100)
                total_results += len(memories)
            except Exception as e:
                read_errors.append((i, str(e)))

        read_duration = time.time() - read_start

        print(f"\n✅ Read Complete:")
        print(f"   Duration: {read_duration:.2f}s")
        print(f"   Throughput: {1000/read_duration:.0f} reads/sec")
        print(f"   Avg time: {read_duration/1000*1000:.2f}ms/read")
        print(f"   Errors: {len(read_errors)}")
        print(f"   Total results: {total_results:,}")

        results["read"] = {
            "total_operations": 1000,
            "errors": len(read_errors),
            "duration_seconds": read_duration,
            "throughput_per_sec": 1000 / read_duration,
            "avg_time_ms": read_duration / 1000 * 1000,
            "total_results": total_results,
        }

        # ========== 数据库统计 ==========
        print("\n\n3️⃣  Database Statistics")

        db_path = cm._adapter._db_path if hasattr(cm._adapter, '_db_path') else None
        if db_path and os.path.exists(db_path):
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"   Database path: {db_path}")
            print(f"   Database size: {db_size_mb:.2f}MB")
            print(f"   Size per memory: {db_size_mb * 1024 / size:.2f}KB")
            results["database"] = {
                "path": str(db_path),
                "size_mb": db_size_mb,
                "size_per_memory_kb": db_size_mb * 1024 / size,
            }
        else:
            print("   ⚠️  Database path not available")
            results["database"] = {"path": None}

        # ========== 内存使用统计 ==========
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        current_mem_mb = current_mem / (1024 * 1024)
        peak_mem_mb = peak_mem / (1024 * 1024)

        print(f"\n\n4️⃣  Memory Usage")
        print(f"   Current memory: {current_mem_mb:.1f}MB")
        print(f"   Peak memory: {peak_mem_mb:.1f}MB")
        print(f"   Memory per memory: {current_mem_mb * 1024 / size:.2f}KB")

        results["memory"] = {
            "current_mb": current_mem_mb,
            "peak_mb": peak_mem_mb,
            "per_memory_kb": current_mem_mb * 1024 / size,
        }

        # 清理
        tracemalloc.stop()
        cm.close()

        # ========== 性能阈值检查 ==========
        print("\n\n5️⃣  Performance Thresholds Check")
        thresholds = {
            "write_throughput": ({"min": 1000, "warn": 500}, "memories/sec"),
            "read_throughput": ({"min": 100, "warn": 50}, "reads/sec"),
            "error_rate": ({"max": 0.01, "warn": 0.05}, "ratio"),
            "memory_per_memory": ({"max": 50, "warn": 100}, "KB"),
        }

        all_passed = True
        for metric, (limits, unit) in thresholds.items():
            if metric in ["write_throughput", "read_throughput"]:
                value = results.get("write", {}).get("throughput_per_sec", 0) if metric == "write_throughput" else results.get("read", {}).get("throughput_per_sec", 0)
                passed = value >= limits["min"]
                warned = value >= limits["warn"]
            elif metric == "error_rate":
                value = results.get("write", {}).get("error_rate", 1)
                passed = value <= limits["max"]
                warned = value <= limits["warn"]
            else:
                value = results.get("memory", {}).get("per_memory_kb", 999)
                passed = value <= limits["max"]
                warned = value <= limits["warn"]

            status = "✅" if passed else ("⚠️" if warned else "❌")
            print(f"   {status} {metric}: {value:.1f} {unit}")

            if not passed:
                all_passed = False

        # ========== 保存结果 ==========
        final_result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_config": {
                "dataset_size": size,
                "read_operations": 1000,
            },
            "results": results,
            "thresholds_passed": all_passed,
        }

        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(final_result, f, indent=2)
            print(f"\n📄 Results saved to: {output_file}")

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ All performance thresholds PASSED!")
        else:
            print("⚠️  Some thresholds FAILED - review above details")
        print("=" * 60)

        return final_result

    except ImportError as e:
        print(f"❌ Cannot import CarryMem: {e}")
        return None
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description='CarryMem Stress Test')
    parser.add_argument('--size', type=int, default=100000,
                        help='Dataset size for stress test (default: 100000)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file for results (default: auto-generated)')

    args = parser.parse_args()

    # 自动生成输出文件名
    output_file = args.output or f"benchmarks/stress_results_{time.strftime('%Y%m%d_%H%M%S')}.json"

    result = stress_test_large_dataset(
        size=args.size,
        output_file=output_file
    )

    if result is None:
        sys.exit(1)

    # 根据阈值结果决定退出码
    sys.exit(0 if result.get("thresholds_passed", True) else 1)


if __name__ == "__main__":
    main()
