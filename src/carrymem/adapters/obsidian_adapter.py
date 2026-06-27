"""Obsidian Knowledge Adapter — CarryMem's knowledge base integration.

Reads Markdown files from an Obsidian vault, indexes them with FTS5,
and provides full-text search for retrieval.

Features:
- Direct Markdown file reading (no Obsidian API dependency)
- YAML frontmatter tag extraction
- FTS5 full-text search index
- Incremental indexing (only re-index changed files)
- Wiki-link extraction for relationship mapping
"""

import hashlib
import json
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..utils.helpers import content_hash, escape_like
from .base import StorageAdapter

_OBSIDIAN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_path TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    wiki_links TEXT,
    frontmatter TEXT,
    file_modified TEXT,
    content_hash TEXT NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title,
    content,
    content='notes',
    content_rowid='rowid',
    tokenize='trigram'
);

CREATE INDEX IF NOT EXISTS idx_notes_tags ON notes(tags);
CREATE INDEX IF NOT EXISTS idx_notes_file_path ON notes(file_path);
CREATE INDEX IF NOT EXISTS idx_notes_content_hash ON notes(content_hash);

CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content)
    VALUES ('delete', old.rowid, old.title, old.content);
END;
"""

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-/]+)")


def _parse_frontmatter(content: str) -> Dict[str, Any]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    raw = match.group(1).strip()
    result: Dict[str, Any] = {}

    for line in raw.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
            result[key] = [i for i in items if i]
        elif value.lower() in ("true", "false"):
            result[key] = value.lower() == "true"
        elif value.isdigit():
            result[key] = int(value)
        else:
            result[key] = value.strip("\"'")

    return result


def _extract_tags(content: str, frontmatter: Dict[str, Any]) -> List[str]:
    tags = set()

    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, list):
        tags.update(fm_tags)
    elif isinstance(fm_tags, str):
        tags.add(fm_tags)

    for match in _TAG_RE.finditer(content):
        tags.add(match.group(1))

    return sorted(tags)


def _extract_wiki_links(content: str) -> List[str]:
    return sorted(set(m.group(1).strip() for m in _WIKI_LINK_RE.finditer(content)))


class ObsidianAdapter(StorageAdapter):
    """Obsidian vault knowledge adapter.

    Reads Markdown files from a vault directory, indexes them with FTS5,
    and provides full-text search. Does NOT modify vault files.

    Usage:
        adapter = ObsidianAdapter("/path/to/obsidian/vault")
        adapter.index_vault()
        results = adapter.recall("Python")
    """

    def __init__(self, vault_path: str, db_path: Optional[str] = None, content_truncate: int = 2000):
        self._vault_path = Path(vault_path).expanduser().resolve()

        if not self._vault_path.exists():
            raise FileNotFoundError(f"Obsidian vault not found: {self._vault_path}")

        if db_path is None:
            from ..constants import DEFAULT_CONFIG_DIR

            carrymem_dir = DEFAULT_CONFIG_DIR
            carrymem_dir.mkdir(exist_ok=True)
            vault_hash = hashlib.md5(str(self._vault_path).encode()).hexdigest()[:8]
            db_path = str(carrymem_dir / f"obsidian_{vault_hash}.db")

        self._db_path = db_path
        self._content_truncate = content_truncate
        self._lock = threading.Lock()
        self._local = threading.local()
        self._all_connections: Dict[int, sqlite3.Connection] = {}
        self._conn_lock = threading.Lock()
        self._closed = False
        conn = self._get_connection()
        conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("ObsidianAdapter has been closed")

        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
            with self._conn_lock:
                self._all_connections[id(conn)] = conn
        return self._local.conn  # type: ignore[no-any-return]

    def _init_schema(self):
        conn = self._get_connection()
        conn.executescript(_OBSIDIAN_SCHEMA_SQL)
        conn.commit()
        self._migrate_trigram()

    def _migrate_trigram(self):
        conn = self._get_connection()
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='notes_fts'")
        row = cursor.fetchone()
        if row and "unicode61" in (row["sql"] or ""):
            conn.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
            conn.execute("DROP TABLE IF EXISTS notes_fts")
            conn.execute("""CREATE VIRTUAL TABLE notes_fts USING fts5(
                    title, content,
                    content='notes', content_rowid='rowid', tokenize='trigram'
                )""")
            conn.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
            conn.commit()

    @property
    def name(self) -> str:
        """Human-readable adapter identifier."""
        return "obsidian"

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Feature flags for this adapter (FTS, batch, graph, etc.)."""
        return {
            "vector_search": False,
            "fts": True,
            "ttl": False,
            "batch": True,
            "graph": True,
            "wiki_links": True,
            "frontmatter": True,
        }

    @property
    def vault_path(self) -> str:
        """Absolute path to the indexed Obsidian vault."""
        return str(self._vault_path)

    # ── Standardized Adapter Interface (abstract method implementations) ──

    def initialize(self, config: dict) -> None:
        """Initialize the adapter with configuration.

        ObsidianAdapter is configured at construction time (vault_path, db_path),
        so ``config`` is accepted for interface compatibility but ignored.

        If the vault has not been indexed yet (no notes in the index), this
        triggers an initial ``index_vault()`` run.
        """
        if self.count() == 0:
            self.index_vault()

    def store(self, entry: dict) -> str:
        """ObsidianAdapter is read-only — storing is not supported."""
        raise NotImplementedError("ObsidianAdapter is read-only")

    def delete(self, entry_id: str) -> bool:
        """ObsidianAdapter is read-only — deleting is not supported."""
        raise NotImplementedError("ObsidianAdapter is read-only")

    def count(self, filter_: Optional[dict] = None) -> int:
        """Count indexed notes, optionally filtered by tags."""
        with self._lock:
            conn = self._get_connection()
            if filter_ and filter_.get("tags"):
                tag_list = filter_["tags"] if isinstance(filter_["tags"], list) else [filter_["tags"]]
                conditions = []
                params = []
                for tag in tag_list:
                    conditions.append("tags LIKE ? ESCAPE '\\'")
                    params.append(f'%"{escape_like(tag)}"%')
                where_clause = "WHERE " + " AND ".join(conditions)
                result = conn.execute(f"SELECT COUNT(*) FROM notes {where_clause}", params).fetchone()
                return result[0]  # type: ignore[no-any-return]
            return conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]  # type: ignore[no-any-return]

    def health_check(self) -> dict:
        """Check vault directory availability."""
        start = time.perf_counter()
        vault_exists = self._vault_path.exists()
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "status": "healthy" if vault_exists else "unhealthy",
            "latency_ms": latency_ms,
            "vault_path": str(self._vault_path),
            "vault_exists": vault_exists,
        }

    def index_vault(self) -> Dict[str, int]:
        """Scan the vault and index new/changed Markdown files."""
        with self._lock:
            return self._index_vault_impl()

    def _index_vault_impl(self) -> Dict[str, int]:
        conn = self._get_connection()
        md_files = list(self._vault_path.rglob("*.md"))
        new_count = 0
        updated_count = 0
        skipped_count = 0

        for md_file in md_files:
            if md_file.name.startswith("."):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                skipped_count += 1
                continue

            c_hash = content_hash(content)

            existing = conn.execute(
                "SELECT content_hash FROM notes WHERE file_path = ?",
                (str(md_file.relative_to(self._vault_path)),),
            ).fetchone()

            if existing and existing["content_hash"] == c_hash:
                skipped_count += 1
                continue

            title = md_file.stem
            frontmatter = _parse_frontmatter(content)
            tags = _extract_tags(content, frontmatter)
            wiki_links = _extract_wiki_links(content)

            body = content
            fm_match = _FRONTMATTER_RE.match(content)
            if fm_match:
                body = content[fm_match.end() :]

            note_id = f"obs_{c_hash[:8]}_{title[:30].replace(' ', '_')}"

            if existing:
                conn.execute(
                    """UPDATE notes SET title=?, content=?, tags=?, wiki_links=?,
                       frontmatter=?, file_modified=?, content_hash=?, indexed_at=?
                       WHERE file_path=?""",
                    (
                        title,
                        body,
                        json.dumps(tags),
                        json.dumps(wiki_links),
                        json.dumps(frontmatter),
                        datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
                        c_hash,
                        datetime.now(timezone.utc).isoformat(),
                        str(md_file.relative_to(self._vault_path)),
                    ),
                )
                updated_count += 1
            else:
                conn.execute(
                    """INSERT INTO notes (id, title, file_path, content, tags,
                       wiki_links, frontmatter, file_modified, content_hash, indexed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        note_id,
                        title,
                        str(md_file.relative_to(self._vault_path)),
                        body,
                        json.dumps(tags),
                        json.dumps(wiki_links),
                        json.dumps(frontmatter),
                        datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
                        c_hash,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                new_count += 1

        conn.commit()

        return {
            "total_files": len(md_files),
            "new": new_count,
            "updated": updated_count,
            "skipped": skipped_count,
        }

    def remember(self, entry) -> Any:
        """Store a memory entry (unsupported on read-only Obsidian adapter)."""
        raise NotImplementedError("ObsidianAdapter is read-only. Use SQLiteAdapter for storing memories.")

    def remember_batch(self, entries: list) -> list:
        """Store multiple memory entries (unsupported on read-only Obsidian adapter)."""
        raise NotImplementedError("ObsidianAdapter is read-only. Use SQLiteAdapter for storing memories.")

    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        update_access: bool = True,
        namespaces: Optional[List[str]] = None,
        **kwargs,
    ) -> list:
        """Full-text search the indexed vault notes."""
        full_content = kwargs.get("full_content", False)
        with self._lock:
            filters = filters or {}

            if query and query.strip():
                results = self._fts_search(query, filters, limit)
            else:
                results = self._filtered_search(filters, limit)

            if full_content:
                for r in results:
                    if "_full_content" in r:
                        r["content"] = r.pop("_full_content")
                    r.pop("_truncated", None)

            return results

    def _fts_search(self, query: str, filters: Dict[str, Any], limit: int) -> list:
        conditions = []
        params = []

        if filters.get("tags"):
            tag_list = filters["tags"] if isinstance(filters["tags"], list) else [filters["tags"]]
            for tag in tag_list:
                conditions.append("tags LIKE ? ESCAPE '\\'")
                params.append(f'%"{escape_like(tag)}"%')

        where_clause = ""
        if conditions:
            where_clause = "AND " + " AND ".join(conditions)

        fts_query = query
        if len(query) < 3:
            fts_query = f'"{query}"'

        sql = f"""
            SELECT n.*, f.rank as fts_rank FROM notes n
            JOIN notes_fts f ON n.rowid = f.rowid
            WHERE n.rowid IN (
                SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?
            )
            {where_clause}
            ORDER BY rank
            LIMIT ?
        """
        params_with_query = [fts_query] + params + [limit]

        try:
            rows = self._get_connection().execute(sql, params_with_query).fetchall()
        except sqlite3.OperationalError:
            rows = self._fallback_search(query, filters, limit)
            return [self._row_to_dict(row) for row in rows]

        query_tags = set(_extract_tags(query, {}))
        results = []
        for row in rows:
            item = self._row_to_dict(row)
            item["relevance_score"] = self._compute_relevance(row, query, query_tags)
            results.append(item)

        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results

    def _compute_relevance(self, row: sqlite3.Row, query: str, query_tags: Set[str]) -> float:
        fts_rank = abs(row["fts_rank"]) if row["fts_rank"] is not None else 0.0
        fts_score = min(1.0 / (1.0 + fts_rank), 1.0)

        tag_score = 0.0
        if query_tags:
            note_tags = set()
            if row["tags"]:
                try:
                    note_tags = set(json.loads(row["tags"]))
                except (json.JSONDecodeError, TypeError):
                    pass
            if note_tags:
                overlap = len(query_tags & note_tags)
                tag_score = overlap / max(len(query_tags), 1)

        wiki_score = 0.0
        if row["wiki_links"]:
            try:
                links = json.loads(row["wiki_links"])
                query_lower = query.lower()
                for link in links:
                    if query_lower in link.lower() or link.lower() in query_lower:
                        wiki_score = 0.3
                        break
            except (json.JSONDecodeError, TypeError):
                pass

        return fts_score * 0.6 + tag_score * 0.25 + wiki_score * 0.15

    def _fallback_search(self, query: str, filters: Dict[str, Any], limit: int) -> list:
        conditions = ["(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"]
        params: List[Any] = [f"%{escape_like(query)}%", f"%{escape_like(query)}%"]

        if filters.get("tags"):
            tag_list = filters["tags"] if isinstance(filters["tags"], list) else [filters["tags"]]
            for tag in tag_list:
                conditions.append("tags LIKE ? ESCAPE '\\'")
                params.append(f'%"{escape_like(tag)}"%')

        where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"SELECT * FROM notes {where_clause} ORDER BY indexed_at DESC LIMIT ?"
        params.append(limit)
        return self._get_connection().execute(sql, params).fetchall()

    def _filtered_search(self, filters: Dict[str, Any], limit: int) -> list:
        conditions = []
        params: List[Any] = []

        if filters.get("tags"):
            tag_list = filters["tags"] if isinstance(filters["tags"], list) else [filters["tags"]]
            for tag in tag_list:
                conditions.append("tags LIKE ? ESCAPE '\\'")
                params.append(f'%"{escape_like(tag)}"%')

        if filters.get("title"):
            conditions.append("title LIKE ? ESCAPE '\\'")
            params.append(f'%{escape_like(filters["title"])}%')

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"SELECT * FROM notes {where_clause} ORDER BY indexed_at DESC LIMIT ?"
        params.append(limit)
        rows = self._get_connection().execute(sql, params).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def forget(self, storage_key: str) -> bool:
        """Delete a memory entry (unsupported on read-only Obsidian adapter)."""
        raise NotImplementedError("ObsidianAdapter is read-only. Delete notes from your vault directly.")

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics about the indexed vault."""
        with self._lock:
            conn = self._get_connection()
            total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            tag_rows = conn.execute("SELECT tags FROM notes WHERE tags IS NOT NULL AND tags != '[]'").fetchall()

            all_tags: Dict[str, int] = {}
            for row in tag_rows:
                try:
                    tags = json.loads(row["tags"])
                    for tag in tags:
                        all_tags[tag] = all_tags.get(tag, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "adapter": self.name,
                "total_notes": total,
                "unique_tags": len(all_tags),
                "top_tags": dict(sorted(all_tags.items(), key=lambda x: -x[1])[:10]),
                "capabilities": self.capabilities,
            }

    def get_tags(self) -> Dict[str, int]:
        """Return all tags with their occurrence counts, sorted by frequency."""
        tag_rows = (
            self._get_connection().execute("SELECT tags FROM notes WHERE tags IS NOT NULL AND tags != '[]'").fetchall()
        )

        all_tags: Dict[str, int] = {}
        for row in tag_rows:
            try:
                tags = json.loads(row["tags"])
                for tag in tags:
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        return dict(sorted(all_tags.items(), key=lambda x: -x[1]))

    def get_linked_notes(self, note_title: str) -> List[Dict[str, Any]]:
        """Return notes that wiki-link to the given note title."""
        rows = (
            self._get_connection()
            .execute(
                "SELECT * FROM notes WHERE wiki_links LIKE ? ESCAPE '\\'",
                (f'%"{escape_like(note_title)}"%',),
            )
            .fetchall()
        )
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        tags = []
        if row["tags"]:
            try:
                tags = json.loads(row["tags"])
            except (json.JSONDecodeError, TypeError):
                pass

        wiki_links = []
        if row["wiki_links"]:
            try:
                wiki_links = json.loads(row["wiki_links"])
            except (json.JSONDecodeError, TypeError):
                pass

        frontmatter = {}
        if row["frontmatter"]:
            try:
                frontmatter = json.loads(row["frontmatter"])
            except (json.JSONDecodeError, TypeError):
                pass

        result = {
            "id": row["id"],
            "type": "knowledge_note",
            "title": row["title"],
            "content": row["content"][: self._content_truncate],
            "file_path": row["file_path"],
            "tags": tags,
            "wiki_links": wiki_links,
            "frontmatter": frontmatter,
            "source": "obsidian",
            "confidence": 1.0,
        }

        if len(row["content"]) > self._content_truncate:
            result["_truncated"] = True
            result["_full_content"] = row["content"]

        return result

    def close(self):
        """Close all database connections and mark the adapter as closed."""
        self._closed = True
        with self._conn_lock:
            for conn in self._all_connections.values():
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._all_connections.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None

    def __del__(self):
        self.close()
