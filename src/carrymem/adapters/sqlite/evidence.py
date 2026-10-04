"""Evidence link management for memory provenance (Phase 1, ADR-015).

Evidence links record "which sources support or contradict a derived
object". Every derived object must trace back to at least one original
source (INV-F1); links are immutable and idempotent (INV-E2/E3); the
namespace of source and target must agree (INV-E1).

Design notes:
- Zero LLM, pure SQL, namespace-isolated — same principles as the
  knowledge graph layer.
- Links are metadata only (no memory content), so they are safe to
  retain permanently (approved decision D2).
- Metric series follow the ``operation``-label contract of the process
  metrics collector: ``carrymem_total{operation="evidence_link_*"}``.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from carrymem.monitoring import get_metrics_collector
from carrymem.utils.logger import logger

if TYPE_CHECKING:  # pragma: no cover
    from carrymem.adapters.sqlite import SQLiteAdapter

try:
    import pysqlite3.dbapi2 as _pysqlite3

    _OpError: tuple = (sqlite3.OperationalError, _pysqlite3.OperationalError)
except ImportError:  # pragma: no cover
    _OpError = (sqlite3.OperationalError,)

VALID_RELATION_TYPES = frozenset(
    {"supports", "contradicts", "derived_from", "observed_in", "confirmed_by", "supersedes"}
)
VALID_SOURCE_KINDS = frozenset({"memory", "observation", "fact", "external_import", "reflection_run"})
VALID_TARGET_KINDS = frozenset(
    {"memory", "observation", "fact", "experience", "profile", "model_claim", "relation", "rule_candidate"}
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceLinkManager:
    """Manages the ``memory_evidence_links`` table (provenance layer).

    Attached to :class:`~carrymem.adapters.sqlite.SQLiteAdapter` and
    created by :meth:`~carrymem.adapters.sqlite.SQLiteAdapter.add_evidence_link`
    and friends. Requires the v200 evolution schema.
    """

    def __init__(self, adapter: "SQLiteAdapter"):
        self._adapter = adapter

    # ── Write path ────────────────────────────────────────────────

    def add_link(
        self,
        namespace: str,
        source_kind: str,
        source_id: str,
        source_snapshot_hash: str,
        target_kind: str,
        target_id: str,
        relation_type: str,
        support_weight: float = 1.0,
    ) -> Optional[str]:
        """Insert one evidence link (idempotent) and return its id.

        Returns ``None`` when the link already exists (UNIQUE constraint
        hit — INV-E3) or when the schema is not available.
        Raises ``ValueError`` on invalid enum values (INV-E1/E2 guards).
        """
        if relation_type not in VALID_RELATION_TYPES:
            raise ValueError(f"Invalid relation_type '{relation_type}'. Valid: {sorted(VALID_RELATION_TYPES)}")
        if source_kind not in VALID_SOURCE_KINDS:
            raise ValueError(f"Invalid source_kind '{source_kind}'. Valid: {sorted(VALID_SOURCE_KINDS)}")
        if target_kind not in VALID_TARGET_KINDS:
            raise ValueError(f"Invalid target_kind '{target_kind}'. Valid: {sorted(VALID_TARGET_KINDS)}")
        if not source_id or not target_id:
            raise ValueError("source_id and target_id must be non-empty")
        if not source_snapshot_hash:
            raise ValueError("source_snapshot_hash must be non-empty")
        if not 0.0 < support_weight <= 2.0:
            raise ValueError(f"support_weight must be in (0, 2], got {support_weight}")

        conn = self._adapter.get_raw_connection()
        link_id = f"ev_{uuid.uuid4().hex}"
        # file_lock invariant: raw-connection writers must serialize with the
        # CRUD/recall write paths (flaky SQLITE_BUSY under concurrent classify).
        with self._adapter.write_lock:
            try:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO memory_evidence_links
                       (id, namespace, source_kind, source_id, source_snapshot_hash,
                        target_kind, target_id, relation_type, support_weight, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        link_id,
                        namespace,
                        source_kind,
                        source_id,
                        source_snapshot_hash,
                        target_kind,
                        target_id,
                        relation_type,
                        support_weight,
                        _utc_now_iso(),
                    ),
                )
                inserted = cursor.rowcount > 0
                conn.commit()
            except _OpError as e:
                try:
                    conn.rollback()
                except _OpError:
                    pass
                logger.warning("add_evidence_link failed (%s): %s", relation_type, e)
                return None

        if inserted:
            get_metrics_collector().increment(f"evidence_link_{relation_type}")
            return link_id
        return None  # duplicate — idempotent no-op

    # ── Read path ─────────────────────────────────────────────────

    def list_links(
        self,
        namespace: str,
        target_kind: Optional[str] = None,
        target_id: Optional[str] = None,
        source_kind: Optional[str] = None,
        source_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        include_stale: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List evidence links scoped to a namespace (INV-E1).

        With ``include_stale=False`` only links whose source still exists
        are returned (valid evidence). Stale detection is source-existence
        based: Phase 1 sources are memories, so validity is a join against
        ``memories.storage_key``.
        """
        conditions = ["el.namespace = ?"]
        params: List[Any] = [namespace]
        if target_kind is not None:
            conditions.append("el.target_kind = ?")
            params.append(target_kind)
        if target_id is not None:
            conditions.append("el.target_id = ?")
            params.append(target_id)
        if source_kind is not None:
            conditions.append("el.source_kind = ?")
            params.append(source_kind)
        if source_id is not None:
            conditions.append("el.source_id = ?")
            params.append(source_id)
        if relation_type is not None:
            conditions.append("el.relation_type = ?")
            params.append(relation_type)
        if not include_stale:
            conditions.append(
                "EXISTS (SELECT 1 FROM memories m WHERE m.storage_key = el.source_id AND el.source_kind = 'memory')"
            )

        sql = (
            "SELECT el.id, el.namespace, el.source_kind, el.source_id, el.source_snapshot_hash, "
            "el.target_kind, el.target_id, el.relation_type, el.support_weight, el.created_at "
            "FROM memory_evidence_links el WHERE " + " AND ".join(conditions) + " ORDER BY el.created_at LIMIT ?"
        )
        params.append(int(limit))

        conn = self._adapter.get_raw_connection()
        try:
            rows = conn.execute(sql, params).fetchall()
        except _OpError as e:
            logger.warning("list_evidence_links failed: %s", e)
            return []
        return [dict(row) for row in rows]

    def get_unsupported_targets(
        self,
        namespace: str,
        candidate_target_ids: List[str],
    ) -> List[str]:
        """Return the subset of ``candidate_target_ids`` with zero valid evidence.

        A target is *unsupported* when none of its evidence links points to
        a source that still exists (INV-E4). Phase 1 sources are memories.
        """
        if not candidate_target_ids:
            return []
        conn = self._adapter.get_raw_connection()
        placeholders = ",".join("?" * len(candidate_target_ids))
        try:
            rows = conn.execute(
                f"""SELECT DISTINCT el.target_id FROM memory_evidence_links el
                    WHERE el.namespace = ? AND el.target_kind = 'memory'
                      AND el.target_id IN ({placeholders})
                      AND NOT EXISTS (
                          SELECT 1 FROM memory_evidence_links el2
                          JOIN memories m2
                            ON el2.source_kind = 'memory' AND m2.storage_key = el2.source_id
                          WHERE el2.namespace = el.namespace
                            AND el2.target_kind = el.target_kind
                            AND el2.target_id = el.target_id
                      )""",
                [namespace, *candidate_target_ids],
            ).fetchall()
        except _OpError as e:
            logger.warning("get_unsupported_targets failed: %s", e)
            return []
        return [row["target_id"] for row in rows]

    # ── Delete cascade (INV-E4 materialization) ──────────────────

    def mark_unsupported_for_deleted_source(
        self,
        conn: sqlite3.Connection,
        namespace: str,
        deleted_source_id: str,
    ) -> int:
        """Flag derived memories that lost their last valid evidence source.

        Called inside the same transaction as the source ``DELETE``: the
        deleted row is already gone, so the validity join naturally excludes
        it. Only targets linked to the deleted source are considered
        (surgical — legacy unlinked derivations are not touched here).

        Returns the number of memories flagged (metadata-only annotation:
        ``provenance_unsupported`` / ``provenance_unsupported_at``).
        """
        try:
            cursor = conn.execute(
                """UPDATE memories
                   SET metadata = json_set(
                           COALESCE(metadata, '{}'),
                           '$.provenance_unsupported', 1,
                           '$.provenance_unsupported_at', ?
                       )
                   WHERE namespace = ?
                     AND json_extract(COALESCE(metadata, '{}'), '$.provenance_unsupported') IS NULL
                     AND storage_key IN (
                         SELECT DISTINCT el.target_id FROM memory_evidence_links el
                         WHERE el.namespace = ?
                           AND el.source_kind = 'memory'
                           AND el.source_id = ?
                           AND el.target_kind = 'memory'
                           AND NOT EXISTS (
                               SELECT 1 FROM memory_evidence_links el2
                               JOIN memories m2
                                 ON el2.source_kind = 'memory' AND m2.storage_key = el2.source_id
                               WHERE el2.namespace = el.namespace
                                 AND el2.target_kind = el.target_kind
                                 AND el2.target_id = el.target_id
                           )
                     )""",
                (_utc_now_iso(), namespace, namespace, deleted_source_id),
            )
            count = int(cursor.rowcount)
        except _OpError as e:
            logger.warning("mark_unsupported_for_deleted_source failed: %s", e)
            return 0
        if count:
            get_metrics_collector().increment("evidence_derived_unsupported", value=count)
        return count
