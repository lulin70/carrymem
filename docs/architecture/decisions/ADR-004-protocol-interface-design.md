# ADR-004: Protocol 接口设计

## 状态: 已采纳
## 日期: 2026-06-11
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem 采用 Mixin + Facade 架构后，8 个 Mixin 之间存在复杂的协作关系（见 ADR-001）。例如：
- `ClassificationMixin` 调用 `RecallMixin.recall_memories()`
- `MemoryCRUDMixin` 调用 `ClassificationMixin._classify_message()`
- `ProfileExportMixin` 同时依赖 `RecallMixin` 和 `BackupMixin`

需要一个机制来**文档化和类型化**这些跨 Mixin 的依赖关系，使 IDE 能提供自动补全，使 mypy 能进行类型检查，使代码审查者能快速理解契约。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: ABC (抽象基类)** | 使用 `abc.ABC` + `abstractmethod` 定义接口 | 运行时可检查 `isinstance()`；Python 传统做法 | 必须显式继承；增加运行时开销；Mixin 已经有多重继承，再加 ABC 层会复杂化 MRO |
| **B: typing.Protocol (结构化类型)** ✅ | 使用 `typing.Protocol` 定义鸭子类型接口 | 无需显式继承；纯静态类型检查；IDE 友好；不影响 MRO | Python < 3.8 需要typing_extensions；运行时不可直接 `isinstance`（除非加 @runtime_checkable） |
| **C: Pydantic BaseModel** | 用 Pydantic 模型定义接口契约 | 自动验证；支持序列化 | 引入重依赖；语义不匹配（Protocol 是行为契约，不是数据模型） |
| **D: 纯文档 (docstring)** | 只在 docstring 和注释中描述接口 | 零成本 | 无类型安全；IDE 无法补全；容易过时 |

## 决策

**采用方案 B：`typing.Protocol` 结构化类型定义。**

具体实现在 `src/carrymem/core/_protocols.py` 中：

```python
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

@runtime_checkable
class HasSharedState(Protocol):
    """所有 Mixin 共享的最小状态集合（由 LifecycleMixin 初始化）。"""
    @property
    def _adapter(self) -> Optional[Any]: ...
    @property
    def _namespace(self) -> str: ...

@runtime_checkable
class HasRecallOps(Protocol):
    """RecallMixin 提供的召回能力。"""
    def recall_memories(self, query: str = "", **kwargs) -> List[Dict]: ...
    def recall_from_knowledge(self, query: str, **kwargs) -> List[Dict]: ...

@runtime_checkable
class HasBackupOps(Protocol):
    """BackupMixin 提供的备份能力。"""
    def backup(self) -> Dict: ...
    def list_backups(self) -> List[Dict]: ...
    def restore_backup(self, path: str) -> Dict: ...

# ... 每个 Mixin 对应一个 Protocol
```

使用方式：

```python
def _some_helper(recaller: HasRecallOps) -> None:
    """这个函数只依赖 RecallMixin 的能力，不关心完整 CarryMem 类型。"""
    results = recaller.recall_memories(query="hello")
    # IDE 能自动补全 recall_memories 的参数和返回值
```

关键设计原则：
- **1:1 映射**：每个 Mixin 对应一个 Protocol。
- **仅公共方法**：Protocol 只声明公共接口，私有辅助方法不暴露。
- **嵌套引用**：跨 Mixin 依赖通过 Protocol 类型注解表达（如 ClassificationMixin 的参数类型包含 HasRecallOps）。
- **@runtime_checkable**：标记后支持 `isinstance(obj, HasRecallOps)` 运行时检查。

## 后果

### 正面
- **零运行时开销**：Protocol 是纯类型构造，不影响运行时行为（除 `isinstance` 外）。
- **IDE 友好**：VS Code / PyCharm 能基于 Protocol 提供准确的自动补全和类型提示。
- **mypy 兼容**：完全兼容 mypy 静态类型检查，能在 CI 中捕获类型错误。
- **不改 MRO**：Protocol 不参与多重继承的方法解析顺序，不会引发 MRO 问题。
- **鸭子类型自然契合**：Mixin 本质就是鸭子类型——只要对象有这些方法就能工作，Protocol 只是将其形式化。

### 负面
- **学习曲线**：团队成员需要理解 structural subtyping（结构化子类型）与 nominal subtyping（名义子类型）的区别。
- **Python 3.7 兼容性**：需要 `from __future__ import annotations` 或 `typing_extensions`。
- **可能的误判**：`@runtime_checkable` 的 `isinstance` 检查只验证属性是否存在，不验证签名是否匹配。
- **维护负担**：每次 Mixin 接口变化时需要同步更新对应的 Protocol 定义。

### 缓解措施
- 在 `_protocols.py` 文件头部添加详细的设计原则注释和使用示例。
- CI 中加入 mypy 严格模式检查 Protocol 与实际实现的兼容性。
- 将 Protocol 文件放在 `core/` 目录下，与 Mixin 实现同级，便于同步维护。
