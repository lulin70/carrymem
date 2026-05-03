# CarryMem 对 DevSquad 集成需求的正式回复

> **From**: CarryMem Team
> **To**: DevSquad Team
> **Date**: 2026-05-01
> **Re**: CarryMem Integration Requirements (V3.5.0)
> **Status**: 正式回复 — 逐项决策

---

## 总体立场

感谢 DevSquad 团队的集成需求文档。CarryMem 团队经7角色评审（PM/架构师/安全专家/测试专家/开发者/DevOps/UI设计师）后，**整体接受集成方向**，但对部分需求有调整意见。

**核心原则**：CarryMem 是个人 AI 记忆层，不是企业级多租户系统。集成方案必须与此定位一致。

---

## 一、✅ 现阶段做的（纳入 v0.2.9 / v0.3.0）

### P0-Core：最小可用集成（v0.2.9）

| ID | 需求 | 做什么 | 怎么做 | 备注 |
|----|------|--------|--------|------|
| CM-002 | `is_available()` 健康检查 | ✅ 原样实现 | 检查 CarryMem 实例 + RuleEngine + 数据库连接 | 第一道门，DevSquad 依赖此方法降级 |
| CM-004 | 优雅错误处理 | ✅ 原样实现 | 所有方法 try/except 包裹，异常返回空列表/None/False | CarryMem 错误绝不崩溃 DevSquad |
| CM-006 | `match_rules()` | ✅ **从P1提升到P0** | 调用 `RuleEngine.match()`，返回结构化 dict | **没有此方法，get_rules 只能返回全量规则，集成无实际价值** |
| CM-007 | `format_rules_as_prompt()` | ✅ **从P1提升到P0** | 调用 `RuleEngine.inject(format="structured")` | **规则注入是集成的核心价值，必须与 match_rules 同步交付** |

### P0-Extended：基础 CRUD（v0.2.9）

| ID | 需求 | 做什么 | 怎么做 | 备注 |
|----|------|--------|--------|------|
| CM-001 | MemoryProvider Protocol | ✅ 实现 | 新建 `DevSquadAdapter` 类，实现 6 个方法 | 适配层独立模块，不修改 CarryMem 核心 API |
| CM-003 | `get_rules()` 角色过滤 | ✅ 实现（调整） | 通过 `context={"role": "architect"}` 过滤，内部调用 `match()` | 角色过滤通过 context 传入，不新增参数 |
| CM-005 | pip 安装暴露适配器 | ✅ 实现 | `pip install carrymem[devsquad]` 安装适配层 | 用 extras 而非默认安装，避免非 DevSquad 用户引入不需要的依赖 |

### P1：增强功能（v0.3.0）

| ID | 需求 | 做什么 | 怎么做 | 备注 |
|----|------|--------|--------|------|
| CM-008 | `log_experience()` | ✅ 实现 | 调用 `RuleEngine.extract_failure_lessons()` + AuditLogger | 记录执行结果和用户反馈 |
| CM-010 | `max_rules` 限制 | ✅ 实现 | `RuleEngine.match()` 已支持 `limit` 参数，直接映射 | 防止 prompt 溢出 |
| CM-012 | 多实例支持 | ✅ **从P2提升到P1** | 多个 CarryMem 实例 = 多个 namespace | CarryMem namespace 天然支持数据隔离，实现成本低 |

---

## 二、⏸️ 现阶段不做的（推迟到 v0.3.x+）

| ID | 需求 | 决策 | 理由 | 预计时间 |
|----|------|------|------|----------|
| CM-009 | Ontology 对象类型匹配 | ⏸️ 推迟 | 现有 `RuleEngine.match()` 基于 FTS5 自然语言匹配，不支持结构化 task_type 标识符。需要扩展 RuleEngine 的 trigger 匹配机制，设计工作量大 | v0.3.1+ |
| CM-011 | 置信度自动调整 | ⏸️ 推迟 | 需要规则与 Agent 假设的冲突检测逻辑，当前 CarryMem 无此能力。需先完成 CM-008 经验学习闭环，积累足够数据后才有意义 | v0.3.x |
| CM-014 | 流式规则更新 | ⏸️ 推迟 | 需要 WebSocket 或长轮询机制，架构复杂度高。当前同步调用模式已满足基本需求 | v0.4.x |

---

## 三、❌ 不做的

| ID | 需求 | 决策 | 理由 |
|----|------|------|------|
| CM-013 | 规则模板市场 | ❌ 拒绝 | CarryMem 是**个人** AI 记忆层，规则是用户个人偏好和决策的体现。规则模板市场暗示规则是可共享的商品，与"个人身份层"定位冲突。如果 DevSquad 需要规则共享功能，建议在 DevSquad 侧实现 RoleTemplate 市场，CarryMem 仅提供规则导入接口 |

---

## 四、⚠️ 需要协商调整的设计

### 4.1 `user_id` 语义调整

| DevSquad 期望 | CarryMem 实际 | 协商建议 |
|--------------|--------------|----------|
| `user_id` 多用户身份 | 单用户 + namespace | **保持 `user_id` 参数签名不变**，CarryMem 内部将其映射为 `namespace` |

**理由**：
- CarryMem 不做用户认证，无用户管理系统
- `namespace` 已实现数据隔离，功能等价
- DevSquad 侧代码无需改动，仅 CarryMem 内部映射

**安全边界声明**：CarryMem 信任调用方提供的 `user_id`，不做鉴权。调用方（DevSquad）负责确保 `user_id` 的真实性。

### 4.2 规则类型映射

| DevSquad 类型 | CarryMem 类型 | 语义 | 映射方向 |
|--------------|--------------|------|----------|
| `forbid` | `never` | 禁止做某事 | `forbid → never`（写入时转换） |
| `avoid` | `avoid` | 尽量避免 | 直接映射 |
| `always` | `always` | 必须做某事 | 直接映射 |
| `override=true` | `override=True` | 不可覆盖 | 直接映射 |

**实现方式**：适配层 `type_mapping.py` 双向映射，对 DevSquad 暴露 `forbid`，对 CarryMem 存储为 `never`。

### 4.3 `get_rules()` 返回值调整

DevSquad 期望返回 `List[str]`（规则字符串列表），但 CarryMem 建议返回更结构化的数据：

```python
# DevSquad 期望
def get_rules(user_id, context) -> List[str]

# CarryMem 建议保持 List[str] 签名不变
# 但每条字符串是格式化的规则描述，如：
# "[ALWAYS] Use SSL for all database connections (override)"
# "[AVOID] Using MongoDB for relational data"
# "[FORBID] Storing passwords in plain text"
```

**理由**：保持 Protocol 签名不变，但规则字符串包含类型前缀，DevSquad 可按需解析。结构化数据通过 `match_rules()` 获取。

---

## 五、交付计划

| 阶段 | 内容 | 优先级 | 目标版本 | 预计交付 |
|------|------|--------|----------|----------|
| **Phase 1** | P0-core: is_available + match_rules + format_rules_as_prompt + 优雅错误处理 | 最高 | v0.2.9 | 2周内 |
| **Phase 2** | P0-extended: MemoryProvider 完整实现 + get_rules + add/update/delete + pip 安装 | 高 | v0.2.9 | 与 Phase 1 同步 |
| **Phase 3** | P1: log_experience + max_rules + 多实例 | 中 | v0.3.0 | 4周内 |
| **Phase 4** | 推迟项: Ontology 匹配 + 置信度调整 | 低 | v0.3.x | 待定 |

### Phase 1 完成后的集成测试清单

```python
# 1. 可用性检查
adapter = DevSquadAdapter(db_path="...")
assert adapter.is_available() == True

# 2. 规则匹配
matched = adapter.match_rules(
    task_description="Design REST API",
    user_id="user1",
    role="architect",
    max_rules=5
)
assert isinstance(matched, list)
assert all("rule_type" in r for r in matched)
assert all("relevance_score" in r for r in matched)

# 3. Prompt 格式化
prompt = adapter.format_rules_as_prompt(matched)
assert isinstance(prompt, str)
assert len(prompt) > 0

# 4. 优雅降级
adapter_bad = DevSquadAdapter(db_path="/nonexistent/path.db")
assert adapter_bad.is_available() == False
matched = adapter_bad.match_rules("test", "user1")  # 不崩溃
assert matched == []
```

---

## 六、需要 DevSquad 侧配合的事项

| 事项 | 说明 | 优先级 |
|------|------|--------|
| **确认 `user_id` → namespace 映射方案** | CarryMem 不做用户认证，DevSquad 需确保 user_id 的真实性 | P0 |
| **确认规则类型映射** | `forbid ↔ never` 双向映射是否可接受 | P0 |
| **更新 MCEAdapter** | 现有 `mce_adapter.py` 未暴露 RuleEngine 接口，需新增规则相关桥接方法 | P0 |
| **提供 NullProvider 更新** | `NullMemoryProvider` 需增加 `match_rules` 和 `format_rules_as_prompt` 的空实现 | P1 |
| **契约测试共建** | 双方共同维护 Protocol 契约测试，任何破坏性变更需提前协商 | P0 |

---

*CarryMem Team — 2026-05-01*
