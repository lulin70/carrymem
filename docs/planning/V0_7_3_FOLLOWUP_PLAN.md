# CarryMem v0.7.3 跟进方案

> **版本**: v0.7.3 (PATCH 递增 — 修复/优化/重构，无新功能，遵循 SemVer)
> **基线**: v0.7.2 (commit 7b55c87, 2026-07-12)
> **来源**: [ASSESSMENT_D7_MATURITY_20260712.md](file:///Users/lin/trae_projects/carrymem/ASSESSMENT_D7_MATURITY_20260712.md) 第十节保留项
> **审核**: DevSquad V4.0.0 五角色并行审核 (architect/security/tester/coder/devops)

---

## 一、版本号决策

| 项 | 决策 | 理由 |
|----|------|------|
| 版本号 | **v0.7.3** (PATCH) | 4 项均为修复/优化/重构，无新功能。遵循 SemVer: "修复、重构、优化等没有新功能的工作只递增PATCH版本" |
| 非 v0.8.0 | 否决 | MINOR 递增仅用于向后兼容的功能新增，本次不满足 |

---

## 二、范围概览

| # | 编号 | 问题 | 类别 | 预估复杂度 |
|---|------|------|------|-----------|
| 1 | P1-1 | HMAC-CTR fallback cipher 不达标 | 安全修复 | 中 |
| 2 | P1-2 | input_validator regex 黑名单可绕过 | 安全评估 | 低 |
| 3 | P1-4 | recall update_access 每次读都写 (WAL 膨胀) | 性能优化 | 中 |
| 4 | P1-5 | 语义回退 N+1 LIKE 查询 | 性能优化 | 低 |

---

## 三、P1-1: HMAC-CTR fallback cipher 移除

### 3.1 问题分析

**当前状态**: `encryption.py` 提供两种加密后端:
- **Fernet** (AES-128-CBC + HMAC) — 需要 `cryptography` 包，符合 OWASP 标准
- **HMAC-CTR stream cipher** — 纯 Python fallback，docstring 自承 "weak security level"

**fallback 触发条件**: `cryptography` 包未安装时自动降级到 stream cipher。

**风险点**:
- `_encrypt_stream` (line 322-340) 使用 HMAC-SHA256 作为 PRF 生成 keystream + XOR，不是真正的 AES-CTR
- Python 级循环 `bytes(a ^ b for a, b in zip(data, keystream))` 性能差
- docstring 明确标注 "does NOT meet 2026 security standards"

**当前依赖状态**: `cryptography>=46.0.6` 在 `setup.py` 的 `extras_require["crypto"]` 中（可选依赖），不在 `install_requires` 中。

### 3.2 方案

**决策**: 将 `cryptography` 提升为硬依赖，移除 HMAC-CTR fallback。

**步骤**:
1. `setup.py`: 将 `cryptography>=46.0.6` 从 `extras_require["crypto"]` 移到 `install_requires`
2. `pyproject.toml`: 同步更新 `[project.dependencies]`
3. `encryption.py`: 
   - 删除 `_encrypt_stream`/`_decrypt_stream`/`_generate_keystream` (line 322-377)
   - 删除 `_check_fernet_availability` 中的 fallback 逻辑
   - `__init__` 中 `cryptography` 导入失败时直接 `raise EncryptionError` 而非降级
4. **数据迁移**: 检测现有数据库是否使用了 stream cipher 加密，提供迁移工具
   - stream cipher 密文格式: `base64(nonce + encrypted + auth_tag)`，可通过长度特征区分
   - 迁移脚本: 读取旧密文 → stream decrypt → fernet encrypt → 写回
5. 更新文档: README/INSTALL 说明 `cryptography` 为必装依赖

### 3.3 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 现有用户数据库用 stream cipher 加密，升级后无法解密 | **高** | 提供迁移脚本 + CLI `carrymem migrate-encryption` 命令 |
| `cryptography` 有 C 扩展依赖，部分平台安装困难 | 中 | `cryptography>=46.0.6` 已有预编译 wheel，覆盖主流平台 |
| CI 环境需安装 `cryptography` | 低 | 已在 `extras_require["crypto"]` 中，CI 已安装 |

### 3.4 验证计划

- 单元测试: `test_encryption.py` 删除 stream cipher 相关测试，新增 "无 cryptography 时 raise" 测试
- 集成测试: 端到端加密/解密流程仅使用 Fernet
- 迁移测试: 创建 stream cipher 加密的测试数据库，验证迁移脚本正确转换为 Fernet
- bandit: 确认无新增 HIGH severity 告警

### 3.5 回滚策略

若迁移脚本出现问题:
- v0.7.3.1 hotfix 恢复 fallback cipher (保留代码在 `git history` 中)
- 迁移脚本可逆向 (Fernet → stream cipher 也可实现)

---

## 四、P1-2: input_validator regex 黑名单评估

### 4.1 问题分析

**当前状态**: `input_validator.py` (509行) 使用 regex 黑名单检测 SQLi/XSS/path traversal。

**已知局限**:
- 编码绕过 (URL encoding, Unicode normalization)
- 注释绕过 (`/* */`, `--`)
- `~` 路径拦截 (已在 v0.7.2 修复中恢复，defense-in-depth)

**实际风险评估**:
- 存储层使用 SQLite **参数化查询**，SQLi 实际攻击面为零
- path traversal 的实际防御在 `_validate_file_path` (db_path 验证) 和 `InputValidator.validate_path` (内容路径验证) 两层
- regex 黑名单是**第三层防御**，不是唯一防线

### 4.2 方案

**决策**: 保留 regex 黑名单作为 defense-in-depth，**不引入专业 WAF 库**。

**理由**:
1. 实际攻击面为零 (参数化查询 + 路径验证两层已封堵)
2. 引入 WAF 库 (如 `bleach`, `sqlparse`) 增加 ~2-5MB 依赖，收益不成比例
3. regex 黑名单的价值在于"快速拒绝明显恶意输入"，而非"拦截所有攻击"
4. CarryMem 是本地运行的记忆系统，不暴露公网

**改进措施** (低成本):
1. 补充注释明确标注 "defense-in-depth layer 3, not primary defense"
2. 补充 URL encoding 检测 (`%2e%2e%2f` 等)
3. 添加 `sqlparse` 作为可选依赖用于 SQL 语句分析 (仅在 `classify_message` 等需要解析 SQL 的场景)

### 4.3 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| regex 可被绕过 | 低 | 参数化查询是主防御，regex 是辅助 |
| 新增 `sqlparse` 可选依赖 | 低 | 仅在 `classify_message` 使用，不影响核心功能 |

### 4.4 验证计划

- 单元测试: 新增 URL encoding 绕过测试用例
- 文档: 在 `input_validator.py` 头部注释中明确防御层级

---

## 五、P1-4: recall update_access WAL 膨胀优化

### 5.1 问题分析

**当前状态**: `recall_engine.py:270-328` — `recall_update_access` 方法在每次 recall 操作时:
1. 构建 `batch_updates` 列表
2. 执行 `conn.execemany()` 批量 UPDATE
3. 执行 `conn.commit()` 写入 WAL

**问题**: 每次 recall (读操作) 都触发写操作 (更新 `access_count` + `last_accessed_at` + `importance_score`)，导致:
- WAL 文件持续膨胀
- 频繁 checkpoint 压力
- 高频 recall 场景下性能下降

**约束**: `update_access=True` 是默认值，改为 `False` 会破坏 `last_accessed_at` 语义 (v0.7.2 修复中已验证)。

### 5.2 方案

**决策**: 引入 **throttled write** 机制 — 同一 memory 的 `last_accessed_at` 最多每 60 秒更新一次。

**设计**:
```python
class RecallEngine:
    _ACCESS_UPDATE_INTERVAL = 60  # seconds

    def recall_update_access(self, rows, update_access=True, ...):
        ...
        now = datetime.now(timezone.utc)
        for stored in rows:
            if update_access and self._should_update_access(stored, now):
                self.increment_access(stored, batch_updates, now_iso)
            results.append(stored)
        ...

    def _should_update_access(self, stored, now: datetime) -> bool:
        """Throttle: skip update if last_accessed_at is within _ACCESS_UPDATE_INTERVAL."""
        if stored.last_accessed_at is None:
            return True
        delta = (now - stored.last_accessed_at).total_seconds()
        return delta >= self._ACCESS_UPDATE_INTERVAL
```

**优势**:
- 保持 `update_access=True` 默认值 (向后兼容)
- `last_accessed_at` 语义不变 (仍记录最近访问时间，精度从秒级降为分钟级)
- WAL 写入频率降低 10-100x (取决于 recall 频率)
- 无需额外存储 (不需要 throttle 状态表)

**配置化**: `_ACCESS_UPDATE_INTERVAL` 通过 `CarryMemConfig` 可配置，默认 60 秒。

### 5.3 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| `last_accessed_at` 精度降低 (秒级→分钟级) | 低 | 对记忆系统而言，60秒精度足够 |
| 测试中需要等待 60 秒才能验证更新 | 中 | 测试中通过 config 设为 0 秒 (always update) |
| 高频 recall 场景下首次访问仍会写入 | 低 | 可接受 — 首次访问本就需要记录 |

### 5.4 验证计划

- 单元测试: 
  - `test_throttle_skips_recent_access`: 60秒内重复 recall 不触发 UPDATE
  - `test_throttle_allows_stale_access`: 超过 60 秒后 recall 触发 UPDATE
  - `test_throttle_configurable`: 通过 config 可调整间隔
- 性能测试: 1000 次 recall 操作的 WAL 文件大小对比 (throttled vs non-throttled)
- 回归测试: 现有 `test_last_accessed_at_updated` 在 `interval=0` 配置下仍然通过

### 5.5 回滚策略

将 `_ACCESS_UPDATE_INTERVAL` 设为 0 即可完全恢复原行为 (每次都更新)。

---

## 六、P1-5: 语义回退 N+1 LIKE 查询优化

### 6.1 问题分析

**当前状态**: `recall_engine.py:330-382` — `_semantic_recall` 方法:
1. **主路径** (line 351-352): 将所有扩展词组合为 `OR` FTS5 查询 — 已批量化 ✓
2. **回退路径** (line 364-374): 当组合查询结果 < limit 时，逐个扩展词执行 LIKE 查询 — **N+1** ✗

```python
# N+1 回退路径 (line 364-374):
if len(all_expanded_rows) < limit:
    for exp_query in valid_expansions:          # N 次循环
        if has_cjk(exp_query):
            like_rows = self._like_search(exp_query, ...)  # 每次一个查询
```

**影响**: 当扩展词有 5 个时，回退路径执行 5 次独立 LIKE 查询。

### 6.2 方案

**决策**: 将 N 次独立 LIKE 查询合并为 1 次 OR LIKE 查询。

**实现**:
```python
if len(all_expanded_rows) < limit:
    cjk_expansions = [e for e in valid_expansions if has_cjk(e)]
    if cjk_expansions:
        # 构建组合 LIKE 查询: WHERE content LIKE '%term1%' OR content LIKE '%term2%' ...
        combined_like_rows = self._combined_like_search(cjk_expansions, where_clause, params, limit)
        for row in combined_like_rows:
            row_id = row["id"] if hasattr(row, "__getitem__") else None
            if row_id and row_id not in seen_row_ids:
                seen_row_ids.add(row_id)
                all_expanded_rows.append(row)
                if len(all_expanded_rows) >= limit:
                    break
```

新增方法:
```python
def _combined_like_search(self, terms: List[str], where_clause: str, params: List, limit: int):
    """Batched LIKE search: combine multiple terms into a single OR query."""
    like_conditions = " OR ".join("content LIKE ?" for _ in terms)
    like_params = [f"%{t}%" for t in terms]
    query = f"SELECT * FROM memories WHERE ({like_conditions})"
    if where_clause:
        query += f" AND ({where_clause})"
    query += " LIMIT ?"
    return self._adapter._conn_mgr.get_connection().execute(query, like_params + params + [limit]).fetchall()
```

### 6.3 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 组合 LIKE 查询性能可能不如单个 LIKE (OR 短路) | 低 | SQLite 优化器对 OR LIKE 有索引优化；且 N=1 总比 N=5 好 |
| SQL 注入风险 (LIKE 参数) | 无 | 使用参数化查询，`?` 占位符 |
| 回退路径本身是低频场景 | 低 | 仅在 FTS5 结果不足时触发 |

### 6.4 验证计划

- 单元测试: 
  - `test_semantic_recall_batched_like`: 5 个 CJK 扩展词只触发 1 次 LIKE 查询
  - `test_semantic_recall_dedup`: 组合 LIKE 结果去重正确
- 性能测试: 5 扩展词场景下的查询次数对比 (5 → 1)
- 回归测试: 现有语义召回测试全部通过

---

## 七、实施顺序与依赖

```
P1-2 (input_validator 评估) ────────────┐
                                         ├──→ 无依赖，可并行
P1-5 (N+1 LIKE 批量化) ─────────────────┘

P1-4 (WAL throttle) ──→ P1-1 (HMAC-CTR 移除)
                         ↑
                    P1-4 先行，因为 P1-1 涉及数据迁移，
                    需要确保 throttle 不影响迁移过程中的读写
```

**推荐顺序**:
1. P1-2 + P1-5 (并行，低风险，快速完成)
2. P1-4 (中等风险，需测试验证)
3. P1-1 (高风险，需迁移脚本 + 充分测试)

---

## 八、版本一致性检查清单

v0.7.3 发布时需同步更新以下位置的版本号:
- [ ] `src/carrymem/__version__.py`
- [ ] `pyproject.toml`
- [ ] `setup.py`
- [ ] `VERSION` 文件 (如存在)
- [ ] `Dockerfile` ARG VERSION
- [ ] `README.md` 版本引用
- [ ] `CHANGELOG.md` 新增 v0.7.3 条目
- [ ] `server.json` / `smithery.yaml` 版本号
- [ ] `skill-manifest.yaml` (如存在)
- [ ] i18n 文档 (26 个文件)

**验证命令**: `grep -r "0.7.2" . --include="*.py" --include="*.toml" --include="*.md" --include="*.json" --include="*.yaml" | grep -v ".git/" | grep -v "node_modules/"`

---

## 九、测试计划

### 9.1 单元测试
- 每项变更新增 3-5 个测试用例
- 现有测试全部通过 (4331+ tests baseline)

### 9.2 集成测试
- P1-1: 加密迁移端到端测试
- P1-4: 高频 recall 场景下的 WAL 大小监控
- P1-5: 语义召回结果一致性验证

### 9.3 E2E 测试 (发布前必做)
- 模拟真实用户使用流程: 创建记忆 → recall → 更新 → backup → restore
- 验证 v0.7.2 数据库在 v0.7.3 上的兼容性 (特别是 P1-1 加密迁移)
- WAL 文件大小在 1000 次 recall 操作后不超过 10MB

### 9.4 性能基准
- recall 延迟 P95: 不超过 v0.7.2 基线 +10%
- WAL 文件大小: 比 v0.7.2 减少 50%+ (throttle 效果)

---

## 十、发布前 Gate

| Gate | 标准 | 阻断 |
|------|------|------|
| 测试 | 4331+ tests passed, 0 failed | ✅ 阻断 |
| 覆盖率 | ≥ 80% (v0.7.2 基线 80.77%) | ✅ 阻断 |
| flake8 | 0 errors | ✅ 阻断 |
| mypy | 0 errors | ✅ 阻断 |
| bandit | 0 HIGH severity | ✅ 阻断 |
| pip-audit | 0 vulnerabilities | ✅ 阻断 |
| E2E | 全部通过 | ✅ 阻断 |
| 版本一致性 | grep 检查所有位置 | ✅ 阻断 |
| CHANGELOG | v0.7.3 条目完整 | ✅ 阻断 |
| 迁移脚本 | P1-1 迁移脚本通过测试 | ✅ 阻断 |
| wheel 大小 | 不超过 v0.7.2 +5MB | ✅ 阻断 |
| 性能基准 | recall P95 不超过基线 +10% | ✅ 阻断 |
| 迁移 E2E | v0.7.2 加密 DB 在 v0.7.3 可迁移可读 | ✅ 阻断 |

---

## 十一、DevSquad 五角色审核共识 (2026-07-12)

### 审核结果汇总

| 项 | 架构师 | 安全 | 测试 | 开发 | DevOps | 共识 |
|----|--------|------|------|------|--------|------|
| P1-1 | CONDITIONS | CONDITIONS | CONDITIONS | CONDITIONS | CONDITIONS | **条件通过** |
| P1-2 | APPROVE | CONDITIONS | CONDITIONS | APPROVE | APPROVE | **条件通过** |
| P1-4 | CONDITIONS | APPROVE | CONDITIONS | CONDITIONS | CONDITIONS | **条件通过** |
| P1-5 | **REJECT** | **REJECT** | CONDITIONS | **REJECT** | APPROVE | **必须修正** |

### P1-5 阻断项修正 (3 票 REJECT — 架构师/安全/开发)

**问题**: 方案伪代码存在 4 个 bug:

1. **SQL 拼接错误**: `where_clause` 实际格式为 `"WHERE conditions"`，方案 `query += f" AND ({where_clause})"` 会生成 `AND (WHERE ...)` — 非法 SQL
2. **LIKE 注入**: 未调用 `escape_like()` + `ESCAPE '\\'`，`%`/`_`/`\` 被当通配符
3. **列遗漏**: 只查 `content`，丢失 `raw_text` + `original_message` 三列覆盖
4. **排序缺失**: 缺 `ORDER BY importance_score DESC, confidence DESC`

**修正方案** (对齐现有 `_like_search` line 472-487):

```python
def _combined_like_search(self, terms: List[str], where_clause: str, params: List, limit: int):
    """Batched LIKE search: combine multiple terms into a single OR query."""
    conn = self._adapter._conn_mgr.get_connection()
    # 每个词对三列生成 LIKE 条件，词间用 OR 连接
    like_parts = []
    like_params = []
    for term in terms:
        escaped = escape_like(term)
        like_parts.append(
            "(content LIKE ? ESCAPE '\\' OR raw_text LIKE ? ESCAPE '\\' "
            "OR original_message LIKE ? ESCAPE '\\')"
        )
        like_params.extend([f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"])
    like_clause = " AND (" + " OR ".join(like_parts) + ")"
    sql = f"""
        SELECT * FROM memories
        {where_clause}
        {like_clause}
        ORDER BY importance_score DESC, confidence DESC
        LIMIT ?
    """
    all_params = params + like_params + [limit]
    return conn.execute(sql, all_params).fetchall()
```

**语义变更声明** (须写入 CHANGELOG): 回退路径排序从"扩展词优先序"改为"importance_score 全局序"。

### P1-1 条件修正 (5 票 CONDITIONS)

| 条件 | 来源 | 修正 |
|------|------|------|
| 密文区分不可靠 | 架构师+安全 | 改用 Fernet 前缀 `gAAAAA` (version byte 0x80 base64) 判定，非长度特征 |
| 迁移脚本与删除顺序矛盾 | 开发 | 保留 `_encrypt_stream`/`_decrypt_stream` 到 `tests/helpers/legacy_cipher.py` 供迁移使用；生产代码中删除但迁移脚本 import from helper |
| `_decrypt_with_key` + `rotate_key` 断裂 | 开发 | `rotate_key` 的 `_re_encrypt` 闭包 (line 444-460) else 分支需同步清理，改为仅支持 Fernet |
| 迁移非原子 | 安全 | 迁移包在单事务内，失败回滚；迁移前 `VACUUM INTO` 物理备份 |
| 迁移明文泄露 | 安全 | 禁止 logger 打印 plaintext；内存中明文即时清理 |
| ≥5 现有测试 FAIL | 测试 | 明确清单: `test_security_crypto_upgrade.py` 中 `TestSecurityLevelAttributes`/`TestFallbackWarning`/`test_rotate_preserves_backend_type`/`test_is_active_and_backend_properties` 等；保留 golden fixture DB |
| CI fallback 路径缺 cryptography | DevOps | `ci.yml:71` fallback 路径补 `cryptography`；`optional-deps` job 的 `encryption` extras 将变空需清理 |
| SemVer 争议 | DevOps | 0.x.y 下无稳定性承诺，PATCH 可接受。CHANGELOG 显式标注"依赖变更: cryptography 从可选提升为必装" |

### P1-4 条件修正 (4 票 CONDITIONS)

| 条件 | 来源 | 修正 |
|------|------|------|
| `last_accessed_at` 类型可能为字符串 | 开发 | `_should_update_access` 增加类型守卫: 若为 str 先 `datetime.fromisoformat()` |
| throttle 跳过时内存增量也被跳过 | 开发 | 文档化: throttle 跳过时 `access_count`/`importance_score` 内存值不递增，下次 DB 读取时刷新 |
| `is_stored=True` 路径也需 throttle | 开发 | 两条路径 (is_stored True/False) 均应用 `_should_update_access` |
| now 参数注入便于测试 | 测试 | `_should_update_access(stored, now=None)`: now=None 时用 `datetime.now(timezone.utc)` |
| 解析异常 fail-open | 安全 | `last_accessed_at` 解析失败时返回 True (触发更新) |
| 环境变量支持 | DevOps | 新增 `CARRYMEM_ACCESS_UPDATE_INTERVAL` 环境变量，默认 60 秒 |
| SRP: 抽取 AccessTracker 类 | 架构师 | **否决** — 60 秒 throttle 逻辑仅 5 行，抽取为独立类属于过度设计。保持 RecallEngine 内部方法，通过 config 注入间隔 |

### P1-2 条件修正 (2 票 CONDITIONS)

| 条件 | 来源 | 修正 |
|------|------|------|
| URL encoding 检测不足 | 安全+测试 | 补充: double-encoding (`%252e`), Unicode 全角 (`．．／`), HTML entity (`&#46;`), RTL (`\u202e`) |
| sqlparse 与"不引入 WAF"表述冲突 | 架构师 | 澄清: sqlparse 非 WAF 库，仅用于 `classify_message` 的 SQL 语句解析。"不引入 WAF"指不引入 bleach/modsecurity 等 |
| symlink traversal | 安全 | `validate_path` 在 `.resolve()` 后增加 `path.is_symlink()` 拒绝 |

### 实施顺序修正

**原方案错误**: P1-4→P1-1 依赖理由"throttle 影响迁移读写"不成立 (架构师+开发一致指出)。

**修正后顺序** (基于风险隔离):
1. P1-2 + P1-5 (并行，低风险)
2. P1-4 (中等风险)
3. P1-1 (高风险，需迁移脚本 + 充分测试)

### 版本一致性清单补充 (DevOps)

遗漏项: `smithery.yaml`, `CLAUDE.md`, `docs/RULES_USER_MANUAL.md`

### release.yml 增强 (DevOps)

pre-release-test 需补: bandit + pip-audit + flake8 + mypy + E2E + 版本一致性 grep + 迁移脚本 E2E + wheel 大小检查 + 性能基准回归

覆盖率阈值统一: ci.yml 75% vs Gate 表 80% → 统一为 80%

---

## 十二、最终共识

**五角色审核结论**: APPROVE WITH CONDITIONS

- P1-5: 3 票 REJECT → 按第十一节修正后放行
- P1-1/P1-4/P1-2: 全部 CONDITIONS → 按第十一节条件修正后放行
- 版本号 v0.7.3 (PATCH): 用户决策，五角色接受 (0.x.y SemVer + CHANGELOG 标注)
- 实施顺序: P1-2+P1-5 → P1-4 → P1-1 (风险递增)

**共识达成**: 2026-07-12，五角色审核完成，方案修正后无阻断项。

---

*方案创建: 2026-07-12*
*审核完成: 2026-07-12*
*审核方式: DevSquad V4.0.0 五角色并行审核 (architect/security/tester/coder/devops)*
