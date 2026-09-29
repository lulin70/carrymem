# ADR-014: 记忆生命周期契约（retain / recall / reflect）

## 状态: 已采纳（Accepted 2026-09-28，Gate 0 批准）
## 日期: 2026-09-28
## 决策者: 项目负责人（Gate 0 批准）
## 契约细节: [MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md](../../design/MEMORY_EVOLUTION_LIFECYCLE_CONTRACT.md)

---

## 上下文

CarryMem 现有入口按实现历史命名（`classify_and_remember` / `recall_memories` / `consolidate_memories`），三者之间没有统一的语义契约：

1. **职责边界模糊**：`consolidate_memories()` 同时做诊断、提案和应用副作用；`classify_and_remember` 内部既写原始记忆又触发图谱、规则候选等派生行为，调用方无法得知哪些是承诺行为、哪些是附带行为。
2. **语义分散**：写入口径、读取可见性、维护动作散落在 mixin 与 adapter 中，新能力（evidence、observation、proposal）没有统一的挂靠语义。
3. **不可测试**：缺少显式契约意味着缺少可断言的不变量，质量只能靠覆盖率间接保证。

上游启发（hindsight 类系统）采用 retain/recall/reflect 三阶段生命周期，但 CarryMem 必须以本地 SQLite-first、零 LLM 核心、Stable API 兼容为前提吸收该方法。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: 保持现状，逐点修补** | 在现有函数上按需加逻辑 | 无迁移成本 | 契约永远不显式；派生语义继续发散 |
| **B: 破坏性重命名三入口** | 直接改 Stable API | 语义最干净 | 违反 API_STABILITY 承诺，生态破坏 |
| **C: 生命周期语义层 + Stable API 委托** ✅ | 新增 `retain/recall/reflect` 语义入口，内部委托现有实现；现有 Stable API 签名与行为不变 | 渐进、可回退、契约可测试 | 需防新旧双轨漂移 |

## 决策

采用方案 C：

1. **`retain` = 写入语义**：委托 `classify_and_remember`，增加 `source_kind` 来源标注与冲突候选登记；旧 API 是第一实现载体。
2. **`recall` = 读取语义**：内部统一 `RecallPlan`（旧参数确定性转换）；旧 API 返回结构不变；可见性裁决（superseded/expired/unsupported/敏感级别）统一收口。
3. **`reflect` = 派生语义**：默认只 inspect + propose；apply 仅限低风险白名单或显式批准（高风险清单硬编码）。
4. **两种状态分离**：事实状态（candidate/accepted/rejected/superseded/expired/unsupported）与执行状态（proposed/approved/applied/rolled_back/failed）正交存储。
5. **不变量即契约**：每个阶段定义编号不变量（INV-*），全部纳入测试计划逐条验证。

## 后果

### 正面
- 派生行为有了统一挂靠点和审计口径；
- Stable API 零破坏，生态兼容；
- 契约不变量可被 CI 持续验证，防止语义漂移。

### 负面
- 存在新旧两套入口，需防漂移（缓解：新入口第一阶段纯委托，旧实现唯一权威）；
- 契约文档与实现的同步成本（缓解：INV 编号被测试引用，文档漂移会在评审暴露）。

## 实现参考（Gate 0 批准后）
- `src/carrymem/core/_memory_crud.py`（retain 委托点）
- `src/carrymem/core/_recall.py`（RecallPlan 转换点）
- `src/carrymem/core/_maintenance.py`（reflect 编排点）
