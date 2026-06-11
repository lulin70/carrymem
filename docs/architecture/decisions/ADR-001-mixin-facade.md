# ADR-001: Mixin + Facade 架构

## 状态: 已采纳
## 日期: 2026-06-11
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem v0.2.x 的核心类 `carrymem.py` 是一个 **1769 行的 God Class**，承担了生命周期管理、记忆 CRUD、分类、召回、备份、规则注入、提示词构建等全部职责。这导致：

1. **可维护性差**：修改一个功能（如加密）需要理解整个文件。
2. **测试困难**：无法单独测试某个功能模块，必须实例化完整的 CarryMem 对象。
3. **协作冲突**：多人同时修改同一文件时 Git 冲突频繁。
4. **扩展受限**：新增功能只能往已有的大文件里塞代码。

需要一种方式将 God Class 拆分为职责清晰的模块，同时保持对外 API 的向后兼容。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: Composition（组合）** | CarryMem 持有多个 Manager 对象的引用，通过委托调用 | 解耦最彻底；每个 Manager 可独立测试和替换 | API 变化大：`cm.memory_crud.add()` vs `cm.add()`；跨模块状态共享复杂 |
| **B: Mixin + Facade（混入+门面）** ✅ | 将功能拆分为 Mixin 类，由 Facade 类（CarryMem）多重继承组合 | API 完全不变（`cm.add()` 依旧）；共享状态通过 `self` 自然传递；改动量最小 | Mixin 间存在隐式依赖；MRO 需要仔细设计 |
| **C: Service Layer** | 引入服务层，CarryMem 仅做路由 | 架构最"正确" | 过度工程化；对个人工具项目而言太重 |

## 决策

**采用方案 B：Mixin + Facade 架构。**

具体实现：

```
src/carrymem/core/
├── __init__.py              # Facade — CarryMem 类（多重继承组合）
├── _protocols.py            # Protocol 接口定义
├── _lifecycle.py            # LifecycleMixin — 根节点，初始化所有共享状态
├── _backup.py               # BackupMixin
├── _memory_crud.py          # MemoryCRUDMixin
├── _classification.py       # ClassificationMixin
├── _recall.py               # RecallMixin
├── _profile_export.py       # ProfileExportMixin
├── _maintenance.py          # MaintenanceMixin
└── _prompt_delegate.py      # PromptDelegateMixin
```

关键设计原则：
- **LifecycleMixin 为根节点**：`__init__()` 初始化 `_adapter`、`_namespace`、`_engine` 等全部共享状态。
- **DAG 依赖图**：Mixin 之间的依赖形成有向无环图，避免循环依赖。
- **Protocol 文档化依赖**：每个 Mixin 的公共接口通过 `typing.Protocol` 定义在 `_protocols.py` 中。

## 后果

### 正面
- **API 零破坏**：外部调用方 `cm.add()`、`cm.recall_memories()` 等签名完全不变。
- **文件大小可控**：每个 Mixin 文件控制在 200~400 行，可读性大幅提升。
- **独立测试**：可以针对单个 Mixin 编写单元测试，无需实例化完整对象。
- **渐进式演进**：新功能只需新增 Mixin 并加入继承链即可。

### 负面
- **隐式耦合**：Mixin 通过 `self.xxx` 访问其他 Mixin 的属性/方法，IDE 无法静态检查这种跨 Mixin 依赖。
- **MRO 复杂性**：8 个 Mixin 的方法解析顺序（MRO）需要开发者理解 C3 线性化算法。
- **命名空间污染**：所有 Mixin 的方法都在同一个 `self` 上，可能出现同名方法覆盖风险。
- **难以替换实现**：相比 Composition，Mixin 不支持运行时替换某个组件的实现（如换一个存储后端）。

### 缓解措施
- 使用 `_protocols.py` 中的 Protocol 接口显式声明每个 Mixin 提供的能力。
- 在 ARCHITECTURE.md 中维护 DAG 依赖图，作为代码审查依据。
- 私有方法以 `_` 前缀命名，公共方法保持语义清晰。
