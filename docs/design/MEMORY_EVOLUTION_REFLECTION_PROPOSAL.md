# Reflection Proposal 生命周期契约

> **版本**：v0.1-draft
> **日期**：2026-09-28
> **状态**：Phase 0 契约草案，待 Gate 0 批准（含待拍板决策 D1、D6）
> **权威关系**：细化 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §8；状态机与幂等规范以本文为准。
> **实现边界**：Gate 0 批准前不修改 `consolidation.py`、`memify.py` 或规则晋升代码。

---

## 1. 目的

当前 `consolidate_memories()` 与 `MemifyEngine` 把诊断、提案和应用副作用混在一个动作里；`derive_facts()` 的派生结果直接进入存储，无来源快照、无幂等键、无审批门槛。本文把反思改造为可恢复、可幂等、可审计的提案生命周期。

总原则：

> **反思只产出提案；应用只执行明确批准且可回滚的提案；后台执行承诺 at-least-once + 幂等，不承诺 exactly-once。**

---

## 2. Reflection Run 模型

```text
memory_reflection_runs
─────────────────────────────────────────────
run_id            TEXT PK        运行唯一标识（UUIDv7）
namespace         TEXT NOT NULL  作用域
reflection_type   TEXT NOT NULL  dedup / conflict_scan / decay / fact_derivation /
                                 profile_rebuild / aggregation / graph_maintenance
strategy_version  TEXT NOT NULL  策略算法版本（用于重算与审计）
input_cursor      TEXT           输入游标（分页/增量断点）
input_snapshot    TEXT NOT NULL  输入集快照哈希（决定性重放依据）
config_snapshot   TEXT NOT NULL  配置 JSON 快照
status            TEXT NOT NULL  running / completed / failed / cancelled / interrupted
started_at        TEXT NOT NULL
completed_at      TEXT
error_text        TEXT           失败摘要（不含敏感原文）
idempotency_key   TEXT NOT NULL  UNIQUE(namespace, reflection_type, input_snapshot, config_hash)
```

### 2.1 Run 状态机

```text
running ──正常结束──→ completed
   │──异常──────→ failed（可重试：新 run 或同 idempotency_key 重放）
   │──主动取消──→ cancelled
   └──进程崩溃──→ interrupted（重启后由恢复器接管）
```

不变量：

| 编号 | 不变量 |
|---|---|
| INV-RR1 | 同 idempotency_key 的 run 不重复产出派生对象：重放时先检查该 run 已产出的 proposal，已存在的直接复用 |
| INV-RR2 | `interrupted` 的 run 重启后必须能从 `input_cursor` 恢复，且已完成部分的产出保持有效 |
| INV-RR3 | run 失败不污染业务表：run 记录与 proposal 记录允许存在，但业务对象未被改动 |

---

## 3. Proposal 模型

```text
memory_reflection_outputs
─────────────────────────────────────────────
proposal_id           TEXT PK
run_id                TEXT NOT NULL   → memory_reflection_runs
namespace             TEXT NOT NULL
proposal_type         TEXT NOT NULL   fact_candidate / profile_rebuild / model_claim /
                                      rule_candidate / graph_update / dedup_merge /
                                      supersede / expire_projection
target_kind           TEXT            目标对象类型（应用型提案必填）
target_id             TEXT            目标对象 id（应用型提案必填）
payload_json          TEXT NOT NULL   提案内容（结构化，禁止自由指令文本）
source_observation_ids TEXT NOT NULL  JSON 数组：来源 Observation
source_evidence_ids   TEXT NOT NULL   JSON 数组：来源 Evidence Link
confidence            REAL NOT NULL
reasoning             TEXT NOT NULL   结构化理由（策略条目 + 证据计数）
risk_level            TEXT NOT NULL   low / high
status                TEXT NOT NULL   proposed / approved / rejected /
                                      applied / failed / rolled_back / expired
approved_by           TEXT            批准者（auto / user / 后续扩展）
applied_at            TEXT
rollback_ref          TEXT            回滚引用（应用型提案必填）
idempotency_key       TEXT NOT NULL   UNIQUE(namespace, proposal_type, payload_hash)
created_at            TEXT NOT NULL
```

不变量：

| 编号 | 不变量 |
|---|---|
| INV-P1 | `high` 风险提案从 proposed 到 applied 必须经过 `approved` 且 `approved_by` 为真实确认记录；`approved_by="auto"` 对 high 提案非法 |
| INV-P2 | payload_hash 相同的提案幂等：重复 propose 不产生第二行 |
| INV-P3 | `applied` 提案必有 `rollback_ref`；`rollback_ref` 为空即阻断级违约 |
| INV-P4 | 提案的 `source_evidence_ids` 为空时，`confidence` 不得高于低信任阈值，且 proposal_type 不得为 fact_candidate |

---

## 4. 风险分级与审批策略（待批准决策 D1）

### 4.1 低风险（可自动应用，`approved_by="auto"`）

全部条件必须同时满足：

```text
1. 类型 ∈ { dedup_merge(强证据), expire_projection, profile_rebuild(基于 accepted 事实),
            graph_update(权重 reinforce，有上限) }
2. 不改变任何用户陈述的语义内容
3. 不跨 namespace
4. 不触碰 §4.2 高风险清单
5. 有完整 evidence 链与幂等键
6. 可回滚（rollback_ref 可生成）
```

### 4.2 高风险（必须人工确认）

```text
规则晋升（forbid / always / override / 新规则写入）
覆盖用户明确偏好或纠正
删除、批量 forget、密钥与权限变化
跨 namespace 操作
高敏感属性推断（健康、财务、身份类）
影响外部行为的提案（导出、发送、系统 prompt 高影响注入）
model_claim 的首次 accepted（新假设进入系统认知）
```

不变量 INV-D1：`auto_accept` 类配置不得绕过 §4.2 清单——高风险清单在代码中硬编码，用户配置只能扩大（更保守）不能缩小。

### 4.3 默认自动化级别（建议，待 Gate 0 确认）

> **低风险自动、高风险确认；后台反思默认只 inspect + propose，apply 显式触发或由低风险白名单驱动。**

---

## 5. 应用与回滚语义

### 5.1 apply（单提案单事务）

```text
前置校验   状态=approved；幂等键未应用；目标仍存在且 snapshot 匹配
执行       单个 SQLite 事务：业务变更 + proposal.status=applied + rollback_ref 写入
失败       事务回滚 → status=failed + error_text；业务零改动（INV-F3）
```

### 5.2 rollback

```text
前置校验   proposal.status=applied；rollback_ref 有效
执行       单事务：按 rollback_ref 逆向应用 + status=rolled_back
效果       变更对 recall 不再可见（INV-F4）；原证据层从未被改动
```

不变量 INV-B1：rollback 不恢复"对原始记忆的任何改动"——因为 apply 本就不允许改动 `memories` 原始层；rollback 只撤销派生投影变更。

### 5.3 失败与重试（待批准决策 D6）

```text
语义       at-least-once + 幂等执行 + 可重试；不承诺 exactly-once
重试       failed 提案可由同 idempotency_key 重放；重放前重跑前置校验
上限       单提案重试 ≤ 3 次；超限转人工（保留 failed 记录）
队列       后台队列需有容量上限、超时、重试计数与失败状态（运维阻断项，见共识文档 §2.6）
```

---

## 6. 现有能力映射（逐项迁移计划）

| 现有能力 | 位置 | 目标形态 | 迁移阶段 |
|---|---|---|---|
| `consolidate_memories()` | `core/_maintenance.py` | reflect 编排入口；签名/返回不变 | Phase 4 |
| P0 去重/衰减/遗忘建议 | `consolidation.py` | dedup_merge / expire / supersede 提案策略 | Phase 4 |
| P1 模式识别 | `consolidation.py` | fact_candidate 提案策略 | Phase 4 |
| P2 语义聚合 | `SemanticAggregator` | aggregation 提案策略 + evidence links | Phase 4 |
| `derive_facts()` | `MemifyEngine` | fact_candidate 提案策略（candidate，非事实） | Phase 1 先接 provenance |
| `reinforce_edges()` | `MemifyEngine` | graph_update 提案（低风险白名单） | Phase 4 |
| `auto_decay()` | `MemifyEngine` | expire/supersede 提案，不物理删除高价值事实 | Phase 4 |
| 规则晋升 pipeline | `rules/promotion_pipeline.py` | rule_candidate 提案；forbid/always/override 恒高风险 | Phase 4 |

迁移约束：**一次只迁移一个策略**，迁移后旧路径与新提案路径并行对拍（新旧产出应一致），确认后再移除旧副作用路径。

---

## 7. 观测与运维要求

- run 与 proposal 的每次状态迁移产生 metrics（见[可观测性规范](MEMORY_EVOLUTION_OBSERVABILITY.md)）；
- 队列积压、重试次数、失败率、apply/rollback 比率可见；
- `interrupted` run 超过阈值触发告警；
- 禁止以 `|| true` 或 advisory 方式掩盖反思任务失败（项目既有教训）。

---

## 8. Gate 0 待确认项

| 决策 | 内容 | 本文建议默认 |
|---|---|---|
| D1 | Reflect 自动化级别 | 低风险白名单自动 + 高风险人工确认；后台默认只 inspect+propose |
| D6 | 异步保证级别 | at-least-once + 幂等 + 可重试，不承诺 exactly-once |
| （关联） | 单提案重试上限 | 3 次，超限转人工 |
