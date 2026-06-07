"""Version history management for SQLiteAdapter."""

from typing import Any, Dict, List, Optional

from ..base import StoredMemory


class VersionManager:
    """Manages memory version history and rollback."""

    def __init__(self, adapter):
        self._adapter = adapter

    def get_memory_history(self, storage_key: str) -> List[Dict[str, Any]]:
        conn = self._adapter._conn_mgr.get_connection()
        row = conn.execute(
            "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._adapter.namespace),
        ).fetchone()
        if not row:
            return []

        memory_id = row["id"]
        versions = conn.execute(
            "SELECT * FROM memory_versions WHERE memory_id = ? ORDER BY version DESC",
            (memory_id,),
        ).fetchall()

        current_row = conn.execute(
            "SELECT * FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._adapter.namespace),
        ).fetchone()
        current = self._adapter._serializer.row_to_stored(current_row)

        history = []
        if current:
            history.append({
                "version": current.version,
                "content": current.content,
                "confidence": current.confidence,
                "changed_at": current.updated_at.isoformat() if current.updated_at else None,
                "change_reason": "Current version",
                "is_current": True,
            })

        for v in versions:
            history.append({
                "version": v["version"],
                "content": v["content"],
                "confidence": v["confidence"],
                "changed_at": v["changed_at"],
                "change_reason": v["change_reason"],
                "is_current": False,
            })

        return history

    def rollback_memory(self, storage_key: str, version: int) -> Optional[StoredMemory]:
        with self._adapter._conn_mgr.lock:
            conn = self._adapter._conn_mgr.get_connection()
            row = conn.execute(
                "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._adapter.namespace),
            ).fetchone()
            if not row:
                return None

            memory_id = row["id"]
            version_row = conn.execute(
                "SELECT * FROM memory_versions WHERE memory_id = ? AND version = ?",
                (memory_id, version),
            ).fetchone()
            if not version_row:
                return None

            old_content = version_row["content"]
            if self._adapter._security.encryption and self._adapter._security.encryption.is_active:
                old_content = self._adapter.decrypt_field(old_content)
            return self._adapter.update_memory(
                storage_key=storage_key,
                new_content=old_content,
                reason=f"Rollback to version {version}",
            )
