# CarryMem Documentation Hub

**Version**: v0.5.2  
**Last Updated**: 2026-05-03

---

## 🚀 Quick Start (New Users)

### 1. Installation
- **[One-Click Install](../scripts/install.sh)** - Recommended! Automatic setup
- **[Quick Start Guide](QUICK_START_GUIDE.md)** - Get started in 5 minutes

### 2. Basic Usage
```bash
# Install
bash scripts/install.sh

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
| [Troubleshooting](TROUBLESHOOTING.md) | Diagnose and fix common issues | All users |
| [Install Guide](INSTALL.md) | Detailed installation instructions | All users |

### Developer Documentation

| Document | Description | Audience |
|----------|-------------|----------|
| [Architecture](ARCHITECTURE.md) | System architecture design | Developers |
| [API Reference](API_REFERENCE.md) | API interface documentation | Developers |
| [API Stability](API_STABILITY.md) | API stability guarantees | Developers |
| [Rules User Manual](RULES_USER_MANUAL.md) | Rule engine usage guide | All users |
| [Roadmap](ROADMAP.md) | Future plans | Contributors |
| [Contributing Guide](../CONTRIBUTING.md) | How to contribute | Contributors |

### Internationalized Documentation (i18n/)

| Document | EN | CN | JP |
|----------|----|----|-----|
| README | [EN](../README.md) | [CN](i18n/README-CN.md) | [JP](i18n/README-JP.md) |
| Install Guide | [EN](INSTALL.md) | [CN](i18n/INSTALL-CN.md) | [JP](i18n/INSTALL-JP.md) |
| Quick Start | [EN](QUICK_START_GUIDE.md) | [CN](i18n/QUICK_START_GUIDE-CN.md) | [JP](i18n/QUICK_START_GUIDE-JP.md) |
| User Guide | [EN](USER_GUIDE.md) | [CN](i18n/USER_GUIDE-CN.md) | [JP](i18n/USER_GUIDE-JP.md) |
| Troubleshooting | [EN](TROUBLESHOOTING.md) | [CN](i18n/TROUBLESHOOTING-CN.md) | [JP](i18n/TROUBLESHOOTING-JP.md) |
| Rules Manual | [EN](RULES_USER_MANUAL.md) | [CN](i18n/RULES_USER_MANUAL-CN.md) | [JP](i18n/RULES_USER_MANUAL-JP.md) |
| Architecture | [EN](ARCHITECTURE.md) | [CN](i18n/ARCHITECTURE-CN.md) | [JP](i18n/ARCHITECTURE-JP.md) |
| API Reference | [EN](API_REFERENCE.md) | [CN](i18n/API_REFERENCE-CN.md) | [JP](i18n/API_REFERENCE-JP.md) |
| API Stability | [EN](API_STABILITY.md) | [CN](i18n/API_STABILITY-CN.md) | [JP](i18n/API_STABILITY-JP.md) |
| Roadmap | [EN](ROADMAP.md) | [CN](i18n/ROADMAP-CN.md) | [JP](i18n/ROADMAP-JP.md) |

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
1. Run `bash scripts/install.sh` for one-click install
2. Read [Quick Start Guide](QUICK_START_GUIDE.md)

### Scenario 2: Installation issues
1. Run `carrymem doctor` for diagnostics
2. Check [Quick Start Guide](QUICK_START_GUIDE.md) FAQ section

### Scenario 3: Configure MCP integration
1. Run `carrymem setup-mcp --tool claude-code`
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
carrymem setup-mcp --tool claude-code # MCP configuration
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
├── TROUBLESHOOTING.md                  # Troubleshooting guide
├── INSTALL.md                          # Install guide
├── ARCHITECTURE.md                    # Architecture
├── API_REFERENCE.md                   # API reference
├── API_STABILITY.md                   # API stability guarantees
├── RULES_USER_MANUAL.md               # Rules engine manual
├── ROADMAP.md                         # Roadmap
├── archive/                           # Archived documents
│   └── review/                        # Internal review documents
└── i18n/                              # Internationalized documents
    ├── README-CN.md                   # Chinese README
    ├── README-JP.md                   # Japanese README
    ├── INSTALL-CN.md                  # Chinese install guide
    ├── INSTALL-JP.md                  # Japanese install guide
    ├── QUICK_START_GUIDE-CN.md        # Chinese quick start
    ├── QUICK_START_GUIDE-JP.md        # Japanese quick start
    ├── USER_GUIDE-CN.md               # Chinese user guide
    ├── USER_GUIDE-JP.md               # Japanese user guide
    ├── TROUBLESHOOTING-CN.md          # Chinese troubleshooting
    ├── TROUBLESHOOTING-JP.md          # Japanese troubleshooting
    ├── RULES_USER_MANUAL-CN.md        # Chinese rules manual
    ├── RULES_USER_MANUAL-JP.md        # Japanese rules manual
    ├── ARCHITECTURE-CN.md             # Chinese architecture
    ├── ARCHITECTURE-JP.md             # Japanese architecture
    ├── API_REFERENCE-CN.md            # Chinese API reference
    ├── API_REFERENCE-JP.md            # Japanese API reference
    ├── API_STABILITY-CN.md            # Chinese API stability
    ├── API_STABILITY-JP.md            # Japanese API stability
    ├── ROADMAP-CN.md                  # Chinese roadmap
    └── ROADMAP-JP.md                  # Japanese roadmap
```

---

## 🆘 Get Help

### Having Issues?
1. **Run diagnostics**: `carrymem doctor`
2. **Check troubleshooting**: [Troubleshooting Guide](TROUBLESHOOTING.md) | [中文版](i18n/TROUBLESHOOTING-CN.md) | [日本語版](i18n/TROUBLESHOOTING-JP.md)
3. **Read docs**: [Quick Start Guide](QUICK_START_GUIDE.md)

### Report Issues
- GitHub Issues: [Submit Issue](https://github.com/lulin70/carrymem/issues)

---

**Last Updated**: 2026-05-03  
**Maintainer**: CarryMem Team
