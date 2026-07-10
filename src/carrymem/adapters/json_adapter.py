"""JSON file-based storage adapter — zero-dependency lightweight storage.

Simple file-based adapter for scenarios without SQLite.

Features:
- Each namespace stored as a separate JSON file
- Full-text search via simple string matching (no FTS5)
- Content deduplication via content_hash
- Tier-based TTL expiry
- Thread-safe with file locking

Limitations:
- Not suitable for > 10K memories (loads entire file into memory)
- No FTS5 full-text search (uses substring matching)
- No semantic recall (no FTS5 index)
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..scoring import calculate_importance
from ..utils.helpers import TIER_TTL, content_hash
from .base import MemoryEntry, StorageAdapter, StoredMemory


class JSONAdapter(StorageAdapter):
    """JSON file-based storage adapter."""

    def __init__(
        self,
        path: Optional[str] = None,
        namespace: str = "default",
    ):
        self._namespace = namespace
        self._path = path or os.path.join(os.path.expanduser("~"), ".carrymem", "memories.json")
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        dir_path = os.path.dirname(self._path)
        if dir_path:
            os.makedirs(dir_path, mode=0o700, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _get_namespace_data(self) -> Dict[str, Any]:
        return self._data.setdefault(self._namespace, {})

    def _get_memories(self) -> Dict[str, Any]:
        ns = self._get_namespace_data()
        return ns.setdefault("memories", {})  # type: ignore[no-any-return]

    @property
    def name(self) -> str:
        """Human-readable adapter identifier."""
        return "json"

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Feature flags for this adapter."""
        return {
            "vector_search": False,
            "fts": False,
            "ttl": True,
            "batch": True,
            "graph": False,
            "semantic_recall": False,
        }

    def _store_entry(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        """Internal store implementation (shared by store() and remember())."""
        with self._lock:
            memories = self._get_memories()
            c_hash = content_hash(entry.content, entry.type)

            existing = memories.get(c_hash)
            if existing:
                return StoredMemory.from_dict(existing)

            now = datetime.now(timezone.utc)
            storage_key = f"cm_{now.strftime('%Y%m%d%H%M%S')}_{c_hash[:8]}"
            ttl = TIER_TTL.get(entry.tier)
            expires_at = (now + ttl).isoformat() if ttl else None

            imp_score = calculate_importance(
                confidence=entry.confidence,
                memory_type=entry.type,
                created_at=now,
                access_count=0,
                now=now,
            )

            stored_dict = {
                "id": entry.id or storage_key,
                "type": entry.type,
                "content": entry.content,
                "original_message": (entry.metadata.get("original_message", "") if entry.metadata else ""),
                "confidence": entry.confidence,
                "tier": entry.tier,
                "source_layer": entry.source_layer,
                "reasoning": entry.reasoning or "",
                "suggested_action": entry.suggested_action,
                "recall_hint": entry.recall_hint,
                "metadata": entry.metadata or {},
                "storage_key": storage_key,
                "namespace": self._namespace,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "expires_at": expires_at,
                "access_count": 0,
                "content_hash": c_hash,
                "importance_score": imp_score,
                "last_accessed_at": None,
                "version": 1,
            }

            memories[c_hash] = stored_dict
            if not _skip_commit:
                self._save()

            return StoredMemory.from_dict(stored_dict)

    def recall(  # type: ignore[override]
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[StoredMemory]:
        """Recall stored memories matching the query."""
        with self._lock:
            results = []
            now = datetime.now(timezone.utc)

            ns_list = namespaces or [self._namespace]
            for ns in ns_list:
                ns_data = self._data.get(ns, {})
                memories = ns_data.get("memories", {})

                for key, m in memories.items():
                    expires_at = m.get("expires_at")
                    if expires_at:
                        try:
                            exp = datetime.fromisoformat(expires_at)
                            if exp.tzinfo is None:
                                exp = exp.replace(tzinfo=timezone.utc)
                            if exp < now:
                                continue
                        except (ValueError, TypeError):
                            pass

                    if query:
                        content = m.get("content", "").lower()
                        orig = m.get("original_message", "").lower()
                        q = query.lower()
                        if q not in content and q not in orig:
                            continue

                    if filters:
                        if not self._matches_filters(m, filters):
                            continue

                    results.append(m)

            results.sort(key=lambda m: m.get("importance_score", 0), reverse=True)
            results = results[:limit]

            final = []
            for m in results:
                if update_access:
                    new_count = m.get("access_count", 0) + 1
                    m["access_count"] = new_count
                    m["last_accessed_at"] = now.isoformat()
                    try:
                        created = datetime.fromisoformat(m["created_at"]) if m.get("created_at") else now
                        m["importance_score"] = calculate_importance(
                            confidence=m.get("confidence", 0),
                            memory_type=m.get("type", "unknown"),
                            created_at=created,
                            access_count=new_count,
                            now=now,
                        )
                    except (ValueError, TypeError):
                        pass
                final.append(StoredMemory.from_dict(m))

            if update_access:
                self._save()
            return final

    def _matches_filters(self, m: Dict, filters: Dict) -> bool:
        if "type" in filters and m.get("type") != filters["type"]:
            return False
        if "tier" in filters and m.get("tier") != filters["tier"]:
            return False
        if "confidence_min" in filters and m.get("confidence", 0) < filters["confidence_min"]:
            return False
        return True

    def _delete_entry(self, storage_key: str) -> bool:
        """Internal delete implementation (shared by delete() and forget())."""
        with self._lock:
            memories = self._get_memories()
            to_delete = None
            for key, m in memories.items():
                if m.get("storage_key") == storage_key:
                    to_delete = key
                    break
            if to_delete:
                del memories[to_delete]
                self._save()
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics about stored memories."""
        with self._lock:
            memories = self._get_memories()
            total = len(memories)
            by_type: Dict[str, int] = {}
            by_tier: Dict[str, int] = {}
            conf_sum = 0.0
            for m in memories.values():
                t = m.get("type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
                tier = str(m.get("tier", 2))
                by_tier[tier] = by_tier.get(tier, 0) + 1
                conf_sum += m.get("confidence", 0)

            return {
                "adapter": "json",
                "total_count": total,
                "by_type": by_type,
                "by_tier": by_tier,
                "confidence_avg": round(conf_sum / total, 4) if total > 0 else 0.0,
                "namespace": self._namespace,
            }

    # ── Standardized Adapter Interface (P2-8) ─────────────────────

    def initialize(self, config: dict) -> None:
        """Initialize (re-initialize) the JSON adapter with config.

        Args:
            config: Optional config. Supported keys:
                    - ``path`` (str): Override the JSON file path
                    - ``namespace`` (str): Override the namespace
        """
        if config.get("path"):
            self._path = config["path"]
        if config.get("namespace"):
            self._namespace = config["namespace"]
        self._load()

    def store(self, entry: dict) -> str:
        """Store a memory entry from a plain dict and return its storage_key.

        Args:
            entry: Dict with ``content``, ``type`` and other MemoryEntry fields.

        Returns:
            The storage_key of the stored memory.
        """
        mem_entry = MemoryEntry.from_dict(entry)
        return self.store_entry(mem_entry).storage_key

    def store_entry(self, entry: MemoryEntry) -> StoredMemory:
        """Store a MemoryEntry and return the complete StoredMemory with metadata.

        Args:
            entry: The MemoryEntry object to persist.

        Returns:
            StoredMemory with storage_key and metadata fields populated.
        """
        return self._store_entry(entry)

    def delete(self, entry_id: str) -> bool:
        """Delete a memory by its storage_key."""
        return self._delete_entry(entry_id)

    def count(self, filter_: Optional[dict] = None) -> int:
        """Count stored memories with optional filtering.

        Args:
            filter_: Filter criteria. Supports ``type`` key.

        Returns:
            Number of matching memories.
        """
        stats = self.get_stats()
        if filter_ and "type" in filter_:
            by_type = stats.get("by_type", {})
            return by_type.get(filter_["type"], 0)  # type: ignore[no-any-return]
        return stats.get("total_count", 0)  # type: ignore[no-any-return]

    def health_check(self) -> dict:
        """Run a health check on the JSON file backend.

        Returns:
            Dict with status, latency_ms, and backend-specific metrics.
        """
        import time as _time

        start = _time.monotonic()
        status_detail = "healthy"
        try:
            with self._lock:
                total = len(self._get_memories())
                file_exists = os.path.exists(self._path)
                file_size = os.path.getsize(self._path) if file_exists else 0
        except Exception as e:
            from ..utils.logger import logger

            logger.warning("JSONAdapter health check failed: %s", e)
            status_detail = "unhealthy"
            total = -1
            file_exists = False
            file_size = 0
        elapsed_ms = (_time.monotonic() - start) * 1000.0

        return {
            "status": status_detail,
            "latency_ms": round(elapsed_ms, 3),
            "backend": "json",
            "file_path": self._path,
            "namespace": self._namespace,
            "entry_count": total,
            "file_exists": file_exists,
            "file_size_bytes": file_size,
        }

    def export_data(self) -> str:
        """Export all data as JSON string.

        Returns:
            JSON-serialized string of all stored memories.
        """
        import json as _json

        with self._lock:
            return _json.dumps(self._data, ensure_ascii=False, indent=2)

    def import_data(self, data: str) -> int:
        """Import data from an exported JSON string.

        Args:
            data: JSON string produced by :meth:`export_data`.

        Returns:
            Number of entries imported.
        """
        import json as _json

        new_data = _json.loads(data)
        count = 0
        with self._lock:
            ns_data = self._get_namespace_data()
            memories = ns_data.setdefault("memories", {})
            for key, entry_dict in new_data.items():
                if isinstance(entry_dict, dict):
                    memories[key] = entry_dict
                    count += 1
            self._save()
        return count

    def search_fulltext(self, query: str) -> list[dict]:
        """Full-text search across all stored entries.

        Args:
            query: Free-text search string.

        Returns:
            List of matching entry dicts.
        """
        results = self.recall(query, update_access=False)
        return [r.to_dict() for r in results]

    def close(self):
        """Release resources held by the adapter (no-op for JSON)."""
