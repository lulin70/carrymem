# CarryMem Troubleshooting Guide

**Version**: v0.10.0

---

## Table of Contents

- [Quick Diagnostic](#quick-diagnostic)
- [Error Message Index](#error-message-index)
- [Installation & Setup](#installation--setup)
  - [1. CLI Command Not Found](#1-cli-command-not-found)
  - [2. Import Error](#2-import-error)
  - [3. Version Mismatch](#3-version-mismatch)
  - [4. pip Install Fails](#4-pip-install-fails)
- [Core Memory Operations](#core-memory-operations)
  - [5. Memory Not Stored](#5-memory-not-stored)
  - [6. Recall Returns No Results](#6-recall-returns-no-results)
  - [7. Memory Classification Wrong](#7-memory-classification-wrong)
  - [8. Database Locked](#8-database-locked)
  - [9. Database Corruption](#9-database-corruption)
- [Rule Engine](#rule-engine)
  - [10. Rules Not Injected](#10-rules-not-injected)
  - [11. Rule Scope Conflicts](#11-rule-scope-conflicts)
  - [12. Skill Verification Failed](#12-skill-verification-failed)
  - [13. Rule Suggestion Quality](#13-rule-suggestion-quality)
- [MCP Integration](#mcp-integration)
  - [14. MCP Integration Not Working](#14-mcp-integration-not-working)
  - [15. MCP Tool Timeout](#15-mcp-tool-timeout)
- [Security & Encryption](#security--encryption)
  - [16. Encryption/Decryption Error](#16-encryptiondecryption-error)
  - [17. Path Validation Error](#17-path-validation-error)
- [Advanced Features](#advanced-features)
  - [18. Obsidian Adapter Issues](#18-obsidian-adapter-issues)
  - [19. TUI Display Issues](#19-tui-display-issues)
  - [20. VS Code Extension Issues](#20-vs-code-extension-issues)
  - [21. Async API Issues](#21-async-api-issues)
  - [22. Backup/Restore Issues](#22-backuprestore-issues)
- [Performance](#performance)
  - [23. Slow Recall or Rule Matching](#23-slow-recall-or-rule-matching)
  - [24. Large Database Optimization](#24-large-database-optimization)
- [Upgrade & Migration](#upgrade--migration)
  - [25. Upgrade Breaking Changes](#25-upgrade-breaking-changes)
- [Common Runtime Errors](#common-runtime-errors)
  - [26. Permission Denied](#26-permission-denied)
  - [27. Encrypted Data Password Lost](#27-encrypted-data-password-lost)
  - [28. Python Version Incompatibility](#28-python-version-incompatibility)
  - [29. Dependency Conflict at Runtime](#29-dependency-conflict-at-runtime)
  - [30. Environment Variable Not Loaded](#30-environment-variable-not-loaded)
- [Getting Help](#getting-help)

---

## Quick Diagnostic

Run `carrymem doctor` for a full health check. Use `--fix` to auto-repair where possible, or `--json` for structured output.

**How to read the output:**

| Doctor Check | ok | warn | fail | Related Issue |
|---|---|---|---|---|
| `python_version` | ≥ 3.12 | — | < 3.12 | [#4](#4-pip-install-fails) |
| `carrymem_import` | importable | — | ImportError | [#2](#2-import-error) |
| `config_dir` | exists | missing | — | [#1](#1-cli-command-not-found) |
| `database_file` | exists | missing | — | [#6](#6-recall-returns-no-results) |
| `db_integrity` | passed | — | FAILED | [#9](#9-database-corruption) |
| `db_permissions` | writable | — | read-only | [#22](#22-backuprestore-issues) |
| `disk_space` | > 1 GB | < 1 GB | < 0.1 GB | [#24](#24-large-database-optimization) |
| `db_lock` | unlocked | locked | — | [#8](#8-database-locked) |
| `write_permissions` | writable | — | denied | [#22](#22-backuprestore-issues) |
| `optional_deps` | all installed | missing | — | [#16](#16-encryptiondecryption-error), [#19](#19-tui-display-issues) |
| `fts5` | supported | — | not supported | [#6](#6-recall-returns-no-results) |
| `security` | available | — | unavailable | [#16](#16-encryptiondecryption-error), [#17](#17-path-validation-error) |
| `mcp_configs` | found | not found | — | [#14](#14-mcp-integration-not-working) |
| `memory_count` | > 0 | 0 | — | [#5](#5-memory-not-stored) |
| `rules_engine` | active | stale | — | [#10](#10-rules-not-injected), [#11](#11-rule-scope-conflicts) |
| `auto_inject` | enabled | disabled | — | [#10](#10-rules-not-injected) |
| `cli_path` | on PATH | not on PATH | — | [#1](#1-cli-command-not-found) |

---

## Error Message Index

| Error Message | Issue |
|---|---|
| `command not found: carrymem` | [#1](#1-cli-command-not-found) |
| `No module named 'carrymem'` | [#2](#2-import-error) |
| `No module named 'carrymem'` | [#2](#2-import-error) |
| `carrymem version shows wrong version` | [#3](#3-version-mismatch) |
| `error: externally-managed-environment` | [#4](#4-pip-install-fails) |
| `should_remember: False` | [#5](#5-memory-not-stored) |
| `recall_memories returns empty list` | [#6](#6-recall-returns-no-results) |
| `sqlite3.OperationalError: database is locked` | [#8](#8-database-locked) |
| `database disk image is malformed` | [#9](#9-database-corruption) |
| `No matching rules found` | [#10](#10-rules-not-injected) |
| `Scope conflict detected` | [#11](#11-rule-scope-conflicts) |
| `Skill signature mismatch` | [#12](#12-skill-verification-failed) |
| `ValueError: Path traversal` | [#17](#17-path-validation-error) |
| `ValueError: Path escapes allowed directory` | [#17](#17-path-validation-error) |
| `HMAC verification failed` | [#16](#16-encryptiondecryption-error) |
| `ImportError: No module named 'cryptography'` | [#16](#16-encryptiondecryption-error) |
| `ImportError: No module named 'textual'` | [#19](#19-tui-display-issues) |
| `RuntimeError: Cannot be used across threads` | [#21](#21-async-api-issues) |
| `Connection refused (MCP)` | [#14](#14-mcp-integration-not-working) |
| `FTS5 module not found` | [#6](#6-recall-returns-no-results) |
| `PermissionError: [Errno 13] Permission denied` | [#26](#26-permission-denied) |
| `ValueError: Invalid password` / `cryptography.fernet.InvalidToken` | [#27](#27-encrypted-data-password-lost) |
| `TypeError: unsupported operand type(s)` after upgrade | [#28](#28-python-version-incompatibility) |
| `pkg_resources.VersionConflict` / `ImportError: cannot import name` | [#29](#29-dependency-conflict-at-runtime) |
| `KeyError: 'CARRYMEM_*'` / env var not taking effect | [#30](#30-environment-variable-not-loaded) |

---

## Installation & Setup

### 1. CLI Command Not Found

**Severity**: 🟡 Warning  
**Doctor check**: `cli_path`, `config_dir`

**Problem**: `carrymem` command returns "command not found"

**Root Cause**: pip installs the `carrymem` script to a Python bin directory that is not in your PATH.

**Quick Fix** (works everywhere):
```bash
python3 -m carrymem.cli version
```

**Standard Fix**:

**macOS** — find and add Python bin to PATH:
```bash
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"
# Then add the output path to ~/.zshrc:
export PATH="$HOME/Library/Python/3.12/bin:$PATH"
source ~/.zshrc
carrymem version
```

**Linux** — add user bin to PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
carrymem version
```

**Windows (WSL2)**:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (native PowerShell)**:
```powershell
pip install carrymem
python -m carrymem.cli version
```

**Deep Fix** — if the above doesn't work, use pipx for isolated install:
```bash
pipx install carrymem
carrymem version
```

**Verification**:
```bash
carrymem doctor
# cli_path should show: ok
```

---

### 2. Import Error

**Severity**: 🔴 Critical  
**Doctor check**: `carrymem_import`

**Problem**: `ImportError: No module named 'carrymem'` or `No module named 'carrymem'`

**Error example**:
```
ModuleNotFoundError: No module named 'carrymem'
```

**Root Cause**: CarryMem is not installed in the current Python environment.

**Quick Fix**:
```bash
pip install carrymem
```

**Standard Fix**:

1. Check which Python is being used:
   ```bash
   which python3
   python3 --version
   ```

2. Install for the correct Python:
   ```bash
   python3 -m pip install carrymem
   ```

3. For development (editable install):
   ```bash
   cd /path/to/carrymem
   pip install -e .
   ```

4. Use compatible import path:
   ```python
   from carrymem import CarryMem  # works the same as from carrymem
   ```

**Deep Fix** — virtual environment conflict:
```bash
# If using a virtual environment, make sure it's activated
source .venv/bin/activate  # or conda activate myenv
pip install carrymem

# If multiple Python versions, use explicit path
/usr/bin/python3.11 -m pip install carrymem
```

**Verification**:
```bash
python3 -c "from carrymem import CarryMem; print('OK')"
carrymem doctor
# carrymem_import should show: ok
```

---

### 3. Version Mismatch

**Severity**: 🟡 Warning  
**Doctor check**: `carrymem_import`

**Problem**: `carrymem version` shows wrong version or different from `pip show carrymem`

**Root Cause**: Multiple installations in different environments, or stale cached version.

**Quick Fix**:
```bash
pip install --force-reinstall carrymem
```

**Standard Fix**:

1. Check all installed versions:
   ```bash
   pip show carrymem
   carrymem version
   python3 -c "from carrymem.__version__ import __version__; print(__version__)"
   ```

2. If versions differ, clean up:
   ```bash
   pip uninstall carrymem -y
   pip install carrymem
   ```

**Deep Fix** — multiple Python environments:
```bash
# Find all carrymem installations
find / -name "__version__.py" -path "*/carrymem/*" 2>/dev/null

# Remove stale ones and reinstall
pipx install --force carrymem
```

**Verification**:
```bash
carrymem version
# Should show: 0.2.0
```

---

### 4. pip Install Fails

**Severity**: 🔴 Critical  
**Doctor check**: `python_version`, `carrymem_import`

**Problem**: `pip install carrymem` fails with an error

**Error example**:
```
error: externally-managed-environment
× This environment is externally managed
```

**Root Cause**: System Python is protected (PEP 668), or dependency conflict, or network issue.

**Quick Fix**:
```bash
pip install --user carrymem
```

**Standard Fix**:

1. For externally-managed-environment error (Ubuntu 23.04+, Fedora 38+):
   ```bash
   # Option A: Use pipx (recommended)
   pipx install carrymem

   # Option B: Use virtual environment
   python3 -m venv ~/carrymem-env
   source ~/carrymem-env/bin/activate
   pip install carrymem
   ```

2. For dependency conflict:
   ```bash
   pip install carrymem --no-deps
   pip install click rich prompt-toolkit
   ```

3. For network/proxy issues:
   ```bash
   pip install carrymem --proxy http://proxy:port
   pip install carrymem -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

**Deep Fix** — Python version too old:
```bash
# CarryMem requires Python >= 3.12
python3 --version
# If < 3.12, install a newer Python via pyenv or your OS package manager
```

**Verification**:
```bash
carrymem version
carrymem doctor
# python_version and carrymem_import should show: ok
```

---

## Core Memory Operations

### 5. Memory Not Stored

**Severity**: 🟡 Warning  
**Doctor check**: `memory_count`, `rules_engine`

**Problem**: `classify_and_remember()` returns `should_remember: False`, or `carrymem add` doesn't persist

**Root Cause**: Content classified as not worth remembering (too vague, duplicate, or low importance).

**Quick Fix**:
```bash
carrymem add "your content" --force
```

**Standard Fix**:

1. Check if content meets minimum requirements (≥ 3 characters, not duplicate):
   ```bash
   carrymem add "I prefer dark mode in all editors" --type user_preference
   ```

2. Check current memory count:
   ```bash
   carrymem stats
   ```

3. Use explicit type to improve classification:
   ```bash
   carrymem add "your content" --type user_preference
   # Types: user_preference, decision, correction, task_pattern, sentiment_marker, identity
   ```

**Deep Fix** — classification logic debugging:
```python
from carrymem import CarryMem
cm = CarryMem()
result = cm.classify_and_remember("your content")
print(result)
# Check: memory_type, should_remember, importance_score, reason
cm.close()
```

**Verification**:
```bash
carrymem stats
carrymem doctor
# memory_count should show: ok (> 0)
```

---

### 6. Recall Returns No Results

**Severity**: 🟡 Warning  
**Doctor check**: `fts5`, `memory_count`

**Problem**: `recall_memories()` or `carrymem search` returns empty results

**Root Cause**: FTS5 not available, no memories stored, or query doesn't match.

**Quick Fix**:
```bash
carrymem search "your query" --limit 10
```

**Standard Fix**:

1. Check if FTS5 is supported:
   ```bash
   carrymem doctor
   # fts5 should show: ok
   ```

2. Check memory count:
   ```bash
   carrymem stats
   # If 0 memories, add some first
   carrymem add "test memory"
   ```

3. Try broader queries:
   ```bash
   carrymem search "mode"
   # Instead of very specific queries like "dark mode preference in VS Code"
   ```

**Deep Fix** — FTS5 not available:
```bash
# Check SQLite FTS5 support
python3 -c "import sqlite3; print(sqlite3.sqlite_version); conn = sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(c)')"

# If FTS5 is not available, rebuild Python with SQLite FTS5 support
# On Ubuntu: sudo apt install python3-full
# On macOS: brew install python@3.11
```

**Verification**:
```bash
carrymem search "test"
carrymem doctor
# fts5 and memory_count should show: ok
```

---

### 7. Memory Classification Wrong

**Severity**: 🔵 Info  
**Doctor check**: `rules_engine`

**Problem**: Memory is classified into the wrong type (e.g., a decision classified as a task_pattern)

**Root Cause**: Rule engine pattern doesn't match, or default classifier misidentified the content.

**Quick Fix**:
```bash
carrymem add "your content" --type user_preference
```

**Standard Fix**:

1. Check active rules:
   ```bash
   carrymem rules list
   ```

2. Add a specific rule for your use case:
   ```bash
   carrymem rules add --trigger "I prefer" --action "Classify as user_preference"
   ```

3. Edit an existing rule:
   ```bash
   carrymem rules edit <rule-id>
   ```

**Deep Fix** — classification priority:
```python
from carrymem import CarryMem
cm = CarryMem()
result = cm.classify_and_remember("I always use vim for editing")
print(f"Type: {result['memory_type']}, Reason: {result.get('reason', 'N/A')}")
cm.close()
```

**Verification**:
```bash
carrymem rules check
carrymem doctor
# rules_engine should show: ok
```

---

### 8. Database Locked

**Severity**: 🔴 Critical  
**Doctor check**: `db_lock`

**Problem**: `sqlite3.OperationalError: database is locked`

**Error example**:
```
sqlite3.OperationalError: database is locked
```

**Root Cause**: Another process is using the database, or a stale lock file remains.

**Quick Fix**:
```bash
pkill -f carrymem
```

**Standard Fix**:

1. Close other CarryMem instances:
   ```bash
   pkill -f carrymem
   ```

2. Remove stale WAL/SHM files:
   ```bash
   rm -f ~/.carrymem/memories.db-shm ~/.carrymem/memories.db-wal
   ```

3. Run diagnostics:
   ```bash
   carrymem doctor
   ```

**Deep Fix** — persistent locking:

CarryMem uses SQLite WAL mode for concurrent reads. If locking persists:

1. Check for zombie processes:
   ```bash
   lsof ~/.carrymem/memories.db
   ```

2. Force-checkpoint the WAL:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.carrymem/memories.db')
   conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   conn.close()
   "
   ```

3. If MCP server is running, restart it:
   ```bash
   carrymem serve  # restart the MCP server
   ```

**Verification**:
```bash
carrymem doctor
# db_lock should show: ok
```

---

### 9. Database Corruption

**Severity**: 🔴 Critical  
**Doctor check**: `db_integrity`

**Problem**: `database disk image is malformed` or `PRAGMA integrity_check` fails

**Error example**:
```
sqlite3.DatabaseError: database disk image is malformed
```

**Root Cause**: Unexpected shutdown, disk full, or hardware error corrupted the SQLite file.

**Quick Fix**:
```bash
carrymem doctor --fix
```

**Standard Fix**:

1. **Backup first**:
   ```bash
   cp ~/.carrymem/memories.db ~/.carrymem/memories.db.bak
   ```

2. Run integrity check:
   ```bash
   carrymem doctor
   # db_integrity will show: fail
   ```

3. Attempt recovery:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.carrymem/memories.db')
   result = conn.execute('PRAGMA integrity_check').fetchone()
   print(f'Integrity: {result[0]}')
   conn.close()
   "
   ```

**Deep Fix** — full database rebuild:
```bash
# Export all recoverable data
carrymem export ~/carrymem_backup.json

# Remove corrupted database
rm ~/.carrymem/memories.db

# Reinitialize (carrymem doctor --fix will recreate it)
carrymem doctor --fix

# Reimport data
carrymem import ~/carrymem_backup.json
```

**Verification**:
```bash
carrymem doctor
# db_integrity should show: ok
```

---

## Rule Engine

### 10. Rules Not Injected

**Severity**: 🟡 Warning  
**Doctor check**: `rules_engine`, `auto_inject`

**Problem**: Rules exist but aren't injected into AI prompts

**Root Cause**: Auto-inject is disabled, or no rules match the current context.

**Quick Fix**:
```bash
export CARRYMEM_AUTO_INJECT=true
```

**Standard Fix**:

1. Check rule status:
   ```bash
   carrymem rules list
   carrymem rules check
   ```

2. Verify rule matching:
   ```bash
   carrymem rules match "your scene description"
   ```

3. Enable auto-inject permanently:
   ```bash
   echo 'export CARRYMEM_AUTO_INJECT=true' >> ~/.zshrc
   source ~/.zshrc
   ```

**Deep Fix** — rule priority and scope:
```bash
# Check if rules are paused
carrymem rules list
# Look for status: paused

# Resume paused rules
carrymem rules resume <rule-id>

# Check scope priority: company > negotiated > personal
carrymem rules stats
```

**Verification**:
```bash
carrymem doctor
# rules_engine should show: ok
# auto_inject should show: ok (enabled)
```

---

### 11. Rule Scope Conflicts

**Severity**: 🔵 Info  
**Doctor check**: `rules_engine`

**Problem**: Rules from different scopes (company/negotiated/personal) conflict with each other

**Root Cause**: Scope priority is company > negotiated > personal; a higher-scope rule may override your personal rule.

**Quick Fix**:
```bash
carrymem rules list
# Check which scope each rule belongs to
```

**Standard Fix**:

1. View rules by scope:
   ```bash
   carrymem rules list
   # Each rule shows its scope field
   ```

2. Create a rule in the appropriate scope:
   ```bash
   carrymem rules add --trigger "coding style" --action "Use 4-space indentation"
   ```

3. Check for conflicts:
   ```bash
   carrymem rules check
   ```

**Deep Fix** — understanding scope priority:

| Scope | Priority | Use Case |
|-------|----------|----------|
| `company` | Highest | Organization-wide standards |
| `negotiated` | Medium | Team-level agreements |
| `personal` | Lowest | Individual preferences |

A `company`-scope rule will always override a `personal`-scope rule with the same trigger.

**Verification**:
```bash
carrymem rules stats
carrymem doctor
# rules_engine should show: ok
```

---

### 12. Skill Verification Failed

**Severity**: 🟡 Warning  
**Doctor check**: `security`

**Problem**: `rules verify` returns signature mismatch

**Error example**:
```
Skill signature mismatch: expected abc123..., got def456...
```

**Root Cause**: Skill file was modified after signing, or SHA-256 hash doesn't match.

**Quick Fix**:
```bash
carrymem rules verify <skill-file>
# Check the output for details
```

**Standard Fix**:

1. Verify the skill file hasn't been tampered with:
   ```bash
   carrymem rules verify <skill-file>
   ```

2. If you created the skill, re-pack it:
   ```bash
   carrymem rules pack my-skill.json --name "my-skill"
   ```

3. Check version compatibility:
   ```bash
   carrymem version
   # Ensure both packer and verifier are using the same version
   ```

**Deep Fix** — manual integrity check:
```bash
sha256sum <skill-file>
# Compare with the signature embedded in the skill JSON
```

**Verification**:
```bash
carrymem rules verify <skill-file>
# Should show: valid
```

---

### 13. Rule Suggestion Quality

**Severity**: 🔵 Info  
**Doctor check**: `rules_engine`

**Problem**: `rules suggest` produces low-quality or irrelevant suggestions

**Root Cause**: Not enough memory patterns detected, or `--min-count` threshold too low.

**Quick Fix**:
```bash
carrymem rules suggest --min-count 5
```

**Standard Fix**:

1. Increase the minimum occurrence threshold:
   ```bash
   carrymem rules suggest --min-count 5
   ```

2. Filter by memory type:
   ```bash
   carrymem rules suggest --type user_preference
   carrymem rules suggest --type correction
   ```

3. Review and selectively accept:
   ```bash
   carrymem rules suggest
   # Review each suggestion, then:
   carrymem rules suggest --accept  # accepts all
   ```

**Deep Fix** — improve suggestion quality:

Suggestions are generated from repeated memory patterns. To improve quality:
- Add more detailed memories (not just "I like X")
- Use explicit `--type` when adding memories
- Ensure at least 3-5 similar memories exist before running suggest

**Verification**:
```bash
carrymem rules suggest --min-count 5
# Should show relevant suggestions
```

---

## MCP Integration

### 14. MCP Integration Not Working

**Severity**: 🟡 Warning  
**Doctor check**: `mcp_configs`

**Problem**: AI tool (Cursor, Claude Code) doesn't see CarryMem tools

**Root Cause**: MCP configuration file missing or incorrect.

**Quick Fix**:
```bash
carrymem setup-mcp --tool cursor
# or
carrymem setup-mcp --tool claude-code
```

**Standard Fix**:

1. Run setup for your tool:
   ```bash
   carrymem setup-mcp --tool cursor
   carrymem setup-mcp --tool claude-code
   ```

2. Restart your AI tool after setup

3. Verify MCP config exists:
   ```bash
   # For Cursor
   cat .cursor/mcp.json
   # For Claude Code
   cat .claude/mcp.json
   ```

4. Verify the config content:
   ```json
   {
     "mcpServers": {
       "carrymem": {
         "command": "python3",
         "args": ["-m", "carrymem.integration.layer2_mcp"]
       }
     }
   }
   ```

**Deep Fix** — manual MCP config:

If `setup-mcp` doesn't work, create the config manually:

```bash
# For Cursor
mkdir -p .cursor
cat > .cursor/mcp.json << 'EOF'
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "carrymem.integration.layer2_mcp"]
    }
  }
}
EOF

# For Claude Code
mkdir -p .claude
cat > .claude/mcp.json << 'EOF'
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "carrymem.integration.layer2_mcp"]
    }
  }
}
EOF
```

**Verification**:
```bash
carrymem doctor
# mcp_configs should show: ok (found)
```

---

### 15. MCP Tool Timeout

**Severity**: 🟡 Warning  
**Doctor check**: `mcp_configs`

**Problem**: MCP tool calls time out or return no response

**Root Cause**: MCP server process not running, or Python import takes too long.

**Quick Fix**:
```bash
# Restart the AI tool (it will spawn a new MCP server process)
```

**Standard Fix**:

1. Test MCP server manually:
   ```bash
   python3 -m carrymem.integration.layer2_mcp
   # Should start without errors
   ```

2. Check if the process is running:
   ```bash
   ps aux | grep layer2_mcp
   ```

3. Check for import errors:
   ```bash
   python3 -c "from carrymem.integration.layer2_mcp import mcp; print('OK')"
   ```

**Deep Fix** — slow first import:

The first MCP call may be slow due to Python module loading. To pre-warm:
```bash
# Add to your shell startup
python3 -c "from carrymem import CarryMem" &
```

**Verification**:
```bash
carrymem doctor
# mcp_configs should show: ok
```

---

## Security & Encryption

### 16. Encryption/Decryption Error

**Severity**: 🔴 Critical  
**Doctor check**: `security`, `optional_deps`

**Problem**: Encryption or decryption fails, or HMAC verification fails

**Error example**:
```
ImportError: No module named 'cryptography'
HMAC verification failed
```

**Root Cause**: `cryptography` package not installed, or encrypted data was tampered with.

**Quick Fix**:
```bash
pip install cryptography
```

**Standard Fix**:

1. Install the cryptography package:
   ```bash
   pip install cryptography
   ```

2. Check security module availability:
   ```bash
   carrymem doctor
   # security should show: ok
   # optional_deps should list cryptography as installed
   ```

3. If HMAC verification fails, the data may have been tampered with:
   ```bash
   # Check if the database was modified externally
   carrymem doctor
   # db_integrity should show: ok
   ```

**Deep Fix** — re-encrypt after key change:

If you changed the encryption key, old data cannot be decrypted with the new key:
```bash
# Export unencrypted data first (if still accessible)
carrymem export backup.json

# Reinitialize
rm ~/.carrymem/memories.db
carrymem doctor --fix

# Reimport
carrymem import backup.json
```

**Verification**:
```bash
carrymem doctor
# security and optional_deps should show: ok
```

---

### 17. Path Validation Error

**Severity**: 🟡 Warning  
**Doctor check**: `security`

**Problem**: `ValueError: Path traversal` or `ValueError: Path escapes allowed directory`

**Error example**:
```
ValueError: Path traversal: system directory not allowed: /etc/passwd
```

**Root Cause**: The specified path resolves to a system directory that CarryMem blocks for safety.

**Quick Fix**:
```bash
# Use a path within your home directory
carrymem export ~/my_export.json
```

**Standard Fix**:

1. Use a safe output path:
   ```bash
   carrymem export ~/carrymem_backup.json
   carrymem import ~/carrymem_backup.json
   ```

2. If you need to export to a specific directory, ensure it's within your home:
   ```bash
   mkdir -p ~/backups
   carrymem export ~/backups/memories.json
   ```

3. System directories that are blocked: `/etc`, `/usr`, `/bin`, `/sbin`, `/System`, `/Library`, `/private/etc`

**Deep Fix** — allowed_base parameter:

If using the Python API, you can specify an `allowed_base`:
```python
from carrymem import CarryMem
cm = CarryMem()
cm.export_memories(output_path="/data/exports/backup.json")
# This will work if /data/exports is not a system directory
cm.close()
```

**Verification**:
```bash
carrymem export ~/test_export.json && echo "OK" && rm ~/test_export.json
```

---

## Advanced Features

### 18. Obsidian Adapter Issues

**Severity**: 🔵 Info  
**Doctor check**: `config_dir`

**Problem**: Obsidian vault connection or sync fails

**Root Cause**: Vault path not configured, or file permissions prevent reading/writing.

**Quick Fix**:
```bash
carrymem doctor
# Check config_dir status
```

**Standard Fix**:

1. Verify the vault path exists:
   ```bash
   ls -la /path/to/your/obsidian/vault
   ```

2. Check file permissions:
   ```bash
   # Ensure read/write access
   chmod u+rw /path/to/your/obsidian/vault
   ```

3. Reconfigure the adapter:
   ```python
   from carrymem import CarryMem
   cm = CarryMem(storage_adapter="obsidian", vault_path="/path/to/vault")
   cm.close()
   ```

**Verification**:
```bash
carrymem doctor
# config_dir should show: ok
```

---

### 19. TUI Display Issues

**Severity**: 🔵 Info  
**Doctor check**: `optional_deps`

**Problem**: `carrymem tui` displays incorrectly or crashes

**Error example**:
```
ImportError: No module named 'textual'
```

**Root Cause**: `textual` package not installed, or terminal doesn't support rich output.

**Quick Fix**:
```bash
pip install textual
```

**Standard Fix**:

1. Install textual:
   ```bash
   pip install textual
   ```

2. Check terminal compatibility:
   ```bash
   echo $TERM
   echo $COLORTERM
   # Should show: xterm-256color and truecolor (or 24bit)
   ```

3. Try with explicit terminal settings:
   ```bash
   TERM=xterm-256color carrymem tui
   ```

**Deep Fix** — terminal not supported:

If your terminal doesn't support rich output:
```bash
# Use CLI commands instead of TUI
carrymem list
carrymem search "query"
carrymem rules list
```

**Verification**:
```bash
carrymem doctor
# optional_deps should show textual as installed
```

---

### 20. VS Code Extension Issues

**Severity**: 🔵 Info  
**Doctor check**: `carrymem_import`, `cli_path`

**Problem**: VS Code extension can't connect to CarryMem

**Root Cause**: Extension can't find the CarryMem Python module or CLI.

**Quick Fix**:
```bash
carrymem doctor
# Ensure carrymem_import and cli_path both show: ok
```

**Standard Fix**:

1. Verify CarryMem is accessible from the VS Code terminal:
   ```bash
   carrymem version
   ```

2. Check the extension's Python path setting:
   - Open VS Code Settings
   - Search for "carrymem"
   - Ensure the Python path points to the environment where CarryMem is installed

3. Reinstall the extension:
   ```bash
   code --install-extension vscode-carrymem-0.2.0.vsix
   ```

**Deep Fix** — Python path in VS Code:

If VS Code uses a different Python than your terminal:
```bash
# Find the Python with CarryMem installed
which python3
python3 -c "import carrymem; print(carrymem.__file__)"

# Configure VS Code to use this Python
# Command Palette → Python: Select Interpreter → choose the correct one
```

**Verification**:
```bash
carrymem doctor
# carrymem_import and cli_path should show: ok
```

---

### 21. Async API Issues

**Severity**: 🔵 Info  
**Doctor check**: `carrymem_import`

**Problem**: Async API calls fail with `RuntimeError` or event loop errors

**Error example**:
```
RuntimeError: Cannot be used across threads
RuntimeError: Event loop is closed
```

**Root Cause**: CarryMem's SQLite connection is not thread-safe; async calls must use the same event loop.

**Quick Fix**:
```python
import asyncio
from carrymem import CarryMem

async def main():
    cm = CarryMem()
    result = await cm.classify_and_remember_async("content")
    print(result)
    cm.close()

asyncio.run(main())
```

**Standard Fix**:

1. Ensure all async calls are within the same event loop:
   ```python
   # Correct
   async def app():
       cm = CarryMem()
       result = await cm.classify_and_remember_async("content")
       cm.close()

   # Incorrect — don't create CarryMem outside the event loop
   cm = CarryMem()  # This creates a sync connection
   result = await cm.classify_and_remember_async("content")  # May fail
   ```

2. Don't share CarryMem instances across threads:
   ```python
   # Each thread should create its own instance
   def worker():
       cm = CarryMem()
       result = cm.classify_and_remember("content")
       cm.close()
   ```

**Verification**:
```python
python3 -c "
import asyncio
from carrymem import CarryMem
async def test():
    cm = CarryMem()
    print('Async API available:', hasattr(cm, 'classify_and_remember_async'))
    cm.close()
asyncio.run(test())
"
```

---

### 22. Backup/Restore Issues

**Severity**: 🟡 Warning  
**Doctor check**: `db_permissions`, `write_permissions`, `disk_space`

**Problem**: `carrymem export` or `carrymem import` fails

**Root Cause**: Insufficient permissions, disk full, or invalid file format.

**Quick Fix**:
```bash
carrymem export ~/backup.json
```

**Standard Fix**:

1. Check write permissions:
   ```bash
   carrymem doctor
   # write_permissions and db_permissions should show: ok
   ```

2. Check disk space:
   ```bash
   carrymem doctor
   # disk_space should show: ok
   ```

3. Use correct merge strategy on import:
   ```bash
   # Skip existing memories (default)
   carrymem import ~/backup.json --merge skip_existing

   # Overwrite existing memories
   carrymem import ~/backup.json --merge overwrite
   ```

**Deep Fix** — partial import recovery:

If import partially fails:
```bash
# Check the JSON file integrity
python3 -c "
import json
with open('$HOME/backup.json') as f:
    data = json.load(f)
print(f'Memories: {len(data.get(\"memories\", []))}')
print(f'Rules: {len(data.get(\"rules\", []))}')
"

# Import with verbose output
carrymem import ~/backup.json 2>&1 | tee import.log
```

**Verification**:
```bash
carrymem stats
carrymem doctor
# All checks should show: ok
```

---

## Performance

### 23. Slow Recall or Rule Matching

**Severity**: 🟡 Warning  
**Doctor check**: `database_file`, `disk_space`

**Problem**: Memory recall or rule matching takes noticeably long

**Root Cause**: Database has grown large, expired memories accumulate, or FTS index is stale.

**Quick Fix**:
```bash
carrymem clean --expired --force
```

**Standard Fix**:

1. Clean expired memories:
   ```bash
   carrymem clean --expired --dry-run  # preview first
   carrymem clean --expired --force
   ```

2. Check database size:
   ```bash
   carrymem doctor
   # database_file shows the size
   ```

3. Run optimization:
   ```python
   from carrymem import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   ```

**Deep Fix** — manual VACUUM and index rebuild:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.carrymem/memories.db')
print('Before VACUUM:', conn.execute('SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()').fetchone())
conn.execute('VACUUM')
print('After VACUUM: done')
conn.close()
"
```

**Verification**:
```bash
carrymem search "test" --limit 5
# Should return results quickly (< 1 second)
```

---

### 24. Large Database Optimization

**Severity**: 🔵 Info  
**Doctor check**: `database_file`, `disk_space`

**Problem**: Database exceeds 100 MB, operations are consistently slow

**Root Cause**: Large volume of memories and rules without regular maintenance.

**Quick Fix**:
```bash
carrymem clean --expired --force
carrymem clean --quality 0.3 --force
```

**Standard Fix**:

1. Check database size and memory count:
   ```bash
   carrymem doctor
   carrymem stats
   ```

2. Clean low-quality and expired memories:
   ```bash
   carrymem clean --expired --dry-run
   carrymem clean --quality 0.3 --dry-run
   carrymem clean --expired --quality 0.3 --force
   ```

3. VACUUM the database:
   ```python
   from carrymem import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   ```

**Deep Fix** — archive old data:

For very large databases, consider archiving:
```bash
# Export old memories
carrymem export ~/archive_$(date +%Y%m%d).json

# Then clean them from the active database
carrymem clean --expired --force
```

**Verification**:
```bash
ls -lh ~/.carrymem/memories.db
# Should be significantly smaller after cleanup
```

---

## Upgrade & Migration

### 25. Upgrade Breaking Changes

**Severity**: 🔵 Info  
**Doctor check**: `carrymem_import`

**Problem**: After upgrading CarryMem, existing code or CLI commands behave differently

**Root Cause**: API or CLI changes between versions.

**Quick Fix**:
```bash
# Check the changelog
pip show carrymem
# Visit: https://github.com/lulin70/carrymem/blob/main/CHANGELOG.md
```

**Standard Fix**:

1. Check current version:
   ```bash
   carrymem version
   ```

2. Review the CHANGELOG for breaking changes:
   ```bash
   # See: CHANGELOG.md in the repository root
   ```

3. Use compatible import paths:
   ```python
   # Both work in v0.2.0+
   from carrymem import CarryMem
   from carrymem import CarryMem
   ```

4. Use `carrymem rules` hub instead of individual commands:
   ```bash
   # New (recommended)
   carrymem rules list
   carrymem rules add --trigger "..." --action "..."
   carrymem rules match "scene"

   # Old (still works but deprecated)
   carrymem list-rules
   carrymem add-rule --trigger "..." --action "..."
   carrymem match-rules "scene"
   ```

**Deep Fix** — API stability reference:

See [API_STABILITY.md](API_STABILITY.md) for a complete list of stable, experimental, and deprecated APIs.

**Verification**:
```bash
carrymem doctor
# All checks should show: ok
```

---

## Common Runtime Errors

### 26. Permission Denied

**Severity**: 🔴 Critical
**Doctor check**: `db_permissions`, `write_permissions`

**Problem**: `PermissionError: [Errno 13] Permission denied` when running `carrymem add`, `pack`, `backup`, or `import`.

**Error example**:
```
PermissionError: [Errno 13] Permission denied: '/home/user/.carrymem/memories.db'
```

**Root Cause**: CarryMem's data directory (`~/.carrymem/`) or its files are owned by another user (often caused by running with `sudo` once, or copying files between users).

**Quick Fix**:
```bash
# Take ownership of the CarryMem data directory
sudo chown -R $USER:$USER ~/.carrymem
```

**Standard Fix**:

1. Check current ownership and permissions:
   ```bash
   ls -la ~/.carrymem/
   ```

2. Fix ownership recursively:
   ```bash
   sudo chown -R $USER:$USER ~/.carrymem
   ```

3. Fix permissions (read/write for owner, nothing for others):
   ```bash
   chmod -R u+rwX,go-rwx ~/.carrymem
   ```

4. Verify the database file is writable:
   ```bash
   test -w ~/.carrymem/memories.db && echo "writable" || echo "read-only"
   ```

**Deep Fix** — SELinux or container context:

On SELinux-enabled systems (Fedora, RHEL) or inside containers:
```bash
# Check SELinux context
ls -Z ~/.carrymem/memories.db

# Restore default context (if moved from another location)
restorecon -Rv ~/.carrymem/

# In containers, ensure the volume mount is writable
docker run --user $(id -u):$(id -g) -v ~/.carrymem:/home/user/.carrymem ...
```

**Verification**:
```bash
carrymem doctor
# db_permissions and write_permissions should show: ok
carrymem add "test permission fix"  # should succeed
```

---

### 27. Encrypted Data Password Lost

**Severity**: 🔴 Critical (data unrecoverable)
**Doctor check**: `security`

**Problem**: Cannot unpack an encrypted `.carry` file because the password is forgotten.

**Error example**:
```
ValueError: Invalid password
cryptography.fernet.InvalidToken
```

**Root Cause**: CarryMem uses PBKDF2-HMAC-SHA256 (260,000 iterations) to derive the encryption key from your password. The password is never stored anywhere — if lost, the encrypted data cannot be decrypted.

**Quick Fix**: None. The password cannot be recovered.

**Standard Fix** — restore from an unencrypted backup:

If you have an unencrypted JSON export or a previous unencrypted `.carry` file:
```bash
# Restore from JSON export
carrymem import ~/carrymem_backup.json

# Or restore from an unencrypted .carry file
carrymem unpack ~/old_memories.carry
```

**Deep Fix** — prevention strategy:

1. **Always create an unencrypted backup before encrypting**:
   ```bash
   # Keep an unencrypted JSON export as a safety net
   carrymem export ~/carrymem_safety_backup.json
   # Store it in a secure location (password manager, encrypted volume)
   ```

2. **Test the password immediately after packing**:
   ```bash
   carrymem pack -o my_memories.carry --encrypt
   # Test unpack on the same machine
   carrymem unpack my_memories.carry --dry-run
   ```

3. **Use a password manager** to store the encryption password.

4. **Document your recovery procedure** — there is no backdoor.

**Important**: This is by design. CarryMem cannot decrypt your data without the password. There is no master key, no recovery tool, and no way to bypass the encryption. If anyone claims to offer such a tool, it is a scam.

**Verification**:
```bash
# If you have the password, verify the file is intact
carrymem unpack my_memories.carry  # enter password
carrymem doctor
```

---

### 28. Python Version Incompatibility

**Severity**: 🔴 Critical
**Doctor check**: `python_version`

**Problem**: CarryMem fails to install or crashes at runtime with Python version errors.

**Error examples**:
```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
SyntaxError: invalid syntax (at type hints like `str | None`)
ModuleNotFoundError: No module named 'tomllib'
```

**Root Cause**: CarryMem requires Python ≥ 3.12. It uses:
- PEP 604 union syntax (`str | None`) — requires Python 3.10+
- `tomllib` standard library — requires Python 3.11+
- `typing.Self` — requires Python 3.11+
- Some dependencies require Python 3.12+

**Quick Fix**:
```bash
# Check your Python version
python3 --version
# If < 3.12, install a newer version
```

**Standard Fix**:

1. Install Python 3.12+ using pyenv (recommended):
   ```bash
   curl https://pyenv.run | bash
   pyenv install 3.12
   pyenv global 3.12
   python3 --version  # should show 3.12.x
   ```

2. Or use your OS package manager:
   ```bash
   # macOS (Homebrew)
   brew install python@3.12

   # Ubuntu 24.04+ (already has 3.12)
   sudo apt install python3 python3-pip python3-venv

   # Fedora 40+
   sudo dnf install python3 python3-pip
   ```

3. Reinstall CarryMem with the correct Python:
   ```bash
   python3.12 -m pip install carrymem
   python3.12 -m carrymem.cli version
   ```

**Deep Fix** — multiple Python versions conflict:

```bash
# List all Python versions installed
ls /usr/bin/python3* /usr/local/bin/python3* 2>/dev/null

# Use update-alternatives (Linux)
sudo update-alternatives --config python3

# Or always use explicit version
python3.12 -m pip install carrymem
python3.12 -m carrymem.cli doctor
```

**Verification**:
```bash
python3 --version  # ≥ 3.12
carrymem doctor
# python_version should show: ok
```

---

### 29. Dependency Conflict at Runtime

**Severity**: 🟡 Warning
**Doctor check**: `carrymem_import`, `optional_deps`

**Problem**: CarryMem imports fail at runtime with version conflict errors.

**Error examples**:
```
pkg_resources.VersionConflict: (cryptography 40.0.0 (installed), Requirement.parse('cryptography>=46.0.6'))
ImportError: cannot import name 'Fernet' from 'cryptography'
AttributeError: module 'pycld2' has no attribute 'detect'
```

**Root Cause**: Another package on the system requires an older version of a shared dependency, causing a conflict.

**Quick Fix**:
```bash
# Upgrade the conflicting dependency
pip install --upgrade cryptography
```

**Standard Fix**:

1. Identify the conflicting package:
   ```bash
   pip check
   # Lists all dependency conflicts
   ```

2. Upgrade CarryMem's dependencies:
   ```bash
   pip install --upgrade carrymem
   pip install --upgrade cryptography pycld2 langdetect
   ```

3. If the conflict persists, use a virtual environment:
   ```bash
   python3 -m venv ~/carrymem-env
   source ~/carrymem-env/bin/activate
   pip install carrymem
   ```

**Deep Fix** — pinned dependency hell:

If a system package pins an old version (e.g., `cryptography<40`):
```bash
# Option A: Use pipx for an isolated install (recommended)
pipx install carrymem

# Option B: Force-reinstall the correct version
pip install --force-reinstall --no-deps cryptography>=46.0.6

# Option C: Use --no-deps to skip dependency resolution
pip install carrymem --no-deps
pip install cryptography>=46.0.6 PyYAML>=5.0  # install required deps manually
```

**Optional dependency matrix** (if a feature fails):

| Feature | Required Package | Install Command |
|---------|------------------|-----------------|
| Encryption (required) | `cryptography>=46.0.6` | `pip install carrymem` (included) |
| Multi-language | `pycld2`, `langdetect` | `pip install carrymem[language]` |
| Semantic search | `sqlite-vec`, `sentence-transformers` | `pip install carrymem[semantic]` |
| TUI | `textual` | `pip install textual` |
| All features | all above | `pip install carrymem[full]` |

**Verification**:
```bash
pip check  # should show no conflicts
carrymem doctor
# carrymem_import and optional_deps should show: ok
```

---

### 30. Environment Variable Not Loaded

**Severity**: 🟡 Warning
**Doctor check**: `auto_inject`, `rules_engine`

**Problem**: Environment variables like `CARRYMEM_AUTO_INJECT` are set in `.zshrc`/`.bashrc` but not effective in the current shell or in AI tools (Cursor, Claude Code).

**Error example**:
```bash
# In .zshrc:
export CARRYMEM_AUTO_INJECT=true

# But in Cursor's terminal or MCP server:
echo $CARRYMEM_AUTO_INJECT  # (empty)
```

**Root Cause**: GUI applications (Cursor, VS Code, Claude Code desktop) on macOS/Linux do **not** source `.zshrc`/`.bashrc` by default. They inherit the environment from the login shell or launchd, which doesn't run interactive shell startup files.

**Quick Fix**:
```bash
# Export in the current shell before launching the AI tool
export CARRYMEM_AUTO_INJECT=true
cursor  # or: claude-code
```

**Standard Fix**:

1. Set environment variables in `~/.zshenv` (not `.zshrc`):
   ```bash
   # ~/.zshenv is sourced for ALL shells (login, non-interactive, non-login)
   echo 'export CARRYMEM_AUTO_INJECT=true' >> ~/.zshenv
   ```

2. On macOS, also set via `launchctl` for GUI apps:
   ```bash
   launchctl setenv CARRYMEM_AUTO_INJECT true
   ```

3. Restart the AI tool completely (Cmd+Q, then reopen).

4. Verify the variable is visible to the AI tool's terminal:
   ```bash
   # In Cursor's integrated terminal:
   echo $CARRYMEM_AUTO_INJECT  # should show: true
   ```

**Deep Fix** — MCP server doesn't see env vars:

The MCP server spawned by Cursor/Claude Code inherits the environment from the parent process. If the parent doesn't have the variable, neither will the MCP server.

```bash
# Option A: Hardcode in MCP config (works but less flexible)
# Edit .cursor/mcp.json or .claude/mcp.json:
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "carrymem.integration.layer2_mcp"],
      "env": {
        "CARRYMEM_AUTO_INJECT": "true"
      }
    }
  }
}

# Option B: Use a wrapper script
cat > ~/.carrymem/run-mcp.sh << 'EOF'
#!/bin/bash
export CARRYMEM_AUTO_INJECT=true
exec python3 -m carrymem.integration.layer2_mcp
EOF
chmod +x ~/.carrymem/run-mcp.sh

# Then in mcp.json, set "command" to "/Users/YOU/.carrymem/run-mcp.sh"
```

**Common CarryMem environment variables**:

| Variable | Purpose | Default |
|----------|---------|---------|
| `CARRYMEM_AUTO_INJECT` | Enable auto rule injection into prompts | `false` |
| `CARRYMEM_DB_PATH` | Custom database file location | `~/.carrymem/memories.db` |
| `CARRYMEM_CONFIG_DIR` | Custom config directory | `~/.carrymem/` |
| `CARRYMEM_LOG_LEVEL` | Log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`) | `WARNING` |

**Verification**:
```bash
# In the AI tool's terminal (not your regular terminal):
echo $CARRYMEM_AUTO_INJECT  # should show: true
carrymem doctor
# auto_inject should show: ok (enabled)
```

---

## Getting Help

- **Diagnostics**: `carrymem doctor` — run this first for any issue
- **GitHub Issues**: https://github.com/lulin70/carrymem/issues
- **Documentation**: https://github.com/lulin70/carrymem
- **Changelog**: [CHANGELOG.md](../CHANGELOG.md)
- **API Stability**: [API_STABILITY.md](API_STABILITY.md)
