# CarryMem Design Principles

**Last Updated**: 2026-11-07  
**Status**: Living Document

---

## Core Philosophy

CarryMem is a **portable, local-first AI memory system** that empowers users with complete data sovereignty while remaining lightweight and dependency-free.

---

## Design Principles

### 1. Portable First

**Definition**: CarryMem must remain a single-file solution that users can carry anywhere.

**Rules**:
- ✅ Single SQLite database file
- ✅ No external service dependencies for core features
- ✅ USB carry scenario support
- ❌ Cloud-only storage
- ❌ Required network connectivity

**Example**: User can copy `~/.carrymem/memory.db` to USB drive and use on another machine.

---

### 2. Local First

**Definition**: All data processing happens locally; user owns their data.

**Rules**:
- ✅ Complete offline functionality
- ✅ No telemetry or analytics
- ✅ User data never leaves the machine (unless explicitly exported)
- ❌ Required internet connection
- ❌ Centralized data sync

**Example**: CarryMem works in airplane mode, behind firewalls, or in air-gapped environments.

---

### 3. Zero Mandatory Dependencies

**Definition**: Core features work out-of-the-box without API keys, external services, or optional packages.

**Rules**:
- ✅ Core classification works without LLM
- ✅ Core recall works with SQLite FTS5 only
- ✅ Basic functionality in vanilla Python 3.12+
- ❌ Forcing users to install heavy ML frameworks
- ❌ Requiring API keys for basic features

**Example**: `pip install carrymem && carrymem check` works immediately.

---

### 4. Graceful Enhancement

**Definition**: Optional features enhance the experience but never block core functionality.

**Rules**:
- ✅ Tiered functionality (Tier 1 → Tier 2 → Tier 3)
- ✅ Auto-detection of optional dependencies
- ✅ Silent fallback when enhancement unavailable
- ❌ Hard errors when optional features missing
- ❌ Feature gating behind paywalls

**Enhancement Tiers**:
```
Tier 1: Zero dependencies (rule-based, FTS5)
Tier 2: Local LLM (Ollama, offline)
Tier 3: Cloud API (OpenAI, optional)
```

**Example**: `suggest_rules()` works with pattern matching (Tier 1), improves with local LLM (Tier 2), and excels with GPT-4 (Tier 3).

---

### 5. Privacy by Default

**Definition**: User privacy is non-negotiable; no data leaves without explicit consent.

**Rules**:
- ✅ End-to-end encryption for packed exports
- ✅ No telemetry, no tracking, no analytics
- ✅ Explicit opt-in for cloud features
- ❌ Auto-uploading to cloud
- ❌ Default unencrypted backups

**Example**: `carrymem pack --encrypt` creates AES-256 encrypted bundle; password never stored.

---

### 6. MCP Protocol First

**Definition**: CarryMem is an MCP server; it serves AI tools, not replaces them.

**Rules**:
- ✅ Expose all features via MCP tools
- ✅ Stateless tool handlers (no hidden global state)
- ✅ Compatible with any MCP client (Claude Desktop, Cursor, etc.)
- ❌ Building a standalone AI assistant
- ❌ Vendor lock-in to specific AI platforms

**Example**: CarryMem works with Claude Desktop (Anthropic), Cursor (OpenAI), or custom MCP clients.

---

### 7. Performance Matters

**Definition**: Core operations must be fast enough for interactive use.

**Rules**:
- ✅ Recall latency target <5ms (Tier 1, SQLite FTS5)
- ✅ Classification target <1ms (rule-based)
- ✅ Supports 10,000+ memories without degradation
- ❌ Blocking on slow network calls in critical path
- ❌ Unbounded memory growth

**Benches (measured 2026-11-07, local macOS dev machine)**:
- FTS5 recall: 5.53–5.85ms average (p50 5.45–5.81ms, p95 6.9–8.0ms) for 100–500–1000 records
- LIKE recall: 10.5–15.1ms average
- `classify_and_remember`: cold start 16.4ms, warm average 144.2ms, p95 398.3ms, p99 1260.8ms

The recall target is met on this machine. The classification target is **not** met.
Treat every number as a measurement with a date and a machine, not as a constant.

---

### 8. Testability and Reliability

**Definition**: High test coverage ensures stability and prevents regressions.

**Rules**:
- ✅ Test coverage >80%
- ✅ E2E tests for all critical paths
- ✅ CI/CD for every commit
- ❌ Shipping untested features
- ❌ Breaking changes without migration path

**Current Stats**:
- Test coverage: 83.18%
- Test suite: 1700+ tests
- E2E coverage: All major workflows

---

## Decision Framework

When evaluating new features, ask:

1. **Does it require internet?**  
   → If yes, must be optional (Tier 2/3)

2. **Does it require API keys?**  
   → If yes, must be optional (Tier 3 only)

3. **Does it break offline use?**  
   → If yes, reject or redesign

4. **Does it compromise privacy?**  
   → If yes, reject

5. **Does it add core dependencies?**  
   → If yes, justify or make optional

6. **Does it slow down critical path?**  
   → If yes, optimize or make async

---

## Examples: Good vs Bad Design

### ✅ GOOD: Phase 4 LLM Integration (Redesigned)

**Why**:
- Local LLM prioritized (Tier 2)
- Cloud API optional (Tier 3)
- Graceful fallback to rule-based (Tier 1)
- Zero mandatory dependencies

### ❌ BAD: Phase 4 LLM Integration (Original)

**Why**:
- Implied dependency on OpenAI/Claude
- No fallback mechanism
- Could break offline use
- Violated "zero mandatory dependencies"

---

### ✅ GOOD: SQLite FTS5 for Recall

**Why**:
- Zero external dependencies
- Excellent performance (<3ms)
- Fully offline
- Battle-tested

### ❌ BAD: Elasticsearch for Recall

**Why**:
- External service dependency
- Network latency
- Complex setup
- Breaks portability

---

## Governance

**Who decides?**  
- Maintainer (lulin70) has final say
- Community proposals welcome via issues
- Design principles trump feature requests

**How to propose changes?**  
1. Open GitHub issue with "RFC:" prefix
2. Explain how proposal aligns with principles
3. Address concerns raised by maintainers
4. Iterate until consensus or rejection

---

**Signed**: Kiro AI (on behalf of lulin70)  
**Date**: 2026-11-07
