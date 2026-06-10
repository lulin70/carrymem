"""
Experience Rule Bridge — Convert failure lessons into rule candidates.
[RESERVED] Rule-engine extension point — not yet integrated into main pipeline.
Planned for v0.4.0 auto-rule-generation feature.

Bridges FailureExperienceExtractor output to the rule creation system.
Provides a confirmation workflow where users review extracted lessons
before they become active rules.

Workflow:
    1. Extract lessons from failure memories
    2. Queue lessons as pending candidates (experience_audit table)
    3. User reviews and accepts/rejects
    4. Accepted lessons become active "avoid" rules

Audit trail: every experience→rule action is logged.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .failure_experience import (
    ExtractedLesson,
    FailureConfidence,
    FailureExperienceExtractor,
)
from .sanitizer import RuleSanitizer
from .storage import RuleStorage

EXPERIENCE_STATUS_PENDING = "pending"
EXPERIENCE_STATUS_ACCEPTED = "accepted"
EXPERIENCE_STATUS_REJECTED = "rejected"
EXPERIENCE_STATUS_EXPIRED = "expired"

VALID_EXPERIENCE_STATUSES = frozenset(
    {
        EXPERIENCE_STATUS_PENDING,
        EXPERIENCE_STATUS_ACCEPTED,
        EXPERIENCE_STATUS_REJECTED,
        EXPERIENCE_STATUS_EXPIRED,
    }
)

DEFAULT_EXPIRY_DAYS = 14
MAX_PENDING_LESSONS = 30

_CONFIDENCE_SCORE_MAP = {
    FailureConfidence.HIGH: 0.9,
    FailureConfidence.MEDIUM: 0.7,
    FailureConfidence.LOW: 0.5,
}


@dataclass
class ExperienceAuditEntry:
    id: str
    source_memory_id: str
    source_content: str
    failure_signal: str
    lesson: str
    trigger_hint: str
    action_hint: str
    confidence: float
    status: str
    domain: str
    created_at: str
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None
    resulting_rule_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_memory_id": self.source_memory_id,
            "source_content": self.source_content,
            "failure_signal": self.failure_signal,
            "lesson": self.lesson,
            "trigger_hint": self.trigger_hint,
            "action_hint": self.action_hint,
            "confidence": self.confidence,
            "status": self.status,
            "domain": self.domain,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "review_note": self.review_note,
            "resulting_rule_id": self.resulting_rule_id,
        }


class ExperienceRuleBridge:
    """Bridge failure experiences to rule candidates with confirmation workflow."""

    def __init__(self, storage: RuleStorage, expiry_days: int = DEFAULT_EXPIRY_DAYS):
        self.storage = storage
        self.extractor = FailureExperienceExtractor()
        self.expiry_days = expiry_days
        self._audit_table_ensured = False
        self._ensure_audit_table()
        self._audit_table_ensured = True

    def _ensure_audit_table(self):
        """Create experience_audit table if not exists."""
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experience_audit (
                    id TEXT PRIMARY KEY,
                    source_memory_id TEXT NOT NULL,
                    source_content TEXT NOT NULL,
                    failure_signal TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    trigger_hint TEXT NOT NULL,
                    action_hint TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','accepted','rejected','expired')),
                    domain TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    review_note TEXT,
                    resulting_rule_id TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_experience_status
                ON experience_audit(status)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_experience_source
                ON experience_audit(source_memory_id)
            """
            )
            conn.commit()
        finally:
            pass

    def extract_lessons(
        self,
        memories: List[Dict],
        memory_type: Optional[str] = None,
    ) -> Dict:
        """
        Extract failure lessons from memories and queue for review.

        Args:
            memories: List of memory dicts from CarryMem.recall_memories
            memory_type: Optional filter for specific memory type

        Returns:
            Dictionary with extraction results
        """
        if not memories:
            return {
                "lessons_found": 0,
                "candidates_queued": 0,
                "skipped_already_processed": 0,
            }

        lessons = self.extractor.extract(memories, memory_type=memory_type)

        queued = 0
        skipped = 0
        existing_sources = self._get_processed_source_ids()

        pending_count = self._count_pending()
        remaining_slots = max(0, MAX_PENDING_LESSONS - pending_count)

        for lesson in lessons:
            if lesson.source_memory_id in existing_sources:
                skipped += 1
                continue

            if queued >= remaining_slots:
                break

            audit_id = self._queue_lesson(lesson)
            if audit_id:
                queued += 1

        self._expire_old_candidates()

        return {
            "lessons_found": len(lessons),
            "candidates_queued": queued,
            "skipped_already_processed": skipped,
        }

    def _get_processed_source_ids(self) -> set:
        """Get set of already-processed source memory IDs."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT source_memory_id FROM experience_audit " "WHERE status IN ('pending', 'accepted')"
            )
            return {row[0] for row in cursor.fetchall()}
        finally:
            pass

    def _queue_lesson(self, lesson: ExtractedLesson) -> Optional[str]:
        """Queue a lesson for user review."""
        try:
            sanitized_trigger = RuleSanitizer.validate_trigger(lesson.trigger_hint)
            sanitized_action = RuleSanitizer.validate_action(lesson.action_hint)
        except ValueError:
            return None

        now = datetime.now(timezone.utc).isoformat()
        audit_id = f"exp_{uuid.uuid4().hex[:12]}"

        confidence_score = _CONFIDENCE_SCORE_MAP.get(lesson.confidence, 0.5)

        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO experience_audit
                    (id, source_memory_id, source_content, failure_signal,
                     lesson, trigger_hint, action_hint, confidence,
                     status, domain, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    lesson.source_memory_id,
                    lesson.source_content[:500],
                    lesson.failure_signal.value,
                    lesson.lesson[:500],
                    sanitized_trigger,
                    sanitized_action,
                    confidence_score,
                    EXPERIENCE_STATUS_PENDING,
                    lesson.domain,
                    now,
                ),
            )
            conn.commit()
            return audit_id
        except Exception:
            conn.rollback()
            return None
        finally:
            pass

    def list_pending(self, limit: int = 20) -> List[ExperienceAuditEntry]:
        """List all pending experience lessons."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM experience_audit
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (EXPERIENCE_STATUS_PENDING, limit),
            )
            rows = cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            pass

    def accept_lesson(
        self,
        audit_id: str,
        note: Optional[str] = None,
        trigger_override: Optional[str] = None,
        action_override: Optional[str] = None,
    ) -> Optional[str]:
        """
        Accept a pending lesson and create an active avoidance rule.

        Args:
            audit_id: ID of the pending experience audit entry
            note: Optional review note
            trigger_override: Optional custom trigger (overrides extracted hint)
            action_override: Optional custom action (overrides extracted hint)

        Returns:
            The created rule ID, or None on failure
        """
        entry = self._get_entry(audit_id)
        if not entry or entry.status != EXPERIENCE_STATUS_PENDING:
            return None

        trigger = trigger_override or entry.trigger_hint
        action = action_override or entry.action_hint

        try:
            trigger = RuleSanitizer.validate_trigger(trigger)
            action = RuleSanitizer.validate_action(action)
        except ValueError:
            return None

        try:
            rule = self.storage._create_validated(
                trigger=trigger,
                action=action,
                rule_type="avoid",
                override=True,
                derived_from="failure_lesson",
                source_memories=[entry.source_memory_id],
                confidence=entry.confidence,
            )
        except Exception:
            return None

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE experience_audit
                SET status = ?, reviewed_at = ?, review_note = ?, resulting_rule_id = ?
                WHERE id = ?
                """,
                (EXPERIENCE_STATUS_ACCEPTED, now, note, rule.id, audit_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            pass

        return rule.id

    def reject_lesson(self, audit_id: str, note: Optional[str] = None) -> bool:
        """Reject a pending lesson."""
        entry = self._get_entry(audit_id)
        if not entry or entry.status != EXPERIENCE_STATUS_PENDING:
            return False

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE experience_audit
                SET status = ?, reviewed_at = ?, review_note = ?
                WHERE id = ?
                """,
                (EXPERIENCE_STATUS_REJECTED, now, note, audit_id),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            pass

    def _expire_old_candidates(self) -> int:
        """Expire pending lessons older than expiry_days."""
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=self.expiry_days)).isoformat()
        now_iso = now.isoformat()

        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE experience_audit
                SET status = ?, reviewed_at = ?
                WHERE status = ? AND created_at < ?
                """,
                (EXPERIENCE_STATUS_EXPIRED, now_iso, EXPERIENCE_STATUS_PENDING, cutoff),
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            return 0
        finally:
            pass

    def _count_pending(self) -> int:
        """Count pending experience lessons efficiently."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM experience_audit WHERE status = ?",
                (EXPERIENCE_STATUS_PENDING,),
            )
            return cursor.fetchone()[0]
        finally:
            pass

    def get_audit_log(self, limit: int = 50) -> List[ExperienceAuditEntry]:
        """Get full audit log of all experience→rule actions."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM experience_audit
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            pass

    def get_stats(self) -> Dict:
        """Get experience bridge statistics."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM experience_audit
                GROUP BY status
                """
            )
            rows = cursor.fetchall()
            stats = {row[0]: row[1] for row in rows}
            stats["total"] = sum(stats.values())
            return stats
        finally:
            pass

    def _get_entry(self, audit_id: str) -> Optional[ExperienceAuditEntry]:
        """Get a single audit entry by ID."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM experience_audit WHERE id = ?",
                (audit_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entry(row)
            return None
        finally:
            pass

    def _row_to_entry(self, row) -> ExperienceAuditEntry:
        """Convert a database row to ExperienceAuditEntry."""
        return ExperienceAuditEntry(
            id=row[0],
            source_memory_id=row[1],
            source_content=row[2],
            failure_signal=row[3],
            lesson=row[4],
            trigger_hint=row[5],
            action_hint=row[6],
            confidence=row[7],
            status=row[8],
            domain=row[9],
            created_at=row[10],
            reviewed_at=row[11],
            review_note=row[12],
            resulting_rule_id=row[13],
        )
