# 冲突裁决契约

> **版本**：v1.0
> **日期**：2026-09-28
> **状态**：已批准（Gate 0，2026-09-28；D4 按本文 P1-P6 链执行）
> **权威关系**：细化 [CARRYMEM_MEMORY_EVOLUTION_METHOD.md](CARRYMEM_MEMORY_EVOLUTION_METHOD.md) §6；裁决流程与状态机以本文为准。
> **实现边界**：Gate 0 批准前不修改 `_recall.py`、`recall_engine.py` 或任何裁决代码。

---

## 1. 问题定义

当前系统在遇到语义冲突时依赖隐式规则（latest-wins 的写入顺序、去重窗口、置信度比较），存在三类问题：

1. **静默覆盖**：旧的高置信用户偏好可能被新的系统推断无声取代；
2. **不可解释**：召回结果无法说明"为什么是这一条"；
3. **不可恢复**：被覆盖的结论没有结构化记录，用户纠正失效时无从排查。

本文定义统一的冲突检测、裁决、记录与呈现契约。总原则：

> **裁决必须有据（优先级链 + 证据），裁决必须留痕（ConflictRecord），不可裁决时必须呈现冲突而非静默择一，高风险主题 fail-closed。**

---

## 2. 默认优先级链（待批准决策 D4）

```text
P1  用户明确纠正（correction）
      ↓
P2  当前 namespace/项目作用域内的用户明确陈述（user_statement）
      ↓
P3  有明确来源且仍有效的近期观察（observation, source_kind=user_feedback/task_result）
      ↓
P4  历史观察与已确认经验（旧 observation / accepted experience）
      ↓
P5  系统派生事实（derived fact，有 provenance）
      ↓
P6  共现、相似度或图谱路径推断（inference，无直接声明）
```

**该顺序明确否决简单 latest-wins**：时间只影响同级内排序，不跨越信任层级。

### 2.1 同级内排序因子（按序）

1. 有效期状态（valid 者优先于 expired）；
2. 未被 supersede / 未被撤回；
3. 证据支持数 − 反驳数（经 evidence link 统计）;
4. 置信度；
5. 时间新者优先。

### 2.2 裁决输入（九因素）

裁决某冲突时，至少综合以下因素，任何"只看一个因素"的实现视为违约：

| # | 因素 | 来源 |
|---|---|---|
| 1 | source_kind（来源类型） | 写入时标注 |
| 2 | namespace 作用域 | 安全上下文 |
| 3 | 是否用户明确纠正 | correction 路径 |
| 4 | 有效时间（valid_from/until、expires_at） | 对象字段 |
| 5 | 支持/反驳证据数 | evidence links |
| 6 | 置信度 | 对象字段 |
| 7 | 确认状态（accepted/rejected） | 事实状态 |
| 8 | supersede/撤回状态 | 版本链 |
| 9 | 敏感级别 | 安全策略 |

---

## 3. 裁决流程

```text
检测 detect
  ├─ retain 时：新输入与现有记忆语义冲突（现有纠错路径扩展）
  ├─ reflect 时：反思发现支持/反驳证据失衡
  └─ recall 时：候选组内存在 contradict 关系
分类 classify
  ├─ 高风险主题？→ 强制 fail-closed 路径（§5）
  └─ 普通主题 → 进入裁决
裁决 resolve
  ├─ 优先级链可明确分出胜负 → 选出 selected_id
  ├─ 无法明确（同级同证据）→ 记录 conflict，呈现给调用方
  └─ 用户纠正参与 → correction 恒胜，且旧结论标记 superseded
记录 record
  └─ 写入 ConflictRecord（含 reasoning 与全部候选）
呈现 present
  ├─ recall 按 conflict_policy 呈现（hide/show_top/always）
  └─ 高风险冲突 → 不可回答降级 + 说明
```

不变量：

| 编号 | 不变量 | 违约后果 |
|---|---|---|
| INV-X1 | 任何非平凡的裁决（非"唯一候选"）必须产生 ConflictRecord | 不可追溯 |
| INV-X2 | 裁决不得跨信任层级使用时间因子（新推断不得凭"新"胜过旧的用户陈述） | 事实污染，阻断级 |
| INV-X3 | 用户纠正生效后，被纠正结论必须标记 superseded 并在 correction_resolution 任务下不再作为唯一结论返回 | 纠正失效，阻断级 |
| INV-X4 | 无法裁决时不得静默择一：要么呈现冲突，要么显式"不可回答" | 静默覆盖，阻断级 |
| INV-X5 | ConflictRecord 的 reasoning 必须引用具体优先级条目与证据计数（可机器校验） | 假解释 |

---

## 4. ConflictRecord 模型

```text
memory_conflicts
─────────────────────────────────────────────
conflict_id        TEXT PK
namespace          TEXT NOT NULL
subject_key        TEXT NOT NULL    冲突主题（规范化 subject+predicate）
candidate_ids      TEXT NOT NULL    JSON 数组：参与冲突的对象 id 列表
conflict_type      TEXT NOT NULL    preference / fact / rule / entity_state
resolution_status  TEXT NOT NULL    unresolved / resolved / user_decided / expired
resolution_policy  TEXT NOT NULL    采用的优先级链版本（如 chain-v1）
selected_id        TEXT             裁决结果（unresolved 时为 NULL）
reasoning          TEXT NOT NULL    结构化裁决理由（优先级条目 + 证据计数）
created_at         TEXT NOT NULL
resolved_at        TEXT
```

索引：`(namespace, subject_key, resolution_status)`。

状态机：

```text
unresolved ──自动裁决──→ resolved
    │                        │
    │────用户选择──→ user_decided
    │                        │
    └──全部候选过期──→ expired      resolved ──再纠正──→ 新 ConflictRecord
```

不变量 INV-X6：`resolved` 记录的 `selected_id` 必须存在于 `candidate_ids` 且该对象当时处于 accepted/candidate 状态；用户再纠正产生**新记录**而非改写旧记录（审计不可变）。

---

## 5. 高风险主题（fail-closed 清单）

以下主题的冲突**禁止自动裁决**，必须呈现冲突或要求用户确认：

```text
安全策略与权限
隐私与敏感属性（健康、财务、身份凭证类）
删除与保留决策
凭证与密钥相关内容
外部通信行为（发送、导出、共享）
规则覆盖（forbid / always / override）
跨 namespace 内容
```

不变量 INV-X7：上表主题的冲突若被系统自动选定单一结论，即为阻断级违约；正确行为是进入 `unresolved` 并显式呈现。

---

## 6. 与现有代码的对应

| 现有机制 | 位置 | 演进方向 |
|---|---|---|
| 纠错检测 | `core/_classification.py` 纠错分支 | 产出 correction + ConflictRecord（P1 恒胜写入） |
| 去重窗口 | `consolidation.py::DEDUP_WINDOW_HOURS` | 保留为重复检测策略，不再隐式承担冲突裁决 |
| `check_conflicts()` | Stable API | 保留签名；实现升级为查询 `memory_conflicts` 的兼容投影 |
| 边置信度 | `memory_relations.confidence`（ADR-013） | contradicts 关系作为冲突检测输入之一 |
| 版本链 supersession | `version_chain_id` / `superseded_at` | 纠正生效时由裁决器调用，替代隐式覆盖 |

---

## 7. 召回呈现策略（conflict_policy）

| 策略 | 行为 | 适用 |
|---|---|---|
| `hide`（默认） | 只返回裁决胜者；结果附带 `conflict_status=resolved` 与 conflict_id | 普通任务 |
| `show_top` | 胜者在前，败者降权附带返回 | fact_lookup、timeline_review |
| `always` | 全部候选等权返回 + 冲突说明 | conflict_explanation 任务 |

不变量 INV-X8：无论何种策略，`correction_resolution` 任务下 correction 必须排第一（INV-C3 的呈现侧保障）。

---

## 8. Gate 0 待确认项

| 决策 | 内容 | 本文建议默认 |
|---|---|---|
| D4 | 优先级链顺序 | §2 的 P1→P6 链，否决 latest-wins |
| （关联） | 高风险清单范围 | §5 七类，宁可多列不可漏列 |

负责人可调整顺序或清单；调整需同步更新[测试计划](../testing/MEMORY_EVOLUTION_TEST_PLAN.md)中 INV-X2/X3/X7 的测试用例。
