# CarryMem Documentation Hub

**Version**: v0.11.2
**Last Updated**: 2026-09-21

New here? Start with the [Quick Start Guide](QUICK_START_GUIDE.md).
Want to know where the project actually stands? Read [Project Status](PROJECT_STATUS.md).

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

## 📚 Documentation Index

### For users

| Document | Description |
|----------|-------------|
| [Quick Start Guide](QUICK_START_GUIDE.md) | Get started in 5 minutes |
| [Install Guide](INSTALL.md) | Detailed installation instructions |
| [User Guide](USER_GUIDE.md) | Complete usage guide |
| [Rules User Manual](RULES_USER_MANUAL.md) | Rule engine usage guide |
| [Troubleshooting](TROUBLESHOOTING.md) | Diagnose and fix common issues |

### For developers and contributors

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | Core architecture — Mixin coupling governance (P0-1) |
| [Module Boundaries](MODULE_BOUNDARIES.md) | Module boundary visualisation |
| [API Reference](API_REFERENCE.md) | API interface documentation (Chinese) |
| [API Stability](API_STABILITY.md) | API stability guarantees |
| [Error Handling Guide](ERROR_HANDLING_GUIDE.md) | Error handling conventions |
| [Entry Points](ENTRY_POINTS.md) | CLI / TUI / MCP feature parity matrix |
| [Dependency Audit](DEPENDENCY_AUDIT.md) | Dependency security audit |
| [Contributing Guide](../CONTRIBUTING.md) | How to contribute |

### Project status and process

| Document | Description |
|----------|-------------|
| [Project Status](PROJECT_STATUS.md) | Current release, release evidence, open follow-ups |
| [Roadmap](ROADMAP.md) | Product roadmap |
| [Technical Debt Plan](TECH_DEBT_PLAN.md) | Living technical debt tracker |
| [P0–P3 Debt Roadmap](ROADMAP_P0_P3.md) | Wave-by-wave debt execution plan |
| [Release Runbook](RELEASE_RUNBOOK.md) | Release and rollback procedure |
| [Project Review](PROJECT_REVIEW.md) | v0.8.0 consolidation assessment (historical) |

### Research and benchmarks

| Document | Description |
|----------|-------------|
| [External Memory Benchmarks](EXTERNAL_MEMORY_BENCHMARKS.md) | External benchmark evaluation plan |
| [MSC Benchmark Guide](MSC_BENCHMARK_GUIDE.md) | MSC official benchmark guide |
| [Competitive Analysis](COMPETITIVE_ANALYSIS_MEMORY_GRAPH.md) | Memory graph design-space positioning |
| [Architecture Evolution Plan](CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md) | Long-term architecture evolution |
| [Obsidian Adapter](OBSIDIAN_ADAPTER.md) | Obsidian integration |

### Versioned records

| Directory | Contents |
|-----------|----------|
| [design/](design/) | Per-version design documents, retrospectives and reviews |
| [runbooks/](runbooks/) | Per-version operational runbooks |
| [architecture/decisions/](architecture/decisions/) | ADR-001 … ADR-013 |
| [spec/](spec/) | Implementation specs (v0.5.0, v0.5.2) |
| [archive/](archive/) | Superseded plans and historical assessments |

---

## 🌐 Translations (`i18n/`)

| Document | EN | CN | JP | KO | ZH-TW |
|----------|----|----|----|----|-------|
| README | [EN](../README.md) | [CN](i18n/README-CN.md) | [JP](i18n/README-JP.md) | [KO](i18n/README-KO.md) | [ZH-TW](i18n/README-ZH-TW.md) |
| Install Guide | [EN](INSTALL.md) | [CN](i18n/INSTALL-CN.md) | [JP](i18n/INSTALL-JP.md) | [KO](i18n/INSTALL-KO.md) | [ZH-TW](i18n/INSTALL-ZH-TW.md) |
| Quick Start | [EN](QUICK_START_GUIDE.md) | [CN](i18n/QUICK_START_GUIDE-CN.md) | [JP](i18n/QUICK_START_GUIDE-JP.md) | — | — |
| User Guide | [EN](USER_GUIDE.md) | [CN](i18n/USER_GUIDE-CN.md) | [JP](i18n/USER_GUIDE-JP.md) | — | — |
| Troubleshooting | [EN](TROUBLESHOOTING.md) | [CN](i18n/TROUBLESHOOTING-CN.md) | [JP](i18n/TROUBLESHOOTING-JP.md) | — | — |
| Rules Manual | [EN](RULES_USER_MANUAL.md) | [CN](i18n/RULES_USER_MANUAL-CN.md) | [JP](i18n/RULES_USER_MANUAL-JP.md) | — | — |
| API Stability | [EN](API_STABILITY.md) | [CN](i18n/API_STABILITY-CN.md) | [JP](i18n/API_STABILITY-JP.md) | — | — |
| Roadmap | [EN](ROADMAP.md) | [CN](i18n/ROADMAP-CN.md) | [JP](i18n/ROADMAP-JP.md) | [KO](i18n/ROADMAP-KO.md) | [ZH-TW](i18n/ROADMAP-ZH-TW.md) |

**Architecture and API Reference have no English edition.** Both root files are
written in Chinese, and the `i18n/` copies are separate, longer documents rather
than translations of them:

| Document | Root (Chinese) | `i18n/` (separate document) |
|----------|----------------|-----------------------------|
| Architecture | [Mixin coupling governance](ARCHITECTURE.md), 208 lines | [架构设计](i18n/ARCHITECTURE-CN.md), 879 lines · [JP](i18n/ARCHITECTURE-JP.md), 882 lines |
| API Reference | [API 参考手册（中文版）](API_REFERENCE.md), 1492 lines | [API 参考](i18n/API_REFERENCE-CN.md), 1274 lines · [JP](i18n/API_REFERENCE-JP.md), 1266 lines |

These two pairs are queued for consolidation; see [Project Status](PROJECT_STATUS.md).

---

## 🛠️ Core Features

### 1. Smart Memory Classification
```bash
carrymem add "I prefer dark mode"
```
Auto-classified into 7 types: user_preference, correction, fact_declaration, decision, relationship, task_pattern, sentiment_marker.
(Session summaries are a separate 8th stored type, produced by `summarize_and_store`, not by the classifier.)

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
- Fernet (AES-128-CBC + HMAC) encrypted storage — the single supported backend
  since v0.7.3 ([ADR-011](architecture/decisions/ADR-011-fernet-only-encryption.md))
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
3. Read [Project Status](PROJECT_STATUS.md) for the release-level view

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

The full CLI / TUI / MCP parity matrix lives in [Entry Points](ENTRY_POINTS.md).

---

## 📁 Documentation Directory Structure

```
docs/
├── README.md                          # This document (docs index)
├── QUICK_START_GUIDE.md               # Quick start
├── INSTALL.md                         # Install guide
├── USER_GUIDE.md                      # User guide
├── RULES_USER_MANUAL.md               # Rules engine manual
├── TROUBLESHOOTING.md                 # Troubleshooting guide
├── ARCHITECTURE.md                    # Core architecture (Mixin coupling governance)
├── MODULE_BOUNDARIES.md               # Module boundary visualisation
├── API_REFERENCE.md                   # API reference (Chinese)
├── API_STABILITY.md                   # API stability guarantees
├── ERROR_HANDLING_GUIDE.md            # Error handling conventions
├── ENTRY_POINTS.md                    # CLI / TUI / MCP parity matrix
├── DEPENDENCY_AUDIT.md                # Dependency security audit
├── OBSIDIAN_ADAPTER.md                # Obsidian integration
├── PROJECT_STATUS.md                  # Release state and open follow-ups
├── PROJECT_REVIEW.md                  # v0.8.0 consolidation assessment
├── ROADMAP.md                         # Product roadmap
├── ROADMAP_P0_P3.md                   # P0-P3 debt roadmap (living)
├── TECH_DEBT_PLAN.md                  # Technical debt plan (living)
├── RELEASE_RUNBOOK.md                 # Release and rollback runbook
├── CARRYMEM_ARCHITECTURE_EVOLUTION_PLAN.md
├── COMPETITIVE_ANALYSIS_MEMORY_GRAPH.md
├── EXTERNAL_MEMORY_BENCHMARKS.md
├── MSC_BENCHMARK_GUIDE.md
├── architecture/decisions/            # ADR-001 … ADR-013
├── design/                            # Per-version design docs and reviews
├── runbooks/                          # Per-version operational runbooks
├── spec/                              # Implementation specs
├── archive/                           # Superseded plans and assessments
└── i18n/                              # Translations (CN / JP / KO / ZH-TW)
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

**Last Updated**: 2026-09-21
**Maintainer**: CarryMem Team
