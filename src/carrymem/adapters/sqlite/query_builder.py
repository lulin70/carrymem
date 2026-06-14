"""Query building utilities for SQLiteAdapter."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from ...utils.language import _STOP_WORDS

_QUERY_EXPANSIONS = {
    "theme": ["dark mode", "light mode", "theme preference"],
    "database": ["postgresql", "mysql", "database selection", "database choice", "decided to use", "sqlite"],
    "db": ["database", "sqlite", "postgresql", "mysql"],
    "api": ["api rate", "api design", "graphql", "rest", "rate limit"],
    "typescript": ["typescript strict", "typescript configuration"],
    "cloud": ["aws", "gcp", "cloud hosting", "cloud provider", "chose aws"],
    "deployment": ["deploy", "friday", "deployment rules", "never deploy"],
    "server": ["server address", "server port", "staging server", "ip", "staging"],
    "cache": ["redis", "cache ttl", "cache settings"],
    "workflow": ["trunk-based", "development workflow", "git workflow", "trunk"],
    "design": ["composition", "inheritance", "design pattern", "class design"],
    "editor": ["vscode", "intellij", "ide", "vim"],
    "language": ["python", "programming language"],
    "indentation": ["spaces", "tabs", "indentation style"],
    "version": ["git", "version control", "github"],
    "security": ["oauth", "jwt", "authentication", "tls"],
    "framework": ["react", "vue", "angular", "django", "flask", "frontend", "backend"],
    "preference": ["prefer", "like", "always use", "never"],
    "ip": ["staging server", "server address", "10.0"],
    "port": ["server port", "9090", "8080"],
    "数据库": ["postgresql", "mysql", "database"],
    "偏好": ["prefer", "like", "preference"],
    "深色": ["dark mode", "dark theme"],
    "主题": ["theme", "theme preference"],
    "ダークモード": ["dark mode", "dark theme"],
    "データベース": ["database", "postgresql", "mysql"],
}

_ALLOWED_FILTER_KEYS = {
    "type",
    "tier",
    "confidence_min",
    "created_after",
    "created_before",
    "session_id",
    "include_superseded",
    "_order_oldest",
    "include_session_summary",
}

_TIME_EXPRESSIONS = [
    (r"\b(recently|lately|just)\b", 7, False),
    (r"\b(this\s+week|past\s+week|last\s+week)\b", 7, False),
    (r"\b(this\s+month|past\s+month|last\s+month)\b", 30, False),
    (r"\b(recent|latest|newest|current)\b", 14, False),
    (r"\b(today|yesterday)\b", 2, False),
    (r"\b(first|initial|earliest|original)\b", None, True),
    (r"\b(before|prior\s+to|earlier)\b", None, False),
    (r"\b(after|since|following)\b", None, False),
    (r"\b(last\s+year|previous\s+year)\b", 365, False),
    (r"\b(\d+)\s+(days?|weeks?|months?)\s+ago\b", None, False),
]

_VALID_MEMORY_TYPES = {
    "user_preference",
    "correction",
    "fact_declaration",
    "decision",
    "relationship",
    "task_pattern",
    "sentiment_marker",
    "session_summary",
}


class QueryBuilder:
    """Builds and expands queries for recall operations."""

    @staticmethod
    def expand_query(query: str) -> List[str]:
        """Expand a short query with related terms for better recall."""
        query_lower = query.lower().strip()
        words = [w for w in query_lower.split() if w not in _STOP_WORDS and len(w) > 1]
        expanded = []

        for word in words:
            for key, terms in _QUERY_EXPANSIONS.items():
                if key == word or key in word or word in key:
                    expanded.extend(terms)

        if not expanded:
            for word in words:
                if len(word) > 2:
                    expanded.append(word)

        return expanded

    @staticmethod
    def parse_time_expressions(query: str) -> Dict[str, Any]:
        if not query:
            return {}

        result = {}
        query_lower = query.lower()

        for pattern, days, is_oldest in _TIME_EXPRESSIONS:
            m = re.search(pattern, query_lower)
            if not m:
                continue

            if is_oldest:
                result["order_oldest"] = True
                continue

            if days is not None:
                result["created_after"] = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                continue

            ago_match = re.search(r"(\d+)\s+(days?|weeks?|months?)\s+ago", query_lower)
            if ago_match:
                n = int(ago_match.group(1))
                unit = ago_match.group(2)
                if "day" in unit:
                    delta = timedelta(days=n)
                elif "week" in unit:
                    delta = timedelta(weeks=n)
                elif "month" in unit:
                    delta = timedelta(days=n * 30)
                else:
                    delta = timedelta(days=n)
                result["created_after"] = (datetime.now(timezone.utc) - delta).isoformat()
                continue

        return result

    @staticmethod
    def sanitize_fts_query(query: str) -> str:
        """Sanitize a query string for FTS5 MATCH."""
        from ...utils.language import has_cjk

        tokens = query.strip().split()
        sanitized = []
        for token in tokens:
            clean = token.replace('"', "").strip()
            if not clean:
                continue
            if has_cjk(clean):
                sanitized.append(clean)
            else:
                sanitized.append(f'"{clean}"')
        return " ".join(sanitized)


class QueryBuilderWithContext(QueryBuilder):
    """QueryBuilder that can rebuild context using DB profile data."""

    def __init__(self, adapter):
        self._adapter = adapter

    def rebuild_context(self, original_query: str, keywords: str) -> str:
        if not keywords:
            return original_query

        try:
            conn = self._adapter._conn_mgr.get_connection()
            profile_rows = conn.execute(
                "SELECT content, type FROM memories "
                "WHERE namespace = ? AND type IN ('user_preference', 'decision', 'fact_declaration') "
                "AND (superseded_at IS NULL OR superseded_at = '') "
                "ORDER BY importance_score DESC LIMIT 5",
                (self._adapter.namespace,),
            ).fetchall()
        except sqlite3.OperationalError as e:
            logger = __import__("logging").getLogger(__name__)
            logger.debug("_rebuild_context query failed: %s", e)
            return original_query

        if not profile_rows:
            return original_query

        query_words = set(keywords.lower().split())
        context_words = set()
        for row in profile_rows:
            content = (row["content"] or "").lower()
            content_words = set(content.split())
            overlap = query_words & content_words
            if overlap:
                context_words.update(content_words - query_words)

        if not context_words:
            return original_query

        extra = " ".join(w for w in list(context_words)[:5] if len(w) > 2)
        if extra:
            return f"{keywords} {extra}"
        return original_query
