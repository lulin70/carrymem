# ADR-009: 异步管道

## 状态: 部分修订（2026-09-07）— `native_async=True` 模式已移除，方案 A（线程池包装）成为唯一路径
## 日期: 2026-07-11 (v0.7.2)
## 决策者: CarryMem 核心团队

> **2026-09-07 修订**：双模式中的 `native_async=True`（AsyncSQLiteAdapter 支持）在真实使用中不可用——
> `AsyncCarryMem` 的 20 个公开方法中有 16 个在该模式下无条件抛出 `RuntimeError`，属于无法兑现的承诺。
> 已删除该模式（含 `connect`/`store_entry`/`recall_async`/`count_async` 4 个半残方法），保留方案 A 的
> 线程池包装作为唯一异步 API。`AsyncSQLiteAdapter` 类保留，可独立使用（`encryption_key` 改为
> fail-closed：传入即抛 `NotImplementedError`）。本文件其余内容作为历史决策记录保留。

---

## 上下文

CarryMem v0.7.1 及之前的所有 I/O 都是**同步阻塞**的——基于 `sqlite3` 标准库。这在单用户/低并发场景下表现良好，但在以下场景成为瓶颈：

1. **高并发 MCP 服务**：MCP HTTP server 同时处理多个 agent 请求，同步 SQLite 会让事件循环阻塞，并发吞吐受限。
2. **异步框架集成**：上层应用基于 FastAPI / aiohttp 等异步框架，调用同步 CarryMem 需要包一层 `run_in_executor`，增加心智负担。
3. **长尾查询**：召回（尤其多模式 + 图遍历）耗时较长，同步调用会拖慢整个请求链路。

需要提供**原生异步 I/O** 能力，同时不破坏零依赖的核心定位。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 仅 run_in_executor 包装** | `AsyncCarryMem` 把同步方法丢进线程池 | 零新依赖；改动最小 | 线程池有上限；高并发下线程切换开销大；并未真正异步 |
| **B: 原生 async + 可选 aiosqlite** ✅ | 双模式：默认线程池包装；`native_async=True` 时用 `AsyncSQLiteAdapter`（aiosqlite） | 真正异步 I/O；按需启用；零依赖核心不变 | 增加 async/await 复杂度；aiosqlite 为可选依赖 |
| **C: 全量异步重写** | 所有适配器改为 async | 一致性最好 | 破坏既有同步 API；影响全部用户；工作量过大 |

## 决策

**采用方案 B：双模式异步管道——线程池包装（默认）+ 原生 aiosqlite（可选）。**

核心组件：

- **`AsyncCarryMem`**（双模式）：
  - **模式 1（默认）**：包装同步 `CarryMem`，用 `asyncio.run_in_executor` 调度，零额外依赖。
  - **模式 2（`native_async=True`）**：使用 `AsyncSQLiteAdapter` 进行真正的异步 I/O，新增 `connect()`、`store_entry()`、`recall_async()`、`count_async()` 方法；同步方法在此模式下抛 `RuntimeError`（反之亦然）。
- **`AsyncSQLiteAdapter`**：基于 `aiosqlite`，复用 `SQLiteAdapter` 的 SQL 与 schema 字符串（含 FTS5 触发器），但连接模型不同（`aiosqlite.Connection` vs `sqlite3.Connection`）。**不是** `StorageAdapter` 的子类。
- **可选依赖**：`pip install carrymem[async]` 安装 `aiosqlite>=0.19`；未安装时 `import aiosqlite` 优雅失败并提示安装命令。
- **`_require_sync()` 辅助方法**：满足 mypy 对 `Optional[CarryMem]` 的类型检查，同时保留运行时安全。

## 后果

### 正面
- **高并发性能提升**：`native_async` 模式下，单事件循环可处理大量并发 I/O，无需线程切换。
- **渐进式采用**：默认线程池模式零破坏，已有用户无感；需要性能时再启用 `native_async`。
- **零依赖核心不变**：aiosqlite 是可选 extra，核心包仍可零依赖安装运行。
- **FTS5 触发器复用**：`AsyncSQLiteAdapter` 复用 `_SCHEMA_SQL` 的 `memories_ai`/`memories_ad`/`memories_au` 触发器，无需在 `store_entry` 中手动维护 FTS。

### 负面
- **async/await 复杂度**：异步代码传染性——一旦启用 `native_async`，上层调用链必须全程 async。
- **双实现维护**：同步 `SQLiteAdapter` 与 `AsyncSQLiteAdapter` 共享 SQL 但各有连接管理逻辑，需同步演进。
- **能力子集**：`AsyncSQLiteAdapter` 仅实现核心方法（`store_entry`/`recall`/`forget_memory`/`count`/`close`），尚未覆盖全部图/会话 API。

### 缓解措施
- 同步与异步适配器共享 schema SQL 字符串，减少 SQL 漂移风险。
- `native_async` 模式下同步方法显式抛 `RuntimeError`，避免误用导致隐蔽 bug。
- ImportError 时给出明确的安装提示（`pip install carrymem[async]`）。

## 实现参考 (Implementation References)

- `src/carrymem/async_carrymem.py`: `AsyncCarryMem` 双模式封装——默认线程池模式 + `native_async` 模式（`_require_sync()` L66、`connect()` L72、`store_entry()` L77）
- `src/carrymem/adapters/async_sqlite.py`: `AsyncSQLiteAdapter`——基于 aiosqlite 的原生异步适配器（L38），复用 `SQLiteAdapter` SQL 与 FTS5 触发器
- `setup.py`: `[async]` extra 声明 `aiosqlite>=0.19`
- `CHANGELOG.md`: v0.7.2 "Native Async I/O" 章节
