# 分层预算契约（Recall / Reflection Budget）

> **版本**：v1.2（草稿，待 Gate 0 重决策）
> **日期**：2026-10-07
> **状态**：v1.2 DRAFT —— §10.5 hindsight 复盘未批准前不修改代码
> **权威关系**：细化 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §7；预算结构、截断顺序与原因码以本文为准。
> **v1.1 → v1.2 主要变更**：
> 1. **§5.1 新增第 5.5 档 reflection_hints**（re-rank 提示保护层缺位的修复）；
> 2. **§10.5 hindsight 复盘**（诚实披露 v1.1 三处设计缺陷，源自 Phase 5 Slice 5 三阶段路径讨论）；
> 3. **§11 新增 InlineReflectionHint 数据契约**（取代原"未定义的内联反思执行器"占位）；
> 4. **§10.3 第 2 项更新**："reflection 预算尚未接入内联反思执行器" 升级为"v1.2 实施中"。
>
> **Phase 5 Slice 1/2/3/4 已落地**：RecallPlan 契约、四层预算结构、在线执行入口 `recall_with_plan`、graph/time 模式真实执行、`retrieval_timeout_ms` 软超时、output 截断按信任层细化、superseded 精确计数（§10.1）。

---

## 1. 目的

（与 v1.1 §1 一致，不重述）

---

## 2. 四层预算结构

（与 v1.1 §2 一致）

---

## 3. RecallPlan 契约

（与 v1.1 §3 一致；§3.1 字段表保留 `entity` / `time_range` Slice 3 增量）

---

## 4. 任务模式（封闭枚举）

（与 v1.1 §4 一致）

---

## 5. 截断顺序与原因码

### 5.1 output 超限时的确定性截断顺序

**v1.2 新增第 5.5 档**（修复 v1.1 设计缺陷 #2）：

```text
1. 推断类候选（inference/candidate，未被确认）
2. 共现/图谱路径候选（低信任边）
3. 重复或语义高度相似的条目（保分高者）
4. 普通 fact / preference（时间旧者先）
5. observation（若被显式纳入）
5.5 ★ v1.2 新增：reflection_hints（re-rank 提示，非保护层）   ←—
─── 以下为保护层，普通截断不得触及 ───
6. accepted fact / accepted rule
7. correction（correction_resolution 任务下绝对保护）
8. 安全类事实与策略性记忆（安全保护层，永不自动截断）
```

**第 5.5 档语义约束**：
- `drop_priority=50`（高于普通 fact 40，低于 observation 60），普通档裁剪时按 drop_priority 排序，先于 fact 删、后于 observation 删；
- **非保护**：`protected=False`，截断到保护层前允许丢弃；
- **数量硬上限**：`max_hints_per_response=20`（防御性，避免 LLM 调用方被 hint 淹没，**与 §5.1 INV-TB3 确定性兼容**——同一 plan + 同一 ranked → 同 hints 顺序）；
- **DLP 约束**（与 §4.2 隐私对齐）：hint payload 不允许含 memory content 原文，仅含 `storage_key` + 结构化 hint_type + ≤50 字符 reasoning_short（`InlineReflectionHint.reasoning_short` 字段）；
- **不进入 sensitivity_policy 过滤路径**：hint 本身是元数据，若被 §5.1 第 8 层反向保护则用户看不到 flag，违反"re-rank 提示"产品语义。

不变量：

| 编号 | 不变量 |
|---|---|
| INV-TB1 | （与 v1.1 一致） |
| INV-TB2 | （与 v1.1 一致） |
| INV-TB3 | （与 v1.1 一致） |
| **INV-TB4（v1.2 新增）** | hint 数量受 `max_hints_per_response=20` 硬上限约束；超出按 hint_type 优先级 + score 降序截断，记 `OUTPUT_BUDGET_EXCEEDED` + `protected=False` |
| **INV-TB5（v1.2 新增）** | hint 不含 memory content 原文；DLP 校验在 `_build_hint_from_observation` 内置 fail-closed |

### 5.2 截断原因码（封闭枚举）

（与 v1.1 一致；v1.2 不新增 reason_code，沿用 `RETRIEVAL_TIMEOUT` 标 `BudgetLayer.REFLECTION`）

---

## 6. Reflection 预算（后台任务）

（与 v1.1 一致）

---

## 7. Token 估算与校准

（与 v1.1 一致）

---

## 8. 可观测性挂钩

**v1.2 新增 series**：

| Series | 类型 | 标签 | 产生者（v1.2 接线） | 触发条件 |
|---|---|---|---|---|
| `carrymem_recall_reflection_hints_total` | counter | hint_type | `_run_inline_reflection` 出口 | 每个 hint 产出 +1（受 `max_hints_per_response` 截断后） |
| `carrymem_recall_reflection_inspect_duration_ms` | summary | 无 | `_run_inline_reflection` 入口 | 每次 inspect 总耗时（含超时退出场景） |

**既有 series 扩展**：`carrymem_recall_budget_utilization_ratio{layer="reflection"}` 由硬编码 0.0 改为真实 utilization = `inspected / max(1, inline_max_candidates)`。

标签均为低基数枚举（hint_type ∈ {downrank, boost, flag_conflict, stale} ≤ 4 值）。

---

## 9. Gate 0 待确认项

（与 v1.1 一致；新增 D7）

| 决策 | 内容 | 本文建议默认 |
|---|---|---|
| D7 | 内联反思产品语义与 hint 保护层 | §5.1 第 5.5 档 + §11.1 数据契约；re-rank 提示非保护；DLP 强制 |
| D8 | 内联反思告警上线时机 | series + utilization 先上线 1 周，再加 alert rule（避免误报） |

---

## 10. 实现状态（v1.2 草稿）

### 10.1 已实现（v1.2 之前所有 Slice）

（与 v1.1 §10.1 一致：在线执行入口、graph/time 真实执行、retrieval 软超时、output 硬闸、信任层截断顺序、conflict policy、sensitivity 过滤、vector 回退、evidence 预算、metrics、superseded 精确计数）

### 10.1.1 Slice 5 实施状态（2026-10-07 完成）

三阶段路径已全部落地：

- **阶段 1（文档）**：本 v1.2 草稿获 Gate 0 批准（2026-10-07），§5.1 第 5.5 档、§11 数据契约、§10.5 hindsight 三缺陷全部成立；
- **阶段 2（纯函数 + 前置测试）**：`src/carrymem/inline_reflection.py` 落地 `HintType` / `InlineReflectionHint` / `InlineReflectionReport` / `inspect_candidates_for_hints`（无 DB 写、无 metrics 发射、不耦合 `ReflectionManager`、不持有 file_lock）；`tests/test_inline_reflection.py` 11 项前置测试全绿；baseline 实测 50 候选（含 10 stale）p50=48.67ms / p90=49.84ms → `inline_timeout_ms=100` 默认值成立，无需调整；
- **阶段 3（接线）**：`_execute_recall_plan` 在 output 硬闸后调用 `_run_inline_reflection`；utilization gauge 改为 `inspected/inline_max_candidates` 实际值；metadata 增 `hints_count/reflection_timeout_hit/reflection_hints_capped`（wall-clock 不进 metadata，保证同 plan 两次执行 `to_dict()` 相等）；`RecallResult.hints` β 形态暴露；超时复用 `RETRIEVAL_TIMEOUT` 标 `BudgetLayer.REFLECTION`；hint 计数经 `metrics.increment("carrymem_recall_reflection_hints_total.<type>")` 产生。
- **附带技术债治理**：本切片触发 `tests/test_exception_narrowing.py` 宽异常门禁（41 处历史未注释 > 上限 40），经用户确认全量治理——9 处历史宽异常补 `NOTE: intentional` 及业务理由，Slice 5 新增捕获全部使用窄异常，门禁恢复绿色。
- **全量门禁**：pytest 5180 passed / 4 skipped（`--no-cov`）；black/isort/flake8/mypy/radon 聚焦复跑全绿；覆盖率未随本切片重测。

### 10.2 与 §5.1 截断顺序的差异

（与 v1.1 §10.2 一致）

### 10.3 已知遗留缺口（v1.2 更新）

| # | 项 | 状态 |
|---|---|---|
| 1 | `retrieval_timeout_ms` 软预算（mode 级，不可中断同步查询） | 文档（与 v1.1 一致） |
| 2 | **reflection 预算未接入**——v1.1 披露为"接入完成"，但产品语义未定义 + 保护层无 hint 档 + 复用接口错误假设 | **已修复（Slice 5，2026-10-07）**。剩余子项：boost/downrank 枚举已定义无产生规则；hints 计数器的 Prometheus exporter 映射与 `/metrics` E2E 断言待补 |
| 3 | `TOKENIZER_DRIFT_WARNING` 未接线 | 仍延期（需真实 tokenizer 基准集） |
| 4 | semantic 不可用时复用 `VECTOR_UNAVAILABLE_FALLBACK` 原因码 | 仍延期（扩码需先升版） |
| 5 | candidate 预算按"命中次数"计量，多模式重复命中同一内存重复计数 | 仍延期（去重维属设计决策） |
| 6 | 单条 memory 序列化固定开销约 200 token，`output.max_tokens` 过小时保护条目降级 | 文档（与 v1.1 一致） |
| 7 | 默认 `retrieval_timeout_ms=200` 下首次 vector/semantic embedding 加载会被软超时推迟 | 文档（与 v1.1 一致） |
| 8 | stale hint 候选集来自 best-effort 衰减门扫描，adapter 不暴露连接时仅产 conflict hint（降级有意为之，未单独计量） | Slice 5 新披露 |

### 10.4 测试证据

- v1.1 基线：契约 29 项 + 真实 E2E 4 项 + HTTP/MCP metrics E2E；
- Slice 5 新增：`tests/test_inline_reflection.py` 11 项前置 + `tests/test_recall_plan.py` 2 项集成（metadata/utilization 契约、零预算 REFLECTION 层截断），聚焦合计 42 项。

---

## 11. 内联反思契约（v1.2 新增章节）

### 11.1 InlineReflectionHint 数据契约

```text
InlineReflectionHint(
    storage_key: str                 # memory 主键，禁止 content 原文
    hint_type: HintType              # 封闭枚举（见 §11.2）
    confidence: float                # [0.0, 1.0]
    reasoning_short: str             # ≤ 50 字符，DLP 校验 fail-closed
    score_delta: float               # [-1.0, +1.0]，注入 §5.1 截断时的优先级调整
)
```

**不变量**：

| 编号 | 不变量 |
|---|---|
| INV-IR1 | `storage_key` 必须存在于 ranked candidates 中（避免悬空 hint） |
| INV-IR2 | `reasoning_short` 长度 ≤ 50 字符；超过则 fail-closed 弃 hint 并记 metrics |
| INV-IR3 | `score_delta` 与 `_rank_and_dedupe` 兼容（同区间，不破坏 §INV-TB3 确定性） |

### 11.2 HintType 封闭枚举

```text
downrank      候选价值低于同组其他成员，建议降权
boost         候选价值高于分数，建议加权（受 hint 总数上限保护）
flag_conflict 候选与同 namespace 其他候选存在冲突，调用方决定展示
stale         候选命中 find_decay_candidates 门（重要性 < 阈值或 stale_days 超限）
```

### 11.3 内联反思执行器（§11 实施对象）

```python
def inspect_candidates_for_hints(
    ranked: Sequence[RecallItem],
    *,
    inline_max_candidates: int,
    inline_timeout_ms: int,
) -> InlineReflectionReport:
    """纯函数 inspect——不写事务表、不发 metrics、不持锁。
    
    返回 (hints, elapsed_ms, timeout_hit, capped_count)。
    调用方负责 metrics 与 truncation 记录。
    """
```

**与 Phase 4 `ReflectionManager` 边界**：
- **不复用**：`ReflectionManager.start_run / create_proposal / apply / rollback`——事务表 + INV-P2 幂等键 + file_lock 不适合高频 recall 路径
- **可复用**：[`layers/memify.py::find_decay_candidates`](file:///Users/lin/trae_projects/carrymem/src/carrymem/layers/memify.py) 的"衰减候选"门（hint_type=stale 的来源）；[`consolidation.py::consolidate`](file:///Users/lin/trae_projects/carrymem/src/carrymem/consolidation.py) 的冲突检测输出（hint_type=flag_conflict 的来源，但不物理删除）
- **抽象层**：`InlineReflectionRule` Protocol（`def match(candidate) -> Optional[InlineReflectionHint]`），各 hint_type 注册为 rule，新规则按 §11.4 纪律加入

### 11.4 新规则加入纪律

1. 必须有 §7 验证方法（单元 + 集成 + 受控证伪）；
2. 必须有 DLP 测试（构造 PII 候选验证 hint 不含原文）；
3. 必须 baseline 测量加入后的 `_run_inline_reflection` 总耗时 P99；
4. 加入后必须更新 [PROJECT_STATUS.md](../PROJECT_STATUS.md) 与 §10.4 测试证据。

---

## 10.5 hindsight 复盘（v1.2 新增章节）

> **诚实披露**：v1.1 文档通过 Gate 0 后，Phase 5 Slice 5 实施时发现以下三处**真实设计缺陷**。本节列出缺陷、复盘根因、给出 v1.2 修复路径。

### 缺陷 #1：`ReflectionBudget` 是"已批准但产品语义未定义"的孤儿预算

**症状**：[§2.1](MEMORY_EVOLUTION_BUDGET.md#L51-L62) 给出 `inline_max_candidates=50 / inline_timeout_ms=100` 建议默认，[§10.3 第 2 项](MEMORY_EVOLUTION_BUDGET.md#L250-L258) 披露"未接入内联反思执行器，utilization 恒为 0"——但 **"内联反思执行器"从未被定义**。

**根因**：v1.1 Gate 0 决策时把 `ReflectionBudget` 当作"独立预算结构"批准，但未定义：
- 反思产出物在 recall 流程里做什么（re-rank / hint / proposal / metric？）
- 与 §5.1 截断顺序的相对位置
- 与 Phase 4 `ReflectionManager` 的边界

**v1.2 修复**：§11.1 数据契约 + §11.3 抽象层 + §11.4 加入纪律。

### 缺陷 #2：§5.1 保护层 6 档无"hint"位置

**症状**：v1.1 §5.1 第 1-5 档 + 6-8 保护层完整定义，但若选 A（re-rank 提示）实施，hint 既非普通条目也不能进保护层——**第 5 与第 6 之间需要第 5.5 档**。

**根因**：v1.1 Gate 0 时"内联反思"被当作"独立预算"看待，未考虑 hint 注入 final output 后的截断冲突。

**v1.2 修复**：§5.1 第 5.5 档（`drop_priority=50`，`protected=False`，`max_hints_per_response=20`）+ INV-TB4/INV-TB5。

### 缺陷 #3：Phase 4 `inspect_proposals` 是幻觉接口

**症状**：Phase 5 Slice 5 讨论中曾假设"复用 Phase 4 `inspect_for_proposals` 入口"。**该入口在 reflection.py 中不存在**。

**根因**：Phase 4 的真实产品形态是 `ReflectionManager.run_decay_reflection / run_consolidation_reflection`（事务性提案生命周期），与"内联反思 inspect 候选"语义不一致——前者写 `memory_reflection_runs` / `memory_reflection_outputs` 表 + INV-P2 幂等键 + file_lock，**绝不能在每次 recall 时调用**。

**v1.2 修复**：§11.3 明确"不复用 `ReflectionManager`、可复用 `find_decay_candidates` 与 `consolidate` 策略门函数"。新建议接口 `inspect_candidates_for_hints`（纯函数，不写事务表）。

### 复盘结论

v1.1 Gate 0 的失误在于**"预算结构"与"产品语义"被分离决策**——批准了 budget 但未定义 budget 的语义填充物。v1.2 修复路径：**先把语义定义完整（§11）再谈接线（§10.3 第 2 项实施）**，且接线必须遵守 §11.4 加入纪律。

---

## 12. 决策历史（v1.2 新增）

| 版本 | 日期 | 主要决策 | 状态 |
|---|---|---|---|
| v1.1 | 2026-10-06 | D5 四层预算 + 截断顺序 + 原因码 | 已批准（Gate 0） |
| v1.2 | 2026-10-07 | D7 §5.1 第 5.5 档 + §11 数据契约；D8 告警延后 | 草稿（待 Gate 0 重决策） |
