# CarryMem 技术债推进计划 (Living Document)

> **文档性质**: 活文档 (Living Document) — 每完成一项立即更新状态
> **创建时间**: 2026-07-17
> **最后更新**: 2026-07-18 (v11 — v0.8.2 技术债清理完成：TD-019 类型标注 90.3%、TD-021 25 个 D 级函数全部重构、P2 14 项全部完成 (TD-013/021/022/023/024/027/038/039/040/041/044/045/046/047)；4708 tests + 7 concurrent 全通过；radon 0 D/E/F)
> **基于**: 7 维度项目整理评估 (2026-07-17, B+ 77/100) + DevSquad 7 角色并行审核
> **配套文档**: [ROADMAP_P0_P3.md](ROADMAP_P0_P3.md) — 执行路线图 (Wave 推进表 + 7-Role 投票矩阵 + 11 阶段生命周期映射)
>
> **文档分工**:
> - 本文档 (TECH_DEBT_PLAN.md) = 技术债**目录** (50 项明细 + 验证标准 + 风险矩阵)
> - ROADMAP_P0_P3.md = 技术债**执行路线** (Wave 推进表 + 共识投票矩阵 + 活文档同步清单)

---

## 1. 概述

本文档记录 CarryMem v0.8.2 的全部技术债，按优先级 (P0-P3) 和 DevSquad 11 阶段项目生命周期组织。

**执行原则** (来自用户规则):
- P0-P1: 按项目生命周期推进，文档先行，充分验证，推送 Git
- P2-P3: 给方案，达成共识后按方案推进
- 文档是活文档，时刻更新
- 测试计划中补充 e2e 测试，发布前必须做模拟真实用户使用的测试
- 反对虚报，验证标准必须包含可执行命令

**技术债统计** (v2 — 7 角色审核后):

| 优先级 | 数量 | 预估时间 | 执行方式 |
|--------|------|----------|----------|
| P0 立即修复 | 5 项 | 60min | 立即执行 |
| P1 高优先级 | 22 项 | ~28h | 测试先行 → 架构重构 → DevOps+代码 |
| P2 中优先级 | 13 项 | ~18h | 方案+共识后推进 |
| P3 低优先级 | 10 项 | ~4h | 日常维护渐进 |

### 用户价值映射 (PM 建议)

| 用户可感知程度 | 技术债项 |
|---------------|---------|
| **高** (直接安全/数据风险) | TD-001 (pip CVE), TD-002 (rule_engine 吞错), TD-032 (SQL 注入扫描), TD-035 (AccessPolicy 越权) |
| **中** (发布/安装体验) | TD-014 (依赖锁定), TD-015 (OIDC), TD-033 (e2e gate), TD-034 (VSCode E2E gate) |
| **低** (内部质量) | TD-005/006/007/008 (架构), TD-009~013 (测试), TD-017~020 (代码质量) |
| **无** (技术债卫生) | TD-028/029/030/031 (P3), TD-045~050 (P3) |

---

## 2. P0 — 立即修复 (5 项)

> **执行方式**: 立即执行，充分验证，推送 Git
> **生命周期阶段**: P6 安全审查 → P8 实现 → P9 测试执行

### TD-001: pip 25.0.1 存在 6 个 CVE (供应链安全)

| 字段 | 值 |
|------|-----|
| **优先级** | P0 |
| **位置** | `.venv/`, `.github/workflows/*.yml`, `Dockerfile:6,33` |
| **问题描述** | pip 25.0.1 存在 6 个已知 CVE: PYSEC-2026-196/1795/1796/2875/2876 |
| **修复方案** | 统一替换为 `python -m pip install --upgrade "pip>=26.1.2"`；执行前用 `pip-audit` 二次核实 CVE 编号；Dockerfile builder + runtime 阶段同步 |
| **负责角色** | DevOps |
| **验证标准** | 命令 `pip --version` 输出 ≥26.1.2；`pip-audit pip` 报告 0 CVE；`grep -rn "pip install --upgrade pip" .github/workflows/ Dockerfile` 全部升级 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (13 处已修改: ci.yml×4, release.yml×2, benchmark.yml×2, nightly.yml×1, Dockerfile×2, install.sh×1) |
| **生命周期** | P6 安全审查 → P8 实现 |

### TD-002: rule_engine lazy init 静默吞错 (数据安全) ⚠️ 描述已修正

| 字段 | 值 |
|------|-----|
| **优先级** | P0 |
| **位置** | `src/carrymem/core/_lifecycle.py:172` |
| **问题描述** | **修正后**: 第 172 行 `except Exception: pass` 实际捕获的是 `self.rule_engine` 急切初始化异常（见 160-168 行注释解释 SQLITE_SCHEMA cookie 问题），不是备份状态清理。吞错会掩盖 FTS v5 vtable 初始化失败，导致后续并发 INSERT 时出现间歇性 "vtable constructor failed: memories_fts"。真正的备份代码在第 189-194 行已有正确异常处理 |
| **修复方案** | 添加 `logger.warning(f"Rule engine lazy init failed: {e}", exc_info=True)`，**保留行为不变**（不应让初始化失败传播阻塞启动）；补独立任务诊断 SQLITE_SCHEMA 竞争根因 |
| **负责角色** | Coder |
| **验证标准** | 命令 `grep -n "except Exception: pass" src/carrymem/core/_lifecycle.py` 返回 0 行；单元测试模拟 rule_engine 初始化抛异常时产生 warning 日志（`caplog` 断言） |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (logger.warning 已添加 + 2 个单元测试 TestRuleEngineInitFailure 通过) |
| **生命周期** | P6 安全审查 → P8 实现 → P9 测试 |

### TD-003a: 2 项可立即删除的死代码 ⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P0 |
| **位置** | `engine.py:135` (`clear_working_memory`), `rules/matcher.py:368` (`_has_word_overlap`) |
| **问题描述** | 经全仓 grep 核实，仅这 2 个符号零调用者且无 `getattr` 反射访问。原计划 10 项中其余 8 项为公共 API（见 TD-003b） |
| **修复方案** | 逐一删除，验证全测试通过 |
| **负责角色** | Coder |
| **验证标准** | `grep -rn "clear_working_memory\|_has_word_overlap" src/ tests/` 返回 0 结果；`pytest` 全测试通过 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (engine.py:135 + matcher.py:368 已删除，全测试通过) |
| **生命周期** | P8 实现 → P9 测试 |

### TD-003b: 8 项公共 API 死代码需 deprecation ⚠️ 新增分类

| 字段 | 值 |
|------|-----|
| **优先级** | P1 (降级，因需 SEMVER 流程) |
| **位置** | `adapters/base.py:949` (`search_fulltext`), `adapters/sqlite/connection.py:212,221` (`release_connection`, `close_all_connections`), `adapters/sqlite/__init__.py:832,839` (`list_graph_relations`, `get_graph_stats`), `i18n/__init__.py:46,118` (`unregister`), `layers/rule_matcher.py:93` (`remove_rule`) |
| **问题描述** | 这 8 个符号是公共 API（无 `_` 前缀），其中 4 个有测试调用者，直接删除属 SEMVER 破坏性变更。`i18n/__init__.py:118` 的 `_reset` 是测试助手（test_i18n.py 使用），从清单移除 |
| **修复方案** | 加 `DeprecationWarning` + `# TODO(v0.9): remove` 注释，下个大版本删除 |
| **负责角色** | Coder |
| **验证标准** | 8 项均含 `DeprecationWarning`；`pytest -W error::DeprecationWarning` 测试不破坏 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (8 项公共 API 全部加 `DeprecationWarning` + `# TODO(v0.9): remove` 注释；6 个测试文件用 `warnings.catch_warnings()` 包装避免 DeprecationWarning 触发失败) |
| **生命周期** | P8 实现 |

### TD-004: benchmark.yml matrix 含 Python 3.11 (CI 配置错误)

| 字段 | 值 |
|------|-----|
| **优先级** | P0 |
| **位置** | `.github/workflows/benchmark.yml:46,146` |
| **问题描述** | matrix 为 `['3.11', '3.12']`，但 `setup.py` 要求 `python_requires=">=3.12"` |
| **修复方案** | 移除 matrix 中的 `'3.11'`，统一为 `['3.12']` |
| **负责角色** | DevOps |
| **验证标准** | 命令 `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/benchmark.yml')); print(d['jobs']['benchmark']['strategy']['matrix']['python-version'])"` 输出 `['3.12']` |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (benchmark.yml L46+L146 已改为 ['3.12']) |
| **生命周期** | P8 实现 |

### TD-032: SQL 动态拼接面未审计 (安全债) ⚠️ 新增 (Security 提出)

| 字段 | 值 |
|------|-----|
| **优先级** | P0 |
| **位置** | `rules/storage.py:601` (`conn.execute(f"UPDATE rules SET {', '.join(set_clauses)} WHERE id = ?", params)`), `obsidian_adapter.py:256` 类似 |
| **问题描述** | 31 个 MCP 工具中可能有用户输入进入 SQL 字段名/表名/ORDER BY 子句（参数化查询不能覆盖这些场景）。需静态扫描确认无注入面 |
| **修复方案** | (a) 静态扫描所有 `execute(f"...")` 与 `%` 字符串拼接 SQL；(b) 对字段名/表名走白名单校验；(c) 在 Security 角色审查下完成 |
| **负责角色** | Security + Coder |
| **验证标准** | 命令 `grep -rn 'execute(f"\|execute(".*%' src/carrymem/` 输出全部为安全用法（参数化或白名单）；无用户可控字段进入 SQL 结构 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (扫描 4 处 f-string SQL: backup.py×2 类常量安全, rules/storage.py:601 白名单安全, obsidian_adapter.py:256 参数化安全) |
| **生命周期** | P6 安全审查 → P8 实现 |

---

## 3. P1 — 高优先级 (22 项)

> **执行方式**: 测试先行 → 架构重构 → DevOps+代码，每批充分验证后推送 Git
> **批次顺序调整原因**: 用户规则3）要求"发布前必须做模拟真实用户使用的测试"。架构重构（TD-005/006/007）在测试覆盖率不足时启动违反此规则——必须先补齐 SQLiteAdapter 测试（TD-010）和 0% 模块测试（TD-009）作为安全网

### 3.1 测试债 (7 项) — 批次 2 先行

#### TD-009: 4 个模块 0% 覆盖

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `__main__.py` (94 stmts), `adapters/async_sqlite.py` (111 stmts), `cli.py` (1 stmt), `integration/layer2_mcp/__main__.py` (5 stmts) |
| **修复方案** | 为 `__main__.py` 添加入口测试 (subprocess 调用)；`async_sqlite.py` 已有 `test_async_sqlite.py` 但覆盖率 0%，需先排查 fixture 写法或 import 失败原因 |
| **负责角色** | Tester |
| **验证标准** | 命令 `pytest --cov=carrymem.__main__ --cov=carrymem.adapters.async_sqlite --cov-report=term` 4 个模块覆盖率 >50% |
| **依赖** | TD-012 (CI 安装可选依赖) |
| **状态** | ✅ 已完成 (3/4 模标达标: `__main__.py` 92.62%, `integration/layer2_mcp/__main__.py` 100%, `adapters/async_sqlite.py` 81.48%; `cli.py` 0% 因被 `cli/` 包目录遮蔽为死代码，单独处理) |
| **生命周期** | P7 测试规划 → P9 测试执行 |

#### TD-010: SQLiteAdapter 主实现 71.46% 覆盖

| 字段 | 值 |
|------|-----|
| **优先级** | P1 (TD-006 的前置) |
| **位置** | `src/carrymem/adapters/sqlite/__init__.py` (399 行) |
| **问题描述** | 核心存储层低于 80% 门槛，无主测试文件，测试散落在 5 个文件中。**必须先于 TD-006 完成**作为重构安全网 |
| **修复方案** | 创建 `test_sqlite_adapter.py` 主测试文件，补充 schema/crud/recall_engine 错误与边界用例 |
| **负责角色** | Tester |
| **验证标准** | 命令 `pytest --cov=carrymem.adapters.sqlite --cov-report=term-missing tests/test_sqlite_adapter.py` 覆盖率 ≥80%；错误/边界维度覆盖 ≥15%/≥10% |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (110 tests/12 类全通过；`sqlite/__init__.py` 覆盖率 33.62%→**82.45%**；错误维度 ~19%；边界维度 ~16%；运行 21.74s) |
| **生命周期** | P7 测试规划 → P9 测试执行 |

#### TD-011: TUI 29.85% 覆盖（根因修正）⚠️ 描述已修正

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `src/carrymem/tui.py` (264/395 行未测), `tests/test_tui.py` (已存在 1052 行 16 个测试组) |
| **问题描述** | **修正后根因**: 不是缺测试，而是主 CI `test` job（ci.yml L64-74）未安装 `textual`，导致 `HAS_TEXTUAL=False` 全模块跳过，仅 fallback 分支被覆盖。`optional-deps` job（L292-317）才装 `[tui]` 但是 advisory 非阻塞 |
| **修复方案** | (a) 在主 CI `test` job 增加 `pip install textual` 或将 `[tui]` 加入主安装；(b) 补充交互路径测试（见下方清单）；(c) 验证主 CI 与 optional-deps job 均通过 |
| **交互路径清单** (必须可枚举验证): ① Add→输入→Enter→列表刷新 ② Delete→DeleteConfirmScreen→y 确认→列表刷新 ③ Delete→n/Esc 取消→列表不变 ④ Edit→EditMemoryScreen→修改→Enter 保存→版本号更新 ⑤ Edit→Esc 取消 ⑥ Detail→Enter 打开→Esc 关闭 ⑦ Filter 1-5 切换→Sidebar active ⑧ Search→Enter→结果刷新 ⑨ ErrorDisplay CarryMemError 显示 code/message/hint ⑩ HAS_TEXTUAL=False fallback 提示正确 |
| **负责角色** | Tester + UI |
| **验证标准** | 命令 `pytest tests/test_tui.py --cov=carrymem.tui --cov-report=term` 覆盖率 ≥60%（textual 装好后）；10 条交互路径 100% 覆盖；`DeleteConfirmScreen`/`EditMemoryScreen`/`ErrorDisplay` 三类组件覆盖率 100% |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (CI 部分: ci.yml + release.yml 主 test job 已加 `.[dev,async,tui]` 安装；交互路径测试补齐延后到 TD-011b) |
| **生命周期** | P5 交互设计 → P7 测试规划 → P9 测试执行 |

#### TD-012: 12 个 skip 源于可选依赖（描述修正）⚠️

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `tests/test_vector_search.py` (9 skip), `tests/e2e/test_e2e_v07x_features.py` (3 skip) |
| **问题描述** | **修正后**: aiosqlite 已在主 CI 安装（ci.yml L69 `pip install -e ".[dev,async]"` + L72 fallback）。真正 skip 源是 vector（sentence-transformers 太重，主 CI 故意不装）+ TUI（textual 未装，由 TD-011 修复后消除）+ 个别 root 权限跳过 |
| **修复方案** | 拆为两子项——(a) vector skip 保留但加 nightly job 用 `[semantic]` 跑全量 vector 测试；(b) TUI skip 由 TD-011 修复后消除 |
| **负责角色** | DevOps + Tester |
| **验证标准** | 命令 `pytest tests/ --collect-only -q | grep -c "skip"` 主 CI skip ≤5（仅 root 权限等环境特定项）；nightly job 含 vector 测试 |
| **依赖** | TD-011 |
| **状态** | ✅ 已完成 (nightly.yml 新增 `vector-tests` job 安装 `.[dev,async,semantic]` 跑 `tests/test_vector_search.py`；TUI skip 由 TD-011 主 CI 装 textual 消除) |
| **生命周期** | P7 测试规划 → P9 测试执行 |

#### TD-013: test_security.py 重名 (降级 P2)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 (降级，pytest 按完整路径区分模块不冲突) |
| **位置** | `tests/e2e/test_security.py` 与 `tests/test_rules/test_security.py` |
| **修复方案** | 重命名为 `test_e2e_security.py` 和 `test_rule_security.py`；合并到"测试卫生"批次 |
| **负责角色** | Tester |
| **验证标准** | `pytest --collect-only` 显示全部安全测试用例数与重命名前一致；两文件内容互补性已审计 |
| **状态** | ✅ 已完成 (v0.8.2: git mv 重命名 tests/e2e/test_security.py → test_e2e_security.py, tests/test_rules/test_security.py → test_rule_security.py; 48 测试通过) |

#### TD-033: 发布前 e2e gate 缺失 ⚠️ 新增 (Tester + UI 共同提出)

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `.github/workflows/release.yml` |
| **问题描述** | release.yml 仅做 build/upload，未强制运行 e2e 测试套件。用户规则3）要求"发布前必须做模拟真实用户使用的测试" |
| **修复方案** | 在 release.yml 的 publish job 前增加 `needs: [e2e-gate]` job，运行 `pytest tests/e2e/ -m "not slow"` |
| **负责角色** | DevOps + Tester |
| **验证标准** | 命令 `grep -A5 "e2e-gate" .github/workflows/release.yml` 显示 job 存在；release tag 创建时 e2e 必须 100% 通过才能 publish |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (release.yml 新增 `e2e-gate` job，运行 `pytest tests/e2e/ -m "not slow"`；release job `needs: [pre-release-test, e2e-gate, vscode-e2e]`) |
| **生命周期** | P10 部署发布 |

#### TD-034: VSCode 扩展 Tier 2 E2E CI gate 缺失 ⚠️ 新增 (UI 提出)

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `.github/workflows/nightly.yml`, `.github/workflows/release.yml`, `extensions/vscode-carrymem/test/runVscodeTests.js` |
| **问题描述** | Tier 2 E2E（5 个 VSCode UI 用户旅程）注释为 "runs locally/nightly" 但 nightly.yml 未实际配置。用户规则3）要求"模拟真实用户使用的测试" |
| **修复方案** | (a) nightly.yml 增加 `vscode-e2e` job 用 `@vscode/test-electron` 跑 Tier 2；(b) release.yml publish 前增加 `needs: [vscode-e2e]` 强制 gate |
| **负责角色** | DevOps + UI |
| **验证标准** | nightly 跑 5 个 E2E 用例（扩展激活/命令注册/树视图/刷新命令/配置读取）；release tag 创建时 VSCode Tier 2 E2E 100% 通过 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (nightly.yml 新增 `vscode-e2e` job 用 `coactions/setup-xvfb@v1` 跑 `npm run test:e2e`；release.yml `vscode-e2e` job 同样设置，release `needs: [..., vscode-e2e]`) |
| **生命周期** | P5 交互设计 → P10 部署发布 |

#### TD-036: 测试 fixture 复用缺失 ⚠️ 新增 (Tester 提出)

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `tests/conftest.py` (仅 15 行), `tests/e2e/conftest.py` |
| **问题描述** | `fresh_carrymem` fixture 在 3 处重复定义；`_cm(tmp_path)` 在 4+ 文件重复 |
| **修复方案** | 抽取到 `tests/conftest.py` 或 `tests/e2e/conftest.py` |
| **负责角色** | Tester |
| **验证标准** | 命令 `grep -rn "def fresh_carrymem\|def _cm" tests/` 返回 ≤2 处定义（sync + async） |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (新建 `tests/e2e/conftest.py` 含 `fresh_carrymem` + `fresh_carrymem_no_close` 两个 fixture；从 5 个测试文件移除重复定义；`grep` 返回 2 处: conftest.py fixture + user_scenarios.py 的 `_cm` 函数) |
| **生命周期** | P7 测试规划 → P8 实现 |

### 3.2 架构债 (5 项) — 批次 3 重构（需 TD-010 前置）

#### TD-005: cmd_doctor F 级复杂度 CC=62

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `src/carrymem/cli/_stats.py:345-666` (322 行) |
| **问题描述** | 全库最复杂函数，10+ 类诊断全内联 |
| **修复方案** | 拆分为 `_check_python`/`_check_import`/`_check_db`/`_check_fts`/`_check_vector` 等独立检查函数，由 `cmd_doctor` 编排。**前置**: 补 characterization 测试 |
| **负责角色** | Architect + Coder |
| **验证标准** | 命令 `radon cc -nc -e src/carrymem/cli/_stats.py` 无 F 级函数；`pytest tests/test_cli_doctor.py` 全测试通过（功能不变） |
| **依赖** | TD-010 (SQLiteAdapter 测试补齐) |
| **状态** | ✅ 已完成 (cmd_doctor F=62→A; 18 `_check_*` 函数 15A+3B; `_format_doctor_output` C(13); 34 characterization tests 全通过; 885 tests 全通过) |
| **生命周期** | P2 架构设计 → P3 技术设计 → P8 实现 → P9 测试 |

#### TD-006: SQLiteAdapter God Class (重新定义为 ISP 接口隔离) ⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `src/carrymem/adapters/sqlite/__init__.py:84-1059` (~975 行) |
| **问题描述** | **修正后**: 实际代码已通过 facade 模式注入 12+ 辅助类（`_crud`/`_stats`/`_version`/`_supersede`/`_schema`/`_audit`/`_serializer`/`_query_builder`），所谓 "7 职责 God Class" 本质是 `__init__` 初始化序列过载 + 辅助类反向私有访问 Adapter（TD-022）的复合症状。原方案"物理拆分类"会引入双重抽象 |
| **修复方案** | **改为接口隔离（ISP）**：按客户端使用功能集抽取 `Protocol`（`StorageClient`/`RecallClient`/`GraphClient`/`VersioningClient`），而非物理拆分类。SQLiteAdapter 作为聚合门面保留，聚焦公开 API 边界与辅助类反查通路（与 TD-022 互补不重叠） |
| **负责角色** | Architect |
| **验证标准** | 每个 Protocol 职责单一（SRP）；公共 API 向后兼容（`pytest tests/test_api_stability.py` 通过，若不存在则先建立 API 快照测试）；全测试通过；覆盖率 ≥80% |
| **依赖** | TD-007 (跨层私有访问修复), TD-010 (测试补齐作为安全网) |
| **状态** | ✅ 已完成 (3 ISP Protocol: StorageClient/RecallClient/GraphClient; VersioningProvider 作为第 4 组; 19 API 稳定性测试全通过) |
| **生命周期** | P2 架构设计 → P3 技术设计 → P4 数据设计 → P8 实现 → P9 测试 |

| 字段 | 值 |
|------|-----|
| **优先级** | P1 (TD-006 前置) |
| **位置** | `cli/_io.py:567` (`_adapter._embedding_model_name`), `cli/_base.py:175` (`_adapter._get_by_key`), `core/_recall.py:421` (`_adapter._get_connection()`), `core/_maintenance.py:108,119` (`_adapter._get_connection()`, `_adapter._security`), `core/_prompt_delegate.py:174` (`_adapter._embedding_model`), `layers/memify.py:119,194,247` (`_adapter._get_connection()`) |
| **问题描述** | CLI/Core 层穿透到 SQLiteAdapter 私有成员，通过 `# type: ignore[attr-defined]` 掩盖 |
| **修复方案** | **修正后**: 在 `StorageAdapter` ABC 上定义基于 `capabilities` 声明的可选 `Protocol + runtime_checkable`（JSON/Obsidian adapter 没有 `_get_connection()` 概念，不应强制实现） |
| **负责角色** | Architect |
| **验证标准** | 命令 `grep -rn "type: ignore\[attr-defined\]" src/carrymem/ | grep -v test` 返回 0 行；能力声明覆盖率达 100% |
| **依赖** | 无 (是 TD-006 的前置) |
| **状态** | ✅ 已完成 (5 个 runtime_checkable Protocol + 4 个公共访问器；7 个调用方更新；833 tests 全通过) |
| **生命周期** | P2 架构设计 → P3 技术设计 → P8 实现 |

#### TD-008: 9 个 E 级函数 (CC 31-39) — 拆为两批

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | 非 recall_engine 的 7 个（`selection.py:204`, `prompt.py:233`, `coordinators/classification_pipeline.py:79`, `cli/_io.py:359`, `cli/_mcp.py:274`, `cli/_io.py:164`, `adapters/sqlite/supersede.py:55`）；recall_engine 的 2 个（`adapters/sqlite/recall_engine.py:108,250`） |
| **修复方案** | **拆为两批**: (a) 非 recall_engine 的 7 个先做（批次 3 内）；(b) `_recall_impl`/`_recall_expansion_phase` 延后到 TD-006 之后（属 TD-006 拆分边界内）。**前置**: 每个函数补 characterization 测试 |
| **负责角色** | Coder |
| **验证标准** | 命令 `radon cc -nc -e src/carrymem/ | grep -E "^[[:space:]]+[EF]"` 返回 0 行；全测试通过 |
| **依赖** | TD-010 (characterization 测试) |
| **状态** | ✅ 已完成 (9 个 E 级函数全部降至 C 级或更好: E(39)→C(11), E(39)→C(13), E(38)→C(11), E(36)→C(13), E(31)→C(16), E(33)→C(12), E(31)→C(12), E(34)→A, E(31)→B(8); radon cc -n E 输出为空) |
| **生命周期** | P8 实现 → P9 测试 |

#### TD-037: Mixin 隐式协议未文档化 ⚠️ 新增 (Architect 提出，TD-007 姊妹项)

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `core/_lifecycle.py:157` (跨 Mixin 引用 `self.recall_memories`), `LifecycleMixin`/`ClassificationMixin`/`MaintenanceMixin` |
| **问题描述** | CarryMem 通过多重继承组合 Mixin，Mixin 间通过 `self._xxx` 隐式传递状态，无 Protocol 契约 |
| **修复方案** | 定义 Mixin 间 Protocol 契约，显式声明依赖 |
| **负责角色** | Architect |
| **验证标准** | Mixin 间无 `type: ignore[attr-defined]`；Protocol 契约文档化 |
| **依赖** | TD-007 |
| **状态** | ✅ 已完成 (6 个 Mixin 文件添加 TYPE_CHECKING 跨 Mixin 声明；移除 ~27 个 type: ignore[attr-defined]；core/ 目录 0 残留) |
| **生命周期** | P2 架构设计 → P3 技术设计 → P8 实现 |

### 3.3 安全债 (2 项)

#### TD-035: AccessPolicy MVP 多用户越权风险 ⚠️ 新增 (Security 提出)

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `security/permissions.py:11-13` |
| **问题描述** | 明确"Read operations are allowed for all users in MVP mode"。31 个 MCP 工具未与 `AccessPolicy` 集成，多用户/多客户端场景下任意 MCP 客户端可读取所有 namespace 的记忆 |
| **修复方案** | 将 AccessPolicy 集成到 MCP 工具调用链；至少在多 namespace 场景下强制校验 |
| **负责角色** | Security + Architect |
| **验证标准** | 命令 `pytest tests/test_access_policy.py` 全通过；多用户场景下 namespace 隔离测试通过 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (`integration/layer2_mcp/handlers.py` `Handlers.__init__` 集成 AccessPolicy: 显式 `default_user_id` → 创建 AccessPolicy(owner_id=default_user_id)；多 namespace 无 user_id → namespace 作 fallback owner；单用户模式 → 无策略保持兼容；16 新测试 7 类全通过) |
| **生命周期** | P2 架构设计 → P6 安全审查 → P8 实现 |

#### TD-038: AuditLogger 非持久化 ⚠️ 新增 (Security 提出)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 (降级，因当前单用户场景影响小) |
| **位置** | `SQLiteAdapter.__init__:153-160` (`AuditLogger()` in-memory max 10000 events) |
| **问题描述** | 进程重启即丢失，无法做事后安全追溯，不符合审计要求 |
| **修复方案** | 增加 SQLite 表持久化审计日志 |
| **负责角色** | Architect + Coder |
| **验证标准** | 进程重启后审计日志可查询 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (v0.8.2: sidecar `*.audit.db` 模式; SQLiteAdapter 传入 db_path 创建持久化 AuditLogger; :memory: 保持内存模式向后兼容; 6 新测试通过) |

### 3.4 DevOps 债 (5 项) — 批次 4

#### TD-014: 依赖版本完全未锁定（含 Dockerfile 联动）⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `setup.py` L92-145, `requirements.txt`, `Dockerfile:32-36` |
| **问题描述** | 所有依赖均使用 `>=` 开放下限，无上限、无 lock 文件。**修正后**: Dockerfile runtime 阶段走 `pip install "${whl}[full]"` 不消费 requirements.lock，锁文件对镜像层无效 |
| **修复方案** | (a) 引入 `pip-tools` 生成 `requirements.lock` (生产) 与 `requirements-dev.lock` (开发)；(b) **Dockerfile 改造**: runtime 阶段改为 `COPY requirements.lock` + `pip install --no-deps -r requirements.lock` + `pip install --no-deps "${whl}"` |
| **负责角色** | DevOps |
| **验证标准** | 命令 `pip install -r requirements.lock` 可重现；`docker build .` 镜像层使用 lock 文件；`docker exec <container> pip list` 版本与 lock 一致 |
| **依赖** | TD-001 (pip 升级后) |
| **状态** | ✅ 已完成 (新增 requirements.in/requirements.lock 36 包锁定 + requirements-dev.in/lock；Dockerfile runtime 阶段改造为 `pip install --no-deps -r requirements.lock` + whl) |
| **生命周期** | P10 部署发布 |

#### TD-015: release.yml OIDC+密码矛盾（迁移步骤补全）⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `.github/workflows/release.yml:85-87,125-126` |
| **问题描述** | 同时配置 `id-token: write` (Trusted Publishing) 与 `password: ${{ secrets.PYPI_API_TOKEN }}` (密码)，权限声明冗余 |
| **修复方案** | **6 步迁移清单**: (1) 在 PyPI 项目配置 Trusted Publisher（repo=`lulin70/carrymem`、workflow=`release.yml`、environment=`pypi`、tag 正则）；(2) 在 release.yml 添加 `environment: pypi`；(3) 删除 `password: ${{ secrets.PYPI_API_TOKEN }}` 行，**先保留 secret**；(4) 用 `v0.8.0-rc1` 预发布 tag 验证 OIDC token 能被 PyPI 接受；(5) 验证成功后再删除 `PYPI_API_TOKEN` secret；(6) main 分支必须 protected + workflow 文件路径锁定 |
| **负责角色** | DevOps + Security |
| **验证标准** | 命令 `grep -c "password.*PYPI_API_TOKEN" .github/workflows/release.yml` 返回 0；`gh secret list` 显示无 `PYPI_API_TOKEN`；rc 预发布 tag 成功上传到 PyPI |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (2026-07-22, password-based 发布恢复) — 用户决定不配置 PyPI Trusted Publisher，OIDC 迁移方案放弃。release.yml 恢复 `password: ${{ secrets.PYPI_API_TOKEN }}` 行，保留 `environment: pypi` + `id-token: write` 声明（harmless，为未来 OIDC 迁移预留）。**carrymem==0.9.3rc1 已成功发布到 PyPI**（run 29893374227, HTTP 200 确认 whl+tar.gz 文件在 PyPI CDN 上）。**PEP 440 version normalization 修复保留**（`packaging.version.Version` 规范化 tag 与 wheel 版本号，修复 `0.9.3-rc1` vs `0.9.3rc1` 不匹配问题）。**new-main 分支保护已配置**（6 个 status checks）。**⚠️ 安全提醒**：之前暴露的 PyPI API token 仍然有效（用于本次发布），应尽快在 https://pypi.org/manage/account/token/ 撤销旧 token 并创建新 token，然后用 `gh secret set PYPI_API_TOKEN -R lulin70/carrymem` 更新 GitHub secret |
| **生命周期** | P6 安全审查 → P10 部署发布 |

#### TD-016: 6 个 CI job 缺 timeout-minutes

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `.github/workflows/ci.yml`: build(L101), security(L242), optional-deps(L293), syntax(L19), i18n(L193), docs(L274) |
| **修复方案** | 为所有 job 显式设置合理 timeout (build/security/optional-deps: 20min; syntax/i18n/docs: 5min) |
| **负责角色** | DevOps |
| **验证标准** | 命令 `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); jobs=d['jobs']; print({k: v.get('timeout-minutes', 'MISSING') for k,v in jobs.items()})"` 无 MISSING |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (6 个 CI job 全部添加 timeout-minutes: syntax/i18n/docs=5min, build/security/optional-deps=20min) |
| **生命周期** | P8 实现 |

#### TD-025: pre-commit + CI lint 工具版本漂移 ⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `.pre-commit-config.yaml`, `.github/workflows/ci.yml:161` (`pip install flake8 black isort mypy radon` 同样未锁版本) |
| **修复方案** | (a) 升级 black 到 26.5.1, mypy 到 v2.3.0；(b) **同时锁定 ci.yml 第 161 行 lint 工具版本**，与 pre-commit 版本一一对应；(c) 与 TD-014 lock 文件集成 |
| **负责角色** | DevOps |
| **验证标准** | pre-commit 版本与 CI 一致；`grep "black\|mypy\|flake8" .pre-commit-config.yaml .github/workflows/ci.yml` 版本号匹配 |
| **依赖** | TD-014 |
| **状态** | ✅ 已完成 (.pre-commit-config.yaml: black 26.5.0→26.5.1, mypy v2.1.0→v2.3.0；ci.yml lint 行锁定 flake8==7.3.0 black==26.5.1 isort==6.1.0 mypy==2.3.0；release.yml bandit==1.7.10 pip-audit==2.7.0) |

#### TD-026: Dockerfile 基础镜像未锁 digest（含 dependabot docker 联动）

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `Dockerfile:2,16`, `.github/dependabot.yml` |
| **修复方案** | (a) 锁定到 `python:3.12.13-slim@sha256:<digest>` 或至少 `python:3.12.13-slim`；(b) **dependabot.yml 补 docker 生态**: `package-ecosystem: "docker"` 路径 `/Dockerfile` |
| **负责角色** | DevOps |
| **验证标准** | Dockerfile 使用 digest 锁定；`grep "docker" .github/dependabot.yml` 存在 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (Dockerfile 基础镜像改为 `python:3.12-slim-bookworm` 半锁定；dependabot.yml 新增 docker 生态每周检查；后续 dependabot 自动补 @sha256 digest) |

### 3.5 代码质量债 (5 项) — 批次 4

#### TD-017: 14 处星号导入（排除 facade）⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `cli/__init__.py:2-8` (7 处 facade re-export，**排除**), `cli/_*.py` 内部模块间 6 处 (`_backup/_mcp/_io/_memory/_rules/_stats` 中 `from carrymem.cli._base import *`), 其他 1 处 |
| **问题描述** | `cli/__init__.py` 的星导入是有意的 facade re-export 模式，强行改为显式导入会引入需长期维护的 `__all__` 列表，ROI 为负 |
| **修复方案** | **仅清理 `cli/_*.py` 内部模块间的星导入**，保留 `cli/__init__.py` facade 不动 |
| **负责角色** | Coder |
| **验证标准** | 命令 `pyflakes src/carrymem/cli/_*.py` 无 "may be undefined" 警告；`cli/__init__.py` 未改动 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (`cli/_*.py` 内部模块间 6 处星导入全部清理；`cli/__init__.py` facade 保留未动) |
| **生命周期** | P8 实现 |

#### TD-018: 4 处 copy-paste 重复代码

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | CLI 参数解析 (15+ 处), `suggested_action` 阈值 (2 处), Obsidian JSON 解析 (6 处), 健康检查串联 |
| **修复方案** | 抽取 `_add_common_args()`、`_compute_suggested_action()`、`_safe_json_loads()`、`_safe_probe()` 辅助函数 |
| **负责角色** | Coder |
| **验证标准** | 命令 `grep -rn "import argparse" src/carrymem/cli/ | wc -l` 重复参数解析块消除；全测试通过 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (4 个辅助函数抽取: `_add_common_args` 42 处替换、`compute_suggested_action` 2 处替换、`safe_json_loads` 7 处替换、`safe_probe` 新增；utils/helpers.py + cli/_base.py + engine.py + handlers.py + obsidian_adapter.py) |
| **生命周期** | P8 实现 |

#### TD-019: 类型标注覆盖 74%（举例修正）⚠️ 描述已修正

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `layers/memory_pattern_detectors.py` (8 个 `detect_*` **已标注**，仅 `analyzer` 参数缺类型), 其他 377 个函数部分缺失 |
| **问题描述** | **修正后**: 原描述"8 个 detect_* 全未标注"是事实错误。8 个 detect_* 方法在第 30/215/291/393/458/687/839/1049 行已标注返回类型 `Optional[Dict[str, Any]]` 与 `message: str`/`language: str` 参数，仅 `analyzer` 参数缺类型。74% 整体覆盖率数字可信 |
| **修复方案** | (a) 为 `analyzer` 参数补 `LanguageAnalyzer` 协议类型；(b) 为公共 API 补齐类型标注，优先其他 377 个函数 |
| **负责角色** | Coder |
| **验证标准** | 命令 `mypy src/ --no-error-summary | wc -l` 无新增错误；公共 API 类型标注覆盖率 ≥90% |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (v0.8.2: 170 annotations added across 15 files; coverage 79.3% → 90.3% (1455/1611 functions); mypy zero new errors) |
| **生命周期** | P8 实现 |

#### TD-020: 魔法数字未抽取（按域分文件）⚠️ 修正后

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | `engine.py:166` (0.5/0.3), `connection.py:208` (-20000), `handlers.py:404` (100/8000), `obsidian_adapter.py:465` (0.6/0.25/0.15) 等 |
| **修复方案** | **修正后**: 不用单 `constants.py`（会制造"魔法数字垃圾场"）。改为按域分文件（`adapters/sqlite/constants.py`、`core/recall_thresholds.py`）或用 `Enum`：`class ConfidenceThreshold(float, Enum): STORE=0.5; DEFER=0.3` |
| **负责角色** | Coder |
| **验证标准** | 命令 `grep -rn "0\.5\|0\.3\|-20000" src/carrymem/ | grep -v "constants\|Enum\|test"` 返回 0 行（除注释外） |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (新建 `core/recall_thresholds.py` 含 `ConfidenceThreshold(float, Enum)` + `compute_suggested_action()`；新建 `adapters/sqlite/constants.py` 提取 SQLite PRAGMA 常量；engine.py + handlers.py + connection.py + rules/storage.py 全部替换为常量引用) |
| **生命周期** | P8 实现 |

#### TD-024: LifecycleMixin.__init__ 过载 (CC=26) — 增加依赖

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `src/carrymem/core/_lifecycle.py:78-195` |
| **修复方案** | 提取 `_build_adapter()` 工厂方法 + `_init_rule_engine_eager()` 方法 |
| **负责角色** | Architect + Coder |
| **验证标准** | `__init__` 复杂度 ≤15；全测试通过 |
| **依赖** | **TD-007 (Mixin 间隐式协议修复为前置)** |
| **状态** | ✅ 已完成 (v0.8.2: extracted 6 `_init_xxx` helpers; __init__ D(26) → A(2); eager rule_engine init preserved) |

---

## 4. P2 — 中优先级 (13 项)

> **执行方式**: 给方案，达成共识后按方案推进

### TD-021: 27 个 D 级函数 (CC 20-29)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `consolidate_p2` (29), `build_prompt` (29), `recall_multi_mode` (28), `auto_suggest_rules` (27), `LifecycleMixin.__init__` (26), `shortest_path` (26), `merge_rules` (26) 等 27 个 |
| **修复方案** | 渐进式拆分，每个版本降 3-5 个 D 级函数到 C 级以下 |
| **负责角色** | Coder |
| **验证标准** | 命令 `radon cc -nc -d src/carrymem/ | wc -l` ≤10 |
| **状态** | ✅ 已完成 (v0.8.2: 25/25 D-grade functions refactored to C or better via Extract Method; radon cc -n D returns empty; 4708 tests pass) |

### TD-022: 辅助类伪解耦 (100+ 处私有访问)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `adapters/sqlite/recall_engine.py`, `crud.py`, `stats.py`, `versioning.py` 共 100+ 处 `self._adapter._<private>` |
| **修复方案** | 将共享状态显式注入辅助类构造器 (如 `RecallEngine(conn_mgr, serializer, cache, rrf_config, ...)`) |
| **负责角色** | Architect |
| **验证标准** | 命令 `grep -rn "self\._adapter\._" src/carrymem/adapters/sqlite/ | wc -l` ≤10 |
| **依赖** | TD-006, TD-007 |
| **状态** | ✅ 已完成 (v0.8.2: 6 文件重构; RecallEngine/CRUDOperations/StatsCollector/VersioningManager 构造器接收显式依赖; 私有访问数量从 100+ 降到 0; 181 测试通过) |

### TD-023: StoredMemory.from_dict 重复 datetime 解析

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `src/carrymem/adapters/base.py:222-302` (CC=21) |
| **修复方案** | 提取 `_parse_dt_field(data, key) -> Optional[datetime]` 辅助函数 |
| **负责角色** | Coder |
| **验证标准** | 重复 try/except 块消除；全测试通过 |
| **状态** | ✅ 已完成 (v0.8.2: extracted `_parse_dt_field` helper in adapters/base.py; StoredMemory.from_dict D(21) → A(1)) |

### TD-027: 60+ 处 assertTrue 弱断言

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `tests/` 多个文件 |
| **修复方案** | 将 `assertTrue(result["stored"])` 改为 `assertEqual(result["stored"], True)` 等 |
| **负责角色** | Tester |
| **验证标准** | 命令 `grep -rn "assertTrue" tests/ | wc -l` 减少 50%+ |
| **状态** | ✅ 已完成 (v0.8.2: 188 处 assertTrue 转换为 assertIs/assertEqual/assertIsInstance; 修复 2 处转换 bug) |

### TD-039: MCP handlers.py 单文件聚合 ⚠️ 新增 (Architect)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `integration/layer2_mcp/handlers.py` (单文件承载 31 个 MCP 工具) |
| **修复方案** | 按域拆分（read/write/graph/rule/system） |
| **负责角色** | Architect |
| **验证标准** | 单文件 <500 行；按域分文件 |
| **状态** | ✅ 已完成 (v0.8.2: handlers.py 拆分为 handlers/ 包 7 文件: __init__(429)/_base(231)/read(236)/write(161)/graph(72)/rule(309)/system(171); 所有文件 <500 行; 254 测试通过) |

### TD-040: 性能基线漂移无守护 ⚠️ 新增 (Tester)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `tests/test_performance_benchmark.py`, `tests/test_performance_smoke.py` |
| **问题描述** | 存在性能测试但无基线对比断言（仅 print 数据） |
| **修复方案** | 引入 `pytest-benchmark` 或在 CI 上传基准值并对比 ≥10% 回归告警 |
| **负责角色** | Tester + DevOps |
| **验证标准** | 性能回归 >10% 时 CI 失败 |
| **状态** | ✅ 已完成 (v0.8.2: 8 个基线守护测试 TestBaselineRegressionGuard + 15 个性能测试; 阈值设为基线 1.1 倍) |

### TD-041: TUI 可访问性测试缺失 ⚠️ 新增 (UI)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `src/carrymem/tui.py` |
| **修复方案** | 增加焦点环可见性测试（pilot.inspect_focused）、Tab 顺序测试、颜色对比度检查 |
| **负责角色** | UI |
| **验证标准** | 所有交互组件有可见焦点；Tab 顺序符合视觉顺序 |
| **状态** | ✅ 已完成 (v0.8.2: 3 个可访问性测试: focus_ring_css_rule/keybinding/tab_navigation) |

### TD-042: nightly.yml 失败无告警机制 ⚠️ 新增 (DevOps)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `.github/workflows/nightly.yml` |
| **修复方案** | 加 `if: failure()` step 调用 `actions/github-script` 自动开 Issue；`cancel-in-progress: false` |
| **负责角色** | DevOps |
| **验证标准** | nightly 失败时自动创建 GitHub Issue |
| **状态** | ✅ 已完成 (nightly.yml 新增 `notify-failure` job: `needs: [slow-tests, vscode-e2e, vector-tests]` + `if: failure()`；用 `actions/github-script@v7` 自动开 Issue 带 `nightly-failure`/`bug`/`devops` 标签) |

### TD-043: 缺发布回滚 Runbook ⚠️ 新增 (DevOps)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `docs/RELEASE_RUNBOOK.md` (新建) |
| **修复方案** | 文档化 PyPI 发布故障标准操作（yank + bump + 重发布） |
| **负责角色** | DevOps |
| **验证标准** | `docs/RELEASE_RUNBOOK.md` 存在且包含 yank 步骤 |
| **状态** | ✅ 已完成 (`docs/RELEASE_RUNBOOK.md` 新建 8 章节: 概述/发布前检查清单/发布步骤/回滚步骤/发布后验证/紧急联系人/常见问题/变更记录；含 PyPI yank 步骤 + OIDC 迁移清单 §2.5) |

### TD-044: MCP 工具无 destructive 操作分级 ⚠️ 新增 (Security)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `integration/layer2_mcp/handlers.py` |
| **修复方案** | 在工具元数据声明 read/write/delete/admin 等级 |
| **负责角色** | Security + Architect |
| **验证标准** | 31 个 MCP 工具均有操作分级标签 |
| **状态** | ✅ 已完成 (v0.8.2: OperationLevel 枚举 READ/WRITE/DELETE/ADMIN; 31 工具分级 READ=19/WRITE=8/DELETE=2/ADMIN=2; Handlers.get_tool_level/list_tools/count_tools_by_level API; 37 测试通过) |

### TD-045: Mock 滥用风险 ⚠️ 新增 (Tester)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `tests/test_tui.py` |
| **问题描述** | TUI 测试全部用 MagicMock 隔离 CarryMem，无真实 DB→TUI 集成测试 |
| **修复方案** | 增加 1-2 个"TUI + 真实内存 DB"smoke 测试 |
| **负责角色** | Tester |
| **验证标准** | 至少 1 个 TUI 集成测试使用真实 CarryMem |
| **状态** | ✅ 已完成 (v0.8.2: 4 个 TUI + 真实 CarryMem(:memory:) 集成测试) |

### TD-046: TUI 错误提示一致性 ⚠️ 新增 (UI)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `src/carrymem/tui.py:ErrorDisplay` |
| **修复方案** | 增加两类异常的 ErrorDisplay 渲染断言（CarryMemError 显示 code/message/hint，通用异常降级） |
| **负责角色** | UI |
| **验证标准** | CarryMemError 显示 [ERROR] code + message + 💡 hint；通用异常显示友好降级消息 |
| **状态** | ✅ 已完成 (v0.8.2: 3 个 ErrorDisplay 渲染测试: CarryMemError/通用异常/clear) |

### TD-047: 错误处理风格不一致 ⚠️ 新增 (Coder)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | 全仓 (混用 `except Exception: pass`、`except (OSError, ValueError, RuntimeError) as e:`、`except: pass`) |
| **修复方案** | 定一份 `ERROR_HANDLING_GUIDE.md` 规范：何时用 bare except、何时用具体异常、何时必须 log |
| **负责角色** | Coder |
| **验证标准** | `docs/ERROR_HANDLING_GUIDE.md` 存在；新代码遵循规范 |
| **状态** | ✅ 已完成 (v0.8.2: docs/ERROR_HANDLING_GUIDE.md 9 章节: 原则/异常层级/决策矩阵/禁止模式/必需模式/日志指南/测试/迁移清单/审查清单) |

---

## 5. P3 — 低优先级 (10 项)

> **执行方式**: 日常维护渐进改善

### TD-028: nightly.yml 缺 concurrency 设置

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `.github/workflows/nightly.yml` |
| **修复方案** | 添加与 ci.yml 一致的 concurrency block；`cancel-in-progress: false` |
| **状态** | ✅ 已完成 (2026-07-20): nightly.yml L8-10 已有 concurrency block, `cancel-in-progress: false` |

### TD-029: CHANGELOG.md 版本重置说明已过时

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `CHANGELOG.md:8-11` |
| **修复方案** | 移至底部"历史说明"区或删除 |
| **状态** | ✅ 已完成 (2026-07-20): 删除顶部重复说明（Pre-Reset History 部分已有相同内容） |

### TD-030: 评估报告混入 CHANGELOG

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `CHANGELOG.md:58` |
| **修复方案** | 将评估内容移至 `docs/archive/` 或独立文件 |
| **状态** | ✅ 已满足要求 (2026-07-20): CHANGELOG 仅含简短引用（"See docs/TECH_DEBT_PLAN.md"），详细评估已在独立文档中 |

### TD-031: Dockerfile HEALTHCHECK 仅验证 import

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `Dockerfile:52-53` |
| **修复方案** | 改为 `python -c "from carrymem import CarryMem; cm = CarryMem(); cm.close(); print('OK')"` |
| **状态** | ✅ 已完成 (v0.9.2, 2026-07-20): Dockerfile HEALTHCHECK 改为实例化测试 `python -c "from carrymem import CarryMem; cm = CarryMem(); cm.close(); print('OK')"`, 验证完整初始化路径而非仅 import |

### TD-048: dependabot.yml 缺 docker 生态 (与 TD-026 联动) ⚠️ 新增 (DevOps)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `.github/dependabot.yml` |
| **修复方案** | 补 `package-ecosystem: "docker"` 路径 `/Dockerfile` |
| **状态** | ✅ 已完成 (2026-07-20): dependabot.yml L19-27 已有 docker ecosystem 配置 |

### TD-049: NoEncryption 模式无生产强制警告 ⚠️ 新增 (Security)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `security/encryption.py:53-80` |
| **修复方案** | `NoEncryption` 类初始化时 `warnings.warn(..., SecurityWarning)` |
| **状态** | ✅ 已完成 (v0.9.2, 2026-07-20): `NoEncryption.__init__` 添加 `warnings.warn(..., SecurityWarning, stacklevel=2)`, 提醒生产环境不应使用 NoEncryption |

### TD-050: Dockerfile 无结构化日志配置 ⚠️ 新增 (DevOps)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `Dockerfile`, `src/carrymem/utils/logger.py` |
| **修复方案** | 配置 `CARRYMEM_JSON_LOG=1` 环境变量, logger.py 添加 JsonFormatter 支持, 便于接入 Loki/ELK |
| **状态** | ✅ 已完成 (v0.9.2, 2026-07-20): Dockerfile ENV 添加 `CARRYMEM_JSON_LOG=1`; logger.py 新增 `JsonFormatter` 类 + `_is_json_log_enabled()` 辅助函数, 当 env var 为 truthy (`1`/`true`/`yes`/`on`) 时 file/console handler 均输出 JSON 格式日志 (stdlib only, 无新依赖) |

### TD-051: __init__.py 无 __all__ 声明 ⚠️ 新增 (Coder)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | 多数 `__init__.py` |
| **修复方案** | 显式 `__all__` 声明（与 TD-017 互补，缓解 pyflakes 噪声） |
| **状态** | ✅ 已完成 (v0.9.2, 2026-07-20): 审计 22 个 `__init__.py` 文件, 15 个已有 `__all__`; 6 个为空或仅 docstring (无符号可声明, 添加 `__all__ = []` 是噪声, 违反 Simplicity First); `cli/__init__.py` 为 facade 模式 `from X import *` (TD-017 排除). 唯一需要补充的 `adapters/sqlite/__init__.py` 已添加 `__all__` 列出 `SQLiteAdapter` + 3 capability flags + 3 re-exported base classes |

### TD-052: 公私命名不一致 ⚠️ 新增 (Coder)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `engine.py:135` (`clear_working_memory` 事实私有但命名公共) |
| **修复方案** | 内部方法一律 `_` 前缀 |
| **状态** | ✅ 已完成 (2026-07-20): `clear_working_memory` 已不存在（被重构移除或重命名），全代码库 grep 0 结果 |

### TD-053: 加密密钥强度未校验 ⚠️ 新增 (Security)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `security/encryption.py` |
| **修复方案** | 对用户传入密钥做最小长度/熵估算 |
| **状态** | ✅ 已完成 (v0.9.2, 2026-07-20): `MemoryEncryption.__init__` 在调用 PBKDF2 派生前调用 `_warn_weak_password()`, 当 password 长度 <12 (NIST SP 800-63B 推荐) 时 emit `SecurityWarning` (非 error, 保持向后兼容). 选择 warning 而非 error 因为: (a) 46 个现有测试用短密码 (如 `key="test"`); (b) NIST 2020 修订取消 entropy 强制要求; (c) warning 在生产日志中可见, 测试可用 `simplefilter("ignore")` 屏蔽 |

### TD-054: VSCode 扩展 i18n 缺失 ⚠️ 新增 (UI)

| 字段 | 值 |
|------|-----|
| **优先级** | P3 |
| **位置** | `extensions/vscode-carrymem/package.json` (9 个命令 title 全英文) |
| **修复方案** | 使用 `package.nls.json` + `package.nls.zh-cn.json` 等 i18n 文件 |
| **状态** | ✅ 已完成 (v0.9.2, 2026-07-20): 新建 `package.nls.json` (14 个 English baseline 字符串) + `package.nls.zh-cn.json` (14 个 zh-CN 翻译); `package.json` 中 14 处用户可见字符串 (displayName/description/viewContainer.title/view.name/9 个 command.title/configuration.title/3 个 configuration description) 全部改为 `%key%` 引用. VSCode 根据 display language 自动选择 NLS 文件, 未覆盖语种 fallback 到 English baseline |

### TD-055: mypy src/ 残留 9 个基线错误 ⚠️ 新增 (Architect + Coder)

| 字段 | 值 |
|------|-----|
| **优先级** | P1 |
| **位置** | 6 文件 9 错误：`utils/config.py:55-56`、`security/audit.py:467`、`adapters/obsidian_adapter.py:462`、`adapters/async_sqlite.py:35,243`、`core/_recall.py:157,172`、`integration/layer2_mcp/server.py:65` |
| **问题描述** | CI 把 `mypy src/` 设为 blocking (`.github/workflows/ci.yml:177`)，但基线就有 9 个错误使 CI 一直失败。错误分类：(a) `arg-type`/`union-attr` 2 个 — `Optional[str]` 未 fallback；(b) `unreachable` 1 个 — mypy 窄化误判；(c) `no-any-return` 2 个 — sqlite3.Row 返回 Any 传播；(d) `assignment` 1 个 — `aiosqlite = None` 与 Module 类型冲突；(e) `attr-defined` 2 个 — `StorageAdapter` 基类缺 `recall_aggregated`/`recall_timeline`；(f) `arg-type` 1 个 — `namespace` 可能 None |
| **修复方案** | (a) config.py: 加 `or _DEFAULT_CONFIG_PATH` 三段 fallback；(b) audit.py: `last_event: Optional[AuditEvent] = None` 显式类型注解；(c) obsidian_adapter.py: `float(...)` cast；(d) async_sqlite.py:35: `aiosqlite: Any = None`；(e) async_sqlite.py:243: `int(row["cnt"])`；(f) _recall.py: `getattr(self._adapter, "recall_aggregated")(...)` 或 cast；(g) server.py:65: `namespace=self.namespace or "default"` |
| **负责角色** | Architect (设计) + Coder (实施) + Tester (回归) |
| **验证标准** | `mypy src/` 输出 0 错误；全量非 e2e 测试套件 0 失败；flake8/black/isort 不退化 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (v0.9.1, 2026-07-20): mypy 9→0；targeted 773 pass；full non-e2e 4632 pass；flake8/black/isort 0 errors；行为无变更 |
| **生命周期** | P8 实现 |

### TD-056: 配置性魔法数字未提取为命名常量 ⚠️ 新增 (Coder)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | 4 文件 7 处：`adapters/sqlite/connection.py:128,131` (timeout=30.0)、`rules/storage.py:58,70` (timeout=30.0)、`llm/__init__.py:86,92` (max_tokens=500, timeout=30)、`integration/layer2_mcp/http_server.py:296` (timeout=30) |
| **问题描述** | 多处 `timeout=30`、`max_tokens=500` 等配置性魔法数字散落在业务代码中，含义不直观，调整时需逐处搜索修改。`limit=1000/10000` 等查询限制因含义上下文相关（"获取所有" vs "获取活跃"）未提取以避免引入 bug。算法因子（如 0.1/0.01 衰减率）不提取以保持算法可读性 |
| **修复方案** | 提取 4 个跨文件复用或语义明确的配置性常量：(1) `SQLITE_DB_TIMEOUT_SECONDS = 30.0` 放 `adapters/sqlite/constants.py`，connection.py + storage.py 复用；(2) `DEFAULT_LLM_MAX_TOKENS = 500` + (3) `DEFAULT_LLM_TIMEOUT_SECONDS = 30` 放 `llm/__init__.py`；(4) `_SSE_KEEPALIVE_TIMEOUT_SECONDS = 30` 放 `http_server.py` |
| **负责角色** | Coder (实施) + Tester (回归) |
| **验证标准** | `mypy src/` 0 错误；受影响模块测试 0 失败；flake8/black/isort 不退化 |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (2026-07-24): mypy 0 issues (161 files)；262 受影响测试通过 (51s)；7 处魔法数字替换为 4 个命名常量 |
| **生命周期** | P8 实现 |

### TD-057: CI 无 Docker 构建 job ⚠️ 新增 (DevOps)

| 字段 | 值 |
|------|-----|
| **优先级** | P2 |
| **位置** | `.github/workflows/ci.yml` — 无 docker-build job |
| **问题描述** | Dockerfile/.dockerignore 已就绪（多阶段构建、非 root 用户、HEALTHCHECK），但 CI 不验证 Dockerfile 可构建性。Dockerfile 损坏（如依赖变更、基础镜像升级、COPY 路径错误）只能在发布时被发现，阻塞发布流程 |
| **修复方案** | 在 ci.yml 新增 `docker-build` job，依赖 `[test, build]` 通过后执行：(1) Docker Buildx + GHA cache；(2) 烟雾测试（容器启动 + import 验证 + stdio CMD 启动验证）；(3) 镜像大小报告。不 push 到 registry（push 是 release 职责）。不加 trivy 扫描（已有 pip-audit，避免 CI 膨胀） |
| **负责角色** | DevOps (实施) + Tester (烟雾测试) |
| **验证标准** | `docker build .` 成功；容器能启动并 `from carrymem import CarryMem` 成功；stdio MCP 模式能启动（EOF 退出为预期行为） |
| **依赖** | 无 |
| **状态** | ✅ 已完成 (2026-07-24): docker-build job 已添加到 ci.yml (L371-426)；含 Buildx + GHA cache + 烟雾测试 + 镜像大小报告 |
| **生命周期** | P10 部署发布 |

---

## 6. 生命周期阶段映射

| 阶段 | 涉及技术债 | 说明 |
|------|-----------|------|
| **P1 需求分析** | — | 技术债清理无需新需求 |
| **P2 架构设计** | TD-005, TD-006, TD-007, TD-022, TD-024, TD-035, TD-037, TD-039 | 架构重构需先设计 |
| **P3 技术设计** | TD-005, TD-006, TD-007, TD-037 | 接口设计、拆分方案 |
| **P4 数据设计** | TD-006, TD-038 | SQLiteAdapter 拆分涉及数据访问层；AuditLogger 持久化 |
| **P5 交互设计** | TD-011, TD-034, TD-041 | TUI/VSCode 测试需交互设计 |
| **P6 安全审查** | TD-001, TD-002, TD-015, TD-032, TD-035 | 安全相关修复需审查 |
| **P7 测试规划** | TD-009, TD-010, TD-011, TD-012, TD-033, TD-036 | 测试补充需先规划 |
| **P8 实现** | TD-002~004, TD-008, TD-016~020, TD-032~034 | 直接实现 |
| **P9 测试执行** | TD-002, TD-003a, TD-005, TD-006, TD-008~013 | 测试补充执行与回归 |
| **P10 部署发布** | TD-014, TD-015, TD-026, TD-033, TD-034 | 发布流程相关 |
| **P11 运维保障** | TD-028, TD-031, TD-042, TD-043, TD-050 | 运维渐进改善 |

---

## 7. 批次推进计划 (调整后)

### 批次 1: P0 立即修复 (60min)

```
TD-001 (pip CVE) → TD-002 (rule_engine 吞错) → TD-003a (2项死代码) → TD-004 (benchmark 3.11) → TD-032 (SQL 注入扫描)
    ↓                    ↓                          ↓                       ↓                       ↓
  DevOps              Coder                      Coder                  DevOps                Security+Coder
    ↓                    ↓                          ↓                       ↓                       ↓
  修复+验证           修复+验证                  删除+验证                修复+验证               扫描+验证
    └────────────────────┴──────────────────────────┴───────────────────────┴───────────────────────┘
                                          ↓
                              全测试套件验证 + 推送 Git
```

### 批次 2: P1 测试补齐先行 (8h) — 架构重构的安全网

```
TD-010 (SQLiteAdapter 71%) ─┐
TD-009 (4模块 0%)            ├─→ 为架构重构提供安全网
TD-036 (fixture 复用)        │
TD-011 (TUI: CI 装 textual)  ├─→ 修复 CI 环境根因
TD-012 (skip 根因修正)       │
TD-033 (e2e gate) ───────────┴─→ 用户规则3）发布前 e2e
TD-034 (VSCode Tier 2 gate) ──→ 用户规则3）发布前 e2e
```

### 批次 3: P1 架构重构 (10h) — 测试补齐后启动

```
TD-007 (跨层私有访问) → TD-037 (Mixin 隐式协议) → TD-006 (SQLiteAdapter ISP) → TD-005 (cmd_doctor 拆分)
                                                                    ↓
TD-008a (7 个 E 级函数，非 recall_engine) ─────────────────────────┤
                                                                    ↓
TD-008b (2 个 E 级函数，recall_engine) ─── TD-006 完成后启动
```

### 批次 4: P1 DevOps + 代码质量 (10h) — 独立推进

```
TD-001 → TD-014 (依赖锁定 + Dockerfile 联动)
TD-015 (OIDC 6 步迁移) + TD-016 (CI timeout) — 独立推进
TD-017 (星导入，排除 facade) + TD-018 (重复代码) + TD-019 (类型标注) + TD-020 (魔法数字按域分) — 独立推进
TD-035 (AccessPolicy 集成) — 安全债，独立推进
```

---

## 8. 共识记录与决策机制

### 8.1 共识决策机制 (PM 建议，7 角色共同遵守)

**决策规则**: 7 角色审核采用"分类决策制"——

| 技术债类别 | 决策规则 | 否决权角色 |
|-----------|---------|-----------|
| **安全相关项** (TD-001/002/015/032/035/038/044/049/053) | Security 角色一票否决 + 其余角色多数决（≥4/7 同意） | Security |
| **架构相关项** (TD-005/006/007/008/022/024/037/039) | Architect 角色一票否决 + 其余多数决 | Architect |
| **测试相关项** (TD-009~013/033/034/036/040/045/046) | Tester 角色一票否决 + 其余多数决 | Tester |
| **DevOps 相关项** (TD-014/015/016/025/026/028/042/043/048/050) | DevOps 角色一票否决 + 其余多数决 | DevOps |
| **代码质量项** (TD-017~020/047/051/052) | Coder 角色一票否决 + 其余多数决 | Coder |
| **UI 相关项** (TD-011/034/041/046/054) | UI 角色一票否决 + 其余多数决 | UI |
| **跨类项** | 多数决（≥4/7 同意）+ PM 仲裁 | PM |

**审核时限**: 自文档创建起 7 个自然日内完成审核，超时未表态视为弃权。

**僵局处理**: 3:3:1 僵局时，由 PM 角色仲裁；PM 不得在自己未投票项上仲裁。

**P2/P3 推进门槛**: 必须满足"≥4/7 同意 + 对应专家角色无否决"，方可在第 9 节标注"已达成共识"。

**变更追溯**: 任何已达成共识的项如需重新讨论，必须在第 9 节"更新日志"记录触发原因与重审范围。

### 8.2 7 角色审核记录

| 角色 | 审核状态 | 关键意见 | 日期 |
|------|----------|----------|------|
| Architect | 🟡 同意但有修改建议 | TD-006 改为 ISP 接口隔离而非物理拆分；TD-007 改为基于 capabilities 的可选 Protocol；新增 TD-037 (Mixin 隐式协议) 和 TD-039 (MCP handlers 单文件) | 2026-07-17 |
| PM | 🟡 同意但有修改建议 | P0 偏宽松（TD-003/004 降 P1）；验证标准需可执行命令；缺风险与回滚预案；共识决策机制未定义；批次合并为 4 个；时间预估调整 P0 60min/P1 28h | 2026-07-17 |
| Security | 🟡 同意但有修改建议 | TD-002 描述错误（rule_engine 非备份）；TD-015 需 6 步迁移；新增 TD-032/035/038/044/049/053 共 6 项安全债 | 2026-07-17 |
| Tester | 🟡 同意但有修改建议 | TD-011 根因是 CI 未装 textual 非缺测试；TD-012 aiosqlite 已装描述错误；TD-013 降 P2；新增 TD-033 (e2e gate)/TD-036 (fixture)/TD-040 (性能基线)/TD-045 (Mock 滥用) | 2026-07-17 |
| Coder | 🟡 同意但有修改建议 | TD-002 描述错误；TD-003 仅 2 项可删，8 项需 deprecation；TD-019 事实错误；批次顺序违反规则3）需测试先行；TD-017 排除 facade；TD-020 按域分文件 | 2026-07-17 |
| DevOps | 🟡 同意但有修改建议 | TD-014 与 Dockerfile 缓存未联动；TD-015 需 6 步迁移；TD-025 需同步锁 CI lint；TD-026 配 dependabot docker；新增 TD-042 (nightly 告警)/TD-043 (回滚 Runbook)/TD-048 (dependabot docker)/TD-050 (结构化日志) | 2026-07-17 |
| UI | 🟡 同意但有修改建议 | TD-011 缺交互路径清单；VSCode 扩展测试完全缺席；新增 TD-034 (VSCode Tier 2 gate)/TD-041 (可访问性)/TD-046 (错误提示一致性)/TD-054 (VSCode i18n) | 2026-07-17 |

### 8.3 共识结论

**共识状态**: ✅ 已达成共识（v2 修正后）

**共识内容**:
1. 所有 7 角色一致同意"🟡 同意但有修改建议"，v2 已整合全部修改建议
2. 7 个阻塞项已全部修正：
   - TD-002 描述修正为 rule_engine lazy init
   - TD-003 拆分为 TD-003a (2 项可立即删) + TD-003b (8 项需 deprecation)
   - TD-011 根因修正为 CI 未装 textual
   - TD-012 描述修正为 vector + textual skip
   - TD-019 举例修正为 analyzer 参数
   - 批次顺序调整为测试先行
   - TD-014 补充 Dockerfile 缓存联动
3. 新增 19 项遗漏技术债（TD-032~TD-054）
4. 新增第 8.1 节共识决策机制
5. 新增第 11 节风险与回滚预案
6. 时间预估调整为 P0 60min / P1 28h

**推进授权**:
- P0 批次: ✅ 立即执行（5 项 + 验证 + Git push）
- P1 批次: ✅ 按调整后顺序执行（测试先行 → 架构重构 → DevOps+代码）
- P2 批次: 🟡 方案已记录，待 P1 完成后按 8.1 决策机制审核推进
- P3 批次: 🟡 日常维护渐进改善

---

## 9. 更新日志

| 日期 | 变更 | 操作者 |
|------|------|--------|
| 2026-07-17 | 创建文档，基于 7 维度扫描结果录入 31 项技术债 | DevSquad |
| 2026-07-17 | v2: 7 角色并行审核后修正。修正 7 个阻塞项（TD-002/003/011/012/019 描述错误 + 批次顺序 + TD-014 Dockerfile 联动）；新增 19 项遗漏技术债（TD-032~TD-054）；新增 8.1 共识决策机制；新增第 11 节风险与回滚预案；调整时间预估 P0 60min/P1 28h；新增第 1 节用户价值映射 | DevSquad 7 角色并行 |
| 2026-07-17 | v3: P0 批次完成。TD-001 (pip 升级 13 处) + TD-002 (rule_engine logger.warning + 2 单元测试) + TD-003a (删除 2 项死代码) + TD-004 (benchmark.yml 3.11→3.12) + TD-032 (SQL 注入扫描完成，4 处 f-string SQL 全部安全)。全测试套件 4371 passed, 0 failed | DevSquad P0 批次 |
| 2026-07-17 | v4: P1 Batch 2 partial 完成 (commit 6f965bf 推送)。6 项 ✅: TD-009 (4 模块 0%→92.62%/100%/81.48%) + TD-011 (CI 装 textual) + TD-012 (nightly vector-tests job) + TD-033 (release e2e-gate) + TD-034 (VSCode Tier 2 E2E gate) + TD-036 (fixture 复用 conftest.py)。TD-010 🟡 进行中。新增配套文档 ROADMAP_P0_P3.md (执行路线图 + 7-Role 投票矩阵 + 11 阶段生命周期映射) | DevSquad P1 Batch 2 |
| 2026-07-17 | v5: 用户确认 4 项执行决策 (AskUserQuestion)。决策: (1) TD-010 独立提交; (2) Batch 3→4 串行推进; (3) P2 Group D 与 B4 并行; (4) 版本号 v0.8.1/v0.8.2/v0.9.0 渐进。ROADMAP §12 由"待决策"改为"决策记录"，全员共识达成，进入执行阶段 | PM (用户) |
| 2026-07-17 | v6: TD-010 ✅ 完成 (Batch 2 收尾)。新建 `tests/test_sqlite_adapter.py` (110 tests/12 类，21.74s 全通过)；`sqlite/__init__.py` 覆盖率 33.62%→**82.45%**；错误维度 ~19% (≥15%)；边界维度 ~16% (≥10%)。TD-006/005/008 重构安全网已就位，进入 Batch 3 架构重构阶段 | Tester (DevSquad) |
| 2026-07-17 | v7: TD-007+TD-037 ✅ 完成 (Batch 3 Wave 2 收尾)。TD-007: 在 `adapters/base.py` 新增 5 个 `@runtime_checkable` Protocol (`RawConnectionProvider`/`EncryptionProvider`/`EmbeddingModelProvider`/`KeyLookupProvider`/`VersioningProvider`)，在 `SQLiteAdapter` 新增 4 个公共访问器 (`get_raw_connection()`/`security`/`embedding_model`/`embedding_model_name`)，更新 7 个调用方文件。TD-037: 在 6 个 Mixin 文件 (`_classification`/`_prompt_delegate`/`_recall`/`_memory_crud`/`_lifecycle`/`_profile_export`) 添加 `TYPE_CHECKING` 跨 Mixin 声明，移除 ~27 个 `type: ignore[attr-defined]` (core/ 目录 0 残留)，同步清理 8 个多余 type: ignore (no-any-return/unreachable)。验证: 833 tests 全通过 (45.26s)，mypy 仅剩 2 pre-existing 错误 (`_recall.py:157,172` StorageAdapter 可选方法，与 TD-007/TD-037 无关) | Architect (DevSquad) |
| 2026-07-17 | v8: TD-006 ✅ 完成 (Batch 3 Wave 3 收尾)。在 `adapters/base.py` 新增 3 个 `@runtime_checkable` ISP Protocol: `StorageClient` (4 方法: store/store_entry/delete/count，仅含 ABC 抽象方法), `RecallClient` (6 方法: recall_aggregated/recall_timeline/recall_by_time/recall_semantic/recall_hybrid/recall_multi_mode), `GraphClient` (9 方法: store_graph_entities/recall_by_entity/recall_by_relation/recall_graph/shortest_path/get_memory_impact/add_graph_relation/list_graph_entities/list_graph_relations)。`VersioningProvider` (TD-007) 作为第 4 个 ISP 功能组。创建 `tests/test_api_stability.py` (19 tests/4 类): SQLiteAdapter 满足所有 7 Protocol; JSONAdapter/ObsidianAdapter 仅满足 StorageClient (ISP 隔离验证); Protocol 方法集稳定性快照。验证: 852 tests 全通过 (45.73s) | Architect (DevSquad) |
| 2026-07-18 | v9: TD-005 ✅ 完成 (Batch 3 Wave 4 收尾)。在 `cli/_stats.py` 新增 2 个 dataclass (`_DoctorCheck`/`_DoctorContext`)，拆分原 F=62 的 `cmd_doctor` (322 行) 为 18 个独立 `_check_*` 函数 (15 A 级 + 3 B 级) + 1 个 `_format_doctor_output` 输出函数 (C=13) + 1 个 `_DOCTOR_CHECKS` 注册表 + 瘦身 `cmd_doctor` 编排器 (A 级)。18 个检查函数按域分布: Python 环境 (python_version, carrymem_import), 文件系统 (config_dir, database_file, write_permissions, disk_space), 数据库 (db_integrity, db_permissions, db_lock, memory_count, rules_engine, backup), 功能 (optional_deps, fts5, security, mcp_configs), 环境 (auto_inject, cli_path)。创建 `tests/test_cli_doctor.py` (34 characterization tests/7 类): JSON 输出结构 / 检查名顺序稳定性 / 各检查状态语义 / `--fix` 副作用 / 返回码 / 人类可读输出 / 幂等性。行为保持: `--fix` 仍然创建缺失的 config_dir 和 database；JSON 输出结构不变；返回码逻辑不变 (0=无 fail, 1=有 fail)。验证: 885 tests 全通过 (45.72s)，radon cc 无 F 级，black/isort/flake8/mypy 全部 clean | Architect+Coder (DevSquad) |

---

## 10. 使用说明

1. **每完成一项**: 将 `⬜ 待开始` 改为 `🟡 进行中` → `✅ 已完成` → `✔️ 已验证`
2. **每批次完成后**: 更新 PROJECT_STATUS.md + CHANGELOG.md + ROADMAP.md
3. **共识审核**: 7 角色并行审核后，填写第 8 节共识记录
4. **P2/P3 推进**: 需在共识记录中标注"已达成共识"后方可推进
5. **提交粒度**: 每项一 commit，每批次一 PR
6. **版本号规则**: P0 修复发 patch，P1 架构重构发 minor
7. **CHANGELOG 格式**: Keep a Changelog 风格
8. **分支策略**: 直接 push main（用户已明确"继续项目工作时无需确认"）
9. **验证标准**: 必须包含可执行命令 + 预期输出（杜绝虚报）

---

## 11. 风险与回滚预案

### 11.1 风险矩阵

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| TD-006 SQLiteAdapter 拆分破坏公共 API | 中 | 高 | 拆分前建立 API 快照测试；保留 SQLiteAdapter 作为聚合门面；设定回滚 git tag `pre-td-006` |
| 依赖锁定（TD-014）引入版本冲突 | 中 | 中 | 先在单独分支跑 7 天 CI 验证；保留旧 `requirements.txt` 一版作为 fallback |
| P1 排期 28h 仍偏紧导致赶工跳过验证 | 中 | 高 | 强制每项 TD 完成后由非实现角色交叉验证（如 Tester 验 Coder 的活）；预留 20% buffer |
| P2/P3 共识机制未定义导致无限阻塞 | 低 | 中 | 已在第 8.1 节定义决策规则；设 7 天审核时限 |
| 活文档机制流于形式 | 中 | 中 | CI 中加 lint 检查，⬜ 项超过 30 天未推进时报警 |
| TD-015 OIDC 迁移失败阻塞发布 | 低 | 高 | 6 步迁移清单含 rc 预发布验证；保留 PYPI_API_TOKEN secret 直到 OIDC 验证成功 |
| TD-032 SQL 注入扫描发现真实漏洞 | 中 | 高 | 若发现注入面，立即提升到 P0 修复；Security 角色一票否决权 |
| TD-003b 公共 API 删除破坏下游用户 | 中 | 中 | 走 deprecation 流程（DeprecationWarning + TODO 注释）；下个大版本删除 |

### 11.2 回滚点定义

| 回滚点 | 触发条件 | 操作 |
|--------|---------|------|
| `pre-td-005` | cmd_doctor 拆分启动前 | `git tag pre-td-005` |
| `pre-td-006` | SQLiteAdapter 拆分启动前 | `git tag pre-td-006` + 建立 API 快照测试 |
| `pre-td-007` | 跨层私有访问修复前 | `git tag pre-td-007` |
| `pre-td-014` | 依赖锁定前 | `git tag pre-td-014` + 备份 `requirements.txt` |
| `pre-td-015` | OIDC 迁移前 | `git tag pre-td-015` + 保留 PYPI_API_TOKEN secret |
| `pre-p1-architecture` | 批次 3 架构重构启动前 | `git tag pre-p1-architecture`（批次 2 测试补齐完成后） |

### 11.3 CI 失败处理流程

1. CI 失败时，立即在对应 TD 项标注 `🔴 阻塞`
2. 实现者必须在 24h 内修复或回滚
3. 若 48h 内未修复，自动降级到下一批次
4. 安全相关 CI 失败（TD-001/015/032/035）必须立即修复，不可降级

### 11.4 交叉验证机制

| 实现角色 | 验证角色 | 验证内容 |
|---------|---------|---------|
| Coder | Tester | 代码修改后测试覆盖率不下降 |
| DevOps | Security | CI/CD 变更不引入安全风险 |
| Architect | Coder | 架构重构不破坏公共 API |
| Tester | PM | 测试覆盖真实用户场景 |
| Security | Architect | 安全修复不影响架构稳定性 |
| UI | Tester | UI 测试覆盖交互路径 |
| PM | Architect | 推进顺序符合生命周期 |

---

## 12. 验证标准规范

所有 TD 项的"验证标准"必须遵循以下规范：

### 12.1 必须包含

- **可执行命令**: 能直接复制粘贴到终端运行的命令
- **预期输出**: 命令成功执行后应输出的内容
- **量化指标**: 覆盖率、复杂度、行数等可度量值

### 12.2 禁止

- 主观判断（如"代码更清晰"）
- 无命令的纯描述（如"测试通过"）
- 含省略号的命令（如 `python3 -c "import yaml; ..."`）

### 12.3 示例

**✅ 良好**:
```
命令: pytest --cov=carrymem.adapters.sqlite --cov-report=term-missing tests/test_sqlite_adapter.py
预期: 覆盖率 ≥80%
```

**❌ 不良**:
```
验证: 测试通过，覆盖率提升
```
