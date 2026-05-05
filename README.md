# CarryMem — The Identity Layer for AI

**AI remembers who you are. Not just what you said.**

> Your portable AI identity layer — preferences, decisions, and corrections that follow you across models, tools, and devices.

CarryMem is a lightweight, zero-dependency AI memory system that stores **who you are** — your preferences, decisions, corrections — and makes that identity available to any AI tool. Switch from Cursor to Claude Code, from GPT to Claude, your AI always knows you.

### 🏆 Benchmark Highlights

| | Metric | Result |
|---|--------|--------|
| 🥇 | **Overall Score** | **94.5% (Grade A)** across 4 benchmarks |
| 🥇 | **Multi-Session Recall** | **100%** at 90 days — AI truly "remembers you" |
| 🥇 | **Only Rule Engine** | **93.3%** compliance — competitors: **0%** |
| 💰 | **Zero-Cost Classification** | **88%** needs **no LLM tokens** at all |
| ⚡ | **P99 Latency** | **1.3ms** — **93x faster** than Mem0 |
| 🪶 | **Dependencies** | **SQLite only** — no vector DB needed |

**English** | [中文](docs/i18n/README-CN.md) | [日本語](docs/i18n/README-JP.md)

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-2070%20passing%20(99.81%25)-brightgreen" alt="Tests">
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
python3 -m memory_classification_engine.cli version
```

Then run `carrymem doctor` to check your setup.

### 5 Lines of Code

> ⚠️ **Package vs Import Name**: Install with `pip install carrymem`, but import as `from memory_classification_engine import CarryMem`. You can also use `from carrymem import CarryMem`. This will be fully unified in v1.0.0.

```python
from memory_classification_engine import CarryMem

cm = CarryMem()
cm.classify_and_remember("I prefer dark mode")        # Auto-classified as preference
cm.classify_and_remember("Use PostgreSQL not MySQL")   # Auto-classified as correction
memories = cm.recall_memories("database")              # Semantic recall
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

### 6. Security & Reliability

| Feature | Description |
|---------|-------------|
| **Encryption** | AES-128 (Fernet) or HMAC-CTR fallback, zero-dep |
| **Backup** | Zero-downtime SQLite VACUUM INTO |
| **Audit Log** | Append-only operation history |
| **Version History** | Every edit tracked, rollback supported |
| **Input Validation** | SQL injection, XSS, path traversal protection |

### 7. MCP Integration (One-Line Setup)

```bash
# Configure for Cursor
carrymem setup-mcp --tool cursor

# Configure for Claude Code
carrymem setup-mcp --tool claude-code

# Configure for all
carrymem setup-mcp --tool all
```

23 MCP tools available: Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (1) · Rules (11)

### 8. Terminal UI

```bash
pip install textual
carrymem tui
```

Interactive terminal interface with sidebar filters, search, and add mode.

### 9. Rule Engine with Scopes

Behavioral rules with three scope levels for team/organization alignment:

```python
from memory_classification_engine.rules import RuleEngine

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

### 10. Skill Format — Portable Rule Bundles

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

### 11. Merge Protocol — Conflict Resolution

Three strategies for merging rules from different sources:

| Strategy | Description |
|----------|-------------|
| `company_overrides` | Higher scope always wins |
| `negotiate` | Conflicting rules adapted to "negotiated" scope |
| `keep_both` | Both rules kept for manual review |

### 12. VS Code Extension

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

## Benchmark Results (Phase 1 — Optimized)

**Overall Score: 94.5% (Grade A — Outstanding)** — Tested across 4 benchmarks, 20 dimensions

| Benchmark | Score | Grade | Key Metric |
|-----------|-------|-------|------------|
| **MSC** | **100.0%** | A+ | 100% recall at Day 90, AI truly "remembers you" |
| **LongMemEval** | **91.5%** | A | 100% recall accuracy, 100% privacy compliance |
| **MemEval** | **93.1%** | A | 92% classification accuracy, 88% zero-cost |
| **RuleEngine-Eval** | **93.3%** | A | Only system with rule engine (competitors: 0%) |

### CarryMem vs Industry

| System | Accuracy | Token Cost | Vector DB | P99 Latency |
|--------|----------|------------|-----------|-------------|
| **CarryMem** | **92.0%** | **88% zero-cost** | **No** | **1.3ms** |
| Mem0 | 85.0% | High | Yes | 120ms |
| MemGPT | 82.0% | Very High | Yes | 250ms |
| Zep | 83.0% | High | Yes | 130ms |
| LangChain Memory | 80.0% | Medium | No | 110ms |
| Chroma | 77.0% | Medium | Yes | 100ms |

### Why CarryMem Wins

- 🏆 **Only rule engine** — 93.3% compliance, competitors score 0%
- 🏆 **100% multi-session recall** — AI remembers you across 90+ days
- 🏆 **88% zero-cost** — No LLM tokens needed for most classifications
- 🏆 **93x faster** — P99 classify 1.3ms vs Mem0 120ms
- 🏆 **Zero dependencies** — SQLite only, no vector DB required

> Full benchmark details: [BENCHMARK_STRATEGY_FINAL.md](docs/BENCHMARK_STRATEGY_FINAL.md)

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
from memory_classification_engine import CarryMem, ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python design patterns")
```

### Async API

```python
from memory_classification_engine import AsyncCarryMem

async with AsyncCarryMem() as cm:
    await cm.classify_and_remember("I prefer dark mode")
    memories = await cm.recall_memories("theme")
```

### JSON Adapter (No SQLite)

```python
from memory_classification_engine import CarryMem, JSONAdapter

cm = CarryMem(adapter=JSONAdapter("/path/to/memories.json"))
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

**Developers** — Building AI agents that need to remember users across sessions

**Power Users** — Want AI tools (Cursor, Claude Code, Windsurf) to remember them

**Teams** — Share organizational knowledge through shared memory namespaces

---

## Project Status

**Current Version**: v0.1.6
**Tests**: 2056/2056 passing
**Coverage**: ~78%

**Changelog**:
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

**CarryMem — AI remembers who you are. Only you own the data.** 🚀
