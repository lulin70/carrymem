# Changelog

All notable changes to CarryMem will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.2] - 2026-05-02

### Fixed — UX Remediation (User Experience Review)
- **CLI command not found** — added `bin/carrymem` script + `scripts` field in setup.py
- **pip version mismatch** — `get_version()` now reads `__version__.py` via regex instead of import
- **Rule suggestion quality** — rewrote `_extract_trigger()` and `_extract_action()`:
  - Trigger: domain-specific scene descriptions (e.g., "programming language selection" instead of "python")
  - Action: extracted behavior instructions (e.g., "prefer python over java" instead of "遵循: I prefer...")
  - Quality filters: skip vague triggers, comma-separated word dumps, and duplicate suggestions
  - Limited to 3 suggestions max per call
- **Implicit preference detection** — raised threshold from 2 to 3 occurrences, unified to English
- **Pattern detection filter** — skip low-quality suggestions with vague triggers

### Added — User Experience Improvements
- **CLI aliases**: `carrymem remember` = `carrymem add`, `carrymem save` = `carrymem add`
- **`carrymem rules` sub-command hub**: `carrymem rules list/add/delete/match/edit/...`
- **`carrymem tutorial`**: 5-minute interactive quick-start guide
- **`rule_suggestions` field**: unified return field name (with `auto_rules` backward compat)
- **`from carrymem import CarryMem`**: compatible import path
- **`build_system_prompt()` convenience function**: in `layer2_mcp` module
- **TROUBLESHOOTING.md**: comprehensive troubleshooting guide

### Changed
- Version upgraded to v0.4.2
- `_detect_implicit_preferences()` minimum memory count raised from 1 to 3
- `_detect_implicit_preferences()` minimum tech count raised from 2 to 3

## [0.4.1] - 2026-05-02

### Added — Core Loop Fix (Product初心 Review)
- **`_auto_suggest_rules()`** — automatic rule candidate generation from stored memories
  - Trigger extraction from natural language (tech keyword detection, domain hints)
  - Rule type inference from memory type (correction→avoid, decision→always, preference→prefer)
  - Integration with PatternDetector for pattern-based suggestions
- **MCP rule tools target fix** — shared RuleEngine instance in Handlers
  - Handlers.__init__ creates shared RuleEngine with correct db_path
  - Rule tools target changed from None to self._rule_engine
- **`get_system_prompt` auto-inject without context** — rules always injected
  - No-context path lists all active rules and formats them
  - Global rules always available in AI prompt
- **User management MCP tools**:
  - `my_rules` — view all rules in readable summary format
  - `delete_rule` — delete a rule by ID
  - `update_rule` — update rule trigger/action/scope/type
  - `my_profile` — complete user identity view (memories + rules + distribution)
  - `onboard` — first-time user guidance (EN/ZH/JA)
  - `suggest_rules` — analyze memories and suggest rule candidates
  - `promote_rules` — run full promotion pipeline
- **Rule injection security filter** — INJECTION_DANGER_PATTERNS regex in RuleInjector
- **Correction auto-updates old memories/rules** — `_handle_correction()` method
- **Rule application feedback** — `applied_rules` field in build_context response
- **Rule conflict detection** — `_conflict_warnings` on add_rule when same trigger+scope exists
- **FTS5 rank score optimization** — `search_with_rank()` method with dynamic scoring
- **Rule expiry mechanism** — `expires_at` field + `is_expired()` method + matcher filtering
- **CLI rule management enhancement** — `--format table/compact/detail` for list-rules
- **`carrymem doctor` enhancement** — rules engine check + auto-inject status check
- **MCP config auto-inject** — `CARRYMEM_AUTO_INJECT` and `CARRYMEM_ONBOARD_NEW_USER` env vars

### Tests
- Natural conversation preference extraction tests (23 cases)
- E2E user journey tests (conversation→store→rule→inject→verify)
- Promotion pipeline integration tests
- Multi-turn conversation accumulation tests
- Rule management CRUD tests
- Onboarding flow tests (EN/ZH/JA)
- Total: 2056 tests passing

## [0.4.0-dev] - 2026-05-02

### Added
- **Rule Scope dimension** (personal/company/negotiated)
  - `RuleScope` type alias + `VALID_RULE_SCOPES` + `SCOPE_PRIORITY` in models.py
  - Rule model: new `scope` field (default: `personal`, backward-compatible)
  - Storage: `scope` column with CHECK constraint + index
  - `RuleEngine.add_rule(scope="personal")` — scope-aware creation
  - `RuleEngine.list_rules(scope="company")` — scope-aware filtering
  - `RuleEngine.match(scopes=["company", "personal"])` — scope-aware matching
  - `RuleInjector` scope labels: `[COMPANY]`, `[NEGOTIATED]` in anchored/structured output
  - `get_effectiveness_report()` now includes `scope_breakdown` and `scope_trigger_totals`
- **Rule Skill Format** (`carrymem-skill-v1`)
  - Skill manifest: name, version, author, description, scope, dependencies, tags
  - Content signature: SHA-256 hash for integrity verification (manifest included)
  - `RuleEngine.skill_pack()` — export rules as portable Skill bundle
  - `RuleEngine.skill_install()` — import Skill with scope override + conflict resolution
  - `RuleEngine.skill_verify()` — verify Skill bundle integrity
  - CLI: `carrymem skill-pack <path> --name <name>`
  - CLI: `carrymem skill-install <path> --scope company --mode skip|overwrite|rename`
  - CLI: `carrymem skill-verify <path>`
  - Backward-compatible: `carrymem-rules-v1` import still supported
- **Rule Merge Protocol** ("customs clearance")
  - `merge_protocol.py`: scope-aware merge engine with 3 strategies
  - `MergeStrategy`: company_overrides / negotiate / keep_both
  - `detect_merge_conflicts()`: trigger_overlap + type_contradiction detection
  - `resolve_conflict()`: scope-priority resolution (company override rules ALWAYS win)
  - `review_incoming_rules()`: preview conflicts without modifying data
  - `accept_rules()`: apply merge strategy + store accepted rules + delete replaced rules
  - `MergeResult.replaced_ids`: tracks rules replaced during merge
  - Merge audit trail: all decisions logged with timestamp, reason, details
- **VS Code Extension** (TypeScript)
  - `extensions/vscode-carrymem/` — full extension scaffold
  - Rule List sidebar with scope badges (shield/company, git-merge/negotiated, person/personal)
  - Rule Editor Webview (add/edit with trigger, action, type, scope, override)
  - Commands: refresh, add, edit, delete, toggle (pause/resume), match for current file
  - Effectiveness Report panel (HTML webview with stats tables)
  - Skill operations: pack and install via file dialogs
  - Configuration: dbPath, autoMatch, defaultScope
  - Communication via CarryMem CLI subprocess

### Fixed (Code Review 2026-05-02)
- **[Critical]** FTS5 search SELECT missing `scope` column — results always showed "personal"
- **[Critical]** `KEEP_INCOMING` merge decision didn't delete existing rule — caused duplicate conflicts
- **[Critical]** Skill signature didn't cover manifest — scope/author could be tampered without detection
- **[Critical]** `import_rules()` didn't pass `scope` field — imported rules lost their scope
- **[High]** `storage.update()` didn't allow updating `scope` field
- **[High]** `skill_install()` overwrite mode didn't update scope
- **[High]** `merge_rules()`/`review_incoming_rules()` mutated incoming Rule objects (side effect)
- **[High]** `skill_install()` didn't check `RuleLimiter` total limit
- **[High]** Skill duplicate detection key didn't include scope — cross-scope rules misidentified
- **[High]** VS Code EditorPanel didn't update content when reusing existing panel
- **[Medium]** `renderReport()` HTML injection — user input not escaped in webview
- **[Medium]** `skill_install()` imported `RuleSanitizer` inside loop
- **[Medium]** Empty rules list could be packed into a Skill bundle
- **[Low]** `__version__` updated from 0.2.8 to 0.4.0-dev

## [0.3.0-dev] - 2026-05-01

### Added
- **Knowledge Adapter: CJK trigram full-text search**
  - ObsidianAdapter FTS5 tokenizer: `unicode61` → `trigram` for CJK character-level matching
  - Auto-migration from `unicode61` → `trigram` on existing databases
  - Fallback LIKE search when FTS5 query fails (e.g., short queries < 3 chars)
- **Knowledge Adapter: Content truncation configurable**
  - `content_truncate` parameter (default 2000, was 500)
  - `full_content=True` on `recall()` returns complete content without truncation
- **Knowledge Adapter: Relevance scoring**
  - `relevance_score` field in recall results
  - Scoring: FTS5 rank (60%) + tag overlap (25%) + wiki-link proximity (15%)
- **Three-layer retrieval orchestration**
  - `recall_all()` now includes `rules` layer with `include_rules=True`
  - `build_context()` budget allocation: Rules 30% / Memory 45% / Knowledge 25%
  - `build_system_prompt()` structured output: Rules → Memory → Knowledge
  - `max_rules` parameter on `build_context()` and `build_system_prompt()`
- **`trigger_count` activation**
  - `RuleStorage.increment_trigger_count(rule_id)`: atomic DB update
  - `RuleStorage.batch_increment_trigger_counts(rule_ids)`: batch update
  - `RuleEngine.match()` now increments trigger_count by default (`increment_count=True`)
  - Frequency bonus in RuleMatcher now functional
- **Rule effectiveness metrics**
  - `RuleEngine.get_effectiveness_report()`: trigger stats, confidence distribution,
    type breakdown, override usage, top-triggered/never-triggered lists, derivation sources
- **Source memories confidence validation**
  - `RuleEngine.validate_source_memories(rule_id)`: checks active/deleted/superseded status
  - Auto-calculated confidence adjustment penalty
- **TypedDict return types** (`api_types.py`)
  - `RuleDict`, `MatchResultDict`, `EffectivenessReportDict`, `SourceMemoryValidationDict`
  - `KnowledgeNoteDict`, `RecallAllResultDict`, `BuildContextResultDict`
  - All dict-compatible, importable from package root
- **API Stability: Rules Engine promoted to Stable**
  - `add_rule`, `list_rules`, `match_rules`, `edit_rule`, `delete_rule`, `pause_rule`, `resume_rule`
  - `get_effectiveness_report`, `validate_source_memories`
  - Advanced features (inject, promote, refine, experience) remain Experimental

## [0.2.8] - 2026-05-01

### Added
- **Security Audit**: InputValidator integrated into all external input paths
  - CLI: `cmd_add`, `cmd_search`, `cmd_edit`, `cmd_forget` now validate inputs
  - MCP handlers: all 8 input handlers now validate via `_validate_input()` / `_validate_query_input()`
  - `import_memories()`: validates imported content before storage
  - `_contains_command_injection()` now called in `validate_content()` and `validate_query()`
- **API Stability Policy**: `docs/API_STABILITY.md` — Stable/Experimental/Internal tier classification
  - Deprecation policy: 2 minor version grace period + DeprecationWarning
  - Conditional imports: `_make_lazy_import()` replaces `None` sentinel pattern
- **`carrymem doctor` comprehensive health check** (14 checks, was 11)
  - New: database file permissions, disk space, database lock detection
  - `--json` flag for structured output (automation-friendly)
  - `--fix` no longer writes test data to database
  - Structured `_record()` method replaces ad-hoc counters
- **DevSquad Integration Adapter** (`integration/devsquad/`)
  - `DevSquadAdapter` implements MemoryProvider + CarryMemAdapter protocols
  - `is_available()`, `get_rules()`, `add_rule()`, `update_rule()`, `delete_rule()`
  - `match_rules()`, `format_rules_as_prompt()`, `log_experience()`
  - `type_mapping.py`: bidirectional rule type mapping (forbid↔forbid, avoid↔avoid, always↔always)
  - `protocol.py`: `@runtime_checkable` Protocol definitions
  - Audit logging for all operations (source="devsquad")
  - Graceful degradation: all methods safe when `is_available()=False`
- **Test coverage ≥ 80%** (80.68%, up from 68.61%)
  - 1709 tests passing (up from 884)
  - New test files: test_cli_comprehensive, test_carrymem_full, test_handlers, test_mcp_server, test_audit, test_devsquad_adapter
- **AuditLogger tests**: 25 independent tests for `security/audit.py`
- `setup.py`: added `[devsquad]` and `[full]` extras
- `ContextBudget` — Token-aware context budget monitor
  - CJK/English mixed token estimation heuristic
  - 70% compression threshold with override-priority preservation
  - `compress_rules()` — drops soft rules when over budget
  - `should_compress()` — check if text exceeds threshold
- `RuleInjector` anchored layout mode (`format="anchored"`)
  - Head anchor: override=True + forbid rules (highest LLM attention)
  - Middle: normal rules by relevance (lower attention zone)
  - Tail anchor: override=True + always rules (high attention)
  - `_classify_anchored()` — tri-partition matches into head/middle/tail
  - Addresses Lost-in-the-Middle effect in LLM context windows
- `RuleInjector` DDD language view (`format="ddd"`)
  - Maps CarryMem concepts to Domain-Driven Design terminology
  - forbid → Invariant, always → Consistency Guarantee, avoid/prefer → Soft Constraint
  - trigger → Bounded Context, override → Invariant Flag
  - source_memories → Event Sourcing Chain (in metadata)
  - Display-only, no storage layer changes
- `RuleInjector.estimate_context_usage()` — estimate token usage for a scene
- `RuleInjector.inject()` now accepts `context_budget_tokens` parameter
- `RuleEngine.inject()` now passes through `context_budget_tokens`
- CLI: `match-rules` supports `--format anchored|ddd` and `--context-budget <tokens>`
- `VALID_FORMATS` constant listing all supported output formats

### Tests
- 44 new tests for context engineering (anchored layout, DDD view, budget compression)
- 928/928 total passing (884 existing + 44 context engineering)

## [0.2.7] - 2026-04-30

### Added
- `RuleRefiner` — Multi-turn Q&A for rule abstraction
  - 4 refinement phases: Scope → Generality → Exception → Confirm
  - Specificity analysis: detect project/tool/time-specific rules
  - Template-based question generation with multiple-choice options
  - Scope broadening: "avoid MongoDB" → "avoid document databases"
  - Exception handling: "unless explicitly approved"
  - Confidence increases with each refinement round
- `RefinementSessionManager` — Session persistence and conversation tracking
  - `refinement_sessions` table with full audit trail
  - Start/answer/confirm/cancel workflow
  - Conversation history stored as JSON
  - Configurable expiry (default: 7 days), max 5 rounds
  - Auto-forced confirm when max rounds reached
- `RuleEngine` high-level API:
  - `start_refinement()`, `answer_refinement()`, `confirm_refinement()`
  - `cancel_refinement()`, `list_refinement_sessions()`, `get_refinement_detail()`
- CLI commands:
  - `carrymem refine-rule --trigger <scene> --action <action>` — Start refinement session
  - `carrymem refine-rule --session <id> --answer "..."` — Answer question
  - `carrymem refine-rule --session <id> --confirm` — Confirm and create rule
  - `carrymem refinement-sessions` — List active sessions
- `refinement_session` added to `VALID_DERIVATION_SOURCES` in models.py

### Fixed
- Python 3.9 compatibility: f-string backslash expressions extracted to variables
- Test adjustments for specificity analysis and question generation

### Tests
- 38 new tests for refinement (refiner + session manager)
- 884/884 total passing

## [0.2.6] - 2026-04-30

### Added
- `FailureExperienceExtractor` — Extract actionable lessons from single failure memories
  - 5 failure signal types: mistake, regret, negative_outcome, lesson_learned, correction_from_failure
  - Bilingual pattern matching (English + Chinese)
  - Domain inference from content (7 domains: competitive_analysis, vendor_management, tech_selection, etc.)
  - Confidence scoring based on signal type and content richness
  - Trigger/action hint generation for rule candidates
- `ExperienceRuleBridge` — Bridge failure lessons to rule candidates with confirmation workflow
  - `extract_lessons()` — Extract and queue lessons from memories
  - `accept_lesson()` — Accept a lesson and create an "avoid" rule (with optional trigger/action override)
  - `reject_lesson()` — Reject a pending lesson
  - `experience_audit` table — Full audit trail of all experience→rule actions
  - Configurable expiry for pending lessons (default: 14 days)
  - Queue size limit (max 30 pending lessons)
  - Duplicate detection — skip already-processed source memories
- `RuleEngine` high-level API:
  - `extract_failure_lessons()`, `list_pending_lessons()`, `accept_lesson()`, `reject_lesson()`
  - `get_lesson_log()`, `get_lesson_stats()`
- CLI commands:
  - `carrymem learn-experience` — Extract failure lessons from memories
  - `carrymem review-lessons` — Review/accept/reject pending lessons (with --trigger/--action override)
  - `carrymem lesson-log` — View experience learning audit log

### Fixed (3D Code Review)
- L4: `_infer_trigger` fallback changed from Chinese to English ("related scenarios")
- S2: Input content length capped at 2000 chars to prevent ReDoS
- L3: `_get_processed_source_ids` only queries pending/accepted statuses (perf optimization)
- Regex fix: `should not have` pattern now correctly matches "Should not have used..."

### Tests
- 47 new tests for experience learning (extractor + bridge)
- 792/793 total passing (1 perf benchmark flaky)

## [0.2.5] - 2026-04-30

### Added
- `PromotionPipeline` — Automated rule candidate generation from memory patterns
  - 5-stage pipeline: Collect → Detect → Generate → Queue → Confirm
  - Audit trail: every promotion action logged to `promotion_audit` table
  - Configurable expiry for pending candidates (default: 7 days)
  - Queue size limit (max 50 pending candidates)
- `RuleEngine.run_promotion()` — Run full promotion pipeline on memories
- `RuleEngine.list_pending_promotions()` — List pending promotion candidates
- `RuleEngine.accept_promotion()` — Accept a candidate and create active rule
- `RuleEngine.reject_promotion()` — Reject a pending candidate
- `RuleEngine.get_promotion_log()` — Get full audit log of promotion actions
- `RuleEngine.get_promotion_stats()` — Get promotion pipeline statistics
- `carrymem promote-rules` — CLI command to run promotion pipeline
  - `--type` filter by memory type
  - `--auto-accept` auto-accept all candidates (with confirmation)
  - `--expiry-days` configurable candidate expiry
- `carrymem review-promotions` — CLI command to review/accept/reject pending promotions
  - `--accept <id>` accept specific candidate
  - `--reject <id>` reject specific candidate
  - `--accept-all` accept all pending candidates
  - `--note` add review note
- `carrymem promotion-log` — CLI command to view promotion audit log
- `_count_pending()` — Efficient COUNT query for pending candidates
- Trigger validation now checks for prompt injection patterns (security hardening)
- Test: `test_apostrophe_allowed_in_trigger` — Verify apostrophes work in triggers
- Test: `test_prompt_injection_blocked_in_trigger` — Verify injection blocked in triggers

### Fixed
- `import_rules` overwrite mode now uses `update()` instead of `delete+create` (atomicity fix)
- `validate_trigger` now checks for prompt injection patterns (was missing)
- `validate_trigger` relaxed SQL char blocking — apostrophes and backslashes now allowed
- Candidate rule templates internationalized to English (was Chinese-only)
- Domain display names internationalized to English
- Keyword separator changed from `、` to `, ` for English compatibility
- `_expire_old_candidates` now uses single `datetime.now()` call (consistency fix)
- `validate_new_rule` in limiter reduces redundant DB queries

### Tests
- 746/746 passing (718 existing + 28 promotion pipeline)

## [0.2.4] - 2026-04-30

### Added
- `PatternDetector` — Identify repeated memory patterns (avoidance/preference/consistency/aversion)
- `CandidateRuleGenerator` — Convert detected patterns into rule suggestions with templates
- `RuleEngine.suggest_rules()` — Analyze memories and generate rule candidates
- `carrymem suggest-rules` — CLI command to detect patterns and suggest rules
  - `--type` filter by memory type
  - `--min-count` configurable minimum occurrences (default: 3)
  - `--accept` accept all suggestions and create rules
- Keyword extraction: English + Chinese with stop-word filtering
- Negation detection: English + Chinese negation signal identification
- Domain inference: 7 domains (tech_selection, code_review, report, security, api, testing, project)
- Cross-type pattern detection: patterns spanning multiple memory types
- Pattern merging and deduplication

### Fixed
- Fix f-string backslash syntax error in Python 3.9 (cmd_suggest_rules)
- Fix test collection errors in test_v080_cli.py and test_v080_quality.py

### Tests
- 718/718 passing (680 existing + 38 pattern detection)

## [0.2.3] - 2026-04-30

### Added
- `RuleEngine.export_rules()` — Export all rules as portable JSON dictionary
- `RuleEngine.import_rules()` — Import rules with skip/overwrite/rename conflict resolution
- `ImportModeError` — Dedicated exception for invalid import modes
- `carrymem export-rules <path>` — CLI command to export rules to JSON file
- `carrymem import-rules <path>` — CLI command to import rules from JSON file
- `carrymem edit-rule <id>` — CLI command to edit existing rule (trigger/action/type/soft/hard)
- `carrymem list-templates` — CLI command to list available rule templates
- `carrymem add-rule --interactive` — Guided interactive rule creation
- `carrymem add-rule --template <name>` — Create rule from pre-defined template
- `rules/templates.py` — 10 pre-defined rule templates (code-review, report-format, tech-selection, etc.)
- Help text updated with all new commands and usage examples

### Fixed
- Register 4 CLI commands (export-rules, import-rules, edit-rule, list-templates) in command dispatch table
- `export_rules()` now uses dynamic `__version__` instead of hardcoded version string
- `import_rules()` now sanitizes imported rules through RuleSanitizer (security fix)
- `update_rule()` now sanitizes trigger/action/rule_type through RuleSanitizer (security fix)
- `ImportModeError` properly re-raised instead of silently caught in import loop
- `cmd_export_rules()` now handles file write errors (OSError)
- Remove 13 unused imports across test files (flake8: 13→0 errors in test_rules/)

### Tests
- 680/680 passing (639 existing + 20 templates + 21 export/import)
- New test files: `test_templates.py` (20 tests), `test_export_import.py` (21 tests)

## [0.2.2] - 2026-04-29

### Added
- `RuleConflictDetector` — Detects contradictions, overlaps, redundancies, and global rule conflicts
- `RuleConflict` / `ConflictType` / `ConflictSeverity` — Data models for conflict reporting
- `RuleEngine.check_conflicts()` — Public API for conflict detection
- `RuleEngine.check_health()` — Comprehensive rules health check
- `carrymem check-rules` — CLI command for rules health & conflict inspection (--json output supported)
- Performance benchmark test suite (13 tests): match/create/read/update/delete/search latency + storage overhead
- CJK character-level trigger overlap detection in conflict_detector

### Fixed
- Remove 16 unused imports across rules module (flake8: 16→0 errors)
- Fix f-string without placeholders in conflict_detector
- Fix global conflict check logic for new_rule path
- Fix line too long in injector.py timestamp formatting
- Update README version to v0.2.1, test count to 639/639

### Tests
- 639/639 passing (600 existing + 13 performance + 26 conflict detection)

## [0.2.1] - 2026-04-29

### Added
- Rules Engine core implementation (7 modules):
  - `rules/models.py` — Rule dataclass with validation, serialization, lifecycle
  - `rules/sanitizer.py` — Input validation with 10+ prompt injection patterns
  - `rules/limiter.py` — Usage limits (global/total/per-type/rate)
  - `rules/storage.py` — SQLite CRUD with FTS5 full-text search
  - `rules/matcher.py` — Multi-strategy scene matching (global/exact/FTS5/partial)
  - `rules/injector.py` — Prompt formatting (structured/compact/JSON)
  - `rules/__init__.py` — RuleEngine facade for unified API
- 8 CLI commands: add-rule, list-rules, match-rules, delete-rule, pause-rule, resume-rule, rules-stats, check-rules
- Security: prompt injection detection, SQL injection blocking, template injection prevention, HTML/XSS stripping
- Usage limits: max 3 global rules, max 200 total, rate limiting (20/hr, 50/day)

### Fixed
- `from_dict` JSON deserialization for source_memories and metadata fields
- Double validation in `add_rule` eliminated via `_create_validated`
- `__import__` replaced with proper import in sanitizer
- `datetime.utcnow()` replaced with timezone-aware `datetime.now(timezone.utc)`
- SQL field mapping uses safe whitelist in `storage.update()`
- `get_active_global_rules` now correctly filters trigger="*"
- Exception handling added in `limiter.check_rate_limit`
- Active rules cached in matcher (3x→1x DB queries per match)
- FTS5 JOIN column ambiguity resolved with explicit column names

### Tests
- 600/600 passing (490 existing + 110 rules engine)

## [0.2.0] - 2026-04-28

### Added
- Rules Engine design documents (architecture, user stories, test plan, user manual)
- ROADMAP redesigned with v0.2.1(alpha)→v0.2.8(beta)→v0.3.0(GA) version scheme
- ROADMAP updated in three languages (EN/CN/JP)
- Three-layer identity architecture design (Rules > Memory > Knowledge)

## [0.1.2] - 2026-04-28

### Added
- `carrymem whoami` — AI identity portrait showing preferences, decisions, corrections
- `carrymem profile export` — export identity as JSON for cross-AI portability
- `CarryMem.whoami()` — API method returning structured identity summary
- `CarryMem.export_profile()` — API method exporting full identity profile
- Internationalization (i18n): English-primary codebase with CN/JP documentation
- Documentation reorganization: English primary + `-CN`/`-JP` suffix convention
- Sentiment keywords expanded: slow, too slow, painful, annoying, clunky, laggy

### Fixed
- **BLOCKING** `conflict_detector`: offset-naive vs offset-aware datetime crash in `carrymem check`
  - Added `_normalize_dt()` to `ConflictResolver` class
  - Fixed sort comparisons at lines 210 and 365
- **BLOCKING** All GitHub URLs updated from `memory-classification-engine` → `carrymem`
- **BLOCKING** `install.sh`: added pip upgrade step for Python 3.9 compatibility
- All Chinese code comments translated to English (77 mangled comments removed)
- Hardcoded Chinese user-facing strings converted to English default:
  - `helpers.py`: MEMORY_TYPES/MEMORY_TIERS display labels
  - `sqlite_adapter.py`: summary generation strings
  - `pattern_analyzer.py`: description and content format strings
- README.md memory type table corrected (removed non-existent types)
- `.gitignore`: rewritten in English, added missing entries (coverage.xml, .mypy_cache, etc.)
- Removed 4MB Chinese-named image from root directory

## [0.8.1] - 2026-04-27

### Added
- `carrymem show <key>` — detailed memory card view with all metadata
- `carrymem edit <key> <content>` — update memory content with confirmation
- `carrymem clean` — remove expired/low-quality memories (--dry-run, --expired, --quality)
- `carrymem add --force` — bypass classification, always store the message
- Color output: green/red/yellow/cyan/dim/bold for better readability
- Unified memory card format (`_print_memory_card`)
- Command aliases: `ls`=list, `get`=show, `update`=edit
- Doctor now checks for `textual` dependency

### Fixed
- `update_memory()` called with dict instead of string in `cmd_edit()`
- Python 3.9 f-string backslash compatibility (4 fixes)

## [0.8.0] - 2026-04-27

### Added
- Complete CLI rewrite: 19 commands (add/list/search/show/edit/forget/clean/export/import/stats/check/doctor/setup-mcp/tui/serve/init/version/whoami/profile)
- `carrymem setup-mcp` — one-line MCP configuration for Cursor/Claude Code
- `carrymem doctor` — 11 diagnostic checks with `--fix` auto-repair
- `carrymem tui` — Textual terminal UI with sidebar filters, search, add mode
- `carrymem check` — quality & conflict check (--conflicts/--quality/--expired)
- `CarryMem.check_conflicts()` — detect contradictions, duplicates, superseded memories
- `CarryMem.check_quality()` — identify low-quality memories
- `CarryMem.list_expired()` — find expired memories
- CI/CD: GitHub Actions with quality lint, multi-Python testing, build validation
- `setup.py` extras: `pip install carrymem[tui]`, `pip install carrymem[encryption]`

### Fixed
- `ConflictDetector`: use `getattr` for namespace (StoredMemory compatibility)

## [0.7.0] - 2026-04-26

### Added
- MCP HTTP/SSE server (`MCPHTTPServer`) with API key auth
- JSON adapter (`JSONAdapter`) — zero-dependency file-based storage
- Async API (`AsyncCarryMem`) — `run_in_executor` wrapper
- Integration configs for Claude Code and Cursor
- `StoredMemory.from_dict()` — full deserialization including new fields

### Fixed
- AsyncCarryMem `:memory:` SQLite thread issue — use temp file instead
- JSONAdapter forget logic — proper key removal

## [0.6.0] - 2026-04-25

### Added
- Data encryption (`MemoryEncryption`) — Fernet/HMAC-CTR dual backend
- Automatic backup (`BackupManager`) — VACUUM INTO with FIFO cleanup
- Audit logging (`AuditLogger`) — append-only operation history

### Fixed
- `rollback_memory()` deadlock — split into `_update_memory_impl()` (no lock) and `update_memory()` (with lock)
- Schema migration index error — moved indexes to `_migrate_v050()`

## [0.5.0] - 2026-04-24

### Added
- Importance scoring (`scoring.py`) — confidence × type_weight × recency × access
- Query cache (`RecallCache`) — LRU + TTL with write-through invalidation
- Smart context injection (`context.py`) — token budget, relevance ranking
- Memory merge (`merge.py`) — conflict detection, 3 strategies
- Memory versioning — `memory_versions` table, `update_memory()`, `rollback_memory()`
- `build_context()` — structured dict with system_prompt, memories, knowledge

### Fixed
- Cache TTL test hanging — manipulate `expires_at` instead of `time.sleep()`
- `_update_memory_impl` indentation error after SearchReplace

## [0.4.1] - 2024-12-01

### Fixed
- Thread safety issues in SQLiteAdapter (ThreadLocal connections)
- Resource leaks from unclosed database connections
- Potential race conditions in multi-threaded environments
- Memory leak in MemoryClassificationEngine (`message_history` unbounded growth)

### Security
- Fixed potential SQL injection risks in dynamic query construction
- Improved input validation

## [0.4.0] - 2024-11-15

### Added
- Semantic recall with synonym expansion, spell correction, cross-language mapping
- FTS5 full-text search with trigram tokenizer for CJK support
- Content deduplication via `content_hash`

## [0.3.0] - 2024-10-01

### Added
- Obsidian knowledge base adapter
- Multi-namespace support
- Memory profile and statistics

## [0.2.0] - 2024-09-01

### Added
- Three-tier classification engine (Rule → Pattern → Semantic)
- Seven memory types with confidence scoring
- SQLite default storage adapter
- MCP protocol support (stdio)
