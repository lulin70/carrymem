"""JSON file-based storage adapter — zero-dependency lightweight storage.

v0.7.0: Simple file-based adapter for scenarios without SQLite.

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

import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .base import MemoryEntry, StorageAdapter, StoredMemory
from ..scoring import calculate_importance


def _content_hash(content: str, memory_type: str) -> str:
    return hashlib.sha256(f"{memory_type}:{content}".encode()).hexdigest()[:16]


_TIER_TTL = {
    1: timedelta(hours=24),
    2: timedelta(days=90),
    3: timedelta(days=365),
    4: None,
}


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
        return ns.setdefault("memories", {})

    @property
    def name(self) -> str:
        return "json"

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "vector_search": False,
            "fts": False,
            "ttl": True,
            "batch": True,
            "graph": False,
            "semantic_recall": False,
        }

    def remember(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        with self._lock:
            memories = self._get_memories()
            c_hash = _content_hash(entry.content, entry.type)

            existing = memories.get(c_hash)
            if existing:
                return StoredMemory.from_dict(existing)

            now = datetime.now(timezone.utc)
            storage_key = f"cm_{now.strftime('%Y%m%d%H%M%S')}_{c_hash[:8]}"
            ttl = _TIER_TTL.get(entry.tier)
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
                "original_message": entry.metadata.get("original_message", "") if entry.metadata else "",
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

    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
    ) -> List[StoredMemory]:
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

    def forget(self, storage_key: str) -> bool:
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
        with self._lock:
            memories = self._get_memories()
            total = len(memories)
            by_type = {}
            by_tier = {}
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

    def close(self):
        pass
