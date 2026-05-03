# CarryMem API Stability Policy

**Version**: 1.1
**Effective**: v0.1.5+
**Last Updated**: 2026-05-02

## 1. API Classification

CarryMem APIs are classified into three stability tiers:

| Tier | Label | Stability | Breaking Changes |
|------|-------|-----------|-----------------|
| **Stable** | `@stable` | Guaranteed stable within major version | Only in major version bumps |
| **Experimental** | `@experimental` | May change between minor versions | With deprecation notice |
| **Internal** | `@internal` | No stability guarantee | Any time without notice |

## 2. Stable API (v0.4.x guarantee)

The following public interfaces are **Stable** and will not have breaking changes within the v0.4.x series:

### 2.1 Core Python API (`memory_classification_engine`)

```python
# Stable classes
CarryMem                  # Main entry point
MemoryClassificationEngine  # Classification engine
MemoryEntry               # Input data class
StoredMemory              # Stored memory data class

# Stable methods on CarryMem
CarryMem.classify_and_remember(message, context=None) -> Dict
CarryMem.recall_memories(query=None, filters=None, limit=20) -> List[Dict]
CarryMem.forget_memory(storage_key) -> bool
CarryMem.declare(message, context=None) -> Dict
CarryMem.declare_preference(message, context=None) -> Dict  # Alias for declare()
CarryMem.get_stats() -> Dict
CarryMem.get_memory_profile() -> Dict
CarryMem.whoami() -> Dict
CarryMem.export_memories(output_path=None, format="json", namespace=None) -> Dict
CarryMem.import_memories(input_path=None, data=None, namespace=None, merge_strategy="skip_existing") -> Dict
CarryMem.build_context(context=None, max_memories=10, max_knowledge=5, max_rules=5, max_tokens=2000, language="en") -> Dict
CarryMem.build_system_prompt(context=None, max_memories=10, max_knowledge=5, max_rules=5, language="en") -> str
CarryMem.check_conflicts() -> List
CarryMem.check_quality(min_score=0.3) -> List
CarryMem.list_expired() -> List
CarryMem.close() -> None

# Stable - Rules Engine (promoted from Experimental in v0.3.0)
CarryMem.add_rule(trigger, action, rule_type="avoid", override=True, confidence=0.8, scope="personal") -> Rule
CarryMem.list_rules(status=None, rule_type=None, scope=None, limit=50) -> List[Rule]
CarryMem.match_rules(scene_description, limit=10, scopes=None) -> List[MatchResult]
CarryMem.edit_rule(rule_id, **kwargs) -> Rule
CarryMem.delete_rule(rule_id) -> bool
CarryMem.pause_rule(rule_id) -> Rule
CarryMem.resume_rule(rule_id) -> Rule
CarryMem.get_effectiveness_report() -> Dict
CarryMem.validate_source_memories(rule_id) -> Dict

# Stable constructors
CarryMem(storage="sqlite", db_path=None, namespace="default", knowledge_adapter=None)

# Stable exceptions
StorageNotConfiguredError
KnowledgeNotConfiguredError
ValidationError
```

### 2.2 CLI Commands

The following CLI commands and their primary flags are **Stable**:

```
carrymem add MESSAGE [--force] [--type TYPE] [--namespace NS] [--context JSON] [--db PATH]
carrymem list [--limit N] [--type TYPE] [--namespace NS] [--format FORMAT] [--db PATH]
carrymem search QUERY [--limit N] [--type TYPE] [--namespace NS] [--format FORMAT] [--db PATH]
carrymem show KEY [--json] [--db PATH]
carrymem edit KEY CONTENT [--db PATH]
carrymem forget KEY [--force] [--db PATH]
carrymem clean [--expired] [--quality SCORE] [--dry-run] [--force] [--db PATH]
carrymem export PATH [--db PATH]
carrymem import PATH [--merge STRATEGY] [--db PATH]
carrymem stats [--db PATH]
carrymem check [--conflicts] [--quality] [--expired] [--db PATH]
carrymem doctor [--fix] [--json] [--db PATH]
carrymem version
carrymem init [--db PATH]
carrymem setup-mcp --tool TOOL [--project PATH] [--force]
```

### 2.3 MCP Tools

The following MCP tool names and their input schemas are **Stable**:

```
classify_message       {message: str, context?: str}
get_classification_schema  {format?: "json"|"markdown"}
batch_classify         {messages: [{message: str, context?: str}]}
mce_status             {}
classify_and_remember  {message: str, context?: str}
recall_memories        {query?: str, filters?: object, limit?: int}
forget_memory          {memory_id: str}
declare_preference     {message: str}
get_memory_profile     {}
get_system_prompt      {context?: str, max_memories?: int, max_knowledge?: int, language?: "en"|"zh"|"ja"}
```

## 3. Experimental API

The following are **Experimental** and may change between minor versions with a deprecation notice:

```python
# Experimental - Rules Engine (advanced features, not yet Stable)
CarryMem.inject_rules(scene_description, format="structured", max_rules=10) -> str
CarryMem.suggest_rules(...) -> List
CarryMem.promote_rules(...) -> List
CarryMem.review_promotions(...) -> List
CarryMem.learn_experience(...) -> Dict
CarryMem.review_lessons(...) -> List
CarryMem.refine_rule(...) -> Rule
CarryMem.refinement_sessions(...) -> List

# Experimental - Skill Format
CarryMem.skill_pack(name, version="1.0.0", scope="personal", ...) -> Dict
CarryMem.skill_verify(data) -> Dict
CarryMem.skill_install(data, scope_override=None, mode="skip") -> Dict

# Experimental - Merge Protocol
CarryMem.review_incoming_rules(incoming, target_scope=None) -> Dict
CarryMem.accept_rules(incoming, strategy="negotiate", target_scope=None) -> Dict
MergeStrategy / MergeDecision / MergeConflict / MergeResult

# Experimental - Rule Scope types
RuleScope / VALID_RULE_SCOPES / SCOPE_PRIORITY

# Experimental - Advanced features
CarryMem.update_memory(storage_key, content) -> Dict
CarryMem.rollback_memory(storage_key, version) -> Dict
CarryMem.get_memory_history(storage_key) -> List
CarryMem.merge_memories() -> Dict
CarryMem.backup(backup_dir=None) -> Dict
CarryMem.restore_backup(backup_path) -> Dict
CarryMem.index_knowledge() -> Dict
CarryMem.recall_from_knowledge(query, filters=None, limit=20) -> List
CarryMem.recall_all(query, filters=None, limit=20, namespaces=None, include_rules=True) -> Dict

# Experimental - CLI Rules commands
carrymem add-rule / edit-rule / delete-rule / list-rules / ...
carrymem suggest-rules / promote-rules / review-promotions / ...
carrymem learn-experience / review-lessons / lesson-log / ...
carrymem refine-rule / refinement-sessions / ...
carrymem skill-pack / skill-install / skill-verify
```

## 4. Internal API

The following are **Internal** and should not be relied upon by external code:

- All modules under `memory_classification_engine.adapters.*` (except through CarryMem)
- All modules under `memory_classification_engine.rules.*` (except through CarryMem)
- All modules under `memory_classification_engine.security.*` (except InputValidator)
- All modules under `memory_classification_engine.utils.*`
- All private methods (prefixed with `_`)

### 4.1 DevSquad Integration Adapter (Experimental)

The `integration.devsquad` module is **Experimental** and provides Protocol-based integration for DevSquad:

```python
from memory_classification_engine.integration.devsquad import DevSquadAdapter

adapter = DevSquadAdapter(db_path="carrymem.db")
if adapter.is_available():
    rules = adapter.match_rules("Design REST API", "user1", role="architect")
```

Protocol definitions (`MemoryProvider`, `CarryMemAdapter`) are stable interfaces defined by DevSquad. The `DevSquadAdapter` implementation may change between minor versions.

## 5. Deprecation Policy

When an API needs to change:

1. **Minor version (0.x.y → 0.x+1.0)**: Deprecated APIs remain functional for at least 2 minor versions
2. **Deprecation process**:
   - Add `warnings.warn("...", DeprecationWarning, stacklevel=2)` to the deprecated API
   - Document in CHANGELOG under "Deprecated" section
   - Provide migration guide in docstring
3. **Removal process**:
   - After 2 minor versions, the deprecated API may be removed
   - Removal is documented in CHANGELOG under "Removed" section

## 6. Version Numbering

CarryMem follows Semantic Versioning (SemVer) with the following convention:

- **0.x.y**: Pre-GA development. Minor version bumps may include breaking changes with deprecation notice.
- **0.3.x**: API stability guarantee begins. No breaking changes to Stable APIs within 0.3.x.
- **1.0.0**: First GA release. Full SemVer compliance.

### Historical Note

Early development used various version numbering schemes. The current v0.1.5 is a version reset that consolidates all features with security hardening and quality improvements.

## 7. Conditional Imports

Optional dependencies that may not be available (e.g., `cryptography`, `pycld2`) are handled via conditional imports. When an optional dependency is missing:

- The corresponding feature is **disabled** (not crash)
- A clear error message is shown when the feature is attempted
- `None` sentinel values in `__init__.py` are being phased out in favor of lazy imports with clear error messages

## 8. Return Value Contracts

Stable API methods return `Dict[str, Any]` with documented key structures. Future versions may introduce TypedDict or dataclass return types, but dict compatibility will be maintained.

Key conventions:
- All return dicts include a `"success"` or `"error"` key for operation results
- Memory dicts always include `"storage_key"`, `"content"`, `"type"`, `"confidence"`, `"tier"`
- List-returning methods accept `limit` parameter (default 20, max 1000)
