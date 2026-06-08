"""Statistics and profile queries for SQLiteAdapter."""

from typing import Any, Dict, List, Optional

from ..base import StoredMemory


class StatsManager:
    """Provides statistics, profiles, aggregated recalls, and timelines."""

    def __init__(self, adapter):
        self._adapter = adapter

    def get_stats(self) -> Dict[str, Any]:
        conn = self._adapter._conn_mgr.get_connection()
        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE namespace = ?",
            (self._adapter.namespace,),
        ).fetchone()[0]
        by_type_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM memories WHERE namespace = ? GROUP BY type",
            (self._adapter.namespace,),
        ).fetchall()
        by_type = {row["type"]: row["cnt"] for row in by_type_rows}

        return {
            "adapter": self._adapter.name,
            "namespace": self._adapter.namespace,
            "total_count": total,
            "by_type": by_type,
            "capabilities": self._adapter.capabilities,
            "db_path": self._adapter._conn_mgr.db_path,
        }

    def get_profile(self) -> Dict[str, Any]:
        conn = self._adapter._conn_mgr.get_connection()
        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE namespace = ?",
            (self._adapter.namespace,),
        ).fetchone()[0]

        if total == 0:
            return {
                "summary": "No memories yet",
                "total_memories": 0,
                "highlights": {},
                "stats": {"by_type": {}, "by_tier": {}, "confidence_avg": 0.0},
                "namespace": self._adapter.namespace,
                "last_updated": None,
            }

        by_type_rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM memories WHERE namespace = ? GROUP BY type",
            (self._adapter.namespace,),
        ).fetchall()
        by_type = {row["type"]: row["cnt"] for row in by_type_rows}

        by_tier_rows = conn.execute(
            "SELECT tier, COUNT(*) as cnt FROM memories WHERE namespace = ? GROUP BY tier",
            (self._adapter.namespace,),
        ).fetchall()
        by_tier = {str(row["tier"]): row["cnt"] for row in by_tier_rows}

        avg_conf = (
            conn.execute(
                "SELECT AVG(confidence) FROM memories WHERE namespace = ?",
                (self._adapter.namespace,),
            ).fetchone()[0]
            or 0.0
        )

        highlight_types = [
            "user_preference",
            "correction",
            "decision",
            "fact_declaration",
        ]
        highlights: Dict[str, List[str]] = {}
        for mem_type in highlight_types:
            rows = conn.execute(
                "SELECT content FROM memories WHERE namespace = ? AND type = ? ORDER BY confidence DESC LIMIT 5",
                (self._adapter.namespace, mem_type),
            ).fetchall()
            items = [row["content"][:100] for row in rows]
            if items:
                highlights[mem_type] = items

        last_updated_row = conn.execute(
            "SELECT MAX(updated_at) FROM memories WHERE namespace = ?",
            (self._adapter.namespace,),
        ).fetchone()
        last_updated = last_updated_row[0] if last_updated_row else None

        type_parts = []
        type_labels = {
            "user_preference": "preferences",
            "correction": "corrections",
            "decision": "decisions",
            "fact_declaration": "facts",
            "relationship": "relationships",
            "task_pattern": "task patterns",
            "sentiment_marker": "sentiments",
        }
        for t, cnt in by_type.items():
            label = type_labels.get(t, t)
            type_parts.append(f"{cnt} {label}")

        summary = f"AI remembers {total} things about you: " + ", ".join(type_parts)

        return {
            "summary": summary,
            "total_memories": total,
            "highlights": highlights,
            "stats": {
                "by_type": by_type,
                "by_tier": by_tier,
                "confidence_avg": round(avg_conf, 4),
            },
            "namespace": self._adapter.namespace,
            "last_updated": last_updated,
        }

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemory]]:
        with self._adapter._conn_mgr.lock:
            return self._recall_aggregated_impl(memory_type, namespaces, limit_per_type)

    def _recall_aggregated_impl(
        self,
        memory_type: Optional[str] = None,
        namespaces: Optional[List[str]] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemory]]:
        ns = namespaces or [self._adapter.namespace]
        placeholders = ",".join(["?"] * len(ns))
        params = list(ns)

        conditions = [f"namespace IN ({placeholders})"]
        conditions.append("(superseded_at IS NULL OR superseded_at = '')")

        if memory_type:
            conditions.append("type = ?")
            params.append(memory_type)

        where_clause = "WHERE " + " AND ".join(conditions)

        conn = self._adapter._conn_mgr.get_connection()
        if memory_type:
            sql = f"SELECT * FROM memories {where_clause} ORDER BY importance_score DESC, created_at DESC LIMIT ?"
            params.append(limit_per_type)
            rows = conn.execute(sql, params).fetchall()
            return {
                memory_type: [
                    self._adapter._serializer.row_to_stored(r)
                    for r in rows
                    if self._adapter._serializer.row_to_stored(r)
                ]
            }

        # Single-query aggregation: fetch all non-superseded memories ordered by
        # (type, importance_score DESC), then slice limit_per_type per type in Python.
        sql = f"SELECT * FROM memories {where_clause} ORDER BY type, importance_score DESC, created_at DESC"
        rows = conn.execute(sql, params).fetchall()

        result: Dict[str, List[StoredMemory]] = {}
        for row in rows:
            mtype = row["type"]
            if mtype not in result:
                result[mtype] = []
            if len(result[mtype]) < limit_per_type:
                stored = self._adapter._serializer.row_to_stored(row)
                if stored:
                    result[mtype].append(stored)
        return result

    def recall_timeline(
        self,
        topic: str,
        namespaces: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[StoredMemory]:
        with self._adapter._conn_mgr.lock:
            return self._recall_timeline_impl(topic, namespaces, limit)

    def _recall_timeline_impl(
        self,
        topic: str,
        namespaces: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[StoredMemory]:
        ns = namespaces or [self._adapter.namespace]
        placeholders = ",".join(["?"] * len(ns))
        params = list(ns)

        conditions = [f"namespace IN ({placeholders})"]

        words = [w for w in topic.lower().split() if len(w) > 1]
        if words:
            like_parts = []
            for w in words:
                like_parts.append("(content LIKE ? OR raw_text LIKE ?)")
                params.extend([f"%{w}%", f"%{w}%"])
            conditions.append(f"({' OR '.join(like_parts)})")

        where_clause = "WHERE " + " AND ".join(conditions)

        conn = self._adapter._conn_mgr.get_connection()
        sql = f"SELECT * FROM memories {where_clause} ORDER BY created_at ASC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [self._adapter._serializer.row_to_stored(r) for r in rows if self._adapter._serializer.row_to_stored(r)]
