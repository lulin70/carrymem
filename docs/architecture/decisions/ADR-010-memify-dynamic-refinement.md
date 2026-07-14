# ADR-010: Memify 动态精炼

## 状态: 已采纳
## 日期: 2026-07-11 (v0.7.2)
## 决策者: CarryMem 核心团队

---

## 上下文

随着记忆数量增长，CarryMem 面临"记忆熵增"问题：

1. **重要记忆被淹没**：大量低价值记忆稀释了高价值记忆的可见度，召回时噪声占比上升。
2. **隐含关系未被发现**：频繁共现的实体对（如"React"与"前端"）蕴含结构化事实，但从未被显式记录。
3. **陈旧记忆持续占位**：长期未被访问、重要性低的记忆仍参与召回排序，拖累相关性。

受 Cognee 的 Memify 模式启发，需要一套**基于使用信号的动态精炼机制**，让记忆质量随使用自动改善，而非依赖人工整理。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: LLM 驱动精炼** | 调用 LLM 分析记忆并生成摘要/关系 | 精炼质量高；能处理复杂语义 | 引入 LLM 依赖与成本；延迟高；不可离线运行 |
| **B: 纯 SQL 信号驱动** ✅ | 基于实体共现、访问频次、时间衰减等信号，纯 SQL 分析精炼 | 零 LLM；可离线/后台运行；确定性强 | 仅能发现统计层面模式；语义理解弱于 LLM |
| **C: 手动整理工具** | 提供 CLI 让用户手动合并/删除记忆 | 用户掌控力强 | 无法规模化；依赖人工；违背"自动精炼"目标 |

## 决策

**采用方案 B：引入 `MemifyEngine`，基于使用信号纯 SQL 动态精炼记忆。**

三阶段精炼（灵感来自 Cognee Memify，零 LLM）：

1. **`derive_facts(namespace, min_co_occurrence=3)`**：通过 `memory_entities` 上的 SQL JOIN 发现共现频次 ≥ 阈值的实体对，为每对生成 `type="relationship"` 的派生记忆（`metadata.derived=true`）。置信度保守取值 `min(0.6, 0.3 + count * 0.05)`。
2. **`reinforce_edges(namespace)`**：为共现实体对创建/更新 `co_occurs` 关系，权重按 upsert 模式递增并设上限（`max_weight` 封顶），强化高频关联。
3. **`auto_decay(namespace)`**：三重门控衰减——同时满足"陈旧 + 低重要性 + 零访问"的记忆才标记 `metadata.decayed=true` 并将 `importance_score * 0.5`。**不修改 tier 列**，保持分级稳定。幂等：跳过已衰减和已废弃记忆。

统一入口 `consolidate_memories()` 串联三阶段，暴露在 `SQLiteAdapter`、`StorageAdapter` 基类（默认空结果）、`RecallMixin` 及 `RecallOps` Protocol 上。

## 后果

### 正面
- **记忆质量随使用改善**：高频共现关系被显式记录并强化，重要记忆重要性提升，陈旧记忆衰减退场。
- **零 LLM 成本**：纯 SQL 分析，可离线/后台定时运行，无 API 调用开销。
- **保守安全**：衰减三重门控避免误伤活跃记忆；仅写 metadata 标记，不改 tier 列，可逆。
- **幂等可重入**：重复运行 `consolidate_memories()` 不会重复派生或重复衰减。

### 负面
- **需要后台计算**：精炼是批量任务，需调度执行（定时或手动触发），非实时。
- **语义理解有限**：纯统计信号无法发现深层语义关联，质量上限低于 LLM 方案。
- **派生记忆膨胀**：`derive_facts` 会新增记忆条目，需靠 `max_derived`（默认 10）控制单次产出。

### 缓解措施
- 衰减仅标记 metadata、不改 tier，保留可逆性。
- `max_derived` 限制单次派生数量，防止记忆库膨胀。
- 性能基线写入测试：`derive_facts` 100 实体 <500ms，`auto_decay` 200 记忆 <200ms。

## 实现参考 (Implementation References)

- `src/carrymem/layers/memify.py`: `MemifyEngine`——`derive_facts()`（L45）、`reinforce_edges()`（L93）、`auto_decay()`（L166）
- `src/carrymem/adapters/base.py`: `StorageAdapter.consolidate_memories()` 基类默认实现（L670，返回空结果）
- `src/carrymem/core/_recall.py`: RecallMixin 暴露的 `consolidate_memories()` 门面方法
- `src/carrymem/core/_protocols.py`: `RecallOps` Protocol 的 `consolidate_memories` 签名
- `CHANGELOG.md`: v0.7.2 "Memify Engine" 章节
