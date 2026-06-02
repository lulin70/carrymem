# CarryMem Product Roadmap

**Last Updated**: 2026-05-29
**Product Positioning**: AI Identity Layer — Memory + Rules + Knowledge
**Version Scheme**: v0.2.x (Incremental) → v0.3.0 (GA Milestone)

---

## Version Strategy

```
v0.1.7 ─── Memory Layer Enhancement (Session + Supersession + Time Reasoning) ✅
  │
  ├── v0.2.0  Scene Detection      (Pattern Recognition from Memories)   ✅
  ├── v0.2.1  Rules Engine Alpha   (Manual CRUD + FTS5 Match + Security) ✅
  ├── v0.2.2  Rules Engine Alpha+  (Performance + Conflict Detection)    ✅
  ├── v0.2.3  Rules Engine Alpha+  (Export/Import + Interactive CLI)     ✅
  ├── v0.2.5  Auto-Promotion       (Memory → Rule Candidate Generation)  ✅
  ├── v0.2.6  Experience Learning   (Failure → Avoidance Rules)          ✅
  ├── v0.2.7  Q&A Refinement       (Multi-turn Rule Abstraction)         ✅
  ├── v0.2.8  Rules Engine Beta    (Context Engineering + Hardened)      ✅
  │
  ├── v0.3.0  GA Release           (Production Ready + Knowledge Adapter) ✅
  ├── v0.4.0  Enterprise           (Scopes + Skill + Merge + VS Code)     ✅
  └── v0.4.1  Core Loop Fix        (Auto Rule Suggestion + Security)      ✅
```

**Versioning Rules**:
- Third digit changes for incremental updates within a phase
- Second digit changes for GA milestones (API stability guarantee)
- No "v1.0.0 jump" — earn it through proven production usage

> **Note**: The v0.3.0–v0.4.1 versions listed above represent the project's development history. Current version is v0.2.4, including auto-backup, encrypted .carry files, concurrent safety, E2E tests, **PrefEval 83.0%** (200-sample, 3-condition canonical), state/event version chain, security hardening, preference injection optimization, context.py modularization, and consolidation scheduling. Next milestones: v0.3.0 (GA).

---

## Product Vision

### Three-Layer Identity Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    CarryMem Identity Layer                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Layer 3: Rules (HOW to act)        ← v0.2.x DONE       │
│  ┌──────────────────────────────────────────────────┐    │
│  │  "When X happens, do Y"                          │    │
│  │  • Manual rules (v0.2.1)                         │    │
│  │  • Auto-promoted from patterns (v0.2.5)          │    │
│  │  • Learned from failures (v0.2.6)                │    │
│  │  • Refined through dialogue (v0.2.7)             │    │
│  │  • Context-anchored injection (v0.2.8)           │    │
│  └──────────────────────────────────────────────────┘    │
│              ↑ reads from          ↑ injects into         │
│  Layer 2: Memory (WHO you are)     ← v0.3.0 STABLE       │
│  ┌──────────────────────────────────────────────────┐    │
│  │  "You prefer X, decided Y, corrected Z"          │    │
│  │  • 7 memory types + 4-tier hierarchy             │    │
│  │  • Cross-language semantic recall (FTS5)          │    │
│  │  • Session-aware storage + knowledge supersession (v0.1.7)    │    │
│  │  • Time reasoning + structured prompt injection (v0.1.7)      │    │
│  │  • 3050+ tests passing, 79%+ coverage           │    │
│  └──────────────────────────────────────────────────┘    │
│              ↑ reads from          ↑ injects into         │
│  Layer 1: Knowledge (WHAT you know) ← v0.3.0 PLANNED     │
│  ┌──────────────────────────────────────────────────┐    │
│  │  "Your Obsidian vault, your docs, your notes"    │    │
│  │  • Obsidian Markdown adapter (existing)          │    │
│  │  • Memory + Knowledge joint retrieval            │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Retrieval Priority: Rules(override) > Memory > Knowledge │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### The Key Distinction

| Layer | Answers | Form | Trigger | Example |
|-------|---------|------|---------|---------|
| **Memory** | "Who are you?" | Declarative | Passive (context-relevant) | "I prefer PostgreSQL" |
| **Rules** | "How do you act?" | Conditional → Action | Active (scene-matched) | "When choosing DB, use PostgreSQL" |
| **Knowledge** | "What do you know?" | Reference | On-demand (retrieved) | "PostgreSQL vs MySQL comparison" |

---

## Context Engineering Insights (NEW — v0.2.8)

### Lost-in-the-Middle Effect on Rule Injection

LLM attention follows a U-curve: **high at start and end, low in the middle** (10-40% recall drop). This directly impacts rule injection reliability.

**Current Problem** (v0.2.1-v0.2.7):
```
## Personal Rules (from CarryMem)
Rule A (relevance=0.92, override=true)   ← Start: high attention
Rule B (relevance=0.88, override=false)  ← Middle: attention collapse
Rule C (relevance=0.85, override=true)   ← Middle: MOST IMPORTANT rule ignored!
Rule D (relevance=0.80, avoid)           ← End: secondary attention
```

**v0.2.8 Solution**: Anchored layout mode
```
## Personal Rules (from CarryMem)

### Absolute Prohibitions (never violate)
- [forbid] Never cite competitor data without verification     ← HEAD ANCHOR

### Recommended
- [always] Confirm inventory by phone for Hamburg warehouse
- [avoid] Prefer domestic warehouses for cross-border transfers

### Mandatory Actions (never skip)
- [always] All external quotes must include validity period     ← TAIL ANCHOR
```

### Context Budget Monitoring

When rule injection exceeds 70% of context window, auto-compress:
- Priority: keep override=true rules, compress avoid rules to summaries
- Over threshold: one-line summaries per rule, no source attribution

### DDD Language View

CarryMem concepts map to DDD concepts, enabling enterprise architect dialogue:

| CarryMem | DDD | Relationship |
|----------|-----|-------------|
| trigger | Bounded Context | Scope definition |
| rule_type (forbid/avoid/always) | Aggregate Consistency Constraint | Invariant ≈ forbid, Guarantee ≈ always |
| override | Invariant | Cannot be overridden by higher priority |
| source_memories | Event Sourcing Chain | Rule traceable to originating experience |
| refine process | Ubiquitous Language Refinement | Specific → General abstraction |

Implementation: `style="ddd"` parameter in `format_rules_as_prompt()`, display-only, no storage change.

---

## Milestone Plan

### ✅ v0.2.0 (DONE)

See CHANGELOG.md for detailed history.

---

### ✅ v0.2.5 — Auto-Promotion (DONE)

**Implemented Features**:
- [x] PromotionPipeline: 5-stage pipeline (Collect→Detect→Generate→Queue→Confirm)
- [x] Audit trail: `promotion_audit` table with full action logging
- [x] CLI: `promote-rules`, `review-promotions`, `promotion-log`
- [x] Queue size limit (50), configurable expiry (7 days)
- [x] `_count_pending()` efficient COUNT query

---

### ✅ v0.2.6 — Experience Learning (DONE)

**Implemented Features**:
- [x] FailureExperienceExtractor: 5 signal types (mistake/regret/negative_outcome/lesson_learned/correction_from_failure)
- [x] Bilingual pattern matching (EN + ZH)
- [x] ExperienceRuleBridge: confirmation workflow with `experience_audit` table
- [x] Domain inference: 7 domains
- [x] CLI: `learn-experience`, `review-lessons`, `lesson-log`

---

### ✅ v0.2.7 — Q&A Refinement (DONE)

**Implemented Features**:
- [x] RuleRefiner: 4-phase refinement (Scope→Generality→Exception→Confirm)
- [x] Specificity analysis: detect project/tool/time-specific rules
- [x] RefinementSessionManager: session persistence + conversation tracking
- [x] CLI: `refine-rule`, `refinement-sessions`
- [x] Max 5 rounds, auto-forced confirm

---

### ✅ v0.2.8 — Rules Engine Beta (Context Engineering + Hardened)

**Theme**: Production hardening + Context engineering optimization
**LLM Dependency**: None (core features work without)

**P0 — Context Engineering (from optimization memo)**:
- [x] `format_rules_as_prompt()` anchored layout mode
  - Head anchor: override=true + forbid rules
  - Middle: normal rules by relevance
  - Tail anchor: override=true + always rules
- [x] `format_rules_as_prompt()` style="ddd" output
  - DDD terminology: "Personal Context → Invariant/Consistency/Soft Constraint"
  - Display-only, no storage layer change

**P1 — Production Hardening**:
- [x] Context budget monitoring (token-aware compression)
- [x] Test coverage ≥ 80% (current: 80.70%, up from 68.61%)
- [x] CLI coverage ≥ 70% (current: ~77%)
- [x] Security audit: review all input paths (InputValidator integrated into CLI/MCP/import)
- [x] API stability guarantee (no breaking changes in v0.3.x) — see API_STABILITY.md
- [x] `carrymem doctor` comprehensive health check (14 checks + JSON output + --fix)
- [x] Documentation complete (API_REFERENCE synchronized to v0.2.8)

**P2 — Quality Improvements**:
- [ ] source_memories confidence status (active/overridden/superseded)
- [ ] Rule effectiveness metrics (trigger count, user satisfaction)

---

### 🎉 v0.3.0 — GA Release (Production Ready) ✅ **DONE**

**Theme**: First production-ready release with Knowledge Adapter
**LLM Dependency**: Optional (core works without)

**P0 — Knowledge Adapter Enhancement**:
- [x] ObsidianAdapter CJK full-text search upgrade
  - Replace `unicode61` tokenizer with `trigram` for CJK character-level matching
  - Content truncation: 500 → configurable (default 2000 chars, full via `full_content=True`)
  - Auto-migration from `unicode61` → `trigram` on existing databases
- [x] Knowledge relevance scoring
  - Score based on: FTS5 rank (60%) + tag overlap (25%) + wiki-link proximity (15%)
  - `relevance_score` field in recall results
- [x] Knowledge + Rules + Memory three-layer retrieval orchestration
  - Retrieval priority: Rules(override) > Memory > Knowledge
  - `build_context()` unified budget allocation: Rules 30% / Memory 45% / Knowledge 25%
  - `build_system_prompt()` structured output: Rules → Memory → Knowledge
  - `recall_all()` now includes `rules` layer with `include_rules=True`

**P1 — Production Hardening (from v0.2.8 P2)**:
- [x] `trigger_count` activation — wire `increment_trigger_count()` into `RuleEngine.match()`
  - `RuleStorage.increment_trigger_count(rule_id)` for atomic DB update
  - `batch_increment_trigger_counts()` for multi-rule efficiency
  - Frequency bonus in matcher now functional
- [x] Rule effectiveness metrics
  - `engine.get_effectiveness_report()` — trigger stats, confidence distribution, override usage
  - Type breakdown, derivation sources, top-triggered/never-triggered lists
- [x] source_memories confidence status
  - `validate_source_memories(rule_id)` — check if source memories still exist
  - Status tracking: active / deleted / superseded
  - Auto-calculated confidence adjustment penalty

**P2 — API Stability & Governance**:
- [x] Promote Rules Engine API from Experimental → Stable
  - `RuleEngine` CRUD + match + inject: `@stable`
  - Promotion/Refinement/Experience: remain `@experimental`
- [x] TypedDict return types for Stable APIs (dict-compatible)
- [x] Community governance: CONTRIBUTING.md, issue templates, PR checklist

**Existing Foundation** (already working):
- ObsidianAdapter: read-only FTS5 index + search + wiki-link + frontmatter ✅
- `recall_all()`: memory + knowledge unified retrieval ✅
- `build_context()` / `build_system_prompt()`: knowledge injection ✅
- DevSquadAdapter: Protocol-based integration ✅
- API_STABILITY.md: Stable/Experimental/Internal tiers ✅

---

## v0.4.0 Enterprise Features — DONE ✅

### v0.4.0 — Enterprise Features

**Theme**: Multi-scope rules, portable Skill format, editor integration
**Prerequisite**: v0.3.0 GA release

**P0 — Rule Scope Dimension**:
- [x] Rule model: add `scope` field (`personal` / `company` / `negotiated`)
  - `RuleScope` enum: personal (user-created), company (org-mandated), negotiated (user-adapted from company)
  - Default: `personal` (backward-compatible)
  - Storage: new `scope` column in SQLite rules table
  - Migration: existing rules default to `personal`
- [x] Scope-aware matching and injection
  - `RuleEngine.match()` accepts `scopes` filter (default: all)
  - `RuleInjector` annotates output with scope labels
  - Priority: `company(override) > negotiated > personal` when conflicts arise
- [x] Scope-aware CRUD
  - `add_rule(scope="personal")` — default
  - `list_rules(scope="company")` — filter by scope
  - Company rules: immutable by non-admin users (enforced at adapter layer)

**P1 — Rule Skill Format**:
- [x] Skill manifest specification (`carrymem-skill-v1`)
  - Metadata: name, author, version, description, dependencies, scope
  - Structure: rules + templates + config in single JSON bundle
  - Signature: content hash for integrity verification
- [x] Skill CLI commands
  - `carrymem skill-pack <path>` — export rules as Skill bundle
  - `carrymem skill-install <path>` — import Skill with scope assignment
  - `carrymem skill-verify <path>` — verify Skill integrity
- [x] Skill export/import upgrade
  - Extend existing `export_rules()` / `import_rules()` to Skill format
  - Backward-compatible: `carrymem-rules-v1` still supported for import

**P2 — Rule Merge Protocol ("Customs Clearance")**:
- [x] Scope-aware merge engine
  - `RuleMergeEngine` with strategies: `company_overrides`, `negotiate`, `keep_both`
  - Conflict detection: company rule vs personal rule on same trigger
  - Auto-negotiation: personal rule adjusted to not violate company constraints
- [x] "Customs clearance" flow
  - When company rules enter personal space: review → adapt → confirm
  - `engine.review_incoming_rules(rules, scope="company")` — preview conflicts
  - `engine.accept_rules(rule_ids, merge_strategy="negotiate")` — accept with adaptation
- [x] Merge audit trail
  - All merge decisions logged with reason, timestamp, original values

**P3 — VS Code Extension (stretch goal)**:
- [x] Extension scaffold (TypeScript)
  - Webview rule editor panel
  - Sidebar: rule list with scope badges
  - Commands: add/edit/delete/toggle rule
- [x] Backend communication via CarryMem CLI
  - CarryMemClient: subprocess-based communication
  - All CRUD + match + effectiveness + skill operations
- [x] Inline rule suggestions
  - On command: match rules to current file type/context
  - QuickPick with matched rules and scores

**Existing Foundation** (already working):
- `export_rules()` / `import_rules()` with 3 conflict modes ✅
- Rule templates (10 predefined) ✅
- Memory namespace isolation (reusable pattern) ✅
- `validate_namespace()` (reusable for scope validation) ✅
- Rule conflict detector (detect-only, extensible) ✅
- MCP HTTP Server (reusable for VS Code backend) ✅

### v0.4.1 — Core Loop Fix (Product初心 Review)

**Theme**: Fix the broken core loop — memory→rule→injection pipeline
**Prerequisite**: v0.4.0 enterprise features

**P0 — Core Loop Repair** (product from unusable → usable):
- [x] `_auto_suggest_rules()` implementation — memory→rule candidate generation
  - PatternDetector + CandidateRuleGenerator integration
  - Trigger extraction from natural language (tech keyword detection)
  - Rule type inference from memory type (correction→avoid, decision→always)
- [x] MCP rule tools target fix — shared RuleEngine instance
  - Handlers init creates shared RuleEngine with correct db_path
  - Rule tools target changed from None to self._rule_engine
- [x] `get_system_prompt` auto-inject without context
  - No-context path lists all active rules and formats them
  - Global rules always injected into AI prompt
- [x] User management MCP tools: `my_rules`, `delete_rule`
- [x] Rule injection security filter — INJECTION_DANGER_PATTERNS regex
- [x] Natural conversation preference extraction tests (23 cases)
- [x] E2E user journey tests (conversation→store→rule→inject→verify)

**P1 — Experience Optimization** (product from usable → good):
- [x] Correction auto-updates old memories/rules (`_handle_correction`)
- [x] `update_rule` MCP tool
- [x] `my_profile` MCP tool — complete user identity view
- [x] `onboard` MCP tool — first-time user guidance (EN/ZH/JA)
- [x] Rule application feedback — `applied_rules` field in build_context
- [x] Rule conflict detection on add_rule — `_conflict_warnings`
- [x] FTS5 rank score optimization — `search_with_rank()` method
- [x] MCP config auto-inject settings — `CARRYMEM_AUTO_INJECT` env var

**P2 — Smart Enhancement** (product from good → smart):
- [x] Rule expiry mechanism — `expires_at` field + `is_expired()` method
- [x] CLI rule management enhancement — `--format table/compact/detail`
- [x] `carrymem doctor` enhancement — rules engine + auto-inject checks
- [x] Chinese tokenization optimization (jieba) — jieba segmentation with n-gram fallback
- [x] Conditional preference support — `condition` field for if-then rules
- [x] Implicit preference inference — `_detect_implicit_preferences()` from memory patterns

**MCP Tools** (27 tools):
- Core (3): classify_message, get_classification_schema, batch_classify
- Storage (3): classify_and_remember, recall_memories, forget_memory
- Knowledge (3): index_knowledge, recall_from_knowledge, recall_all
- Profile (2): declare_preference, get_memory_profile
- Prompt (2): get_system_prompt, summarize_and_store
- Consolidation (3): consolidate_memories, schedule_consolidation, stop_consolidation
- Rules (11): add_rule, list_rules, match_rules, inject_rules, my_rules, delete_rule, suggest_rules, promote_rules, update_rule, my_profile, onboard

### v0.1.7 — Memory Layer Enhancement (Intelligent Memory Layer) ✅

**Theme**: From retrieval system to intelligent memory layer
**LLM Dependency**: None (all features work without LLM)

**Phase 1: Session-Aware Storage + Knowledge Supersession**:
- [x] `classify_and_remember(session_id=...)` — session identifier for cross-session awareness
- [x] Auto-supersession — `superseded_at`/`supersedes` fields, contradiction detection, update markers
- [x] `recall_aggregated()` — aggregate memories by type across all sessions
- [x] `recall_timeline(topic)` — recall memories about a topic ordered by time
- [x] New filter keys: `session_id`, `created_before`, `include_superseded`, `_order_oldest`

**Phase 2: Time Reasoning + Context Rebuild**:
- [x] `_parse_time_expressions()` — extract time constraints from queries (zero LLM)
- [x] `_rebuild_context()` — extend FTS5 queries with related words from user profile
- [x] `_order_oldest` filter — support "first/earliest" queries

**Phase 3: Structured Prompt + Knowledge Updates**:
- [x] Priority labels: `[MANDATORY]`, `[IMPORTANT]`, `[OUTDATED]`
- [x] `_build_superseded_notes()` — knowledge update tracking
- [x] Structured prompt sections: Mandatory → Important → Context → Outdated → Knowledge Updates
- [x] `build_context()` safe access for `__new__()` created objects

**Benchmark Results (LongMemEval 100-question sample)**:
- temporal-reasoning: 0.110 → 0.127 (+15%)
- single-session-assistant: 0.196 → 0.200
- knowledge-update: 0.055 → 0.057
- Overall: 0.107 → 0.105 (stable, value in new capabilities)

**Next**: Phase 4 — Session Summary + Semantic Aggregation (requires LLM)

### v0.5.0 — Intelligence Enhancement (Partially Complete)
> **Status**: Partially complete — Consolidation Engine and PrefEval achieved in pre-reset cycle. Remaining items deferred to v0.6.0+.
- [x] Consolidation Engine (P0: dedup+decay, P1: pattern→rules, P2: semantic merge)
- [x] PrefEval 96.0% preference adherence (50 items, ICLR 2025 Oral)
- [x] 27 MCP tools (added consolidate_memories)

> **Note on PrefEval numbers**: Different sample sizes and seeds produce different results. The canonical result is **83.0%** (200 items, 3-condition comparison: CarryMem 83.0% > reminder 80.0% > zero-shot 71.5%), as documented in the README. Other figures (85.0%, 87.9%, 96.0%) reflect different evaluation configurations and should not be compared directly.
- [ ] Consolidation scheduled trigger (auto dedup+decay)
- [ ] Motive memory type (pending→activated→completed lifecycle)
- [ ] PrefEval evaluation standardization (reproducible scripts + report template)
- Vector-based semantic matching (optional embedding model)
- Rule recommendation engine
- Cross-user rule sharing (with anonymization)
- Ontology-based trigger matching

### ✅ v0.2.2 — PrefEval Violation Optimization + Version Chain

**Theme**: PrefEval optimization + state/event version chain + security hardening
**Principle**: #3 PrefEval focus + #1 Lightweight

**P0 — Violation Rate Optimization** (DONE):
- [x] Analyze PrefEval 200-sample violation cases
- [x] Fix coreference replacement text injection vulnerability (security)
- [x] Preference token budget 40%→60%, preventing preference truncation
- [x] PrefEval 200-sample: CarryMem **87.9%** (single-condition peak)
- [x] Update README PrefEval progress table (EN/CN/JP)
> *Historical note: Peak single-condition result. Canonical: **83.0%** (3-condition).*

**P0 — Version Chain** (DONE):
- [x] Add `memory_nature`(state/event) + `version_chain_id` + `version_number` fields
- [x] State memory: auto-supersede old version on write, maintain version chain
- [x] Event memory: no merge, full retention, no versioning
- [x] Query: state→latest version only (superseded filtered by default), event→chronological
- [x] Backward compatibility: __post_init__ auto-infer, SQLite migration v0.90 with backfill
- [x] 27 version chain tests all passing

**P1 — context.py Modularization** (DONE):
- [x] Split context.py (910 lines) into: selection.py, scope.py, format.py, prompt.py
- [x] Each module < 250 lines, original API preserved via re-export

### v0.2.0 — Auto-Maintenance + Evaluation Standardization ✅

**Theme**: Consolidation scheduling + reproducible PrefEval + non-technical user reach
**Principle**: #1 Lightweight — auto-maintenance reduces manual burden

**P0 — PrefEval Fair Benchmark** (DONE):
- [x] 200-sample, 3-condition comparison (zero-shot/reminder/carrymem)
- [x] CarryMem **85.0%** > reminder 83.0% > zero-shot 69.5% (seed=42)
- [x] SQLite "database is locked" fix (busy_timeout + _auto_supersede commit)
- [x] PrefEval script: force_type + no noise + include_question=True + max_tokens=500
> *Historical note: seed=42 fair comparison result. Canonical: **83.0%** (latest run).*

**P1 — Consolidation Scheduling** (DONE):
- [x] `schedule_consolidation(interval_hours=1)` method
- [x] CLI: `carrymem consolidate --schedule 1h`

**P2 — Non-Technical User Reach** (DONE):
- [x] README scenario entry points (EN/CN/JP)
- [x] `carrymem pack` / `carrymem unpack` CLI (gzip .carry format)
- [x] `carrymem setup-mcp --global` (one install, all agents share CarryMem)
- [x] `carrymem mcp` subcommand (stdio transport)
- [x] GitHub About/topics/description updated

**P3 — Technical Debt Cleanup** (DONE):
- [x] Unified path management (constants.py replaces hardcoded paths)
- [x] Empty except:pass → debug/warning logging (35+ locations)
- [x] pyproject.toml fail_under 55→75
- [x] README data conflict resolved
- [x] .gitignore updated (*.carry)

**Remaining**:
- [ ] Integration with APScheduler (optional dependency)
- [ ] McNemar statistical significance test

### v1.0.0 — Autonomous Identity
- Fully automatic rule learning
- Predictive rule suggestion
- Multi-agent coordination
- Identity portability standard

---

## Post-Beta Roadmap — Competitive Intelligence Absorption

> **Source**: DevSquad 4-role review (Architect + PM + Security + DevOps)
> **Date**: 2026-06-02 | **Reviewed Projects**: Lum1104/Understand-Anything (v2.7.3) + rtk-ai/rtk (v0.40.0)
> **Rule**: Beta frozen — no code changes until post-release. These items are recorded for v0.2.5+ planning.

### Analysis Summary

| Dimension | Understand-Anything | rtk | CarryMem Current |
|-----------|---------------------|-----|------------------|
| **Positioning** | Code → Knowledge Graph | Token-saving proxy | AI Memory Layer |
| **Languages** | 8 (EN/ZH-CN/ZH-TW/JA/KO/ES/TR/RU) | 7 (EN/FR/ZH/JA/KO/ES/PT) | 3 (EN/CN/JP) |
| **Platforms** | 14 (Plugin + install.sh) | 14 (Hook + Plugin) | 9 (MCP stdio) |
| **Tech Stack** | TypeScript + Tree-sitter + LLM | Rust (single binary) | Python + SQLite |
| **Key Differentiator** | Visual Dashboard + Guided Tour | `rtk gain` value metrics | Zero-LLM classification (88%) |

### ✅ Consensus: ABSORB (4/4 roles agreed)

#### P0-1: Multi-Language Expansion (KO + ZH-TW)

| Role | Verdict | Rationale |
|------|---------|-----------|
| Architect | ✅ Feasible (5/5) | i18n template exists, translation-only effort |
| PM | ✅ High Value (9/10) | Korean = Asia AI hub, ZH-TW = Taiwan/HK market |
| Security | ✅ Zero Risk | Documentation only, no code change |
| DevOps | ✅ Low Cost | MD files only, no CI impact |

**Target**: v0.2.5 (post-Beta patch) or v0.3.0
**Scope**: Add `README-KO.md` + `README-ZH-TW.md` + update language switcher in all READMEs

---

#### P1-1: `carrymem stats --value` (Value Perception Command)

**Inspired by**: rtk's `rtk gain` — real-time token savings analytics

| Role | Verdict | Rationale |
|------|---------|-----------|
| Architect | ✅ Reuse existing (4/5) | Extends `stats` command, adds value metrics |
| PM | ✅ ROI Driver (9/10) | Users who see value → retain 3x longer |
| Security | ✅ Low Risk | Read-only stats, no data exposure |
| DevOps | ✅ Zero Infra | No new dependencies |

**Proposed Output**:
```
$ carrymem stats --value
╭─────────────────────────────────────────╮
│ CarryMem Value Report                   │
├─────────────────────────────────────────┤
│ Memories Stored:        147             │
│ Rules Active:           23              │
│ Sessions Remembered:    12              │
│ Repetitions Avoided:    ~340 est.       │
│ Tokens Saved (est.):    ~17,000         │
│ Identity Coverage:      87%             │
│ Days Since First Use:   23              │
╰─────────────────────────────────────────╯
```

**Target**: v0.2.5

---

#### P1-2: `.carry` Team Sharing Workflow Enhancement

**Inspired by**: UA's "commit knowledge graph to Git" pattern

| Role | Verdict | Rationale |
|------|---------|-----------|
| Architect | ✅ Already Works (5/5) | `.carry` files are git-friendly by design |
| PM | ✅ Differentiator (8/10) | Competitors can't do encrypted portable memory |
| Security | ✅ AES-128 Protected | Encryption already verified |
| DevOps | ✅ No Change Needed | Just documentation enhancement |

**Action**: Add "Team Sharing" section to README / USER_GUIDE:
```bash
# Share your identity with teammates (encrypted):
carrymem pack --output team-identity.carry
git add team-identity.carry && git commit -m "share identity"

# Teammate imports:
carrymem unpack team-identity.carry
```

**Target**: v0.2.4 (documentation only, can ship with Beta)

---

### ⚠️ Consensus: CONDITIONAL ABSORB (needs further discussion)

#### P2-1: Web Dashboard (Optional Dependency)

**Inspired by**: UA's interactive knowledge graph dashboard

| Role | Verdict | Condition |
|------|---------|-----------|
| Architect | ⚠️ Feasible but heavy | Requires Streamlit/FastAPI as optional dep |
| PM | ⚠️ Nice-to-have | Visual users love it; CLI purists don't care |
| Security | ⚠️ New attack surface | Web server = new vuln vector |
| DevOps | ⚠️ Deployment complexity | Docker already solves this |

**Decision**: Defer to **v0.3.0 GA** as optional `carrymem[dashboard]` extra.
**Condition**: Must be opt-in (`pip install carrymem[dashboard]`), never auto-enabled.

---

#### P2-2: Git Post-Commit Auto-Consolidation Hook

**Inspired by**: UA's `--auto-update` post-commit hook

| Role | Verdict | Condition |
|------|---------|-----------|
| Architect | ⚠️ Simple implementation | `carrymem hook install --post-commit` wrapper |
| PM | ⚠️ Power user feature | Most Beta users won't use this |
| Security | ⚠️ Hook execution risk | Must validate hook script integrity |
| DevOps | ✅ Low complexity | Just a .git/hooks file template |

**Decision**: Defer to **v0.3.0**, implement as opt-in hook only.

---

### ❌ Consensus: DO NOT ABSORB (4/4 roles agreed)

| Feature | Source | Reason to Skip |
|---------|--------|----------------|
| **Rust rewrite** | rtk | Python ecosystem is our strength; SQLite/MCP integration is Python-native |
| **Tree-sitter integration** | UA | Out of scope — we do memory, not code analysis |
| **Karpathy Wiki parser** | UA | Niche feature; Obsidian adapter covers our knowledge use case |
| **Hook-based command rewriting** | rtk | MCP protocol is our integration layer; hooks are platform-specific |
| **Single binary distribution** | rtk | Docker image (Glama) already provides this; pip is our primary channel |
| **Persona-adaptive UI** | UA | We serve AI agents, not humans directly; rules engine is our "persona" system |

---

## Test Coverage Progress

| Version | Total Tests | Coverage | Key Addition |
|---------|-------------|----------|--------------|
| v0.3.0 (pre-reset) | 490 | 57.6% | Memory layer |
| v0.2.5 (pre-reset) | 746 | ~77% | +auto-promotion |
| v0.2.6 (pre-reset) | 793 | ~59% | +experience learning (new modules lower %) |
| v0.2.7 (pre-reset) | 884 | ~68% | +Q&A refinement + cleanup |
| v0.2.8 (pre-reset) | 1709 | ~81% | +Anchored injection +DDD view +security audit |
| v0.2.9 (pre-reset) | 1800+ | ~82% | +DevSquad integration adapter |
| v0.3.0 (pre-reset) | 1900+ | ~85% | +Knowledge CJK +relevance scoring |
| v0.4.0 (pre-reset) | 1814 | ~77% | +Rule Scopes +Skill Format +VS Code Extension |
| v0.4.1 (pre-reset) | 2056 | 79% | +Core Loop Fix +Auto Rule Suggestion +Security |
| **v0.2.4 (current)** | **3050+** | **79%+** | **+Recall Purity +Scope Injection +PrefEval **83.0%** +8-client MCP** |

---

## Security Strategy (Defense in Depth)

### Layer 1: Input Validation (v0.2.1 ✅)
- Prompt injection pattern detection (10+ patterns)
- SQL injection character blocking
- Template injection prevention
- HTML/XSS tag stripping
- Length limits (trigger: 200, action: 500)

### Layer 2: Usage Limits (v0.2.1 ✅)
- Global rule cap: max 3 trigger="*"
- Total rule cap: max 200
- Rate limiting: 20/hr, 50/day

### Layer 3: Auto-Promotion Safety (v0.2.5 ✅)
- Auto-promotion requires explicit user action
- All auto-generated rules start as `override=false`
- Unconfirmed candidates expire after 7 days
- Queue size limit (50 pending)

### Layer 4: Experience Learning Safety (v0.2.6 ✅)
- Duplicate memory detection (skip already-processed)
- Sanitizer validates all extracted triggers/actions
- Audit trail for all experience→rule actions

### Layer 5: Refinement Safety (v0.2.7 ✅)
- Max 5 rounds per session
- Session expiry (7 days)
- All refined rules go through sanitizer

### Layer 6: Context Engineering Safety (v0.2.8 ✅)
- Context budget monitoring prevents prompt overflow
- Anchored layout ensures critical rules are never lost-in-middle
- Compression strategy preserves override=true rules

### Layer 7: Knowledge Injection Safety (v0.3.0 PLANNED)
- Knowledge content length limits before injection
- Source vault path validation (no path traversal)
- Knowledge recall results sanitized through InputValidator

---

## Priority Matrix

| Feature | Impact | Effort | Priority | Version |
|---------|--------|--------|----------|---------|
| **Anchored layout mode** | **Critical** | **Low** | **P0** | **v0.2.8 ✅** |
| **DDD style output** | **High** | **Low** | **P0** | **v0.2.8 ✅** |
| **Context budget monitoring** | **High** | **Medium** | **P1** | **v0.2.8 ✅** |
| **Test coverage ≥ 80%** | **High** | **Medium** | **P1** | **v0.2.8 ✅** |
| **Obsidian CJK trigram search** | **High** | **Low** | **P0** | **v0.3.0** |
| **Knowledge relevance scoring** | **High** | **Medium** | **P0** | **v0.3.0** |
| **Three-layer retrieval orchestration** | **Critical** | **Medium** | **P0** | **v0.3.0** |
| **trigger_count activation** | **High** | **Low** | **P1** | **v0.3.0** |
| **Rule effectiveness metrics** | **Medium** | **Medium** | **P1** | **v0.3.0** |
| **source_memories confidence** | **Medium** | **Medium** | **P1** | **v0.3.0** |
| **Rules API Stable promotion** | **High** | **Low** | **P2** | **v0.3.0 ✅** |
| **TypedDict return types** | **Medium** | **Medium** | **P2** | **v0.3.0 ✅** |
| **Rule scope dimension** | **Critical** | **Medium** | **P0** | **v0.4.0** |
| **Scope-aware matching/injection** | **High** | **Medium** | **P0** | **v0.4.0** |
| **Skill manifest specification** | **High** | **Medium** | **P1** | **v0.4.0** |
| **Skill CLI commands** | **Medium** | **Medium** | **P1** | **v0.4.0** |
| **Rule merge protocol** | **High** | **High** | **P2** | **v0.4.0** |
| **VS Code extension** | **Medium** | **High** | **P3** | **v0.4.0** |
| **Ontology trigger matching** | **Medium** | **High** | **P3** | **v0.5.0** |
| **Community directory: mcp.directory ✅ + Glama ✅** | **High** | **Low** | **P1** | **v0.3.0** |
| **mcp-marketplace.io** | — | — | **Dropped** | Scanner rejects custom MCP impl (no SDK import) |
| **Smithery (requires .mcpb bundle or HTTP transport)** | **Medium** | **High** | **P2** | **v0.4.0** |
| **WorkBuddy/CodeBuddy internal MCP Market (requires Plugin format)** | **Medium** | **Medium** | **P2** | **v0.4.0** |
| **SSE/HTTP transport for MCP server** | **Critical** | **High** | **P2** | **v0.4.0** |
| **Cloud MCP Server** | **High** | **Very High** | **P2** | **v0.5.0** |

---

**Next Milestone**: v0.3.0 GA (General Availability)
**Status**: ✅ **v0.2.4 complete (3050+ tests, 79%+ coverage, Memory + Rules + Knowledge + Enterprise)**
