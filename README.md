# CarryMem — Your AI Finally Remembers Who You Are

**Stop teaching AI who you are. Every. Single. Time.**

> Your portable AI memory — preferences, decisions, and corrections that follow you across models, tools, and devices.

Every time you open a new chat, you introduce yourself again. Your preferences, your decisions, your corrections — all forgotten. Switch from Cursor to Claude Code, from GPT to Claude, start from scratch every time.

You're not using AI. You're training it. Over and over.

CarryMem fixes this. It's a lightweight, zero-dependency memory system that stores **who you are** and makes that identity available to any AI tool. Your AI remembers your preferences, your past decisions, and the corrections you've made — so you can focus on building, not repeating yourself.

**English** | [中文](docs/i18n/README-CN.md) | [日本語](docs/i18n/README-JP.md)

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-2100%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-77.12%25-green" alt="Coverage">
  <img src="https://img.shields.io/badge/code%20quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" alt="Code Quality">
  <img src="https://img.shields.io/badge/security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" alt="Security">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python">
</p>

---

## Why CarryMem?

### The Problem: AI Always Forgets Who You Are

Every new conversation, AI starts from zero:
- You prefer dark mode? **Forgotten.**
- You corrected it last time? **Forgotten.**
- You decided to use React? **Forgotten.**

Switch tools (Cursor → Windsurf), switch models (Claude → GPT) — start from scratch every time.

### The Solution: CarryMem Identity Layer

CarryMem doesn't just store text — it understands **who you are**:

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

---

## Quick Start

### Install

```bash
pip install carrymem
```

> **From PyPI**: [https://pypi.org/project/carrymem/](https://pypi.org/project/carrymem/)
>
> **For development**: `git clone https://github.com/lulin70/carrymem.git && cd carrymem && pip install -e ".[dev]"`

### Verify Installation

```bash
carrymem version
```

**If `command not found`**, add Python bin to PATH:

```bash
# macOS (add to ~/.zshrc)
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Linux (add to ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Or use Python module directly
python3 -m carrymem.cli version
```

Then run `carrymem doctor` to check your setup.

### 5 Lines of Code

> ⚠️ **Package vs Import Name**: Install with `pip install carrymem`, but import as `from carrymem import CarryMem`. You can also use `from carrymem import CarryMem`. This will be fully unified in v1.0.0.

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

### CLI (40+ commands)

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
carrymem version                        # Show version
# Rule Engine commands
carrymem add-rule "use SSL" --trigger "database" --type avoid  # Add a rule
carrymem list-rules --status active                      # List active rules
carrymem skill-pack rules.json --name team-conventions   # Pack rules as Skill
carrymem skill-install team-conventions.json --scope company  # Install Skill
carrymem skill-verify team-conventions.json              # Verify Skill integrity
```

---

## Core Features

### 1. Auto-Classification (7 Memory Types)

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

### 2. Semantic Recall (Cross-Language)

```python
cm.classify_and_remember("我偏好使用PostgreSQL")

# All of these find it:
cm.recall_memories("PostgreSQL")     # Exact match
cm.recall_memories("数据库")          # Synonym expansion
cm.recall_memories("Postgres")       # Spell correction
cm.recall_memories("データベース")    # Cross-language (Japanese)
```

### 3. Identity Layer (whoami)

```python
identity = cm.whoami()
print(identity["preferences"])   # ["I prefer dark mode", ...]
print(identity["decisions"])     # ["Let's use React", ...]
print(identity["corrections"])   # ["The port should be 5432", ...]
```

### 4. Importance Scoring & Lifecycle

Every memory has an importance score that evolves over time:

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30-day half-life decay** — old memories fade unless accessed
- **Access reinforcement** — frequently recalled memories stay fresh
- **Type weighting** — corrections (1.3x) > decisions (1.2x) > preferences (1.1x)

### 5. Quality Management

```bash
carrymem check                    # Check all
carrymem check --conflicts        # Detect contradictions
carrymem check --quality          # Find low-quality memories
carrymem check --expired          # Find expired memories
carrymem clean --expired --dry-run # Preview cleanup
```

### 6. Memory Consolidation

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

### 7. Security & Reliability

| Feature | Description |
|---------|-------------|
| **Encryption** | AES-128 (Fernet) or HMAC-CTR fallback, zero-dep |
| **Backup** | Zero-downtime SQLite VACUUM INTO |
| **Audit Log** | Append-only operation history |
| **Version History** | Every edit tracked, rollback supported |
| **Input Validation** | SQL injection, XSS, path traversal protection |

### 8. MCP Integration (One-Line Setup)

```bash
# Configure for Cursor
carrymem setup-mcp --tool cursor

# Configure for Claude Code
carrymem setup-mcp --tool claude-code

# Configure for all
carrymem setup-mcp --tool all
```

25 MCP tools available: Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (1) · Rules (11)

### 9. Terminal UI

```bash
pip install textual
carrymem tui
```

Interactive terminal interface with sidebar filters, search, and add mode.

### 10. Rule Engine with Scopes

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

### 11. Skill Format — Portable Rule Bundles

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

### 12. Merge Protocol — Conflict Resolution

Three strategies for merging rules from different sources:

| Strategy | Description |
|----------|-------------|
| `company_overrides` | Higher scope always wins |
| `negotiate` | Conflicting rules adapted to "negotiated" scope |
| `keep_both` | Both rules kept for manual review |

### 13. VS Code Extension

Rule management directly in your editor:

- Rule sidebar with scope badges
- Add/edit/delete rules via webview
- Effectiveness report panel
- Skill pack/install from file dialogs

---

## Comparison

|  | CarryMem | Mem0 | OpenChronicle | ima |
|--|----------|------|---------------|-----|
| **Zero Dependencies** | ✅ SQLite only | ⚠️ Vector DB optional | ✅ | ❌ Cloud |
| **Auto-Classification** | ✅ 7 types | ❌ | ❌ Manual | ❌ |
| **Identity Portrait** | ✅ whoami | ❌ | ❌ | ❌ |
| **Rule Engine** | ✅ Scopes + Skills | ❌ | ❌ | ❌ |
| **Skill Format** | ✅ SHA-256 signed | ❌ | ❌ | ❌ |
| **Merge Protocol** | ✅ 3 strategies | ❌ | ❌ | ❌ |
| **VS Code Extension** | ✅ | ❌ | ❌ | ❌ |
| **CLI** | ✅ 40+ commands | ❌ | ❌ | ❌ |
| **TUI** | ✅ textual | ❌ | ❌ | ✅ App |
| **Encryption** | ✅ Built-in | ❌ | ❌ | ❌ |
| **Version History** | ✅ Rollback | ❌ | ❌ | ❌ |
| **Conflict Detection** | ✅ Built-in | ❌ | ❌ | ❌ |
| **Data Ownership** | ✅ Local files | ⚠️ Self-hostable | ✅ Local | ❌ Cloud |
| **5-Line Integration** | ✅ | ⚠️ SDK required | ❌ | ❌ |
| **Cross-Language Recall** | ✅ EN/CN/JP | ❌ | ❌ | ❌ |

> **Note**: Comparison based on publicly available information. Products evolve rapidly — please verify latest features.

**Key Difference**: Other products store *what you read*. CarryMem stores *who you are*.

---

### 🏆 Benchmark — v0.2.1 baseline

| Benchmark | Score | Note |
|-----------|-------|------|
| **PrefEval** | **96.0%** | ICLR 2025 Oral, 50 items, preference adherence (zero-shot: 90%, reminder: 92%) |
| **LongMemEval** | **42.6%** | Official oracle dataset, 500 questions |
| **RuleEngine-Eval** | **93.3%** | CarryMem-original — no other system has a rule engine |
| **MemEval** | **F1=0.127** | Official framework, 20Q sample |
| **MSC** | **40.9%** | Persona Summary F1 (3 episodes) |

| | Advantage | Result |
|---|-----------|--------|
| 💰 | Zero-LLM Ingestion | **88%** memories need **no LLM tokens** |
| ⚡ | P99 Latency | **1.3ms** — **93x faster** than Mem0 |
| 🪶 | Dependencies | **SQLite only** — no vector DB |
| 🛡️ | Rule Engine | **Only system** with rule engine (competitors: 0%) |

> **Transparency first.** First-run baseline scores — not perfect, but honest. Full breakdown: [BENCHMARK_STRATEGY_FINAL.md](docs/BENCHMARK_STRATEGY_FINAL.md)

> Full benchmark methodology & compliance: [BENCHMARK_STRATEGY_FINAL.md](docs/BENCHMARK_STRATEGY_FINAL.md)

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

### Encryption

```python
cm = CarryMem(encryption_key="my-secret-key")
# All content encrypted at rest, decrypted on read
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

## Who Is This For?

**Tired of repeating yourself?**
You use Cursor, Claude Code, ChatGPT daily. You've told AI your stack, your style, your decisions a hundred times. And it still asks "what framework do you prefer?" CarryMem makes your AI remember — so you don't have to keep reminding it.

**Maintaining CLAUDE.md by hand?**
You already know AI needs memory. You have prompt files everywhere. They conflict, they go stale, and they don't follow you between tools. CarryMem auto-classifies your preferences, decisions, and corrections — and keeps them fresh automatically.

**Building AI agents?**
Your agents forget users between sessions. You need a memory layer that's lightweight, local, and works with any LLM. CarryMem gives you 5-line integration, 7 memory types, and a rule engine — with zero dependencies beyond SQLite.

---

## Project Status

**Current Version**: v0.2.1
**Tests**: 2761+ passing
**Coverage**: 80.5%

**Changelog**:
- **v0.2.1**: Coreference resolution, auto-redaction, QA prompt optimization, PrefEval 0.870 (first time surpassing reminder)
- **v0.2.0**: Recall purity, scope-based preference injection, PromptBuilder extraction, PrefEval 0.940, E2E tests
- **v0.1.9**: Consolidation engine (P0/P1/P2), preference injection fix, 25 MCP tools
- **v0.1.6**: Version reset — security hardening (FTS5 sanitization, path validation, rule content filtering), thread safety, documentation reorganization, test cleanup
- **v0.4.1**: Core loop fix — auto rule suggestion, MCP rule tools, prompt injection protection, connection pooling
- **v0.4.0**: Enterprise features — Rule Scopes, Skill Format (SHA-256), Merge Protocol, VS Code Extension
- **v0.3.0**: GA Release — Knowledge Adapter, Effectiveness Report, Context Engineering
- **v0.2.6**: Experience learning — failure→avoidance rules, learn-experience/review-lessons CLI
- **v0.2.5**: Auto-promotion pipeline — memory patterns→rule candidates, promotion-log CLI
- **v0.2.4**: Pattern detection from memories, suggest-rules CLI, candidate rule generator
- **v0.2.3**: Export/import rules, interactive CLI, rule templates, edit-rule, 12 CLI commands
- **v0.2.2**: Performance benchmarks + conflict detection (check-rules command)
- **v0.2.1**: Rules Engine Alpha — manual CRUD, FTS5 matching, security, 8 CLI commands
- **v0.2.0**: PyPI release, identity layer (whoami, profile export), 490 tests
- **v0.0.7**: MCP HTTP/SSE, JSON adapter, async API
- **v0.0.6**: Encryption, backup, audit logging
- **v0.0.5**: Smart context injection, importance scoring, cache, merge, versioning

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

## License

MIT License — see [LICENSE](LICENSE)

---

**CarryMem — Your AI finally remembers who you are. Only you own the data.**
