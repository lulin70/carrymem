"""Unit tests for ProfileExportMixin: get_stats, export_profile, import_memories, whoami."""

import json
import os
import shutil
import tempfile
import unittest

from carrymem import CarryMem
from carrymem.core._lifecycle import StorageNotConfiguredError


class TestGetStats(unittest.TestCase):
    """Tests for CarryMem.get_stats() (ProfileExportMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "stats.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_stats_returns_dict(self):
        """get_stats() returns a dictionary."""
        stats = self.cm.get_stats()
        self.assertIsInstance(stats, dict)

    def test_get_stats_includes_total_count(self):
        """get_stats() includes total_count key."""
        stats = self.cm.get_stats()
        self.assertIn("total_count", stats)

    def test_get_stats_after_declare(self):
        """get_stats() reflects memories added via declare."""
        self.cm.declare("I prefer dark mode")
        stats = self.cm.get_stats()
        self.assertGreater(stats["total_count"], 0)


class TestExportProfile(unittest.TestCase):
    """Tests for CarryMem.export_profile() (ProfileExportMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "export.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_profile_returns_dict(self):
        """export_profile() returns a dictionary."""
        result = self.cm.export_profile()
        self.assertIsInstance(result, dict)

    def test_export_profile_includes_preferences(self):
        """export_profile() includes preferences key."""
        result = self.cm.export_profile()
        self.assertIn("preferences", result)

    def test_export_profile_includes_stats(self):
        """export_profile() includes stats section."""
        result = self.cm.export_profile()
        self.assertIn("stats", result)
        self.assertIn("total_memories", result["stats"])

    def test_export_profile_includes_schema_version(self):
        """export_profile() includes schema_version."""
        result = self.cm.export_profile()
        self.assertIn("schema_version", result)

    def test_export_profile_includes_format(self):
        """export_profile() includes format field."""
        result = self.cm.export_profile()
        self.assertEqual(result["format"], "carrymem_identity")

    def test_export_profile_empty_db(self):
        """export_profile() works on empty database."""
        tmpdir2 = tempfile.mkdtemp()
        db_path2 = os.path.join(tmpdir2, "empty.db")
        cm2 = CarryMem(storage="sqlite", db_path=db_path2, auto_backup_interval=0)
        try:
            result = cm2.export_profile()
            self.assertIsInstance(result, dict)
            self.assertIn("schema_version", result)
        finally:
            cm2.close()
            shutil.rmtree(tmpdir2, ignore_errors=True)

    def test_export_profile_to_file(self):
        """export_profile() writes to file when output_path given."""
        output_path = os.path.join(self.tmpdir, "profile.json")
        result = self.cm.export_profile(output_path=output_path)
        self.assertIs(os.path.exists(output_path), True)
        with open(output_path) as f:
            data = json.load(f)
        self.assertIn("schema_version", data)

    def test_export_profile_format_consistency(self):
        """export_profile() returns consistent structure with all expected keys."""
        result = self.cm.export_profile()
        expected_keys = {"schema_version", "format", "exported_at", "identity", "summary", "preferences", "stats"}
        self.assertIs(expected_keys.issubset(set(result.keys())), True)


class TestImportMemories(unittest.TestCase):
    """Tests for CarryMem.import_memories() (ProfileExportMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "import.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_import_profile_restores_preferences(self):
        """import_memories() imports memories from data dict."""
        import_data = {
            "memories": [
                {
                    "type": "user_preference",
                    "content": "I prefer dark mode",
                    "confidence": 0.9,
                    "tier": 2,
                }
            ],
            "source": {"namespace": "test"},
        }
        result = self.cm.import_memories(data=import_data)
        self.assertGreater(result["imported"], 0)

    def test_import_profile_validates_data(self):
        """import_memories() requires either input_path or data."""
        with self.assertRaises(ValueError):
            self.cm.import_memories()

    def test_import_profile_with_conflict_resolution(self):
        """import_memories() supports skip_existing merge strategy."""
        import_data = {
            "memories": [
                {
                    "type": "user_preference",
                    "content": "I prefer dark mode",
                    "confidence": 0.9,
                }
            ],
            "source": {"namespace": "test"},
        }
        result = self.cm.import_memories(data=import_data, merge_strategy="skip_existing")
        self.assertIn("imported", result)

    def test_import_profile_idempotent(self):
        """import_memories() with same data twice uses skip_existing."""
        import_data = {
            "memories": [
                {
                    "type": "user_preference",
                    "content": "I prefer dark mode",
                    "confidence": 0.9,
                    "content_hash": "hash_abc123",
                }
            ],
            "source": {"namespace": "test"},
        }
        result1 = self.cm.import_memories(data=import_data)
        result2 = self.cm.import_memories(data=import_data)
        # Second import should skip existing (same content_hash)
        self.assertIn("skipped", result2)

    def test_import_memories_no_adapter_raises(self):
        """import_memories() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.import_memories(data={"memories": []})
        finally:
            cm.close()


class TestExportMemories(unittest.TestCase):
    """Tests for CarryMem.export_memories() (ProfileExportMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "export_mem.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_export_memories_returns_dict(self):
        """export_memories() returns a result dict."""
        result = self.cm.export_memories()
        self.assertIs(result["exported"], True)
        self.assertEqual(result["format"], "json")

    def test_export_memories_with_namespace(self):
        """export_memories() accepts namespace parameter."""
        result = self.cm.export_memories(namespace="default")
        self.assertIs(result["exported"], True)

    def test_export_memories_to_file(self):
        """export_memories() writes to file when output_path given."""
        output_path = os.path.join(self.tmpdir, "memories.json")
        result = self.cm.export_memories(output_path=output_path)
        self.assertIs(os.path.exists(output_path), True)

    def test_export_memories_markdown_format(self):
        """export_memories() supports markdown format."""
        result = self.cm.export_memories(format="markdown")
        self.assertEqual(result["format"], "markdown")
        self.assertIn("content", result)


class TestWhoami(unittest.TestCase):
    """Tests for CarryMem.whoami() (ProfileExportMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "whoami.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_whoami_new_user(self):
        """whoami() returns new_user identity for empty database."""
        result = self.cm.whoami()
        self.assertEqual(result["identity"], "new_user")

    def test_whoami_known_user(self):
        """whoami() returns known_user identity after storing memories."""
        self.cm.declare("I prefer dark mode")
        result = self.cm.whoami()
        self.assertEqual(result["identity"], "known_user")

    def test_whoami_no_adapter(self):
        """whoami() returns unknown identity without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            result = cm.whoami()
            self.assertEqual(result["identity"], "unknown")
        finally:
            cm.close()


if __name__ == "__main__":
    unittest.main()
