# ADR-009: 异步管道

## 状态: 部分修订（2026-09-07）— `native_async=True` 模式已移除，方案 A（线程池包装）成为唯一路径
## 日期: 2026-07-11 (v0.7.2)
## 决策者: CarryMem 核心团队

> **2026-09-07 修订**：双模式中的 `native_async=True`（AsyncSQLiteAdapter 支持）在真实使用中不可用——
> `AsyncCarryMem` 的 20 个公开方法中有 16 个在该模式下无条件抛出 `RuntimeError`，属于无法兑现的承诺。
> 已删除该模式（含 `connect`/`store_entry`/`recall_async`/`count_async` 4 个半残方法），保留方案 A 的
> 线程池包装作为唯一异步 API。`AsyncSQLiteAdapter` 类保留，可独立使用（`encryption_key` 改为
> fail-closed：传入即抛 `NotImplementedError`）。本文件其余内容作为历史决策记录保留。

## 当前决策（v0.11.0）

`AsyncCarryMem` 只提供 executor-backed async facade，构造函数不再接受 `native_async`，也不再暴露该模式下的半成品方法。需要原生异步 SQLite I/O 时，直接使用独立的 `AsyncSQLiteAdapter`；它不是 `StorageAdapter` 子类，且暂不支持加密参数，传入 `encryption_key` 会 fail-closed。

迁移规则：

- 旧的 `AsyncCarryMem(..., native_async=True)` 调用改为 `AsyncCarryMem(...)`，继续使用现有 facade 方法。
- 需要 `connect()`、`store_entry()`、`recall()`、`count()` 等原生异步适配器能力时，改为直接创建并管理 `AsyncSQLiteAdapter`。
- 安装原生异步适配器所需依赖：`pip install carrymem[async]`。

以下章节保留 v0.7.2 的历史决策，不能视为 v0.11.0 当前 API 契约。

---

CarryMem v0.7.1 及之前的所有 I/O 都是**同步阻塞**的——基于 `sqlite3` 标准库。这在单用户/低并发场景下表现良好，但在以下场景成为瓶颈：
1. **高并发 MCP 服务**：MCP HTTP server 同时处理多个 agent 请求，同步 SQLite 会让事件循环阻塞，并发吞吐受限。
2. **异步框架集成**：上层应用基于 FastAPI / aiohttp 等异步框架，调用同步 CarryMem 需要包一层 `run_in_executor`，增加心智负担。
3. **长尾查询**：召回（尤其多模式 + 图遍历）耗时较长，同步调用会拖慢整个请求链路。

需要提供**原生异步 I/O** 能力，同时不破坏零依赖的核心定位。

## 历史决策（v0.7.2，仅供追溯）

以下内容描述的是 v0.7.2 的双模式方案；它已被 v0.11.0 的当前决策取代，不是现行 API 契约。

### 历史候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 仅 run_in_executor 包装** | `AsyncCarryMem` 把同步方法丢进线程池 | 零新依赖；改动最小 | 线程池有上限；高并发下线程切换开销大；并未真正异步 |
| **B: 原生 async + 可选 aiosqlite** | 历史双模式：默认线程池包装；曾以 `native_async=True` 启用 `AsyncSQLiteAdapter` | 原生异步 I/O；按需启用 | 增加复杂度；高层 facade 能力不完整，最终在 v0.11.0 移除 |
| **C: 全量异步重写** | 所有适配器改为 async | 一致性最好 | 破坏既有同步 API；影响全部用户；工作量过大 |

### 历史决策与组件

**历史决策（已被 v0.11.0 取代）**：曾采用方案 B 的双模式异步管道——线程池包装（默认）+ 原生 aiosqlite（可选）。

核心组件：

- **`AsyncCarryMem`**（历史双模式设计，已由 v0.11.0 当前决策取代）：
  - **模式 1（历史默认）**：包装同步 `CarryMem`，用 `asyncio.run_in_executor` 调度，零额外依赖。
  - **模式 2（历史 `native_async=True`）**：曾使用 `AsyncSQLiteAdapter` 进行真正的异步 I/O；该构造参数和对应半成品方法已在 v0.11.0 删除。
- **`AsyncSQLiteAdapter`**：基于 `aiosqlite`，复用 `SQLiteAdapter` 的 SQL 与 schema 字符串（含 FTS5 触发器），但连接模型不同（`aiosqlite.Connection` vs `sqlite3.Connection`）。**不是** `StorageAdapter` 的子类。
- **可选依赖**：`pip install carrymem[async]` 安装 `aiosqlite>=0.19`；未安装时 `import aiosqlite` 优雅失败并提示安装命令。
- **`_require_sync()` 辅助方法**：满足 mypy 对 `Optional[CarryMem]` 的类型检查，同时保留运行时安全。

## 后果

### 正面
- **历史正面评估**：v0.7.2 曾预计 `native_async` 模式可在单事件循环中处理大量并发 I/O；该模式后来因公开方法不完整而移除。
- **历史渐进式采用评估**：v0.7.2 曾预计默认线程池模式零破坏、按需启用 `native_async`；v0.11.0 改为显式区分 `AsyncCarryMem` 与 standalone `AsyncSQLiteAdapter`。
- **零依赖核心不变**：aiosqlite 是可选 extra，核心包仍可零依赖安装运行。
- **FTS5 触发器复用**：`AsyncSQLiteAdapter` 复用 `_SCHEMA_SQL` 的 `memories_ai`/`memories_ad`/`memories_au` 触发器，无需在 `store_entry` 中手动维护 FTS。

### 负面
- **历史负面评估**：双实现维护和能力子集曾是 v0.7.2 方案的已知代价；v0.11.0 将 native async 能力从高层 facade 中移除，改由 standalone adapter 提供。
- **历史缓解措施**：v0.7.2 曾依赖同步/异步 schema 复用、运行时模式检查和 ImportError 提示；这些措施不构成 v0.11.0 的 `AsyncCarryMem` API 契约。

## 实现参考 (Implementation References)

- `src/carrymem/async_carrymem.py`: v0.11.0 executor-backed `AsyncCarryMem`; historical native mode references above are retained only for traceability
- `src/carrymem/adapters/async_sqlite.py`: `AsyncSQLiteAdapter`——基于 aiosqlite 的原生异步适配器（L38），复用 `SQLiteAdapter` SQL 与 FTS5 触发器
- `setup.py`: `[async]` extra 声明 `aiosqlite>=0.19`
- `CHANGELOG.md`: v0.7.2 "Native Async I/O" 章节
