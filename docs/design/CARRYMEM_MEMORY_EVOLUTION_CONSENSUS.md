# CarryMem 记忆演进方案：多角色共识评审记录

> **日期**：2026-09-28  
> **评审范围**：全面记忆演进方法论、目标架构、交付路线、质量与安全门禁  
> **评审角色**：产品经理、架构师、安全专家、测试专家、开发负责人、DevOps/可观测性负责人  
> **评审方式**：基于现有代码、设计文档、CI、E2E 和发布约束的并行预审与联合归纳  
> **状态**：**Gate 0 已批准（2026-09-28，项目负责人批准 8 项决策按契约文档建议默认执行）**，Phase 1 Provenance 实现已授权

---

## 1. 结论摘要

评审一致认为 CarryMem 已具备可继续演进的工程基础，但不批准一次性全量重构或直接进入大规模实现。

### 共识结论

> **保留 `memories` 作为稳定原始证据层，增量引入 Evidence、Observation、Fact、Experience、Profile、Mental Model 和 Reflection Proposal；所有派生结果必须有 provenance；Reflect 默认先生成提案，低风险可自动应用，高风险必须确认；Stable API、SQLite-first、本地优先和核心无外部服务依赖保持不变。**

### 当前批准范围

可以继续进行：

- 领域模型、生命周期契约和数据契约设计；
- Evidence/Observation/Conflict/Proposal 的 ADR 和测试计划；
- recall 质量、token budget、迁移和可观测性基线；
- 现有 Memify/consolidation 的 proposal 化设计；
- 文档事实校准和用户价值 E2E 设计。

### 当前禁止范围

在 Gate 0 未批准前，不执行：

- 大规模 schema 或核心 recall 实现改造；
- 全量历史数据 backfill；
- Stable API 返回结构破坏性变更；
- 自动高风险 reflect/apply；
- B2 版本发布动作。

---

## 2. 各角色独立结论

### 2.1 产品经理

**认可：**

- 首要价值应收敛为“本地保存偏好和纠正，并在下一次 AI 交互中自动、可解释、可撤销地使用”；
- `retain → recall → reflect` 必须成为用户可理解的产品闭环；
- 所有自动注入、覆盖、晋升和删除都需要解释与控制；
- 三个入口先统一 P0 核心路径，不追求所有高级能力同时对齐。

**产品风险：**

- 记忆、规则、知识、图谱、向量、TUI、MCP 等承诺过宽；
- 结构化接口可用不等于用户获得正确记忆；
- 迁移“可导出”容易被误解为跨版本、跨后端无损；
- MCP 工具过多可能降低 Agent 工具选择质量。

**产品验收重点：**

- 首次记住并再次召回成功率；
- 下一会话正确召回率；
- 无关注入率；
- 纠正生效率；
- 100% 自动注入可解释；
- 忘记后不再召回。

### 2.2 架构师

**认可：**

- 保留 `memories`，不要重写稳定存储核心；
- 新领域模型采用 additive projection；
- `evidence_links` 是 Fact、Profile、Mental Model 和 Reflect 的基础；
- Profile 是可重建投影，Mental Model 是版本化假设集合；
- Reflection Run 必须可恢复、可幂等、可审计；
- migration 采用 additive + lazy backfill。

**架构风险：**

- 继续把所有语义塞入 metadata；
- 把 consolidation、Memify、规则晋升合并成一个无边界动作；
- 让 core 继续扩大对 SQLite 内部连接和 SQL 的直接耦合；
- 用一次大版本改名替换 Stable API。

**架构验收重点：**

- 任意派生对象可追溯到原始证据；
- schema migration 可重复、失败停止、可恢复；
- 不支持新能力的 adapter 不影响 Stable API；
- 反思输出有运行、配置、算法和幂等标识。

### 2.3 安全专家

**认可：**

- namespace 必须升级为不可绕过的安全上下文；
- Evidence、Observation、Graph、Rule、Vector、Cache、Async Job 和 Export 全链路隔离；
- inference 不得冒充用户事实；
- Reflect 不得改变权限、namespace、删除和安全边界；
- 规则数据与执行指令分离；
- 解密失败、审计失败和迁移关键失败必须 fail-closed。

**安全阻断项：**

- 任何 namespace 泄漏；
- evidence、日志或 metrics 泄露敏感原文；
- 派生结果无来源链；
- `.carry` 仅有 checksum 而无认证完整性；
- 删除原始记忆后留下可继续召回的无来源高信任派生事实；
- 自动接受高风险规则。

### 2.4 测试专家

**认可：**

- 覆盖率仍是底线，但不能替代 recall 质量和真实用户结果；
- 每项新能力必须同时有单元、集成、迁移、异步、安全、E2E、恢复和可观测性测试；
- 发布前必须模拟真实用户使用链路；
- migration、backup/restore、token budget 和 namespace 泄漏属于发布阻断项。

**测试阻断项：**

- 只断言返回类型，不断言用户结果；
- 迁移失败后服务仍进入 ready；
- async/sync 行为不一致；
- 反思重复执行生成重复派生对象；
- metrics 只在单元测试中变化，真实链路没有证据。

### 2.5 开发负责人

**认可：**

- 复用现有 `StoredMemory`、版本链、namespace、Memify、RecallBudget 和 MetricsCollector；
- 新 API 先委托现有实现；
- Reflect 采用 inspect/propose/apply 边界；
- 旧接口和新接口共享内部实现，避免双轨逻辑漂移；
- 后台反思采用 at-least-once + 幂等，不承诺 exactly-once。

**开发风险：**

- 同时改变 API、schema、排序和 consolidation 行为，导致回归无法定位；
- 观察事件无限写入导致 SQLite 写放大；
- 派生记忆没有幂等键造成数量膨胀；
- Mixin、Protocol、Async、CLI、MCP 未同步演进。

### 2.6 DevOps/可观测性负责人

**认可：**

- 每项新能力必须有真实生产指标写入路径；
- user operation、internal operation、background job 分开统计；
- migration、backup、restore、reflection job、budget truncation 和 authorization failure 可见；
- 发布必须包含迁移演练、恢复演练、真实 MCP/HTTP E2E 和回滚预案。

**运维阻断项：**

- benchmark 失败被 `|| true` 掩盖；
- `/metrics` 与业务使用不同 collector；
- readiness 只代表端口打开，不代表 schema 完整；
- 反思队列无容量、超时、重试和失败状态；
- 无法确认版本、schema、数据集和测试结果的对应关系。

---

## 3. 角色冲突与解决方案

| 冲突 | 解决方案 |
|---|---|
| 自动反思提高体验 vs 自动错误污染记忆 | 默认 proposal；低风险自动应用；高风险确认 |
| latest-wins 简单直观 vs 新信息未必更可信 | 来源、作用域、纠正、时间、置信度、证据综合裁决 |
| 尽量召回完整证据 vs Token/延迟有限 | retrieval/evidence/output 分层硬预算，并保留截断原因 |
| 保留更多证据便于解释 vs 原始数据敏感 | evidence 分级、加密、脱敏、最小化留存和可删除 |
| 原生异步吞吐 vs 当前维护成本 | 保持同步兼容 facade；后台任务 at-least-once + 幂等 |
| 快速增加表结构 vs SQLite 数据安全 | additive、migration ledger、事务、完整性检查和恢复 |
| 指标全面 vs 高基数和隐私 | 低基数标签，内容只做 hash 或不记录 |
| 入口全部对齐 vs 高级能力复杂 | 先统一 remember/recall/explain/forget/whoami/context/export/import |

---

## 4. 必须拍板的决策

以下决策已完成 Gate 0 拍板（**2026-09-28 项目负责人批准，按各契约文档"建议默认"执行**）：

1. **Reflect 自动化级别** ✅：低风险白名单自动应用，高风险人工确认（高风险清单代码硬编码）——见 [ADR-016](../architecture/decisions/ADR-016-reflection-proposal-lifecycle.md)。
2. **Evidence 保留策略** ✅：evidence link 行永久保留（仅元数据不含原文）；彻底删除需用户显式要求并审计——见 [ADR-015](../architecture/decisions/ADR-015-evidence-observation-model.md)。
3. **Observation 语义** ✅：默认 TTL 表生效；默认**不进入**普通长期 recall，仅 conflict_resolution/reflection 任务按需读取——见 Evidence/Observation 契约 §3.5。
4. **冲突裁决顺序** ✅：采用 P1-P6 信任层级优先级链，否决 latest-wins——见 [ADR-017](../architecture/decisions/ADR-017-conflict-resolution-policy.md)。
5. **Token budget 边界** ✅：采用 retrieval/evidence/reflection/output 四层预算，`build_context` 默认 `max_tokens=2000` 不变——见预算契约 §2。
6. **异步保证级别** ✅：at-least-once + 幂等执行 + 可重试，不承诺 exactly-once；单提案重试 ≤ 3 次后转人工——见 Reflection Proposal 契约 §5.3。
7. **SQLite 迁移范围** ✅：additive + migration ledger + fail-closed；旧版本程序可打开新库（新表对旧代码透明）；ledger checksum 防篡改——见 [ADR-018](../architecture/decisions/ADR-018-memory-evolution-migration.md)。
8. **Audit/Metrics 隐私** ✅：metrics 零原文、封闭枚举低基数标签；evidence/observation 写入前与 memories 同策略脱敏；导出 allowlist 默认不含——见可观测性规范 §4 与 Evidence/Observation 契约 §3.6。

---

## 5. Gate 0-6 批准门槛

### Gate 0：方案

完成生命周期、领域对象、冲突、自动应用、删除、预算、异步和兼容契约。

**审批材料（2026-09-28 已就位）**：

- 生命周期契约：[`MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md`](MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md)
- Evidence/Observation 契约：[`MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md`](MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md)
- 冲突裁决契约：[`MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md`](MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md)
- Reflection Proposal 契约：[`MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md`](MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md)
- 分层预算契约：[`MEMORY_EVOLUTION_BUDGET.md`](MEMORY_EVOLUTION_BUDGET.md)
- 可观测性规范：[`MEMORY_EVOLUTION_OBSERVABILITY.md`](MEMORY_EVOLUTION_OBSERVABILITY.md)
- 测试计划：[`../testing/MEMORY_EVOLUTION_TEST_PLAN.md`](../testing/MEMORY_EVOLUTION_TEST_PLAN.md)
- 迁移恢复 Runbook：[`../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md`](../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md)
- ADR-014 ~ ADR-018（均为 Proposed 状态）：[`../architecture/decisions/ADR-014-memory-lifecycle-contract.md`](../architecture/decisions/ADR-014-memory-lifecycle-contract.md) 起
- 实现启动清单：[`PHASE1_PROVENANCE_READINESS.md`](PHASE1_PROVENANCE_READINESS.md)

审批方式：§4 的 8 项决策逐项拍板（各契约文档中的"建议默认"即为待确认项），批准后由负责人将相关 ADR 状态改为 Accepted，再按 [`PHASE1_PROVENANCE_READINESS.md`](PHASE1_PROVENANCE_READINESS.md) §2 启动 Phase 1。

### Gate 1：数据契约

完成类型定义、namespace、versioning、evidence lineage、proposal 状态机、ConflictRecord 和旧 API 投影。

### Gate 2：SQLite 迁移

完成空库、最新库、历史库、重复迁移、中断恢复、备份恢复、FTS/Graph/Vector 一致性和 namespace 测试。

### Gate 3：安全

完成证据脱敏、全链路隔离、规则注入、加密 fail-closed、删除级联、审计落盘和异步 namespace 测试。

### Gate 4：真实用户 E2E

完成：

```text
retain → recall
retain → conflict → reflect proposal → approve/reject
reflect → rollback
backup → migration → restore → recall
async reflect → restart → resume
budget exhausted → deterministic fallback
```

### Gate 5：可观测性

每个新增指标都有生产写入点、exporter 读取点、真实 E2E 证据和低基数标签审查。

### Gate 6：发布

全量质量门禁、关键 E2E、安全扫描、迁移/恢复演练、性能/token 基线、文档/runbook、回滚和 feature flag 关闭路径全部通过。

---

## 6. 评审依据

- [`CARRYMEM_MEMORY_EVOLUTION_METHOD.md`](CARRYMEM_MEMORY_EVOLUTION_METHOD.md)
- [`METHODOLOGY.md`](METHODOLOGY.md)
- [`CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md`](../CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md)
- [`API_STABILITY.md`](../API_STABILITY.md)
- [`RELEASE_RUNBOOK.md`](../RELEASE_RUNBOOK.md)
- [`ADR-009-async-pipeline.md`](../architecture/decisions/ADR-009-async-pipeline.md)
- [`ADR-010-memify-dynamic-refinement.md`](../architecture/decisions/ADR-010-memify-dynamic-refinement.md)
- [`ADR-013-edge-confidence-labels.md`](../architecture/decisions/ADR-013-edge-confidence-labels.md)
- `src/carrymem/core/_memory_crud.py`
- `src/carrymem/core/_recall.py`
- `src/carrymem/core/_maintenance.py`
- `src/carrymem/consolidation.py`
- `src/carrymem/layers/memify.py`
- `src/carrymem/adapters/sqlite/schema.py`
- `src/carrymem/adapters/sqlite/recall_engine.py`
- `tests/e2e/`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

---

## 7. 最终评审意见

**结论：有条件通过方案预研，不批准一次性全量实现。**

项目负责人审阅并明确上述 8 项决策后，才可以进入 Phase 1：Provenance 基础的实现准备。实现前仍需补齐对应 ADR、数据契约、迁移演练脚本和测试计划；实现完成后必须重新通过 Gate 1-6。
