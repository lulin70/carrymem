"""Recall cache — LRU with TTL invalidation for query results.

v0.5.0: Performance layer for frequently repeated recall queries.

Design:
- LRU eviction when cache exceeds max_size
- TTL-based automatic expiration (default 5 minutes)
- Write-through invalidation: remember/forget/declare clears affected namespace
- Thread-safe with threading.Lock
- Cache key: namespace + query + filters_hash + limit
"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from .adapters.base import StoredMemory


class _CacheEntry:
    __slots__ = ("value", "expires_at", "namespace")

    def __init__(self, value: List[Dict[str, Any]], expires_at: float, namespace: str):
        self.value = value
        self.expires_at = expires_at
        self.namespace = namespace


class RecallCache:
    """LRU cache for recall results with TTL invalidation."""

    def __init__(self, max_size: int = 256, ttl_seconds: int = 300):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

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
        key = self._make_key(namespace, query, filters, limit)
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._cache[key] = _CacheEntry(value, expires_at, namespace)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, namespace: str = None) -> None:
        with self._lock:
            if namespace is None:
                self._cache.clear()
                return
            keys_to_remove = [
                k for k, entry in self._cache.items()
                if entry.namespace == namespace
            ]
            for k in keys_to_remove:
                del self._cache[k]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
            }
