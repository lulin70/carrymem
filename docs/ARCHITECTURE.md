# CarryMem Architecture

**Version**: v0.2.4
**Date**: 2026-05-27
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
8. [Concurrent Safety](#concurrent-safety)
9. [Auto-Backup Architecture](#auto-backup-architecture)
10. [.carry File Format](#carry-file-format)
11. [Extension Mechanisms](#extension-mechanisms)
12. [Performance Optimization](#performance-optimization)
13. [Security Design](#security-design)

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
User Input → Auto-Classify → Smart Store → Semantic Recall → Proactive Inject
   ↓              ↓              ↓             ↓              ↓
 Simple       90%+ accuracy   Dedup+TTL    <100ms      AI knows who you are
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
│  │  - recall_aggregated()      - recall_timeline()   │  │
│  │  - declare()  - forget_memory()                   │  │
│  │  - export_memories()  - import_memories()         │  │
│  │  Note: classify_and_remember(session_id=...)      │  │
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
                         ↓
┌─────────────────────────────────────────────────────────┐
│            Consolidation Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  P0: Dedup   │  │  P1: Pattern │  │  P2: Semantic│ │
│  │  + Decay     │  │  → Rules     │  │  Merge       │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Layer Design

### 1. User Layer

**Responsibility**: Provide multiple interaction methods

#### 1.1 Python API
```python
from carrymem import CarryMem

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
      "args": ["-m", "carrymem.integration.layer2_mcp"]
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
    raw_text TEXT,              -- NEW: Verbatim user input for FTS5 dual-index
    confidence REAL NOT NULL,
    tier INTEGER NOT NULL,
    namespace TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    access_count INTEGER,
    content_hash TEXT NOT NULL,
    metadata TEXT,
    superseded_at TEXT,         -- NEW: When this memory was superseded
    supersedes TEXT             -- NEW: Which memory this replaces
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

### 6. Knowledge Lifecycle Layer

**Responsibility**: Track knowledge evolution and manage memory supersession

#### 6.1 Auto-Supersession Pipeline

```
New Memory → Jaccard Similarity Check → Contradiction Detection → Mark Old as Superseded
     ↓              ↓                        ↓                         ↓
  INSERT      ≥ 0.25 threshold      Word boundary regex         superseded_at = now
              + Update marker detection      (like/dislike, etc.)        supersedes = new_key
              detection              + Assistant exclusion
```

#### 6.2 Session-Aware Storage

```
classify_and_remember(session_id="s_20260513")
     ↓
session_id → metadata JSON → session_id filter in recall()
```

#### 6.3 Time Expression Parsing

```
Query: "What did I recently decide about databases?"
     ↓
_parse_time_expressions() → created_after = 7 days ago
     ↓
recall_memories(query="databases", filters={"created_after": "2026-05-06T..."})
```

#### 6.4 Structured Prompt Generation

```
Memories → Priority Classification → Structured Prompt
              ↓                         ↓
         MANDATORY (correction/decision)  → Head section
         IMPORTANT (high confidence)       → Middle section
         OUTDATED (superseded)            → Tail section with update notes
```

### 7. LLM-Augmented Layer

**Responsibility**: LLM-powered session summarization and semantic aggregation (optional, requires API key)

- **Consolidation Engine** (`consolidation.py`): Memory lifecycle management with three phases:
  - P0: Jaccard-based deduplication (≥0.85) + exponential half-life decay
  - P1: Pattern detection → rule candidate generation via PromotionPipeline
  - P2: Semantic clustering → host LLM consolidation requests
  - Preferences are always preserved (never decayed or deduplicated)

#### 7.1 LLM Client Abstraction

```
Environment Variables → LLMClient → OpenAI/ZhipuAI/vLLM
     ↓                     ↓              ↓
CARRYMEM_LLM_*      Lazy-cached      chat(prompt) → str
CARRYMEM_LLM_API_KEY  instance       is_available() → bool
CARRYMEM_LLM_MODEL                   count_tokens() → int
```

#### 7.2 Session Summarizer Pipeline

```
Session Memories → Prioritize (correction/decision > preference > other)
     ↓                    ↓
Exclude superseded    Cap at 50 memories
     ↓
LLM available? ──Yes──→ LLM Summarize → session_summary (confidence: 0.9)
     │
     No
     ↓
Rule-based Concat → session_summary (confidence: 0.7)
     ↓
Store with metadata: {session_id, source_memory_ids, summary_method}
```

#### 7.3 Semantic Aggregator Pipeline

```
All Active Memories → Embed (all-MiniLM-L6-v2)
     ↓
Pairwise Cosine Similarity Matrix
     ↓
Connected Component Clustering (DFS, threshold: 0.55)
     ↓
For each cluster (size ≥ 2):
  LLM available? ──Yes──→ LLM Merge → aggregated memory
       │
       No
       ↓
  Rule-based (latest + note) → aggregated memory
```

#### 7.4 Session Summary in Recall

```
recall_memories() → Exclude session_summary by default
                     (avoid noise from rule-based summaries)

build_context() → Include session_summary (top 3)
                   (cross-session context for decision support)

filters={"include_session_summary": True} → Explicit inclusion
filters={"type": "session_summary"}       → Type-specific query
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
3. Time Expression Parsing (NEW)
   ↓
4. FTS5 Search
   ↓
5. Results insufficient? → Context Rebuild (NEW)
   ↓
6. Result Fusion
   ↓
7. Dedup + Sort + Supersession Filter (NEW)
   ↓
8. Update access_count
   ↓
9. Return Top-K
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
from carrymem.utils.logger import logger

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

## Concurrent Safety

### Problem: Multi-Instance Write Contention

Multiple CarryMem instances (different AI Agent processes) may write to the same SQLite database file simultaneously. Without coordination, this leads to `database is locked` errors or data corruption.

### Solution: Per-File Write Lock

```
┌──────────────────────────────────────────────────────────┐
│              _db_write_locks (global dict)                │
│                                                           │
│  "/path/to/memories.db" → Lock A                         │
│  "/other/path/db.db"     → Lock B                        │
│  ...                                                      │
└──────────────────────────────────────────────────────────┘
         ↑                           ↑
    Instance 1 (Cursor)        Instance 2 (Claude Code)
    self._file_lock = A        self._file_lock = A
    (shares same Lock)         (shares same Lock)
```

**Implementation**:

```python
# Global registry: maps realpath → Lock
_db_write_locks: Dict[str, threading.Lock] = {}
_db_write_locks_guard = threading.Lock()  # guards dict itself

class SQLiteAdapter:
    def __init__(self, ...):
        resolved = str(os.path.realpath(self._db_path))
        with _db_write_locks_guard:
            if resolved not in _db_write_locks:
                _db_write_locks[resolved] = threading.Lock()
            self._file_lock = _db_write_locks[resolved]
```

**Lock Hierarchy**:

| Operation | Lock Used | Scope | Behavior |
|-----------|-----------|-------|----------|
| Write (remember/forget/update/recalculate/remember_batch) | `self._file_lock` | Cross-instance | Serializes all writes to the same DB file |
| Read (recall/list) | `self._lock` | Per-instance | Does not block reads from other instances |

**Secondary Protection**: WAL mode + `busy_timeout=10000ms`

```python
conn = sqlite3.connect(db_path, timeout=10.0)
conn.execute("PRAGMA journal_mode=WAL")
```

WAL mode allows concurrent reads while a write is in progress. The `busy_timeout` provides a 10-second window for lock acquisition before raising an error, handling edge cases where the per-file lock is insufficient (e.g., external processes).

---

## Auto-Backup Architecture

### Overview

CarryMem provides automatic, zero-downtime database backup to protect against data loss.

### Trigger Conditions

- **Interval-based**: Every N write operations (default: 20, configurable via `auto_backup_interval`)
- **Initial backup**: Automatically created when opening an existing database for the first time

```
Write Operation → _write_count += 1
     ↓
_write_count % auto_backup_interval == 0?
     ↓ Yes
BackupManager.create_backup()
```

### Backup Method: VACUUM INTO

```python
conn.execute("VACUUM INTO ?", (backup_path,))
```

- **Zero downtime**: Does not block reads or writes
- **Consistent snapshot**: SQLite-recommended backup method
- **Fallback**: If `VACUUM INTO` is not supported, falls back to `shutil.copy2`

### Backup Location and Naming

- **Directory**: `~/.carrymem/backups/` (configurable via `backup_dir` config)
- **File name format**: `memories_backup_YYYYMMDD_HHMMSS_微秒.db`
- **Permissions**: Directory `0o700`, backup files `0o600`

### Automatic Cleanup

- **Max backups**: 5 (configurable via `max_backups`)
- **Strategy**: FIFO — oldest backups are removed first
- **Timing**: Cleanup runs after each new backup is created

### Restore

```bash
carrymem backup --list              # List all backups
carrymem backup --restore <path>    # Restore from a backup
```

Restore process:
1. Validates the backup file (opens and queries it)
2. Creates a pre-restore safety copy (`.pre_restore.bak`)
3. Copies backup over the current database
4. On failure, rolls back from the safety copy

---

## .carry File Format

The `.carry` file is CarryMem's portable identity format for transferring memories across machines and tools.

### Version History

#### v1.0: Legacy Format

- Pure gzip-compressed JSON
- No checksum, no encryption support
- Structure: `gzip(json_data)`

#### v1.1: Container Format (Current)

```json
{
    "version": "1.1",
    "checksum": "<SHA-256 hex of payload before encryption>",
    "encrypted": false,
    "payload": "<base64(gzip(json_data)) or encrypted_string>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Format version (`"1.1"`) |
| `checksum` | string | SHA-256 hash of the JSON payload (before compression/encryption) |
| `encrypted` | boolean | Whether the payload is encrypted |
| `payload` | string | `base64(gzip(json))` if unencrypted, or encrypted string if encrypted |
| `encryption_backend` | string | (optional) Encryption backend used (`"fernet"` or `"hmac_ctr"`) |

### Pack Flow

```
Memory Data → JSON serialize → SHA-256 checksum
     ↓
Encrypted? ──Yes──→ MemoryEncryption.encrypt(json_string)
     │                    ↓
     No              encrypted payload
     ↓
base64(gzip(json_bytes)) = unencrypted payload
     ↓
Container {version, checksum, encrypted, payload}
     ↓
gzip(container_json) → .carry file
```

### Unpack Flow

```
.carry file → gzip decompress → parse JSON
     ↓
Has "payload" and "checksum" keys? ──Yes──→ v1.1 format
     │                                         ↓
     No                                   encrypted?
     ↓                                   ↓ Yes        ↓ No
v1.0 format                          Decrypt       base64 decode
(warn: legacy)                           ↓              ↓
                                    Verify SHA-256 checksum
                                         ↓
                                    gzip decompress → JSON parse → Memory Data
```

### Backward Compatibility

- v1.0 format files can still be unpacked
- A warning is displayed: `⚠ Legacy .carry format (no checksum verification available)`
- Unsupported version numbers are rejected with an error

### CLI Commands

```bash
carrymem pack                         # Pack identity (unencrypted)
carrymem pack --encrypt               # Pack with password-protected encryption
carrymem pack --output my_id.carry    # Custom output path
carrymem unpack identity.carry        # Unpack and restore
carrymem unpack identity.carry --replace  # Replace existing memories
```

---

## Extension Mechanisms

### 1. Custom Storage Adapter

```python
from carrymem.adapters import StorageAdapter

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
✅ **Knowledge Lifecycle**: Auto-supersession + session-aware + time reasoning
✅ **Structured Injection**: MANDATORY/IMPORTANT/OUTDATED priority labels
✅ **Concurrent Safety**: Per-file write lock + WAL mode + busy_timeout
✅ **Auto-Backup**: VACUUM INTO + interval trigger + FIFO cleanup
✅ **Portable Identity**: .carry format with SHA-256 checksum + optional encryption
