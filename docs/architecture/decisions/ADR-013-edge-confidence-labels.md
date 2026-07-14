# ADR-013: 边置信度标签

## 状态: 已采纳
## 日期: 2026-07-13 (v0.8.0)
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem v0.7.0 的知识图谱中，`memory_relations` 表的所有关系边**权重相同**（默认 `weight=1.0`），无法区分边的来源与可信度：

1. **来源不可辨**：由 `EntityNormalizer` 模式匹配**确定性抽取**的关系，与未来可能由 LLM **语义推断**的关系，在表中无任何区分字段。
2. **可信度不透明**：AI agent 调用图查询时，无法判断某条关系是"确定成立"还是"推测性结论"，可能误把推断当事实。
3. **难以分级处理**：无法对低置信度边做过滤、降权或触发人工确认流程。

随着图谱能力被 MCP 工具（ADR-012）暴露给 AI agent，关系可信度的区分变得迫切——agent 需要据此决定是否依赖某条关系进行推理。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 数值置信度（REAL）** | 用 0.0~1.0 浮点数表示置信度 | 粒度细；可做加权计算 | 语义模糊；抽取与推断的边界不清；难以做离散过滤 |
| **B: 离散标签（TEXT 枚举）** ✅ | 用 `EXTRACTED`/`INFERRED`/`AMBIGUOUS` 三种标签 | 语义明确；便于过滤与索引；可扩展 | 粒度粗；无法表达连续置信度 |
| **C: 双列（标签 + 数值）** | 同时存标签和数值 | 信息最全 | schema 复杂；当前无 LLM 推断，数值列暂无数据来源 |

## 决策

**采用方案 B：在 `memory_relations` 表新增 `confidence` 列（TEXT 类型），支持三种离散标签。**

三种标签语义：

- **`EXTRACTED`**（默认）：确定性抽取——来自 `EntityNormalizer` 的模式匹配，可信度高。
- **`INFERRED`**：LLM 语义推断——未来由 LLM 推导得出，需谨慎依赖。
- **`AMBIGUOUS`**：模糊匹配——需用户确认才能定性的关系（未来用）。

实现要点：

- **Schema 迁移 `migrate_v100()`**：`ALTER TABLE memory_relations ADD COLUMN confidence TEXT NOT NULL DEFAULT 'EXTRACTED'`。幂等——先检查列是否存在再执行。因 `migrate_v080`/`v090` 已被 `superseded_at`/`memory_nature` 占用，故用 `v100` 命名。
- **索引**：`idx_relations_confidence` 支持按标签过滤查询。
- **校验**：`_VALID_CONFIDENCE_LABELS = frozenset({"EXTRACTED", "INFERRED", "AMBIGUOUS"})`，`add_relation(confidence=...)` 校验非法值并抛 `ValueError`。
- **查询富化**：`list_relations()` 与 `recall_by_relation()` 返回结果中携带 `confidence` / `relation_confidence` 字段。
- **Protocol 同步**：`StorageAdapter.add_graph_relation()` 抽象基类与 Protocol 定义均接受 `confidence` 参数。

## 后果

### 正面
- **可信度可辨**：AI agent 可通过 MCP 查询关系时判断可信度，决定是否依赖该边推理。
- **默认安全**：所有既有关系自动获得 `EXTRACTED` 标签，向后兼容，无需迁移脚本。
- **便于过滤**：离散标签 + 索引，可高效按 `WHERE confidence = 'EXTRACTED'` 过滤高可信关系。
- **可扩展**：`INFERRED`/`AMBIGUOUS` 为未来 LLM 推断与人工确认预留通道。

### 负面
- **粒度有限**：离散标签无法表达"80% 确定是 INFERRED"这类连续置信度。
- **未来标签膨胀**：若需更多分级（如 `VERIFIED`），需修改校验集合与文档。
- **校验开销**：每次 `add_relation` 需做集合成员检查（开销极小，可忽略）。

### 缓解措施
- 标签集合用 `frozenset` 定义为模块级常量，集中管理，避免散落魔法字符串。
- 迁移幂等且自动执行，既有数据默认 `EXTRACTED`，用户无感升级。
- 校验失败抛 `ValueError` 并在消息中列出全部合法标签，便于排错。

## 实现参考 (Implementation References)

- `src/carrymem/adapters/sqlite/schema.py`: `_V100_GRAPH_CONFIDENCE_SQL`（L134-136）+ `_V100_GRAPH_CONFIDENCE_INDEX_SQL`（L138-140）+ `migrate_v100()`（L481-503）
- `src/carrymem/layers/knowledge_graph.py`: `_VALID_CONFIDENCE_LABELS`（L27）、`add_relation(confidence=...)`（L677，校验 L709）、`list_relations()` / `recall_by_relation()` 返回 confidence 字段（L844、L863）
- `src/carrymem/adapters/base.py`: `StorageAdapter.add_graph_relation()` 抽象基类接受 `confidence` 参数（L574）
- `src/carrymem/core/_protocols.py`: Protocol 定义中 `add_graph_relation` 的 `confidence` 参数
- `tests/test_v080_graph_tools.py`: `TestEdgeConfidence`（8 个测试）覆盖默认值、INFERRED、AMBIGUOUS、非法值抛错、查询富化
- `CHANGELOG.md`: v0.8.0 "P0-2: Edge Confidence Labels" 章节
