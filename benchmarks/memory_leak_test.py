#!/usr/bin/env python3
"""
CarryMem 内存泄漏测试 - 长时间运行稳定性测试

检测长时间运行下的内存使用情况，识别潜在的内存泄漏问题：
- 持续写入和读取操作
- 内存使用趋势监控
- 垃圾回收效率
- 泄漏阈值告警

Usage:
    python benchmarks/memory_leak_test.py
    python benchmarks/memory_leak_test.py --duration 30  # 30分钟测试
    python benchmarks/memory_leak_test.py --iterations 10000  # 1万次迭代
"""

import time
import argparse
import sys
import os
import json
import gc
import tracemalloc

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_memory_leak(duration_minutes=None, iterations=None, output_file=None):
    """
    测试内存泄漏

    Args:
        duration_minutes: 测试时长（分钟）
        iterations: 迭代次数（与duration二选一）
        output_file: 结果输出文件路径
    """
    print(f"\n🔍 Memory Leak Test")
    print("=" * 60)

    try:
        from memory_classification_engine import CarryMem

        # 确定测试模式
        if duration_minutes:
            mode = "time_based"
            print(f"\nMode: Time-based ({duration_minutes} minutes)")
            max_duration = duration_minutes * 60
        elif iterations:
            mode = "iteration_based"
            print(f"\nMode: Iteration-based ({iterations:,} iterations)")
            max_iterations = iterations
        else:
            # 默认：基于迭代次数（快速测试）
            mode = "iteration_based"
            max_iterations = 10000
            print(f"\nMode: Iteration-based (default: {max_iterations:,} iterations)")

        # 初始化
        cm = CarryMem()
        tracemalloc.start()

        # 记录初始状态
        start_time = time.time()
        start_mem, start_peak = tracemalloc.get_traced_memory()
        start_mem_mb = start_mem / (1024 * 1024)
        start_peak_mb = start_peak / (1024 * 1024)

        print(f"\nInitial State:")
        print(f"   Memory: {start_mem_mb:.1f}MB")
        print(f"   Peak: {start_peak_mb:.1f}MB")

        # 测试循环
        iteration = 0
        errors = []
        memory_samples = []
        gc_collections = []

        print(f"\nRunning test...")

        while True:
            # 执行操作
            try:
                # 写入
                cm.classify_and_remember(
                    f"Leak-Test-{iteration}: Testing memory leak with "
                    f"option {iteration % 10} for stability verification"
                )

                # 读取
                if iteration % 10 == 0:
                    cm.recall_memories(f"option {iteration % 10}", limit=10)

                # 定期清理（模拟正常使用）
                if iteration % 1000 == 0:
                    gc.collect()

            except Exception as e:
                errors.append((iteration, str(e)))

            iteration += 1

            # 定期采样内存
            if iteration % 500 == 0:
                current_mem, current_peak = tracemalloc.get_traced_memory()
                current_mem_mb = current_mem / (1024 * 1024)
                current_peak_mb = current_peak / (1024 * 1024)

                elapsed = time.time() - start_time
                memory_increase = current_mem_mb - start_mem_mb

                sample = {
                    "iteration": iteration,
                    "elapsed_seconds": round(elapsed, 2),
                    "memory_mb": round(current_mem_mb, 2),
                    "peak_mb": round(current_peak_mb, 2),
                    "memory_increase_mb": round(memory_increase, 2),
                    "errors_count": len(errors),
                }
                memory_samples.append(sample)

                # 打印进度
                if duration_minutes:
                    progress = min(elapsed / max_duration * 100, 100)
                    print(f"   [{progress:>5.1f}%] {elapsed/60:.1f}min | "
                          f"Iter:{iteration:>6,} | "
                          f"Mem:{current_mem_mb:>6.1f}MB "
                          f"(+{memory_increase:>6.1f}MB) | "
                          f"Peak:{current_peak_mb:.1f}MB | "
                          f"Err:{len(errors)}")
                else:
                    progress = iteration / max_iterations * 100
                    print(f"   [{progress:>5.1f}%] Iter:{iteration:>6,}/{max_iterations:,} | "
                          f"{elapsed:.1f}s | "
                          f"Mem:{current_mem_mb:>6.1f}MB "
                          f"(+{memory_increase:>6.1f}MB) | "
                          f"Peak:{current_peak_mb:.1f}MB | "
                          f"Err:{len(errors)}")

                # 强制GC并记录
                gc.collect()
                after_gc_mem = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
                gc_collections.append({
                    "iteration": iteration,
                    "before_gc_mb": round(current_mem_mb, 2),
                    "after_gc_mb": round(after_gc_mem, 2),
                    "freed_mb": round(current_mem_mb - after_gc_mem, 2),
                })

            # 检查终止条件
            should_stop = False

            if mode == "time_based":
                elapsed = time.time() - start_time
                if elapsed >= max_duration:
                    should_stop = True
            else:
                if iteration >= max_iterations:
                    should_stop = True

            if should_stop:
                break

        # ========== 测试完成统计 ==========
        end_time = time.time()
        total_duration = end_time - start_time
        end_mem, end_peak = tracemalloc.get_traced_memory()
        end_mem_mb = end_mem / (1024 * 1024)
        end_peak_mb = end_peak / (1024 * 1024)

        memory_growth = end_mem_mb - start_mem_mb
        peak_growth = end_peak_mb - start_peak_mb

        print(f"\n\n{'='*60}")
        print("📊 Test Results Summary")
        print(f"{'='*60}")

        print(f"\n⏱️  Duration:")
        if duration_minutes:
            print(f"   Target: {duration_minutes} minutes")
        else:
            print(f"   Target: {max_iterations:,} iterations")
        print(f"   Actual: {total_duration:.1f}s ({total_duration/60:.1f}min)")
        print(f"   Iterations completed: {iteration:,}")

        print(f"\n💾 Memory Usage:")
        print(f"   Initial: {start_mem_mb:.1f}MB")
        print(f"   Final: {end_mem_mb:.1f}MB")
        print(f"   Growth: {memory_growth:+.1f}MB (+{memory_growth/max(iteration,1)*1000:.2f}KB/iter)")
        print(f"   Peak: {end_peak_mb:.1f}MB (growth: {peak_growth:+.1f}MB)")

        print(f"\n❌ Errors:")
        print(f"   Total: {len(errors)}")
        if errors:
            print(f"   Error rate: {len(errors)/iteration*100:.3f}%")
            print(f"\n   Sample errors (first 5):")
            for idx, err in errors[:5]:
                print(f"      [{idx}] {err}")

        # GC效率分析
        if gc_collections:
            avg_freed = sum(gc["freed_mb"] for gc in gc_collections) / len(gc_collections)
            print(f"\n🗑️  Garbage Collection:")
            print(f"   Collections: {len(gc_collections)}")
            print(f"   Avg freed per collection: {avg_freed:.2f}MB")

        # ========== 泄漏判断 ==========
        print(f"\n\n{'='*60}")
        print("🔍 Leak Detection Analysis")
        print(f"{'='*60}")

        is_leaking = False
        warnings = []

        # 阈值检查
        thresholds = {
            "absolute_growth_mb": {"warning": 50, "critical": 100},
            "growth_per_1000_iter_kb": {"warning": 10, "critical": 20},
            "error_rate_percent": {"warning": 0.1, "critical": 1.0},
        }

        growth_per_1k = memory_growth / max(iteration / 1000, 1)

        checks = [
            ("Absolute memory growth", memory_growth, thresholds["absolute_growth_mb"]),
            ("Growth per 1K iterations", growth_per_1k, thresholds["growth_per_1000_iter_kb"]),
            ("Error rate", len(errors) / max(iteration, 1) * 100, thresholds["error_rate_percent"]),
        ]

        for name, value, limits in checks:
            if value > limits["critical"]:
                status = "❌ CRITICAL"
                is_leaking = True
            elif value > limits["warning"]:
                status = "⚠️  WARNING"
                warnings.append(name)
            else:
                status = "✅ OK"

            unit = "MB" if "growth" in name.lower() or "memory" in name.lower() else "%" if "rate" in name.lower() else ""
            print(f"   {status} {name}: {value:.2f}{unit}")

        # 趋势分析（如果有足够样本）
        if len(memory_samples) >= 3:
            first_half = memory_samples[:len(memory_samples)//2]
            second_half = memory_samples[len(memory_samples)//2:]

            avg_first = sum(s["memory_increase_mb"] for s in first_half) / len(first_half)
            avg_second = sum(s["memory_increase_mb"] for s in second_half) / len(second_half)

            trend_acceleration = avg_second - avg_first

            print(f"\n📈 Trend Analysis:")
            print(f"   First half avg growth: {avg_first:.2f}MB")
            print(f"   Second half avg growth: {avg_second:.2f}MB")
            print(f"   Trend acceleration: {trend_acceleration:+.2f}MB")

            if trend_acceleration > 10:
                print(f"   ⚠️  Accelerating trend detected!")
                is_leaking = True
            elif trend_acceleration > 5:
                warnings.append("Accelerating memory growth")

        # 最终结论
        print(f"\n\n{'='*60}")
        if is_leaking:
            print("❌ MEMORY LEAK DETECTED!")
            print("   Immediate investigation required!")
        elif warnings:
            print("⚠️  POTENTIAL ISSUES DETECTED")
            print(f"   Warnings: {', '.join(warnings)}")
            print("   Monitor closely in production")
        else:
            print("✅ NO MEMORY LEAK DETECTED")
            print("   System appears stable under sustained load")
        print(f"{'='*60}")

        # 清理
        tracemalloc.stop()
        cm.close()

        # 保存结果
        result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_config": {
                "mode": mode,
                "target_duration_minutes": duration_minutes,
                "target_iterations": iterations or max_iterations,
            },
            "execution": {
                "total_duration_seconds": round(total_duration, 2),
                "iterations_completed": iteration,
                "total_errors": len(errors),
                "error_rate": round(len(errors) / max(iteration, 1), 6),
            },
            "memory": {
                "initial_mb": round(start_mem_mb, 2),
                "final_mb": round(end_mem_mb, 2),
                "growth_mb": round(memory_growth, 2),
                "peak_mb": round(end_peak_mb, 2),
                "peak_growth_mb": round(peak_growth, 2),
                "growth_per_1k_iterations_kb": round(growth_per_1k, 2),
            },
            "gc_efficiency": {
                "collections": len(gc_collections),
                "avg_freed_mb": round(sum(gc["freed_mb"] for gc in gc_collections) / max(len(gc_collections), 1), 2) if gc_collections else 0,
            },
            "samples": memory_samples[-10:],  # 只保存最后10个样本
            "leak_detected": is_leaking,
            "warnings": warnings,
        }

        if output_file:
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n📄 Results saved to: {output_file}")

        return result

    except ImportError as e:
        print(f"❌ Cannot import CarryMem: {e}")
        return None
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description='CarryMem Memory Leak Test')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--duration', type=int, default=None,
                       help='Test duration in minutes')
    group.add_argument('--iterations', type=int, default=None,
                       help='Number of iterations (default: 10000)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file path')

    args = parser.parse_args()

    output_file = args.output or f"benchmarks/memory_leak_results_{time.strftime('%Y%m%d_%H%M%S')}.json"

    result = test_memory_leak(
        duration_minutes=args.duration,
        iterations=args.iterations,
        output_file=output_file
    )

    if result is None:
        sys.exit(1)

    # 如果检测到泄漏，返回非零退出码
    sys.exit(1 if result.get("leak_detected", False) else 0)


if __name__ == "__main__":
    main()
