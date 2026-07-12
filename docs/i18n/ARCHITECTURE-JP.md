# CarryMem アーキテクチャ

**バージョン**: v0.7.2
**日付**: 2026-05-27
**状態**: 安定

---

## 目次

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

## システム概要

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

## コアアーキテクチャ

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
                         ↓
┌─────────────────────────────────────────────────────────┐
│          記憶統合レイヤー                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  P0: 重複排除│  │  P1: パターン│  │  P2: 意味    │ │
│  │  + 減衰      │  │  → ルール    │  │  マージ      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## レイヤー設計

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

NLPベースのパターン分析。ほぼゼロコスト、入力の約30%をカバー。

**アーキテクチャ**：階層型パターン管理システム（`carrymem.patterns`）を使用：

- **Pattern**（基底クラス）：コンパイル済み正規表現とメタデータ（言語、タイプ、信頼度、マッチ方法）。サブクラス：`NoisePattern`、`PreferencePattern`、`CorrectionPattern`、`FactPattern`、`TaskPattern`、`DecisionPattern`、`RelationshipPattern`、`SentimentPattern`、`LocationPattern`。
- **PatternGroup**：関連パターンの名前付きコレクション、言語インデックス付きルックアップ（例：`noise_ack`、`preference_strong`、`correction_explicit`）。
- **PatternRegistry**：全グループを管理する中央レジストリ、言語別インデックスによる高速マッチング。
- **PatternBuilder**：パターングループの構築と登録のためのFluent API。
- **Definitions**：パターン定義をカテゴリ別に分割（`definitions_noise.py`、`definitions_preference.py`など）、EN/ZH/JA言語をサポート。

```
PatternAnalyzer
  └── PatternRegistry
        ├── PatternGroup "noise_ack"     → [NoisePattern(en), NoisePattern(zh), NoisePattern(ja)]
        ├── PatternGroup "noise_chat"    → [NoisePattern(en), NoisePattern(zh), NoisePattern(ja)]
        ├── PatternGroup "preference_strong" → [PreferencePattern(en), PreferencePattern(zh), ...]
        ├── PatternGroup "correction_explicit" → [CorrectionPattern(en), CorrectionPattern(zh), ...]
        └── ... (全29グループ)
```

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
    raw_text TEXT,              -- NEW: ユーザー生入力、FTS5デュアルインデックス用
    confidence REAL NOT NULL,
    tier INTEGER NOT NULL,
    namespace TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    access_count INTEGER,
    content_hash TEXT NOT NULL,
    metadata TEXT,
    superseded_at TEXT,         -- NEW: この記憶が置換された日時
    supersedes TEXT             -- NEW: この記憶が置換する記憶ID
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

### 6. ナレッジライフサイクルレイヤー

**責務**: 知識の変遷を追跡し、記憶の置換を管理

#### 6.1 自動置換パイプライン

```
新規記憶 → Jaccard 類似度チェック → 矛盾検出 → 旧記憶を置換済みとしてマーク
    ↓            ↓                      ↓                    ↓
 INSERT    ≥ 0.25 閾値            単語境界正規表現       superseded_at = now
           + 更新マーカー検出    (like/dislike 等)        supersedes = new_key
                                  + アシスタント除外
```

#### 6.2 セッション認識ストレージ

```
classify_and_remember(session_id="s_20260513")
     ↓
session_id → metadata JSON → recall() の session_id フィルタ
```

#### 6.3 時間表現パース

```
クエリ: "最近データベースについて何を決めた？"
     ↓
_parse_time_expressions() → created_after = 7日前
     ↓
recall_memories(query="データベース", filters={"created_after": "2026-05-06T..."})
```

### 7. 記憶統合レイヤー

**責務**: 記憶ライフサイクル管理、重複排除・減衰・意味マージ

- **記憶統合エンジン** (`consolidation.py`)：記憶ライフサイクル管理、3フェーズ：
  - P0：Jaccard ベースの重複排除（≥0.85）+ 指数半減期減衰
  - P1：パターン検出 → PromotionPipeline によるルール候補生成
  - P2：意味クラスタリング → ホストLLM統合リクエスト
  - 嗜好は常に保持（減衰・重複排除なし）

---

## データフロー

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

## 主要コンポーネント

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

## ルールエンジン

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

## コンテキストエンジニアリング

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

複数の CarryMem インスタンス（異なる AI Agent プロセス）が同じ SQLite データベースファイルに同時に書き込む可能性があります。調整なしでは `database is locked` エラーやデータ破損が発生します。

### Solution: Per-File Write Lock

```
┌──────────────────────────────────────────────────────────┐
│              _db_write_locks（グローバル辞書）              │
│                                                           │
│  "/path/to/memories.db" → Lock A                         │
│  "/other/path/db.db"     → Lock B                        │
│  ...                                                      │
└──────────────────────────────────────────────────────────┘
         ↑                           ↑
    インスタンス1 (Cursor)        インスタンス2 (Claude Code)
    self._file_lock = A          self._file_lock = A
    （同じ Lock を共有）          （同じ Lock を共有）
```

**実装**:

```python
# グローバルレジストリ: realpath → Lock
_db_write_locks: Dict[str, threading.Lock] = {}
_db_write_locks_guard = threading.Lock()  # 辞書自体を保護

class SQLiteAdapter:
    def __init__(self, ...):
        resolved = str(os.path.realpath(self._db_path))
        with _db_write_locks_guard:
            if resolved not in _db_write_locks:
                _db_write_locks[resolved] = threading.Lock()
            self._file_lock = _db_write_locks[resolved]
```

**ロック階層**:

| 操作 | 使用するロック | スコープ | 動作 |
|------|-------------|---------|------|
| 書き込み（store_entry/store_batch/delete/update/recalculate） | `self._file_lock` | インスタンス間 | 同じ DB ファイルへの全書き込みを直列化 |
| 読み取り（recall/list） | `self._lock` | インスタンス内 | 他のインスタンスの読み取りをブロックしない |

**セカンダリ保護**: WAL モード + `busy_timeout=10000ms`

```python
conn = sqlite3.connect(db_path, timeout=10.0)
conn.execute("PRAGMA journal_mode=WAL")
```

WAL モードは書き込み中の並行読み取りを許可します。`busy_timeout` は10秒間のロック取得ウィンドウを提供し、per-file lock だけでは不十分なエッジケース（外部プロセスなど）を処理します。

---

## Auto-Backup Architecture

### 概要

CarryMem はデータ損失を防ぐため、自動・ゼロダウンタイムのデータベースバックアップを提供します。

### トリガー条件

- **間隔ベース**: N回の書き込み操作ごと（デフォルト: 20、`auto_backup_interval` で設定可能）
- **初期バックアップ**: 既存のデータベースを初めて開いたときに自動作成

```
書き込み操作 → _write_count += 1
     ↓
_write_count % auto_backup_interval == 0?
     ↓ はい
BackupManager.create_backup()
```

### バックアップ方式: VACUUM INTO

```python
conn.execute("VACUUM INTO ?", (backup_path,))
```

- **ゼロダウンタイム**: 読み取りや書き込みをブロックしない
- **一貫性スナップショット**: SQLite 推奨のバックアップ方式
- **フォールバック**: `VACUUM INTO` がサポートされていない場合、`shutil.copy2` にフォールバック

### バックアップ場所と命名

- **ディレクトリ**: `~/.carrymem/backups/`（`backup_dir` 設定で変更可能）
- **ファイル名形式**: `memories_backup_YYYYMMDD_HHMMSS_マイクロ秒.db`
- **パーミッション**: ディレクトリ `0o700`、バックアップファイル `0o600`

### 自動クリーンアップ

- **最大バックアップ数**: 5（`max_backups` で設定可能）
- **戦略**: FIFO — 最も古いバックアップから削除
- **タイミング**: 新しいバックアップ作成後にクリーンアップを実行

### リストア

```bash
carrymem backup --list              # 全バックアップを一覧
carrymem backup --restore <path>    # バックアップからリストア
```

リストアプロセス:
1. バックアップファイルを検証（開いてクエリを実行）
2. リストア前の安全コピーを作成（`.pre_restore.bak`）
3. バックアップを現在のデータベースに上書き
4. 失敗時は安全コピーからロールバック

---

## .carry File Format

`.carry` ファイルは CarryMem のポータブルアイデンティティ形式で、マシンやツール間でメモリを転送するために使用します。

### バージョン履歴

#### v1.0: レガシーフォーマット

- 純粋な gzip 圧縮 JSON
- チェックサムなし、暗号化サポートなし
- 構造: `gzip(json_data)`

#### v1.1: コンテナフォーマット（現在）

```json
{
    "version": "1.1",
    "checksum": "<SHA-256 hex、暗号化前の payload チェックサム>",
    "encrypted": false,
    "payload": "<base64(gzip(json_data)) または暗号化文字列>"
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `version` | string | フォーマットバージョン（`"1.1"`） |
| `checksum` | string | JSON payload の SHA-256 ハッシュ（圧縮/暗号化前） |
| `encrypted` | boolean | payload が暗号化されているか |
| `payload` | string | 暗号化なしの場合 `base64(gzip(json))`、暗号化の場合は暗号化文字列 |
| `encryption_backend` | string | （オプション）使用された暗号化バックエンド（`"fernet"` または `"hmac_ctr"`） |

### パックフロー

```
メモリデータ → JSON シリアライズ → SHA-256 チェックサム
     ↓
暗号化？ ──はい──→ MemoryEncryption.encrypt(json_string)
     │                    ↓
     いいえ           暗号化された payload
     ↓
base64(gzip(json_bytes)) = 暗号化なし payload
     ↓
コンテナ {version, checksum, encrypted, payload}
     ↓
gzip(container_json) → .carry ファイル
```

### アンパックフロー

```
.carry ファイル → gzip 解凍 → JSON パース
     ↓
"payload" と "checksum" キーがある？ ──はい──→ v1.1 フォーマット
     │                                         ↓
     いいえ                                encrypted?
     ↓                                   ↓ はい      ↓ いいえ
v1.0 フォーマット                       復号      base64 デコード
（警告: レガシー）                         ↓            ↓
                                    SHA-256 チェックサム検証
                                         ↓
                                    gzip 解凍 → JSON パース → メモリデータ
```

### 後方互換性

- v1.0 フォーマットのファイルは引き続きアンパック可能
- 警告を表示: `⚠ Legacy .carry format (no checksum verification available)`
- サポートされていないバージョン番号はエラーで拒否

### CLI コマンド

```bash
carrymem pack                         # アイデンティティをパック（暗号化なし）
carrymem pack --encrypt               # パスワード暗号化パック
carrymem pack --output my_id.carry    # カスタム出力パス
carrymem unpack identity.carry        # アンパックして復元
carrymem unpack identity.carry --replace  # 既存のメモリを置換
```

---

## 拡張メカニズム

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

## パフォーマンス最適化

### 1. Query Optimization

**Index Strategy**:
- Single column: type, namespace, content_hash
- Composite: (namespace, type), (namespace, tier)
- FTS5: trigram tokenizer

### 2. Batch Operations

```python
# Atomic batch with transaction
adapter.store_batch(entries)
# → BEGIN → INSERT... → COMMIT (or ROLLBACK on error)
```

### 3. Thread Safety

```python
# ThreadLocal connections + Lock
adapter = SQLiteAdapter()  # Thread-safe by default
```

---

## セキュリティ設計

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

## まとめ

CarryMem uses a **layered architecture + plugin design**, achieving:

✅ **High Performance**: FTS5 + indexing + caching
✅ **Extensible**: Adapter pattern + plugin system
✅ **Easy to Use**: Zero config + CLI tools
✅ **Secure**: Input validation + parameterized queries + path safety
✅ **Concurrent Safety**: Per-file write lock + WAL mode + busy_timeout
✅ **Auto-Backup**: VACUUM INTO + interval trigger + FIFO cleanup
✅ **Portable Identity**: .carry format with SHA-256 checksum + optional encryption
