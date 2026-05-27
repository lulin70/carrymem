# CarryMem Quick Start Guide

**Get started with CarryMem in 5 minutes**

---

## What is CarryMem?

CarryMem lets AI remember you, not the other way around.

**One sentence**: Your AI memory layer that works across models, tools, and devices.

**Core Value**:
- 🧠 AI automatically remembers your preferences, corrections, decisions
- 🔄 Memories are portable - switch tools without losing data
- ⚡ 60%+ zero-cost classification - no token waste

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
- Config file: `~/.carrymem/config.json`
- Database: `~/.carrymem/memories.db`

### 2. Store Your First Memory (1 minute)

```python
from carrymem import CarryMem

# Create instance
with CarryMem() as cm:
    # Classify and store preferences
    cm.classify_and_remember("I prefer dark mode")
    cm.classify_and_remember("I use PostgreSQL for databases")
    cm.classify_and_remember("I work at a startup in Tokyo")
```

### 3. View Memories (30 seconds)

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

### 4. Check Statistics (30 seconds)

```bash
carrymem stats
```

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
A: No! 60%+ classifications are zero-cost, only complex cases call LLM.

### Q: Can I use a different database?
A: Yes! Supports SQLite (default), Obsidian, and custom adapters.

---

## Next Steps

- 📖 Read [Full Documentation](../README.md)
- 🎯 Check [User Guide](USER_GUIDE.md)
- 🏗️ Learn [Architecture Design](ARCHITECTURE.md)
- 🤝 Contribute [Contributing Guide](../CONTRIBUTING.md)

---

## Get Help

- Report issues: [GitHub Issues](https://github.com/lulin70/carrymem/issues)
- Diagnostic tool: `carrymem doctor`

---

**Start using CarryMem and let AI remember you!** 🚀
