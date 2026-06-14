"""
CarryMem Rules Engine — Data Access Layer (SQLite)

Provides CRUD operations for rules with:
- SQLite persistence with FTS5 full-text search
- Thread-safe operations
- Automatic schema migration
- Index optimization for performance
"""

import json
import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from carrymem.utils.language import has_cjk

_logger = logging.getLogger(__name__)

from .models import Rule
from .sanitizer import RuleSanitizer


class RuleStorage:
    """
    SQLite-backed storage for rules.

    Manages the lifecycle of rule objects in a SQLite database,
    providing thread-safe CRUD operations and FTS5-based search.

    Usage:
        storage = RuleStorage("~/.carrymem/memories.db")
        rule = storage.create(trigger="写报告", action="控制在3页以内", rule_type="format")
        rules = storage.search("报告")  # FTS5 search
        storage.delete(rule_id)
    """

    def __init__(self, db_path: str):
        """
        Initialize storage with database connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = str(Path(db_path).expanduser().resolve())
        self._local = threading.local()
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            # Set busy_timeout FIRST so subsequent PRAGMAs respect it
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        else:
            try:
                self._local.conn.execute("SELECT 1")
            except (sqlite3.OperationalError, sqlite3.ProgrammingError) as e:
                _logger.debug("[RuleStorage] Connection health check failed, reconnecting: %s", e)
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                conn.row_factory = sqlite3.Row
                # Set busy_timeout FIRST so subsequent PRAGMAs respect it
                conn.execute("PRAGMA busy_timeout=10000")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                self._local.conn = conn
        return self._local.conn

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except sqlite3.Error as e:
                _logger.debug("[RuleStorage] close failed: %s", e)
            self._local.conn = None

    def _ensure_schema(self):
        """Create tables and indexes if they don't exist"""
        conn = self._get_connection()
        try:
            # Main rules table
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,

                    -- Core fields (NOT NULL)
                    trigger TEXT NOT NULL,
                    action TEXT NOT NULL,
                    rule_type TEXT NOT NULL CHECK(rule_type IN ('avoid','always','prefer','forbid','format')),

                    -- Metadata (JSON-encoded lists)
                    source_memories TEXT DEFAULT '[]',
                    derived_from TEXT NOT NULL DEFAULT 'manual',

                    -- State management
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','deprecated')),
                    override INTEGER NOT NULL DEFAULT 1,
                    confidence REAL NOT NULL DEFAULT 0.8,
                    trigger_count INTEGER NOT NULL DEFAULT 0,
                    confirmed_by_user INTEGER NOT NULL DEFAULT 1,
                    scope TEXT NOT NULL DEFAULT 'personal' CHECK(scope IN ('personal','company','negotiated')),

                    -- Timestamps
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    -- Extension
                metadata TEXT DEFAULT '{}'
            );
            """)

            try:
                pragma_cursor = conn.execute("PRAGMA table_info(rules)")
                columns = [row[1] for row in pragma_cursor.fetchall()]
                if "expires_at" not in columns:
                    conn.execute("ALTER TABLE rules ADD COLUMN expires_at TEXT DEFAULT ''")
                if "condition" not in columns:
                    conn.execute("ALTER TABLE rules ADD COLUMN condition TEXT DEFAULT ''")
            except (sqlite3.OperationalError, sqlite3.ProgrammingError) as e:
                _logger.debug("[RuleStorage] Schema migration (add columns) skipped: %s", e)

            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_rules_status ON rules(status);
                CREATE INDEX IF NOT EXISTS idx_rules_trigger ON rules(trigger);
                CREATE INDEX IF NOT EXISTS idx_rules_type ON rules(rule_type);
                CREATE INDEX IF NOT EXISTS idx_rules_scope ON rules(scope);

                -- Full-text search index for matching
                CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
                    id UNINDEXED,
                    trigger,
                    action,
                    content='rules',
                    content_rowid='rowid',
                    tokenize='trigram'
                );

                -- Triggers to keep FTS5 in sync
                CREATE TRIGGER IF NOT EXISTS rules_ai AFTER INSERT ON rules BEGIN
                    INSERT INTO rules_fts(rowid, id, trigger, action)
                    VALUES (new.rowid, new.id, new.trigger, new.action);
                END;

                CREATE TRIGGER IF NOT EXISTS rules_ad AFTER DELETE ON rules BEGIN
                    INSERT INTO rules_fts(rules_fts, rowid, id, trigger, action)
                    VALUES('delete', old.rowid, old.id, old.trigger, old.action);
                END;

                CREATE TRIGGER IF NOT EXISTS rules_au AFTER UPDATE ON rules BEGIN
                    INSERT INTO rules_fts(rules_fts, rowid, id, trigger, action)
                    VALUES('delete', old.rowid, old.id, old.trigger, old.action);
                    INSERT INTO rules_fts(rowid, id, trigger, action)
                    VALUES (new.rowid, new.id, new.trigger, new.action);
                END;
                """)
            conn.commit()
            self._migrate_fts_tokenizer()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            _logger.debug("[RuleStorage] _ensure_schema failed: %s", e)

    def _migrate_fts_tokenizer(self):
        """Migrate rules_fts from unicode61 to trigram tokenizer if needed."""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='rules_fts'").fetchone()
            if row and "unicode61" in (row[0] or ""):
                conn.execute("INSERT INTO rules_fts(rules_fts) VALUES('rebuild')")
                conn.commit()
                _logger.info("Migrated rules_fts from unicode61 to trigram tokenizer")
        except sqlite3.OperationalError as e:
            _logger.warning("FTS5 tokenizer migration skipped: %s", e)

    def _create_validated(
        self,
        trigger: str,
        action: str,
        rule_type: str = "avoid",
        override: bool = True,
        derived_from: str = "manual",
        source_memories: Optional[List[str]] = None,
        **kwargs,
    ) -> Rule:
        """
        Create and store a new rule WITHOUT re-validating.

        Used internally when validation has already been performed
        by the caller (e.g., RuleEngine.add_rule).

        Args:
            trigger: Pre-validated trigger string
            action: Pre-validated action string
            rule_type: Pre-validated rule type
            override: If True, AI cannot ignore this rule
            derived_from: How this rule was created
            source_memories: IDs of source memories if derived
            **kwargs: Additional fields

        Returns:
            Created Rule object
        """
        rule = Rule(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=override,
            derived_from=derived_from,
            source_memories=source_memories or [],
            **kwargs,
        )

        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO rules (
                    id, trigger, action, rule_type,
                    source_memories, derived_from,
                    status, override, confidence, trigger_count, confirmed_by_user, scope,
                    created_at, updated_at, expires_at, condition, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.id,
                    rule.trigger,
                    rule.action,
                    rule.rule_type,
                    json.dumps(rule.source_memories),
                    rule.derived_from,
                    rule.status,
                    1 if rule.override else 0,
                    rule.confidence,
                    rule.trigger_count,
                    1 if rule.confirmed_by_user else 0,
                    rule.scope,
                    rule.created_at,
                    rule.updated_at,
                    rule.expires_at,
                    rule.condition,
                    json.dumps(rule.metadata),
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] _create_validated insert failed: %s", e)

        return rule

    def create(
        self,
        trigger: str,
        action: str,
        rule_type: str = "avoid",
        override: bool = True,
        derived_from: str = "manual",
        source_memories: Optional[List[str]] = None,
        **kwargs,
    ) -> Rule:
        """
        Create and store a new rule.

        Args:
            trigger: Scene description that activates this rule
            action: Behavioral instruction to execute
            rule_type: Type of rule (avoid/always/prefer/forbid/format)
            override: If True, AI cannot ignore this rule
            derived_from: How this rule was created
            source_memories: IDs of source memories if derived
            **kwargs: Additional fields (confidence, metadata, etc.)

        Returns:
            Created Rule object

        Raises:
            ValueError: If validation fails
        """
        # Validate input through sanitizer
        trigger = RuleSanitizer.validate_trigger(trigger)
        action = RuleSanitizer.validate_action(action)
        RuleSanitizer.validate_rule_type(rule_type)

        # Create rule object
        rule = Rule(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=override,
            derived_from=derived_from,
            source_memories=source_memories or [],
            **kwargs,
        )

        # Insert into database
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO rules (
                    id, trigger, action, rule_type,
                    source_memories, derived_from,
                    status, override, confidence, trigger_count, confirmed_by_user, scope,
                    created_at, updated_at, expires_at, condition, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.id,
                    rule.trigger,
                    rule.action,
                    rule.rule_type,
                    json.dumps(rule.source_memories),
                    rule.derived_from,
                    rule.status,
                    1 if rule.override else 0,
                    rule.confidence,
                    rule.trigger_count,
                    1 if rule.confirmed_by_user else 0,
                    rule.scope,
                    rule.created_at,
                    rule.updated_at,
                    rule.expires_at,
                    rule.condition,
                    json.dumps(rule.metadata),
                ),
            )
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            _logger.debug("[RuleStorage] create insert failed: %s", e)

        return rule

    def get(self, rule_id: str) -> Optional[Rule]:
        """
        Retrieve a rule by ID.

        Args:
            rule_id: Unique rule identifier

        Returns:
            Rule object or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_rule(row)
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] get failed: %s", e)

    def list_all(
        self,
        status: Optional[str] = None,
        rule_type: Optional[str] = None,
        scope: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Rule]:
        """
        List rules with optional filtering.

        Args:
            status: Filter by status (active/paused/deprecated)
            rule_type: Filter by type
            scope: Filter by scope (personal/company/negotiated)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of Rule objects
        """
        query = "SELECT * FROM rules WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if rule_type:
            query += " AND rule_type = ?"
            params.append(rule_type)

        if scope:
            query += " AND scope = ?"
            params.append(scope)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_connection()
        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_rule(row) for row in rows]
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] list_all failed: %s", e)

    @staticmethod
    def _estimate_rank(rule: Rule, query_text: str) -> float:
        """Estimate a rank score for fallback search results."""
        query_lower = query_text.lower()
        score = 0.5
        if query_lower in rule.trigger.lower():
            score += 0.3
        if query_lower in rule.action.lower():
            score += 0.1
        query_words = set(query_lower.split())
        trigger_words = set(rule.trigger.lower().split())
        overlap = query_words & trigger_words
        if overlap:
            score += 0.2 * (len(overlap) / max(len(query_words), 1))
        return min(score, 1.0)

    @staticmethod
    def _sanitize_field(value: str, field_name: str) -> str:
        danger_pattern = re.compile(
            r"(?:ignore\s+(?:previous|above|all)\s+(?:instructions?|rules?)|"
            r"system\s*[:：]\s*|"
            r"forget\s+(?:all\s+)?(?:rules?|instructions?)|"
            r"you\s+are\s+now|"
            r"(?:DAN|jailbreak|developer)\s+mode|"
            r"bypass\s+(?:all\s+)?(?:restrictions?|filters?|safety)|"
            r"\$\{.*?\}|\{\{.*?\}\}|"
            r"eval\(|exec\(|__import__)",
            re.IGNORECASE,
        )
        if danger_pattern.search(value):
            raise ValueError(f"Potentially unsafe content in {field_name}")
        return value[:500]

    @staticmethod
    def _sanitize_fts_query(query_text: str) -> str:
        cleaned = re.sub(r"[{}():^!|*]", " ", query_text)
        cleaned = re.sub(r"\b(NEAR|NOT|OR|AND|COLUMN)\b", " ", cleaned, flags=re.IGNORECASE)
        terms = [t for t in cleaned.split()[:20] if t.strip()]
        if not terms:
            return ""
        if len(terms) == 1:
            return terms[0]
        return " ".join(f'"{t}"' for t in terms)

    def search(self, query_text: str, limit: int = 20) -> List[Rule]:
        safe_query = self._sanitize_fts_query(query_text)
        if not safe_query.strip():
            return []
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT r.id, r.trigger, r.action, r.rule_type,
                       r.source_memories, r.derived_from,
                       r.status, r.override, r.confidence,
                       r.trigger_count, r.confirmed_by_user, r.scope,
                       r.created_at, r.updated_at, r.metadata,
                       r.expires_at, r.condition
                FROM rules r
                JOIN rules_fts fts ON r.rowid = fts.rowid
                WHERE rules_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, limit),
            )
            rows = cursor.fetchall()
            results = [self._row_to_rule(row) for row in rows]
            if results:
                return results
        except sqlite3.OperationalError as e:
            _logger.warning("FTS5 search failed (%s), falling back to LIKE", e)
        if has_cjk(query_text) or len(query_text) < 3:
            like_results = self._fallback_search(query_text, limit)
            if like_results:
                return like_results
        return self._fallback_search(query_text, limit)

    def search_with_rank(self, query_text: str, limit: int = 20) -> List[tuple]:
        safe_query = self._sanitize_fts_query(query_text)
        if not safe_query.strip():
            return []
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT r.id, r.trigger, r.action, r.rule_type,
                       r.source_memories, r.derived_from,
                       r.status, r.override, r.confidence,
                       r.trigger_count, r.confirmed_by_user, r.scope,
                       r.created_at, r.updated_at, r.metadata,
                       r.expires_at, r.condition,
                       bm25(rules_fts) as rank_score
                FROM rules r
                JOIN rules_fts fts ON r.rowid = fts.rowid
                WHERE rules_fts MATCH ?
                ORDER BY rank_score
                LIMIT ?
                """,
                (safe_query, limit),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                rule = self._row_to_rule(row[:17])
                rank_score = row[17] if len(row) > 17 else 0.0
                results.append((rule, rank_score))
            if results:
                return results
        except sqlite3.OperationalError as e:
            _logger.warning("FTS5 search_with_rank failed (%s), falling back", e)
        if has_cjk(query_text) or len(query_text) < 3:
            like_rules = self._fallback_search(query_text, limit)
            if like_rules:
                return [(r, self._estimate_rank(r, query_text)) for r in like_rules]
        rules = self._fallback_search(query_text, limit)
        return [(r, self._estimate_rank(r, query_text)) for r in rules]

    def _fallback_search(self, query_text: str, limit: int) -> List[Rule]:
        """Fallback to LIKE-based search if FTS5 fails"""
        conn = self._get_connection()
        try:
            escaped = query_text.replace("%", "\\%").replace("_", "\\_")
            like_pattern = f"%{escaped}%"
            cursor = conn.execute(
                """
                SELECT * FROM rules
                WHERE (trigger LIKE ? ESCAPE '\\' OR action LIKE ? ESCAPE '\\')
                AND status = 'active'
                AND (expires_at = '' OR expires_at IS NULL OR expires_at > datetime('now'))
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (like_pattern, like_pattern, limit),
            )
            rows = cursor.fetchall()
            return [self._row_to_rule(row) for row in rows]
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] _fallback_search failed: %s", e)

    def update(self, rule_id: str, **updates) -> Optional[Rule]:
        existing = self.get(rule_id)
        if existing is None:
            return None

        if "trigger" in updates and updates["trigger"]:
            updates["trigger"] = self._sanitize_field(updates["trigger"], "trigger")
        if "action" in updates and updates["action"]:
            updates["action"] = self._sanitize_field(updates["action"], "action")

        set_clauses = []
        params = []
        allowed_fields = {
            "trigger": "trigger",
            "action": "action",
            "rule_type": "rule_type",
            "status": "status",
            "override": "override",
            "confidence": "confidence",
            "metadata": "metadata",
            "source_memories": "source_memories",
            "scope": "scope",
            "expires_at": "expires_at",
            "condition": "condition",
        }

        for field, col_name in allowed_fields.items():
            if field in updates:
                value = updates[field]
                if field in ("metadata", "source_memories"):
                    value = json.dumps(value)
                elif field == "override":
                    value = 1 if value else 0
                set_clauses.append(f"{col_name} = ?")
                params.append(value)

        if not set_clauses:
            return existing

        # Always update timestamp
        from datetime import datetime, timezone

        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(rule_id)

        conn = self._get_connection()
        try:
            conn.execute(f"UPDATE rules SET {', '.join(set_clauses)} WHERE id = ?", params)
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            _logger.debug("[RuleStorage] update failed: %s", e)

        return self.get(rule_id)

    def delete(self, rule_id: str) -> bool:
        """
        Delete a rule by ID.

        Args:
            rule_id: ID of rule to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] delete failed: %s", e)
            return False

    def count(self, status: Optional[str] = None) -> int:
        """
        Count total rules, optionally filtered by status.

        Args:
            status: Filter by status

        Returns:
            Count of rules
        """
        conn = self._get_connection()
        try:
            if status:
                cursor = conn.execute("SELECT COUNT(*) FROM rules WHERE status = ?", (status,))
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM rules")
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] count failed: %s", e)
            return 0

    def get_active_global_rules(self) -> List[Rule]:
        """
        Get all active global rules (trigger="*").

        Returns:
            List of active global rules
        """
        all_active = self.list_all(status="active", limit=1000)
        return [r for r in all_active if r.trigger == "*"]

    def increment_trigger_count(self, rule_id: str) -> bool:
        """
        Atomically increment the trigger_count of a rule.

        Uses a single UPDATE statement for atomicity — no read-then-write race.

        Args:
            rule_id: ID of rule to increment

        Returns:
            True if rule was found and updated, False otherwise
        """
        from datetime import datetime, timezone

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE rules
                SET trigger_count = trigger_count + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), rule_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] increment_trigger_count failed: %s", e)
            return False

    def batch_increment_trigger_counts(self, rule_ids: List[str]) -> int:
        """
        Atomically increment trigger_count for multiple rules.

        Args:
            rule_ids: List of rule IDs to increment

        Returns:
            Number of rules successfully updated
        """
        if not rule_ids:
            return 0

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        updated = 0

        conn = self._get_connection()
        try:
            for rule_id in rule_ids:
                cursor = conn.execute(
                    """
                    UPDATE rules
                    SET trigger_count = trigger_count + 1,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, rule_id),
                )
                updated += cursor.rowcount
            conn.commit()
        except sqlite3.Error as e:
            _logger.debug("[RuleStorage] batch_increment_trigger_counts failed: %s", e)

        return updated

    _RULE_COLUMNS = [
        "id", "trigger", "action", "rule_type",
        "source_memories", "derived_from",
        "status", "override", "confidence",
        "trigger_count", "confirmed_by_user", "scope",
        "created_at", "updated_at", "metadata",
        "expires_at", "condition",
    ]

    def _row_to_rule(self, row) -> Rule:
        """Convert SQLite Row object or tuple to Rule dataclass"""
        if hasattr(row, "keys"):
            return Rule.from_dict(dict(zip(row.keys(), row)))
        return Rule.from_dict(dict(zip(self._RULE_COLUMNS, row)))
