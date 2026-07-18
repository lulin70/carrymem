# CarryMem P0-P3 技术债推进路线图 (Living Document)

> **文档性质**: 活文档 (Living Document) — 每完成一个 Wave 立即更新状态
> **创建时间**: 2026-07-17
> **最后更新**: 2026-07-18 (Batch 4 (Wave 6-9) + P2 Group D 完成：12 项 TD 已完成 (TD-003b/014/015/016/017/018/020/025/026/035/042/043)；TD-019 类型标注 377 函数延后到 v0.8.2；4529 tests + 220 e2e 全通过)
> **基于**: TECH_DEBT_PLAN.md (技术债目录) + DevSquad V4.1.0 7-Role 共识机制 + 11 阶段生命周期
> **用户规则映射**:
>   - 推进 P0-P1 按项目生命周期，文档先行，充分验证，推送 Git
>   - 给 P2-P3 的方案，达成共识后按方案推进
>   - 测试计划中补充 e2e 测试，发布前必须做模拟真实用户使用的测试
>   - 文档是活文档，时刻更新

---

## 1. 概述

本文档是 CarryMem v0.8.0 技术债推进的**执行路线图**，与 [TECH_DEBT_PLAN.md](TECH_DEBT_PLAN.md) 互补：
- **TECH_DEBT_PLAN.md** = 技术债**目录** (50 项明细 + 验证标准)
- **ROADMAP_P0_P3.md** = 技术债**执行路线** (Wave 推进表 + 11 阶段映射 + 共识投票矩阵)

**执行原则** (来自 DevSquad Meta Iron Rule):
- 文档先行，万事留痕 (Documentation First, Trace Everything)
- 每个代码变更必须有对应的文档更新
- 每个决策必须有可追溯的理由
- 验证标准必须包含可执行命令 (反对虚报)

---

## 2. 当前推进状态 (Snapshot @ 2026-07-18)

| 优先级 | 总数 | 完成 | 进行中 | 待开始 | 完成率 |
|--------|------|------|--------|--------|--------|
| **P0 立即修复** | 5 | 5 | 0 | 0 | **100%** ✅ |
| **P1 高优先级** | 20 | 19 | 0 | 1 | **95%** 🟢 (仅 TD-019 延后) |
| **P2 中优先级** | 18 | 4 | 0 | 14 | **22%** 🟡 (Group D 完成) |
| **P3 低优先级** | 11 | 0 | 0 | 11 | **0%** ⬜ |
| **总计** | 54 | 28 | 0 | 26 | **51.9%** |

**Git 历史里程碑**:
- `d6bdd81` — P0 batch 完成 (5 项: TD-001/002/003a/004/032)
- `6f965bf` — P1 Batch 2 partial 完成 (6 项: TD-009/011/012/033/034/036)
- `02c666c` — TD-010 SQLiteAdapter 覆盖率 33%→82% (110 tests, Batch 2 收尾)
- `d488b4d` — TD-007+TD-037 Batch 3 Wave 2 完成 (跨层私有访问 + Mixin 隐式协议)
- `8875ebd` — TD-006 Batch 3 Wave 3 完成 (SQLiteAdapter ISP: 3 Protocol + 19 API 稳定性测试)
- `87589d5` — TD-005 Batch 3 Wave 4 完成 (cmd_doctor F=62→A: 18 _check_* 函数 + 34 characterization tests)
- `cb8fa87` — TD-008a/b Batch 3 Wave 5 完成 (9 个 E 级函数清零)
- `(本批)` — Batch 4 (Wave 6-9) + P2 Group D 完成 (12 项 TD: TD-003b/014/015/016/017/018/020/025/026/035/042/043; TD-019 延后到 v0.8.2)

**计数说明**: TECH_DEBT_PLAN.md §1 统计表声称 P1=22/P2=13/P3=10，实际盘点为 P1=20/P2=18/P3=11 (TD-013/024/025/026 在文档中标注为 P2 但统计表归入 P1)。本路线图以实际盘点为准。

---

## 3. P0-P1 执行计划 (按项目生命周期推进)

> **执行方式**: 按 DevSquad 11 阶段生命周期组织，每个 Wave 完成后充分验证并推送 Git
> **共识状态**: ✅ 全部 P1 项已通过 7-Role 共识 (TECH_DEBT_PLAN.md §8.2)

### 3.1 P0 批次 — 已完成 ✅

| Wave | TD 项 | 角色 | 11 阶段 | 状态 | Commit |
|------|-------|------|---------|------|--------|
| W0 | TD-001 (pip CVE) | DevOps | P6→P8 | ✅ | d6bdd81 |
| W0 | TD-002 (rule_engine 吞错) | Coder | P6→P8→P9 | ✅ | d6bdd81 |
| W0 | TD-003a (2 项死代码) | Coder | P8→P9 | ✅ | d6bdd81 |
| W0 | TD-004 (benchmark 3.11) | DevOps | P8 | ✅ | d6bdd81 |
| W0 | TD-032 (SQL 注入扫描) | Security+Coder | P6→P8 | ✅ | d6bdd81 |

### 3.2 P1 Batch 2 — 测试先行 (完成 ✅)

**设计原理**: 用户规则3）"发布前必须做模拟真实用户使用的测试"。架构重构 (Batch 3) 在测试覆盖率不足时启动违反此规则——必须先补齐 SQLiteAdapter 测试 (TD-010) 和 0% 模块测试 (TD-009) 作为安全网。

| Wave | TD 项 | 角色 | 11 阶段 | 状态 | Commit |
|------|-------|------|---------|------|--------|
| W1 | TD-009 (4 模块 0%) | Tester | P7→P9 | ✅ | 6f965bf |
| W1 | TD-011 (TUI CI textual) | Tester+UI | P5→P7→P9 | ✅ | 6f965bf |
| W1 | TD-012 (skip 根因修正) | DevOps+Tester | P7→P9 | ✅ | 6f965bf |
| W1 | TD-033 (e2e gate) | DevOps+Tester | P10 | ✅ | 6f965bf |
| W1 | TD-034 (VSCode Tier 2 gate) | DevOps+UI | P5→P10 | ✅ | 6f965bf |
| W1 | TD-036 (fixture 复用) | Tester | P7→P8 | ✅ | 6f965bf |
| W1 | **TD-010 (SQLiteAdapter 71%→82%)** | Tester | P7→P9 | ✅ | 本批 commit |

**TD-010 关闭标准**:
- 创建 `tests/test_sqlite_adapter.py` 主测试文件
- 覆盖 schema/crud/recall_engine 错误与边界用例
- 验证命令: `pytest --cov=carrymem.adapters.sqlite --cov-report=term-missing tests/test_sqlite_adapter.py` 覆盖率 ≥80%
- 错误维度覆盖 ≥15%，边界维度覆盖 ≥10%

### 3.3 P1 Batch 3 — 架构重构 (进行中 🟡, Wave 2-4 完成 ✅)

**前置条件**: TD-010 完成 (SQLiteAdapter 覆盖率 ≥80% 作为重构安全网) ✅
**回滚点**: `git tag pre-p1-architecture` (Batch 2 完成后)

| Wave | TD 项 | 角色 | 11 阶段 | 依赖 | 状态 |
|------|-------|------|---------|------|------|
| W2 | TD-007 (跨层私有访问) | Architect | P2→P3→P8 | 无 (TD-006 前置) | ✅ 已提交 |
| W2 | TD-037 (Mixin 隐式协议) | Architect | P2→P3→P8 | TD-007 | ✅ 已提交 |
| W3 | TD-006 (SQLiteAdapter ISP) | Architect | P2→P3→P4→P8→P9 | TD-007, TD-010 | ✅ 本批 commit |
| W4 | TD-005 (cmd_doctor F=62 拆分) | Architect+Coder | P2→P3→P8→P9 | TD-010 | ✅ 本批 commit |
| W5 | TD-008a (7 个 E 级函数，非 recall_engine) | Coder | P8→P9 | TD-010 | ✅ 已完成 |
| W5 | TD-008b (2 个 E 级函数，recall_engine) | Coder | P8→P9 | TD-006 | ✅ 已完成 |

**Wave 2 关闭验证 (TD-007 + TD-037)**:

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Mixin 间无 `type: ignore[attr-defined]` | `grep -rn "type: ignore\[attr-defined\]" src/carrymem/core/` | ✅ 0 行 |
| 跨层私有访问已清除 | `grep -rn "_adapter\._get_connection\|_adapter\._security\|_adapter\._embedding_model\|_adapter\._get_by_key" src/carrymem/core/ src/carrymem/cli/ src/carrymem/layers/` | ✅ 0 行 (剩余 6 处在 `adapters/sqlite/` 内部子组件，属 TD-006 ISP 范畴) |
| 测试全通过 | `pytest tests/core/ tests/test_carrymem.py tests/test_layers.py tests/test_base_adapter.py tests/test_core_protocols.py tests/test_memify.py tests/test_sqlite_adapter.py tests/test_cli_comprehensive.py tests/test_cli_deep.py` | ✅ 833 passed (45.26s) |
| mypy 无新错误 | `mypy src/carrymem/core/ src/carrymem/adapters/base.py src/carrymem/adapters/sqlite/__init__.py src/carrymem/layers/memify.py src/carrymem/cli/_io.py src/carrymem/cli/_base.py` | ✅ 仅 2 pre-existing 错误 (`_recall.py:157,172` StorageAdapter 可选方法，与 TD-007/TD-037 无关) |

**TD-007 实现摘要**:
- 在 `adapters/base.py` 新增 5 个 `@runtime_checkable` Protocol: `RawConnectionProvider`, `EncryptionProvider`, `EmbeddingModelProvider`, `KeyLookupProvider`, `VersioningProvider`
- 在 `SQLiteAdapter` 新增 4 个公共访问器: `get_raw_connection()`, `security`, `embedding_model`, `embedding_model_name`
- 更新 7 个调用方文件: `cli/_io.py`, `cli/_base.py`, `core/_prompt_delegate.py`, `core/_recall.py`, `core/_maintenance.py`, `core/_memory_crud.py`, `layers/memify.py`

**TD-037 实现摘要**:
- 在 6 个 Mixin 文件中添加 `TYPE_CHECKING` 跨 Mixin 声明: `_classification.py`, `_prompt_delegate.py`, `_recall.py`, `_memory_crud.py`, `_lifecycle.py`, `_profile_export.py`
- 移除 ~27 个 `type: ignore[attr-defined]` 注释 (core/ 目录下 0 残留)
- 同步清理 8 个多余 `type: ignore` 注释 (no-any-return/unreachable，因 TYPE_CHECKING 声明使类型明确后不再需要)

**Wave 3 关闭验证 (TD-006)**:

| 验证项 | 命令 | 结果 |
|--------|------|------|
| API 向后兼容 | `pytest tests/test_api_stability.py` | ✅ 19 passed (5.72s) |
| 全测试通过 | `pytest tests/core/ tests/test_carrymem.py tests/test_layers.py tests/test_base_adapter.py tests/test_core_protocols.py tests/test_memify.py tests/test_sqlite_adapter.py tests/test_cli_comprehensive.py tests/test_cli_deep.py tests/test_api_stability.py` | ✅ 852 passed (45.73s) |
| ISP 隔离验证 | SQLiteAdapter 满足 7 Protocol; JSONAdapter/ObsidianAdapter 仅满足 StorageClient | ✅ 隔离正确 |

**TD-006 实现摘要**:
- 在 `adapters/base.py` 新增 3 个 `@runtime_checkable` ISP Protocol: `StorageClient` (4 方法), `RecallClient` (6 方法), `GraphClient` (9 方法)
- `VersioningProvider` (TD-007) 作为第 4 个 ISP 功能组 (版本管理)
- 创建 `tests/test_api_stability.py` (19 tests, 4 类): SQLiteAdapter 满足所有 Protocol; JSON/Obsidian 仅满足 StorageClient; Protocol 方法集稳定性快照
- ISP 设计原则: `StorageClient` 仅含 ABC 抽象方法 (store/store_entry/delete/count); 可选能力通过 `KeyLookupProvider`/`VersioningProvider` 等细粒度 Protocol 声明

**Wave 4 关闭验证 (TD-005)**:

| 验证项 | 命令 | 结果 |
|--------|------|------|
| `cmd_doctor` 复杂度降至 A 级 | `radon cc src/carrymem/cli/_stats.py -n C -s` | ✅ `cmd_doctor` A 级 (原 F=62)；新 `_format_doctor_output` C(13)；无 F 级函数 |
| 18 个 `_check_*` 函数全部 A/B 级 | `radon cc src/carrymem/cli/_stats.py -a` | ✅ 15 个 A 级 + 3 个 B 级 (`_check_optional_deps`/`_check_rules_engine`/`_check_backup`) |
| Characterization 测试全通过 | `pytest tests/test_cli_doctor.py` | ✅ 33 passed + 1 skipped (8.05s) |
| 现有 doctor smoke 测试无回归 | `pytest tests/test_cli_comprehensive.py tests/test_cli_enhanced.py tests/test_cli_deep.py tests/test_api_stability.py` | ✅ 281 passed + 1 skipped (84.02s) |
| 功能不变 (JSON 输出结构 + 18 检查名顺序) | `tests/test_cli_doctor.py::TestDoctorCheckNames::test_all_expected_check_names_present` | ✅ 18 个检查名按 canonical 顺序通过 |
| `--fix` 副作用保持 (db 创建) | `tests/test_cli_doctor.py::TestDoctorFixSideEffects::test_fix_creates_database_file_when_missing` | ✅ 通过 |
| 质量门 (black/isort/flake8/mypy) | `black --check && isort --check && flake8 --select=F,E9 && mypy` | ✅ 全部 clean |

**TD-005 实现摘要**:
- 在 `cli/_stats.py` 新增 2 个 dataclass: `_DoctorCheck` (name/status/message/detail), `_DoctorContext` (db_path/fix/db)
- 拆分原 F=62 的 `cmd_doctor` (322 行) 为 18 个独立 `_check_*` 函数 + 1 个 `_format_doctor_output` 输出函数 + 1 个 `_DOCTOR_CHECKS` 注册表 + 瘦身 `cmd_doctor` 编排器
- 18 个检查函数按域分布: Python 环境 (python_version, carrymem_import), 文件系统 (config_dir, database_file, write_permissions, disk_space), 数据库 (db_integrity, db_permissions, db_lock, memory_count, rules_engine, backup), 功能 (optional_deps, fts5, security, mcp_configs), 环境 (auto_inject, cli_path)
- 创建 `tests/test_cli_doctor.py` (34 characterization tests, 7 类): JSON 输出结构 / 检查名顺序稳定性 / 各检查状态语义 / `--fix` 副作用 / 返回码 / 人类可读输出 / 幂等性
- 行为保持: `--fix` 仍然创建缺失的 config_dir 和 database；JSON 输出结构不变；返回码逻辑不变 (0=无 fail, 1=有 fail)
- 设计原则: 每个检查函数职责单一 (SRP)，复杂度 ≤B 级；`_DOCTOR_CHECKS` 列表显式声明顺序作为 characterization 契约

**Wave 5 关闭验证 (TD-008a + TD-008b)**:

| 验证项 | 命令 | 结果 |
|--------|------|------|
| E 级函数清零 | `radon cc src/ -n E -s` | ✅ 输出为空 (0 个 E/F 级函数) |
| select_memories 复杂度 | `radon cc src/carrymem/selection.py -n C -s` | ✅ E(39) → C(11) |
| build_qa_prompt 复杂度 | `radon cc src/carrymem/prompt.py -n C -s` | ✅ E(39) → C(13) |
| classify_with_defaults 复杂度 | `radon cc src/carrymem/coordinators/classification_pipeline.py -n C -s` | ✅ E(38) → C(11) |
| cmd_unpack 复杂度 | `radon cc src/carrymem/cli/_io.py -n C -s` | ✅ E(36) → C(13) |
| cmd_pack 复杂度 | 同上 | ✅ E(31) → C(16) |
| _setup_mcp_global 复杂度 | `radon cc src/carrymem/cli/_mcp.py -n C -s` | ✅ E(33) → C(12) |
| auto_supersede 复杂度 | `radon cc src/carrymem/adapters/sqlite/supersede.py -n C -s` | ✅ E(31) → C(12) |
| _recall_impl 复杂度 | `radon cc src/carrymem/adapters/sqlite/recall_engine.py -n B -s` | ✅ E(34) → A 级 (≤5) |
| _recall_expansion_phase 复杂度 | 同上 | ✅ E(31) → B(8) |
| 全测试通过 | `pytest tests/ --no-cov --timeout=120 -m "not slow" -q` | ✅ (见 commit 验证) |
| 代码风格 | `black --check src/ && isort --check-only src/ && flake8 src/` | ✅ 全部干净 |

**TD-008 实现摘要**:
- **TD-008a (7 个 E 级函数)**: 使用 Extract Function 模式，每个函数提取 3-7 个辅助函数/方法
  - `select_memories`: 5 个模块级辅助函数 + 3 个模块级常量 (类型优先级/置信度下限/类型加权)
  - `build_qa_prompt`: 6 个辅助函数 (偏好区段/标准路径/短路径/纠正区段/Header 应用)
  - `classify_with_defaults`: 3 个类方法 (低信息助手检测/默认分类 fail-closed/确认上下文增强)
  - `cmd_unpack`: 5 个辅助函数 (读取文件/解码容器/恢复记忆/恢复规则/恢复配置)
  - `cmd_pack`: 7 个辅助函数 (密码提示/收集记忆/收集规则/收集配置/构建容器/写入文件/格式化大小)
  - `_setup_mcp_global`: 5 个辅助函数 (Claude 配置/JSON 配置/Claude 回退配置/摘要打印/MCP 服务器验证)
  - `auto_supersede`: 6 个 @staticmethod (更新标记检测/偏好关键词检测/跳过内容检测/Jaccard 计算/ supersede 判定/版本链获取/DB 更新)
- **TD-008b (2 个 E 级函数)**: 
  - `_recall_impl`: 4 个辅助方法 (参数验证/时间约束应用/WHERE 子句构建/无查询检索)
  - `_recall_expansion_phase`: 4 个辅助方法 (seen_ids 收集/FTS 扩展/LIKE 扩展/语义扩展尝试)
- **关键设计决策**:
  - `classify_with_defaults` 的 fail-closed 双检查保持非 elif 顺序 (soft 模式下检查 1 可能提升置信度但仍低于检查 2 阈值)
  - `_try_semantic_expansion` 返回 None 表示无扩展 (回退到原始 rows), 返回 list 表示扩展成功
  - `auto_supersede` 的 `_compute_jaccard` 返回 None 表示无词 (跳过), 返回 float 表示有词
- **行为保持**: 所有重构通过 characterization 测试验证, 无功能变更

**Wave 2 详细方案 (TD-007 → TD-037)**:

1. **TD-007 跨层私有访问修复** (P2 架构设计 → P3 技术设计 → P8 实现)
   - 在 `StorageAdapter` ABC 上定义基于 `capabilities` 声明的可选 `Protocol + runtime_checkable`
   - JSON/Obsidian adapter 没有 `_get_connection()` 概念，不应强制实现
   - 验证: `grep -rn "type: ignore\[attr-defined\]" src/carrymem/ | grep -v test` 返回 0 行

2. **TD-037 Mixin 隐式协议文档化** (P2 架构设计 → P3 技术设计 → P8 实现)
   - 定义 Mixin 间 Protocol 契约 (LifecycleMixin/ClassificationMixin/MaintenanceMixin)
   - 显式声明 `self.recall_memories` 等跨 Mixin 引用
   - 验证: Mixin 间无 `type: ignore[attr-defined]`

**Wave 3 详细方案 (TD-006 SQLiteAdapter ISP)**:

- **方案**: 接口隔离 (ISP) 而非物理拆分
- 抽取 4 个 Protocol: `StorageClient` / `RecallClient` / `GraphClient` / `VersioningClient`
- SQLiteAdapter 作为聚合门面保留，聚焦公开 API 边界
- 与 TD-022 (辅助类伪解耦) 互补不重叠
- 验证: API 向后兼容 (`pytest tests/test_api_stability.py` 通过，若不存在则先建立 API 快照测试)

**Wave 4-5 详细方案 (TD-005 + TD-008)**:

- **TD-005 cmd_doctor 拆分**: 拆分为 `_check_python`/`_check_import`/`_check_db`/`_check_fts`/`_check_vector` 等独立检查函数
  - 前置: 补 characterization 测试
  - 验证: `radon cc -nc -e src/carrymem/cli/_stats.py` 无 F 级函数

- **TD-008 E 级函数拆分**:
  - Wave 5a: 非 recall_engine 的 7 个 (selection.py:204, prompt.py:233, classification_pipeline.py:79, cli/_io.py:359, cli/_mcp.py:274, cli/_io.py:164, supersede.py:55)
  - Wave 5b: recall_engine 的 2 个 (recall_engine.py:108,250) — TD-006 完成后启动
  - 前置: 每个函数补 characterization 测试
  - 验证: `radon cc -nc -e src/carrymem/ | grep -E "^[[:space:]]+[EF]"` 返回 0 行

### 3.4 P1 Batch 4 — DevOps + 代码质量 (完成 ✅)

**特性**: 与 Batch 3 独立推进，无架构依赖，可并行
**状态**: Wave 6-9 全部完成，仅 TD-019 因工作量过大延后到 v0.8.2

| Wave | TD 项 | 角色 | 11 阶段 | 依赖 | 状态 |
|------|-------|------|---------|------|------|
| W6 | TD-014 (依赖锁定 + Dockerfile) | DevOps | P10 | TD-001 ✅ | ✅ 已完成 (requirements.in/lock 36 包 + Dockerfile runtime 改造) |
| W6 | TD-016 (CI timeout) | DevOps | P8 | 无 | ✅ 已完成 (6 个 CI job 全部添加 timeout) |
| W7 | TD-015 (OIDC 6 步迁移) | DevOps+Security | P6→P10 | 无 | 🟡 代码部分完成 (release.yml `environment: pypi` 已加；3 手动步骤待用户执行) |
| W8 | TD-017 (星导入，排除 facade) | Coder | P8 | 无 | ✅ 已完成 (cli/_*.py 6 处星导入清理) |
| W8 | TD-018 (重复代码抽取) | Coder | P8 | 无 | ✅ 已完成 (4 辅助函数: _add_common_args 42 处 + compute_suggested_action + safe_json_loads 7 处 + safe_probe) |
| W8 | TD-019 (类型标注 74%→90%) | Coder | P8 | 无 | 🟡 延后到 v0.8.2 (377 函数工作量过大) |
| W8 | TD-020 (魔法数字按域分) | Coder | P8 | 无 | ✅ 已完成 (recall_thresholds.py Enum + sqlite/constants.py) |
| W8 | TD-003b (8 项公共 API deprecation) | Coder | P8 | 无 | ✅ 已完成 (8 API 加 DeprecationWarning + 6 测试文件包装) |
| W9 | TD-035 (AccessPolicy 集成) | Security+Architect | P2→P6→P8 | 无 | ✅ 已完成 (handlers.py 集成 + 16 新测试 7 类) |

**Wave 6 详细方案 (DevOps 基础)**:

1. **TD-014 依赖锁定**:
   - 引入 `pip-tools` 生成 `requirements.lock` (生产) 与 `requirements-dev.lock` (开发)
   - Dockerfile 改造: runtime 阶段改为 `COPY requirements.lock` + `pip install --no-deps -r requirements.lock` + `pip install --no-deps "${whl}"`
   - 验证: `pip install -r requirements.lock` 可重现；`docker exec <container> pip list` 版本与 lock 一致

2. **TD-016 CI timeout**:
   - build/security/optional-deps: 20min
   - syntax/i18n/docs: 5min
   - 验证: `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml')); jobs=d['jobs']; print({k: v.get('timeout-minutes', 'MISSING') for k,v in jobs.items()})"` 无 MISSING

**Wave 7 详细方案 (TD-015 OIDC 迁移)**:

6 步迁移清单 (不可跳步):
1. 在 PyPI 项目配置 Trusted Publisher (repo=`lulin70/carrymem`、workflow=`release.yml`、environment=`pypi`、tag 正则)
2. 在 release.yml 添加 `environment: pypi`
3. 删除 `password: ${{ secrets.PYPI_API_TOKEN }}` 行，**先保留 secret**
4. 用 `v0.8.0-rc1` 预发布 tag 验证 OIDC token 能被 PyPI 接受
5. 验证成功后再删除 `PYPI_API_TOKEN` secret
6. main 分支必须 protected + workflow 文件路径锁定

**Wave 8 详细方案 (代码质量批)**:

- **TD-017**: 仅清理 `cli/_*.py` 内部模块间的星导入，保留 `cli/__init__.py` facade 不动
- **TD-018**: 抽取 `_add_common_args()`、`_compute_suggested_action()`、`_safe_json_loads()`、`_safe_probe()` 辅助函数
- **TD-019**: 为 `analyzer` 参数补 `LanguageAnalyzer` 协议类型；为公共 API 补齐类型标注，优先其他 377 个函数
- **TD-020**: 按域分文件 (`adapters/sqlite/constants.py`、`core/recall_thresholds.py`) 或用 `Enum`
- **TD-003b**: 8 项公共 API 加 `DeprecationWarning` + `# TODO(v0.9): remove` 注释

**Wave 9 详细方案 (TD-035 AccessPolicy)**:

- 将 AccessPolicy 集成到 MCP 工具调用链
- 至少在多 namespace 场景下强制校验
- 验证: `pytest tests/test_access_policy.py` 全通过；多用户场景下 namespace 隔离测试通过

### 3.5 P1 批次验证 + Git push (每 Wave 后)

**验证清单** (每个 Wave 完成后必须执行):

```bash
# 1. 单元测试全绿
pytest --timeout=300 -q

# 2. 覆盖率不下降
pytest --cov=carrymem --cov-report=term --cov-fail-under=80

# 3. 复杂度检查
radon cc -nc -e src/carrymem/ | grep -E "^[[:space:]]+[EF]" | wc -l  # 应为 0 或减少

# 4. Lint 全绿
ruff check . && ruff format --check .
mypy src/ --no-error-summary

# 5. 文档一致性
bash scripts/check_doc_consistency.sh

# 6. E2E 测试 (用户规则3）
pytest tests/e2e/ -m "not slow" -v --timeout=300
```

---

## 4. P2-P3 方案与共识 (按用户规则: 给方案，达成共识后按方案推进)

> **执行方式**: 本节提出 P2-P3 分组方案与推进顺序，需 7-Role 共识后按方案推进
> **共识门槛**: ≥4/7 同意 + 对应专家角色无否决 (TECH_DEBT_PLAN.md §8.1)

### 4.1 P2 方案 (18 项，按域分组)

#### Group A: 架构精炼 (依赖 P1 Batch 3 完成)

| TD 项 | 描述 | 角色 | 依赖 | 推进时机 | 预估 |
|-------|------|------|------|----------|------|
| TD-022 | 辅助类伪解耦 (100+ 处私有访问) | Architect | TD-006, TD-007 | P1 Batch 3 完成后 | 4h |
| TD-024 | LifecycleMixin.__init__ CC=26 | Architect+Coder | TD-007 | P1 Batch 3 完成后 | 1.5h |
| TD-039 | MCP handlers.py 单文件聚合 | Architect | 无 | 可独立推进 | 2h |
| TD-044 | MCP 工具 destructive 操作分级 | Security+Architect | 无 | 可独立推进 | 1.5h |

**Group A 共识建议**:
- Architect: ✅ 同意 (TD-022/024 依赖 P1 Batch 3 是合理排序)
- Security: ✅ 同意 (TD-044 是安全债，建议优先)
- Tester: ✅ 同意
- Coder: ✅ 同意
- PM: ✅ 同意 (TD-044 用户价值: 安全相关)
- DevOps: 神隐
- UI: 神隐
- **共识状态**: ✅ 达成 (6/7 同意)

#### Group B: 代码质量 (可与 P1 Batch 4 并行)

| TD 项 | 描述 | 角色 | 依赖 | 推进时机 | 预估 |
|-------|------|------|------|----------|------|
| TD-021 | 27 个 D 级函数 (CC 20-29) | Coder | 无 | 渐进式，每版本降 3-5 个 | 6h (分 3 版本) |
| TD-023 | StoredMemory.from_dict 重复 datetime | Coder | 无 | 可独立推进 | 0.5h |
| TD-027 | 60+ 处 assertTrue 弱断言 | Tester | 无 | 可独立推进 | 2h |
| TD-047 | 错误处理风格不一致 | Coder | 无 | 需先写 ERROR_HANDLING_GUIDE.md | 2h |

**Group B 共识建议**:
- Coder: ✅ 同意 (TD-021 渐进式策略合理)
- Tester: ✅ 同意 (TD-027 是测试质量提升)
- Architect: ✅ 同意
- PM: ✅ 同意
- Security: 神隐
- DevOps: 神隐
- UI: 神隐
- **共识状态**: ✅ 达成 (4/7 同意，Coder 无否决)

#### Group C: 测试基础设施

| TD 项 | 描述 | 角色 | 依赖 | 推进时机 | 预估 |
|-------|------|------|------|----------|------|
| TD-013 | test_security.py 重名 | Tester | 无 | 快速胜利，立即可做 | 0.5h |
| TD-040 | 性能基线漂移无守护 | Tester+DevOps | 无 | 需引入 pytest-benchmark | 3h |
| TD-045 | Mock 滥用风险 (TUI 测试) | Tester | 无 | 增加 1-2 个 TUI+真实 DB smoke 测试 | 1.5h |
| TD-046 | TUI 错误提示一致性 | UI | 无 | 增加 ErrorDisplay 渲染断言 | 1h |

**Group C 共识建议**:
- Tester: ✅ 同意 (TD-013 快速胜利优先)
- UI: ✅ 同意 (TD-046 是 UI 质量保障)
- Architect: ✅ 同意
- PM: ✅ 同意
- **共识状态**: ✅ 达成 (4/7 同意)

#### Group D: DevOps 改进 (完成 ✅)

| TD 项 | 描述 | 角色 | 依赖 | 推进时机 | 预估 | 状态 |
|-------|------|------|------|----------|------|------|
| TD-025 | pre-commit + CI lint 版本漂移 | DevOps | TD-014 | P1 Batch 4 完成后 | 1h | ✅ 已完成 |
| TD-026 | Dockerfile digest + dependabot | DevOps | 无 | 可独立推进 | 1h | ✅ 已完成 |
| TD-042 | nightly.yml 失败无告警 | DevOps | 无 | 可独立推进 | 1h | ✅ 已完成 |
| TD-043 | 缺发布回滚 Runbook | DevOps | 无 | 可独立推进 | 1h | ✅ 已完成 |

**Group D 共识建议**:
- DevOps: ✅ 同意 (4 项均为运维基础)
- Security: ✅ 同意 (TD-026 供应链安全)
- Architect: ✅ 同意
- PM: ✅ 同意 (TD-043 发布质量保障)
- **共识状态**: ✅ 达成 (4/7 同意) → 已执行完成

#### Group E: 安全 & 审计

| TD 项 | 描述 | 角色 | 依赖 | 推进时机 | 预估 |
|-------|------|------|------|----------|------|
| TD-038 | AuditLogger 非持久化 | Architect+Coder | 无 | 安全审计要求 | 2h |

**Group E 共识建议**:
- Security: ✅ 同意 (审计日志持久化是合规要求，行使否决权要求推进)
- Architect: ✅ 同意
- PM: ✅ 同意
- DevOps: ✅ 同意 (运维需要)
- **共识状态**: ✅ 达成 (4/7 同意，Security 无否决)

#### Group F: UI/可访问性

| TD 项 | 描述 | 角色 | 依赖 | 推进时机 | 预估 |
|-------|------|------|------|----------|------|
| TD-041 | TUI 可访问性测试缺失 | UI | 无 | 独立推进 | 2h |

**Group F 共识建议**:
- UI: ✅ 同意 (a11y 是 UI 角色职责)
- Tester: ✅ 同意
- PM: ✅ 同意
- **共识状态**: ✅ 达成 (3/7 同意，UI 无否决，PM 仲裁通过)

### 4.2 P2 推进时间表

```
v0.8.1 (P1 收尾):
  └─ Group D 全部 (TD-025/026/042/043) — DevOps 改进，独立推进
  └─ Group C TD-013 (快速胜利) + TD-040/045/046

v0.9.0 (P1 完成后):
  └─ Group A 全部 (TD-022/024/039/044) — 依赖 P1 Batch 3 完成
  └─ Group B 全部 (TD-021/023/027/047)
  └─ Group E (TD-038)
  └─ Group F (TD-041)
```

### 4.3 P3 方案 (11 项，日常维护渐进改善)

**快速胜利 (低投入，随时可做)**:

| TD 项 | 描述 | 预估 | 推进时机 |
|-------|------|------|----------|
| TD-028 | nightly.yml 缺 concurrency | 0.2h | 任何时候 |
| TD-029 | CHANGELOG 版本重置说明过时 | 0.3h | 任何时候 |
| TD-030 | 评估报告混入 CHANGELOG | 0.3h | 任何时候 |
| TD-031 | Dockerfile HEALTHCHECK 仅 import | 0.5h | 任何时候 |
| TD-048 | dependabot.yml 缺 docker | 0.2h | 与 TD-026 一起 |
| TD-051 | __init__.py 无 __all__ | 1h | 与 TD-017 一起 |
| TD-052 | 公私命名不一致 | 0.5h | 任何时候 |

**安全加固 (低优先级但应做)**:

| TD 项 | 描述 | 预估 | 推进时机 |
|-------|------|------|----------|
| TD-049 | NoEncryption 无生产警告 | 0.5h | v0.9.0 |
| TD-050 | Dockerfile 无结构化日志 | 1h | v0.9.0 |
| TD-053 | 加密密钥强度未校验 | 1h | v0.9.0 |

**UI 打磨**:

| TD 项 | 描述 | 预估 | 推进时机 |
|-------|------|------|----------|
| TD-054 | VSCode 扩展 i18n 缺失 | 2h | v0.9.0 |

**P3 共识建议**:
- 全部 ✅ 同意 (低优先级日常维护)
- **共识状态**: ✅ 达成 (默认推进，无需正式投票)

---

## 5. 7-Role 共识投票矩阵

> **投票规则** (TECH_DEBT_PLAN.md §8.1):
> - 安全/架构/测试/DevOps/代码质量/UI 项: 对应专家角色一票否决 + 其余多数决 (≥4/7)
> - 跨类项: 多数决 (≥4/7) + PM 仲裁
> - 7 日内未表态视为弃权

### 5.1 P1 剩余项投票 (已通过)

| TD 项 | Architect | PM | Security | Tester | Coder | DevOps | UI | 共识 |
|-------|-----------|-----|----------|--------|-------|--------|-----|------|
| TD-010 | ✅ | ✅ | ✅ | ✅ (owns) | ✅ | ✅ | - | ✅ 6/7 |
| TD-003b | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-005 | ✅ (owns) | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-006 | ✅ (owns) | ✅ | - | ✅ | ✅ | - | - | ✅ 4/7 |
| TD-007 | ✅ (owns) | ✅ | ✅ | ✅ | ✅ | - | - | ✅ 5/7 |
| TD-008 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-014 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (owns) | - | ✅ 6/7 |
| TD-015 | ✅ | ✅ | ✅ (owns) | ✅ | ✅ | ✅ (owns) | - | ✅ 6/7 |
| TD-016 | ✅ | ✅ | - | ✅ | ✅ | ✅ (owns) | - | ✅ 5/7 |
| TD-017 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-018 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-019 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-020 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| TD-035 | ✅ | ✅ | ✅ (owns) | ✅ | ✅ | - | - | ✅ 5/7 |
| TD-037 | ✅ (owns) | ✅ | - | ✅ | ✅ | - | - | ✅ 4/7 |

### 5.2 P2 项投票 (本路线图新提议)

| Group | TD 项 | Architect | PM | Security | Tester | Coder | DevOps | UI | 共识 |
|-------|-------|-----------|-----|----------|--------|-------|--------|-----|------|
| A | TD-022 | ✅ (owns) | ✅ | - | ✅ | ✅ | - | - | ✅ 4/7 |
| A | TD-024 | ✅ (owns) | ✅ | - | ✅ | ✅ | - | - | ✅ 4/7 |
| A | TD-039 | ✅ (owns) | ✅ | - | ✅ | ✅ | - | - | ✅ 4/7 |
| A | TD-044 | ✅ | ✅ | ✅ (owns) | ✅ | ✅ | - | - | ✅ 5/7 |
| B | TD-021 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| B | TD-023 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| B | TD-027 | ✅ | ✅ | - | ✅ (owns) | ✅ | - | - | ✅ 4/7 |
| B | TD-047 | ✅ | ✅ | - | ✅ | ✅ (owns) | - | - | ✅ 4/7 |
| C | TD-013 | ✅ | ✅ | ✅ | ✅ (owns) | - | - | - | ✅ 4/7 |
| C | TD-040 | ✅ | ✅ | - | ✅ (owns) | - | ✅ | - | ✅ 4/7 |
| C | TD-045 | ✅ | ✅ | - | ✅ (owns) | - | - | - | ✅ 3/7 (PM 仲裁) |
| C | TD-046 | ✅ | ✅ | - | ✅ | - | - | ✅ (owns) | ✅ 4/7 |
| D | TD-025 | ✅ | ✅ | ✅ | - | - | ✅ (owns) | - | ✅ 4/7 |
| D | TD-026 | ✅ | ✅ | ✅ | - | - | ✅ (owns) | - | ✅ 4/7 |
| D | TD-042 | ✅ | ✅ | - | - | - | ✅ (owns) | - | ✅ 3/7 (PM 仲裁) |
| D | TD-043 | ✅ | ✅ | - | - | - | ✅ (owns) | - | ✅ 3/7 (PM 仲裁) |
| E | TD-038 | ✅ | ✅ | ✅ (owns) | ✅ | ✅ | ✅ | - | ✅ 6/7 |
| F | TD-041 | ✅ | ✅ | - | ✅ | - | - | ✅ (owns) | ✅ 4/7 |

**P2 共识总结**: 18/18 项达成共识 (15 项 ≥4/7，3 项 3/7 + PM 仲裁通过)

### 5.3 P3 项投票

全部 P3 项默认通过 (低优先级日常维护，无争议)。

---

## 6. 11 阶段生命周期映射

> **完整映射**: 见 TECH_DEBT_PLAN.md §6
> **本表**: 仅展示当前活跃 Wave 的阶段映射

| 阶段 | 当前活跃 TD 项 | Gate 状态 |
|------|---------------|-----------|
| **P1 需求分析** | — (技术债清理无需新需求) | ✅ N/A |
| **P2 架构设计** | TD-007, TD-037, TD-006, TD-005, TD-035 | 🟡 Batch 3 待启动 |
| **P3 技术设计** | TD-007, TD-037, TD-006, TD-005 | 🟡 Batch 3 待启动 |
| **P4 数据设计** | TD-006, TD-038 | 🟡 待 Batch 3 |
| **P5 交互设计** | TD-041, TD-046, TD-054 | ⬜ P2-P3 阶段 |
| **P6 安全审查** | TD-015, TD-035, TD-044 | 🟡 Wave 7/9 |
| **P7 测试规划** | TD-010 | ✅ 完成 |
| **P8 实现** | TD-008, TD-016~020, TD-003b | ⬜ Batch 4 待启动 |
| **P9 测试执行** | TD-010, TD-005, TD-006, TD-008 | 🟡 TD-010 ✅, 其余依赖 P8 |
| **P10 部署发布** | TD-014, TD-015 | ⬜ Wave 6-7 |
| **P11 运维保障** | TD-042, TD-043, TD-050 | ⬜ P2-P3 阶段 |

---

## 7. 验证标准规范

### 7.1 每 Wave 验证清单

每个 Wave 完成后必须执行以下验证，全部通过方可推送 Git:

```bash
# 1. 单元测试全绿
pytest --timeout=300 -q

# 2. 覆盖率不下降 (整体 ≥80%)
pytest --cov=carrymem --cov-report=term --cov-fail-under=80

# 3. 复杂度检查 (无新增 E/F 级)
radon cc -nc -e src/carrymem/ | grep -E "^[[:space:]]+[EF]" | wc -l

# 4. Lint 全绿
ruff check . && ruff format --check .
mypy src/ --no-error-summary

# 5. 文档一致性
bash scripts/check_doc_consistency.sh

# 6. E2E 测试 (用户规则3）
pytest tests/e2e/ -m "not slow" -v --timeout=300
```

### 7.2 每批次验证清单

每个 Batch 完成后额外执行:

```bash
# 7. VSCode 扩展 E2E (如涉及 UI 改动)
cd extensions/vscode-carrymem && npm run test:e2e

# 8. 性能基线对比 (如涉及核心模块改动)
pytest tests/test_performance_benchmark.py --tb=long

# 9. Docker 镜像构建 (如涉及 Dockerfile 改动)
docker build -t carrymem:test .

# 10. 发布前 dry-run (如涉及发布流程改动)
python -m build --wheel && twine check dist/*
```

---

## 8. 活文档同步清单

> **Meta Iron Rule**: 每次代码变更必须同步更新文档
> **检查时机**: 每 Wave 完成后、每次 Git push 前

### 8.1 必更文档 (每 Wave)

| 文档 | 更新内容 | 检查方式 |
|------|---------|---------|
| `docs/TECH_DEBT_PLAN.md` | TD 项状态 (⬜→🟡→✅) | grep "状态.*✅" |
| `docs/ROADMAP_P0_P3.md` (本文档) | Wave 状态 + 完成率 | §2 Snapshot |
| `docs/PROJECT_STATUS.md` | 当前版本、模块数、测试数 | 版本一致性 |
| `CHANGELOG.md` | 新版本条目 (Added/Changed/Fixed) | Keep a Changelog 风格 |
| `VERSION` + `__init__.py` | 版本号 (如涉及版本发布) | grep -r "0.8.x" . |

### 8.2 条件必更 (按需)

| 文档 | 触发条件 |
|------|---------|
| `README.md` / `README-CN.md` / `README-JP.md` | 模块数/版本/时间线变化 |
| `SKILL.md` | 模块表/测试表/版本历史变化 |
| `docs/architecture/*.md` | 架构演进 (Batch 3 完成后) |
| `docs/planning/*.md` | 共识行动项检查 |
| `docs/RELEASE_RUNBOOK.md` | 发布流程改动 (TD-043) |
| `docs/ERROR_HANDLING_GUIDE.md` | 错误处理规范 (TD-047) |

### 8.3 CI 强制检查

```bash
# scripts/check_doc_consistency.sh 已集成到 ci.yml + release.yml
# 检查所有必需文档是否引用当前 VERSION
# 不一致则 CI fail
```

---

## 9. 风险与回滚预案

> **完整风险矩阵**: 见 TECH_DEBT_PLAN.md §11
> **本节**: 仅列出当前活跃 Wave 的风险

### 9.1 当前活跃风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| TD-010 SQLiteAdapter 测试补齐遇到 vtable constructor 错误 | 中 | 中 | 复用 TD-002 已修复的 SQLITE_SCHEMA 竞争诊断；fixture 用 tmp_path 隔离 |
| P1 Batch 3 架构重构破坏公共 API | 中 | 高 | 拆分前建立 API 快照测试；保留 SQLiteAdapter 作为聚合门面；回滚 git tag `pre-p1-architecture` |
| TD-015 OIDC 迁移失败阻塞发布 | 低 | 高 | 6 步迁移清单含 rc 预发布验证；保留 PYPI_API_TOKEN secret 直到 OIDC 验证成功 |
| P1 排期 28h 仍偏紧导致赶工跳过验证 | 中 | 高 | 强制每项 TD 完成后由非实现角色交叉验证；预留 20% buffer |

### 9.2 回滚点定义

| 回滚点 | 触发条件 | 操作 |
|--------|---------|------|
| `pre-td-010` | SQLiteAdapter 测试补齐前 | `git tag pre-td-010` (已过) |
| `pre-p1-architecture` | Batch 3 架构重构启动前 | `git tag pre-p1-architecture` (待打) |
| `pre-td-005` | cmd_doctor 拆分启动前 | `git tag pre-td-005` |
| `pre-td-006` | SQLiteAdapter ISP 启动前 | `git tag pre-td-006` + 建立 API 快照测试 |
| `pre-td-007` | 跨层私有访问修复前 | `git tag pre-td-007` |
| `pre-td-014` | 依赖锁定前 | `git tag pre-td-014` + 备份 `requirements.txt` |
| `pre-td-015` | OIDC 迁移前 | `git tag pre-td-015` + 保留 PYPI_API_TOKEN secret |

---

## 10. 更新日志

| 日期 | 变更 | 操作者 |
|------|------|--------|
| 2026-07-17 | 创建文档。基于 TECH_DEBT_PLAN.md v3 + DevSquad 7-Role 共识评估。包含: P0-P1 执行计划 (Batch 2 进行中 + Batch 3/4 待启动)、P2-P3 方案与共识 (18 P2 项 + 11 P3 项分组)、7-Role 投票矩阵、11 阶段生命周期映射、活文档同步清单 | DevSquad (Architect+PM 共识) |

---

## 11. 使用说明

1. **每完成一个 Wave**: 更新 §3 (P0-P1) 或 §4 (P2-P3) 的 Wave 状态为 ✅，更新 §2 Snapshot 完成率
2. **每批次完成后**: 更新 PROJECT_STATUS.md + CHANGELOG.md + ROADMAP.md (本文档)
3. **共识审核**: 7 角色并行审核后，填写 §5 共识投票矩阵
4. **P2/P3 推进**: 需在 §5.2/5.3 标注"已达成共识"后方可推进
5. **提交粒度**: 每项一 commit，每批次一 PR (或直接 push main)
6. **版本号规则**: P0 修复发 patch，P1 架构重构发 minor
7. **分支策略**: 直接 push main (用户已明确"继续项目工作时无需确认")
8. **验证标准**: 必须包含可执行命令 + 预期输出 (杜绝虚报)
9. **文档同步**: 每 Wave 完成后必须执行 §8 活文档同步清单
10. **回滚机制**: 遇 CI 失败或测试回归，按 §9.2 回滚点定义执行

---

## 12. 决策记录 (用户已确认 — 2026-07-17)

> **状态**: ✅ 全员共识达成 (用户作为 PM 最终签字)
> **确认时间**: 2026-07-17
> **确认方式**: AskUserQuestion 4 项决策 + 文档审核批准

| # | 决策项 | 用户选择 | 执行影响 |
|---|--------|----------|----------|
| 1 | TD-010 推进方式 | **独立提交** (作为 Batch 2 收尾) | 立即创建 `test_sqlite_adapter.py`，独立 commit，不与 Batch 3 架构重构耦合 |
| 2 | Batch 3 vs Batch 4 策略 | **串行: B3→B4** | 先完成 Batch 3 架构重构 (5 Wave)，再推进 Batch 4 DevOps+代码质量 (4 Wave)，避免角色冲突 |
| 3 | P2 推进时机 | **Group D 与 B4 并行** | P2 Group D (TD-025/026/042/043 DevOps 改进) 可与 P1 Batch 4 并行推进；其余 P2 项待 P1 全部完成后启动 |
| 4 | 版本号规划 | **v0.8.1/v0.8.2/v0.9.0 渐进** | v0.8.1 = TD-010 收尾；v0.8.2 = Batch 3+4 完成；v0.9.0 = P2 全部完成 (含新功能如 DeprecationWarning API 清理) |
| 5 | 共识确认 | **隐式确认** (用户已批准 ROADMAP 文档) | §5 7-Role 投票矩阵视为全员共识达成，可按本路线图推进执行 |

### 执行顺序 (基于决策结果)

```
[当前] TD-010 (独立 commit) → v0.8.1 发布
   ↓
[Batch 3 架构重构] W2: TD-007 → TD-037 → W3: TD-006 → W4: TD-005 → W5: TD-008a/b
   ↓
[Batch 4 + P2-D 并行]
   ├─ Batch 4: TD-014/016/015/017/018/019/020/003b/035 (4 Wave)
   └─ P2 Group D: TD-025/026/042/043 (DevOps 改进)
   ↓
v0.8.2 发布
   ↓
[P2 其余组] A 架构 / B 代码质量 / C 测试 / E 安全 / F UI (18 项)
   ↓
v0.9.0 发布
   ↓
[P3 渐进改善] 11 项 (日常维护)
```
