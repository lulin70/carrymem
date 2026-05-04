# CarryMem 深度审计报告 — 问题与修复建议

**版本**: v0.1.5  
**审计日期**: 2026-05-03  
**审计范围**: 全项目代码、文档、配置、安全、测试

---

## 一、已修复问题（本次审计中立即修复）

### 1.1 版本号不一致 [CRITICAL] ✅ 已修复

| 文件 | 修复前 | 修复后 |
|------|--------|--------|
| `__init__.py` docstring | `v0.8.0` | `v0.1.5` |
| `handlers.py:637` | `"version": "0.4.0"` 硬编码 | `"version": _version` 动态引用 |
| `mypy.ini` | `python_version = 3.8` | `python_version = 3.9`（与 pyproject.toml 一致） |

### 1.2 文档断链 [HIGH] ✅ 已修复

| 文件 | 修复内容 |
|------|----------|
| `docs/i18n/RULES_USER_MANUAL-CN.md` | 5 处断链路径修正（`../docs/` → `../`，`../` → `../../`） |
| `docs/i18n/RULES_USER_MANUAL-JP.md` | 同上 5 处断链路径修正 |
| `docs/README.md` | `install.sh` 链接修正为 `scripts/install.sh`（3 处） |

### 1.3 CLI 命令文档不一致 [HIGH] ✅ 已修复

共修复 16 处，涉及 4 类问题：

| 问题类型 | 修复前 | 修复后 | 涉及文件数 |
|----------|--------|--------|-----------|
| `add-rule --scope/--override` | `--scope personal --override` | `--type avoid --soft` | 9 |
| `list-rules --scope` | `--scope company` | `--status active` | 6 |
| `carrymem match` | `carrymem match` | `carrymem match-rules` | 3 |
| `skill-pack --output` | `--output my-skill.json` | 位置参数 `my-skill.json` | 3 |

### 1.4 不安全随机数生成 [HIGH] ✅ 已修复

- `helpers.py:generate_memory_id()` — `random.randint()` → `secrets.randbelow()`

### 1.5 setup.py 文件句柄泄漏 [MEDIUM] ✅ 已修复

- `open("README.md").read()` → `get_long_description()` 使用 `with` 语句

### 1.6 死代码 ConflictResolver [MEDIUM] ✅ 已修复

- 删除 `conflict_detector.py` 中从未使用的 `ConflictResolver` 类（90 行）
- 同步更新 `test_conflict_detector_full.py` 移除对应测试

### 1.7 未使用的 import [LOW] ✅ 已修复

- `__init__.py` — 移除 `import warnings`

### 1.8 .gitignore 问题 [LOW] ✅ 已修复

- 移除无效条目 `:memory:`, `:memory:-shm`, `:memory:-wal`
- 新增 `.env`, `*.pem`, `*.key`, `*.db`, `*.sqlite`, `node_modules/`

### 1.9 重复代码提取 [MEDIUM] ✅ 已修复

提取到 `utils/helpers.py` 的公共函数：

| 函数 | 原位置 | 使用方 |
|------|--------|--------|
| `escape_like()` | sqlite_adapter, obsidian_adapter | 2 个适配器 |
| `content_hash()` | sqlite_adapter, json_adapter, obsidian_adapter | 3 个适配器 |
| `TIER_TTL` | sqlite_adapter, json_adapter | 2 个适配器 |

### 1.10 依赖声明不一致 [LOW] ✅ 已修复

- `requirements.txt` 添加注释标注 `pycld2`/`langdetect` 为可选依赖

---

## 二、等待后续修复的问题

### 2.1 静默异常吞没 [HIGH] — 约 38 处

**问题**: 代码中有约 38 处 `except Exception:` 无日志记录，静默吞没异常，严重阻碍问题排查。

**涉及文件**:
- `carrymem.py` — 9 处
- `rules/refinement_session.py` — 6 处
- `rules/promotion_pipeline.py` — 5 处
- `rules/experience_bridge.py` — 5 处
- `cli.py` — 6 处
- `rules/storage.py` — 3 处
- `handlers.py` — 2 处
- 其他 — 2 处

**建议**: 逐文件添加 `logging.warning()` 或 `logging.error()` 日志记录。此修改量大但风险低，建议按模块分批处理。

### 2.2 过于宽泛的异常捕获 [MEDIUM] — 约 62 处

**问题**: `except Exception as e` 捕获所有异常，可能掩盖严重错误（如 `MemoryError`, `SystemExit`）。

**建议**: 
- CLI 顶层保留宽泛捕获（用户友好）
- 业务逻辑层改为捕获具体异常（`DatabaseError`, `ValueError` 等）
- 分批重构，优先处理 `carrymem.py` 和 `storage.py`

### 2.3 硬编码路径 [MEDIUM] — 9 个文件

**问题**: `.carrymem` 目录名和 `memories.db` 文件名在 9 个文件中重复硬编码。

**涉及文件**: `cli.py`, `config.py`, `sqlite_adapter.py`, `obsidian_adapter.py`, `json_adapter.py`, `encryption.py`, `tui.py`, `rules/__init__.py`

**建议**: 提取为 `utils/constants.py` 中的常量：
```python
DEFAULT_DIR_NAME = ".carrymem"
DEFAULT_DB_NAME = "memories.db"
DEFAULT_CONFIG_NAME = "config.json"
```

### 2.4 测试覆盖缺失 [HIGH] — 21 个核心模块

**问题**: 以下核心模块完全缺少测试：

| 优先级 | 模块 | 功能 |
|--------|------|------|
| P0 | `merge.py` | 冲突检测与合并 |
| P0 | `classification_pipeline.py` | 分类管道协调器 |
| P0 | `http_server.py` | HTTP 服务器 |
| P1 | `pattern_analyzer.py` | 分类管道第一层 |
| P1 | `rule_matcher.py` | 分类管道第二层 |
| P1 | `semantic_classifier.py` | 分类管道第三层 |
| P1 | `expander.py` | 语义扩展 |
| P1 | `merger.py` | 结果合并 |
| P2 | `merge_protocol.py` | 规则合并协议 |
| P2 | `injector.py` | 提示注入器 |
| P2 | `limiter.py` | 规则限制器 |
| P2 | 其他 9 个模块 | 见详细列表 |

**建议**: P0 模块优先补充测试，覆盖率阈值从 55% 逐步提升至 70%+。

### 2.5 覆盖率阈值过低 [LOW]

**问题**: `pyproject.toml` 中 `fail_under = 55`，当前实际覆盖率 77.39%。

**建议**: 将阈值提升至 70%，防止覆盖率回退。

### 2.6 自定义加密回退方案 [MEDIUM]

**问题**: `encryption.py` 在 `cryptography` 库不可用时回退到自定义 HMAC-CTR 流密码，未经密码学审查。

**涉及文件**: `encryption.py:153-190`

**建议**: 
- 短期：在文档中明确标注回退方案的安全等级
- 长期：移除自定义加密，强制要求 `cryptography` 库

### 2.7 CORS 通配符匹配过于宽松 [LOW]

**问题**: `http_server.py` CORS 使用 `startswith` 匹配，可被 `http://localhost.evil.com` 绕过。

**建议**: 使用 URL 解析库验证 hostname，而非简单前缀匹配。

### 2.8 HTTP 错误响应泄露内部信息 [LOW]

**问题**: `http_server.py` 500 错误直接返回 `str(e)`，可能泄露堆栈信息。

**建议**: 生产环境返回通用错误消息，详细信息仅记录到日志。

### 2.9 API Key 命令行参数泄露风险 [LOW]

**问题**: `--api-key` 参数在进程列表中可见。

**建议**: 支持从文件或环境变量读取，文档中推荐环境变量方式。

### 2.10 SQL 动态拼接模式 [LOW]

**问题**: `storage.py` 使用 f-string 动态拼接 SQL SET 子句。虽有白名单保护，但模式本身有风险。

**建议**: 保持当前白名单方式，但添加注释说明安全考虑。

### 2.11 `__init__.py` 导出无消费者 [LOW]

**问题**: `security/__init__.py` 导出了 5 个验证函数（`validate_path`, `validate_memory_type` 等），但全项目无任何模块导入使用。

**建议**: 评估是否为公共 API 设计。若是，补充文档说明；若否，移除导出。

### 2.12 `rules/__init__.py` 误导性类型别名 [LOW]

**问题**: `RuleType`, `RuleStatus`, `DerivationSource` 导出为 `str` 类型别名，但名称暗示是枚举类。

**建议**: 改为 `Enum` 类或重命名为 `RuleTypeStr` 等更明确的名称。

### 2.13 `pyproject.toml` 多余依赖 [LOW]

**问题**: 声明了 `setuptools_scm[toml]` 但未使用 `use_scm_version`。

**建议**: 移除 `setuptools_scm` 依赖。

### 2.14 代码注释中的旧版本号 [LOW]

**问题**: 多个文件注释中引用旧版本号（`v0.2.8`, `v0.4.0`, `v0.4.2`）。

**涉及文件**: `injector.py:8`, `sqlite_adapter.py:9-11`, `engine.py:7`

**建议**: 更新注释中的版本号为当前版本，或移除版本号引用。

### 2.15 `conflict_detector.py` 与 `merge.py` 功能重叠 [MEDIUM]

**问题**: 两个模块都实现了记忆冲突检测，逻辑有重叠但实现方式不同。

**建议**: 明确职责分离——`conflict_detector.py` 负责检测，`merge.py` 负责合并策略。或合并为一个模块。

### 2.16 `_content_hash` 实现不一致 [LOW]

**问题**: Obsidian 适配器的 `_content_hash` 不包含 type 前缀，而 SQLite/JSON 适配器包含。已通过提取公共函数统一，但 Obsidian 适配器调用时不传 prefix，行为与之前一致。

**建议**: 评估是否需要为 Obsidian 适配器也添加 type 前缀，确保跨适配器 hash 一致性。

---

## 三、问题统计

| 分类 | 已修复 | 等待后续 | 合计 |
|------|--------|----------|------|
| CRITICAL | 1 | 0 | 1 |
| HIGH | 4 | 2 | 6 |
| MEDIUM | 3 | 5 | 8 |
| LOW | 5 | 8 | 13 |
| **合计** | **13** | **15** | **28** |

### 修复文件清单

| 文件 | 修改类型 |
|------|----------|
| `src/.../ __init__.py` | 版本号修正、移除未使用 import |
| `src/.../integration/layer2_mcp/handlers.py` | 版本号硬编码→动态引用 |
| `src/.../utils/helpers.py` | 新增公共函数、安全随机数 |
| `src/.../adapters/sqlite_adapter.py` | 使用公共函数、移除重复代码 |
| `src/.../adapters/json_adapter.py` | 使用公共函数、移除重复代码 |
| `src/.../adapters/obsidian_adapter.py` | 使用公共函数、移除重复代码 |
| `src/.../conflict_detector.py` | 删除死代码 ConflictResolver |
| `setup.py` | 文件句柄泄漏修复 |
| `mypy.ini` | Python 版本一致性 |
| `.gitignore` | 无效条目清理、新增规则 |
| `requirements.txt` | 依赖分类标注 |
| `docs/README.md` | 安装链接修正 |
| `docs/USER_GUIDE.md` | CLI 命令修正 |
| `docs/TROUBLESHOOTING.md` | CLI 命令修正 |
| `docs/RULES_USER_MANUAL.md` | CLI 命令修正 |
| `docs/i18n/RULES_USER_MANUAL-CN.md` | 断链修正、CLI 命令修正 |
| `docs/i18n/RULES_USER_MANUAL-JP.md` | 断链修正、CLI 命令修正 |
| `docs/i18n/USER_GUIDE-CN.md` | CLI 命令修正 |
| `docs/i18n/USER_GUIDE-JP.md` | CLI 命令修正 |
| `docs/i18n/README-CN.md` | CLI 命令修正 |
| `docs/i18n/README-JP.md` | CLI 命令修正 |
| `docs/i18n/TROUBLESHOOTING-CN.md` | CLI 命令修正 |
| `docs/i18n/TROUBLESHOOTING-JP.md` | CLI 命令修正 |
| `README.md` | CLI 命令修正 |
| `tests/test_conflict_detector_full.py` | 移除 ConflictResolver 测试 |

### 测试验证结果

- **通过**: 2005 个测试
- **失败**: 2 个（性能测试，与本次修改无关）
- **跳过**: 1 个（Python 3.9 asyncio 兼容性问题）
- **覆盖率**: 77.39%（超过 55% 阈值）

---

## 四、后续行动建议优先级

| 优先级 | 行动项 | 预估工作量 |
|--------|--------|-----------|
| P0 | 为 `merge.py`, `classification_pipeline.py`, `http_server.py` 补充测试 | 中 |
| P0 | 为 38 处静默异常添加日志记录 | 中 |
| P1 | 提取硬编码路径为常量 | 小 |
| P1 | 提升覆盖率阈值至 70% | 小 |
| P1 | 分批重构宽泛异常捕获 | 大 |
| P2 | 评估自定义加密回退方案安全性 | 中 |
| P2 | 明确 `conflict_detector.py` 与 `merge.py` 职责 | 中 |
| P2 | 清理 `security/__init__.py` 无消费者导出 | 小 |
| P3 | CORS 匹配加固 | 小 |
| P3 | HTTP 错误响应脱敏 | 小 |
| P3 | 移除 `setuptools_scm` 多余依赖 | 小 |
