# ADR-012: MCP Graph Tools 工具组

## 状态: 已采纳
## 日期: 2026-07-13 (v0.8.0)
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem v0.7.0 已在内部实现了 SQLite 原生知识图谱（`KnowledgeGraph` 层 + `memory_entities`/`memory_relations` 表），支持实体召回、多跳 BFS 遍历、关系管理。但这些能力**仅通过 Python API 暴露**，未对 MCP 协议开放。

AI agent 通过 MCP 接入 CarryMem 时，只能使用既有的 28 个工具（核心记忆 CRUD、检索、规则、画像等），无法进行图维度的查询：

1. **无法多跳遍历**：agent 不能"从一个实体出发找到关联记忆"。
2. **无法探查连接路径**：agent 不能回答"实体 A 和实体 B 之间如何关联"。
3. **无法评估记忆影响力**：agent 不能判断某条记忆在图谱中的结构重要性。

知识图谱能力已内部就绪，缺的只是 MCP 工具层的封装与暴露。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 复用既有 KNOWLEDGE_TOOLS** | 把图查询塞进现有知识工具组 | 不新增工具组 | 语义混杂；工具组职责不清 |
| **B: 新增 GRAPH_TOOLS 工具组** ✅ | 单独定义 3 个图专用工具，作为独立工具组挂载 | 职责单一；便于按需启用/禁用；MCP 工具表面积清晰 | MCP 工具总数增加（28→31） |
| **C: 通用图查询 DSL 工具** | 暴露一个接受 JSON 查询语言的通用图工具 | 表达力强 | agent 难以构造查询；缺乏 schema 校验；调试困难 |

## 决策

**采用方案 B：新增 `GRAPH_TOOLS` 工具组，包含 3 个图专用 MCP 工具，MCP 工具总数 28→31。**

三个工具：

- **`query_graph`**：暴露既有 `recall_graph()` 为 MCP 工具，从指定实体出发做 BFS 多跳遍历，返回连通实体与关联记忆。`max_hops` 默认 2、上限 5；`limit` 默认 20、上限 100。
- **`shortest_path`**：新增双向 BFS 算法（`KnowledgeGraph.shortest_path()`），查找两实体间最短路径，复杂度 O(b^(d/2))，跳数硬上限 10。返回路径、长度、是否找到。
- **`get_memory_impact`**：新增影响力评分算法（`KnowledgeGraph.get_memory_impact()`），公式 `entity_count * 0.4 + relation_count * 0.4 + cross_namespace * 0.2`，评估记忆在图谱中的结构影响力。

工具组挂载到 `TOOLS` 列表末尾，并定义 `GRAPH_TOOL_NAMES` 集合便于路由与权限控制。新增 Facade 方法 `CarryMem.recall_shortest_path()`、`CarryMem.recall_memory_impact()` 及对应的 `SQLiteAdapter` / 基类默认实现。

## 后果

### 正面
- **补齐图维度**：AI agent 可通过 MCP 直接调用图查询，无需绕道 Python API。
- **工具组解耦**：`GRAPH_TOOLS` 独立定义，便于未来按需启用/禁用或做权限隔离。
- **能力门控透明**：非图适配器在基类返回空/零结果，agent 调用不会报错，降级优雅。
- **算法内聚**：`shortest_path` 与 `get_memory_impact` 算法封装在 `KnowledgeGraph` 层，MCP 工具仅做参数转发。

### 负面
- **工具总数增加**：MCP 工具达 31 个，agent 的工具选择空间变大，可能增加 prompt 长度与选错工具概率。
- **新算法维护**：双向 BFS 与影响力评分是新增算法，需独立测试与性能基线。
- **跳数限制**：`shortest_path` 硬上限 10 跳，超大规模图上可能找不到路径。

### 缓解措施
- 工具描述明确标注"Requires storage adapter with graph capability"，引导 agent 在合适场景调用。
- 双向 BFS 设硬上限防止性能退化；影响力公式简单可解释。
- 25 个新测试覆盖正向/边界/错误场景（`tests/test_v080_graph_tools.py`）。

## 实现参考 (Implementation References)

- `src/carrymem/integration/layer2_mcp/tools.py`: `GRAPH_TOOLS` 工具组定义（L761-848）——`query_graph`（L763）、`shortest_path`（L797）、`get_memory_impact`（L828）；`TOOLS` 挂载（L850-860）；`GRAPH_TOOL_NAMES`（L870）
- `src/carrymem/layers/knowledge_graph.py`: `KnowledgeGraph.shortest_path()`（L370）双向 BFS、`get_memory_impact()`（L583）影响力评分
- `src/carrymem/adapters/sqlite/__init__.py`: SQLiteAdapter `shortest_path()`（L765）、`get_memory_impact()`（L785）委托
- `src/carrymem/adapters/base.py`: `StorageAdapter` 基类 `shortest_path()`（L603）、`get_memory_impact()`（L626）默认空/零实现
- `src/carrymem/core/_recall.py`: RecallMixin `recall_shortest_path()`、`recall_memory_impact()` Facade 方法
- `tests/test_v080_graph_tools.py`: 25 个测试覆盖最短路径、影响力评分、Facade 集成
- `CHANGELOG.md`: v0.8.0 "P0-1: MCP Graph Tools" 章节
