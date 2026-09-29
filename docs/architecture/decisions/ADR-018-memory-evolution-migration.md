# ADR-018: 记忆演进 SQLite 迁移策略（additive + ledger + fail-closed）

## 状态: 已采纳（Accepted 2026-09-28，Gate 0 批准）
## 日期: 2026-09-28
## 决策者: 项目负责人（Gate 0 批准）
## 操作手册: [MEMORY_EVOLUTION_MIGRATION_RECOVERY.md](../../runbooks/MEMORY_EVOLUTION_MIGRATION_RECOVERY.md)

---

## 上下文

记忆演进需要新增最多 9 张表（evidence/observations/facts/experiences/profiles/model_claims/conflicts/reflection_runs/reflection_outputs）。现有迁移模式（`migrate_v080`/`migrate_v090`/`migrate_v100`，ADR-013 先例）是"幂等检查 + ALTER/CREATE"，但缺少：

1. **Ledger**：迁移历史无统一记录（靠列存在性检查推断），无法表达"执行过但失败""执行到一半"等状态，中断恢复依赖推断；
2. **Checksum**：SQL 内容被篡改（或文件与执行版本不一致）时无法检测；
3. **Ready 门禁**：迁移失败时的服务行为未形成硬契约（共识文档 DevOps 阻断项："readiness 只代表端口打开，不代表 schema 完整"）；
4. **演练记录**：发布前的迁移/恢复演练没有标准化手册。

2026-09-26 教训（项目级）：**"从文件里抽某样东西再校验"的门禁必须补"这样东西还在吗"的反向守护**——迁移门禁同理：不能只校验"列存在"，必须校验"ledger 声称的状态与实际 schema 一致"。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 沿用幂等检查模式** | 逐表检查列/表存在性 | 无新机制 | 无法可靠恢复、无法防篡改、失败语义弱 |
| **B: 外部迁移工具（alembic 等）** | 引入框架 | 功能全 | 新依赖，违背核心轻量与零外部服务原则；SQLite 方言适配成本 |
| **C: 内建 migration ledger + 独立事务 + fail-closed** ✅ | `carrymem_migrations` 表记录 id/checksum/status/时间 | 自洽、可恢复、可审计、无新依赖 | 需要自研 ledger 逻辑（约百行级） |

## 决策

采用方案 C：

1. **Ledger 表 `carrymem_migrations`**：`(migration_id PK, checksum, status, started_at, completed_at, error_text)`；执行前先查 ledger——已成功则跳过（幂等），失败则拒绝服务。
2. **单迁移单事务**：SQLite DDL 事务性保证中断即回滚；ledger 记录与 DDL 同事务提交。
3. **Checksum fail-closed**：迁移 SQL 文本哈希与 ledger 不一致 → 拒绝执行并告警（防篡改，负向测试 MIG-9）。
4. **Ready 门禁**：存在未完成/失败的 migration → `/readyz` 拒绝 ready（解密失败、审计失败同级 fail-closed）。
5. **Additive only**：不重命名不删除既有列；新表允许空表启用；旧版本程序兼容承诺（D7）建议为"旧程序可打开新库"。
6. **Backfill 不在 migration 内**：历史数据补 evidence link 用独立可恢复任务（分页 + cursor + dry-run），避免长事务锁库。
7. **发布前演练强制**：真实规模副本库 + 三个故障场景恢复演练，记录写入 runbook §7。

## 后果

### 正面
- 中断恢复从"推断"变为"查表"；
- 篡改可检测；失败即 fail-closed，杜绝"半迁移状态对外服务"；
- 与现有迁移函数（migrate_v100 模式）平滑衔接，无新依赖。

### 负面
- 每次迁移多一次 ledger 写入（可忽略）；
- ledger 自身需要被迁移门禁守护（反向守护：ledger 声称成功但表缺失 → 拒绝 ready）。

## 实现参考（Gate 0 批准后）
- `src/carrymem/adapters/sqlite/schema.py`（ledger 表 + v200/v210/v220 迁移）
- `src/carrymem/integration/layer2_mcp/http_server.py`（/readyz 接入迁移状态）
- `tests/migration/`（MIG-1~9）
