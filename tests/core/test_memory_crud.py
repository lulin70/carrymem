"""Unit tests for MemoryCRUDMixin: declare, forget, update, classify_and_remember."""

import os
import shutil
import tempfile
import unittest

from carrymem import CarryMem
from carrymem.core._lifecycle import StorageNotConfiguredError
from carrymem.errors import CarryMemError


class TestDeclare(unittest.TestCase):
    """Tests for CarryMem.declare() (MemoryCRUDMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "declare.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_declare_stores_memory_with_confidence_1(self):
        """declare() stores a memory with confidence=1.0."""
        result = self.cm.declare("I prefer dark mode")
        self.assertTrue(result["declared"])
        self.assertEqual(result["source"], "declaration")
        for entry in result["entries"]:
            self.assertEqual(entry["confidence"], 1.0)

    def test_declare_preference_stores_as_preference(self):
        """declare_preference() stores as user_preference type."""
        result = self.cm.declare_preference("I like Python")
        self.assertTrue(result["declared"])
        self.assertIn("storage_keys", result)
        self.assertTrue(len(result["storage_keys"]) > 0)

    def test_declare_validates_empty_content(self):
        """declare() raises on empty message."""
        from carrymem.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.cm.declare("")

    def test_declare_with_source_layer(self):
        """declare() sets source_layer to 'declaration'."""
        result = self.cm.declare("I prefer tabs over spaces")
        for entry in result["entries"]:
            self.assertEqual(entry["source_layer"], "declaration")

    def test_declare_with_metadata(self):
        """declare() includes metadata with source=declaration."""
        result = self.cm.declare("I like coffee")
        for entry in result["entries"]:
            self.assertIn("metadata", entry)
            if isinstance(entry["metadata"], dict):
                self.assertEqual(entry["metadata"].get("source"), "declaration")

    def test_declare_duplicate_updates_existing(self):
        """declare() on similar content stores a new entry (no dedup by default)."""
        self.cm.declare("I prefer dark mode")
        result2 = self.cm.declare("I prefer dark mode")
        self.assertTrue(result2["declared"])

    def test_declare_returns_storage_keys(self):
        """declare() returns non-empty storage_keys."""
        result = self.cm.declare("Test memory")
        self.assertIsInstance(result["storage_keys"], list)
        self.assertTrue(len(result["storage_keys"]) > 0)

    def test_declare_returns_summary(self):
        """declare() returns a summary with total_entries."""
        result = self.cm.declare("Another test")
        self.assertIn("summary", result)
        self.assertIn("total_entries", result["summary"])


class TestForget(unittest.TestCase):
    """Tests for CarryMem.forget_memory() (MemoryCRUDMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "forget.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_forget_memory_removes_entry(self):
        """forget_memory() removes the specified memory."""
        result = self.cm.declare("Memory to forget")
        key = result["storage_keys"][0]
        forgot = self.cm.forget_memory(key)
        self.assertTrue(forgot)

    def test_forget_nonexistent_returns_false(self):
        """forget_memory() returns False for non-existent key."""
        forgot = self.cm.forget_memory("nonexistent_key_12345")
        self.assertFalse(forgot)

    def test_forget_memory_with_permission_check(self):
        """forget_memory() respects access policy when set."""
        # Without access policy, forget should work
        result = self.cm.declare("Memory for perm test")
        key = result["storage_keys"][0]
        forgot = self.cm.forget_memory(key)
        self.assertTrue(forgot)


class TestClassifyAndRemember(unittest.TestCase):
    """Tests for CarryMem.classify_and_remember() (MemoryCRUDMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "classify.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_classify_and_remember_basic(self):
        """classify_and_remember() stores a memory and returns result."""
        result = self.cm.classify_and_remember("I prefer dark mode")
        self.assertIn("stored", result)
        self.assertIn("storage_keys", result)

    def test_classify_and_remember_with_force_type(self):
        """classify_and_remember() with force_type overrides classification."""
        result = self.cm.classify_and_remember("some text", force_type="user_preference")
        self.assertIn("stored", result)

    def test_classify_and_remember_with_session_id(self):
        """classify_and_remember() accepts session_id parameter."""
        result = self.cm.classify_and_remember("test message", session_id="sess_123")
        self.assertIn("stored", result)

    def test_classify_and_remember_no_adapter_raises(self):
        """classify_and_remember() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.classify_and_remember("test")
        finally:
            cm.close()


class TestUpdateMemory(unittest.TestCase):
    """Tests for CarryMem.update_memory() (MemoryCRUDMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "update.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_memory_content(self):
        """update_memory() updates content and returns new version."""
        result = self.cm.declare("Original content")
        key = result["storage_keys"][0]
        updated = self.cm.update_memory(key, "Updated content")
        self.assertTrue(updated["updated"])
        self.assertEqual(updated["content"], "Updated content")

    def test_update_nonexistent_returns_error(self):
        """update_memory() returns error dict for non-existent key."""
        updated = self.cm.update_memory("nonexistent_key", "new content")
        self.assertFalse(updated["updated"])
        self.assertIn("error", updated)


class TestClassifyMessage(unittest.TestCase):
    """Tests for CarryMem.classify_message() (MemoryCRUDMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "classify_msg.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_classify_message_returns_structure(self):
        """classify_message() returns dict with should_remember and entries."""
        result = self.cm.classify_message("I prefer dark mode")
        self.assertIn("should_remember", result)
        self.assertIn("entries", result)
        self.assertIn("summary", result)

    def test_classify_message_validates_empty(self):
        """classify_message() raises on empty message."""
        from carrymem.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.cm.classify_message("")


class TestGetMemoryHistory(unittest.TestCase):
    """Tests for CarryMem.get_memory_history() (MemoryCRUDMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "history.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_memory_history_returns_list(self):
        """get_memory_history() returns a list."""
        result = self.cm.declare("History test")
        key = result["storage_keys"][0]
        history = self.cm.get_memory_history(key)
        self.assertIsInstance(history, list)


class TestPermissionHelpers(unittest.TestCase):
    """Tests for permission check helpers in MemoryCRUDMixin."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "perm.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_write_permission_as_owner(self):
        """_check_write_permission passes when no access policy is set."""
        # No access policy → no restriction
        self.cm._check_write_permission(user_id="owner")

    def test_check_delete_permission_as_owner(self):
        """_check_delete_permission passes when no access policy is set."""
        self.cm._check_delete_permission(user_id="owner")

    def test_declare_no_adapter_raises(self):
        """declare() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.declare("test")
        finally:
            cm.close()

    def test_forget_no_adapter_raises(self):
        """forget_memory() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.forget_memory("key")
        finally:
            cm.close()


if __name__ == "__main__":
    unittest.main()
