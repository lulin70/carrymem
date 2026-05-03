# CarryMem Documentation Hub

**Version**: v0.1.5  
**Last Updated**: 2026-05-03

---

## 🚀 Quick Start (New Users)

### 1. Installation
- **[One-Click Install](../install.sh)** - Recommended! Automatic setup
- **[Quick Start Guide](QUICK_START_GUIDE.md)** - Get started in 5 minutes

### 2. Basic Usage
```bash
# Install
bash install.sh

# Initialize
carrymem init

# Add memory
carrymem add "I prefer dark mode"

# Search memories
carrymem search "theme"

# Check status
carrymem status
```

---

## 📚 Core Documentation

### User Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [Quick Start Guide](QUICK_START_GUIDE.md) | Get started in 5 minutes | ⭐ All users |
| [User Guide](USER_GUIDE.md) | Complete usage guide | All users |

### Developer Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [Architecture](ARCHITECTURE.md) | System architecture design | Developers |
| [API Reference](API_REFERENCE.md) | API interface documentation | Developers |
| [Roadmap](ROADMAP.md) | Future plans | Contributors |
| [Contributing Guide](../CONTRIBUTING.md) | How to contribute | Contributors |

---

## 🛠️ Core Features

### 1. Smart Memory Classification
```bash
carrymem add "I prefer dark mode"
```
Auto-classified into 7 types: user_preference, correction, fact_declaration, decision, relationship, task_pattern, sentiment_marker

### 2. Semantic Recall
```bash
carrymem search "dark"
```
Cross-language search: dark mode / 深色模式 / ダークモード

### 3. AI Identity Layer
```bash
carrymem whoami
carrymem profile export identity.json
```

### 4. System Diagnostics
```bash
carrymem doctor
carrymem check
```

### 5. MCP Integration
```bash
carrymem setup-mcp --tool cursor
carrymem serve --port 8765
```

### 6. Data Security
- AES encrypted storage
- Automatic backup + safe rollback
- Access audit logging
- Input validation (SQL injection / XSS / path traversal protection)

---

## 📖 Find Documentation by Scenario

### Scenario 1: New user, want to get started quickly
1. Run `bash install.sh` for one-click install
2. Read [Quick Start Guide](QUICK_START_GUIDE.md)

### Scenario 2: Installation issues
1. Run `carrymem doctor` for diagnostics
2. Check [Quick Start Guide](QUICK_START_GUIDE.md) FAQ section

### Scenario 3: Configure MCP integration
1. Run `carrymem setup-mcp --tool claude`
2. Check integration configs in `integrations/` directory

### Scenario 4: Check system status
1. Run `carrymem status`
2. Run `carrymem stats`

### Scenario 5: Developer, want to contribute
1. Read [Architecture](ARCHITECTURE.md)
2. Read [API Reference](API_REFERENCE.md)
3. Check [Roadmap](ROADMAP.md)
4. Read [Contributing Guide](../CONTRIBUTING.md)

---

## 🔧 Command Reference

### Basic Commands
```bash
carrymem init                    # Initialize database
carrymem add "message"           # Add memory
carrymem list                    # List memories
carrymem search "query"          # Search memories
carrymem stats                   # Statistics
```

### Diagnostic Commands
```bash
carrymem doctor                  # System diagnostics
carrymem status                  # System status
carrymem setup-mcp --tool claude # MCP configuration
```

### Management Commands
```bash
carrymem edit <key> "new text"   # Edit memory
carrymem forget <key>            # Delete memory
carrymem clean                   # Clean expired memories
carrymem export <path>           # Export memories
carrymem import <path>           # Import memories
```

---

## 📁 Documentation Directory Structure

```
docs/
├── README.md                          # This document (docs index)
├── QUICK_START_GUIDE.md               # Quick start
├── USER_GUIDE.md                       # User guide
├── ARCHITECTURE.md                    # Architecture
├── API_REFERENCE.md                   # API reference
├── ROADMAP.md                         # Roadmap
├── guides/                            # Detailed guides
├── planning/                          # Planning documents
├── internal/                          # Internal documents
└── i18n/                              # Internationalized documents
    ├── README-CN.md                   # Chinese README
    ├── README-JP.md                   # Japanese README
    ├── CONTRIBUTING-CN.md             # Chinese contributing guide
    └── ROADMAP-CN.md                  # Chinese roadmap
```

---

## 🆘 Get Help

### Having Issues?
1. **Run diagnostics**: `carrymem doctor`
2. **Check status**: `carrymem status`
3. **Read docs**: [Quick Start Guide](QUICK_START_GUIDE.md)

### Report Issues
- GitHub Issues: [Submit Issue](https://github.com/lulin70/carrymem/issues)

---

**Last Updated**: 2026-04-28  
**Maintainer**: CarryMem Team
