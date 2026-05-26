"""CodingContext Adapter — CarryMem's coding convention integration.

Reads coding convention files from a project directory, indexes them
with FTS5, and provides full-text search for retrieval.

Supported file types:
- AI assistant instructions: CLAUDE.md, .cursorrules, .windsurfrules, .aider.conf.yml
- Editor configs: .editorconfig, .eslintrc*, .prettierrc*, pyproject.toml (lint sections)
- Project metadata: package.json, pyproject.toml, Cargo.toml, go.mod
- CI/CD configs: .github/workflows/*.yml (convention-relevant sections)

Memory type mapping:
- Coding style rules → user_preference
- Lint/format rules → decision
- Bug fix patterns → correction
- Tech stack choices → fact_declaration
- AI assistant instructions → mapped by content semantics
"""

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import StorageAdapter
from ..utils.helpers import escape_like


_CODING_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS coding_entries (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_path TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'personal_fact',
    source_type TEXT NOT NULL,
    language TEXT,
    framework TEXT,
    content_hash TEXT NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS coding_fts USING fts5(
    title,
    content,
    content='coding_entries',
    content_rowid='rowid',
    tokenize='trigram'
);

CREATE INDEX IF NOT EXISTS idx_coding_memory_type ON coding_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_coding_source_type ON coding_entries(source_type);
CREATE INDEX IF NOT EXISTS idx_coding_content_hash ON coding_entries(content_hash);

CREATE TRIGGER IF NOT EXISTS coding_ai AFTER INSERT ON coding_entries BEGIN
    INSERT INTO coding_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS coding_ad AFTER DELETE ON coding_entries BEGIN
    INSERT INTO coding_fts(coding_fts, rowid, title, content)
    VALUES ('delete', old.rowid, old.title, old.content);
END;
"""

_AI_INSTRUCTION_FILES = {
    "CLAUDE.md": "ai_instruction",
    "claude.md": "ai_instruction",
    ".cursorrules": "ai_instruction",
    ".windsurfrules": "ai_instruction",
    ".aider.conf.yml": "ai_instruction",
    "COPILOT.md": "ai_instruction",
    "AGENTS.md": "ai_instruction",
}

_EDITOR_CONFIG_FILES = {
    ".editorconfig": "editor_config",
    ".eslintrc": "lint_config",
    ".eslintrc.js": "lint_config",
    ".eslintrc.json": "lint_config",
    ".eslintrc.yml": "lint_config",
    ".prettierrc": "format_config",
    ".prettierrc.json": "format_config",
    ".prettierrc.yml": "format_config",
    ".stylelintrc": "lint_config",
    ".flake8": "lint_config",
    ".pylintrc": "lint_config",
    "mypy.ini": "type_config",
    ".mypy.ini": "type_config",
    "ruff.toml": "lint_config",
    ".ruff.toml": "lint_config",
}

_PROJECT_METADATA_FILES = {
    "package.json": "project_meta",
    "pyproject.toml": "project_meta",
    "Cargo.toml": "project_meta",
    "go.mod": "project_meta",
    "pom.xml": "project_meta",
    "build.gradle": "project_meta",
    "Gemfile": "project_meta",
    "composer.json": "project_meta",
}

_CONTENT_TYPE_PATTERNS = [
    (r'\b(prefer|always|never|must|should|avoid|don\'t|do not)\b', "user_preference"),
    (r'\b(lint|format|style|indent|tab|space|semicolon|comma|quote)\b', "decision"),
    (r'\b(fix|bug|issue|error|workaround|hack|patch)\b', "correction"),
    (r'\b(use|using|built.?with|stack|framework|library|version|runtime)\b', "personal_fact"),
]


def _infer_memory_type(content: str, source_type: str) -> str:
    if source_type == "ai_instruction":
        for pattern, mtype in _CONTENT_TYPE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return mtype
        return "decision"

    if source_type in ("editor_config", "lint_config", "format_config", "type_config"):
        return "decision"

    if source_type == "project_meta":
        return "personal_fact"

    return "personal_fact"


def _infer_language(file_path: str, content: str) -> Optional[str]:
    path_lower = file_path.lower()

    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".rs": "rust", ".go": "go", ".java": "java",
        ".rb": "ruby", ".php": "php", ".swift": "swift",
        ".kt": "kotlin", ".cs": "csharp",
    }
    for ext, lang in lang_map.items():
        if path_lower.endswith(ext):
            return lang

    if "package.json" in path_lower:
        try:
            data = json.loads(content)
            deps = list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())
            if any("react" in d for d in deps):
                return "react"
            if any("vue" in d for d in deps):
                return "vue"
            if any("next" in d for d in deps):
                return "nextjs"
            if any("svelte" in d for d in deps):
                return "svelte"
        except (json.JSONDecodeError, TypeError):
            pass
        return "javascript"

    if "pyproject.toml" in path_lower:
        return "python"
    if "cargo.toml" in path_lower:
        return "rust"
    if "go.mod" in path_lower:
        return "go"

    return None


def _infer_framework(content: str, language: Optional[str]) -> Optional[str]:
    if not language:
        return None

    content_lower = content.lower()

    framework_patterns = {
        "python": [
            (r'django', "django"), (r'flask', "flask"), (r'fastapi', "fastapi"),
            (r'pytorch', "pytorch"), (r'tensorflow', "tensorflow"),
        ],
        "javascript": [
            (r'react', "react"), (r'vue', "vue"), (r'angular', "angular"),
            (r'next\.?js', "nextjs"), (r'svelte', "svelte"),
            (r'express', "express"), (r'nuxt', "nuxt"),
        ],
        "typescript": [
            (r'react', "react"), (r'vue', "vue"), (r'angular', "angular"),
            (r'next\.?js', "nextjs"), (r'nuxt', "nuxt"),
        ],
        "rust": [
            (r'actix', "actix"), (r'axum', "axum"), (r'rocket', "rocket"),
        ],
    }

    for pattern, framework in framework_patterns.get(language, []):
        if re.search(pattern, content_lower):
            return framework

    return None


def _parse_file(file_path: Path) -> List[Dict[str, Any]]:
    """Parse a single file into one or more coding entries."""
    entries = []
    file_name = file_path.name
    content_raw = ""

    try:
        content_raw = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, IOError):
        return entries

    if not content_raw.strip():
        return entries

    source_type = _AI_INSTRUCTION_FILES.get(file_name)
    if not source_type:
        source_type = _EDITOR_CONFIG_FILES.get(file_name)
    if not source_type:
        source_type = _PROJECT_METADATA_FILES.get(file_name)
    if not source_type:
        return entries

    if source_type == "ai_instruction" and len(content_raw) > 200:
        sections = re.split(r'\n(?=#{1,3}\s)', content_raw)
        if len(sections) > 1:
            for section in sections:
                section = section.strip()
                if not section or len(section) < 20:
                    continue
                first_line = section.split("\n")[0].strip()
                title = re.sub(r'^#+\s*', '', first_line)[:80] or file_name
                mtype = _infer_memory_type(section, source_type)
                lang = _infer_language(str(file_path), section)
                fw = _infer_framework(section, lang)
                entries.append({
                    "title": title,
                    "content": section[:2000],
                    "memory_type": mtype,
                    "source_type": source_type,
                    "language": lang,
                    "framework": fw,
                })
            return entries

    title = file_name
    mtype = _infer_memory_type(content_raw, source_type)
    lang = _infer_language(str(file_path), content_raw)
    fw = _infer_framework(content_raw, lang)

    entries.append({
        "title": title,
        "content": content_raw[:2000],
        "memory_type": mtype,
        "source_type": source_type,
        "language": lang,
        "framework": fw,
    })

    return entries


class CodingContextAdapter(StorageAdapter):
    """Coding context knowledge adapter.

    Reads coding convention files from a project directory, indexes them
    with FTS5, and provides full-text search. Does NOT modify project files.

    Usage:
        adapter = CodingContextAdapter("/path/to/project")
        adapter.index_project()
        results = adapter.recall("coding style")
    """

    def __init__(self, project_path: str, db_path: Optional[str] = None):
        self._project_path = Path(project_path).expanduser().resolve()

        if not self._project_path.exists():
            raise FileNotFoundError(f"Project directory not found: {self._project_path}")

        if db_path is None:
            from ..constants import DEFAULT_CONFIG_DIR
            carrymem_dir = DEFAULT_CONFIG_DIR
            carrymem_dir.mkdir(exist_ok=True)
            project_hash = hashlib.md5(str(self._project_path).encode()).hexdigest()[:8]
            db_path = str(carrymem_dir / f"coding_{project_hash}.db")

        self._db_path = db_path
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
            raise RuntimeError("CodingContextAdapter has been closed")

        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
            with self._conn_lock:
                self._all_connections[id(conn)] = conn
        return self._local.conn

    def _init_schema(self):
        conn = self._get_connection()
        conn.executescript(_CODING_SCHEMA_SQL)
        conn.commit()

    @property
    def name(self) -> str:
        return "coding_context"

    def _find_config_files(self) -> List[Path]:
        all_patterns = (
            list(_AI_INSTRUCTION_FILES.keys())
            + list(_EDITOR_CONFIG_FILES.keys())
            + list(_PROJECT_METADATA_FILES.keys())
        )
        found = []
        for pattern in all_patterns:
            matches = list(self._project_path.glob(pattern))
            found.extend(matches)

        github_dir = self._project_path / ".github" / "workflows"
        if github_dir.exists():
            found.extend(github_dir.glob("*.yml"))
            found.extend(github_dir.glob("*.yaml"))

        return list(set(found))

    def index_project(self, force: bool = False) -> Dict[str, Any]:
        config_files = self._find_config_files()
        stats = {
            "files_found": len(config_files),
            "files_indexed": 0,
            "files_skipped": 0,
            "entries_created": 0,
            "entries_updated": 0,
        }

        with self._lock:
            conn = self._get_connection()
            for file_path in config_files:
                try:
                    content_raw = file_path.read_text(encoding="utf-8", errors="replace")
                except (OSError, IOError):
                    stats["files_skipped"] += 1
                    continue

                chash = hashlib.md5(content_raw.encode()).hexdigest()

                if not force:
                    existing = conn.execute(
                        "SELECT content_hash FROM coding_entries WHERE file_path = ?",
                        (str(file_path),),
                    ).fetchone()
                    if existing and existing["content_hash"] == chash:
                        stats["files_skipped"] += 1
                        continue

                entries = _parse_file(file_path)
                if not entries:
                    stats["files_skipped"] += 1
                    continue

                conn.execute(
                    "DELETE FROM coding_entries WHERE file_path = ?",
                    (str(file_path),),
                )

                for entry in entries:
                    entry_id = hashlib.md5(
                        f"{file_path}:{entry['title']}".encode()
                    ).hexdigest()[:12]

                    conn.execute(
                        """INSERT OR REPLACE INTO coding_entries
                           (id, title, file_path, content, memory_type, source_type,
                            language, framework, content_hash, indexed_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            entry_id,
                            entry["title"],
                            str(file_path),
                            entry["content"],
                            entry["memory_type"],
                            entry["source_type"],
                            entry.get("language"),
                            entry.get("framework"),
                            chash,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    stats["entries_created"] += 1

                stats["files_indexed"] += 1

            conn.commit()

        return stats

    def recall(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: int = 10,
        update_access: bool = True,
        namespaces: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        if not query.strip():
            cursor = conn.execute(
                """SELECT * FROM coding_entries ORDER BY indexed_at DESC LIMIT ?""",
                (limit,),
            )
        else:
            escaped = escape_like(query)
            cursor = conn.execute(
                """SELECT ce.*, rank
                   FROM coding_entries ce
                   JOIN coding_fts cf ON ce.rowid = cf.rowid
                   WHERE coding_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (escaped, limit),
            )

        results = []
        for row in cursor:
            result = dict(row)
            results.append(result)

        if filters:
            filtered = []
            for r in results:
                if "memory_type" in filters and r.get("memory_type") != filters["memory_type"]:
                    continue
                if "source_type" in filters and r.get("source_type") != filters["source_type"]:
                    continue
                if "language" in filters and r.get("language") != filters["language"]:
                    continue
                filtered.append(r)
            results = filtered

        return results[:limit]

    def get_conventions(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = {"source_type": "editor_config"}
        if language:
            filters["language"] = language
        return self.recall(query="", limit=50, filters=filters)

    def get_tech_stack(self) -> Dict[str, Any]:
        cursor = self._get_connection().execute(
            """SELECT DISTINCT language, framework FROM coding_entries
               WHERE source_type = 'project_meta'"""
        )
        stack = {}
        for row in cursor:
            lang = row["language"]
            fw = row["framework"]
            if lang:
                stack[lang] = fw or ""
        return stack

    def remember(self, *args, **kwargs) -> Any:
        raise NotImplementedError("CodingContextAdapter is read-only")

    def forget(self, *args, **kwargs) -> Any:
        raise NotImplementedError("CodingContextAdapter is read-only")

    def close(self):
        self._closed = True
        with self._conn_lock:
            for conn in self._all_connections.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        if hasattr(self._local, 'conn'):
            self._local.conn = None
