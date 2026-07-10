# CarryMem Obsidian Adapter

## Overview

The Obsidian Adapter is a **read-only knowledge base adapter** that indexes your Obsidian vault and provides full-text search over your notes. It reads Markdown files directly from the vault directory — no Obsidian API dependency required.

CarryMem uses a dual-adapter architecture: the **storage adapter** (SQLite by default) handles read-write memories, while the **knowledge adapter** (Obsidian) provides read-only access to your existing notes. Recall priority is: rules > memories > knowledge base.

Key characteristics:
- **Read-only**: Cannot write to or modify your vault files
- **FTS5 full-text search**: Fast search with CJK (Chinese/Japanese/Korean) support via trigram tokenizer
- **Frontmatter parsing**: Extracts YAML frontmatter fields and tags
- **Wiki-link extraction**: Parses `[[wiki-link]]` syntax for graph traversal
- **Incremental indexing**: Only re-indexes files that have changed since the last scan

---

## Quick Start

```python
from carrymem import CarryMem
from carrymem.adapters import ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("project architecture")
```

> **Important**: Use `knowledge_adapter=ObsidianAdapter(...)`, NOT `storage="obsidian"`.
> Passing `storage="obsidian"` will raise a `ValueError` because the vault path is required.

---

## Configuration

### Vault Path

The vault path is the only required parameter. There are three ways to configure it:

**1. Constructor argument (recommended)**

```python
adapter = ObsidianAdapter("/path/to/obsidian/vault")
```

**2. Environment variable**

Set `CARRYMEM_OBSIDIAN_VAULT` and use `get_obsidian_vault_path()` from constants:

```python
from carrymem.constants import get_obsidian_vault_path

vault_path = get_obsidian_vault_path()  # reads CARRYMEM_OBSIDIAN_VAULT
if vault_path:
    adapter = ObsidianAdapter(str(vault_path))
```

**3. Auto-discovery**

If no environment variable is set, `get_obsidian_vault_path()` checks these locations in order:

| Priority | Path |
|----------|------|
| 1 | `~/Documents/Obsidian` |
| 2 | `~/Obsidian` |
| 3 | `~/Documents/ObsidianVault` |

The first existing directory is used. If none exist, `get_obsidian_vault_path()` returns `None`.

### Database Path

The FTS5 index is stored in a SQLite database. By default, it is placed at:

```
~/.carrymem/obsidian_{vault_hash}.db
```

Where `vault_hash` is the first 8 characters of the MD5 hash of the vault path. This ensures different vaults get separate index databases.

You can override the database location:

```python
adapter = ObsidianAdapter("/path/to/vault", db_path="/custom/path/obsidian.db")
```

### Content Truncation

By default, note content is truncated to 2000 characters in search results to keep responses concise. You can adjust this:

```python
adapter = ObsidianAdapter("/path/to/vault", content_truncate=5000)
```

To retrieve full content in search results, pass `full_content=True`:

```python
results = adapter.recall("query", full_content=True)
```

---

## Features

### Full-Text Search (FTS5)

The adapter uses SQLite's FTS5 extension with the **trigram tokenizer**, which provides:

- **CJK support**: Chinese, Japanese, and Korean text is indexed character-by-character, enabling substring matching without word boundaries
- **Automatic migration**: If an existing index was built with the `unicode61` tokenizer, it is automatically rebuilt with `trigram` on the next initialization
- **Fallback search**: If FTS5 query syntax fails (e.g., special characters), a `LIKE`-based fallback search is used automatically

The FTS5 index covers both `title` and `content` fields. Short queries (under 3 characters) are automatically wrapped in quotes for exact matching.

### Frontmatter Parsing

YAML frontmatter at the top of Markdown files is parsed and stored:

```markdown
---
tags: [python, architecture, design-pattern]
priority: high
project: backend-refactor
---

# Note content here...
```

The parser handles:
- String values: `key: value`
- List values: `key: [item1, item2, item3]`
- Boolean values: `key: true` / `key: false`
- Integer values: `key: 42`

Frontmatter is stripped from the indexed content body so search results show the actual note content.

### Tag Extraction

Tags are collected from two sources:

1. **Frontmatter tags**: The `tags` field in YAML frontmatter (list or single string)
2. **Inline tags**: `#tag` patterns in the note body (e.g., `#python`, `#design-pattern`)

```markdown
---
tags: [architecture, microservices]
---

We chose #microservices for the #backend architecture.
```

In this example, the extracted tags are: `architecture`, `backend`, `microservices`.

Tags are searchable via the `filters` parameter:

```python
results = adapter.recall("query", filters={"tags": "python"})
results = adapter.recall("query", filters={"tags": ["python", "architecture"]})
```

### Wiki-Links

Obsidian-style wiki-links are extracted from note content:

- Standard syntax: `[[note-title]]` → extracts `note-title`
- Alias syntax: `[[note-title|display name]]` → extracts `note-title`

Use `get_linked_notes()` to find all notes that link to a specific note:

```python
backlinks = adapter.get_linked_notes("Project Architecture")
for note in backlinks:
    print(f"{note['title']} links to Project Architecture")
```

Wiki-links also contribute to relevance scoring — if a query matches a wiki-link target, the note gets a small score boost.

### Incremental Indexing

The adapter uses content hashing to skip unchanged files:

1. On `index_vault()`, each `.md` file's content hash is computed
2. If the hash matches the stored hash, the file is skipped
3. Only new or modified files are processed and indexed

This makes subsequent indexing runs fast even for large vaults.

The return value of `index_vault()` provides statistics:

```python
stats = adapter.index_vault()
# {
#     "total_files": 150,
#     "new": 3,
#     "updated": 2,
#     "skipped": 145
# }
```

Files starting with `.` (dotfiles) are excluded from indexing. Files that cannot be read (encoding errors, permission errors) are skipped gracefully.

---

## Relevance Scoring

Search results are ranked using a weighted combination of three signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| FTS score | 0.60 | Inverse of FTS5 rank — higher rank = closer match |
| Tag score | 0.25 | Overlap ratio between query tags and note tags |
| Wiki-link score | 0.15 | Bonus if query text matches a wiki-link target |

The formula is:

```
relevance = fts_score * 0.6 + tag_score * 0.25 + wiki_score * 0.15
```

Results are sorted by `relevance_score` in descending order.

---

## MCP Integration

The Obsidian adapter integrates with CarryMem's MCP server through the `vault_path` parameter in the Handlers constructor.

### Available MCP Tools

When a knowledge adapter is configured, three additional MCP tools become available:

| Tool | Description |
|------|-------------|
| `index_knowledge` | Index the Obsidian vault (scan files, build FTS5 index) |
| `recall_from_knowledge` | Search the knowledge base using full-text search |
| `recall_all` | Unified retrieval across both memories and knowledge base |

### Configuring MCP with Obsidian

The MCP server's `Handlers` class accepts a `vault_path` parameter:

```python
from carrymem.integration.layer2_mcp import Handlers

handlers = Handlers(vault_path="/path/to/obsidian/vault")
```

When `vault_path` is provided, an `ObsidianAdapter` is automatically created and passed as the `knowledge_adapter` to the `CarryMem` instance.

### MCP Tool Parameters

**`index_knowledge`** — no parameters required.

**`recall_from_knowledge`**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `filters` | object | No | Tag/title filters |
| `filters.tags` | string or array | No | Filter by tag(s) |
| `filters.title` | string | No | Filter by title (partial match) |
| `limit` | integer | No | Max results (1–100, default 20) |

**`recall_all`**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `filters` | object | No | Type/tag filters |
| `limit` | integer | No | Max results per source (1–100, default 20) |

---

## API Reference

### Constructor

```python
ObsidianAdapter(vault_path: str, db_path: Optional[str] = None, content_truncate: int = 2000)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vault_path` | `str` | required | Path to the Obsidian vault directory |
| `db_path` | `Optional[str]` | `None` | Custom SQLite database path (auto-generated if None) |
| `content_truncate` | `int` | `2000` | Max characters for content preview in results |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Always returns `"obsidian"` |
| `vault_path` | `str` | Resolved absolute path to the vault |
| `capabilities` | `Dict[str, bool]` | Adapter capability flags |

**Capabilities:**

| Capability | Value |
|------------|-------|
| `vector_search` | `False` |
| `fts` | `True` |
| `ttl` | `False` |
| `batch` | `True` |
| `graph` | `True` |
| `wiki_links` | `True` |
| `frontmatter` | `True` |

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `index_vault` | `() -> Dict[str, int]` | Scan vault, index new/changed files. Returns `{"total_files", "new", "updated", "skipped"}` |
| `recall` | `(query: str, filters: Optional[Dict] = None, limit: int = 20, update_access: bool = True, namespaces: Optional[List[str]] = None, **kwargs) -> list` | Search indexed notes. Accepts `full_content=True` in kwargs |
| `get_stats` | `() -> Dict[str, Any]` | Returns `{"adapter", "total_notes", "unique_tags", "top_tags", "capabilities"}` |
| `get_tags` | `() -> Dict[str, int]` | Returns all tags with their occurrence counts, sorted by frequency |
| `get_linked_notes` | `(note_title: str) -> List[Dict[str, Any]]` | Find all notes that wiki-link to the given title |
| `store_entry` | `(entry: MemoryEntry) -> StoredMemory` | **Raises NotImplementedError** — read-only adapter |
| `store_batch` | `(entries: list) -> list` | **Raises NotImplementedError** — read-only adapter |
| `delete` | `(entry_id: str) -> bool` | **Raises NotImplementedError** — read-only adapter |
| `close` | `() -> None` | Close all database connections |

### Search Result Format

Each result from `recall()` is a dictionary with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Note ID (format: `obs_{hash}_{title}`) |
| `type` | `str` | Always `"knowledge_note"` |
| `title` | `str` | Note title (filename stem) |
| `content` | `str` | Content preview (truncated to `content_truncate` chars) |
| `file_path` | `str` | Relative path from vault root |
| `tags` | `List[str]` | Extracted tags |
| `wiki_links` | `List[str]` | Extracted wiki-link targets |
| `frontmatter` | `Dict[str, Any]` | Parsed YAML frontmatter |
| `source` | `str` | Always `"obsidian"` |
| `confidence` | `float` | Always `1.0` |
| `relevance_score` | `float` | Computed relevance score (FTS search only) |
| `_truncated` | `bool` | `True` if content was truncated (absent if not) |

---

## CarryMem Integration

### Using with CarryMem

```python
from carrymem import CarryMem
from carrymem.adapters import ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))

cm.index_knowledge()

results = cm.recall_from_knowledge("design patterns")

all_results = cm.recall_all("database")
# Returns {"rules": [...], "memories": [...], "knowledge": [...], ...}
```

### Using with AsyncCarryMem

```python
from carrymem import AsyncCarryMem
from carrymem.adapters import ObsidianAdapter

cm = AsyncCarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
```

### Auto-Discovery Pattern

```python
from carrymem import CarryMem
from carrymem.adapters import ObsidianAdapter
from carrymem.constants import get_obsidian_vault_path

vault = get_obsidian_vault_path()
if vault:
    cm = CarryMem(knowledge_adapter=ObsidianAdapter(str(vault)))
    cm.index_knowledge()
else:
    print("No Obsidian vault found. Set CARRYMEM_OBSIDIAN_VAULT or create ~/Documents/Obsidian")
```

---

## Limitations

- **Read-only**: The adapter cannot write to or modify vault files. `store_entry()`, `store_batch()`, and `delete()` all raise `NotImplementedError`. To delete a note, remove it from your vault and re-index.
- **No vector search**: Semantic similarity search is not supported. Only FTS5 full-text search is available.
- **No TTL support**: Notes do not expire. They remain in the index until the source file is removed from the vault.
- **No `storage="obsidian"`**: You cannot pass `storage="obsidian"` to `CarryMem()`. The Obsidian adapter must be used as `knowledge_adapter`, not as the primary storage adapter.
- **Markdown only**: Only `.md` files are indexed. Other file types (images, PDFs, etc.) are ignored.
- **Dotfiles excluded**: Files starting with `.` are skipped during indexing.
- **Simple frontmatter parser**: The built-in YAML parser handles common patterns but does not support nested objects, multi-line values, or advanced YAML features.

---

## Troubleshooting

### "Obsidian vault not found" error

The vault path does not exist. Verify the path is correct:

```python
from pathlib import Path
print(Path("/your/vault/path").exists())
```

Ensure you are using the vault's root directory (the one containing `.obsidian/`).

### Search returns no results

1. **Run `index_knowledge()` first**: The vault must be indexed before searching
2. **Check index stats**: `adapter.get_stats()` shows `total_notes` — if 0, indexing may have failed
3. **CJK queries need 3+ characters**: The trigram tokenizer requires at least 3 characters for FTS5 matching. Shorter queries are auto-quoted for exact match.

### "Knowledge adapter not configured" error

You tried to call `index_knowledge()` or `recall_from_knowledge()` without providing a knowledge adapter:

```python
# Wrong
cm = CarryMem()
cm.recall_from_knowledge("query")  # raises KnowledgeNotConfiguredError

# Correct
cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.recall_from_knowledge("query")
```

### "ObsidianAdapter requires a vault_path" error

You used `storage="obsidian"` instead of `knowledge_adapter`:

```python
# Wrong
cm = CarryMem(storage="obsidian")  # raises ValueError

# Correct
cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
```

### Index is stale after vault changes

Re-run `index_knowledge()` to pick up changes. Incremental indexing will only process new or modified files:

```python
cm.index_knowledge()
```

### Database file location

The index database is stored at `~/.carrymem/obsidian_{vault_hash}.db`. To find it:

```python
adapter = ObsidianAdapter("/path/to/vault")
print(adapter._db_path)
```

If the database becomes corrupted, delete it and re-index:

```bash
rm ~/.carrymem/obsidian_*.db
```

Then call `index_knowledge()` again to rebuild the index from scratch.

### Performance with large vaults

For vaults with thousands of notes:
- Incremental indexing skips unchanged files, so subsequent runs are fast
- Content truncation (`content_truncate`) keeps search results compact
- The SQLite WAL journal mode enables concurrent reads during indexing
