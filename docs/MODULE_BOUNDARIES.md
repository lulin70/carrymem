# CarryMem 模块边界可视化文档

> 生成日期: 2026-07-17
> 项目版本: v0.8.0
> 分析范围: `src/carrymem/` 全部子包和模块

---

## 一、项目目录总览

```
src/carrymem/
├── __init__.py              # 公共 API 入口（顶层 re-export）
├── carrymem.py              # CarryMem 类的向后兼容重导出（→ core）
├── engine.py                # MemoryClassificationEngine（独立分类引擎）
├── async_carrymem.py        # AsyncCarryMem 异步封装
│
├── core/                    # ★ 核心层：CarryMem Facade + 8 个 Mixin
│   ├── __init__.py          # CarryMem 类定义（多重继承组合）
│   ├── _lifecycle.py        # LifecycleMixin（__init__/close/属性）
│   ├── _classification.py   # ClassificationMixin（分类管线）
│   ├── _recall.py           # RecallMixin（召回操作）
│   ├── _memory_crud.py      # MemoryCRUDMixin（CRUD 操作）
│   ├── _backup.py           # BackupMixin（备份/审计）
│   ├── _maintenance.py      # MaintenanceMixin（质量/冲突/合并）
│   ├── _profile_export.py   # ProfileExportMixin（统计/导出/导入）
│   ├── _prompt_delegate.py  # PromptDelegateMixin（Prompt 构建/LLM）
│   └── _protocols.py        # Protocol 结构化类型定义
│
├── adapters/                # ★ 存储适配器层
│   ├── __init__.py          # 适配器统一导出
│   ├── base.py              # StorageAdapter ABC + MemoryEntry
│   ├── sqlite_adapter.py    # SQLiteAdapter 主入口
│   ├── async_sqlite.py      # 异步 SQLite 适配器 (v0.7.2)
│   ├── json_adapter.py      # JSONAdapter
│   ├── obsidian_adapter.py  # ObsidianAdapter
│   ├── loader.py            # 动态加载器
│   └── sqlite/              # SQLite 内部实现细节
│       ├── connection.py, crud.py, query_builder.py
│       ├── recall_engine.py, schema.py, security.py
│       ├── serializer.py, stats.py, supersede.py, versioning.py
│
├── layers/                  # ★ 分类层（三层漏斗）
│   ├── rule_matcher.py      # 第一层：规则匹配
│   ├── pattern_analyzer.py  # 第二层：模式分析
│   ├── semantic_classifier.py # 第三层：语义分类
│   ├── semantic_aggregator.py # LLM 聚合
│   ├── session_summarizer.py  # 会话摘要
│   ├── knowledge_graph.py     # SQLite 原生图谱 (v0.7.0)
│   ├── memify.py              # Memify 精炼 (v0.7.2)
│   ├── memory_pattern_detectors.py # 实体提取 (v0.7.0)
│   ├── noise_detector.py      # 噪声检测 (v0.7.x)
│   ├── feedback_detector.py   # 反馈检测 (v0.7.x)
│   ├── summary_layer.py       # RuleBasedSummarizer (SummaryLayer 类已删, post-v0.10.1)
│   └── entity_normalizer.py   # 实体规范化 (v0.5.1)
│
├── rules/                   # ★ 规则引擎（独立子系统）
│   ├── __init__.py          # RuleEngine 门面类
│   ├── models.py            # Rule 数据模型
│   ├── storage.py           # RuleStorage 持久化
│   ├── matcher.py           # RuleMatcher 匹配引擎
│   ├── injector.py          # RuleInjector 注入器
│   ├── sanitizer.py         # RuleSanitizer 清洗
│   ├── limiter.py           # RuleLimiter 限流
│   ├── conflict_detector.py # 冲突检测
│   ├── merge_protocol.py    # 合并协议
│   ├── candidate_generator.py / candidate_rule_generator.py
│   ├── pattern_detector.py, promotion_pipeline.py
│   ├── experience_bridge.py, failure_experience.py
│   ├── refinement_session.py, rule_refiner.py
│   ├── skill.py, templates.py
│
├── security/                # ★ 安全模块
│   ├── __init__.py          # 统一安全 API 导出
│   ├── encryption.py        # 加密/解密
│   ├── input_validator.py   # 输入校验
│   ├── redaction.py         # 内容脱敏
│   ├── audit.py             # 审计日志
│   └── permissions.py       # 权限控制 (P1-8 MVP)
│
├── utils/                   # ★ 工具模块
│   ├── config.py            # ConfigManager 配置管理
│   ├── helpers.py           # 通用辅助函数
│   ├── logger.py            # 日志封装
│   ├── validators.py        # 参数校验器集合
│   ├── language.py          # 语言检测
│   └── confirmation.py      # 确认检测
│
├── i18n/                    # ★ 国际化 (v0.7.x)
│   └── __init__.py          # 多语言资源
│
├── cli/                     # CLI 命令行界面
│   ├── __init__.py          # 命令路由主入口
│   ├── _base.py, _io.py, _memory.py, _rules.py
│   ├── _backup.py, _stats.py, _mcp.py
│
├── coordinators/            # 协调器
│   └── classification_pipeline.py  # 分类管线编排
│
├── patterns/                # 模式定义系统
│   ├── base.py, builder.py, group.py, registry.py
│   ├── definitions.py + definitions_*.py（10+ 子类型）
│
├── semantic/                # 语义扩展
│   ├── expander.py          # SemanticExpander
│   └── merger.py            # ResultMerger
│
├── integration/             # 外部集成
│   ├── layer2_mcp/          # MCP Server (HTTP + stdio)
│   └── devsquad/            # DevSquad 适配器
│
├── llm/                     # LLM 客户端抽象
├── monitoring/              # 监控（预留）
├── security/                # 加密 + 权限 + 审计 + 输入校验 + 脱敏
│
└── [根级模块]               # ~30 个平铺模块文件
    ├── constants.py, types.py, errors.py, exceptions.py
    ├── context.py, domain.py, scoring.py, selection.py
    ├── coreference.py, cache.py, backup.py, merge.py
    ├── consolidation.py, conflict_detector.py, prompt.py
    ├── prompt_builder.py, quality_scorer.py, scope.py
    ├── format.py, tui.py, cli.py, api_types.py
    ├── error_messages.py, __version__, __main__
```

---

## 二、模块依赖图（文字版）

### 2.1 根级模块依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `__init__.py` | `adapters.base`, `adapters.json_adapter`, `adapters.obsidian_adapter`, `adapters.sqlite_adapter`, `carrymem`, `engine`, `semantic.expander`, `semantic.merger`, `security.*`, `async_carrymem`, `api_types`, `__version__` | **公共 API 总出口**，re-export 所有公共符号 |
| `carrymem.py` | `core` (CarryMem, errors, exceptions) | 向后兼容薄包装，委托到 core |
| `engine.py` | `coordinators.classification_pipeline`, `utils.config`, `utils.helpers`, `utils.language`, `__version__` | **独立分类引擎**，不依赖 core/CarryMem |
| `async_carrymem.py` | `adapters.base`, `carrymem` | 异步封装层 |
| `cli.py` | → `cli/` 包 | CLI 入口脚本 |

### 2.2 core/ 核心层依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `core/__init__.py` (CarryMem) | `core._*`(全部8个), `errors`, `types` | **Facade 类**，多重继承组合所有 Mixin |
| `core/_lifecycle.py` | `adapters.base`, `adapters.sqlite_adapter`, `engine`, `errors`, `exceptions`, `rules.candidate_generator`, `constants` | **最核心**：持有 engine/adapter/rule_engine |
| `core/_classification.py` | `adapters.base`, `security.input_validator`, `types`, `utils.validators`, `constants`, `coreference`, `security.redaction` | 分类管线 + 规则代理方法 |
| `core/_recall.py` | `adapters.obsidian_adapter`, `adapters.sqlite_adapter`, `core._lifecycle`, `types`, `utils.validators`, `constants` | 召回/搜索操作 |
| `core/_memory_crud.py` | `adapters.base`, `adapters.sqlite_adapter`, `core._lifecycle`, `constants`, `types`, `utils.validators`, `merge` | CRUD 操作主体 |
| `core/_backup.py` | `adapters.sqlite_adapter`, `core._lifecycle`, `constants`, `backup` | 备份/审计/缓存 |
| `core/_maintenance.py` | `adapters.sqlite_adapter`, `core._lifecycle`, `constants`, `conflict_detector`, `quality_scorer`, `consolidation`, `rules.storage` | 质量/冲突/合并调度 |
| `core/_profile_export.py` | `__version__`, `adapters.base`, `adapters.sqlite_adapter`, `core._lifecycle`, `domain`, `security.input_validator`, `types`, `constants` | 统计/导出/导入 |
| `core/_prompt_delegate.py` | `adapters.base`, `core._lifecycle`, `constants`, `layers.session_summarizer`, `layers.semantic_aggregator`, `llm` | Prompt 构建 / LLM 功能 |
| `core/_protocols.py` | （仅 typing.Protocol） | 零运行时依赖 |

### 2.3 adapters/ 适配器层依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `adapters/base.py` | （无内部依赖） | **ABC 基类**，零内部耦合 |
| `adapters/sqlite_adapter.py` | `adapters.base`, `sqlite/*`(全部), `security.encryption`, `cache`, `constants`, `types` | SQLite 适配器主实现 |
| `adapters/json_adapter.py` | `adapters.base` | JSON 文件适配器 |
| `adapters/obsidian_adapter.py` | `adapters.base` | Obsidian Vault 适配器 |
| `adapters/loader.py` | `adapters.base` | 动态适配器加载 |
| `adapters/sqlite/*` | `adapters.base`, `security.*`, `constants` | SQLite 内部实现（封装良好） |

### 2.4 layers/ 分类层依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `layers/rule_matcher.py` | `utils.helpers`, `utils.language` | 第一层：规则匹配 |
| `layers/pattern_analyzer.py` | `patterns.*`, `utils.*` | 第二层：模式分析 |
| `layers/semantic_classifier.py` | `utils.*`, 可能 `semantic.expander` | 第三层：语义分类 |
| `layers/semantic_aggregator.py` | `llm` | LLM 聚合（实验性） |
| `layers/session_summarizer.py` | `llm` | 会话摘要（实验性） |

### 2.5 rules/ 规则引擎依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `rules/__init__.py` (RuleEngine) | `rules.*`(全部子模块), `constants`, `__version__` | **规则门面**，组合所有规则子组件 |
| `rules/models.py` | （无内部依赖或极少） | 数据模型 |
| `rules/storage.py` | `constants` | SQLite 持久化 |
| `rules/matcher.py` | `rules.models` | 匹配引擎 |
| 其余 rules/ 子模块 | 主要依赖 `rules.models`, `rules.storage` | 各功能组件 |

### 2.6 security/ 安全模块依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `security/__init__.py` | `security.audit`, `security.encryption`, `security.input_validator`, `security.permissions`, `security.redaction` | 统一导出 |
| `security/encryption.py` | `constants` | 加密实现 |
| `security/input_validator.py` | `constants` | 输入校验 |
| `security/redaction.py` | `constants` | 脱敏逻辑 |
| `security/audit.py` | `constants` | 审计日志 |
| `security/permissions.py` | `constants` | 权限框架 |

### 2.7 utils/ 工具模块依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `utils/config.py` | `constants` | 配置管理 |
| `utils/helpers.py` | （基本无内部依赖） | 通用工具函数 |
| `utils/logger.py` | （无内部依赖） | 日志封装 |
| `utils/validators.py` | `constants` | 参数校验 |
| `utils/language.py` | （无内部依赖） | 语言检测 |
| `utils/confirmation.py` | （无内部依赖） | 确认检测 |

### 2.8 coordinators/ 协调器依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `coordinators/classification_pipeline.py` | `layers.rule_matcher`, `layers.pattern_analyzer`, `layers.semantic_classifier`, `utils.confirmation`, `utils.logger` | **编排三层分类** |

### 2.9 cli/ 命令行依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `cli/__init__.py` | `cli._*`(全部), `errors` | 命令路由 |
| `cli/_base.py` | `core`, `adapters`, `utils` | 基础命令 |
| `cli/_memory.py` | `core`, `utils` | 记忆操作命令 |
| `cli/_rules.py` | `rules`, `core`, `utils` | 规则操作命令 |
| 其他 cli/_*.py | `core`, `utils`, `security` 等 | 各自领域命令 |

### 2.10 其他模块依赖

| 模块 | 依赖的内部模块 | 说明 |
|------|---------------|------|
| `patterns/__init__.py` | `patterns.base`, `patterns.builder`, `patterns.group`, `patterns.registry` | 模式系统 |
| `patterns/definitions_*.py` | `patterns.base` | 具体模式定义 |
| `semantic/expander.py` | （可能依赖外部库） | 语义扩展 |
| `semantic/merger.py` | （可能依赖外部库） | 结果合并 |
| `integration/layer2_mcp/*` | `core`, `rules`, `adapters`, `security` | MCP 服务端 |
| `integration/devsquad/*` | `core`, `rules` | DevSquad 集成 |
| `llm/__init__.py` | （无内部依赖） | LLM 客户端 |

---

## 三、层次划分与架构分层

### 3.1 设计目标层次

```
┌─────────────────────────────────────────────────────┐
│                    cli/  (CLI 命令行)                │  ← 第 6 层: 用户接口层
├─────────────────────────────────────────────────────┤
│         integration/  (MCP / DevSquad)              │  ← 第 5 层: 集成层
├──────────┬──────────┬──────────┬────────────────────┤
│  core/   │  rules/  │ semantic/ │   llm/            │  ← 第 4 层: 业务逻辑层
│(Facade)  │ (引擎)   │ (扩展)    │  (LLM)            │
├──────────┴──────────┴──────────┴────────────────────┤
│              layers/  (分类三层漏斗)                  │  ← 第 3 层: 处理层
│     rule_matcher → pattern_analyzer → semantic_cls  │
├─────────────────────────────────────────────────────┤
│              adapters/  (存储适配器)                  │  ← 第 2 层: 适配器层
│    base → sqlite / json / obsidian                  │
├──────────┬───────────┬──────────┬───────────────────┤
│security/ │  utils/   │ patterns/│ coordinators/     │  ← 第 1 层: 基础设施层
│(安全)    │ (工具)    │ (模式)   │ (协调器)           │
└──────────┴───────────┴──────────┴───────────────────┘
```

### 3.2 分层原则说明

| 层次 | 目录 | 职责 | 允许依赖的下层 |
|------|------|------|---------------|
| L6 用户接口 | `cli/` | 命令解析、用户交互 | L1~L5 全部 |
| L5 集成 | `integration/` | 外部协议适配 | L1~L4 |
| L4 业务逻辑 | `core/`, `rules/`, `semantic/`, `llm/` | 核心业务、规则、语义 | L1~L3 |
| L3 处理 | `layers/`, `coordinators/` | 分类管线编排 | L1~L2 |
| L2 适配器 | `adapters/` | 存储抽象与实现 | L1 (`utils/`, `security/`) |
| L1 基础 | `security/`, `utils/`, `patterns/` | 基础能力 | 仅 stdlib + 第三方库 |

**关键规则：低层数不能依赖高层数据。**

---

## 四、循环依赖检测报告

### 4.1 检测方法

通过 AST 解析所有 `import` 和 `from ... import` 语句，构建有向依赖图后检测环路。

### 4.2 发现的循环依赖

#### ⚠️ 循环 1: `core` ↔ `rules`

```
core/_lifecycle.py  ──import──→  rules/candidate_generator.py
                                ↓
rules/__init__.py (RuleEngine)  ──lazy import──→  core (通过 CarryMem.rule_engine 属性)
```

**严重程度**: 中等（已缓解）
**缓解方式**: `_lifecycle.py` 在 `__init__` 中直接 import `RuleCandidateGenerator`，而 `RuleEngine` 通过 lazy property 延迟导入 `core.CarryMem`。实际运行时不会产生死循环，但存在**设计层面的循环耦合**。

#### ⚠️ 循环 2: `core` ↔ `adapters/sqlite_adapter`

```
core/_lifecycle.py  ──import──→  adapters/sqlite_adapter.py (SQLiteAdapter)
core/_recall.py     ──import──→  adapters/sqlite_adapter.py
core/_memory_crud.py ──import──→  adapters/sqlite_adapter.py
core/_backup.py     ──import──→  adapters/sqlite_adapter.py
core/_maintenance.py ──import──→  adapters/sqlite_adapter.py
core/_profile_export.py ──import──→  adapters/sqlite_adapter.py
                                ↓
adapters/sqlite_adapter.py ──(间接)──→  core (通过类型注解或错误引用)
```

**严重程度**: 低（单向实际依赖）
**说明**: 实际上 `sqlite_adapter` 并不直接 import `core`，这是**概念上的**紧密耦合——core 的 6 个 Mixin 都硬编码了 `SQLiteAdapter` 类型检查（`isinstance(self._adapter, SQLiteAdapter)`），导致 core 层对具体适配器实现有强依赖。

#### ⚠️ 循环 3: `__init__.py` ↔ 几乎所有模块

```
__init__.py  ──import──→  carrymem, engine, adapters.*, security.*, semantic.*, async_carrymem
carrymem.py   ──import──→  core
core/__init__ ──import──→  core._*, errors, types
```

**严重程度**: 无（正常模式）
**说明**: 这是 Python 包的典型 **API Re-export 模式**。`__init__.py` 作为公共 API 汇聚点，单向依赖所有内部模块，不构成真正的循环。

### 4.3 循环依赖总结

| ID | 环路 | 严重程度 | 状态 | 建议 |
|----|------|---------|------|------|
| CD-01 | `core/_lifecycle` ↔ `rules` | 🟡 中 | 已缓解(lazy) | 考虑引入 events 解耦 |
| CD-02 | `core` → `adapters/sqlite_adapter` (强耦合) | 🟡 中 | 活跃 | 引入 AdapterCapability 协议 |
| CD-03 | `__init__.py` 重型汇聚 | 🟢 低 | 正常 | 可接受，但需控制 __init__ 导入量 |

---

## 五、违反分层原则的地方标注

### 🔴 严重违规

| # | 位置 | 违规描述 | 影响 |
|---|------|---------|------|
| V-01 | `core/_lifecycle.py` | 直接 import `adapters.sqlite_adapter.SQLiteAdapter` | Core 层不应依赖具体 Adapter 实现，应依赖 `adapters.base.StorageAdapter` ABC |
| V-02 | `core/_recall.py` | 直接 import `adapters.sqlite_adapter.SQLiteAdapter` + `adapters.obsidian_adapter.ObsidianAdapter` | 同上，且引入了两个具体实现 |
| V-03 | `core/_memory_crud.py` | 大量 `isinstance(self._adapter, SQLiteAdapter)` 类型检查 | 违反迪米特法则，Core 不应知道 Adapter 具体类型 |
| V-04 | `core/_backup.py` | 全文基于 `SQLiteAdapter` 假设编写 | BackupMixin 无法用于非 SQLite 适配器 |
| V-05 | `core/_maintenance.py` | 同上，直接操作 SQLite 连接 (`self._adapter._get_connection()`) | 穿透 Adapter 抽象 |
| V-06 | `core/_profile_export.py` | 同上，大量 `isinstance(self._adapter, SQLiteAdapter)` | 同 V-03 |

### 🟡 中度违规

| # | 位置 | 违规描述 | 影响 |
|---|------|---------|------|
| V-07 | `core/_classification.py` | 直接 import `security.input_validator.InputValidator` + `security.redaction.should_redact` | Core 跨层调用 Security（可接受但应通过接口） |
| V-08 | `core/_prompt_delegate.py` | 直接 import `layers.session_summarizer` + `layers.semantic_aggregator` + `llm.LLMClient` | Core 直接依赖 Layers 和 LLM 层 |
| V-09 | `engine.py` | import `coordinators.classification_pipeline` | Engine 作为独立模块依赖 coordinators（合理但需注意） |

### 🟢 轻微 / 可接受

| # | 位置 | 违规描述 | 说明 |
|---|------|---------|------|
| V-10 | `__init__.py` | 一次性导入 30+ 模块 | API 汇聚点，可接受 |
| V-11 | `rules/__init__.py` | 导入 rules 下全部 15+ 子模块 | Rules 门面模式，可接受 |

---

## 六、公共 API vs 内部 API 边界

### 6.1 公共 API（Public API）

通过 `src/carrymem/__init__.py` 的 `__all__` 导出的符号：

```python
# === 核心类 ===
CarryMem                          # 主门面类
MemoryClassificationEngine       # 独立分类引擎
AsyncCarryMem                    # 异步封装

# === 适配器 ===
StorageAdapter                   # ABC 基类
MemoryEntry / StoredMemory       # 数据模型
SQLiteAdapter                    # 默认存储
ObsidianAdapter                  # Obsidian 集成
JSONAdapter                      # JSON 文件存储

# === 安全 ===
InputValidator                   # 输入校验器
ValidationError                  # 校验异常
validate_content / validate_query / validate_namespace

# === 语义扩展（可选依赖）===
SemanticExpander                 # 语义扩展器
ResultMerger                     # 结果合并器

# === 类型字典（Dict 别名）===
RuleDict, MatchResultDict, EffectivenessReportDict
KnowledgeNoteDict, RecallAllResultDict, BuildContextResultDict
SourceMemoryValidationDict
```

### 6.2 内部 API（Internal API）

**以下模块/符号属于内部实现，不应被外部代码直接 import：**

| 类别 | 模块/符号 | 理由 |
|------|----------|------|
| Core Mixin | `core._lifecycle.LifecycleMixin` | 组合细节，不属于公共 API |
| Core Mixin | `core._classification.ClassificationMixin` | 同上 |
| Core Mixin | `core._*` 所有 Mixin | 同上 |
| Protocols | `core._protocols.*Ops` | 仅用于类型检查 |
| 适配器内部 | `adapters/sqlite/*` | SQLite 实现细节 |
| 规则内部 | `rules/models.Rule` 底层 | 通过 RuleEngine 操作 |
| 工具内部 | `utils/*` | 内部工具函数 |
| CLI | `cli/_*.py` | CLI 实现细节 |
| 常量 | `constants.py` | 内部配置常量 |
| 根级散落模块 | `context.py`, `scoring.py`, `selection.py` 等 | 待整理的内部模块 |

### 6.3 命名约定区分

| 前缀/模式 | 含义 | 示例 | 可见性 |
|-----------|------|------|--------|
| 无前缀 | 公共 API | `CarryMem`, `classify_and_remember()` | ✅ Public |
| 单下划线前缀 | 受保护 API | `_lifecycle.py`, `_validate_file_path()`, `_engine` | ⚠️ Internal |
| 双下划线前缀 | 私有 API | `__init__` 中的 `_os` | ❌ Private |
| `_*`.py 文件 | 内部实现模块 | `_backup.py`, `_classification.py` | ❌ Internal |

---

## 七、模块健康度评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **分层清晰度** | ⭐⭐⭐☆☆ (3/5) | 有明确层次意图，但 core→adapter 耦合偏高 |
| **循环依赖** | ⭐⭐⭐⭐☆ (4/5) | 无硬循环，有 1 个设计级循环（已缓解） |
| **内聚性** | ⭐⭐⭐⭐☆ (4/5) | 各包职责明确，rules/ 和 core/ 内聚性好 |
| **耦合度** | ⭐⭐⭐☆☆ (3/5) | core 对 SQLiteAdapter 耦合过高（6处 isinstance） |
| **API 边界** | ⭐⭐⭐⭐☆ (4/5) | `__all__` 明确，但根级 ~30 个散落模块边界模糊 |
| **可测试性** | ⭐⭐⭐⭐☆ (4/5) | Mixin 架构便于单独测试，但集成测试依赖 SQLite |

---

## 八、改进建议优先级

### P0 — 应尽快修复
1. **消除 core → SQLiteAdapter 硬编码**: 将 `isinstance(check, SQLiteAdapter)` 替换为 capability-based 检查（duck typing 或 protocol）
2. **抽取 Backup/Versioning 接口**: 从 SQLiteAdapter 中提取到 base.StorageAdapter ABC

### P1 — 近期规划
3. **整理根级散落模块**: `context.py`, `scoring.py`, `selection.py`, `domain.py`, `format.py` 等应归入合适的子包
4. **core/rules 循环解耦**: 通过事件机制或依赖注入替代直接引用

### P2 — 长期优化
5. **`__init__.py` 瘦身**: 考虑使用 lazy import 或 sub-package re-export
6. **layers/ 与 core/ 的关系澄清**: PromptDelegateMixin 直接依赖 layers/ 和 llm/
