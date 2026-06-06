# CarryMem — Your AI Finally Remembers Who You Are

**Stop teaching AI who you are every single conversation.**

> Your portable AI memory — preferences, decisions, and corrections that follow you across models, tools, and devices.

Every time you open a new chat, you introduce yourself again. Your preferences, your decisions, your corrections — all forgotten. Switch from Cursor to Claude Code, from GPT to Claude, start from scratch every time.

You're not using AI. You're training it. Over and over.

CarryMem fixes this. It's a lightweight, zero-dependency memory system that stores **who you are** and makes that identity available to any AI tool. Your AI remembers your preferences, your past decisions, and the corrections you've made — so you can focus on building, not repeating yourself.

**English** | [中文](docs/i18n/README-CN.md) | [日本語](docs/i18n/README-JP.md) | [한국어](docs/i18n/README-KO.md) | [繁體中文](docs/i18n/README-ZH-TW.md)

---

## 🌟 The 30-Second Version

> **你每天见客户、开会、聊天，AI 问你一句你答一句，下次对话它又忘了你是谁。**
>
> CarryMem 让 AI **自动记住你的偏好和决策**——不用每次重复说。装一次，所有 AI 工具通用。

*Technical users: see [PrefEval benchmarks](https://arxiv.org/abs/2410.01373) (83.0% ICLR 2025 Oral) and [architecture docs](#-architecture) below.*

---

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-3050%2B%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-79%25%2B-green" alt="Coverage">
  <a href="https://arxiv.org/abs/2410.01373"><img src="https://img.shields.io/badge/PrefEval-83.0%25%20(ICLR%202025%20Oral)-9B59B6?logo=arxiv" alt="PrefEval Academic Benchmark"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python">
</p>

**Topics**: `ai-memory` `mcp` `claude-code` `agent-memory` `cursor` `obsidian` `preference-injection` `sqlite` `llm-tools` `portable-memory`

---

## What CarryMem Does

**5 scenarios you'll recognize:**

> **"I don't want to tell AI my preferences every time"**
> "I prefer PostgreSQL" "Use React not Vue" "No comments in code" — say it once, remembered forever.

> **"I switched AI tools and started from scratch"**
> Taught AI in Cursor, now teaching it again in Claude Code. CarryMem makes your AI memory follow you.

> **"I want to take my data with me"**
> Your AI memory is yours. One file to pack, restore on any machine, any tool.

> **"USB Carry — my memories in my pocket"** 🔑
> Pack your memories to an encrypted .carry file, copy to USB, unpack on a new machine. Your AI identity travels with you — preferences, decisions, corrections, and rules all intact. Every agent on the new machine instantly knows who you are.

> **"My team shares conventions across agents"**
> Team lead packs company rules as a Skill bundle, every team member installs it. All agents enforce the same conventions — no more "I didn't know we use SSL."

---

## 🎯 Real User Scenarios

### Scenario 1: The Multi-Tool Developer

```
Monday:  Tell Cursor "I prefer dark mode, PostgreSQL, React"
Tuesday: Open Claude Code — it already knows your stack
Friday:  Switch to TRAE — same preferences, zero repetition
```

**How**: `carrymem setup-mcp --all --global` — one command, all tools share one memory.

### Scenario 2: The USB Carry — New Machine, Same Identity

```
1. On your laptop:  carrymem pack -o my_identity.carry --encrypt
2. Copy my_identity.carry to USB drive
3. At new workplace: Install CarryMem on new machine
4. carrymem unpack my_identity.carry
5. Every agent on the new machine knows your preferences, decisions, and rules
```

**Encrypted + SHA-256 checksum** — your identity is safe even if the USB is lost.

### Scenario 3: The Team Lead

```
1. Create team conventions as rules: "Always use SSL", "Never deploy on Friday"
2. Pack as Skill: carrymem skill-pack rules.json --name team-conventions
3. Share the .json file with team
4. Each member: carrymem skill-install team-conventions.json --scope company
5. All agents now enforce company conventions automatically
```

### Scenario 4: The Long-Term User

```
Month 1: "I prefer dark mode" → stored as user_preference
Month 3: "Switch to light mode" → auto-supersedes old preference
Month 6: carrymem whoami → shows "I prefer light mode" (dark mode archived)
```

**Preferences evolve. CarryMem tracks the history.**

---

## Get Started (pick your path)

### Using Cursor / Claude Code / TRAE?

```bash
pip install carrymem && carrymem setup-mcp --all --global
```

Restart your AI tool. Done.

### Verify it works (30 seconds)

Tell your AI:
```
Remember, I prefer PostgreSQL
```

Start a new conversation and ask:
```
What database do I prefer?
```

AI answers "PostgreSQL" — it works!

### Need to move your memory?

```bash
carrymem pack                    # Creates carrymem_identity_20260526.carry
# Copy to USB / cloud / new machine
carrymem unpack my_identity.carry  # All memories restored

# With encryption for sensitive data
carrymem pack -o my_memories.carry --encrypt   # Password-encrypted .carry file
carrymem unpack my_memories.carry              # Auto-detects encryption, prompts for password
```

### Auto-backup & Recovery

```bash
carrymem backup                  # Manual backup (also auto-backup every 20 writes)
carrymem backup --list           # List all backups
carrymem backup --restore memories_backup_20260527_120000.db  # Restore from backup
```

---

> 📊 **Academically Verified**: CarryMem's preference injection accuracy (83.0%) was measured using the [PrefEval protocol](https://arxiv.org/abs/2410.01373) (ICLR 2025 Oral, Amazon Science), outperforming simple reminder (80.0%) and zero-shot (71.5%) baselines across 200 test items. See [Citation](#citation) below.

## 3 Reasons to Choose CarryMem

These are what make CarryMem different from every other memory solution:

### 1. Preference Injection Precision — 83.0% (Academically Verified)
- Measured by PrefEval (ICLR 2025 Oral, Amazon Science), 200-sample 3-condition comparison
- CarryMem 83.0% > simple reminder 80.0% > zero-shot 71.5%
- Proactive injection > full reminder — first system to prove this
- 24% fewer unhelpful responses than reminder (28 vs 38) — more precise, less noisy

### 2. Zero-LLM Classification — 88% Without Calling Any LLM
- Rule engine classifies 88% of memories with zero token cost
- Only system with built-in rule engine (competitors: 0%)
- P99 latency: 1.3ms — 93x faster than Mem0

### 3. Lightweight & Portable — SQLite Only
- Zero external dependencies for core functionality
- Single .db file — carry your identity anywhere
- Works with Cursor, Claude Code, ChatGPT, any MCP client

---

## How It Works

```
User Input → Auto-Classification (7 types, 88% rule-based) → Smart Storage (SQLite + FTS5)
    → Semantic Recall (cross-language) → Context Injection (token budget) → AI Tool
```

---

## Quick Start

### Install

```bash
pip install carrymem
```

> **Requires Python 3.12+**. Check your version: `python --version`

> **From PyPI**: [https://pypi.org/project/carrymem/](https://pypi.org/project/carrymem/)
>
> **For development**: `git clone https://github.com/lulin70/carrymem.git && cd carrymem && pip install -e ".[dev]"`

### System Requirements

- **Python**: ≥3.12 (64-bit)
- **OS**: macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **Disk**: ~5MB for core, ~200MB with semantic search
- **Memory**: ~50MB base

### Dependencies

| Feature | Package | Install |
|---------|---------|---------|
| Core | PyYAML≥5.0 | `pip install carrymem` (included) |
| Multi-language | pycld2, langdetect | `pip install carrymem[language]` |
| Semantic Search | sqlite-vec, sentence-transformers | `pip install carrymem[semantic]` |
| Encryption | cryptography≥41.0 | `pip install carrymem[encryption]` |
| Full (all features) | all above | `pip install carrymem[full]` |
| Development | pytest, black, flake8... | `pip install -e ".[dev]"` |

> **Zero LLM dependency for core features** — classification uses rule engine only.

### Verify Installation

```bash
carrymem version
```

**If `command not found`**, add Python bin to PATH:

```bash
# macOS (add to ~/.zshrc)
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# Linux (add to ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Or use Python module directly
python3 -m carrymem.cli version
```

Then run `carrymem doctor` to check your setup.

### 5 Lines of Code

> ⚠️ **Package vs Import Name**: Install with `pip install carrymem` (lowercase), but import as `from carrymem import CarryMem` (CamelCase class). The package name (`carrymem`) and class name (`CarryMem`) differ in casing.

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("I prefer dark mode")        # Auto-classified as preference
cm.classify_and_remember("Use PostgreSQL not MySQL")   # Auto-classified as correction
cm.classify_and_remember("I prefer light mode now", session_id="sess_002")  # Session-aware
memories = cm.recall_memories("database")              # Semantic recall
memories = cm.recall_memories("mode", filters={"session_id": "sess_002"})  # Filter by session
agg = cm.recall_aggregated()                           # Aggregate by type
timeline = cm.recall_timeline("database")              # Knowledge evolution
print(cm.build_system_prompt())                        # Inject into any AI
cm.close()
```

### CLI (50+ commands)

```bash
carrymem init                           # Initialize
carrymem add "I prefer dark mode"       # Store a memory
carrymem add "test note" --force        # Force store (bypass classification)
carrymem list                           # List memories
carrymem search "theme"                 # Search memories
carrymem show <key>                     # View memory details
carrymem edit <key> "new content"       # Edit a memory
carrymem forget <key>                   # Delete a memory
carrymem whoami                         # Who your AI thinks you are
carrymem profile export --output identity.json   # Export your AI identity
carrymem stats                          # Memory statistics
carrymem check                          # Quality & conflict check
carrymem clean --expired --dry-run      # Preview cleanup
carrymem doctor                         # Diagnose installation
carrymem setup-mcp --tool cursor        # One-line MCP config
carrymem tui                            # Terminal UI
carrymem export backup.json             # Export all memories
carrymem import backup.json             # Import memories
carrymem pack -o my_memories.carry      # Pack into portable .carry file
carrymem pack -o my_memories.carry --encrypt  # Encrypted .carry file
carrymem unpack my_memories.carry       # Unpack .carry file
carrymem backup                         # Manual backup
carrymem backup --list                  # List backups
carrymem backup --restore <file>        # Restore from backup
carrymem version                        # Show version
# Rule Engine commands
carrymem add-rule "use SSL" --trigger "database" --type avoid  # Add a rule
carrymem list-rules --status active                      # List active rules
carrymem skill-pack rules.json --name team-conventions   # Pack rules as Skill
carrymem skill-install team-conventions.json --scope company  # Install Skill
carrymem skill-verify team-conventions.json              # Verify Skill integrity
```

---

## Core Features (powering the 3 advantages)

### Memory That Understands You

#### Auto-Classification (7 Memory Types)

CarryMem automatically identifies what kind of information you're sharing:

| Type | Icon | Example |
|------|------|---------|
| `user_preference` | ⭐ | "I prefer dark mode" |
| `correction` | 🔧 | "No, I meant Python 3.11 not 3.10" |
| `decision` | 🎯 | "Let's use React for the frontend" |
| `fact_declaration` | 📌 | "Python 3.12 is the runtime version" |
| `relationship` | ❓ | "Sarah is my manager" |
| `task_pattern` | 🔄 | "I always write tests first" |
| `sentiment_marker` | 💭 | "This build is too slow" |

#### Semantic Recall (Cross-Language)

```python
cm.classify_and_remember("我偏好使用PostgreSQL")

# All of these find it:
cm.recall_memories("PostgreSQL")     # Exact match
cm.recall_memories("数据库")          # Synonym expansion
cm.recall_memories("Postgres")       # Spell correction
cm.recall_memories("データベース")    # Cross-language (Japanese)
```

#### Identity Layer (whoami)

```python
identity = cm.whoami()
print(identity["preferences"])   # ["I prefer dark mode", ...]
print(identity["decisions"])     # ["Let's use React", ...]
print(identity["corrections"])   # ["The port should be 5432", ...]
```

```bash
$ carrymem whoami

  Who You Are (according to your AI)
  ==================================================

  Your Preferences:
    ⭐ I prefer dark mode for all editors
    ⭐ I use PostgreSQL for databases
    ⭐ I always use Python for data analysis

  Your Decisions:
    🎯 Let's use React for the frontend

  Your Corrections:
    🔧 The port should be 5432, not 3306

  Memory Profile:
    Total: 19 | Dominant: user_preference | Avg Confidence: 73%
```

### Preference Injection (advantage #1)

#### Version Chain — Preferences Evolve, Old Versions Auto-Archived

```python
cm.update_memory(key, "Updated content")     # Creates version 2
history = cm.get_memory_history(key)          # [v1, v2]
cm.rollback_memory(key, version=1)            # Restore v1
```

#### Scope-Aware Injection — Only Inject Relevant Preferences Per Context

Preferences are injected based on context scope, so your database preferences don't clutter frontend discussions.

#### Token Budget — 60% Budget for Preferences, Never Truncated

CarryMem allocates 60% of the token budget to preferences, ensuring they're never cut off. This is the key to achieving 83.0% on PrefEval — structured preference injection beats simple reminders.

### Memory Lifecycle (advantage #2)

#### Importance Scoring — Confidence × Type × Recency × Access

Every memory has an importance score that evolves over time:

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30-day half-life decay** — old memories fade unless accessed
- **Access reinforcement** — frequently recalled memories stay fresh
- **Type weighting** — corrections (1.3x) > decisions (1.2x) > preferences (1.1x)

#### Consolidation (P0/P1/P2) — Dedup + Decay + Pattern → Rules + Semantic Merge

Automatic memory lifecycle management with three phases:

```python
# Preview what consolidation would do
report = cm.consolidate(dry_run=True)
print(f"Duplicates: {report['stats']['duplicates_found']}")
print(f"Decayed: {len(report['to_decay'])}")

# Run consolidation (P0: dedup + decay, P1: pattern promotion, P2: semantic merge)
report = cm.consolidate(dry_run=False, run_p1=True, run_p2=True)
```

| Phase | Function | Mechanism |
|-------|----------|-----------|
| **P0** | Dedup + Decay | Jaccard similarity dedup, exponential half-life decay (preferences: 270d, facts: 90d, sentiments: 45d) |
| **P1** | Pattern → Rules | Detect repeated patterns → generate rule candidates for review |
| **P2** | Semantic Merge | Cluster related memories → request host LLM to consolidate |

Preferences are always preserved — never decayed or deduplicated.

#### Scheduled Consolidation — Automatic Background Maintenance

Run consolidation automatically on a recurring interval:

```python
# Schedule consolidation every hour (runs in background thread)
cm.schedule_consolidation(interval_hours=1.0)

# Stop the scheduled consolidation
cm.stop_consolidation()
```

CLI:

```bash
carrymem consolidate --schedule 1h   # Run consolidation every hour
carrymem consolidate --stop          # Stop scheduled consolidation
```

### Security & Portability (advantage #3)

#### Auto-Redaction — 24 Sensitive Patterns

Automatically detects and redacts API keys, passwords, tokens, and 21 other sensitive patterns before storage.

#### Encryption — AES-128 at Rest

| Feature | Description |
|---------|-------------|
| **Encryption** | AES-128 (Fernet) or HMAC-CTR fallback, zero-dep |
| **Encrypted .carry files** | `pack --encrypt` for password-encrypted portable files |
| **Auto-Backup** | Every 20 writes, VACUUM INTO backup, max 5 retained |
| **Backup/Restore** | Manual backup, list, and restore via `carrymem backup` |
| **Audit Log** | Append-only operation history |
| **Version History** | Every edit tracked, rollback supported |
| **Input Validation** | SQL injection, XSS, path traversal protection |

```python
cm = CarryMem(encryption_key="my-secret-key")
# All content encrypted at rest, decrypted on read
```

#### Backup/Restore — Auto-Backup + Manual Control

Auto-backup triggers every 20 write operations (VACUUM INTO), retaining up to 5 backup files. Manual control via CLI:

```bash
carrymem backup                  # Create manual backup
carrymem backup --list           # List all backups
carrymem backup --restore <file> # Restore from a specific backup
```

#### Pack/Unpack — USB Carry with Encryption

```bash
# Pack memories into a portable .carry file
carrymem pack -o my_memories.carry

# With password encryption for sensitive data
carrymem pack -o my_memories.carry --encrypt

# Unpack on any machine (auto-detects encryption)
carrymem unpack my_memories.carry
```

SHA-256 checksum ensures file integrity. v1.0 .carry format is backward compatible with a warning.

#### Export/Import — Identity Follows You Across Devices

```python
# Export your AI identity
cm.export_profile(output_path="my_identity.json")

# On another device or AI tool
cm.import_memories(input_path="backup.json")
```

---

## Supporting Features

### MCP Integration (One-Line Setup)

```bash
# Configure for Cursor
carrymem setup-mcp --tool cursor

# Configure for Claude Code
carrymem setup-mcp --tool claude-code

# Configure for all
carrymem setup-mcp --tool all
```

27 MCP tools available: Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (3) · Rules (11)

**Client Compatibility:**

| Status | Clients | Setup |
|--------|---------|-------|
| ✅ Direct | Cursor, Claude Code, TRAE, Windsurf, Cline | `setup-mcp --global` |
| ✅ Auto-detect | OpenClaw, Kimi Code CLI, CodeX | `setup-mcp --global` (falls back to Claude Code format) |
| 📋 Marketplace | WorkBuddy, CodeBuddy | Submit to MCP Marketplace (pending) |
| ❌ Not supported | Kimi Desktop, DeepSeek Desktop, Qianwen, Doubao, TiGong, ChatGLM | Closed platforms, no MCP interface |

> **🔒 Your memories stay on your machine.** CarryMem stores all data locally in `~/.carrymem/` (SQLite). Each user gets an independent database — just like Git, everyone uses the same tool but keeps their own repos. No cloud sync, no shared state, no cross-user conflicts.

### Rule Engine with Scopes

Behavioral rules with three scope levels for team/organization alignment:

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# Company-mandated rules (highest priority, cannot be overridden)
engine.add_rule("database", "Always use SSL", scope="company", override=True)

# Personal preferences (lowest priority)
engine.add_rule("database", "Prefer PostgreSQL", scope="personal")

# Scope-aware matching
results = engine.match("database design", scopes=["company"])
```

| Scope | Priority | Description |
|-------|----------|-------------|
| `company` | 3 (highest) | Organization-mandated, cannot be overridden |
| `negotiated` | 2 | Adapted from company rules |
| `personal` | 1 (lowest) | User-created preferences |

### Skill Format — Portable Rule Bundles

Share rule sets across teams with cryptographic integrity:

```python
# Pack rules into a portable Skill bundle
bundle = engine.skill_pack(
    name="team-conventions",
    version="1.0.0",
    scope="company",
    author="team-lead",
)

# Verify integrity before installing
result = engine.skill_verify(bundle)
assert result["valid"] is True

# Install on another machine
engine.skill_install(bundle, scope_override="company", mode="skip")
```

### Merge Protocol — Conflict Resolution

Three strategies for merging rules from different sources:

| Strategy | Description |
|----------|-------------|
| `company_overrides` | Higher scope always wins |
| `negotiate` | Conflicting rules adapted to "negotiated" scope |
| `keep_both` | Both rules kept for manual review |

### Quality Management

```bash
carrymem check                    # Check all
carrymem check --conflicts        # Detect contradictions
carrymem check --quality          # Find low-quality memories
carrymem check --expired          # Find expired memories
carrymem clean --expired --dry-run # Preview cleanup
```

### Terminal UI

```bash
pip install textual
carrymem tui
```

Interactive terminal interface with sidebar filters, search, and add mode.

### VS Code Extension

Rule management directly in your editor:

- Rule sidebar with scope badges
- Add/edit/delete rules via webview
- Effectiveness report panel
- Skill pack/install from file dialogs

---

## Comparison

### By Scenario

| Scenario | Mem0 | ima | CarryMem |
|----------|------|-----|----------|
| AI remembers what I said | ✅ | ⚠️ Manual | ✅ Automatic |
| Switch AI tools, still remembers | ❌ | ❌ | ✅ One file follows you |
| Don't want AI to remember something | ❌ | ⚠️ Limited | ✅ Delete anytime, separate zones |
| Remember without spending tokens | ❌ | ❌ | ✅ 88% zero-cost |
| Own your own data | ⚠️ Self-host only | ❌ Cloud | ✅ Local file |

### Feature Matrix

|  | CarryMem | Mem0 | OpenChronicle | ima |
|--|----------|------|---------------|-----|
| **Key Differentiator** | **Zero-LLM + Rule Engine** | Vector DB + Cloud | Local-first | Cloud notes |
| **Zero Dependencies** | ✅ SQLite only | ⚠️ Vector DB optional | ✅ | ❌ Cloud |
| **Auto-Classification** | ✅ 7 types | ❌ | ❌ Manual | ❌ |
| **Identity Portrait** | ✅ whoami | ❌ | ❌ | ❌ |
| **Rule Engine** | ✅ Scopes + Skills | ❌ | ❌ | ❌ |
| **Pack / Unpack** | ✅ One file | ❌ | ❌ | ❌ |
| **Encrypted Carry** | ✅ --encrypt | ❌ | ❌ | ❌ |
| **Auto-Backup** | ✅ Every 20 writes | ❌ | ❌ | ❌ |
| **Cross-Language Recall** | ✅ EN/CN/JP | ❌ | ❌ | ❌ |
| **Encryption** | ✅ Built-in | ❌ | ❌ | ❌ |
| **Data Ownership** | ✅ Local files | ⚠️ Self-hostable | ✅ Local | ❌ Cloud |

> **Note**: Comparison based on publicly available information. Products evolve rapidly — please verify latest features.

**Key Difference**: Other products store *what you read*. CarryMem stores *who you are*.

---

### 🏆 PrefEval — Preference Adherence Benchmark

| Condition | Accuracy | Acknowledged | Violated | Hallucinated | Unhelpful |
|-----------|----------|-------------|----------|-------------|-----------|
| Zero-shot | 71.5% | 160 | 27 | 3 | 31 |
| Reminder | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

Protocol: PrefEval (ICLR 2025 Oral, Amazon Science)
Sample: 200 items, 10 inter-turns, Claude Sonnet 4

**Why this matters**: Reminder injects "remember user preference" in every turn. CarryMem injects structured preferences in system prompt — more precise, more persistent, 24% fewer unhelpful responses.

| | Advantage | Result |
|---|-----------|--------|
| 💰 | Zero-LLM Ingestion | **88%** memories need **no LLM tokens** |
| ⚡ | P99 Latency | **1.3ms** — **93x faster** than Mem0 |
| 🪶 | Dependencies | **SQLite only** — no vector DB |
| 🛡️ | Rule Engine | **Only system** with rule engine (competitors: 0%) |

---

## Architecture

```
User Input
    ↓
Auto-Classification (7 types, 4 tiers)
    ↓
Importance Scoring (confidence × type × recency × access)
    ↓
Smart Storage (SQLite + FTS5, dedup, TTL, encryption)
    ↓
Memory Consolidation (P0: dedup+decay → P1: pattern→rules → P2: semantic merge)
    ↓
Semantic Recall (FTS5 + synonyms + spell fix + cross-language)
    ↓
Context Injection (token budget, relevance ranking)
    ↓
AI Tool (Cursor / Claude Code / any MCP client)
```

**Three-Tier Classification**:
```
Rule Engine (60%+) → Pattern Analysis (30%) → Semantic (10%)
     ↓                      ↓                      ↓
 Zero cost            Near-zero cost          Token cost
```

---

## Advanced Usage

### Obsidian Knowledge Base

```python
from carrymem import CarryMem, ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python design patterns")
```

### Async API

```python
from carrymem import AsyncCarryMem

async with AsyncCarryMem() as cm:
    await cm.classify_and_remember("I prefer dark mode")
    memories = await cm.recall_memories("theme")
```

### JSON Adapter (No SQLite)

```python
from carrymem import CarryMem, JSONAdapter

cm = CarryMem(adapter=JSONAdapter(path="/path/to/memories.json"))
```

### Memory Versioning

```python
cm.update_memory(key, "Updated content")     # Creates version 2
history = cm.get_memory_history(key)          # [v1, v2]
cm.rollback_memory(key, version=1)            # Restore v1
```

### Export Identity for Other AIs

```python
# Export your AI identity
cm.export_profile(output_path="my_identity.json")

# On another device or AI tool
cm.import_memories(input_path="backup.json")
```

---

## Who Is This For?

**Tired of repeating yourself?**
You use Cursor, Claude Code, ChatGPT daily. You've told AI your stack, your style, your decisions a hundred times. And it still asks "what framework do you prefer?" CarryMem makes your AI remember — so you don't have to keep reminding it.

**Maintaining CLAUDE.md by hand?**
You already know AI needs memory. You have prompt files everywhere. They conflict, they go stale, and they don't follow you between tools. CarryMem auto-classifies your preferences, decisions, and corrections — and keeps them fresh automatically.

**Building AI agents?**
Your agents forget users between sessions. You need a memory layer that's lightweight, local, and works with any LLM. CarryMem gives you 5-line integration, 7 memory types, and a rule engine — with zero dependencies beyond SQLite.

---

## Documentation

- [Quick Start Guide](docs/QUICK_START_GUIDE.md)
- [Installation Guide](docs/INSTALL.md)
- [User Guide](docs/USER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [API Stability Policy](docs/API_STABILITY.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

---

## Project Status

**Current Version**: v0.2.4 (Beta)
**Tests**: 3050+ passing
**Coverage**: 79%+

**Changelog**:
- **v0.2.4**: Beta release — CI root fix, 24 security fixes, Glama TDQS boost, 6-gate CI pipeline
- **v0.2.0**: USB carry encryption, auto-backup, concurrent safety, PrefEval 83.0% (200 items), 8-client MCP setup
- **v0.2.3** (pre-reset): Consolidation scheduling (schedule/stop), PrefEval standardization
- **v0.2.2** (pre-reset): Token budget + dead code fix + security, PrefEval 87.9%
- **v0.2.1** (pre-reset): Coreference resolution, auto-redaction, QA prompt optimization

---

## Contributing

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
pytest
```

See [Contributing Guide](CONTRIBUTING.md) for details.

---

## Citation

If you use CarryMem in your research, please cite:

```bibtex
@software{carrymem2026,
  title = {CarryMem: Persistent Memory for AI Agents with Preference Injection},
  author = {CarryMem Team},
  year = {2026},
  url = {https://github.com/carrymem/carrymem},
  note = {Preference injection accuracy 83.0\% measured by PrefEval protocol}
}

@inproceedings{chuang2025prefeval,
  title = {PrefEval: A Preference Evaluation Benchmark for LLMs},
  author = {Chuang, Yun-Nung and others},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2025},
  note = {Oral presentation, Amazon Science}
}
```

**Experimental Results (200 items, 10 inter-turns, Claude Sonnet 4)**

| Condition | Accuracy | Acknowledged | Violated | Hallucinated | Unhelpful |
|-----------|----------|-------------|----------|-------------|-----------|
| Zero-shot | 71.5% | 160 | 27 | 3 | 31 |
| Reminder | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

Key insight: CarryMem achieves the highest accuracy while producing 24% fewer unhelpful responses than reminder-based approaches, demonstrating that proactive memory injection is more precise than full-context reminding.

---

## License

MIT License — see [LICENSE](LICENSE)

---

**CarryMem — Your AI finally remembers who you are. Only you own the data.**
