# CI regression investigation

- session: ci-regressions
- project_root: `/Users/lin/trae_projects/carrymem`
- source: GitHub Actions run `38059226751`
- pre-fix evidence:
  - Ubuntu: 5088 passed, 22 failed, 11 skipped, 77 deselected.
  - macOS: 5088 passed, 22 failed, 11 skipped, 77 deselected.
  - Dependabot open alerts: 0.

## Hypotheses

| ID | Hypothesis | Observation required | Status |
|---|---|---|---|
| H1 | KnowledgeGraph production code now requires `ConnectionManager.file_lock`, but `FakeConnMgr` test doubles do not implement the contract. | Reproduce the failing graph tests and inspect the fake manager shape. | CONFIRMED — added `file_lock` to `tests/test_v080_graph_tools.py`; graph tests pass. |
| H2 | `DevSquadAdapter.is_available()` checks only object construction or path presence, not whether the configured database is usable. | Reproduce bad-db tests and trace the availability predicate. | CONFIRMED — `RuleStorage` creates missing parents; adapter now rejects a missing parent directory. |
| H3 | The read-only-parent E2E assumes ordinary-user permission semantics, but GitHub runners can bypass mode-bit denial. | Reproduce the test and inspect its permission setup and production boundary. | CONFIRMED — public API maps the permission failure to `CarryMemError`; E2E now accepts that contract. |
| H4 | The three failure groups are caused by the dependency migration. | Run targeted tests without the Z.AI client path and compare failures. | REJECTED — failures were independent test and API-contract regressions. |

## Evidence

- 2026-10-10 CI logs show the same 22 failures on Ubuntu and macOS.
- 16 failures report `FakeConnMgr` without `file_lock`.
- 5 failures report `DevSquadAdapter` unavailable-state assertions returning available.
- 1 failure reports `CM-106` from the read-only-parent E2E.

## Post-fix verification

- `tests/test_v080_graph_tools.py`: 33 passed.
- `tests/test_devsquad_adapter.py`: 55 passed.
- `tests/e2e/test_e2e_edge_cases.py::TestE2EPermissionScenarios`: 3 passed.
- Combined regression subset: 117 passed in 18.60s.
- Black check: passed for all changed Python files.
- Diagnostics: no issues in `src/carrymem/integration/devsquad/adapter.py`.

## Progress

- progress_status: fixed_locally_pending_push
- next: commit the repair, push to `origin/new-main`, and inspect the complete CI workflow.
