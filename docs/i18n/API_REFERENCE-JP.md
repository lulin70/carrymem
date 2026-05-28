# CarryMem API リファレンス

**バージョン**: v0.2.0
**日付**: 2026-05-13

---

## CarryMem Class

Main entry point for CarryMem.

### Constructor

```python
from carrymem import CarryMem

cm = CarryMem(
    storage="sqlite",           # "sqlite", "obsidian", StorageAdapter instance, or None
    db_path=None,               # Custom database path (default: ~/.carrymem/memories.db)
    knowledge_adapter=None,     # ObsidianAdapter for knowledge base
    namespace="default",        # Namespace for memory isolation
    config=None,                # Optional configuration dict
)
```

### Context Manager

```python
with CarryMem() as cm:
    cm.classify_and_remember("I prefer dark mode")
```

---

## Core Methods

### classify_and_remember()

Classify a message and store it if it's worth remembering.

```python
result = cm.classify_and_remember(
    message="I prefer dark mode",
    context=None,
    language=None,
    session_id=None,           # セッション識別子（クロスセッション認識用）
)
```

**Returns**:
```python
{
    "should_remember": True,
    "entries": [...],
    "stored": True,
    "storage_keys": ["cm_20260425_..."],
    "summary": {
        "total_entries": 1,
        "by_type": {"user_preference": 1},
        "avg_confidence": 0.95,
    }
}
```

### classify_message()

Classify a message without storing it.

```python
result = cm.classify_message(
    message="I prefer dark mode",
    context=None,
    language=None,
)
```

**Returns**: Same structure as `classify_and_remember()` but without storage.

### recall_memories()

Recall memories matching a query.

```python
memories = cm.recall_memories(
    query="database",
    filters=None,               # {"type": "user_preference", "tier": 2,
                                #  "session_id": "sess_...", "created_before": "2026-05-10T...",
                                #  "include_superseded": False, "_order_oldest": False}
    limit=20,                   # Max results (1-1000)
)
```

**Returns**: `List[Dict]` where each dict contains:
```python
{
    "id": "cm_...",
    "type": "user_preference",
    "content": "I prefer dark mode",
    "confidence": 0.95,
    "tier": 2,
    "created_at": "2026-04-25T...",
    "storage_key": "cm_...",
    ...
}
```

### recall_aggregated()

タイプ別に全セッションの記憶を集約して召回します。

```python
result = cm.recall_aggregated(
    memory_type=None,           # タイプでフィルタ（例: "user_preference"）
    limit_per_type=50,          # タイプごとの最大結果数
)
```

**戻り値**: `Dict[str, List[Dict]]`、キーは記憶タイプ：
```python
{
    "user_preference": [
        {"id": "cm_...", "content": "ダークモードが好き", "confidence": 0.95, ...},
        ...
    ],
    "decision": [...],
    ...
}
```

### recall_timeline()

トピックに関する記憶を時系列で召回し、知識の変遷を表示します。

```python
results = cm.recall_timeline(
    topic="database",           # 検索トピック
    limit=20,                   # 最大結果数
)
```

**戻り値**: `List[Dict]`、作成日時順（古い順）、置換済みの記憶を含む：
```python
[
    {"id": "cm_...", "content": "MySQLを使っている", "superseded_at": "2026-05-10T...", ...},
    {"id": "cm_...", "content": "PostgreSQLに切り替えた", "supersedes": "cm_...", ...},
]
```

### forget_memory()

Delete a specific memory.

```python
deleted = cm.forget_memory(memory_id="cm_20260425_...")
```

**Returns**: `bool` — True if the memory was found and deleted.

### `consolidate(dry_run=True, run_p1=True, run_p2=True)`

記憶統合を実行：類似記憶の重複排除、時間ベースの減衰適用、ルール昇格のためのパターン検出、意味統合リクエストの準備。

**パラメータ：**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `dry_run` | `bool` | `True` | True の場合、変更を加えずに実行内容を報告のみ |
| `run_p1` | `bool` | `True` | True の場合、P1 パターン認識とルール候補生成を実行 |
| `run_p2` | `bool` | `True` | True の場合、P2 意味統合（ホストLLM借用）を実行 |

**統合フェーズ：**

| フェーズ | 機能 | メカニズム |
|---------|------|-----------|
| P0 | 重複排除 + 減衰 | Jaccard 類似度（≥0.85）、指数半減期減衰 |
| P1 | パターン → ルール | PatternDetector → CandidateRuleGenerator → PromotionPipeline |
| P2 | 意味マージ | Jaccard クラスタリング（≥0.65）→ ホストLLM統合リクエスト |

**タイプ別減衰半減期：**

嗜好 270日（3.0x）、事実/決定/修正/関係/タスクパターン 90日（1.0x）、感情 45日（0.5x）、セッション要約 63日（0.7x）

### declare()

Actively declare a preference or fact (confidence=1.0).

```python
result = cm.declare(
    message="I prefer PostgreSQL over MySQL",
)
```

### declare_preference()

Alias for `declare()`.

```python
result = cm.declare_preference(message="I prefer PostgreSQL over MySQL")
```

### whoami()

Get AI identity portrait showing preferences, decisions, corrections.

```python
identity = cm.whoami()
```

**Returns**:
```python
{
    "identity": "known_user",       # "new_user" if no memories
    "preferences": ["I prefer dark mode", ...],
    "decisions": ["Use React for frontend", ...],
    "corrections": [...],
    "total_memories": 12,
}
```

### get_memory_profile()

Get a summary of stored memories.

```python
profile = cm.get_memory_profile()
```

**Returns**:
```python
{
    "summary": "AI remembers 12 things about you: 5 preferences, 3 corrections, 2 decisions",
    "total_memories": 12,
    "by_type": {"user_preference": 5, "correction": 3, ...},
    "highlights": {"user_preference": ["I prefer dark mode", ...], ...},
}
```

### get_stats()

Get storage statistics.

```python
stats = cm.get_stats()
```

**Returns**:
```python
{
    "total_count": 12,
    "by_type": {"user_preference": 5, ...},
    "by_tier": {"2": 8, "3": 4},
    "avg_confidence": 0.89,
}
```

### export_memories()

Export memories to a file.

```python
result = cm.export_memories(
    output_path="my_memories.json",
    format="json",                     # "json" or "markdown"
    namespace=None,
)
```

### import_memories()

Import memories from a file or dict. Imported content is validated through InputValidator.

```python
result = cm.import_memories(
    input_path="my_memories.json",     # OR data={"memories": [...]}
    merge_strategy="skip_existing",      # "skip_existing" or "overwrite"
    namespace=None,
)
```

### build_system_prompt()

Build a system prompt with relevant memories.

```python
prompt = cm.build_system_prompt(
    context=None,
    max_memories=10,
    max_knowledge=5,
    language="en",              # "en", "zh", "ja"
)
```

### build_context()

Build a context dict with memories and knowledge for prompt assembly.

```python
result = cm.build_context(
    context=None,
    max_memories=10,
    max_knowledge=5,
    max_tokens=2000,
    language="en",
)
```

**Returns**:
```python
{
    "system_prompt": "...",
    "memories": [...],
    "knowledge": [...],
    "total_count": 5,
}
```

### export_profile()

Export full identity profile to a file.

```python
result = cm.export_profile(
    output_path="my_profile.json",
)
```

---

## Advanced Methods

### update_memory()

Update the content of an existing memory (SQLiteAdapter only).

```python
result = cm.update_memory(
    storage_key="cm_20260425_...",
    content="Updated content",
)
```

### rollback_memory()

Roll back a memory to a previous version (SQLiteAdapter only).

```python
result = cm.rollback_memory(
    storage_key="cm_20260425_...",
    version=1,
)
```

### get_memory_history()

Get version history of a memory (SQLiteAdapter only).

```python
history = cm.get_memory_history(storage_key="cm_20260425_...")
```

### merge_memories()

Merge duplicate or similar memories.

```python
result = cm.merge_memories()
```

### check_conflicts()

Detect conflicting memories.

```python
conflicts = cm.check_conflicts()
```

**Returns**: `List[Dict]` — each conflict has `conflict_type`, `severity`, `memories`, `reason`.

### check_quality()

Find memories below a quality threshold.

```python
low_quality = cm.check_quality(min_score=0.3)
```

### list_expired()

List memories that have exceeded their TTL.

```python
expired = cm.list_expired()
```

### backup()

Create a database backup.

```python
result = cm.backup(backup_dir="/path/to/backups")
```

### restore_backup()

Restore from a backup file.

```python
result = cm.restore_backup(backup_path="/path/to/backup.db")
```

### list_backups()

List available backup files.

```python
backups = cm.list_backups(backup_dir="/path/to/backups")
```

### get_audit_log()

Get audit log of all operations.

```python
log = cm.get_audit_log()
```

### clear_cache()

Clear internal caches.

```python
cm.clear_cache()
```

---

## Knowledge Base Methods

### index_knowledge()

Index Obsidian vault for knowledge base search.

```python
result = cm.index_knowledge()
```

### recall_from_knowledge()

Search knowledge base (Obsidian vault).

```python
results = cm.recall_from_knowledge(
    query="Python design patterns",
    filters=None,
    limit=20,
)
```

### recall_all()

Search rules, memories, and knowledge base with three-layer orchestration.

```python
result = cm.recall_all(
    query="database",
    filters=None,
    limit=20,
    namespaces=None,
    include_rules=True,
)
```

**Returns**:
```python
{
    "rules": [
        {"rule_id": "...", "trigger": "...", "action": "...", "rule_type": "always", "override": True, "score": 0.95, "match_type": "exact"},
    ],
    "memories": [...],
    "knowledge": [...],
    "rule_count": 2,
    "memory_count": 3,
    "knowledge_count": 2,
    "total_count": 7,
    "priority": "rules > memory > knowledge",
}
```

---

## Rules Engine API

The Rules Engine provides a rule-based identity layer on top of memories.

### RuleEngine

```python
from carrymem.rules import RuleEngine

engine = RuleEngine(db_path="carrymem.db")
```

#### CRUD Operations

```python
rule = engine.add_rule(
    trigger="database selection",     # Scene description
    action="always use PostgreSQL",   # What to do
    rule_type="always",               # "always", "avoid", "forbid", "format", "prefer"
    override=True,                    # Cannot be overridden by other rules
    derived_from="manual",            # "manual", "promotion", "experience", "refinement"
)

rule = engine.get_rule(rule_id="rule_...")
rules = engine.list_rules(status="active", rule_type="avoid", limit=50)
rule = engine.update_rule(rule_id="rule_...", trigger="new trigger", action="new action")
deleted = engine.delete_rule(rule_id="rule_...")
rules = engine.search_rules(query="database", limit=20)
```

#### Matching and Injection

```python
matched = engine.match(
    scene_description="Design a REST API",
    limit=10,
)
# Returns List[MatchResult] sorted by relevance

prompt_text = engine.inject(
    scene_description="Design a REST API",
    format="structured",              # "structured", "compact", "json", "anchored", "ddd"
    max_rules=10,
    include_metadata=False,           # Include source_memories, metadata in output
    context_budget_tokens=None,       # Token budget for auto-compression (e.g. 2000)
)
# Returns formatted string for prompt injection
```

**Supported formats** (`VALID_FORMATS`):

| Format | Description |
|--------|-------------|
| `structured` | Markdown sections by rule type |
| `compact` | One-line per rule |
| `json` | JSON array of rule objects |
| `anchored` | Head/Middle/Tail layout (addresses Lost-in-the-Middle effect) |
| `ddd` | Domain-Driven Design terminology view |

**Anchored layout** (`format="anchored"`):

Optimizes rule placement for LLM attention U-curve (high at start/end, low in middle):

```
### Absolute Prohibitions (never violate)     ← Head anchor (override + forbid)
- [forbid] Never cite competitor data without verification

### Recommended                                ← Middle (normal rules by relevance)
- [always] Confirm inventory by phone
- [avoid] Prefer domestic warehouses

### Mandatory Actions (never skip)             ← Tail anchor (override + always)
- [always] All external quotes must include validity period
```

**DDD view** (`format="ddd"`):

Maps CarryMem concepts to Domain-Driven Design terminology:

| CarryMem | DDD Term |
|----------|----------|
| `forbid` | Invariant |
| `always` | Consistency Guarantee |
| `avoid`/`prefer`/`format` | Soft Constraint |
| `trigger` | Bounded Context |
| `override` | Invariant Flag |
| `source_memories` | Event Sourcing Chain |

#### Context Budget

```python
from carrymem.rules.injector import ContextBudget

budget = ContextBudget(budget_tokens=2000)

token_count = budget.estimate_tokens("Some text with rules")
# Heuristic: CJK ~2 chars/token, English ~4 chars/token

should = budget.should_compress("Long rules text...")
# Returns True when usage exceeds 70% of budget

compressed = budget.compress_rules(matches, budget_tokens=2000)
# Keeps override=True rules, trims soft rules to fit budget
```

#### Context Usage Estimation

```python
usage = engine.injector.estimate_context_usage(
    scene_description="Design a REST API",
    format="anchored",
    max_rules=10,
    budget_tokens=2000,
)
# Returns:
# {
#     "total_rules": 8,
#     "estimated_tokens": 1450,
#     "budget_tokens": 2000,
#     "usage_percent": 72.5,
#     "needs_compression": True,
# }
```

#### Combined Injection

```python
full_context = engine.injector.inject_with_memories(
    scene_description="Design a REST API",
    memories_text="User prefers PostgreSQL over MySQL...",
    format="anchored",
    context_budget_tokens=2000,
)
# Returns merged rules + memories context paragraph
```

#### Statistics and Health

```python
stats = engine.get_stats()
count = engine.count_rules(status="active")
conflicts = engine.check_conflicts(new_rule=None)
health = engine.check_health()
```

#### Export and Import

```python
data = engine.export_rules(status="active")
result = engine.import_rules(data={"rules": [...]}, mode="skip")  # "skip", "overwrite", "rename"
```

#### Promotion Pipeline

```python
candidates = engine.suggest_rules(
    memories=[...],
    memory_type="user_preference",
    max_candidates=10,
)

result = engine.run_promotion(
    memories=[...],
    auto_accept=False,
)

pending = engine.list_pending_promotions(limit=20)
rule_id = engine.accept_promotion(audit_id="audit_...", note="Looks good")
engine.reject_promotion(audit_id="audit_...", note="Not applicable")
log = engine.get_promotion_log(limit=50)
stats = engine.get_promotion_stats()
```

#### Failure Experience Learning

```python
result = engine.extract_failure_lessons(
    memories=[...],
    memory_type="correction",
)

pending = engine.list_pending_lessons(limit=20)
rule_id = engine.accept_lesson(
    audit_id="audit_...",
    trigger_override="custom trigger",
    action_override="custom action",
)
engine.reject_lesson(audit_id="audit_...")
log = engine.get_lesson_log(limit=50)
stats = engine.get_lesson_stats()
```

#### Rule Refinement (Multi-turn Q&A)

```python
session = engine.start_refinement(
    trigger="database selection",
    action="avoid MongoDB",
    rule_type="avoid",
)

session = engine.answer_refinement(
    session_id=session["session_id"],
    answer="Yes, all document databases",
    selected_option="A",
)

result = engine.confirm_refinement(session_id=session["session_id"])
engine.cancel_refinement(session_id=session["session_id"])

sessions = engine.list_refinement_sessions(limit=20)
detail = engine.get_refinement_detail(session_id=session["session_id"])
stats = engine.get_refinement_stats()
```

#### Effectiveness Report

```python
report = engine.get_effectiveness_report()
# Returns:
# {
#     "total_rules": 25,
#     "active": 20,
#     "paused": 3,
#     "deprecated": 2,
#     "triggered": 15,
#     "never_triggered": 5,
#     "trigger_rate": 0.75,
#     "override_rules": 8,
#     "soft_rules": 12,
#     "type_breakdown": {"always": 6, "avoid": 8, "forbid": 4, "prefer": 2},
#     "type_trigger_totals": {"always": 45, "avoid": 12, "forbid": 30, "prefer": 3},
#     "confidence_distribution": {"high": 14, "medium": 4, "low": 2},
#     "top_triggered": [...],
#     "never_triggered_sample": [...],
#     "derivation_sources": {"manual": 15, "auto_promotion": 5, "failure_lesson": 3, ...},
# }
```

#### Source Memories Validation

```python
validation = engine.validate_source_memories("rule_abc123")
# Returns:
# {
#     "rule_id": "rule_abc123",
#     "source_memories": [
#         {"source_memory_id": "mem_001", "status": "active"},
#         {"source_memory_id": "mem_002", "status": "deleted"},
#         {"source_memory_id": "mem_003", "status": "superseded"},
#     ],
#     "total": 3,
#     "active": 1,
#     "deleted": 1,
#     "superseded": 1,
#     "confidence_adjustment": -0.15,  # -0.10 per deleted, -0.05 per superseded
# }
```

---

## DevSquad Integration Adapter

Provides Protocol-based integration for DevSquad multi-agent orchestration.

```python
from carrymem.integration.devsquad import DevSquadAdapter

adapter = DevSquadAdapter(db_path="carrymem.db", namespace="default")
```

### MemoryProvider Protocol

```python
if adapter.is_available():
    rules = adapter.get_rules("user1", context={"task": "design API", "role": "architect"})
    adapter.add_rule("user1", "Always use SSL", metadata={"trigger": "security", "rule_type": "always"})
    adapter.update_rule("user1", "rule_...", "Updated action")
    adapter.delete_rule("user1", "rule_...")
    stats = adapter.get_stats()
```

### CarryMemAdapter Protocol

```python
matched = adapter.match_rules(
    task_description="Design REST API",
    user_id="user1",
    role="architect",
    max_rules=5,
)
# Returns List[Dict] with rule_id, trigger, action, rule_type, override, relevance_score

prompt = adapter.format_rules_as_prompt(matched)
# Returns Markdown string with Mandatory Rules and Guidelines sections

exp_id = adapter.log_experience(
    user_id="user1",
    role="architect",
    task="Design API",
    rules_applied=["rule_1", "rule_2"],
    outcome="Success",
    user_feedback="Rules were helpful",
)
```

### Rule Type Mapping

| DevSquad | CarryMem | Semantic |
|----------|----------|----------|
| `forbid` | `forbid` | Must not do |
| `avoid` | `avoid` | Should not do |
| `always` | `always` | Must do |

### Graceful Degradation

When `is_available()` returns `False`, all methods return safe defaults:
- `get_rules()` → `[]`
- `match_rules()` → `[]`
- `format_rules_as_prompt()` → `""`
- `add_rule()`, `update_rule()`, `delete_rule()` → no-op
- `get_stats()` → `{"available": False, "total_rules": 0}`
- `log_experience()` → `""`

---

## Security Module

### InputValidator

Validates all external inputs for injection attacks.

```python
from carrymem.security import InputValidator, validate_content, validate_query

validator = InputValidator(strict_mode=False)

content = validator.validate_content("I prefer dark mode", field_name="message")
query = validator.validate_query("database")
namespace = validator.validate_namespace("work")
path = validator.validate_path("/path/to/file", must_exist=True)
memory_type = validator.validate_memory_type("user_preference")
confidence = validator.validate_confidence(0.9)
limit = validator.validate_limit(20)
filters = validator.validate_filters({"type": "user_preference"})
```

Detection patterns:
- SQL injection: `DROP TABLE`, `UNION SELECT`, `1=1`, etc.
- XSS: `<script>`, `javascript:`, `on\w+=`, etc.
- Command injection: `$()`, backticks, `rm/chmod/wget/curl`
- Path traversal: `../`, `/etc/`, `/proc/`, etc.

### AuditLogger

Records all operations for audit trail.

```python
from carrymem.security.audit import AuditLogger

logger = AuditLogger(connection_factory=lambda: sqlite3.connect(db_path), namespace="default")
logger.log_operation(
    operation="remember",
    namespace="default",
    storage_key="cm_...",
    success=True,
    details={"source": "cli"},
    source="api",
)
results = logger.query(operation="remember", namespace="default", limit=50)
stats = logger.get_stats()
```

### MemoryEncryption

Encrypts stored data at rest.

```python
from carrymem.security.encryption import MemoryEncryption, NoEncryption

encryptor = MemoryEncryption(key_path="~/.carrymem/.key")
encrypted = encryptor.encrypt("sensitive data")
decrypted = encryptor.decrypt(encrypted)

no_encrypt = NoEncryption()
assert no_encrypt.encrypt("data") == "data"
```

---

## Exceptions

```python
from carrymem import (
    StorageNotConfiguredError,
    KnowledgeNotConfiguredError,
    ValidationError,
)

try:
    cm = CarryMem(storage=None)
    cm.recall_memories(query="test")
except StorageNotConfiguredError:
    print("Storage not configured")
```

---

## CLIリファレンス

### carrymem doctor

Comprehensive health check with 14 diagnostic items.

```bash
carrymem doctor                    # Run all checks
carrymem doctor --fix              # Auto-fix issues (create dirs, init DB)
carrymem doctor --json             # Structured JSON output
carrymem doctor --db /path/to/db   # Custom database path
```

**Check items**:

| # | Check | Description |
|---|-------|-------------|
| 1 | `python_version` | Python >= 3.9 |
| 2 | `carrymem_import` | Module import succeeds |
| 3 | `config_dir` | `~/.carrymem` directory exists |
| 4 | `database_file` | Database file exists and has content |
| 5 | `db_integrity` | SQLite PRAGMA integrity_check |
| 6 | `db_permissions` | Database file write permissions |
| 7 | `disk_space` | Sufficient disk space remaining |
| 8 | `db_lock` | No stale database locks |
| 9 | `write_permissions` | Config directory writable |
| 10 | `optional_deps` | Optional dependencies available |
| 11 | `fts5` | SQLite FTS5 full-text search support |
| 12 | `security` | InputValidator security module |
| 13 | `mcp_configs` | MCP configuration files detected |
| 14 | `memory_count` | Memory entry count |

**JSON output example**:

```json
{
  "version": "0.2.2",
  "checks_passed": 13,
  "checks_total": 14,
  "issues": ["disk_space: Low disk space (< 100MB)"],
  "checks": [
    {"name": "python_version", "status": "ok", "message": "Python 3.11.5"},
    {"name": "disk_space", "status": "warn", "message": "Low disk space (< 100MB)"}
  ]
}
```

### carrymem match-rules

Match rules against a scene description.

```bash
carrymem match-rules "Design REST API"                  # Default structured format
carrymem match-rules "Design REST API" --format anchored # Anchored layout
carrymem match-rules "Design REST API" --format ddd      # DDD terminology view
carrymem match-rules "Design REST API" --context-budget 2000  # Token-aware compression
```

---

## Storage Adapters

### SQLiteAdapter (Default)

```python
from carrymem import SQLiteAdapter

adapter = SQLiteAdapter(
    db_path=None,
    namespace="default",
    enable_semantic_recall=True,
    enable_cache=True,
)
```

### ObsidianAdapter

Read-only adapter for Obsidian vault full-text search.

```python
from carrymem import ObsidianAdapter

adapter = ObsidianAdapter(
    vault_path="/path/to/vault",
    db_path=None,
    content_truncate=2000,     # Max content chars in results (default 2000, was 500)
)

stats = adapter.index_vault()          # Incremental index: {total_files, new, updated, skipped}
results = adapter.recall("query")      # FTS5 trigram search (CJK-supported)
results = adapter.recall("查询", full_content=True)  # Full content without truncation
tags = adapter.get_tags()              # Tag frequency map
linked = adapter.get_linked_notes("API Design")  # Wiki-link back-references
```

**Relevance scoring**: Each recall result includes `relevance_score` (0.0-1.0):
- FTS5 rank: 60% weight
- Tag overlap: 25% weight
- Wiki-link proximity: 15% weight

### JSONAdapter

```python
from carrymem import JSONAdapter

adapter = JSONAdapter(
    file_path="/path/to/memories.json",
)
```

---

## Memory Types

| Type | Description | Default Tier |
|------|-------------|-------------|
| `user_preference` | Stated preferences | 2 (90 days) |
| `correction` | Corrections to AI | 2 (90 days) |
| `fact_declaration` | Facts about user | 3 (365 days) |
| `decision` | Made decisions | 3 (365 days) |
| `relationship` | Social/context info | 2 (90 days) |
| `task_pattern` | Work patterns | 2 (90 days) |
| `sentiment_marker` | 感情反応 | 1 (24 hours) |

## ナレッジライフサイクル

### 自動置換（Auto-Supersession）

新しい記憶が既存の記憶と矛盾または更新する場合、旧記憶は自動的に置換済みとしてマークされます：

- **トリガー**: Jaccard 類似度 ≥ 0.25 + 矛盾検出または更新マーカー
- **矛盾ペア**: like/dislike、prefer/avoid、love/hate、enabled/disabled 等
- **更新マーカー**: "now"、"currently"、"switched"、"changed"、"no longer"、"instead" 等
- **安全機構**: アシスタントメッセージと分類プレフィックスは置換対象外

### 記憶優先度ラベル

システムプロンプト構築時、記憶に優先度ラベルが付与されます：

| ラベル | 条件 | 意味 |
|--------|------|------|
| `[MANDATORY]` | type=correction または decision | 必須遵守、無視不可 |
| `[IMPORTANT]` | type=user_preference + confidence ≥ 0.8 | 高信頼度の嗜好 |
| `[OUTDATED]` | superseded_at が null でない | 置換済み、参考用 |

### 時間表現パース

クエリに含まれる時間表現が自動的にパースされます：

| 表現 | 解釈 |
|------|------|
| recently、lately、just | 過去7日間 |
| this week、past week | 過去7日間 |
| this month、past month | 過去30日間 |
| today、yesterday | 過去2日間 |
| first、initial、earliest | 古い順でソート |
| N days/weeks/months ago | 日付範囲を計算 |

## Storage Tiers

| Tier | Name | Default TTL |
|------|------|-------------|
| 1 | Sensory | 24 hours |
| 2 | Procedural | 90 days |
| 3 | Episodic | 365 days |
| 4 | Semantic | Permanent |

## Rule Types

| Type | Description | Priority |
|------|-------------|----------|
| `always` | Must always be followed | High |
| `avoid` | Should be avoided | Medium |
| `forbid` | Must never be done | Highest |
| `format` | Output format rules | Low |
| `prefer` | Preferred approach | Low |

## Rule Scopes

| Scope | Description | Priority |
|-------|-------------|----------|
| `personal` | User-created rules | 1 (lowest) |
| `negotiated` | User-adapted from company rules | 2 |
| `company` | Organization-mandated rules | 3 (highest) |

When rules from different scopes conflict, higher-priority scope wins. Company rules with `override=True` cannot be overridden by personal rules.

```python
# Create a company-mandated rule
engine.add_rule("database", "Always use SSL", scope="company", override=True)

# Create a personal preference
engine.add_rule("database", "Prefer PostgreSQL", scope="personal")

# Match only company rules
results = engine.match("database design", scopes=["company"])

# List all company rules
rules = engine.list_rules(scope="company")
```

## Skill Format API

### `skill_pack(name, version, scope, ...)`

Export rules as a portable Skill bundle with SHA-256 signature.

```python
from carrymem.rules import skill_pack, skill_verify, skill_install

# Pack all active rules into a Skill bundle
bundle = engine.skill_pack(
    name="my-team-conventions",
    version="1.0.0",
    scope="company",
    author="team-lead",
    description="Team coding conventions",
)

# Save to file
import json
with open("my-team-conventions.skill.json", "w") as f:
    json.dump(bundle, f, indent=2)
```

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | required | Skill bundle name |
| `version` | str | "1.0.0" | Semantic version |
| `scope` | str | "personal" | Default scope for rules |
| `author` | str | "" | Author identifier |
| `description` | str | "" | Human-readable description |
| `dependencies` | List[str] | [] | Required Skill names |
| `tags` | List[str] | [] | Searchable tags |
| `status` | str | "active" | Filter rules by status |
| `config` | dict | {} | Skill-specific configuration |

**Returns**: `dict` with format `carrymem-skill-v1`, including manifest, rules, and SHA-256 signature.

### `skill_verify(data)`

Verify a Skill bundle's integrity by checking its SHA-256 signature.

```python
result = engine.skill_verify(bundle)
# {"valid": True, "name": "my-team-conventions", "rule_count": 15, "algorithm": "sha256"}
```

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | dict | required | Skill bundle dictionary |

**Returns**: `dict` with `valid`, `name`, `rule_count`, `algorithm`, and `reason` (if invalid).

### `skill_install(data, scope_override, mode)`

Install a Skill bundle into the rule storage with conflict resolution.

```python
# Install with default scope
result = engine.skill_install(bundle, mode="skip")

# Install as company scope
result = engine.skill_install(bundle, scope_override="company", mode="overwrite")

# Result: {"installed": 12, "skipped": 3, "overwritten": 0, "errors": [], "scope": "company"}
```

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | dict | required | Skill bundle dictionary |
| `scope_override` | str | None | Override Skill's default scope |
| `mode` | str | "skip" | Conflict mode: skip/overwrite/rename |

**Returns**: `dict` with `installed`, `skipped`, `overwritten`, `errors`, `skill_name`, `scope`.

## マージプロトコルAPI

### `review_incoming_rules(incoming, existing, target_scope)`

Preview merge conflicts without modifying any data.

```python
from carrymem.rules import review_incoming_rules

preview = engine.review_incoming_rules(
    incoming=new_rules,
    target_scope="personal",
)
# {"conflict_count": 2, "no_conflict_count": 8, "conflicts": [...], "strategies": {...}}
```

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `incoming` | List[Rule] | required | Rules to merge in |
| `existing` | List[Rule] | required | Current rules |
| `target_scope` | str | None | Apply this scope to incoming rules |

**Returns**: `dict` with `conflict_count`, `no_conflict_count`, `conflicts`, and `strategies` preview.

### `accept_rules(incoming, strategy, target_scope)`

Apply merge strategy and store accepted rules. Replaced rules are automatically deleted.

```python
result = engine.accept_rules(
    incoming=new_rules,
    strategy="negotiate",
    target_scope="personal",
)
# MergeResult with accepted, skipped, modified, replaced_ids, audit_entries
```

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `incoming` | List[Rule] | required | Rules to merge in |
| `strategy` | str | "negotiate" | MergeStrategy: company_overrides/negotiate/keep_both |
| `target_scope` | str | None | Apply this scope to incoming rules |

**Merge Strategies**:
| Strategy | Description |
|----------|-------------|
| `company_overrides` | Higher scope always wins; same scope favors incoming |
| `negotiate` | Conflicting rules adapted to "negotiated" scope with override=False |
| `keep_both` | Both rules kept; user should review manually |

## API Stability Tiers

See [API_STABILITY.md](../API_STABILITY.md) for full details.

| Tier | Label | Breaking Changes |
|------|-------|-----------------|
| Stable | `@stable` | Only in major version bumps |
| Experimental | `@experimental` | With deprecation notice |
| Internal | `@internal` | Any time without notice |

## TypedDict Return Types

All Stable API return types have corresponding TypedDict definitions for type checking:

```python
from carrymem import (
    RuleDict,
    MatchResultDict,
    EffectivenessReportDict,
    SourceMemoryValidationDict,
    KnowledgeNoteDict,
    RecallAllResultDict,
    BuildContextResultDict,
)
```

| TypedDict | Used By |
|-----------|---------|
| `RuleDict` | `add_rule()`, `list_rules()`, `edit_rule()` |
| `MatchResultDict` | `match_rules()` |
| `EffectivenessReportDict` | `get_effectiveness_report()` |
| `SourceMemoryValidationDict` | `validate_source_memories()` |
| `KnowledgeNoteDict` | `recall_from_knowledge()` |
| `RecallAllResultDict` | `recall_all()` |
| `BuildContextResultDict` | `build_context()` |

All TypedDicts are dict-compatible — existing code using `dict` continues to work without changes.
