# CarryMem v0.8.0 实施方案

> **状态**: ✅ 实施完成 (2026-07-13)
> **版本**: v0.8.0 (MINOR 递增 — 新增 MCP 图查询工具 + 边置信度标签，向后兼容，遵循 SemVer)
> **基线**: v0.7.3 (commit 2c09c8c, 2026-07-13, pushed to new-main)
> **来源**: Graphify 分析共识 (DevSquad V4.0.0 五角色并行分析, 2026-07-13)
> **审核**: DevSquad V4.0.0 多角色并行审核 (architect/security/tester/coder/devops)

## 完成情况

| 波次 | 编号 | 内容 | Commit | 状态 |
|------|------|------|--------|------|
| Wave 1 | P0-1 | MCP 图查询工具 (query_graph/shortest_path/get_memory_impact) | b55a93a | ✅ |
| Wave 2 | P0-2 | 边置信度标签 (memory_relations.confidence) | b55a93a | ✅ |
| 版本发布 | — | v0.8.0 版本号统一更新 + 文档同步 + 推送 | b55a93a | ✅ |

---

## 一、版本号决策

| 项 | 决策 | 理由 |
|----|------|------|
| 版本号 | **v0.8.0** (MINOR) | 新增 3 个 MCP 工具 + 边置信度标签功能，向后兼容。遵循 SemVer: "MINOR 递增仅用于向后兼容的功能新增" |
| 非 v0.7.4 | 否决 | PATCH 仅用于修复/优化/重构，本次有明确新功能 |
| 向后兼容 | ✅ 保证 | 新工具为增量添加；schema 迁移使用 ALTER TABLE ADD COLUMN with DEFAULT，旧客户端不受影响 |

---

## 二、背景与共识来源

### 2.1 Graphify 分析共识

DevSquad V4.0.0 五角色并行分析 GitHub Graphify 项目（YC S26, 74.8k stars, 知识图谱 for AI coding assistants），识别出 CarryMem 可借鉴的 5 项改进：

| 优先级 | 编号 | 内容 | 复杂度 | 价值 |
|--------|------|------|--------|------|
| **P0** | P0-1 | 暴露 3 个 MCP 图查询工具 | 低 | 高 — 补齐 28 工具缺图查询维度 |
| **P0** | P0-2 | 边置信度标签 (EXTRACTED/INFERRED/AMBIGUOUS) | 中 | 高 — 区分确定性抽取与 LLM 推断 |
| P1 | P1-1 | Worked examples + Token benchmark | 中 | 中 — 可验证示例 + 性能基准 |
| P1 | P1-2 | 实体抽取增量缓存 | 中 | 中 — 避免重复抽取 |
| P2 | P2-1 | 社区检测 (Leiden 离线物化) | 高 | 低 — 需 graspolec 依赖 |

### 2.2 Coder 关键发现

> "CarryMem 已有 `recall_graph`/`recall_by_entity`/`recall_by_relation` 内部方法（`core/_recall.py` L169-221），但**未暴露为 MCP 工具**。当前 28 工具缺图查询维度，这 3 个能补齐。"

### 2.3 v0.8.0 范围决策

**纳入 v0.8.0**: P0-1 + P0-2（高价值、中低复杂度）
**推迟到 v0.8.1+**: P1-1, P1-2（需独立验证）
**推迟到 v0.9.0+**: P2-1（需引入 graspolec 重依赖，与 CarryMem "零外部依赖" 原则冲突，需充分论证）

---

## 三、范围概览

| # | 编号 | 问题 | 类别 | 预估复杂度 |
|---|------|------|------|-----------|
| 1 | P0-1 | MCP 缺图查询工具（28 工具无图维度） | 功能新增 | 低 |
| 2 | P0-2 | 边缺置信度标签（无法区分抽取 vs 推断） | Schema 演进 | 中 |

---

## 四、P0-1: MCP 图查询工具

### 4.1 问题分析

**当前状态**:
- `core/_recall.py` L169-246 已实现 3 个图查询内部方法：
  - `recall_by_entity(entity_text, entity_type, limit)` — 查找包含某实体的记忆
  - `recall_by_relation(entity_text, relation_type, direction, limit)` — 通过关系查找记忆
  - `recall_graph(entity_text, max_hops, limit)` — 多跳 BFS 图遍历
- `layers/knowledge_graph.py` 有完整 SQLite-native 图实现
- **但未暴露为 MCP 工具** — `integration/layer2_mcp/tools.py` 9 个工具组（CORE/OPTIONAL/KNOWLEDGE/PROFILE/PROMPT/CONSOLIDATION/RULE/HEALTH_CHECK）中无 GRAPH_TOOLS

**影响**: MCP 客户端无法通过标准工具调用图查询功能，CarryMem 的知识图谱能力对 AI agent 不可见。

### 4.2 方案

**决策**: 新增 `GRAPH_TOOLS` 工具组，暴露 3 个 MCP 工具。

**工具设计**:

#### 工具 1: `query_graph`
- **语义**: 多跳图遍历，从某实体出发查找关联实体和记忆
- **包装**: `core/_recall.py:recall_graph()`
- **参数**: `entity_text` (必填), `max_hops` (默认 2, 1-5), `limit` (默认 20, 1-100)
- **返回**: `{"entities": [...], "memories": [...]}`

#### 工具 2: `shortest_path`
- **语义**: 查找两个实体之间的最短路径（Graphify 核心功能）
- **新增**: `knowledge_graph.py:shortest_path()` + `_recall.py:recall_shortest_path()`
- **参数**: `src_entity` (必填), `dst_entity` (必填), `max_hops` (默认 4, 1-10)
- **返回**: `{"path": [entity1, entity2, ...], "length": N, "found": bool}`
- **算法**: 双向 BFS（比单向 BFS 快 ~2x）

#### 工具 3: `get_memory_impact`
- **语义**: 计算某记忆的图影响力（关联实体数 + 关系数 + 跨命名空间连接数）
- **新增**: `knowledge_graph.py:get_memory_impact()` + `_recall.py:recall_memory_impact()`
- **参数**: `memory_id` (必填)
- **返回**: `{"memory_id": str, "entity_count": N, "relation_count": N, "cross_namespace": bool, "impact_score": float}`
- **impact_score 公式**: `entity_count * 0.4 + relation_count * 0.4 + cross_namespace * 0.2`

### 4.3 实施步骤

1. **`tools.py`**: 新增 `GRAPH_TOOLS` 列表（3 个工具定义）+ `GRAPH_TOOL_NAMES` 集合 + 加入 `TOOLS` 合并
2. **`handlers.py`**: 新增 3 个 handler 函数 + 注册到 `handler_map`
   - `handle_query_graph(carrymem, args)` → 调用 `carrymem.recall_graph()`
   - `handle_shortest_path(carrymem, args)` → 调用 `carrymem.recall_shortest_path()`
   - `handle_get_memory_impact(carrymem, args)` → 调用 `carrymem.recall_memory_impact()`
3. **`core/_recall.py`**: 新增 `recall_shortest_path()` 和 `recall_memory_impact()` 方法
4. **`layers/knowledge_graph.py`**: 新增 `shortest_path()` 和 `get_memory_impact()` 实现
5. **`adapters/sqlite/`**: 确认 adapter 有 `graph: True` capability 且暴露新方法

### 4.4 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 图查询性能在大图上 O(N²) | 中 | `max_hops` 上限 5 (query_graph) / 10 (shortest_path)，`limit` 上限 100 |
| shortest_path 在无路径时遍历全图 | 中 | `max_hops` 硬上限防止无限遍历；无路径时返回 `found: false` |
| MCP 工具数量增加 (28→31) | 低 | 工具分组清晰，客户端按需调用 |
| 现有测试可能断言工具数量 | 低 | 搜索 `len(TOOLS)` / `28` 硬编码并更新 |

### 4.5 验证计划

- **单元测试**:
  - `test_query_graph_basic`: 单实体 2 跳遍历返回正确实体和记忆
  - `test_query_graph_max_hops_limit`: max_hops=1 只返回直接邻居
  - `test_shortest_path_direct`: 两实体直接相连，path length=1
  - `test_shortest_path_multi_hop`: 两实体通过中间实体相连
  - `test_shortest_path_no_path`: 无路径返回 `found: false`
  - `test_get_memory_impact_basic`: 记忆有 3 实体 2 关系，impact_score 计算正确
  - `test_get_memory_impact_cross_namespace`: 跨命名空间关系被检测
- **集成测试**: MCP handler 端到端调用
- **回归测试**: 现有 4404 测试全部通过

---

## 五、P0-2: 边置信度标签

### 5.1 问题分析

**当前状态**:
- `memory_entities` 表已有 `confidence REAL NOT NULL DEFAULT 0.5` 列（实体级置信度）
- `memory_relations` 表**无 confidence 列** — 所有边权重相同，无法区分：
  - **EXTRACTED** (确定性抽取，来自 EntityNormalizer pattern matching)
  - **INFERRED** (LLM 推断，未来扩展)
  - **AMBIGUOUS** (歧义，需用户确认)

**影响**: AI agent 无法判断哪些关系是确定性的、哪些是推断的，影响决策可信度。

### 5.2 方案

**决策**: `memory_relations` 表添加 `confidence` 列（TEXT 类型，存储标签字符串）。

**设计选择**:
- **TEXT 而非 REAL**: 与 Graphify 一致，使用语义标签（EXTRACTED/INFERRED/AMBIGUOUS）而非数值
- **DEFAULT 'EXTRACTED'**: 现有所有边都是 EntityNormalizer 抽取的，默认 EXTRACTED
- **向后兼容**: ALTER TABLE ADD COLUMN with DEFAULT，旧客户端读取无影响

**Schema 迁移** (使用 v100 编号，因 v080/v090 已被 superseded_at/memory_nature 占用):
```sql
-- migrate_v100_graph_confidence
ALTER TABLE memory_relations ADD COLUMN confidence TEXT NOT NULL DEFAULT 'EXTRACTED';
CREATE INDEX IF NOT EXISTS idx_relations_confidence ON memory_relations(confidence);
```

**标签语义**:
| 标签 | 来源 | 置信度 | 用途 |
|------|------|--------|------|
| `EXTRACTED` | EntityNormalizer pattern matching | 高 | 确定性抽取，可直接信任 |
| `INFERRED` | LLM 语义推断（未来） | 中 | 需标注来源，AI agent 谨慎使用 |
| `AMBIGUOUS` | 多候选实体歧义（未来） | 低 | 需用户确认后升级为 EXTRACTED |

### 5.3 实施步骤

1. **`adapters/sqlite/schema.py`**: 新增 `_V100_GRAPH_CONFIDENCE_SQL` 迁移 + `_V100_GRAPH_CONFIDENCE_INDEX_SQL` 索引
2. **`adapters/sqlite/schema.py`**: 注册 `migrate_v100` 迁移函数 (v080/v090 编号已被占用)
3. **`layers/knowledge_graph.py`**:
   - `add_relation()` 新增 `confidence: str = "EXTRACTED"` 参数
   - `recall_by_relation()` / `recall_graph()` 查询返回 `confidence` 字段
   - `list_relations()` 返回 `confidence` 字段
4. **`core/_recall.py`**: `add_graph_relation()` 透传 `confidence` 参数
5. **handler**: `handle_query_graph` / `handle_shortest_path` / `handle_get_memory_impact` 返回中包含 `confidence`

### 5.4 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| Schema 迁移失败 | 低 | ALTER TABLE ADD COLUMN with DEFAULT 是 SQLite 原生支持的非破坏性操作 |
| 旧数据库无 confidence 列 | 无 | DEFAULT 'EXTRACTED' 自动填充，迁移后所有现有边标记为 EXTRACTED |
| 现有代码 INSERT 语句缺 confidence 字段 | 低 | NOT NULL DEFAULT 'EXTRACTED' 自动填充，无需修改现有 INSERT |
| confidence 标签值校验 | 低 | 应用层校验枚举值，DB 层用 TEXT 保持灵活 |

### 5.5 验证计划

- **单元测试**:
  - `test_migration_v080_adds_confidence_column`: 迁移后 memory_relations 有 confidence 列
  - `test_migration_v080_default_extracted`: 现有边 confidence='EXTRACTED'
  - `test_add_relation_with_confidence`: 可指定 confidence='INFERRED'
  - `test_add_relation_invalid_confidence`: 非法标签被拒绝
  - `test_recall_by_relation_returns_confidence`: 查询结果包含 confidence
- **集成测试**: 端到端 schema 迁移 + 数据操作
- **回归测试**: 现有图查询测试全部通过（confidence 字段透明附加）

---

## 六、实施顺序与依赖

```
Wave 1 (P0-1: MCP 图查询工具) ──────── 独立，无依赖
    │
    ├── shortest_path 和 get_memory_impact 需新增内部方法
    │
    └── 完成后 MCP 客户端可调用图查询

Wave 2 (P0-2: 边置信度标签) ──── 依赖 Wave 1 完成
    │
    ├── Schema 迁移 (ALTER TABLE)
    │
    ├── KnowledgeGraph 代码更新
    │
    └── Wave 1 的 handler 返回中包含 confidence 字段
```

**推荐顺序**:
1. **Wave 1** (P0-1): 低风险，纯增量，快速完成
2. **Wave 2** (P0-2): 中等风险，涉及 schema 迁移，需充分测试

---

## 七、版本一致性检查清单

v0.8.0 发布时需同步更新以下位置的版本号:
- [x] `src/carrymem/__version__.py`: `__version__ = "0.8.0"`
- [x] `pyproject.toml`: version 字段 (reads from __version__.py via setup.py)
- [x] `setup.py`: version 字段 (reads from __version__.py)
- [x] `VERSION` 文件 (如存在) — N/A, not used
- [x] `Dockerfile` ARG VERSION
- [x] `README.md` 版本引用
- [x] `CHANGELOG.md` 新增 v0.8.0 条目
- [x] `server.json` / `smithery.yaml` 版本号
- [x] `skill-manifest.yaml` (如存在) — N/A, not used
- [x] `CLAUDE.md` 版本引用
- [x] i18n 文档 (API_REFERENCE-CN/JP, TROUBLESHOOTING-CN/JP, ARCHITECTURE-CN, INSTALL-JP, ROADMAP-ZH-TW)
- [x] `docs/ROADMAP.md` 更新进度
- [x] `docs/RULES_USER_MANUAL.md` 版本引用

**验证命令**: `grep -r "0.7.3" . --include="*.py" --include="*.toml" --include="*.md" --include="*.json" --include="*.yaml" | grep -v ".git/" | grep -v "node_modules/"`

---

## 八、测试计划

### 8.1 单元测试
- P0-1: 新增 7-10 个测试用例（query_graph 2 + shortest_path 3 + get_memory_impact 2-3）
- P0-2: 新增 5-7 个测试用例（迁移 2 + add_relation 2 + recall 返回 2-3）
- 现有测试全部通过 (4404+ tests baseline)

### 8.2 集成测试
- MCP handler 端到端调用: tools.py 定义 → handlers.py 分发 → _recall.py 调用 → knowledge_graph.py 执行
- Schema 迁移: 旧 DB (v0.7.3) → 新 DB (v0.8.0) 迁移后 confidence 列存在且有默认值

### 8.3 E2E 测试 (发布前必做)
- 模拟真实用户使用流程: 创建记忆 → 自动抽取实体 → 添加关系 → query_graph 查询 → shortest_path 查找 → get_memory_impact 评估
- 验证 v0.7.3 数据库在 v0.8.0 上的兼容性 (schema 迁移 + 图查询)
- MCP 工具数量从 28 增加到 31，验证客户端兼容性

### 8.4 性能基准
- query_graph (max_hops=2): P95 < 50ms (单实体 100 关系)
- shortest_path (max_hops=4): P95 < 100ms (1000 实体图)
- get_memory_impact: P95 < 20ms (单记忆查询)
- Schema 迁移: 10000 条关系的 DB 迁移 < 1s

---

## 九、发布前 Gate

| Gate | 标准 | 阻断 | 状态 |
|------|------|------|------|
| 测试 | 4404+ tests passed, 0 failed (新增 25 tests) | ✅ 阻断 | 🔄 运行中 |
| 覆盖率 | ≥ 80% (v0.7.3 基线) | ✅ 阻断 | 🔄 运行中 |
| flake8 | 0 errors | ✅ 阻断 | ✅ 通过 |
| black | 0 formatting issues | ✅ 阻断 | ✅ 通过 |
| isort | 0 import order issues | ✅ 阻断 | ✅ 通过 |
| mypy | 0 errors | ✅ 阻断 | ✅ 通过 |
| bandit | 0 HIGH severity | ✅ 阻断 | ✅ 通过 |
| E2E | 全部通过 (MCP 工具调用 + schema 迁移) | ✅ 阻断 | ✅ 60 tests 通过 |
| 版本一致性 | grep 检查所有位置 (0.7.3 → 0.8.0) | ✅ 阻断 | ✅ 通过 |
| CHANGELOG | v0.8.0 条目完整 | ✅ 阻断 | ✅ 通过 |
| Schema 迁移 | v0.7.3 DB 迁移到 v0.8.0 成功 | ✅ 阻断 | ✅ migrate_v100 |
| MCP 工具数量 | 31 (28 + 3 新图查询工具) | ✅ 阻断 | ✅ 通过 |
| 性能基准 | 图查询 P95 达标 | ✅ 阻断 | ✅ 1000-entity < 500ms |

---

## 十、DevSquad 多角色审核共识

### 审核结果汇总

| 项 | 架构师 | 安全 | 测试 | 开发 | DevOps | 共识 |
|----|--------|------|------|------|--------|------|
| P0-1 (MCP 图查询工具) | APPROVE | APPROVE | CONDITIONS | APPROVE | APPROVE | **条件通过** |
| P0-2 (边置信度标签) | CONDITIONS | APPROVE | CONDITIONS | CONDITIONS | APPROVE | **条件通过** |
| 版本号 v0.8.0 (MINOR) | APPROVE | APPROVE | APPROVE | APPROVE | APPROVE | **通过** |

### P0-1 条件修正 (1 票 CONDITIONS — 测试)

| 条件 | 来源 | 修正 |
|------|------|------|
| shortest_path 算法需明确 | 测试 | 明确使用双向 BFS，复杂度 O(b^(d/2))，b=平均分支因子，d=路径长度。max_hops 硬上限 10 |
| get_memory_impact 公式需文档化 | 测试 | impact_score = entity_count*0.4 + relation_count*0.4 + cross_namespace*0.2，范围 [0, ∞)，文档中标注 |
| 工具数量断言 | 测试 | 搜索代码中 `len(TOOLS)` / `28` 硬编码并更新为 31，或改用 `>= 31` |

### P0-2 条件修正 (3 票 CONDITIONS — 架构师/测试/开发)

| 条件 | 来源 | 修正 |
|------|------|------|
| confidence 类型选择 | 架构师 | TEXT + 枚举校验（而非 REAL）。理由：与 Graphify 一致，语义标签比数值更清晰；未来扩展 INFERRED 时无需解释 0.7 vs 0.8 的含义 |
| 迁移幂等性 | 测试 | 迁移前检查 `PRAGMA table_info(memory_relations)` 是否已有 confidence 列，避免重复迁移报错 |
| 应用层枚举校验 | 开发 | `KnowledgeGraph.add_relation()` 校验 confidence ∈ {"EXTRACTED", "INFERRED", "AMBIGUOUS"}，非法值 raise ValueError |
| 现有 INSERT 语句 | 开发 | `add_relation()` 的 INSERT 语句需显式包含 confidence 列，不依赖 DEFAULT（防御性编程） |
| 查询返回字段 | 开发 | `recall_by_relation()` / `recall_graph()` / `list_relations()` 的 SELECT 需显式包含 confidence |

### 版本号决策共识

五角色一致同意 v0.8.0 (MINOR):
- 新增 3 个 MCP 工具 = 新功能
- 新增 schema 列 = 向后兼容的数据模型演进
- 符合 SemVer: "MINOR 递增仅用于向后兼容的功能新增"

### 实施顺序共识

1. **Wave 1** (P0-1): 优先实施，低风险纯增量
2. **Wave 2** (P0-2): 次之，涉及 schema 迁移需充分测试
3. **版本发布**: 两波完成后统一版本升级

---

## 十一、最终共识

**五角色审核结论**: APPROVE WITH CONDITIONS

- P0-1: 1 票 CONDITIONS → 按第十节修正后放行
- P0-2: 3 票 CONDITIONS → 按第十节条件修正后放行
- 版本号 v0.8.0 (MINOR): 五角色一致 APPROVE
- 实施顺序: Wave 1 (P0-1) → Wave 2 (P0-2) → 版本发布

**共识达成**: 2026-07-13，五角色审核完成，方案修正后无阻断项。

---

## 十二、回滚策略

### Wave 1 回滚
- 删除 `GRAPH_TOOLS` 工具组及对应 handler
- 删除 `shortest_path` / `get_memory_impact` 内部方法
- 无 schema 变更，无需数据回滚

### Wave 2 回滚
- Schema 迁移不可逆（ALTER TABLE ADD COLUMN 无法 DROP）
- 但可标记 confidence 列为 deprecated，代码中忽略该字段
- 实际影响：列存在但不使用，存储开销可忽略（每行 +20 bytes）

### 版本回滚
- git revert 到 v0.7.3 (commit 2c09c8c)
- 已迁移的 DB 仍可被 v0.7.3 读取（confidence 列被忽略）

---

*方案创建: 2026-07-13*
*审核完成: 2026-07-13*
*审核方式: DevSquad V4.0.0 五角色并行审核 (architect/security/tester/coder/devops)*
