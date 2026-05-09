# CarryMem 战略方向：从产品初心出发

> 日期：2026-05-07
> 基于：v0.1.6 官方benchmark基线数据

## 1. 产品初心回顾

CarryMem解决的核心问题是：**AI Always Forgets Who You Are**

产品定位是 **Identity Layer**（身份层），不是通用记忆检索系统。用户关心的是：
- "我偏好dark mode" → AI下次还记得吗？
- "我上次纠正了" → AI改了吗？
- "我决定用React" → AI还知道吗？

这些场景的特征是：**用户主动表达、明确意图、高价值**。这恰好是FTS5关键词匹配能覆盖的场景。

## 2. 官方Benchmark数据的诚实解读

| Benchmark | 得分 | 对标 | 解读 |
|-----------|------|------|------|
| LongMemEval | 12.7% F1 | PropMem 55% | 检索层太弱，语义匹配几乎为零 |
| LoCoMo | 27.14% | EverOS 93% | 长对话信息碎片化，FTS5拼不回上下文 |
| MSC | 31.2% F1 | EverOS ~65% | 人物偏好提取勉强可用 |

**关键洞察**：12.7%和27.14%指向同一个根因——FTS5没有语义理解。但这不意味着CarryMem没有价值，而是说明**CarryMem当前只覆盖了它设计目标的一部分场景**。

## 3. 两个选择的深度分析

### 选择一：先优化再对外

**加embedding检索**（all-MiniLM-L6-v2，80MB），预期LongMemEval从12.7%拉到30-40%。

**优点**：
- 分数好看，能和竞品对话
- 技术上可行，2-3周能完成

**风险**：
- 失去"零向量依赖"定位——这是CarryMem最独特的卖点
- 变成"又一个带向量的记忆系统"，和Mem0/Zep同质化
- 80MB的embedding模型对轻量部署场景是负担
- 30-40%仍然远低于PropMem的55%，还是不好看

**核心矛盾**：加embedding后，CarryMem的差异化在哪里？如果只是"比Mem0便宜但分数更低"，这不是一个有竞争力的定位。

### 选择二：先对外，标注清楚局限

**优点**：
- 诚实，开源社区尊重诚实
- 31.2%的MSC F1可以说故事——"轻量级方案，有限条件下达到这个水平"
- 保持产品定位清晰

**风险**：
- 12.7%的LongMemEval很难解释
- 可能被解读为"产品不行"

## 4. 我的建议：第三条路——"分层架构，渐进增强"

**核心思路**：不选"加不加embedding"这个二元问题，而是把CarryMem做成**分层的、可插拔的架构**。

### 架构设计

```
CarryMem v0.2 Architecture:

Layer 0: FTS5 Keyword Recall (默认，零依赖)
  → 覆盖场景：用户主动表达的偏好、决策、纠正
  → 预期得分：LongMemEval ~15%, MSC ~35%
  → 价值：1.3ms P99, 零LLM摄入, SQLite only

Layer 1: Local Embedding Recall (可选，80MB)
  → 覆盖场景：语义相似但措辞不同的查询
  → 预期得分：LongMemEval ~35%, MSC ~50%
  → 价值：语义理解，仍保持本地部署

Layer 2: LLM-Augmented Recall (可选，需API)
  → 覆盖场景：多跳推理、时间推理、跨会话聚合
  → 预期得分：LongMemEval ~50%, MSC ~60%
  → 价值：深度理解，但增加token成本
```

### 产品故事

> "CarryMem is the **only memory system that starts at zero cost and scales up**.
>
> - **Starter**: FTS5-only, 1.3ms, SQLite, zero LLM tokens — perfect for user identity
> - **Enhanced**: Add local embedding (80MB) for semantic recall — still no cloud dependency
> - **Advanced**: Add LLM-augmented recall for complex reasoning — when you need it
>
> You don't pay for what you don't use."

这个故事的竞争力在于：**其他系统要么全有要么全无，CarryMem是唯一可以按需升级的**。

### 对标重新定位

不是和PropMem比F1分数（我们永远打不过专门优化的系统），而是比**性价比**：

| 系统 | LongMemEval F1 | Token成本 | 向量DB | 部署复杂度 |
|------|---------------|----------|--------|-----------|
| PropMem | ~55% | 极高 | 是 | 高 |
| EverOS | ~93% | 极高 | 是 | 极高 |
| **CarryMem L0** | ~15% | **接近零** | **否** | **pip install** |
| **CarryMem L1** | ~35% | 低 | **否**(本地) | +80MB |
| **CarryMem L2** | ~50% | 中 | 否 | +API key |

## 5. 具体行动方案

### Phase 0（立即）：诚实发布 v0.1.6 baseline

- README标注"v0.1.6 baseline (FTS5-only)"
- 公布所有官方分数，不加修饰
- 在README中明确说明：**CarryMem当前是FTS5-only模式，适合用户身份记忆场景，不适合通用对话检索**
- 写一篇技术博客："Why Our Benchmark Scores Look Bad (And Why That's OK)"

### Phase 1（1-2周）：实现Layer 1 — Local Embedding

- 集成 `all-MiniLM-L6-v2`（80MB，sentence-transformers）
- 用 `sqlite-vss` 或 `sqlite-vec` 存储向量（保持SQLite-only！）
- FTS5 + Embedding 双路召回 + Reciprocal Rank Fusion
- 重新跑官方benchmark，预期LongMemEval 30-40%

### Phase 2（2-3周）：实现Layer 2 — LLM-Augmented Recall

- 对复杂查询（temporal, multi-hop, aggregation）使用LLM做query expansion
- 每次扩展约50 tokens，成本极低
- 预期LongMemEval 45-55%

### Phase 3（同步）：LaMP个性化评测

- 修复HuggingFace下载问题
- LaMP的7个个性化任务对产品故事有帮助
- "个性化输出"比"记忆检索"更好懂

## 6. 关于12.7%这个数字

12.7%看起来很糟，但它其实验证了一个重要事实：**纯关键词匹配在通用对话检索场景下确实不够用**。

这不是CarryMem的bug，而是设计选择的结果。CarryMem选择用FTS5换取：
- 1.3ms P99延迟（vs Mem0 120ms）
- 零LLM摄入（vs 全链路LLM）
- SQLite only（vs 向量DB集群）

**这些优势在用户身份记忆场景下是决定性的**，但在通用对话检索场景下不够。

所以正确的做法不是隐藏12.7%，而是**重新定义CarryMem的适用场景**，然后通过分层架构扩展覆盖范围。

## 7. 结论

**推荐：第三条路——分层架构，渐进增强**

1. 立即诚实发布v0.1.6 baseline（FTS5-only分数）
2. 1-2周内实现Layer 1（local embedding），重新跑benchmark
3. 用分层架构作为产品故事的核心差异化
4. LaMP评测同步推进，补全个性化维度

**不推荐**：加embedding后假装CarryMem一直就有这个能力。诚实是开源社区最看重的品质。

**最不推荐**：继续用自建的93分报告。那不是产品评测，那是自嗨。
