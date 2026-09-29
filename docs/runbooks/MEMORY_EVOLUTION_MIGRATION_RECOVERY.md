# SQLite 迁移与恢复 Runbook（Memory Evolution Migration & Recovery）

> **版本**：v0.1-draft
> **日期**：2026-09-28
> **状态**：Phase 0 Runbook 草案，待 Gate 0 批准；迁移代码落地（Phase 2 schema）后按本文执行演练
> **适用范围**：记忆演进新增表族（evidence/observations/facts/experiences/profiles/model_claims/conflicts/reflection_runs/reflection_outputs）的 additive 迁移与故障恢复
> **关联文档**：[RELEASE_RUNBOOK.md](../RELEASE_RUNBOOK.md)（发布流程）、[测试计划 MIG-1~9](../testing/MEMORY_EVOLUTION_TEST_PLAN.md)

---

## 1. 迁移原则（不可协商）

1. **Additive only**：不重命名、不删除 `memories` 及任何既有列；新表可为空表启用。
2. **Ledger 记账**：每次迁移记录 `migration_id`、时间、checksum（SQL 文本哈希）、状态；先查 ledger 再执行，天然幂等。
3. **Fail-closed**：迁移失败必须阻止服务 ready，**禁止**记 warning 后继续（沿用共识文档 DevOps 阻断项）。
4. **先备份**：任何迁移前创建可验证备份（见 §3）。
5. **旧程序兼容承诺**（待批准决策 D7）：建议"旧版本程序打开新库不受影响"（新表不被旧代码触碰）；"新库直升跨版本"允许（ledger 支持连续执行）；最终承诺范围以 Gate 0 为准。

---

## 2. 迁移内容清单（Phase 2 落地时以此为准）

```text
migrate_v200_evolution_foundation
  ├─ memory_evidence_links     （含 UNIQUE 幂等约束与两个索引）
  ├─ memory_observations       （含 TTL 索引）
  └─ ledger 记录 + checksum
migrate_v210_knowledge_objects
  ├─ memory_facts / memory_experiences / memory_profiles / memory_model_claims
migrate_v220_reflection
  ├─ memory_conflicts / memory_reflection_runs / memory_reflection_outputs
```

约束：

- 每个 migration 是**独立事务**（SQLite DDL 事务性），失败整体回滚；
- `migration_id` 命名延续现有 `migrate_v100()` 模式（ADR-013 先例：列被占用则递增版本号）；
- checksum 写入 ledger：SQL 文本与执行时哈希不一致 → fail-closed（防篡改，测试 MIG-9）；
- 大型 backfill（历史数据补 evidence link）**不在** migration 内执行——用独立可恢复任务（lazy/backfill job，分页 + cursor + dry-run）。

---

## 3. 标准迁移流程（操作者手册）

### 3.1 迁移前检查

```bash
# 1. 确认服务已停止写入（本地单实例：进程退出即可）
# 2. 磁盘空间 ≥ 数据库体积 × 2（备份 + WAL 余量）
df -h <db_dir>

# 3. 记录迁移前状态（用于恢复验证）
sqlite3 <db_path> "PRAGMA integrity_check;"
sqlite3 <db_path> "SELECT COUNT(*) FROM memories;"
sqlite3 <db_path> "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
```

### 3.2 创建可验证备份

```bash
# 在线安全备份（WAL 感知）
sqlite3 <db_path> ".backup '<backup_path>'"

# 验证备份可用性（必须通过，否则中止迁移）
sqlite3 <backup_path> "PRAGMA integrity_check;"
sqlite3 <backup_path> "SELECT COUNT(*) FROM memories;"   # 与迁移前一致
```

### 3.3 执行迁移

```bash
# 程序启动时自动执行；手动触发（如 CLI 维护命令，Phase 2 交付）
carrymem migrate --db <db_path> --dry-run   # 先演练：只校验，不写入
carrymem migrate --db <db_path>             # 正式执行
```

### 3.4 迁移后验证

```bash
# 1. ledger 完整
sqlite3 <db_path> "SELECT migration_id, status, checksum, completed_at FROM carrymem_migrations ORDER BY rowid;"

# 2. 新表存在且可为空
sqlite3 <db_path> "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'memory_%' ORDER BY name;"

# 3. FTS/Graph/Vector 一致性（MIG-7）
sqlite3 <db_path> "SELECT (SELECT COUNT(*) FROM memories) AS m, (SELECT COUNT(*) FROM memories_fts) AS f;"

# 4. 完整性
sqlite3 <db_path> "PRAGMA integrity_check;"

# 5. 旧 API 冒烟：recall_memories / classify_and_remember 各一次真实调用
```

**全部通过才算迁移完成**；任一步失败 → §4 恢复流程。

---

## 4. 故障场景与恢复

### 4.1 场景 A：迁移执行中途中断（进程崩溃 / kill）

```text
表现     ledger 无该 migration 记录（或状态 running 未完结）
影响     SQLite DDL 事务保证：未提交的 DDL 已回滚，库处于迁移前状态
恢复     ① 确认 integrity_check 通过
         ② 重新启动 → 迁移自动重放（幂等，ledger 缺失即重跑）
         ③ 重放前仍先做新备份
验证     MIG-4 测试项；重放后走 §3.4 全套验证
```

### 4.2 场景 B：迁移失败（checksum 不符 / DDL 错误 / 约束冲突）

```text
表现     服务拒绝 ready（fail-closed），日志含 migration_id 与错误摘要
影响     无数据损坏（单事务回滚）
恢复     ① 禁止跳过或手工改 ledger（唯一例外见 §4.4）
         ② 修复触发条件（磁盘满 / 版本不匹配 / 损坏的旧结构）
         ③ 重新执行 §3.3
验证     服务 ready 后 MIG-5 场景回归
```

### 4.3 场景 C：迁移成功但数据异常（一致性校验失败）

```text
表现     §3.4 第 3/4 步失败：FTS 行数不符 / integrity_check 失败
恢复     ① 立即停止服务（勿继续写入）
         ② 从 §3.2 备份恢复：
            cp <backup_path> <db_path>
         ③ 删除 ledger 中该 migration 记录（仅此场景允许）→ 修复根因 → 重新迁移
         ④ 恢复后必须执行 E2E-6（backup → migration → restore → recall 完整性）
验证     用户内容、版本链、图谱关系、语义召回四项逐一比对
```

### 4.4 场景 D：需要回滚到旧版本程序

```text
前提     决策 D7 承诺旧程序可开新库（additive 保证）
操作     旧版本程序直接打开即可——新表对其透明
若失败   （旧程序仍报错）恢复备份 + 使用旧版本程序 + 提交缺陷（承诺范围需修正）
```

---

## 5. 发布前演练要求（Gate 6 必过）

| 演练 | 内容 | 通过标准 |
|---|---|---|
| rehearsal-1 | 用真实规模副本库（≥1 万条记忆）执行 §3 全流程 | 全部验证通过，耗时记录 |
| rehearsal-2 | 演练 §4.1/4.2/4.3 三个故障场景 | 每个场景按手册可恢复，数据零丢失 |
| rehearsal-3 | 0.11.2 库直升 + 旧 API 冒烟 + E2E-6 | 内容/版本/关系/语义一致 |
| rehearsal-4 | dry-run 与正式执行结果一致 | 无副作用差异 |

演练记录追加到本文 §7（含日期、库规模、结果、操作者）。

---

## 6. 运维注意事项

- WAL 模式库的备份必须用 `.backup` 命令或 `VACUUM INTO`，禁止直接 cp 活跃库文件（WAL 未合并导致数据不完整）；
- 迁移期间禁止其他进程打开同一库（busy_timeout 沿用现有 PRAGMA 配置）；
- `carrymem_migration_total{migration_id, result}` metrics 是迁移可观测的唯一权威来源；告警规则见[可观测性规范](../design/MEMORY_EVOLUTION_OBSERVABILITY.md) §6；
- 禁止在未备份的库上做任何手工 schema 变更（包括"顺手加个索引"）。

---

## 7. 演练记录

| 日期 | 库规模 | 演练项 | 结果 | 操作者 | 备注 |
|---|---|---|---|---|---|
| （待迁移代码落地后填写） | | | | | |
