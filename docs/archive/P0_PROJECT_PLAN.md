# CarryMem P0 项目计划 — 端到端验证 + 行为式 Prompt + 借宿主 LLM + PrefEval 适配

> 基于：DevSquad V3.5 项目全生命周期 11 阶段模型
> 模板：internal_tool + P6（8 阶段：P1→P2→P3→P6→P7→P8→P9→P10）
> 时间：3 天冲刺
> 成功标准：MCP 链路通畅 + 行为式 Prompt 生效 + 借宿主 LLM 跑通 + PrefEval 数据拉取完成

***

## P1 需求分析

**主导**：pm | **评审**：arch+test+sec

### 用户故事

| # | 用户故事 | 验收标准 | 优先级 |
|---|---------|---------|--------|
| US1 | 作为 CarryMem 用户，我希望在 TRAE 中说话时 CarryMem 自动记住我的偏好/纠正/决策 | 说一句话后查数据库，确认记忆已存入且分类正确 | P0 |
| US2 | 作为 CarryMem 用户，我希望 AI 遵守我注入的偏好指令 | 告诉 AI "我偏好 PostgreSQL"，后续问数据库推荐时 AI 主动推荐 PostgreSQL | P0 |
| US3 | 作为 CarryMem 用户，我希望 AI 能帮我做会话摘要而不需要我配 API Key | TRAE 调用 CarryMem 工具做摘要，摘要包含至少1条偏好或决策，结果写回 CarryMem | P0 |
| US4 | 作为 CarryMem 开发者，我需要用 PrefEval 证明 CarryMem 的偏好遵守能力 | PrefEval 数据集拉取完成，适配脚本可运行 | P0 |

### 非功能性需求

| # | 需求 | 标准 |
|---|------|------|
| NFR1 | MCP 链路响应时间 | remember/recall < 2s |
| NFR2 | 行为式 Prompt 不增加 token 开销 | prompt 长度变化 < 10% |
| NFR3 | 借宿主 LLM 不引入安全风险 | 摘要内容经过注入防护 |

### 优先级矩阵

| | 高影响 | 低影响 |
|---|--------|--------|
| **低成本** | US2（行为式 Prompt）| NFR2 |
| **高成本** | US1（MCP 链路）| US3（借宿主 LLM）|

### 门禁条件

- [x] 验收标准可量化、无歧义
- [x] 优先级矩阵已排序
- [x] 评审通过（7/7 批准，6 条建议已采纳）

***

## P2 架构设计

**主导**：arch | **评审**：pm+sec

### 架构方案

```
TRAE (本地 IDE)
  │
  ├── MCP Protocol ──→ CarryMem MCP Server
  │                     │
  │                     ├── remember()             ← US1: 存储记忆
  │                     ├── recall_memories()       ← US2: 召回记忆
  │                     ├── build_system_prompt()   ← US2: 行为式注入
  │                     └── summarize_and_store()   ← US3: 借宿主 LLM
  │
  └── TRAE 自身 AI 上下文 ←── 行为式 Prompt 注入
                              ←── 摘要生成（借宿主 LLM）

PrefEval 适配
  │
  ├── PrefEval 数据集 → 适配脚本 → CarryMem 记忆库
  └── CarryMem 偏好注入 → PrefEval 评估 → Preference Following Accuracy
```

### 技术选型

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| MCP Server 框架 | FastMCP / mcp-python-sdk | **mcp-python-sdk** | 已有实现 |
| Prompt 格式 | 标签式 / 行为式 | **行为式** | 投入产出比最高 |
| 借宿主 LLM | 新 MCP tool / 复用 remember | **新 MCP tool** | 需要返回"需要摘要的内容" |
| PrefEval 评估 | 独立脚本 / 集成到 benchmark | **独立脚本** | PrefEval 协议与 LongMemEval 不同 |

### 服务边界

| 组件 | 职责 | 不负责 |
|------|------|--------|
| CarryMem MCP Server | 记忆存储/召回/注入 | LLM 推理 |
| TRAE | 对话/摘要/推理 | 记忆持久化 |
| context.py | Prompt 格式化 | 记忆选择逻辑 |
| PrefEval 适配脚本 | 数据加载 + 评估 | 记忆系统内部逻辑 |

### 门禁条件

- [x] 架构方案通过加权共识
- [x] 评审通过（7/7 批准，6 条建议已采纳）

***

## P3 技术设计

**主导**：arch+coder | **评审**：coder+test

### 3.1 行为式 Prompt 格式变更

**文件**：`context.py` → `format_memory_entry()`

**映射规则**：

| 记忆类型 + auto_rule | 行为式指令模板 |
|---------------------|--------------|
| user_preference + prefer | "Prefer {content} — the user has expressed this preference" |
| user_preference + avoid | "NEVER suggest {content} — the user has explicitly rejected it" |
| correction | "Do NOT repeat: {content} — the user has corrected this before" |
| decision | "Always follow: {content} — this is the user's confirmed decision" |
| fact_declaration | "{content}" (保持不变) |
| session_summary | "Based on previous conversations: {content}" |
| superseded | "NOTE: \"{content[:80]}\" is outdated" |

### 3.2 借宿主 LLM MCP Tool

**文件**：`tools.py` + `handlers.py`

`summarize_and_store(session_id, max_tokens=2000, namespace="default")` → 返回需要摘要的内容给宿主 AI，宿主 AI 生成摘要后调用 `classify_and_remember` 写回。

### 3.3 TRAE MCP 配置

在 TRAE 的 MCP Server 设置中添加：

```json
{
  "mcpServers": {
    "carrymem": {
      "command": "python",
      "args": ["-m", "carrymem.integration.layer2_mcp"],
      "env": {
        "MCE_DATA_PATH": "/Users/lin/.carrymem"
      }
    }
  }
}
```

### 3.4 PrefEval 适配

**目标**：拉取 PrefEval 数据集，编写适配脚本，为 P1 的 PrefEval 跑分做准备。

**步骤**：

1. 拉 PrefEval 论文和 GitHub 仓库
2. 理解 PrefEval 的数据格式（用户画像 + 偏好对 + 评估协议）
3. 编写 `benchmarks/_prefeval.py` 适配脚本
4. 验证脚本可运行（不需要跑完，能加载前 10 条即可）

### 技术约束

1. 行为式 Prompt 不能增加 prompt token 超过 10%
2. 借宿主 LLM 工具不调用外部 LLM API，只返回指令让宿主 AI 处理
3. MCP Server 启动时间 < 5s
4. PrefEval 适配脚本不依赖外部 LLM（数据加载阶段）

### 技术风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| TRAE MCP 配置不兼容 | 中 | 高 | 查 TRAE 文档确认 MCP 配置格式 |
| 行为式 Prompt 反而降低 AI 遵从率 | 低 | 高 | 保留标签式作为 fallback |
| PrefEval 数据集格式与预期不符 | 中 | 中 | 先拉数据再适配，不假设格式 |

### 门禁条件

- [x] API 规范无歧义
- [x] 技术风险评估完成
- [x] 评审通过（7/7 批准，6 条建议已采纳）

***

## P6 安全评审

**主导**：sec | **评审**：arch+infra

### 威胁模型

| 威胁 | 严重度 | 可能性 | 缓解 |
|------|--------|--------|------|
| Prompt 注入：记忆内容包含恶意指令 | 高 | 中 | `<memory_data>` 分隔符 + 反注入指令（已有） |
| 借宿主 LLM：摘要内容被篡改 | 中 | 低 | 摘要写入前经过 content 验证 |
| MCP Server：未授权访问 | 中 | 低 | 本地部署，无网络暴露 |

### 门禁条件

- [x] 无 P0/P1 漏洞
- [x] 评审通过（7/7 批准，6 条建议已采纳）

***

## P7 测试计划

**主导**：test | **评审**：arch+sec+pm

### 测试用例

| # | 测试场景 | 类型 | 预期结果 | 优先级 |
|---|---------|------|---------|--------|
| T1 | TRAE 中说"我偏好 PostgreSQL"，查数据库 | 集成 | 记忆存入，type=user_preference | P0 |
| T2 | TRAE 中问"推荐一个数据库"，AI 推荐 PostgreSQL | E2E | AI 遵守偏好 + build_system_prompt() 输出含行为式指令 | P0 |
| T3 | TRAE 中说"别用 MySQL"，查数据库 | 集成 | 记忆存入，auto_rule=avoid | P0 |
| T4 | TRAE 中问数据库推荐，AI 不提 MySQL | E2E | AI 遵守纠正 + build_system_prompt() 输出含行为式指令 | P0 |
| T5 | 调用 summarize_and_store，TRAE AI 做摘要 | E2E | 摘要写回 CarryMem | P0 |
| T6 | PrefEval 数据集加载前 10 条 | 集成 | 数据格式正确，适配脚本可运行 | P0 |
| T7 | 行为式 Prompt token 开销 < 10% | 性能 | token 数对比 | P1 |
| T8 | MCP 链路响应时间 < 2s | 性能 | remember/recall 延迟 | P1 |
| T9 | 记忆内容含注入指令时不影响 AI 行为 | 安全 | AI 忽略注入 | P1 |
| T10 | remember() 过滤 MCP 工具调用指令 | 安全 | 含工具调用指令的内容被拒绝或清洗 | P1 |

### 门禁条件

- [x] 测试计划评审通过
- [x] 评审通过（7/7 批准，6 条建议已采纳）

***

## P8 开发实现

**主导**：coder | **评审**：arch+sec+test

### 任务分解

| # | 任务 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|
| D1 | 行为式 Prompt 格式实现 | P3 | context.py format 改动 | ✅ 完成 |
| D2 | 借宿主 LLM MCP tool 实现 | P3 | tools.py + handlers.py 新 tool | ✅ 完成 |
| D3 | TRAE MCP 配置 | P3 | MCP settings JSON | ✅ 完成 |
| D4 | 单元测试 | D1+D2 | 2127 passed | ✅ 完成 |
| D5 | PrefEval 数据拉取 + 适配脚本 | P3 | benchmarks/_prefeval.py | 待执行 |
| D6 | 端到端验证（TRAE） | D1+D2+D3 | 验证报告 | 待执行 |

### 门禁条件

- [x] 代码审查通过（D1-D4）
- [x] 无 P0 缺陷
- [x] 单元测试通过（2127 passed）
- [ ] PrefEval 适配脚本可运行
- [ ] 端到端验证通过

***

## P9 测试执行

**主导**：test | **评审**：arch+pm

### 执行顺序

1. T1→T2（偏好存储+遵守）
2. T3→T4（纠正存储+遵守）
3. T5（借宿主 LLM）
4. T6（PrefEval 数据加载）
5. T7→T8（性能）
6. T9→T10（安全）

### 成功标准

| 指标 | 目标 | 实际 |
|------|------|------|
| P0 测试通过率 | 100% | — |
| P1 测试通过率 | ≥80% | — |
| MCP 链路通畅 | ✅ | — |
| 行为式 Prompt 生效 | ✅ | — |
| 借宿主 LLM 跑通 | ✅ | — |
| PrefEval 数据可加载 | ✅ | — |

### 门禁条件

- [ ] P0 测试 100% 通过
- [ ] 无 P0 缺陷
- [ ] 4 条成功标准全过

***

## P10 部署发布

**主导**：infra | **评审**：arch+sec+test

### 部署方案

| 步骤 | 动作 |
|------|------|
| 1 | 行为式 Prompt 合并到 main |
| 2 | 借宿主 LLM tool 合并到 main |
| 3 | PrefEval 适配脚本合并到 main |
| 4 | 更新 TRAE MCP Server 配置 |
| 5 | 更新决策文档 |

### 回滚预案

- 行为式 Prompt 有问题 → 恢复标签式格式（git revert）
- 借宿主 LLM tool 有问题 → 移除 tool（不影响其他功能）
- MCP 链路有问题 → 回退到 CLI 模式

### 门禁条件

- [ ] 部署演练通过
- [ ] 回滚预案验证
- [ ] 决策文档已更新

***

## RACI 矩阵

| 阶段 | pm | arch | coder | sec | test | infra | ui |
|------|-----|------|-------|-----|------|-------|-----|
| P1 需求分析 | **R** | C | I | C | C | I | — |
| P2 架构设计 | C | **R** | C | C | I | C | — |
| P3 技术设计 | I | **R** | **R** | C | **R*** | I | — |
| P6 安全评审 | I | **R*** | C | **R** | I | **R*** | — |
| P7 测试计划 | A | **R*** | C | **R*** | **R** | **R*** | — |
| P8 开发实现 | I | **R*** | **R** | **R*** | **R*** | I | — |
| P9 测试执行 | **R*** | **R*** | C | **R*** | **R** | **R*** | — |
| P10 部署发布 | I | **R*** | I | **R*** | **R*** | **R** | — |

> R=负责 A=协助 C=咨询 I=知会 R*=评审人

***

## 时间线

| 天 | 阶段 | 产出 |
|----|------|------|
| Day 1 上午 | P1+P2+P3 | 需求确认 + 架构方案 + 技术设计 |
| Day 1 下午 | P6+P7 | 安全评审 + 测试计划 |
| Day 2 全天 | P8 | 开发实现 + 单元测试 + PrefEval 适配 |
| Day 3 上午 | P9 | 测试执行（TRAE 端到端验证） |
| Day 3 下午 | P10 | 部署发布 + 文档更新 |

***

## 后续：P1 项目计划概要

P0 完成后，进入 P1 阶段。P1 的核心目标是**用 PrefEval 证明 CarryMem 的偏好遵守能力**。

| 阶段 | P1 核心任务 | 产出 |
|------|-----------|------|
| P1 需求 | 定义 PrefEval 跑分目标 | 目标分数 + baseline 对比表 |
| P2 架构 | PrefEval 评估管道设计 | 适配脚本架构 |
| P3 技术设计 | CarryMem → PrefEval 接口规范 | API + 数据流 |
| P8 开发 | PrefEval 完整跑分 + 结果分析 | 跑分报告 |
| P9 测试 | 修裂缝（soft_catchall 置信度等） | 断点修复验证 |
| P10 发布 | 公开 PrefEval 结果 | 数据驱动的定位澄清 |

P1 的成功标准：**PrefEval Preference Following Accuracy 超过至少 1 个 baseline**。

***

*本文档基于 DevSquad V3.5 项目全生命周期模型编写，采用 internal_tool + P6 模板。*
*v2：修正 TRAE 为唯一验证环境，新增 PrefEval 适配（US4+T6+D5），新增 P1 项目计划概要。*
