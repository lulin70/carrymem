# CarryMem ユーザーガイド

## 目次

1. [Getting Started](#getting-started)
2. [Memory System](#memory-system)
3. [Rule Engine](#rule-engine)
4. [Rule Scopes](#rule-scopes)
5. [Skill Format](#skill-format)
6. [Merge Protocol](#merge-protocol)
7. [Memory Consolidation](#memory-consolidation)
8. [VS Code Extension](#vs-code-extension)
9. [CLI Reference](#cli-reference)

---

## はじめに

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("I prefer dark mode")
memories = cm.recall_memories("theme")
print(cm.build_system_prompt())
cm.close()
```

---

## Memory System

CarryMem auto-classifies your inputs into 7 memory types:

| Type | Example |
|------|---------|
| `user_preference` | "I prefer dark mode" |
| `correction` | "No, I meant Python 3.11" |
| `decision` | "Let's use React" |
| `fact_declaration` | "Python 3.12 is the runtime" |
| `relationship` | "Sarah is my manager" |
| `task_pattern` | "I always write tests first" |
| `sentiment_marker` | "This build is too slow" |

---

## Rule Engine

Rules are behavioral contracts: **when X happens, do Y**.

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# Create rules
engine.add_rule("database", "Always use SSL connections")
engine.add_rule("code review", "Check for SQL injection", rule_type="forbid")

# Match rules to current context
results = engine.match("setting up database connection")
for r in results:
    print(f"[{r.rule.rule_type}] {r.rule.trigger} → {r.rule.action}")

# Inject rules into AI context
injection = engine.inject("database design session", format="structured")
```

### Rule Types

| Type | Priority | Description |
|------|----------|-------------|
| `forbid` | Highest | Must never be done |
| `always` | High | Must always be followed |
| `avoid` | Medium | Should be avoided (default) |
| `prefer` | Low | Preferred approach |
| `format` | Low | Output format rules |

---

## Rule Scopes

Scopes control rule priority and visibility across organizational boundaries.

### Scope Hierarchy

```
company (priority 3) — Organization-mandated, cannot be overridden
  ↓
negotiated (priority 2) — Adapted from company rules
  ↓
personal (priority 1) — User-created preferences
```

### Usage

```python
# Company rule — highest priority
engine.add_rule("database", "Always use SSL", scope="company", override=True)

# Personal preference — lowest priority
engine.add_rule("database", "Prefer PostgreSQL", scope="personal")

# Scope-aware matching
results = engine.match("database", scopes=["company"])  # Only company rules

# Scope-aware listing
company_rules = engine.list_rules(scope="company")
```

### Security Boundary

**Company override rules cannot be overridden by personal rules.** This is a hard security boundary enforced by the merge protocol:

```python
# This will NEVER override a company override rule
engine.add_rule("database", "Skip SSL for dev", scope="personal", override=True)
# → In any conflict, company rule wins
```

---

## Skill Format

Skills are portable rule bundles with cryptographic integrity verification.

### Creating a Skill

```python
# Pack all active rules into a Skill bundle
bundle = engine.skill_pack(
    name="team-conventions",
    version="1.0.0",
    scope="company",
    author="team-lead",
    description="Team coding conventions",
    dependencies=["base-security-rules"],
    tags=["security", "database", "api"],
)

# Save to file
import json
with open("team-conventions.skill.json", "w") as f:
    json.dump(bundle, f, indent=2)
```

### Verifying a Skill

```python
# Verify integrity before installing
result = engine.skill_verify(bundle)
if result["valid"]:
    print(f"Skill '{result['name']}' is valid ({result['rule_count']} rules)")
else:
    print(f"INVALID: {result['reason']}")
```

### Installing a Skill

```python
# Install with default scope
result = engine.skill_install(bundle, mode="skip")

# Install as company scope
result = engine.skill_install(bundle, scope_override="company", mode="overwrite")

print(f"Installed: {result['installed']}, Skipped: {result['skipped']}")
```

### Conflict Modes

| Mode | Behavior |
|------|----------|
| `skip` | Skip rules that already exist (default) |
| `overwrite` | Replace existing rules with incoming |
| `rename` | Auto-rename conflicting rules |

### CLI Commands

```bash
carrymem skill-pack rules.json --name my-rules --scope company
carrymem skill-verify my-rules.skill.json
carrymem skill-install my-rules.skill.json --scope company --mode skip
```

---

## Merge Protocol

When rules from different sources conflict, the merge protocol resolves them.

### Preview Conflicts

```python
from carrymem.rules import review_incoming_rules

preview = engine.review_incoming_rules(
    incoming=new_rules,
    target_scope="personal",
)
print(f"Conflicts: {preview['conflict_count']}")
print(f"Clean: {preview['no_conflict_count']}")
```

### Apply Merge

```python
result = engine.accept_rules(
    incoming=new_rules,
    strategy="negotiate",
    target_scope="personal",
)
print(f"Accepted: {result['accepted_count']}")
print(f"Skipped: {result['skipped_count']}")
print(f"Replaced: {result['replaced_count']}")
```

### Merge Strategies

| Strategy | When to Use | Behavior |
|----------|-------------|----------|
| `company_overrides` | Strict org compliance | Higher scope always wins |
| `negotiate` | Collaborative teams | Conflicting rules adapted to "negotiated" scope |
| `keep_both` | Manual review needed | Both rules kept, user decides later |

---

## Memory Consolidation

時間の経過とともに、記憶ストアには重複、古いエントリ、低価値の記憶が蓄積されます。統合により記憶ストアをクリーンアップ・最適化します。

### 統合の実行

```bash
# 変更内容をプレビュー（安全、変更なし）
carrymem consolidate --dry-run

# 統合を実行
carrymem consolidate

# 重複排除+減衰のみ実行（パターン昇格と意味マージをスキップ）
carrymem consolidate --no-p1 --no-p2
```

### 3つのフェーズ

| フェーズ | 機能 | 実行タイミング |
|---------|------|--------------|
| **P0: 重複排除 + 減衰** | 重複を除去（Jaccard ≥0.85）、時間ベース減衰を適用 | 毎日または毎週 |
| **P1: パターン → ルール** | 繰り返しパターンを検出、レビュー用ルール候補を生成 | 毎週 |
| **P2: 意味マージ** | 関連記憶をクラスタリング、ホストLLMに統合をリクエスト | 毎月 |

### 減衰動作

記憶は時間とともに減衰します（アクセスされない場合）。嗜好は常に保持されます。

| 記憶タイプ | 半減期 |
|-----------|--------|
| 嗜好 | 270日 |
| 事実、決定、修正 | 90日 |
| 感情 | 45日 |

### ベストプラクティス

- 常に最初に `--dry-run` で変更をプレビュー
- 低使用時間帯に統合を実行
- P1ルール候補を承認前にレビュー
- 嗜好は減衰・重複排除されません — あなたの嗜好は永続的です

---

## VS Code Extension

### Installation

1. Open VS Code
2. Install from VSIX: `code --install-extension vscode-carrymem-0.2.1.vsix`
3. Or press F5 in the extension directory to run in debug mode

### Features

- **Rule Sidebar**: Tree view with scope badges (🛡️ company, 🔀 negotiated, 👤 personal)
- **Rule Editor**: Add/edit rules with trigger, action, type, scope, override
- **Effectiveness Report**: HTML panel with stats and scope breakdown
- **Skill Operations**: Pack and install via file dialogs

### Commands

| Command | Description |
|---------|-------------|
| `CarryMem: Refresh Rules` | Reload rule list |
| `CarryMem: Add Rule` | Create a new rule |
| `CarryMem: Edit Rule` | Edit selected rule |
| `CarryMem: Delete Rule` | Delete selected rule |
| `CarryMem: Toggle Rule` | Pause/resume rule |
| `CarryMem: Match Rules` | Match rules for current file |
| `CarryMem: Effectiveness Report` | Show stats panel |
| `CarryMem: Skill Pack` | Export rules as Skill |
| `CarryMem: Skill Install` | Install a Skill bundle |

---

## CLIリファレンス

### Memory Commands

```bash
carrymem add "content"           # Store a memory
carrymem list                     # List memories
carrymem search "query"           # Search memories
carrymem show <key>               # View memory details
carrymem edit <key> "new"         # Edit a memory
carrymem forget <key>             # Delete a memory
carrymem whoami                   # Identity portrait
carrymem stats                    # Statistics
carrymem check                    # Quality check
carrymem doctor                   # Diagnose installation
```

### Rule Commands

```bash
carrymem add-rule "action" --trigger "trigger" [--type avoid] [--soft]
carrymem list-rules [--status active] [--type avoid]
carrymem edit-rule <id> [--trigger "new"] [--action "new"]
carrymem delete-rule <id>
carrymem match-rules "scene description"
carrymem rules-stats
carrymem export-rules output.json
carrymem import-rules input.json
```

### Skill Commands

```bash
carrymem skill-pack <output> --name <name> [--scope company] [--author "name"]
carrymem skill-install <input> [--scope company] [--mode skip|overwrite|rename]
carrymem skill-verify <input>
```
