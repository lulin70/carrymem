"""
Promotion Pipeline — Automated rule candidate generation from memory patterns.

Pipeline stages:
1. Collect: gather memories of same type within configurable time window
2. Detect: run PatternDetector to find repeated patterns
3. Generate: create RuleCandidate objects from detected patterns
4. Queue: store candidates with "pending" status for user review
5. Confirm: user accepts/rejects, candidate becomes active rule or is discarded

Audit trail: every promotion action is logged to promotion_audit table.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .candidate_rule_generator import CandidateRuleGenerator, RuleCandidate
from .pattern_detector import PatternDetector
from .sanitizer import RuleSanitizer
from .storage import RuleStorage

PROMOTION_STATUS_PENDING = "pending"
PROMOTION_STATUS_ACCEPTED = "accepted"
PROMOTION_STATUS_REJECTED = "rejected"
PROMOTION_STATUS_EXPIRED = "expired"

VALID_PROMOTION_STATUSES = frozenset(
    {
        PROMOTION_STATUS_PENDING,
        PROMOTION_STATUS_ACCEPTED,
        PROMOTION_STATUS_REJECTED,
        PROMOTION_STATUS_EXPIRED,
    }
)

DEFAULT_EXPIRY_DAYS = 7
DEFAULT_MIN_OCCURRENCES = 3
DEFAULT_MAX_CANDIDATES = 10


@dataclass
class PromotionAuditEntry:
    id: str
    candidate_trigger: str
    candidate_action: str
    candidate_rule_type: str
    source_pattern_type: str
    source_memory_ids: List[str]
    confidence: float
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None
    resulting_rule_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "candidate_trigger": self.candidate_trigger,
            "candidate_action": self.candidate_action,
            "candidate_rule_type": self.candidate_rule_type,
            "source_pattern_type": self.source_pattern_type,
            "source_memory_ids": self.source_memory_ids,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "review_note": self.review_note,
            "resulting_rule_id": self.resulting_rule_id,
        }


class PromotionPipeline:
    """Automated rule candidate generation from memory patterns."""

    def __init__(self, storage: RuleStorage, expiry_days: int = DEFAULT_EXPIRY_DAYS):
        self.storage = storage
        self.pattern_detector = PatternDetector(min_occurrences=DEFAULT_MIN_OCCURRENCES)
        self.candidate_generator = CandidateRuleGenerator()
        self.expiry_days = expiry_days
        self._audit_table_ensured = False
        self._ensure_audit_table()
        self._audit_table_ensured = True

    def _ensure_audit_table(self):
        """Create promotion_audit table if not exists."""
        conn = self.storage._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS promotion_audit (
                    id TEXT PRIMARY KEY,
                    candidate_trigger TEXT NOT NULL,
                    candidate_action TEXT NOT NULL,
                    candidate_rule_type TEXT NOT NULL,
                    source_pattern_type TEXT NOT NULL,
                    source_memory_ids TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','accepted','rejected','expired')),
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    review_note TEXT,
                    resulting_rule_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_promotion_status
                ON promotion_audit(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_promotion_created
                ON promotion_audit(created_at)
            """)
            conn.commit()
        finally:
            pass

    def run_pipeline(
        self,
        memories: List[Dict],
        memory_type: Optional[str] = None,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        auto_accept: bool = False,
    ) -> Dict:
        """
        Run the full promotion pipeline.

        Args:
            memories: List of memory dicts from CarryMem.recall_memories
            memory_type: Optional filter for specific memory type
            max_candidates: Maximum candidates to generate
            auto_accept: If True, automatically accept all candidates

        Returns:
            Dictionary with pipeline results
        """
        if not memories:
            return {
                "patterns_found": 0,
                "candidates_generated": 0,
                "candidates_queued": 0,
                "candidates_auto_accepted": 0,
            }

        patterns = self.pattern_detector.detect_patterns(memories, memory_type=memory_type)

        candidates = self.candidate_generator.generate(patterns, max_candidates=max_candidates)

        queued = 0
        auto_accepted = 0

        existing_pending = self._count_pending()
        max_queue_size = 50
        remaining_slots = max(0, max_queue_size - existing_pending)

        for candidate in candidates[:remaining_slots]:
            audit_id = self._queue_candidate(candidate)
            if audit_id:
                queued += 1
                if auto_accept:
                    rule_id = self.accept_candidate(audit_id)
                    if rule_id:
                        auto_accepted += 1

        self._expire_old_candidates()

        return {
            "patterns_found": len(patterns),
            "candidates_generated": len(candidates),
            "candidates_queued": queued,
            "candidates_auto_accepted": auto_accepted,
        }

    def _queue_candidate(self, candidate: RuleCandidate) -> Optional[str]:
        """Queue a candidate for user review."""
        try:
            sanitized_trigger = RuleSanitizer.validate_trigger(candidate.trigger)
            sanitized_action = RuleSanitizer.validate_action(candidate.action)
        except ValueError:
            return None

        now = datetime.now(timezone.utc).isoformat()
        audit_id = f"promo_{uuid.uuid4().hex[:12]}"

        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO promotion_audit
                    (id, candidate_trigger, candidate_action, candidate_rule_type,
                     source_pattern_type, source_memory_ids, confidence,
                     status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    sanitized_trigger,
                    sanitized_action,
                    candidate.rule_type,
                    candidate.pattern_type,
                    json.dumps(candidate.source_memories[:10]),
                    candidate.confidence,
                    PROMOTION_STATUS_PENDING,
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

    def list_pending(self, limit: int = 20) -> List[PromotionAuditEntry]:
        """List all pending promotion candidates."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM promotion_audit
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (PROMOTION_STATUS_PENDING, limit),
            )
            rows = cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            pass

    def _count_pending(self) -> int:
        """Count pending promotion candidates efficiently."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM promotion_audit WHERE status = ?",
                (PROMOTION_STATUS_PENDING,),
            )
            return cursor.fetchone()[0]
        finally:
            pass

    def accept_candidate(self, audit_id: str, note: Optional[str] = None) -> Optional[str]:
        """
        Accept a pending candidate and create an active rule.

        Returns:
            The created rule ID, or None on failure
        """
        entry = self._get_entry(audit_id)
        if not entry or entry.status != PROMOTION_STATUS_PENDING:
            return None

        try:
            rule = self.storage._create_validated(
                trigger=entry.candidate_trigger,
                action=entry.candidate_action,
                rule_type=entry.candidate_rule_type,
                override=False,
                derived_from="auto_promotion",
                source_memories=entry.source_memory_ids,
                confidence=entry.confidence,
            )
        except (ValueError, Exception):
            return None

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE promotion_audit
                SET status = ?, reviewed_at = ?, review_note = ?, resulting_rule_id = ?
                WHERE id = ?
                """,
                (PROMOTION_STATUS_ACCEPTED, now, note, rule.id, audit_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            pass

        return rule.id

    def reject_candidate(self, audit_id: str, note: Optional[str] = None) -> bool:
        """Reject a pending candidate."""
        entry = self._get_entry(audit_id)
        if not entry or entry.status != PROMOTION_STATUS_PENDING:
            return False

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE promotion_audit
                SET status = ?, reviewed_at = ?, review_note = ?
                WHERE id = ?
                """,
                (PROMOTION_STATUS_REJECTED, now, note, audit_id),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            pass

    def _expire_old_candidates(self) -> int:
        """Expire pending candidates older than expiry_days."""
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=self.expiry_days)).isoformat()
        now_iso = now.isoformat()

        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE promotion_audit
                SET status = ?, reviewed_at = ?
                WHERE status = ? AND created_at < ?
                """,
                (PROMOTION_STATUS_EXPIRED, now_iso, PROMOTION_STATUS_PENDING, cutoff),
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            return 0
        finally:
            pass

    def get_audit_log(self, limit: int = 50) -> List[PromotionAuditEntry]:
        """Get full audit log of all promotion actions."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM promotion_audit
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
        """Get promotion pipeline statistics."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM promotion_audit
                GROUP BY status
                """)
            rows = cursor.fetchall()
            stats = {row[0]: row[1] for row in rows}
            stats["total"] = sum(stats.values())
            return stats
        finally:
            pass

    def _get_entry(self, audit_id: str) -> Optional[PromotionAuditEntry]:
        """Get a single audit entry by ID."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM promotion_audit WHERE id = ?",
                (audit_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entry(row)
            return None
        finally:
            pass

    def _row_to_entry(self, row) -> PromotionAuditEntry:
        """Convert a database row to PromotionAuditEntry."""
        return PromotionAuditEntry(
            id=row[0],
            candidate_trigger=row[1],
            candidate_action=row[2],
            candidate_rule_type=row[3],
            source_pattern_type=row[4],
            source_memory_ids=json.loads(row[5]) if row[5] else [],
            confidence=row[6],
            status=row[7],
            created_at=row[8],
            reviewed_at=row[9],
            review_note=row[10],
            resulting_rule_id=row[11],
        )
