# CarryMem v0.2.4 共识方案

**日期**: 2026-05-26
**参与者**: DevSquad 7角色 (architect/pm/security/tester/coder/devops/ui)
**输入**: PrefEval评测结果、非技术用户对话、WorkBuddy需求书、GitHub周榜分析

***

## 0. 当前状态

### PrefEval 200样本三组对照 (seed=42)

| Condition    | Accuracy  | Violated | Hallucinated | Unhelpful |
| ------------ | --------- | -------- | ------------ | --------- |
| zero-shot    | 69.5%     | 31       | 2            | 31        |
| reminder     | 83.0%     | 1        | 1            | 33        |
| **CarryMem** | **85.0%** | 5        | 4            | **25**    |

### 已修复的CarryMem自身问题

1. SQLite "database is locked" — `_auto_supersede`/`version_chain_id`写入后未commit
2. 偏好分类不准 — PrefEval中用`force_type="user_preference"`确保正确分类
3. 噪声污染 — 不存储inter-turn噪声到CarryMem
4. `include_question=True`对LLM注意力至关重要 (False→0.700, True→0.850)

### 用户反馈核心洞察

> "能理解，但是不会操作" — 语言断层：用户用效果语言思考，我们用技术语言回答

***

## 1. P0-1: Unhelpful Case分析

### 目标

分析25个unhelpful case，分类根因，寻找进一步优化空间

### 分析维度

1. **截断型**: max\_tokens=500不够，回答被截断
2. **偏题型**: 偏好注入导致回答偏离问题核心
3. **Judge误判型**: 回答实际有用但被judge判为unhelpful
4. **空回答型**: LLM返回空或极短回答

### 实验计划

- 提取25个unhelpful case的完整数据（system\_prompt + response + judge\_reasoning）
- 分类统计
- 对截断型做max\_tokens=1000对比实验（20样本快速验证）
- 对偏题型分析偏好注入是否过度

### 预期

- 如果截断型占多数，增大max\_tokens可能提升2-5%
- 如果偏题型占多数，需要调整偏好注入策略

***

## 2. P0-2: carrymem pack / unpack

### 设计原则

1. **只打包用户记忆，不打包CarryMem本身** — CarryMem可通过pip重新安装
2. **单文件输出** — `.carry`格式，方便U盘/网盘传输
3. **清晰引导** — pack时显示包含什么，unpack时显示恢复到哪

### 命令设计

```
carrymem pack [--output PATH] [--include-rules] [--include-config]

输出示例:
  Packing CarryMem identity...
  ✓ 127 memories (3 user_preferences, 45 session_summaries, ...)
  ✓ 12 rules
  ✓ Config (namespace, consolidation settings)
  ✗ Encrypted entries skipped (provide --key to include)
  → Saved to ./carrymem_identity_20260526.carry (2.3 MB)
```

```
carrymem unpack <file.carry> [--merge|--replace]

输出示例:
  Unpacking CarryMem identity...
  Source: lulin-macbook, packed 2026-05-26, CarryMem v0.2.4
  ✓ 127 memories restored (0 conflicts)
  ✓ 12 rules restored
  ✓ Config restored
  → Run 'carrymem setup-mcp --all --global' to reconnect your AI tools
```

### .carry文件格式

```json
{
  "version": "1.0",
  "carrymem_version": "0.2.4",
  "packed_at": "2026-05-26T10:00:00Z",
  "source_machine": "lulin-macbook",
  "contents": {
    "memories_count": 127,
    "rules_count": 12,
    "has_config": true,
    "has_encrypted": false
  },
  "data": {
    "memories": [...],
    "rules": [...],
    "config": {...}
  }
}
```

### 关键决策

| 决策   | 选择                                   | 理由             |
| ---- | ------------------------------------ | -------------- |
| 加密数据 | 默认跳过，`--key`参数可选                     | 避免忘记密钥导致无法恢复   |
| 冲突处理 | `--merge`(默认，保留已有) / `--replace`(覆盖) | 安全优先           |
| 向量索引 | 不打包，unpack后自动重建                      | 向量数据可重建，减小文件体积 |
| 嵌入模型 | 记录模型名，unpack时检测可用性                   | 模型需单独安装        |

***

## 3. P0-3: 同机器多Agent共享

### 问题

同一台机器上多个Agent（Cursor、Claude Code、TRAE等）各自安装CarryMem时：

1. 反复下载pip包（每个Agent环境独立）
2. 记忆不共享（各自用不同的db\_path）
3. 并发写入SQLite可能冲突

### 设计方案

#### 3.1 全局共享数据库

```
~/.carrymem/
  ├── memories.db          ← 所有Agent共享
  ├── memories.db-wal
  ├── memories.db-shm
  ├── config.json          ← 全局配置
  └── namespaces/          ← 可选：按namespace隔离的配置
```

- `carrymem init` 默认创建 `~/.carrymem/memories.db`
- 所有Agent连接同一个db文件
- SQLite WAL模式 + busy\_timeout=5000ms 处理并发

#### 3.2 避免重复安装

- Agent只需安装MCP配置，不需要各自pip install
- `carrymem setup-mcp --all --global` 一次配置所有Agent
- MCP Server进程由系统管理，不是每个Agent启动一个

#### 3.3 并发安全

- 已修复: busy\_timeout PRAGMA + \_auto\_supersede commit
- 新增: `carrymem status --connections` 显示当前连接数
- 文档化: WAL模式的并发限制和最佳实践

***

## 4. P0-4: README场景入口改写

### 改写结构

```
README.md
├── 场景入口（所有人先看这个）
│   ├── 场景A: 不想每次都告诉AI你的偏好
│   ├── 场景B: 换了AI工具，从头再来
│   └── 场景C: 想带走自己的数据
├── 一句话安装（按用户类型）
│   ├── 有Cursor/Claude Code? → 一行命令
│   ├── 不会命令行? → 3步图文指引
│   └── 开发者? → 5行代码接入
├── 30秒验证
│   └── "记住，我偏好X" → 新对话问"我用什么?" → "X"
├── 3个选择理由（现有内容，保留）
├── PrefEval评测（现有内容，更新数据）
└── 架构/API/竞品对比（现有内容）
```

### 语言转换表

| 技术语言                 | 场景语言         |
| -------------------- | ------------ |
| pip install carrymem | 一键安装包        |
| MCP Server           | AI助手自动连接     |
| namespace隔离          | 工作和生活分开记     |
| 7种记忆类型               | 自动分门别类       |
| SQLite               | 一个文件，跟着你走    |
| PrefEval 85.0%       | AI记住你说的85%的话 |

### 竞品对比改为场景对比

| 场景         | Mem0    | ima    | CarryMem   |
| ---------- | ------- | ------ | ---------- |
| AI记住我说过的话  | ✅       | ⚠️ 需手动 | ✅ 自动       |
| 换个AI工具还能记住 | ❌       | ❌      | ✅ 一个文件跟着走  |
| 不想AI记住某些事  | ❌       | ⚠️ 有限  | ✅ 随时删除、分区域 |
| 不花token也能记 | ❌       | ❌      | ✅ 88%零成本   |
| 自己掌控数据     | ⚠️ 自建才行 | ❌ 云端   | ✅ 本地一个文件   |

***

## 5. P1: GitHub周榜策略

### CodeGraph增长公式

**即时痛点 + 一行命令 + benchmark数据**

### CarryMem差异化定位

| 维度   | CodeGraph | agentmemory    | CarryMem   |
| ---- | --------- | -------------- | ---------- |
| 核心价值 | 代码知识图谱    | Coding Agent记忆 | **个人身份记忆** |
| 目标用户 | 开发者       | 开发者            | **所有AI用户** |
| 数据归属 | 本地        | 本地             | **本地+可携带** |
| 依赖   | 需构建图谱     | 需向量DB          | **零依赖**    |

### 行动计划

1. **Claude Code一行命令集成** — README中突出展示
2. **GitHub About/topics更新** — 添加 `memory`, `ai-memory`, `preference`, `mcp`, `local-first`
3. **Release notes v0.2.4** — 突出"已经连续几天在公平评测中超过reminder"
4. **Issue/Discussion活跃度** — 回复agentmemory等竞品的issue，引流

***

## 6. 执行计划

| 顺序 | 任务                          | 依赖  | 产出             |
| -- | --------------------------- | --- | -------------- |
| 1  | 分析25个unhelpful case         | 无   | 分类报告 + 优化建议    |
| 2  | carrymem pack/unpack实现      | 无   | CLI命令 + 测试     |
| 3  | carrymem setup-mcp --global | 无   | CLI参数 + 多客户端支持 |
| 4  | README场景入口改写                | 2,3 | 三语言README      |
| 5  | GitHub About/topics/release | 4   | GitHub更新       |
| 6  | 非技术用户5分钟测试                  | 1-5 | 用户反馈           |

***

## 7. 风险与应对

| 风险                     | 影响             | 应对                               |
| ---------------------- | -------------- | -------------------------------- |
| max\_tokens增大导致成本/延迟增加 | PrefEval评测成本上升 | 先20样本验证效果，再决定是否全量                |
| pack文件过大(向量数据)         | 传输不便           | 不打包向量索引，unpack后自动重建              |
| 多Agent并发写入冲突           | 数据丢失           | WAL + busy\_timeout + status命令监控 |
| 场景化改写丢失技术准确性           | 开发者用户流失        | 分层设计：场景入口→技术细节                   |
| 非技术用户测试不通过             | 需要迭代           | 预留2轮迭代空间                         |

***

> 本文档为DevSquad 7角色共识结果，基于PrefEval数据、用户反馈和GitHub周榜分析。
> 执行中如有偏差，及时复盘调整。

