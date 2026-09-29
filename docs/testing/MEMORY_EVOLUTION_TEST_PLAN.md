# 记忆演进测试计划（Memory Evolution Test Plan）

> **版本**：v1.0
> **日期**：2026-09-28
> **状态**：已批准（Gate 0，2026-09-28），随各 Phase 交付逐项执行
> **权威关系**：落实 [主方案](../design/CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §11 与四份契约文档中的全部 INV 不变量；本文是演进能力的**验收权威**。
> **实现边界**：Gate 0 批准前不新增任何测试代码。

---

## 1. 目标与原则

1. 覆盖率仍是底线（当前 83.19%，floor 80%），但**不能替代领域质量**：召回质量、纠正有效性、迁移完整性、真实用户结果必须单独度量。
2. 每项新能力必须同时具备：单元、集成、迁移、异步、安全、E2E、恢复、可观测性八类验证。
3. 测试是质量守门员：**禁止为了通过而修改断言**；发现伪问题先复现再修（项目铁律）。
4. 发布前必须执行模拟真实用户使用的 E2E（用户规则 3），执行口径与本地门禁一致（`scripts/ci_local_check.py`）。

---

## 2. 测试金字塔与现有基线

```text
静态/安全/类型        flake8 / black / isort / mypy / radon / bandit / swallowed-assert
单元与纯函数          tests/（当前 4907 passed, 10 skipped 基线）
核心集成与迁移        tests/integration/ + 新增 tests/migration/
异步/并发/恢复        tests/（asyncio 标记）+ 新增恢复测试
真实 HTTP/MCP         tests/integration/test_monitoring_endpoints.py 等
真实用户 E2E          tests/e2e/（当前 245 passed in 82.24s 基线）
发布门禁              scripts/ci_local_check.py 八项阻塞门禁
```

新演进能力测试放在：

```text
tests/migration/          迁移与恢复（新目录）
tests/evidence/           Evidence/Observation（新目录）
tests/reflection/         Run/Proposal/apply/rollback（新目录）
tests/recall_quality/     召回质量评估（新目录，离线数据集驱动）
tests/e2e/                真实用户路径扩展（现有目录）
```

---

## 3. 不变量 → 测试映射总表

### 3.1 生命周期契约（[LIFECYCLE](../design/MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md)）

| INV | 测试要点 | 层级 | 阶段 |
|---|---|---|---|
| INV-S1 | 事实状态与执行状态分别存储查询，接口不得互相冒充 | 单元 | P4 |
| INV-S2 | candidate 不进高信任路径（prompt 注入/规则晋升） | 集成 | P4 |
| INV-R1 | retain 后可检索回原文 | 单元+集成 | P1 |
| INV-R2 | 派生记忆 source_kind 不可伪装 user_statement | 单元 | P1 |
| INV-R3 | 重复 retain 幂等 | 单元 | P1 |
| INV-R4 | retain 失败计错误 metrics 且无半写入 | 单元 | P1 |
| INV-R5 | 冲突登记失败 → retain 整体失败或显式降级留痕 | 单元 | P2 |
| INV-R6 | namespace=None 底层写入被拒 | 单元+安全 | P1 |
| INV-C1 | 跨 namespace 内容零泄漏 | 安全+集成 | P1 |
| INV-C2 | include_superseded=False 不返回被取代版本 | 单元+集成 | P2 |
| INV-C3 | correction_resolution 下 correction 100% 优先 | 集成+E2E | P2 |
| INV-C4 | 输出不超 output budget，截断带原因码 | 单元+集成 | P5 |
| INV-C5 | 内部簿记读取不计用户 recall metrics | 单元（已有守卫扩展） | P1 |
| INV-C6 | 空结果与冲突不可回答可区分 | 单元 | P2 |
| INV-C7 | 恶意 query 全路径无 SQL 执行 | 安全（扩展现有注入守卫） | P1 |
| INV-F1 | 派生对象可追溯到 ≥1 原始来源 | 集成 | P1 |
| INV-F2 | 同幂等键提案不重复产出 | 单元+集成 | P4 |
| INV-F3 | apply 失败业务零改动 | 集成 | P4 |
| INV-F4 | rollback 后 recall 不可见已回滚变更 | 集成+E2E | P4 |
| INV-F5 | 高风险提案无批准记录不得 applied | 安全+单元 | P4 |
| INV-F6 | 反思崩溃重启可恢复且不重复产出 | 恢复 | P4 |
| INV-F7 | inspect 零业务写 | 单元+集成 | P4 |

### 3.2 Evidence/Observation（[EVIDENCE](../design/MEMORY_EVOLUTION_EVIDENCE_OBSERVATION.md)）

| INV | 测试要点 | 层级 | 阶段 |
|---|---|---|---|
| INV-E1 | evidence 三方 namespace 一致；查询先按 namespace 过滤 | 安全 | P1 |
| INV-E2 | evidence 不可变；更正走 supersedes 新链接 | 单元 | P1 |
| INV-E3 | (source,target,relation) 唯一幂等 | 单元 | P1 |
| INV-E4 | 无有效 evidence 的派生对象判 unsupported | 集成 | P1 |
| INV-E5 | 来源变更 → 链接 stale → 重算 | 集成 | P1 |
| INV-O1 | 非白名单写 Observation 被拒并计数 | 单元 | P2 |
| INV-O2 | 单次 retain 产生 Observation ≤ 2 | 集成 | P2 |
| INV-O3 | 无 TTL 的 Observation 写入被拒 | 单元 | P2 |
| INV-O4 | Observation 不得直接以 accepted 参与决策 | 集成 | P2 |

### 3.3 冲突裁决（[CONFLICT](../design/MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md)）

| INV | 测试要点 | 层级 | 阶段 |
|---|---|---|---|
| INV-X1 | 非平凡裁决必产 ConflictRecord | 单元+集成 | P2 |
| INV-X2 | 新推断不得凭时间越过旧用户陈述 | 单元 | P2 |
| INV-X3 | 纠正后旧结论 superseded 且不再唯一返回 | 集成+E2E | P2 |
| INV-X4 | 不可裁决时呈现冲突或显式不可回答 | 单元 | P2 |
| INV-X5 | reasoning 引用优先级条目与证据计数（可机器校验） | 单元 | P2 |
| INV-X6 | resolved.selected_id ∈ candidates 且状态合法；再纠正产生新记录 | 单元 | P2 |
| INV-X7 | 高风险主题自动择一 = 阻断级违约（负向测试） | 安全 | P2 |
| INV-X8 | 各 conflict_policy 呈现行为符合 §7 表 | 集成 | P2 |

### 3.4 Reflection Proposal（[PROPOSAL](../design/MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md)）

| INV | 测试要点 | 层级 | 阶段 |
|---|---|---|---|
| INV-RR1 | 同 idempotency_key run 重放复用已产出 proposal | 单元+恢复 | P4 |
| INV-RR2 | interrupted run 从 cursor 恢复，已完成产出有效 | 恢复 | P4 |
| INV-RR3 | run 失败不污染业务表 | 集成 | P4 |
| INV-P1 | high 提案 approved_by=auto 非法（负向） | 安全 | P4 |
| INV-P2 | 同 payload_hash 提案幂等 | 单元 | P4 |
| INV-P3 | applied 必有 rollback_ref（负向探针） | 单元 | P4 |
| INV-P4 | 零证据提案置信度受限且不得为 fact_candidate | 单元 | P4 |
| INV-D1 | auto_accept 配置无法缩小高风险清单（负向） | 安全 | P4 |
| INV-B1 | rollback 不改原始层（原始层本就不可被 apply 触碰） | 集成 | P4 |

### 3.5 预算（[BUDGET](../design/MEMORY_EVOLUTION_BUDGET.md)）

| INV | 测试要点 | 层级 | 阶段 |
|---|---|---|---|
| INV-BP1 | 旧 API 参数 → 计划确定性构造，无 IO | 单元 | P5 |
| INV-BP2 | namespace 缺失构造失败 | 单元 | P5 |
| INV-BP3 | 任务模式只能收紧不能放宽 | 单元 | P5 |
| INV-T1 | 非法任务模式被拒 | 单元 | P5 |
| INV-TB1 | 截断至保护层仍超限 → 整体降级不静默丢保护层 | 集成+E2E | P5 |
| INV-TB2 | 每次截断有 Truncation 记录 | 单元 | P5 |
| INV-TB3 | 同输入同计划截断确定一致 | 单元 | P5 |
| INV-RB1 | 后台 run 超时/达上限有序收尾留 cursor | 恢复 | P4 |
| INV-TK1 | 同进程单一估算口径 | 单元 | P5 |

### 3.6 迁移（[RUNBOOK](../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md)）

| 编号 | 测试要点 | 层级 | 阶段 |
|---|---|---|---|
| MIG-1 | 空库迁移成功 | 集成 | P2（schema 落地时） |
| MIG-2 | 最新版本库重复迁移幂等 | 集成 | 同上 |
| MIG-3 | 历史库（0.10.x/0.11.0/0.11.2）直升成功 | 集成 | 同上 |
| MIG-4 | 中断恢复（kill 在 migration 中途）→ 重启后 ledger 一致 | 恢复 | 同上 |
| MIG-5 | 迁移失败 → ready 阻断（fail-closed，非 warning 继续） | 集成+安全 | 同上 |
| MIG-6 | backup → 迁移 → restore → recall 内容/版本/关系/语义一致 | 集成+E2E | 同上 |
| MIG-7 | FTS/Graph/Vector 与主表行数一致性校验 | 集成 | 同上 |
| MIG-8 | namespace 隔离在迁移后保持 | 安全 | 同上 |
| MIG-9 | ledger checksum 篡改可检测（负向） | 安全 | 同上 |

---

## 4. 真实用户 E2E 路径（扩展 tests/e2e/）

主方案 §11.2 的 10 条路径全部落地为 E2E 用例（真实 SQLite、真实 API 入口，禁 Mock 核心对象）：

```text
E2E-1  retain → recall → build_context         相关进上下文，无关不进
E2E-2  retain → correction → recall            纠正生效，旧结论不唯一
E2E-3  retain → conflict → proposal → approve/reject   冲突可见可审计
E2E-4  reflect apply → rollback → recall       应用与回滚正确
E2E-5  namespace A/B                           memory/graph/evidence/rule/export 全链路隔离
E2E-6  backup → migration → restore → recall   完整性保持
E2E-7  async reflect → restart → resume        至少一次执行且不重复产出
E2E-8  budget exhausted                        确定性截断，correction/安全事实不丢
E2E-9  HTTP/MCP → metrics                      真实请求产生真实 collector 变化
E2E-10 解密失败/审计失败/迁移失败 → fail-closed  服务不 ready，数据可恢复
```

E2E-2/E2E-3/E2E-4/E2E-8 为**发布阻断项**（共识文档测试专家结论）。

---

## 5. 召回质量评估（tests/recall_quality/）

- **数据集版本化**：离线评估集入库存档（query、期望结果、must-not-return、冲突场景、correction 场景），带版本号；变更走评审。
- **指标与初始阈值**（主方案 §11.3，以真实基线校准）：

| 指标 | 初始阈值 |
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

- **CI 集成**：评估作为 advisory 先跑（建基线期），基线稳定后转 blocking；任何 namespace 泄漏 / 数据损坏 / 预算超限从第一天起就是 blocking。
- **诚实门禁**：评估未执行或数据集缺失时报告 `NOT_EVALUATED` 并非零退出，禁止假绿（沿用覆盖度报告教训）。

---

## 6. 性能与 SLO 验证

| 项 | 目标 | 验证方式 |
|---|---|---|
| recall P95 / P99 | ≤ 200ms / ≤ 500ms | 现有 101 次真实调用测量法（扩展到新路径） |
| retain P95 / P99 | ≤ 100ms / ≤ 200ms | 同上 |
| migration 成功率 | 100% | MIG-1~9 |
| backup/restore 校验失败率 | 0 | MIG-6 |
| 异步取消连接泄漏 | 0 | 压力 + 泄漏探针 |
| P99 回归 | >15% 阻断 | benchmark gate（非 advisory，禁止 `\|\| true`） |
| 首次调用延迟 | 覆盖插桩口径测量（防 7.5ms→106ms 类隐身） | ci_local_check 同口径 |

---

## 7. 安全测试专项

```text
SEC-1  namespace 泄漏矩阵：evidence/observation/facts/profiles/rules/graph/vector/cache/async/export 全对象 × 跨域访问全拒绝
SEC-2  提示注入：记忆内容含指令文本注入 system prompt 时的边界与转义
SEC-3  多语言/Unicode 同形/编码变形的分类与检索鲁棒性（扩展现有注入检测）
SEC-4  解密失败 fail-closed：密文不得当明文传播（回归现有 AsyncSQLiteAdapter 语义）
SEC-5  审计落盘失败 → 高风险操作阻断
SEC-6  规则数据与指令分离：payload 含可执行文本不产生执行
SEC-7  .carry pack 认证完整性（升级项，Phase 6 前完成设计）
SEC-8  evidence/observation 中的敏感内容脱敏一致性（与 memories 同策略）
```

---

## 8. 可观测性验证

每条新增 series 遵循 V0.11.0 判定标准（[OBSERVABILITY](../design/MEMORY_EVOLUTION_OBSERVABILITY.md) §2）：

1. 能指出"哪个进程、哪条代码路径、什么条件"产生样本；
2. 真实 HTTP/MCP E2E 前后对照（对照组 → 动作 → 断言 series 出现/变化）；
3. 失败路径也有计数（防 no_data 假健康）；
4. user / internal / background 三类语义边界有守卫测试（扩展 `test_storing_a_memory_does_not_count_as_a_recall` 模式，覆盖全部触发条件形态）。

---

## 9. 阶段完成标准（与 Gate 对齐）

| Gate | 测试完成标准 |
|---|---|
| Gate 1 数据契约 | §3.1/3.2 中 P1 相关 INV 单元级全绿；类型契约有负向测试 |
| Gate 2 SQLite 迁移 | MIG-1~9 全绿；旧版本库直升矩阵（0.10.x/0.11.0/0.11.2）覆盖 |
| Gate 3 安全 | SEC-1~6 全绿；INV-R6/C1/X7/P1/D1 负向测试全绿 |
| Gate 4 真实用户 E2E | E2E-1~10 全绿；四条阻断路径（2/3/4/8）100% 通过 |
| Gate 5 可观测性 | 全部新 series 有真实 E2E 证据 + 语义边界守卫 |
| Gate 6 发布 | 八项本地门禁 + 全量回归 + E2E + 迁移/恢复演练 + 性能基线 + runbook 更新 |

---

## 10. 执行口径

- 本地全量门禁：`python3 scripts/ci_local_check.py`（与 CI 同锁版本、同测试口径，含 `--cov` 插桩）；
- 全量回归参考时长：约 13 分钟（0.11.x 可观测性验证实测 774.91s，4963 项全量口径；B1 期 `-m "not slow"` 口径为 4907 passed, 10 skipped, 77 deselected——两者范围不同，引用时必须注明口径），后台托管执行，禁止反复重跑；
- 单测调试可用 `-o addopts=''` 脱离 coverage，正式门禁不适用；
- 长任务一律 `run_in_background` 托管，不用 `nohup ... & disown`（项目教训）。
