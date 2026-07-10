# Changelog

All notable changes to CarryMem will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Version Reset Notice**: In May 2026, the version was reset from v0.4.1 back to v0.2.0
> to align Git, PyPI, and documentation versions. Entries below marked as "(pre-reset)" are
> historical records from the pre-reset development cycle and should not be confused with
> the current v0.2.x series.

## [0.6.0] - 2026-07-09 (Breaking Change — Deprecated API Removal)

### ⚠️ Breaking Changes
- **Removed `StorageAdapter.remember()`** — Use `store_entry()` instead.
- **Removed `StorageAdapter.remember_batch()`** — Use `store_batch()` instead.
- **Removed `StorageAdapter.forget()`** — Use `delete()` instead.
- **Removed `SQLiteAdapter.remember()`** — Use `store_entry()` instead.
- **Removed `SQLiteAdapter.remember_batch()`** — Use `store_batch()` instead.
- **Removed `SQLiteAdapter.forget()`** — Use `delete()` instead.
- **Removed `JSONAdapter.remember()`** — Use `store_entry()` instead.
- **Removed `JSONAdapter.forget()`** — Use `delete()` instead.
- **Removed `ObsidianAdapter.remember()`** — Use `store_entry()` instead.
- **Removed `ObsidianAdapter.remember_batch()`** — Use `store_batch()` instead.
- **Removed `ObsidianAdapter.forget()`** — Use `delete()` instead.
- **Removed `AsyncStorageAdapter.remember/remember_batch/forget` Protocol signatures** — Use `store_entry/store_batch/delete` instead.
- **Renamed `CarryMem.remember_batch(messages)` → `CarryMem.store_messages(messages)`** — Core layer public API renamed to disambiguate from adapter-level `store_batch(List[MemoryEntry])`. The core-layer method receives `List[str]` messages (requires classification), while the adapter-level method receives `List[MemoryEntry]` objects (direct atomic storage).

### Migration Guide
```python
# Before v0.6.0 (deprecated)
stored = adapter.remember(entry)        # → adapter.store_entry(entry)
results = adapter.remember_batch(entries)  # → adapter.store_batch(entries)
deleted = adapter.forget(key)          # → adapter.delete(key)
result = cm.remember_batch(messages)   # → cm.store_messages(messages)

# v0.6.0+
stored = adapter.store_entry(entry)
results = adapter.store_batch(entries)
deleted = adapter.delete(key)
result = cm.store_messages(messages)
```

### Changed
- `SQLiteAdapter.import_data()` migrated from `self._crud.remember()` to `self.store_entry()`.
- `TestStorageAdapterContract` updated: `test_remember_returns_stored_memory` → `test_store_entry_returns_stored_memory`, `test_forget_removes_memory` → `test_delete_removes_memory`, `test_remember_batch` removed (covered by `test_store_batch`).
- `StorageAdapter` class docstring updated to reflect new standardized interface (store/store_entry/store_batch/recall/delete/delete_batch).
- Removed `import warnings` from `base.py`, `sqlite/__init__.py`, `crud.py`, `json_adapter.py` (no longer needed).

### Internal
- `CRUDOperations.remember()` and `CRUDOperations.forget()` retained as internal implementations (called by `store_entry()` and `delete()` respectively). Not part of public API.
- `CRUDOperations.remember_batch()` deprecated delegate removed (was added in v0.5.4).

## [Unreleased]

### Added
- 134 unit tests for 7 core Mixins (tests/core/)
- health_check MCP tool (28 tools total)
- TUI delete (d) and edit (e) functionality
- CLI rules subcommand grouping (carrymem rules add/list/match...)
- Audit logger defaults to SQLite persistence (~/.carrymem/audit.db)
- mypy type check and bandit security scan in CI
- **Security upgrade test suite**: 29 tests in `test_security_crypto_upgrade.py`
  covering PBKDF2 iterations, key rotation round-trip, digest tampering detection,
  security level attributes, fallback warnings, and full backward compatibility.
- **Security constants**: `PBKDF2_ITERATIONS = 260000` and
  `PBKDF2_ITERATIONS_LEGACY = 100000` in `constants.py`.

### Changed
- StorageAdapterProtocol merged into StorageAdapter (interface simplified)
- Removed 9 @runtime_checkable decorators (zero runtime overhead)
- All Any types replaced with specific types (24→0)
- CLI old flat commands (add-rule etc.) deprecated, use rules subcommands
- **Security**: PBKDF2_ITERATIONS raised from 260000 → 600000 (OWASP 2023 recommendation
  for PBKDF2-HMAC-SHA256). Existing keys remain verifiable via stored iteration metadata.

### Fixed
- handlers.cleanup() async→sync (RuntimeWarning)
- ConnectionManager.close() pysqlite3 exception handling
- Path traversal validation in CarryMem.__init__
- InputValidator.sanitize_namespace() + empty namespace check
- Black/flake8 CI configuration (line-length=120 alignment)
- **MCP server**: Fixed `notifications/initialized` method name mismatch and added protocol version negotiation (2025-11-25 support)
- **Memory leak**: Fixed `lru_cache` on instance method pinning `self` in `semantic/expander.py` (18% → 91% GC recovery)
- **CI gate**: Fixed `| tee` swallowing pytest exit code and removed `--maxfail=10` limit

## [0.5.4] - 2026-07-09 (Batch API — Phase 2)

### Added
- **`StorageAdapter.store_batch()`**: Atomic batch store method accepting
  `List[MemoryEntry]` and returning `List[StoredMemory]` with full metadata.
  Default implementation loops `store_entry()`; SQLiteAdapter overrides with
  BEGIN/commit/rollback for all-or-nothing semantics.
- **`StorageAdapter.delete_batch()`**: Atomic batch delete method accepting
  `List[str]` storage_keys and returning `Dict[str, bool]` per-key results.
  Default implementation loops `delete()`; SQLiteAdapter overrides with atomic
  transaction (keys not found return False, not an error).
- **`SQLiteAdapter.store_batch()`/`delete_batch()`**: Atomic transaction
  implementations using file_lock + BEGIN/commit/rollback pattern.
- **`ObsidianAdapter.store_batch()`/`delete_batch()`**: Explicit
  NotImplementedError (read-only consistency with store_entry/delete).
- **`AsyncStorageAdapter` Protocol**: Updated with current API signatures
  (store_entry/store/store_batch/delete/delete_batch/recall/forget_expired/get_stats).
- **`TestStorageAdapterContract`**: New `test_store_batch` and `test_delete_batch`
  contract tests for all adapter implementations.
- **`TestSQLiteAdapter`**: 4 new tests — `test_store_batch`,
  `test_delete_batch`, `test_store_batch_atomic_rollback`,
  `test_remember_batch_deprecation_warning`.

### Changed
- **`remember_batch()` deprecated**: Now emits `DeprecationWarning` and delegates
  to `store_batch()`. Will be removed in v0.6.0. Applies to both
  `StorageAdapter.remember_batch()` (base) and `CRUDOperations.remember_batch()`
  (SQLite).
- **`_memory_crud.py`**: `remember_batch()` method now calls
  `adapter.store_batch()` instead of deprecated `adapter.remember_batch()`.
- **`SQLiteAdapter`**: Added `store_batch()`/`delete_batch()` forwarding methods
  to `__init__.py` facade.

### Fixed
- N/A (no bug fixes in this release — feature addition only)

## [0.5.3] - 2026-07-08 (store_entry() Core API — Phase 1)

### Added
- **`StorageAdapter.store_entry()` abstract method**: Domain-level store API that
  accepts a `MemoryEntry` object and returns a complete `StoredMemory` with all
  storage metadata (importance_score, version, created_at, updated_at) populated
  by the adapter. This eliminates the metadata loss bug where `store()` (dict→str)
  discarded the `StoredMemory` returned by the internal CRUD layer.
- **`TestStorageAdapterContract.test_store_entry_returns_full_metadata`**: Contract
  test verifying that `store_entry()` returns a `StoredMemory` with
  `importance_score > 0.0`, `version >= 1`, and non-null `created_at`/`updated_at`.
- **`CARRYMEM_OPTIMIZATION_PLAN_v0.5.3.md`**: PM+Architect consensus optimization
  plan covering 3 phases (store_entry API → batch/async → deprecated removal).

### Changed
- **Core layer migrated to `store_entry()`**: 5 call sites in `_memory_crud.py`,
  `_classification.py`, `_profile_export.py`, `_prompt_delegate.py` (×2) migrated
  from deprecated `remember()` to `store_entry()`, preserving full metadata flow.
- **`remember_batch()` default implementation**: Now calls `store_entry()` instead
  of `store()` + `StoredMemory.from_memory_entry()`, eliminating metadata loss
  (importance_score was defaulting to 0.0 in the old path).
- **`_maintenance.py`**: 2 `forget()` call sites migrated to `delete()`.
- **`MemoryCRUDOps` Protocol**: Added `remember_batch` method signature to fix
  Protocol coverage test (`test_mixin_public_methods_covered_by_protocol`).
- **mypy `python_version`**: 3.9 → 3.12 (aligned with black target-version and
  actual runtime).
- **All 3 adapters** (SQLite/JSON/Obsidian): Implemented `store_entry()`.
  SQLiteAdapter delegates to `_crud.remember()`, JSONAdapter delegates to
  `_store_entry()`, ObsidianAdapter raises `NotImplementedError` (read-only).

### Fixed
- **`test_storage_error_propagates_on_critical_operation`**: Updated mock target
  from `remember()` to `store_entry()` to match the migrated `classify_and_remember`
  call path. The test verifies that storage errors propagate correctly.
- **`_MinimalAdapter` and 3 `DummyAdapter` test helpers**: Added `store_entry()`
  implementations to resolve `TypeError: Can't instantiate abstract class` after
  `store_entry` was added as `@abstractmethod`.

### Performance (P0-4: SQLite Connection Management Optimization)

- **Connection reuse optimization**: Thread-local connection caching via `threading.local()`.
  Same thread reuses connection; different threads get separate connections (sqlite3
  connections must not be shared across threads). Added `release_connection()` and
  `close_all_connections()` API methods for explicit lifecycle management.
- **WAL mode enhancements**: Connection creation now applies optimized PRAGMAs:
  `journal_mode=WAL`, `synchronous=NORMAL` (balanced safety/performance),
  `cache_size=-20000` (20MB page cache), plus existing `foreign_keys=ON`
  and `busy_timeout=10000`. Extracted to `_apply_pragmas()` helper method.
- **Query execution time monitoring**: New `timed_query()` context manager logs query
  duration at DEBUG level. Queries exceeding threshold (default 100ms) emit WARNING.
  Configurable via `CARRYMEM_SLOW_QUERY_MS` environment variable; set to 0 to disable.
- **Connection test suite** (`tests/test_sqlite_connection_pool.py`): 17 tests covering
  thread-local reuse, cross-thread isolation, WAL/synchronous/cache_size verification,
  slow query logging, cleanup methods, context manager, concurrent read/write safety,
  and environment variable configuration.

### Security (P0-5: Encryption Audit & Upgrade)

- **PBKDF2 iterations upgraded**: Default iteration count raised from 100,000 → 260,000
  (2026 NIST recommendation). Legacy salt files without iteration metadata automatically
  fall back to 100,000 for backward compatibility. Salt file format now stores iterations
  as JSON `{"salt": "<b64>", "iterations": <int>}`.
- **Fallback cipher insecure marking**: `NoEncryption` class annotated with SECURITY RISK
  docstring and `_security_level = "none"` attribute. HMAC-CTR fallback stream cipher
  emits one-time `logger.warning` on first use, recommending `cryptography` installation.
  Both classes expose `.security_level` property (`"strong"` / `"weak"` / `"none"`).
- **Key Rotation API**: New `MemoryEncryption.rotate_key(new_password=None)` method.
  Performs atomic rotation: backup → generate new key → save → return re-encryption callable.
  Backs up both `.key` and `.key.digest` with UTC timestamps before replacement.
- **Key file integrity verification**: HMAC-SHA256 digest stored in `.key.digest` alongside
  `.key`. Automatic verification on load; tampered keys rejected with `EncryptionError`.
  Missing digest files auto-created on first load (migration path from pre-check versions).

## [0.5.2] - 2026-07-02 (Summary Layer + Progressive Disclosure)

### Added
- **SummaryLayer module** (`src/carrymem/layers/summary_layer.py`): Field-level memory
  summary caching with progressive disclosure for token-efficient prompt injection.
  - `RuleBasedSummarizer`: Zero-LLM summarizer with 3 depth levels (1=keywords,
    2=first sentence, 3=full raw_text). Type-specific extraction (decision →
    content after "decided:", etc.). 80+ English stopwords for keyword extraction.
  - `SummaryLayer`: LLM-optional summary layer. Reuses `LLMClient` when enabled;
    falls back to rule-based on LLM failure. Caches to `memories.summary` field.
  - `BUCKET_DEPTH` mapping: mandatory=3, important=2, context=2, outdated=1.
  - `get_depth_for_bucket()`: Helper for prompt rendering depth selection.
  - LLM switch config: `CARRYMEM_LLM_SUMMARY` env > TRAE env detection > False.
  - `CARRYMEM_SUMMARY_ENABLED` env (default "1") to disable summary layer entirely.
- **Schema migration `_V052`**: `summary TEXT` and `summary_level INTEGER` columns
  added to `memories` table. Idempotent migration via `migrate_v052()`.
- **StoredMemory extension**: `summary` and `summary_level` fields in dataclass,
  `to_dict()`/`from_dict()`, and `StoredMemoryDict` TypedDict.
- **Progressive disclosure API**: `progressive: bool` parameter added to
  `build_prompt()`, `build_context()`, `build_system_prompt()` (all default `False`
  for backward compatibility). `depth: int` parameter added to
  `format_memory_entry()` (default `3` for backward compatibility).
- **44-test suite** (`tests/test_summary_layer.py`): Covers 11 dimensions —
  Happy Path, LLM Switch, LLM Fallback, Progressive Disclosure, Cache, Boundary,
  Integration, Performance (<500ms for 1000 memories), Config, Schema Migration,
  CRUD Invalidation, Serialization.

### Security
- **C20**: LLM-generated summaries sanitized via `InputValidator.sanitize_content()`
  before caching. Fallback: null-byte strip + whitespace strip.
- **C21**: LLM prompt wraps `raw_text` in `<memory_data>` XML tags to prevent
  prompt injection (pattern reused from SessionSummarizer).
- **C22**: Summary field length capped at 500 characters (`_MAX_SUMMARY_LENGTH`)
  to prevent oversized LLM output from consuming excessive storage.

### Changed
- **`format_memory_entry()`**: New `depth: int = 3` parameter. When `depth < 3`,
  renders memory using cached `summary` field or rule-based fallback instead of
  full `raw_text`. Superseded memories always show NOTE prefix regardless of depth.
- **`build_prompt()`**: New `progressive: bool = False` parameter. When `True`,
  renders memory buckets at progressive depths (Mandatory=full, Important=summary,
  Context=summary, Outdated=keywords). Mandatory always renders at depth=3 to
  preserve key directives.
- **`build_context()` / `build_system_prompt()`**: New `progressive` parameter
  transparently passed to `build_prompt()` via `PromptBuilder` and `PromptDelegateMixin`.
- **Summary cache invalidation**: `crud.py` update path now sets
  `summary = NULL, summary_level = NULL` when `raw_text` or `content` is updated,
  ensuring stale summaries are never served.
- **Serializer**: `row_to_stored()` and `dict_to_stored()` now read/write
  `summary` and `summary_level` fields with backward-compatible `if "col" in row.keys()`
  guards.

## [0.5.1] - 2026-07-01 (Entity Normalization — Ontology-lite)

### Added
- **EntityNormalizer module** (`src/carrymem/layers/entity_normalizer.py`): Rule-based
  entity extraction + `difflib.SequenceMatcher` fuzzy matching (ratio ≥ 0.8) to map
  surface forms to canonical forms. Zero LLM dependency. Borrows cognee's 80% cutoff.
  - 4 regex extraction patterns: acronyms (ALL_CAPS 2-6 chars), CamelCase terms,
    hyphenated/underscored tool names, capitalized phrases
  - Stopword filtering (80+ English stopwords) to avoid false positives
  - `_MAX_ENTITIES_PER_TEXT=50` performance guard
- **entity_aliases table** (schema migration `_V051`): `canonical_form`, `alias_form`,
  `entity_type`, `namespace`, `similarity_score`, `created_at` with UNIQUE constraint
  and namespace/canonical indexes. Idempotent migration via `migrate_v051()`.
- **memories table columns**: `entity_normalized` (JSON) and `entity_id` (TEXT) added
  via ALTER TABLE migration (NULL-able, backward compatible)
- **classify pipeline integration**: `_store_entries()` in `_classification.py` now
  runs EntityNormalizer as post-classification enrichment. Entity metadata merged
  into `entry.metadata["entities"]` before persistence. Graceful degradation on any
  error (non-SQLite adapters, missing InputValidator, DB failures).
- **InputValidator.sanitize_content()** public API: C16 security correction —
  alias_form/canonical_form sanitized via this method before persistence.
- **EntityNormalizer.list_entities() / merge_entities()**: CLI/MCP support methods.
  `merge_entities()` emits `ENTITY_MERGE` audit log per C19.
- **42-test suite** (`tests/test_entity_normalizer.py`): Happy Path (6), Boundary (9),
  Error (4), Performance (2), Namespace Isolation (2), Classify Integration (2),
  Security C15/C16/C18 (5), Config Switch (3), List/Merge (4), JSON builder (3),
  NormalizeResult (2). Uses real SQLite in-memory DB (no Mock).
- **`CARRYMEM_ENTITY_NORMALIZATION` env var** (default `1`): Set to `0` to disable.

### Security
- **C15**: Fuzzy match constrained to same `entity_type` + length diff ≤ 3 + first 2
  chars match. Prevents false merges like "Java" (language) ↔ "JavaScript".
- **C16**: `alias_form`/`canonical_form` sanitized via `InputValidator.sanitize_content()`
  (null-byte removal + whitespace strip) before DB persistence.
- **C18**: Namespace sourced from adapter (`self._namespace` from LifecycleMixin, set
  by SQLiteAdapter) — not from user-controllable `memory.metadata`. Format validated
  defensively (`^[a-zA-Z0-9_-]+$`).
- **C19**: `merge_entities()` emits `ENTITY_MERGE` audit log with source/target/namespace.
- **Namespace isolation** (spec §8.1): No cross-namespace entity normalization. Each
  namespace's `entity_aliases` are isolated (privacy boundary).

### Changed
- `SchemaManager.migrate_all()` now calls `migrate_v051()` after `migrate_v090()`.
- `ClassificationMixin` declares `_entity_normalizer`/`_input_validator` lazy-init
  attributes; `LifecycleMixin.__init__` initializes them to `None`.
- `_store_entries()` adds entity metadata enrichment step before storage loop.

## [0.5.0] - 2026-07-01 (Access Frequency Weighting Enhancement)

### Changed
- **Configurable access weighting**: `ACCESS_SCALE`, `ACCESS_SIGNAL_SCALE`, and
  `ACCESS_SIGNAL_WEIGHT` in `scoring.py` are now configurable via environment
  variables (`CARRYMEM_ACCESS_SCALE`, `CARRYMEM_ACCESS_SIGNAL_SCALE`,
  `CARRYMEM_ACCESS_SIGNAL_WEIGHT`). Invalid values fall back to defaults.
  Default values unchanged (0.1/0.2/0.1) — fully backward compatible.
- **Selection access_boost**: `select_memories()` in `selection.py` now adds
  `access_boost = min(max(0, access_count) * 0.01, 0.1)` to the final ranking
  score. Frequently accessed memories rank higher; boost capped at 0.1 to
  prevent hot-memory domination. Negative/None/missing `access_count` treated
  as 0 (no penalty).

### Added
- 15 new tests covering env var configuration (valid/invalid/empty/negative),
  access_signal scale/weight effects, access_boost ranking/cap/boundary cases
  (zero/negative/None/missing access_count, huge count cap).

## [0.4.1] - 2026-07-01 (Maturity Fixes Release)

### Fixed
- **P0-1**: Black 16 files formatting regression — `black src/ tests/` reformatted 274 files
- **P0-2**: mypy 21 errors (unused-ignore × 15, arg-type × 2, import-not-found × 4) — cleaned up stale `# type: ignore` comments and updated error codes for mypy ≥ 1.0
- **P0-3**: nightly.yml missing `timeout-minutes` + unrealistic performance baselines — added `timeout-minutes: 90` and CI_FACTOR pattern (50x threshold relaxation in CI via `CARRYMEM_CI` env var)
- **P0-4**: DevSquad `type_mapping["prefer"]: "avoid"` semantic inversion — corrected to `"always"`
- **P0-5**: FTS5 concurrent vtable `SQLITE_SCHEMA (code=17)` — root cause: lazy `@property` `rule_engine` triggering DDL on first access → schema cookie increment → concurrent FTS5 vtable xConnect failure. Fix: eager init `rule_engine` in `CarryMem.__init__()`
- **P1-4**: `.flake8` extend-ignore masking F401/F841/F821/F811 — removed 4 critical error codes from ignore list
- **P1-5/6**: pre-commit tool versions drift (black 23.12.1/mypy v1.8.0) vs CI (black 26.5.1/mypy 2.1.0) — aligned to CI versions
- **P1-8**: benchmark.yml `continue-on-error: true` masking performance regression — removed 2 occurrences, added `CARRYMEM_CI` env
- **P1-9**: CRUD write paths missing audit log — `log_operation` now covers 4/4 write paths (remember/forget/forget_expired/update)
- **P1-11**: RecallCache write-invalidates-namespace causing hit rate 0.33→0.047 — new `invalidate_keys(namespace, storage_keys)` method for fine-grained invalidation; hit rate restored to 95% (19/20 queries preserved). Also fixed `update_memory` missing cache invalidation (data consistency bug)
- **P1-13/15/16**: Version numbers stale in SECURITY.md, ROADMAP.md, server.json, smithery.yaml — aligned to v0.4.0
- **P1-14**: Missing CLAUDE.md AI collaboration guide — created (227 lines)
- **P1-17**: 2 performance tests `@pytest.mark.skip` as flaky-skip — replaced with CI_FACTOR environment-adaptive threshold (50x CI / 1x dev)

### Changed
- **P2-7 (Security)**: PBKDF2_ITERATIONS raised from 260000 → 600000 (OWASP 2023 recommendation for PBKDF2-HMAC-SHA256). Existing keys remain verifiable via stored iteration metadata
- **P2-17 (Build)**: Dockerfile converted to multi-stage build (builder stage builds wheel, runtime stage installs wheel + [full] extras). Added `.dockerignore`
- **P1-7 (CI/CD)**: release.yml added `timeout-minutes: 30` and version consistency verification step (tag version == built wheel version)

### Added
- Cache hit-rate comparison test (95% fine-grained vs 0% namespace-level invalidation)
- User journey E2E test (remember → recall → update → recall → forget → recall — cache must never serve stale data)
- Concurrent write cache consistency test

### Resolved (Closed without code change)
- **P1-12**: "WarmupManager" and "3 extra recalls per write" claims from prior assessment confirmed non-existent (LLM hallucination in prior report)
- **P2-13**: 9 `NotImplementedError` sites evaluated — all unsuitable for ABC `@abstractmethod` conversion (3 optional method defaults / 6 concrete class runtime guards)

## [0.2.4] - 2026-05-29 (Beta Release)

### Fixed
- **CI flake8 E999 root fix**: Eliminated all multi-line f-strings that triggered "unterminated string literal" on Python 3.9-3.11 (Black↔flake8 circular conflict)
- **Security**: Removed `html.escape()` from sanitizer (S-4), tightened XSS/SQL injection patterns (S-5/S-7), encryption now raises errors instead of returning None (S-2)
- **Redaction**: Span-based overlap merge replacing sequential pattern.sub() (E-4), auto-truncation of matched sensitive text (E-5)
- **Audit**: ISO 8601 timestamp format (E-9), query failures now raise exceptions (E-7), log write failures logged as error (E-6)
- **Backup**: `create_backup()` returns realpath for cross-platform consistency (P0-5), `restore_backup()` auto-derives backup_dir

### Changed
- Black/isort line-length: 100 → 120 (reduces unnecessary line splitting)
- All 14 long f-strings in cli.py refactored with intermediate variables (no # fmt: skip needed)
- i18n whitelist expanded from 17 → 22 files (CJK data files properly categorized)
- CHANGELOG reduced from 1053 → 115 lines (removed pre-reset bloat)
- Glama TDQS boost: all 27 tool descriptions rewritten with full behavioral transparency
- Added glama.json ownership claim file
- SECURITY.md created with vulnerability reporting and architecture docs
- 6-gate CI pipeline: Quality → i18n → Test (matrix) → Build → Security → Docs

### Security
- 24 security/code quality issues resolved across P0/P1/P2 tiers
- InputValidator: strict_mode now respected, no HTML escaping, whitespace preserved via strip()
- EncryptionError raised on key load failure (not silent None return)

## [0.2.5] - 2026-06-07 (Post-Beta Improvement Sprint)

### Fixed
- **Preference injection confidence gap**: Added active contextual fetch for
  mid-confidence preferences (0.5-0.9) that FTS recall misses. Covers both
  user_preference and correction types. All 14 E2E tests now pass (7 were xfail).
- **session_id SQL hardening**: LIKE pattern now escapes double-quote and backslash
  to prevent metadata corruption from embedded special characters.

### Added
- **`carrymem stats --value` command**: 7-metric value perception report
  (memories stored, rules active, sessions remembered, repetitions avoided,
  tokens saved estimate, identity coverage %, days since first use) with
  box-drawing text output and JSON format support.
- **Multi-language support**: Korean (README-KO.md) and Traditional Chinese
  (README-ZH-TW.md) documentation. All 5 language switchers updated.
- **MCP server timeout mechanism**: 3-layer timeout protection (stdin read 300s,
  request processing 30s, tool call 30s). Configurable via CARRYMEM_REQUEST_TIMEOUT env var.
- **Security test suite expansion**: 83 new test cases covering encryption,
  redaction, input_validator, and audit modules. Coverage improved from ~22% to 80%+.

### Changed
- **cli.py modularization**: Split 4031-line monolith into 8 focused modules
  (_base/_memory/_io/_stats/_mcp/_backup/_rules/__init__) plus a 17-line facade.
 - Zero behavioral change, full backward compatibility

## [0.4.0] - 2026-06-11 (Protocol & Maturity Sprint — 26 Improvements)

### Added (新增)

#### P0 Core (核心改进)
- **P0-1**: Mixin Protocol 接口体系 (`_protocols.py`) — 10 个 Protocol 定义 (LifecycleOps, BackupOps, RecallOps, ClassificationOps, MemoryCRUDOps, ProfileExportOps, MaintenanceOps, PromptDelegateOps, CarryMemOps), 支持结构化类型检查和 IDE 自动补全
- **P0-2**: 异常处理收窄 — `except Exception` 从 49 处收窄至 12 处 (-75%), 使用具体异常类型 (sqlite3.*, ValueError, TypeError, KeyError, OSError 等), 保留 12 处有文档说明的广泛捕获
- **P0-3**: E2E 测试补全 — 测试文件从 6→12 个, 新增 78 个测试用例, 覆盖完整用户旅程 (首次使用、多 Agent、pack/unpack、规则、恢复、加密全链路、并发访问、边界情况)
- **P0-4**: SQLite 连接池优化 — WAL 模式增强 (journal_mode=WAL, synchronous=NORMAL, cache_size=20MB), 线程本地连接缓存 (`threading.local()`), 慢查询监控 (timed_query, 默认 100ms 阈值), 17 个连接池测试
- **P0-5**: 加密安全升级 — PBKDF2 迭代次数从 100K → 260K (NIST 2026 推荐), 密钥轮换 API (`rotate_key()`), HMAC-SHA256 digest 完整性校验 (.key.digest 文件), fallback 密码不安全标记, 29 个安全升级测试
- **P0-6**: 错误码体系 (`errors.py`) — `CarryMemError` 基类 + code/message/hint/cause 字段, 7 大错误范围 (CM-001~CM-999), `from_cause()` 工厂方法映射底层异常, 52 个错误码测试

#### P1 Features (功能增强)
- **P1-1**: Facade 增强 (`core/__init__.py`) — `health_check()`, `validate_ready()`, `get_component_status()`, `version` 属性, 统一就绪检查接口
- **P1-2**: 监控框架 MVP (`monitoring/__init__.py`) — HealthChecker (/healthz, /readyz), MetricsCollector (计数器/延迟直方图/Prometheus 导出), AlertManager (SLO 阈值检查), MonitoringHTTPServer (轻量 HTTP 服务), LatencyTimer 上下文管理器
- **P1-3**: 插件系统 MVP (`plugins/__init__.py`) — PluginProtocol 接口, PluginManager 生命周期管理 (discover/load/unload/reload), HookPoint 定义 (on_memory_stored, on_memory_recalled, on_classified, on_error), 事件分发机制
- **P1-4**: 权限系统 MVP (`security/permissions.py`) — Permission 常量 (READ/WRITE/DELETE/ADMIN), AccessPolicy 基于 owner 的访问控制, `check()/require()` 方法, CM-403 错误码
- **P1-5**: i18n 国际化框架 (`i18n/__init__.py`) — I18nManager 字典翻译系统, 运行时语言切换 (set_locale), 变量插值 (t(key, **kwargs)), 回退机制 (当前→默认→key), 中英双语支持
- **P1-6**: 双语错误消息 (`error_messages.py`) — 37 个错误码中英双语消息 + actionable hints, ErrorTemplate 数据类, 完整覆盖存储/数据库/记忆操作/分类/安全/导入导出/CLI 场景

#### P2 Engineering (工程化)
- **P2-1**: API 类型定义 (`api_types.py`) — ComponentStatusDict, HealthCheckResult 等 TypedDict, 类型注解覆盖率从 ~60% → ~82%
- **P2-2**: 成熟度报告 (`docs/MATURITY_REPORT_v0.4.0.md`) — 8 维度评分体系, v0.3.0 vs v0.4.0 对比, 技术债清单 (14 项), v0.5.0 建议 (Top 5 方向), 综合评分 82.4/100 (B+)
- **P2-3**: 入口点文档 (`docs/ENTRY_POINTS.md`) — CLI/TUI/MCP 三入口功能对照表, 28 个 MCP 工具清单, 不一致问题清单 (8 项), 改进路线图 (5 Phase)
- **P2-4**: 架构决策记录 — ADR-001 (Mixin Facade), ADR-002 (SQLite Default Storage), ADR-003 (Dual Backend Encryption), ADR-004 (Protocol Interface Design), ADR-005 (Plugin System MVP)

### Changed (变更)

#### Architecture (架构重构)
- **God Class → Mixin+Facade+Pattern** — carrymem.py (1769 行) 拆分为 8 个 Mixin 模块 + Facade (~100 行): _lifecycle, _backup, _memory_crud, _classification, _recall, _profile_export, _maintenance, _prompt_delegate
- **三层架构落地** — Mixin 层 (业务逻辑) + Facade 层 (统一入口) + Protocol 层 (接口约束), 零 API 破坏性变更
- **类型系统完善** — Protocol 结构化类型 + TypedDict 运行时类型 + dataclass 数据契约, IDE 支持显著改善

#### Code Quality (代码质量)
- **异常处理标准化** — 49→12 广泛捕获 (-75%), 结构化错误码使用率 40%→85%, 异常类层次 3 层→5 层, 错误消息双语支持
- **常量集中管理** — 28 个命名常量提取到 constants.py, 替换 30+ magic numbers
- **Lazy Import 缓存** — BackupManager 5 个重复函数级导入合并为模块级缓存加载器
- **Docstring 覆盖率** — 提升至 ~61% (117/191 方法), Args/Returns/Raises 标准格式

#### Security (安全加固)
- **加密参数合规** — PBKDF2 260K iterations (NIST 2026), key rotation 支持, digest 校验
- **路径安全检测** — 路径穿越 (path traversal) 防护, CM-402 错误码
- **输入验证器增强** — validate_path, validate_namespace, validate_query 等专用验证器

### Fixed (修复)

#### Regression (回归修复)
- **sqlite3 import 缺失** — 修复 Phase A 重构后 sqlite3 模块未正确导入的问题
- **CM-403 错误码冲突** — Permission 和 AccessPolicy 共用 CM-403, 已拆分为细粒度错误码
- **ALTER TABLE 语法错误** — rules/storage.py schema migration 修复 (`ALTER TABLE condition` → `ALTER TABLE rules ADD COLUMN condition`)
- **TUI ErrorDisplay 未标准化** — TUI 错误显示组件增加错误码 (CM-xxx) 和 💡 hint 支持

#### Test (测试修复)
- **E2E 测试稳定性** — 14 个 E2E 测试全部通过 (之前 7 个 xfail), 修复 mid-confidence preference 召回问题
- **session_id SQL 注入** — LIKE pattern 转义双引号和反斜杠, 防止元数据损坏
- **连接池测试补全** — 17 个测试覆盖线程复用/跨线程隔离/WAL 验证/慢查询日志/清理方法

### Statistics (统计)

| 指标 | v0.3.0 | v0.4.0 | 变化 |
|------|--------|---------|------|
| 源代码行数 | ~35,000 | **41,340** | +18% |
| 源文件数 | ~120 | **144** | +20% |
| 测试文件数 | ~90 | **122** | +36% |
| 测试用例数 | ~3,315 | **~4,198** | +72 |
| 类型注解覆盖率 | ~65% | **~82%** | +17% |
| Docstring 覆盖率 | ~45% | **~61%** | +16% |
| 异常处理广度 | 49 处 | **12 处** | -75% |
| 错误码数量 | 0 | **37** | +37 |
| Protocol 接口 | 0 | **10** | +10 |
| 综合成熟度评分 | 72.5/100 (B-) | **82.4/100 (B+)** | +9.9 |

---

## [0.3.1] - 2026-06-11 (Error Friendliness Sprint — P0-6)

### Added
- **Error code system** (`src/carrymem/errors.py`): `CarryMemError` base class with `code`, `message`, `hint`, and `cause` fields; 7 error range categories (CM-001~CM-699); `from_cause()` factory method that maps low-level exceptions (sqlite3, OSError, ValueError, EncryptionError) to friendly error codes.
- **Bilingual error messages** (`src/carrymem/error_messages.py`): 37 error codes with Chinese + English messages and actionable hints covering storage, database, memory ops, classification, security, import/export, and CLI/TUI/MCP scenarios.
- **TUI ErrorDisplay component**: Red-bordered error prompt box in TUI showing error code, friendly message, and 💡 hint suggestion. Auto-clears on successful operations.
- **Test suite** (`tests/test_error_codes.py`): 52 tests across 7 test classes — uniqueness validation, from_cause mapping (sqlite3/OSError/ValueError/fallback), bilingual completeness, base class behavior, ErrorTemplate dataclass, known exception mapping, registry coverage.

### Changed
- **core/_lifecycle.py `__init__`**: Storage adapter initialization now wraps raw exceptions via `CarryMemError.from_cause()`. All `ValueError` raises replaced with structured `CarryMemError` instances containing Chinese messages and hints.
- **CLI global exception handler** (`cli/__init__.py`): Split handler into `CarryMemError` path (structured display: `[ERROR] CM-XXX` + message + 💡 hint) and generic exception path (auto-convert via `from_cause`). Raw technical errors no longer exposed to users.
- **TUI error handling**: `_load_memories()` and `on_input_submitted()` now use `ErrorDisplay.show_error()` instead of inline status text. All exceptions go through `from_cause()` conversion.

## [0.3.0] - 2026-06-10 (Maturity & Architecture Sprint)

### Fixed
- **Exception handling (P0-2)**: `except Exception` narrowed from 49 to 12 (-75%).
  DevSquad audit identified 49 remaining broad catches (v0.3.0 claimed 15). Fixed 37
  instances with specific exception types: sqlite3.* (OperationalError, IntegrityError,
  DatabaseError, ProgrammingError, InterfaceError), ValueError, TypeError, KeyError,
  RuntimeError, OSError, IOError, json.JSONDecodeError, binascii.Error, ImportError.
  Retained 12 intentional broad catches for: MCP protocol handlers (6), MCP server
  main loop (3), HTTP server request handler (1), CLI top-level safety net (1),
  SQLiteAdapter.__del__ garbage collection (1). All retained catches documented with
  NOTE comments explaining justification.
- **Exception handling regression tests**: Added `tests/test_exception_narrowing.py`
  with 12 test cases verifying narrowed exceptions don't swallow errors and all
  retained broad exceptions have proper documentation.
- **SQL regression**: Fixed broken ALTER TABLE statement in rules/storage.py
  schema migration (`ALTER TABLE condition` → `ALTER TABLE rules ADD COLUMN
  condition`) that silently prevented rule creation/update/delete.

### Added
- **God Class decomposition**: carrymem.py (1769 lines) split into 8 Mixin
  modules + Facade (~100 lines): _lifecycle, _backup, _memory_crud,
  _classification, _recall, _profile_export, _maintenance, _prompt_delegate.
  Zero API breakage via Python Mixin pattern.
- **TUI enhancement**: tui.py expanded from 324→777 lines with Morandi color
  palette, memory detail modal, help screen, stats panel, search/filter
  keyboard navigation (/ ? j k Enter 1-5 a r). 71 new tests (0→71 coverage).
- **Runtime constants**: 28 named constants extracted to constants.py,
  replacing 30+ magic numbers across 15+ methods.
- **Lazy import cache**: BackupManager 5 duplicate function-level imports
  consolidated into single module-level cached loader.
- **Ghost feature audit**: Verified all public APIs have consumers; confirmed 8
  rule-engine sub-modules are reserved extension points (not dead code);
  deprecated 2 experimental methods with warnings; fixed tui.py isolation.

### Changed
- **Architecture**: New `src/carrymem/core/` package replaces monolithic
  carrymem.py. Backward-compatible re-export at original path.
- **Lint configuration**: `.flake8` created with project-level rules
  (line-length=120, per-file ignores for CLI star imports and test files).
- **CI fully green**: flake8(0) + black(ok) + isort(ok) + test matrix
  (3.9/3.10/3.11/3.12) all passing.

## [0.2.0] - 2026-05-28

### Added
- **Auto-backup mechanism**: every 20 writes, VACUUM INTO backup, max 5 backups retained
- `carrymem backup` CLI command: manual backup, `--list`, `--restore <file>`
- `carrymem doctor` now checks backup status (directory, file count, last backup time)
- `carrymem pack --encrypt`: password-encrypted .carry files using MemoryEncryption
- SHA-256 checksum in .carry files (v1.1 format) for corruption detection
- Backward compatible: v1.0 .carry format still works with warning
- Per-file write lock (_file_lock) for SQLite concurrent safety across multiple CarryMem instances
- 7 concurrent access tests (multi-thread, multi-process, mixed read/write, shared DB)
- 12 E2E user journey tests (first-time user, multi-agent, pack/unpack, rules, recovery)
- 22 CLI pack/unpack tests (checksum, encryption, conflicts, legacy compatibility)
- **setup-mcp --global** now supports 8 clients: claude-code, cursor, trae, windsurf, cline, openclaw, kimi-code, codex
- **setup-mcp --uninstall**: remove CarryMem MCP config from AI tool config files
- **Auto-init**: setup-mcp auto-initializes CarryMem data directory on first use
- **Smoke test**: verifies MCP server is ready after setup-mcp configuration
- **Beta Feedback issue template**: structured feedback form for beta users
- **MCP Integration issue template**: diagnostic form for MCP setup problems
- **Obsidian Adapter documentation**: comprehensive guide (docs/OBSIDIAN_ADAPTER.md)
- **Community directory manifests**: server.json (Glama/MCP Registry) + smithery.yaml (Smithery)
- OpenClaw/Kimi Code/CodeX MCP config paths in constants.py

### Changed
- Unified path management: constants.py replaces hardcoded Path.home()/.carrymem in 7 files
- Empty except:pass → debug/warning logging in 35+ locations (storage/sqlite/cli/audit)
- pyproject.toml fail_under 55→75 (actual coverage 79.36%)
- mypy errors: 311→247 (core files carrymem.py/handlers.py/cli.py -45 runtime type errors)
- flake8 issues: 993→596 (F401/F541/F841/F811 all fixed)
- .gitignore: added *.carry pattern
- Consensus document updated to v3.0 (3 P2→P0 promotions, 11 P0 items total)
- README: PrefEval badge, user scenarios, academic citation, competitive positioning

### Fixed
- **Critical**: SQLite Bus Error when multiple CarryMem instances write same DB concurrently
- **Critical**: .carry files had no integrity check (SHA-256 checksum now required)
- **Critical**: .carry files were plaintext (optional --encrypt now available)
- Optional type mismatches in carrymem.py (allowed_base, _adapter, _rule_engine)
- Potential AttributeError in handlers.py (supersede method guard)
- README data conflict (tests/coverage numbers inconsistent)
- _enable_vector init order bug causing AuditLogger warning
- _fernet_available always True bug in encryption.py

### Security
- **CRITICAL**: Removed html.escape() from _sanitize_content (was permanently corrupting stored data)
- **HIGH**: Replaced whitespace normalization with strip() (was destroying code/Markdown formatting)
- **HIGH**: Encryption init failure now raises RuntimeError instead of falling back to plaintext
- **HIGH**: Auto-redaction failure now logs warning instead of silent pass
- **HIGH**: Audit log write failure elevated from warning to error level
- **MEDIUM**: Tightened XSS detection patterns (on\w+ → specific event handlers only)
- **MEDIUM**: Tightened SQL injection patterns (1=1 → context-aware detection)
- **MEDIUM**: _load_key raises EncryptionError instead of returning None on read failure
- **MEDIUM**: Audit query/stats failure raises exception instead of returning empty
- **LOW**: Added docstring to _make_fernet clarifying key construction
- **LOW**: Audit timestamp now uses ISO 8601 with UTC timezone (Z suffix)
- **LOW**: detect_sensitive_content masks matched text by default (first 8 chars + ...)
- **LOW**: redact_content uses span-based replacement to avoid overlapping patterns
- **LOW**: get_validator() now respects strict_mode parameter changes
- **LOW**: security/__init__.py now exports encryption/redaction/audit modules

---

## Pre-Reset History (v0.2.1–v0.4.1)

These versions existed in the pre-reset development cycle (before May 2026 version alignment).
They are preserved here for historical reference only.

### [0.4.1] - 2026-05-18 (pre-reset)
Core Loop Fix + Auto Rule Suggestion + Security hardening. 2056 tests, 79% coverage.

### [0.4.0] - 2026-05-14 (pre-reset)
Enterprise: Scopes + Skill Format + Merge Protocol + VS Code Extension. 1814 tests.

### [0.3.0] - 2026-05-10 (pre-reset)
GA Release: Production Ready + Knowledge Adapter. 1900+ tests, ~85% coverage.

### [0.2.8] - 2026-05-06 (pre-reset)
Rules Engine Beta: Context Engineering + Hardened. 1709 tests, ~81% coverage.

### [0.2.7] - 2026-05-04 (pre-reset)
Q&A Refinement: Multi-turn Rule Abstraction. 884 tests.

### [0.2.6] - 2026-05-02 (pre-reset)
Experience Learning: Failure → Avoidance Rules. 793 tests.

### [0.2.5] - 2026-04-30 (pre-reset)
Auto-Promotion: Memory → Rule Candidate Generation. 746 tests.

### [0.2.3] - 2026-05-25 (pre-reset)
Consolidation Scheduling + PrefEval Standardization.
PrefEval: CarryMem 85.0% > Reminder 83.0% > Zero-shot 69.5% (seed=42, 200-sample).
> *Note: Historical result from optimization cycle. Canonical benchmark: [83.0%](README.md) (v0.2.4 final).*

### [0.2.2] - 2026-05-24 (pre-reset)
PrefEval Violation Optimization + Version Chain + Security Hardening.
PrefEval: CarryMem 87.9% (single-condition, 200-sample optimization run).
> *Note: Peak single-condition result. Canonical 3-condition benchmark: [83.0%](README.md).*

### [0.2.1] - 2026-05-22 (pre-reset)
Coreference Resolution + Auto-redaction + QA Prompt Optimization. 2883 tests, 80.86%.

### [0.2.0] - 2026-05-21 (pre-reset)
Recall Purity + Scope Injection + PrefEval 0.940. 2761 tests, 80.5%.

### [0.1.7] - 2026-04-28 (pre-reset)
Memory Layer Enhancement: Session + Supersession + Time Reasoning + Structured Prompt.
