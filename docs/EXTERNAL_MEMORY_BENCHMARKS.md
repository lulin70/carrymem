# CarryMem 外部 Benchmark 评测计划

**版本**: v0.1.6  
**更新日期**: 2026-05-03  
**目标**: 通过业界标准 benchmark 获取可对比分数，展示 CarryMem 在质量与效率上的双重优势

---

## 一、评测优先级

### 1.1 完整优先级排序

| 优先级 | Benchmark | 理由 | CarryMem 角色 |
|--------|-----------|------|--------------|
| ⭐⭐⭐ | **MSC** | 最贴切核心场景，适配成本最低 | 主力：跨会话记忆保持 |
| ⭐⭐⭐ | **LongMemEval** | 500题5维度，通用领域，有说服力 | 主力：综合对标 |
| ⭐⭐ | **ES-MemEval** | 冲突检测+用户建模维度有价值 | 补充：证明冲突处理能力 |
| ⭐⭐ | **LaMP** | 个性化任务，补"记忆→应用"链路 | 补充 |
| ⭐ | **LoCoMo** | 和LongMemEval重叠多 | 可选：定性case study |
| ⭐ | **MemoryBank** | 遗忘机制对比 | 可选：学术深挖 |
| — | PersonaChat | 太旧 | 跳过 |
| — | MemPrompt | 不是标准benchmark | 跳过 |

### 1.2 为什么 MSC 排第一？

MSC（Multi-Session Chat, Meta Research, ACL 2022）是 **CarryMem 最天然匹配的 benchmark**：

| MSC 特性 | CarryMem 对应 | 匹配度 |
|----------|--------------|--------|
| **多会话渐进式认识** — 5 sessions 中逐步了解对方兴趣 | `classify_and_remember()` 跨会话存储 | ★★★★★ |
| **Persona 学习** — 记住用户偏好、事实、关系 | 7 种记忆类型（user_preference, fact_declaration, relationship...） | ★★★★★ |
| **跨会话一致性** — 后续会话引用之前讨论的内容 | `recall_memories()` + FTS5 全文检索 | ★★★★★ |
| **RAG 优于 encoder-decoder** — MSC 论文核心结论 | CarryMem 天然是 RAG 架构 | ★★★★★ |
| **Persona Summary 任务** — 从对话中提取 persona 摘要 | `classify_and_remember()` 自动分类 + 存储 | ★★★★☆ |

MSC 测试的不只是"能否回答问题"，而是 **"记住你之后能否自然地聊下去"**——这正是 CarryMem 的产品定位。

### 1.3 为什么 LongMemEval 排第二？

LongMemEval（ICLR 2025）的 5 维度评测能全面对标：

| 能力 | 测试内容 | CarryMem 对应功能 |
|------|---------|------------------|
| Information Extraction | 从对话中提取关键信息 | classify_and_remember |
| Multi-Session Reasoning | 跨会话推理 | recall_memories + 语义匹配 |
| Temporal Reasoning | 时间相关推理 | 时间戳 + TTL 机制 |
| Knowledge Updates | 知识更新/冲突处理 | 冲突检测 + correction 类型 |
| Abstention | 知道何时"不知道" | confidence 阈值 + 弃权判断 |

### 1.4 补充 Benchmark 的价值

| Benchmark | 补充价值 |
|-----------|---------|
| **ES-MemEval** | 冲突检测维度 + 用户建模维度，证明 CarryMem 的 conflict_detector 和 correction 类型处理能力 |
| **LaMP** | 个性化任务（个性化新闻摘要/邮件撰写等），补全"记忆→个性化应用"的链路证明 |
| **LoCoMo** | 和 LongMemEval 重叠多，但超长对话（600轮）场景可做定性 case study |
| **MemoryBank** | 遗忘机制对比，证明 CarryMem 的 TTL + tier 体系 vs Ebbinghaus 遗忘曲线 |

---

## 二、Benchmark 详细对比

| 维度 | MSC | LongMemEval | ES-MemEval | LaMP | LoCoMo | MemoryBank |
|------|-----|-------------|------------|------|--------|------------|
| **来源** | Meta, ACL 2022 | UCLA/Tencent, ICLR 2025 | 2025 | 2024 | Snap/UNC, ACL 2024 | 2023 |
| **数据规模** | 4K conv, 12K sessions | 500 questions | ~1K questions | 7 tasks, ~10K samples | 10 conv, ~600轮 | 893 questions |
| **会话结构** | 5 sessions/conv | 多会话+时间戳 | 多会话 | 单轮+用户画像 | 单超长对话 | 多轮对话 |
| **核心场景** | Persona学习+跨会话一致性 | 5种记忆能力 | 冲突+用户建模 | 个性化生成 | QA+事件摘要 | 遗忘机制 |
| **评测方式** | Persona F1+人工评估 | Token F1+LLM Judge | F1+LLM Judge | ROUGE+LLM Judge | Token F1+LLM Judge | F1+人工评估 |
| **适配难度** | 中 | 低 | 低 | 中 | 中 | 低 |
| **业界认可度** | ACL 2022, 300+引用 | ICLR 2025 | 新兴 | EMNLP 2024 | ACL 2024 | ACL 2023 |

---

## 三、CarryMem 适配方案

### 3.1 MSC 适配（⭐⭐⭐ 主力）

#### 方式 A：Persona Summary 任务（自动评估，推荐先跑）

```python
from memory_classification_engine import CarryMem

def run_msc_persona_summary(conv_sessions, llm_model="gpt-4.1-mini"):
    cm = CarryMem()
    
    for session_idx, session in enumerate(conv_sessions):
        for turn in session:
            if turn["speaker"] == "user":
                cm.classify_and_remember(
                    turn["text"],
                    metadata={"session": session_idx + 1}
                )
    
    preferences = cm.recall_memories("user preferences", 
                                      memory_type="user_preference", limit=50)
    facts = cm.recall_memories("user facts", 
                                memory_type="fact_declaration", limit=50)
    relationships = cm.recall_memories("user relationships", 
                                        memory_type="relationship", limit=50)
    
    all_memories = preferences + facts + relationships
    prompt = "Based on the following memories about a person, write a persona summary:\n"
    for m in all_memories:
        prompt += f"- {m['content']}\n"
    
    summary = call_llm(prompt, model=llm_model)
    cm.close()
    return summary
```

#### 方式 B：对话生成 + 人工评估（高质量但高成本，按需）

用 CarryMem 作为记忆后端，生成第 5 session 的回复，人工评估 engagingness 和 consistency。

### 3.2 LongMemEval 适配（⭐⭐⭐ 主力）

```python
import json
from memory_classification_engine import CarryMem

def run_longmemeval(data_file, output_file, llm_model="gpt-4.1-mini"):
    with open(data_file) as f:
        data = json.load(f)
    
    results = []
    for item in data:
        cm = CarryMem()
        
        for session, date in zip(item["haystack_sessions"], item["haystack_dates"]):
            for turn in session:
                if turn["role"] == "user":
                    cm.classify_and_remember(turn["content"])
        
        memories = cm.recall_memories(item["question"], limit=20)
        prompt = cm.build_system_prompt(item["question"], memories)
        answer = call_llm(prompt, model=llm_model)
        
        results.append({
            "question_id": item["question_id"],
            "hypothesis": answer,
        })
        cm.close()
    
    with open(output_file, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
```

### 3.3 MemEval 适配（⭐ 可选，含 LoCoMo）

MemEval（ProsusAI 2026.03）整合了 LoCoMo + LongMemEval，内置全链路 token 成本追踪和 9 个系统基线。如果需要与 PropMem/Mem0/Graphiti 等系统直接对比，可通过 MemEval 跑 LoCoMo。

```python
# 在 MemEval 的 scripts/run_full_benchmark.py 中注册
SYSTEMS["carrymem"] = {
    "fn": run_carrymem,
    "architecture": "Classified memory with rules engine and token budget management",
    "infrastructure": "SQLite + FTS5 + local classification (no LLM for ingestion)",
}
```

---

## 四、评测指标体系

### 4.1 核心指标

| 指标 | 说明 | 来源 |
|------|------|------|
| **Token F1** | 生成文本与参考答案的 token 重叠度 | 通用 |
| **LLM-as-Judge** | GPT 评分（相关性 + 完整性 + 准确性） | 通用 |
| **Persona Summary F1** | 提取的 persona 与参考 persona 的 F1 | MSC |
| **Engagingness** | 人工评估回复吸引力（1-5 分） | MSC |
| **Consistency** | 人工评估跨会话一致性（1-5 分） | MSC |

### 4.2 CarryMem 特色指标（差异化优势）

| 指标 | 说明 | 为什么重要 |
|------|------|-----------|
| **Ingestion Token Cost** | 记忆存储阶段的 LLM token 消耗 | CarryMem = 0（本地分类），其他系统 > 0 |
| **Quality-per-Token** | F1 / Total Tokens | 越高越好，展示效率优势 |
| **Retrieval Latency** | P50/P95/P99 召回延迟 | CarryMem 已有 P50: 0.01ms |
| **Memory Compression Ratio** | 原始对话 tokens / 存储记忆 tokens | 展示记忆压缩效率 |
| **Zero-LLM Ingestion** | 是否不需要 LLM 即可存储记忆 | CarryMem 独有优势 |

### 4.3 分维度评分

#### 对齐 LongMemEval 5 能力

| 能力 | 测试内容 | CarryMem 对应功能 |
|------|---------|------------------|
| Information Extraction | 从对话中提取关键信息 | classify_and_remember |
| Multi-Session Reasoning | 跨会话推理 | recall_memories + 语义匹配 |
| Temporal Reasoning | 时间相关推理 | 时间戳 + TTL 机制 |
| Knowledge Updates | 知识更新/冲突处理 | 冲突检测 + correction 类型 |
| Abstention | 知道何时"不知道" | confidence 阈值 + 弃权判断 |

#### 对齐 MSC Persona 能力

| 能力 | 测试内容 | CarryMem 对应功能 |
|------|---------|------------------|
| Preference Learning | 记住用户偏好 | user_preference 类型 + 规则引擎 |
| Fact Retention | 记住用户陈述的事实 | fact_declaration 类型 |
| Relationship Tracking | 记住人际关系 | relationship 类型 |
| Cross-Session Consistency | 跨会话保持一致 | recall_memories + 规则匹配 |
| Interest Evolution | 兴趣变化追踪 | correction 类型 + 冲突检测 |

---

## 五、执行计划

### Phase 1: MSC + LongMemEval（主力，1-2 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1.1 | 从 HuggingFace 获取 MSC 数据集 | MSC 数据 |
| 1.2 | 编写 MSC Persona Summary 适配 | Persona Summary F1 |
| 1.3 | 运行 MSC Persona Summary 评测 | MSC 分数 |
| 1.4 | 获取 LongMemEval 数据 | LongMemEval 数据 |
| 1.5 | 编写 LongMemEval 适配 | 5 维度分数 |
| 1.6 | 运行 LongMemEval 评测 | LongMemEval 分数 |

### Phase 2: ES-MemEval + LaMP（补充，1 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 2.1 | 获取 ES-MemEval 数据 | ES-MemEval 数据 |
| 2.2 | 重点跑冲突检测+用户建模维度 | 冲突处理分数 |
| 2.3 | 获取 LaMP 数据 | LaMP 数据 |
| 2.4 | 跑个性化生成任务 | 个性化分数 |

### Phase 3: 结果分析与报告（1 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 3.1 | 汇总所有 benchmark 分数 | 综合对比表 |
| 3.2 | 计算 Quality-per-Token | 效率优势量化 |
| 3.3 | 分维度分析 | 强弱项识别 |
| 3.4 | 生成评测报告 | 公开发布的报告 |

### Phase 4: 优化迭代（按需）

| 优化方向 | 预期效果 | 影响的 Benchmark |
|----------|---------|-----------------|
| 添加 persona-aware prompt 模板 | 提升 Persona Summary F1 | MSC |
| 添加 time-aware query expansion | 提升 Temporal F1 | LongMemEval |
| 改进 recall 策略（entity-scoped 检索） | 提升 Multi-hop F1 | LongMemEval/LoCoMo |
| 添加 interest evolution tracking | 提升 Interest Evolution 分数 | MSC |
| 优化 confidence 阈值 | 提升 Abstention 准确率 | LongMemEval |

---

## 六、预期结果与核心叙事

### 6.1 核心叙事

> **CarryMem 在记忆质量与 LLM 成本之间取得了最优平衡。**
>
> - **Ingestion 零 LLM 成本**：本地分类引擎（90.6% 准确率）替代 LLM 事实提取
> - **Token 预算管理**：精确控制注入上下文的 token 数量，避免浪费
> - **FTS5 + 语义双检索**：毫秒级召回，无需 LLM 参与检索
> - **Quality-per-Token 最高**：每百万 token 获得最高 F1 分数
> - **MSC 场景完美匹配**：7 种记忆类型天然适配 persona 学习

### 6.2 对比图表示例

```
Quality (F1) vs Cost (Tokens)

F1  0.60 |          * PropMem (5.9M)
    0.55 |       * OpenClaw (16.4M)
    0.50 |    * Full Context (37.5M)
    0.45 | * Hindsight (24.2M)
    0.40 |
    0.35 |              * CarryMem (~1.5M) ← 效率之王
         +----------------------------------→ Tokens
         0    5M   10M   15M   20M   25M   30M
```

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 本地分类丢失隐式信息 | F1 偏低 | 补充 LLM 辅助分类作为可选模式 |
| FTS5 对长问题召回不足 | Multi-hop F1 偏低 | 添加 query expansion + entity 检索 |
| MSC 依赖 ParlAI 框架 | 适配成本高 | 从 HuggingFace 提取数据，绕过 ParlAI |
| API 费用 | 成本 | 使用 gpt-4.1-mini，预估 $10-20 |
| MSC 人工评估成本 | 高 | 先跑自动评估（Persona Summary F1），人工评估按需 |

---

## 八、参考资源

- **MSC**: https://parl.ai/projects/msc/ — Meta Research, "Beyond Goldfish Memory" (ACL 2022)
- **LongMemEval**: https://github.com/xiaowu0162/LongMemEval — ICLR 2025 长期记忆 benchmark
- **ES-MemEval**: Evaluating Social Memory Systems (2025) — 冲突检测 + 用户建模
- **LaMP**: https://github.com/LaMP-Benchmark/LaMP — 个性化生成 benchmark (EMNLP 2024)
- **LoCoMo**: https://snap-research.github.io/locomo — ACL 2024 长期对话 benchmark
- **MemoryBank**: https://github.com/zhao-ht/MemoryBank — 遗忘机制 benchmark (ACL 2023)
- **MemEval**: https://github.com/ProsusAI/MemEval — 公平评估框架（2026.03），含 LoCoMo + LongMemEval
