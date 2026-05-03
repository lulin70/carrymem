# CarryMem Troubleshooting Guide

## CLI Command Not Found

**Problem**: `carrymem` command returns "command not found"

**Root Cause**: pip installs the `carrymem` script to a Python bin directory that is not in your PATH.

**Quick Fix** (works everywhere):
```bash
python3 -m memory_classification_engine.cli version
```

**Permanent Fix**:

**macOS** — find and add Python bin to PATH:
```bash
# Step 1: Find where pip installed the script
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"

# Step 2: Add to PATH (add to ~/.zshrc for persistence)
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Step 3: Reload shell
source ~/.zshrc

# Step 4: Verify
carrymem version
```

**Linux** — add user bin to PATH:
```bash
# Add to ~/.bashrc for persistence
export PATH="$HOME/.local/bin:$PATH"

# Reload
source ~/.bashrc

# Verify
carrymem version
```

**Windows (WSL2)**:
```bash
# Add to ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
```

**Verify with doctor**:
```bash
carrymem doctor
# The doctor will check if 'carrymem' is on PATH and show the fix command
```

## Import Error

**Problem**: `ImportError: No module named 'memory_classification_engine'`

**Solutions**:

1. Install CarryMem:
   ```bash
   pip install carrymem
   ```

2. For development:
   ```bash
   cd /path/to/carrymem
   pip install -e .
   ```

3. Use compatible import path:
   ```python
   from carrymem import CarryMem  # equivalent to from memory_classification_engine
   ```

## Database Locked

**Problem**: `sqlite3.OperationalError: database is locked`

**Solutions**:

1. Close other CarryMem instances:
   ```bash
   pkill -f memory_classification_engine
   ```

2. Run diagnostics:
   ```bash
   carrymem doctor
   ```

3. Check for stale lock files:
   ```bash
   rm -f ~/.carrymem/memories.db-shm ~/.carrymem/memories.db-wal
   ```

## Version Mismatch

**Problem**: `carrymem version` shows wrong version

**Solutions**:

1. Check installed version:
   ```bash
   pip show carrymem
   ```

2. Reinstall:
   ```bash
   pip install --force-reinstall carrymem
   ```

## MCP Integration Not Working

**Problem**: AI tool doesn't see CarryMem tools

**Solutions**:

1. Run setup:
   ```bash
   carrymem setup-mcp --tool cursor
   # or
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

4. Run diagnostics:
   ```bash
   carrymem doctor
   ```

## Memory Not Stored

**Problem**: `classify_and_remember()` returns `should_remember: False`

**Solutions**:

1. Use `--force` flag:
   ```bash
   carrymem add "your content" --force
   ```

2. Check if content is too vague or short (minimum 3 characters)

3. Use explicit type:
   ```bash
   carrymem add "your content" --force --type user_preference
   ```

## Rules Not Injected

**Problem**: Rules exist but aren't injected into AI prompts

**Solutions**:

1. Enable auto-inject:
   ```bash
   export CARRYMEM_AUTO_INJECT=true
   ```

2. Check rule status:
   ```bash
   carrymem list-rules
   carrymem check-rules
   ```

3. Verify rule matching:
   ```bash
   carrymem match-rules "your scene description"
   ```

## Performance Issues

**Problem**: Slow memory recall or rule matching

**Solutions**:

1. Clean expired memories:
   ```bash
   carrymem clean --expired
   ```

2. Check database size:
   ```bash
   carrymem doctor
   ```

3. Run optimization:
   ```bash
   python3 -c "
   from memory_classification_engine import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   "
   ```

## Getting Help

- GitHub Issues: https://github.com/lulin70/carrymem/issues
- Documentation: https://github.com/lulin70/carrymem
- Diagnostics: `carrymem doctor`
