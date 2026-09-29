# 记忆生命周期契约：retain / recall / reflect

> **版本**：v0.1-draft
> **日期**：2026-09-28
> **状态**：Phase 0 契约草案，待 Gate 0 批准
> **权威关系**：本文细化并落实 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §4 的三阶段契约；细节以本文为准，总纲以主方案为准。两者冲突时，以项目负责人批准版本为准。
> **实现边界**：Gate 0 批准前，本文不触发任何代码修改。

---

## 1. 目的与范围

本文定义 CarryMem 记忆系统的三阶段生命周期契约——`retain`（保留）、`recall`（召回）、`reflect`（反思）：

- 每个阶段的**输入、输出、职责与非职责**；
- 每条契约对应的**可测试不变量**（INV 编号，供[测试计划](../testing/MEMORY_EVOLUTION_TEST_PLAN.md)逐条映射）；
- 契约违约时的**fail-closed 行为**；
- 与现有 Stable API 的**委托映射**（新入口复用旧实现，避免双轨漂移）。

不在范围内：领域对象的字段级 schema（见 [Evidence/Observation 契约](MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md)）、冲突裁决细则（见[冲突裁决契约](MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md)）、预算数值（见[预算契约](MEMORY_EVOLUTION_BUDGET.md)）。

---

## 2. 两种状态的分离

每个记忆对象同时拥有两个独立正交的状态维度，禁止混用：

### 2.1 事实状态（这个结论可信吗）

| 状态 | 含义 | 进入条件 | 退出条件 |
|---|---|---|---|
| `candidate` | 候选，未经确认 | 任何派生/推断产出的初始状态 | 被确认、被否决或过期 |
| `accepted` | 已确认可信 | 用户确认，或低风险自动应用 | 被 supersede / 被纠正 |
| `rejected` | 已否决 | 用户拒绝或裁决否决 | 终态（保留记录供审计） |
| `superseded` | 已被更新版本取代 | 新事实/纠正生效 | 终态 |
| `expired` | 已过有效期 | `valid_until` 已过且未续期 | 可被新观察重新激活为 candidate |
| `unsupported` | 失去来源支撑 | 来源记忆被删除/撤销且无可替代证据 | 重新获得证据，或被清理 |

### 2.2 执行状态（这次变更执行了吗）

| 状态 | 含义 | 允许的后继 |
|---|---|---|
| `proposed` | 已生成提案，未审批 | approved / rejected / failed / expired |
| `approved` | 已批准，未执行 | applied / failed |
| `applied` | 已生效 | rolled_back / superseded |
| `rolled_back` | 已回滚 | 终态（可重新提案） |
| `failed` | 执行失败 | 重试（新 proposal 或同 idempotency key 重放） |

**不变量 INV-S1**：事实状态与执行状态必须分别存储、分别查询；任何接口不得用执行状态回答"这条结论可信吗"。

**不变量 INV-S2**：`candidate` 事实不得进入默认高信任路径（系统 prompt 注入、规则晋升、高置信回答），除非显式声明降级策略并留痕。

---

## 3. retain 契约

### 3.1 定义

`retain` 是记忆系统的唯一合法写入入口语义：接收原始输入，产出持久化的原始证据，并为其建立可追溯的元数据基础。

### 3.2 输入

```text
message/content        原始文本（必填，非空）
context                可选上下文（会话、任务、来源渠道）
language               可选语言标记
session_id             可选会话标识（决定 session/permanent 层）
force_type             可选强制分类
user_id                可选用户标识
namespace              安全上下文（由实例或认证上下文决定，不可由普通参数绕过）
```

### 3.3 处理步骤（有序）

1. **输入校验**：空输入、超长、非法类型拒绝并计入 metrics（错误路径也计数）。
2. **脱敏**：按敏感级别策略处理密钥、凭证类内容（沿用现有 sanitizer 语义）。
3. **指代消解**：仅使用未埋点的内部读取路径（保持 v0.11.x metrics 语义边界）。
4. **分类**：零 LLM 规则分类为主；LLM 仅为显式可选增强。
5. **幂等检测**：内容哈希命中已有记忆时，去重或更新 access 信号，不产生重复行。
6. **写入原始记忆**：`memories` 表写入，含 namespace、版本、来源类型。
7. **建立来源标注**：记录 `source_kind`（user_statement / correction / import / system_observation / inference），用户明确陈述与系统推断从写入起就不可混淆。
8. **冲突候选登记**：与现有记忆语义冲突时，登记冲突候选（见冲突契约），不静默覆盖。
9. **后处理**：图谱实体/关系抽取、规则候选生成、metrics 记账。

### 3.4 职责

- 完整保留原始输入（脱敏后），作为后续一切派生的证据基础；
- 区分用户明确陈述与系统推断（`source_kind`）；
- 检测并登记冲突候选；
- 幂等处理重复输入；
- 全程可观测（成功与失败路径都有 metrics）。

### 3.5 非职责（禁止行为）

- 不自动把系统推断升级为用户事实（`source_kind` 不可被派生路径篡改）；
- 不无依据覆盖现有高置信度记忆（覆盖必须走冲突裁决或用户纠正路径）；
- 不改变 namespace、权限、规则状态或删除状态；
- 不因分类失败而丢弃原始输入的审计记录（降级存储需标注原因）。

### 3.6 不变量

| 编号 | 不变量 | 违约后果 |
|---|---|---|
| INV-R1 | 任何成功 retain 的输入，都能通过 API 检索到原始内容（除非用户显式删除） | 数据丢失，阻断级 |
| INV-R2 | 派生路径产出的记忆 `source_kind` 必须为 inference/observation 类，不得伪装为 user_statement | 事实污染，阻断级 |
| INV-R3 | 相同内容重复 retain 不产生第二行（幂等键命中） | 数据膨胀 |
| INV-R4 | retain 失败（异常/校验拒绝）时必须计入错误 metrics，且不留下半写入状态 | 假观测 |
| INV-R5 | 冲突候选登记不得静默丢失：登记失败时 retain 必须整体失败或显式降级并留痕 | 冲突静默覆盖 |
| INV-R6 | namespace 由安全上下文决定；`namespace=None` 的底层写入必须被拒绝 | 跨域泄漏，阻断级 |

### 3.7 与现有 API 的映射

```text
retain(...)          → 委托 classify_and_remember（签名、返回结构、metrics 语义均不变）
declare(...)         → 保留，等价于 retain 且 source_kind=user_statement
```

旧 API 是 retain 的第一实现载体；新 `retain()` 仅是语义别名 + 来源标注增强，additive 引入。

---

## 4. recall 契约

### 4.1 定义

`recall` 是记忆系统唯一合法的读取出口语义：按任务需求检索候选，裁决可见性，在预算内组装证据化上下文。

### 4.2 输入

```text
query                  检索文本（可为空：纯过滤召回）
task                   任务模式（preference_following / correction_resolution / ...）
namespace              安全上下文（必经认证边界）
modes                  检索模式组合（fts/vector/graph/time/semantic）
max_results            结果上限
budget                 预算对象（见预算契约）
include_evidence       是否携带证据
include_superseded     是否包含已被取代版本（默认 False）
conflict_policy        冲突呈现策略（hide/show_top/always）
sensitivity_policy     敏感级别过滤
filters                兼容旧版过滤参数
```

### 4.3 处理步骤（有序）

1. **输入防护**：注入检测（现有 `detect_sql_injection` 边界保留在最前）。
2. **计划构建**：旧 API 参数 → 内部 `RecallPlan`（默认值见预算契约）。
3. **多路候选**：FTS → 向量（如启用）→ 扩展 → 语义回退（现有 RecallEngine 顺序不变）。
4. **可见性裁决**：过滤 superseded/expired/unsupported/敏感级别不符/跨 namespace。
5. **冲突裁决呈现**：按 conflict_policy 决定冲突组的呈现方式，不静默择一。
6. **证据展开**：include_evidence 时按 evidence budget 附加来源链接。
7. **预算约束**：按预算契约截断，截断必须留痕（原因码）。
8. **结果包装**：旧 API 返回兼容列表结构；新实验 API 返回带解释的 `RecallResult`。
9. **观测记账**：仅用户发起的 recall 计入 `recall` metrics；内部簿记读取走未埋点路径。

### 4.4 职责

- 返回与任务相关、作用域合法、状态有效的候选；
- 冲突、截断、降级、空结果可解释；
- correction 与高信任安全事实在预算内优先保留；
- 更新 access 信号（可关闭）。

### 4.5 非职责（禁止行为）

- 不静默修改任何记忆（包括"顺带"更新置信度/状态）；
- 不把推断结果伪装成用户陈述返回；
- 不因预算不足无提示丢弃 correction 或安全事实（要么保留并说明，要么整体降级）；
- 不自动扩大 namespace、图谱跳数或敏感级别范围。

### 4.6 不变量

| 编号 | 不变量 | 违约后果 |
|---|---|---|
| INV-C1 | 返回结果中不出现调用方无权访问的 namespace 内容 | 泄漏，阻断级 |
| INV-C2 | `include_superseded=False` 时，任何被取代版本不得出现 | 陈旧事实误导 |
| INV-C3 | correction 类记忆在与旧偏好冲突时优先返回（correction_resolution 任务下 100%） | 纠正失效，阻断级 |
| INV-C4 | 最终输出不超过 output budget；每次截断带原因码 | 预算失控 |
| INV-C5 | 内部簿记读取不计入用户 recall metrics（保持 0.11.x 守卫语义） | 指标失真 |
| INV-C6 | 空结果与"因冲突不可回答"必须可区分（原因码/状态字段） | 假阴性 |
| INV-C7 | 恶意 query 在所有路径（FTS/LIKE/向量/语义回退）上都不会触发 SQL 执行 | 注入，阻断级 |

### 4.7 与现有 API 的映射

```text
recall(...)            → 新实验入口：返回 RecallResult + explanation
recall_memories(...)   → 现有 Stable API：内部转默认 RecallPlan，返回结构不变
recall_multi_mode(...) → 显式 modes 的包装
build_context(...)     → 增加 output budget 与 evidence policy，默认行为兼容
recall_by_entity / recall_by_relation / recall_graph / recall_by_time
                        → 保留，作为特定模式的便捷入口，复用统一可见性裁决
```

---

## 5. reflect 契约

### 5.1 定义

`reflect` 是记忆系统唯一合法的派生与维护入口语义：分析证据，产出可审计提案，审批后受控应用。

### 5.2 三阶段边界

```text
inspect  → 只读分析：重复、冲突、衰减、图谱变化、使用信号
            副作用仅限 metrics 与分析缓存；不写任何业务表
propose  → 生成提案：Fact/Profile/MentalModel/Rule/Graph 变更候选
            写入 proposal 记录与幂等键；不改动业务对象本身
apply    → 受控应用：仅应用 approved 且通过校验的提案
            单提案单事务，写 rollback_ref；失败可重试不重复
```

### 5.3 职责

- 生成带来源、置信度、推理说明、幂等键的提案；
- 区分低风险（可自动应用）与高风险（必须确认）提案；
- 应用时保证事务性、幂等性与可回滚；
- 失败可恢复（at-least-once + 幂等执行）。

### 5.4 非职责（禁止行为）

- 不物理删除原始证据；
- 不改变 namespace、权限、删除策略、安全策略；
- 不自动批准高风险提案（规则晋升 forbid/always/override、跨 namespace、批量删除等）;
- 无事务、无版本、无回滚保障时执行批量覆盖。

### 5.5 不变量

| 编号 | 不变量 | 违约后果 |
|---|---|---|
| INV-F1 | 任何派生对象都能通过 evidence link 追溯到至少一个原始来源 | 无源事实，阻断级 |
| INV-F2 | 同一幂等键的提案重复执行不产生第二个派生对象 | 数据膨胀/重复污染 |
| INV-F3 | apply 失败时业务状态保持不变（事务回滚），失败计入 metrics | 半应用状态 |
| INV-F4 | rollback 后，被应用的变更对 recall 不再可见 | 回滚失效 |
| INV-F5 | 高风险提案在没有显式批准记录时不得进入 applied | 越权变更，阻断级 |
| INV-F6 | 反思运行崩溃后重启，可从中断点恢复且不重复产出 | 恢复失效 |
| INV-F7 | inspect 不产生任何业务表写入 | 副作用失控 |

### 5.6 与现有 API 的映射

```text
reflect(...)                → 新实验入口：默认 inspect+propose，不产生破坏性写入
consolidate_memories(...)   → Stable API：签名与返回结构不变，内部逐步改造为 reflect 编排
run_reflection(...)         → 显式运行反思策略（Phase 4 交付）
get_reflection_run(...)     → 查询运行状态与提案
```

现有 `MemifyEngine.derive_facts()`、`reinforce_edges()`、`auto_decay()` 与 `SemanticAggregator` 的产出一律降格为 `candidate` 提案，接入 provenance（Phase 1 起逐个迁移）。

---

## 6. 契约违约的统一处置

1. **阻断级违约**（INV-R1/R2/R6、INV-C1/C3/C7、INV-F1/F5）：触发所在 Gate 的失败，禁止发布；修复前相关功能保持关闭（feature flag off）。
2. **可降级违约**：允许显式降级（如跳过证据展开），但降级必须留痕（原因码 + metrics），禁止静默。
3. **fail-closed 项**：解密失败、审计落盘失败、迁移关键失败——服务不得进入 ready（沿用项目既有原则）。

---

## 7. 与 Gate 0 的关系

本文与以下文档共同构成 Gate 0 审批材料：

- [Evidence/Observation 模型契约](MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md)
- [冲突裁决契约](MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md)
- [Reflection Proposal 生命周期契约](MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md)
- [分层预算契约](MEMORY_EVOLUTION_BUDGET.md)
- [可观测性规范](MEMORY_EVOLUTION_OBSERVABILITY.md)
- [记忆演进测试计划](../testing/MEMORY_EVOLUTION_TEST_PLAN.md)
- [SQLite 迁移与恢复 Runbook](../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md)
- [ADR-014 ~ ADR-018](../architecture/decisions/ADR-014-memory-lifecycle-contract.md)

Gate 0 通过标准：本文全部不变量被测试计划覆盖且实现方案可行，8 项待拍板决策全部明确。
