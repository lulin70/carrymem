"""Recall cache — LRU with TTL invalidation for query results.

Performance layer for frequently repeated recall queries.

Design:
- LRU eviction when cache exceeds max_size
- TTL-based automatic expiration (default 5 minutes)
- Write-through invalidation: remember/forget/declare clears affected namespace
- Thread-safe with threading.Lock
- Cache key: namespace + query + filters_hash + limit
- Session dual-layer (v0.7.0): per-session memory pre-loading for O(1) recall
"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional


class _CacheEntry:
    __slots__ = ("value", "expires_at", "namespace")

    def __init__(self, value: List[Dict[str, Any]], expires_at: float, namespace: str):
        self.value = value
        self.expires_at = expires_at
        self.namespace = namespace


class RecallCache:
    """LRU cache for recall results with TTL invalidation.

    v0.7.0: Also supports session-scoped memory pre-loading for O(1) recall
    within a conversation session. Session memories are stored separately
    from query-result cache and survive until the session is invalidated.
    """

    def __init__(self, max_size: int = 256, ttl_seconds: int = 300, session_max_size: int = 128):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        # v0.7.0: Session dual-layer — session_id -> {storage_key -> memory_dict}
        self._session_max_size = session_max_size
        self._sessions: Dict[str, OrderedDict[str, Dict[str, Any]]] = {}
        self._session_hits = 0
        self._session_misses = 0

    @staticmethod
    def _make_key(
        namespace: str,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
    ) -> str:
        filters_str = json.dumps(filters or {}, sort_keys=True, ensure_ascii=False)
        raw = f"{namespace}:{query}:{filters_str}:{limit}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(
        self,
        namespace: str,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Return cached results for the query, or None if missing/expired."""
        key = self._make_key(namespace, query, filters, limit)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time.monotonic() > entry.expires_at:
                del self._cache[key]
                self._misses += 1
                return None
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def put(
        self,
        namespace: str,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        value: List[Dict[str, Any]],
    ) -> None:
        """Store query results in the cache with TTL eviction."""
        key = self._make_key(namespace, query, filters, limit)
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._cache[key] = _CacheEntry(value, expires_at, namespace)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, namespace: Optional[str] = None) -> None:
        """Drop cached entries, optionally scoped to a namespace."""
        with self._lock:
            if namespace is None:
                self._cache.clear()
                return
            keys_to_remove = [k for k, entry in self._cache.items() if entry.namespace == namespace]
            for k in keys_to_remove:
                del self._cache[k]

    def invalidate_keys(self, namespace: str, storage_keys: set[str]) -> None:
        """Drop cached entries whose results contain any of the given storage_keys.

        Finer-grained than invalidate(namespace): only queries whose cached
        result set references a modified/deleted memory are dropped, preserving
        hit rate for unrelated queries in the same namespace.
        """
        if not storage_keys:
            return
        with self._lock:
            keys_to_remove: list[str] = []
            for cache_key, entry in self._cache.items():
                if entry.namespace != namespace:
                    continue
                if any(item.get("storage_key") in storage_keys for item in entry.value):
                    keys_to_remove.append(cache_key)
            for k in keys_to_remove:
                del self._cache[k]

    def clear(self) -> None:
        """Remove all entries and reset hit/miss counters."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._sessions.clear()
            self._session_hits = 0
            self._session_misses = 0

    @property
    def stats(self) -> Dict[str, Any]:
        """Return cache size and hit/miss statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            session_total = self._session_hits + self._session_misses
            session_hit_rate = self._session_hits / session_total if session_total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
                "session_count": len(self._sessions),
                "session_hits": self._session_hits,
                "session_misses": self._session_misses,
                "session_hit_rate": round(session_hit_rate, 4),
            }

    # ── Session dual-layer (v0.7.0) ──────────────────────────────

    def session_preload(self, session_id: str, memories: List[Dict[str, Any]]) -> int:
        """Pre-load memories into the session cache for O(1) recall.

        Args:
            session_id: Unique session identifier.
            memories: List of memory dicts to pre-load.

        Returns:
            Number of memories stored.
        """
        if not session_id or not memories:
            return 0
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = OrderedDict()
            session = self._sessions[session_id]
            for mem in memories:
                key = mem.get("storage_key", "")
                if key:
                    session[key] = mem
            # Enforce max size with LRU eviction
            while len(session) > self._session_max_size:
                session.popitem(last=False)
            return len(session)

    def session_search(
        self,
        session_id: str,
        query: str,
        limit: int = 10,
    ) -> Optional[List[Dict[str, Any]]]:
        """Search session-cached memories by keyword (v0.7.0).

        Performs a simple case-insensitive substring match on content and
        raw_text fields. This is O(n) where n is the number of pre-loaded
        memories, but n is small (typically <128) so it's effectively O(1)
        compared to a full FTS5 query.

        Args:
            session_id: Session to search.
            query: Search query.
            limit: Maximum results.

        Returns:
            List of matching memory dicts, or None if session not found.
        """
        if not session_id or not query:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                self._session_misses += 1
                return None
            query_lower = query.lower()
            results: List[Dict[str, Any]] = []
            for mem in session.values():
                content = (mem.get("content") or "").lower()
                raw_text = (mem.get("raw_text") or "").lower()
                if query_lower in content or query_lower in raw_text:
                    results.append(mem)
                if len(results) >= limit:
                    break
            self._session_hits += 1
            return results

    def session_put(self, session_id: str, memory: Dict[str, Any]) -> None:
        """Add a single memory to the session cache (v0.7.0).

        Args:
            session_id: Session to add to.
            memory: Memory dict with storage_key.
        """
        if not session_id or not memory:
            return
        key = memory.get("storage_key", "")
        if not key:
            return
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = OrderedDict()
            session = self._sessions[session_id]
            session[key] = memory
            session.move_to_end(key)
            while len(session) > self._session_max_size:
                session.popitem(last=False)

    def invalidate_session(self, session_id: Optional[str] = None) -> None:
        """Clear session cache (v0.7.0).

        Args:
            session_id: Session to clear. If None, clears all sessions.
        """
        with self._lock:
            if session_id is None:
                self._sessions.clear()
            else:
                self._sessions.pop(session_id, None)

    def session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a specific session (v0.7.0)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return {"session_id": session_id, "size": 0, "exists": False}
            return {
                "session_id": session_id,
                "size": len(session),
                "max_size": self._session_max_size,
                "exists": True,
            }
