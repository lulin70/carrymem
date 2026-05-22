# CarryMem 用户指南

## 目录

1. [快速入门](#快速入门)
2. [记忆系统](#记忆系统)
3. [规则引擎](#规则引擎)
4. [规则作用域](#规则作用域)
5. [Skill 格式](#skill-格式)
6. [合并协议](#合并协议)
7. [记忆整合](#记忆整合)
8. [VS Code 扩展](#vs-code-扩展)
9. [CLI 参考](#cli-参考)

---

## 快速入门

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("我偏好深色模式")
memories = cm.recall_memories("主题")
print(cm.build_system_prompt())
cm.close()
```

---

## 记忆系统

CarryMem 自动将你的输入分类为 7 种记忆类型：

| 类型 | 示例 |
|------|------|
| `user_preference` | "我偏好深色模式" |
| `correction` | "不对，是 Python 3.11" |
| `decision` | "前端用 React" |
| `fact_declaration` | "Python 3.12 是运行时" |
| `relationship` | "Sarah 是我的经理" |
| `task_pattern` | "我总是先写测试" |
| `sentiment_marker` | "这个构建太慢了" |

---

## 规则引擎

规则是行为契约：**当 X 发生时，做 Y**。

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# 创建规则
engine.add_rule("数据库", "始终使用SSL连接")
engine.add_rule("代码审查", "检查SQL注入", rule_type="forbid")

# 匹配规则到当前上下文
results = engine.match("数据库连接设置")
for r in results:
    print(f"[{r.rule.rule_type}] {r.rule.trigger} → {r.rule.action}")

# 注入规则到 AI 上下文
injection = engine.inject("数据库设计会议", format="structured")
```

### 规则类型

| 类型 | 优先级 | 说明 |
|------|--------|------|
| `forbid` | 最高 | 绝对禁止 |
| `always` | 高 | 必须始终遵守 |
| `avoid` | 中 | 应当避免（默认） |
| `prefer` | 低 | 推荐方式 |
| `format` | 低 | 输出格式规则 |

---

## 规则作用域

作用域控制规则在组织边界内的优先级和可见性。

### 作用域层级

```
company（优先级 3）— 组织强制，不可被覆盖
  ↓
negotiated（优先级 2）— 从公司规则适配而来
  ↓
personal（优先级 1）— 用户创建的偏好
```

### 用法

```python
# 公司规则 — 最高优先级
engine.add_rule("数据库", "始终使用SSL", scope="company", override=True)

# 个人偏好 — 最低优先级
engine.add_rule("数据库", "偏好PostgreSQL", scope="personal")

# 作用域感知匹配
results = engine.match("数据库", scopes=["company"])  # 只匹配公司规则

# 作用域感知列表
company_rules = engine.list_rules(scope="company")
```

### 安全边界

**公司覆盖规则不可被个人规则覆盖。** 这是合并协议强制执行的硬安全边界：

```python
# 这条规则永远不会覆盖公司覆盖规则
engine.add_rule("数据库", "开发环境跳过SSL", scope="personal", override=True)
# → 在任何冲突中，公司规则获胜
```

---

## Skill 格式

Skill 是具有加密完整性验证的便携规则包。

### 创建 Skill

```python
# 将所有活跃规则打包为 Skill 包
bundle = engine.skill_pack(
    name="团队规范",
    version="1.0.0",
    scope="company",
    author="团队负责人",
    description="团队编码规范",
    dependencies=["base-security-rules"],
    tags=["安全", "数据库", "API"],
)

# 保存到文件
import json
with open("团队规范.skill.json", "w") as f:
    json.dump(bundle, f, indent=2)
```

### 验证 Skill

```python
# 安装前验证完整性
result = engine.skill_verify(bundle)
if result["valid"]:
    print(f"Skill '{result['name']}' 验证通过（{result['rule_count']} 条规则）")
else:
    print(f"验证失败：{result['reason']}")
```

### 安装 Skill

```python
# 使用默认作用域安装
result = engine.skill_install(bundle, mode="skip")

# 以公司作用域安装
result = engine.skill_install(bundle, scope_override="company", mode="overwrite")

print(f"已安装：{result['installed']}，已跳过：{result['skipped']}")
```

### 冲突模式

| 模式 | 行为 |
|------|------|
| `skip` | 跳过已存在的规则（默认） |
| `overwrite` | 用新规则替换已有规则 |
| `rename` | 自动重命名冲突规则 |

### CLI 命令

```bash
carrymem skill-pack rules.json --name my-rules --scope company
carrymem skill-verify my-rules.skill.json
carrymem skill-install my-rules.skill.json --scope company --mode skip
```

---

## 合并协议

当来自不同来源的规则冲突时，合并协议负责解决。

### 预览冲突

```python
from carrymem.rules import review_incoming_rules

preview = engine.review_incoming_rules(
    incoming=new_rules,
    target_scope="personal",
)
print(f"冲突：{preview['conflict_count']}")
print(f"无冲突：{preview['no_conflict_count']}")
```

### 执行合并

```python
result = engine.accept_rules(
    incoming=new_rules,
    strategy="negotiate",
    target_scope="personal",
)
print(f"已接受：{result['accepted_count']}")
print(f"已跳过：{result['skipped_count']}")
print(f"已替换：{result['replaced_count']}")
```

### 合并策略

| 策略 | 适用场景 | 行为 |
|------|---------|------|
| `company_overrides` | 严格组织合规 | 高作用域始终获胜 |
| `negotiate` | 协作团队 | 冲突规则适配为 "negotiated" 作用域 |
| `keep_both` | 需要手动审查 | 两条规则都保留，用户稍后决定 |

---

## 记忆整合

随着时间推移，记忆库会积累重复条目、过时条目和低价值记忆。整合功能可以清理和优化记忆库。

### 运行整合

```bash
# 预览整合操作（安全，不修改数据）
carrymem consolidate --dry-run

# 执行整合
carrymem consolidate

# 仅运行去重+衰减（跳过模式晋升和语义合并）
carrymem consolidate --no-p1 --no-p2
```

### 三个阶段

| 阶段 | 功能 | 使用时机 |
|------|------|---------|
| **P0: 去重 + 衰减** | 移除重复记忆（Jaccard ≥0.85），应用时间衰减 | 每日或每周运行 |
| **P1: 模式 → 规则** | 检测重复模式，生成规则候选供审查 | 每周运行 |
| **P2: 语义合并** | 聚类相关记忆，请求宿主 LLM 整合 | 每月运行 |

### 衰减行为

记忆随时间衰减，除非被访问。偏好始终保留。

| 记忆类型 | 半衰期 |
|---------|--------|
| 偏好 | 270 天 |
| 事实、决策、纠正 | 90 天 |
| 情绪 | 45 天 |

### 最佳实践

- 始终先用 `--dry-run` 预览变更
- 在低使用时段运行整合
- 审查 P1 规则候选后再接受
- 偏好永远不会被衰减或去重——你的偏好是永久的

---

## VS Code 扩展

### 安装

1. 打开 VS Code
2. 从 VSIX 安装：`code --install-extension vscode-carrymem-0.3.0.vsix`
3. 或在扩展目录中按 F5 以调试模式运行

### 功能

- **规则侧边栏**：树形视图，带作用域徽章（🛡️ company、🔀 negotiated、👤 personal）
- **规则编辑器**：添加/编辑规则，支持 trigger、action、type、scope、override
- **有效性报告**：HTML 面板，统计和作用域分布
- **Skill 操作**：通过文件对话框打包和安装

### 命令

| 命令 | 说明 |
|------|------|
| `CarryMem: 刷新规则` | 重新加载规则列表 |
| `CarryMem: 添加规则` | 创建新规则 |
| `CarryMem: 编辑规则` | 编辑选中规则 |
| `CarryMem: 删除规则` | 删除选中规则 |
| `CarryMem: 切换规则` | 暂停/恢复规则 |
| `CarryMem: 匹配规则` | 为当前文件匹配规则 |
| `CarryMem: 有效性报告` | 显示统计面板 |
| `CarryMem: Skill 打包` | 导出规则为 Skill |
| `CarryMem: Skill 安装` | 安装 Skill 包 |

---

## CLI 参考

### 记忆命令

```bash
carrymem add "内容"           # 存储记忆
carrymem list                  # 列出记忆
carrymem search "查询"         # 搜索记忆
carrymem show <key>            # 查看记忆详情
carrymem edit <key> "新内容"   # 编辑记忆
carrymem forget <key>          # 删除记忆
carrymem whoami                # 身份画像
carrymem stats                 # 统计
carrymem check                 # 质量检查
carrymem doctor                # 诊断安装
```

### 规则命令

```bash
carrymem add-rule "动作" --trigger "触发器" [--type avoid] [--soft]
carrymem list-rules [--status active] [--type avoid]
carrymem edit-rule <id> [--trigger "新"] [--action "新"]
carrymem delete-rule <id>
carrymem match-rules "场景描述"
carrymem rules-stats
carrymem export-rules output.json
carrymem import-rules input.json
```

### Skill 命令

```bash
carrymem skill-pack <输出文件> --name <名称> [--scope company] [--author "名字"]
carrymem skill-install <输入文件> [--scope company] [--mode skip|overwrite|rename]
carrymem skill-verify <输入文件>
```
