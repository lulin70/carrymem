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
| S8 | **consolidate() 检测提案化（契约 §6 第二个迁移策略）**：检测层原样复用 legacy `consolidate()` 引擎（零漂移，含 `entries_to_dicts()` 共享规范化）；输出转提案——`to_supersede` → `supersede` 提案（**恒高风险，人工审批**）、`to_forget` + below-floor `to_decay` → `expire_projection` 提案（低风险，可自动应用）、非 below-floor `to_decay` 无提案（legacy 实为 no-op，对拍保持一致）；门面 `reflect_consolidation()` | ✅ 已实现 + **对拍通过** |

### S8 修复的两个真实产品缺陷（测试驱动发现）

1. **INV-P2 幂等键缺 target（设计缺陷）**：幂等键原为 `sha256(payload_json)`；consolidation 场景下多个不同 target 共享同一 `{"expires_at": ...}` payload → 第 2 个起全部被误判为重复提案（多候选只建 1 个提案）。已改为 `sha256(payload|target_kind|target_id)`——同 payload 应用到不同 target 是不同提案。
2. **legacy consolidate 的 to_supersede 从未生效（静默失效）**：`hasattr(adapter, "supersede")` 在 Phase 2 将原语改名为 `supersede_memory(old, new)` 后恒为 False，dedup 检测结果被静默跳过。已修复为优先调用 `supersede_memory(older_key, newer_key)`（保留旧单参方法 fallback）。

### S8 对拍证据（孪生库，按内容对齐——storage_key 含插入时间戳，跨库 key 必然不同）

```text
test_dup_pair_supersede_proposals_are_high_risk: 重复对 → supersede 提案且恒 high/proposed；偏好重复被保留（不提案）
test_forget_becomes_expire_proposal_not_delete: to_forget → expire 提案；below-floor to_decay → expire 提案；
  非 below-floor to_decay 无提案（对齐 legacy no-op）；检测阶段零删除
test_auto_apply_expires_low_risk_and_keeps_high_risk_proposed: expire 自动应用（expires_at 落库）、
  supersede 提案保持 proposed（INV-P1）；全程零物理删除
test_idempotent_replay_reuses_runs_and_proposals: 二次运行复用双 run（INV-RR1）、提案数不变（INV-P2）、applied 为空
test_twin_db_legacy_and_proposal_paths_agree: 孪生库对拍——legacy 实际 superseded 集 == 提案 supersede 目标集；
  legacy 物理删除集 == 提案 expire 目标集；效果按契约 §6 有意不同（删除 vs 可回滚 expiry）
验证：tests/evolution/test_reflection_proposal_phase4.py 46 passed + maintenance/consolidation/memify 回归全绿；
black/isort/flake8/mypy（164 source files）/radon 全绿
```

遗留策略（dedup_merge 语义合并、consolidate_p1/p2 提案化）按 §6 纪律逐个迁移，见 §6 显式延期项。

> **审计诚实记录（S8 调试过程排除项）**：对拍测试一度失败，探针依次证伪了"陈旧 WAL 快照""连接池轮换""删除未提交"三个假设（文件级裸连接读证实删除已正确提交）。最终根因是测试自身的比较错误——对"已物理删除的 legacy 行"事后查 content 恒为空；已改为 seed 时快照 key→content 映射再比较。产品删除/提交路径无缺陷。

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
| reflection.py 全部写方法补 file_lock | 后续切片（Phase 4 并发收尾） | 现用 BEGIN IMMEDIATE（前置取写锁 + busy_timeout）已是安全形态，调用方当前单线程；全量不变量"所有 raw-connection 写事务持 file_lock"在下一切片补齐 |

### 6.1 全量门禁并发失败根因闭环（2026-10-04）

Phase 4 两次全量门禁分别失败于 `test_concurrent_mixed_read_write` 与 `test_concurrent_writes_from_multiple_threads`（`OperationalError: database is locked`，code=5 SQLITE_BUSY）。按 Phase 2 readiness §6.1 承诺独立立项，**未放宽任何断言**。三轮受控探针（`/tmp/probe_concurrent_lock*.py`、`/tmp/probe_trace.py`，含 sqlite errorcode 捕获、连接 `in_transaction` 转储、`set_trace_callback` 语句级追踪）定位出**两个叠加机制**：

**机制一：file_lock 不变量被 Phase 2/3 新增写路径绕过**。设计上 `_db_write_locks[path]`（进程级 RLock）应串行化同库全部写事务，但 observations/conflicts/evidence/knowledge_graph/`_bump_repetition_count`/`supersede_by_keys` 等经 `get_raw_connection()` 的写路径未持锁，与 file_lock 持有者并发竞争。探针 3 实锤：round 结束仍有连接 `in_transaction=True`（泄漏写事务持有 WAL 写锁），首个等待者耗尽 10s busy_timeout 后，**后续写者 26~500ms 即失败**（WAL shm 锁路径不咨询 busy handler）。部分失败路径吞掉 sqlite3.Error 后既不 commit 也不 rollback（如 `_apply_supersede_db_update` 第一条 UPDATE 成功、第二条失败），泄漏事务由此固化。
修复：adapter 新增公共 `write_lock` 属性；上述全部写事务持 `file_lock`（RLock 可重入，嵌套安全）；所有吞掉点补 rollback；`store_batch`/`delete_batch` 的 deferred `BEGIN` 对齐为 `BEGIN IMMEDIATE`（与 schema/reflection 惯例一致，杜绝 deferred 读-升级写快照冲突形态）。

**机制二：WAL 读侧瞬时 BUSY（语句级追踪定位）**。classify 内部召回（冲突候选搜索）的 `SELECT * FROM memories ...` 在并发写入（FTS+vector BLOB 使 WAL 每 1000 页默认阈值反复触发 checkpoint/重置）下，`walTryBeginRead` 无法锁定稳定 read-mark 而瞬时 BUSY——此路径 busy_timeout 不生效。修复（SQLite 官方实践，分层）：`busy_timeout` 10s→30s（与 connect timeout 对齐）；`wal_autocheckpoint` 1000→4000 页（env 可调 `CARRYMEM_WAL_AUTOCHECKPOINT_PAGES`）降低 checkpoint churn；`classify_and_remember`/`recall_memories` 入口加有界重试（3 次、指数退避，仅对类名为 OperationalError 且含 locked/busy 的瞬时错误，其余原样上抛；按异常类名匹配因 vector 路径使用 pysqlite3 驱动、异常类与 stdlib 不同）。

验证：并发 e2e 修复前 6 轮 1 挂 → 修复后 **6/6 全绿**；evolution/reflection/concurrent/adapter 专项 212 passed；knowledge_graph 专项修复 `FakeConnMgr` 测试替身缺 `file_lock` 属性（生产契约扩展同步替身，断言未动）后 35 passed。全量门禁终态见 §7。

## 7. 测试与门禁计划

- 专项：`tests/evolution/test_reflection_proposal_phase4.py`（不变量矩阵）
- E2E：`tests/e2e/test_e2e_reflection_proposal.py`（真实用户 propose→apply→rollback 旅程 + INV-B1/F4）
- 回归：Phase 2 专项 + async/maintenance 邻近文件
- 静态：black / isort / flake8 / mypy（受影响文件）；radon 无 ≥21
- 全量门禁：Phase 4 收尾时独占重跑（同 Phase 2 口径）
