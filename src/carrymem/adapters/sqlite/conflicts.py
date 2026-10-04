"""Synchronous Phase 2 ConflictRecord storage and priority resolution."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from carrymem.security.redaction import should_redact

VALID_CONFLICT_TYPES = frozenset({"preference", "fact", "rule", "entity_state"})
VALID_STATUSES = frozenset({"unresolved", "resolved", "user_decided", "expired"})
VALID_POLICIES = frozenset({"chain-v1"})
HIGH_RISK_TERMS = frozenset(
    {
        "security",
        "permission",
        "privacy",
        "health",
        "financial",
        "identity",
        "credential",
        "delete",
        "retention",
        "export",
        "share",
        "forbid",
        "always",
        "override",
        "cross-namespace",
        "email",
        "send",
        "communication",
        "notify",
        "message",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConflictManager:
    """Stores immutable conflict records and resolves only within P1-P6 tiers."""

    def __init__(self, adapter):
        self._adapter = adapter

    def create_conflict(
        self,
        namespace: str,
        subject_key: str,
        candidate_ids: List[str],
        conflict_type: str,
        resolution_status: str = "unresolved",
        resolution_policy: str = "chain-v1",
        selected_id: Optional[str] = None,
        reasoning: Optional[Dict[str, Any]] = None,
    ) -> str:
        self._validate_namespace(namespace)
        self._validate_record(candidate_ids, conflict_type, resolution_status, resolution_policy, selected_id)
        conflict_id = f"conf_{uuid.uuid4().hex}"
        payload = reasoning or {"priority": None, "evidence": {"support": 0, "contradiction": 0}}
        try:
            subject_json = json.dumps(subject_key, ensure_ascii=False, sort_keys=True)
            reasoning_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("ConflictRecord fields must be JSON serializable") from exc
        for field_name, serialized in (("subject_key", subject_json), ("reasoning", reasoning_json)):
            blocked, reason = should_redact(serialized)
            if blocked:
                raise ValueError(f"ConflictRecord {field_name} blocked by redaction: {reason}")
        conn = self._adapter.get_raw_connection()
        # file_lock invariant: raw-connection writers must serialize with the
        # CRUD/recall write paths (flaky SQLITE_BUSY under concurrent classify).
        with self._adapter.write_lock:
            try:
                conn.execute(
                    """INSERT INTO memory_conflicts
                       (conflict_id, namespace, subject_key, candidate_ids, conflict_type,
                        resolution_status, resolution_policy, selected_id, reasoning, created_at, resolved_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        conflict_id,
                        namespace,
                        subject_key,
                        json.dumps(candidate_ids, ensure_ascii=False),
                        conflict_type,
                        resolution_status,
                        resolution_policy,
                        selected_id,
                        reasoning_json,
                        _now(),
                        _now() if resolution_status in {"resolved", "user_decided"} else None,
                    ),
                )
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
        return conflict_id

    def list_conflicts(
        self, namespace: str, subject_key: Optional[str] = None, unresolved_only: bool = False, limit: int = 100
    ) -> List[Dict[str, Any]]:
        self._validate_namespace(namespace)
        conditions = ["namespace = ?"]
        params: List[Any] = [namespace]
        if subject_key is not None:
            conditions.append("subject_key = ?")
            params.append(subject_key)
        if unresolved_only:
            conditions.append("resolution_status = 'unresolved'")
        params.append(max(0, int(limit)))
        rows = (
            self._adapter.get_raw_connection()
            .execute(
                "SELECT * FROM memory_conflicts WHERE " + " AND ".join(conditions) + " "
                "ORDER BY created_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        result = []
        for row in rows:
            item = dict(row)
            item["candidate_ids"] = json.loads(item["candidate_ids"])
            item["reasoning"] = json.loads(item["reasoning"])
            result.append(item)
        return result

    def resolve_conflict(
        self,
        conflict_id: str,
        selected_id: Optional[str],
        status: str = "resolved",
        reasoning: Optional[Dict[str, Any]] = None,
    ) -> str:
        if status not in {"resolved", "user_decided", "unresolved", "expired"}:
            raise ValueError(f"Invalid resolution status: {status}")
        conn = self._adapter.get_raw_connection()
        row = conn.execute("SELECT * FROM memory_conflicts WHERE conflict_id = ?", (conflict_id,)).fetchone()
        if not row:
            raise KeyError(conflict_id)
        candidates = json.loads(row["candidate_ids"])
        self._validate_record(candidates, row["conflict_type"], status, row["resolution_policy"], selected_id)
        new_reasoning = reasoning or json.loads(row["reasoning"])
        return self.create_conflict(
            row["namespace"],
            row["subject_key"],
            candidates,
            row["conflict_type"],
            status,
            row["resolution_policy"],
            selected_id,
            new_reasoning,
        )

    def resolve_candidates(
        self, namespace: str, subject_key: str, candidates: List[Dict[str, Any]], conflict_type: str
    ) -> Dict[str, Any]:
        self._validate_namespace(namespace)
        if conflict_type not in VALID_CONFLICT_TYPES:
            raise ValueError(f"Invalid conflict_type: {conflict_type}")
        ranked = sorted(candidates, key=self._rank_key, reverse=True)
        high_risk = any(term in subject_key.lower() for term in HIGH_RISK_TERMS)
        top = ranked[0] if ranked else None
        tied = len(ranked) > 1 and self._rank_key(ranked[0]) == self._rank_key(ranked[1])
        selected_id = None if high_risk or tied or not top else top.get("id")
        source_priority = {
            "correction": 6,
            "user_statement": 5,
            "user_feedback": 4,
            "task_result": 4,
            "observation": 3,
            "accepted": 2,
            "derived": 1,
            "inference": 0,
        }
        priority = int(top.get("priority", source_priority.get(str(top.get("source_kind")), 0))) if top else None
        reasoning = {
            "priority": priority,
            "evidence": {
                "support": sum(int(c.get("support_count", 0)) for c in candidates),
                "contradiction": sum(int(c.get("contradiction_count", 0)) for c in candidates),
            },
            "factors": [
                "source_kind",
                "namespace",
                "explicit_correction",
                "expires_at",
                "support_count",
                "contradiction_count",
                "confidence",
                "superseded",
                "accepted",
                "sensitivity",
            ],
            "high_risk": high_risk,
            "tie": tied,
        }
        conflict_id = self.create_conflict(
            namespace,
            subject_key,
            [str(c["id"]) for c in candidates],
            conflict_type,
            "resolved" if selected_id else "unresolved",
            "chain-v1",
            selected_id,
            reasoning,
        )
        return {
            "conflict_id": conflict_id,
            "selected_id": selected_id,
            "status": "resolved" if selected_id else "unresolved",
            "reasoning": reasoning,
        }

    @staticmethod
    def _rank_key(candidate: Dict[str, Any]):
        source_priority = {
            "correction": 6,
            "user_statement": 5,
            "user_feedback": 4,
            "task_result": 4,
            "observation": 3,
            "accepted": 2,
            "derived": 1,
            "inference": 0,
        }
        return (
            int(candidate.get("priority", source_priority.get(str(candidate.get("source_kind")), 0))),
            1 if candidate.get("explicit_correction") else 0,
            1 if not candidate.get("expired", False) else 0,
            1 if not candidate.get("superseded", False) else 0,
            int(candidate.get("support_count", 0)) - int(candidate.get("contradiction_count", 0)),
            float(candidate.get("confidence", 0.0)),
            1 if candidate.get("accepted", False) else 0,
            candidate.get("observed_at", ""),
        )

    def _validate_namespace(self, namespace: str) -> None:
        if not namespace or namespace != self._adapter.namespace:
            raise ValueError("namespace must match the adapter namespace")

    @staticmethod
    def _validate_record(candidate_ids, conflict_type, status, policy, selected_id):
        if not candidate_ids:
            raise ValueError("candidate_ids must not be empty")
        if conflict_type not in VALID_CONFLICT_TYPES:
            raise ValueError(f"Invalid conflict_type: {conflict_type}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid resolution_status: {status}")
        if policy not in VALID_POLICIES:
            raise ValueError(f"Invalid resolution_policy: {policy}")
        if status == "unresolved" and selected_id is not None:
            raise ValueError("unresolved conflicts cannot select a candidate")
        if status in {"resolved", "user_decided"} and selected_id not in candidate_ids:
            raise ValueError("selected_id must be one of candidate_ids")
