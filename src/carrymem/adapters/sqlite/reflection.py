"""Phase 4 reflection run/proposal storage and lifecycle.

Implements the approved contract in
docs/design/MEMORY_EVOLUTION_REFLECTION_PROPOSAL.md:

- Reflection runs are resumable and idempotent (INV-RR1/RR2/RR3).
- Proposals only become visible changes through an explicit, single-transaction
  apply that must record a rollback reference (INV-P3), and a rollback that
  only undoes the derived projection (INV-B1).
- High-risk proposals can never be auto-approved (INV-P1/INV-D1).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from carrymem.monitoring import get_metrics_collector
from carrymem.security.redaction import should_redact

VALID_RUN_TYPES = frozenset(
    {
        "dedup",
        "conflict_scan",
        "decay",
        "fact_derivation",
        "profile_rebuild",
        "aggregation",
        "graph_maintenance",
    }
)
VALID_RUN_STATUSES = frozenset({"running", "completed", "failed", "cancelled", "interrupted"})
VALID_PROPOSAL_TYPES = frozenset(
    {
        "fact_candidate",
        "profile_rebuild",
        "model_claim",
        "rule_candidate",
        "graph_update",
        "dedup_merge",
        "supersede",
        "expire_projection",
    }
)
VALID_PROPOSAL_STATUSES = frozenset({"proposed", "approved", "rejected", "applied", "failed", "rolled_back", "expired"})
VALID_RISK_LEVELS = frozenset({"low", "high"})

#: Proposal types that act on an existing business object and therefore must
#: carry a target (contract §3: 应用型提案必填).
TARGET_REQUIRED_TYPES = frozenset({"graph_update", "dedup_merge", "supersede", "expire_projection"})

#: INV-P4: a fact_candidate without evidence must stay at or below the low-trust
#: confidence ceiling.
LOW_TRUST_MAX_CONFIDENCE = 0.5

#: Hardcoded high-risk list (contract §4.2, INV-D1). Deliberately not
#: configurable: callers may only widen conservatism, never shrink it.
_HIGH_RISK_TYPES = frozenset(
    {
        "rule_candidate",
        "model_claim",
        "fact_candidate",
        "supersede",
        "profile_rebuild",
    }
)
_GRAPH_MAX_WEIGHT_CAP = 10.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_risk(proposal_type: str, payload: Dict[str, Any], evidence_count: int) -> str:
    """Hardcoded risk classification (contract §4.1/§4.2).

    Unknown shapes classify as high (fail-closed). INV-D1: this mapping is
    code, not configuration.
    """
    if proposal_type not in VALID_PROPOSAL_TYPES:
        return "high"
    if proposal_type in _HIGH_RISK_TYPES:
        return "high"
    if proposal_type == "expire_projection":
        return "low"
    if proposal_type == "graph_update":
        action = payload.get("action")
        max_weight = payload.get("max_weight")
        capped = isinstance(max_weight, (int, float)) and 0 < float(max_weight) <= _GRAPH_MAX_WEIGHT_CAP
        if action == "reinforce" and capped:
            return "low"
        return "high"
    if proposal_type == "dedup_merge":
        return "low" if evidence_count >= 2 else "high"
    return "high"


def _apply_expire_projection(conn, namespace: str, target_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    expires_at = payload.get("expires_at")
    if not expires_at or not isinstance(expires_at, str):
        raise ValueError("expire_projection payload requires a non-empty 'expires_at' ISO string")
    row = conn.execute(
        "SELECT expires_at FROM memories WHERE storage_key = ? AND namespace = ? AND superseded_at IS NULL",
        (target_id, namespace),
    ).fetchone()
    if row is None:
        raise ValueError(f"expire_projection target not found or already superseded: {target_id}")
    conn.execute(
        "UPDATE memories SET expires_at = ? WHERE storage_key = ? AND namespace = ? AND superseded_at IS NULL",
        (expires_at, target_id, namespace),
    )
    return {"kind": "expire_projection", "previous_expires_at": row["expires_at"]}


def _rollback_expire_projection(conn, namespace: str, target_id: str, rollback_ref: Dict[str, Any]) -> None:
    cursor = conn.execute(
        "UPDATE memories SET expires_at = ? WHERE storage_key = ? AND namespace = ?",
        (rollback_ref.get("previous_expires_at"), target_id, namespace),
    )
    if int(cursor.rowcount) != 1:
        raise ValueError(f"rollback target missing: {target_id}")


def _apply_graph_update(conn, namespace: str, target_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("action") != "reinforce":
        raise ValueError("graph_update payload action must be 'reinforce'")
    weight = payload.get("weight")
    max_weight = payload.get("max_weight")
    if not isinstance(weight, (int, float)) or weight <= 0:
        raise ValueError("graph_update payload requires a positive numeric 'weight'")
    if not isinstance(max_weight, (int, float)) or not 0 < float(max_weight) <= _GRAPH_MAX_WEIGHT_CAP:
        raise ValueError(f"graph_update requires 0 < max_weight <= {_GRAPH_MAX_WEIGHT_CAP}")
    effective = min(float(weight), float(max_weight))
    try:
        relation_id = int(target_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("graph_update target_id must be a relation id") from exc
    row = conn.execute(
        "SELECT weight FROM memory_relations WHERE id = ? AND namespace = ?",
        (relation_id, namespace),
    ).fetchone()
    if row is None:
        raise ValueError(f"graph_update target relation not found: {target_id}")
    conn.execute(
        "UPDATE memory_relations SET weight = ? WHERE id = ? AND namespace = ?",
        (effective, relation_id, namespace),
    )
    return {"kind": "graph_update", "previous_weight": row["weight"]}


def _rollback_graph_update(conn, namespace: str, target_id: str, rollback_ref: Dict[str, Any]) -> None:
    cursor = conn.execute(
        "UPDATE memory_relations SET weight = ? WHERE id = ? AND namespace = ?",
        (rollback_ref.get("previous_weight"), int(target_id), namespace),
    )
    if int(cursor.rowcount) != 1:
        raise ValueError(f"rollback target missing: {target_id}")


def _apply_supersede(conn, namespace: str, target_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    new_key = payload.get("new_storage_key")
    if not new_key or not isinstance(new_key, str):
        raise ValueError("supersede payload requires 'new_storage_key'")
    row = conn.execute(
        "SELECT superseded_at, supersedes FROM memories "
        "WHERE storage_key = ? AND namespace = ? AND superseded_at IS NULL",
        (target_id, namespace),
    ).fetchone()
    if row is None:
        raise ValueError(f"supersede target not found or already superseded: {target_id}")
    conn.execute(
        "UPDATE memories SET superseded_at = ?, supersedes = ? "
        "WHERE storage_key = ? AND namespace = ? AND superseded_at IS NULL",
        (_now(), new_key, target_id, namespace),
    )
    return {
        "kind": "supersede",
        "previous_superseded_at": row["superseded_at"],
        "previous_supersedes": row["supersedes"],
    }


def _rollback_supersede(conn, namespace: str, target_id: str, rollback_ref: Dict[str, Any]) -> None:
    cursor = conn.execute(
        "UPDATE memories SET superseded_at = ?, supersedes = ? " "WHERE storage_key = ? AND namespace = ?",
        (rollback_ref.get("previous_superseded_at"), rollback_ref.get("previous_supersedes"), target_id, namespace),
    )
    if int(cursor.rowcount) != 1:
        raise ValueError(f"rollback target missing: {target_id}")


ApplyHandler = Callable[[Any, str, str, Dict[str, Any]], Dict[str, Any]]
RollbackHandler = Callable[[Any, str, str, Dict[str, Any]], None]

#: Only derived-projection handlers ship in the minimal loop. Types whose
#: first-class target tables do not exist yet (fact_candidate, profile_rebuild,
#: model_claim, rule_candidate) and dedup_merge (needs merge semantics) stay
#: unimplemented on purpose: apply fails closed instead of guessing.
_APPLY_HANDLERS: Dict[str, ApplyHandler] = {
    "expire_projection": _apply_expire_projection,
    "graph_update": _apply_graph_update,
    "supersede": _apply_supersede,
}
_ROLLBACK_HANDLERS: Dict[str, RollbackHandler] = {
    "expire_projection": _rollback_expire_projection,
    "graph_update": _rollback_graph_update,
    "supersede": _rollback_supersede,
}


def _safe_error_text(text: str) -> str:
    trimmed = str(text)[:200]
    blocked, _reason = should_redact(trimmed)
    return "error text blocked by redaction" if blocked else trimmed


class ReflectionManager:
    """Stores reflection runs and proposals; applies only what can be rolled back."""

    def __init__(self, adapter):
        self._adapter = adapter

    # -- namespace guard ----------------------------------------------------

    def _require_namespace(self, namespace: str) -> None:
        if namespace != self._adapter.namespace or not namespace:
            raise ValueError("namespace must match the adapter namespace")

    # -- run lifecycle ------------------------------------------------------

    def start_run(
        self,
        namespace: str,
        reflection_type: str,
        strategy_version: str,
        input_snapshot: str,
        config_snapshot: str,
        input_cursor: Optional[str] = None,
    ) -> str:
        """Start (or idempotently resume) a reflection run.

        INV-RR1: a completed run with the same identity is reused, never
        re-executed. interrupted/failed runs resume from their cursor.
        """
        self._require_namespace(namespace)
        if reflection_type not in VALID_RUN_TYPES:
            raise ValueError(f"Invalid reflection_type: {reflection_type}")
        if not strategy_version or not input_snapshot or not config_snapshot:
            raise ValueError("strategy_version, input_snapshot and config_snapshot must be non-empty")
        conn = self._adapter.get_raw_connection()
        existing = conn.execute(
            "SELECT run_id, status FROM memory_reflection_runs "
            "WHERE namespace = ? AND reflection_type = ? AND input_snapshot = ? AND config_snapshot = ?",
            (namespace, reflection_type, input_snapshot, config_snapshot),
        ).fetchone()
        if existing is not None:
            run_id = str(existing["run_id"])
            status = existing["status"]
            if status == "running":
                return run_id
            if status == "completed":
                get_metrics_collector().increment("reflection_runs_reused")
                return run_id
            if status == "cancelled":
                raise ValueError("run was cancelled; start a new reflection with a different identity")
            conn.execute(
                # Do NOT reset started_at on resume: run identity (and the
                # payload hashes derived from it) must stay stable so
                # replayed proposals dedup via INV-P2.
                "UPDATE memory_reflection_runs SET status = 'running', error_text = NULL, "
                "completed_at = NULL WHERE run_id = ?",
                (run_id,),
            )
            conn.commit()
            get_metrics_collector().increment("reflection_runs_resumed")
            return run_id
        run_id = f"run_{uuid.uuid4().hex}"
        conn.execute(
            """INSERT INTO memory_reflection_runs
               (run_id, namespace, reflection_type, strategy_version, input_cursor,
                input_snapshot, config_snapshot, status, started_at, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)""",
            (
                run_id,
                namespace,
                reflection_type,
                strategy_version,
                input_cursor,
                input_snapshot,
                config_snapshot,
                _now(),
                f"{namespace}:{reflection_type}:{input_snapshot}:{config_snapshot}",
            ),
        )
        conn.commit()
        get_metrics_collector().increment("reflection_runs_started")
        return run_id

    def update_cursor(self, run_id: str, input_cursor: str) -> None:
        """INV-RR2: persist the resume point of an in-flight run."""
        conn = self._adapter.get_raw_connection()
        cursor = conn.execute(
            "UPDATE memory_reflection_runs SET input_cursor = ? " "WHERE run_id = ? AND status = 'running'",
            (input_cursor, run_id),
        )
        if int(cursor.rowcount) != 1:
            raise ValueError(f"run is not running (or unknown): {run_id}")
        conn.commit()

    def complete_run(self, run_id: str, input_cursor: Optional[str] = None) -> None:
        conn = self._adapter.get_raw_connection()
        cursor = conn.execute(
            "UPDATE memory_reflection_runs SET status = 'completed', completed_at = ?, "
            "input_cursor = COALESCE(?, input_cursor) "
            "WHERE run_id = ? AND status = 'running'",
            (_now(), input_cursor, run_id),
        )
        if int(cursor.rowcount) != 1:
            raise ValueError(f"run is not running (or unknown): {run_id}")
        conn.commit()
        get_metrics_collector().increment("reflection_runs_completed")

    def fail_run(self, run_id: str, error_text: str) -> None:
        """INV-RR3: only the run row changes; business tables are untouched."""
        conn = self._adapter.get_raw_connection()
        cursor = conn.execute(
            "UPDATE memory_reflection_runs SET status = 'failed', completed_at = ?, error_text = ? "
            "WHERE run_id = ? AND status = 'running'",
            (_now(), _safe_error_text(error_text), run_id),
        )
        if int(cursor.rowcount) != 1:
            raise ValueError(f"run is not running (or unknown): {run_id}")
        conn.commit()
        get_metrics_collector().increment("reflection_runs_failed")

    def mark_interrupted(self, run_id: str) -> None:
        conn = self._adapter.get_raw_connection()
        cursor = conn.execute(
            "UPDATE memory_reflection_runs SET status = 'interrupted', completed_at = ? "
            "WHERE run_id = ? AND status = 'running'",
            (_now(), run_id),
        )
        if int(cursor.rowcount) != 1:
            raise ValueError(f"run is not running (or unknown): {run_id}")
        conn.commit()

    def cancel_run(self, run_id: str) -> None:
        conn = self._adapter.get_raw_connection()
        cursor = conn.execute(
            "UPDATE memory_reflection_runs SET status = 'cancelled', completed_at = ? "
            "WHERE run_id = ? AND status = 'running'",
            (_now(), run_id),
        )
        if int(cursor.rowcount) != 1:
            raise ValueError(f"run is not running (or unknown): {run_id}")
        conn.commit()

    def list_runs(self, namespace: str, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        self._require_namespace(namespace)
        if status is not None and status not in VALID_RUN_STATUSES:
            raise ValueError(f"Invalid run status: {status}")
        conditions = ["namespace = ?"]
        params: List[Any] = [namespace]
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        params.append(max(0, int(limit)))
        rows = (
            self._adapter.get_raw_connection()
            .execute(
                "SELECT * FROM memory_reflection_runs WHERE "
                + " AND ".join(conditions)
                + " ORDER BY started_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [dict(row) for row in rows]

    # -- proposal lifecycle -------------------------------------------------

    def _serialize_proposal_fields(
        self,
        proposal_type: str,
        payload: Dict[str, Any],
        reasoning: Dict[str, Any],
        confidence: float,
        observation_ids: List[str],
        evidence_ids: List[str],
        target_kind: Optional[str],
        target_id: Optional[str],
        risk_level: Optional[str],
    ):
        """Validate inputs and produce the serialized, risk-resolved fields."""
        if proposal_type not in VALID_PROPOSAL_TYPES:
            raise ValueError(f"Invalid proposal_type: {proposal_type}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        try:
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            reasoning_json = json.dumps(reasoning, ensure_ascii=False, sort_keys=True)
            observations_json = json.dumps(observation_ids, ensure_ascii=False)
            evidence_json = json.dumps(evidence_ids, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("proposal fields must be JSON serializable") from exc
        for field_name, serialized in (
            ("payload", payload_json),
            ("reasoning", reasoning_json),
        ):
            blocked, reason = should_redact(serialized)
            if blocked:
                raise ValueError(f"Proposal {field_name} blocked by redaction: {reason}")
        if proposal_type in TARGET_REQUIRED_TYPES and (not target_kind or not target_id):
            raise ValueError(f"proposal_type {proposal_type} requires target_kind and target_id")
        if proposal_type == "fact_candidate" and not evidence_ids and confidence > LOW_TRUST_MAX_CONFIDENCE:
            raise ValueError(
                "INV-P4: fact_candidate without evidence cannot exceed "
                f"low-trust confidence {LOW_TRUST_MAX_CONFIDENCE}"
            )
        effective_risk = classify_risk(proposal_type, payload, len(evidence_ids))
        if risk_level is not None and risk_level not in VALID_RISK_LEVELS:
            raise ValueError(f"Invalid risk_level: {risk_level}")
        if risk_level == "high":
            effective_risk = "high"
        return payload_json, reasoning_json, observations_json, evidence_json, effective_risk

    def create_proposal(
        self,
        namespace: str,
        run_id: str,
        proposal_type: str,
        payload: Dict[str, Any],
        reasoning: Dict[str, Any],
        confidence: float,
        source_observation_ids: Optional[List[str]] = None,
        source_evidence_ids: Optional[List[str]] = None,
        target_kind: Optional[str] = None,
        target_id: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> str:
        """Create (or idempotently reuse) a proposal inside a running run."""
        self._require_namespace(namespace)
        observation_ids = list(source_observation_ids or [])
        evidence_ids = list(source_evidence_ids or [])
        payload_json, reasoning_json, observations_json, evidence_json, effective_risk = (
            self._serialize_proposal_fields(
                proposal_type,
                payload,
                reasoning,
                confidence,
                observation_ids,
                evidence_ids,
                target_kind,
                target_id,
                risk_level,
            )
        )
        conn = self._adapter.get_raw_connection()
        run = conn.execute(
            "SELECT namespace, status FROM memory_reflection_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if run is None or run["namespace"] != namespace:
            raise ValueError(f"run not found in namespace: {run_id}")
        if run["status"] != "running":
            raise ValueError("proposals can only be created inside a running run")
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        existing = conn.execute(
            "SELECT proposal_id FROM memory_reflection_outputs "
            "WHERE namespace = ? AND proposal_type = ? AND idempotency_key = ?",
            (namespace, proposal_type, payload_hash),
        ).fetchone()
        if existing is not None:
            get_metrics_collector().increment("reflection_proposals_reused")
            return str(existing["proposal_id"])
        proposal_id = f"prp_{uuid.uuid4().hex}"
        try:
            conn.execute(
                """INSERT INTO memory_reflection_outputs
                   (proposal_id, run_id, namespace, proposal_type, target_kind, target_id,
                    payload_json, source_observation_ids, source_evidence_ids, confidence,
                    reasoning, risk_level, status, idempotency_key, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?)""",
                (
                    proposal_id,
                    run_id,
                    namespace,
                    proposal_type,
                    target_kind,
                    target_id,
                    payload_json,
                    observations_json,
                    evidence_json,
                    confidence,
                    reasoning_json,
                    effective_risk,
                    payload_hash,
                    _now(),
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        get_metrics_collector().increment("reflection_proposals_created")
        return proposal_id

    def get_proposal(self, namespace: str, proposal_id: str) -> Optional[Dict[str, Any]]:
        self._require_namespace(namespace)
        row = (
            self._adapter.get_raw_connection()
            .execute(
                "SELECT * FROM memory_reflection_outputs WHERE proposal_id = ? AND namespace = ?",
                (proposal_id, namespace),
            )
            .fetchone()
        )
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        item["reasoning"] = json.loads(item.pop("reasoning"))
        return item

    def list_proposals(
        self,
        namespace: str,
        status: Optional[str] = None,
        proposal_type: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        self._require_namespace(namespace)
        if status is not None and status not in VALID_PROPOSAL_STATUSES:
            raise ValueError(f"Invalid proposal status: {status}")
        if proposal_type is not None and proposal_type not in VALID_PROPOSAL_TYPES:
            raise ValueError(f"Invalid proposal_type: {proposal_type}")
        conditions = ["namespace = ?"]
        params: List[Any] = [namespace]
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if proposal_type is not None:
            conditions.append("proposal_type = ?")
            params.append(proposal_type)
        if run_id is not None:
            conditions.append("run_id = ?")
            params.append(run_id)
        params.append(max(0, int(limit)))
        rows = (
            self._adapter.get_raw_connection()
            .execute(
                "SELECT * FROM memory_reflection_outputs WHERE "
                + " AND ".join(conditions)
                + " ORDER BY created_at DESC LIMIT ?",
                params,
            )
            .fetchall()
        )
        return [dict(row) for row in rows]

    def approve_proposal(self, namespace: str, proposal_id: str, approved_by: str) -> None:
        """INV-P1: 'auto' is illegal for high-risk proposals."""
        self._require_namespace(namespace)
        if approved_by not in {"auto", "user"}:
            raise ValueError("approved_by must be 'auto' or 'user'")
        conn = self._adapter.get_raw_connection()
        row = conn.execute(
            "SELECT risk_level, status FROM memory_reflection_outputs " "WHERE proposal_id = ? AND namespace = ?",
            (proposal_id, namespace),
        ).fetchone()
        if row is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        if row["status"] != "proposed":
            raise ValueError(f"proposal is not proposed (status={row['status']})")
        if row["risk_level"] == "high" and approved_by == "auto":
            raise ValueError("INV-P1: high-risk proposals cannot be auto-approved")
        conn.execute(
            "UPDATE memory_reflection_outputs SET status = 'approved', approved_by = ? "
            "WHERE proposal_id = ? AND namespace = ?",
            (approved_by, proposal_id, namespace),
        )
        conn.commit()
        get_metrics_collector().increment("reflection_proposals_approved")

    def reject_proposal(self, namespace: str, proposal_id: str, approved_by: str) -> None:
        self._require_namespace(namespace)
        if approved_by not in {"auto", "user"}:
            raise ValueError("approved_by must be 'auto' or 'user'")
        conn = self._adapter.get_raw_connection()
        cursor = conn.execute(
            "UPDATE memory_reflection_outputs SET status = 'rejected', approved_by = ? "
            "WHERE proposal_id = ? AND namespace = ? AND status = 'proposed'",
            (approved_by, proposal_id, namespace),
        )
        if int(cursor.rowcount) != 1:
            raise ValueError(f"proposal not found or not proposed: {proposal_id}")
        conn.commit()
        get_metrics_collector().increment("reflection_proposals_rejected")

    # -- apply / rollback ---------------------------------------------------

    def apply_proposal(self, namespace: str, proposal_id: str) -> Dict[str, Any]:
        """Apply an approved proposal in a single transaction (INV-P3/INV-F3)."""
        self._require_namespace(namespace)
        conn = self._adapter.get_raw_connection()
        row = conn.execute(
            "SELECT * FROM memory_reflection_outputs WHERE proposal_id = ? AND namespace = ?",
            (proposal_id, namespace),
        ).fetchone()
        if row is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        if row["status"] == "applied":
            return {"proposal_id": proposal_id, "status": "applied", "reused": True}
        if row["status"] not in {"approved", "failed", "rolled_back"}:
            raise ValueError(f"proposal must be approved before apply (status={row['status']})")
        proposal_type = row["proposal_type"]
        handler = _APPLY_HANDLERS.get(proposal_type)
        payload = json.loads(row["payload_json"])
        target_id = row["target_id"]
        try:
            if handler is None:
                raise ValueError(f"no apply handler for proposal_type {proposal_type} (fail-closed)")
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            rollback_ref = handler(conn, namespace, str(target_id), payload)
            if not rollback_ref:
                raise ValueError("handler produced no rollback reference (INV-P3)")
            conn.execute(
                "UPDATE memory_reflection_outputs SET status = 'applied', applied_at = ?, "
                "rollback_ref = ?, error_text = NULL WHERE proposal_id = ?",
                (_now(), json.dumps(rollback_ref, ensure_ascii=False, sort_keys=True), proposal_id),
            )
            conn.commit()
        except (sqlite3.Error, ValueError) as exc:
            conn.rollback()
            self._record_apply_failure(proposal_id, exc)
            raise ValueError(f"apply failed: {exc}") from exc
        # Apply/rollback change which keys a query returns (visibility), so a
        # key-scoped invalidation cannot reach cached results that were
        # captured while the key was hidden. Match the visibility-changing
        # crud write paths and drop the whole namespace cache.
        self._adapter.invalidate_cache()
        get_metrics_collector().increment("reflection_proposals_applied")
        return {"proposal_id": proposal_id, "status": "applied", "rollback_ref": rollback_ref}

    def _record_apply_failure(self, proposal_id: str, exc: Exception) -> None:
        try:
            conn = self._adapter.get_raw_connection()
            conn.execute(
                "UPDATE memory_reflection_outputs SET status = 'failed', error_text = ? "
                "WHERE proposal_id = ? AND status IN ('approved', 'failed')",
                (_safe_error_text(str(exc)), proposal_id),
            )
            conn.commit()
            get_metrics_collector().increment("reflection_proposals_apply_failed")
        except sqlite3.Error:
            get_metrics_collector().increment("reflection_proposals_apply_failed")

    def rollback_proposal(self, namespace: str, proposal_id: str) -> Dict[str, Any]:
        """Undo an applied proposal's derived projection (INV-B1/INV-F4)."""
        self._require_namespace(namespace)
        conn = self._adapter.get_raw_connection()
        row = conn.execute(
            "SELECT proposal_type, target_id, rollback_ref, status FROM memory_reflection_outputs "
            "WHERE proposal_id = ? AND namespace = ?",
            (proposal_id, namespace),
        ).fetchone()
        if row is None:
            raise ValueError(f"proposal not found: {proposal_id}")
        if row["status"] != "applied" or not row["rollback_ref"]:
            raise ValueError(f"proposal is not applied (status={row['status']})")
        rollback_handler = _ROLLBACK_HANDLERS.get(row["proposal_type"])
        if rollback_handler is None:
            raise ValueError(f"no rollback handler for proposal_type {row['proposal_type']}")
        rollback_ref = json.loads(row["rollback_ref"])
        try:
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            rollback_handler(conn, namespace, str(row["target_id"]), rollback_ref)
            conn.execute(
                "UPDATE memory_reflection_outputs SET status = 'rolled_back' WHERE proposal_id = ?",
                (proposal_id,),
            )
            conn.commit()
        except (sqlite3.Error, ValueError) as exc:
            conn.rollback()
            raise ValueError(f"rollback failed: {exc}") from exc
        # Visibility changed (see apply_proposal): drop the namespace cache.
        self._adapter.invalidate_cache()
        get_metrics_collector().increment("reflection_proposals_rolled_back")
        return {"proposal_id": proposal_id, "status": "rolled_back"}

    def apply_auto_low_risk(self, namespace: str, run_id: str) -> List[str]:
        """Approve (auto) and apply every still-proposed low-risk proposal of a run."""
        self._require_namespace(namespace)
        applied: List[str] = []
        for row in self.list_proposals(namespace, status="proposed", run_id=run_id, limit=1000):
            proposal_id = row["proposal_id"]
            if row["risk_level"] != "low":
                continue
            try:
                self.approve_proposal(namespace, proposal_id, "auto")
                self.apply_proposal(namespace, proposal_id)
                applied.append(proposal_id)
            except ValueError:
                continue
        return applied

    def run_decay_reflection(
        self,
        namespace: str,
        stale_days: int = 90,
        min_importance: float = 0.3,
        batch_size: int = 100,
        grace_days: int = 30,
        auto_apply: bool = True,
    ) -> Dict[str, Any]:
        """Contract §6 migration slice: run the memify decay gate in proposal
        mode instead of direct mutation.

        Candidate selection uses the SAME shared three-way gate as
        ``MemifyEngine.auto_decay`` (对拍 baseline). The applied effect is the
        contract-approved expire semantics: each candidate gets an
        ``expire_projection`` proposal with ``expires_at = run.started_at +
        grace_days``. The timestamp is derived from the run's started_at, not
        wall clock, so replays produce identical payload hashes and dedup via
        INV-P2.
        """
        from carrymem.layers.memify import find_decay_candidates

        self._require_namespace(namespace)
        conn = self._adapter.get_raw_connection()
        candidate_keys = find_decay_candidates(conn, namespace, stale_days, min_importance, batch_size)
        config = {
            "stale_days": stale_days,
            "min_importance": min_importance,
            "batch_size": batch_size,
            "grace_days": grace_days,
        }
        config_json = json.dumps(config, sort_keys=True)
        snapshot = hashlib.sha256("\n".join(sorted(candidate_keys)).encode("utf-8")).hexdigest()
        run_id = self.start_run(namespace, "decay", "decay-proposal-v1", snapshot, config_json)
        run = conn.execute(
            "SELECT started_at, status FROM memory_reflection_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        started_at = datetime.fromisoformat(str(run["started_at"]))
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        expires_at = (started_at + timedelta(days=grace_days)).isoformat()
        created = 0
        try:
            if run["status"] == "running":
                for key in candidate_keys:
                    self.create_proposal(
                        namespace,
                        run_id,
                        "expire_projection",
                        {"expires_at": expires_at},
                        {
                            "strategy": "decay-gate",
                            "gate": config,
                            "evidence": {"support": 0, "contradiction": 0},
                        },
                        0.8,
                        target_kind="memory",
                        target_id=key,
                    )
                    created += 1
                self.complete_run(run_id)
        except Exception as exc:
            try:
                status_row = conn.execute(
                    "SELECT status FROM memory_reflection_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if status_row is not None and status_row["status"] == "running":
                    self.fail_run(run_id, str(exc))
            except (sqlite3.Error, ValueError):
                pass
            raise
        applied = self.apply_auto_low_risk(namespace, run_id) if auto_apply else []
        proposals_total = len(self.list_proposals(namespace, run_id=run_id, limit=1000))
        return {
            "run_id": run_id,
            "candidates": len(candidate_keys),
            "proposals_created": created,
            "proposals_total": proposals_total,
            "applied": applied,
        }
