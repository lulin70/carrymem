# MSC Official Benchmark Guide for CarryMem

本指南说明如何使用Meta AI的官方MSC (Multi-Session Chat) benchmark测试CarryMem。

## 📋 目录

1. [什么是MSC Benchmark](#什么是msc-benchmark)
2. [准备工作](#准备工作)
3. [下载MSC数据集](#下载msc数据集)
4. [运行Benchmark](#运行benchmark)
5. [配置魔卡模型](#配置魔卡模型)
6. [结果解读](#结果解读)

---

## 什么是MSC Benchmark

**MSC (Multi-Session Chat)** 是Meta AI开发的官方benchmark，用于评估对话系统的长期记忆能力。

### 特点

- **多会话设计**: 模拟跨多个时间段的对话（Day 0, 1, 7, 30, 90）
- **记忆保持测试**: 评估系统是否能记住并使用之前会话的信息
- **官方基准**: 有9个系统基线可供对比
- **真实场景**: 基于真实的人类对话数据

### 评估指标

- **Recall Rate**: 记忆召回率
- **Session Consistency**: 跨会话一致性
- **Memory Retention**: 记忆保持能力

---

## 准备工作

### 1. 安装CarryMem

```bash
cd /Users/lin/trae_projects/carrymem
pip install -e .
```

### 2. 验证安装

```bash
python -c "from carrymem import CarryMem; print('✅ CarryMem installed')"
```

### 3. 准备LLM API

CarryMem支持多种LLM提供商：

- **魔卡 (MokaAI)** - 推荐用于中文场景
- OpenAI
- Anthropic Claude
- 其他兼容OpenAI API的服务

---

## 下载MSC数据集

### 方法1: 使用ParlAI (推荐)

```bash
# 安装ParlAI
pip install parlai

# 下载MSC数据集
parlai display_data -t msc -dt train

# 数据集会自动下载到: ~/.parlai/data/msc/
```

### 方法2: 手动下载

1. 访问 [ParlAI GitHub](https://github.com/facebookresearch/ParlAI)
2. 下载MSC数据集
3. 解压到本地目录，例如: `/Users/lin/trae_projects/.benchmarks/msc/`

### 数据集结构

```
msc/
├── msc_personasummary/
│   ├── train.txt
│   ├── valid.txt
│   └── test.txt
└── msc_dialogue/
    ├── train.txt
    ├── valid.txt
    └── test.txt
```

---

## 运行Benchmark

### 基础用法

```bash
cd /Users/lin/trae_projects/carrymem/benchmarks

# 使用默认配置运行
python msc_official_adapter.py --dataset_path ~/.parlai/data/msc
```

### 完整参数

```bash
python msc_official_adapter.py \
  --dataset_path ~/.parlai/data/msc \
  --split valid \
  --num_episodes 10 \
  --model moka \
  --api_key YOUR_MOKA_API_KEY \
  --output results/msc_results.json
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dataset_path` | MSC数据集路径 | **必需** |
| `--split` | 数据集分割 (train/valid/test) | `valid` |
| `--num_episodes` | 测试的episode数量 | `10` |
| `--model` | LLM提供商 | `default` |
| `--api_key` | API密钥 | 无 |
| `--output` | 结果输出路径 | 自动生成 |

---

## 配置魔卡模型

### 方法1: 命令行参数

```bash
python msc_official_adapter.py \
  --dataset_path ~/.parlai/data/msc \
  --model moka \
  --api_key sk-moka-xxxxxxxxxxxxx
```

### 方法2: 环境变量

```bash
# 设置环境变量
export MOKA_API_KEY="sk-moka-xxxxxxxxxxxxx"

# 运行benchmark
python msc_official_adapter.py \
  --dataset_path ~/.parlai/data/msc \
  --model moka
```

### 方法3: 配置文件

创建 `config/moka_config.json`:

```json
{
  "provider": "moka",
  "api_key": "sk-moka-xxxxxxxxxxxxx",
  "model": "moka-chat-v1",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

---

## 结果解读

### 输出示例

```
============================================================
📊 MSC Benchmark Results
============================================================

🎯 Overall Performance:
   Average Recall Rate: 78.5%
   Min Recall Rate: 65.2%
   Max Recall Rate: 92.3%

📈 Statistics:
   Total Sessions: 50
   Total Memories Stored: 1,234
   Total Memories Recalled: 969

⏱️  Duration: 145.32s
```

### 指标解释

#### 1. Average Recall Rate (平均召回率)
- **含义**: 系统能够成功召回的记忆百分比
- **好的表现**: > 75%
- **优秀表现**: > 85%

#### 2. Min/Max Recall Rate
- **含义**: 最差和最好的会话表现
- **用途**: 评估系统稳定性

#### 3. Total Memories Stored/Recalled
- **含义**: 存储和召回的记忆总数
- **用途**: 评估系统容量

### 结果文件

结果会保存为JSON格式:

```json
{
  "metadata": {
    "benchmark": "MSC (Multi-Session Chat)",
    "source": "Meta AI / ParlAI",
    "timestamp": "2026-05-05T22:53:00",
    "model_config": {
      "provider": "a"
    },
    "duration_seconds": 145.32,
    "episodes_tested": 10
  },
  "sessions": [
    {
      "session_id": 1,
      "memories_stored": 25,
      "memories_recalled": 20,
      "recall_rate": 0.80,
      "turns": [...]
    }
  ],
  "metrics": {
    "avg_recall_rate": 0.785,
    "min_recall_rate": 0.652,
    "max_recall_rate": 0.923,
    "total_sessions": 50,
    "total_memories_stored": 1234,
    "total_memories_recalled": 969
  }
}
```

---

## 与其他系统对比

### MSC官方基线

根据MSC论文，以下是官方基线系统的表现：

| 系统 | Recall Rate | 说明 |
|------|-------------|------|
| No Memory | ~40% | 无记忆基线 |
| Full History | ~65% | 完整历史 |
| Summarization | ~72% | 摘要方法 |
| **MemNet** | ~78% | 记忆网络 |
| **Transformer-XL** | ~82% | 长序列模型 |

### CarryMem目标

- **短期目标**: > 75% (超过摘要方法)
- **中期目标**: > 80% (接近Transformer-XL)
- **长期目标**: > 85% (超越现有基线)

---

## 故障排除

### 问题1: 找不到数据集

```
❌ Error: MSC dataset not found at ~/.parlai/data/msc
```

**解决方案**:
1. 确认数据集路径正确
2. 重新下载数据集: `parlai display_data -t msc -dt train`
3. 或手动指定路径: `--dataset_path /path/to/msc`

### 问题2: CarryMem导入失败

```
❌ Error: CarryMem not found
```

**解决方案**:
```bash
cd /Users/lin/trae_projects/carrymem
pip install -e .
```

### 问题3: API密钥错误

```
❌ Error: Invalid API key
```

**解决方案**:
1. 检查API密钥是否正确
2. 确认API密钥有足够的配额
3. 尝试使用环境变量: `export MOKA_API_KEY="your-key"`

### 问题4: 内存不足

```
❌ Error: Out of memory
```

**解决方案**:
1. 减少测试episode数量: `--num_episodes 5`
2. 使用较小的数据集分割: `--split valid`
3. 增加系统内存或使用云服务器

---

## 高级用法

### 1. 批量测试

```bash
#!/bin/bash
# batch_test.sh

for split in train valid test; do
  python msc_official_adapter.py \
    --dataset_path ~/.parlai/data/msc \
    --split $split \
    --num_episodes 20 \
    --output results/msc_${split}_results.json
done
```

### 2. 对比不同配置

```bash
# 测试不同的记忆策略
python msc_official_adapter.py --dataset_path ~/.parlai/data/msc --output results/default.json
python msc_official_adapter.py --dataset_path ~/.parlai/data/msc --memory_strategy aggressive --output results/aggressive.json
python msc_official_adapter.py --dataset_path ~/.parlai/data/msc --memory_strategy conservative --output results/conservative.json
```

### 3. 生成对比报告

```python
# compare_results.py
import json

def compare_results(file1, file2):
    with open(file1) as f1, open(file2) as f2:
        r1 = json.load(f1)\ r2 = json.load(f2)
    
    print(f"Config 1 Recall: {r1['metrics']['avg_recall_rate']:.1%}")
    print(f"Config 2 Recall: {r2['metrics']['avg_recall_rate']:.1%}")
    
    improvement = r2['metrics']['avg_recall_rate'] - r1['metrics']['avg_recall_rate']
    print(f"Improvement: {improvement:+.1%}")

compare_results('results/default.json', 'results/aggressive.json')
```

---

## 下一步

1. **运行完整测试**: 使用所有数据集分割
2. **优化配置**: 根据结果调整CarryMem参数
3. **对比分析**: 与官方基线对比
4. **发布结果**: 在论文或博客中分享发现

---

## 参考资料

- [MSC论文](https://arxiv.org/abs/2106.00672)
- [ParlAI文档](https://parl.ai/)
- [CarryMem文档](../README.md)

---

## 联系支持

如有问题，请：
1. 查看 [FAQ](../docs/FAQ.md)
2. 提交 [Issue](https://github.com/your-repo/carrymem/issues)
3. 加入讨论组

---

**最后更新**: 2026-05-05
**版本**: 1.0.0
