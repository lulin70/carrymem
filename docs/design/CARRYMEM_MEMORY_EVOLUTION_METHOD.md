# CarryMem 记忆演进方法论与全面优化方案

> **版本**：v1.0  
> **日期**：2026-09-28  
> **状态**：**Gate 0 已批准（2026-09-28）**，Phase 1 Provenance 实现已授权；Phase 0 契约文档集见 §16  
> **适用范围**：CarryMem 核心记忆、召回、反思、规则、图谱、异步、SQLite 迁移、可观测性与发布质量  
> **重要边界**：Phase 1 仅实现 Provenance 基础（evidence links）；Phase 2+ 能力（Observation/Conflict/Proposal/RecallPlan）按生命周期逐 Gate 推进，禁止跨阶段实现。

---

## 1. 摘要

CarryMem 已经具备可靠的本地记忆基础设施：SQLite 单文件存储、FTS5/可选向量/图谱混合召回、namespace 隔离、版本链、Session 记忆、规则系统、Memify 精炼、异步适配器、MCP/CLI/Python 多入口以及完整的发布质量门禁。

当前真正的瓶颈不是“缺少一个检索算法”，而是记忆的语义层仍分散在 `memories`、`metadata`、图谱行、规则候选和 consolidation 流程中，尚未形成统一的：

- 原始证据模型；
- 事实、经验、观察的领域边界；
- 证据链和冲突裁决模型；
- 可审计、可恢复、可幂等的反思过程；
- 面向任务和预算的召回契约；
- 从 retain 到 recall 再到 reflect 的产品闭环。

本方案采用以下总路线：

```text
Raw Memory
  → Evidence / Observation
  → Fact / Experience
  → Profile / Mental Model
  → Task-oriented Recall
  → Reflect Proposal
  → Approved Projection
```

核心原则是：

> **原始记忆保留事实来源，派生层负责结构化和解释，反思只产生可追踪的提案，召回只返回有边界的证据与上下文，任何高影响变更都必须可审计、可撤销、可恢复。**

---

## 2. 方案目标与非目标

### 2.1 目标

1. 将 CarryMem 从“记忆存储 + 多路召回”升级为“可演化、可解释、可证据追溯的本地知识系统”。
2. 保留 SQLite-first、本地优先、核心无需外部服务、零 LLM 规则与分类能力。
3. 保持现有 Stable API、CLI、MCP 工具和数据迁移路径的兼容性。
4. 支持事实、经验、观察、Profile、Mental Model 的分层表达。
5. 让每个派生结论都能追溯到来源、算法、时间和反思运行。
6. 把 `recall` 从“返回列表”升级为受任务、作用域、证据和预算约束的召回计划。
7. 把 `reflect` 从隐式维护动作升级为可恢复、幂等、可审批的提案生命周期。
8. 将产品质量从“测试通过”扩展到召回质量、纠正有效性、上下文相关性、迁移完整性和真实用户 E2E。

### 2.2 非目标

本阶段不做：

- 将主存储替换为 PostgreSQL、Neo4j、Redis 或云端记忆服务；
- 强制引入 LLM、向量模型或外部 embedding 服务；
- 一次性重写 `memories` 表和全部 Stable API；
- 让模型自动修改权限、namespace、删除策略或高风险规则；
- 以“功能数量”追赶竞品；
- 在没有证据、冲突和回滚契约前开启激进自动 consolidation；
- 在用户批准前执行大规模 schema、recall 或规则实现改造。

---

## 3. 当前基线与核心判断

### 3.1 已实现资产

| 能力 | 当前基线 | 主要位置 |
|---|---|---|
| 原始记忆 | `StoredMemory`、版本链、supersession、TTL、重要性、加密 | [`adapters/base.py`](../../src/carrymem/adapters/base.py)、[`adapters/sqlite/schema.py`](../../src/carrymem/adapters/sqlite/schema.py) |
| 写入/retain 基础 | 分类、脱敏、指代消解、纠正、审计、metrics | [`core/_memory_crud.py`](../../src/carrymem/core/_memory_crud.py)、[`core/_classification.py`](../../src/carrymem/core/_classification.py) |
| 多路 recall | FTS5、向量、查询扩展、语义回退、RRF/多模式召回 | [`adapters/sqlite/recall_engine.py`](../../src/carrymem/adapters/sqlite/recall_engine.py)、[`core/_recall.py`](../../src/carrymem/core/_recall.py) |
| 图谱 | 实体规范化、实体/关系表、BFS、多跳、关系置信度标签 | [`layers/entity_normalizer.py`](../../src/carrymem/layers/entity_normalizer.py)、[`layers/knowledge_graph.py`](../../src/carrymem/layers/knowledge_graph.py) |
| consolidation | 去重、supersede、衰减、遗忘建议、P1/P2 聚合 | [`consolidation.py`](../../src/carrymem/consolidation.py)、[`core/_maintenance.py`](../../src/carrymem/core/_maintenance.py) |
| Memify | 派生关系、边强化、自动衰减 | [`layers/memify.py`](../../src/carrymem/layers/memify.py) |
| Session | Session/Permanent 双层记忆与缓存 | [`docs/architecture/decisions/ADR-007-session-dual-layer-memory.md`](../architecture/decisions/ADR-007-session-dual-layer-memory.md) |
| 异步 | `AsyncCarryMem`、`AsyncSQLiteAdapter`，保留同步 API | [`async_carrymem.py`](../../src/carrymem/async_carrymem.py)、[`docs/architecture/decisions/ADR-009-async-pipeline.md`](../architecture/decisions/ADR-009-async-pipeline.md) |
| 规则 | 候选、检测、队列、确认、规则注入 | [`rules/promotion_pipeline.py`](../../src/carrymem/rules/promotion_pipeline.py)、[`rules/sanitizer.py`](../../src/carrymem/rules/sanitizer.py) |
| 入口 | Python、CLI、MCP、VSCode 集成 | [`docs/API_STABILITY.md`](../API_STABILITY.md)、[`docs/ENTRY_POINTS.md`](../ENTRY_POINTS.md) |
| 质量门禁 | 单元/集成/E2E、覆盖率、mypy、静态检查、真实 MCP 指标测试 | [`pyproject.toml`](../../pyproject.toml)、`.github/workflows/ci.yml`、`tests/e2e/` |

### 3.2 主要缺口

1. `memories` 既承担原始输入，又承担事实、推断、关系和聚合结果，语义边界不清。
2. `derived`、`aggregated_from`、`source_memory_ids` 等信息分散在 metadata 中，没有统一 evidence lineage。
3. 共现不等于事实；`MemifyEngine.derive_facts()` 的派生结果需要低信任、可回溯、不可冒充用户声明。
4. `consolidate()` 同时包含诊断、提案和应用副作用，缺少明确的 observe/propose/apply 边界。
5. recall 主要返回记忆列表，不能稳定表达匹配模式、证据、冲突、时间状态和预算截断。
6. Profile 多为动态聚合结果，不是版本化、可重建的投影；Mental Model 尚未成为一等领域对象。
7. namespace 在部分图谱、规则、上下文和异步路径中仍依赖调用方正确传递，不能完全作为不可绕过的安全上下文。
8. 当前工程测试较强，但召回质量、token 预算、纠正生效、迁移完整性和用户价值指标仍不足。
9. 既有部分规划文档仍把已实现能力描述为未来能力，需要以本方案和实际代码为准进行事实校准。

### 3.3 对 Hindsight 类设计的吸收边界

吸收的是方法，不是基础设施替换：

| 借鉴点 | CarryMem 的落地方式 |
|---|---|
| retain / recall / reflect 生命周期 | 作为统一语义门面，旧 API 继续兼容 |
| Fact/Experience/Observation/Profile/Mental Model 分层 | SQLite 增量投影表，保留 `memories` 原始证据层 |
| 证据与冲突 | `evidence_links`、ConflictRecord、版本和状态 |
| 任务型召回 | `RecallPlan`、模式、作用域、证据和预算 |
| 预算控制 | retrieval/evidence/output/reflection 分层硬预算 |
| 异步前取和后处理 | 作为可选本地增强，采用 at-least-once + 幂等 |
| reflect | 生成可审计提案，不直接成为事实或规则 |
| 外部服务部署模式 | 不作为核心依赖；本地 SQLite 是默认主路径 |

---

## 4. 统一方法论：四层、三阶段、两种状态

### 4.1 四层记忆对象

#### A. Raw Memory：原始证据载体

表示用户输入、会话内容、导入记录、系统观察或历史兼容数据。它保留原文、来源、时间、namespace、版本和生命周期，不能被派生层静默覆盖。

#### B. Structured Knowledge：结构化知识

包括：

- **Fact**：结构化命题或用户声明；
- **Experience**：带上下文、行动和结果的事件经验；
- **Observation**：特定时间、主体、来源和作用域下的观察；
- **Rule**：系统应该如何行动的受控策略，不等同于事实。

#### C. Cognitive Projection：认知投影

包括：

- **Profile**：面向快速读取和上下文构建的用户状态投影；
- **Mental Model**：带置信度、证据、冲突和版本的假设集合。

#### D. Reflection Process：反思过程

包括反思运行、输入快照、提案、审批、应用结果、失败信息、重试和回滚关系。

### 4.2 三阶段生命周期

```text
retain  = 接收、分类、保留证据
recall  = 按任务检索、裁决可见性、预算化组装
reflect = 分析证据、生成提案、审批后应用
```

#### retain 契约

负责：

- 输入校验、脱敏和作用域确定；
- 分类、幂等检测和原始记忆写入；
- 建立证据引用、版本和冲突候选；
- 记录用户明确陈述与系统推断的来源差异。

不负责：

- 自动把推断升级为用户事实；
- 无依据覆盖现有高置信度记忆；
- 自动改变权限、规则或删除状态。

#### recall 契约

负责：

- 根据任务、query、namespace、时间和实体选择候选；
- 执行关键词、语义、图谱、时间等模式组合；
- 应用冲突、状态、来源和敏感级别过滤；
- 在预算内输出证据化上下文；
- 报告排序来源、截断、降级和不确定性。

不负责：

- 静默改变核心记忆；
- 将推断伪装成用户声明；
- 在 token 不足时无提示丢弃关键冲突或纠正。

#### reflect 契约

负责：

- 分析重复、冲突、过期、使用信号和图谱关系；
- 生成 Fact、Profile、Mental Model、Rule 的候选提案；
- 记录输入快照、算法、证据、置信度和幂等键；
- 支持 inspect、propose、approve/reject、apply、rollback。

默认不负责：

- 物理删除原始证据；
- 自动改变安全边界；
- 自动批准高风险规则；
- 在没有事务、版本和回滚时批量覆盖数据。

### 4.3 两种状态：事实状态与执行状态

每个派生对象同时拥有：

1. **事实状态**：candidate、accepted、rejected、superseded、expired、unsupported；
2. **执行状态**：proposed、approved、applied、rolled_back、failed。

这样可以区分“这个结论是否可信”和“这次反思变更是否已经执行”。

---

## 5. 目标数据架构

### 5.1 总体关系

```text
memories (Raw Memory / compatibility)
        │
        ├── memory_evidence_links ──┬── memory_facts
        │                            ├── memory_experiences
        │                            ├── memory_observations
        │                            ├── memory_profiles
        │                            ├── memory_model_claims
        │                            └── reflection_outputs
        │
        ├── memory_entities / memory_relations
        └── memory_reflection_runs → proposals → approved projections
```

### 5.2 建议新增的逻辑实体

#### Evidence Link

统一表达“派生对象由哪些来源支持或反驳”：

```text
id
namespace
source_memory_key
source_kind
source_snapshot_hash
target_kind
target_id
relation_type
support_weight
created_at
```

关系类型至少包括：

```text
supports / contradicts / derived_from / observed_in / confirmed_by / supersedes
```

#### Fact

```text
id
namespace
subject
predicate
object/value_json
source_kind
status
confidence
valid_from
valid_until
superseded_by
created_at
updated_at
```

用户明确声明、导入事实和系统推断必须通过 `source_kind` 区分。

#### Experience

```text
id
namespace
context_json
trigger_text
action_json
outcome_json
success_status
lesson_text
occurred_at
created_at
updated_at
```

经验是“发生了什么、采取了什么行动、结果如何”，不等同于简单的 session summary。

#### Observation

```text
id
namespace
subject
predicate
value_json
source_kind
source_ref
confidence
observed_at
expires_at
created_at
```

Observation 默认不是永久事实。内部 recall 不应默认每次写入 observation，以避免 SQLite 写放大；优先记录用户可见 recall、明确反馈、任务结果、纠正和关键生命周期事件。

#### Profile

```text
id
namespace
profile_key
value_json
confidence
status
generated_by
profile_version
valid_from
valid_until
created_at
updated_at
```

Profile 是可重建、面向读取的物化投影，不是未经版本控制的“大 JSON”。

#### Mental Model Claim

```text
id
namespace
model_name
claim_type
subject
predicate
object
confidence
status
model_version
valid_from
valid_until
created_at
updated_at
```

Mental Model 表达带证据和冲突的假设集合，不能与 Profile 合并。

#### Reflection Run / Proposal

```text
run_id
namespace
reflection_type
input_cursor
config_snapshot
status
started_at
completed_at
error_text
idempotency_key
```

提案至少包含：

```text
proposal_id
proposal_type
target_id
source_observation_ids
source_evidence_ids
confidence
reasoning
status
approved_by
applied_at
rollback_ref
idempotency_key
```

### 5.3 现有表的定位

- `memories`：继续作为原始证据和 Stable API 兼容层；
- `memory_entities`、`memory_relations`：继续作为图谱投影，但关系必须有 namespace、来源、置信度和删除语义；
- `metadata`：继续兼容历史字段，但不再作为新领域模型的唯一存储；
- `memory_versions`：作为原始记忆与派生投影的版本依据之一；
- FTS5 和向量索引：继续服务 recall，不承担事实状态和审批状态。

---

## 6. 冲突与信任模型

### 6.1 默认优先级

初版建议采用：

```text
用户明确纠正
  > 当前 namespace/项目作用域内的用户明确陈述
  > 有明确来源且仍有效的近期观察
  > 历史观察与已确认经验
  > 系统派生事实
  > 共现、相似度或图谱路径推断
```

该优先级不是简单的 latest-wins。裁决至少综合：

- 来源类型；
- 作用域；
- 用户是否明确纠正；
- 有效时间；
- 证据支持/反驳数量；
- 置信度；
- 是否已确认；
- 是否已 supersede 或撤回；
- 安全和隐私敏感级别。

### 6.2 事实、观察、推断、规则不可混淆

| 类型 | 默认信任 | 可否进入上下文 | 可否改变系统状态 |
|---|---:|---|---|
| 用户事实 | 高，但需带来源 | 可以 | 只能经受控写入 |
| Observation | 中或未知 | 需标明时间和作用域 | 不得直接改变权限/规则 |
| Inference | 低于事实 | 必须显式标记 | 默认不能自动提升 |
| Rule | 取决于审批级别 | 可影响行为，但结构化注入 | 高风险规则必须人工批准 |

### 6.3 冲突记录

任何无法确定裁决的冲突，都应形成 ConflictRecord，而不是静默选择一条：

```text
conflict_id
namespace
subject/key
candidate_ids
conflict_type
resolution_status
resolution_policy
selected_id
reasoning
created_at
resolved_at
```

高风险主题包括安全策略、隐私、删除、凭证、权限、外部通信和规则覆盖。这些主题默认 fail-closed 或要求用户确认。

### 6.4 派生事实边界

`MemifyEngine.derive_facts()` 产生的是推断候选，不是用户事实。必须：

- 保留 source memory keys 和快照哈希；
- 标记 `derived/inferred`；
- 采用幂等键；
- 限制参与规则注入和高信任回答；
- 支持源记忆删除后的失效重算；
- 在召回中区分原始事实、派生事实和关系候选。

---

## 7. Task-oriented Recall 与预算方法

### 7.1 RecallPlan

建议增加内部统一计划对象，不立即替换旧 `recall_memories()`：

```text
RecallPlan(
    query,
    task,
    namespace,
    modes,
    max_results,
    retrieval_budget,
    evidence_budget,
    output_budget,
    include_evidence,
    include_superseded,
    conflict_policy,
    sensitivity_policy,
)
```

现有 API 可先转换为默认 RecallPlan：

- `recall_memories()`：兼容列表结果；
- `recall_multi_mode()`：显式 modes；
- `build_context()`：增加 output budget 和 evidence policy；
- 新实验 API：返回 RecallResult 和 explanation。

### 7.2 召回结果

统一内部结果至少包含：

```text
memory_id
match_type
score
source
created_at
validity_status
evidence_ids
conflict_status
namespace
truncated_reason
```

对外旧返回结构保持兼容；新解释接口可以返回完整结果。

### 7.3 分层预算

```text
request budget
├── retrieval budget       候选数量、图遍历、检索耗时
├── evidence budget        证据展开数量和字符/token
├── reflection budget      反思输入、批次、CPU/耗时
└── output budget          最终 prompt/context
```

硬约束：

- 最终输出不得超预算；
- 预算估算必须覆盖模板、系统提示、用户输入、工具说明、会话摘要和记忆；
- correction 和高信任安全事实不得因普通截断优先丢失；
- 截断、降级、无答案和冲突必须可观测并可解释；
- 估算 tokenizer 与真实 tokenizer 的偏差需要定期校准。

### 7.4 任务模式

初期支持有限且可解释的任务模式：

```text
preference_following
correction_resolution
project_context
fact_lookup
timeline_review
rule_application
conflict_explanation
```

不允许仅凭 query 自动扩大 namespace、图谱 hop 或敏感级别。

---

## 8. Reflect 与 Consolidation 演进

### 8.1 三阶段执行边界

```text
inspect  → 只读分析：重复、冲突、衰减、图谱变化
propose  → 生成候选：Fact/Profile/Rule/Graph 变更提案
apply    → 只应用明确批准、可验证、可回滚的提案
```

新 `reflect()` 默认等价于安全的 inspect/propose，不默认产生破坏性写入。旧 `consolidate()` 保持签名和返回结构不变。

### 8.2 现有能力映射

| 现有能力 | 目标映射 | 约束 |
|---|---|---|
| `consolidate()` | reflect 编排入口 | 拆分只读、提案、应用 |
| `consolidation.py` P0/P1/P2 | reflection strategies | 保留算法边界，不与图谱 SQL 合并 |
| `MemifyEngine.derive_facts()` | Fact candidate strategy | 不得冒充用户事实 |
| `reinforce_edges()` | Graph/Mental Model projection | 有上限、幂等、可解释 |
| `auto_decay()` | lifecycle proposal | 不直接物理删除高价值事实 |
| Rule promotion pipeline | Rule proposal/apply | 高风险规则必须人工批准 |
| SemanticAggregator | aggregation proposal | 保留 source ids，区分支持和反驳 |

### 8.3 幂等与恢复

每次反思必须记录：

- namespace；
- 输入 cursor 或 snapshot hash；
- 配置快照；
- 算法版本；
- proposal idempotency key；
- 输出对象；
- 成功/失败/重试；
- 应用事务和 rollback ref。

后台任务承诺：

> **at-least-once + 幂等执行 + 可重试；当前不承诺 exactly-once。**

### 8.4 自动应用策略

初期采用“低风险可自动，高风险需确认”：

可考虑自动应用：

- 已有强证据的重复去重候选；
- 不改变语义的索引、摘要或缓存投影；
- 已确认事实的非破坏性 Profile 重建；
- 明确过期且不再参与 recall 的低风险投影。

必须确认：

- 覆盖用户明确偏好；
- 规则晋升、forbid/always/override；
- 删除、批量 forget、密钥或权限变化；
- 跨 namespace；
- 高敏感属性推断；
- 外部调用、导出和系统 prompt 高影响注入。

---

## 9. API、入口与迁移策略

### 9.1 API 演进

保留：

```text
classify_and_remember
recall_memories
forget_memory
get_memory_profile
whoami
build_context
build_system_prompt
consolidate_memories
```

新增能力先以 additive/experimental 形式出现：

```text
retain
recall
reflect
record_observation
list_observations
list_facts
list_experiences
get_profile_snapshot
get_mental_model
run_reflection
get_reflection_run
explain_memory
```

新入口第一阶段复用现有实现，不改变旧参数、返回结构和指标语义：

```text
retain  → classify_and_remember
recall  → recall_memories
reflect → consolidate(dry_run/propose-safe path)
```

### 9.2 Python、CLI、MCP 一致性

P0 核心能力统一为：

```text
remember / recall / explain / forget / whoami / build_context / export / import
```

三种入口至少统一：

- 参数语义；
- namespace 行为；
- 成功/失败语义；
- 核心输出字段；
- 解释和来源字段；
- 删除和回滚语义。

高级图谱、Memify、维护工具可以继续作为高级能力，不要求第一阶段完全功能对齐。

### 9.3 SQLite 迁移

只做 additive migration：

- 不重命名或删除 `memories` 和旧字段；
- 新表可为空；
- 旧数据库升级后仍能使用旧 API；
- 使用 migration ledger 记录 migration_id、时间和 checksum；
- 迁移失败必须阻止 ready，不得只记录 warning 后继续；
- 大型 backfill 采用惰性投影、分页、cursor、dry-run 和可恢复任务；
- 迁移前创建可验证备份；
- 支持空库、最新库、历史库、重复执行和中断恢复测试。

建议的未来表族：

```text
memory_evidence_links
memory_facts
memory_experiences
memory_observations
memory_profiles
memory_model_claims
memory_conflicts
memory_reflection_runs
memory_reflection_outputs
```

### 9.4 删除和遗忘

删除必须区分：

1. 逻辑删除：不再参与 recall/prompt；
2. 物理删除：从主表、FTS、vector 等删除；
3. 派生删除：处理 Fact、Profile、Model、Graph、Rule proposal；
4. 副本删除：处理版本、cache、backup、pack、audit 引用。

删除源记忆后，派生对象默认标记 `unsupported/stale` 并重算；彻底删除由用户明确要求并经过审计。不能留下无法追溯来源的高信任事实。

---

## 10. 安全与隐私边界

### 10.1 Namespace 是安全上下文

namespace 必须从认证请求上下文或实例安全上下文获得，不能只依赖普通字符串参数。底层 API 默认拒绝 `namespace=None`；跨 namespace 查询必须有明确 ADMIN 权限。

覆盖范围：

```text
memories / evidence / observations / facts / profiles / models
rules / graph / vectors / cache / async jobs / exports / backups / audit
```

### 10.2 证据与导出

- evidence、原始消息、审计详情默认加密或脱敏；
- metrics 禁止包含 query、memory content、用户 ID 和完整路径；
- `get_system_prompt` 视为高敏感聚合出口；
- 导出采用 allowlist；
- embedding/LLM 外发必须是显式可选能力，核心路径默认本地；
- 解密失败必须 fail-closed，不得把密文继续当内容传播；
- `.carry` pack 应使用认证加密，而非仅依赖 checksum。

### 10.3 规则与提示注入

- 规则数据与执行指令分离；
- action 只能映射到预定义动作；
- 不允许规则改变 namespace、权限、删除、安全策略；
- `auto_accept=True` 不作为生产默认；
- 高风险规则必须人工批准；
- 记忆注入 prompt 时使用明确的不可信数据边界；
- 测试多语言、Unicode 同形、编码变形、嵌套模板和间接指令。

### 10.4 审计

审计至少记录：

```text
主体、namespace、动作、资源、授权结果、proposal/run id、输入哈希、输出分类、correlation id
```

高风险操作包括导出、导入、删除、规则晋升、反思应用、跨 namespace、pack 解密和密钥轮换。审计落盘失败时，高风险操作必须阻断或显式进入 fail-closed 状态。

---

## 11. 测试、Benchmark 与发布门禁

### 11.1 测试金字塔

```text
静态/安全/类型
  → 单元与纯函数
  → 核心集成与 SQLite migration
  → 异步/并发/恢复
  → 真实 HTTP/MCP
  → 发布前真实用户 E2E
```

覆盖率 80% 保持为底线，但不能替代领域质量指标。

### 11.2 必须增加的 E2E 用户路径

1. `retain → recall → build_context`：相关内容进入上下文，不相关内容不进入。
2. `retain → correction → recall`：纠正优先，旧结论不再作为唯一结论。
3. `retain → conflict → reflect proposal → approve/reject`：冲突可见，提案可审计。
4. `reflect apply → rollback → recall`：应用和回滚结果正确。
5. `namespace A/B`：memory、graph、evidence、rule、export 全链路不泄漏。
6. `backup → migration → restore → recall`：内容、版本、关系和语义保持。
7. `async reflect → restart → resume`：任务至少一次执行但不重复生成结果。
8. `budget exhausted`：确定性截断，关键纠正和安全事实不丢失。
9. `HTTP/MCP → metrics`：真实请求导致真实 collector 变化。
10. 解密失败、审计失败、迁移失败：服务不进入 ready，数据可恢复。

### 11.3 Recall 质量指标

在固定、版本化的离线数据集上建立基线：

| 指标 | 初始建议 |
|---|---:|
| Recall@5 | ≥ 0.90 |
| Recall@10 | ≥ 0.95 |
| Precision@5 | ≥ 0.80 |
| MRR@10 | ≥ 0.85 |
| correction 优先率 | ≥ 99% |
| namespace 泄漏率 | 0 |
| must-not-return 命中率 | 0 |
| 重复结果率 | 0 |
| 预算超限率 | 0 |

阈值需以真实基线和数据集版本校准，但任何 namespace 泄漏、数据损坏、预算超限和不可解释覆盖都属于阻断问题。

### 11.4 SLO 与性能

固定硬件和数据规模下，建议初始目标：

- recall P95 ≤ 200ms，P99 ≤ 500ms；
- classify/retain P95 ≤ 100ms，P99 ≤ 200ms；
- migration 失败率为 0；
- backup/restore 校验失败率为 0；
- 异步取消导致的连接泄漏为 0；
- P99 回归超过 15% 阻断；
- 性能 benchmark 无法执行不得以 advisory 或 `|| true` 掩盖。

### 11.5 可观测性

新增指标必须有真实生产写入路径并由 E2E 验证：

```text
retain/recall/reflect 请求数与错误数
recall 空结果、预算截断、冲突数
reflection proposal/apply/reject/rollback
migration、backup、restore
async queued/succeeded/failed/retried/cancelled
namespace denied、authorization failure
```

区分：

```text
user operation / internal operation / background job
```

避免把 query、memory id、用户输入和 namespace 原文作为高基数 label。

---

## 12. 分阶段路线图

### Phase 0：契约和基线（先行）

交付：

- retain/recall/reflect 责任边界；
- Evidence、Observation、Conflict、Proposal 类型契约；
- 冲突优先级与自动应用级别；
- token budget 语义；
- API 行为基线和指标基线；
- 文档事实校准。

出口：Gate 0 通过，项目负责人批准进入实现。

### Phase 1：Provenance 基础

交付：

- evidence link；
- source kind、snapshot hash、derived 状态；
- 删除/失效策略；
- 现有 Memify、SemanticAggregator、版本链接入来源关系。

出口：任意派生对象可追溯至原始来源。

### Phase 2：Observation 与 Conflict

交付：

- 关键行为 Observation；
- ConflictRecord；
- correction/作用域/时间优先级；
- recall 结果解释和冲突显示。

出口：冲突不再静默覆盖，用户可查看原因。

### Phase 3：Fact、Experience、Profile

交付：

- Fact/Experience 显式投影；
- `get_memory_profile()` 的兼容投影；
- 可重建 Profile；
- 旧数据 lazy backfill 和显式 backfill。

出口：核心黄金路径行为保持兼容，投影可重建。

### Phase 4：Reflect Proposal

交付：

- reflection run；
- inspect/propose/apply；
- 幂等、审批、回滚、重试；
- Memify 和 consolidation 作为独立策略接入。

出口：反思不会无审计地直接覆盖原始记忆。

### Phase 5：Task Recall 与预算

交付：

- RecallPlan；
- 任务模式；
- 分层预算；
- 解释卡片；
- 真实 tokenizer 校准和召回评估集。

出口：最终上下文预算硬约束，召回质量可量化。

### Phase 6：入口产品化与迁移

交付：

- Python/CLI/MCP P0 入口统一；
- migration ledger；
- migration dry-run/recovery；
- 发布 runbook、告警和回滚演练。

出口：发布前完整真实用户 E2E、迁移演练和安全门禁通过。

### 可延后事项

- TUI 全量能力对齐；
- 大型语义模型和外部 LLM；
- 复杂图谱推理和全自动 consolidation；
- 外部知识库、多适配器扩张；
- 继续增加 MCP 工具数量。

---

## 13. 多角色共识评审结论

### 13.1 共同认可

产品、架构、安全、测试、开发和 DevOps 角色共同认可：

1. 保留 SQLite-first、本地优先和核心无外部服务依赖；
2. 保留 `memories` 作为稳定原始证据层；
3. Fact、Experience、Observation、Profile、Mental Model 需要显式领域边界；
4. 所有派生结论必须有 provenance；
5. `reflect` 默认先提案，低风险自动、高风险确认；
6. Stable API 采用增量兼容，不做一次性破坏性重构；
7. 迁移、异步、删除、预算、metrics 和 E2E 必须成为正式契约；
8. 任何 namespace 泄漏、静默数据丢失、事实污染、不可回滚和预算失控都不可接受。

### 13.2 主要冲突与处理

| 冲突 | 解决方案 |
|---|---|
| 自动变聪明 vs 用户控制 | 低风险自动应用，高风险提案确认 |
| latest-wins vs 证据优先 | 来源、作用域、纠正、时间、置信度综合裁决 |
| 召回完整性 vs 延迟/Token | 分层硬预算，关键纠正和安全事实优先 |
| 证据完整性 vs 隐私 | evidence 分级、脱敏、加密、最小化留存 |
| 原生异步 vs 维护复杂度 | 保持兼容 facade，后台任务 at-least-once + 幂等 |
| 快速 schema 扩展 vs 数据安全 | additive、事务、ledger、失败停止、备份恢复 |
| 指标全面 vs 高基数泄漏 | 低基数标签，内容只做 hash 或完全不记录 |

### 13.3 需要项目负责人拍板

在实现前必须确认：

1. reflect 自动化级别；
2. evidence 默认保留、导出和删除策略；
3. Observation 是否进入长期 recall、默认 TTL；
4. 冲突优先级是否采用本文默认顺序；
5. token budget 是否采用 retrieval/evidence/reflection/output 四层；
6. 异步是否接受 at-least-once + 幂等；
7. SQLite 跨版本迁移承诺范围；
8. audit/metrics 的隐私字段与保留周期。

---

## 14. 批准门槛

### Gate 0：方案批准

必须明确：

- 生命周期契约；
- 领域对象；
- 冲突政策；
- 自动应用策略；
- 删除语义；
- token budget；
- 异步一致性；
- 旧 API 兼容策略。

### Gate 1：数据契约

必须能回答：

> 任意一条最终记忆或 Profile 结论，能否追溯到来源、证据、观察和反思运行？

### Gate 2：迁移

必须通过空库、最新库、历史库、重复执行、中断恢复、备份恢复、FTS/Graph/Vector 一致性和 namespace 测试。

### Gate 3：安全

必须通过 evidence 脱敏、namespace 越权、规则注入、加密 fail-closed、删除级联、审计落盘和异步 namespace 测试。

### Gate 4：真实用户 E2E

必须通过：

```text
retain → recall
retain → conflict → reflect proposal → approve/reject
reflect → rollback
backup → migration → restore → recall
async reflect → restart → resume
budget exhausted → deterministic fallback
```

### Gate 5：可观测性

所有新增指标必须有真实写入点、exporter 读取点和 E2E 证据。

### Gate 6：发布

全量质量门禁、关键 E2E、安全扫描、迁移演练、备份恢复演练、性能/token 基线、文档/runbook 和 feature flag 关闭路径全部通过。

---

## 15. 当前决议

本方案结论为：

> **Gate 0 已批准（2026-09-28）：8 项决策按契约文档建议默认执行，Phase 1 Provenance 基础实现已授权。**

按生命周期推进：

- Phase 1（当前）：evidence links + source_kind + snapshot hash + unsupported 级联，现有 Memify/SemanticAggregator 接入 provenance；
- Phase 2+：Observation/Conflict → Fact/Experience/Profile → Reflect Proposal → Task Recall/预算 → 入口产品化，逐 Gate 推进；
- 仍然禁止：跨阶段实现（Phase 2+ 内容提前做）、全量 backfill、Stable API 返回结构破坏、B2 版本发布动作（tag/Release/PyPI）。

相关既有文档：

- [`docs/design/METHODOLOGY.md`](METHODOLOGY.md)
- [`docs/CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md`](../CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md)
- [`docs/API_STABILITY.md`](../API_STABILITY.md)
- [`docs/RELEASE_RUNBOOK.md`](../RELEASE_RUNBOOK.md)
- [`docs/architecture/decisions/ADR-010-memify-dynamic-refinement.md`](../architecture/decisions/ADR-010-memify-dynamic-refinement.md)
- [`docs/architecture/decisions/ADR-009-async-pipeline.md`](../architecture/decisions/ADR-009-async-pipeline.md)

---

## 16. Phase 0 配套契约文档（已就位，待 Gate 0 审批）

本方案 §4/§5/§6/§7/§8/§11 的契约细节已由以下文档承接；字段定义、状态机、不变量（INV-*）与默认值以这些文档为准：

| 文档 | 承接内容 |
|---|---|
| [`MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md`](MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md) | retain/recall/reflect 责任边界、两种状态、22 条生命周期不变量、fail-closed 处置 |
| [`MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md`](MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md) | Evidence Link 与 Observation 字段契约、写入准入白名单、TTL、metadata 兼容映射 |
| [`MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md`](MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md) | 优先级链（P1-P6）、九因素裁决、ConflictRecord 状态机、高风险 fail-closed 清单 |
| [`MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md`](MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md) | Run/Proposal 状态机、幂等键规范、风险分级审批、apply/rollback 语义、现有能力迁移映射 |
| [`MEMORY_EVOLUTION_BUDGET.md`](MEMORY_EVOLUTION_BUDGET.md) | 四层预算、RecallPlan/RecallResult 契约、确定性截断顺序与原因码、token 估算校准 |
| [`MEMORY_EVOLUTION_OBSERVABILITY.md`](MEMORY_EVOLUTION_OBSERVABILITY.md) | 新增指标权威表（产生者/触发条件/标签）、语义边界、隐私约束、SLO 扩展、告警草案 |
| [`../testing/MEMORY_EVOLUTION_TEST_PLAN.md`](../testing/MEMORY_EVOLUTION_TEST_PLAN.md) | 全部 INV→测试映射、E2E-1~10、MIG-1~9、SEC-1~8、召回质量阈值、Gate 对齐 |
| [`../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md`](../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md) | 迁移操作流程、四类故障恢复、发布前演练要求 |
| [`../architecture/decisions/ADR-014-memory-lifecycle-contract.md`](../architecture/decisions/ADR-014-memory-lifecycle-contract.md) | 生命周期契约决策（Proposed） |
| [`../architecture/decisions/ADR-015-evidence-observation-model.md`](../architecture/decisions/ADR-015-evidence-observation-model.md) | Evidence/Observation 模型决策（Proposed） |
| [`../architecture/decisions/ADR-016-reflection-proposal-lifecycle.md`](../architecture/decisions/ADR-016-reflection-proposal-lifecycle.md) | Reflection 审批分级决策（Proposed） |
| [`../architecture/decisions/ADR-017-conflict-resolution-policy.md`](../architecture/decisions/ADR-017-conflict-resolution-policy.md) | 冲突裁决策略决策（Proposed） |
| [`../architecture/decisions/ADR-018-memory-evolution-migration.md`](../architecture/decisions/ADR-018-memory-evolution-migration.md) | 迁移策略决策（Proposed） |
| [`PHASE1_PROVENANCE_READINESS.md`](PHASE1_PROVENANCE_READINESS.md) | Gate 0 批准后的实现启动检查单 |

Gate 0 审批顺序建议：先逐份审批上表契约文档与 8 项决策（共识文档 §4），再按 [`PHASE1_PROVENANCE_READINESS.md`](PHASE1_PROVENANCE_READINESS.md) §2 启动检查后进入 Phase 1。
