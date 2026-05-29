# CarryMem User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Memory System](#memory-system)
3. [Rule Engine](#rule-engine)
4. [Rule Scopes](#rule-scopes)
5. [Skill Format](#skill-format)
6. [Merge Protocol](#merge-protocol)
7. [Memory Consolidation](#memory-consolidation)
8. [Auto-Backup](#auto-backup)
9. [Pack/Unpack with Encryption](#packunpack-with-encryption)
10. [USB Carry Scenario](#usb-carry-scenario)
11. [VS Code Extension](#vs-code-extension)
12. [CLI Reference](#cli-reference)

---

## Getting Started

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

Over time, your memory store accumulates duplicates, outdated entries, and low-value memories. Consolidation cleans up and optimizes your memory store.

### Running Consolidation

```bash
# Preview what consolidation would do (safe, no changes)
carrymem consolidate --dry-run

# Execute consolidation
carrymem consolidate

# Run only dedup + decay (skip pattern promotion and semantic merge)
carrymem consolidate --no-p1 --no-p2
```

### Three Phases

| Phase | What It Does | When to Use |
|-------|-------------|-------------|
| **P0: Dedup + Decay** | Removes duplicates (Jaccard ≥0.85), applies time-based decay | Run daily or weekly |
| **P1: Pattern → Rules** | Detects repeated patterns, generates rule candidates for your review | Run weekly |
| **P2: Semantic Merge** | Clusters related memories, requests host LLM to consolidate | Run monthly |

### Decay Behavior

Memories fade over time unless accessed. Preferences are always preserved.

| Memory Type | Half-Life |
|-------------|-----------|
| Preferences | 270 days |
| Facts, Decisions, Corrections | 90 days |
| Sentiments | 45 days |

### Best Practices

- Always run with `--dry-run` first to preview changes
- Run consolidation during low-usage periods
- Review P1 rule candidates before accepting
- Preferences are never decayed or deduplicated — your preferences are permanent

---

## Auto-Backup

CarryMem automatically backs up your database to protect against data loss.

### How Auto-Backup Works

- **Trigger**: Every 20 write operations (classify_and_remember, update, forget, etc.)
- **Mechanism**: SQLite `VACUUM INTO` — creates a consistent snapshot without stopping your workflow
- **Retention**: Up to 5 backup files retained (oldest automatically removed)
- **Location**: `~/.carrymem/backups/`

### Manual Backup

```bash
# Create a backup immediately
carrymem backup

# List all available backups
carrymem backup --list

# Restore from a specific backup
carrymem backup --restore memories_backup_20260527_120000.db
```

### Checking Backup Status

```bash
carrymem doctor
```

The `doctor` command now checks:
- Backup directory exists and is accessible
- Number of backup files
- Last backup timestamp

### Best Practices

- Auto-backup is enabled by default — no configuration needed
- Run `carrymem backup` before major operations (bulk import, consolidation)
- Use `carrymem backup --list` to verify backups exist before relying on them
- Restore replaces the current database — make sure you have a recent backup first

---

## Pack/Unpack with Encryption

CarryMem's `.carry` file format lets you pack all your memories into a single portable file, optionally encrypted with a password.

### Pack (Export to .carry file)

```bash
# Pack all memories into a .carry file
carrymem pack -o my_memories.carry

# Pack with password encryption
carrymem pack -o my_memories.carry --encrypt
```

When using `--encrypt`, you will be prompted for a password (minimum 4 characters). The password is used to derive an encryption key via PBKDF2-HMAC-SHA256 (100,000 iterations), and the .carry file is encrypted using MemoryEncryption (AES-128 Fernet).

### Unpack (Import from .carry file)

```bash
# Unpack a .carry file (auto-detects encryption)
carrymem unpack my_memories.carry
```

If the .carry file is encrypted, you will be prompted for the password. Unpacking merges memories into your current database — existing memories are not overwritten.

### .carry File Format

| Version | Features |
|---------|----------|
| **v1.1** (current) | SHA-256 checksum for integrity verification + optional encryption |
| **v1.0** (legacy) | No checksum, no encryption — still works with a warning |

The SHA-256 checksum ensures the file was not corrupted during transfer. If checksum verification fails, unpacking is aborted with an error message.

### Password Requirements

- Minimum 4 characters
- The password is not stored anywhere — if you forget it, the data cannot be recovered
- Use a strong, memorable password for sensitive data

---

## USB Carry Scenario

Carry your AI identity on a USB drive and use it on any machine.

### Complete Workflow

```bash
# === On your home machine ===

# 1. Pack your memories with encryption
carrymem pack -o my_memories.carry --encrypt
# Enter password: ********

# 2. Copy to USB drive
cp my_memories.carry /Volumes/USB_DRIVE/

# === On a new machine ===

# 3. Install CarryMem
pip install carrymem

# 4. Initialize
carrymem init

# 5. Unpack your memories
carrymem unpack /Volumes/USB_DRIVE/my_memories.carry
# Enter password: ********

# 6. Verify your memories are restored
carrymem whoami

# 7. Start using AI with your identity
# Your AI now remembers your preferences, decisions, and corrections
```

### Tips

- Always use `--encrypt` when carrying data on a USB drive — USB drives can be lost or stolen
- Run `carrymem doctor` after unpacking to verify everything is working
- Use `carrymem backup` after unpacking to create a local backup
- If you make changes on the new machine, pack again to take them back home
- The .carry file is a single file — easy to copy, email, or store in the cloud

---

## VS Code Extension

### Installation

1. Open VS Code
2. Install from VSIX: `code --install-extension vscode-carrymem-0.2.0.vsix`
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

## CLI Reference

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

### Backup Commands

```bash
carrymem backup                   # Create manual backup
carrymem backup --list            # List all backups
carrymem backup --restore <file>  # Restore from a specific backup
```

### Pack/Unpack Commands

```bash
carrymem pack -o <file>.carry           # Pack memories into .carry file
carrymem pack -o <file>.carry --encrypt # Pack with password encryption
carrymem unpack <file>.carry            # Unpack .carry file (auto-detects encryption)
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
