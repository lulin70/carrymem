"""Synchronous Phase 2 Observation storage."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from carrymem.monitoring import get_metrics_collector
from carrymem.security.redaction import should_redact

VALID_PREDICATES = frozenset(
    {
        "preference_detected",
        "correction_detected",
        "entity_state",
        "task_outcome",
        "conflict_signal",
        "usage_pattern",
    }
)
VALID_SOURCE_KINDS = frozenset({"user_feedback", "task_result", "correction", "lifecycle_event", "explicit_api"})
VALID_ADMISSIONS = frozenset({"explicit_feedback", "task_result", "correction", "lifecycle_event", "explicit_api"})


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class ObservationManager:
    """Persists short-lived, non-authoritative observation signals."""

    def __init__(self, adapter):
        self._adapter = adapter

    def record_observation(
        self,
        namespace: str,
        subject: str,
        predicate: str,
        value: Any,
        source_kind: str,
        source_ref: str,
        confidence: float,
        observed_at: datetime,
        expires_at: datetime,
        admission: str = "explicit_api",
    ) -> str:
        if namespace != self._adapter.namespace or not namespace:
            raise ValueError("namespace must match the adapter namespace")
        if predicate not in VALID_PREDICATES:
            raise ValueError(f"Invalid predicate: {predicate}")
        if source_kind not in VALID_SOURCE_KINDS:
            raise ValueError(f"Invalid source_kind: {source_kind}")
        if admission not in VALID_ADMISSIONS:
            get_metrics_collector().increment("observation_write_denied")
            raise ValueError(f"Invalid observation admission: {admission}")
        if not subject or not source_ref:
            raise ValueError("subject and source_ref must be non-empty")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        if expires_at <= observed_at:
            raise ValueError("expires_at must be later than observed_at")
        try:
            value_json = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be JSON serializable") from exc
        blocked, reason = should_redact(value_json)
        if blocked:
            raise ValueError(f"Observation value blocked by redaction: {reason}")
        subject_blocked, subject_reason = should_redact(subject)
        if subject_blocked:
            raise ValueError(f"Observation subject blocked by redaction: {subject_reason}")

        observation_id = f"obs_{uuid.uuid4().hex}"
        conn = self._adapter.get_raw_connection()
        try:
            conn.execute(
                """INSERT INTO memory_observations
                   (id, namespace, subject, predicate, value_json, source_kind, source_ref,
                    confidence, observed_at, expires_at, created_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid')""",
                (
                    observation_id,
                    namespace,
                    subject,
                    predicate,
                    value_json,
                    source_kind,
                    source_ref,
                    confidence,
                    _iso(observed_at),
                    _iso(expires_at),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        return observation_id

    def list_observations(
        self,
        namespace: str,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        source_kind: Optional[str] = None,
        include_expired: bool = False,
        include_unsupported: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if namespace != self._adapter.namespace or not namespace:
            raise ValueError("namespace must match the adapter namespace")
        conditions = ["namespace = ?"]
        params: List[Any] = [namespace]
        if subject is not None:
            conditions.append("subject = ?")
            params.append(subject)
        if predicate is not None:
            if predicate not in VALID_PREDICATES:
                raise ValueError(f"Invalid predicate: {predicate}")
            conditions.append("predicate = ?")
            params.append(predicate)
        if source_kind is not None:
            if source_kind not in VALID_SOURCE_KINDS:
                raise ValueError(f"Invalid source_kind: {source_kind}")
            conditions.append("source_kind = ?")
            params.append(source_kind)
        if not include_expired:
            conditions.append("expires_at > ?")
            params.append(datetime.now(timezone.utc).isoformat())
        if not include_unsupported:
            conditions.append("status = 'valid'")
        params.append(max(0, int(limit)))
        rows = (
            self._adapter.get_raw_connection()
            .execute(
                "SELECT * FROM memory_observations WHERE " + " AND ".join(conditions) + " "
                "ORDER BY observed_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["value"] = json.loads(item["value_json"])
            except (TypeError, ValueError):
                item["value"] = None
            result.append(item)
        return result

    def mark_unsupported_for_deleted_source(self, conn, namespace: str, source_ref: str) -> int:
        cursor = conn.execute(
            "UPDATE memory_observations SET status = 'unsupported' "
            "WHERE namespace = ? AND source_ref = ? AND status = 'valid'",
            (namespace, source_ref),
        )
        return int(cursor.rowcount)
