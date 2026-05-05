# CarryMem Benchmark Score Optimization Plan

**Created**: 2026-05-05
**Status**: Team Review & Consensus
**Target**: Improve overall score from 80.3% (B) to 90%+ (A)

---

## Current Scores

| Benchmark | Current | Target | Gap |
|-----------|---------|--------|-----|
| RuleEngine-Eval | 88.3% | 95%+ | -6.7% |
| LongMemEval | 71.5% | 85%+ | -13.5% |
| MSC | 76.6% | 85%+ | -8.4% |
| MemEval | 84.7% | 90%+ | -5.3% |
| **Overall** | **80.3%** | **90%+** | **-9.7%** |

---

## Root Cause Analysis

### Problem 1: FTS5 Search Degradation (Affects: LongMemEval, MSC, RuleEngine-Eval)

**Impact**: Recall accuracy drops to 40%, session continuity drops to 60%

**Root Cause**:
- `rules_fts` virtual table uses default `unicode61` tokenizer instead of `trigram`
- `_sanitize_fts_query` wraps all terms in double quotes (phrase queries)
- `unicode61` cannot tokenize CJK text, causing phrase queries to fail
- `search_with_rank` catches `OperationalError` and falls back to LIKE with `rank_score=0.0`
- No FTS5 tokenizer migration for `rules_fts` table

**Files**:
- [storage.py:129-135](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/rules/storage.py#L129-L135) — Missing `tokenize='trigram'`
- [storage.py:401-406](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/rules/storage.py#L401-L406) — Phrase query wrapping
- [storage.py:437-471](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/rules/storage.py#L437-L471) — Silent fallback with zero rank

**Fix**:
1. Add `tokenize='trigram'` to `rules_fts` CREATE TABLE
2. Add FTS5 tokenizer migration for existing databases
3. Improve `_sanitize_fts_query` to not wrap single terms in quotes
4. Add rank score estimation for fallback search

**Expected Impact**: Recall accuracy 40% → 80%+, Session continuity 60% → 90%+

---

### Problem 2: Decision Classification Accuracy 50% (Affects: MemEval, LongMemEval)

**Impact**: Classification accuracy 68%, decision type only 50%

**Root Cause**:
- Task detector runs BEFORE decision detector in the loop (ordering bug)
- Task keywords overlap with decision vocabulary ("migrate", "use", "integrate")
- Decision patterns missing key forms ("We'll use X", "decided to migrate")
- Over-broad "using X for" pattern causes false positives on preferences
- No type-priority resolution when multiple types match

**Files**:
- [pattern_analyzer.py:95-104](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/layers/pattern_analyzer.py#L95-L104) — Task before decision
- [pattern_analyzer.py:934-948](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/layers/pattern_analyzer.py#L934-L948) — Keyword overlap
- [pattern_analyzer.py:1092-1109](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/layers/pattern_analyzer.py#L1092-L1109) — Missing patterns
- [classification_pipeline.py:46-49](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/coordinators/classification_pipeline.py#L46-L49) — No priority resolution

**Fix**:
1. Move decision detector before task detector in the loop
2. Add decision-gating to task detector (skip if strong decision markers present)
3. Add missing decision patterns: "We'll use X", "decided to migrate", "agreed to use X"
4. Fix over-broad "using X for" pattern to require comparative prepositions
5. Implement type-priority resolution in classification pipeline

**Expected Impact**: Decision accuracy 50% → 85%+, Overall classification 68% → 80%+

---

### Problem 3: Conflict Detection Gaps (Affects: RuleEngine-Eval, LongMemEval)

**Impact**: Conflict detection 66.7%, conflict resolution 50%

**Root Cause**:
- Memory-level `ConflictType` has no `OVERLAP` type
- Rule-level `OVERLAPPING_PAIRS` too narrow: only `prefer/prefer`, `format/format`, `always/format`
- Missing pairs: `always/always`, `always/prefer`, `avoid/avoid`, `forbid/forbid`
- No bridge between memory-level and rule-level conflict detection
- Preference change detection uses Jaccard similarity >= 0.6, too high for semantically opposite preferences
- Cross-type preference changes not detected (correction overriding preference)

**Files**:
- [conflict_detector.py:19-24](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/conflict_detector.py#L19-L24) — Missing OVERLAP type
- [conflict_detector.py:198-222](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/conflict_detector.py#L198-L222) — Narrow preference change detection
- [rules/conflict_detector.py:80-84](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/rules/conflict_detector.py#L80-L84) — Narrow OVERLAPPING_PAIRS
- [carrymem.py:1433-1445](file:///Users/lin/trae_projects/carrymem/src/memory_classification_engine/carrymem.py#L1433-L1445) — No bridge to rule-level detection

**Fix**:
1. Add `OVERLAP` to memory-level `ConflictType` enum
2. Expand `OVERLAPPING_PAIRS` to include `always/always`, `always/prefer`, `avoid/avoid`, `forbid/forbid`
3. Bridge `CarryMem.check_conflicts()` to also call `RuleConflictDetector.detect()`
4. Lower Jaccard threshold for preference change detection (0.6 → 0.4)
5. Combine negation-pair logic with preference change detection
6. Add cross-type preference change detection

**Expected Impact**: Conflict detection 66.7% → 90%+, Conflict resolution 50% → 80%+

---

### Problem 4: Recall Query Matching (Affects: LongMemEval, MSC)

**Impact**: Recall accuracy 40%, session continuity 60%

**Root Cause**:
- FTS5 search degradation (Problem 1) is the primary cause
- Additionally, recall queries use short keywords ("theme", "cloud") that may not match stored content
- No query expansion or synonym mapping for recall queries

**Fix**:
1. Fix FTS5 tokenizer (Problem 1 fix)
2. Add query expansion for common recall terms
3. Improve FTS5 query construction to use OR combinations

**Expected Impact**: Recall accuracy 40% → 80%+, Session continuity 60% → 90%+

---

## Optimization Plan (Priority Order)

### P0: FTS5 Tokenizer Fix (Highest Impact)

| Step | Action | Files | Expected Score Change |
|------|--------|-------|----------------------|
| 1 | Add `tokenize='trigram'` to `rules_fts` | `rules/storage.py` | +15% recall |
| 2 | Add FTS5 migration for existing databases | `rules/storage.py` | Compatibility |
| 3 | Fix `_sanitize_fts_query` to not quote single terms | `rules/storage.py` | +5% matching |
| 4 | Add rank estimation for fallback search | `rules/storage.py` | Better ranking |
| 5 | Verify `memories_fts` also uses trigram | `adapters/sqlite_adapter.py` | Verify |

**Estimated Impact**: Overall 80.3% → 87%+

### P1: Classification Priority Fix (High Impact)

| Step | Action | Files | Expected Score Change |
|------|--------|-------|----------------------|
| 1 | Move decision detector before task detector | `pattern_analyzer.py` | +10% decision accuracy |
| 2 | Add decision-gating to task detector | `pattern_analyzer.py` | +5% decision accuracy |
| 3 | Add missing decision patterns | `pattern_analyzer.py` | +5% decision accuracy |
| 4 | Fix over-broad "using X for" pattern | `pattern_analyzer.py` | +3% preference accuracy |
| 5 | Implement type-priority resolution | `classification_pipeline.py` | +3% overall accuracy |

**Estimated Impact**: Overall 87% → 89%+

### P2: Conflict Detection Enhancement (Medium Impact)

| Step | Action | Files | Expected Score Change |
|------|--------|-------|----------------------|
| 1 | Add OVERLAP to memory-level ConflictType | `conflict_detector.py` | +10% conflict detection |
| 2 | Expand OVERLAPPING_PAIRS | `rules/conflict_detector.py` | +10% conflict detection |
| 3 | Bridge CarryMem.check_conflicts() to rule-level | `carrymem.py` | +5% conflict resolution |
| 4 | Lower Jaccard threshold for preference changes | `conflict_detector.py` | +5% preference detection |
| 5 | Add cross-type preference change detection | `conflict_detector.py` | +5% preference detection |

**Estimated Impact**: Overall 89% → 90%+

### P3: Recall Query Enhancement (Medium Impact)

| Step | Action | Files | Expected Score Change |
|------|--------|-------|----------------------|
| 1 | Add query expansion for common terms | `sqlite_adapter.py` | +5% recall |
| 2 | Improve FTS5 OR query construction | `sqlite_adapter.py` | +3% recall |
| 3 | Add synonym mapping for recall queries | New: `synonyms.py` | +3% recall |

**Estimated Impact**: Overall 90% → 92%+

---

## Implementation Timeline

| Week | Tasks | Target Score |
|------|-------|-------------|
| Week 1 | P0: FTS5 Tokenizer Fix | 87%+ |
| Week 1-2 | P1: Classification Priority Fix | 89%+ |
| Week 2 | P2: Conflict Detection Enhancement | 90%+ |
| Week 3 | P3: Recall Query Enhancement | 92%+ |
| Week 3 | Re-run all benchmarks, update scores | Final |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| FTS5 trigram migration breaks existing databases | Low | High | Test migration on copy first |
| Detector reordering causes regression in other types | Medium | Medium | Run full test suite after change |
| Expanding OVERLAPPING_PAIRS creates false positives | Medium | Low | Add confidence scoring |
| Query expansion returns too many results | Low | Low | Add relevance threshold |

---

## Success Criteria

1. Overall benchmark score >= 90% (Grade A)
2. No regression in existing 2070 tests
3. All P0 and P1 fixes implemented and verified
4. Benchmark results reproducible and documented

---

## Team Consensus

### Architect Review ✅ APPROVED

**Technical Approach Assessment**: Sound

1. **FTS5 Fix (P0)**: Correctly identified root cause. The `rules_fts` missing `tokenize='trigram'` is a clear bug — `memories_fts` already uses it. Adding trigram + migration is the right approach. The `_sanitize_fts_query` phrase-wrapping issue compounds the problem. **Agree with P0 priority.**

2. **Classification Priority (P1)**: Detector ordering is a design flaw, not a bug. Moving decision before task is correct, but we should also add the decision-gating guard to prevent future regressions. The type-priority resolution in the pipeline is architecturally important — it prevents similar issues from recurring. **Agree with P1 approach.**

3. **Conflict Detection (P2)**: The gap between memory-level and rule-level detection is a real architectural issue. Bridging `CarryMem.check_conflicts()` to also call `RuleConflictDetector.detect()` is the right unification. However, expanding `OVERLAPPING_PAIRS` needs careful consideration — too many pairs could cause false positives. **Approve with condition: add confidence scoring for new overlap pairs.**

4. **Recall Query (P3)**: Query expansion is valuable but should be implemented as a separate concern, not mixed into the FTS5 fix. **Agree with P3 as lower priority.**

**Architect Concern**: The FTS5 migration for existing databases must be tested thoroughly. Dropping and recreating the virtual table on production data could cause data loss if not handled correctly. Recommend: create new FTS5 table, rebuild index, then swap atomically.

**Verdict**: ✅ APPROVE — Technical approach is sound, priorities are correct.

---

### Coder Review ✅ APPROVED

**Implementation Feasibility**: All changes are implementable within the timeline

1. **P0 (FTS5 Fix)**: ~50 lines of code change. The `tokenize='trigram'` addition is a one-line fix. The migration needs careful implementation — suggest using `INSERT INTO new_fts(memories_fts) VALUES('rebuild')` pattern. The `_sanitize_fts_query` fix is straightforward: only wrap multi-word phrases in quotes, leave single terms unwrapped. **Estimated: 2-3 hours.**

2. **P1 (Classification Priority)**: ~30 lines of code change. Reordering the detector loop is trivial. Adding decision-gating to the task detector requires ~10 lines of guard code. The type-priority resolution in the pipeline needs more thought — suggest a simple priority map: `correction > decision > preference > task > fact`. **Estimated: 3-4 hours.**

3. **P2 (Conflict Detection)**: ~80 lines of code change. Adding `OVERLAP` to the enum is trivial. Expanding `OVERLAPPING_PAIRS` is a config change. Bridging `CarryMem.check_conflicts()` requires importing the rule-level detector and merging results. **Estimated: 4-5 hours.**

4. **P3 (Recall Query)**: ~40 lines of code change. Query expansion can be a simple dictionary mapping. **Estimated: 2-3 hours.**

**Coder Concern**: The `_sanitize_fts_query` change could affect existing behavior. Need to ensure that removing quotes from single terms doesn't break FTS5 syntax for special characters. Recommend: only remove quotes when term is purely alphanumeric.

**Verdict**: ✅ APPROVE — All changes are feasible, total estimated effort ~15 hours.

---

### Tester Review ✅ APPROVED WITH CONDITIONS

**Testing Strategy Assessment**: Adequate with additions

1. **P0 (FTS5 Fix)**: Must test:
   - New database creation with trigram tokenizer ✅
   - Migration from existing unicode61 database ✅
   - CJK search after migration ✅
   - English search still works after migration ✅
   - `_sanitize_fts_query` with special characters ✅
   - Fallback search still works when FTS5 fails ✅
   - **Missing**: Performance regression test — trigram index is larger than unicode61, need to verify no significant latency increase

2. **P1 (Classification Priority)**: Must test:
   - Decision messages correctly classified after reorder ✅
   - Task messages still correctly classified (no regression) ✅
   - Preference messages not misclassified as decision ✅
   - **Missing**: Edge cases where both decision AND correction patterns match
   - **Missing**: Performance test — does the decision-gating guard add latency?

3. **P2 (Conflict Detection)**: Must test:
   - New overlap type detected correctly ✅
   - Existing conflict types still detected ✅
   - Bridge returns both memory and rule conflicts ✅
   - **Missing**: False positive rate test for expanded OVERLAPPING_PAIRS
   - **Missing**: Performance test for O(n^2) conflict detection with many rules

4. **P3 (Recall Query)**: Must test:
   - Synonym expansion works correctly ✅
   - No irrelevant results from expansion ✅
   - **Missing**: Benchmark-specific test cases to verify score improvement

**Tester Conditions**:
1. Add performance regression tests for P0 and P1
2. Add false positive rate test for P2
3. Run full test suite (2070 tests) after each P-level change
4. Re-run all benchmarks after all changes to verify score improvement

**Verdict**: ✅ APPROVE WITH CONDITIONS — Must add performance and false positive tests.

---

### Security Review ✅ APPROVED

**Security Implications Assessment**: Low risk

1. **FTS5 Fix (P0)**: The `_sanitize_fts_query` change must maintain SQL injection protection. Currently, the method strips special characters and wraps terms in quotes. Removing quotes from single terms is safe as long as we still strip `{ } ( ) : ^ ! | *` and SQL keywords. **Recommendation: Keep the sanitization logic, only change the quoting behavior for single alphanumeric terms.**

2. **Classification Priority (P1)**: No security implications. The change only affects classification ordering, not data storage or retrieval.

3. **Conflict Detection (P2)**: The bridge between memory-level and rule-level detection introduces a new code path in `CarryMem.check_conflicts()`. Ensure the rule-level detector doesn't expose rule data that should be scope-restricted. **Recommendation: Verify that rule conflicts respect scope boundaries — a personal rule conflict should not be visible to company scope.**

4. **Recall Query (P3)**: Query expansion could potentially be exploited to return unexpected results. **Recommendation: Validate expanded terms against the same sanitization logic as the original query.**

**Security Concern**: The FTS5 migration drops and recreates the virtual table. If this happens on a production database, there's a brief window where the FTS index is empty and searches return no results. **Recommendation: Implement migration as: create new FTS5 table → rebuild index → atomic rename → drop old table.**

**Verdict**: ✅ APPROVE — Low security risk, follow recommendations for sanitization and migration safety.

---

### Consensus Summary

| Role | Verdict | Key Condition |
|------|---------|---------------|
| Architect | ✅ APPROVE | Test FTS5 migration on copy first, atomic swap |
| Coder | ✅ APPROVE | Only remove quotes from alphanumeric terms |
| Tester | ✅ APPROVE WITH CONDITIONS | Add performance + false positive tests |
| Security | ✅ APPROVE | Maintain sanitization, verify scope boundaries |

**Overall Consensus**: ✅ **APPROVED — Proceed with implementation**

**Priority Execution Order**: P0 → P1 → P2 → P3 (as planned)

**Gate Criteria**: Each P-level must pass full test suite before proceeding to next level.

---

**Sign-off**: Multi-Role Review Completed 2026-05-05
**Next Step**: Begin P0 implementation (FTS5 Tokenizer Fix)
