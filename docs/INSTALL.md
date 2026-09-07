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
| `CARRYMEM_DB_PATH` | `~/.carrymem/memories.db` | Database file path |
| `CARRYMEM_ENCRYPTION_KEY` | None | Fernet encryption key |

### VS Code Settings

```json
{
  "carrymem.dbPath": "~/.carrymem/memories.db",
  "carrymem.autoMatch": false,
  "carrymem.defaultScope": "personal"
}
```

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
