# ADR-017: 冲突裁决策略（信任层级优先级链）

## 状态: 提议（Proposed）— 待 Gate 0 批准
## 日期: 2026-09-28
## 决策者: 待项目负责人批准
## 契约细节: [MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md](../../design/MEMORY_EVOLUTION_CONFLICT_RESOLUTION.md)

---

## 上下文

系统当前对语义冲突的处理是隐式的：

1. 纠错路径靠 `_classification.py` 的关键词与历史匹配，纠正之后旧结论未必结构化失效；
2. 去重窗口（`DEDUP_WINDOW_HOURS=24`）隐式承担了"新数据胜出"的裁决；
3. 召回结果无法解释"为什么是这一条"，也无法呈现"这里有冲突"；
4. 无 ConflictRecord：被覆盖的结论无结构化记录，纠正失效时无从排查。

关键矛盾：**latest-wins 简单直观，但新信息未必更可信**——一条系统推断（共现、相似度）按时间新于用户三个月前的明确偏好，latest-wins 会用推断覆盖用户事实。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: latest-wins** | 时间新者胜 | 实现最简 | 推断可覆盖用户事实；纠正与偏好地位相同 |
| **B: 纯置信度比较** | 分数高者胜 | 数值化 | 置信度语义不统一（用户陈述 vs 推断的分数不可比） |
| **C: 来源信任层级优先级链 + 综合因子** ✅ | 层级恒定，时间/证据/置信度只在同级内排序 | 用户事实受层级保护；可解释；可审计 | 需要来源分类（source_kind）先落地 |

## 决策

采用方案 C（D4 建议默认）：

```text
P1 用户明确纠正 > P2 当前作用域用户明确陈述 > P3 有来源且仍有效的近期观察
  > P4 历史观察与已确认经验 > P5 系统派生事实 > P6 共现/相似度/图谱路径推断
```

1. **时间不跨层**：时间只影响同级内排序，新推断永远不能凭"新"越过旧用户陈述（INV-X2）。
2. **九因素裁决**：来源类型、作用域、是否纠正、有效时间、证据计数、置信度、确认状态、supersede 状态、敏感级别——禁止单因素裁决。
3. **ConflictRecord 落库**：非平凡裁决必产记录（含 reasoning 与优先级条目引用，可机器校验）；不可裁决时呈现冲突或显式"不可回答"，禁止静默择一。
4. **高风险主题 fail-closed**：安全/隐私/删除/凭证/外部通信/规则覆盖/跨 namespace 七类冲突禁止自动裁决。
5. **呈现策略**：conflict_policy = hide（默认）/ show_top / always；correction_resolution 任务下 correction 恒第一。
6. **与现有机制对接**：纠正路径产 ConflictRecord + supersede 版本链；`check_conflicts()` 升级为兼容投影；ADR-013 的 `contradicts` 语义边作为冲突检测输入。

## 后果

### 正面
- 用户事实获得结构性保护，纠正有制度性生效路径；
- 裁决可解释（reasoning 引用优先级条目），支撑 explain_memory；
- 冲突可查询、可审计、可恢复。

### 负面
- 裁决逻辑比 latest-wins 复杂（缓解：优先级链是查表而非启发式；INV-X2/X3/X7 有负向测试守卫）；
- source_kind 标注质量成为前置依赖（缓解：标注在 retain 写入口收口，ADR-014/015 已覆盖）。

## 实现参考（Gate 0 批准后）
- `src/carrymem/core/_classification.py`（纠正分支 → ConflictRecord）
- `src/carrymem/adapters/sqlite/recall_engine.py`（可见性/呈现层接入）
- `src/carrymem/consolidation.py`（去重窗口降级为重复检测，不再承担裁决）
