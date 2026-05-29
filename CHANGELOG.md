# Changelog

All notable changes to CarryMem will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Version Reset Notice**: In May 2026, the version was reset from v0.4.1 back to v0.2.0
> to align Git, PyPI, and documentation versions. Entries below marked as "(pre-reset)" are
> historical records from the pre-reset development cycle and should not be confused with
> the current v0.2.x series.

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
Consolidation Scheduling + PrefEval Standardization. PrefEval 85.0% > Reminder 83.0%.

### [0.2.2] - 2026-05-24 (pre-reset)
PrefEval Violation Optimization + Version Chain + Security Hardening. PrefEval 87.9%.

### [0.2.1] - 2026-05-22 (pre-reset)
Coreference Resolution + Auto-redaction + QA Prompt Optimization. 2883 tests, 80.86%.

### [0.2.0] - 2026-05-21 (pre-reset)
Recall Purity + Scope Injection + PrefEval 0.940. 2761 tests, 80.5%.

### [0.1.7] - 2026-04-28 (pre-reset)
Memory Layer Enhancement: Session + Supersession + Time Reasoning + Structured Prompt.
