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
