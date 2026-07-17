# CarryMem Core 架构文档 — Mixin 耦合治理 (P0-1)

> **版本**: v0.8.0 | **日期**: 2026-07-14 | **状态**: ✅ 已完成

## 1. 概述

v0.3.0 将原始的 `carrymem.py`（1769 行 God Class）拆分为 **8 个 Mixin + 1 个 Facade** 模式。
本文档记录 Mixin 之间的依赖关系、共享状态使用情况，以及如何安全地扩展架构。

## 2. 文件结构

```
src/carrymem/core/
├── __init__.py              # Facade — CarryMem 类（多重继承组合）
├── _protocols.py            # Protocol 接口定义（结构性类型）
├── _lifecycle.py            # LifecycleMixin — 生命周期 & 共享状态
├── _backup.py               # BackupMixin — 备份/审计
├── _memory_crud.py          # MemoryCRUDMixin — 核心增删改查
├── _classification.py       # ClassificationMixin — 分类管道
├── _recall.py               # RecallMixin — 检索操作
├── _profile_export.py       # ProfileExportMixin — 档案/导出/导入
├── _maintenance.py          # MaintenanceMixin — 质量/冲突/合并
└── _prompt_delegate.py      # PromptDelegateMixin — 提示词构建/LLM
```

## 3. Mixin 依赖图 (DAG)

```
                        ┌─────────────────────┐
                        │   LifecycleMixin    │ ◄── 根节点（无外部依赖）
                        │  __init__/close/     │     提供所有共享状态
                        │  properties          │
                        └──────┬──────┬───────┘
                               │      │
              ┌────────────────┘      └────────────────┐
              ▼                                          ▼
    ┌─────────────────┐                     ┌─────────────────────┐
    │   BackupMixin   │                     │     RecallMixin     │
    │ backup/audit    │                     │ recall/search        │
    └────────┬────────┘                     └──────┬───────────────┘
             │                                      │
             │         ┌──────────────────┐         │
             └────────►│ ClassificationMix│◄────────┘
                       │ in (分类管道)      │
                       └────────┬─────────┘
                                │
                     ┌──────────▼──────────┐
                     │  MemoryCRUDMixin    │ ◄── 最高层消费者
                     │  增删改查核心操作     │
                     └─────────────────────┘

             ┌─────────────────────┐
             │ ProfileExportMixin  │ ◄── 依赖 Recall + Backup
             │ whoami/export/import│
             └─────────────────────┘

             ┌─────────────────────┐
             │ MaintenanceMixin    │ ◄── 仅依赖 Lifecycle 状态
             │ quality/conflict/   │
             │ consolidation       │
             └─────────────────────┘

             ┌─────────────────────┐
             │ PromptDelegateMixin │ ◄── 依赖 Lifecycle + Recall
             │ prompt/LLM features │
             └─────────────────────┘
```

### 3.1 依赖关系详解

| Mixin | 依赖的 Mixin / 属性 | 调用的方法 |
|-------|---------------------|-----------|
| **LifecycleMixin** | 无（根节点） | — |
| **BackupMixin** | LifecycleMixin（共享状态） | `self._adapter`, `self._backup_dir`, `self._write_count`, `self._auto_backup_interval`, `self._initial_backup_done`, `self._namespace` |
| **RecallMixin** | LifecycleMixin（共享状态） | `self.rule_engine`, `self._adapter`, `self._knowledge_adapter`, `self._namespace`, `self.recall_memories()` (自身), `self.recall_from_knowledge()` (自身) |
| **ClassificationMixin** | RecallMixin, LifecycleMixin, BackupMixin | `self.recall_memories()` (Recall), `self._engine`, `self.rule_engine` (Lifecycle), `self._candidate_generator.*` (Lifecycle), `self._adapter`, `self._auto_backup()` (Backup) |
| **MemoryCRUDMixin** | ClassificationMixin, BackupMixin | `self._validate_and_resolve()`, `self._classify_message()`, `self._store_entries()` (Classification), `self.classify_message()`, `self._count_by_type()` (Classification), `self._auto_backup()` (Backup) |
| **ProfileExportMixin** | RecallMixin, BackupMixin, LifecycleMixin | `self.recall_memories()` (Recall), `self._auto_backup()` (Backup), `_validate_file_path()` (Lifecycle), `self._adapter`, `self._namespace` |
| **MaintenanceMixin** | LifecycleMixin（共享状态） | `self._adapter`, `self._rule_engine`, `self._namespace`, `self._consolidation_timer` (Lifecycle class attr), `self.consolidate()` (自身) |
| **PromptDelegateMixin** | LifecycleMixin, RecallMixin | `self.prompt_builder` (Lifecycle), `self.recall_memories()` (Recall), `self._adapter`, `self._config` |

## 4. 共享状态说明

### 4.1 由 LifecycleMixin.__init__() 初始化的状态

| 属性名 | 类型 | 说明 | 主要消费者 |
|--------|------|------|-----------|
| `_engine` | `MemoryClassificationEngine` | 分类引擎 | ClassificationMixin, MemoryCRUDMixin |
| `_adapter` | `StorageAdapter \| None` | 存储适配器 | **全部 Mixin** |
| `_knowledge_adapter` | `StorageAdapter \| None` | 知识库适配器 | RecallMixin |
| `_namespace` | `str` | 命名空间 | BackupMixin, RecallMixin, MaintenanceMixin, ProfileExportMixin |
| `_config` | `Dict \| None` | 配置字典 | PromptDelegateMixin, ProfileExportMixin |
| `_rule_engine` | `RuleEngine \| None` (lazy) | 规则引擎 | ClassificationMixin, RecallMixin, MaintenanceMixin |
| `_prompt_builder` | `PromptBuilder \| None` (lazy) | 提示词构建器 | PromptDelegateMixin |
| `_candidate_generator` | `RuleCandidateGenerator` | 规则候选生成器 | ClassificationMixin |
| `_write_count` | `int` | 写入计数器 | BackupMixin |
| `_auto_backup_interval` | `int` | 自动备份间隔 | BackupMixin |
| `_initial_backup_done` | `bool` | 初始备份标记 | BackupMixin |
| `_backup_dir` | `str \| None` | 备份目录 | BackupMixin |

### 4.2 类级别属性

| 属性名 | 所属 Mixin | 类型 | 说明 |
|--------|-----------|------|------|
| `_consolidation_timer` | `LifecycleMixin` | `Timer \| None` | 后台合并定时器，被 MaintenanceMixin 读写 |

### 4.3 运行时动态属性

| 属性名 | 所属 Mixin | 类型 | 说明 |
|--------|-----------|------|------|
| `_llm_client` | `PromptDelegateMixin` | `LLMClient \| None` | LLM 客户端（延迟初始化） |

## 5. MRO（Method Resolution Order）

### 5.1 CarryMem 的 MRO 验证

```python
>>> import carrymem
>>> CarryMem = carrymem.CarryMem
>>> [c.__name__ for c in CarryMem.__mro__]
[
    'CarryMem',           # 0: Facade 自身
    'LifecycleMixin',    # 1 ← 首先解析，确保 __init__ 首先被调用
    'BackupMixin',        # 2
    'MemoryCRUDMixin',   # 3
    'ClassificationMixin',# 4
    'RecallMixin',        # 5
    'ProfileExportMixin', # 6
    'MaintenanceMixin',   # 7
    'PromptDelegateMixin',# 8
    'object',             # 9
]
```

### 5.2 关键设计决策

- **LifecycleMixin 在 MRO 最前面**（继承列表第一位）：确保 `__init__` 首先被调用，所有共享状态在其他 Mixin 方法执行前就绪。
- **MemoryCRUDMixin 在 ClassificationMixin 之后**：因为 `classify_and_remember()` 内部调用 ClassificationMixin 的私有方法。
- **PromptDelegateMixin 在 MRO 最后面**：不与其他 Mixin 有方法名冲突。

## 6. Protocol 接口体系 (`_protocols.py`)

### 6.1 设计原则

1. **每个 Mixin 一个 Protocol** — 1:1 映射，便于追踪
2. **公共方法 + 关键私有方法** — 私有方法如果构成跨 Mixin 契约也纳入
3. **Composite Protocol** — `CarryMemOps` 组合所有子 Protocol
4. **纯结构性类型** — 零运行时开销，无 isinstance() 检查；`type: ignore` 注解避免运行时冲突

### 6.2 Protocol 映射表

| Protocol 名 | 对应 Mixin | 方法数 | 用途 |
|------------|-----------|--------|------|
| `HasSharedState` | 无对应 Mixin，共享状态基础契约 | 5 (属性) | 共享状态基础契约 |
| `LifecycleOps` | LifecycleMixin | ~12 | 生命周期管理 |
| `BackupOps` | BackupMixin | ~9 | 备份与审计 |
| `RecallOps` | RecallMixin | ~7 | 检索操作 |
| `ClassificationOps` | ClassificationMixin | ~16 | 分类管道（含内部方法） |
| `MemoryCRUDOps` | MemoryCRUDMixin | ~10 | CRUD 操作 |
| `ProfileExportOps` | ProfileExportMixin | ~7 | 档案与导入导出 |
| `MaintenanceOps` | MaintenanceMixin | ~7 | 维护与质量 |
| `PromptDelegateOps` | PromptDelegateMixin | ~6 | 提示词与 LLM |
| **`CarryMemOps`** | **全部组合** | **~74** | **完整 Facade 契约** |

## 7. 新增 Mixin 指南

### 7.1 步骤清单

1. **创建文件** `src/carrymem/core/_your_feature.py`
2. **定义 Mixin 类** 继承自无基类（纯 Mixin）
3. **定义对应 Protocol** 在 `_protocols.py` 中添加 `YourFeatureOps(Protocol)`
4. **注册到 Facade** 在 `__init__.py` 中：
   - 导入新 Mixin 和新 Protocol
   - 将新 Mixin 加入 `CarryMem` 的继承列表
   - 添加 Protocol 断言 `_: YourFeatureOps = CarryMem`
   - 更新 `__all__`
5. **更新本文档** 更新依赖图和 MRO 表
6. **编写测试** 在 `tests/test_core_protocols.py` 中添加验证

### 7.2 注意事项

⚠️ **不要做的事**：
- 不要在 Mixin 中重新定义 `__init__`（除非你清楚 MRO 影响）
- 不要在多个 Mixin 中定义同名公共方法（会导致 MRO 冲突）
- 不要直接访问其他 Mixin 的私有属性（应通过 Protocol 或公共方法）
- 不要引入循环依赖（参考 DAG 图）

✅ **推荐做法**：
- 只通过 `self.xxx()` 调用其他 Mixin 的公共/约定方法
- 共享状态统一在 LifecycleMixin 中声明和初始化
- 新 Mixin 放在 MRO 列表靠前位置（继承列表靠后），避免覆盖已有方法
- 所有新方法必须有对应的 Protocol 定义

## 8. 已知耦合点 & 改进方向

| 编号 | 耦合描述 | 当前方案 | 未来改进 |
|------|---------|---------|---------|
| C-01 | ClassificationMixin 直接访问 `self._adapter` 写入数据 | 通过共享状态 | 可考虑注入 Adapter 接口 |
| C-02 | MemoryCRUDMixin 调用 ClassificationMixin 的 4 个私有方法 | 跨 Mixin 私有方法调用 | 可提升为受保护方法或抽取独立 Service |
| C-03 | `_candidate_generator` 在 LifecycleMixin 中创建但被 ClassificationMixin 使用 | 通过共享状态 | 可考虑依赖注入 |
| C-04 | MaintenanceMixin 直接读取 `LifecycleMixin._consolidation_timer` 类属性 | 跨 Mixin 类属性访问 | 可封装为 property 或方法 |

## 9. 变更日志

| 日期 | 变更内容 | 作者 |
|------|---------|------|
| 2026-06-15 | v0.4.0: Removed @runtime_checkable, merged StorageAdapterProtocol, added health_check MCP tool | v0.4.0 更新 |
| 2026-06-11 | 初始版本 — P0-1 Mixin 耦合治理完成；新增 `_protocols.py`、更新 `__init__.py`、本文档、测试 | P0-1 任务 |
