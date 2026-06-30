"""Tests for cache.py module - LRU cache with TTL"""

import time

import pytest

from carrymem.cache import RecallCache


class TestRecallCache:
    """Tests for RecallCache class"""

    def test_init(self):
        """Test cache initialization"""
        cache = RecallCache(max_size=100, ttl_seconds=60)
        assert cache._max_size == 100
        assert cache._ttl == 60
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_put_and_get(self):
        """Test basic put and get operations"""
        cache = RecallCache()
        value = [{"id": "1", "content": "test"}]

        cache.put("ns1", "query1", None, 10, value)
        result = cache.get("ns1", "query1", None, 10)

        assert result == value
        assert cache._hits == 1
        assert cache._misses == 0

    def test_get_miss(self):
        """Test cache miss"""
        cache = RecallCache()
        result = cache.get("ns1", "query1", None, 10)

        assert result is None
        assert cache._hits == 0
        assert cache._misses == 1

    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        cache = RecallCache(ttl_seconds=1)
        value = [{"id": "1"}]

        cache.put("ns1", "query1", None, 10, value)
        time.sleep(1.1)
        result = cache.get("ns1", "query1", None, 10)

        assert result is None
        assert cache._misses == 1

    def test_lru_eviction(self):
        """Test LRU eviction when max_size exceeded"""
        cache = RecallCache(max_size=2)

        cache.put("ns1", "q1", None, 10, [{"id": "1"}])
        cache.put("ns1", "q2", None, 10, [{"id": "2"}])
        cache.put("ns1", "q3", None, 10, [{"id": "3"}])

        assert len(cache._cache) == 2
        assert cache.get("ns1", "q1", None, 10) is None
        assert cache.get("ns1", "q2", None, 10) is not None
        assert cache.get("ns1", "q3", None, 10) is not None

    def test_lru_move_to_end(self):
        """Test LRU move to end on access"""
        cache = RecallCache(max_size=2)

        cache.put("ns1", "q1", None, 10, [{"id": "1"}])
        cache.put("ns1", "q2", None, 10, [{"id": "2"}])
        cache.get("ns1", "q1", None, 10)
        cache.put("ns1", "q3", None, 10, [{"id": "3"}])

        assert cache.get("ns1", "q1", None, 10) is not None
        assert cache.get("ns1", "q2", None, 10) is None

    def test_filters_in_key(self):
        """Test that filters affect cache key"""
        cache = RecallCache()
        value1 = [{"id": "1"}]
        value2 = [{"id": "2"}]

        cache.put("ns1", "query", {"type": "A"}, 10, value1)
        cache.put("ns1", "query", {"type": "B"}, 10, value2)

        assert cache.get("ns1", "query", {"type": "A"}, 10) == value1
        assert cache.get("ns1", "query", {"type": "B"}, 10) == value2

    def test_limit_in_key(self):
        """Test that limit affects cache key"""
        cache = RecallCache()
        value1 = [{"id": "1"}]
        value2 = [{"id": "2"}]

        cache.put("ns1", "query", None, 10, value1)
        cache.put("ns1", "query", None, 20, value2)

        assert cache.get("ns1", "query", None, 10) == value1
        assert cache.get("ns1", "query", None, 20) == value2

    def test_invalidate_all(self):
        """Test invalidate without namespace clears all"""
        cache = RecallCache()

        cache.put("ns1", "q1", None, 10, [{"id": "1"}])
        cache.put("ns2", "q2", None, 10, [{"id": "2"}])

        cache.invalidate()

        assert len(cache._cache) == 0
        assert cache.get("ns1", "q1", None, 10) is None
        assert cache.get("ns2", "q2", None, 10) is None

    def test_invalidate_namespace(self):
        cache = RecallCache()

        cache.put("ns1", "q1", None, 10, [{"id": "1"}])
        cache.put("ns2", "q2", None, 10, [{"id": "2"}])

        cache.invalidate("ns1")

        assert len(cache._cache) == 1
        assert cache.get("ns1", "q1", None, 10) is None
        assert cache.get("ns2", "q2", None, 10) is not None

    def test_invalidate_keys_empty_set_noop(self):
        """invalidate_keys with empty set does nothing."""
        cache = RecallCache()
        cache.put("ns1", "q1", None, 10, [{"storage_key": "k1"}])
        cache.invalidate_keys("ns1", set())
        assert len(cache._cache) == 1
        assert cache.get("ns1", "q1", None, 10) is not None

    def test_invalidate_keys_drops_only_matching_entries(self):
        """invalidate_keys drops only entries referencing the given storage_key."""
        cache = RecallCache()
        # query1 returns items with storage_key=k1
        cache.put("ns1", "q1", None, 10, [{"storage_key": "k1"}, {"storage_key": "k2"}])
        # query2 returns items with storage_key=k3 (unrelated)
        cache.put("ns1", "q2", None, 10, [{"storage_key": "k3"}])
        # query3 in different namespace (must be preserved)
        cache.put("ns2", "q1", None, 10, [{"storage_key": "k1"}])

        cache.invalidate_keys("ns1", {"k1"})

        # q1 dropped (contains k1), q2 preserved (only k3), ns2 preserved (different ns)
        assert cache.get("ns1", "q1", None, 10) is None
        assert cache.get("ns1", "q2", None, 10) is not None
        assert cache.get("ns2", "q1", None, 10) is not None

    def test_invalidate_keys_multiple_keys(self):
        """invalidate_keys handles multiple storage_keys in one call."""
        cache = RecallCache()
        cache.put("ns1", "q1", None, 10, [{"storage_key": "k1"}])
        cache.put("ns1", "q2", None, 10, [{"storage_key": "k2"}])
        cache.put("ns1", "q3", None, 10, [{"storage_key": "k3"}])

        cache.invalidate_keys("ns1", {"k1", "k2"})

        assert cache.get("ns1", "q1", None, 10) is None
        assert cache.get("ns1", "q2", None, 10) is None
        assert cache.get("ns1", "q3", None, 10) is not None

    def test_invalidate_keys_preserves_unrelated_queries(self):
        """invalidate_keys preserves hit rate for unrelated queries."""
        cache = RecallCache()
        # Simulate a write-heavy scenario: 10 queries, only 1 references the modified key
        for i in range(10):
            cache.put("ns1", f"q{i}", None, 10, [{"storage_key": f"k{i}"}])
        cache.put("ns1", "q_target", None, 10, [{"storage_key": "k_modified"}])

        cache.invalidate_keys("ns1", {"k_modified"})

        # Only q_target dropped, other 10 queries preserved
        for i in range(10):
            assert cache.get("ns1", f"q{i}", None, 10) is not None
        assert cache.get("ns1", "q_target", None, 10) is None

    def test_clear(self):
        """Test clear method resets stats"""
        cache = RecallCache()

        cache.put("ns1", "q1", None, 10, [{"id": "1"}])
        cache.get("ns1", "q1", None, 10)
        cache.get("ns1", "q2", None, 10)

        assert cache._hits > 0
        assert cache._misses > 0

        cache.clear()

        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_stats(self):
        """Test stats property"""
        cache = RecallCache(max_size=100, ttl_seconds=300)

        cache.put("ns1", "q1", None, 10, [{"id": "1"}])
        cache.get("ns1", "q1", None, 10)
        cache.get("ns1", "q2", None, 10)

        stats = cache.stats

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["ttl_seconds"] == 300
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_stats_zero_total(self):
        """Test stats with zero total requests"""
        cache = RecallCache()
        stats = cache.stats

        assert stats["hit_rate"] == 0.0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_make_key_consistency(self):
        """Test that _make_key produces consistent results"""
        key1 = RecallCache._make_key("ns", "query", {"a": 1, "b": 2}, 10)
        key2 = RecallCache._make_key("ns", "query", {"b": 2, "a": 1}, 10)

        assert key1 == key2

    def test_make_key_none_filters(self):
        """Test _make_key with None filters"""
        key1 = RecallCache._make_key("ns", "query", None, 10)
        key2 = RecallCache._make_key("ns", "query", {}, 10)

        assert key1 == key2

    def test_thread_safety(self):
        """Test basic thread safety with lock"""
        import threading

        cache = RecallCache()
        results = []

        def worker():
            cache.put("ns1", "q1", None, 10, [{"id": "1"}])
            result = cache.get("ns1", "q1", None, 10)
            results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r is not None for r in results)
