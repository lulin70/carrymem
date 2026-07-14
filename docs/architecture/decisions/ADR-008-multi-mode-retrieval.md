# ADR-008: 多模式检索 API

## 状态: 已采纳
## 日期: 2026-07-11 (v0.7.1)
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem v0.7.0 之前只有 `recall_memories()` 单一检索入口，内部固定走 FTS + 向量 RRF 融合。但不同业务场景对检索的诉求差异很大：

1. **时间范围检索**："上周聊过的部署方案"——纯时间过滤，不需要语义匹配。
2. **纯语义检索**："和容器化相关的内容"——只需向量相似度，排除 FTS 噪音。
3. **显式混合检索**：需要按场景调节 FTS 与向量的权重比例，而非使用全局默认。
4. **统一多模式**：一次调用同时跑多种模式并合并去重，避免上层多次往返。

单一入口无法满足这些差异化需求；强制上层自行组合底层原语又会暴露过多内部实现细节。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 单入口 + 参数开关** | 在 `recall_memories()` 增加大量参数控制行为 | 入口统一 | 参数爆炸；语义混杂；难以测试 |
| **B: 多模式独立 API + 统一入口** ✅ | 提供 4 个语义明确的独立方法 + `recall_multi_mode()` 统一聚合 | 每个方法职责单一；可独立测试；上层按需选用 | API 数量增加；学习成本上升 |
| **C: 查询 DSL** | 设计类 Elasticsearch 的 JSON 查询语言 | 表达力最强 | 过度工程化；学习曲线陡；对个人工具项目过重 |

## 决策

**采用方案 B：提供 6 种检索模式，通过独立 API + 统一聚合入口暴露。**

四种独立 API：

- **`recall_by_time(start, end)`**：时间范围检索，`[start, end)` 半开区间，按 `created_at` 降序。
- **`recall_semantic(query)`**：纯向量相似度检索（不触发 FTS、不做 RRF 融合），能力门控——向量搜索未启用时返回空列表。
- **`recall_hybrid(query, fts_weight, vec_weight, rrf_k)`**：显式混合检索，支持**单次调用**覆盖适配器 RRF 配置，在 `finally` 块中恢复，保证线程安全。
- **`recall_multi_mode(query, modes)`**：统一多模式入口，支持 6 种模式（`fts` / `vector` / `hybrid` / `graph` / `time` / `entity`），返回结构化 `{modes, merged, mode_count, total_count}`，按 `storage_key` 去重。

底层由 `RecallEngine` 的 3 个可组合私有方法支撑：`vector_search_only`、`hybrid_search`、`search_by_time`。

设计约束：
- **零新依赖**：全部基于既有 FTS5 + 向量检索基础设施，无需 schema 迁移。
- **基类默认安全**：非 SQLite 适配器在基类返回空默认值，保证向后兼容。
- **Protocol 一致**：`RecallOps` 同步更新 4 个新方法签名。

## 后果

### 正面
- **API 更灵活**：上层可按场景精确选择检索模式，避免"一刀切"。
- **线程安全**：`recall_hybrid` 的 save/restore 模式确保临时覆盖 RRF 配置不会泄漏到其他线程。
- **优雅降级**：未知模式或缺参数的模式被初始化为空列表而非静默丢弃，行为可预测。
- **可组合**：`recall_multi_mode` 一次调用即合并多模式结果，减少上层往返。

### 负面
- **学习成本增加**：4 个新方法 + 6 种模式，API 表面积扩大，新用户需要理解何时用哪个。
- **权重调参**：`recall_hybrid` 暴露 `fts_weight` / `vec_weight` / `rrf_k`，不当取值会影响检索质量。
- **维护负担**：每新增一种模式需同时更新独立方法、统一入口、Protocol 签名与基类默认值。

### 缓解措施
- 文档为每种模式提供典型场景示例（时间范围用 `recall_by_time`，语义匹配用 `recall_semantic`）。
- 基类默认实现兜底，确保非 SQLite 适配器不报错。
- 性能基线写入测试：`recall_by_time` 1000 条 <50ms，`recall_hybrid` <100ms。

## 实现参考 (Implementation References)

- `src/carrymem/core/_recall.py`: RecallMixin 公共 API——`recall_by_time()`（L475）、`recall_semantic()`（L500）、`recall_hybrid()`（L527）、`recall_multi_mode()`（L560）
- `src/carrymem/adapters/sqlite/recall_engine.py`: RecallEngine 可组合私有方法——`vector_search_only()`（L585）、`hybrid_search()`（L642）、`search_by_time()`（L727）
- `src/carrymem/adapters/base.py`: `StorageAdapter` 基类默认实现——`recall_by_time()`（L690）、`recall_semantic()`（L715）、`recall_hybrid()`（L738）、`recall_multi_mode()`（L767）
- `CHANGELOG.md`: v0.7.1 "Multi-Mode Retrieval API" 章节
