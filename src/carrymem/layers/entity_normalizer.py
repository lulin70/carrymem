"""Entity normalization layer (Ontology-lite).

Rule-based entity extraction + difflib.SequenceMatcher fuzzy matching (ratio >= 0.8)
to map surface forms to canonical forms. Zero LLM dependency.

Security corrections implemented (per v0.5.0 spec §8.3):
  - C15: fuzzy match constrained to same entity_type + length diff <= 3 + first 2 chars match
  - C16: alias_form/canonical_form sanitized via InputValidator.sanitize_content()
  - C18: namespace must come from adapter (trusted), not memory.metadata (user-controllable)
  - C19: ENTITY_MERGE audit log emitted on merge_entities()
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, cast

from carrymem.utils.logger import logger

# Env switch (default enabled per spec §4.1.4)
_ENTITY_NORMALIZATION_ENV = "CARRYMEM_ENTITY_NORMALIZATION"


def is_entity_normalization_enabled() -> bool:
    """Return True unless CARRYMEM_ENTITY_NORMALIZATION=0 explicitly disables."""
    return os.environ.get(_ENTITY_NORMALIZATION_ENV, "1") != "0"


# Stopwords filtered from capitalized-phrase extraction (avoid false positives
# like "The", "This", "It" being treated as entities).
_STOPWORDS = {
    "the",
    "this",
    "that",
    "these",
    "those",
    "it",
    "is",
    "was",
    "are",
    "were",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "then",
    "else",
    "for",
    "to",
    "of",
    "in",
    "on",
    "at",
    "by",
    "with",
    "from",
    "as",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "can",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "its",
    "our",
    "their",
    "what",
    "which",
    "who",
    "whom",
    "where",
    "when",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "now",
    "here",
    "there",
}

# Entity extraction patterns:
# 1. Acronyms: 2-6 uppercase letters (API, SDK, HTTP, SQL, REST, GraphQL)
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}\b")
# 2. CamelCase terms: PostgreSQL, JavaScript, EntityNormalizer
_CAMELCASE_RE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
# 3. hyphenated/underscored tool names: entity-normalizer, rule_based
_TOOL_RE = re.compile(r"\b[a-zA-Z]+(?:[-_][a-zA-Z]+)+\b")
# 4. Capitalized phrases (1+ words): REST API, Memory Engine
_PHRASE_RE = re.compile(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b")

_MAX_ENTITIES_PER_TEXT = 50  # perf guard
_MAX_ENTITY_LENGTH = 80
_FUZZY_CANDIDATE_LIMIT = 200  # max candidates scanned per fuzzy match


@dataclass
class NormalizeResult:
    """Result of entity normalization for a text."""

    entities: List[Dict[str, Any]] = field(default_factory=list)
    new_aliases: int = 0

    def to_metadata(self) -> Dict[str, Any]:
        """Return a metadata dict safe to merge into MemoryEntry.metadata."""
        return {
            "entities": [
                {
                    "canonical": e["canonical"],
                    "alias": e["alias"],
                    "type": e["type"],
                    "score": round(e["score"], 4),
                }
                for e in self.entities
            ],
            "new_aliases": self.new_aliases,
        }


class EntityNormalizer:
    """Rule-based entity normalization (Ontology-lite).

    Uses difflib.SequenceMatcher (ratio >= 0.8) for fuzzy matching, borrowing
    cognee's 80% cutoff. No LLM dependency. Aliases are persisted per-namespace
    (privacy isolation — no cross-namespace normalization per spec §8.1).
    """

    SIMILARITY_THRESHOLD = 0.8  # cognee 80% cutoff

    def __init__(self, conn_mgr: Any, input_validator: Optional[Any] = None):
        """Initialize the normalizer.

        Args:
            conn_mgr: ConnectionManager providing sqlite3 connections.
            input_validator: InputValidator instance for C16 sanitization.
                If None, a minimal sanitizer is used (strip + null-byte removal).
        """
        self._conn_mgr = conn_mgr
        self._input_validator = input_validator

    def normalize(self, text: str, namespace: str) -> NormalizeResult:
        """Extract entities from text and normalize to canonical forms.

        Args:
            text: Input text (post-coreference, pre-storage).
            namespace: Trusted namespace from adapter (C18). Used for isolation.

        Returns:
            NormalizeResult with entities list and new_aliases count.
        """
        if not is_entity_normalization_enabled():
            return NormalizeResult()

        if not text or not text.strip():
            return NormalizeResult()

        safe_ns = self._validate_namespace(namespace)
        if not safe_ns:
            return NormalizeResult()

        candidates = self._extract_entities(text)
        if not candidates:
            return NormalizeResult()

        result = NormalizeResult()
        seen_canonicals: Dict[str, str] = {}  # alias_lower -> canonical (dedup within text)

        for alias_form, entity_type in candidates:
            if len(result.entities) >= _MAX_ENTITIES_PER_TEXT:
                break

            canonical, score, is_new = self._normalize_entity(alias_form, entity_type, safe_ns)
            if not canonical:
                continue

            dedup_key = alias_form.lower()
            if dedup_key in seen_canonicals:
                continue
            seen_canonicals[dedup_key] = canonical

            result.entities.append(
                {
                    "canonical": canonical,
                    "alias": alias_form,
                    "type": entity_type,
                    "score": score,
                }
            )
            if is_new:
                result.new_aliases += 1

        return result

    def list_entities(self, namespace: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List canonical entities and their alias counts for a namespace.

        Args:
            namespace: Trusted namespace from adapter.
            limit: Max entities to return.

        Returns:
            List of {canonical, entity_type, alias_count, last_alias}.
        """
        safe_ns = self._validate_namespace(namespace)
        if not safe_ns:
            return []

        conn = self._conn_mgr.get_connection()
        try:
            rows = conn.execute(
                """
                SELECT canonical_form, entity_type, COUNT(*) as alias_count,
                       MAX(created_at) as last_alias
                FROM entity_aliases
                WHERE namespace = ?
                GROUP BY canonical_form, entity_type
                ORDER BY alias_count DESC, last_alias DESC
                LIMIT ?
                """,
                (safe_ns, limit),
            ).fetchall()
            return [
                {
                    "canonical": row["canonical_form"],
                    "entity_type": row["entity_type"],
                    "alias_count": row["alias_count"],
                    "last_alias": row["last_alias"],
                }
                for row in rows
            ]
        except (sqlite3.Error, KeyError, IndexError) as e:
            logger.warning("list_entities failed: %s", e)
            return []

    def merge_entities(self, source_canonical: str, target_canonical: str, namespace: str) -> int:
        """Merge source canonical into target canonical (repoint all aliases).

        Emits ENTITY_MERGE audit log per C19.

        Args:
            source_canonical: Canonical form to merge away (will be repointed).
            target_canonical: Canonical form to merge into.
            namespace: Trusted namespace from adapter.

        Returns:
            Number of aliases repointed.
        """
        safe_ns = self._validate_namespace(namespace)
        if not safe_ns:
            return 0

        source = self._sanitize(source_canonical)
        target = self._sanitize(target_canonical)
        if not source or not target or source == target:
            return 0

        conn = self._conn_mgr.get_connection()
        repointed = 0
        try:
            # Repoint all aliases currently pointing to source -> target.
            # INSERT OR IGNORE preserves UNIQUE(canonical, alias, namespace)
            # in case the alias already exists under target.
            existing = conn.execute(
                "SELECT alias_form, entity_type, similarity_score FROM entity_aliases "
                "WHERE canonical_form = ? AND namespace = ?",
                (source, safe_ns),
            ).fetchall()
            for row in existing:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO entity_aliases "
                        "(canonical_form, alias_form, entity_type, namespace, similarity_score, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            target,
                            row["alias_form"],
                            row["entity_type"],
                            safe_ns,
                            row["similarity_score"],
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    repointed += 1
                except sqlite3.Error as e:
                    logger.debug("merge_entities insert skipped: %s", e)
            # Remove old source aliases
            conn.execute(
                "DELETE FROM entity_aliases WHERE canonical_form = ? AND namespace = ?",
                (source, safe_ns),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.warning("merge_entities failed: %s", e)
            return 0

        # C19: audit log
        logger.info(
            "ENTITY_MERGE source=%s target=%s namespace=%s repointed=%d",
            source,
            target,
            safe_ns,
            repointed,
        )
        return repointed

    # ── Internal: extraction ──────────────────────────────────────────

    def _extract_entities(self, text: str) -> List[tuple]:
        """Extract candidate (alias_form, entity_type) pairs from text.

        Types:
          - acronym: ALL_CAPS 2-6 chars (API, SDK)
          - concept: CamelCase or capitalized phrases (PostgreSQL, REST API)
          - tool: hyphenated/underscored (entity-normalizer, rule_based)
        """
        candidates: List[tuple] = []
        seen_spans: set = set()

        # Order matters: acronyms first (most specific), then camelcase,
        # then tools, then phrases (broadest).
        for pattern, entity_type in (
            (_ACRONYM_RE, "acronym"),
            (_CAMELCASE_RE, "concept"),
            (_TOOL_RE, "tool"),
            (_PHRASE_RE, "concept"),
        ):
            for m in pattern.finditer(text):
                span = m.span()
                if span in seen_spans:
                    continue
                alias = m.group()
                if len(alias) > _MAX_ENTITY_LENGTH:
                    continue
                # Skip single capitalized stopwords ("The", "This")
                if entity_type == "concept" and alias.lower() in _STOPWORDS:
                    continue
                # Skip phrases whose first word is a stopword ("The API")
                if " " in alias and alias.split()[0].lower() in _STOPWORDS:
                    continue
                seen_spans.add(span)
                candidates.append((alias, entity_type))

        return candidates

    # ── Internal: normalization ───────────────────────────────────────

    def _normalize_entity(self, alias_form: str, entity_type: str, namespace: str) -> tuple:
        """Normalize a single alias to its canonical form.

        Returns:
            (canonical_form, similarity_score, is_new_alias) or ("", 0.0, False) on failure.
        """
        safe_alias = self._sanitize(alias_form)
        if not safe_alias:
            return ("", 0.0, False)

        # 1. Exact match: alias already mapped
        existing = self._lookup_exact(safe_alias, namespace)
        if existing:
            return (existing["canonical_form"], 1.0, False)

        # 2. C15 fuzzy match: same entity_type + length diff <= 3 + first 2 chars match
        fuzzy = self._lookup_fuzzy(safe_alias, entity_type, namespace)
        if fuzzy:
            canonical = fuzzy["canonical_form"]
            score = fuzzy["similarity_score"]
            # Persist this new alias pointing to the fuzzy-matched canonical
            self._persist_alias(canonical, safe_alias, entity_type, namespace, score)
            return (canonical, score, True)

        # 3. New canonical: alias becomes its own canonical
        self._persist_alias(safe_alias, safe_alias, entity_type, namespace, 1.0)
        return (safe_alias, 1.0, True)

    def _lookup_exact(self, alias_form: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Look up an exact alias match in entity_aliases."""
        conn = self._conn_mgr.get_connection()
        try:
            row = conn.execute(
                "SELECT canonical_form, entity_type, similarity_score FROM entity_aliases "
                "WHERE alias_form = ? AND namespace = ? LIMIT 1",
                (alias_form, namespace),
            ).fetchone()
            if row:
                return {
                    "canonical_form": row["canonical_form"],
                    "entity_type": row["entity_type"],
                    "similarity_score": row["similarity_score"],
                }
        except (sqlite3.Error, KeyError, IndexError) as e:
            logger.debug("exact lookup failed: %s", e)
        return None

    def _lookup_fuzzy(self, alias_form: str, entity_type: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Find a fuzzy match (C15 constraints + ratio >= 0.8).

        C15: same entity_type + |len(alias) - len(canonical_or_existing_alias)| <= 3
             + first 2 chars match
        """
        conn = self._conn_mgr.get_connection()
        try:
            # Pull candidate aliases for this namespace + entity_type, limited
            # to those sharing the first 2 chars (index-friendly via LIKE).
            prefix = alias_form[:2].replace("%", r"\%").replace("_", r"\_")
            rows = conn.execute(
                "SELECT canonical_form, alias_form, similarity_score FROM entity_aliases "
                "WHERE namespace = ? AND entity_type = ? AND alias_form LIKE ? ESCAPE '\\' "
                "LIMIT ?",
                (namespace, entity_type, f"{prefix}%", _FUZZY_CANDIDATE_LIMIT),
            ).fetchall()
        except (sqlite3.Error, KeyError, IndexError) as e:
            logger.debug("fuzzy lookup failed: %s", e)
            return None

        best_score = 0.0
        best_canonical: Optional[str] = None
        alias_len = len(alias_form)
        for row in rows:
            candidate = row["alias_form"]
            # C15: length diff <= 3
            if abs(len(candidate) - alias_len) > 3:
                continue
            # C15: first 2 chars already match via LIKE, but double-check defensively
            if candidate[:2].lower() != alias_form[:2].lower():
                continue
            ratio = SequenceMatcher(None, alias_form.lower(), candidate.lower()).ratio()
            if ratio >= self.SIMILARITY_THRESHOLD and ratio > best_score:
                best_score = ratio
                best_canonical = row["canonical_form"]

        if best_canonical is None:
            return None
        return {
            "canonical_form": best_canonical,
            "similarity_score": best_score,
        }

    def _persist_alias(
        self,
        canonical_form: str,
        alias_form: str,
        entity_type: str,
        namespace: str,
        similarity_score: float,
    ) -> None:
        """Persist an alias mapping (idempotent via UNIQUE constraint)."""
        conn = self._conn_mgr.get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO entity_aliases "
                "(canonical_form, alias_form, entity_type, namespace, similarity_score, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    canonical_form,
                    alias_form,
                    entity_type,
                    namespace,
                    float(similarity_score),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.debug("persist_alias skipped: %s", e)

    # ── Internal: sanitization & validation ───────────────────────────

    def _sanitize(self, value: str) -> str:
        """C16: sanitize alias_form/canonical_form via InputValidator."""
        if self._input_validator is not None:
            try:
                return cast(str, self._input_validator.sanitize_content(value))
            except Exception as e:  # pragma: no cover — NOTE: intentional defensive fallback for sanitize
                logger.debug("InputValidator.sanitize_content failed: %s", e)
        # Minimal fallback: null-byte strip + whitespace strip
        return value.replace("\x00", "").strip()

    @staticmethod
    def _validate_namespace(namespace: str) -> str:
        """Validate namespace format. Returns sanitized namespace or empty string.

        Namespace must come from adapter (C18), but we still validate format
        defensively in case of upstream bugs.
        """
        if not namespace or not isinstance(namespace, str):
            return ""
        ns = namespace.strip().lower()
        if not ns or not re.match(r"^[a-zA-Z0-9_-]+$", ns):
            return ""
        return ns


def build_entity_normalized_json(result: NormalizeResult) -> str:
    """Build the JSON payload for memories.entity_normalized column.

    Schema: [{"canonical": "REST API", "type": "concept"}]
    Returns empty string for empty result (NULL-able column).
    """
    if not result.entities:
        return ""
    payload = [{"canonical": e["canonical"], "type": e["type"]} for e in result.entities]
    return json.dumps(payload, ensure_ascii=False)
