# 分层预算契约（Recall / Reflection Budget）

> **版本**：v0.1-draft
> **日期**：2026-09-28
> **状态**：Phase 0 契约草案，待 Gate 0 批准（含待拍板决策 D5）
> **权威关系**：细化 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §7；预算结构、截断顺序与原因码以本文为准。
> **实现边界**：Gate 0 批准前不修改 `build_context()`、`recall_engine.py` 或预算相关代码。

---

## 1. 目的

当前 `build_context()` 以 `max_tokens=2000` 做总量控制，但存在三个缺口：

1. 只有总预算，没有分层——候选扩展、证据展开、反思开销与最终输出互相挤占，不可观测；
2. 截断无原因码——调用方无法知道"少了什么、为什么少"；
3. 无关键内容保护——理论上 correction 与安全事实可能被普通截断挤掉。

本文定义四层预算结构、硬约束与确定性降级行为。总原则：

> **预算是硬约束，不是软建议；最终输出不得超预算；任何截断、降级、无答案都必须有原因码且可观测。**

---

## 2. 四层预算结构（待批准决策 D5）

```text
request budget（单次请求总控）
├── retrieval budget      检索阶段：候选数量上限、图遍历跳数/边数、检索耗时上限
├── evidence budget       证据展开：每结果附带的 evidence/来源条数与字符量
├── reflection budget     反思阶段：单次 inspect/propose 的输入批次、候选数、耗时
└── output budget         最终输出：build_context/build_system_prompt 的最终 token 量
```

关系约束：

- 四层独立计量，互不挪用；`retrieval` 超支不侵占 `output`；
- `output budget` 是最终硬闸：即使各层未超支，组装后超限仍须按截断顺序收缩并留痕；
- `reflection budget` 仅在请求内联反思时生效；后台反思任务用独立预算配置（见 §6）。

### 2.1 建议默认值（初版，以真实基线校准后为准）

| 层 | 参数 | 建议默认 |
|---|---|---|
| retrieval | max_candidates | 100 |
| retrieval | graph_max_hops | 2（沿用现有图谱边界） |
| retrieval | retrieval_timeout_ms | 200 |
| evidence | per_result_evidence | 3 条 |
| evidence | evidence_chars_total | 2000 字符 |
| reflection | inline_max_candidates | 50 |
| reflection | inline_timeout_ms | 100（超出转后台提案，不阻塞 recall） |
| output | build_context max_tokens | 2000（现有 Stable 默认不变） |

---

## 3. RecallPlan 契约

### 3.1 字段定义

```text
RecallPlan(
    query: Optional[str],                 # 检索文本
    task: TaskMode,                       # 任务模式（封闭枚举，见 §4）
    namespace: str,                       # 安全上下文（必填，来自认证边界）
    modes: Sequence[RetrievalMode],       # fts / vector / graph / time / semantic
    max_results: int,                     # 最终结果条数上限
    budget: BudgetSpec,                   # 四层预算
    include_evidence: bool = False,       # 是否携带证据
    include_superseded: bool = False,     # 默认 False（INV-C2）
    conflict_policy: ConflictPolicy,      # hide / show_top / always
    sensitivity_policy: SensitivityPolicy # 敏感过滤
)
```

构造约束：

| 编号 | 不变量 |
|---|---|
| INV-BP1 | `RecallPlan` 由旧 API 参数确定性构造（同输入必同计划），构造过程不产生 IO |
| INV-BP2 | `namespace` 缺失时构造失败（fail-closed），不默认 "default" 绕过安全上下文 |
| INV-BP3 | 任务模式只能收紧范围（更少 mode、更小预算），不允许凭 query 自动放宽 namespace/hop/敏感级别 |

### 3.2 RecallResult 包装（新实验 API 专用）

```text
RecallResult(
    items: List[RecallItem],        # 旧 API 兼容字段 + match_type/score/source/
                                    # validity_status/evidence_ids/conflict_status
    plan: RecallPlanSnapshot,       # 实际生效的计划（含预算消耗）
    truncations: List[Truncation],  # 全部截断事件（见 §5 原因码）
    conflicts: List[ConflictView],  # 按 conflict_policy 呈现的冲突说明
    degraded: Optional[Degradation] # 降级说明（如向量不可用回退语义检索）
)
```

旧 API `recall_memories()` 返回结构不变，仅内部消费 `RecallResult.items` 的兼容投影。

---

## 4. 任务模式（封闭枚举）

```text
preference_following    遵循用户偏好：偏好/纠正优先，排除过期观察
correction_resolution   纠正解析：correction 恒第一（INV-C3）
project_context         项目上下文：近期事实+实体状态优先
fact_lookup             事实查询：accepted fact 优先，可 show_top 冲突
timeline_review         时间线：时间序完整呈现，可包含 superseded（显式）
rule_application        规则应用：accepted 规则 + 高信任事实
conflict_explanation    冲突解释：conflict_policy=always
```

不变量 INV-T1：未登记的任务模式字符串必须被拒绝（`ValueError`），禁止自由文本任务。

---

## 5. 截断顺序与原因码

### 5.1 output 超限时的确定性截断顺序

先降级低信任、后收缩高信任；同级内按分数逆序淘汰：

```text
1. 推断类候选（inference/candidate，未被确认）
2. 共现/图谱路径候选（低信任边）
3. 重复或语义高度相似的条目（保分高者）
4. 普通 fact / preference（时间旧者先）
5. observation（若被显式纳入）
─── 以下为保护层，普通截断不得触及 ───
6. accepted fact / accepted rule
7. correction（correction_resolution 任务下绝对保护）
8. 安全类事实与策略性记忆（安全保护层，永不自动截断）
```

不变量：

| 编号 | 不变量 |
|---|---|
| INV-TB1 | 截断到保护层仍超限时：返回整体降级（缩减版结果 + 明确说明），不静默丢弃保护层内容 |
| INV-TB2 | 每次截断产生 `Truncation(reason_code, layer, dropped_count, protected=False/True)` |
| INV-TB3 | 同一输入 + 同一计划 → 截断结果确定一致（无随机性） |

### 5.2 截断原因码（封闭枚举）

```text
OUTPUT_BUDGET_EXCEEDED      最终输出超限
EVIDENCE_BUDGET_EXCEEDED    证据展开超限
RETRIEVAL_TIMEOUT           检索超时（部分候选未评估）
RETRIEVAL_CANDIDATE_CAP     候选数量达上限
VECTOR_UNAVAILABLE_FALLBACK 向量不可用，语义回退
SENSITIVITY_FILTERED        敏感级别过滤剔除
SUPERSEDED_FILTERED         被取代版本剔除
CONFLICT_DEPRIORITIZED      冲突败者降权/剔除
NAMESPACE_DENIED            跨域拒绝（同时计入安全 metrics）
TOKENIZER_DRIFT_WARNING     估算与真实 tokenizer 偏差超阈值
```

原因码扩展须经本文档版本更新；禁止运行时自由字符串。

---

## 6. Reflection 预算（后台任务）

后台反思独立预算配置（不与在线请求共享）：

```text
batch_size            单批输入记忆数（建议 100，沿用 auto_decay 量级）
max_runtime_ms        单 run 时间上限（超限存 input_cursor，转 interrupted 可恢复）
max_proposals_per_run 单 run 提案产出上限（防 runaway 生成）
queue_max_size        后台队列容量上限（超限拒绝入队并计 metrics）
```

不变量 INV-RB1：后台 run 超时或达提案上限时，以 `interrupted/completed(capped)` 结束并留 cursor——不允许无上限运行。

---

## 7. Token 估算与校准

- 初版采用字符比例估算（无外部依赖），估算器与真实 tokenizer 的偏差需定期校准；
- 校准方式：固定基准集（版本化）上，估算值与真实 tokenizer 值的偏差 > 10% 时输出 `TOKENIZER_DRIFT_WARNING` 并要求更新估算系数；
- 校准结果记录在测试基线中（真实 tokenizer 校准属 Phase 5 交付，见主方案 §12）。

不变量 INV-TK1：`output budget` 的判定必须基于统一估算器；同一进程内不得混用两种估算口径。

---

## 8. 可观测性挂钩

预算事件必须进入 metrics（定义见[可观测性规范](MEMORY_EVOLUTION_OBSERVABILITY.md)）：

```text
carrymem_recall_truncations_total{reason_code, layer}
carrymem_recall_budget_utilization_ratio{layer}      (gauge)
carrymem_reflection_budget_capped_total
carrymem_tokenizer_drift_ratio                        (gauge, 校准时更新)
```

标签均为低基数枚举（reason_code ≤ 10、layer = 4），不包含 query/内容/namespace 原文。

---

## 9. Gate 0 待确认项

| 决策 | 内容 | 本文建议默认 |
|---|---|---|
| D5 | 预算分层边界 | §2 四层结构 + §2.1 默认值 |
| （关联） | 保护层清单 | §5.1 第 6-8 层，安全类永不自动截断 |
| （关联） | build_context 现有默认 | `max_tokens=2000` 不变（Stable 兼容） |
