# CarryMem Benchmark检查建议报告

**生成时间**: 2026-05-04  
**评估版本**: v0.3.0  
**评估者**: 代码审查团队

---

## 📋 执行摘要

CarryMem已有完善的benchmark体系，包括分类准确率、性能测试和基准对比。本报告提供全面的benchmark检查建议，帮助确保产品质量和性能持续优化。

---

## 🎯 现有Benchmark评估

### ✅ 已有的Benchmark

| Benchmark | 文件 | 覆盖范围 | 状态 |
|-----------|------|---------|------|
| **分类准确率** | `run_benchmark.py` | 7种记忆类型 | ✅ 完善 |
| **性能测试** | `performance_benchmark.py` | 存储/召回/语义 | ✅ 完善 |
| **分类精度** | `classification_accuracy.py` | 准确率/F1 | ✅ 完善 |
| **基准对比** | `baseline_benchmark.py` | 历史对比 | ✅ 完善 |
| **排行榜** | `leaderboard.py` | 版本对比 | ✅ 完善 |

### 📊 最新Benchmark结果（2026-04-17）

**分类性能**:
- ✅ 准确率: 90.6%
- ✅ F1分数: 97.9%
- ✅ 精确率: 高
- ✅ 召回率: 高

**性能指标**:
- ✅ 召回P50: 0.01ms（极快）
- ✅ 召回P99: 65.97ms（良好）
- ✅ 处理P50: 326ms（可接受）
- ✅ 处理P99: 1452ms（需优化）
- ✅ 缓存命中率: 97.8%（优秀）

---

## 🔍 Benchmark检查建议

### 1️⃣ 定期运行Benchmark（必做）

#### 建议频率

| 场景 | 频率 | 命令 |
|------|------|------|
| **代码提交前** | 每次 | `python benchmarks/run_benchmark.py` |
| **版本发布前** | 每次 | 完整benchmark套件 |
| **性能优化后** | 每次 | `python benchmarks/performance_benchmark.py` |
| **每周例行** | 每周 | 完整benchmark + 对比 |
| **每月报告** | 每月 | 生成趋势报告 |

#### 执行命令

```bash
cd /Users/lin/trae_projects/carrymem

# 1. 分类准确率测试
python benchmarks/run_benchmark.py

# 2. 性能测试（1000次操作）
python benchmarks/performance_benchmark.py --scale 1000

# 3. 性能测试（大规模10000次）
python benchmarks/performance_benchmark.py --scale 10000 --output results/perf_10k.json

# 4. 分类精度测试
python benchmarks/classification_accuracy.py

# 5. 基准对比
python benchmarks/baseline_benchmark.py
```

---

### 2️⃣ 性能回归检测（重要）

#### 建议阈值

| 指标 | 当前值 | 警告阈值 | 失败阈值 |
|------|--------|---------|---------|
| **分类准确率** | 90.6% | <88% | <85% |
| **F1分数** | 97.9% | <95% | <90% |
| **召回P99** | 65.97ms | >80ms | >100ms |
| **处理P99** | 1452ms | >1800ms | >2000ms |
| **缓存命中率** | 97.8% | <95% | <90% |

#### 自动化检查脚本

创建 `benchmarks/check_regression.py`:

```python
#!/usr/bin/env python3
"""
性能回归检测脚本

Usage:
    python benchmarks/check_regression.py
    python benchmarks/check_regression.py --baseline final_results.json
"""

import json
import sys
from pathlib import Path

# 阈值配置
THRESHOLDS = {
    "classification_accuracy": {"warning": 0.88, "fail": 0.85},
    "f1_score": {"warning": 0.95, "fail": 0.90},
    "recall_p99_ms": {"warning": 80, "fail": 100},
    "process_p99_ms": {"warning": 1800, "fail": 2000},
    "cache_hit_rate": {"warning": 0.95, "fail": 0.90},
}

def load_baseline(path="benchmarks/final_results.json"):
    """加载基准数据"""
    with open(path) as f:
        return json.load(f)

def load_current():
    """运行当前benchmark并获取结果"""
    import subprocess
    
    # 运行benchmark
    subprocess.run(["python", "benchmarks/run_benchmark.py"], check=True)
    subprocess.run(["python", "benchmarks/performance_benchmark.py"], check=True)
    
    # 加载结果
    # ... 实现加载逻辑
    pass

def compare_results(baseline, current):
    """对比结果"""
    issues = []
    
    # 检查分类准确率
    if current["accuracy"] < THRESHOLDS["classification_accuracy"]["fail"]:
        issues.append(f"❌ FAIL: 分类准确率 {current['accuracy']:.1%} < {THRESHOLDS['classification_accuracy']['fail']:.1%}")
    elif current["accuracy"] < THRESHOLDS["classification_accuracy"]["warning"]:
        issues.append(f"⚠️  WARNING: 分类准确率 {current['accuracy']:.1%} < {THRESHOLDS['classification_accuracy']['warning']:.1%}")
    
    # 检查其他指标...
    
    return issues

def main():
    baseline = load_baseline()
    current = load_current()
    issues = compare_results(baseline, current)
    
    if issues:
        print("\n".join(issues))
        sys.exit(1 if any("FAIL" in i for i in issues) else 0)
    else:
        print("✅ 所有benchmark通过！")

if __name__ == "__main__":
    main()
```

---

### 3️⃣ 扩展Benchmark覆盖（建议）

#### 当前缺失的Benchmark

| 类别 | 缺失项 | 优先级 | 建议 |
|------|--------|--------|------|
| **并发测试** | 多线程/多进程 | 🔴 高 | 测试线程安全 |
| **压力测试** | 极限负载 | 🟡 中 | 10万+记忆 |
| **内存泄漏** | 长时间运行 | 🔴 高 | 24小时测试 |
| **跨语言** | 中英日混合 | 🟡 中 | 扩展数据集 |
| **边界情况** | 极端输入 | 🟡 中 | 空字符串、超长文本 |
| **安全性** | 注入攻击 | 🔴 高 | SQL/XSS测试 |
| **兼容性** | Python版本 | 🟢 低 | 3.9-3.12 |
| **集成测试** | MCP/CLI | 🟡 中 | 端到端测试 |

#### 建议新增Benchmark

**A. 并发测试** `benchmarks/concurrency_benchmark.py`

```python
#!/usr/bin/env python3
"""并发性能测试"""

import concurrent.futures
import time
from carrymem import CarryMem

def test_concurrent_writes(num_threads=10, operations_per_thread=100):
    """测试并发写入"""
    cm = CarryMem()
    
    def write_memories(thread_id):
        for i in range(operations_per_thread):
            cm.classify_and_remember(f"Thread {thread_id} memory {i}")
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(write_memories, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)
    
    duration = time.time() - start
    total_ops = num_threads * operations_per_thread
    
    print(f"✅ 并发写入: {total_ops}次操作, {duration:.2f}秒")
    print(f"   吞吐量: {total_ops/duration:.0f} ops/sec")
    
    cm.close()

def test_concurrent_reads(num_threads=10, operations_per_thread=100):
    """测试并发读取"""
    cm = CarryMem()
    
    # 预填充数据
    for i in range(100):
        cm.classify_and_remember(f"Test memory {i}")
    
    def read_memories(thread_id):
        for i in range(operations_per_thread):
            cm.recall_memories("test", limit=10)
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(read_memories, i) for i in num_threads)]
        concurrent.futures.wait(futures)
    
    duration = time.time() - start
    total_ops = num_threads * operations_per_thread
    
    print(f"✅ 并发读取: {total_ops}次操作, {duration:.2f}秒")
    print(f"   吞吐量: {total_ops/duration:.0f} ops/sec")
    
    cm.close()

if __name__ == "__main__":
    print("🔄 并发性能测试\n")
    test_concurrent_writes()
    test_concurrent_reads()
```

**B. 压力测试** `benchmarks/stress_test.py`

```python
#!/usr/bin/env python3
"""压力测试 - 极限负载"""

from carrymem import CarryMem
import time

def stress_test_large_dataset(size=100000):
    """测试大规模数据集"""
    print(f"📊 压力测试: {size}条记忆\n")
    
    cm = CarryMem()
    
    # 写入测试
    print("1️⃣ 写入测试...")
    start = time.time()
    for i in range(size):
        cm.classify_and_remember(f"Memory {i}: I prefer option {i % 10}")
        if (i + 1) % 10000 == 0:
            print(f"   进度: {i+1}/{size}")
    
    write_duration = time.time() - start
    print(f"✅ 写入完成: {write_duration:.2f}秒")
    print(f"   平均: {write_duration/size*1000:.2f}ms/条\n")
    
    # 读取测试
    print("2️⃣ 读取测试...")
    start = time.time()
    for i in range(1000):
        results = cm.recall_memories(f"option {i % 10}", limit=100)
    
    read_duration = time.time() - start
    print(f"✅ 读取完成: {read_duration:.2f}秒")
    print(f"   平均: {read_duration/1000*1000:.2f}ms/次\n")
    
    # 数据库大小
    import os
    db_size = os.path.getsize(cm._adapter._db_path) / (1024 * 1024)
    print(f"💾 数据库大小: {db_size:.2f}MB")
    print(f"   每条记忆: {db_size*1024/size:.2f}KB\n")
    
    cm.close()

if __name__ == "__main__":
    stress_test_large_dataset(100000)
```

**C. 内存泄漏测试** `benchmarks/memory_leak_test.py`

```python
#!/usr/bin/env python3
"""内存泄漏测试 - 长时间运行"""

import psutil
import time
from carrymem import CarryMem

def test_memory_leak(duration_minutes=60):
    """测试内存泄漏"""
    print(f"🔍 内存泄漏测试: {duration_minutes}分钟\n")
    
    process = psutil.Process()
    cm = CarryMem()
    
    start_time = time.time()
    start_memory = process.memory_info().rss / (1024 * 1024)  # MB
    
    iteration = 0
    while time.time() - start_time < duration_minutes * 60:
        # 模拟正常使用
        cm.classify_and_remember(f"Memory {iteration}")
        cm.recall_memories("test", limit=10)
        
        iteration += 1
        
        if iteration % 1000 == 0:
            current_memory = process.memory_info().rss / (1024 * 1024)
            elapsed = (time.time() - start_time) / 60
            print(f"   {elapsed:.1f}分钟: {current_memory:.1f}MB (+{current_memory-start_memory:.1f}MB)")
    
    end_memory = process.memory_info().rss / (1024 * 1024)
    memory_increase = end_memory - start_memory
    
    print(f"\n✅ 测试完成:")
    print(f"   初始内存: {start_memory:.1f}MB")
    print(f"   最终内存: {end_memory:.1f}MB")
    print(f"   增长: {memory_increase:.1f}MB")
    print(f"   迭代次数: {iteration}")
    
    # 判断是否泄漏
    if memory_increase > 100:  # 增长超过100MB视为可能泄漏
        print(f"\n⚠️  警告: 内存增长过大，可能存在泄漏")
    else:
        print(f"\n