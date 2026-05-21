# CarryMem — 你的 AI 终于认识你了

**别再一遍遍教 AI 你是谁了。**

> 你的随身 AI 记忆 — 偏好、决策和纠正，跨模型、跨工具、跨设备随身携带。

每次开新对话，你都要重新介绍自己。你的偏好、你的决策、你的纠正，全忘了。换工具（Cursor → Claude Code），换模型（GPT → Claude），每次都从零开始。

你不是在用 AI，你是在反复教 AI。

CarryMem 解决这个问题。它是一个轻量级、零依赖的记忆系统，存储**你是谁**，并将这个身份提供给任何 AI 工具。你的 AI 记住你的偏好、你过去的决策和你做过的纠正，让你专注做事，而不是反复自我介绍。

[English](../../README.md) | **中文** | [日本語](README-JP.md)

<p align="center">
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI 版本"></a>
  <img src="https://img.shields.io/badge/tests-2100%20passing-green" alt="测试">
  <img src="https://img.shields.io/badge/coverage-78%25-green" alt="覆盖率">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python">
</p>

---

## 为什么需要 CarryMem？

### 问题：AI 总是忘记你是谁

每次新对话，AI 都从零开始：
- 你偏好深色模式？**忘了。**
- 你上次纠正过？**忘了。**
- 你决定用 React？**忘了。**

换工具（Cursor → Windsurf），换模型（Claude → GPT）— 每次都从零开始。

### 解决方案：CarryMem 身份层

CarryMem 不只是存储文本 — 它理解**你是谁**：

```bash
$ carrymem whoami

  你是谁（根据你的 AI）
  ==================================================

  你的偏好：
    ⭐ 我偏好所有编辑器都用深色模式
    ⭐ 我用 PostgreSQL 做数据库
    ⭐ 我总是用 Python 做数据分析

  你的决策：
    🎯 前端用 React

  你的纠正：
    🔧 端口号应该是 5432

  记忆画像：
    总计: 19 | 主导类型: user_preference | 平均置信度: 73%
```

---

## 快速开始

### 安装

```bash
pip install carrymem
```

> **PyPI 地址**: [https://pypi.org/project/carrymem/](https://pypi.org/project/carrymem/)
>
> **开发模式**: `git clone https://github.com/lulin70/carrymem.git && cd carrymem && pip install -e ".[dev]"`

### 验证安装

```bash
carrymem version
```

**如果提示 `command not found`**，添加 Python bin 到 PATH：

```bash
# macOS（添加到 ~/.zshrc）
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Linux（添加到 ~/.bashrc）
export PATH="$HOME/.local/bin:$PATH"

# 或直接使用 Python 模块
python3 -m carrymem.cli version
```

然后运行 `carrymem doctor` 检查配置。

### 5 行代码

> ⚠️ **包名与导入名**：安装用 `pip install carrymem`，导入用 `from carrymem import CarryMem` 或 `from carrymem import CarryMem`。将在 v1.0.0 统一。

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("我偏好深色模式")              # 自动分类为偏好
cm.classify_and_remember("用 PostgreSQL 不用 MySQL")    # 自动分类为纠正
memories = cm.recall_memories("数据库")                  # 语义召回
print(cm.build_system_prompt())                          # 注入任何 AI
cm.close()
```

### 命令行（22+ 命令）

```bash
carrymem init                           # 初始化
carrymem add "我偏好深色模式"            # 存储记忆
carrymem add "测试笔记" --force         # 强制存储（跳过分类）
carrymem list                           # 列出记忆
carrymem search "主题"                  # 搜索记忆
carrymem show <key>                     # 查看记忆详情
carrymem edit <key> "新内容"            # 编辑记忆
carrymem forget <key>                   # 删除记忆
carrymem whoami                         # AI 认为你是谁
carrymem profile export --output identity.json   # 导出 AI 身份
carrymem stats                          # 记忆统计
carrymem check                          # 质量与冲突检查
carrymem clean --expired --dry-run      # 预览清理
carrymem doctor                         # 诊断安装
carrymem setup-mcp --tool cursor        # 一行配置 MCP
carrymem tui                            # 终端界面
carrymem export backup.json             # 导出所有记忆
carrymem import backup.json             # 导入记忆
carrymem version                        # 显示版本
# 规则引擎命令
carrymem add-rule "始终使用SSL" --trigger "数据库" --type avoid   # 添加规则
carrymem list-rules --status active                      # 列出活跃规则
carrymem skill-pack rules.json --name team-conventions   # 打包规则为 Skill
carrymem skill-install team-conventions.json --scope company  # 安装 Skill
carrymem skill-verify team-conventions.json              # 验证 Skill 完整性
```

---

## 核心功能

### 1. 自动分类（7 种记忆类型）

CarryMem 自动识别你分享的信息类型：

| 类型 | 图标 | 示例 |
|------|------|------|
| `user_preference` | ⭐ | "我偏好深色模式" |
| `correction` | 🔧 | "不对，是 Python 3.11 不是 3.10" |
| `decision` | 🎯 | "前端用 React" |
| `fact_declaration` | 📌 | "我在东京的一家创业公司工作" |
| `task_pattern` | 🔄 | "我总是先写测试" |
| `relationship` | 👥 | "张三偏好深色模式" |
| `sentiment_marker` | 💡 | "对微服务方案持积极态度" |

### 2. 语义召回（跨语言）

```python
cm.classify_and_remember("我偏好使用PostgreSQL")

# 以下查询都能找到：
cm.recall_memories("PostgreSQL")     # 精确匹配
cm.recall_memories("数据库")          # 同义词扩展
cm.recall_memories("Postgres")       # 拼写纠正
cm.recall_memories("データベース")    # 跨语言（日语）
```

### 3. 身份层（whoami）

```python
identity = cm.whoami()
print(identity["preferences"])   # ["我偏好深色模式", ...]
print(identity["decisions"])     # ["前端用 React", ...]
print(identity["corrections"])   # ["端口号应该是 5432", ...]
```

### 4. 重要性评分与生命周期

每条记忆都有随时间演化的重要性评分：

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30天半衰期衰减** — 旧记忆逐渐淡出，除非被访问
- **访问强化** — 频繁召回的记忆保持新鲜
- **类型加权** — 纠正(1.3x) > 决策(1.2x) > 偏好(1.1x)

### 5. 质量管理

```bash
carrymem check                    # 全面检查
carrymem check --conflicts        # 检测矛盾
carrymem check --quality          # 发现低质量记忆
carrymem check --expired          # 发现过期记忆
carrymem clean --expired --dry-run # 预览清理
```

### 6. 安全与可靠性

| 特性 | 说明 |
|------|------|
| **加密** | AES-128 (Fernet) 或 HMAC-CTR 降级，零依赖 |
| **备份** | 零停机 SQLite VACUUM INTO |
| **审计日志** | 只追加操作历史 |
| **版本历史** | 每次编辑追踪，支持回滚 |
| **输入验证** | SQL注入、XSS、路径遍历防护 |

### 7. MCP 集成（一行配置）

```bash
# 配置 Cursor
carrymem setup-mcp --tool cursor

# 配置 Claude Code
carrymem setup-mcp --tool claude-code

# 配置所有工具
carrymem setup-mcp --tool all
```

25 个 MCP 工具：Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (1) · Rules (11)

### 8. 规则引擎与作用域

行为规则支持三个作用域级别，实现团队/组织对齐：

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# 公司强制规则（最高优先级，不可被覆盖）
engine.add_rule("数据库", "始终使用SSL连接", scope="company", override=True)

# 个人偏好（最低优先级）
engine.add_rule("数据库", "偏好PostgreSQL", scope="personal")

# 作用域感知匹配
results = engine.match("数据库设计", scopes=["company"])
```

| 作用域 | 优先级 | 说明 |
|--------|--------|------|
| `company` | 3（最高） | 组织强制规则，不可被覆盖 |
| `negotiated` | 2 | 从公司规则适配而来 |
| `personal` | 1（最低） | 用户创建的偏好 |

### 9. Skill 格式 — 便携规则包

通过加密完整性验证跨团队共享规则集：

```python
# 打包规则为便携 Skill 包
bundle = engine.skill_pack(
    name="团队规范",
    version="1.0.0",
    scope="company",
    author="团队负责人",
)

# 安装前验证完整性
result = engine.skill_verify(bundle)
assert result["valid"] is True

# 在另一台机器上安装
engine.skill_install(bundle, scope_override="company", mode="skip")
```

### 10. 合并协议 — 冲突解决

三种策略合并来自不同来源的规则：

| 策略 | 说明 |
|------|------|
| `company_overrides` | 高作用域始终获胜 |
| `negotiate` | 冲突规则适配为 "negotiated" 作用域 |
| `keep_both` | 两条规则都保留，用户手动审查 |

### 11. VS Code 扩展

直接在编辑器中管理规则：

- 规则侧边栏，带作用域徽章
- 通过 Webview 添加/编辑/删除规则
- 有效性报告面板
- Skill 打包/安装文件对话框

### 12. 终端界面

```bash
pip install textual
carrymem tui
```

交互式终端界面，侧边栏过滤、搜索、添加模式。

---

## 架构

```
用户输入
    ↓
自动分类（7 种类型，4 层）
    ↓
重要性评分（confidence × type × recency × access）
    ↓
智能存储（SQLite + FTS5，去重，TTL，加密）
    ↓
记忆整合（P0: 去重+衰减 → P1: 模式→规则 → P2: 语义合并）
    ↓
语义召回（FTS5 + 同义词 + 拼写纠正 + 跨语言）
    ↓
上下文注入（token 预算，相关性排序）
    ↓
AI 工具（Cursor / Claude Code / 任意 MCP 客户端）
```

---

## 竞品对比

|  | CarryMem | Mem0 | OpenChronicle | ima |
|--|----------|------|---------------|-----|
| **零依赖** | ✅ 仅 SQLite | ⚠️ 可选向量数据库 | ✅ | ❌ 云端 |
| **自动分类** | ✅ 7 种类型 | ❌ | ❌ 手动 | ❌ |
| **身份画像** | ✅ whoami | ❌ | ❌ | ❌ |
| **规则引擎** | ✅ 作用域 + Skill | ❌ | ❌ | ❌ |
| **Skill 格式** | ✅ SHA-256 签名 | ❌ | ❌ | ❌ |
| **合并协议** | ✅ 3 种策略 | ❌ | ❌ | ❌ |
| **VS Code 扩展** | ✅ | ❌ | ❌ | ❌ |
| **命令行** | ✅ 22+ 命令 | ❌ | ❌ | ❌ |
| **终端界面** | ✅ textual | ❌ | ❌ | ✅ App |
| **加密** | ✅ 内置 | ❌ | ❌ | ❌ |
| **版本历史** | ✅ 回滚 | ❌ | ❌ | ❌ |
| **冲突检测** | ✅ 内置 | ❌ | ❌ | ❌ |
| **数据所有权** | ✅ 本地文件 | ⚠️ 自托管 | ✅ 本地 | ❌ 云端 |
| **5 行代码接入** | ✅ | ⚠️ 需要 SDK | ❌ | ❌ |
| **跨语言召回** | ✅ 中/英/日 | ❌ | ❌ | ❌ |

> **注**：对比基于公开信息。产品迭代迅速，请核实最新功能。

**核心差异**：其他产品存储*你读了什么*。CarryMem 记住*你是谁*。

---

### 🏆 Benchmark — v0.2.0 基线

| Benchmark | 得分 | 说明 |
|-----------|------|------|
| **PrefEval** | **96.0%** | ICLR 2025 Oral，50 样本，偏好遵守率（zero-shot: 90%，reminder: 92%） |
| **LongMemEval** | **42.6%** | 官方 oracle 数据集，500 题 |
| **RuleEngine-Eval** | **93.3%** | CarryMem 原创基准 — 唯一拥有规则引擎的记忆系统 |
| **MemEval** | *运行中* | 官方框架，CarryMem 适配器 |
| **MSC** | *待定* | 数据集受限 |

| | 优势 | 结果 |
|---|------|------|
| 💰 | 零 LLM 摄入 | **88%** 记忆无需 **LLM Token** |
| ⚡ | P99 延迟 | **1.3ms** — 比 Mem0 **快 93 倍** |
| 🪶 | 依赖 | **仅需 SQLite** — 无需向量数据库 |
| 🛡️ | 规则引擎 | **唯一拥有**规则引擎（竞争对手：0%） |

> **透明优先。** 首次运行基线分数，不完美但诚实。完整数据：[BENCHMARK_STRATEGY_FINAL.md](../BENCHMARK_STRATEGY_FINAL.md)

---

## 适合谁？

**厌倦了反复自我介绍？**
你每天用 Cursor、Claude Code、ChatGPT。你的技术栈、编码风格、架构决策，你告诉 AI 一百遍了，它还在问"你偏好什么框架？"CarryMem 让你的 AI 记住这些，不用再说第二遍。

**在手动维护 CLAUDE.md？**
你已经知道 AI 需要记忆。你到处都是 prompt 文件，它们互相矛盾，会过时，而且换工具就失效。CarryMem 自动分类你的偏好、决策和纠正，并自动保持更新。

**在开发 AI Agent？**
你的 Agent 在会话之间会忘记用户。你需要一个轻量、本地、兼容任何 LLM 的记忆层。CarryMem 提供 5 行代码接入、7 种记忆类型和规则引擎，除了 SQLite 外零依赖。

---

## 文档

- [快速入门指南](../QUICK_START_GUIDE.md)
- [安装指南](../INSTALL.md)
- [用户指南](../USER_GUIDE.md)
- [架构设计](../ARCHITECTURE.md)
- [API 参考](../API_REFERENCE.md)
- [API 稳定性策略](../API_STABILITY.md)
- [路线图](ROADMAP-CN.md)
- [贡献指南](../../CONTRIBUTING.md)

---

## 项目状态

**当前版本**：v0.2.0
**测试**：2100+ passing
**覆盖率**：~78%

**更新日志**：
- **v0.2.0**：记忆整合引擎（P0/P1/P2），PrefEval 96.0%，偏好注入修复，25 个 MCP 工具
- **v0.2.0**：版本重置 — 安全加固（FTS5查询净化、路径验证、规则内容过滤）、线程安全、文档整理、测试清理
- **v0.4.1**：核心循环修复 — 自动规则建议、MCP 规则工具、提示注入防护、连接池
- **v0.4.0**：企业功能 — 规则作用域、Skill 格式（SHA-256）、合并协议、VS Code 扩展
- **v0.3.0**：GA 发布 — 知识适配器、有效性报告、上下文工程
- **v0.2.6**：经验学习 — 失败→规避规则、learn-experience/review-lessons CLI
- **v0.2.5**：自动提升管道 — 记忆模式→规则候选、promotion-log CLI
- **v0.2.4**：从记忆中检测模式、suggest-rules CLI、候选规则生成器
- **v0.2.3**：导出/导入规则、交互式 CLI、规则模板、edit-rule、12 个 CLI 命令
- **v0.2.2**：性能基准 + 冲突检测（check-rules 命令）
- **v0.2.1**：规则引擎 Alpha — 手动 CRUD、FTS5 匹配、安全、8 个 CLI 命令
- **v0.2.0**：PyPI 发布、身份层（whoami、profile 导出）、490 测试

---

## 贡献

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
pytest
```

详见 [贡献指南](../../CONTRIBUTING.md)。

---

## 许可证

MIT 许可证 — 详见 [LICENSE](../../LICENSE)

---

**CarryMem — 你的 AI 终于认识你了。只有你拥有数据。**
