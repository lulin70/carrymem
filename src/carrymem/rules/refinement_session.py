"""
Refinement Session — Track multi-turn rule refinement conversations.
[RESERVED] Rule-engine extension point — not yet integrated into main pipeline.
Planned for v0.4.0 interactive rule-refinement feature.

Manages the full lifecycle of a rule refinement session:
    1. Start session from a specific rule or memory
    2. Generate questions round by round
    3. Process answers and refine the draft
    4. Confirm and create the final rule

All sessions are persisted to the refinement_sessions table for audit.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .rule_refiner import (
    RefinedRuleDraft,
    RefinementAnswer,
    RefinementPhase,
    RuleRefiner,
)
from .sanitizer import RuleSanitizer
from .storage import RuleStorage

SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_CANCELLED = "cancelled"
SESSION_STATUS_EXPIRED = "expired"

VALID_SESSION_STATUSES = frozenset(
    {
        SESSION_STATUS_ACTIVE,
        SESSION_STATUS_COMPLETED,
        SESSION_STATUS_CANCELLED,
        SESSION_STATUS_EXPIRED,
    }
)

DEFAULT_SESSION_EXPIRY_DAYS = 7
MAX_ROUNDS = 5


@dataclass
class SessionEntry:
    """A single rule refinement session record."""

    id: str
    source_rule_id: Optional[str]
    source_memory_id: Optional[str]
    original_trigger: str
    original_action: str
    current_trigger: str
    current_action: str
    rule_type: str
    phase: str
    round_number: int
    status: str
    scope_notes: str
    conversation: str
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    resulting_rule_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize this session entry to a plain dict."""
        return {
            "id": self.id,
            "source_rule_id": self.source_rule_id,
            "source_memory_id": self.source_memory_id,
            "original_trigger": self.original_trigger,
            "original_action": self.original_action,
            "current_trigger": self.current_trigger,
            "current_action": self.current_action,
            "rule_type": self.rule_type,
            "phase": self.phase,
            "round_number": self.round_number,
            "status": self.status,
            "scope_notes": self.scope_notes,
            "conversation": self.conversation,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "resulting_rule_id": self.resulting_rule_id,
        }


class RefinementSessionManager:
    """Manage multi-turn rule refinement sessions with persistence."""

    def __init__(self, storage: RuleStorage, expiry_days: int = DEFAULT_SESSION_EXPIRY_DAYS):
        self.storage = storage
        self.refiner = RuleRefiner()
        self.expiry_days = expiry_days
        self._sessions_table_ensured = False
        self._ensure_sessions_table()
        self._sessions_table_ensured = True

    def _ensure_sessions_table(self):
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS refinement_sessions (
                    id TEXT PRIMARY KEY,
                    source_rule_id TEXT,
                    source_memory_id TEXT,
                    original_trigger TEXT NOT NULL,
                    original_action TEXT NOT NULL,
                    current_trigger TEXT NOT NULL,
                    current_action TEXT NOT NULL,
                    rule_type TEXT NOT NULL DEFAULT 'avoid',
                    phase TEXT NOT NULL DEFAULT 'scope',
                    round_number INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active','completed','cancelled','expired')),
                    scope_notes TEXT NOT NULL DEFAULT '',
                    conversation TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    resulting_rule_id TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_refinement_status
                ON refinement_sessions(status)
            """
            )
            conn.commit()
        finally:
            pass

    def start_session(
        self,
        trigger: str,
        action: str,
        rule_type: str = "avoid",
        source_rule_id: Optional[str] = None,
        source_memory_id: Optional[str] = None,
    ) -> Dict:
        """
        Start a new refinement session.

        Returns:
            Dictionary with session info and first question
        """
        try:
            trigger = RuleSanitizer.validate_trigger(trigger)
            action = RuleSanitizer.validate_action(action)
        except ValueError:
            return {"error": "Invalid trigger or action content"}

        self._expire_old_sessions()

        now = datetime.now(timezone.utc).isoformat()
        session_id = f"ref_{uuid.uuid4().hex[:10]}"

        specificity = self.refiner.analyze_specificity(trigger, action)

        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO refinement_sessions
                    (id, source_rule_id, source_memory_id, original_trigger, original_action,
                     current_trigger, current_action, rule_type, phase, round_number,
                     status, scope_notes, conversation, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    source_rule_id,
                    source_memory_id,
                    trigger,
                    action,
                    trigger,
                    action,
                    rule_type,
                    RefinementPhase.SCOPE.value,
                    0,
                    SESSION_STATUS_ACTIVE,
                    "",
                    json.dumps([]),
                    now,
                    now,
                ),
            )
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError, ValueError):
            conn.rollback()
            return {"error": "Failed to create session"}
        finally:
            pass

        question = self.refiner.generate_question(
            trigger=trigger,
            action=action,
            phase=RefinementPhase.SCOPE,
            round_number=1,
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "phase": RefinementPhase.SCOPE.value,
            "round": 1,
            "specificity": specificity,
            "question": question.to_dict() if question else None,
            "current_draft": {
                "trigger": trigger,
                "action": action,
                "rule_type": rule_type,
            },
        }

    def answer_question(self, session_id: str, answer_text: str, selected_option: Optional[str] = None) -> Dict:
        """
        Process an answer to the current question and advance the session.

        Returns:
            Dictionary with updated session info and next question
        """
        entry = self._get_session(session_id)
        if not entry or entry.status != SESSION_STATUS_ACTIVE:
            return {"error": "Session not found or not active"}

        if entry.round_number >= MAX_ROUNDS:
            return self._force_confirm(session_id, entry)

        current_phase = RefinementPhase(entry.phase)
        draft = RefinedRuleDraft(
            trigger=entry.current_trigger,
            action=entry.current_action,
            rule_type=entry.rule_type,
            scope_notes=entry.scope_notes,
        )

        question = self.refiner.generate_question(
            trigger=entry.current_trigger,
            action=entry.current_action,
            phase=current_phase,
            round_number=entry.round_number + 1,
            session_id=session_id,
        )

        if not question:
            return self._force_confirm(session_id, entry)

        answer = RefinementAnswer(
            question_id=question.question_id,
            answer_text=answer_text,
            selected_option=selected_option,
        )

        refined_draft = self.refiner.refine_from_answer(draft, question, answer)

        conversation = json.loads(entry.conversation)
        conversation.append(
            {
                "round": entry.round_number + 1,
                "phase": current_phase.value,
                "question": question.question_text,
                "answer": answer_text,
                "selected_option": selected_option,
            }
        )

        next_phase = self.refiner.determine_next_phase(current_phase, entry.round_number + 1)

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE refinement_sessions
                SET current_trigger = ?, current_action = ?,
                    phase = ?, round_number = ?, scope_notes = ?,
                    conversation = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    refined_draft.trigger,
                    refined_draft.action,
                    next_phase.value,
                    entry.round_number + 1,
                    refined_draft.scope_notes,
                    json.dumps(conversation),
                    now,
                    session_id,
                ),
            )
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError, ValueError):
            conn.rollback()
            return {"error": "Failed to update session"}
        finally:
            pass

        next_question = self.refiner.generate_question(
            trigger=refined_draft.trigger,
            action=refined_draft.action,
            phase=next_phase,
            round_number=entry.round_number + 2,
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "phase": next_phase.value,
            "round": entry.round_number + 1,
            "refined_draft": refined_draft.to_dict(),
            "next_question": next_question.to_dict() if next_question else None,
        }

    def confirm_session(self, session_id: str, note: Optional[str] = None) -> Dict:
        """Confirm and create the refined rule."""
        entry = self._get_session(session_id)
        if not entry or entry.status != SESSION_STATUS_ACTIVE:
            return {"error": "Session not found or not active"}

        try:
            trigger = RuleSanitizer.validate_trigger(entry.current_trigger)
            action = RuleSanitizer.validate_action(entry.current_action)
        except ValueError as e:
            return {"error": f"Invalid refined content: {e}"}

        try:
            rule = self.storage._create_validated(
                trigger=trigger,
                action=action,
                rule_type=entry.rule_type,
                override=True,
                derived_from="refinement_session",
                source_memories=[entry.source_memory_id] if entry.source_memory_id else [],
                confidence=0.8,
            )
        except (sqlite3.IntegrityError, sqlite3.OperationalError, ValueError) as e:
            return {"error": f"Failed to create rule: {e}"}

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE refinement_sessions
                SET status = ?, completed_at = ?, resulting_rule_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (SESSION_STATUS_COMPLETED, now, rule.id, now, session_id),
            )
            conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            conn.rollback()
        finally:
            pass

        return {
            "session_id": session_id,
            "status": "completed",
            "rule_id": rule.id,
            "trigger": trigger,
            "action": action,
        }

    def cancel_session(self, session_id: str) -> bool:
        """Cancel an active session."""
        entry = self._get_session(session_id)
        if not entry or entry.status != SESSION_STATUS_ACTIVE:
            return False

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                "UPDATE refinement_sessions SET status = ?, updated_at = ? WHERE id = ?",
                (SESSION_STATUS_CANCELLED, now, session_id),
            )
            conn.commit()
            return True
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            conn.rollback()
            return False
        finally:
            pass

    def list_active_sessions(self, limit: int = 20) -> List[SessionEntry]:
        """List all active refinement sessions."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM refinement_sessions
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (SESSION_STATUS_ACTIVE, limit),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        finally:
            pass

    def get_session_detail(self, session_id: str) -> Optional[Dict]:
        """Get full session detail including conversation."""
        entry = self._get_session(session_id)
        if not entry:
            return None

        conversation = json.loads(entry.conversation)
        return {
            **entry.to_dict(),
            "conversation": conversation,
        }

    def get_stats(self) -> Dict:
        """Return counts of refinement sessions grouped by status."""
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute("SELECT status, COUNT(*) as count FROM refinement_sessions GROUP BY status")
            stats = {row[0]: row[1] for row in cursor.fetchall()}
            stats["total"] = sum(stats.values())
            return stats
        finally:
            pass

    def _force_confirm(self, session_id: str, entry: SessionEntry) -> Dict:
        """Force the session into confirm phase."""
        question = self.refiner.generate_question(
            trigger=entry.current_trigger,
            action=entry.current_action,
            phase=RefinementPhase.CONFIRM,
            round_number=entry.round_number + 1,
            session_id=session_id,
        )

        now = datetime.now(timezone.utc).isoformat()
        conn = self.storage._get_connection()
        try:
            conn.execute(
                """
                UPDATE refinement_sessions
                SET phase = ?, updated_at = ?
                WHERE id = ?
                """,
                (RefinementPhase.CONFIRM.value, now, session_id),
            )
            conn.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            conn.rollback()
        finally:
            pass

        return {
            "session_id": session_id,
            "phase": RefinementPhase.CONFIRM.value,
            "round": entry.round_number + 1,
            "refined_draft": {
                "trigger": entry.current_trigger,
                "action": entry.current_action,
                "rule_type": entry.rule_type,
            },
            "next_question": question.to_dict() if question else None,
        }

    def _expire_old_sessions(self) -> int:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=self.expiry_days)).isoformat()
        now_iso = now.isoformat()

        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE refinement_sessions
                SET status = ?, updated_at = ?
                WHERE status = ? AND created_at < ?
                """,
                (SESSION_STATUS_EXPIRED, now_iso, SESSION_STATUS_ACTIVE, cutoff),
            )
            conn.commit()
            return cursor.rowcount
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            conn.rollback()
            return 0
        finally:
            pass

    def _get_session(self, session_id: str) -> Optional[SessionEntry]:
        conn = self.storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM refinement_sessions WHERE id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            return self._row_to_entry(row) if row else None
        finally:
            pass

    def _row_to_entry(self, row) -> SessionEntry:
        return SessionEntry(
            id=row[0],
            source_rule_id=row[1],
            source_memory_id=row[2],
            original_trigger=row[3],
            original_action=row[4],
            current_trigger=row[5],
            current_action=row[6],
            rule_type=row[7],
            phase=row[8],
            round_number=row[9],
            status=row[10],
            scope_notes=row[11],
            conversation=row[12],
            created_at=row[13],
            updated_at=row[14],
            completed_at=row[15],
            resulting_rule_id=row[16],
        )
