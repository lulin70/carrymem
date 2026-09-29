# ADR-015: Evidence Link 与 Observation 模型

## 状态: 提议（Proposed）— 待 Gate 0 批准
## 日期: 2026-09-28
## 决策者: 待项目负责人批准
## 契约细节: [MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md](../../design/MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md)

---

## 上下文

当前派生信息没有统一 lineage：

1. `SemanticAggregator` 把 `aggregated_from`（最多 20 条 source id）塞进 metadata；
2. `MemifyEngine.derive_facts()` 用共现生成"事实"候选，直接落库，无来源快照、无幂等键——共现不等于事实；
3. 规则晋升的 `source_memory_ids` 验证依赖松散的 id 列表；
4. 派生对象在来源被删除后继续存在且不可察觉（无源孤儿）。

同时系统缺少结构化的"观察"对象：纠正信号、任务结果、偏好信号都淹没在自由文本记忆里，反思无法可靠消费。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 继续扩展 metadata** | 约定 metadata 键规范 | 零迁移 | 无法索引、无法强制约束、无法做反向查询，事实上的 schema 漂移 |
| **B: 每类派生对象各带 source 列** | 冗余存储 | 查询直接 | 来源关系碎片化，跨对象 provenance 无法统一 |
| **C: 独立 evidence_links 表 + observations 表** ✅ | 统一多对多 provenance；Observation 成为独立领域对象 | 统一、可索引、可校验；来源删除可级联检测 | 新增两表与写入路径 |

## 决策

采用方案 C：

1. **`memory_evidence_links`**：`(source_kind, source_id, source_snapshot_hash) → (target_kind, target_id)` + 封闭 relation_type 枚举（supports/contradicts/derived_from/observed_in/confirmed_by/supersedes）+ UNIQUE 幂等约束。链接不可变，更正走 supersedes。
2. **`memory_observations`**：结构化观察（subject/predicate/value_json/source_kind/source_ref/confidence/observed_at/expires_at），谓词封闭枚举，强制 TTL。
3. **写入准入白名单**：内部 recall 不写 Observation（防写放大，沿用 0.11.x internal/uninstrumented 语义边界教训）；单次 retain 产出的 Observation ≤ 2。
4. **快照哈希**：来源内容变更可检测，链接转 stale 触发重算。
5. **无源降级**：证据链断裂的派生对象转 `unsupported`，退出高信任路径。
6. **迁移策略**：additive 两表 + ledger；metadata 旧字段保留为兼容投影，不一次性 backfill。

## 后果

### 正面
- 任意派生对象可追溯到原始来源（Gate 1 核心验收）；
- Observation 为反思提供可靠结构化输入；
- 来源删除的级联影响可检测、可处理。

### 负面
- 写入路径增加（缓解：准入白名单 + 幂等约束 + 白名单外写入被拒并有 metrics）；
- evidence link 行数随派生增长（缓解：仅元数据不含原文；TTL 与清理策略在 D2 决策中确认）。

## 关联决策
- D2：Evidence 保留/导出/删除策略（建议：link 行永久保留，彻底删除需用户显式要求并审计）
- D3：Observation TTL 与是否进入长期 recall（建议：默认 TTL 表 + 默认不进普通 recall）

## 实现参考（Gate 0 批准后）
- `src/carrymem/adapters/sqlite/schema.py`（additive migration）
- `src/carrymem/layers/memify.py::derive_facts`（第一个 evidence link 写入点）
- `src/carrymem/layers/semantic_aggregator.py`（aggregated_from → evidence links）
