# CarryMem Architecture

**Version**: v0.1.5
**Date**: 2026-05-01
**Status**: Stable

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Layer Design](#layer-design)
4. [Data Flow](#data-flow)
5. [Key Components](#key-components)
6. [Rules Engine](#rules-engine)
7. [Context Engineering](#context-engineering)
8. [Extension Mechanisms](#extension-mechanisms)
9. [Performance Optimization](#performance-optimization)
10. [Security Design](#security-design)

---

## System Overview

### Design Philosophy

CarryMem uses a **layered architecture + plugin design**:

1. **Zero-config**: Works out of the box, auto-initializes
2. **High performance**: 60%+ zero-cost classification, FTS5 full-text search
3. **Extensible**: Adapter pattern supports multiple storage backends
4. **Cross-platform**: Pure Python, minimal external dependencies

### Core Value

```
User Input → Auto-Classify → Smart Store → Semantic Recall
   ↓              ↓              ↓             ↓
 Simple       90%+ accuracy   Dedup+TTL    <100ms
```

---

## Core Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Python   │  │   CLI    │  │   MCP    │              │
│  │   API    │  │  Tool    │  │  Server  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   API Layer                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │              CarryMem (Main Entry)                │  │
│  │  - classify_and_remember()  - recall_memories()   │  │
│  │  - declare()  - forget_memory()                   │  │
│  │  - export_memories()  - import_memories()         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Classification Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Rule Engine │  │   Pattern    │  │   Semantic   │ │
│  │ (Zero-cost)  │  │  Analyzer    │  │  Classifier  │ │
│  │    60%+      │  │    ~30%      │  │    <10%      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               Storage Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   SQLite     │  │   Obsidian   │  │   Custom     │ │
│  │  (Default)   │  │   (Plugin)   │  │  (Adapter)   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               Recall Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  FTS5 Search │  │   Semantic   │  │    Result    │ │
│  │  (Exact)     │  │   Expander   │  │    Merger    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Layer Design

### 1. User Layer

**Responsibility**: Provide multiple interaction methods

#### 1.1 Python API
```python
from memory_classification_engine import CarryMem

with CarryMem() as cm:
    cm.classify_and_remember("I prefer dark mode")
    memories = cm.recall_memories(query="theme")
```

#### 1.2 CLI Tool
```bash
carrymem init
carrymem list
carrymem stats
```

#### 1.3 MCP Server
```json
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "memory_classification_engine.integration.layer2_mcp"]
    }
  }
}
```

### 2. API Layer

**Responsibility**: Unified business logic entry point

#### Core Class: CarryMem

```python
class CarryMem:
    def __init__(
        self,
        storage: Optional[Any] = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict] = None,
    ): ...

    def classify_and_remember(self, message, context=None, language=None) -> Dict: ...
    def recall_memories(self, query=None, filters=None, limit=20) -> List[Dict]: ...
    def forget_memory(self, memory_id: str) -> bool: ...
    def declare(self, message: str) -> Dict: ...
    def get_memory_profile(self) -> Dict: ...
    def export_memories(self, output_path=None, format="json", namespace=None) -> Dict: ...
    def import_memories(self, input_path=None, merge_strategy="skip", namespace=None) -> Dict: ...
    def build_system_prompt(self, context=None, max_memories=10, max_knowledge=5, language="en") -> str: ...
```

### 3. Classification Layer

**Responsibility**: Auto-identify memory types

#### Three-Tier Classification Strategy

```
Input → Rule Engine (60%+) → Pattern Analyzer (~30%) → Semantic Classifier (<10%)
          ↓                       ↓                         ↓
      Zero cost             Near-zero cost             Token cost
      High speed            Medium speed               Low speed
```

#### 3.1 Rule Engine (RuleMatcher)

Pattern-based classification using regex and keywords. Zero cost, covers ~60% of inputs.

#### 3.2 Pattern Analyzer (PatternAnalyzer)

NLP-based pattern analysis. Near-zero cost, covers ~30% of inputs.

#### 3.3 Semantic Classifier (SemanticClassifier)

LLM-based classification for ambiguous cases. Token cost, covers <10% of inputs.

### 4. Storage Layer

**Responsibility**: Persistence and retrieval

#### 4.1 Adapter Interface

```python
class StorageAdapter(ABC):
    @abstractmethod
    def remember(self, entry: MemoryEntry) -> StoredMemory: ...

    @abstractmethod
    def recall(self, query: str, filters=None, limit=20, namespaces=None) -> List[StoredMemory]: ...

    @abstractmethod
    def forget(self, storage_key: str) -> bool: ...
```

#### 4.2 SQLite Adapter

**Features**:
- FTS5 full-text search with trigram tokenizer
- Content deduplication (content_hash)
- TTL auto-expiry
- Transaction support (BEGIN/COMMIT/ROLLBACK)
- Thread safety (threading.Lock + threading.local)

**Database Schema**:
```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    original_message TEXT,
    confidence REAL NOT NULL,
    tier INTEGER NOT NULL,
    namespace TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    access_count INTEGER,
    content_hash TEXT NOT NULL,
    metadata TEXT
);

CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    original_message,
    tokenize='trigram'
);
```

### 5. Recall Layer

**Responsibility**: Smart retrieval and result optimization

#### 5.1 Recall Pipeline

```
Query → FTS5 Search → Semantic Expansion → Result Fusion → Sort → Return
  ↓         ↓              ↓                 ↓           ↓       ↓
Validate  Exact match  Synonym expand    Dedup     Relevance  Top-K
```

#### 5.2 Semantic Expansion

Zero-dependency semantic expansion:
- **Synonym expansion**: YAML-based synonym graph (470+ terms, CN/EN/JP)
- **Spell correction**: Levenshtein edit distance
- **Cross-language mapping**: CN↔EN↔JP term mapping

#### 5.3 Result Fusion

```python
class ResultMerger:
    def merge(self, original_results, expanded_results, query, limit=20, source="synonym"):
        # 1. Deduplicate by storage_key
        # 2. Calculate relevance score
        # 3. Sort by relevance
        # 4. Return top-K
```

---

## Data Flow

### Store Flow

```
1. User Input
   ↓
2. Input Validation
   ↓
3. Classification (Rule → Pattern → Semantic)
   ↓
4. Create MemoryEntry
   ↓
5. Calculate content_hash
   ↓
6. Check duplicate
   ↓
7. Store to database
   ↓
8. Update FTS5 index
   ↓
9. Return result
```

### Recall Flow

```
1. User Query
   ↓
2. Query Validation
   ↓
3. FTS5 Search
   ↓
4. Results insufficient? → Semantic Expansion
   ↓
5. Result Fusion
   ↓
6. Dedup + Sort
   ↓
7. Update access_count
   ↓
8. Return Top-K
```

---

## Key Components

### 1. Configuration

```python
# Default config
CarryMem(storage="sqlite", db_path=None, namespace="default")

# Custom storage
CarryMem(storage=SQLiteAdapter(db_path="/custom/path.db"))

# With knowledge base
CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
```

### 2. Exception Hierarchy

```python
class CarryMemError(Exception):
    """Base exception"""

class StorageError(CarryMemError):
    """Storage error"""

class DatabaseError(StorageError):
    """Database error"""

class ValidationError(CarryMemError):
    """Validation error"""
```

### 3. Logging

```python
from memory_classification_engine.utils.logger import logger

# Log levels: DEBUG, INFO, WARNING, ERROR
# File: ~/.carrymem/logs/carrymem.log (if configured)
```

---

## Rules Engine

### Architecture Overview

The Rules Engine is CarryMem's behavioral contract system, converting memories into actionable rules.

```
┌─────────────────────────────────────────────────────────────┐
│                    Rules Engine               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Rule Sources:                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  Manual CRUD │ │  Auto        │ │  Experience  │        │
│  │      │ │  Promotion   │ │  Learning    │        │
│  │              │ │      │ │      │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │  Q&A         │ │  Templates   │                          │
│  │  Refinement  │ │      │                          │
│  │      │ │              │                          │
│  └──────────────┘ └──────────────┘                          │
│                                                              │
│  Core Pipeline:                                              │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐    │
│  │ Sanitize│ → │  Limit  │ → │  Store  │ → │  Match  │    │
│  │ (input) │   │ (usage) │   │ (SQLite)│   │ (FTS5)  │    │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘    │
│       ↓                                          ↓          │
│  ┌─────────┐   ┌──────────────┐   ┌─────────────────┐     │
│  │ Conflict│   │   Inject     │   │   Audit Trail   │     │
│  │ Detect  │   │ (format for  │   │ (promotion_audit│     │
│  │         │   │  LLM prompt) │   │  experience_audit│     │
│  └─────────┘   └──────────────┘   │  refinement_    │     │
│                                     │  sessions)      │     │
│                                     └─────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Rule Model

```python
class Rule:
    id: str                    # rule_xxxxxxxx
    trigger: str               # Scene description (FTS5 indexed)
    action: str                # What to do when triggered
    rule_type: str             # forbid | avoid | always | prefer | format
    override: bool             # True = cannot be overridden
    status: str                # active | paused | deprecated
    derived_from: str          # manual | auto_promotion | failure_lesson | refined | refinement_session
    source_memories: List[str] # Originating memory IDs
    confidence: float          # 0.0-1.0
    created_at: str
    updated_at: str
```

### Rule Lifecycle

```
Create → Active → Paused → Deprecated
  ↑        ↓
  └── Resume

Derivation paths:
  Manual : User explicitly creates via CLI or API
  Auto-Promotion : Pattern detection → Candidate → User confirms
  Experience Learning : Failure signal → Lesson → User confirms
  Q&A Refinement : Specific rule → Multi-turn dialogue → General rule
```

### Conflict Detection

Three types of conflicts detected:

| Conflict Type | Severity | Example |
|--------------|----------|---------|
| **Contradiction** | HIGH | "always use React" vs "never use React" |
| **Overlap** | MEDIUM | "prefer PostgreSQL" vs "prefer MySQL" (same trigger) |
| **Redundancy** | LOW | "avoid MongoDB" vs "avoid document databases" |

### Security Layers

1. **Sanitizer** : Prompt injection detection, SQL injection blocking, length limits
2. **Limiter** : Global rule cap (3), total cap (200), rate limiting
3. **Auto-Promotion Safety** : User confirmation required, expiry, queue limits
4. **Experience Safety** : Duplicate detection, sanitizer validation, audit trail
5. **Refinement Safety** : Max rounds, session expiry, sanitizer validation

---

## Context Engineering

### Problem: Lost-in-the-Middle Effect

LLM attention follows a U-curve pattern — high at the start and end of context, significantly lower in the middle. Research shows 10-40% recall drop for information placed in the middle of long contexts.

This directly impacts CarryMem's rule injection: if critical override rules are placed in the middle of the injected prompt, they may be ignored by the LLM.

### Solution: Anchored Layout Mode 

```
┌─────────────────────────────────────────────────┐
│ HEAD ANCHOR (highest attention)                  │
│ ┌─────────────────────────────────────────────┐ │
│ │ Absolute Prohibitions (override + forbid)   │ │
│ │ - Never cite competitor data w/o verification│ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ MIDDLE (lower attention)                         │
│ ┌─────────────────────────────────────────────┐ │
│ │ Recommended (override=false)                │ │
│ │ - Prefer domestic warehouses                │ │
│ │ - Confirm inventory by phone                │ │
│ └─────────────────────────────────────────────┘ │
│                                                  │
│ TAIL ANCHOR (high attention)                     │
│ ┌─────────────────────────────────────────────┐ │
│ │ Mandatory Actions (override + always)       │ │
│ │ - All quotes must include validity period   │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

Implementation in `format_rules_as_prompt()`:
```python
def format_rules_as_prompt(
    matches: List[MatchResult],
    style: str = "default",     # "default" | "ddd" | "anchored"
    context_budget_tokens: int = 2000,
) -> str:
    if style == "anchored":
        # Sort: head=override+forbid, middle=normal, tail=override+always
        head = [m for m in matches if m.override and m.rule_type == "forbid"]
        middle = [m for m in matches if not m.override]
        tail = [m for m in matches if m.override and m.rule_type == "always"]
        ...
```

### DDD Language View

CarryMem concepts can be expressed in Domain-Driven Design terminology, enabling enterprise architect dialogue:

| CarryMem Concept | DDD Equivalent | Relationship |
|-----------------|---------------|-------------|
| trigger | Bounded Context | Defines scope boundary |
| rule_type: forbid | Aggregate Invariant | Cannot be violated |
| rule_type: always | Consistency Guarantee | Must be satisfied |
| rule_type: avoid/prefer | Soft Constraint | Best-effort compliance |
| override | Invariant Flag | Cannot be overridden by higher priority |
| source_memories | Event Sourcing Chain | Rule traceable to originating experience |
| refine process | Ubiquitous Language Refinement | Specific → General abstraction |

### Context Budget Monitoring

When rule injection approaches context window limits:

1. **Token estimation**: Rough token count = len(text) / 4 (English) or len(text) / 2 (CJK)
2. **Compression strategy**: Override rules preserved, avoid rules compressed to one-line summaries
3. **Threshold**: 70% of `context_budget_tokens` triggers compression

---

## Extension Mechanisms

### 1. Custom Storage Adapter

```python
from memory_classification_engine.adapters import StorageAdapter

class PostgreSQLAdapter(StorageAdapter):
    def remember(self, entry: MemoryEntry) -> StoredMemory: ...
    def recall(self, query: str, **kwargs) -> List[StoredMemory]: ...
    def forget(self, storage_key: str) -> bool: ...

# Usage
cm = CarryMem(storage=PostgreSQLAdapter("postgresql://..."))
```

### 2. Plugin System

```python
# setup.py
entry_points={
    "carrymem.adapters": [
        "postgresql=my_plugin:PostgreSQLAdapter",
    ],
}

# Dynamic loading
cm = CarryMem(storage="postgresql")
```

---

## Performance Optimization

### 1. Query Optimization

**Index Strategy**:
- Single column: type, namespace, content_hash
- Composite: (namespace, type), (namespace, tier)
- FTS5: trigram tokenizer

### 2. Batch Operations

```python
# Atomic batch with transaction
adapter.remember_batch(entries)
# → BEGIN → INSERT... → COMMIT (or ROLLBACK on error)
```

### 3. Thread Safety

```python
# ThreadLocal connections + Lock
adapter = SQLiteAdapter()  # Thread-safe by default
```

---

## Security Design

### 1. Input Validation

All inputs validated via `validators.py`:
- Message length limits
- Namespace character whitelist
- Storage key format validation
- Query length limits

### 2. SQL Injection Prevention

All queries use parameterized statements (`?` placeholders).

### 3. Path Safety

```python
# Path traversal prevention
def _validate_file_path(path: str) -> str:
    if ".." in path:
        raise ValueError("Path traversal not allowed")
    return os.path.realpath(os.path.expanduser(path))
```

### 4. MCP Handler Safety

- Exception sanitization: internal errors never exposed to clients
- Parameter clamping: limit, max_memories, max_knowledge all bounded
- Language whitelist: only "en", "zh", "ja" accepted

---

## Summary

CarryMem uses a **layered architecture + plugin design**, achieving:

✅ **High Performance**: FTS5 + indexing + caching
✅ **Extensible**: Adapter pattern + plugin system
✅ **Easy to Use**: Zero config + CLI tools
✅ **Secure**: Input validation + parameterized queries + path safety
