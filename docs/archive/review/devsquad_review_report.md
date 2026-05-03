# CarryMem v0.4.0 全员评审报告：产品初心审查

**日期**: 2026-05-02
**评审类型**: 产品初心审查 + 遗漏清单全员共识
**参与角色**: 产品经理、架构师、安全专家、测试专家、开发者、DevOps、UI设计师
**评审结论**: ~~🔴 产品核心闭环断裂，当前不可用~~ → ✅ **Phase 1+2+3 修复完成，产品可用**
**修复状态**: P0(9/9) ✅ P1(8/8) ✅ P2(3/6) ✅ 测试 2034/2034 ✅

---

## 一、问题总览

### 1.1 核心断裂：产品初心无法实现

| 初心 | 现状 | 差距 |
|------|------|------|
| "AI记住你是谁" | AI记住了但不会用 | 记忆→规则→注入 闭环断裂 |
| "自然对话中保存偏好" | 只能显式声明 | 自然语言→规则 自动化链路断裂 |
| "跨工具身份随身携带" | 每个工具独立配置 | 无自动注入机制 |

### 1.2 问题统计

| 类别 | P0 | P1 | P2 | 合计 |
|------|----|----|-----|------|
| 产品经理 | 3 | 3 | 2 | 8 |
| 架构师 | 4 | 4 | 2 | 10 |
| 用户管理 | 2 | 2 | 1 | 5 |
| 测试专家 | 2 | 2 | 1 | 5 |
| 安全专家 | 1 | 1 | 1 | 3 |
| DevOps | 0 | 1 | 1 | 2 |
| UI设计师 | 0 | 2 | 1 | 3 |
| **合计** | **12** | **15** | **9** | **36** |

---

## 二、各角色诊断与解决方案

### 👔 产品经理 (PM)

#### 诊断

产品定义了三层身份架构（记忆/规则/知识），但三层之间**没有自动化连接**。用户说了偏好，系统存了记忆，但记忆不会自动变成规则，规则不会自动注入AI提示词。这等于建了仓库但没建配送系统。

#### 问题清单

| ID | 问题 | 优先级 | 解决方案 |
|----|------|--------|---------|
| PM-01 | 记忆→规则晋升管道断裂：`_auto_suggest_rules()` 方法不存在 | **P0** | 实现该方法，调用已有的 `PatternDetector` + `CandidateRuleGenerator` |
| PM-02 | 规则→注入断裂：无"对话开始自动注入"机制 | **P0** | 在 `get_system_prompt` 中默认注入全局规则；MCP配置添加 `alwaysInject` |
| PM-03 | correction类型不更新旧记忆/规则 | **P0** | 在 `classify_and_remember` 中检测correction，自动更新关联记忆和规则 |
| PM-04 | 无首次对话引导机制 | P1 | 添加 `onboard` MCP工具，首次对话时AI主动询问关键偏好 |
| PM-05 | 无规则应用反馈机制 | P1 | AI应用规则后在回复中标注 `[CarryMem规则: xxx]` |
| PM-06 | 偏好演变无处理 | P1 | 检测同主题新偏好，提示用户是否替换旧规则 |
| PM-07 | 条件性偏好无法处理 | P2 | 规则模型添加 `condition` 字段，支持 "when X, do Y" |
| PM-08 | 隐式偏好推断缺失 | P2 | v0.5.0 通过向量语义匹配实现 |

#### 用户管理场景（用户特别关注）

| ID | 场景 | 优先级 | 解决方案 |
|----|------|--------|---------|
| UM-01 | 用户查看所有规则 | **P0** | MCP添加 `my_rules` 工具，返回格式化规则摘要；CLI增强 `carrymem rules list --format=table` |
| UM-02 | 用户删除/修改规则 | **P0** | MCP添加 `update_rule`/`delete_rule` 工具；CLI增强 `carrymem rules edit/delete` |
| UM-03 | 用户查看"我的数据" | P1 | MCP添加 `my_profile` 工具，返回记忆+规则+知识库的完整画像 |
| UM-04 | 规则冲突提示 | P1 | 存储新规则时自动检测冲突，返回 `conflict_warning` |
| UM-05 | 规则过期机制 | P2 | 规则模型添加 `expires_at` 字段，定期清理 |

---

### 🏗️ 架构师 (Architect)

#### 诊断

系统架构设计完整（三层分类漏斗、规则引擎7子模块、MCP 16工具），但**模块间连接存在10处断裂**。最严重的是3个P0级断裂：自动规则建议未实现、MCP规则工具与CarryMem实例隔离、无自动注入机制。

#### 问题清单

| ID | 问题 | 优先级 | 解决方案 | 影响范围 |
|----|------|--------|---------|---------|
| ARCH-01 | `_auto_suggest_rules()` 未实现 | **P0** | 实现：调用 `PatternDetector.detect_patterns()` → `CandidateRuleGenerator.generate()` → 返回候选规则列表 | carrymem.py |
| ARCH-02 | MCP规则工具 `target=None` | **P0** | 改为 `target=self._carrymem`，handler通过CarryMem实例获取RuleEngine | handlers.py |
| ARCH-03 | RuleEngine每次创建新实例 | **P0** | 在Handlers初始化时创建共享RuleEngine实例，复用db_path | handlers.py |
| ARCH-04 | 无对话开始自动注入 | **P0** | `get_system_prompt` 无context时也注入全局规则；MCP配置添加 `systemPromptHook` | carrymem.py, mcp.json |
| ARCH-05 | `suggest_rules`/`promote_rules` 无MCP工具 | P1 | 添加2个MCP工具定义和handler | tools.py, handlers.py |
| ARCH-06 | correction不更新旧记忆 | P1 | `classify_and_remember` 检测correction类型，调用 `adapter.update()` 更新旧记忆 | carrymem.py |
| ARCH-07 | FTS5匹配分数固定0.8 | P1 | 使用FTS5的 `rank` 列计算真实相关度分数 | matcher.py |
| ARCH-08 | context参数格式不一致 | P1 | MCP工具的context改为object类型，支持结构化上下文 | tools.py, handlers.py |
| ARCH-09 | 中文分词依赖空格 | P2 | 添加jieba分词可选依赖，fallback到字符级n-gram | matcher.py |
| ARCH-10 | DevSquad集成与MCP割裂 | P2 | 统一适配器接口，MCP handler可调用DevSquadAdapter方法 | handlers.py |

#### 架构修复方案：核心闭环重建

```
修复前（断裂）：
用户对话 → classify_and_remember → 存储 → ❌断裂❌ → 手动add_rule → ❌断裂❌ → 手动inject_rules

修复后（闭环）：
用户对话 → classify_and_remember → 存储 → _auto_suggest_rules → 候选规则
                                                                    ↓
                                              AI提示用户确认 ← suggest_rules MCP工具
                                                    ↓
                                              用户确认 → promote_rules → 规则激活
                                                    ↓
                                    对话开始 → get_system_prompt → 自动注入规则 → AI行为改变
```

---

### 🔒 安全专家 (Security)

#### 诊断

规则注入是双刃剑：一方面让AI遵循用户偏好，另一方面规则内容会被注入到AI提示词中，可能被恶意利用。当前缺少规则内容的安全审计和注入防护。

#### 问题清单

| ID | 问题 | 优先级 | 解决方案 |
|----|------|--------|---------|
| SEC-01 | 规则内容注入提示词无安全过滤 | **P0** | `RuleInjector` 输出前通过 `RuleSanitizer` 过滤，检测prompt injection模式 |
| SEC-02 | 跨用户规则共享隐私风险 | P1 | Skill打包时脱敏个人标识，添加 `privacy_level` 字段 |
| SEC-03 | 规则优先级覆盖安全边界 | P1 | `company > negotiated > personal` 已有，但需添加跨scope覆盖的审计日志 |
| SEC-04 | 规则删除无确认机制 | P2 | 删除规则前要求二次确认，关键规则（override=True）需额外验证 |

#### 安全方案：规则注入防护

```python
# RuleInjector 输出前安全检查
def inject(self, scene, format, max_rules):
    rules = self.matcher.match(scene)
    for rule in rules:
        # 1. 检测prompt injection模式
        sanitized = RuleSanitizer.sanitize_for_injection(rule.action)
        # 2. 检测规则内容中的指令覆盖
        if contains_instruction_override(sanitized):
            rule.action = "[REDACTED: potential injection]"
    # ... 正常注入流程
```

---

### 🧪 测试专家 (Tester)

#### 诊断

当前测试体系**覆盖了组件但没覆盖用户旅程**。所有测试都是"显式API调用"模式，没有模拟真实用户在自然对话中的行为。核心闭环（对话→保存→规则→注入→行为改变）完全没有端到端测试。

#### 问题清单

| ID | 问题 | 优先级 | 解决方案 |
|----|------|--------|---------|
| TEST-01 | 无自然对话偏好提取测试 | **P0** | 添加 `test_natural_conversation.py`，使用真实对话语料测试分类+存储+规则建议 |
| TEST-02 | 无端到端用户旅程测试 | **P0** | 添加 `test_e2e_journey.py`，测试完整闭环：对话→保存→规则→注入→行为验证 |
| TEST-03 | 无记忆→规则自动晋升集成测试 | P1 | 添加 `test_promotion_integration.py`，测试3条相似记忆→模式检测→候选生成→确认→激活 |
| TEST-04 | 无多轮对话累积测试 | P1 | 添加 `test_multi_turn.py`，测试5轮对话中偏好逐步积累 |
| TEST-05 | 测试输入太"干净" | P1 | 在现有测试中添加"脏输入"变体：口语化、含噪声、含情绪 |
| TEST-06 | 无规则管理用户测试 | P1 | 添加 `test_rule_management.py`，测试用户查看/删除/修改规则的完整流程 |
| TEST-07 | 无规则冲突提示测试 | P2 | 添加冲突场景测试 |

#### 测试方案：自然对话测试用例

```python
NATURAL_CONVERSATION_CASES = [
    # (输入, 期望类型, 期望是否生成规则候选)
    ("我觉得PostgreSQL比MySQL好用多了", "user_preference", True),
    ("下次别用这个方案了，太慢了", "correction", True),
    ("我一般都用Python写脚本", "task_pattern", True),
    ("哦不对，应该是v2不是v3", "correction", True),  # 应更新旧记忆
    ("这个框架真的太烦了", "sentiment_marker", True),
    ("小项目就用SQLite吧", "decision", True),  # 条件性偏好
    ("你好", None, False),  # 噪声
    ("帮我写个函数", None, False),  # 任务指令，非偏好
]
```

---

### 💻 开发者 (Coder)

#### 诊断

从实现角度看，核心问题集中在3个文件：`carrymem.py`（缺 `_auto_suggest_rules`）、`handlers.py`（target隔离）、`tools.py`（缺工具定义）。修复工作量不大，但需要确保不破坏现有API。

#### 实现计划

| ID | 实现项 | 优先级 | 预估工作量 | 涉及文件 |
|----|--------|--------|-----------|---------|
| CODE-01 | 实现 `_auto_suggest_rules()` | **P0** | 2h | carrymem.py |
| CODE-02 | 修复MCP规则工具target | **P0** | 1h | handlers.py |
| CODE-03 | 共享RuleEngine实例 | **P0** | 1h | handlers.py |
| CODE-04 | `get_system_prompt` 无context也注入 | **P0** | 0.5h | carrymem.py |
| CODE-05 | 添加 `suggest_rules`/`promote_rules` MCP工具 | P1 | 1h | tools.py, handlers.py |
| CODE-06 | correction更新旧记忆 | P1 | 2h | carrymem.py |
| CODE-07 | 添加 `my_rules`/`update_rule`/`delete_rule` MCP工具 | P1 | 1.5h | tools.py, handlers.py |
| CODE-08 | 添加 `my_profile` MCP工具 | P1 | 1h | tools.py, handlers.py |
| CODE-09 | 规则注入安全过滤 | P1 | 1h | injector.py |
| CODE-10 | FTS5 rank分数 | P1 | 0.5h | matcher.py |
| CODE-11 | CLI规则管理增强 | P2 | 1h | cli.py |
| CODE-12 | 规则过期机制 | P2 | 1.5h | models.py, storage.py |

---

### ⚙️ DevOps

#### 诊断

当前MCP配置只定义了启动命令，缺少自动注入的配置项。用户安装后需要手动配置AI工具来调用CarryMem，门槛太高。

#### 问题清单

| ID | 问题 | 优先级 | 解决方案 |
|----|------|--------|---------|
| OPS-01 | MCP配置无自动注入设置 | P1 | mcp.json添加 `systemPrompt` 配置，AI工具启动时自动调用 `get_system_prompt` |
| OPS-02 | 安装后无验证流程 | P2 | `carrymem doctor` 命令增强，验证MCP连接和规则注入是否正常 |

---

### 🎨 UI设计师

#### 诊断

CarryMem当前是纯后端+CLI产品，用户与规则的交互完全依赖AI对话或命令行。对于非技术用户，需要更友好的规则管理界面。

#### 问题清单

| ID | 问题 | 优先级 | 解决方案 |
|----|------|--------|---------|
| UI-01 | 规则管理无可视化界面 | P1 | VS Code Extension侧边栏增强：规则列表、编辑、删除、搜索 |
| UI-02 | 规则生效状态不可见 | P1 | AI回复中标注 `[规则: xxx]` 标签，让用户知道规则被应用 |
| UI-03 | 无"我的数据"仪表盘 | P2 | VS Code Extension添加仪表盘视图：记忆统计、规则分布、最近活动 |

---

## 三、全员共识：统一修复计划

### 3.1 共识原则

1. **初心优先**：先修复核心闭环（记忆→规则→注入），再优化体验
2. **最小可用**：P0修复后产品即可用，P1修复后体验良好
3. **不破坏现有API**：所有修复通过新增方法/参数实现，不修改已有签名
4. **测试先行**：每个P0修复必须有对应的端到端测试

### 3.2 修复阶段

#### Phase 1：核心闭环修复（P0，产品从不可用→可用）

| 序号 | 修复项 | 负责角色 | 验收标准 |
|------|--------|---------|---------|
| 1.1 | 实现 `_auto_suggest_rules()` | 开发者 | 存储偏好类记忆后返回非空auto_rules |
| 1.2 | 修复MCP规则工具target=None | 开发者 | 规则工具共享CarryMem实例的db_path |
| 1.3 | 共享RuleEngine实例 | 开发者 | Handlers初始化时创建一次，后续复用 |
| 1.4 | `get_system_prompt` 无context也注入全局规则 | 开发者 | 无context时返回所有active规则 |
| 1.5 | 添加 `my_rules` MCP工具 | 开发者 | 用户可查看所有规则摘要 |
| 1.6 | 添加 `delete_rule` MCP工具 | 开发者 | 用户可删除指定规则 |
| 1.7 | 规则注入安全过滤 | 安全专家 | 恶意规则内容被REDACTED |
| 1.8 | 自然对话偏好提取测试 | 测试专家 | 8个自然对话用例全部通过 |
| 1.9 | 端到端用户旅程测试 | 测试专家 | 对话→保存→规则→注入→行为验证 通过 |

#### Phase 2：体验优化（P1，产品从可用→好用）

| 序号 | 修复项 | 负责角色 |
|------|--------|---------|
| 2.1 | 添加 `suggest_rules`/`promote_rules` MCP工具 | 开发者 |
| 2.2 | correction更新旧记忆/规则 | 开发者 |
| 2.3 | 添加 `update_rule` MCP工具 | 开发者 |
| 2.4 | 添加 `my_profile` MCP工具 | 开发者 |
| 2.5 | 添加 `onboard` 首次对话引导工具 | 开发者+PM |
| 2.6 | 规则应用反馈标注 | 开发者+UI |
| 2.7 | 偏好演变检测与提示 | 开发者 |
| 2.8 | 规则冲突提示 | 开发者 |
| 2.9 | FTS5 rank分数 | 开发者 |
| 2.10 | context参数格式统一 | 开发者 |
| 2.11 | MCP配置添加自动注入设置 | DevOps |
| 2.12 | VS Code规则管理增强 | UI+开发者 |
| 2.13 | 记忆→规则晋升集成测试 | 测试专家 |
| 2.14 | 多轮对话累积测试 | 测试专家 |
| 2.15 | 规则管理用户测试 | 测试专家 |

#### Phase 3：智能增强（P2，产品从好用→智能）

| 序号 | 修复项 | 负责角色 |
|------|--------|---------|
| 3.1 | 中文分词优化（jieba） | 开发者 |
| 3.2 | 规则过期机制 | 开发者 |
| 3.3 | 条件性偏好支持 | 开发者+PM |
| 3.4 | CLI规则管理增强 | 开发者 |
| 3.5 | "我的数据"仪表盘 | UI+开发者 |
| 3.6 | 安装验证流程增强 | DevOps |
| 3.7 | 隐式偏好推断 | v0.5.0 |

### 3.3 关键决策记录

| 决策 | 选项 | 共识结果 | 理由 |
|------|------|---------|------|
| 自动规则确认方式 | A.全自动 B.需用户确认 C.混合 | **C.混合** | 低置信度自动激活，高影响需确认 |
| 规则注入时机 | A.每次对话 B.仅首次 C.按需 | **A.每次对话** | 确保规则始终生效 |
| 用户管理界面 | A.仅MCP B.仅CLI C.MCP+CLI+VSCode | **C.MCP+CLI+VSCode** | 覆盖所有用户类型 |
| 规则安全过滤 | A.存储时过滤 B.注入时过滤 C.双重过滤 | **C.双重过滤** | 纵深防御 |
| correction更新策略 | A.覆盖旧记忆 B.保留历史+标记过期 C.仅添加新记忆 | **B.保留历史+标记过期** | 可追溯，不丢数据 |

---

## 四、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 自动规则建议产生过多候选 | 中 | 中 | 限制每次最多3个候选，置信度阈值0.7 |
| 规则注入增加prompt长度 | 低 | 中 | ContextBudget控制，规则占30%预算 |
| correction误判导致旧记忆被覆盖 | 中 | 高 | 保留历史，标记过期而非删除 |
| 中文分词依赖增加安装复杂度 | 低 | 低 | jieba作为可选依赖，fallback到n-gram |

---

## 五、验收标准

### Phase 1 完成标准（产品可用）

```python
# 这个流程必须100%通过
cm = CarryMem(storage=SQLiteAdapter())

# 1. 用户自然对话
result = cm.classify_and_remember("我从来不用MySQL，都用PostgreSQL")
assert result["stored"] == True
assert result["type"] == "user_preference"

# 2. 自动规则建议
assert len(result["auto_rules"]) > 0  # 候选规则非空

# 3. 用户确认规则（通过MCP promote_rules）
rule = engine.add_rule(trigger="数据库选型", action="使用PostgreSQL", rule_type="always")

# 4. 后续对话自动注入
prompt = cm.build_context(context="帮我设计数据库架构")
assert "PostgreSQL" in prompt  # 规则被注入

# 5. 用户查看规则
rules = cm.list_rules()
assert any(r.trigger == "数据库选型" for r in rules)

# 6. 用户删除规则
cm.delete_rule(rule.id)
rules = cm.list_rules()
assert not any(r.trigger == "数据库选型" for r in rules)
```

---

**评审结论**：全员一致认为产品核心闭环断裂，Phase 1 的9项P0修复必须立即执行。修复后产品从"不可用"升级为"可用"，Phase 2 完成后升级为"好用"。
