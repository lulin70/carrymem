"""Unit tests for LifecycleMixin: __init__, close, context manager, properties."""

import os
import shutil
import tempfile
import unittest

from carrymem import CarryMem
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.core._lifecycle import StorageNotConfiguredError, _validate_file_path
from carrymem.errors import CarryMemError


class TestLifecycleInit(unittest.TestCase):
    """Tests for CarryMem.__init__ (LifecycleMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_adapter_with_sqlite(self):
        """Init with storage='sqlite' creates a SQLiteAdapter."""
        db_path = os.path.join(self.tmpdir, "test.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        try:
            self.assertIsInstance(cm.adapter, SQLiteAdapter)
        finally:
            cm.close()

    def test_init_creates_adapter_with_json(self):
        """Init with storage='json' loads the JSON adapter via loader."""
        cm = CarryMem(storage="json", auto_backup_interval=0)
        try:
            self.assertIsNotNone(cm.adapter)
        finally:
            cm.close()

    def test_init_raises_on_unsupported_storage_type(self):
        """Init with an unknown storage string raises CarryMemError."""
        with self.assertRaises(CarryMemError):
            CarryMem(storage="nonexistent_adapter_xyz", auto_backup_interval=0)

    def test_init_with_custom_namespace(self):
        """Init with a custom namespace sets the namespace property."""
        db_path = os.path.join(self.tmpdir, "ns.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, namespace="my_ns", auto_backup_interval=0)
        try:
            self.assertEqual(cm.namespace, "my_ns")
        finally:
            cm.close()

    def test_init_with_encryption_enabled(self):
        """Init with encryption_key creates adapter without error."""
        db_path = os.path.join(self.tmpdir, "enc.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, encryption_key="test-key-12345678", auto_backup_interval=0)
        try:
            self.assertIsInstance(cm.adapter, SQLiteAdapter)
        finally:
            cm.close()

    def test_init_with_db_path_validation(self):
        """Init validates db_path for path traversal."""
        with self.assertRaises(ValueError):
            CarryMem(storage="sqlite", db_path="/tmp/../etc/passwd", auto_backup_interval=0)

    def test_init_rejects_path_traversal(self):
        """_validate_file_path rejects '..' in path segments."""
        with self.assertRaises(ValueError):
            _validate_file_path("/some/../etc/passwd")

    def test_init_with_none_storage(self):
        """Init with storage=None sets adapter to None (pure classification mode)."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            self.assertIsNone(cm.adapter)
        finally:
            cm.close()

    def test_init_with_custom_adapter_instance(self):
        """Init with a StorageAdapter instance uses it directly."""
        db_path = os.path.join(self.tmpdir, "custom.db")
        adapter = SQLiteAdapter(db_path=db_path)
        cm = CarryMem(storage=adapter, auto_backup_interval=0)
        try:
            self.assertIs(cm.adapter, adapter)
        finally:
            cm.close()


class TestRuleEngineInitFailure(unittest.TestCase):
    """Tests for TD-002: rule_engine lazy init failure must log warning, not silently pass."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rule_engine_init_failure_logs_warning(self):
        """When rule_engine lazy init fails, a warning is logged (TD-002)."""
        from unittest.mock import patch

        db_path = os.path.join(self.tmpdir, "rule_fail.db")
        with patch("carrymem.rules.RuleEngine", side_effect=RuntimeError("simulated FTS vtable failure")):
            with self.assertLogs("carrymem.core._lifecycle", level="WARNING") as log_ctx:
                cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
                try:
                    # Warning must be emitted during __init__
                    self.assertTrue(
                        any("Rule engine lazy init failed" in msg for msg in log_ctx.output),
                        f"Expected warning not found in logs: {log_ctx.output}",
                    )
                finally:
                    cm.close()

    def test_rule_engine_init_failure_does_not_block_startup(self):
        """rule_engine init failure must not propagate (behavior preserved)."""
        from unittest.mock import patch

        db_path = os.path.join(self.tmpdir, "rule_fail2.db")
        with patch("carrymem.rules.RuleEngine", side_effect=RuntimeError("simulated failure")):
            # Should not raise — failure is caught and logged
            cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
            cm.close()


class TestLifecycleClose(unittest.TestCase):
    """Tests for CarryMem.close() (LifecycleMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_close_cleans_up_resources(self):
        """close() sets rule_engine to None."""
        db_path = os.path.join(self.tmpdir, "close.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        _ = cm.rule_engine  # force lazy init
        cm.close()
        self.assertIsNone(cm._rule_engine)

    def test_close_idempotent(self):
        """Calling close() twice does not raise."""
        db_path = os.path.join(self.tmpdir, "idem.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        cm.close()
        cm.close()  # second close should not raise

    def test_double_close_no_error(self):
        """Double close on a None-storage instance is safe."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        cm.close()
        cm.close()


class TestLifecycleContextManager(unittest.TestCase):
    """Tests for CarryMem context manager (LifecycleMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_context_manager_enter_returns_self(self):
        """__enter__ returns the CarryMem instance."""
        db_path = os.path.join(self.tmpdir, "ctx.db")
        with CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0) as cm:
            self.assertIsInstance(cm, CarryMem)

    def test_context_manager_exit_calls_close(self):
        """__exit__ calls close() and cleans up rule_engine."""
        db_path = os.path.join(self.tmpdir, "ctx2.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        _ = cm.rule_engine
        cm.__exit__(None, None, None)
        self.assertIsNone(cm._rule_engine)


class TestLifecycleProperties(unittest.TestCase):
    """Tests for CarryMem properties (LifecycleMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_namespace_property(self):
        """namespace property returns the configured namespace."""
        cm = CarryMem(storage=None, namespace="test_ns", auto_backup_interval=0)
        try:
            self.assertEqual(cm.namespace, "test_ns")
        finally:
            cm.close()

    def test_engine_property(self):
        """engine property returns the classification engine."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            from carrymem.engine import MemoryClassificationEngine

            self.assertIsInstance(cm.engine, MemoryClassificationEngine)
        finally:
            cm.close()

    def test_adapter_property(self):
        """adapter property returns the storage adapter."""
        db_path = os.path.join(self.tmpdir, "prop.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        try:
            self.assertIsNotNone(cm.adapter)
        finally:
            cm.close()

    def test_storage_property_same_as_adapter(self):
        """storage property is an alias for adapter."""
        db_path = os.path.join(self.tmpdir, "storage.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        try:
            self.assertIs(cm.storage, cm.adapter)
        finally:
            cm.close()

    def test_knowledge_adapter_property(self):
        """knowledge_adapter property returns None when not configured."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            self.assertIsNone(cm.knowledge_adapter)
        finally:
            cm.close()


class TestGetStatsReturnsStructure(unittest.TestCase):
    """Tests for get_stats returning expected structure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_stats_returns_structure(self):
        """get_stats() returns a dict with expected keys."""
        db_path = os.path.join(self.tmpdir, "stats.db")
        cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        try:
            stats = cm.get_stats()
            self.assertIsInstance(stats, dict)
            self.assertIn("total_count", stats)
        finally:
            cm.close()

    def test_get_stats_no_adapter(self):
        """get_stats() with no adapter returns minimal dict."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            stats = cm.get_stats()
            self.assertIsInstance(stats, dict)
            self.assertEqual(stats.get("total_count", 0), 0)
        finally:
            cm.close()


if __name__ == "__main__":
    unittest.main()
