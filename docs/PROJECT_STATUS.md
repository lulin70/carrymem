# CarryMem — Project Status

**Version**: v0.9.8
**Last Updated**: 2026-07-27
**Maintainer**: CarryMem Team

---

## v0.9.8 Project Status (2026-07-27)

**Current State**: Production-ready beta. Tech debt cleanup ongoing via DevSquad 7-role methodology.

### Recent Releases (v0.9.x series)

| Version | Date | Key Changes |
|---------|------|-------------|
| v0.9.8 | 2026-07-27 | Knowledge graph deletion completeness: `forget()` cascades to `memory_entities` + `memory_relations` (TD-066). 4 new tests. Oracle Agent Memory report启发. |
| v0.9.7 | 2026-07-26 | Tech debt cleanup: TD-003b/009/011b/002 follow-ups (deleted cli.py facade, added TUI fallback tests, downgraded SQLITE_SCHEMA to P3) |
| v0.9.6 | 2026-07-26 | Nightly slow test threshold fix (store_messages batch API) + release.yml cp consistency |
| v0.9.5 | 2026-07-26 | Nightly slow test fix + release.yml cp consistency |
| v0.9.4 | 2026-07-25 | TD-063/TD-064/TD-065: test skip cleanup + flake8 bugbear fix + ruff config |
| v0.9.3rc1 | 2026-07-22 | TD-015 Password-based publish restored (OIDC abandoned) |
| v0.9.2 | 2026-07-20 | P3 Tech Debt Cleanup: TD-031/049/050/051/053/054 |
| v0.9.1 | 2026-07-20 | TD-055: mypy src/ baseline errors cleared 9 → 0 |
| v0.9.0 | 2026-07-20 | UI/UX Overhaul — Morandi Aesthetic + Accessibility + Onboarding |

### Test & Quality Metrics (v0.9.8)

- **Non-e2e tests**: 4666 passed, 0 failed, 4 skipped (vector/semantic optional deps)
- **TUI tests**: 97 passed (including 3 new TD-011b fallback tests)
- **Lint**: flake8 bugbear 0 errors, black clean, isort clean, mypy 0 errors
- **Complexity**: radon 0 D/E/F functions
- **Coverage**: ≥80% on core modules

### v0.8.0 Project Assessment (2026-07-17, archived)

**7-Dimension Maturity Score**: B+ (77/100)

### Assessment Summary

| Dimension | Score | Status |
|-----------|-------|--------|
| Architecture | B+ | PromptDelegateMixin MRO corrected, doctor Python 3.12 aligned |
| Modularity | A- | ✅ No ghost features, all 31 tools have handlers |
| Security | B+ | MCP XSS strict_mode enabled, SecurityError propagation fixed |
| Performance | B | Smoke tests added to CI (4 tests, not marked slow) |
| Maintainability | B+ | Documentation consistency verified across 15 files |
| Testability | B | 4405 tests pass, VSCode extension tests added (14 Tier 1 + 5 Tier 2) |
| Observability | B | health_check uses O(1) count() instead of O(n) recall |

### P0 Fixes Completed

1. **VSCode Extension UI E2E Framework** — Two-tier test framework:
   - Tier 1: 14 integration tests (CI-runnable, mock execFile, all passing)
   - Tier 2: 5 VSCode UI E2E user journeys (@vscode/test-electron, activation/commands/tree/config/contract)
   - CI job `vscode-ext` added to ci.yml
2. **Performance Test CI Deselect** — Created `tests/test_performance_smoke.py` (4 tests, not marked slow):
   - Classify/recall/forget/batch smoke tests with loose thresholds (10x CI_FACTOR)
   - Runs in CI via `-m "not slow"`, catches catastrophic regressions only
3. **MCP Access Control E2E** — 5 new E2E tests + bug fix:
   - `TestMCPAccessControlE2E` (4 tests): write denied/succeed, forget denied, read open mode
   - `TestMCPConfidenceLabelE2E` (1 test): confidence label flows through MCP
   - **Bug fix**: `SecurityError` now propagates as `access_denied` (was `internal_error`)

### P1 Fixes Completed

- **Documentation**: 10 consistency fixes (version numbers, test counts, i18n tool counts, milestones)
- **CI/CD**: benchmark.yml advisory comments, ci.yml lint blocking, dependabot.yml, ci.yml YAML syntax fix
- **Directory**: ASSESSMENT/planning docs archived, 13 e2e tests moved to tests/e2e/, .gitignore补全
- **Architecture**: doctor Python 3.12, health_check O(1) count(), MCP XSS strict_mode=True
- **Testing**: Weak assertion `>0.0` → `>0.1` (test_context_and_scoring.py), e2e directory unified

### Tech Debt Plan 2026-07-17 — P0 Batch Complete

**Plan**: `docs/TECH_DEBT_PLAN.md` (living document, 50 items: P0:5, P1:22, P2:13, P3:10)
**Consensus**: 7-role DevSquad parallel review completed, all 7 blockers resolved in v2

**P0 Items Completed (5/5)**:
1. **TD-001**: pip upgraded to `>=26.1.2` across 13 locations (CVE remediation)
2. **TD-002**: `rule_engine` lazy init failure now logs warning (was silent `pass`); 2 unit tests added
3. **TD-003a**: 2 dead-code symbols removed (`clear_working_memory`, `_has_word_overlap`)
4. **TD-004**: benchmark.yml matrix `['3.11','3.12']` → `['3.12']` (setup.py requires ≥3.12)
5. **TD-032**: SQL injection audit complete — 4 f-string SQL sites all safe (whitelist/constant/parameterized)

**Next**: P1 batch (22 items) — test-first → architecture refactor → DevOps+code quality

### Test Results

- **Total**: 4371 passed, 7 skipped, 71 deselected, 0 failed (P0 batch, `--no-cov`)
- **Previous baseline**: 4405 passed, 17 skipped, 70 deselected (pre-P0)
- **Coverage**: 80.88% (meets ≥80% gate, pre-P0 baseline)
- **VSCode Extension**: 14/14 Tier 1 tests passing
- **Performance Smoke**: 4/4 tests passing (CI-runnable)

---

## Current Release: v0.8.0

**Theme**: Graphify — MCP Graph Query Tools + Edge Confidence Labels

**Release Date**: 2026-07-14
**PyPI**: `carrymem==0.8.0` ([PyPI](https://pypi.org/project/carrymem/))
**Git Tag**: [v0.8.0](https://github.com/lulin70/carrymem/releases/tag/v0.8.0)

### Core Features (v0.8.0)

- **3 MCP Graph Query Tools**: New graph-exploration surface for the MCP layer.
  - `query_graph(entity_text, max_hops=2, limit=20)` — multi-hop BFS graph traversal.
  - `shortest_path(src_entity, dst_entity, max_hops=4)` — shortest path lookup between two entities.
  - `get_memory_impact(memory_id)` — graph-based memory impact assessment.
- **Edge Confidence Labels**: Relations now carry a confidence label so consumers can
  distinguish deterministic facts from inferred or ambiguous links.
  - `EXTRACTED` — deterministic extraction via `EntityNormalizer` pattern matching.
  - `INFERRED` — LLM-based semantic inference (reserved for future expansion).
  - `AMBIGUOUS` — ambiguous relation requiring user confirmation (reserved for future expansion).
- **MCP integration**: New tools registered alongside existing recall/forget MCP tools,
  reusing the SQLite-native Knowledge Graph introduced in v0.7.0.
- **Backward compatible**: Existing `recall_graph()` / `recall_by_entity()` / `recall_by_relation()`
  APIs unchanged; new tools layer on top of the same KnowledgeGraph engine.

### Previous Release: v0.7.3 (Security Hardening)

- **Fernet-only encryption**: Encryption stack consolidated to a single Fernet-based
  implementation. Legacy AES-128 paths removed to eliminate crypto ambiguity and
  reduce attack surface.
- **WAL throttle**: SQLite WAL checkpoint throttling to prevent disk I/O spikes during
  high-frequency write bursts; stabilizes latency under load.
- **Input validation**: Hardened input validation across public APIs (SQL injection,
  XSS, path traversal protection extended to graph and MCP entry points).
- **Zero new dependencies**: Built on existing `cryptography` Fernet primitive.

### Previous Release: v0.7.2 (Memify Dynamic Refinement + Native Async I/O)

- **`MemifyEngine`**: Three-phase dynamic memory refinement (zero LLM, pure SQL).
  - `derive_facts()`: Creates derived "relationship" memories from co-occurring entity pairs.
  - `reinforce_edges()`: Reinforces graph edge weights for co-occurring entities (upsert with max_weight cap).
  - `auto_decay()`: Decays stale, low-importance, zero-access memories (three-way gate, idempotent).
- **`consolidate_memories()`**: Unified API running all three Memify phases. Exposed on
  SQLiteAdapter, StorageAdapter base, RecallMixin, and RecallOps Protocol.
- **`AsyncSQLiteAdapter`**: Native async SQLite adapter using aiosqlite. Same SQL as
  SQLiteAdapter but with async I/O. Implements connect/store_entry/recall/forget_memory/count/close
  + async context manager protocol.
- **`[async]` extra**: `pip install carrymem[async]` installs aiosqlite>=0.19.
- **`AsyncCarryMem.native_async` mode**: True async I/O via AsyncSQLiteAdapter when
  `native_async=True`. Adds connect/store_entry/recall_async/count_async methods.
- **Dual-mode coexistence**: Sync SQLiteAdapter (zero-dep) + AsyncSQLiteAdapter ([async] extra).
- **Protocol consistency**: `RecallOps` Protocol updated with `consolidate_memories` signature.
- **58 new tests**: 32 (test_memify.py) + 26 (test_async_sqlite.py). 6 dimensions each,
  no Mock, real SQLite/aiosqlite adapters.

### Previous Release: v0.7.1 (Multi-Mode Retrieval API)

- **`recall_by_time()`**: Time-range retrieval with `[start, end)` semantics, descending
  order. Supports filters and namespace isolation. Performance: 1000 memories <50ms.
- **`recall_semantic()`**: Pure vector similarity search (no FTS, no RRF fusion).
  Capability-gated: returns empty list when vector search is disabled.
- **`recall_hybrid()`**: Explicit hybrid FTS+Vector search with per-call RRF weight
  override (`fts_weight`, `vec_weight`, `rrf_k`).
- **`recall_multi_mode()`**: Unified interface supporting 6 modes (`fts`, `vector`,
  `hybrid`, `graph`, `time`, `entity`) in a single call. Returns structured dict with
  deduplication by `storage_key`.
- **Zero new dependencies**: Built on existing FTS5 + vector search infrastructure.
- **Protocol consistency**: `RecallOps` protocol updated with 4 new method signatures.
- **40 new tests**: Happy Path (8) + Boundary (12) + Error Cases (8) + Performance (2) +
  Configuration (4) + Integration (6). Uses real SQLiteAdapter (no Mock).

### Previous Release: v0.7.0 (Knowledge Graph + Session Dual-Layer Memory)

- **SQLite-native Knowledge Graph**: Two new tables (`memory_entities` + `memory_relations`)
  with 8 indexes for namespace-isolated entity/relation storage. Zero LLM — entity extraction
  reuses `EntityNormalizer`'s pattern-based approach. Multi-hop BFS graph traversal via
  `recall_graph()`. Automatic entity extraction during classification pipeline.
- **Session Dual-Layer Memory**: Per-session LRU cache (`session_max_size=128`) for O(1) recall
  within a conversation session. `set_session()` / `preload_session()` / `end_session()` API.
  `promote_to_permanent()` boosts importance for permanent retention.
- **Bug fixes**: `promote_to_permanent()` rowcount check; FK constraint on
  `memory_entities.memory_key` relaxed to nullable for standalone entities.
- **Protocol consistency**: `RecallOps` protocol updated with 8 new method signatures.

### Previous Release: v0.6.2 (Security Fix + Access Frequency Weighting)

- **recall() signature unified**: `namespaces` parameter promoted to `StorageAdapter` base class.
  Removed 3 `type: ignore[override]` annotations and core-layer `isinstance` check.
- **count() optimized**: Direct `SELECT COUNT(*)` replaces `get_stats()` full aggregation.
  Added namespace/type filter support.
- **Audit access publicized**: `log_audit()`/`query_audit()` public methods on base class replace
  private `_audit` attribute access in core layer.
- **Core layer decoupled**: 12 `isinstance(adapter, SQLiteAdapter)` checks replaced with
  `adapter.capabilities.get()` checks. New capability keys: `versioning`, `backup`, `audit`,
  `namespace_filtering`.
- **search_fulltext fixed**: Base class provides default implementation (delegates to `recall()`).
  Removed duplicate implementations from SQLiteAdapter and JSONAdapter.

### Previous Release: v0.6.0 (Breaking Change — Deprecated API Removal)

- **Deprecated API removed**: All `remember()`/`remember_batch()`/`forget()` methods removed
  from `StorageAdapter`, `SQLiteAdapter`, `JSONAdapter`, `ObsidianAdapter`, and
  `AsyncStorageAdapter` Protocol. Users must migrate to `store_entry()`/`store_batch()`/`delete()`.
- **Core layer API rename**: `CarryMem.remember_batch(messages)` → `CarryMem.store_messages(messages)`
  to disambiguate from adapter-level `store_batch(List[MemoryEntry])`.
- **TestStorageAdapterContract updated**: `test_remember_*` → `test_store_entry_*`,
  `test_forget_*` → `test_delete_*`, `test_remember_batch` removed (covered by `test_store_batch`).
- **50+ test call sites migrated**: All deprecated API calls in tests migrated to new API.
- **Internal cleanup**: `import warnings` removed from 4 source files no longer needing it.

### Previous Release: v0.5.4 (Batch API — Phase 2)

- **store_batch() API**: Atomic batch store method accepting `List[MemoryEntry]` and
  returning `List[StoredMemory]` with full metadata. SQLiteAdapter uses BEGIN/commit/rollback
  for all-or-nothing semantics.
- **delete_batch() API**: Atomic batch delete method accepting `List[str]` storage_keys
  and returning `Dict[str, bool]` per-key results. SQLiteAdapter uses atomic transaction.
- **remember_batch() deprecated**: Emitted DeprecationWarning and delegated to
  `store_batch()`. **Removed in v0.6.0.**
- **AsyncStorageAdapter Protocol**: Updated with store_entry/store/store_batch/delete/
  delete_batch current API signatures.
- **ObsidianAdapter**: Explicit store_batch/delete_batch raising NotImplementedError
  (read-only consistency with store_entry/delete).
- **Core layer migration**: `_memory_crud.py` remember_batch() now calls
  `adapter.store_batch()` instead of deprecated `adapter.remember_batch()`.

### Previous Release: v0.5.3 (store_entry() Core API — Phase 1)

- **store_entry() API**: Domain-level store method that returns complete `StoredMemory`
  with full metadata (importance_score, version, created_at), eliminating the metadata
  loss bug in `store()` (dict→str) path.
- **Core layer migration**: 5 call sites migrated from deprecated `remember()` to
  `store_entry()`, 2 `forget()` call sites migrated to `delete()`.
- **remember_batch() fix**: Default implementation now uses `store_entry()` to preserve
  metadata (was losing importance_score via `StoredMemory.from_memory_entry()`).
- **TestStorageAdapterContract**: New `test_store_entry_returns_full_metadata` contract
  test for all adapter implementations.

- **Summary Layer**: Field-level `summary` cache on memories table (schema migration `_V052`)
- **Progressive Disclosure**: Bucket-based depth mapping
  - `mandatory` → depth 3 (full raw_text)
  - `important` → depth 2 (first sentence)
  - `context` → depth 2 (first sentence)
  - `outdated` → depth 1 (keywords)
- **RuleBasedSummarizer**: Zero-LLM summarizer (level 1=keywords, 2=first sentence, 3=full raw_text)

---

## CI Pipeline Status

### Current State (as of v0.8.0, commits `b55a93a` / `fab1ea4`)

| Job | Status | Duration | Notes |
|-----|--------|----------|-------|
| Syntax Check | ✅ Pass | ~7s | Advisory (continue-on-error) |
| Lint (Quality Gate) | ✅ Pass | ~30s | flake8 + Black + isort + mypy all green |
| Tests (py3.12) | ✅ Pass | ~16m | 4334+ passed, 17 skipped, coverage 80%+ |
| Build & Install Test | ✅ Pass | ~23s | Fresh wheel install verified |
| Docs Check | ✅ Pass | ~4s | Advisory |
| i18n Check | ✅ Pass | ~3s | Advisory |
| Security | ✅ Pass | ~8s | Advisory |

### CI Fix History (v0.5.2 Post-Release)

CI Pipeline was red for 3 consecutive versions (v0.5.0/v0.5.1/v0.5.2) due to
quality gate failures. The `release.yml` workflow (PyPI publishing) was unaffected
and continued to publish successfully. The following commits document the fix
process:

| Commit | Date | Fix | Root Cause |
|--------|------|-----|------------|
| `88fc771` | 2026-07-02 | Black formatting + test_no_write_permission_on_file | 6 files never Black-formatted; SQLite WAL mode bypasses chmod on Ubuntu CI |
| `dd430dc` | 2026-07-02 | isort — remove extra blank line in permissions.py | `from __future__ import annotations` followed by extra blank line (pre-existing, masked by Black failure) |
| `a505ea3` | 2026-07-02 | mypy — add ignore_missing_imports + remove unused type: ignore | mypy.ini lacked `ignore_missing_imports`; 12 `import-not-found` errors for optional deps (openai/textual/pycld2/langdetect) not installed in CI |
| `dc5f861` | 2026-07-03 | P3 tech debt cleanup — actions/checkout@v5 + optional-deps job + consolidate fail_under | Node.js 20 deprecation warnings (forced EOL 2026-06-02); optional-dep import errors undetected by CI; duplicate coverage fail_under config |
| `2fad777` | 2026-07-06 | P2-P4 CarryMem system performance optimizations | classify_and_remember P95/P99 dual threshold; added remember_batch() fast path; encryption overhead threshold adjustment |

### Key Insight: Coverage Gate Was Not the Problem

Initial analysis suspected coverage 34.39% < 75% gate as the CI failure cause.
This was a **misdiagnosis** — the 34.39% figure came from a cancelled CI run
(`28587198361`, interrupted by `cancel-in-progress: true` concurrency policy)
that only executed a subset of tests before being killed.

The complete test run (`b55a93a`, commit `b55a93a`) executed all 4334+ tests and
achieved **80%+ coverage**, passing the 75% gate. The actual CI blocker was
the **mypy** step in the Lint job, not the coverage gate in the Tests job.

---

## Test Summary

### Test Counts (CI run `b55a93a`, commit `b55a93a`; supplemental `fab1ea4`)

- **Total**: 4334+ passed, 17 skipped, 65 deselected
- **Duration**: ~16m
- **Coverage**: 80%+ (gate: 75%)

### Test File Organization

- **102 test files** in `tests/` directory
- **Categories**: unit, integration, e2e, edge cases, CLI, adapters, rules, security
- **Optional-dep tests**: Tests for textual TUI, openai LLM, etc. are conditionally
  skipped when optional dependencies are not installed

### Known Test Behavior

- `test_no_write_permission_on_file`: Skips on systems where SQLite WAL mode
  creates new sidecar files (`-wal`/`-shm`) in writable parent directories,
  bypassing `chmod 0o444` on the `.db` file. This is environment-specific
  behavior, not a source code bug.

---

## Quality Metrics

### Lint Pipeline (ci.yml Lint job)

| Check | Status | Config |
|-------|--------|--------|
| flake8 | ✅ Pass | `--max-line-length=120` |
| Black | ✅ Pass | `--line-length=120`, target py312 |
| isort | ✅ Pass | profile=black, line_length=120 |
| mypy | ✅ Pass (local) | `pyproject.toml [tool.mypy]` with `ignore_missing_imports=True` |

### Coverage

- **Gate**: 75% (`fail_under = 75` in pyproject.toml — single source of truth)
- **Actual**: 80%+ (CI run `b55a93a`)
- **Config**: `source = ["src/carrymem"]`, `branch = true`

### Security

- No hardcoded secrets (CI security scan advisory)
- No bare `except:` clauses
- bandit scan: advisory (non-blocking)

---

## Known Technical Debt

### Resolved in `dc5f861` (2026-07-03) — P3 Tech Debt Cleanup

1. **Node.js 20 deprecation warnings** ✅ RESOLVED (partial): Upgraded
   `actions/checkout@v4` → `@v5` across 4 workflow files (11 sites:
   ci.yml ×7, nightly.yml ×1, benchmark.yml ×2, release.yml ×1).
   Removed `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` env hack from ci.yml and
   benchmark.yml. This eliminates the checkout-related deprecation
   warnings. Node.js 20 reached forced EOL on 2026-06-02.

   **Honest note**: CI run `28639820546` still shows Node.js 20
   deprecation warnings from `actions/setup-python@v5` and
   `actions/upload-artifact@v4`. These actions were NOT upgraded in
   P3 (out of scope). A future cleanup should upgrade these to versions
   supporting Node.js 24 natively (e.g. setup-python@v6+ when available).

2. **Optional dependency test coverage gap** ✅ RESOLVED: Added
   `optional-deps` advisory job to ci.yml. Installs
   `.[dev,tui,encryption,llm,language]` (excludes heavy semantic extras
   like sentence-transformers) and runs tests with `continue-on-error: true`.
   Detects import errors in optional-dependency code paths, preventing
   recurrence of mypy `import-not-found` misdiagnosis.

3. **Duplicate fail_under configuration** ✅ RESOLVED: Removed
   `--cov-fail-under=75` from ci.yml pytest command line.
   `pyproject.toml` `[tool.coverage.report] fail_under = 75` is now the
   single source of truth.

### Current State

No known P3 technical debt remaining. CI pipeline is green with 8 jobs in
CI Pipeline (syntax, test, build, lint, i18n, security, docs, optional-deps)
plus 4 jobs in Performance Benchmarks (benchmark + memory-optimization,
each py3.11 + py3.12).

### P3 Verification Data (CI run `28639820546`, commit `dc5f861`)

**CI Pipeline** (8/8 success):
| Job | Conclusion |
|-----|-----------|
| Syntax Check | ✅ success |
| Tests (py3.12) | ✅ success |
| Build & Install Test | ✅ success |
| Lint (Quality Gate) | ✅ success |
| i18n Check (Advisory) | ✅ success |
| Security (Advisory) | ✅ success |
| Docs Check (Advisory) | ✅ success |
| Optional Deps Test (Advisory) | ✅ success (NEW) |

**Performance Benchmarks** (run `28639820550`, 4/4 success):
| Job | Conclusion |
|-----|-----------|
| Performance Benchmarks (py3.11) | ✅ success |
| Performance Benchmarks (py3.12) | ✅ success |
| Memory Optimization Tests (py3.11) | ✅ success |
| Memory Optimization Tests (py3.12) | ✅ success |

**Remaining advisory warnings** (non-blocking, out of P3 scope):
- Node.js 20 deprecation: `actions/setup-python@v5`, `actions/upload-artifact@v4`
- `git exit code 128` on some jobs (submodule-related, non-fatal)

---

## Version History

| Version | Date | Theme | Status |
|---------|------|-------|--------|
| v0.8.0 | 2026-07-14 | Graphify — MCP Graph Query Tools + Edge Confidence Labels | ✅ Released |
| v0.7.3 | 2026-07-12 | Security Hardening (Fernet-only, WAL throttle, input validation) | ✅ Released |
| v0.7.2 | 2026-07-11 | Memify Dynamic Refinement + Native Async I/O | ✅ Released |
| v0.7.1 | 2026-07-11 | Multi-Mode Retrieval API | ✅ Released |
| v0.7.0 | 2026-07-11 | Knowledge Graph + Session Dual-Layer Memory | ✅ Released |
| v0.6.2 | 2026-07-11 | Security Fix + Access Frequency Weighting | ✅ Released |
| v0.6.1 | 2026-07-10 | Architecture Cleanup — Phase 3.5 refactoring & decoupling | ✅ Released |
| v0.6.0 | 2026-07-09 | Deprecated API Removal (Breaking Change — Phase 3) | ✅ Released |
| v0.5.4 | 2026-07-09 | Batch API (store_batch/delete_batch) — Phase 2 | ✅ Released |
| v0.5.3 | 2026-07-08 | store_entry() Core API — Phase 1 | ✅ Released |
| v0.5.2 | 2026-07-02 | Summary Layer + Progressive Disclosure | ✅ Released |
| v0.5.1 | 2026-07-02 | Entity Normalization (Ontology-lite) | ✅ Released |
| v0.5.0 | 2026-07-01 | Rules Engine + Maturity Fixes | ✅ Released |

---

## Next Milestone

**v0.10.0** (next MINOR — TBD based on user feedback and architecture evolution plan)

Note: v0.9.0 ~ v0.9.7 series completed (2026-07-20 ~ 2026-07-26). The original "v0.9.0 next milestone" plan items below have been addressed or superseded:

Potential areas for v0.10.0+ (per CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md):
- Vector search enhancements (HNSW indexing, approximate nearest neighbor)
- Cross-namespace knowledge transfer
- LLM-assisted entity extraction (optional, capability-gated)
- Memory compaction and summarization strategies

### v0.8.0 Completed (2026-07-14)

- 3 MCP graph query tools: query_graph / shortest_path / get_memory_impact ✅
- Edge confidence labels: EXTRACTED / INFERRED / AMBIGUOUS ✅
- MCP registration alongside existing recall/forget tools ✅
- Reuse of SQLite-native KnowledgeGraph engine (no schema migration) ✅
- Backward-compatible: existing recall_graph/recall_by_entity/recall_by_relation unchanged ✅
- CI green: 4334+ passed, 17 skipped, coverage 80%+ (commits b55a93a / fab1ea4) ✅

### v0.7.3 Completed (2026-07-12)

- Security Hardening: Fernet-only encryption (legacy AES-128 paths removed) ✅
- WAL checkpoint throttle for write-burst latency stabilization ✅
- Input validation hardened across graph + MCP entry points ✅
- Zero new dependencies (reuses cryptography Fernet primitive) ✅

### v0.7.2 Completed (2026-07-11)

- MemifyEngine: derive_facts (co-occurring entity pairs → derived relationship memories) ✅
- MemifyEngine: reinforce_edges (co_occurs relation upsert with max_weight cap) ✅
- MemifyEngine: auto_decay (three-way gate: stale + low importance + zero access) ✅
- consolidate_memories() unified API on SQLiteAdapter + base + RecallMixin + Protocol ✅
- AsyncSQLiteAdapter: native async I/O via aiosqlite ([async] extra) ✅
- AsyncCarryMem: native_async=True mode with connect/store_entry/recall_async/count_async ✅
- [async] extra in setup.py + added to [full] extra ✅
- 58 new tests (32 test_memify.py + 26 test_async_sqlite.py) — 6 dimensions, no Mock ✅

### v0.7.1 Completed (2026-07-11)

- `recall_by_time()`: time-range retrieval with [start, end) semantics ✅
- `recall_semantic()`: pure vector similarity search (capability-gated) ✅
- `recall_hybrid()`: hybrid FTS+Vector with per-call RRF weight override ✅
- `recall_multi_mode()`: unified 6-mode interface with deduplication ✅
- RecallEngine extensions: vector_search_only + hybrid_search + search_by_time ✅
- StorageAdapter base defaults for backward compatibility ✅
- RecallOps Protocol updated with 4 new method signatures ✅
- 40 new tests (test_multi_mode_retrieval.py) — 6 dimensions, no Mock ✅

### v0.7.0 Completed (2026-07-11)

- SQLite-native Knowledge Graph (memory_entities + memory_relations tables) ✅
- KnowledgeGraph layer with BFS multi-hop traversal ✅
- SQLiteAdapter graph API (8 methods, capability-gated) ✅
- Automatic entity extraction in classification pipeline ✅
- Session Dual-Layer Memory (per-session LRU cache, O(1) recall) ✅
- CarryMem session API (set_session/preload_session/end_session/promote_to_permanent) ✅
- Bug fix: promote_to_permanent() rowcount check ✅
- Bug fix: FK constraint on memory_entities.memory_key relaxed to nullable ✅
- Protocol consistency: RecallOps updated with 8 new method signatures ✅
- 74 new tests (test_knowledge_graph.py + test_session_memory.py) ✅

### Completed Milestones

Phase 1 (store_entry core API) complete (commit `6aaa477`, 2026-07-09).
Phase 2 (batch API + adapter migration) complete (2026-07-09).
Phase 3 (deprecated API removal) complete (2026-07-09).
Phase 3.5 (architecture cleanup) complete (commit `f4580dd`, 2026-07-10):
- recall() signature normalization (namespaces parameter) ✅
- Core layer hard-coupling decoupling (capabilities vs isinstance) ✅
- count() performance optimization (direct SELECT COUNT(*)) ✅
- Audit access publicization (log_audit/query_audit methods) ✅
- search_fulltext semantic correction (base class default impl) ✅

### Remaining Tech Debt

- `_maintenance.py:105`: 1 isinstance check retained (list_expired uses
  SQLite-specific `_get_connection()`; requires list_expired() in adapter
  interface to fully decouple)
- Pre-existing macOS flaky test: `test_e2e_edge_cases.py::TestE2EPermissionScenarios::test_no_write_permission_on_file`
  (disk I/O error vs readonly matching, not a regression)
- CI Actions: `actions/setup-python@v5`, `actions/upload-artifact@v4`
  still trigger Node.js 20 deprecation warnings (upgrade to v6+ when available)
- VSCode Extension Tier 2 E2E tests require `@vscode/test-electron` (downloads ~150MB VSCode);
  currently run locally/nightly, not in PR-level CI
- Performance smoke tests use loose thresholds (10x CI_FACTOR); full benchmark suite
  (18 tests, marked slow) runs nightly/locally only

### Long-term Direction

See [ROADMAP.md](ROADMAP.md) for product roadmap and
[COMPETITIVE_ANALYSIS_MEMORY_GRAPH.md](COMPETITIVE_ANALYSIS_MEMORY_GRAPH.md)
for competitive analysis-driven architecture evolution plan.
