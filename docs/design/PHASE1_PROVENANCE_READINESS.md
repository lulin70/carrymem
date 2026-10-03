# Phase 1（Provenance 基础）实现就绪清单

> **版本**：v0.1
> **日期**：2026-09-30
> **性质**：Gate 0 批准后的 Phase 1 出口检查单；本清单本身不授权任何代码修改
> **前置**：[Gate 0 批准](CARRYMEM_MEMORY_EVOLUTION_CONSENSUS.md) + 8 项决策拍板完成

---

## 1. Phase 1 目标（回顾）

主方案 §12：**任意派生对象可追溯至原始来源**。交付：

- `memory_evidence_links` 表 + 写入 API；
- `source_kind`、snapshot hash、derived 状态；
- 删除/失效（unsupported）策略；
- 现有 Memify、SemanticAggregator、版本链接入来源关系。

Phase 1 **不包含**：Observation 写入路径（Phase 2）、ConflictRecord（Phase 2）、Proposal 状态机（Phase 4）、RecallPlan（Phase 5）。

---

## 2. 启动前置条件（全部勾选后才可动代码）

- [x] Gate 0 获项目负责人明确批准（**2026-09-28 批准，8 项决策按契约文档建议默认执行**，见共识文档 §4）；
- [x] 8 项决策结论回写到四份契约文档的"待批准"标记处，去除 draft 状态（2026-09-28 完成）；
- [x] 相关 ADR（014/015/016/017/018）状态从 Proposed 改为 Accepted（2026-09-28 完成）；
- [x] [测试计划](../testing/MEMORY_EVOLUTION_TEST_PLAN.md) 中 Phase 1 相关 INV 的测试要点已冻结（§3.1/3.2/3.6）；
- [x] 当前 `new-main` CI 全绿，无未发布 tag 遗留（实现提交前复核）。

## 2.1 实现状态（2026-09-30，代码已完成；质量门禁已完成隔离复核）

| # | 清单项 | 状态 | 位置 |
|---|---|---|---|
| 1 | `migrate_v200`：ledger + `memory_evidence_links`（UNIQUE 含 namespace） | ✅ | `adapters/sqlite/schema.py` |
| 2 | `StorageAdapter`/`ProvenanceClient` 协议 additive 方法 | ✅ | `adapters/base.py`、`adapters/sqlite/__init__.py` |
| 3 | `derive_facts` 写 provenance + `source_layer="memify_derived"` | ✅ | `layers/memify.py` |
| 4 | `aggregated_from(_hashes)` → derived_from links | ✅ | `layers/semantic_aggregator.py`、`core/_prompt_delegate.py` |
| 5 | retain source_kind 标注（user_statement/user_correction） | ✅ | `core/_classification.py` |
| 6 | forget 级联 unsupported 标注（单删+批删） | ✅ | `adapters/sqlite/crud.py`、`adapters/sqlite/evidence.py` |
| 7 | metrics：`evidence_link_*` / `evidence_derived_unsupported` | ✅ | `adapters/sqlite/evidence.py` |
| 8 | tests/migration + tests/evidence（32 项） | ✅ | `tests/migration/`、`tests/evidence/` |
| 9 | async provenance schema/API/级联 parity（evidence 表、查询、unsupported cascade） | ✅ | `adapters/async_sqlite.py` |

实现期发现的契约修正：`UNIQUE` 约束**必须包含 namespace**（否则跨 namespace 的同名对象对会互相顶掉，违反 INV-E1），契约文档 §2.1 已同步更新。

---

## 3. 文件级实现清单（预计触碰点）

| # | 文件 | 改动 | 对应不变量 |
|---|---|---|---|
| 1 | `src/carrymem/adapters/sqlite/schema.py` | `migrate_v200`：`memory_evidence_links` 表 + UNIQUE/索引；ledger 前置表若 D7 批准则同批落地 | MIG-1~9 |
| 2 | `src/carrymem/adapters/base.py` | `StorageAdapter`/Protocol 增加 evidence link 抽象方法（additive） | INV-E1~E3 |
| 3 | `src/carrymem/layers/memify.py::derive_facts` | 派生结果写 `derived_from` evidence link + source_kind=inference + candidate 状态 | INV-R2/E3/E4 |
| 4 | `src/carrymem/layers/semantic_aggregator.py` | `aggregated_from` 同步写 evidence links（metadata 字段保留兼容投影） | INV-E3/E5 |
| 5 | `src/carrymem/core/_memory_crud.py` | retain 语义标注（source_kind 写入点）；冲突候选登记钩子占位 | INV-R2/R5/R6 |
| 6 | `src/carrymem/core/_maintenance.py` 或删除路径 | `forget_memory` 级联触发 unsupported 标记 | INV-E4 |
| 7 | `src/carrymem/monitoring/` | `evidence_links_total`、`derived_unsupported_total` 埋点（按可观测性规范 §2 的产生者表） | OBS 系列 |
| 8 | `tests/evidence/`（新目录） | INV-E1~E5 单元/集成测试 | — |
| 9 | `tests/migration/`（新目录） | MIG-1~9 | — |
| 10 | `tests/integration/` 或 `tests/e2e/` | INV-F1 端到端追溯 + 真实 metrics 对照 | INV-F1 |

**禁止触碰**（Phase 1 范围外）：`recall_engine.py` 排序逻辑、`build_context()`、规则晋升行为、`consolidation.py` 副作用路径。

---

## 4. 兼容性红线

1. Stable API（API_STABILITY §2）签名与返回结构零变更；
2. `memories` 表与 FTS/Graph/Vector 既有结构零变更；
3. metrics 既有 series 语义零变更（`recall`/`classify_and_remember` 计数行为不因 evidence 写入改变）；
4. 迁移遵循 [ADR-018](../architecture/decisions/ADR-018-memory-evolution-migration.md)：ledger + 单事务 + fail-closed + 先备份；
5. 不执行历史数据一次性 backfill（lazy 策略，Phase 3 处理旧数据投影）。

---

## 5. 完成标准（Phase 1 出口 = Gate 1 就绪）

- [x] INV-E1~E5、INV-R1/R2/R3/R4/R6、INV-F1 相关专项测试绿；
- [x] MIG-1~9 相关专项测试绿；
- [x] derive_facts 与 SemanticAggregator 产出均有 evidence link（受控证伪：删除写入点 → 测试 FAIL）；
- [x] 删除来源记忆 → 派生对象转 unsupported 的端到端验证；
- [x] 新 metrics 有真实 HTTP/MCP E2E 对照证据（对照组 → 动作 → series 出现）；
- [x] 八项本地门禁全绿（见 §5.1：2026-09-30 runtime isolation 落地后，`ci_local_check.py` 全部门禁在临时 venv + 隔离 runtime 下真实执行通过）；
- [x] 文档同步：主方案 §12 Phase 1 状态、CHANGELOG（Unreleased 段）、契约文档回填实现位置。

### 5.1 当前质量证据与未闭环项（2026-09-30 更新：CI/runtime 隔离已闭环）

**Runtime isolation（本节新增，2026-09-30 落地）：**

- `scripts/ci_local_check.py` 新增临时 runtime root：所有 gate 子进程统一继承 `HOME`、`CARRYMEM_CONFIG_DIR`、`CARRYMEM_CONFIG_FILE`、`CARRYMEM_DB_PATH`、`CARRYMEM_DATA_PATH`、`CARRYMEM_CACHE_DIR`、`CARRYMEM_LOG_DIR`、`CARRYMEM_BACKUP_DIR`、`CARRYMEM_LOCK_FILE`，与 venv 一起随 `TemporaryDirectory` 退出清理；隔离失败时 gate 照常暴露失败，不存在假绿路径。
- 隔离实现期修复两个真实问题（均以日志为证）：
  1. **pip 镜像继承**：覆盖 `HOME` 会让 pip 读不到用户级 `pip.conf`（本机为清华 TUNA 镜像），disposable venv 安装回退官方 PyPI 后 `rich` 下载失败。修复为 `resolve_pip_index_url()` 把宿主 index-url 显式注入 `PIP_INDEX_URL`；
  2. **HOME symlink 归一**：macOS 系统临时目录位于 `/var → /private/var` 符号链接之后，未 resolve 的 HOME 会让 `expanduser('~')` 与 `Path.resolve()` 对同一目录产生两种拼写，3 个路径校验测试失败（`test_tilde_expansion`、`test_safe_path_passes`、`test_valid_temp_path`）。修复为 runtime root 取 `Path(temp_dir).resolve()`（真实路径；GitHub `runner.temp` 本就是真实路径，no-op）。修复后 3 项单独复核通过，未改任何测试断言。
- `.github/workflows/ci.yml` test job、`release.yml` pre-release-test job、`nightly.yml` slow-tests / vector-tests job 使用同一套 `${{ runner.temp }}` 隔离变量约定（GitHub-hosted runner 每次运行均为全新 VM，`runner.temp` 天然一次性）。
- ci.yml / release.yml 的 test 步骤前新增「Run Phase 1 provenance blocking tests」阻塞步骤（`tests/migration/ tests/evidence/`），Phase 1 专项不再混在全量里被动覆盖。
- 隔离环境验证（`mktemp -d` + 上述九个变量，现有 `.venv` 执行）：
  - `tests/migration/ tests/evidence/`：**32 passed**；
  - `tests/e2e/`（not slow）：**245 passed**；
  - 曾受默认数据库污染的 `tests/test_core_protocols.py` + `tests/test_main_entry.py`：**54 passed**（readiness 旧记录中的 4 个失败项在隔离下全部消失，确认根因是环境污染而非 Phase 1 代码）。
- **完整独立门禁闭环（2026-09-30 实测，`ci_local_check.py` 全量输出存档）**：disposable venv + 隔离 runtime 下八项阻塞门禁全部通过——`4939 passed, 10 skipped, 77 deselected`（13m30s），coverage `83.27%`（floor 80%），flake8/black/isort/mypy/radon/version-consistency/swallowed-assert 均 OK。
- 遗留观察项（不阻塞 Phase 1 出口）：ci.yml 安装 fallback 中 `--no-deps ... || true` 仍可能掩盖 fallback 安装失败（主安装成功时不触发，风险有限）；已记入后续收紧项。

**此前质量证据（保留）：**

- 隔离专项结果：迁移/evidence/真实用户生命周期与并发 E2E `57 passed`；预算与上下文回归 `110 passed`；HTTP/MCP metrics E2E `4 passed`。
- 隔离非慢全量结果：`4944 passed, 1 skipped, 77 deselected`；4 个失败集中在既有默认数据库损坏路径（`test_core_protocols.py` 3 项、`test_main_entry.py` 1 项）。同类测试在临时 `HOME`、`CARRYMEM_CONFIG_DIR`、`CARRYMEM_DB_PATH`、`CARRYMEM_DATA_PATH` 下单独复核均通过，因此不归因于 Phase 1 变更。
- 另一轮全量结果中的 10 个 vector 相关失败来自可选 vector 依赖/模型与旧测试条件（`memory_vectors` 不存在、模型不可用、临时路径校验），不涉及 Phase 1 Provenance 路径；Phase 1 专项与真实用户 E2E 不依赖 vector 搜索。
- migration/backup/restore 临时演练已复核：`PRAGMA integrity_check=ok`、ledger `v200_evolution_foundation/success`、备份计数一致、恢复后 recall 成功。
- `flake8`、`black`、`isort`、`mypy`、version-consistency、swallowed-assert、radon 均通过；完整 `ci_local_check` 因临时 venv 安装阶段无法访问外部包源，未取得可重复的独立 venv 结果。
- 默认用户数据库曾造成全量回归污染；该环境问题不能被记为 Phase 1 代码回归。提交前仍需保留上述隔离结果，并不得把“全量门禁全绿”宣称为已完成。
- `max_tokens=2000` 当前只完成候选选择层验证，尚未完成客户需求验收；最终 prompt hard gate、真实 tokenizer 校准、Recall@5/10 质量评估属于 Phase 5，不在本 Phase 1 范围内。

---

## 6. 风险与回退

| 风险 | 缓解 |
|---|---|
| evidence 写入放大 SQLite 写压力 | derive_facts/aggregate 批量路径批量写 + 幂等 UNIQUE 去重；必要时每策略开关（feature flag 默认开，可关） |
| 迁移在生产库失败 | ADR-018 fail-closed + runbook §4 恢复流程 + 发布前 rehearsal |
| 新旧双轨漂移（metadata vs evidence） | metadata 字段冻结为兼容投影；评审检查"新代码不得以 metadata 为唯一 provenance" |
| Phase 1 范围蔓延 | 本清单 §3 之外的文件改动需回到 Gate 评审，不允许顺手实现 Phase 2+ 内容 |
