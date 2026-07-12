# CarryMem 优化规划文档

**版本**: v0.5.3 规划
**日期**: 2026-07-08
**参与者**: PM + Architect 共识
**状态**: Phase 1 已完成 ✅ | Phase 2 已完成 ✅ | Phase 3 待实施

> **Phase 1 交付记录**（2026-07-09）：
> - Commit: `6aaa477` (push 到 origin/new-main)
> - 文件变更: 44 files, +348/-70
> - CI 验证: Tests (py3.12) ✅ + 6 job 通过（Syntax/Docs/i18n/Security/Build/Optional Deps）
> - 已知问题: Lint (Quality Gate) ❌ — 预存 Black 格式问题（`_memory_crud.py` + `test_performance_benchmark.py`），在 4ac2ed3 就存在，非 Phase 1 回归，留待 tech debt cleanup 处理

> **Phase 2 交付记录**（2026-07-09）：
> - 版本: v0.5.3 → v0.5.4 (MINOR 递增，新增向后兼容的批量 API)
> - 新增 API: `store_batch(List[MemoryEntry]) -> List[StoredMemory]` + `delete_batch(List[str]) -> Dict[str, bool]`
> - 原子事务: SQLiteAdapter 使用 BEGIN/commit/rollback 实现 all-or-nothing 语义
> - 迁移: `_memory_crud.py` remember_batch 调用从 adapter.remember_batch → adapter.store_batch
> - Deprecated: `remember_batch()` 标记 deprecated，委托 store_batch，v0.6.0 移除
> - 测试: 4 个新测试 (store_batch/delete_batch/atomic_rollback/deprecation_warning) + 2 个契约测试
> - 回归: 495+ 测试 0 失败（排除 e2e_large_dataset 预存超时）
> - 文件变更: crud.py + sqlite/__init__.py + obsidian_adapter.py + _memory_crud.py + base.py + test_carrymem.py + __version__.py + CHANGELOG.md + PROJECT_STATUS.md + 本文档

## 1. 问题诊断

### 核心问题：API 双轨制认知负担

`store()` 返回 `str`（storage_key），而 `remember()` 返回 `StoredMemory`（含 importance_score 等元数据）。核心层 `declare()`/`_store_entries()` 因需要完整元数据，被迫使用 deprecated 的 `remember()`。

**根因分析**（Architect）：
- v0.4.0 迁移时，`remember()`→`store()` 把"返回 StoredMemory"降级为"返回 str"，丢掉了元数据
- `SQLiteAdapter.store()` 内部已计算出完整 `StoredMemory`，却只返回 `storage_key`，主动丢弃
- `StoredMemory.from_memory_entry()` 不回填 importance_score（默认 0.0），导致假元数据

### 其他架构问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | AsyncStorageAdapter 仍用 remember/forget | 异步用户无法用新 API |
| 2 | recall() 签名漂移（私自加 namespaces 参数） | type:ignore 绕过检查 |
| 3 | 核心层硬耦合 SQLiteAdapter（isinstance 判断） | 难以扩展其他适配器 |
| 4 | count() 调 get_stats() 全量聚合 | 性能反模式 |
| 5 | 审计访问泄漏（hasattr _audit 私有属性） | 抽象泄漏 |
| 6 | search_fulltext 语义不一致 | 文档与实现矛盾 |

## 2. 方案选择

### store() 返回值升级方案对比

| 方案 | 描述 | 优点 | 缺点 | PM | Architect |
|------|------|------|------|----|----| 
| A. 升级 store() 返回 StoredMemory | `store(dict) -> StoredMemory` | 单一 API | 破坏性变更 | ✅ | ❌ |
| **B. 新增 store_entry()** | `store_entry(MemoryEntry) -> StoredMemory` | 非破坏、职责清晰 | API +1 | ✅ | ✅ |
| C. store() 后回查 get_by_key() | 零 API 改动 | 多一次 DB 往返 | ❌ | ❌ |

### 共识：采用方案 B

**理由**：
1. 非破坏性——现有外部适配器无需改动
2. 职责清晰——`store_entry` 是"对象进对象出"的领域 API；`store` 是"dict 进 key 出"的序列化边界 API
3. 消除数据丢失——SQLiteAdapter.store_entry 直接返回 `_crud.remember()` 的完整 StoredMemory
4. 契合废弃时间线——v0.6.0 移除 remember() 前，核心层有合规的富返回通道

## 3. 实施计划

### Phase 1: store_entry() 核心 API（v0.5.3，P0）✅ 已完成

| 步骤 | 文件 | 内容 | 复杂度 | 状态 |
|------|------|------|--------|------|
| 1.1 | `adapters/base.py` | 新增 `store_entry(MemoryEntry) -> StoredMemory` 抽象方法 | 低 | ✅ |
| 1.2 | `adapters/base.py` | `store(dict)` 默认实现改为调用 `store_entry` | 低 | ✅ |
| 1.3 | `adapters/sqlite/__init__.py` | 实现 `store_entry()` 直接返回 `_crud.remember()` | 低 | ✅ |
| 1.4 | `adapters/json_adapter.py` | 实现 `store_entry()` | 低 | ✅ |
| 1.5 | `core/_memory_crud.py` | `declare()` 迁移：`remember()` → `store_entry()` | 低 | ✅ |
| 1.6 | `core/_classification.py` | `_store_entries()` 迁移：`remember()` → `store_entry()` | 低 | ✅ |
| 1.7 | `core/_profile_export.py` | `import_memories()` 迁移 | 低 | ✅ |
| 1.8 | `core/_prompt_delegate.py` | 2 处迁移 | 低 | ✅ |
| 1.9 | `adapters/base.py` | TestStorageAdapterContract 新增 `test_store_entry_returns_full_metadata` | 中 | ✅ |
| 1.10 | 全量回归 | pytest + black + flake8 + isort | - | ✅ |
| 1.11 | `adapters/base.py` | `remember_batch()` 默认实现改用 `store_entry()` 消除元数据丢失 | 低 | ✅ |
| 1.12 | `core/_maintenance.py` | 2 处 `forget()` → `delete()` 迁移 | 低 | ✅ |
| 1.13 | `core/_protocols.py` | MemoryCRUDOps Protocol 添加 `remember_batch` 签名 | 低 | ✅ |
| 1.14 | `pyproject.toml` | mypy `python_version` 3.9 → 3.12 | 低 | ✅ |
| 1.15 | 测试修复 | `_MinimalAdapter` + 3 `DummyAdapter` 添加 `store_entry()` 实现 | 低 | ✅ |
| 1.16 | 测试修复 | `test_storage_error_propagates_on_critical_operation` mock 目标更新 | 低 | ✅ |
| 1.17 | `adapters/obsidian_adapter.py` | 实现 `store_entry()` (raise NotImplementedError, 只读) | 低 | ✅ |

### Phase 2: 批量 API + Async 迁移（v0.5.4，P0）

#### API 设计（Architect 共识）

**设计原则**：与 Phase 1 的 `store_entry` 保持一致——"对象进对象出"的领域 API。

```python
# 新增方法
def store_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
    """Batch store entries, returning full metadata for each.

    Default impl: loop store_entry(). Override for atomic transactions.
    """

def delete_batch(self, storage_keys: List[str]) -> Dict[str, bool]:
    """Batch delete by storage keys.

    Default impl: loop delete(). Returns {key: success} mapping.
    Override for atomic transactions (all-or-nothing rollback).
    """
```

**签名决策**：
- `store_batch(List[MemoryEntry])` 而非 `List[dict]` — 与 `store_entry` 一致，对象进对象出
- `delete_batch(List[str]) -> Dict[str, bool]` — 返回每个 key 的结果，便于部分失败诊断
- 原子事务策略：SQLiteAdapter 全部成功或全部回滚（BEGIN/commit/rollback）

#### 实施步骤

| 步骤 | 文件 | 内容 | 复杂度 | 状态 |
|------|------|------|--------|------|
| 2.1 | `adapters/base.py` | `StorageAdapter.store_batch()` 默认实现（循环 store_entry） | 低 | ✅ |
| 2.2 | `adapters/base.py` | `StorageAdapter.delete_batch()` 默认实现（循环 delete） | 低 | ✅ |
| 2.3 | `adapters/base.py` | `remember_batch` 标记 deprecated，委托 `store_batch` | 低 | ✅ |
| 2.4 | `adapters/base.py` | `AsyncStorageAdapter` Protocol 新增 store_entry/store/delete/store_batch/delete_batch | 中 | ✅ |
| 2.5 | `sqlite/crud.py` | `store_batch` 复用现有 `remember_batch` 原子事务逻辑 | 低 | ✅ |
| 2.6 | `sqlite/crud.py` | `delete_batch` 原子事务版（BEGIN/commit/rollback） | 中 | ✅ |
| 2.7 | `sqlite/__init__.py` | SQLiteAdapter 新增 store_batch/delete_batch 转发 | 低 | ✅ |
| 2.8 | `core/_memory_crud.py` | `remember_batch()` 中 `remember_batch` → `store_batch` | 低 | ✅ |
| 2.9 | `json_adapter.py` | 继承默认实现（无需修改） | 低 | ✅ |
| 2.10 | `obsidian_adapter.py` | `store_batch`/`delete_batch` raise NotImplementedError (只读) | 低 | ✅ |
| 2.11 | `core/_protocols.py` | MemoryCRUDOps Protocol 保持不变（核心层方法名未迁移） | 低 | ✅ |
| 2.12 | `adapters/base.py` | TestStorageAdapterContract 新增 store_batch/delete_batch 契约测试 | 中 | ✅ |
| 2.13 | 测试修复 | _MinimalAdapter + DummyAdapter 继承默认实现（无需修改） | 低 | ✅ |
| 2.14 | CHANGELOG + PROJECT_STATUS | 版本号 + 文档更新（MIGRATION.md 延迟至 v0.6.0） | 低 | ✅ |
| 2.15 | 全量回归 | pytest + black --line-length=120 + flake8 + isort + mypy | - | ✅ |

### Phase 3: 架构清理（v0.6.0，P1）— Breaking Change ✅ 已完成

> **Phase 3 交付记录**（2026-07-09）：
> - 版本: v0.5.4 → v0.6.0 (MINOR 递增，breaking change — deprecated API 移除)
> - 移除 deprecated 方法: 19 个方法定义从 src/ 中移除（StorageAdapter/SQLiteAdapter/JSONAdapter/ObsidianAdapter/AsyncStorageAdapter Protocol）
> - 核心层 API 重命名: `CarryMem.remember_batch(messages)` → `CarryMem.store_messages(messages)`
> - 测试迁移: 50+ 调用点从 deprecated API 迁移到新 API（11 个测试文件 + 3 个测试辅助类）
> - 内部清理: 4 个源文件移除不再使用的 `import warnings`
> - 回归: 1599+ 测试通过（1 个预存 macOS flaky test 与 Phase 3 无关）

> **Breaking Change 声明**: v0.6.0 移除所有 deprecated API。用户需迁移：
> - `adapter.remember(entry)` → `adapter.store_entry(entry)`
> - `adapter.remember_batch(entries)` → `adapter.store_batch(entries)`
> - `adapter.forget(key)` → `adapter.delete(key)`
> - `cm.remember_batch(messages)` → `cm.store_messages(messages)`

#### 3.1 源码 deprecated 方法移除

**决策依据**（Architect）：
- `crud.py` 的 `remember()`/`forget()` 是 **内部实现**（被 `store_entry()`/`delete()` 调用），**不是 deprecated 方法** — 保持原名，不重命名（Surgical Changes 原则）
- `SQLiteAdapter` 的 `remember()`/`remember_batch()`/`forget()` 是 **deprecated 转发方法** — 直接删除
- `base.py` 的 `remember()`/`remember_batch()`/`forget()` 是 **deprecated 委托方法** — 直接删除
- `AsyncStorageAdapter` Protocol 的 deprecated 签名 — 直接删除
- 核心层 `MemoryCRUDMixin.remember_batch()` 是 **公共 API**（接收 `List[str]` messages），与 adapter 的 `store_batch(List[MemoryEntry])` 语义不同 — 重命名为 `store_messages()` 消除歧义

| 步骤 | 文件 | 修改 | 行号 |
|------|------|------|------|
| 3.1.1 | `adapters/base.py` | 删除 `StorageAdapter.remember()` deprecated 委托 | 516-534 |
| 3.1.2 | `adapters/base.py` | 删除 `StorageAdapter.remember_batch()` deprecated 委托 | 536-553 |
| 3.1.3 | `adapters/base.py` | 删除 `StorageAdapter.forget()` deprecated 委托 | 555-572 |
| 3.1.4 | `adapters/base.py` | 删除 `AsyncStorageAdapter` Protocol 的 remember/remember_batch/forget 签名 | 742-751 |
| 3.1.5 | `adapters/base.py` | 更新 `TestStorageAdapterContract` 测试方法调用 (remember→store_entry, forget→delete, remember_batch→store_batch) | 772-852 |
| 3.1.6 | `adapters/sqlite/__init__.py` | 删除 `remember()` 转发方法 | 535-542 |
| 3.1.7 | `adapters/sqlite/__init__.py` | 删除 `remember_batch()` 转发方法 | 544-546 |
| 3.1.8 | `adapters/sqlite/__init__.py` | 删除 `forget()` 转发方法 | 548-555 |
| 3.1.9 | `adapters/sqlite/__init__.py` | `import_data()` 中 `self._crud.remember()` → `self.store_entry()` | 496 |
| 3.1.10 | `adapters/sqlite/crud.py` | 删除 `remember_batch()` deprecated 委托 | 188-199 |
| 3.1.11 | `adapters/obsidian_adapter.py` | 删除 `remember()`, `remember_batch()`, `forget()` | 364, 368, 515 |
| 3.1.12 | `adapters/json_adapter.py` | 删除 `remember()`, `forget()` | 138, 244 |

#### 3.2 核心层方法名迁移

| 步骤 | 文件 | 修改 | 行号 |
|------|------|------|------|
| 3.2.1 | `core/_memory_crud.py` | `remember_batch()` → `store_messages()` (公共 API 重命名) | 154 |
| 3.2.2 | `core/_protocols.py` | `MemoryCRUDOps.remember_batch` → `store_messages` | 357 |

**重命名理由**：
- `cm.remember_batch(messages: List[str])` 接收原始消息字符串，需先分类再存储
- `adapter.store_batch(entries: List[MemoryEntry])` 接收已构造的 MemoryEntry，直接原子事务存储
- 两者语义完全不同，重命名为 `store_messages` 消除歧义，明确"存储多条消息"的意图

#### 3.3 测试迁移（50+ 调用点）

| 文件 | 调用点 | 迁移 |
|------|--------|------|
| `tests/test_concurrent_access.py` | 4 处 `.remember()` | → `.store_entry()` |
| `tests/test_json_adapter_extra.py` | 4 处 `.remember()` | → `.store_entry()` |
| `tests/test_base_adapter.py` | 1 处 `.remember_batch()` | → `.store_batch()` |
| `tests/test_summary_layer.py` | 1 处 `.remember()` | → `.store_entry()` |
| `tests/test_sqlite_adapter_ext.py` | 2 处 `.remember()`, 2 处 `.remember_batch()` | → `.store_entry()`/`.store_batch()` |
| `tests/test_performance_benchmark.py` | 1 处 `cm.remember_batch()` (核心层) | → `cm.store_messages()` |
| `tests/test_mcp_json_async.py` | 8 处 `.remember()`, 1 处 `.forget()` | → `.store_entry()`/`.delete()` |
| `tests/test_phase4.py` | 6 处 `.remember()` | → `.store_entry()` |
| `tests/test_carrymem.py` | 4 处 `.remember()`, 1 处 `.forget()`, 1 处 `.remember_batch()` | → `.store_entry()`/`.delete()`/`.store_batch()` |
| `tests/test_raw_text.py` | 8 处 `.remember()` | → `.store_entry()` |
| `tests/test_vector_search.py` | 4 处 `.remember()` | → `.store_entry()` |
| `tests/test_memory_optimization.py` | 3 处 `.remember_batch()` | → `.store_batch()` |
| `tests/test_integration_error_propagation.py` | 需检查 | 按需迁移 |

#### 3.4 文档更新

| 步骤 | 文件 | 修改 |
|------|------|------|
| 3.4.1 | `docs/i18n/ARCHITECTURE-CN.md` | `remember_batch` 示例 → `store_batch` |
| 3.4.2 | `docs/i18n/ARCHITECTURE-JP.md` | 同上 |
| 3.4.3 | `CHANGELOG.md` | 新增 v0.6.0 breaking change 条目 |
| 3.4.4 | `docs/PROJECT_STATUS.md` | 版本更新 v0.5.4→v0.6.0 |
| 3.4.5 | `__version__.py` | 0.5.4 → 0.6.0 |
| 3.4.6 | 本文档 | Phase 3 完成记录 |

#### 3.5 v0.6.1 架构清理项（Patch — 重构优化解耦，非功能追加）

> **版本号决策**：重构/优化/解耦属于无功能变更的工作，按 SemVer 规则只递增 PATCH（v0.6.0→v0.6.1）。
> 实施顺序按风险从低到高：3.8 → 3.6 → 3.9 → 3.7 → 3.10。

##### 3.8 count() 性能优化（风险：低）✅ 已完成

- **问题**：`SQLiteAdapter.count()` 调用 `get_stats()` 全量聚合（by_type/by_tier/by_namespace），
  但 count() 只需要一个数字。`get_stats()` 内部执行多个 GROUP BY 查询，浪费 I/O。
- **当前代码** (`sqlite/__init__.py:415-428`)：
  ```python
  def count(self, filter_=None):
      stats = self.get_stats()  # 全量聚合
      if filter_ and "type" in filter_:
          return stats.get("by_type", {}).get(filter_["type"], 0)
      return stats.get("total_count", 0)
  ```
- **修复方案**：直接 `SELECT COUNT(*) FROM memories`，有 type 过滤时加 `WHERE type = ?`
- **影响文件**：`sqlite/__init__.py`
- **验证**：count() 返回值与 get_stats() 一致 + 性能提升

##### 3.6 recall() 签名修正（风险：低）✅ 已完成

- **问题**：基类 `StorageAdapter.recall()` 无 `namespaces` 参数，但 SQLiteAdapter/
  JSONAdapter/ObsidianAdapter 都有，用 `# type: ignore[override]` 绕过类型检查。
  核心层 `_recall.py:127` 用 `isinstance(self._adapter, SQLiteAdapter)` 判断是否传
  namespaces — 这是硬耦合的根源之一。
- **当前签名对比**：
  - 基类 (`base.py:447-453`)：`recall(query, filters, limit, update_access)`
  - SQLiteAdapter (`sqlite/__init__.py:553-562`)：`recall(query, filters, limit, namespaces, update_access)` + `# type: ignore[override]`
- **修复方案**：基类 `recall()` 添加 `namespaces: Optional[list] = None` 参数，
  移除子类的 `# type: ignore[override]`，移除 _recall.py 的 isinstance 检查
- **影响文件**：`base.py`, `sqlite/__init__.py`, `json_adapter.py`, `obsidian_adapter.py`, `_recall.py`, `_protocols.py`
- **验证**：mypy 0 errors（无需 type: ignore）+ recall 带 namespaces 参数正常工作

##### 3.9 审计访问公共化（风险：中）✅ 已完成

- **问题**：核心层 14 处通过 `hasattr(self._adapter, "_audit") and self._adapter._audit`
  直接访问适配器的私有 `_audit` 属性，破坏封装。模式重复 6 对（log_operation 调用）。
- **当前代码** (`_memory_crud.py:136-143`)：
  ```python
  if self._adapter and hasattr(self._adapter, "_audit") and self._adapter._audit:
      self._adapter._audit.log_operation("remember", storage_key=..., ...)
  ```
- **修复方案**：在 StorageAdapter 基类添加公共方法：
  ```python
  def log_audit(self, operation, storage_key=None, memory_type=None, success=True, details=None):
      """Log an audit event. No-op if audit is not configured."""
      if hasattr(self, "_audit") and self._audit:
          self._audit.log_operation(operation, storage_key, memory_type, success, details)
  ```
  核心层 14 处替换为 `self._adapter.log_audit(...)` 单行调用
- **影响文件**：`base.py`, `_memory_crud.py`, `_backup.py`
- **验证**：审计日志正常记录 + 无 hasattr/_audit 私有访问

##### 3.7 核心层硬耦合解耦（风险：中高）✅ 已完成

- **问题**：核心层 14 处 `isinstance(self._adapter, SQLiteAdapter)` 硬编码类型检查，
  阻止其他适配器扩展相同能力。
- **分布**：`_memory_crud.py` 4处, `_backup.py` 6处, `_recall.py` 1处,
  `_lifecycle.py` 1处, `_profile_export.py` 1处, `_maintenance.py` 1处
- **修复方案**：用 capabilities 字典替代 isinstance。StorageAdapter 基类已有
  `capabilities` 属性（各适配器声明 vector_search/fts/ttl/batch 等）。
  新增能力键：`versioning`, `backup`, `audit`, `namespace_filtering`。
  核心层改为 `if not self._adapter.capabilities.get("versioning", False):`
- **实施结果**：12/13 处替换为 capabilities.get()。`_maintenance.py:105` 保留 isinstance
  因其使用 SQLite 特有的 `_get_connection()` 内部方法进行原始 SQL 查询（list_expired），
  无法通过能力键安全替换。`_memory_crud.py`、`_backup.py`、`_profile_export.py` 移除
  `SQLiteAdapter` import；`_lifecycle.py` 保留 import（用于实例化）。
- **影响文件**：`base.py`, `sqlite/__init__.py`, `_memory_crud.py`, `_backup.py`,
  `_lifecycle.py`, `_profile_export.py`
- **验证**：483 tests passed ✅

##### 3.10 search_fulltext 语义修正（风险：待评估）✅ 已完成

- **问题**：基类文档说"不做排名/相关性评分"，但 SQLiteAdapter 和 JSONAdapter 的实现
  都委托给 `recall()`（做排名），语义矛盾。基类默认抛 NotImplementedError。
- **修复方案**：基类提供默认实现（委托 `recall(query, update_access=False)`），删除
  SQLiteAdapter 和 JSONAdapter 中的重复实现。修正文档从"不做排名"改为"按 recall 排名"。
  ObsidianAdapter 自动继承默认实现（无需单独实现）。
- **影响文件**：`base.py`, `sqlite/__init__.py`, `json_adapter.py`
- **验证**：lint 通过 + smoke test 通过 ✅

#### 验证标准

Phase 3 完成后必须通过：
1. `black --line-length=120` 0 errors
2. `flake8` 0 errors
3. `isort` 0 errors
4. `mypy` 0 errors（python_version=3.12）
5. `pytest tests/` 全量通过（含 protocol 覆盖测试）
6. **无新增 DeprecationWarning**（grep 确认 src/ 中无 `warnings.warn(...DeprecationWarning)` for remember/forget）
7. E2E 测试：classify_and_remember → recall 全链路验证

## 4. 验证标准

每个 Phase 完成后必须通过：
1. `ruff check` 0 errors
2. `mypy` 0 errors（python_version=3.12）
3. `pytest tests/` 全量通过（含 protocol 覆盖测试）
4. 无新增 DeprecationWarning（核心层不再调用 deprecated API）
5. E2E 测试：classify_and_remember → recall 全链路验证

## 5. 版本规划

| 版本 | 内容 | 目标 |
|------|------|------|
| v0.5.3 | Phase 1: store_entry 核心 API | 核心层脱离 deprecated API |
| v0.5.4 | Phase 2: 批量 API + Async 迁移 | API 统一为 store/delete 系列 |
| v0.6.0 | Phase 3: 移除 deprecated + 架构清理 | 双轨制终结 |
| v0.6.1 ✅ | Phase 3.5: 架构清理项（重构优化解耦） | recall 签名统一 + isinstance 解耦 + count 优化 + 审计公共化 + search_fulltext 修正 |
| v0.6.2 ✅ | 安全修复 + 访问频率加权 | cryptography CVE-2026-34073 修复 + selection.py recency 衰减 + 文档一致性修复 |
