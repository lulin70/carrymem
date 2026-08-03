# CarryMem 方法论：记忆工程设计空间

> **版本**: v0.9.9 | **日期**: 2026-08-03 | **状态**: 新增
> **来源**: issue #42 — 基于 ai-agent-book (bojieli) 第 3 章「三套正交分类」方法论

---

## 1. 正交分类表：记忆工程的三维设计空间

CarryMem 的所有能力可以用三套正交的维度完整描述。三轴可自由组合，每个组合对应一个具体的功能点。

### 表 1-1：三轴正交分类体系

| 分类体系 | 回答的问题 | CarryMem 具体类别 | 对应工具/功能 |
|---------|-----------|----------------|-------------|
| **记忆类型**（What） | 存的是什么？ | 偏好（Preference） | `declare_preference` |
| | | 决策（Decision） | `classify_and_remember` |
| | | 纠正（Correction） | `classify_and_remember` |
| | | 规则（Rule） | `add_rule` / `inject_rules` |
| **存储格式**（How） | 用什么形式存？ | 文本（Notes） | `classify_and_remember` |
| | | JSON Cards | 内部结构化存储 |
| | | 知识图谱（Graph） | `query_graph` / `shortest_path` |
| | | 可执行规则（Executable Rule） | `add_rule` → 规则引擎匹配 |
| **生命周期**（When） | 何时生效？ | 写入（Write） | `remember` / `classify_and_remember` |
| | | 召回（Recall） | `recall_memories` / `get_system_prompt` |
| | | 固化（Consolidate） | `consolidate_memories`（P0 去重/P1 模式/P2 语义） |
| | | 遗忘（Forget） | `forget_memory` / `forget_expired` |

### 表 1-2：组合示例

| 记忆内容 | 类型 | 格式 | 生命周期 | 效果 |
|---------|------|------|---------|------|
| "偏好靠窗座位" | 偏好 | JSON Card | 长期有效 | recall 时自动注入 system prompt |
| "纠正：端口号应为 5432" | 纠正 | 可执行规则 | 永久 | match_rules 时验证，重复则阻断 |
| "规则：使用 PostgreSQL" | 规则 | 可执行规则 | 永久 | inject_rules 注入，always 优先级 |
| "上周讨论过预算" | 决策 | 文本 | 时间衰减 | consolidate 后降权，遗忘阈值后清理 |
| "用户偏好暗黑模式" | 偏好 | JSON Card | 长期有效 | declare_preference 固化，永不衰减 |

### 认知科学对应（Why）

参考 ai-agent-book 第 3 章认知科学框架：

| 认知类型 | 人类例子 | CarryMem 对应 |
|---------|---------|-------------|
| 情景记忆（Episodic） | "上周三讨论了项目预算" | 文本 Notes，含时间戳 |
| 语义记忆（Semantic） | "用户偏好 PostgreSQL" | JSON Cards / Preference |
| 程序记忆（Procedural） | "先搜索直飞→确认座位→订餐" | Executable Rules / Skills |

**偏好永不衰减**是 CarryMem 区别于所有其他框架的独特策略——人类语义记忆不会随时间自然消失，CarryMem 的 preference 类型同样不受时间衰减影响。

---

## 2. 设计空间定位图：竞品坐标系

### 2.1 设计空间定义

记忆框架可以用三个轴定位：

```
X轴：便携性      单人单设备 ←————————→ 团队共享
Y轴：可执行性    纯检索 ←————————————→ 可执行约束
Z轴：零依赖      完全自包含 ←———————→ 依赖外部服务
```

### 2.2 各框架定位

| 框架 | 便携性 | 可执行性 | 零依赖 | 定位描述 |
|------|-------|---------|--------|---------|
| **CarryMem** | 团队共享（.carry 文件） | 可执行规则（Rules Engine） | 零依赖（仅 SQLite） | **唯一三者交汇点** |
| **Mem0 v3** | 单人 | 纯检索（追加日志） | 依赖外部向量库 | 检索优先，无规则引擎 |
| **Memobase** | 团队（画像） | 纯检索（Profile+Event） | 依赖外部服务 | 用户画像+事件，无规则引擎 |
| **User as Code** | 单人 | 完全可执行（Python 代码） | 依赖代码执行环境 | 可执行性最强，不可移植 |
| **Cognee** | 单人 | 纯检索（图+向量混合） | 依赖 Neo4j/Kuzu/向量库 | 检索功能强，架构复杂 |
| **Codebase-Memory-MCP** | 单人 | 纯检索（代码图谱） | 零依赖（单二进制） | 代码专用，无通用记忆 |

### 2.3 CarryMem 的独特位置

```
                    零依赖
                       ↑
                       |  CarryMem ←———— (团队共享, 可执行规则, 零依赖)
                       |
    Cognee           |  Memobase
    (向量库依赖)      |
                       |  Mem0 v3
    Codebase-MCP     |  (向量库依赖)
    (代码专用)        |
                       |  User as Code
                       |  (代码执行环境依赖)
                       └————————————————————→ 可执行性
                       ↑
                       |
              便携性：单人 ←————————→ 团队
```

**CarryMem 是唯一在「团队共享 + 可执行规则 + 零依赖」三者交汇点的框架。**

### 2.4 差异化声明（边界即方法论）

CarryMem **不做**：
- **参数内化**（User as Engram / LoRA）：与零依赖冲突，违反便携性
- **向量检索**（向量数据库）：与零依赖冲突，引入外部依赖
- **多模态感知记忆**（声音/图像编码）：超出当前产品定位
- **异步管道**（aiosqlite）：P2 以后考虑，当前同步 SQLite 已满足需求

---

## 3. 评估 Benchmark：超越 PrefEval 单一指标

### 3.1 现有评估

| 基准 | 分数 | 来源 | 说明 |
|------|------|------|------|
| PrefEval | 83.0% | ICLR 2025 Oral | 偏好遵循率（200 样本） |

### 3.2 自有评估维度（件套 2，P2 延期）

> 当前仅规划，详见 `docs/EXTERNAL_MEMORY_BENCHMARKS.md` 完整 benchmark 计划。

| 维度 | 指标 | 方法 | 状态 |
|------|------|------|------|
| 偏好 adherence | 偏好遵循率 | PrefEval（已有） | ✅ |
| 决策一致性 | 决策不被重复质疑率 | 自定义评估集 | 📋 规划 |
| 纠正有效性 | 纠正不被重复犯错率 | 自定义评估集 | 📋 规划 |
| 冲突检测 | 多条记忆矛盾时识别率 | LongMemEval Knowledge Updates 维度 | ✅ |
| 聚合能力 | 跨记忆统计类问题正确率 | 参考 User as Code 论文（6-43% vs 99%） | 📋 规划 |

### 3.3 P2 Benchmark 实施规划（v0.10.x）

件套 2 延期到 v0.10.x（MINOR），实施路径：

| 阶段 | 交付物 | 评估维度 | 依赖 |
|------|--------|---------|------|
| v0.10.0 | `benchmarks/carrymem_eval/` 评估框架骨架 | 偏好 adherence（复用 PrefEval 200 样本） | 无 |
| v0.10.1 | 决策一致性评估集（100 样本） | 决策不被重复质疑率 | LLM judge 或规则匹配 |
| v0.10.2 | 纠正有效性评估集（100 样本） | 纠正不被重复犯错率 | 历史纠正记录 + 重放 |
| v0.10.3 | 聚合能力评估集（50 样本） | 跨记忆统计类问题正确率 | 参考 User as Code 方法 |

**设计原则**：
- 评估集必须可离线运行（零依赖核心原则）
- LLM judge 作为可选依赖（`pip install carrymem[eval]`）
- 评估结果输出 JSON + Markdown 双格式，支持 CI 集成
- 基准数据集版本化（`benchmarks/data/v1/`），支持回归对比

**与竞品 benchmark 的关系**：
- PrefEval（ICLR 2025）：偏好遵循——CarryMem 已有 83%，作为基线
- LongMemEval（ICLR 2025）：5 维度——复用 Knowledge Updates 维度
- User as Code 聚合测试：6-43% → 99%——CarryMem 目标 >80%（规则引擎 + 图谱聚合）

---

## 4. 与 ai-agent-book 第 3 章的关系

ai-agent-book 第 3 章「用户记忆和知识库」提供了通用框架，本文档是 CarryMem 对该框架的具体化：

| ai-agent-book | CarryMem 实现 |
|-------------|-------------|
| 表 3-1 三套正交分类 | 表 1-1 本文档（三轴 + CarryMem 具体类别） |
| 四种存储格式 | 文本/JSON Cards/知识图谱/可执行规则 |
| Mem0 v3 案例 | Mem0 v3 竞品定位 |
| Memobase 案例 | Memobase 竞品定位 |
| User as Code | User as Code 竞品定位 + 差异化边界 |
| 认知科学框架 | 情景/语义/程序记忆映射 |
| 记忆压缩机制 | `consolidate_memories` P0/P1/P2 三级固化 |
| 日志脱敏 | `forget_memory` / 审计日志 |

---

## 5. 参考

- ai-agent-book 第 3 章：https://bojieli.github.io/ai-agent-book/book/chapter3.html
- User as Code 论文：Li, Bojie. arXiv:2606.16707, 2026
- LongMemEval：ICLR 2025，5 维度记忆评估
- PrefEval：ICLR 2025 Oral，Amazon Science
