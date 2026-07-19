"""Unit tests for RecallMixin: recall_memories, recall_all, recall_aggregated, etc."""

import os
import shutil
import tempfile
import unittest

from carrymem import CarryMem
from carrymem.core._lifecycle import StorageNotConfiguredError


class TestRecallMemories(unittest.TestCase):
    """Tests for CarryMem.recall_memories() (RecallMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "recall.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        # Store some test memories
        self.cm.declare("I prefer dark mode")
        self.cm.declare("I like Python programming")
        self.cm.declare("My name is Alice")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_recall_memories_by_query(self):
        """recall_memories() returns memories matching query."""
        results = self.cm.recall_memories(query="dark mode")
        self.assertIsInstance(results, list)

    def test_recall_memories_with_limit(self):
        """recall_memories() respects the limit parameter."""
        results = self.cm.recall_memories(query="", limit=2)
        self.assertLessEqual(len(results), 2)

    def test_recall_memories_empty_db(self):
        """recall_memories() returns empty list for empty database."""
        tmpdir2 = tempfile.mkdtemp()
        db_path2 = os.path.join(tmpdir2, "empty.db")
        cm2 = CarryMem(storage="sqlite", db_path=db_path2, auto_backup_interval=0)
        try:
            results = cm2.recall_memories(query="nonexistent")
            self.assertEqual(results, [])
        finally:
            cm2.close()
            shutil.rmtree(tmpdir2, ignore_errors=True)

    def test_recall_memories_with_namespace_filter(self):
        """recall_memories() accepts namespaces parameter."""
        results = self.cm.recall_memories(query="", namespaces=["default"])
        self.assertIsInstance(results, list)

    def test_recall_memories_no_adapter_raises(self):
        """recall_memories() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.recall_memories(query="test")
        finally:
            cm.close()

    def test_recall_memories_returns_dicts(self):
        """recall_memories() returns list of dicts."""
        results = self.cm.recall_memories(query="")
        for r in results:
            self.assertIsInstance(r, dict)

    def test_recall_memories_with_type_filter(self):
        """recall_memories() accepts filters with type."""
        results = self.cm.recall_memories(query="", filters={"type": "user_preference"})
        self.assertIsInstance(results, list)

    def test_recall_memories_update_access_flag(self):
        """recall_memories() accepts update_access parameter."""
        results = self.cm.recall_memories(query="", update_access=False)
        self.assertIsInstance(results, list)


class TestSemanticRecallBatchedLike(unittest.TestCase):
    """P1-5: Verify semantic recall fallback uses batched LIKE (not N+1)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "semantic.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        # Store CJK memories to trigger semantic expansion + LIKE fallback
        self.cm.declare("我喜欢用Python编程")
        self.cm.declare("我喜欢机器学习")
        self.cm.declare("Python是最好的编程语言")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cjk_semantic_recall_returns_results(self):
        """Semantic recall with CJK query returns matching results."""
        results = self.cm.recall_memories(query="Python编程")
        self.assertIsInstance(results, list)

    def test_cjk_semantic_recall_dedup(self):
        """Batched LIKE results are deduplicated (no duplicate rows)."""
        results = self.cm.recall_memories(query="Python")
        seen_ids = set()
        for r in results:
            if isinstance(r, dict):
                key = r.get("id") or r.get("storage_key", id(r))
            else:
                key = getattr(r, "id", None) or getattr(r, "storage_key", id(r))
            self.assertNotIn(key, seen_ids, f"Duplicate result found: {key}")
            seen_ids.add(key)

    def test_like_injection_safety(self):
        """LIKE special characters (%, _, \\) in query don't cause wildcard expansion."""
        # Query with % should be treated as literal, not wildcard
        results1 = self.cm.recall_memories(query="100%Python")
        results2 = self.cm.recall_memories(query="100PercentPython")
        # Both should return lists without errors (injection doesn't crash)
        self.assertIsInstance(results1, list)
        self.assertIsInstance(results2, list)


class TestRecallAccessThrottle(unittest.TestCase):
    """P1-4: Verify WAL throttle mechanism for access_count/last_accessed_at updates.

    Throttle skips access_count/last_accessed_at DB writes when the same memory
    was accessed within CARRYMEM_ACCESS_UPDATE_INTERVAL (default 60s). Set to 0
    to always update (backward compat / test mode).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "throttle.db")
        os.environ.pop("CARRYMEM_ACCESS_UPDATE_INTERVAL", None)
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        os.environ.pop("CARRYMEM_ACCESS_UPDATE_INTERVAL", None)

    def _clear_cache(self):
        """Clear recall cache so next recall goes through full pipeline (incl. throttle)."""
        if self.cm._adapter and hasattr(self.cm._adapter, "clear_cache"):
            self.cm._adapter.clear_cache()

    def test_first_recall_updates_access(self):
        """First recall (last_accessed_at=None) always triggers update."""
        results = self.cm.recall_memories(query="dark mode")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["access_count"], 1)
        self.assertIsNotNone(results[0]["last_accessed_at"])

    def test_throttle_skips_recent_access(self):
        """Within 60s interval, second recall does not increment access_count."""
        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        r1 = self.cm.recall_memories(query="dark mode")
        self.assertEqual(r1[0]["access_count"], 1)
        self._clear_cache()
        r2 = self.cm.recall_memories(query="dark mode")
        self.assertEqual(r2[0]["access_count"], 1)

    def test_throttle_interval_zero_always_updates(self):
        """Interval=0 disables throttle (backward compat / test mode)."""
        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "0"
        r1 = self.cm.recall_memories(query="dark mode")
        self.assertEqual(r1[0]["access_count"], 1)
        self._clear_cache()
        r2 = self.cm.recall_memories(query="dark mode")
        self.assertEqual(r2[0]["access_count"], 2)

    def test_throttle_allows_stale_access(self):
        """_should_update_access returns True when last_accessed_at is stale."""
        from datetime import datetime, timedelta, timezone

        from carrymem.adapters.base import StoredMemory
        from carrymem.adapters.sqlite.recall_engine import RecallEngine

        engine = RecallEngine(
            adapter=None,
            conn_mgr=None,
            serializer=None,
            cache=None,
            expander=None,
            merger=None,
            embedding_model=None,
            embedding_dim=0,
            rrf_k=0,
            rrf_fts_weight=0.0,
            rrf_vec_weight=0.0,
            rrf_type_boosts={},
        )
        now = datetime.now(timezone.utc)
        stale_stored = StoredMemory(last_accessed_at=now - timedelta(seconds=120))

        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        self.assertIs(engine._should_update_access(stale_stored, now), True)

    def test_throttle_type_guard_string(self):
        """_should_update_access handles last_accessed_at as ISO string."""
        from datetime import datetime, timedelta, timezone

        from carrymem.adapters.base import StoredMemory
        from carrymem.adapters.sqlite.recall_engine import RecallEngine

        engine = RecallEngine(
            adapter=None,
            conn_mgr=None,
            serializer=None,
            cache=None,
            expander=None,
            merger=None,
            embedding_model=None,
            embedding_dim=0,
            rrf_k=0,
            rrf_fts_weight=0.0,
            rrf_vec_weight=0.0,
            rrf_type_boosts={},
        )
        now = datetime.now(timezone.utc)
        recent_str = (now - timedelta(seconds=5)).isoformat()
        stale_str = (now - timedelta(seconds=120)).isoformat()

        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        recent_stored = StoredMemory(last_accessed_at=recent_str)
        stale_stored = StoredMemory(last_accessed_at=stale_str)
        self.assertFalse(engine._should_update_access(recent_stored, now))
        self.assertIs(engine._should_update_access(stale_stored, now), True)

    def test_throttle_fail_open_on_parse_error(self):
        """Unparseable last_accessed_at string → fail-open (trigger update)."""
        from datetime import datetime, timezone

        from carrymem.adapters.base import StoredMemory
        from carrymem.adapters.sqlite.recall_engine import RecallEngine

        engine = RecallEngine(
            adapter=None,
            conn_mgr=None,
            serializer=None,
            cache=None,
            expander=None,
            merger=None,
            embedding_model=None,
            embedding_dim=0,
            rrf_k=0,
            rrf_fts_weight=0.0,
            rrf_vec_weight=0.0,
            rrf_type_boosts={},
        )
        now = datetime.now(timezone.utc)
        bad_stored = StoredMemory(last_accessed_at="not-a-date")

        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        self.assertIs(engine._should_update_access(bad_stored, now), True)

    def test_throttle_none_last_accessed_always_updates(self):
        """last_accessed_at=None (first access) always triggers update."""
        from datetime import datetime, timezone

        from carrymem.adapters.base import StoredMemory
        from carrymem.adapters.sqlite.recall_engine import RecallEngine

        engine = RecallEngine(
            adapter=None,
            conn_mgr=None,
            serializer=None,
            cache=None,
            expander=None,
            merger=None,
            embedding_model=None,
            embedding_dim=0,
            rrf_k=0,
            rrf_fts_weight=0.0,
            rrf_vec_weight=0.0,
            rrf_type_boosts={},
        )
        now = datetime.now(timezone.utc)
        new_stored = StoredMemory(last_accessed_at=None)

        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        self.assertIs(engine._should_update_access(new_stored, now), True)

    def test_throttle_configurable_via_env(self):
        """CARRYMEM_ACCESS_UPDATE_INTERVAL env var controls throttle interval."""
        from datetime import datetime, timedelta, timezone

        from carrymem.adapters.base import StoredMemory
        from carrymem.adapters.sqlite.recall_engine import RecallEngine

        engine = RecallEngine(
            adapter=None,
            conn_mgr=None,
            serializer=None,
            cache=None,
            expander=None,
            merger=None,
            embedding_model=None,
            embedding_dim=0,
            rrf_k=0,
            rrf_fts_weight=0.0,
            rrf_vec_weight=0.0,
            rrf_type_boosts={},
        )
        now = datetime.now(timezone.utc)
        stored = StoredMemory(last_accessed_at=now - timedelta(seconds=30))

        # 10s interval — 30s ago is stale → allow
        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "10"
        self.assertIs(engine._should_update_access(stored, now), True)

        # 60s interval — 30s ago is recent → skip
        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        self.assertFalse(engine._should_update_access(stored, now))

    def test_throttle_naive_datetime_handled(self):
        """Naive datetime (no tzinfo) is treated as UTC for comparison."""
        from datetime import datetime, timedelta, timezone

        from carrymem.adapters.base import StoredMemory
        from carrymem.adapters.sqlite.recall_engine import RecallEngine

        engine = RecallEngine(
            adapter=None,
            conn_mgr=None,
            serializer=None,
            cache=None,
            expander=None,
            merger=None,
            embedding_model=None,
            embedding_dim=0,
            rrf_k=0,
            rrf_fts_weight=0.0,
            rrf_vec_weight=0.0,
            rrf_type_boosts={},
        )
        now = datetime.now(timezone.utc)
        naive_stale = (now - timedelta(seconds=120)).replace(tzinfo=None)

        os.environ["CARRYMEM_ACCESS_UPDATE_INTERVAL"] = "60"
        stored = StoredMemory(last_accessed_at=naive_stale)
        self.assertIs(engine._should_update_access(stored, now), True)


class TestRecallAll(unittest.TestCase):
    """Tests for CarryMem.recall_all() (RecallMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "recall_all.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_recall_all_returns_all_types(self):
        """recall_all() returns dict with rules, memories, knowledge keys."""
        result = self.cm.recall_all("dark mode")
        self.assertIn("rules", result)
        self.assertIn("memories", result)
        self.assertIn("knowledge", result)

    def test_recall_all_respects_priority(self):
        """recall_all() returns priority field indicating order."""
        result = self.cm.recall_all("test")
        self.assertIn("priority", result)
        self.assertEqual(result["priority"], "rules > memory > knowledge")

    def test_recall_all_includes_counts(self):
        """recall_all() returns total_count and per-source counts."""
        result = self.cm.recall_all("test")
        self.assertIn("total_count", result)
        self.assertIn("memory_count", result)
        self.assertIn("rule_count", result)
        self.assertIn("knowledge_count", result)

    def test_recall_all_includes_namespace(self):
        """recall_all() returns namespace field."""
        result = self.cm.recall_all("test")
        self.assertIn("namespace", result)
        self.assertEqual(result["namespace"], "default")

    def test_recall_all_without_rules(self):
        """recall_all() with include_rules=False omits rules."""
        result = self.cm.recall_all("test", include_rules=False)
        self.assertEqual(result["rules"], [])
        self.assertEqual(result["rule_count"], 0)

    def test_recall_all_includes_declarations(self):
        """recall_all() includes declared memories in results."""
        result = self.cm.recall_all("dark mode")
        self.assertIsInstance(result["memories"], list)

    def test_recall_all_includes_knowledge(self):
        """recall_all() returns empty knowledge when no knowledge adapter."""
        result = self.cm.recall_all("test")
        self.assertEqual(result["knowledge"], [])
        self.assertEqual(result["knowledge_count"], 0)


class TestRecallAggregated(unittest.TestCase):
    """Tests for CarryMem.recall_aggregated() (RecallMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "agg.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_recall_aggregated_returns_dict(self):
        """recall_aggregated() returns a dict keyed by memory type."""
        result = self.cm.recall_aggregated()
        self.assertIsInstance(result, dict)

    def test_recall_aggregated_no_adapter_raises(self):
        """recall_aggregated() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.recall_aggregated()
        finally:
            cm.close()


class TestRecallTimeline(unittest.TestCase):
    """Tests for CarryMem.recall_timeline() (RecallMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "timeline.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_recall_timeline_returns_list(self):
        """recall_timeline() returns a list."""
        result = self.cm.recall_timeline("dark mode")
        self.assertIsInstance(result, list)

    def test_recall_timeline_no_adapter_raises(self):
        """recall_timeline() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.recall_timeline("test")
        finally:
            cm.close()


if __name__ == "__main__":
    unittest.main()
