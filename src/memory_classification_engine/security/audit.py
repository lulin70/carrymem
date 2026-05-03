"""Audit logging for memory operations.

v0.6.0: Structured audit trail for all memory operations.

Audit log is stored in the same SQLite database as memories,
in a separate audit_log table. This ensures:
- Atomic logging (same transaction as the operation)
- No external dependencies
- Easy querying via SQL

Design:
- Append-only: no UPDATE or DELETE on audit_log
- Lightweight: only essential fields logged
- Queryable: by time range, operation type, namespace
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


_AUDIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    operation TEXT NOT NULL,
    namespace TEXT NOT NULL,
    storage_key TEXT,
    memory_type TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    details TEXT,
    source TEXT DEFAULT 'api'
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_namespace ON audit_log(namespace);
"""


class AuditLogger:
    """Structured audit logging for memory operations."""

    def __init__(self, connection_factory, namespace: str = "default"):
        self._get_connection = connection_factory
        self._namespace = namespace
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._get_connection()
        try:
            conn.executescript(_AUDIT_SCHEMA_SQL)
            conn.commit()
        except sqlite3.Error:
            pass

    def log_operation(
        self,
        operation: str,
        namespace: Optional[str] = None,
        storage_key: Optional[str] = None,
        memory_type: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        source: str = "api",
    ) -> None:
        conn = self._get_connection()
        try:
            details_json = json.dumps(details) if details else None
            conn.execute(
                """INSERT INTO audit_log (operation, namespace, storage_key, memory_type, success, details, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation,
                    namespace or self._namespace,
                    storage_key,
                    memory_type,
                    1 if success else 0,
                    details_json,
                    source,
                ),
            )
            conn.commit()
        except sqlite3.Error:
            pass

    def query(
        self,
        operation: Optional[str] = None,
        namespace: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        conditions = []
        params: list = []

        if operation:
            conditions.append("operation = ?")
            params.append(operation)
        if namespace:
            conditions.append("namespace = ?")
            params.append(namespace)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)
        if source:
            conditions.append("source = ?")
            params.append(source)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM audit_log WHERE {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for row in rows:
                entry = {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "operation": row["operation"],
                    "namespace": row["namespace"],
                    "storage_key": row["storage_key"],
                    "memory_type": row["memory_type"],
                    "success": bool(row["success"]),
                    "details": json.loads(row["details"]) if row["details"] else None,
                    "source": row["source"],
                }
                results.append(entry)
            return results
        except sqlite3.Error:
            return []

    def get_stats(self) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            by_op_rows = conn.execute(
                "SELECT operation, COUNT(*) as cnt FROM audit_log GROUP BY operation"
            ).fetchall()
            by_op = {row["operation"]: row["cnt"] for row in by_op_rows}

            last_row = conn.execute(
                "SELECT timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            last_activity = last_row["timestamp"] if last_row else None

            return {
                "total_operations": total,
                "by_operation": by_op,
                "last_activity": last_activity,
            }
        except sqlite3.Error:
            return {"total_operations": 0, "by_operation": {}, "last_activity": None}
