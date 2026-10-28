"""Row serialization utilities for SQLiteAdapter."""

import json
from datetime import datetime
from typing import Dict, Optional

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

    @staticmethod
    def _load_json(row, key, default):
        """Load a JSON field from a row, returning default on invalid data."""
        if not row[key]:
            return default
        try:
            return json.loads(row[key])
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _row_value(row, key, default=None):
        """Return an optional row value without changing row access semantics."""
        return row[key] if key in row.keys() else default

    def _decrypt_optional(self, row, key, default=""):
        """Decrypt an optional field when it exists in the row."""
        if key not in row.keys():
            return default
        return self._adapter.decrypt_field(row[key])

    def _build_stored(self, row, metadata, recall_hint) -> StoredMemory:
        """Build a StoredMemory from the extracted row fields."""
        return StoredMemory(
            id=row["id"],
            type=row["type"],
            content=self._adapter.decrypt_field(row["content"]),
            raw_text=self._decrypt_optional(row, "raw_text"),
            confidence=row["confidence"],
            tier=row["tier"],
            source_layer=row["source_layer"] or "unknown",
            reasoning=row["reasoning"] or "",
            suggested_action=row["suggested_action"] or "store",
            recall_hint=recall_hint,
            metadata=metadata,
            storage_key=row["storage_key"],
            namespace=self._row_value(row, "namespace", self._adapter.namespace),
            created_at=self.safe_get_datetime(row, "created_at"),
            updated_at=self.safe_get_datetime(row, "updated_at"),
            expires_at=self.safe_get_datetime(row, "expires_at"),
            access_count=row["access_count"] or 0,
            importance_score=self.safe_get_float(row, "importance_score"),
            last_accessed_at=self.safe_get_datetime(row, "last_accessed_at"),
            version=self._row_value(row, "version", 1),
            superseded_at=self.safe_get_datetime(row, "superseded_at"),
            supersedes=self._row_value(row, "supersedes"),
            memory_nature=self._row_value(row, "memory_nature", "state"),
            version_chain_id=self._row_value(row, "version_chain_id"),
            version_number=self._row_value(row, "version_number", 1),
            summary=self._row_value(row, "summary"),
            summary_level=self._row_value(row, "summary_level"),
            paused=bool(self._row_value(row, "paused", False)),
            paused_at=self.safe_get_datetime(row, "paused_at"),
            pause_reason=self._row_value(row, "pause_reason"),
        )

    def row_to_stored(self, row) -> Optional[StoredMemory]:
        """Convert a sqlite3.Row to StoredMemory."""
        if not row:
            return None
        metadata = self._load_json(row, "metadata", {})
        recall_hint = self._load_json(row, "recall_hint", None)
        stored = self._build_stored(row, metadata, recall_hint)
        return stored

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
                id=d.get("id"),  # type: ignore[arg-type]
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
                storage_key=d.get("storage_key"),  # type: ignore[arg-type]
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
                summary=d.get("summary"),
                summary_level=d.get("summary_level"),
                paused=bool(d.get("paused", False)),
                paused_at=_get_dt("paused_at"),
                pause_reason=d.get("pause_reason"),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug("Failed to convert dict to StoredMemory: %s", e)
            return None
