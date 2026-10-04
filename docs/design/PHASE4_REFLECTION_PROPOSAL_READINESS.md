# Phase 4 Readiness — Reflection Proposal

> 状态日期：2026-10-03
> 阶段边界：本文件只覆盖 Phase 4（Reflection Run + Proposal 同步最小闭环）。
> 契约来源：[MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md](MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md)
>（Gate 0 已批准）；实现以该契约为准，本文只做落地计划与证据记录。
> RecallPlan / token 硬门禁（Phase 5）**未开始**。

## 1. 阶段总览

| 阶段 | 状态 |
|---|---|
| Phase 1 async provenance parity | 完成 |
| Phase 2 Observation/ConflictRecord | 完成（全量门禁 green，2026-10-03） |
| Phase 4 Reflection Run + Proposal 同步最小闭环 | **核心切片已实现，专项 37 passed；待独占全量门禁收尾** |
| Phase 5 RecallPlan / token 硬门禁 | 未开始 |

## 2. 交付物切片

| 切片 | 内容 | 状态 |
|---|---|---|
| S1 | v220 迁移：`memory_reflection_runs` + `memory_reflection_outputs` 两表 + 索引 + CHECK 约束，migration ledger fail-closed（checksum + status 校验 + 事务回滚） | ✅ 已实现（`schema.py` `migrate_v220`；outputs 表含 `error_text`（契约 §5.1 apply 失败留痕要求）与 `applied⇒rollback_ref/applied_at NOT NULL`、`rejected⇒approved_by NOT NULL` 两条 schema 级 CHECK） |
| S2 | `ReflectionManager`（`adapters/sqlite/reflection.py`）：run 生命周期（start/complete/fail/interrupt/cancel + INV-RR1 幂等重放 + INV-RR2 cursor + INV-RR3 失败不污染）、proposal 生命周期（propose/list/get/approve/reject），INV-P2 幂等（payload sha256）、INV-P4 证据-置信度约束、脱敏 | ✅ 已实现 |
| S3 | apply / rollback 单事务语义（INV-P3 rollback_ref 必填、INV-B1 只撤销派生投影）：apply 处理器注册表，首发 3 个真实处理器 `expire_projection` / `graph_update(reinforce, max_weight≤10)` / `supersede`；其余 proposal_type apply 一律 fail-closed 拒绝（`no apply handler ... (fail-closed)`） | ✅ 已实现 |
| S4 | 风险分级（INV-D1：高风险清单代码硬编码 `classify_risk()`）：低风险白名单 = expire_projection / graph_update(reinforce+上限) / dedup_merge(≥2 证据)；高风险恒人工（rule_candidate、model_claim、fact_candidate、supersede、profile_rebuild）；未知形状 fail-closed 为 high；调用方只能调高不能调低 | ✅ 已实现 |
| S5 | 适配器接线（capabilities `reflection_runs` / `reflection_proposals` + 门面 14 个方法）+ metrics（runs started/reused/resumed/completed/failed；proposals created/reused/approved/rejected/applied/apply_failed/rolled_back） | ✅ 已实现 |
| S6 | 测试：不变量单测（INV-RR1-3、INV-P1-4、INV-D1 矩阵、INV-B1/F3）+ 真实用户 E2E（propose → inspect → approve → apply → recall 生效 → rollback → recall 恢复） | ✅ **40 passed**（`tests/evolution/test_reflection_proposal_phase4.py` 34 项 + `tests/e2e/test_e2e_reflection_proposal.py` 2 项 + memify 回归 32 项） |
| S7 | **decay 策略提案化（契约 §6 第一个迁移策略）**：抽取共享三重门 `find_decay_candidates()`（memify 与 reflection 单一事实源）；`ReflectionManager.run_decay_reflection()` + 门面 `reflect_decay()`（候选 → expire_projection 提案 → 低风险白名单自动应用）；`expires_at = run.started_at + grace_days`（从 run 身份派生，重放 payload hash 稳定 → INV-P2 幂等）；resume 不再重置 started_at（否则破坏重放幂等，已修） | ✅ 已实现 + **对拍通过** |

### S7 对拍证据（新旧路径，双库孪生种子）

```text
test_shared_gate_matches_auto_decay_effect: 共享门候选 == auto_decay 实际衰减集（排除预置已衰减）
test_reflect_decay_proposes_for_exactly_gate_candidates: 提案目标集 == 门候选集，全部 low/proposed
test_reflect_decay_auto_apply_then_idempotent_replay: 二次运行复用同 run（INV-RR1）、提案数不变（INV-P2）、applied 为空
test_reflect_decay_rollback_restores_previous_expiry: 回滚恢复原 expires_at（INV-B1）
test_twin_db_legacy_and_proposal_paths_agree_on_candidates: 孪生库对拍，legacy 衰减集 == 提案应用目标集；
  效果按契约 §6 有意不同——legacy 折半 importance，提案路径设 expires_at，两者均不物理删除
验证：tests/evolution/test_reflection_proposal_phase4.py 40 passed + tests/test_memify.py 32 passed；
black/isort/flake8/mypy（164 source files）/radon 全绿
```

遗留策略（dedup_merge / consolidate() 的 to_supersede/to_forget）按 §6 纪律逐个迁移，见 §6 显式延期项。

### 2.1 实现过程中由测试揭示并修复的两个真实缺陷

1. **apply/rollback 未失效召回缓存（一致性缺陷，产品级）**：E2E 首版失败探针证明，apply 期间的召回结果被 query-result cache 缓存，rollback 后仍返回陈旧结果。根因：apply/rollback 属可见性变更（改变某查询返回哪些 key），key 级失效（`invalidate_keys`）够不到"被隐藏 key 期间缓存的查询"；已对齐 crud.py 可见性变更路径的约定，apply/rollback 成功后整命名空间 `invalidate_cache()`。
2. **radon 复杂度门禁拦截**：`create_proposal` 初版 CC=22（D 级，CI 阻断线 ≥21），已拆分 `_serialize_proposal_fields()` 验证助手后消除。

### 2.2 静态与回归证据（2026-10-03）

```text
Phase 4 专项 + E2E：37 passed（tests/evolution/test_reflection_proposal_phase4.py + tests/e2e/test_e2e_reflection_proposal.py）
邻近回归：evolution 全目录 + sqlite adapter + migration v200 + async + maintenance = 253 passed
black / isort / flake8 / mypy（reflection.py, schema.py）：全部通过
radon：reflection.py 无 D/E/F 函数
capability 契约测试已同步新 capabilities（test_sqlite_adapter.py）
```

## 3. 数据模型（与契约 §2/§3 逐字段一致）

```text
memory_reflection_runs
  run_id TEXT PK
  namespace TEXT NOT NULL
  reflection_type TEXT NOT NULL   -- dedup / conflict_scan / decay / fact_derivation /
                                  -- profile_rebuild / aggregation / graph_maintenance
  strategy_version TEXT NOT NULL
  input_cursor TEXT
  input_snapshot TEXT NOT NULL    -- 输入集快照哈希（决定性重放依据）
  config_snapshot TEXT NOT NULL   -- 配置 JSON 快照
  status TEXT NOT NULL            -- running / completed / failed / cancelled / interrupted
  started_at TEXT NOT NULL
  completed_at TEXT
  error_text TEXT                 -- 失败摘要（不含敏感原文）
  idempotency_key TEXT NOT NULL
  UNIQUE (namespace, reflection_type, input_snapshot, config_snapshot)

memory_reflection_outputs
  proposal_id TEXT PK
  run_id TEXT NOT NULL            -- → memory_reflection_runs
  namespace TEXT NOT NULL
  proposal_type TEXT NOT NULL     -- fact_candidate / profile_rebuild / model_claim /
                                  -- rule_candidate / graph_update / dedup_merge /
                                  -- supersede / expire_projection
  target_kind TEXT                -- 应用型提案必填
  target_id TEXT                  -- 应用型提案必填
  payload_json TEXT NOT NULL      -- 结构化，禁止自由指令文本
  source_observation_ids TEXT NOT NULL   -- JSON 数组
  source_evidence_ids TEXT NOT NULL      -- JSON 数组
  confidence REAL NOT NULL
  reasoning TEXT NOT NULL         -- 结构化理由（策略条目 + 证据计数）
  risk_level TEXT NOT NULL        -- low / high
  status TEXT NOT NULL            -- proposed / approved / rejected / applied /
                                  -- failed / rolled_back / expired
  approved_by TEXT                -- auto / user
  applied_at TEXT
  rollback_ref TEXT               -- 应用型提案 applied 后必填（INV-P3）
  idempotency_key TEXT NOT NULL
  UNIQUE (namespace, proposal_type, idempotency_key)
  created_at TEXT NOT NULL
```

## 4. 不变量 → 测试映射

| 编号 | 内容 | 验证方式 |
|---|---|---|
| INV-RR1 | 同 idempotency_key 重放复用已产出 proposal，不重复产出 | 单测：同 key 二次 propose 返回既有行 |
| INV-RR2 | interrupted run 可从 input_cursor 恢复 | 单测：cursor 保存与读取 |
| INV-RR3 | run 失败不污染业务表 | 单测：fail_run 后业务行零改动 |
| INV-P1 | high 提案 approved_by="auto" 非法 | 单测：approve(auto) 抛错 |
| INV-P2 | 同 payload_hash 幂等，不产生第二行 | 单测：重复 propose 返回同 proposal_id |
| INV-P3 | applied 必有 rollback_ref，空即阻断 | 单测 + apply 事务内强制 |
| INV-P4 | 无 evidence 的 fact_candidate confidence 不得高于低信任阈值 | 单测：propose 抛错 |
| INV-D1 | 高风险清单硬编码，配置不可缩小 | 单测：classify_risk 矩阵 |
| INV-B1 | rollback 只撤销派生投影，不动 memories 原始层 | E2E：rollback 后原记忆 content 不变 |
| INV-F3 | apply 失败事务回滚，业务零改动 | 单测：处理器抛错后 status=failed 且目标未变 |
| INV-F4 | rollback 后变更对 recall 不可见 | E2E |

## 5. 风险分级（硬编码，契约 §4.2 逐条落地）

高（恒人工确认）：`rule_candidate`（forbid/always/override）、覆盖用户偏好/纠正、删除/批量 forget、跨 namespace、敏感属性推断、外部行为、`model_claim` 首次 accepted。
低（白名单可 auto）：`expire_projection`、`graph_update`（reinforce 且有权重上限）、`dedup_merge`（强证据 ≥2 条 support）。
其余类型默认 high（fail-closed）。

## 6. 显式延期项（不做假绿）

| 项 | 去向 | 理由 |
|---|---|---|
| fact_candidate / profile_rebuild / model_claim / rule_candidate 的 apply 处理器 | 后续切片 | 目标一等表未建，apply 无处落地；propose 可产生但 apply fail-closed |
| consolidate()/memify 旧路径 → 提案策略逐个迁移与新旧对拍 | 后续切片 | 契约 §6：一次只迁移一个策略，需并行对拍确认 |
| 后台队列（容量/超时/重试计数） | 后续切片 | 最小闭环为同步显式触发；队列属运维项（契约 §5.3） |
| 异步侧 run/proposal parity | Backlog | 与 Phase 2 异步写入 API 同批 |
| target 存在性/snapshot 匹配校验的完整矩阵 | 本切片实现 target 存在性；snapshot 匹配完整矩阵 Backlog | 最小闭环先保证不 apply 到已消失目标 |

## 7. 测试与门禁计划

- 专项：`tests/evolution/test_reflection_proposal_phase4.py`（不变量矩阵）
- E2E：`tests/e2e/test_e2e_reflection_proposal.py`（真实用户 propose→apply→rollback 旅程 + INV-B1/F4）
- 回归：Phase 2 专项 + async/maintenance 邻近文件
- 静态：black / isort / flake8 / mypy（受影响文件）；radon 无 ≥21
- 全量门禁：Phase 4 收尾时独占重跑（同 Phase 2 口径）
