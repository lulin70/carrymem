# ADR-006: SQLite 原生知识图谱

## 状态: 已采纳
## 日期: 2026-07-11 (v0.7.0)
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem v0.6.x 已具备记忆 CRUD、分类、召回等能力，但记忆之间是**扁平孤立**的——无法表达"实体 A 与实体 B 存在关系"这类结构化知识。AI agent 在多轮对话中需要的不是单条记忆，而是**关联推理**（如"用户提到过的项目用了哪些技术栈"）。

业务场景对知识图谱提出了明确需求：

1. **多跳推理**：从一个实体出发，沿关系边遍历，召回关联记忆。
2. **实体消歧**：同一实体在不同记忆中重复出现，需要去重并聚合。
3. **关系权重**：高频共现的实体对应有更强的关联强度。

问题在于：**引入哪种图存储后端？** CarryMem 的核心定位是"零外部依赖的单文件中间件"，任何重依赖都会破坏这一承诺。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: Neo4j 外部图数据库** | 引入 Neo4j 作为图存储 | 功能最完整；Cypher 查询表达力强 | 重依赖（JVM、独立服务）；破坏单文件部署；运维成本高 |
| **B: SQLite 原生图谱** ✅ | 用 `memory_entities` + `memory_relations` 两张关系表模拟图 | 零外部依赖；与现有 SQLite 共享连接；事务一致性好 | 无原生图查询语言；多跳遍历靠应用层 BFS；不支持分布式 |
| **C: 纯内存图（networkx）** | 在进程内构建图对象 | 查询极快；API 灵活 | 进程重启即丢失；无法持久化；内存随实体数线性增长 |

## 决策

**采用方案 B：基于 SQLite 原生表实现知识图谱。**

核心实现：

- **`memory_entities` 表**：存储实体（类型、文本、置信度、namespace），`memory_key` 可空以支持独立实体。
- **`memory_relations` 表**：存储实体间关系（src/dst 外键、relation_type、weight、namespace）。
- **8 个索引**：覆盖 entity_text / entity_type / memory_key / namespace 及关系两端，保证万级实体下的查询性能。
- **`KnowledgeGraph` 层**：实体抽取委托给 `EntityNormalizer`（模式匹配，零 LLM），多跳遍历使用应用层 BFS（`recall_graph`）。
- **Schema 迁移**：`migrate_v062()` 创建两张表与索引，幂等执行。
- **向后兼容**：非 SQLite 适配器在基类返回安全空默认值（空列表 / False / 0）。

## 后果

### 正面
- **零外部依赖**：知识图谱能力内嵌于 SQLite 单文件，部署模型不变。
- **性能足够**：万级实体、十万级关系下，BFS 两跳遍历 <100ms（基准测试验证）。
- **事务一致性**：实体与记忆同库，写入/删除可纳入同一事务，无跨库一致性问题。
- **namespace 隔离**：实体与关系均带 namespace 字段，多租户场景天然隔离。
- **自动填充**：`_store_entries()` 在每次 `store_entry()` 后自动调用 `store_graph_entities()`，图谱随记忆增长自动构建。

### 负面
- **不支持分布式**：单机 SQLite 无法横向扩展；超大规模（百万级实体）需迁移至专用图数据库。
- **无图查询语言**：复杂图模式（最短路径、子图同构）需在应用层手写算法，表达力弱于 Cypher。
- **多跳成本**：BFS 每跳一次 SQL 查询，深度受 `max_hops` 限制（默认 2，上限 5）以防性能退化。

### 缓解措施
- 对高频查询路径建索引；BFS 深度硬上限保护。
- 在 `KnowledgeGraph` 层封装图算法（如 v0.8.0 新增的 `shortest_path` 双向 BFS），对上层透明。
- 基类默认实现保证非图适配器不报错，保留未来替换后端的扩展点。

## 实现参考 (Implementation References)

- `src/carrymem/layers/knowledge_graph.py`: `KnowledgeGraph` 层——实体抽取、关系管理、BFS 图遍历
- `src/carrymem/adapters/sqlite/schema.py`: `_V062_GRAPH_SQL`（L170-194）+ `migrate_v062()`（L406-418）——图谱表与索引创建
- `src/carrymem/adapters/sqlite/__init__.py`: SQLiteAdapter 图 API（`recall_by_entity` L680、`recall_graph` L743、`add_graph_relation` L787、`store_graph_entities` L844）+ 懒加载 `_get_knowledge_graph()`（L608）
- `src/carrymem/adapters/base.py`: `StorageAdapter` 基类图方法默认实现（L503+），保证非 SQLite 适配器向后兼容
- `src/carrymem/core/_recall.py`: `RecallMixin` 图召回门面方法（`recall_by_entity` L169、`recall_graph` L221）
- `src/carrymem/core/_classification.py`: `_store_entries()` 自动调用 `store_graph_entities()` 填充图谱
- `CHANGELOG.md`: v0.7.0 "Knowledge Graph" 章节
