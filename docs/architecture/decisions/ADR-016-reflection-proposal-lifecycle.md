# ADR-016: Reflection Proposal 生命周期与审批分级

## 状态: 已采纳（Accepted 2026-09-28，Gate 0 批准）
## 日期: 2026-09-28
## 决策者: 项目负责人（Gate 0 批准）
## 契约细节: [MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md](../../design/MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md)

---

## 上下文

当前反思/维护能力把"分析"和"改数据"混在一个动作里：

1. `consolidate_memories()` 一次调用同时输出去重、supersede、衰减等副作用，无提案阶段、无审批、无回滚；
2. `MemifyEngine.derive_facts()` 的派生结果直接落库且被当作可用记忆；
3. `auto_decay()` 直接改重要性分值，无版本、无回滚；
4. 规则晋升管线虽有确认队列，但与其他反思路径不统一，且"高风险必须人工"未在代码层硬编码。

后台化后的反思任务还面临崩溃恢复问题：没有 run 概念、没有幂等键，重试必然产生重复派生对象。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 保持直接副作用** | 现状 | 简单 | 不可审计、不可回滚、重试即重复 |
| **B: 全部人工审批** | 所有提案都等用户确认 | 最安全 | 体验差，低风险操作也被阻塞 |
| **C: inspect/propose/apply 三段 + 风险分级审批** ✅ | Run 记录 + Proposal 状态机 + 低风险白名单自动/高风险硬编码确认 | 安全与自动化平衡；幂等可恢复 | 状态机复杂度（以表结构与测试换取可控性） |

## 决策

采用方案 C：

1. **Run 层**：`memory_reflection_runs` 记录每次反思（type、input_snapshot、config_snapshot、cursor、status、idempotency_key），支持 interrupted 恢复与决定性重放。
2. **Proposal 层**：`memory_reflection_outputs` 记录提案（payload、证据引用、置信度、reasoning、risk_level、状态机、rollback_ref）。
3. **审批分级（D1 建议默认）**：
   - 低风险白名单（dedup_merge 强证据、expire_projection、accepted 事实的 profile 重建、有上限的边强化）可 `approved_by="auto"`；
   - 高风险清单（规则晋升 forbid/always/override、覆盖用户偏好、删除/批量 forget/密钥权限、跨 namespace、高敏感推断、外部行为影响、model_claim 首次 accepted）必须人工确认；
   - **高风险清单代码硬编码，用户配置只能扩大不能缩小**（auto_accept 不构成绕过通道）。
4. **幂等与恢复（D6 建议默认）**：at-least-once + 幂等执行 + 可重试，不承诺 exactly-once；proposal 以 `(namespace, proposal_type, payload_hash)` 幂等；单提案重试 ≤ 3 次后转人工。
5. **apply 单提案单事务**，必须写 rollback_ref；rollback 撤销派生投影，原始 `memories` 层永不被 apply 触碰。
6. **逐策略迁移**：consolidation P0/P1/P2、Memify 三动作、规则晋升逐个改造为提案策略，新旧路径并行对拍后切换。

## 后果

### 正面
- 反思全程可审计（run/proposal/证据链/批准记录）；
- 崩溃恢复与重试安全（幂等键）；
- "系统变聪明"与"用户控制"的冲突有了制度化解法。

### 负面
- 两张新表 + 状态机维护成本；
- 全审批路径的低风险操作也多一次落库（缓解：低风险自动应用无人工等待）。

## 实现参考（Gate 0 批准后）
- `src/carrymem/consolidation.py`（策略化改造）
- `src/carrymem/layers/memify.py`（derive_facts/reinforce_edges/auto_decay 提案化）
- `src/carrymem/rules/promotion_pipeline.py`（统一到 proposal 审批分级）
