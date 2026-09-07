# CLAUDE.md — CarryMem AI 协作指引

本文件为 AI 代理（Claude / Codex 等）在 CarryMem 仓库内工作提供统一上下文。所有命令均假设在仓库根目录执行，且已激活包含 `dev` extras 的虚拟环境。

---

## 项目概述

- **CarryMem** 是一个可移植的 AI 记忆层：让 AI 自动记住用户的偏好、决策与纠正，跨模型 / 工具 / 设备复用，无需每次重复自我介绍。
- **当前版本**：`0.10.1`（来源：`src/carrymem/__version__.py`）
- **核心技术栈**：
  - Python 3.12+（`setup.py` 中 `python_requires=">=3.12"`）
  - SQLite + FTS5（默认存储与全文检索）
  - MCP（Model Context Protocol）服务器集成
  - 核心依赖：`PyYAML>=5.0` + `cryptography>=46.0.6`（v0.7.3 起 cryptography 为硬依赖），语言检测 / 向量检索 / LLM / TUI 均为可选 extras
- **仓库**：https://github.com/lulin70/carrymem
- **CI 默认分支**：`new-main`（非 `main`，提交 PR 时注意基分支）

---

## 安装与构建

```bash
# 开发模式安装（含 dev extras：pytest 全家桶、black、flake8、mypy、pre-commit 等）
pip install -e ".[dev]"

# 用户安装（已发布到 PyPI）
pip install carrymem

# 完整功能安装
pip install -e ".[full]"

# 构建 sdist + wheel（CI 使用流程）
python -m build
twine check dist/*

# 全新虚拟环境验证安装（CI 的 build gate）
python -m venv /tmp/carrymem_venv
/tmp/carrymem_venv/bin/pip install $(ls dist/carrymem-*.whl | head -1)
/tmp/carrymem_venv/bin/python -c "import carrymem; print(carrymem.__version__)"
```

CLI 入口：`carrymem`（`entry_points` → `carrymem.cli:main`），也可 `python -m carrymem`。

---

## 测试命令

pytest 配置位于 `pyproject.toml` 的 `[tool.pytest.ini_options]`：默认开启 `--cov=carrymem`、`--strict-markers`、`asyncio_mode = "auto"`，覆盖率门槛 `fail_under = 75`。

```bash
# 全量测试（默认带覆盖率，输出 term/html/xml 三份报告）
pytest tests/

# 排除慢测试（CI 主 gate 使用，附加 --timeout=120）
pytest tests/ -m "not slow" -q

# 仅 E2E 测试（tests/e2e/，共 18 个场景文件）
pytest tests/e2e/

# 带覆盖率（默认即开启，显式写法）
pytest tests/ --cov=carrymem --cov-report=term-missing

# 仅单元 / 集成测试（按 marker 过滤）
pytest tests/ -m "unit"
pytest tests/ -m "integration"

# 长超时调试单个文件
pytest tests/test_e2e_mcp_tools.py --timeout=300 -v
```

可用 marker：`slow`、`integration`、`unit`、`asyncio`、`coverage`。

E2E 测试覆盖：并发访问、大数据集、MCP 工具、适配器切换、加密全链路、完整生命周期、用户场景、边界用例、经验精炼、安全管线、版本回滚、用户旅程。发布前务必运行 E2E 套件做模拟真实用户使用的验证。

---

## 代码质量

CI 的 lint gate（`.github/workflows/ci.yml`）执行以下命令，本地应保持一致：

```bash
# 格式检查（line-length=120，target py312）
black --check --diff --color --line-length=120 src/ tests/
isort --check-only --diff src/ tests/

# Lint（max-line-length=120，配置见 .flake8）
flake8 src/ tests/ --count --max-line-length=120 --statistics

# 类型检查（配置在 pyproject.toml [tool.mypy]）
mypy src/
```

### 配置文件

| 文件 | 作用 | 关键设置 |
| --- | --- | --- |
| `pyproject.toml` | pytest / coverage / black / isort / mypy | line-length=120；`[tool.mypy] python_version="3.12"`，`warn_unused_ignores=True`，`strict_equality=True` |
| `.flake8` | flake8 | `max-line-length=120`；`extend-ignore` 含 E203/W503/F403/F405/E402/E731 等 |
| `.pre-commit-config.yaml` | pre-commit 钩子 | black 26.5.0 / isort 6.1.0 / flake8 7.3.0 / mypy v2.1.0 |

```bash
# pre-commit（工具版本须与 CI 对齐）
pre-commit install
pre-commit run --all-files
```

---

## 架构

```
src/carrymem/
├── core/                    # CarryMem Facade + 7 Mixin 组合
│   ├── __init__.py          #   class CarryMem(LifecycleMixin, BackupMixin, MemoryCRUDMixin,
│   │                        #         ClassificationMixin, RecallMixin, ProfileExportMixin,
│   │                        #         MaintenanceMixin, PromptDelegateMixin)
│   ├── _lifecycle.py        #   __init__ / close / 上下文管理器 / 共享属性
│   ├── _protocols.py        #   结构化类型 Protocol（CarryMemOps 等 9 个）
│   ├── _backup.py           #   BackupMixin
│   ├── _memory_crud.py      #   MemoryCRUDMixin
│   ├── _classification.py   #   ClassificationMixin
│   ├── _recall.py           #   RecallMixin
│   ├── _profile_export.py   #   ProfileExportMixin
│   ├── _maintenance.py      #   MaintenanceMixin
│   └── _prompt_delegate.py  #   PromptDelegateMixin
├── adapters/                # 存储适配器（可插拔）
│   ├── base.py              #   StorageAdapter 抽象基类
│   ├── loader.py            #   按 entry_point 加载适配器
│   ├── sqlite_adapter.py    #   SQLiteAdapter（默认，注册名 "sqlite"）
│   ├── obsidian_adapter.py  #   ObsidianAdapter（注册名 "obsidian"，需 vault_path）
│   ├── json_adapter.py      #   JSONAdapter（注册名 "json"）
│   ├── async_sqlite.py      #   AsyncSQLiteAdapter（v0.7.2，[async] extra，aiosqlite）
│   └── sqlite/              #   SQLite 实现细节（schema / crud / recall_engine / connection / versioning / supersede / security / stats / serializer / query_builder）
├── rules/                   # 规则引擎（自动匹配 + 注入 + 精炼 + 晋升管线）
│   ├── __init__.py          #   RuleEngine 入口
│   ├── matcher.py           #   规则匹配
│   ├── injector.py          #   规则注入
│   ├── sanitizer.py / limiter.py
│   ├── candidate_generator.py / candidate_rule_generator.py
│   ├── promotion_pipeline.py / rule_refiner.py / refinement_session.py
│   ├── conflict_detector.py / merge_protocol.py
│   ├── failure_experience.py / experience_bridge.py
│   ├── pattern_detector.py / skill.py / templates.py / models.py / storage.py
├── integration/layer2_mcp/  # MCP 服务器（共 31 个工具，分 9 类）
│   ├── server.py / http_server.py / __main__.py
│   ├── tools.py             #   工具定义（CORE/OPTIONAL/KNOWLEDGE/PROFILE/PROMPT/CONSOLIDATION/RULE/HEALTH_CHECK/GRAPH）
│   └── handlers/            #   工具分发处理（TD-039 拆分的域子包：_base/read/write/graph/rule/system）
├── security/                # 加密 + 权限 + 审计 + 输入校验 + 脱敏
│   ├── encryption.py        #   AES 加密
│   ├── permissions.py       #   AccessPolicy 访问策略
│   ├── audit.py             #   审计日志
│   ├── input_validator.py   #   输入校验
│   └── redaction.py         #   敏感信息脱敏
├── layers/                  # 分类管线 + 知识图谱 + Memify 精炼
│   ├── noise_detector.py    #   噪声检测
│   ├── pattern_analyzer.py  #   模式分析
│   ├── semantic_classifier.py / semantic_aggregator.py
│   ├── rule_matcher.py / memory_pattern_detectors.py / feedback_detector.py / session_summarizer.py
│   ├── knowledge_graph.py   #   KnowledgeGraph 层（v0.7.0，实体提取 + 图遍历）
│   └── memify.py            #   MemifyEngine（v0.7.2，三阶段动态精炼）
├── engine.py                # MemoryClassificationEngine
├── carrymem.py / async_carrymem.py   # 同步 / 异步顶层封装
├── prompt.py / prompt_builder.py     # Prompt 构建
├── scoring.py / selection.py         # 评分与选择（MMR 等）
├── cli.py / cli/                     # CLI 命令
└── __version__.py           # 版本号唯一来源
```

**MCP 31 工具清单**（`src/carrymem/integration/layer2_mcp/tools.py`）：
- CORE(3)：classify_message、get_classification_schema、batch_classify
- OPTIONAL(3)：classify_and_remember、recall_memories、forget_memory
- KNOWLEDGE(3)：index_knowledge、recall_from_knowledge、recall_all
- PROFILE(2)：declare_preference、get_memory_profile
- PROMPT(2)：get_system_prompt、summarize_and_store
- CONSOLIDATION(3)：consolidate_memories、schedule_consolidation、stop_consolidation
- RULE(11)：add_rule、list_rules、match_rules、inject_rules、my_rules、delete_rule、suggest_rules、promote_rules、update_rule、my_profile、onboard
- HEALTH_CHECK(1)：health_check
- GRAPH(3)：query_graph、shortest_path、get_memory_impact

---

## 关键约束（务必遵守）

1. **rule_engine 必须在 `__init__()` 中 eager 初始化**（见 `core/_lifecycle.py` 第 158-171 行）。
   `RuleStorage._ensure_schema()` 会创建 `rules_fts` vtable 与触发器，递增 SQLite schema cookie。若改为懒加载，在并发 `classify_and_remember → rule_engine` 访问期间 schema 变更会使其它连接上的 `memories_fts` vtable 失效，间歇性报 `vtable constructor failed: memories_fts`（SQLITE_SCHEMA）。eager init 确保所有 schema 变更在线程访问前完成。改动 `__init__` 或 rule_engine 属性前务必保留该 eager probe。

2. **FTS5 vtable 的 schema 变更会影响所有连接的 schema cookie**。新增 / 修改 FTS5 vtable 时，必须评估对既有连接（连接池、并发 worker）的影响，避免运行期 `SQLITE_SCHEMA` 错误。

3. **`# type: ignore` 使用 `import-not-found` 码**（而非 `import-untyped`）。pyproject.toml `[tool.mypy]` 设置 `warn_unused_ignores=True`，错误或多余的 ignore 码会被报告，新增 ignore 注释请使用正确错误码。

4. **`.flake8` 不全局屏蔽 F401/F841/F821/F811**（已清理完毕）。`extend-ignore` 仅含 F403/F405 等；F401/F841 仅在 `tests/*` 按 `per-file-ignores` 忽略。不要把这些码加回全局 ignore。

5. **pre-commit 工具版本须与 CI 对齐**（见 `.pre-commit-config.yaml` 顶部注释）。升级 black / isort / flake8 / mypy 时需同步更新 CI（`.github/workflows/ci.yml`）与本地 `.venv`，否则格式化结果会漂移。

6. **Python 版本**：`setup.py` 要求 `>=3.12`，CI 在 3.12 运行；black `target-version=['py312']`。不要使用 3.12 以下才有的语法糖之外的新特性。

7. **mypy 配置统一在 `pyproject.toml`** `[tool.mypy]`（`python_version="3.12"`）。CI 命令为 `mypy src/`（自动发现 pyproject.toml）。

8. **CI 默认分支为 `new-main`**，PR 与 push 的 gate 触发分支均为 `new-main`，勿误用 `main`。

9. **覆盖率门槛 75%**（`pyproject.toml` `[tool.coverage.report] fail_under = 75`）。新增代码需维持覆盖率。

10. **i18n 约束**：非 i18n 白名单文件不得出现 CJK 字符（CI `i18n` job 会扫描）。中文文案应放入 `src/carrymem/i18n/zh_CN.py` 等白名单文件。

---

## 关键文件位置

| 用途 | 路径 |
| --- | --- |
| 版本号（唯一来源） | `src/carrymem/__version__.py` |
| 构建配置 | `setup.py`（src 布局）、`pyproject.toml`（工具配置）、`MANIFEST.in` |
| MCP 清单 | `server.json`、`smithery.yaml` |
| 安全策略 | `SECURITY.md` |
| 路线图 | `docs/ROADMAP.md` |
| CI 流水线 | `.github/workflows/ci.yml`、`nightly.yml`、`release.yml`、`benchmark.yml` |
| 测试套件 | `tests/`（E2E 位于 `tests/e2e/`，18 个 `test_e2e_*.py`） |
| Lint / 类型配置 | `.flake8`、`pyproject.toml [tool.mypy]`、`.pre-commit-config.yaml` |
| 国际化文案 | `src/carrymem/i18n/en.py`、`zh_CN.py` 等 |

---

## 工作流建议

1. 改动前先运行 `pre-commit run --files <改动文件>` 与相关测试，建立基线。
2. 涉及存储 / rule_engine / FTS5 schema 的改动，必须额外运行 `pytest tests/test_e2e_concurrent_access.py tests/test_sqlite_connection_pool.py -v` 验证并发安全。
3. 涉及 MCP 工具的改动，运行 `pytest tests/test_e2e_mcp_tools.py tests/test_mcp_server.py tests/test_handlers.py -v`。
4. 提交前确认 `black --check`、`flake8`、`mypy`、`pytest tests/ -m "not slow"` 全绿。
5. **发布前必须先本地复刻 CI 四门禁预跑**（radon/flake8/black/isort/mypy 锁定版本，防止 lint 红门禁随版本带入——v0.10.0/0.10.1 教训）：`python3 scripts/ci_local_check.py`（脚本内部对齐 `.pre-commit-config.yaml` 与 ci.yml 锁定版本；需先在 /tmp venv 装锁定版本 + textual/aiosqlite 以同构 mypy 环境）。
6. 发布前必须运行完整 E2E 套件（`pytest tests/test_e2e_*.py`）做模拟真实用户使用的端到端验证。
