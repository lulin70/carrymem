"""Integration tests for fine-grained cache invalidation in CRUD operations.

Verifies that forget() and update_memory() use invalidate_keys() to drop only
cached entries whose results reference the modified storage_key, preserving the
hit rate of unrelated queries in the same namespace.

Strategy: use empty query + type filter to isolate result sets per storage_key,
avoiding non-deterministic FTS matching behavior.
"""

import os
import tempfile
import unittest

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite_adapter import SQLiteAdapter

# Use distinct valid memory types so each recall query returns a disjoint set
TYPE_A = "user_preference"
TYPE_B = "fact_declaration"
NS = "test_ns"


def _make_adapter(db_path: str) -> SQLiteAdapter:
    return SQLiteAdapter(db_path=db_path, namespace=NS, enable_cache=True)


def _seed_two_entries(adapter: SQLiteAdapter):
    """Seed two memories of different types; returns (stored_a, stored_b)."""
    entry_a = MemoryEntry(
        id="mem_a",
        type=TYPE_A,
        content="alpha content unique token",
        confidence=0.9,
        tier=2,
    )
    entry_b = MemoryEntry(
        id="mem_b",
        type=TYPE_B,
        content="beta content unique token",
        confidence=0.9,
        tier=2,
    )
    stored_a = adapter.remember(entry_a)
    stored_b = adapter.remember(entry_b)
    return stored_a, stored_b


class TestCacheInvalidationForget(unittest.TestCase):
    """forget() should only invalidate cache entries referencing the deleted key."""

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.adapter = _make_adapter(self.db)
        self.stored_a, self.stored_b = _seed_two_entries(self.adapter)
        self.key_a = self.stored_a.storage_key
        self.key_b = self.stored_b.storage_key

    def tearDown(self):
        self.adapter.close()
        if os.path.exists(self.db):
            os.unlink(self.db)

    def _prime_cache_with_both_queries(self):
        """Run two recall queries so both are cached. Returns (results_a, results_b)."""
        filters_a = {"type": TYPE_A}
        filters_b = {"type": TYPE_B}
        results_a = self.adapter.recall("", filters=filters_a, limit=10)
        results_b = self.adapter.recall("", filters=filters_b, limit=10)
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0].storage_key, self.key_a)
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0].storage_key, self.key_b)
        self.assertEqual(self.adapter._cache.stats["size"], 2)
        return filters_a, filters_b

    def test_forget_preserves_unrelated_cache_entries(self):
        """forget(key_a) must drop only cache entries containing key_a."""
        filters_a, filters_b = self._prime_cache_with_both_queries()

        # Delete key_a — should invalidate only query_a, preserve query_b
        self.adapter.forget(self.key_a)

        # query_b (fact_declaration) should still be cached (hit)
        cached_b = self.adapter._cache.get(NS, "", filters_b, 10)
        self.assertIsNotNone(cached_b, "forget(key_a) must not evict unrelated query_b")

        # query_a (user_preference) should have been evicted (miss)
        cached_a = self.adapter._cache.get(NS, "", filters_a, 10)
        self.assertIsNone(cached_a, "forget(key_a) must evict cache entries containing key_a")

    def test_forget_nonexistent_key_does_not_invalidate(self):
        """forget() on a missing key should not touch the cache."""
        filters_a, filters_b = self._prime_cache_with_both_queries()
        size_before = self.adapter._cache.stats["size"]

        # Forget a key that does not exist → result=False → no invalidation
        self.adapter.forget("nonexistent_key_xyz")

        size_after = self.adapter._cache.stats["size"]
        self.assertEqual(size_before, size_after, "forget on missing key must not invalidate cache")

    def test_forget_then_recall_returns_empty(self):
        """After forget, recall should not return the deleted memory."""
        filters_a = {"type": TYPE_A}
        self.adapter.recall("", filters=filters_a, limit=10)

        self.adapter.forget(self.key_a)

        results = self.adapter.recall("", filters=filters_a, limit=10)
        self.assertEqual(len(results), 0, "deleted memory should not appear in recall")


class TestCacheInvalidationUpdate(unittest.TestCase):
    """update_memory() should invalidate cache entries referencing the updated key."""

    def setUp(self):
        self.db = tempfile.mktemp(suffix=".db")
        self.adapter = _make_adapter(self.db)
        self.stored_a, self.stored_b = _seed_two_entries(self.adapter)
        self.key_a = self.stored_a.storage_key
        self.key_b = self.stored_b.storage_key

    def tearDown(self):
        self.adapter.close()
        if os.path.exists(self.db):
            os.unlink(self.db)

    def _prime_cache_with_both_queries(self):
        """Run two recall queries so both are cached. Returns (filters_a, filters_b)."""
        filters_a = {"type": TYPE_A}
        filters_b = {"type": TYPE_B}
        self.adapter.recall("", filters=filters_a, limit=10)
        self.adapter.recall("", filters=filters_b, limit=10)
        self.assertEqual(self.adapter._cache.stats["size"], 2)
        return filters_a, filters_b

    def test_update_invalidates_only_affected_entry(self):
        """update_memory(key_a) must drop only cache entries containing key_a."""
        filters_a, filters_b = self._prime_cache_with_both_queries()

        # Update key_a content
        self.adapter.update_memory(self.key_a, "alpha content updated token", reason="test")

        # query_b (fact_declaration) should still be cached (hit)
        cached_b = self.adapter._cache.get(NS, "", filters_b, 10)
        self.assertIsNotNone(cached_b, "update(key_a) must not evict unrelated query_b")

        # query_a (user_preference) should have been evicted (content changed)
        cached_a = self.adapter._cache.get(NS, "", filters_a, 10)
        self.assertIsNone(cached_a, "update(key_a) must evict cache entries containing key_a")

    def test_update_reflects_new_content_after_invalidation(self):
        """After update, recall should return the new content (not stale cache)."""
        filters_a = {"type": TYPE_A}
        results_before = self.adapter.recall("", filters=filters_a, limit=10)
        self.assertEqual(len(results_before), 1)
        self.assertIn("alpha", results_before[0].content)

        # Update content
        self.adapter.update_memory(self.key_a, "alpha content UPDATED token", reason="test")

        # Recall again — cache was invalidated, should re-query and return new content
        results_after = self.adapter.recall("", filters=filters_a, limit=10)
        self.assertEqual(len(results_after), 1)
        self.assertIn(
            "UPDATED",
            results_after[0].content,
            "recall after update must return new content, not stale cache",
        )

    def test_update_unrelated_key_preserves_other_cache(self):
        """update_memory(key_b) must not evict cache entries for key_a."""
        filters_a, filters_b = self._prime_cache_with_both_queries()

        # Update key_b (fact_declaration) — should not affect query_a (user_preference)
        self.adapter.update_memory(self.key_b, "beta content updated token", reason="test")

        # query_a should still be cached (hit)
        cached_a = self.adapter._cache.get(NS, "", filters_a, 10)
        self.assertIsNotNone(cached_a, "update(key_b) must not evict unrelated query_a")

        # query_b should have been evicted (content changed)
        cached_b = self.adapter._cache.get(NS, "", filters_b, 10)
        self.assertIsNone(cached_b, "update(key_b) must evict cache entries containing key_b")


if __name__ == "__main__":
    unittest.main()
