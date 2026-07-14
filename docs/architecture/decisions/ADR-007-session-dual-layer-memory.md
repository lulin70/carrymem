# ADR-007: Session 双层记忆

## 状态: 已采纳
## 日期: 2026-07-11 (v0.7.0)
## 决策者: CarryMem 核心团队

---

## 上下文

AI 助手与用户的多轮对话存在两类截然不同的记忆需求：

1. **临时会话记忆**：当前对话刚刚提到的内容（"我刚才说的那个文件名"），需要**极低延迟**的 O(1) 召回，且仅在本会话内有意义。
2. **持久记忆**：跨会话的用户偏好、事实、决策，必须可靠持久化到磁盘，不能因会话结束而丢失。

CarryMem v0.6.x 只有单一持久层——所有召回都走 SQLite 查询。这导致：

- **会话内召回偏慢**：即便只查最近几条记忆，也要执行完整 SQL + FTS 流程。
- **临时记忆与持久记忆混淆**：会话内的瞬时上下文被无差别持久化，污染长期记忆库。
- **无法区分生命周期**：缺少"会话结束后清理临时记忆"的机制。

需要在持久层之上引入**会话缓存层**，并支持临时记忆向持久记忆的升级。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 单层 + TTL 过期** | 所有记忆写入持久层，靠 expires_at 自动过期 | 实现简单；无需新层 | 过期前仍占查询资源；无法做到 O(1) 召回 |
| **B: Session 缓存层 + 持久层** ✅ | 进程内 LRU 缓存当前会话记忆，持久层不变；提供 `promote_to_permanent()` 升级接口 | 临时记忆 O(1) 命中；持久记忆不受污染；升级路径清晰 | 多了一层状态需维护；进程重启丢失会话缓存 |
| **C: Redis 外部缓存** | 用 Redis 做会话层 | 跨进程共享；可水平扩展 | 引入 Redis 依赖；破坏单文件部署；延迟增加 |

## 决策

**采用方案 B：Session 缓存层 + 持久层的双层记忆架构。**

核心设计：

- **RecallCache 会话扩展**：每个 `session_id` 维护独立 LRU 缓存（默认 `session_max_size=128`），支持大小写不敏感的 `content` + `raw_text` 子串匹配检索。
- **会话生命周期 API**：
  - `set_session(session_id)`：开启会话，激活缓存层。
  - `preload_session(limit=50)`：将近期高重要性记忆预加载进缓存，实现 O(1) 命中。
  - `end_session()`：结束会话，清理缓存。
- **升级机制**：`promote_to_permanent(memory_key)` 将临时记忆升级为持久记忆——提升 `importance_score +0.05`（上限 1.0）并 `access_count +1`；通过 `cursor.rowcount > 0` 校验记忆确实存在。
- **缓存统计**：`RecallCache.stats` 新增 `session_count`、`session_hits`、`session_misses`、`session_hit_rate`，便于观测缓存效果。

## 后果

### 正面
- **O(1) 会话内召回**：预加载后，当前对话上下文命中内存缓存，无需走 SQL/FTS。
- **持久记忆不丢失**：持久层逻辑完全不变，会话缓存是纯加速层，崩溃/重启后持久记忆无损。
- **生命周期清晰**：临时记忆随会话结束自动清理，不污染长期记忆库。
- **可控升级**：`promote_to_permanent()` 提供显式的"临时→持久"通道，避免无差别持久化。

### 负面
- **进程内状态**：会话缓存位于进程内存，进程重启或水平扩展时缓存失效（但持久层仍安全）。
- **缓存一致性**：会话内写入的记忆需同时更新缓存与持久层，存在双写一致性维护成本。
- **内存占用**：每个活跃会话占用一定内存（默认 128 条），高并发会话数场景需评估上限。

### 缓解措施
- 缓存仅作为加速层，所有数据以持久层为权威来源；缓存未命中时回退到持久层查询。
- LRU 上限可配置（`session_max_size`），防止内存无限增长。
- `promote_to_permanent()` 通过 rowcount 校验，避免对不存在记忆的误升级。

## 实现参考 (Implementation References)

- `src/carrymem/cache.py`: RecallCache 会话扩展——`session_preload()`（L164）、`session_search()`（L189）、`session_put()`（L229）、`invalidate_session()`（L250）
- `src/carrymem/core/_recall.py`: RecallMixin 会话 API——`set_session()`（L343）、`end_session()`（L358）、`preload_session()`（L370）、`promote_to_permanent()`（L406）
- `src/carrymem/core/_protocols.py`: `RecallOps` Protocol 会话方法签名（L281-293）
- `CHANGELOG.md`: v0.7.0 "Session Dual-Layer Memory" 章节
