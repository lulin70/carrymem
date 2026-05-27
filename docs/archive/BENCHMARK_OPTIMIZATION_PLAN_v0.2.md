# CarryMem v0.3.0 Benchmark Optimization Plan

> Based on official LongMemEval evaluation (42.6%, 500Q baseline)
> Date: 2026-05-07
> Version: v0.3.0 baseline → v0.3.0 target

## 1. Current Baseline (v0.3.0)

| Question Type | Score | Gap |
|---------------|-------|-----|
| single-session-user | **67.1%** | Baseline OK |
| knowledge-update | **62.8%** | Baseline OK |
| single-session-preference | **46.7%** | Needs improvement |
| multi-session | **42.1%** | Significant gap |
| single-session-assistant | **26.8%** | Major gap |
| temporal-reasoning | **24.1%** | Critical gap |
| **Overall** | **42.6%** | **Target: 55%+ for v0.3.0** |

## 2. Root Cause Analysis

### 2.1 Temporal Reasoning (24.1%) — Critical

**Symptom**: 76% of failures show "memories don't contain information" — CarryMem's FTS5 keyword search cannot recall time-stamped memories.

**Root cause**:
- FTS5 is a **keyword matching engine**, not a semantic search engine
- Temporal queries like "How many days between X and Y?" contain no keywords that match stored memories
- CarryMem stores memories with timestamps but **does not use timestamps in recall**
- The `_expand_query` dictionary is hardcoded for specific scenarios, useless for general temporal queries

**Example failure**:
- Q: "How many days had passed between the Sunday mass at St. Mary's Church and the Ash Wednesday?"
- Expected: "30 days"
- Got: "I don't have enough information" — because "Sunday mass" and "Ash Wednesday" don't match any FTS5 trigrams

### 2.2 Single-Session-Assistant (26.8%) — Major

**Symptom**: CarryMem fails to recall information that the AI assistant previously said.

**Root cause**:
- CarryMem's `classify_and_remember()` is designed for **user messages**, not assistant messages
- Assistant messages are stored with `[Assistant said]` prefix, but this prefix is not searched for
- The classification engine treats assistant messages as "task" type (low priority), not as "decision" or "fact"
- FTS5 search for "what did you suggest for X" returns nothing because the query doesn't match stored content

### 2.3 Multi-Session (42.1%) — Significant

**Symptom**: Cross-session aggregation questions fail (e.g., "How many total X across all sessions?").

**Root cause**:
- CarryMem stores individual memories but **cannot aggregate** across memories
- FTS5 returns top-20 results, but aggregation questions may need **all** relevant memories
- No "summarization" or "counting" capability in the recall layer
- The answer generation LLM only sees top-20 memories, missing information from other sessions

### 2.4 Single-Session-Preference (46.7%) — Moderate

**Symptom**: Preference-based recommendations fail when the preference is implicit.

**Root cause**:
- Explicit preferences ("I prefer dark mode") are stored correctly
- Implicit preferences (inferred from behavior) are not captured
- FTS5 search for "recommend a restaurant" doesn't match "I love Italian food"

## 3. Optimization Plan

### Phase 1: Quick Wins (Target: 42.6% → 50%+, ~1 week)

#### P1.1: Temporal Metadata in Recall
**Priority**: Critical | **Effort**: Medium | **Expected gain**: +5-8%

- Add `created_at` timestamp to FTS5 search results
- When query contains temporal keywords ("when", "how many days", "last week", "before", "after"), include a **time-filtered recall** pass
- Store session dates alongside memories, use date ranges to narrow recall
- Implementation: Modify `recall_memories()` to detect temporal queries and add date-range filtering

```python
# In sqlite_adapter.py recall_memories():
if self._is_temporal_query(query):
    # Extract date references from query
    # Add WHERE created_at BETWEEN ? AND ? to SQL
    # Also return memories with timestamps for LLM to reason about
```

#### P1.2: Increase Recall Limit for Aggregation Queries
**Priority**: High | **Effort**: Low | **Expected gain**: +3-5%

- Detect aggregation queries ("how many", "total", "all") and increase recall limit from 20 to 50+
- Pass all recalled memories to the answer generation LLM
- Implementation: Simple heuristic in `recall_memories()`

```python
if any(w in query.lower() for w in ["how many", "total", "all", "sum", "count"]):
    limit = 50  # instead of default 20
```

#### P1.3: Improve Assistant Message Classification
**Priority**: High | **Effort**: Low | **Expected gain**: +3-5%

- Classify `[Assistant said]` messages as "decision" type (higher priority) instead of "task"
- Add "assistant-knowledge" memory type for AI-provided information
- When query asks "what did you suggest/recommend/tell me", search for `[Assistant said]` prefix

```python
# In pattern_analyzer.py:
if content.startswith("[Assistant said]"):
    return MemoryType.DECISION  # Higher priority than TASK
```

### Phase 2: Architecture Improvements (Target: 50% → 60%+, ~2-3 weeks)

#### P2.1: Hybrid Search (FTS5 + Embedding)
**Priority**: High | **Effort**: Large | **Expected gain**: +8-12%

- Add optional embedding-based semantic search alongside FTS5
- Use a lightweight embedding model (e.g., `all-MiniLM-L6-v2`, 80MB) for local inference
- Merge FTS5 and embedding results with reciprocal rank fusion
- Keep FTS5 as primary (zero-cost), use embedding as secondary (low-cost)

**Architecture**:
```
Query → FTS5 Search (fast, zero-LLM) → candidates_1
      → Embedding Search (local model) → candidates_2
      → Reciprocal Rank Fusion → merged_results
```

**Why this works**: FTS5 excels at exact keyword matching (user facts), embedding excels at semantic matching (temporal, preference, assistant). Combining both covers all question types.

#### P2.2: LLM-Powered Query Expansion
**Priority**: Medium | **Effort**: Medium | **Expected gain**: +3-5%

- Replace hardcoded `_expand_query` dictionary with LLM-based query expansion
- Use the answer-generation LLM to expand queries before recall
- Example: "How many days between X and Y?" → ["X", "Y", "date of X", "date of Y", "timeline"]
- Cost: ~50 tokens per query expansion (minimal)

```python
def _llm_expand_query(self, query: str) -> list[str]:
    prompt = f"Expand this search query into 5-10 search terms for finding relevant memories:\nQuery: {query}\nSearch terms:"
    # Call LLM, parse response
    # ~50 tokens cost per query
```

#### P2.3: Memory Summarization
**Priority**: Medium | **Effort**: Medium | **Expected gain**: +2-4%

- Periodically summarize related memories into higher-level concepts
- Store summaries as "summary" type memories alongside individual memories
- When answering aggregation questions, use summaries instead of raw memories
- Example: "User visited 5 restaurants: A, B, C, D, E" → summary: "User has tried 5 restaurants"

### Phase 3: Advanced Features (Target: 60% → 70%+, ~4-6 weeks)

#### P3.1: Temporal Reasoning Engine
**Priority**: Medium | **Effort**: Large | **Expected gain**: +5-8%

- Build a dedicated temporal reasoning module
- Extract and store temporal relationships (before, after, during, N days between)
- When query requires temporal reasoning, use the temporal module instead of keyword search
- Implementation: Parse dates from stored content, build a temporal graph

#### P3.2: Multi-Hop Retrieval
**Priority**: Low | **Effort**: Large | **Expected gain**: +3-5%

- For multi-session questions, perform iterative retrieval
- First recall: find relevant sessions → Second recall: find specific memories within those sessions
- Chain multiple recall operations to gather all necessary information

#### P3.3: Context-Aware Answer Generation
**Priority**: Low | **Effort**: Medium | **Expected gain**: +2-3%

- Improve the answer generation prompt to better handle different question types
- Use question-type-specific prompts (temporal, aggregation, preference)
- Include memory metadata (type, timestamp, confidence) in the generation prompt

## 4. Priority Matrix

| ID | Optimization | Effort | Gain | Priority | Phase |
|----|-------------|--------|------|----------|-------|
| P1.1 | Temporal metadata in recall | Medium | +5-8% | 🔴 Critical | 1 |
| P1.2 | Increase recall limit | Low | +3-5% | 🟡 High | 1 |
| P1.3 | Assistant message classification | Low | +3-5% | 🟡 High | 1 |
| P2.1 | Hybrid search (FTS5 + embedding) | Large | +8-12% | 🔴 Critical | 2 |
| P2.2 | LLM query expansion | Medium | +3-5% | 🟡 High | 2 |
| P2.3 | Memory summarization | Medium | +2-4% | 🟢 Medium | 2 |
| P3.1 | Temporal reasoning engine | Large | +5-8% | 🟡 High | 3 |
| P3.2 | Multi-hop retrieval | Large | +3-5% | 🟢 Medium | 3 |
| P3.3 | Context-aware generation | Medium | +2-3% | 🟢 Medium | 3 |

## 5. Expected Score Trajectory

| Version | Overall | User | Knowledge | Preference | Multi | Assistant | Temporal |
|---------|---------|------|-----------|------------|-------|-----------|----------|
| v0.3.0 (current) | 42.6% | 67.1% | 62.8% | 46.7% | 42.1% | 26.8% | 24.1% |
| v0.3.0 (Phase 1) | ~50% | 70% | 65% | 50% | 48% | 35% | 35% |
| v0.3.0 (Phase 2) | ~60% | 75% | 70% | 58% | 55% | 45% | 50% |
| v0.4.0 (Phase 3) | ~70% | 80% | 75% | 65% | 62% | 55% | 60% |

## 6. Key Principle

**CarryMem's design tradeoff is deliberate**: zero-LLM ingestion + low latency + SQLite-only. The optimization plan must preserve these core advantages:

- ✅ Hybrid search with **optional** embedding (not required, FTS5 still primary)
- ✅ LLM query expansion uses **minimal** tokens (~50 per query)
- ✅ Temporal metadata uses existing **timestamps** (no new infrastructure)
- ❌ Do NOT add vector DB as a hard dependency
- ❌ Do NOT require LLM for ingestion (keep zero-LLM ingestion)
- ❌ Do NOT increase P99 latency above 5ms

The goal is to **narrow the accuracy gap** while **maintaining the efficiency advantage** that makes CarryMem unique.
