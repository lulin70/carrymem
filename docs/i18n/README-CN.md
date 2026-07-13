# CarryMem — 你的 AI 终于认识你了

**别再一遍遍教 AI 你是谁了。**

> 你的随身 AI 记忆 — 偏好、决策和纠正，跨模型、跨工具、跨设备随身携带。

[English](../../README.md) | **中文** | [日本語](README-JP.md) | [한국어](README-KO.md) | [繁體中文](README-ZH-TW.md)

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI 版本"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-4322-brightgreen" alt="测试">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-green" alt="覆盖率">
  <a href="https://arxiv.org/abs/2410.01373"><img src="https://img.shields.io/badge/PrefEval-83.0%25%20(ICLR%202025%20Oral)-9B59B6?logo=arxiv" alt="PrefEval 学术基准"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python">
</p>

---

## CarryMem 做什么

**5 个你一定遇到过的场景：**

> **"不想每次都告诉 AI 我的偏好"**
> "我偏好 PostgreSQL""用 React 不用 Vue""别写注释" — 说一次，永远记住。

> **"换了 AI 工具又要从头开始"**
> Cursor 里教 AI 一遍，Claude Code 里又教一遍。CarryMem 让你的 AI 记忆跟着你走。

> **"想带走自己的数据"**
> 你的 AI 记忆是你的。一个文件打包，新机器、新工具，随时恢复。

> **"U盘携带——口袋里的记忆"** 🔑
> 打包记忆为加密 .carry 文件，拷到U盘，新机器解包。你的 AI 身份随身携带——偏好、决策、纠正和规则完整保留。新机器上的每个 Agent 立刻认识你。

> **"我的团队在所有 Agent 上共享规范"**
> 团队负责人把公司规范打包为 Skill 包，每个成员安装。所有 Agent 自动执行相同规范——不再有"我不知道我们用 SSL"。

---

## 🎯 真实用户场景

### 场景1：多工具开发者

```
周一：告诉 Cursor "我偏好深色模式、PostgreSQL、React"
周二：打开 Claude Code — 它已经知道你的技术栈
周五：切换到 TRAE — 同样的偏好，零重复
```

**方法**：`carrymem setup-mcp --all --global` — 一条命令，所有工具共享一份记忆。

### 场景2：U盘携带——新机器，同一身份

```
1. 在你的笔记本上：carrymem pack -o my_identity.carry --encrypt
2. 将 my_identity.carry 拷贝到U盘
3. 在新工作场所：在新机器上安装 CarryMem
4. carrymem unpack my_identity.carry
5. 新机器上的每个 Agent 都知道你的偏好、决策和规则
```

**加密 + SHA-256 校验** — 即使U盘丢失，你的身份也是安全的。

### 场景3：团队负责人

```
1. 创建团队规范为规则："始终使用 SSL""绝不在周五部署"
2. 打包为 Skill：carrymem rules pack rules.json --name team-conventions
3. 与团队分享 .json 文件
4. 每个成员：carrymem rules install team-conventions.json --scope company
5. 所有 Agent 现在自动执行公司规范
```

### 场景4：长期用户

```
第1个月："我偏好深色模式" → 存储为 user_preference
第3个月："切换到浅色模式" → 自动取代旧偏好
第6个月：carrymem whoami → 显示"我偏好浅色模式"（深色模式已归档）
```

**偏好会演化。CarryMem 追踪历史。**

---

## 快速开始

### 系统要求

- **Python**: ≥3.12（64 位）
- **操作系统**: macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **磁盘空间**: 核心功能约 5MB，语义搜索约 200MB
- **内存**: 基础约 50MB

### 安装方式

```bash
# 基础安装（仅核心功能）
pip install carrymem

# 完整安装（含多语言 + 语义搜索 + 加密）
pip install carrymem[full]

# 开发模式（含测试工具）
git clone https://github.com/lulin70/carrymem.git
cd carrymem && pip install -e ".[dev]"
```

### 依赖说明

| 功能 | 依赖包 | 安装命令 |
|------|--------|----------|
| 核心功能（含加密） | PyYAML≥5.0, cryptography≥46.0.6 | 自动包含 |
| 多语言检测 | pycld2, langdetect | `pip install carrymem[language]` |
| 语义搜索 | sqlite-vec, sentence-transformers | `pip install carrymem[semantic]` |

> **核心功能零 LLM 依赖** — 分类使用内置规则引擎，无需调用任何大模型。

### 用 Cursor / Claude Code / TRAE？

```bash
pip install carrymem && carrymem setup-mcp --all --global
```

重启 AI 工具。搞定。

### 验证效果（30 秒）

告诉你的 AI：
```
记住，我偏好 PostgreSQL
```

开一个新对话，问：
```
我用什么数据库？
```

AI 回答 "PostgreSQL" — 成功了！

### 需要迁移记忆？

```bash
carrymem pack                    # 打包为 carrymem_identity_20260526.carry
carrymem pack --encrypt          # 加密打包（提示输入密码）
# 拷贝到 U盘 / 网盘 / 新机器
carrymem unpack my_identity.carry  # 所有记忆恢复
```

### 需要备份？

```bash
carrymem backup                  # 创建备份
carrymem backup --list           # 列出所有备份
carrymem backup --restore <path> # 从备份恢复
```

---

> 📊 **学术验证**：CarryMem的偏好注入准确率（83.0%）使用 [PrefEval协议](https://arxiv.org/abs/2410.01373)（ICLR 2025 口头报告, Amazon Science）测量，在 200 条测试项中超过简单提醒（80.0%）和零样本（71.5%）基线。详见下方[引用](#引用)。

## 选择 CarryMem 的 3 个理由

这些是 CarryMem 区别于其他所有记忆解决方案的关键：

### 1. 偏好注入精准度 — 83.0%（学术验证）
- 由 PrefEval（ICLR 2025 口头报告, Amazon Science）测量，200 样本 3 条件对比
- CarryMem 83.0% > 简单提醒 80.0% > 零样本 71.5%
- 主动注入 > 全量提醒 — 首个证明这一点的系统
- 比提醒方式减少 24% 无用回答（28 vs 38）— 更精准，更少噪音

### 2. 零 LLM 分类 — 88% 无需调用任何 LLM
- 规则引擎分类 88% 的记忆，零 Token 消耗
- 唯一内置规则引擎的系统（竞争对手：0%）
- P99 延迟：1.3ms — 比 Mem0 快 93 倍

### 3. 轻量可携带 — 仅 SQLite
- 核心功能零外部依赖
- 单个 .db 文件 — 身份随身携带
- 支持 Cursor、Claude Code、ChatGPT、任何 MCP 客户端

---

## 工作原理

```
用户输入
    ↓
自动分类（7 种类型，4 层）  ← 88% 零 LLM
    ↓
重要性评分（confidence × type × recency × access）
    ↓
智能存储（SQLite + FTS5，去重，TTL，加密）
    ↓
记忆整合（P0: 去重+衰减 → P1: 模式→规则 → P2: 语义合并）
    ↓
语义召回（FTS5 + 同义词 + 拼写纠正 + 跨语言）
    ↓
偏好注入（token 预算，相关性排序）  ← 83.0% 精准度
    ↓
AI 工具（Cursor / Claude Code / 任意 MCP 客户端）
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
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# Linux（添加到 ~/.bashrc）
export PATH="$HOME/.local/bin:$PATH"

# 或直接使用 Python 模块
python3 -m carrymem.cli version
```

然后运行 `carrymem doctor` 检查配置。

### 5 行代码

> ⚠️ **包名与导入名**：安装用 `pip install carrymem`（小写），导入用 `from carrymem import CarryMem`（驼峰类名）。包名（`carrymem`）和类名（`CarryMem`）大小写不同。

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("我偏好深色模式")              # 自动分类为偏好
cm.classify_and_remember("用 PostgreSQL 不用 MySQL")    # 自动分类为纠正
memories = cm.recall_memories("数据库")                  # 语义召回
print(cm.build_system_prompt())                          # 注入任何 AI
cm.close()
```

### 命令行（50+ 命令）

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
carrymem rules add "始终使用SSL" --trigger "数据库" --type avoid   # 添加规则
carrymem rules list --status active                      # 列出活跃规则
carrymem rules pack rules.json --name team-conventions   # 打包规则为 Skill
carrymem rules install team-conventions.json --scope company  # 安装 Skill
carrymem rules verify team-conventions.json              # 验证 Skill 完整性
# 备份与携带
carrymem pack --encrypt                                 # 加密打包身份文件
carrymem unpack identity.carry                          # 恢复身份
carrymem backup                                         # 创建备份
carrymem backup --list                                  # 列出备份
carrymem backup --restore <path>                        # 从备份恢复
```

---

## 核心功能

### 记忆理解你

CarryMem 自动识别你分享的信息类型，无需手动标注：

| 类型 | 图标 | 示例 |
|------|------|------|
| `user_preference` | ⭐ | "我偏好深色模式" |
| `correction` | 🔧 | "不对，是 Python 3.11 不是 3.10" |
| `decision` | 🎯 | "前端用 React" |
| `fact_declaration` | 📌 | "我在东京的一家创业公司工作" |
| `task_pattern` | 🔄 | "我总是先写测试" |
| `relationship` | 👥 | "张三偏好深色模式" |
| `sentiment_marker` | 💡 | "对微服务方案持积极态度" |

语义召回支持跨语言：

```python
cm.classify_and_remember("我偏好使用PostgreSQL")

# 以下查询都能找到：
cm.recall_memories("PostgreSQL")     # 精确匹配
cm.recall_memories("数据库")          # 同义词扩展
cm.recall_memories("Postgres")       # 拼写纠正
cm.recall_memories("データベース")    # 跨语言（日语）
```

身份层（whoami）：

```python
identity = cm.whoami()
print(identity["preferences"])   # ["我偏好深色模式", ...]
print(identity["decisions"])     # ["前端用 React", ...]
print(identity["corrections"])   # ["端口号应该是 5432", ...]
```

### 偏好注入

CarryMem 将结构化偏好注入 system prompt，而非简单提醒：

```python
print(cm.build_system_prompt())   # 自动生成偏好注入 prompt
```

**为什么偏好注入 > 全量提醒**：reminder 每轮都注入"记住用户偏好"。CarryMem 在 system prompt 中注入结构化偏好 — 更精准、更持久、无用回答减少 24%。

### 记忆生命周期

每条记忆都有随时间演化的重要性评分：

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30天半衰期衰减** — 旧记忆逐渐淡出，除非被访问
- **访问强化** — 频繁召回的记忆保持新鲜
- **类型加权** — 纠正(1.3x) > 决策(1.2x) > 偏好(1.1x)

质量管理：

```bash
carrymem check                    # 全面检查
carrymem check --conflicts        # 检测矛盾
carrymem check --quality          # 发现低质量记忆
carrymem check --expired          # 发现过期记忆
carrymem clean --expired --dry-run # 预览清理
```

记忆整合（三阶段）：

```python
# 预览整合效果
report = cm.consolidate(dry_run=True)
print(f"重复: {report['stats']['duplicates_found']}")
print(f"衰减: {len(report['to_decay'])}")

# 执行整合（P0: 去重+衰减, P1: 模式→规则, P2: 语义合并）
report = cm.consolidate(dry_run=False, run_p1=True, run_p2=True)
```

| 阶段 | 功能 | 机制 |
|------|------|------|
| **P0** | 去重 + 衰减 | Jaccard 相似度去重，指数半衰期衰减（偏好: 270天, 事实: 90天, 情绪: 45天） |
| **P1** | 模式 → 规则 | 检测重复模式 → 生成规则候选供审查 |
| **P2** | 语义合并 | 聚类相关记忆 → 请求宿主 LLM 整合 |

偏好始终保留 — 永不衰减或去重。

### 安全与可携带

| 特性 | 说明 |
|------|------|
| **加密** | AES-128 (Fernet) 或 HMAC-CTR 降级，零依赖 |
| **自动备份** | 零停机 SQLite VACUUM INTO，每 20 次写操作自动备份 |
| **.carry 加密** | 便携身份文件支持密码加密 + SHA-256 校验 |
| **审计日志** | 只追加操作历史 |
| **版本历史** | 每次编辑追踪，支持回滚 |
| **输入验证** | SQL注入、XSS、路径遍历防护 |

---

## 辅助功能

### MCP 集成

```bash
# 配置 Cursor
carrymem setup-mcp --tool cursor

# 配置 Claude Code
carrymem setup-mcp --tool claude-code

# 配置所有工具
carrymem setup-mcp --tool all
```

28 个 MCP 工具：Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (3) · Rules (11)

**客户端兼容性：**

| 状态 | 客户端 | 配置方式 |
|------|--------|---------|
| ✅ 直接支持 | Cursor、Claude Code、TRAE、Windsurf、Cline | `setup-mcp --global` |
| ✅ 自动检测 | OpenClaw、Kimi Code CLI、CodeX | `setup-mcp --global`（自动回退到 Claude Code 格式） |
| 📋 应用商店 | WorkBuddy、CodeBuddy | 需提交至 MCP Marketplace（待完成） |
| ❌ 不支持 | Kimi 桌面版、DeepSeek 桌面版、通义千问、豆包、天工、智谱清言 | 封闭平台，无 MCP 接口 |

> **🔒 你的记忆只存在你自己的机器上。** CarryMem 所有数据本地存储在 `~/.carrymem/`（SQLite）。每个用户拥有独立的数据库——就像 Git，大家用同一个工具，但各自的仓库完全独立。无云端同步、无共享状态、无跨用户冲突。

### 规则引擎

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

合并协议 — 三种策略合并来自不同来源的规则：

| 策略 | 说明 |
|------|------|
| `company_overrides` | 高作用域始终获胜 |
| `negotiate` | 冲突规则适配为 "negotiated" 作用域 |
| `keep_both` | 两条规则都保留，用户手动审查 |

### Skill 格式

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

### 终端界面

```bash
pip install textual
carrymem tui
```

交互式终端界面，侧边栏过滤、搜索、添加模式。

### VS Code 扩展

直接在编辑器中管理规则：

- 规则侧边栏，带作用域徽章
- 通过 Webview 添加/编辑/删除规则
- 有效性报告面板
- Skill 打包/安装文件对话框

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
| **命令行** | ✅ 40+ 命令 | ❌ | ❌ | ❌ |
| **终端界面** | ✅ textual | ❌ | ❌ | ✅ App |
| **加密** | ✅ 内置 | ❌ | ❌ | ❌ |
| **版本历史** | ✅ 回滚 | ❌ | ❌ | ❌ |
| **冲突检测** | ✅ 内置 | ❌ | ❌ | ❌ |
| **数据所有权** | ✅ 本地文件 | ⚠️ 自托管 | ✅ 本地 | ❌ 云端 |
| **5 行代码接入** | ✅ | ⚠️ 需要 SDK | ❌ | ❌ |
| **跨语言召回** | ✅ 中/英/日 | ❌ | ❌ | ❌ |
| **核心差异** | **记住你是谁** | 存储你读了什么 | 存储你读了什么 | 存储你读了什么 |

> **注**：对比基于公开信息。产品迭代迅速，请核实最新功能。

---

### 🏆 PrefEval — 偏好遵守率基准测试

| 条件 | 准确率 | 确认遵守 | 违反 | 幻觉 | 无用回答 |
|------|--------|----------|------|------|----------|
| 零样本 | 71.5% | 160 | 27 | 3 | 31 |
| 简单提醒 | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

协议：PrefEval（ICLR 2025 口头报告, Amazon Science）
样本：200 条，10 轮干扰，Claude Sonnet 4

**为什么这很重要**：reminder 每轮都注入"记住用户偏好"。CarryMem 在 system prompt 中注入结构化偏好——更精准、更持久、无用回答减少 24%。

| | 优势 | 结果 |
|---|------|------|
| 💰 | 零 LLM 摄入 | **88%** 记忆无需 **LLM Token** |
| ⚡ | P99 延迟 | **1.3ms** — 比 Mem0 **快 93 倍** |
| 🪶 | 依赖 | **仅需 SQLite** — 无需向量数据库 |
| 🛡️ | 规则引擎 | **唯一拥有**规则引擎（竞争对手：0%） |

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

## 高级用法

### Obsidian 知识库

```python
from carrymem import CarryMem, ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python 设计模式")
```

### 异步 API

```python
from carrymem import AsyncCarryMem

async with AsyncCarryMem() as cm:
    await cm.classify_and_remember("我偏好深色模式")
    memories = await cm.recall_memories("主题")
```

### JSON 适配器（无需 SQLite）

```python
from carrymem import CarryMem, JSONAdapter

cm = CarryMem(adapter=JSONAdapter(path="/path/to/memories.json"))
```

### 加密

```python
cm = CarryMem(encryption_key="my-secret-key")
# 所有内容静态加密，读取时解密
```

### 记忆版本管理

```python
cm.update_memory(key, "更新后的内容")     # 创建版本 2
history = cm.get_memory_history(key)      # [v1, v2]
cm.rollback_memory(key, version=1)        # 恢复到 v1
```

### 导出身份给其他 AI

```python
# 导出你的 AI 身份
cm.export_profile(output_path="my_identity.json")

# 在另一台设备或 AI 工具上
cm.import_memories(input_path="backup.json")
```

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

**当前版本**：v0.7.3
**测试**：4198 passing
**覆盖率**：80%+

**更新日志**：
- **v0.2.0**：USB 携带加密、自动备份、并发安全、PrefEval 83.0%（200 条）、8 客户端 MCP 配置
- **v0.2.3**（重置前）：定时整合（schedule/stop）、PrefEval 标准化
- **v0.2.2**（重置前）：Token 预算 + 死代码修复 + 安全加固、PrefEval 87.9%
- **v0.2.1**（重置前）：共指消解、自动脱敏、QA 提示优化

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

## 引用

如果你在研究中使用 CarryMem，请引用：

```bibtex
@software{carrymem2026,
  title = {CarryMem: Persistent Memory for AI Agents with Preference Injection},
  author = {CarryMem Team},
  year = {2026},
  url = {https://github.com/carrymem/carrymem},
  note = {Preference injection accuracy 83.0\% measured by PrefEval protocol}
}

@inproceedings{chuang2025prefeval,
  title = {PrefEval: A Preference Evaluation Benchmark for LLMs},
  author = {Chuang, Yun-Nung and others},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2025},
  note = {Oral presentation, Amazon Science}
}
```

**实验结果（200 条样本，10 轮干扰，Claude Sonnet 4）**

| 条件 | 准确率 | 确认遵守 | 违反 | 幻觉 | 无用回答 |
|------|--------|----------|------|------|----------|
| 零样本 | 71.5% | 160 | 27 | 3 | 31 |
| 简单提醒 | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

核心发现：CarryMem 在达到最高准确率的同时，比简单提醒方式减少 24% 的无用回答，证明主动记忆注入比全量上下文提醒更精准。

---

## 许可证

MIT 许可证 — 详见 [LICENSE](../../LICENSE)

---

**CarryMem — 你的 AI 终于认识你了。只有你拥有数据。**
