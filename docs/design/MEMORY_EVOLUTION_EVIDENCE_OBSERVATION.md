# Evidence 与 Observation 模型契约

> **版本**：v1.0
> **日期**：2026-09-28
> **状态**：已批准（Gate 0，2026-09-28；D2/D3/D8 按本文建议默认执行）
> **权威关系**：细化 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §5.2、§5.3 与 §6.4；字段定义以本文为准。
> **实现边界**：Gate 0 批准前不修改 `schema.py` 或任何存储代码。

---

## 1. 目的

解决当前最大的语义缺口：`memories` 表同时承担原始输入、事实、推断、聚合结果四种角色，而派生信息（`aggregated_from`、`source_memory_ids`、`derived`）散落在 metadata 中，无统一 lineage。

本文定义两个基础对象：

- **Evidence Link**：表达"任何派生对象由哪些来源支持或反驳"，是全部 provenance 的载体；
- **Observation**：带时间戳、来源和作用域的结构化观察，是派生的主要输入供给。

设计总原则：

> **`memories` 永远是原始证据层；派生层可失效、可重建、可追溯；证据链断裂的派生对象必须降级，不得继续以高信任参与召回与决策。**

---

## 2. Evidence Link 契约

### 2.1 字段定义

```text
memory_evidence_links
─────────────────────────────────────────────
id                   TEXT PK          证据链接唯一标识（UUIDv7）
namespace            TEXT NOT NULL    与来源和目标一致的 namespace
source_kind          TEXT NOT NULL    memory / observation / fact / external_import / reflection_run
source_id            TEXT NOT NULL    来源对象 id（memory 为 storage_key）
source_snapshot_hash TEXT NOT NULL    来源内容快照哈希（SHA-256）
target_kind          TEXT NOT NULL    fact / experience / profile / model_claim / relation / rule_candidate
target_id            TEXT NOT NULL    目标对象 id
relation_type        TEXT NOT NULL    见 2.2
support_weight       REAL NOT NULL DEFAULT 1.0   支持/反驳强度（0, 2]
created_at           TEXT NOT NULL    写入时间
```

索引：

```text
PRIMARY KEY (id)
UNIQUE (source_kind, source_id, target_kind, target_id, relation_type)   -- 幂等
INDEX idx_evidence_target (namespace, target_kind, target_id)
INDEX idx_evidence_source (namespace, source_kind, source_id)
```

### 2.2 关系类型（封闭枚举）

| relation_type | 语义 | 来源 |
|---|---|---|
| `supports` | 来源支持目标结论 | 反思/聚合 |
| `contradicts` | 来源反驳目标结论 | 冲突检测 |
| `derived_from` | 目标由来源派生 | Memify/Aggregator |
| `observed_in` | 观察发生在来源上下文中 | Observation 写入 |
| `confirmed_by` | 用户确认了目标 | 用户确认动作 |
| `supersedes` | 来源取代目标旧版本 | 纠正/更新 |

非法值写入必须抛 `ValueError`（沿用 ADR-013 边置信度标签的校验模式）。

### 2.3 不变量

| 编号 | 不变量 | 说明 |
|---|---|---|
| INV-E1 | 每条 evidence link 的 namespace 必须与 source、target 三方一致，任何查询必须先按 namespace 过滤 | 安全上下文一致性 |
| INV-E2 | evidence link 写入后不可变（不可修改 source/snapshot_hash）；更正只能新增链接并标注 supersedes | 审计完整性 |
| INV-E3 | `UNIQUE` 约束保证同一 (source, target, relation) 幂等；重复写入不产生第二行 | 幂等 |
| INV-E4 | 派生对象被召回或参与决策前，必须能查询到至少一条有效 evidence link；查询失败视为 unsupported | 无源降级 |
| INV-E5 | snapshot_hash 使来源变更可检测：来源内容更新后，旧链接标记 stale，由反思重算 | 证据新鲜度 |

### 2.4 生命周期

```text
创建     retain/reflect 时写入（Phase 1 起逐步接入现有派生路径）
有效     参与 provenance 查询与信任计算
stale    来源内容变更（snapshot_hash 不匹配），等待重算
失效     来源被删除且无替代证据 → 目标对象转 unsupported
清理     仅在用户显式要求彻底删除时随目标对象级联删除并审计
```

**证据保留策略（待批准决策 D2）**：建议默认永久保留 evidence link 行本身（仅元数据，不含原文），原文仍以 `memories` 行为准；用户彻底删除来源时，evidence link 与派生对象一同进入 unsupported 并按用户要求级联清理。此默认值需 Gate 0 确认。

### 2.5 与现有 metadata 的兼容

现有分散标注的映射关系（Phase 1 逐步迁移，不一次性 backfill）：

| 现有标注 | 位置 | 迁移后 |
|---|---|---|
| `aggregated_from` | SemanticAggregator metadata | `derived_from` evidence links（保留 metadata 字段做兼容投影） |
| `source_memory_ids` | 规则晋升/验证 | `supports` evidence links |
| `derived` / `inferred` 标记 | metadata | 目标对象 `source_kind` 列（新增） |
| 图谱关系 | `memory_relations` | `memory_relations.confidence`（ADR-013）+ evidence link 双向引用 |

兼容规则：迁移完成前，metadata 旧字段继续读写（不删除）；迁移后旧字段降级为只读投影。任何时点，新代码不得以 metadata 为唯一 provenance 来源。

---

## 3. Observation 契约

### 3.1 定位

Observation 是"某时刻、某来源、某作用域下看到的一个结构化事实信号"。它与 Fact 的区别：

| 维度 | Observation | Fact |
|---|---|---|
| 默认信任 | 中或未知 | 高（用户陈述）或显式标记（派生） |
| 生命周期 | 短期，有 TTL | 长期，版本化 |
| 进入默认 recall | **否**（待批准决策 D3） | 是 |
| 可否直接改变系统状态 | 否 | 经受控路径可 |
| 数量控制 | 严格准入 + TTL 清理 | 去重 + supersede |

### 3.2 字段定义

```text
memory_observations
─────────────────────────────────────────────
id            TEXT PK          唯一标识（UUIDv7）
namespace     TEXT NOT NULL    安全上下文
subject       TEXT NOT NULL    观察主体（规范化实体，经 EntityNormalizer）
predicate     TEXT NOT NULL    观察谓词（封闭枚举，见 3.3）
value_json    TEXT NOT NULL    观察值（JSON）
source_kind   TEXT NOT NULL    user_feedback / task_result / correction / lifecycle_event / recall_signal
source_ref    TEXT NOT NULL    来源引用（memory key / task id / proposal id）
confidence    REAL NOT NULL DEFAULT 0.5
observed_at   TEXT NOT NULL    观察发生时间
expires_at    TEXT NOT NULL    过期时间（TTL）
created_at    TEXT NOT NULL
```

索引：`(namespace, subject, predicate)`、`(expires_at)`、`(namespace, source_kind)`。

### 3.3 谓词枚举（初版）

```text
preference_detected      观察到偏好信号
correction_detected      用户纠正了某结论
entity_state             实体状态变化（项目/工具/关系）
task_outcome             任务结果（成功/失败/用户满意）
conflict_signal          与现有记忆冲突的信号
usage_pattern            使用模式（何时、何场景被召回）
```

枚举扩展必须经过本文档版本更新，禁止运行时自由字符串。

### 3.4 写入准入（防写放大）

**核心约束：内部 recall 不默认写 Observation。**

允许写入 Observation 的场景（白名单）：

1. 用户显式反馈（纠正、确认、评分）；
2. 任务结果信号（用户主动触发且系统可判定结果）；
3. 纠正检测路径（现有 `_classification.py` 纠错分支的结构化产物）；
4. 关键生命周期事件（supersede、冲突裁决、提案应用）；
5. 显式 API 调用 `record_observation()`。

**禁止写入**的场景：

- 每次内部召回（规则候选、指代消解、纠错历史读取——这些路径在 v0.11.x 已被定义为非用户 recall）；
- 每次向量/FTS 命中；
- 定时任务的常规轮转。

准入守卫（不变量）：

| 编号 | 不变量 |
|---|---|
| INV-O1 | 非白名单路径写入 Observation 必须被拒绝并计入 metrics（`observation_write_denied`） |
| INV-O2 | 单次用户 retain 产生的 Observation 数 ≤ 2（纠正 + 偏好各至多 1 条） |
| INV-O3 | Observation 必须有 `expires_at`；无 TTL 的写入被拒绝 |
| INV-O4 | Observation 不得直接作为 `accepted` 事实参与决策，必须经反思提案确认 |

### 3.5 TTL 与聚合（待批准决策 D3）

建议默认：

```text
correction_detected      180 天（纠正信号相对持久）
preference_detected       90 天
entity_state              90 天
task_outcome              30 天
conflict_signal           30 天
usage_pattern              14 天
```

聚合路径：同类 subject+predicate 的 Observation 在 TTL 内累计到阈值（如 ≥3 条、置信度加权）→ 由反思生成 Fact/Profile 候选提案 → 用户确认后成为 Fact，Observation 保留为证据。聚合不删除原始 Observation（保留 provenance），仅过期清理。

**是否进入长期 recall（待批准 D3）**：建议默认**不进入**普通 recall，仅在 `conflict_resolution` 与 `reflection` 任务模式下按需读取。此默认值需 Gate 0 确认。

### 3.6 隐私与安全

- Observation 的 `value_json` 属于内容数据：写入前应用与 memories 一致的脱敏策略；namespace 隔离强制；
- metrics 只允许记录 `source_kind`、谓词枚举、数量与延迟，禁止记录 subject/value 原文；
- 导出 allowlist：默认不含 Observation；用户显式选择时才包含，且导出包内保留 namespace 绑定；
- 删除来源记忆时，`source_ref` 指向它的 Observation 转 unsupported（与 evidence link 同规则）。

---

## 4. Phase 1 接入点（只列接口，不实现）

Gate 0 批准后，Phase 1 按以下顺序接入现有代码（详见 [Phase 1 Readiness](PHASE1_PROVENANCE_READINESS.md)）：

1. `schema.py`：新增 `memory_evidence_links`、`memory_observations` 两表（additive，migration ledger 记录）；
2. `layers/memify.py::derive_facts`：派生结果写入 evidence link（`derived_from`），标记 candidate；
3. `layers/semantic_aggregator.py`：`aggregated_from` 同步写 evidence link；
4. `core/_classification.py` 纠错分支：产出 `correction_detected` Observation；
5. 删除路径（`forget_memory`）：级联触发 evidence/observation 的 unsupported 标记。

---

## 5. 与 Gate 0 决策的对应

| 决策 | 内容 | 本文建议默认 |
|---|---|---|
| D2 | Evidence 保留、导出与删除策略 | link 行永久保留（仅元数据）；彻底删除需用户显式要求并审计 |
| D3 | Observation TTL 与长期 recall | 见 §3.5 默认 TTL 表；默认不进普通 recall |
| D8 | Audit/Metrics 隐私 | 见 §3.6：metrics 零原文、导出默认不含 |

三项决策的最终取值以项目负责人 Gate 0 批准为准。
