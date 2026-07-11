# CarryMem — Project Status

**Version**: v0.6.2
**Last Updated**: 2026-07-11
**Maintainer**: CarryMem Team

---

## Current Release: v0.6.2

**Theme**: Security Fix + Access Frequency Weighting (PATCH release)

**Release Date**: 2026-07-11
**PyPI**: `carrymem==0.6.2` ([PyPI](https://pypi.org/project/carrymem/))
**Git Tag**: [v0.6.2](https://github.com/lulin70/carrymem/releases/tag/v0.6.2)

### Core Features (v0.6.2)

- **cryptography CVE-2026-34073 fixed**: Version constraint upgraded from `>=42.0` to
  `>=46.0.6` in setup.py (encryption + full extras). Fixes X.509 certificate validation
  bypass vulnerability (CVSS 7.8).
- **PyYAML usage audited**: Verified all `yaml.load()` calls use `safe_load()`. No RCE risk.
- **Access frequency weighting with recency decay**: `selection.py` now applies time-based
  decay to access_count boost via `2^(-0.1 * days_since_last_access)`. Memories without
  `last_accessed_at` are unaffected (backward-compatible).

### Previous Release: v0.6.1 (Architecture Cleanup — Phase 3.5)

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

### Current State (as of commit `a505ea3`)

| Job | Status | Duration | Notes |
|-----|--------|----------|-------|
| Syntax Check | ✅ Pass | ~7s | Advisory (continue-on-error) |
| Lint (Quality Gate) | 🔄 Pending CI | ~30s | mypy fix pushed, awaiting verification |
| Tests (py3.12) | ✅ Pass | ~16m | 4076 passed, 18 skipped, coverage 80.85% |
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

The complete test run (`dd430dc`, commit `dd430dc`) executed all 4076 tests and
achieved **80.85% coverage**, passing the 75% gate. The actual CI blocker was
the **mypy** step in the Lint job, not the coverage gate in the Tests job.

---

## Test Summary

### Test Counts (CI run `dd430dc`, commit `dd430dc`)

- **Total**: 4076 passed, 18 skipped, 65 deselected
- **Duration**: 939.25s (~15m39s)
- **Coverage**: 80.85% (gate: 75%)

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
| mypy | ✅ Pass (local) | `mypy.ini` with `ignore_missing_imports=True` |

### Coverage

- **Gate**: 75% (`fail_under = 75` in pyproject.toml — single source of truth)
- **Actual**: 80.85% (CI run `dd430dc`)
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

**v0.6.2** (next patch — security fix + access frequency weighting)

Security:
- cryptography CVE-2026-34073 fix (>=42.0 → >=46.0.6 in setup.py)

Optimization:
- Access frequency weighting: introduce recency decay factor into selection.py
  boost logic (currently linear access_count boost without time decay)

Documentation:
- PROJECT_STATUS version history sync (v0.5.4/v0.6.0/v0.6.1 added)
- DEPENDENCY_AUDIT.md cryptography CVE marked as resolved

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

### Long-term Direction

See [ROADMAP.md](ROADMAP.md) for product roadmap and
[COMPETITIVE_ANALYSIS_MEMORY_GRAPH.md](COMPETITIVE_ANALYSIS_MEMORY_GRAPH.md)
for competitive analysis-driven architecture evolution plan.
