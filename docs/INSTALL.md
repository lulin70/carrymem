# CarryMem Installation Guide

## System Requirements

- **Python**: ≥3.12 (64-bit)
- **OS**: macOS, Linux, Windows (WSL2 recommended)
- **Disk**: ~10MB for package, ~1MB per database
- **Optional**: Node.js 18+ (for VS Code Extension)

## Installation Methods

### 1. PyPI (Recommended)

```bash
pip install carrymem
```

Verify installation:
```bash
carrymem version
```

**If `carrymem: command not found`**, the pip script directory is not in your PATH. Fix it:

**macOS**:
```bash
# Find your Python bin directory
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"

# Add to PATH (add this line to ~/.zshrc)
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# Then reload
source ~/.zshrc

# Verify
carrymem version
```

**Linux**:
```bash
# Add to PATH (add this line to ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Then reload
source ~/.bashrc

# Verify
carrymem version
```

**Alternative (works everywhere)**:
```bash
python3 -m carrymem version
```

> ⚠️ **Package vs Import Name**: Install with `pip install carrymem`, import as `from carrymem import CarryMem` or `from carrymem.core import CarryMem`.

### 2. Development Install

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

### 3. VS Code Extension

```bash
cd extensions/vscode-carrymem
npm install
npm run compile
```

Then in VS Code: Extensions → "Install from VSIX" or press F5 to run in debug mode.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CARRYMEM_DB_PATH` | `~/.carrymem/memories.db` | Database file path used by the CLI and Python API |
| `CARRYMEM_DATA_PATH` | Not set | Database file path passed to the MCP server; set this to the same file when configuring MCP manually |
| `CARRYMEM_ENCRYPTION_KEY` | None | Fernet encryption key |

### VS Code Settings

```json
{
  "carrymem.dbPath": "~/.carrymem/memories.db",
  "carrymem.defaultScope": "personal"
}
```

## MCP client setup

CarryMem uses MCP. Skill installation is not required. After configuring MCP, use the client chat for normal work.

### Clients configured by the setup command

```bash
carrymem init
carrymem setup-mcp --all --global
carrymem doctor
```

`--all` configures the clients supported by the setup command. Restart the client after configuration.

### Workbuddy manual configuration

CarryMem does not edit Workbuddy configuration automatically. Add the following server to Workbuddy's MCP configuration, usually `~/.workbuddy/mcp.json`, and preserve existing servers:

```json
{
  "mcpServers": {
    "carrymem": {
      "command": "carrymem",
      "args": ["mcp"],
      "env": {
        "CARRYMEM_DATA_PATH": "/Users/your-name/.carrymem/memories.db"
      }
    }
  }
}
```

If `carrymem` is not on PATH, use the absolute Python executable that contains CarryMem:

```json
{
  "command": "/path/to/python",
  "args": ["-m", "carrymem.integration.layer2_mcp"]
}
```

Restart Workbuddy after saving the file. In the client chat, verify the connection:

```text
Please call CarryMem's health_check and report whether the service is healthy.
```

Then store a preference, start a new conversation, and query it:

```text
Remember: I prefer PostgreSQL.
What database do I prefer? Please query CarryMem.
```

To keep a memory under user control, ask the client to query it first, then use its `storage_key`:

```text
Please query CarryMem and show the storage_key, source, scope, and version for the PostgreSQL preference.
Please call update_memory with that storage_key and replace the preference with: I prefer SQLite for local development.
Please call get_memory_history with that storage_key.
Please call forget_memory with that storage_key, then query it again to verify it is gone.
```

CarryMem currently supports memory update, version history, delete, and export/import. It does not currently expose a unified memory-level pause operation; do not confuse rule pause with memory pause.

### Optional vector model

CarryMem may try to download an optional vector model for semantic search. If the download fails because the machine is offline or the model service is unavailable, CarryMem continues to work with rule-based classification and SQLite FTS5 search. This warning does not block installation, MCP, memory write, recall, update, history, delete, backup, or restore. Network access is only required when you want to download or use the optional vector model.

## Verification

Run the installation verification test suite:

```bash
python -m pytest tests/test_rules/test_installation.py -v
```

This verifies:
- All modules are importable
- Version number is correct
- Database initializes with scope support
- CLI skill commands are registered
- VS Code extension files exist
- Full lifecycle smoke test passes

## Troubleshooting

### "Module not found: carrymem"

The PyPI package is `carrymem`, but the import name is `carrymem`:
```python
from carrymem import CarryMem  # Correct
import carrymem                 # Also correct
```

### "carrymem command not found"

Ensure `~/.local/bin` (or equivalent) is in your PATH:
```bash
pip install --user carrymem
export PATH="$HOME/.local/bin:$PATH"
```

### Database permission errors

Ensure write access to the database directory:
```bash
mkdir -p ~/.carrymem
chmod 755 ~/.carrymem
```
