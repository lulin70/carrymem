# CarryMem 架构设计

**版本**: v0.2.0  
**日期**: 2026-05-13  
**状态**: 稳定

---

## 目录

1. [系统概览](#系统概览)
2. [核心架构](#核心架构)
3. [分层设计](#分层设计)
4. [数据流](#数据流)
5. [关键组件](#关键组件)
6. [规则引擎](#规则引擎)
7. [上下文工程](#上下文工程)
8. [扩展机制](#扩展机制)
9. [性能优化](#性能优化)
10. [安全设计](#安全设计)

---

## 系统概览

### 设计哲学

CarryMem 采用 **分层架构 + 插件设计**：

1. **零配置**: 开箱即用，自动初始化
2. **高性能**: 60%+ 零成本分类，FTS5 全文搜索
3. **可扩展**: 适配器模式支持多种存储后端
4. **跨平台**: 纯 Python，最少外部依赖

### 核心价值

```
用户输入 → 自动分类 → 智能存储 → 语义召回
   ↓           ↓          ↓          ↓
 简单      90%+ 准确率  去重+TTL   <100ms
```

---

## 核心架构

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    用户层                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Python   │  │   CLI    │  │   MCP    │              │
│  │   API    │  │  工具    │  │  服务器  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   API 层                                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │              CarryMem（主入口）                    │  │
│  │  - classify_and_remember()  - recall_memories()   │  │
│  │  - declare()  - forget_memory()                   │  │
│  │  - export_memories()  - import_memories()         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              分类层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  规则引擎    │  │   模式      │  │   语义      │ │
│  │ (零成本)     │  │  分析器     │  │  分类器     │ │
│  │    60%+      │  │    ~30%     │  │    <10%     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               存储层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   SQLite     │  │   Obsidian   │  │   自定义     │ │
│  │  (默认)      │  │   (插件)     │  │  (适配器)    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               召回层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  FTS5 搜索   │  │   语义      │  │    结果      │ │
│  │  (精确)      │  │   扩展器    │  │    合并器    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               记忆整合层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  P0: 去重    │  │  P1: 模式    │  │  P2: 语义    │ │
│  │  + 衰减      │  │  → 规则      │  │  合并        │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 分层设计

### 1. 用户层

**职责**: 提供多种交互方式

#### 1.1 Python API
```python
from carrymem import CarryMem

with CarryMem() as cm:
    cm.classify_and_remember("我偏好深色模式")
    memories = cm.recall_memories(query="主题")
```

#### 1.2 CLI 工具
```bash
carrymem init
carrymem list
carrymem stats
```

#### 1.3 MCP 服务器
```json
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "carrymem.integration.layer2_mcp"]
    }
  }
}
```

### 2. API 层

**职责**: 统一业务逻辑入口

#### 核心类: CarryMem

```python
class CarryMem:
    def __init__(
        self,
        storage: Optional[Any] = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict] = None,
    ): ...

    def classify_and_remember(self, message, context=None, language=None) -> Dict: ...
    def recall_memories(self, query=None, filters=None, limit=20) -> List[Dict]: ...
    def forget_memory(self, memory_id: str) -> bool: ...
    def declare(self, message: str) -> Dict: ...
    def get_memory_profile(self) -> Dict: ...
    def export_memories(self, output_path=None, format="json", namespace=None) -> Dict: ...
    def import_memories(self, input_path=None, merge_strategy="skip", namespace=None) -> Dict: ...
    def build_system_prompt(self, context=None, max_memories=10, max_knowledge=5, language="en") -> str: ...
```

### 3. 分类层

**职责**: 自动识别记忆类型

#### 三级分类策略

```
输入 → 规则引擎 (60%+) → 模式分析器 (~30%) → 语义分类器 (<10%)
         ↓                    ↓                    ↓
     零成本             近零成本              Token 成本
     高速度             中速度                低速度
```

#### 3.1 规则引擎 (RuleMatcher)

基于正则和关键词的模式分类。零成本，覆盖约 60% 的输入。

#### 3.2 模式分析器 (PatternAnalyzer)

基于 NLP 的模式分析。近零成本，覆盖约 30% 的输入。

#### 3.3 语义分类器 (SemanticClassifier)

基于 LLM 的模糊分类。Token 成本，覆盖 <10% 的输入。

### 4. 存储层

**职责**: 持久化和检索

#### 4.1 适配器接口

```python
class StorageAdapter(ABC):
    @abstractmethod
    def remember(self, entry: MemoryEntry) -> StoredMemory: ...

    @abstractmethod
    def recall(self, query: str, filters=None, limit=20, namespaces=None) -> List[StoredMemory]: ...

    @abstractmethod
    def forget(self, storage_key: str) -> bool: ...
```

#### 4.2 SQLite 适配器

**特性**:
- FTS5 全文搜索（trigram 分词器）
- 内容去重（content_hash）
- TTL 自动过期
- 事务支持（BEGIN/COMMIT/ROLLBACK）
- 线程安全（threading.Lock + threading.local）

**数据库模式**:
```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    original_message TEXT,
    raw_text TEXT,              -- 新增：用户原始输入，用于 FTS5 双索引
    confidence REAL NOT NULL,
    tier INTEGER NOT NULL,
    namespace TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    access_count INTEGER,
    content_hash TEXT NOT NULL,
    metadata TEXT,
    superseded_at TEXT,         -- 新增：此记忆被取代的时间
    supersedes TEXT             -- 新增：此记忆取代的记忆 ID
);

CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    original_message,
    tokenize='trigram'
);
```

### 5. 召回层

**职责**: 智能检索和结果优化

#### 5.1 召回流水线

```
查询 → FTS5 搜索 → 语义扩展 → 结果融合 → 排序 → 返回
  ↓        ↓          ↓          ↓        ↓      ↓
验证    精确匹配   同义词扩展   去重    相关性   Top-K
```

#### 5.2 语义扩展

零依赖语义扩展：
- **同义词扩展**: 基于 YAML 的同义词图（470+ 术语，CN/EN/JP）
- **拼写纠正**: Levenshtein 编辑距离
- **跨语言映射**: CN↔EN↔JP 术语映射

#### 5.3 结果融合

```python
class ResultMerger:
    def merge(self, original_results, expanded_results, query, limit=20, source="synonym"):
        # 1. 按 storage_key 去重
        # 2. 计算相关性分数
        # 3. 按相关性排序
        # 4. 返回 Top-K
```

### 6. 知识生命周期层

**职责**: 追踪知识演变，管理记忆取代

#### 6.1 自动取代流水线

```
新记忆 → Jaccard 相似度检测 → 矛盾检测 → 标记旧记忆为已取代
   ↓           ↓                    ↓                ↓
 INSERT   ≥ 0.25 阈值          词边界正则匹配      superseded_at = now
          + 更新标记检测     (like/dislike 等)       supersedes = new_key
                              + 助手消息排除
```

#### 6.2 会话感知存储

```
classify_and_remember(session_id="s_20260513")
     ↓
session_id → metadata JSON → recall() 中的 session_id 过滤
```

#### 6.3 时间表达式解析

```
查询: "我最近对数据库做了什么决定？"
     ↓
_parse_time_expressions() → created_after = 7 天前
     ↓
recall_memories(query="数据库", filters={"created_after": "2026-05-06T..."})
```

### 7. 记忆整合层

**职责**: 记忆生命周期管理，去重、衰减与语义合并

- **记忆整合引擎** (`consolidation.py`)：记忆生命周期管理，三个阶段：
  - P0：基于 Jaccard 的去重（≥0.85）+ 指数半衰期衰减
  - P1：模式检测 → 通过 PromotionPipeline 生成规则候选
  - P2：语义聚类 → 宿主 LLM 整合请求
  - 偏好始终保留（不会被衰减或去重）

---

## 数据流

### 存储流程

```
1. 用户输入
   ↓
2. 输入验证
   ↓
3. 分类（规则 → 模式 → 语义）
   ↓
4. 创建 MemoryEntry
   ↓
5. 计算 content_hash
   ↓
6. 检查重复
   ↓
7. 存储到数据库
   ↓
8. 更新 FTS5 索引
   ↓
9. 返回结果
```

### 召回流程

```
1. 用户查询
   ↓
2. 查询验证
   ↓
3. FTS5 搜索
   ↓
4. 结果不足？ → 语义扩展
   ↓
5. 结果融合
   ↓
6. 去重 + 排序
   ↓
7. 更新 access_count
   ↓
8. 返回 Top-K
```

---

## 关键组件

### 1. 配置

```python
# 默认配置
CarryMem(storage="sqlite", db_path=None, namespace="default")

# 自定义存储
CarryMem(storage=SQLiteAdapter(db_path="/custom/path.db"))

# 带知识库
CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
```

### 2. 异常层级

```python
class CarryMemError(Exception):
    """基础异常"""

class StorageError(CarryMemError):
    """存储错误"""

class DatabaseError(StorageError):
    """数据库错误"""

class ValidationError(CarryMemError):
    """验证错误"""
```

### 3. 日志

```python
from carrymem.utils.logger import logger

# 日志级别: DEBUG, INFO, WARNING, ERROR
# 文件: ~/.carrymem/logs/carrymem.log（如已配置）
```

---

## 规则引擎

### 架构概览

规则引擎是 CarryMem 的行为契约系统，将记忆转化为可执行的规则。

```
┌─────────────────────────────────────────────────────────────┐
│                    规则引擎                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  规则来源:                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  手动 CRUD   │ │  自动        │ │  经验        │        │
│  │              │ │  晋升        │ │  学习        │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │  问答精炼    │ │  模板        │                          │
│  │              │ │              │                          │
│  └──────────────┘ └──────────────┘                          │
│                                                              │
│  核心流水线:                                                 │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐    │
│  │ 净化    │ → │  限制   │ → │  存储   │ → │  匹配   │    │
│  │ (输入)  │   │ (使用)  │   │ (SQLite)│   │ (FTS5)  │    │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘    │
│       ↓                                          ↓          │
│  ┌─────────┐   ┌──────────────┐   ┌─────────────────┐     │
│  │ 冲突    │   │   注入       │   │   审计追踪      │     │
│  │ 检测    │   │ (格式化为    │   │ (晋升审计       │     │
│  │         │   │  LLM提示)   │   │  经验审计       │     │
│  └─────────┘   └──────────────┘   │  精炼会话)      │     │
│                                     └─────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 规则模型

```python
class Rule:
    id: str                    # rule_xxxxxxxx
    trigger: str               # 场景描述（FTS5 索引）
    action: str                # 触发时执行的操作
    rule_type: str             # forbid | avoid | always | prefer | format
    override: bool             # True = 不可覆盖
    status: str                # active | paused | deprecated
    derived_from: str          # manual | auto_promotion | failure_lesson | refined | refinement_session
    source_memories: List[str] # 来源记忆 ID
    confidence: float          # 0.0-1.0
    created_at: str
    updated_at: str
```

### 规则生命周期

```
创建 → 活跃 → 暂停 → 废弃
  ↑       ↓
  └── 恢复

派生路径:
  手动创建: 用户通过 CLI 或 API 显式创建
  自动晋升: 模式检测 → 候选 → 用户确认
  经验学习: 失败信号 → 教训 → 用户确认
  问答精炼: 特定规则 → 多轮对话 → 通用规则
```

### 冲突检测

检测三种冲突类型：

| 冲突类型 | 严重度 | 示例 |
|---------|--------|------|
| **矛盾** | 高 | "始终使用 React" vs "从不使用 React" |
| **重叠** | 中 | "偏好 PostgreSQL" vs "偏好 MySQL"（相同触发器） |
| **冗余** | 低 | "避免 MongoDB" vs "避免文档数据库" |

### 安全层

1. **净化器**: Prompt 注入检测、SQL 注入阻止、长度限制
2. **限制器**: 全局规则上限(3)、总上限(200)、速率限制
3. **自动晋升安全**: 需要用户确认、过期机制、队列限制
4. **经验安全**: 重复检测、净化器验证、审计追踪
5. **精炼安全**: 最大轮次、会话过期、净化器验证

---

## 上下文工程

### 问题: 中间丢失效应

LLM 注意力遵循 U 型曲线 — 上下文开头和结尾注意力高，中间显著降低。研究表明，放在长上下文中间的信息召回率下降 10-40%。

这直接影响 CarryMem 的规则注入：如果关键的 override 规则被放在注入提示的中间，它们可能被 LLM 忽略。

### 解决方案: 锚定布局模式

```
┌─────────────────────────────────────────────────┐
│ 头部锚点（最高注意力）                            │
│ ┌─────────────────────────────────────────────┐ │
│ │ 绝对禁止（override + forbid）                │ │
│ │ - 未经核实不得引用竞品数据                   │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ 中间（较低注意力）                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ 推荐（override=false）                      │ │
│ │ - 偏好国内仓库                              │ │
│ │ - 电话确认库存                              │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ 尾部锚点（高注意力）                              │
│ ┌─────────────────────────────────────────────┐ │
│ │ 强制动作（override + always）                │ │
│ │ - 所有报价必须包含有效期                     │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

`format_rules_as_prompt()` 中的实现：
```python
def format_rules_as_prompt(
    matches: List[MatchResult],
    style: str = "default",     # "default" | "ddd" | "anchored"
    context_budget_tokens: int = 2000,
) -> str:
    if style == "anchored":
        # 排序: 头部=override+forbid, 中间=normal, 尾部=override+always
        head = [m for m in matches if m.override and m.rule_type == "forbid"]
        middle = [m for m in matches if not m.override]
        tail = [m for m in matches if m.override and m.rule_type == "always"]
        ...
```

### DDD 语言视图

CarryMem 概念可以用领域驱动设计术语表达，便于与企业架构师对话：

| CarryMem 概念 | DDD 等价物 | 关系 |
|-------------|-----------|------|
| trigger | 限界上下文 | 定义范围边界 |
| rule_type: forbid | 聚合不变量 | 不可违反 |
| rule_type: always | 一致性保证 | 必须满足 |
| rule_type: avoid/prefer | 软约束 | 尽力遵守 |
| override | 不变量标志 | 不可被更高优先级覆盖 |
| source_memories | 事件溯源链 | 规则可追溯到原始经验 |
| 精炼过程 | 统一语言精炼 | 特定 → 通用抽象 |

### 上下文预算监控

当规则注入接近上下文窗口限制时：

1. **Token 估算**: 粗略 Token 数 = len(text) / 4（英文）或 len(text) / 2（CJK）
2. **压缩策略**: Override 规则保留，avoid 规则压缩为单行摘要
3. **阈值**: `context_budget_tokens` 的 70% 触发压缩

---

## 扩展机制

### 1. 自定义存储适配器

```python
from carrymem.adapters import StorageAdapter

class PostgreSQLAdapter(StorageAdapter):
    def remember(self, entry: MemoryEntry) -> StoredMemory: ...
    def recall(self, query: str, **kwargs) -> List[StoredMemory]: ...
    def forget(self, storage_key: str) -> bool: ...

# 使用
cm = CarryMem(storage=PostgreSQLAdapter("postgresql://..."))
```

### 2. 插件系统

```python
# setup.py
entry_points={
    "carrymem.adapters": [
        "postgresql=my_plugin:PostgreSQLAdapter",
    ],
}

# 动态加载
cm = CarryMem(storage="postgresql")
```

---

## 性能优化

### 1. 查询优化

**索引策略**:
- 单列: type, namespace, content_hash
- 复合: (namespace, type), (namespace, tier)
- FTS5: trigram 分词器

### 2. 批量操作

```python
# 事务性批量操作
adapter.remember_batch(entries)
# → BEGIN → INSERT... → COMMIT（出错则 ROLLBACK）
```

### 3. 线程安全

```python
# ThreadLocal 连接 + Lock
adapter = SQLiteAdapter()  # 默认线程安全
```

---

## 安全设计

### 1. 输入验证

所有输入通过 `validators.py` 验证：
- 消息长度限制
- 命名空间字符白名单
- 存储键格式验证
- 查询长度限制

### 2. SQL 注入防护

所有查询使用参数化语句（`?` 占位符）。

### 3. 路径安全

```python
# 路径遍历防护
def _validate_file_path(path: str) -> str:
    if ".." in path:
        raise ValueError("Path traversal not allowed")
    return os.path.realpath(os.path.expanduser(path))
```

### 4. MCP 处理器安全

- 异常净化: 内部错误不暴露给客户端
- 参数钳制: limit, max_memories, max_knowledge 均有上限
- 语言白名单: 仅接受 "en", "zh", "ja"

---

## 总结

CarryMem 采用 **分层架构 + 插件设计**，实现：

✅ **高性能**: FTS5 + 索引 + 缓存  
✅ **可扩展**: 适配器模式 + 插件系统  
✅ **易使用**: 零配置 + CLI 工具  
✅ **安全**: 输入验证 + 参数化查询 + 路径安全
