# CarryMem 外部 Benchmark 评测计划

**版本**: v0.2.4  
**更新日期**: 2026-05-03  
**目标**: 通过业界标准 benchmark 获取可对比分数，展示 CarryMem 在质量与效率上的双重优势

---

## 一、评测优先级

### 1.1 完整优先级排序

| 优先级 | Benchmark | 理由 | CarryMem 角色 |
|--------|-----------|------|--------------|
| ⭐⭐⭐ | **LongMemEval** | 最强证据力，5维度含冲突检测，最快出分 | 主力：综合对标 |
| ⭐⭐⭐ | **MSC** | 最强叙事力，场景完美匹配 | 主力：产品叙事 |
| ⭐⭐ | **MemEval** | 唯一有9系统基线+Token成本追踪 | 主力：公平对比 |
| ⭐⭐ | **ES-MemEval** | 冲突检测维度有价值 | 补充 |
| ⭐ | **MemoryBank** | 遗忘机制对比，TTL vs Ebbinghaus | 可选：学术深挖 |
| ⭐ | **LaMP** | 信噪比低，生成质量归因难 | 可选 |
| ⭐ | **CarryMem Rules Eval** (自定义) | 规则引擎是独有功能，无现有benchmark覆盖 | 自定义：独有卖点证据 |
| — | LoCoMo standalone | 被 MemEval 覆盖 | 跳过 |
| — | PersonaChat | 太旧 | 跳过 |
| — | MemPrompt | 不是标准benchmark | 跳过 |

### 1.2 为什么 LongMemEval 排第一？

LongMemEval（ICLR 2025）是**证据力最强的 benchmark**：

| 优势 | 说明 |
|------|------|
| **5维度全覆盖** | Information Extraction / Multi-Session / Temporal / Knowledge Updates / Abstention |
| **Knowledge Updates 维度** | 直接测试冲突检测 — 这是 CarryMem 独有的差异化能力，其他系统都没有 |
| **500题纯自动评估** | 几小时就能跑完，QA F1 是客观指标，可复现 |
| **适配成本最低** | 直接喂历史+输出 hypothesis，无需框架依赖 |
| **可扩展历史长度** | 支持自定义历史长度，可展示 CarryMem 在超长对话中的优势 |

| 能力 | 测试内容 | CarryMem 对应功能 |
|------|---------|------------------|
| Information Extraction | 从对话中提取关键信息 | classify_and_remember |
| Multi-Session Reasoning | 跨会话推理 | recall_memories + 语义匹配 |
| Temporal Reasoning | 时间相关推理 | 时间戳 + TTL 机制 |
| Knowledge Updates | 知识更新/冲突处理 | 冲突检测 + correction 类型 |
| Abstention | 知道何时"不知道" | confidence 阈值 + 弃权判断 |

### 1.3 为什么 MSC 并列主力？

MSC（Multi-Session Chat, Meta Research, ACL 2022）是**叙事力最强的 benchmark**：

| MSC 特性 | CarryMem 对应 | 匹配度 |
|----------|--------------|--------|
| **多会话渐进式认识** — 5 sessions 中逐步了解对方兴趣 | `classify_and_remember()` 跨会话存储 | ★★★★★ |
| **Persona 学习** — 记住用户偏好、事实、关系 | 7 种记忆类型（user_preference, fact_declaration, relationship...） | ★★★★★ |
| **跨会话一致性** — 后续会话引用之前讨论的内容 | `recall_memories()` + FTS5 全文检索 | ★★★★★ |
| **RAG 优于 encoder-decoder** — MSC 论文核心结论 | CarryMem 天然是 RAG 架构 | ★★★★★ |

MSC 测试的不只是"能否回答问题"，而是 **"记住你之后能否自然地聊下去"**——这正是 CarryMem 的产品定位。

**但 MSC 的局限**：Persona Summary F1 指标窄，人工评估难复现，缺少同框架对比系统。所以 MSC 更适合做**产品叙事**，而非**严格对标**。

### 1.4 为什么 MemEval 被提升到 ⭐⭐？

MemEval（ProsusAI 2026.03）提供了**其他 benchmark 都无法提供的对比能力**：

| MemEval 独特价值 | 为什么重要 |
|-----------------|-----------|
| **9 个系统直接对比** | PropMem/Mem0/Graphiti/Hindsight... 同一框架同分对比，不需要自己建基线 |
| **全链路 Token 成本追踪** | CarryMem 最大的卖点"Zero-LLM Ingestion"只有在这里才能量化证明 |
| **Quality-per-Token 排行榜** | 这可能是 CarryMem 排名最高的指标 |
| **同时覆盖 LoCoMo + LongMemEval** | 一次接入，两套分数 |

**没有 MemEval，你只能报告自己的绝对分数。没有对比就没有伤害，也没有说服力。**

### 1.5 为什么 LaMP 降到 ⭐？

- CarryMem 是**记忆层**，不是**生成层**
- LaMP 评估的是个性化生成质量（新闻摘要、邮件撰写），这主要取决于 LLM，不是 CarryMem
- **信噪比低** — 分数高可能是 LLM 好，分数低可能是 LLM 差，很难归因到 CarryMem

### 1.6 盲点：没有 Benchmark 测试规则引擎

CarryMem 的 **rules engine**（add-rule, match-rules）是所有对比系统中**完全没有的功能**。但现有 benchmark 都不测试"系统能否遵循用户定义的规则"。

**建议**：设计一个自定义评测——给系统注入规则（如"always use Python 3"、"never suggest REST"），然后测试系统是否遵循。这个评测可以成为 CarryMem 的**独有卖点证据**。

---

## 二、Benchmark 详细对比

| 维度 | LongMemEval | MSC | MemEval | ES-MemEval | LaMP | MemoryBank |
|------|-------------|-----|---------|------------|------|------------|
| **来源** | UCLA/Tencent, ICLR 2025 | Meta, ACL 2022 | ProsusAI 2026.03 | 2025 | 2024 | 2023 |
| **数据规模** | 500 questions | 4K conv, 12K sessions | 整合 LoCoMo+LongMemEval | ~1K questions | 7 tasks, ~10K samples | 893 questions |
| **会话结构** | 多会话+时间戳 | 5 sessions/conv | 同 LongMemEval/LoCoMo | 多会话 | 单轮+用户画像 | 多轮对话 |
| **核心场景** | 5种记忆能力 | Persona学习+跨会话一致性 | 公平对比+Token成本 | 冲突+用户建模 | 个性化生成 | 遗忘机制 |
| **评测方式** | Token F1+LLM Judge | Persona F1+人工评估 | Token F1+LLM Judge+Token追踪 | F1+LLM Judge | ROUGE+LLM Judge | F1+人工评估 |
| **Token 成本追踪** | 无 | 无 | **有** | 无 | 无 | 无 |
| **内置对比系统** | 无 | 无 | **9个** | 无 | 无 | 无 |
| **适配难度** | **低** | 中 | **低**（写adapter） | 低 | 中 | 低 |
| **出分速度** | **快（几小时）** | 慢（人工评估） | 快 | 快 | 中 | 快 |
| **业界认可度** | ICLR 2025 | ACL 2022, 300+引用 | 最新 | 新兴 | EMNLP 2024 | ACL 2023 |

---

## 三、CarryMem 适配方案

### 3.1 LongMemEval 适配（⭐⭐⭐ 主力，最先跑）

```python
import json
from carrymem import CarryMem

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

### 3.2 MSC 适配（⭐⭐⭐ 主力）

#### 方式 A：Persona Summary 任务（自动评估，推荐先跑）

```python
from carrymem import CarryMem

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

### 3.3 MemEval 适配（⭐⭐ 公平对比）

```python
# 在 MemEval 的 scripts/run_full_benchmark.py 中注册
SYSTEMS["carrymem"] = {
    "fn": run_carrymem,
    "architecture": "Classified memory with rules engine and token budget management",
    "infrastructure": "SQLite + FTS5 + local classification (no LLM for ingestion)",
}
```

### 3.4 CarryMem Rules Eval（⭐ 自定义，独有卖点）

```python
from carrymem import CarryMem

RULES_TEST_CASES = [
    {
        "rule": {"trigger": "coding language", "action": "always use Python 3", "type": "always"},
        "questions": [
            "What language should I use for this script?",
            "Recommend a language for web scraping",
        ],
        "expected_contains": ["Python"],
    },
    {
        "rule": {"trigger": "database", "action": "never suggest REST API", "type": "forbid"},
        "questions": [
            "How should I connect to the database?",
            "Design an interface for the data service",
        ],
        "expected_not_contains": ["REST"],
    },
]

def run_rules_eval(llm_model="gpt-4.1-mini"):
    cm = CarryMem()
    for tc in RULES_TEST_CASES:
        cm.add_rule(trigger=tc["rule"]["trigger"], 
                     action=tc["rule"]["action"], 
                     rule_type=tc["rule"]["type"])
    
    results = []
    for tc in RULES_TEST_CASES:
        for q in tc["questions"]:
            matched = cm.match_rules(q)
            memories = cm.recall_memories(q, limit=10)
            prompt = cm.build_system_prompt(q, memories, matched_rules=matched)
            answer = call_llm(prompt, model=llm_model)
            
            follow_rule = True
            if "expected_contains" in tc:
                follow_rule = any(kw in answer for kw in tc["expected_contains"])
            if "expected_not_contains" in tc:
                follow_rule = follow_rule and all(kw not in answer for kw in tc["expected_not_contains"])
            
            results.append({"question": q, "answer": answer, "follows_rule": follow_rule})
    
    cm.close()
    return results
```

---

## 四、评测指标体系

### 4.1 核心指标

| 指标 | 说明 | 来源 |
|------|------|------|
| **Token F1** | 生成文本与参考答案的 token 重叠度 | 通用 |
| **LLM-as-Judge** | GPT 评分（相关性 + 完整性 + 准确性） | 通用 |
| **Total Tokens** | 全链路 LLM token 消耗（ingestion + retrieval + answer） | MemEval |
| **Persona Summary F1** | 提取的 persona 与参考 persona 的 F1 | MSC |
| **Engagingness** | 人工评估回复吸引力（1-5 分） | MSC |
| **Consistency** | 人工评估跨会话一致性（1-5 分） | MSC |
| **Rule Compliance Rate** | 回复遵循注入规则的比例 | 自定义 |

### 4.2 CarryMem 特色指标（差异化优势）

| 指标 | 说明 | 为什么重要 |
|------|------|-----------|
| **Ingestion Token Cost** | 记忆存储阶段的 LLM token 消耗 | CarryMem = 0（本地分类），其他系统 > 0 |
| **Quality-per-Token** | F1 / Total Tokens | 越高越好，展示效率优势 |
| **Retrieval Latency** | P50/P95/P99 召回延迟 | CarryMem 已有 P50: 0.01ms |
| **Memory Compression Ratio** | 原始对话 tokens / 存储记忆 tokens | 展示记忆压缩效率 |
| **Zero-LLM Ingestion** | 是否不需要 LLM 即可存储记忆 | CarryMem 独有优势 |
| **Rule Compliance** | 规则遵循率 | CarryMem 独有功能 |

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

### Phase 1: LongMemEval（最快出分，1 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1.1 | 获取 LongMemEval 数据 | LongMemEval 数据 |
| 1.2 | 编写适配脚本 | 适配代码 |
| 1.3 | 运行 500 题评测 | 5 维度分数 + Overall F1 |

### Phase 2: MSC Persona Summary（产品叙事，1 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 2.1 | 从 HuggingFace 获取 MSC 数据集 | MSC 数据 |
| 2.2 | 编写 Persona Summary 适配 | 适配代码 |
| 2.3 | 运行 Persona Summary 评测 | Persona Summary F1 |

### Phase 3: MemEval（公平对比，1-2 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 3.1 | Clone MemEval，配置环境 | 可运行的 MemEval |
| 3.2 | 编写 CarryMem adapter | adapter 代码 |
| 3.3 | 跑 LoCoMo benchmark（10 conversations） | LoCoMo 分数 + Token 成本 |
| 3.4 | 跑 LongMemEval benchmark（102 questions） | LongMemEval 分数 + Token 成本 |
| 3.5 | 与 9 个系统对比 | Quality-per-Token 排行 |

### Phase 4: ES-MemEval + 自定义 Rules Eval（补充，1 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 4.1 | 获取 ES-MemEval 数据，重点跑冲突检测维度 | 冲突处理分数 |
| 4.2 | 设计并运行 Rules Eval | Rule Compliance Rate |

### Phase 5: 结果分析与报告（1 天）

| 步骤 | 内容 | 产出 |
|------|------|------|
| 5.1 | 汇总所有 benchmark 分数 | 综合对比表 |
| 5.2 | 计算 Quality-per-Token | 效率优势量化 |
| 5.3 | 分维度分析 | 强弱项识别 |
| 5.4 | 生成评测报告 | 公开发布的报告 |

### Phase 6: 优化迭代（按需）

| 优化方向 | 预期效果 | 影响的 Benchmark |
|----------|---------|-----------------|
| 添加 persona-aware prompt 模板 | 提升 Persona Summary F1 | MSC |
| 添加 time-aware query expansion | 提升 Temporal F1 | LongMemEval |
| 改进 recall 策略（entity-scoped 检索） | 提升 Multi-hop F1 | LongMemEval/MemEval |
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
> - **Knowledge Updates 最强**：冲突检测 + correction 类型是独有差异化能力
> - **规则引擎独有**：唯一支持用户自定义规则的记忆系统

### 6.2 预期分数范围

#### LongMemEval（最先出分）

| 能力 | 预期范围 | 理由 |
|------|---------|------|
| Overall F1 | 0.30-0.50 | 5 种能力各有强弱 |
| SS-User (信息提取) | 0.60-0.80 | CarryMem 分类引擎强项 |
| Multi-Session | 0.40-0.60 | 跨会话召回是核心能力 |
| Knowledge Updates | 0.50-0.70 | **冲突检测是独有优势** |
| Temporal | 0.20-0.40 | 时序推理需要增强 |
| **Total Tokens** | **1.0-2.0M** | **0 ingestion + 精确 token 预算** |

#### MSC Persona Summary

| 指标 | 预期范围 | 理由 |
|------|---------|------|
| Persona Summary F1 | 0.40-0.60 | 7 种分类类型天然适配 persona 提取 |
| **Ingestion Token** | **0** | 本地分类，不需要 LLM |

#### MemEval（公平对比）

| 指标 | 预期范围 | 理由 |
|------|---------|------|
| LoCoMo F1 | 0.35-0.50 | 本地分类可能丢失部分隐式信息 |
| **Quality-per-Token** | **最高** | F1/Tokens 比值预期优于所有对比系统 |

### 6.3 对比图表示例

```
Quality (F1) vs Cost (Tokens) — LoCoMo (via MemEval)

F1  0.60 |          * PropMem (5.9M)
    0.55 |       * OpenClaw (16.4M)
    0.50 |    * Full Context (37.5M)
    0.45 | * Hindsight (24.2M)
    0.40 |
    0.35 |              * CarryMem (~1.5M) ← 效率之王
         +----------------------------------→ Tokens
         0    5M   10M   15M   20M   25M   30M

LongMemEval — Knowledge Updates 维度

F1  0.70 |    * CarryMem (冲突检测+correction类型)
    0.50 | * PropMem
    0.40 |       * OpenClaw
    0.30 |          * Full Context
         +----------------------------------→ Systems
```

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 本地分类丢失隐式信息 | F1 偏低 | 补充 LLM 辅助分类作为可选模式 |
| FTS5 对长问题召回不足 | Multi-hop F1 偏低 | 添加 query expansion + entity 检索 |
| MSC 依赖 ParlAI 框架 | 适配成本高 | 从 HuggingFace 提取数据，绕过 ParlAI |
| MemEval 环境配置复杂 | 延迟 | 先跑 LongMemEval 直接适配 |
| API 费用 | 成本 | 使用 gpt-4.1-mini，预估 $10-20 |
| MSC 人工评估成本 | 高 | 先跑自动评估（Persona Summary F1），人工评估按需 |
| LaMP 归因困难 | 信噪比低 | 降优先级，按需跑 |

---

## 八、参考资源

- **LongMemEval**: https://github.com/xiaowu0162/LongMemEval — ICLR 2025 长期记忆 benchmark
- **MSC**: https://parl.ai/projects/msc/ — Meta Research, "Beyond Goldfish Memory" (ACL 2022)
- **MemEval**: https://github.com/ProsusAI/MemEval — 公平评估框架（2026.03），含 LoCoMo + LongMemEval + 9系统基线
- **ES-MemEval**: Evaluating Social Memory Systems (2025) — 冲突检测 + 用户建模
- **LaMP**: https://github.com/LaMP-Benchmark/LaMP — 个性化生成 benchmark (EMNLP 2024)
- **MemoryBank**: https://github.com/zhao-ht/MemoryBank — 遗忘机制 benchmark (ACL 2023)
- **LoCoMo**: https://snap-research.github.io/locomo — ACL 2024 长期对话 benchmark（通过 MemEval 覆盖）
