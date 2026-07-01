# CarryMem API 参考手册（中文版）

**版本**: v0.4.0
**最后更新**: 2026-06-11
**源码位置**: `src/carrymem/`

---

## 目录

1. [概述](#概述)
2. [CarryMem 类公共方法](#carrymem-类公共方法)
3. [错误码完整列表](#错误码完整列表)
4. [常量列表](#常量列表)
5. [类型定义](#类型定义)

---

## 概述

CarryMem 是一个便携式 AI 记忆层，使 AI 代理能够记住用户偏好、决策和上下文。

### 快速开始

```python
from carrymem import CarryMem

# 模式1：分类 + 存储（默认 SQLite）
cm = CarryMem()
result = cm.classify_and_remember("我喜欢深色模式")

# 模式2：纯分类（无存储）
cm = CarryMem(storage=None)
result = cm.classify_message("我喜欢深色模式")

# 模式3：自定义存储适配器
from carrymem.adapters import SQLiteAdapter
cm = CarryMem(storage=SQLiteAdapter("/path/to/custom.db"))

# 模式4：带知识库（Obsidian）
from carrymem.adapters import ObsidianAdapter
cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python 设计模式")
```

### 架构说明

CarryMem 采用 **Mixin 组合模式**，由以下 8 个 Mixin 类组成：

| Mixin | 职责 |
|-------|------|
| `LifecycleMixin` | 生命周期管理：初始化、关闭、上下文管理器 |
| `ClassificationMixin` | 分类管道和规则候选生成 |
| `MemoryCRUDMixin` | 核心记忆 CRUD 操作 |
| `RecallMixin` | 召回/搜索操作 |
| `BackupMixin` | 备份与审计日志 |
| `ProfileExportMixin` | 用户画像、统计、导入导出 |
| `MaintenanceMixin` | 质量检查、冲突检测、合并 |
| `PromptDelegateMixin` | 提示词构建和 LLM 功能 |

---

## CarryMem 类公共方法

### 构造函数

#### `__init__(storage, db_path, knowledge_adapter, namespace, config, encryption_key, auto_backup_interval)`

初始化 CarryMem 实例。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `storage` | `str \| StorageAdapter \| None` | `"sqlite"` | 存储适配器类型或实例。支持 `"sqlite"`, `None`（纯分类模式）, 或自定义 `StorageAdapter` 实例 |
| `db_path` | `str \| None` | `None` | 数据库文件路径。默认使用环境变量 `CARRYMEM_DB_PATH` 或 `~/.carrymem/memories.db` |
| `knowledge_adapter` | `StorageAdapter \| None` | `None` | 知识库适配器（如 ObsidianAdapter） |
| `namespace` | `str` | `"default"` | 命名空间，用于隔离不同用户的记忆 |
| `config` | `Dict[str, Any] \| None` | `None` | 额外配置选项 |
| `encryption_key` | `str \| None` | `None` | 加密密钥（SQLite 专用） |
| `auto_backup_interval` | `int` | `20` | 自动备份间隔（写入次数） |

**返回:** `None`

**异常:**
- `CarryMemError(CM-100)`: 存储适配器未配置或未知类型
- `CarryMemError(CM-201)`: 输入验证失败
- `CarryMemError(CM-101)`: 数据库操作失败

**示例:**

```python
# 默认配置
cm = CarryMem()

# 纯分类模式（不存储）
cm = CarryMem(storage=None)

# 自定义数据库路径
cm = CarryMem(db_path="/data/my_memories.db")

# 带加密
cm = CarryMem(encryption_key="my-secret-key")

# 使用上下文管理器
with CarryMem() as cm:
    result = cm.classify_and_remember("用户偏好")
```

---

### 属性 (Properties)

#### `version` → `str`

返回 CarryMem 版本字符串。

```python
>>> cm.version
'0.4.0'
```

#### `namespace` → `str`

当前记忆命名空间。

#### `engine` → `MemoryClassificationEngine`

记忆分类引擎实例。

#### `adapter` → `Optional[StorageAdapter]`

存储适配器实例（alias for storage）。

#### `storage` → `Optional[StorageAdapter]`

存储适配器实例。

#### `knowledge_adapter` → `Optional[StorageAdapter]`

知识库适配器实例（如 ObsidianAdapter）。

#### `rule_engine` → `RuleEngine`

惰性初始化的规则引擎实例。

#### `prompt_builder` → `PromptBuilder`

惰性初始化的提示词构建器实例。

#### `access_policy` → `Optional[Any]`

访问控制策略（P1-8 MVP）。设置后启用权限检查。

---

### 核心方法

#### `classify_and_remember(message, context, language, session_id, force_type, user_id)` → `ClassificationResult`

**核心方法** — 完整管道：验证 → 分类 → 存储。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `message` | `str` | **必需** | 待分类的用户消息 |
| `context` | `Dict[str, Any] \| None` | `None` | 消息上下文 |
| `language` | `str \| None` | `None` | 语言代码（如 "zh", "en"） |
| `session_id` | `str \| None` | `None` | 会话 ID |
| `force_type` | `str \| None` | `None` | 强制指定记忆类型 |
| `user_id` | `str \| None` | `None` | 用户 ID（用于权限检查） |

**返回:** `ClassificationResult` - 包含分类结果、存储状态、规则建议等

**异常:**
- `StorageNotConfiguredError`: 存储未配置
- `CarryMemError(CM-201)`: 输入验证失败
- `CarryMemError(CM-301)`: 分类失败

**示例:**

```python
result = cm.classify_and_remember(
    "我更喜欢使用 Vim 编辑器",
    context={"source": "chat"},
    language="zh"
)
print(result["type"])      # "user_preference"
print(result["stored"])    # True
print(result["entries"])   # [MemoryEntryDict, ...]
```

---

#### `classify_message(message, context, language)` → `ClassificationResult`

纯分类（不存储），用于预览分类结果。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `message` | `str` | **必需** | 待分类的消息 |
| `context` | `Dict[str, Any] \| None` | `None` | 消息上下文 |
| `language` | `str \| None` | `None` | 语言代码 |

**返回:** `ClassificationResult`

**示例:**

```python
result = cm.classify_message("明天下午3点开会")
print(result["type"])  # 可能是 "task" 或 "decision"
```

---

#### `declare(message, context, user_id)` → `DeclareResult`

显式声明一条用户偏好/决策作为记忆存储。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `message` | `str` | **必需** | 要声明的消息内容 |
| `context` | `Dict[str, Any] \| None` | `None` | 消息上下文 |
| `user_id` | `str \| None` | `None` | 用户 ID |

**返回:** `DeclareResult`

**示例:**

```python
result = cm.declare("我承诺每天写代码至少2小时")
print(result["declared"])  # True
print(result["storage_keys"])  # ["xxx"]
```

---

#### `declare_preference(message, context, user_id)` → `DeclareResult`

`declare()` 的别名，语义糖。

---

#### `forget_memory(memory_id, user_id)` → `bool`

删除单条记忆。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `memory_id` | `str` | **必需** | 记忆的 storage_key |
| `user_id` | `str \| None` | `None` | 用户 ID（权限检查） |

**返回:** `bool` - 是否成功删除

**异常:**
- `CarryMemError(CM-204)`: 指定的记忆不存在

---

#### `update_memory(storage_key, new_content, reason, user_id)` → `UpdateMemoryResult`

更新记忆内容（带版本控制，仅 SQLite）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `storage_key` | `str` | **必需** | 记忆的唯一标识符 |
| `new_content` | `str` | **必需** | 新的内容 |
| `reason` | `str \| None` | `None` | 更新原因 |
| `user_id` | `str \| None` | `None` | 用户 ID |

**返回:** `UpdateMemoryResult`

---

#### `get_memory_history(storage_key)` → `List[Dict[str, Any]]`

获取记忆的版本历史（仅 SQLite）。

**参数:**
- `storage_key` (`str`): 记忆的唯一标识符

**返回:** 版本历史列表

---

#### `rollback_memory(storage_key, version)` → `RollbackMemoryResult`

将记忆回滚到指定版本（仅 SQLite）。

**参数:**
- `storage_key` (`str`): 记忆的唯一标识符
- `version` (`int`): 目标版本号

**返回:** `RollbackMemoryResult`

---

#### `merge_memories(namespaces, strategy, conflict_callback)` → `MergeMemoriesResult`

跨命名空间合并重复记忆（仅 SQLite）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `namespaces` | `List[str] \| None` | `None` | 要合并的命名空间列表 |
| `strategy` | `str` | `"latest"` | 合并策略：`"latest"`, `"highest_confidence"`, `"merge_content"` |
| `conflict_callback` | `Callable \| None` | `None` | 冲突解决回调函数 |

**返回:** `MergeMemoriesResult`

---

### 召回/搜索方法

#### `recall_all(query, filters, limit, namespaces, include_rules)` → `RecallAllResult`

统一召回：规则 + 记忆 + 知识库。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | **必需** | 搜索查询 |
| `filters` | `Dict[str, Any] \| None` | `None` | 过滤条件 |
| `limit` | `int` | `20` | 最大结果数 |
| `namespaces` | `List[str] \| None` | `None` | 搜索的命名空间 |
| `include_rules` | `bool` | `True` | 是否包含规则匹配 |

**返回:** `RecallAllResult`

**示例:**

```python
result = cm.recall_all("编程偏好", limit=10)
print(result["memories"])     # 记忆列表
print(result["rules"])       # 规则匹配列表
print(result["knowledge"])   # 知识库结果
print(result["total_count"]) # 总数
```

---

#### `recall_memories(query, filters, limit, namespaces, update_access)` → `List[StoredMemoryDict]`

搜索已存储的记忆。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str \| None` | `None` | 搜索查询 |
| `filters` | `Dict[str, Any] \| None` | `None` | 过滤条件 |
| `limit` | `int` | `20` | 最大结果数 |
| `namespaces` | `List[str] \| None` | `None` | 搜索的命名空间 |
| `update_access` | `bool` | `True` | 是否更新访问统计 |

**返回:** `List[StoredMemoryDict]`

---

#### `recall_from_knowledge(query, filters, limit)` → `List[Dict[str, Any]]`

搜索知识库（需要配置 knowledge_adapter）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | **必需** | 搜索查询 |
| `filters` | `Dict[str, Any] \| None` | `None` | 过滤条件 |
| `limit` | `int` | `20` | 最大结果数 |

**返回:** `List[Dict[str, Any]]`

**异常:**
- `KnowledgeNotConfiguredError`: 知识库未配置

---

#### `index_knowledge()` → `Dict[str, Any]`

索引知识库（如 Obsidian vault）。

**返回:** 索引结果字典

**异常:**
- `KnowledgeNotConfiguredError`: 知识库未配置

---

#### `recall_aggregated(memory_type, limit_per_type)` → `RecallAggregatedResult`

按类型分组召回记忆。

**参数:**
- `memory_type` (`str \| None`): 特定记忆类型，`None` 表示所有类型
- `limit_per_type` (`int`): 每种类型的最大数量

**返回:** `RecallAggregatedResult` - 键为类型名，值为该类型的记忆列表

---

#### `recall_timeline(topic, limit)` → `List[Dict[str, Any]]`

按时间线召回某主题的记忆。

**参数:**
- `topic` (`str`): 主题关键词
- `limit` (`int`): 最大结果数

**返回:** 按时间排序的记忆列表

---

### 统计与画像方法

#### `get_stats()` → `MemoryStats`

获取存储统计信息。

**返回:** `MemoryStats`
```python
{
    "adapter": "sqlite",
    "total_count": 150,
    "by_type": {"preference": 50, "decision": 30, ...},
    "capabilities": {"vector_search": True, "ttl": True}
}
```

---

#### `get_memory_profile()` → `MemoryProfile`

获取详细记忆画像。

**返回:** `MemoryProfile`
```python
{
    "summary": "用户喜欢技术主题...",
    "total_memories": 150,
    "highlights": {"preference": [...], "decision": [...]},
    "stats": {...},
    "last_updated": "2026-06-11T12:00:00"
}
```

---

#### `whoami()` → `WhoamiResult`

基于存储的记忆总结用户身份。

**返回:** `WhoamiResult`
```python
{
    "identity": "技术开发者",
    "summary": "...",
    "total_memories": 150,
    "preferences": ["喜欢Vim", "偏好深色模式"],
    "decisions": ["选择PostgreSQL"],
    "corrections": ["修正：不用MySQL"],
    ...
}
```

---

### 导入导出方法

#### `export_profile(output_path)` → `ExportProfileResult`

导出用户画像到 JSON 文件。

**参数:**
- `output_path` (`str \| None`): 输出路径，`None` 则返回字典

**返回:** `ExportProfileResult`

---

#### `export_memories(output_path, format, namespace)` → `ExportMemoriesResult`

导出所有记忆到文件。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_path` | `str \| None` | `None` | 输出路径 |
| `format` | `str` | `"json"` | 格式：`"json"` 或 `"markdown"` |
| `namespace` | `str \| None` | `None` | 导出的命名空间 |

**返回:** `ExportMemoriesResult`

---

#### `import_memories(input_path, data, namespace, merge_strategy)` → `ImportMemoriesResult`

从文件或字典导入记忆。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `input_path` | `str \| None` | `None` | 输入文件路径 |
| `data` | `Dict \| None` | `None` | 直接传入数据字典 |
| `namespace` | `str \| None` | `None` | 目标命名空间 |
| `merge_strategy` | `str` | `"skip"` | 合并策略：`"skip"`, `"overwrite"`, `"merge"` |

**返回:** `ImportMemoriesResult`

---

### 备份与审计方法

#### `backup(backup_dir)` → `BackupResult`

创建手动备份。

**参数:**
- `backup_dir` (`str \| None`): 备份目录，`None` 使用默认目录

**返回:** `BackupResult`

---

#### `list_backups(backup_dir)` → `List[Dict[str, Any]]`

列出可用备份。

**返回:** 备份信息列表

---

#### `restore_backup(backup_path, backup_dir)` → `RestoreBackupResult`

从备份恢复数据库。

**参数:**
- `backup_path` (`str`): 备份文件路径
- `backup_dir` (`str \| None`): 备份目录

**返回:** `RestoreBackupResult`

---

#### `clear_cache()` → `None`

清除适配器内部缓存。

---

#### `get_audit_log(operation, since, until, source, limit)` → `List[AuditLogEntry]`

查询审计日志。审计日志默认持久化至 ~/.carrymem/audit.db。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `operation` | `str \| None` | `None` | 操作类型过滤 |
| `since` | `str \| None` | `None` | 起始时间（ISO格式） |
| `until` | `str \| None` | `None` | 结束时间（ISO格式） |
| `source` | `str \| None` | `None` | 来源过滤 |
| `limit` | `int` | `100` | 最大条目数 |

**返回:** `List[AuditLogEntry]`

---

### 维护方法

#### `check_quality(min_score)` → `List[QualityIssue]`

检查低质量记忆。

**参数:**
- `min_score` (`float`): 最低质量阈值（默认 0.3）

**返回:** `List[QualityIssue]`

---

#### `check_conflicts()` → `List[ConflictInfo]`

检测冲突的记忆和规则。

**返回:** `List[ConflictInfo]`

---

#### `list_expired()` → `List[Dict[str, Any]]`

列出已过期的记忆（仅 SQLite）。

**返回:** 过期记忆列表

---

#### `consolidate(dry_run, run_p1, run_p2)` → `ConsolidationResult`

运行记忆合并管道：去重 → 衰减 → 清理。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dry_run` | `bool` | `False` | 试运行（不做实际修改） |
| `run_p1` | `bool` | `True` | 运行 P1 阶段（去重） |
| `run_p2` | `bool` | `True` | 运行 P2 阶段（衰减清理） |

**返回:** `ConsolidationResult`

---

#### `schedule_consolidation(interval_hours, dry_run, run_p1, run_p2)` → `ScheduleConsolidationResult`

启动定期后台合并定时器。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `interval_hours` | `float` | `6.0` | 合并间隔（小时） |
| `dry_run` | `bool` | `False` | 试运行 |
| `run_p1` | `bool` | `True` | 运行 P1 |
| `run_p2` | `bool` | `True` | 运行 P2 |

**返回:** `ScheduleConsolidationResult`

---

#### `stop_consolidation()` → `None`

停止后台合并定时器。

---

### 提示词构建方法

#### `build_context(context, max_memories, max_knowledge, max_rules, max_tokens, language)` → `ContextBuildResult`

构建 LLM 注入用的上下文字典。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `context` | `str \| None` | `None` | 当前对话上下文 |
| `max_memories` | `int` | `10` | 最大记忆数量 |
| `max_knowledge` | `int` | `5` | 最大知识条目数 |
| `max_rules` | `int` | `5` | 最大规则数量 |
| `max_tokens` | `int` | `2000` | 最大 token 数 |
| `language` | `str` | `"zh"` | 输出语言 |

**返回:** `ContextBuildResult`

---

#### `build_system_prompt(context, max_memories, max_knowledge, max_rules, max_tokens, language)` → `str`

构建包含注入上下文的系统提示词字符串。

**参数同 `build_context`**

**返回:** `str` - 完整的系统提示词

---

#### `build_qa_prompt(question, max_memories, max_knowledge, max_tokens, language, budget, include_question)` → `str`

构建 QA 提示词，包含检索到的上下文。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `question` | `str` | **必需** | 用户问题 |
| `max_memories` | `int` | `10` | 最大记忆数量 |
| `max_knowledge` | `int` | `5` | 最大知识条目数 |
| `max_tokens` | `int` | `2000` | 最大 token 数 |
| `language` | `str` | `"zh"` | 输出语言 |
| `budget` | `Any \| None` | `None` | Token 预算对象 |
| `include_question` | `bool` | `True` | 是否在提示词中包含问题 |

**返回:** `str` - 完整的 QA 提示词

---

#### `summarize_session(session_id, language, store)` → `SessionSummaryResult`

LLM 驱动的会话摘要（实验性功能）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `session_id` | `str` | **必需** | 会话 ID |
| `language` | `str` | `"zh"` | 输出语言 |
| `store` | `bool` | `True` | 是否存储摘要 |

**返回:** `SessionSummaryResult`

---

#### `aggregate_memories(memory_type, language, store)` → `Dict[str, Any]`

LLM 驱动的语义聚合（实验性功能）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `memory_type` | `str \| None` | `None` | 特定记忆类型 |
| `language` | `str` | `"zh"` | 输出语言 |
| `store` | `bool` | `True` | 是否存储聚合结果 |

**返回:** 聚合结果字典

---

### 工具方法

#### `health_check()` → `HealthCheckResult`

返回所有组件的健康状态。Also available as MCP tool.

**返回:** `HealthCheckResult`
```python
{
    "status": "ok",  # "ok" | "degraded"
    "components": {
        "storage": {"status": "ready", ...},
        "engine": {"status": "ready", ...},
        ...
    },
    "issues": []
}
```

---

#### `get_component_status()` → `ComponentStatusDict`

返回各组件的初始化状态。

**返回:** `ComponentStatusDict`
```python
{"storage": "ready", "engine": "ready", "knowledge": "not_configured", ...}
```

---

#### `validate_ready(require_storage, require_knowledge)` → `None`

统一的就绪检查；未就绪时抛出异常。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `require_storage` | `bool` | `True` | 是否要求存储就绪 |
| `require_knowledge` | `bool` | `False` | 是否要求知识库就绪 |

**异常:**
- `CarryMemError(CM-001)`: 存储未配置但被要求
- `CarryMemError(CM-002)`: 知识库未配置但被要求
- `CarryMemError(CM-003)`: 引擎未初始化
- `CarryMemError(CM-004)`: 规则引擎异常

---

#### `close()` → `None`

释放资源（适配器、规则引擎、知识库适配器）。

**注意**: 支持上下文管理器协议，推荐使用 `with` 语句。

---

## 错误码完整列表

### CM-001 ~ CM-099: 配置与初始化

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-001 | 配置文件格式错误或缺少必要字段 | Configuration file is malformed or missing required fields | 配置文件解析失败 |
| CM-002 | 初始化失败：必要依赖缺失 | Initialization failed: required dependency missing | 缺少依赖包 |

### CM-100 ~ CM-199: 存储适配器

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-100 | 存储适配器未配置或类型未知 | Storage adapter not configured or unknown type | 未提供存储适配器 |
| CM-101 | 数据库操作执行失败 | Database operation execution failed | SQL 执行错误 |
| CM-102 | 检测到重复数据（唯一约束冲突） | Duplicate data detected (unique constraint conflict) | 插入重复记录 |
| CM-103 | 数据库表不存在或未初始化 | Database table does not exist or is uninitialized | 表不存在 |
| CM-104 | 数据库被其他进程锁定 | Database is locked by another process | 并发访问冲突 |
| CM-105 | 无法打开数据库文件 | Unable to open database file | 文件权限/路径问题 |
| CM-106 | 文件权限不足，无法访问 | Permission denied: cannot access file or directory | 权限不足 |
| CM-107 | 磁盘空间不足 | Insufficient disk space | 磁盘满 |
| CM-108 | 指定的文件不存在 | Specified file not found | 文件缺失 |
| CM-109 | 文件系统操作失败 | File system operation failed | I/O 错误 |
| CM-110 | 知识库适配器未配置 | Knowledge base adapter not configured | 知识库未配置 |
| CM-111 | 无法连接到数据库 | Unable to connect to the database | 连接失败 |
| CM-112 | 数据库查询执行失败 | Database query execution failed | 查询语法错误 |
| CM-120 | 存储操作发生错误 | A storage operation error occurred | 通用存储错误 |

### CM-200 ~ CM-299: 记忆操作

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-201 | 输入验证未通过 | Input validation failed | 必填字段缺失/格式错误 |
| CM-202 | 输入参数无效或不合法 | Invalid input parameter | 参数范围/类型错误 |
| CM-203 | 记忆内容为空或过短 | Memory content is empty or too short | 内容太短 |
| CM-204 | 指定的记忆条目不存在 | The specified memory entry does not existence | 删除/更新不存在的记忆 |
| CM-205 | 记忆召回操作失败 | Memory recall operation failed | 搜索出错 |

### CM-300 ~ CM-399: 分类与规则引擎

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-301 | 记忆分类失败 | Memory classification failed | 分类管道异常 |
| CM-302 | 规则引擎执行出错 | Rule engine execution error | 规则定义错误 |
| CM-303 | 规则匹配失败：无匹配的规则 | Rule matching failed: no matching rules found | 无匹配规则 |
| CM-304 | 规则冲突检测异常 | Rule conflict detection error | 冲突检测失败 |

### CM-400 ~ CM-499: 安全与加密

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-401 | 加密操作失败 | Encryption operation failed | 密钥/加密错误 |
| CM-402 | 路径安全检查未通过（路径穿越检测） | Path security check failed (path traversal detected) | 不安全路径 |
| CM-403 | 权限拒绝：用户没有执行此操作的权限 | Permission denied: user does not have permission for this operation | 权限不足 |
| CM-404 | 输入内容触发了安全过滤规则 | Input content triggered security filter rules | 危险输入检测 |
| CM-408 | 解密失败：密钥不匹配或数据已损坏 | Decryption failed: key mismatch or data corruption | 解密失败 |

### CM-500 ~ CM-599: 导入/导出

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-501 | 导入文件格式不受支持或已损坏 | Import file format is unsupported or corrupted | 格式不支持 |
| CM-502 | 导出操作失败 | Export operation failed | 写入失败 |
| CM-503 | 导入数据校验失败：存在无效记录 | Import data validation failed: invalid records found | 数据校验错误 |
| CM-504 | .carry 文件校验和不匹配 | .carry file checksum mismatch, file may be corrupted | 文件损坏 |

### CM-600 ~ CM-699: CLI/TUI/MCP 入口

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-601 | 未知命令或参数错误 | Unknown command or invalid arguments | CLI 参数错误 |
| CM-602 | TUI 启动失败：终端不支持所需功能 | TUI launch failed: terminal lacks required capabilities | 终端不支持 |
| CM-603 | MCP 服务器启动失败 | MCP server startup failed | MCP 配置错误 |
| CM-604 | CLI 命令执行超时 | CLI command execution timed out | 操作超时 |

### CM-999: 兜底错误

| 错误码 | 中文说明 | 英文说明 | 触发场景 |
|--------|----------|----------|----------|
| CM-999 | 发生未知错误 | An unknown error occurred | 未预期的异常 |

---

## 常量列表

### 基础目录常量 (`constants.py`)

| 常量名 | 类型 | 值/说明 |
|--------|------|---------|
| `HOME_DIR` | `Path` | 用户主目录 |
| `DEFAULT_CONFIG_DIR` | `Path` | `~/.carrymem` - 默认配置目录 |
| `CONFIG_DIR` | `Path` | 当前配置目录（可通过环境变量覆盖） |
| `DB_PATH` | `Path` | 数据库文件路径 |
| `CONFIG_FILE` | `Path` | 配置文件路径 |
| `LOG_DIR` | `Path` | 日志目录 |
| `CACHE_DIR` | `Path` | 缓存目录 |
| `BACKUP_DIR` | `Path` | 备份目录 |
| `TEMP_DIR` | `Path` | 临时目录 |
| `LOCK_FILE` | `Path` | 锁文件路径 |

### MCP 集成路径常量

| 常量名 | 说明 |
|--------|------|
| `MCP_CONFIG_CURSOR` | Cursor MCP 配置文件路径 |
| `MCP_CONFIG_CLAUDE` | Claude Code MCP 配置文件路径 |
| `MCP_CONFIG_WINDSURF` | Windsurf MCP 配置文件路径 |
| `MCP_CONFIG_CLINE` | Cline MCP 配置文件路径 |
| `TRAE_MCP_CONFIG` | TRAE MCP 配置文件路径 |
| `TRAE_CN_DIR` | TRAE-CN 配置目录 |
| `TRAE_CN_MCP_CONFIG` | TRAE-CN MCP 配置文件路径 |
| `CLAUDE_GLOBAL_CONFIG` | Claude Code 全局配置文件路径 |
| `OPENCLAW_MCP_CONFIG` | OpenClaw MCP 配置文件路径 |
| `KIMI_CODE_MCP_CONFIG` | Kimi Code MCP 配置文件路径 |
| `CODEX_MCP_CONFIG` | CodeX MCP 配置文件路径 |

### 安全常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `PBKDF2_ITERATIONS` | `600000` | PBKDF2-HMAC-SHA256 迭代次数（OWASP 2023 推荐） |
| `PBKDF2_ITERATIONS_LEGACY` | `100000` | 旧版 PBKDF2 迭代次数（向后兼容） |
| `DANGEROUS_SYSTEM_DIRS` | `List[Path]` | 危险系统目录列表（不应作为数据路径） |

### 限制与阈值常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `DEFAULT_AUTO_BACKUP_INTERVAL` | `20` | 自动备份间隔（写入次数） |
| `MAX_MESSAGE_LENGTH` | `50000` | 最大消息长度（字符） |
| `DEFAULT_RECALL_LIMIT` | `20` | 默认召回数量 |
| `BATCH_RECALL_LIMIT` | `10000` | 大批量召回限制 |
| `AUDIT_LOG_DEFAULT_LIMIT` | `100` | 审计日志默认查询限制 |
| `SESSION_SUMMARIZER_LIMIT` | `200` | 会话摘要最大记忆数 |
| `AGGREGATE_MEMORIES_LIMIT` | `500` | 语义聚合最大记忆数 |
| `RULE_MATCH_LIMIT_CAP` | `5` | 规则匹配上限 |

### 质量与置信度常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `DEFAULT_CONFIDENCE_SCORE` | `0.5` | 默认置信度分数 |
| `MIN_QUALITY_THRESHOLD` | `0.3` | 最低质量阈值 |
| `DECAY_CONFIDENCE_FLOOR` | `0.1` | 衰减后最低置信度 |
| `DECAY_ROUNDING_PRECISION` | `3` | 置信度衰减计算精度（小数位） |

### 显示与截断常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `WHOAMI_PREFERENCE_COUNT` | `10` | whoami() 显示的偏好数量 |
| `WHOAMI_DECISION_COUNT` | `5` | whoami() 显示的决策数量 |
| `WHOAMI_CORRECTION_COUNT` | `5` | whoami() 显示的纠正数量 |
| `CONTENT_PREVIEW_LENGTH` | `100` | 内容预览长度 |
| `RULE_CONTENT_MAX_LENGTH` | `200` | 规则内容最大长度 |

### 上下文构建默认值

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `CONTEXT_BUILD_DEFAULTS` | `Dict` | 包含 `max_memories`(10), `max_knowledge`(5), `max_rules`(5), `max_tokens_context`(2000), `max_tokens_system_prompt`(4000), `max_tokens_qa_prompt`(2000) |

### 共指消解常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `COREFERENCE_RECALL_LIMIT` | `5` | 共指消解使用的最近记忆数 |
| `CORRECTION_RECALL_LIMIT` | `10` | 纠正处理时的搜索记忆数 |
| `CORRECTION_KEYWORD_OVERLAP` | `2` | 纠正匹配的最小关键词重叠数 |
| `ACTIVE_RULES_LIST_LIMIT` | `50` | 纠正处理时检查的最大活跃规则数 |

### 合并调度常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `CONSOLIDATION_MIN_INTERVAL_HOURS` | `0.1` | 定期合并最小间隔（约6分钟） |

### 导入/合并常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `IMPORT_CONTENT_SEARCH_LENGTH` | `50` | 导入时重复检测的内容前缀长度 |
| `MIN_CORRECTION_CONTENT_LENGTH` | `3` | 处理纠正条目的最小内容长度 |

### 分类与强制类型常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `DEFAULT_FORCE_TYPE_CONFIDENCE` | `0.8` | force_type 覆盖分类时的默认置信度 |

### 时间转换常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `SECONDS_PER_HOUR` | `3600` | 一小时的秒数（用于调度计算） |

### 导出格式常量

| 常量名 | 值 | 说明 |
|--------|-----|------|
| `EXPORT_SCHEMA_VERSION` | `"1.0.0"` | 导出/导入文件的 schema 版本 |

### 路径工具函数

| 函数名 | 说明 |
|--------|------|
| `get_config_dir()` | 获取配置目录（支持 `CARRYMEM_CONFIG_DIR` 环境变量） |
| `get_db_path()` | 获取数据库路径（支持 `CARRYMEM_DB_PATH` 环境变量） |
| `get_config_file()` | 获取配置文件路径（支持 `CARRYMEM_CONFIG_FILE` 环境变量） |
| `get_log_dir()` | 获取日志目录（支持 `CARRYMEM_LOG_DIR` 环境变量） |
| `get_cache_dir()` | 获取缓存目录（支持 `CARRYMEM_CACHE_DIR` 环境变量） |
| `get_backup_dir()` | 获取备份目录（支持 `CARRYMEM_BACKUP_DIR` 环境变量） |
| `get_temp_dir()` | 获取临时目录（支持 `CARRYMEM_TEMP_DIR` 环境变量） |
| `get_lock_file()` | 获取锁文件路径（支持 `CARRYMEM_LOCK_FILE` 环境变量） |
| `get_mcp_config_path(tool)` | 获取特定工具的 MCP 配置路径 |
| `get_obsidian_vault_path()` | 获取 Obsidian vault 路径 |
| `ensure_dir_exists(path)` | 确保目录存在，不存在则创建 |
| `validate_path_safety(path, allowed_base)` | 验证路径安全性 |
| `initialize_directories()` | 初始化所有必需目录 |

---

## 类型定义 (`types.py`)

### 基础记忆类型

#### `MemoryEntryDict` (TypedDict)

记忆条目的字典表示（来自 `to_dict()`）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | `str` | 是 | 记忆唯一标识符 |
| `type` | `str` | 是 | 记忆类型（如 preference, decision, fact 等） |
| `content` | `str` | 是 | 记忆内容 |
| `raw_text` | `str` | 是 | 原始文本 |
| `confidence` | `float` | 是 | 置信度分数 (0.0-1.0) |
| `tier` | `int` | 是 | 层级（1=高优先级, 2=中, 3=低） |
| `source_layer` | `str` | 是 | 来源层 |
| `reasoning` | `str` | 是 | 分类推理 |
| `suggested_action` | `str` | 是 | 建议的操作 |
| `recall_hint` | `Optional[Dict[str, Any]]` | 否 | 召回提示 |
| `metadata` | `Dict[str, Any]` | 是 | 元数据 |
| `memory_nature` | `str` | 是 | 记忆性质 |
| `version_chain_id` | `Optional[str]` | 否 | 版本链 ID |
| `version_number` | `int` | 否 | 版本号 |
| `domain` | `Optional[str]` | 否 | 领域标签 |

#### `StoredMemoryDict` (TypedDict)

扩展的存储记忆字典表示。

继承自 `MemoryEntryDict`，额外字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `storage_key` | `str` | 是 | 存储键 |
| `namespace` | `str` | 是 | 命名空间 |
| `created_at` | `Optional[str]` | 否 | 创建时间（ISO格式） |
| `updated_at` | `Optional[str]` | 否 | 更新时间 |
| `expires_at` | `Optional[str]` | 否 | 过期时间 |
| `access_count` | `int` | 是 | 访问次数 |
| `importance_score` | `float` | 是 | 重要度评分 |
| `last_accessed_at` | `Optional[str]` | 否 | 最后访问时间 |
| `version` | `int` | 否 | 当前版本号 |
| `vector_embedding` | `Optional[List[float]]` | 否 | 向量嵌入 |
| `storage_metadata` | `Dict[str, Any]` | 是 | 存储元数据 |
| `superseded_at` | `Optional[str]` | 否 | 被替代的时间 |
| `supersedes` | `Optional[str]` | 否 | 替代的旧记忆键 |

---

### 分类结果类型

#### `ClassificationSummary` (TypedDict)

分类结果的汇总部分。

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_entries` | `int` | 总条目数 |
| `by_type` | `Dict[str, int]` | 按类型分组的计数 |

#### `ClassificationResult` (TypedDict)

`classify_message()` 或 `classify_and_remember()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `should_remember` | `bool` | 否 | 是否应该记住 |
| `type` | `str` | 否 | 主类型 |
| `content` | `str` | 否 | 内容 |
| `entries` | `List[MemoryEntryDict]` | 否 | 分类后的条目列表 |
| `stored` | `bool` | 否 | 是否已存储 |
| `storage_keys` | `List[str]` | 否 | 存储键列表 |
| `rule_suggestions` | `List[Dict[str, Any]]` | 否 | 规则建议 |
| `auto_rules` | `List[Dict[str, Any]]` | 否 | 自动生成的规则 |
| `updated_memories` | `List[Dict[str, Any]]` | 否 | 更新的记忆 |
| `summary` | `ClassificationResult \| ClassificationSummary` | 否 | 汇总信息 |

---

### CRUD 结果类型

#### `DeclareResult` (TypedDict)

`declare()` 或 `declare_preference()` 的返回结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `declared` | `bool` | 是否声明成功 |
| `entries` | `List[StoredMemoryDict]` | 存储的条目 |
| `storage_keys` | `List[str]` | 存储键列表 |
| `source` | `str` | 来源 |
| `summary` | `ClassificationSummary` | 分类汇总 |

#### `UpdateMemoryResult` (TypedDict)

`update_memory()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `updated` | `bool` | 否 | 是否更新成功 |
| `error` | `Optional[str]` | 否 | 错误信息 |
| `storage_key` | `Optional[str]` | 否 | 存储键 |
| `version` | `Optional[int]` | 否 | 新版本号 |
| `content` | `Optional[str]` | 否 | 新内容 |

#### `RollbackMemoryResult` (TypedDict)

`rollback_memory()` 的返回结果。（结构同 `UpdateMemoryResult`）

#### `MergeMemoriesResult` (TypedDict)

`merge_memories()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `total_input` | `int` | 否 | 输入总数 |
| `total_output` | `int` | 否 | 输出总数 |
| `duplicates_removed` | `int` | 否 | 移除的重复数 |
| `strategy` | `str` | 否 | 使用的策略 |
| `namespaces` | `List[str]` | 否 | 涉及的命名空间 |
| `memories` | `List[Dict[str, Any]]` | 否 | 结果记忆列表 |
| `error` | `Optional[str]` | 否 | 错误信息 |

---

### 召回结果类型

#### `RuleMatchDict` (TypedDict)

召回结果中的单个规则匹配。

| 字段 | 类型 | 说明 |
|------|------|------|
| `rule_id` | `str` | 规则 ID |
| `trigger` | `str` | 触发条件 |
| `action` | `str` | 动作 |
| `rule_type` | `str` | 规则类型 |
| `override` | `bool` | 是否覆盖 |
| `score` | `float` | 匹配得分 |
| `match_type` | `str` | 匹配类型 |

#### `RecallAllResult` (TypedDict)

`recall_all()` 的返回结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `rules` | `List[RuleMatchDict]` | 规则匹配列表 |
| `memories` | `List[StoredMemoryDict]` | 记忆列表 |
| `knowledge` | `List[Dict[str, Any]]` | 知识库结果 |
| `rule_count` | `int` | 规则数量 |
| `memory_count` | `int` | 记忆数量 |
| `knowledge_count` | `int` | 知识库数量 |
| `total_count` | `int` | 总数 |
| `namespace` | `str` | 命名空间 |
| `priority` | `str` | 优先级顺序 |

#### `RecallAggregatedResult` (TypedDict)

`recall_aggregated()` 的返回结果。
键为记忆类型名，值为该类型的 `List[StoredMemoryDict]`。

---

### 画像/统计类型

#### `MemoryStats` (TypedDict)

`get_stats()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `adapter` | `Optional[str]` | 否 | 适配器名称 |
| `total_count` | `int` | 否 | 总计数 |
| `by_type` | `Dict[str, int]` | 否 | 按类型分组 |
| `capabilities` | `Dict[str, bool]` | 否 | 能力声明 |

#### `MemoryProfileStats` (TypedDict)

记忆画像中的统计部分。

| 字段 | 类型 | 说明 |
|------|------|------|
| `by_type` | `Dict[str, int]` | 按类型分组 |
| `by_tier` | `Dict[str, int]` | 按层级分组 |
| `confidence_avg` | `float` | 平均置信度 |

#### `MemoryProfile` (TypedDict)

`get_memory_profile()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `summary` | `str` | 否 | 摘要文本 |
| `total_memories` | `int` | 否 | 总记忆数 |
| `highlights` | `Dict[str, List[Dict[str, Any]]]` | 否 | 各类型代表记忆 |
| `stats` | `MemoryProfileStats` | 否 | 统计信息 |
| `last_updated` | `Optional[str]` | 否 | 最后更新时间 |

#### `WhoamiResult` (TypedDict)

`whoami()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `identity` | `str` | 否 | 身份描述 |
| `summary` | `str` | 否 | 摘要 |
| `total_memories` | `int` | 否 | 总记忆数 |
| `top_type` | `str` | 否 | 最常见类型 |
| `confidence_avg` | `float` | 否 | 平均置信度 |
| `preferences` | `List[str]` | 否 | 最近偏好列表 |
| `decisions` | `List[str]` | 否 | 最近决策列表 |
| `corrections` | `List[str]` | 否 | 最近纠正列表 |
| `by_type` | `Dict[str, int]` | 否 | 按类型分组 |
| `domains` | `List[Dict[str, Any]]` | 否 | 领域列表 |

---

### 导入/导出类型

#### `ExportProfileData` (TypedDict)

用户画像导出数据结构。

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | `str` | Schema 版本 |
| `format` | `str` | 格式 |
| `exported_at` | `str` | 导出时间 |
| `identity` | `str` | 身份 |
| `summary` | `str` | 摘要 |
| `preferences` | `List[str]` | 偏好列表 |
| `decisions` | `List[str]` | 决策列表 |
| `corrections` | `List[str]` | 纠正列表 |
| `stats` | `Dict[str, Any]` | 统计 |
| `profile` | `MemoryProfile` | 完整画像 |

#### `ExportProfileResult` (TypedDict)

`export_profile()` 的返回结果。（结构同 `ExportProfileData`）

#### `ExportMemoriesResult` (TypedDict)

`export_memories()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `exported` | `bool` | 否 | 是否导出成功 |
| `format` | `str` | 否 | 导出格式 |
| `path` | `Optional[str]` | 否 | 文件路径 |
| `total_memories` | `int` | 否 | 导出记忆数 |
| `namespace` | `str` | 否 | 命名空间 |
| `content` | `Optional[str]` | 否 | 内容字符串 |
| `data` | `Optional[Dict[str, Any]]` | 否 | 数据字典 |

#### `ImportMemoriesResult` (TypedDict)

`import_memories()` 的返回结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `imported` | `int` | 成功导入数 |
| `skipped` | `int` | 跳过数 |
| `errors` | `int` | 错误数 |
| `total_processed` | `int` | 总处理数 |
| `namespace` | `str` | 目标命名空间 |
| `merge_strategy` | `str` | 使用的合并策略 |

---

### 维护类型

#### `ConflictInfo` (TypedDict)

冲突信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `conflict_id` | `str` | 冲突 ID |
| `type` | `str` | 冲突类型 |
| `items` | `List[Dict[str, Any]]` | 涉及的项目 |
| `severity` | `str` | 严重程度：low/medium/high |
| `suggestion` | `str` | 解决建议 |

#### `QualityIssue` (TypedDict)

质量问题信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `memory_id` | `str` | 记忆 ID |
| `issue_type` | `str` | 问题类型 |
| `score` | `float` | 质量分数 |
| `suggestion` | `str` | 建议 |

#### `ConsolidationResult` (TypedDict)

`consolidate()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `dry_run` | `bool` | 否 | 是否试运行 |
| `memories_processed` | `int` | 否 | 处理的记忆数 |
| `memories_removed` | `int` | 否 | 移除的记忆数 |
| `memories_decayed` | `int` | 否 | 衰减的记忆数 |
| `conflicts_resolved` | `int` | 否 | 解决的冲突数 |
| `duration_seconds` | `float` | 否 | 耗时（秒） |
| `details` | `Dict[str, Any]` | 否 | 详细信息 |

#### `ScheduleConsolidationResult` (TypedDict)

`schedule_consolidation()` 的返回结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `scheduled` | `bool` | 是否成功调度 |
| `interval_hours` | `float` | 间隔（小时） |
| `dry_run` | `bool` | 是否试运行 |
| `message` | `str` | 消息 |

---

### 备份类型

#### `BackupResult` (TypedDict)

`backup()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `backed_up` | `bool` | 否 | 是否成功 |
| `path` | `Optional[str]` | 否 | 备份路径 |
| `error` | `Optional[str]` | 否 | 错误信息 |

#### `RestoreBackupResult` (TypedDict)

`restore_backup()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `restored` | `bool` | 否 | 是否成功 |
| `path` | `str` | 否 | 备份文件路径 |
| `error` | `Optional[str]` | 否 | 错误信息 |

#### `AuditLogEntry` (TypedDict)

单条审计日志。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `timestamp` | `str` | 否 | 时间戳 |
| `operation` | `str` | 否 | 操作类型 |
| `source` | `str` | 否 | 来源 |
| `details` | `Dict[str, Any]` | 否 | 详情 |

---

### 提示词委托类型

#### `ContextBuildResult` (TypedDict)

`build_context()` 的返回结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `context_str` | `str` | 上下文字符串 |
| `memories` | `List[StoredMemoryDict]` | 记忆列表 |
| `knowledge` | `List[Dict[str, Any]]` | 知识列表 |
| `rules` | `List[RuleMatchDict]` | 规则列表 |
| `token_count` | `int` | token 数量 |
| `truncated` | `bool` | 是否被截断 |

#### `SessionSummaryResult` (TypedDict)

`summarize_session()` 的返回结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | `str` | 否 | 会话 ID |
| `summary` | `str` | 否 | 摘要文本 |
| `key_points` | `List[str]` | 否 | 关键点列表 |
| `memories_extracted` | `int` | 否 | 提取的记忆数 |
| `language` | `str` | 否 | | 语言 |
| `stored` | `bool` | 否 | 是否已存储 |

---

### 健康/状态类型

#### `ComponentHealth` (TypedDict)

单个组件健康状态。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | `str` | 是 | 状态："ready"/"not_configured"/"error" |
| `type` | `Optional[str]` | 否 | 类名（如果 ready） |
| `stats` | `Optional[Dict[str, Any]]` | 否 | 统计（对于存储适配器） |
| `error` | `Optional[str]` | 否 | 错误信息（如果 error） |

#### `HealthCheckResult` (TypedDict)

`health_check()` 的返回结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `str` | 整体状态："ok" / "degraded" |
| `components` | `Dict[str, ComponentHealth]` | 各组件状态 |
| `issues` | `List[str]` | 问题列表 |

#### `ComponentStatusDict` (TypedDict)

`get_component_status()` 的返回结果。
键为组件名，值为状态字符串（"ready"/"not_configured"/"error"）。

---

### 便捷类型别名

| 别名 | 实际类型 | 说明 |
|------|----------|------|
| `MemoryDict` | `StoredMemoryDict` | 召回结果中的记忆字典 |
| `FilterDict` | `Dict[str, Any]` | 查询过滤器 |
| `ContextDict` | `Dict[str, Any]` | 消息上下文 |
| `MetadataDict` | `Dict[str, Any]` | 条目元数据 |

---

## 异常类层次结构

```
CarryMemError (base)
├── ConfigError              (CM-001~099)
├── StorageAdapterError      (CM-100~199)
│   ├── StorageError
│   │   ├── StorageNotConfiguredError
│   │   ├── DatabaseError
│   │   │   ├── DBConnectionError
│   │   │   └── QueryError
├── MemoryOperationError     (CM-200~299)
├── ClassificationError      (CM-300~399)
├── SecurityError            (CM-400~499)
├── ImportExportError        (CM-500~599)
└── CLIEntryError            (CM-600~699)
```

---

*文档维护: CarryMem 开发团队*
*最后更新: 2026-06-11*
