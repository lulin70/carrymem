# Phase 1-3 代码走读报告（7维度）

> 日期：2026-05-13
> 范围：Phase 1（会话感知+知识失效）、Phase 2（时间推理+上下文重建）、Phase 3（注入质量优化）

## 改动文件清单

| 文件 | 改动概要 |
|------|---------|
| `adapters/base.py` | StoredMemory 增加 superseded_at/supersedes 字段 |
| `adapters/sqlite_adapter.py` | Schema v080 迁移、auto_supersede、recall_aggregated、recall_timeline、时间表达式解析、上下文重建、过滤增强 |
| `carrymem.py` | session_id 参数、recall_aggregated/timeline API、build_context 安全访问 |
| `context.py` | MANDATORY/OUTDATED 标签、结构化分区、知识更新记录 |
| `__init__.py` | TRANSFORMERS_OFFLINE + HF_HUB_OFFLINE |
| `pyproject.toml` | asyncio marker + asyncio_mode |

## 7维度走读结果

### 1. 功能正确性 ✅

| 问题 | 严重度 | 状态 |
|------|--------|------|
| auto-supersede 在 INSERT 前执行 | 🔴 | ✅ 已修复：移到 INSERT 后 |
| recall_timeline 多词要求精确顺序 | 🟡 | ✅ 已修复：OR 分开匹配 |
| `_is_contradictory` 子串误匹配 | 🟡 | ✅ 已修复：加词边界 `\b` |
| `_UPDATE_MARKERS` "now" 子串误触发 | 🟡 | ✅ 已修复：加空格边界 |
| `format_memory_entry` conf 变量未定义 | 🔴 | ✅ 已修复：改为 `m.get("confidence", 0)` |

### 2. 安全性 ✅

| 问题 | 严重度 | 状态 |
|------|--------|------|
| session_id 过滤 SQL 通配符注入 | 🔴 | ✅ 已修复：转义 `%` 和 `_` |

### 3. 性能 ⚠️

| 问题 | 严重度 | 状态 |
|------|--------|------|
| recall_aggregated 多次 SQL 查询 | 🟡 | 记录，Phase 5 优化 |
| auto_supersede 每次查 20 条 | 🟡 | 记录，Phase 5 优化 |
| build_context 额外 recall 调用 | 🟡 | 可接受 |

### 4. 可维护性 ⚠️

| 问题 | 严重度 | 状态 |
|------|--------|------|
| 矛盾对/更新标记/时间表达式硬编码 | 🟡 | 后续提取配置 |
| recall_aggregated/timeline 加锁 | 🟡 | ✅ 已修复 |

### 5. 可测试性 ⚠️

| 问题 | 严重度 | 状态 |
|------|--------|------|
| 新功能缺单元测试 | 🟡 | 后续补 |

### 6. 兼容性 ✅

| 问题 | 严重度 | 状态 |
|------|--------|------|
| build_context 安全访问 _knowledge_adapter/_rule_engine | 🟡 | ✅ 已修复 |

### 7. 可观测性 ✅

| 问题 | 严重度 | 状态 |
|------|--------|------|
| auto-supersede 只有 debug 日志 | 🟢 | 可接受 |

## 端到端验证

25/25 全部通过，覆盖：
- Phase 1.1: session_id 存储/过滤
- Phase 1.2: auto-supersede / include_superseded
- Phase 1.3: recall_aggregated
- Phase 1.4: recall_timeline
- Phase 2.1: 时间表达式解析（recently/first/3 months ago）
- Phase 2.2: created_after/created_before 过滤
- Phase 2.3: 上下文重建
- Phase 3: 结构化 prompt（MANDATORY/OUTDATED）
- 全链路: ingest → recall → build_prompt

## 回归测试

- 核心功能测试：394 passed
- 预存在失败：handlers（SQLite 线程安全）、加密、规则
- Phase 1-3 引入的失败：0（conf 变量已修复）
