"""Unit tests for MaintenanceMixin: check_conflicts, check_quality, consolidate, list_expired."""

import os
import shutil
import tempfile
import unittest

from carrymem import CarryMem
from carrymem.core._lifecycle import StorageNotConfiguredError


class TestCheckConflicts(unittest.TestCase):
    """Tests for CarryMem.check_conflicts() (MaintenanceMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "conflicts.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_conflicts_returns_list(self):
        """check_conflicts() returns a list."""
        self.cm.declare("I prefer dark mode")
        result = self.cm.check_conflicts()
        self.assertIsInstance(result, list)

    def test_check_conflicts_no_adapter_raises(self):
        """check_conflicts() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.check_conflicts()
        finally:
            cm.close()


class TestCheckQuality(unittest.TestCase):
    """Tests for CarryMem.check_quality() (MaintenanceMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "quality.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_quality_returns_list(self):
        """check_quality() returns a list."""
        self.cm.declare("I prefer dark mode")
        result = self.cm.check_quality()
        self.assertIsInstance(result, list)

    def test_check_quality_empty_db(self):
        """check_quality() returns empty list for empty database."""
        result = self.cm.check_quality()
        self.assertEqual(result, [])

    def test_check_quality_with_custom_threshold(self):
        """check_quality() accepts min_score parameter."""
        self.cm.declare("I prefer dark mode")
        result = self.cm.check_quality(min_score=0.9)
        self.assertIsInstance(result, list)

    def test_check_quality_no_adapter_raises(self):
        """check_quality() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.check_quality()
        finally:
            cm.close()


class TestListExpired(unittest.TestCase):
    """Tests for CarryMem.list_expired() (MaintenanceMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "expired.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_expired_returns_list(self):
        """list_expired() returns a list."""
        result = self.cm.list_expired()
        self.assertIsInstance(result, list)

    def test_list_expired_with_no_expired(self):
        """list_expired() returns empty list when no memories have expired."""
        self.cm.declare("I prefer dark mode")
        result = self.cm.list_expired()
        self.assertEqual(result, [])

    def test_list_expired_no_adapter_raises(self):
        """list_expired() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.list_expired()
        finally:
            cm.close()


class TestConsolidate(unittest.TestCase):
    """Tests for CarryMem.consolidate() (MaintenanceMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "consolidate.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_consolidate_dry_run(self):
        """consolidate() with dry_run=True returns report without changes."""
        result = self.cm.consolidate(dry_run=True)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("dry_run", False))

    def test_consolidate_dry_run_false(self):
        """consolidate() with dry_run=False applies changes."""
        result = self.cm.consolidate(dry_run=False)
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("dry_run", True))

    def test_consolidate_no_adapter_raises(self):
        """consolidate() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with self.assertRaises(StorageNotConfiguredError):
                cm.consolidate()
        finally:
            cm.close()


class TestScheduleConsolidation(unittest.TestCase):
    """Tests for CarryMem.schedule_consolidation() and stop_consolidation() (MaintenanceMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "schedule.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.stop_consolidation()
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_schedule_consolidation_starts_timer(self):
        """schedule_consolidation() returns dict with scheduled=True."""
        result = self.cm.schedule_consolidation(interval_hours=1.0, dry_run=True)
        self.assertIs(result["scheduled"], True)
        self.assertEqual(result["interval_hours"], 1.0)

    def test_stop_consolidation(self):
        """stop_consolidation() stops the active timer."""
        self.cm.schedule_consolidation(interval_hours=1.0, dry_run=True)
        result = self.cm.stop_consolidation()
        self.assertIs(result["stopped"], True)

    def test_stop_consolidation_no_active(self):
        """stop_consolidation() returns stopped=False when no timer active."""
        result = self.cm.stop_consolidation()
        self.assertFalse(result["stopped"])

    def test_schedule_consolidation_min_interval(self):
        """schedule_consolidation() enforces minimum interval."""
        result = self.cm.schedule_consolidation(interval_hours=0.001, dry_run=True)
        # Should be clamped to CONSOLIDATION_MIN_INTERVAL_HOURS
        self.assertGreaterEqual(result["interval_hours"], 0.1)


if __name__ == "__main__":
    unittest.main()
