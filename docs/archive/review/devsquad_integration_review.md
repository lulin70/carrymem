# CarryMem × DevSquad 集成需求评审报告

**评审日期**: 2026-05-01
**需求来源**: DevSquad V3.5.0 — `/docs/prd/carrymem_integration_requirements.md`
**评审方式**: CarryMem 7角色共识评审（PM/架构师/安全专家/测试专家/开发者/DevOps/UI设计师）
**结论**: ✅ 有条件接受 — 需求整体方向一致，但存在3个核心冲突需协商调整

---

## 一、评审结论总览

| 维度 | 评级 | 说明 |
|------|------|------|
| **与初心一致性** | 🟡 部分冲突 | `user_id` 多租户模型与 CarryMem 个人记忆层定位冲突 |
| **技术可行性** | 🟢 可行 | RuleEngine 已有 80% 所需功能，适配层工作量可控 |
| **优先级合理性** | 🟡 部分调整 | P0 过重，建议拆分；P2 的 CM-012 多实例有价值 |
| **性能风险** | 🟡 中等 | 同步调用可能阻塞 DevSquad Worker；需异步/超时机制 |
| **安全风险** | 🔴 高 | `user_id` 跨系统传递存在身份冒充风险；规则注入存在 Prompt 注入风险 |
| **逻辑风险** | 🟡 中等 | 规则类型映射不一致（forbid/avoid/always vs always/avoid/never） |

---

## 二、各角色评审意见

### 2.1 🎯 产品经理 (PM)

**核心判断：方向一致，但用户模型需重新定义**

| 评审项 | 意见 |
|--------|------|
| **定位冲突** | CarryMem 定位是"个人 AI 记忆层"，`user_id` 参数暗示多租户。建议：将 `user_id` 语义改为 `profile_id` 或 `namespace`，CarryMem 内部用 namespace 隔离，而非引入用户认证系统 |
| **P0 范围** | CM-001~CM-005 过重，建议拆分：CM-001/002/004 为 P0-core（最小可用），CM-003/005 为 P0-extended |
| **P1 价值** | CM-006 (match_rules) 和 CM-007 (format_rules_as_prompt) 价值最高，应提升到 P0-core。没有 match_rules，get_rules 只能返回全量规则，实用性极低 |
| **P2 取舍** | CM-012 (多实例) 实际上是 CarryMem namespace 功能的自然延伸，建议降级到 P1。CM-013 (规则市场) 与 CarryMem 定位偏离，建议拒绝 |
| **产品路线图** | 集成应纳入 v0.3.0 GA 里程碑，作为"生态集成"特性，而非 v0.2.x |

### 2.2 🏗️ 架构师 (Architect)

**核心判断：现有 RuleEngine 可支撑 80%，适配层设计需调整**

| 评审项 | 意见 |
|--------|------|
| **接口映射** | CarryMem RuleEngine 已有完整 CRUD + match + inject，与 DevSquad Protocol 映射关系：|
| | `MemoryProvider.get_rules()` → `RuleEngine.match()` + 格式化 |
| | `MemoryProvider.add_rule()` → `RuleEngine.add_rule()` |
| | `MemoryProvider.update_rule()` → `RuleEngine.update_rule()` |
| | `MemoryProvider.delete_rule()` → `RuleEngine.delete_rule()` |
| | `MemoryProvider.is_available()` → 新增，检查 CarryMem 实例健康 |
| | `MemoryProvider.get_stats()` → `RuleEngine.get_stats()` |
| | `CarryMemAdapter.match_rules()` → `RuleEngine.match()` |
| | `CarryMemAdapter.format_rules_as_prompt()` → `RuleEngine.inject()` |
| | `CarryMemAdapter.log_experience()` → `RuleEngine.extract_failure_lessons()` |
| **类型映射冲突** | DevSquad 定义 `forbid/avoid/always`，CarryMem 使用 `always/avoid/never`。需建立双向映射：`forbid↔never`, `avoid↔avoid`, `always↔always` |
| **适配层位置** | 建议在 CarryMem 侧新建 `integration/devsquad/` 模块，而非修改核心 API。适配器模式，不污染 CarryMem 核心接口 |
| **性能架构** | `match()` 和 `inject()` 是同步 SQLite 查询，在 DevSquad ThreadPoolExecutor 中调用是安全的，但需设置超时（建议 500ms，与现有 MCEAdapter 一致） |
| **数据流** | DevSquad → CarryMemAdapter → RuleEngine → SQLite。无需 HTTP，进程内直接调用，零网络延迟 |

### 2.3 🔒 安全专家 (Security)

**核心判断：3个高危风险必须先解决**

| 风险等级 | 风险 | 缓解措施 |
|----------|------|----------|
| 🔴 **高** | **身份冒充**：`user_id` 由 DevSquad 传入，CarryMem 无法验证。恶意 Agent 可传入他人 user_id 读取/修改规则 | 1. CarryMem 不做用户认证，由宿主系统保证隔离 2. `user_id` 改为 `namespace`，CarryMem 仅做数据隔离不做鉴权 3. 在文档中明确安全边界：CarryMem 信任调用方 |
| 🔴 **高** | **Prompt 注入**：`format_rules_as_prompt()` 将规则内容注入 DevSquad prompt。恶意规则可包含 prompt 注入攻击 | 1. 复用 CarryMem 已有的 `RuleSanitizer`（10个注入检测模式） 2. `format_rules_as_prompt()` 输出必须经过 `InputValidator` 验证 3. 规则 action 字段限制长度（≤500字符，已有） |
| 🔴 **高** | **规则篡改**：`add_rule/update_rule` 无权限校验，任何调用方可修改任何规则 | 1. 适配层增加 `source` 标记，记录规则来源（manual/devsquad/imported） 2. `override=true` 的规则不可被外部修改 3. 审计日志记录所有规则变更 |
| 🟡 **中** | **信息泄露**：`get_stats()` 可能暴露用户规则数量和类型分布 | 1. 适配层过滤敏感字段 2. 仅返回聚合统计，不返回具体规则内容 |
| 🟡 **中** | **DoS**：`match_rules()` 无限调用可能耗尽 SQLite 连接 | 1. 适配层增加速率限制（建议 60次/分钟） 2. 复用 CarryMem 已有的 `validate_limit()` 限制 max_rules |

### 2.4 🧪 测试专家 (Tester)

**核心判断：集成测试策略需双方协同制定**

| 评审项 | 意见 |
|--------|------|
| **测试责任** | CarryMem 侧：适配层单元测试 + Protocol 契约测试。DevSquad 侧：集成测试 + 降级测试 |
| **契约测试** | 必须验证 MemoryProvider Protocol 的 6 个方法签名和返回值结构，确保不破坏 DevSquad 的类型假设 |
| **降级测试** | `is_available()=False` 时，所有方法必须安全返回（空列表/None/False），不能抛异常。需覆盖：CarryMem 未安装、数据库损坏、超时、规则引擎异常 |
| **边界测试** | max_rules=0、空规则列表、超长规则内容、特殊字符规则、并发读写 |
| **性能基线** | `match_rules()` 应 <50ms（SQLite FTS5），`format_rules_as_prompt()` 应 <10ms（纯字符串格式化） |
| **回归风险** | 适配层不得修改 CarryMem 核心 API 的行为。所有适配逻辑在独立模块中 |

### 2.5 💻 开发者 (Coder)

**核心判断：实现方案清晰，约 300 行适配代码**

| 评审项 | 意见 |
|--------|------|
| **实现位置** | 新建 `src/memory_classification_engine/integration/devsquad/` 包，包含 `adapter.py` + `protocol.py` + `type_mapping.py` |
| **核心适配器** | `DevSquadAdapter` 类，组合 `CarryMem` + `RuleEngine`，实现 `MemoryProvider` 和 `CarryMemAdapter` 两个 Protocol |
| **类型映射** | 独立 `type_mapping.py`，双向转换：`forbid↔never`, `avoid↔avoid`, `always↔always`；`override` 字段直接映射 |
| **is_available()** | 实现：检查 CarryMem 实例是否已初始化 + RuleEngine 是否可访问 + 数据库是否可连接 |
| **get_rules()** | 实现：调用 `RuleEngine.match(scene_description=context.get("task",""), limit=max_rules)`，过滤 `context.get("role")` 匹配的规则，返回 action 字符串列表 |
| **match_rules()** | 实现：调用 `RuleEngine.match()`，将 MatchResult 转换为 DevSquad 期望的 dict 结构 |
| **format_rules_as_prompt()** | 实现：调用 `RuleEngine.inject(format="structured")`，输出 Markdown |
| **log_experience()** | 实现：调用 `RuleEngine.extract_failure_lessons()` 或直接写入 AuditLogger |
| **错误处理** | 所有方法 try/except 包裹，异常时返回空列表/None/False，记录到 CarryMem AuditLogger |
| **工作量估算** | 适配层 ~300 行 + 类型映射 ~50 行 + 测试 ~200 行，总计 ~550 行 |

### 2.6 ⚙️ DevOps 工程师

**核心判断：部署模型需明确，依赖管理需谨慎**

| 评审项 | 意见 |
|--------|------|
| **部署模型** | CarryMem 作为 DevSquad 的 Python 依赖，进程内调用，无需独立部署。与现有 MCEAdapter 模式一致 |
| **依赖方向** | CarryMem → 不依赖 DevSquad。DevSquad → 可选依赖 CarryMem。方向正确 |
| **pip 安装** | CM-005 要求 `pip install carrymem` 暴露适配器类。建议：在 `pyproject.toml` 中增加 `[devsquad]` extras，`pip install carrymem[devsquad]` 安装适配层 |
| **版本兼容** | 适配层应声明对 DevSquad Protocol 的兼容版本范围，避免静默不兼容 |
| **CI/CD** | 需在 CarryMem CI 中增加适配层测试，确保 Protocol 契约不被破坏 |
| **监控** | `is_available()` 应包含数据库连接检查，而非仅检查 Python 导入 |

### 2.7 🎨 UI 设计师

**核心判断：集成对 CarryMem CLI/TUI 无直接影响，但需考虑规则来源可视化**

| 评审项 | 意见 |
|--------|------|
| **CLI 影响** | 集成是程序化 API 层面的，不涉及 CarryMem CLI 变更 |
| **规则来源标识** | 通过 DevSquad 创建的规则应在 `carrymem list-rules` 中标记来源为 `devsquad`，便于用户区分 |
| **TUI 增强** | 未来可在 TUI 中增加"集成规则"视图，按来源分组展示 |
| **用户感知** | 用户应能感知哪些规则来自 DevSquad 集成，哪些是手动创建。建议在规则 metadata 中增加 `source: "devsquad"` |

---

## 三、核心冲突与协商建议

### 冲突 1：`user_id` 多租户模型 vs 个人记忆层定位

| 维度 | DevSquad 期望 | CarryMem 现状 | 协商建议 |
|------|--------------|--------------|----------|
| 身份模型 | `user_id` 多用户 | 单用户 + namespace | 将 `user_id` 映射为 CarryMem `namespace`，CarryMem 不做用户认证 |
| 数据隔离 | 按 user_id 隔离 | 按 namespace 隔离 | namespace 天然支持，无需新增机制 |
| 权限校验 | 未定义 | 无 | CarryMem 信任调用方，在文档中明确安全边界 |

**建议修改**：将 Protocol 中所有 `user_id: str` 改为 `user_id: str`（保持签名不变），但 CarryMem 内部将其映射为 namespace。这样 DevSquad 侧无需改动，CarryMem 侧无需引入用户系统。

### 冲突 2：规则类型映射不一致

| DevSquad | CarryMem | 语义 | 映射方案 |
|----------|----------|------|----------|
| `forbid` | `never` | 禁止做某事 | `forbid → never`（双向） |
| `avoid` | `avoid` | 尽量避免 | 直接映射 |
| `always` | `always` | 必须做某事 | 直接映射 |
| `override=true` | `override=True` | 不可覆盖 | 直接映射 |

**建议**：在适配层 `type_mapping.py` 中建立双向映射表，对 DevSquad 侧暴露 `forbid`，对 CarryMem 侧存储为 `never`。

### 冲突 3：P0 范围过重，缺少 match_rules

| ID | DevSquad 定级 | 建议调整 | 理由 |
|----|-------------|---------|------|
| CM-001 | P0 | **P0-core** | MemoryProvider Protocol 实现 |
| CM-002 | P0 | **P0-core** | is_available() 健康检查 |
| CM-004 | P0 | **P0-core** | 优雅错误处理 |
| CM-006 | P1 | **↑ P0-core** | match_rules 是核心价值，没有它 get_rules 只能返回全量 |
| CM-007 | P1 | **↑ P0-core** | format_rules_as_prompt 是规则注入的必要步骤 |
| CM-003 | P0 | **P0-extended** | 角色过滤可在 match 中通过 context 实现 |
| CM-005 | P0 | **P0-extended** | pip 安装是发布问题，非功能问题 |
| CM-008 | P1 | **P1** | log_experience 可用现有 extract_failure_lessons |
| CM-009 | P1 | **P1** | Ontology 匹配需扩展 RuleEngine.match() |
| CM-010 | P1 | **P1** | max_rules 限制已在 RuleEngine.match() 中支持 |
| CM-011 | P2 | **P2** | 置信度调整需要更复杂的逻辑 |
| CM-012 | P2 | **↓ P1** | 多实例 = 多 namespace，已有基础 |
| CM-013 | P2 | **❌ 拒绝** | 规则市场与 CarryMem 定位偏离 |
| CM-014 | P2 | **P2** | 流式更新需要 WebSocket，复杂度高 |

---

## 四、风险评估矩阵

| 风险 | 概率 | 影响 | 缓解 | 责任方 |
|------|------|------|------|--------|
| 身份冒充导致跨用户数据泄露 | 中 | 高 | namespace 隔离 + 安全边界文档 | CarryMem |
| Prompt 注入通过规则内容 | 高 | 高 | RuleSanitizer + InputValidator | CarryMem |
| 同步调用阻塞 DevSquad Worker | 低 | 中 | 500ms 超时 + 降级返回空 | DevSquad |
| 规则类型映射不一致导致行为异常 | 中 | 中 | 双向映射表 + 集成测试 | 双方 |
| CarryMem 升级破坏 Protocol 契约 | 低 | 高 | 契约测试 + API Stability Policy | CarryMem |
| SQLite 并发写入冲突 | 低 | 中 | WAL 模式 + 重试 | CarryMem |

---

## 五、建议实现方案

### 5.1 模块结构

```
src/memory_classification_engine/integration/devsquad/
├── __init__.py          # 导出 DevSquadAdapter
├── adapter.py           # DevSquadAdapter 实现
├── protocol.py          # MemoryProvider + CarryMemAdapter Protocol 定义
└── type_mapping.py      # 双向类型映射
```

### 5.2 核心适配器签名

```python
class DevSquadAdapter:
    """CarryMem → DevSquad integration adapter."""

    def __init__(self, db_path: str = None, namespace: str = "default"):
        self._cm = CarryMem(db_path=db_path, namespace=namespace)
        self._rules = self._cm.engine.rules if hasattr(self._cm.engine, 'rules') else None

    # MemoryProvider Protocol
    def is_available(self) -> bool: ...
    def get_rules(self, user_id: str, context: Optional[Dict] = None) -> List[str]: ...
    def add_rule(self, user_id: str, rule: str, metadata: Optional[Dict] = None) -> None: ...
    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None: ...
    def delete_rule(self, user_id: str, rule_id: str) -> None: ...
    def get_stats(self) -> Dict[str, Any]: ...

    # CarryMemAdapter Protocol
    def match_rules(self, task_description: str, user_id: str,
                    role: Optional[str] = None, max_rules: int = 5) -> List[Dict]: ...
    def format_rules_as_prompt(self, rules: List[Dict]) -> str: ...
    def log_experience(self, user_id: str, role: Optional[str],
                       task: str, rules_applied: List[str],
                       outcome: str, user_feedback: Optional[str] = None) -> str: ...
```

### 5.3 实现里程碑

| 阶段 | 内容 | 依赖 | 目标版本 |
|------|------|------|----------|
| **Phase 1** | P0-core: Protocol 定义 + is_available + match_rules + format_rules_as_prompt + 错误处理 | RuleEngine.match() + inject() | v0.2.9 |
| **Phase 2** | P0-extended: get_rules + add/update/delete_rule + 角色过滤 | RuleEngine CRUD | v0.2.9 |
| **Phase 3** | P1: log_experience + Ontology 匹配 + max_rules | extract_failure_lessons | v0.3.0 |
| **Phase 4** | P2: 多实例 + 流式更新 | namespace 增强 | v0.3.x |

---

## 六、共识声明

**7角色一致同意以下立场**：

1. ✅ **接受集成方向**：CarryMem 作为 AI Identity Layer，为 DevSquad 提供规则注入是自然延伸，与"让 AI 记住你"的初心一致
2. ⚠️ **拒绝多租户**：`user_id` 不引入用户认证系统，映射为 namespace 实现数据隔离
3. ⚠️ **调整 P0 范围**：match_rules 和 format_rules_as_prompt 必须纳入 P0-core，否则集成无实际价值
4. ❌ **拒绝 CM-013**：规则模板市场与 CarryMem 个人记忆层定位冲突
5. 🔒 **安全前置**：3个高危风险（身份冒充/Prompt注入/规则篡改）必须在 Phase 1 完成前解决
6. 📋 **契约测试**：双方共同维护 Protocol 契约测试套件，任何破坏契约的变更需提前协商

---

*评审完成。本报告将同步至 CarryMem `docs/review/` 和 DevSquad `docs/prd/` 目录。*
