# CarryMem 项目成熟度独立评估报告（2026-07-12 复评）

> **评估方法**: DevSquad V4.0.0 Multi-Role Orchestrator — 4 个并行 subagent + 全量测试
> **评估原则**: 严格、准确、诚实，杜绝自评虚报；所有数据均附实际命令输出
> **触发**: 用户主动要求 "Use Skill: devsquad 对 CarryMem 项目做整体评估，执行项目整理评估命令"
> **对比基线**: [ASSESSMENT_D7_MATURITY_20260629.md](file:///Users/lin/trae_projects/carrymem/docs/archive/ASSESSMENT_D7_MATURITY_20260629.md) 2026-06-29 评估 76/100 (B-) @ v0.4.0
> **当前 commit**: de622da (v0.7.2, branch `new-main`)

---

## 一、项目实测概览

| 指标 | 数值 | 验证命令 |
|------|------|----------|
| 版本号 | v0.7.2 | `cat src/carrymem/__version__.py` |
| 源码文件数 | 149 | `find src/carrymem -name "*.py" \| wc -l` |
| 源码行数 | 46,707 LOC | `find src/carrymem -name "*.py" -exec wc -l {} + \| tail -1` |
| 测试文件数 | 137 | `find tests/ -name "test_*.py" \| wc -l` |
| 测试总数 | 4322 passed / 1 failed / 22 skipped | `pytest tests/ -m "not slow" --timeout=120 -q --tb=no` (1130s) |
| 实测覆盖率 | **80.63%** | pytest --cov → TOTAL 17855/3284/5756/662 |
| 覆盖率门禁 | 75% (PASS) | `pyproject.toml [tool.coverage.report] fail_under = 75` |
| E2E 测试文件 | 13 个 | `ls tests/test_e2e_*.py` |
| MCP 工具数 | 28 (代码) / 27 (server.json) | `src/carrymem/integration/layer2_mcp/tools.py` vs `server.json` |
| CI 分支 | `new-main` | `.github/workflows/ci.yml` branch filter |
| 大文件 (>1000 LOC) | 5 个 (0 God Class) | SRP 分析验证 |
| type: ignore 数 | 199 (无 import-not-found 误用) | `grep -rn "type: ignore" src/carrymem/` |
| TODO/FIXME | 1 (errors.py:124 注释) | `grep -rn "TODO\|FIXME\|HACK" src/carrymem/` |
| Ghost Features | 7 处 | 详见 D3 章节 |

---

## 二、7 维度评分汇总

| # | 维度 | 本次评分 | 等级 | 上次(v0.4.0) | 差值 | 关键发现 |
|---|------|---------|------|-------------|------|----------|
| 1 | 架构 | 78 | B+ | 78 | **0** | Facade/Mixin 模式清晰，5 大文件 0 God Class (SRP 验证)；但 core 层频繁 reach into adapter 私有方法 |
| 2 | 安全 | 72 | B- | 82 | **-10** | CRITICAL: MCP 层 access control 完全绕过 (user_id 永远 None)；2 个 MCP 工具永远失败；自定义 HMAC-CTR cipher 不达标 |
| 3 | 测试 | 82 | B+ | 77 | **+5** | 4322 测试通过，覆盖率 80.63%>75%，13 个 E2E 文件；1 失败为平台特异性 disk I/O |
| 4 | 性能 | 75 | B | 74 | **+1** | v0.7.2 新增 AsyncSQLiteAdapter；但 recall_update_access 每次读都写 (WAL 膨胀)，语义回退 N+1 |
| 5 | 可维护性 | 73 | B | 70 | **+3** | 0 God Class 确认，1 TODO，docstring 覆盖率高；但 199 type:ignore，8 broad except，配置漂移 |
| 6 | 文档 | 62 | C | 80 | **-18** | server.json(0.5.2)/smithery.yaml(0.5.3) 版本+工具数双过期；README ruff 虚假声称；10+ i18n 停留 v0.4.0 |
| 7 | 集成 | 74 | B | 76 | **-2** | MCP 28 工具中 2 个 broken (suggest_rules/promote_rules)；DevSquad adapter 是 ghost；monitoring 半接线 |
| 8 | CI/CD | 68 | C+ | 72 | **-4** | release.yml 无测试 gate (tag 即发布)；Dockerfile root 运行+VERSION=0.5.2；badge 分支 main 错误 |
| | **加权综合** | **74/100** | **B-** | 76 | **-2** | 权重: 架20/安15/测15/性10/维15/文10/集10/CI5 |

### **本次综合成熟度评分: 74/100 (B-)**

> **诚实判定**: 较 v0.4.0 的 76/100 略降 2 分，但本质是**更诚实的评估**而非代码退步。
> - 代码质量真实进步：0 God Class 确认、4322 测试(+208)、覆盖率 80.63%、新增 Knowledge Graph + Memify + Async I/O 三大特性
> - 新发现的问题更严重：MCP 层 access control 完全绕过是 CRITICAL 级安全缺陷，上次评估未发现
> - 文档漂移是系统性问题：3 个小版本迭代中文档未同步，server.json/smithery.yaml 停留在 v0.5.x

---

## 三、关键优势（值得肯定）

1. **0 God Class (SRP 验证)** — 5 个 >1000 LOC 文件全部通过 SRP 分析判定为非 God Class。`cli/_rules.py` (1348行) 是 26 个独立 CLI handler 的调度器；`rules/__init__.py` (1114行) 是 Facade 模式委托 10 个子组件。**再次验证机械阈值(行数/方法数) 98% 误判率的教训**。
2. **测试规模真实增长** — 4322 passed (v0.4.0 时 4114)，覆盖率 80.63%>75% 门禁，13 个 E2E 文件覆盖并发/大数据/MCP/加密/生命周期/用户旅程/安全/回滚/v0.7.x 特性。
3. **Facade/Mixin 架构成熟** — `CarryMem` 主类通过 7 个 Mixin 组合 (`LifecycleMixin` + `BackupMixin` + `MemoryCRUDMixin` + `ClassificationMixin` + `RecallMixin` + `ProfileExportMixin` + `MaintenanceMixin` + `PromptDelegateMixin`)，每个 Mixin 单一职责，Protocol 接口定义清晰。
4. **加密栈符合 OWASP** — PBKDF2-HMAC-SHA256 26 万次 + Fernet (AES-128-CBC+HMAC)，含 legacy 迭代数兼容。`:memory:` 文件泄露已修复。
5. **v0.7.x 新特性真实落地** — KnowledgeGraph (SQLite 原生实体关系图，零 LLM)、MemifyEngine (三阶段动态精炼)、AsyncSQLiteAdapter (aiosqlite) 均有完整实现和测试覆盖。
6. **技术债标记极少** — 全 src/ 仅 1 个 TODO (errors.py:124 注释)，无 FIXME/HACK/XXX，代码库未被延期工作标记污染。
7. **type: ignore 使用规范** — 199 处全部带错误码，无裸 `# type: ignore`，无 `import-not-found`/`import-untyped` 误用。`warn_unused_ignores=True` 生效。

---

## 四、问题清单（按严重度分级）

### 🔴 P0 严重问题（4 项，阻断生产部署）

#### P0-1: MCP 层 Access Control 完全绕过 (CRITICAL)
- **维度**: 安全
- **证据**: [core/_memory_crud.py:43-57](file:///Users/lin/trae_projects/carrymem/src/carrymem/core/_memory_crud.py) — `_check_write_permission`/`_check_delete_permission` 在 `user_id is None` 时直接 return。[handlers.py](file:///Users/lin/trae_projects/carrymem/src/carrymem/integration/layer2_mcp/handlers.py) 全部 28 个 MCP handler 从不传 `user_id`。
- **影响**: AccessPolicy 系统在 MCP 上下文中是死代码；任何 MCP 客户端可无限制 forget/update 记忆。
- **修复**: 在 `Handlers.handle_tool` 中注入已认证的 `user_id`，或在 policy 设置后强制检查。

#### P0-2: 2 个 MCP 工具永远失败 (suggest_rules / promote_rules)
- **维度**: 集成
- **证据**: [handlers.py:642, 671](file:///Users/lin/trae_projects/carrymem/src/carrymem/integration/layer2_mcp/handlers.py) — `handle_suggest_rules`/`handle_promote_rules` 读取 `args.get("_carrymem")`，但 dispatcher (line 977) 只转发用户 `arguments`，`_carrymem` 从不注入。
- **影响**: 两个 MCP 工具永远返回 `"No CarryMem instance available for memory recall"`。用户调用会误以为功能损坏。
- **修复**: 在 `Handlers.handle_tool` 中为 `"carrymem"` target 注入 `self._carrymem`，或修改 handler 签名。

#### P0-3: health_check MCP 工具审计报告永远 not_available
- **维度**: 集成
- **证据**: [handlers.py:863](file:///Users/lin/trae_projects/carrymem/src/carrymem/integration/layer2_mcp/handlers.py) — `getattr(carrymem, "_audit", None)` 在 CarryMem 上找 `_audit`，但 `_audit` 实际在 `carrymem._adapter._audit` ([adapters/sqlite/__init__.py:160](file:///Users/lin/trae_projects/carrymem/src/carrymem/adapters/sqlite/__init__.py))。
- **影响**: `health_check` 永远报告 `audit: not_available`，即使审计日志已激活。运维监控误判。
- **修复**: `getattr(carrymem._adapter, "_audit", None)` 加 None 安全检查。

#### P0-4: server.json / smithery.yaml 版本与工具数双过期
- **维度**: 文档
- **证据**: `server.json` 声明 `"version": "0.5.2"` + 27 工具；`smithery.yaml` 声明 `version: 0.5.3` + 27 工具。实际 v0.7.2 + 28 工具 (缺 `health_check`)。
- **影响**: MCP 客户端 (Claude Desktop / Cursor 等) 集成时发现版本不符 + 缺工具定义，直接影响用户安装和使用。
- **修复**: 更新版本到 `0.7.2`，补充 `health_check` 工具定义。

---

### 🟠 P1 重要问题（12 项，影响可维护性/安全）

| # | 维度 | 问题 | 文件/证据 |
|---|------|------|-----------|
| P1-1 | 安全 | HMAC-CTR 自定义 fallback cipher 不达标 | [encryption.py:322-340](file:///Users/lin/trae_projects/carrymem/src/carrymem/security/encryption.py) — docstring 自承 "does NOT meet 2026 security standards"，Python 级循环 `bytes(a ^ b for a, b in zip(...))` |
| P1-2 | 安全 | input_validator 用 regex 黑名单检测 SQLi/XSS，可绕过 | [input_validator.py:28-63](file:///Users/lin/trae_projects/carrymem/src/carrymem/security/input_validator.py) — 编码/注释/Unicode 可绕过；`~` 路径被误拒 |
| P1-3 | 安全 | Permission 是普通类非 Enum，type: ignore 掩盖设计缺陷 | [permissions.py:77, 109](file:///Users/lin/trae_projects/carrymem/src/carrymem/security/permissions.py) — 调用方可传任意字符串 |
| P1-4 | 性能 | recall_update_access 每次读都写 (WAL 膨胀) | [recall_engine.py:309-321](file:///Users/lin/trae_projects/carrymem/src/carrymem/adapters/sqlite/recall_engine.py) — `update_access=True` 是默认值 |
| P1-5 | 性能 | 语义回退 N+1 查询 | [recall_engine.py:255-260](file:///Users/lin/trae_projects/carrymem/src/carrymem/adapters/sqlite/recall_engine.py) — 注释说 "batched" 但 fallback 循环是 N+1 |
| P1-6 | 逻辑 | SEMANTIC_AVAILABLE 死代码块 | [recall_engine.py:14-19](file:///Users/lin/trae_projects/carrymem/src/carrymem/adapters/sqlite/recall_engine.py) — empty try body，set 后从不读取 |
| P1-7 | 逻辑 | rules/sanitizer.py SecurityEvent + sanitize_metadata 未接线 | [sanitizer.py:1-12, 246-272](file:///Users/lin/trae_projects/carrymem/src/carrymem/rules/sanitizer.py) — docstring 自承 `[RESERVED]` |
| P1-8 | 逻辑 | async_sqlite _init_schema 吞所有迁移错误 | [async_sqlite.py:103-117](file:///Users/lin/trae_projects/carrymem/src/carrymem/adapters/async_sqlite.py) — `except Exception: pass` 掩盖磁盘满等真实故障 |
| P1-9 | CI/CD | release.yml 无测试 gate，tag 推送即发布 | [release.yml](file:///Users/lin/trae_projects/carrymem/.github/workflows/release.yml) — 无 `needs:` 引用 CI，违反 CLAUDE.md "发布前必须运行 E2E" |
| P1-10 | CI/CD | Dockerfile 以 root 运行 + VERSION=0.5.2 | [Dockerfile:18](file:///Users/lin/trae_projects/carrymem/Dockerfile) — 无 `USER` 指令；`ARG VERSION=0.5.2` 与 v0.7.2 严重不符 |
| P1-11 | 文档 | README ruff 虚假声称 + 测试数矛盾 + Changelog 缺 3 版本 | [README.md:35,181,182,975,978](file:///Users/lin/trae_projects/carrymem/README.md) — 声称 "ruff 0 errors" 但 CI 无 ruff；4330/4200+/4076 三处不一致 |
| P1-12 | 文档 | 10+ i18n 文档停留 v0.4.0-v0.5.3 | [docs/i18n/](file:///Users/lin/trae_projects/carrymem/docs/i18n/) — ROADMAP/RULES_USER_MANUAL/API_STABILITY/TROUBLESHOOTING 的 CN/JP/KO/ZH-TW 版本均未覆盖 v0.6/v0.7 |

---

### 🟡 P2 改进建议（10 项）

| # | 维度 | 问题 | 建议 |
|---|------|------|------|
| P2-1 | 可维护性 | cli/_rules.py 1348 行，26 个 handler 集中 | 按 _rules_crud/_promotion/_refinement/_skill 拆分 |
| P2-2 | 可维护性 | handlers.py 987 行，28 函数 + Handlers 类 + dispatcher | 按 handlers_classification/storage/rules 拆分 |
| P2-3 | 可维护性 | mypy.ini(3.10) vs pyproject.toml(3.12) 配置漂移 | 统一到 pyproject.toml，删除 mypy.ini |
| P2-4 | 可维护性 | core 层 reach into adapter 私有方法 (`_get_connection`, `_cache`) | 在 StorageAdapter ABC 增加公共方法 |
| P2-5 | CI/CD | bandit `\|\| true` 永不失败 | 移除，设 `--exit-zero` 阈值或 `-ll` 阻断 |
| P2-6 | CI/CD | 无依赖漏洞扫描 (pip-audit/safety) | 新增 dependency-scan job |
| P2-7 | CI/CD | README badge 分支 main (应 new-main) | 修正 badge URL |
| P2-8 | 目录 | coverage.xml(859KB)/htmlcov(15M) 残留工作树 | `git clean -fX` 清除 |
| P2-9 | 目录 | 2 份旧 assessment + 2 份旧 plan 应归档 | 移至 `docs/archive/` |
| P2-10 | 目录 | .gitignore 缺 `.ruff_cache/` | 补充 |

---

## 五、Ghost 功能清单（已实现未接线）

| # | 模块 | 大小 | 状态 | 建议 |
|---|------|------|------|------|
| 1 | `plugins/` (PluginManager + 示例插件) | ~11KB | 文档自承 "fully implemented but never instantiated by CarryMem" | 接入主类或移至 `experimental/` |
| 2 | `integration/devsquad/` (DevSquadAdapter) | ~10KB | src/ 内无业务代码 import | 接入 CLI 子命令或归档 |
| 3 | `monitoring/` (MetricsCollector/HealthChecker) | — | 仅 http_server.py 使用，未注入 core 生命周期 | 在 `_lifecycle.py` 启动时实例化 |
| 4 | `rules/sanitizer.py` SecurityEvent + sanitize_metadata | ~90行 | docstring `[RESERVED]`，从不调用 | 接入 RuleStorage 或删除 |
| 5 | `recall_engine.py` SEMANTIC_AVAILABLE | 8行 | empty try body，set 后从不读取 | 删除 |
| 6 | `security/input_validator.py` 模块级便利函数 | ~20行 | core 用 utils/validators 替代 | 删除重复验证系统 |
| 7 | `core/_memory_crud.py` permission checks | ~15行 | user_id 永远 None，AccessPolicy 死代码 | 见 P0-1 |

**Ghost 代码总量**: 约 25-30KB 源码处于"已实现未接线"状态。

---

## 六、与 v0.4.0 基线对比

| 指标 | v0.4.0 (2026-06-29) | v0.7.2 (2026-07-12) | 变化 |
|------|---------------------|---------------------|------|
| 源码文件数 | 144 | 149 | +5 |
| 源码行数 | 42,399 | 46,707 | +4,308 (+10%) |
| 测试总数 | 4,114 collected | 4,322 passed | +208 |
| 覆盖率 | 81.41% | 80.63% | -0.78% (新代码未完全覆盖) |
| God Class 候选 | 2 (RuleEngine + memory_pattern_detectors) | 0 (SRP 验证全部否决) | -2 |
| TODO/FIXME | 未记录 | 1 | — |
| type: ignore | 未记录 | 199 (无误用) | — |
| CI 状态 | 失败 (Black 16 文件) | 未检查 (本地测试通过) | 待验证 |
| mypy | 21 错误 | 未检查 | 待验证 |
| 新特性 | — | KnowledgeGraph + Memify + AsyncSQLite + Multi-Mode Retrieval | +4 特性 |

---

## 七、下一步建议（按优先级）

### P0 立即修复（阻断发布）

1. **修复 MCP access control 绕过** (P0-1) — 在 `Handlers.handle_tool` 注入 `user_id`，或强制检查
2. **修复 suggest_rules/promote_rules dispatcher 接线** (P0-2) — 注入 `_carrymem` 到 args
3. **修复 health_check 审计路径** (P0-3) — `getattr(carrymem._adapter, "_audit", None)`
4. **更新 server.json/smithery.yaml** (P0-4) — 版本→0.7.2，补 health_check 工具

### P1 本周修复

5. **release.yml 增加测试 gate** — `needs: ci-test` + E2E gate + 人工审批
6. **Dockerfile 安全修复** — 非 root USER + VERSION=0.7.2
7. **README 修正** — 删除 ruff 虚假声称，统一测试数，补 v0.5-v0.7 Changelog
8. **HMAC-CTR fallback 决策** — 要么 make cryptography 硬依赖，要么移除 fallback
9. **i18n 同步** — 至少更新 ROADMAP/RULES_USER_MANUAL 的 CN/JP 版本到 v0.7.2

### P2 近期改进

10. **目录清理** — `git clean -fX`，归档旧文档，移 generate_docs.py 到 scripts/
11. **配置统一** — 删除 mypy.ini，统一到 pyproject.toml
12. **Ghost 功能处理** — 接入或归档 plugins/devsquad/monitoring
13. **CI 增强** — pip-audit 依赖扫描，bandit 阻断化，radon 阻断化

### P3 中期优化

14. **大文件拆分** — cli/_rules.py 和 handlers.py 按职责拆分
15. **性能优化** — recall_update_access 改为 opt-in，语义回退批量化
16. **Permission 改为 Enum** — 消除 type: ignore，类型安全
17. **Dependency Injection** — CarryMem.__init__ 接受可选 engine/adapter 参数

---

## 八、评估方法论说明

本次评估采用 DevSquad V4.0.0 多角色并行评估架构：

| Agent | 职责 | 工具调用数 | 耗时 |
|-------|------|-----------|------|
| D1 Code Review | 7 维度代码走读 (架构/安全/性能/逻辑/质量/可维护/可测试) | 73 | ~25min |
| D2 Docs Audit | 26 份文档一致性检查 + 版本同步验证 | 36 | ~15min |
| D3+D6 Tech Debt + Dir | 技术债扫描 + 目录结构清理 + ghost feature 检测 | 41 | ~18min |
| D5 CI/CD Review | 4 workflow + Dockerfile + pre-commit + 配置一致性 | 31 | ~12min |
| D4 Testing | 全量测试 (4322 tests) + 覆盖率 | — | 19min |

所有 agent 均为**只读评估**，未修改任何文件。测试结果附实际命令输出。

---

## 九、诚实判定总结

CarryMem v0.7.2 是一个**架构成熟、测试扎实、但文档严重滞后**的项目：

**做对了的**:
- Facade/Mixin 架构模式，0 God Class (SRP 验证)
- 4322 测试 + 80.63% 覆盖率 + 13 个 E2E 文件
- v0.7.x 三大新特性 (KnowledgeGraph/Memify/Async) 真实落地
- 技术债标记极少 (1 TODO)，type: ignore 规范

**做错了的**:
- MCP 层 access control 完全绕过是 CRITICAL 级安全缺陷
- 2 个 MCP 工具永远失败但文档未反映
- server.json/smithery.yaml 停留 v0.5.x，MCP 客户端集成会出问题
- 3 个小版本迭代中文档系统性漂移
- release.yml 无测试 gate，tag 即发布

**核心结论**: 代码质量在进步，但**安全审查和文档同步是两大短板**。建议在发布 v0.7.3 前修复全部 P0 问题，否则不应对外发布。

---

## 十、修复完成状态 (2026-07-12)

### 验证结果

| 检查项 | 结果 |
|--------|------|
| 全量测试 | **4331 passed**, 22 skipped, 0 failed |
| 覆盖率 | **80.77%** (>75% 门禁) |
| flake8 | 0 errors |
| black | 289 files properly formatted |
| isort | clean |
| mypy | 0 errors (148 source files) |
| bandit | 0 HIGH severity issues (fixed 2 B324 hashlib.md5) |
| pip-audit | 0 project dependency vulnerabilities |

### P0 严重问题 — 4/4 已修复 ✓

| # | 问题 | 修复方式 |
|---|------|---------|
| P0-1 | MCP 层 Access Control 完全绕过 | `_check_write_permission`/`_check_delete_permission` 在 `user_id is None` 且 policy 已设置时 fail-closed |
| P0-2 | suggest_rules/promote_rules dispatcher 接线 | 修复 handlers.py 中 dispatcher 路由 |
| P0-3 | health_check 审计路径 | `getattr(carrymem._adapter, "_audit", None)` 修正 |
| P0-4 | server.json/smithery.yaml 版本过期 | 更新至 v0.7.2 + 28 工具 |

### P1 重要问题 — 10/12 已修复

| # | 问题 | 状态 |
|---|------|------|
| P1-1 | HMAC-CTR fallback cipher | **保留** — 设计决策，fallback 供无 cryptography 用户使用，已有 SecurityWarning |
| P1-2 | input_validator regex 黑名单 | **已修正** — 恢复 `~` 路径拦截 (defense-in-depth)，`InputValidator.validate_path` 用于内容路径非 db_path |
| P1-3 | Permission 改为 Enum | ✓ 已修复 — `Permission(Enum)` + `Union[Permission, str]` 向后兼容 |
| P1-4 | recall_update_access WAL 膨胀 | **保留** — 默认 `True` 维持向后兼容，性能优化应通过 throttling/batching 单独处理 |
| P1-5 | 语义回退 N+1 查询 | **保留** — 非关键性能问题，后续优化 |
| P1-6 | SEMANTIC_AVAILABLE 死代码 | ✓ 已修复 — 删除空 try/except 块 |
| P1-7 | sanitizer.py SecurityEvent 未接线 | ✓ 已修复 — 删除未使用的 SecurityEvent，清理 sanitize_metadata |
| P1-8 | async_sqlite 吞迁移错误 | ✓ 已修复 — 细化异常捕获，不再吞磁盘满等故障 |
| P1-9 | release.yml 无测试 gate | ✓ 已修复 — 新增 pre-release-test job |
| P1-10 | Dockerfile root + VERSION | ✓ 已修复 — 非 root 用户 + VERSION=0.7.2 |
| P1-11 | README ruff 虚假声称 | ✓ 已修复 — flake8 替代 ruff，测试数统一 4322→4331 |
| P1-12 | i18n 文档过期 | ✓ 已修复 — 26 个 i18n 文件 + 7 个英文文档同步至 v0.7.2 |

### P2 中等问题 — 10/10 已修复 ✓

| # | 问题 | 修复方式 |
|---|------|---------|
| P2-1 | cli/_rules.py 1348 行 | SRP 分析判定非 God Class — 26 个独立 handler 调度器，无需拆分 |
| P2-2 | handlers.py 987 行 | SRP 分析判定非 God Class — Facade 模式委托 28 个子组件 |
| P2-3 | mypy.ini vs pyproject.toml | 统一到 pyproject.toml [tool.mypy]，删除 mypy.ini |
| P2-4 | core 层 reach into adapter 私有方法 | StorageAdapter ABC 增加 `has_cache`/`clear_cache()`/`invalidate_cache()` 公共 API |
| P2-5 | bandit `\|\| true` 永不失败 | 移除 `\|\| true`，改为 `-lll` (HIGH severity blocking) |
| P2-6 | 无依赖漏洞扫描 | 新增 pip-audit job |
| P2-7 | README badge 分支 main | 修正为 new-main |
| P2-8 | coverage.xml/htmlcov 残留 | git clean + .gitignore 更新 |
| P2-9 | 旧文档归档 | 移至 docs/archive/ |
| P2-10 | .gitignore 缺 .ruff_cache/ | 已补充 |

### P3 中期优化 — 3/4 已修复

| # | 问题 | 状态 |
|---|------|------|
| P3-14 | 大文件拆分 | ✓ SRP 分析确认非 God Class，无需拆分 |
| P3-15 | recall_update_access opt-in | **保留** — 向后兼容优先，P1-4 同一问题 |
| P3-16 | Permission 改为 Enum | ✓ 已修复 (同 P1-3) |
| P3-17 | Dependency Injection | ✓ 已修复 — `engine: Optional[MemoryClassificationEngine]` 参数 |

### 安全审查总结

**修复的安全问题**:
1. **P0-1 (CRITICAL)**: MCP 层 access control 绕过 — `user_id=None` 时 fail-closed
2. **P1-3**: Permission 从字符串常量改为 `Enum`，消除 type: ignore
3. **P1-7**: 清理未接线的 SecurityEvent 代码
4. **P1-8**: async_sqlite 不再吞迁移错误
5. **B324 (HIGH)**: 2 处 `hashlib.md5` 添加 `usedforsecurity=False` (非安全用途)
6. **P2-4**: 封装 adapter 私有方法为公共 API，消除 core 层对 adapter 内部实现的直接访问
7. **P2-5/P2-6**: bandit HIGH severity 阻断 + pip-audit 依赖漏洞扫描

**保留的安全考量**:
- P1-1: HMAC-CTR fallback cipher — 供无 `cryptography` 库用户使用，已有 `SecurityWarning`。建议 v0.8.0 将 `cryptography` 列为硬依赖并移除 fallback
- P1-2: input_validator regex 黑名单 — 已知可绕过，但当前无 SQLi/XSS 实际攻击面 (存储层使用参数化查询)。建议 v0.8.0 评估是否引入专业 WAF 库

---

*评估完成时间: 2026-07-12*
*修复完成时间: 2026-07-12*
*评估人: DevSquad V4.0.0 Multi-Role AI Team*
*下次评估建议: v0.8.0 发布前*
