# 分层预算契约（Recall / Reflection Budget）

> **版本**：v1.1
> **日期**：2026-10-06
> **状态**：已批准（Gate 0，2026-09-28；D5 按本文四层结构与默认值执行）
> **权威关系**：细化 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §7；预算结构、截断顺序与原因码以本文为准。
> **实现边界**：Gate 0 批准前不修改 `build_context()`、`recall_engine.py` 或预算相关代码。
>
> **Phase 5 Slice 1（2026-10-05）**：已落地纯 `RecallPlan` 契约、四层预算数据结构、封闭任务模式、计划快照与 namespace/task fail-closed 校验；尚未接入在线 recall、token 硬闸或截断执行。
>
> **Phase 5 Slice 2（2026-10-06）**：已接入在线执行入口 `CarryMem.recall_with_plan(plan) -> RecallResult`（含 `AsyncCarryMem.recall_with_plan` 包装）、recall 路径 output token 硬闸、三态 conflict policy、敏感性过滤、vector→fts 回退、evidence 预算展开、截断/降级元数据与 low-cardinality metrics；真实 HTTP/MCP metrics E2E 通过。实现边界与遗留缺口见 §10。
>
> **Phase 5 Slice 3（2026-10-07）**：`RecallPlan` 新增 `entity` 与 `time_range`（ISO-8601 对）输入并纳入 fingerprint——graph/time 模式从显式 skip 变为真实执行（输入缺失仍 fail-closed 报 `INPUT_MISSING`）；`retrieval_timeout_ms` 以"mode 级软预算"接线（超时后不再启动新模式，记 `RETRIEVAL_TIMEOUT`，正在执行的同步 SQLite 查询不可中断）；output 截断顺序按信任层细化（推断/派生 → 普通旧者先 → observation），对齐 §5.1 普通档语义。遗留缺口清单更新见 §10.3。

---

## 1. 目的

当前 `build_context()` 以 `max_tokens=2000` 做兼容性预算控制，但该参数目前主要影响候选选择，尚不是最终模型请求的真实 token 硬上限。当前存在三个缺口：

1. 只有总预算，没有分层——候选扩展、证据展开、反思开销与最终输出互相挤占，不可观测；
2. 截断无原因码——调用方无法知道"少了什么、为什么少"；
3. 无关键内容保护——理论上 correction 与安全事实可能被普通截断挤掉。

截至 2026-09-30，`max_tokens=2000` 已验证可以约束部分候选选择路径，但尚未完成客户需求验收：最终 prompt 组装后可能超过 2000，且当前估算器不是目标模型的真实 tokenizer。因此不得将 `2000` 宣称为最终输出硬上限。

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
| output | build_context max_tokens | 2000（现有 Stable 兼容默认；Phase 5 实现最终 hard gate 后才可作为输出预算验收值） |

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
    sensitivity_policy: SensitivityPolicy,# 敏感过滤
    entity: Optional[str] = None,         # graph 模式起点实体（Slice 3）
    time_range: Optional[Tuple[str, str]] # time 模式 ISO-8601 (start, end) 对
)                                         # （Slice 3；均纳入 fingerprint）
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
- 校准结果记录在测试基线中（真实 tokenizer 校准属 Phase 5 交付，见主方案 §12）；
- `16383` 仅作为接近 16K 上下文窗口的压力测试边界，不作为默认生产预算。若目标模型上下文窗口为 16K，必须从窗口中预留用户输入、工具/协议开销、历史消息和输出空间；初始客户配置应通过 `request_budget`、`input_budget`、`output_reserve` 分离表达，而不是把 `max_tokens` 直接设置为 `context_window - 1`；
- 面向 16K 模型的待验证起始区间为：`request_budget=12000~14000`、`input_budget=9000~12000`、`output_reserve=2048~4096`。该区间是 Phase 5 的评估起点，不是当前已实现或已验收的默认值。

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

---

## 10. 实现状态（诚实披露；Slice 3 更新于 2026-10-07）

### 10.1 已实现

| 能力 | 位置 | 说明 |
|---|---|---|
| 在线执行入口 | `carrymem/core/_recall.py` `recall_with_plan` / `_execute_recall_plan` | plan 校验、namespace fail-closed、`_retry_on_busy` 包裹、recall 延迟采样 |
| 兼容投影 | `RecallResult.to_legacy_list()` | `recall_memories()` 旧签名与返回结构未变 |
| 异步包装 | `AsyncCarryMem.build_recall_plan / recall_with_plan` | plan 构建纯 CPU 不进 executor |
| graph/time 真实执行（Slice 3） | `_rows_for_mode` | plan 新增 `entity` / `time_range`（ISO-8601 对）输入并纳入 fingerprint；graph 走 `recall_graph`（受 `graph_max_hops` 预算约束），time 走 `recall_by_time`；输入缺失仍 fail-closed 报 `INPUT_MISSING` |
| retrieval 软超时（Slice 3） | `_retrieve_plan_candidates` | `retrieval_timeout_ms` 为 mode 级软预算：超时后不再启动新模式并记 `RETRIEVAL_TIMEOUT`；正在执行的同步 SQLite 查询不可中断（预算语义=配额，非硬中断） |
| output 硬闸（recall 路径） | `_enforce_output_limit` | 先删非保护条目；保护内容超限时 `Degradation` + 确定性二分前缀截断（对齐 INV-TB1），`metadata["output_tokens"]` 始终 ≤ 预算 |
| 信任层截断顺序（Slice 3） | `_drop_tier` / `_drop_sort_key` | 普通档按 §5.1 语义：推断/派生/聚合先删 → 普通条目（旧者先）→ observation 最后；同级内旧者先、再低分先 |
| output 硬闸（prompt 路径） | `token_budget.enforce_output_budget`，`prompt_builder` 已接入 | `build_context()` 签名不变，metadata 返回 `truncations/degradation/budget_utilization` |
| conflict policy | `_resolve_conflicts` | `hide`=整组剔除；`show_top`=每组保一条；`always`=返回 `ConflictView`；非 always 记 `CONFLICT_DEPRIORITIZED` |
| 敏感性过滤 | `_filter_sensitive_candidates` | `filter`=剔除+截断记录；`strict`=额外 ModeFailure；序列化失败 fail-closed |
| vector 回退 | `_rows_for_mode` | `vector_search=False` 时回退 fts 并记 `VECTOR_UNAVAILABLE_FALLBACK` |
| evidence 预算 | `_expand_evidence` | per-result 条数 + 全局字符上限，超限记 `EVIDENCE_BUDGET_EXCEEDED` |
| metrics | `monitoring.record_recall_truncation / set_recall_budget_utilization` | §8 四个序列中前两个已在线产生并通过 `/metrics` 暴露（真实 TCP E2E：`tests/integration/test_recall_metrics_http_e2e.py`） |

### 10.2 与 §5.1 截断顺序的差异

保护层（§5.1 第 6-8 层）为三档：correction（correction_resolution 任务下绝对保护）＞其他保护类型（security/strategy/accepted_fact/accepted_rule/accepted 状态）＞普通条目。普通档已按 Slice 3 落地"推断/派生 → 普通（旧者先）→ observation"三级顺序；§5.1 第 3 级"重复或语义高度相似条目"已由 storage_key 去重承担，"语义高度相似"的细粒度去重未实现。补充实现时须以 §5.1 为准并回补测试。

### 10.3 已知遗留缺口（不得宣称为已完成）

1. `retrieval_timeout_ms` 为 mode 级软预算（超时后不再启动新模式），不能中断正在执行的同步 SQLite 查询；`inline_timeout_ms` 仍未接线（依赖内联反思执行器）；
2. reflection 预算尚未接入内联反思执行器，utilization 恒为 0（显式占位，非伪装数据）；
3. `SUPERSEDED_FILTERED` 截断码已定义，由 adapter 过滤 superseded 行为承担，但 executor 未单独计数；
4. `TOKENIZER_DRIFT_WARNING` 未接线（校准属后续交付）；
5. semantic 不可用时复用 `VECTOR_UNAVAILABLE_FALLBACK` 原因码，语义不完全准确，扩码需先更新 §5.2；
6. candidate 预算按"命中次数"计量（多模式重复命中同一内存会重复计数），去重发生在预算之后；
7. 单条 memory 的序列化固定开销约为 200 token（含 metadata/审计字段），`output.max_tokens` 低于该值时保护条目会被降级移除（`Degradation` 如实记录），调用方应避免设置过小的 output 预算；
8. 默认 `retrieval_timeout_ms=200` 下，vector/semantic 模式的首次调用若包含 embedding 模型加载（秒级）会被软超时推迟——调用方应调大该层预算或预热模型，这不是缺陷而是预算语义。

### 10.4 测试证据（2026-10-07）

- 契约与执行测试：`tests/test_recall_plan.py` 28 项（确定性、fail-closed、budget cap、conflict 三态、敏感性 filter/strict、vector 回退去重、evidence 预算、correction 排序、保护内容降级、async parity、entity/time_range 校验与 graph/time 真实执行、软超时、信任层截断顺序）；
- 真实用户 E2E：`tests/e2e/test_e2e_phase5_recall_budget.py` 4 项（全链路确定性、小预算保护 correction、fingerprint 敏感性、legacy prompt 共存）；
- HTTP/MCP metrics E2E：`tests/integration/test_recall_metrics_http_e2e.py`（真实 TCP `/metrics` 断言 truncation 序列与 utilization gauge，真实 `/message` 工具调用共享 collector，`/healthz` 存活）。
