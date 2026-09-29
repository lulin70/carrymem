# 记忆演进可观测性规范（Memory Evolution Observability Spec）

> **版本**：v1.0
> **日期**：2026-09-28
> **状态**：已批准（Gate 0，2026-09-28；D8 按本文 §4 隐私约束执行）
> **权威关系**：在 [V0.11.0_OBSERVABILITY_INSTRUMENTATION.md](V0.11.0_OBSERVABILITY_INSTRUMENTATION.md) 既有契约之上扩展演进能力指标；既有 series 契约不变，本文只新增。
> **实现边界**：Gate 0 批准前不修改 `monitoring/` 或任何埋点代码。

---

## 1. 第一原则（继承，不重述推导）

沿用 v0.11.0 已验证的判定标准：

> **任何一个对外可见的 series，必须能指出「哪个进程、哪条代码路径、什么条件下」写出样本。指不出来的，不允许出现在 `/metrics` 里。**

三条推论继续有效：不允许"定义了但没人写"；不允许"写入了但读不到"（写入方与读取方同一 collector）；不允许"看起来健康其实没数据"（失败路径必须计数）。

**语义边界原则（0.11.1→0.11.2 教训）**：指标标签的语义由"谁发起"决定，不由"走了哪条代码路径"决定。本规范延续 `user operation / internal operation / background job` 三分法，每个新操作必须声明归属。

---

## 2. 新增指标清单（唯一权威表）

| Series | 类型 | 标签 | 产生者（进程/代码路径，Phase 落地） | 触发条件 | 进 SLO |
|---|---|---|---|---|---|
| `carrymem_total{operation="retain"}` | counter | operation | 任意 Python 进程 / `retain()` 委托 `classify_and_remember`（P1） | retain 成功返回 +1 | 否 |
| `carrymem_total{operation="retain_errors"}` | counter | operation | 同上 | retain 抛异常 +1 | 否 |
| `carrymem_latency_ms{operation="retain",...}` | summary | operation | 同上 | 每次调用结束（成功与失败都记） | ✅ P99<200ms |
| `carrymem_total{operation="reflect"}` | counter | operation | 任意 Python 进程 / `reflect()` inspect+propose（P4） | 反思入口调用成功 +1 | 否 |
| `carrymem_total{operation="reflect_errors"}` | counter | operation | 同上 | 抛异常 +1 | 否 |
| `carrymem_latency_ms{operation="reflect",...}` | summary | operation | 同上 | 每次调用结束 | ✅ P99<500ms |
| `carrymem_conflict_records_total` | counter | conflict_type, resolution | 冲突裁决器 `memory_conflicts` 写入点（P2） | 每产生一条 ConflictRecord +1 | 否 |
| `carrymem_conflict_auto_selected_total` | counter | conflict_type | 同上 | 自动裁决选定单一结论 +1（高风险主题出现该样本 = 违约信号） | 否（告警源） |
| `carrymem_observations_total` | counter | source_kind, predicate | Observation 写入准入点（P2） | 白名单写入成功 +1 | 否 |
| `carrymem_observation_write_denied_total` | counter | path | 同上准入点拒绝分支 | 非白名单写入被拒 +1（恒期望为 0，>0 = 路径违约） | 否（告警源） |
| `carrymem_evidence_links_total` | counter | relation_type | evidence link 写入点（P1） | 新链接写入 +1 | 否 |
| `carrymem_derived_unsupported_total` | counter | target_kind | unsupported 降级点（P1/P4） | 派生对象因证据缺失降级 +1 | 否 |
| `carrymem_proposals_total` | counter | proposal_type, risk_level | proposal 生成点（P4） | 每生成一条提案 +1 | 否 |
| `carrymem_proposals_applied_total` | counter | proposal_type, approved_by | apply 事务成功点（P4） | apply 成功 +1 | 否 |
| `carrymem_proposals_failed_total` | counter | proposal_type | apply 失败回滚点（P4） | apply 失败 +1 | 否 |
| `carrymem_proposals_rolled_back_total` | counter | proposal_type | rollback 成功点（P4） | rollback +1 | 否 |
| `carrymem_reflection_runs_total` | counter | reflection_type, status | run 状态迁移点（P4） | run 进入终态 +1（status ∈ completed/failed/cancelled/interrupted） | 否 |
| `carrymem_reflection_queue_size` | gauge | 无 | 后台队列入队/出队点（P4） | 队列长度变化时 set_gauge | 否（告警源） |
| `carrymem_recall_truncations_total` | counter | reason_code, layer | 截断发生点（P5） | 每次截断事件 +1 | 否 |
| `carrymem_recall_budget_utilization_ratio` | gauge | layer | 请求组装完成点（P5） | 每次用户 recall 后更新各层利用率 | 否 |
| `carrymem_migration_total` | counter | migration_id, result | migration ledger 执行点（P2） | 每次迁移尝试结束 +1（result=success/failed/rolled_back） | 否 |
| `carrymem_backup_restore_total` | counter | operation(backup/restore), result | 备份/恢复完成点（P6） | 每次操作结束 +1 | 否 |
| `carrymem_namespace_denied_total` | counter | operation | 全部安全拒绝点（P1 起逐步接入） | namespace 越权被拒 +1（恒期望低且稳定，突增 = 攻击或 bug） | 否（告警源） |
| `carrymem_async_jobs_total` | counter | job_kind, status | 后台任务终态点（P4） | queued/succeeded/failed/retried/cancelled +1 | 否 |

**既有 series 不变**：`classify_and_remember`、`recall`、`startup`、`carrymem_sse_clients`、`carrymem_uptime_seconds` 的定义、标签与语义边界维持 [V0.11.0 文档](V0.11.0_OBSERVABILITY_INSTRUMENTATION.md) §3/§5 契约。

---

## 3. 语义边界声明（防 double counting）

| 边界 | 规则 |
|---|---|
| `retain` vs `classify_and_remember` | retain 是语义别名。**过渡期只计 `classify_and_remember`**；待 retain 成为独立入口后再并列计数，切换时在 CHANGELOG 声明，避免同一次写入被计两次 |
| `reflect` vs `consolidate_memories` | 同上：Stable API 期间只计旧名；reflect 独立入口化后并列 |
| user / internal / background | `reflect`/`retain` 只统计用户发起；后台反思只进 `carrymem_reflection_runs_total`/`carrymem_async_jobs_total`，不得重复进 `reflect` counter |
| recall 截断 vs 冲突降权 | `CONFLICT_DEPRIORITIZED` 与 conflict metrics 可同事件并存（不同维度），不视为 double counting |

---

## 4. 隐私约束（对应决策 D8）

- 全部新 series 的标签只允许封闭枚举：operation、reason_code、layer、proposal_type、risk_level、conflict_type、resolution、source_kind、predicate、relation_type、migration_id、result、approved_by、job_kind、status、path、target_kind、conflict_policy；
- **禁止**出现：query 原文、memory content、memory id、用户标识、namespace 原文、文件路径；
- `migration_id` 允许出现（低基数、非敏感，是运维定位必需）；
- `path` 标签仅用于 `observation_write_denied`，值为白名单路径枚举（如 `internal_recall`），非文件系统路径；
- 高基数审查纳入 Gate 5 检查项。

---

## 5. SLO 扩展

| SLO | 目标 | 数据来源 |
|---|---|---|
| retain P99 | < 200ms | `carrymem_latency_ms{operation="retain"}` |
| reflect（内联路径）P99 | < 500ms | 同上 |
| conflict 自动裁决正确率（抽样审计） | 阻断级主题 0 违约 | `carrymem_conflict_auto_selected_total`（高风险标签恒 0） |
| observation 写入违约 | 0 | `carrymem_observation_write_denied_total` 恒 0 |
| apply 失败率 | < 1% 且每次失败可见 | proposals_applied / proposals_failed |
| 预算超限率 | 0（超保护层为 0；普通层有因码） | `carrymem_recall_truncations_total` |

SLO 计算延续现有 `HealthChecker` + 同一进程单例 collector 架构（v0.11.0 已验证），`no_data` 语义不变。

---

## 6. 告警草案（占位，落地前必须先回答产生者）

遵循项目铁律"写告警前先明确指标产生来源"——以下告警仅在对应 Phase 落地且 series 有真实 E2E 证据后启用：

| 告警 | 条件 | 依据 series |
|---|---|---|
| 反思队列积压 | queue_size > 上限持续 5min | `carrymem_reflection_queue_size` |
| 反思中断堆积 | interrupted runs > 阈值 | `carrymem_reflection_runs_total{status="interrupted"}` |
| 高风险自动裁决 | 任意样本 > 0 | `carrymem_conflict_auto_selected_total`（风险标签） |
| Observation 违约写入 | 任意样本 > 0 | `carrymem_observation_write_denied_total` |
| namespace 拒绝突增 | rate 突增 > 10x 基线 | `carrymem_namespace_denied_total` |
| 迁移失败 | 任意 result=failed | `carrymem_migration_total` |

---

## 7. 验证方法（每条新 series 必须）

1. **单元**：埋点调用点存在性 + 计数值断言（含失败路径）；
2. **集成（真实 E2E 对照）**：起真实服务 → 抓 `/metrics`（对照组：series 不存在/为 0）→ 执行真实动作 → 再抓 `/metrics`（断言样本出现且值正确）；
3. **语义边界守卫**：user/internal/background 互不串计（扩展 0.11.2 的 subTest 覆盖模式，覆盖全部触发条件形态）；
4. **受控证伪**：删除埋点调用 → 对应测试必须 FAIL（证明测试在测接线，不是恒真）。

验证标准沿用 v0.11.0 已验证的测试模式（`tests/test_monitoring.py` + `tests/integration/test_monitoring_endpoints.py`）。

---

## 8. 与 Gate 5 的对应

Gate 5 通过标准：本表全部 series ① 有真实写入点（代码可指认）② 有 exporter 读取点（同一 collector）③ 有真实 E2E 证据 ④ 标签低基数审查通过 ⑤ user/internal/background 守卫全绿。
