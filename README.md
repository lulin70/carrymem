# CarryMem — Your AI Finally Remembers Who You Are

**Stop teaching AI who you are every single conversation.**

> Your portable AI memory — preferences, decisions, and corrections that follow you across models, tools, and devices.

Every time you open a new chat, you introduce yourself again. Your preferences, your decisions, your corrections — all forgotten. Switch from Cursor to Claude Code, from GPT to Claude, start from scratch every time.

You're not using AI. You're training it. Over and over.

CarryMem fixes this. It's a lightweight, zero-dependency memory system that stores **who you are** and makes that identity available to any AI tool. Your AI remembers your preferences, your past decisions, and the corrections you've made — so you can focus on building, not repeating yourself.

**English** | [中文](docs/i18n/README-CN.md) | [日本語](docs/i18n/README-JP.md) | [한국어](docs/i18n/README-KO.md) | [繁體中文](docs/i18n/README-ZH-TW.md)

---

## Table of Contents

- [The 30-Second Version](#-the-30-second-version)
- [What CarryMem Does](#what-carrymem-does)
- [Real User Scenarios](#-real-user-scenarios)
- [Get Started](#get-started-pick-your-path)
- [4 Reasons to Choose CarryMem](#4-reasons-to-choose-carrymem)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
  - [Install](#install)
  - [System Requirements](#system-requirements)
  - [Dependencies](#dependencies)
  - [5 Lines of Code](#5-lines-of-code)
  - [CLI (50+ commands)](#cli-50-commands)
- [Core Features](#core-features-powering-the-3-advantages)
  - [Memory That Understands You](#memory-that-understands-you)
  - [Preference Injection](#preference-injection-advantage-1)
  - [Memory Lifecycle](#memory-lifecycle-advantage-2)
  - [Security & Portability](#security--portability-advantage-3)
- [Supporting Features](#supporting-features)
- [Comparison](#comparison)
- [PrefEval Benchmark](#-prefeval--preference-adherence-benchmark)
- [Architecture](#architecture)
- [Module Overview](#module-overview)
- [Advanced Usage](#advanced-usage)
- [Who Is This For?](#who-is-this-for)
- [Documentation](#documentation)
- [Project Status](#project-status)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)

---

## 🌟 The 30-Second Version

> **你每天见客户、开会、聊天，AI 问你一句你答一句，下次对话它又忘了你是谁。**
>
> CarryMem 让 AI **自动记住你的偏好和决策**——不用每次重复说。装一次，所有 AI 工具通用。

*Technical users: see [PrefEval benchmarks](https://arxiv.org/abs/2410.01373) (83.0% ICLR 2025 Oral) and [architecture docs](#-architecture) below.*

---

<p align="center">
  <a href="https://github.com/lulin70/carrymem/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/lulin70/carrymem/ci.yml?branch=new-main&label=CI&logo=github" alt="CI"></a>
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-4666-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-green" alt="Coverage">
  <img src="https://img.shields.io/badge/mypy-0%20errors-brightgreen" alt="mypy">
  <img src="https://img.shields.io/badge/security-bandit%2Bpip--audit-blue" alt="Security">
  <a href="https://arxiv.org/abs/2410.01373"><img src="https://img.shields.io/badge/PrefEval-83.0%25%20(ICLR%202025%20Oral)-9B59B6?logo=arxiv" alt="PrefEval Academic Benchmark"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/deploy-Local%20No%20Docker-success" alt="Deploy">
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
2. Pack as Skill: carrymem rules pack rules.json --name team-conventions
3. Share the .json file with team
4. Each member: carrymem rules install team-conventions.json --scope company
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

## 4 Reasons to Choose CarryMem

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

### 4. Industrial-Grade Engineering — 4666+ Tests / mypy 0 / flake8 0
- **4666+ non-e2e tests passing** with 80%+ coverage (tested: 7 memory types × 4 tiers × lifecycle)
- **mypy 0 errors** across 150+ source files — fully type-safe (CI blocking gate)
- **flake8 0 errors** — clean codebase, no lint violations (black + isort formatted)
- **24 sensitive-pattern redaction** — auto-detects API keys, passwords, tokens before storage
- **PatternAnalyzer God Class split** (1547→171 LOC facade + 3 modules) — maintainable architecture
- **394 docstrings added** — 50%→100% public API documentation coverage
- Maturity assessment: **80/100 (B)** per 7-dimension DevSquad evaluation

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
| Core (incl. encryption) | PyYAML≥5.0, cryptography≥46.0.6 | `pip install carrymem` (included) |
| Multi-language | pycld2, langdetect | `pip install carrymem[language]` |
| Semantic Search | sqlite-vec, sentence-transformers | `pip install carrymem[semantic]` |
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
carrymem rules add "use SSL" --trigger "database" --type avoid  # Add a rule
carrymem rules list --status active                              # List active rules
carrymem rules suggest                                           # Suggest rules
# Also available: carrymem add-rule, carrymem list-rules (legacy aliases)
carrymem rules pack rules.json --name team-conventions   # Pack rules as Skill
carrymem rules install team-conventions.json --scope company  # Install Skill
carrymem rules verify team-conventions.json              # Verify Skill integrity
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
| **Audit Log** | SQLite-persisted operation history (~/.carrymem/audit.db) |
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

### Error Code System (v0.4.0 New)

Structured error handling with bilingual messages:

```python
from carrymem.errors import CarryMemError

# Error code ranges:
# CM-001~099: Configuration & Initialization
# CM-100~199: Storage Adapter
# CM-200~299: Memory Operations
# CM-300~399: Classification & Rule Engine
# CM-400~499: Security & Encryption
# CM-500~599: Import / Export
# CM-600~699: CLI / TUI / MCP Entry Points

try:
    cm.classify_and_remember("test")
except CarryMemError as e:
    print(e.code)     # "CM-001"
    print(e.message)  # "存储适配器未配置。" (Chinese)
    print(e.hint)     # "💡 Use CarryMem(storage='sqlite')..."
```

**Features**:
- 37 error codes with Chinese + English messages
- `from_cause()` factory maps low-level exceptions → friendly codes
- Actionable hints for every error
- 7 concrete error subclasses for programmatic handling

### Monitoring Framework (v0.4.0 New)

Production-ready monitoring with Prometheus export:

```python
from carrymem.monitoring import HealthChecker, MetricsCollector, AlertManager, MonitoringHTTPServer

# Health checks
health = HealthChecker()
health.register_check("storage", lambda: cm._adapter is not None)
status = health.check()  # {"status": "ok", "checks": {...}, "slo": [...]}

# Metrics collection
metrics = MetricsCollector()
metrics.increment("classify_and_remember")
metrics.record_latency("recall", 12.5)
print(metrics.to_prometheus())  # Prometheus text format

# SLO alerts
alerts = AlertManager()
alert_list = alerts.check_alerts(metrics.get_snapshot())

# HTTP server (optional)
server = MonitoringHTTPServer(port=8766, health_checker=health, metrics_collector=metrics)
```

**SLO Targets**:
- `classify_and_remember` P99 < 200ms
- `recall` P99 < 500ms
- Startup time < 2s

### Plugin System (v0.4.0 New)

Extensible plugin architecture with hook points:

```python
from carrymem.plugins import PluginProtocol, PluginManager, HookPoint

class MyPlugin:
    name = "my-plugin"
    version = "1.0.0"

    def on_load(self, carrymem):
        print(f"Loaded into CarryMem")

    def on_memory_stored(self, memory):
        print(f"Memory stored: {memory.content}")

    def on_unload(self):
        print("Plugin unloaded")

manager = PluginManager(plugin_dir="./plugins")
manager.set_carrymem(cm)
manager.load("my-plugin")
```

**Hook Points**: `on_memory_stored` | `on_memory_recalled` | `on_classified` | `on_error`

### Permission System (v0.4.0 New)

Lightweight access control MVP:

```python
from carrymem.security.permissions import Permission, AccessPolicy

policy = AccessPolicy(owner_id="user-123")

# Check permissions
policy.check("user-123", Permission.READ)   # True
policy.check("other-user", Permission.WRITE)  # False

# Require permission (raises SecurityError on denial)
policy.require("user-123", Permission.DELETE, resource="memory")
```

### i18n Internationalization (v0.4.0 New)

Multi-language support without gettext dependency:

```python
from carrymem.i18n import I18nManager, set_locale, _

# Switch language
set_locale("zh-CN")

# Translate with variable interpolation
print(_("memory.stored", count=3))
# → "已记住 3 条记忆"

# Available locales: en, zh-CN
```

### MCP Integration (One-Line Setup)

```bash
# Configure for Cursor
carrymem setup-mcp --tool cursor

# Configure for Claude Code
carrymem setup-mcp --tool claude-code

# Configure for all
carrymem setup-mcp --tool all
```

31 MCP tools available: Core (3) · Storage (3) · Knowledge (3) · Graph (3) · Profile (2) · Prompt (2) · Consolidation (3) · Rules (11) · Health (1)

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

Interactive terminal interface with sidebar filters, search, add, delete (d), and edit (e).

### VS Code Extension

Rule management directly in your editor:

- Rule sidebar with scope badges
- Add/edit/delete rules via webview
- Effectiveness report panel
- Skill pack/install from file dialogs

---

## Comparison

### By Scenario

| Scenario | Mem0 | Memobase | User as Code | CarryMem |
|----------|------|----------|-------------|----------|
| AI remembers what I said | ✅ | ✅ Profile | ✅ | ✅ Automatic |
| Switch AI tools, still remembers | ❌ | ❌ | ❌ Code-only | ✅ One file follows you |
| Don't want AI to remember something | ❌ | ⚠️ Limited | ⚠️ Delete code | ✅ Delete anytime, separate zones |
| Remember without spending tokens | ❌ | ⚠️ LLM extract | ❌ LLM exec | ✅ 88% zero-cost |
| Own your own data | ⚠️ Self-host only | ⚠️ Self-host | ✅ Local | ✅ Local file |
| **Execute user-defined rules** | ❌ | ❌ | ✅ Python | ✅ Rule Engine |

### Feature Matrix

|  | CarryMem | Mem0 | Memobase | User as Code | OpenChronicle | ima |
|--|----------|------|----------|-------------|---------------|-----|
| **Key Differentiator** | **Zero-LLM + Rule Engine** | Vector DB + Cloud | User Profile + Events | Executable Python | Local-first | Cloud notes |
| **Zero Dependencies** | ✅ SQLite only | ⚠️ Vector DB optional | ⚠️ External | ⚠️ Python runtime | ✅ | ❌ Cloud |
| **Auto-Classification** | ✅ 7 types | ❌ | ⚠️ Profile slots | ❌ | ❌ Manual | ❌ |
| **Identity Portrait** | ✅ whoami | ❌ | ✅ Profile | ❌ | ❌ | ❌ |
| **Rule Engine** | ✅ Scopes + Skills | ❌ | ❌ | ✅ Python functions | ❌ | ❌ |
| **Pack / Unpack** | ✅ One file | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Encrypted Carry** | ✅ --encrypt | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Auto-Backup** | ✅ Every 20 writes | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Cross-Language Recall** | ✅ EN/CN/JP | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Encryption** | ✅ Built-in | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Data Ownership** | ✅ Local files | ⚠️ Self-hostable | ⚠️ Self-host | ✅ Local | ✅ Local | ❌ Cloud |

> **Note**: Comparison based on publicly available information. Products evolve rapidly — please verify latest features.
> See [docs/design/METHODOLOGY.md](docs/design/METHODOLOGY.md) for the full design space positioning diagram and orthogonal classification table.

**Key Difference**: Other products store *what you read*. CarryMem stores *who you are*.

---

### Design Space Positioning

CarryMem occupies a unique position at the intersection of three axes:

```
Portable ←————————————————————————————————→ Team-shareable
   |          CarryMem ⭐                  Memobase
   |                                    (team, retrieval, external)
   |     Mem0
   |   (solo, retrieval, vector)
   |————————————————————————————————————————————→ Executable
   |                                    User as Code
   |                                    (solo, executable, Python)
```

| Axis | CarryMem | Mem0 | Memobase | User as Code |
|------|---------|------|----------|-------------|
| **Portable** | ✅ .carry file | ❌ | ❌ | ❌ code-only |
| **Team-shareable** | ✅ | ❌ | ⚠️ profiles | ❌ |
| **Executable rules** | ✅ Rule Engine | ❌ | ❌ | ✅ Python |
| **Zero dependencies** | ✅ SQLite only | ⚠️ Vector DB | ⚠️ External | ⚠️ Python runtime |

**CarryMem is the only framework at the intersection of team sharing, executable rules, and zero dependencies.**

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

**Three-Layer: Mixin + Facade + Protocol (v0.4.0)**

```
┌─────────────────────────────────────────────────────────┐
│                    Facade Layer                          │
│  CarryMem (unified entry point, health_check, version)  │
├─────────────────────────────────────────────────────────┤
│                   Mixin Layer (8 modules)                │
│  Lifecycle │ MemoryCRUD │ Classification │ Recall       │
│  Backup    │ ProfileExport │ Maintenance │ PromptDelegate│
├─────────────────────────────────────────────────────────┤
│                  Protocol Layer (10 Protocols)            │
│  LifecycleOps │ BackupOps │ RecallOps │ ... │ CarryMemOps│
└─────────────────────────────────────────────────────────┘
```

**Data Flow**:
```
User Input
    ↓
Auto-Classification (7 types, 4 tiers)
    ↓
Importance Scoring (confidence × type × recency × access)
    ↓
Smart Storage (SQLite + FTS5, WAL mode, thread-local pool, dedup, TTL, encryption)
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

**PatternAnalyzer Composition** (v0.4.0 refactor — 1547→171 LOC):
```
PatternAnalyzer (facade, 171 LOC)
    ├── NoiseDetector          — noise filtering (B1-B5, C5 rules)
    ├── FeedbackDetector       — execution feedback detection
    └── MemoryPatternDetectors — 8 memory type detectors
        (preference/correction/fact/relationship/task/decision/sentiment/location)
```
Backward compatible: `from carrymem.layers.pattern_analyzer import PatternAnalyzer` unchanged.

---

## Module Overview

| Module | Path | Description |
|--------|------|-------------|
| **Core Engine** | | |
| `_lifecycle` | `src/carrymem/core/_lifecycle.py` | Lifecycle: `__init__`, `close`, context-manager, properties |
| `_memory_crud` | `src/carrymem/core/_memory_crud.py` | Core CRUD: `classify_and_remember`, declare, forget, update, merge |
| `_classification` | `src/carrymem/core/_classification.py` | Classification pipeline internals + rule-delegate methods |
| `_recall` | `src/carrymem/core/_recall.py` | Recall operations: memories, aggregated, timeline, knowledge |
| `_backup` | `src/carrymem/core/_backup.py` | Backup & audit operations |
| `_maintenance` | `src/carrymem/core/_maintenance.py` | Maintenance: conflict detection, quality scoring, expiry, consolidation |
| `_profile_export` | `src/carrymem/core/_profile_export.py` | Profile, stats, export, import operations |
| `_prompt_delegate` | `src/carrymem/core/_prompt_delegate.py` | Prompt delegation and LLM-powered features |
| `_protocols` | `src/carrymem/core/_protocols.py` | Protocol interfaces for Mixin composition (structural typing) |
| **Error Handling** (v0.4.0 New) | | |
| `errors` | `src/carrymem/errors.py` | CarryMemError base class, 7 error ranges (CM-001~999), from_cause() factory |
| `error_messages` | `src/carrymem/error_messages.py` | 37 bilingual error messages (Chinese + English) with actionable hints |
| **Adapters** | | |
| `base` | `src/carrymem/adapters/base.py` | StorageAdapter ABC + MemoryEntry/StoredMemory dataclasses |
| `sqlite_adapter` | `src/carrymem/adapters/sqlite_adapter.py` | SQLite adapter (re-exports from `adapters/sqlite/`) |
| `json_adapter` | `src/carrymem/adapters/json_adapter.py` | JSON file-based storage adapter (zero-dependency) |
| `obsidian_adapter` | `src/carrymem/adapters/obsidian_adapter.py` | Obsidian vault knowledge-base adapter |
| **Monitoring** (v0.4.0 New) | | |
| `monitoring` | `src/carrymem/monitoring/__init__.py` | HealthChecker, MetricsCollector, AlertManager, MonitoringHTTPServer, LatencyTimer |
| **Plugins** (v0.4.0 New) | | |
| `plugins` | `src/carrymem/plugins/__init__.py` | PluginProtocol, PluginManager, HookPoint definitions, event dispatch |
| **Security** | | |
| `permissions` | `src/carrymem/security/permissions.py` | Permission constants & AccessPolicy (owner-based MVP) |
| **i18n** (v0.4.0 New) | | |
| `i18n` | `src/carrymem/i18n/__init__.py` | I18nManager dictionary-based translation, locale switching, variable interpolation |
| **Coordinators** | | |
| `classification_pipeline` | `src/carrymem/coordinators/classification_pipeline.py` | Multi-phase classification orchestration |
| **Pattern Analysis** (v0.4.0 split — was 1547 LOC God Class) | | |
| `pattern_analyzer` | `src/carrymem/layers/pattern_analyzer.py` | Thin facade (171 LOC) — backward-compatible API |
| `noise_detector` | `src/carrymem/layers/noise_detector.py` | Noise filtering (B1-B5, C5 rules, substantive content detection) |
| `feedback_detector` | `src/carrymem/layers/feedback_detector.py` | Execution feedback detection (positive/negative keywords) |
| `memory_pattern_detectors` | `src/carrymem/layers/memory_pattern_detectors.py` | 8 memory type detectors + result builders (1133 LOC) |

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

**Current Version**: v0.9.9
**Tests**: 4666+ non-e2e tests passing, 0 failed, 4 skipped (vector/semantic optional deps); 97 TUI tests passing
**Coverage**: 80%+
**mypy**: 0 errors (150+ source files, CI blocking gate)
**flake8**: 0 errors (black + isort formatted)
**radon**: 0 D/E/F functions (CI blocking gate)
**Maturity**: 80/100 (B) per 7-dimension DevSquad evaluation

**Changelog**:
- **v0.9.9**: Methodology: orthogonal classification table (docs/design/METHODOLOGY.md) + design space positioning (README Comparison + COMPETITIVE_ANALYSIS). See [docs/design/METHODOLOGY.md](docs/design/METHODOLOGY.md).
- **v0.9.8**: Knowledge graph deletion completeness — `forget()` now cascades to `memory_entities` + `memory_relations` (TD-066, Oracle Agent Memory report启发). 4 new tests.
- **v0.9.7**: Tech debt cleanup — TD-003b/009/011b/002 follow-ups (deleted cli.py facade, added TUI fallback tests, downgraded SQLITE_SCHEMA to P3 observation).
- **v0.9.6**: Nightly slow test threshold fix (store_messages batch API) + release.yml cp consistency.
- **v0.9.4**: TD-063/TD-064/TD-065: test skip cleanup + flake8 bugbear fix + ruff config lock.
- **v0.9.3rc1**: TD-015 Password-based publish restored (OIDC abandoned).
- **v0.9.2**: P3 Tech Debt Cleanup — TD-031/049/050/051/053/054.
- **v0.9.1**: TD-055 — mypy src/ baseline errors cleared 9 → 0.
- **v0.9.0**: UI/UX Overhaul — Morandi Aesthetic + Accessibility + Onboarding.
- **v0.8.0**: Graphify — 3 new MCP graph tools (query_graph, shortest_path, get_memory_impact), edge confidence labels (EXTRACTED/INFERRED/AMBIGUOUS) on memory_relations, schema migration v100.
- **v0.7.3**: Security hardening — removed HMAC-CTR stream cipher fallback (cryptography is now a hard dependency), Fernet-only encryption, migration script for pre-v0.7.3 databases. Input validator defense-in-depth, batched LIKE queries, WAL throttle for recall access updates.
- **v0.7.2**: Native Async I/O — async_sqlite adapter (aiosqlite), async recall/store APIs, Memify enhancement. P0 security fixes (fail-closed access control, MCP dispatcher injection), CI/CD hardening (bandit blocking, pip-audit, Docker non-root, pre-release test gate).
- **v0.7.1**: Multi-Mode Retrieval — vector + FTS + semantic fusion with RRF, Memify content enrichment API.
- **v0.7.0**: Knowledge Graph + Session Dual-Layer Memory — entity graph storage, session-scoped memory isolation, dual-layer recall.
- **v0.6.2**: Security fix — access frequency weighting refinement, PBKDF2 260K→600K (OWASP 2023).
- **v0.6.1**: Architecture cleanup — capabilities decoupling, adapter optimization (PATCH).
- **v0.6.0**: Phase 3 Deprecated API Removal (Breaking Change) — legacy API cleanup, store_entry unified entry point.
- **v0.5.4**: Batch API — store_batch/delete_batch for bulk operations (Phase 2 optimization).
- **v0.5.3**: store_entry() core API — unified entry point (Phase 1 optimization).
- **v0.5.2**: Summary Layer + Progressive Disclosure — token-efficient prompt injection, auto-summarization.
- **v0.5.1**: Entity Normalization (Ontology-lite) — rule-based fuzzy entity matching.
- **v0.5.0**: Configurable access frequency weighting + selection access_boost.
- **v0.4.0** (tech debt cleanup): PatternAnalyzer God Class split (1547→171 LOC facade + NoiseDetector + FeedbackDetector + MemoryPatternDetectors), mypy 536→0 errors with CI blocking gate, 394 public API docstrings added (50%→100%), 67 loose assertions strengthened (assertTrue→assertGreater), mypy.ini cleaned (python_version 3.10, removed unused sections). Maturity 74→80 (B-→B).
- **v0.4.0**: Quality Sprint — 134 unit tests for core Mixins, health_check MCP tool (28 total), TUI delete/edit, CLI rules subcommand grouping, audit SQLite persistence, removed @runtime_checkable, merged StorageAdapterProtocol, all Any types replaced (24→0), mypy+bandit CI
- **v0.4.0**: Protocol & Maturity Sprint — Mixin+Facade+Protocol 三层架构, 10个 Protocol 接口, 错误码体系 (CM-001~999), SQLite 连接池 (WAL+线程缓存), 加密升级 (PBKDF2 260K), E2E 测试补全 (+78), 监控框架 MVP, 插件系统 MVP, 权限系统 MVP, i18n 框架, 类型注解 ~82%, 72 new tests
- **v0.3.0**: Maturity & Architecture Sprint — God Class→8 Mixin, exception narrowing (173→15), TUI enhancement (+453 lines, Morandi palette), constants.py (28 named), lazy import cache, ghost feature audit, 71 new tests
- **v0.2.5**: Integration/E2E audit, ghost feature deprecation warnings, version chain validation, 83 new tests
- **v0.2.4**: Beta release — CI root fix, 24 security fixes, Glama TDQS boost, 6-gate CI pipeline
- **v0.2.0**: USB carry encryption, auto-backup, concurrent safety, PrefEval 83.0% (200 items), 8-client MCP setup

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
