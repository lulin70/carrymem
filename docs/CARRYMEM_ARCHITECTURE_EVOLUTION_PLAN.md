# CarryMem 架构演进方案

**版本**: v1.0
**日期**: 2026-07-11
**参与者**: PM + Architect 共识
**状态**: 规划中

---

## 1. 产品初心回顾

CarryMem 的核心定位是 **AI 身份层**（Memory + Rules + Knowledge），差异化优势：

| 优势 | 说明 | 底线 |
|------|------|------|
| **零 LLM 规则引擎** | 88% 分类覆盖，pattern-based 不依赖 LLM | 不引入 LLM 作为核心依赖 |
| **零依赖核心** | 核心仅 PyYAML，可选 extras 按需安装 | 核心不增加必选依赖 |
| **MCP 28 工具** | 最丰富的 MCP 记忆工具集 | 不减少工具数量 |
| **便携式** | 单文件 SQLite，跨模型/工具/设备 | 保持单文件部署能力 |
| **三语支持** | EN/CN/JP 全链路 | 不减少语言支持 |

**演进原则**:
1. **渐进式增强** — 新功能作为可选层添加，不破坏核心零依赖
2. **SQLite 原生** — 优先用 SQLite 能力，不引入 Neo4j/Redis 等外部服务
3. **零 LLM 优先** — 规则/分类/实体提取保持 pattern-based，LLM 仅作为可选增强
4. **API 稳定** — 现有 API 不 breaking change，新功能通过新方法或参数暴露
5. **可观测** — 每个新功能都有 metrics 和 doctor 检查

---

## 2. 中期方案（v0.7.0 — v0.8.0）

### 2.1 关系图谱 — SQLite 原生（v0.7.0，P2）✅ 已实现

**实现状态**: v0.7.0 已完成（2026-07-11）

**借鉴**: Cognee ECL 管道 + Codebase-Memory SQLite 图谱

**设计原则**:
- 不引入 Neo4j/FalkorDB — SQLite 单文件图谱（Codebase-Memory 证明可行）
- 不引入 LLM 实体提取 — 复用现有 `memory_pattern_detectors.py` 的 8 个 detect_* 方法
- 渐进式 — 现有 `recall()` 不变，新增图遍历 API

**数据模型**:
```sql
CREATE TABLE memory_entities (
    id INTEGER PRIMARY KEY,
    memory_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,      -- person/project/tech/concept/location
    entity_text TEXT NOT NULL,      -- normalized canonical form
    confidence REAL DEFAULT 0.5,
    created_at TEXT,
    FOREIGN KEY (memory_key) REFERENCES memories(storage_key)
);

CREATE TABLE memory_relations (
    id INTEGER PRIMARY KEY,
    src_entity_id INTEGER NOT NULL,
    dst_entity_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,    -- prefers/works_on/located_in/knows/decided
    source_memory_key TEXT,
    weight REAL DEFAULT 1.0,
    created_at TEXT,
    FOREIGN KEY (src_entity_id) REFERENCES memory_entities(id),
    FOREIGN KEY (dst_entity_id) REFERENCES memory_entities(id)
);

CREATE INDEX idx_entities_text ON memory_entities(entity_text);
CREATE INDEX idx_entities_memory ON memory_entities(memory_key);
CREATE INDEX idx_relations_src ON memory_relations(src_entity_id);
```

**实现路径**:
1. Schema 迁移（`adapters/sqlite/schema.py` 新增 `_V070` 迁移）
2. 实体提取集成（`_classification.py` 在 `declare()` 时调用 `memory_pattern_detectors` 提取实体）
3. 图遍历查询 API（`recall_by_entity()`, `recall_by_relation()`, `recall_graph()`）
4. 实体规范化复用现有 `entity_normalizer.py`（v0.5.1 已实现 difflib 模糊匹配）

**风险评估**:
- 🟡 中风险 — schema 迁移需向后兼容（新表不影响现有查询）
- 🟢 低风险 — 实体提取复用现有 pattern detectors，不引入 LLM
- 🟢 低风险 — 新 API 不影响现有 recall

**预期收益**:
- 多跳推理能力（"用户偏好 PostgreSQL" → "用户纠正了 MySQL 用法" 关联）
- 检索准确率提升（通过实体关系路径找到相关记忆）

### 2.2 Session 双层记忆（v0.7.0，P2）✅ 已实现

**实现状态**: v0.7.0 已完成（2026-07-11）

**借鉴**: Cognee Session + Permanent 双层记忆

**设计原则**:
- Session 层是缓存，不是持久存储 — 会话结束可选择提升到 Permanent
- 不引入新依赖 — 复用现有 `RecallCache` LRU 缓存
- 按 session_id 隔离 — 多会话并行不干扰

**实现路径**:
1. `RecallCache` 扩展 — 添加 `session_id` 参数，按会话隔离 LRU
2. 预加载策略 — 会话开始时加载高频/近期记忆到 Session 层
3. recall 优先级 — Session 层 (O(1)) → Persistent 层 (FTS5)
4. 提升机制 — `promote_to_permanent(memory_key)` 将 Session 记忆持久化

**风险评估**:
- 🟢 低风险 — 纯性能优化，不影响功能正确性
- 🟡 中风险 — 缓存一致性需仔细处理（Session 层与 Persistent 层同步）

**预期收益**:
- 会话内 recall 延迟降低 50%+（O(1) vs FTS5 查询）
- 减少持久层 I/O

### 2.3 多模式检索（v0.8.0，P2，依赖 2.1）

**借鉴**: Cognee 14 种检索模式

**设计原则**:
- 渐进式添加 — 先 3 种高价值模式，后续按需扩展
- 不破坏现有 `recall()` — 新模式通过新方法暴露
- 依赖关系图谱 — `recall_by_entity` 和 `recall_graph` 需要 2.1 完成

**新增检索模式**:
```python
def recall_by_entity(self, entity: str, entity_type: str = None) -> List[StoredMemory]:
    """Retrieve memories mentioning a specific entity."""

def recall_by_time(self, start: datetime, end: datetime = None) -> List[StoredMemory]:
    """Timeline-based retrieval within a time range."""

def recall_graph(self, entity: str, max_hops: int = 2) -> List[StoredMemory]:
    """Graph traversal: find memories connected to an entity within N hops."""
```

**风险评估**:
- 🟡 中风险 — 依赖关系图谱实现
- 🟢 低风险 — 新 API 不影响现有功能

---

## 3. 长期方案（v0.9.0+）

### 3.1 异步管道 — aiosqlite（v0.9.0，P1）

**借鉴**: Cognee 全异步 API

**设计原则**:
- **双模式共存** — 同步 API 保留（零依赖核心），异步 API 作为 `[async]` extra
- **不破坏现有 API** — 新增 `AsyncCarryMem` 类，不修改 `CarryMem`
- **MCP server 优先** — MCP server 的 `@server.tool()` 已支持 async，优先迁移

**实现路径**:
1. `aiosqlite` 添加到 `[async]` extra（不进入核心依赖）
2. `AsyncSQLiteAdapter` — 异步版 SQLiteAdapter，复用现有 SQL 但用 aiosqlite
3. `AsyncCarryMem` — 异步版 CarryMem，方法签名 `async def recall()`
4. MCP server 迁移 — 从线程池改为原生 async

**风险评估**:
- 🔴 高风险 — 全链路改造，测试覆盖需重建
- 🟡 中风险 — 双模式共存增加维护成本
- 🟢 机会 — MCP server 性能提升（去除线程池开销）

**预期收益**:
- 高并发场景吞吐量提升 2-5x（asyncio vs 线程池）
- MCP server 响应延迟降低

### 3.2 向量检索 — 可选语义层（v0.9.0+，P2）

**借鉴**: Cognee 三存储（Graph + Vector + Relational）

**设计原则**:
- **保持零依赖核心** — 向量检索作为 `[semantic]` extra（已有 sqlite-vec）
- **不默认安装 embedding 依赖** — sentence-transformers ~2GB，仅按需安装
- **混合检索** — FTS5（默认）+ 向量（可选），用户可选择启用

**实现路径**:
1. 现有 `[semantic]` extra 已包含 `sqlite-vec` + `sentence-transformers`
2. `SQLiteAdapter` 已有 `_enable_vector` 能力键
3. 新增 `recall_semantic(query, top_k=5)` — 向量相似检索
4. 混合排序 — FTS5 rank + 向量相似度加权

**风险评估**:
- 🟢 低风险 — 纯可选功能，不影响核心
- 🟡 中风险 — embedding 模型管理（下载/缓存/更新）

### 3.3 Memify 动态精炼（v1.0.0+，P3）

**借鉴**: Cognee `memify()` — 剪枝陈旧节点、强化频繁连接、添加派生事实

**设计原则**:
- **扩展现有 `consolidate_memories`** — 不新建系统
- **基于使用信号** — access_count + last_accessed + recall hit rate
- **零 LLM** — 规则-based 精炼，不引入 LLM

**实现路径**:
1. 重要性动态调整 — `importance_score = f(base_confidence, access_count, recency)`
   （v0.6.2 已部分实现 recency 衰减）
2. 派生事实 — `consolidate_memories` P1 阶段（模式检测 → 规则候选）已部分实现
3. 边强化 — 若实现关系图谱（2.1），频繁共同出现的实体对强化关系边权重
4. 自动衰减 — 长期未访问 + 低重要度记忆自动降级为 `outdated` tier

**风险评估**:
- 🟢 低风险 — 扩展现有框架，不新建系统
- 🟡 中风险 — 衰减参数需调优（避免误降级重要记忆）

---

## 4. 优先级矩阵

| 方案 | 版本 | 收益 | 复杂度 | 风险 | 优先级 |
|------|------|------|--------|------|--------|
| 关系图谱 | v0.7.0 | 高（多跳推理） | 中 | 中 | P2 |
| Session 双层记忆 | v0.7.0 | 中（性能提升） | 中 | 低 | P2 |
| 多模式检索 | v0.8.0 | 中（查询灵活性） | 中 | 低 | P2 |
| 异步管道 | v0.9.0 | 高（高并发） | 高 | 高 | P1 |
| 向量检索 | v0.9.0+ | 中（语义检索） | 中 | 低 | P2 |
| Memify 动态精炼 | v1.0.0+ | 中（自我进化） | 中 | 低 | P3 |

---

## 5. 产品初心守护检查清单

每个方案实施前必须通过以下检查：

| # | 检查项 | 通过标准 |
|---|--------|----------|
| 1 | 核心零依赖 | 新功能不增加 `install_requires` 依赖 |
| 2 | 零 LLM 优先 | 核心功能不依赖 LLM（LLM 仅作为可选增强） |
| 3 | API 稳定 | 不 breaking change 现有 API |
| 4 | SQLite 原生 | 不引入外部服务（Neo4j/Redis 等） |
| 5 | 向后兼容 | 现有用户升级无需修改代码 |
| 6 | 可观测 | 新功能有 metrics 和 doctor 检查 |
| 7 | 测试覆盖 | 新功能 ≥80% 覆盖率 |
| 8 | 文档同步 | 所有文档同步更新 |

---

## 6. 关键结论

1. **关系图谱是最大机会** — CarryMem 的扁平存储限制了多跳推理。SQLite 单文件图谱（借鉴 Codebase-Memory）是可行路径，无需引入 Neo4j。

2. **异步管道是必要的技术债** — 高并发场景下同步 SQLite 是瓶颈。但双模式共存（同步 + async）可以渐进式迁移，不破坏现有 API。

3. **向量检索已具备基础** — `[semantic]` extra 已有 sqlite-vec 和 sentence-transformers。只需暴露 `recall_semantic()` API，不需要新建系统。

4. **Memify 是长期差异化** — Cognee 的 `memify()` 将记忆从"静态存储"提升为"动态结构"。CarryMem 的 `consolidate_memories` 框架可扩展，v0.6.2 的 recency 衰减是第一步。

5. **产品初心不可妥协** — 零依赖核心、零 LLM 规则引擎、MCP 28 工具是 CarryMem 的差异化。所有演进都应保持这些优势，不引入重依赖。
