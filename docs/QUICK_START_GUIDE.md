# CarryMem Quick Start Guide

**Get started with CarryMem in 5 minutes**

---

## What is CarryMem?

CarryMem lets AI remember you, not the other way around.

**One sentence**: A local AI memory layer shared through MCP-compatible clients.

**Core Value**:
- 🧠 AI automatically remembers your preferences, corrections, decisions
- 🔄 Memories are portable - switch tools without losing data
- ⚡ Rule-based local classification; historical benchmark snapshots are not release gates

---

## Installation

```bash
pip install carrymem
```

Verify installation:
```bash
carrymem version
```

---

## First Time Setup

### 1. Initialize (30 seconds)

```bash
carrymem init
```

This creates:
- Config file: `~/.carrymem/config.yaml`
- Database: `~/.carrymem/memories.db`

### 2. Connect Your AI Tools (1 minute)

CarryMem uses MCP. You do not need to install CarryMem as a Skill. Configure MCP, restart the client, then use the client chat with natural language.

```bash
carrymem setup-mcp --all --global
carrymem doctor
```

This configures CarryMem for clients supported by the setup command:
- **Cursor**: `~/.cursor/mcp.json`
- **Claude Code**: `~/.claude.json`
- **TRAE**: `~/.trae/mcp.json`
- **Windsurf**: `~/.windsurf/mcp.json`
- **Cline**: `~/.cline/mcp.json`
- **OpenClaw / Kimi Code CLI / CodeX**: Auto-detected

Workbuddy is not configured by this command. Add the manual stdio configuration from [INSTALL.md](INSTALL.md#workbuddy-manual-configuration), then restart Workbuddy.

For a specific tool: `carrymem setup-mcp --tool cursor --global`

**Restart your AI tool to activate CarryMem.**

Verify the connection in the client chat:

```text
Please call CarryMem's health_check and report whether the service is healthy.
```

### 3. Store Your First Memory (1 minute)

For normal MCP use, write the memory in the client chat:

```text
Remember: I use PostgreSQL for databases.
```

The Python API is also available for scripts:

```python
from carrymem import CarryMem

with CarryMem() as cm:
    cm.classify_and_remember("I use PostgreSQL for databases")
```

### 4. View Memories (30 seconds)

Start a new client conversation and ask:

```text
Please query CarryMem and tell me which database preference you remember.
```

For local CLI inspection:

```bash
carrymem list
```

Or with code:
```python
with CarryMem() as cm:
    memories = cm.recall_memories(query="database")
    for mem in memories:
        print(f"{mem['type']}: {mem['content']}")
```

### 5. Check Statistics (30 seconds)

```bash
carrymem stats
```

### Offline and optional vector search

CarryMem may show a warning when it cannot download the optional vector model. This does not block the core workflow. Rule-based classification and SQLite FTS5 search remain available, including MCP connection, memory write, new-conversation recall, update, history, delete, backup, and restore. Connect to the network later if you want to download the optional vector model.

---

## Core Features

### Auto-Classification

CarryMem automatically identifies 7 memory types:

```python
with CarryMem() as cm:
    # Preference
    cm.classify_and_remember("I prefer dark mode")
    # → type: user_preference

    # Correction
    cm.classify_and_remember("No, I meant Python 3.11, not 3.10")
    # → type: correction

    # Fact
    cm.classify_and_remember("I work at a startup")
    # → type: fact_declaration

    # Decision
    cm.classify_and_remember("Let's use React for the frontend")
    # → type: decision
```

### Active Declaration

Tell AI about yourself:

```python
with CarryMem() as cm:
    cm.declare("I prefer PostgreSQL over MySQL")
    # → confidence=1.0, guaranteed to be remembered
```

### Smart Recall

```python
with CarryMem() as cm:
    # Exact match
    memories = cm.recall_memories(query="PostgreSQL")

    # Semantic search
    memories = cm.recall_memories(query="database preferences")

    # Cross-language (store in Chinese, query in English)
    cm.classify_and_remember("我喜欢用 PostgreSQL")
    memories = cm.recall_memories(query="database")  # Works!
```

### View Memory Profile

```python
with CarryMem() as cm:
    profile = cm.get_memory_profile()
    print(profile['summary'])
    # → "AI remembers 12 things about you: 5 preferences, 3 corrections, 2 decisions"
```

### Memory Consolidation

```python
# Memory consolidation (run periodically)
report = cm.consolidate(dry_run=True)  # Preview changes
print(f"Found {report['stats']['duplicates_found']} duplicates")
report = cm.consolidate(dry_run=False)  # Execute
```

---

## Knowledge Base (Obsidian)

CarryMem can index your Obsidian vault as a read-only knowledge base, enabling full-text search across your notes alongside your memories.

```python
from carrymem import CarryMem
from carrymem.adapters import ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("project architecture")
```

For detailed configuration, features (FTS5 search, frontmatter parsing, wiki-links, incremental indexing), MCP integration, and troubleshooting, see the [Obsidian Adapter Documentation](OBSIDIAN_ADAPTER.md).

---

## Real-World Scenarios

### Scenario 1: Code Assistant Remembers Your Style

```python
with CarryMem() as cm:
    # First conversation
    cm.classify_and_remember("I prefer using type hints in Python")
    cm.classify_and_remember("I like to use dataclasses instead of dicts")

    # Next conversation, AI automatically knows your preferences
    memories = cm.recall_memories(query="Python coding style")
    # AI generates code with type hints and dataclasses
```

### Scenario 2: Cross-Tool Usage

```python
# In Cursor
with CarryMem(namespace="cursor") as cm_cursor:
    cm_cursor.classify_and_remember("I prefer dark mode")

# In Windsurf, use same memories
with CarryMem(namespace="cursor") as cm_windsurf:
    memories = cm_windsurf.recall_memories(query="theme")  # Found!
```

### Scenario 3: Project Isolation

```python
# Project A
with CarryMem(namespace="project-a") as cm_a:
    cm_a.classify_and_remember("Use React for frontend")

# Project B
with CarryMem(namespace="project-b") as cm_b:
    cm_b.classify_and_remember("Use Vue for frontend")

# No interference!
```

### Scenario 4: Carry Your Memories (USB Carry)

Pack your memories for travel, copy to USB, and unpack on a new machine:

```bash
# Pack your memories for travel
carrymem pack -o my_memories.carry --encrypt

# On a new machine, unpack
carrymem unpack my_memories.carry
```

The `--encrypt` flag prompts for a password (at least 4 characters). The .carry file includes a SHA-256 checksum for integrity verification. Unpacking auto-detects encryption and prompts for the password.

### Scenario 5: Backup & Recovery

CarryMem automatically backs up your database every 20 write operations. You can also manage backups manually:

```bash
# Manual backup
carrymem backup

# List backups
carrymem backup --list

# Restore from backup
carrymem backup --restore memories_backup_20260527_120000.db
```

Auto-backup retains up to 5 backup files using VACUUM INTO (zero-downtime). Check backup status with `carrymem doctor`.

---

## Export and Import

### Export Memories

```python
with CarryMem() as cm:
    # Export as JSON
    cm.export_memories(output_path="my_memories.json")

    # Export as Markdown (human-readable)
    cm.export_memories(output_path="my_memories.md", format="markdown")
```

### Import on New Device

```python
# On new computer
with CarryMem() as cm_new:
    cm_new.import_memories(input_path="my_memories.json")
    # All memories restored!
```

---

## CLI Tools

```bash
# Initialize
carrymem init

# List memories
carrymem list
carrymem list --type user_preference
carrymem list --limit 20

# Statistics
carrymem stats

# Health check
carrymem doctor

# Version info
carrymem version
```

---

## FAQ

### Q: Where is data stored?
A: By default `~/.carrymem/memories.db`. You can specify a custom path.

### Q: Is data secure?
A: Data is stored on your local machine, never uploaded to any server.

### Q: Can I delete memories?
A: Yes!
```python
with CarryMem() as cm:
    cm.forget_memory(memory_id)
```

### Q: Which languages are supported?
A: Chinese, English, Japanese, with cross-language search support.

### Q: Does it consume many tokens?
A: The rule engine handles eligible inputs without LLM tokens first. A historical internal snapshot reported 88%, but that figure has no versioned dataset artifact and is not a release gate.

### Q: Can I use a different database?
A: Yes! Supports SQLite (default), Obsidian, and custom adapters.

---

## Next Steps

- 📖 Read [Full Documentation](../README.md)
- 🎯 Check [User Guide](USER_GUIDE.md)
- 🏗️ Learn [Architecture Design](ARCHITECTURE.md)
- 📓 Connect your vault with [Obsidian Adapter](OBSIDIAN_ADAPTER.md)
- 🤝 Contribute [Contributing Guide](../CONTRIBUTING.md)

---

## Get Help

- Report issues: [GitHub Issues](https://github.com/lulin70/carrymem/issues)
- Diagnostic tool: `carrymem doctor`

---

**Start using CarryMem and let AI remember you!** 🚀
