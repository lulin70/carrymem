"""Row serialization utilities for SQLiteAdapter."""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from ...utils.logger import logger
from ..base import StoredMemory


class RowSerializer:
    """Converts between raw DB rows/dicts and StoredMemory objects."""

    def __init__(self, adapter):
        self._adapter = adapter

    @staticmethod
    def safe_get_datetime(row, key, default=None):
        """Safely extract ISO datetime from a row (sqlite3.Row or dict)."""
        try:
            val = row[key]
        except (KeyError, IndexError):
            return default
        if not val or val == "":
            return default
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def safe_get_float(row, key, default=0.0):
        """Safely extract float from a row (sqlite3.Row or dict)."""
        try:
            val = row[key]
        except (KeyError, IndexError):
            return default
        if val is None or val == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def row_to_stored(self, row) -> Optional[StoredMemory]:
        """Convert a sqlite3.Row to StoredMemory."""
        import sqlite3

        if not row:
            return None

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        recall_hint = None
        if row["recall_hint"]:
            try:
                recall_hint = json.loads(row["recall_hint"])
            except (json.JSONDecodeError, TypeError):
                recall_hint = None

        return StoredMemory(
            id=row["id"],
            type=row["type"],
            content=self._adapter.decrypt_field(row["content"]),
            raw_text=self._adapter.decrypt_field(row["raw_text"]) if "raw_text" in row.keys() else "",
            confidence=row["confidence"],
            tier=row["tier"],
            source_layer=row["source_layer"] or "unknown",
            reasoning=row["reasoning"] or "",
            suggested_action=row["suggested_action"] or "store",
            recall_hint=recall_hint,
            metadata=metadata,
            storage_key=row["storage_key"],
            namespace=row["namespace"] if "namespace" in row.keys() else self._adapter.namespace,
            created_at=self.safe_get_datetime(row, "created_at"),
            updated_at=self.safe_get_datetime(row, "updated_at"),
            expires_at=self.safe_get_datetime(row, "expires_at"),
            access_count=row["access_count"] or 0,
            importance_score=self.safe_get_float(row, "importance_score"),
            last_accessed_at=self.safe_get_datetime(row, "last_accessed_at"),
            version=row["version"] if "version" in row.keys() else 1,
            superseded_at=self.safe_get_datetime(row, "superseded_at"),
            supersedes=row["supersedes"] if "supersedes" in row.keys() else None,
            memory_nature=row["memory_nature"] if "memory_nature" in row.keys() else "state",
            version_chain_id=row["version_chain_id"] if "version_chain_id" in row.keys() else None,
            version_number=row["version_number"] if "version_number" in row.keys() else 1,
        )

    def dict_to_stored(self, d: Dict) -> Optional[StoredMemory]:
        """Convert a dict back to StoredMemory (for merged results)."""
        if not d or not isinstance(d, dict):
            return None

        try:
            metadata = {}
            if d.get("metadata"):
                if isinstance(d["metadata"], str):
                    metadata = json.loads(d["metadata"])
                elif isinstance(d["metadata"], dict):
                    metadata = d["metadata"]

            recall_hint = None
            if d.get("recall_hint"):
                if isinstance(d["recall_hint"], str):
                    recall_hint = json.loads(d["recall_hint"])
                else:
                    recall_hint = d["recall_hint"]

            def _get_dt(key, default=None):
                val = d.get(key)
                if not val:
                    return default
                if isinstance(val, str):
                    try:
                        return datetime.fromisoformat(val)
                    except (ValueError, TypeError):
                        return default
                return val

            return StoredMemory(
                id=d.get("id"),
                type=d.get("type", "unknown"),
                content=d.get("content", ""),
                raw_text=d.get("raw_text", ""),
                confidence=d.get("confidence", 0.0),
                tier=d.get("tier", 2),
                source_layer=d.get("source_layer", "unknown"),
                reasoning=d.get("reasoning", ""),
                suggested_action=d.get("suggested_action", "store"),
                recall_hint=recall_hint,
                metadata=metadata,
                storage_key=d.get("storage_key"),
                created_at=_get_dt("created_at"),
                updated_at=_get_dt("updated_at"),
                expires_at=_get_dt("expires_at"),
                access_count=d.get("access_count", 0),
                importance_score=d.get("importance_score", 0.0),
                last_accessed_at=_get_dt("last_accessed_at"),
                version=d.get("version", 1),
                memory_nature=d.get("memory_nature", "state"),
                version_chain_id=d.get("version_chain_id"),
                version_number=d.get("version_number", 1),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Failed to convert dict to StoredMemory: {e}")
            return None
