# CarryMem — Project Status

**Version**: v0.5.2
**Last Updated**: 2026-07-02
**Maintainer**: CarryMem Team

---

## Current Release: v0.5.2

**Theme**: Summary Layer + Progressive Disclosure — token-efficient prompt injection

**Release Date**: 2026-07-02
**PyPI**: `carrymem==0.5.2` ([PyPI](https://pypi.org/project/carrymem/))
**Git Tag**: [v0.5.2](https://github.com/lulin70/carrymem/releases/tag/v0.5.2)

### Core Features (v0.5.2)

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

- **Gate**: 75% (`--cov-fail-under=75` in ci.yml + `fail_under=75` in pyproject.toml)
- **Actual**: 80.85% (CI run `dd430dc`)
- **Config**: `source = ["src/carrymem"]`, `branch = true`

### Security

- No hardcoded secrets (CI security scan advisory)
- No bare `except:` clauses
- bandit scan: advisory (non-blocking)

---

## Known Technical Debt

### P3 — Low Priority

1. **Node.js 20 deprecation warnings**: GitHub Actions `actions/checkout@v4`
   and `actions/setup-python@v5` target Node.js 20, forced to Node.js 24 via
   `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`. Should upgrade actions versions
   when newer releases are available.

2. **Optional dependency test coverage gap**: CI installs `.[dev]` which
   excludes optional deps (textual, openai, zhipuai, pysqlite3, sqlite-vec,
   sentence-transformers). Tests for these modules are conditionally skipped,
   reducing effective coverage. Future CI improvement could add a job that
   installs `.[full]` and runs the optional-dep tests.

3. **Duplicate fail_under configuration**: Coverage gate is configured in both
   `pyproject.toml` (`[tool.coverage.report] fail_under = 75`) and `ci.yml`
   (`--cov-fail-under=75`). Should consolidate to single source of truth.

---

## Version History

| Version | Date | Theme | Status |
|---------|------|-------|--------|
| v0.5.2 | 2026-07-02 | Summary Layer + Progressive Disclosure | ✅ Released |
| v0.5.1 | 2026-07-02 | Entity Normalization (Ontology-lite) | ✅ Released |
| v0.5.0 | 2026-07-01 | Rules Engine + Maturity Fixes | ✅ Released |

---

## Next Milestone

**v0.5.3** (next patch — planning TBD)

Potential candidates (not yet committed):
- Coverage improvement for optional-dep modules
- CI optional-deps test job
- Node.js 20 deprecation cleanup
- Consolidate fail_under configuration

See [ROADMAP.md](ROADMAP.md) for long-term planning.
