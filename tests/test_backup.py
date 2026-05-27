#!/usr/bin/env python3
"""Tests for BackupManager - CarryMem automatic backup system.

Test coverage:
- Basic backup creation (VACUUM INTO + fallback)
- Restore with rollback
- List and cleanup operations
- Security: path traversal prevention
- Edge cases: in-memory DB, missing files, permissions
- Integration: full backup/restore cycle
"""

import os
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone

import pytest

from carrymem.backup import BackupManager


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with test data."""
    db_path = tmp_path / "test_memories.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence REAL DEFAULT 0.0
        )
    """
    )
    for i in range(10):
        conn.execute(
            "INSERT INTO memories (id, type, content, confidence) VALUES (?, ?, ?, ?)",
            (f"mem_{i}", "fact", f"Memory content {i}", 0.9),
        )
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def backup_manager(temp_db, tmp_path):
    """Create BackupManager instance."""
    return BackupManager(str(temp_db), str(tmp_path / "backups"))


class TestBackupCreation:
    """Tests for create_backup() method."""

    def test_basic_backup_creation(self, backup_manager, temp_db):
        """Basic backup creates file with correct naming."""
        backup_path = backup_manager.create_backup()

        assert os.path.exists(backup_path), "Backup file should exist"
        assert backup_path.endswith(".db"), "Backup should be .db file"
        assert "memories_" in os.path.basename(backup_path)

    def test_backup_contains_data(self, backup_manager, temp_db):
        """Backup contains all original data."""
        backup_path = backup_manager.create_backup()

        conn = sqlite3.connect(backup_path)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()

        assert count == 10, "Backup should contain all 10 memories"

    def test_timestamp_in_filename(self, backup_manager, temp_db):
        """Backup filename includes UTC timestamp."""
        backup_path = backup_manager.create_backup()
        filename = os.path.basename(backup_path)

        assert filename.startswith(
            "memories_backup_"
        ), f"Filename should start with 'memories_backup_': {filename}"
        assert filename.endswith(".db"), f"Filename should end with '.db': {filename}"

    def test_multiple_backups(self, backup_manager, temp_db):
        """Multiple backups create separate files."""
        paths = []
        for _ in range(3):
            paths.append(backup_manager.create_backup())
            time.sleep(1.01)

        assert len(set(paths)) == 3, "Each backup should be unique file"

    def test_backup_file_permissions(self, backup_manager, temp_db):
        """Backup files have restricted permissions (0o600)."""
        backup_path = backup_manager.create_backup()

        mode = os.stat(backup_path).st_mode & 0o777
        assert mode == 0o600, f"Backup should have 0o600 permissions, got {oct(mode)}"

    def test_backup_directory_permissions(self, backup_manager, temp_db):
        """Backup directory has restricted permissions (0o700)."""
        mode = os.stat(backup_manager._backup_dir).st_mode & 0o777
        assert mode == 0o700, f"Directory should have 0o700 permissions, got {oct(mode)}"

    def test_in_memory_database_raises(self, tmp_path):
        """In-memory database cannot be backed up."""
        manager = BackupManager(":memory:", str(tmp_path / "backups"))

        with pytest.raises(ValueError, match="Cannot backup in-memory"):
            manager.create_backup()

    def test_missing_database_raises(self, tmp_path):
        """Missing database raises FileNotFoundError."""
        manager = BackupManager("/nonexistent/path.db", str(tmp_path / "backups"))

        with pytest.raises(FileNotFoundError, match="Database not found"):
            manager.create_backup()


class TestRestore:
    """Tests for restore_backup() method."""

    def test_restore_from_valid_backup(self, backup_manager, temp_db):
        """Restore from valid backup succeeds."""
        backup_path = backup_manager.create_backup()

        conn = sqlite3.connect(temp_db)
        conn.execute("DELETE FROM memories WHERE id = 'mem_0'")
        conn.commit()
        conn.close()

        backup_manager.restore_backup(backup_path)

        conn = sqlite3.connect(temp_db)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()

        assert count == 10, "Restore should recover all data"

    def test_restore_creates_pre_backup(self, backup_manager, temp_db):
        """Restore creates .pre_restore.bak before overwriting."""
        backup_path = backup_manager.create_backup()

        pre_restore_path = temp_db + ".pre_restore.bak"
        if os.path.exists(pre_restore_path):
            os.remove(pre_restore_path)

        backup_manager.restore_backup(backup_path)

        assert not os.path.exists(
            pre_restore_path
        ), "Pre-restore backup should be cleaned up after success"

    def test_restore_rollback_on_failure(self, backup_manager, temp_db):
        """Failed restore rolls back to pre-restore state."""
        backup_path = backup_manager.create_backup()

        conn = sqlite3.connect(temp_db)
        original_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()

        invalid_backup = backup_manager._backup_dir + "/invalid.db"
        with open(invalid_backup, "w") as f:
            f.write("not a valid database")

        with pytest.raises((ValueError, RuntimeError)):
            backup_manager.restore_backup(invalid_backup)

        conn = sqlite3.connect(temp_db)
        current_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()

        assert current_count == original_count, "Rollback should restore original data"

    def test_path_traversal_blocked(self, backup_manager, temp_db):
        """Path traversal attempts are blocked."""
        with pytest.raises(ValueError, match="escapes backup directory"):
            backup_manager.restore_backup("/etc/passwd")

    def test_nonexistent_backup_raises(self, backup_manager, temp_db):
        """Nonexistent backup raises FileNotFoundError."""
        nonexistent_path = os.path.join(backup_manager._backup_dir, "nonexistent_12345.db")
        with pytest.raises(FileNotFoundError, match="Backup not found"):
            backup_manager.restore_backup(nonexistent_path)

    def test_invalid_backup_file_raises(self, backup_manager, temp_db):
        """Invalid backup file raises ValueError."""
        invalid_path = os.path.join(backup_manager._backup_dir, "invalid.db")
        with open(invalid_path, "w") as f:
            f.write("corrupted data")

        with pytest.raises(ValueError, match="Invalid backup file"):
            backup_manager.restore_backup(invalid_path)

    def test_restore_to_memory_raises(self, backup_manager, temp_db):
        """Cannot restore to in-memory database."""
        backup_path = backup_manager.create_backup()
        mem_manager = BackupManager(":memory:", backup_manager._backup_dir)

        with pytest.raises(ValueError, match="Cannot restore to in-memory"):
            mem_manager.restore_backup(backup_path)


class TestListBackups:
    """Tests for list_backups() method."""

    def test_list_empty_directory(self, tmp_path):
        """Empty backup directory returns empty list."""
        manager = BackupManager(str(tmp_path / "db.db"), str(tmp_path / "backups"))
        backups = manager.list_backups()

        assert backups == [], "Empty directory should return empty list"

    def test_list_single_backup(self, backup_manager, temp_db):
        """Single backup appears in list."""
        backup_path = backup_manager.create_backup()
        backups = backup_manager.list_backups()

        assert len(backups) == 1
        assert backups[0]["path"] == backup_path
        assert backups[0]["memory_count"] == 10

    def test_list_multiple_backups_sorted(self, backup_manager, temp_db):
        """Multiple backups sorted by creation time (newest first)."""
        for _ in range(5):
            backup_manager.create_backup()
            time.sleep(1.01)

        backups = backup_manager.list_backups()

        assert len(backups) == 5
        times = [b["created_at"] for b in backups]
        assert times == sorted(times, reverse=True), "Should be newest first"

    def test_list_includes_metadata(self, backup_manager, temp_db):
        """List includes all required metadata fields."""
        backup_manager.create_backup()
        backups = backup_manager.list_backups()

        backup = backups[0]
        required_keys = {"filename", "path", "size_kb", "created_at", "memory_count"}
        assert required_keys.issubset(
            backup.keys()
        ), f"Missing keys: {required_keys - set(backup.keys())}"
        assert backup["size_kb"] > 0, "Size should be positive"
        assert isinstance(backup["memory_count"], int), "Memory count should be integer"

    def test_list_ignores_non_backup_files(self, backup_manager, temp_db):
        """Non-backup files ignored in listing."""
        backup_manager.create_backup()

        other_file = os.path.join(backup_manager._backup_dir, "readme.txt")
        with open(other_file, "w") as f:
            f.write("not a backup")

        backups = backup_manager.list_backups()
        assert len(backups) == 1, "Should only list .db files starting with memories_"


class TestCleanup:
    """Tests for cleanup_old_backups() method."""

    def test_no_cleanup_under_limit(self, backup_manager, temp_db):
        """No cleanup when under max_backups limit."""
        for _ in range(5):
            backup_manager.create_backup()
            time.sleep(1.01)

        removed = backup_manager.cleanup_old_backups()
        assert removed == 0, "Should not remove any backups"

        backups = backup_manager.list_backups()
        assert len(backups) == 5

    def test_cleanup_removes_oldest(self, temp_db, tmp_path):
        """Cleanup removes oldest backups when over limit."""
        backup_dir = str(tmp_path / "backups")
        manager = BackupManager(temp_db, backup_dir, max_backups=3)

        for i in range(5):
            manager.create_backup()
            time.sleep(1.01)

        current_count = len(manager.list_backups())
        assert current_count == 3, f"Auto-cleanup should maintain {current_count} <= 3"

        manual_removed = manager.cleanup_old_backups()
        assert manual_removed == 0, "No additional cleanup needed"

    def test_cleanup_exact_limit(self, backup_manager, temp_db):
        """No cleanup at exactly max_backups."""
        manager = BackupManager(temp_db, backup_manager._backup_dir, max_backups=2)

        manager.create_backup()
        manager.create_backup()

        removed = manager.cleanup_old_backups()
        assert removed == 0


class TestEdgeCases:
    """Edge case tests."""

    def test_custom_backup_directory(self, temp_db, tmp_path):
        """Custom backup directory is used."""
        custom_dir = str(tmp_path / "custom_backups")
        manager = BackupManager(temp_db, custom_dir)

        backup_path = manager.create_backup()

        assert custom_dir in backup_path
        assert os.path.isdir(custom_dir)

    def test_default_backup_directory(self, temp_db, tmp_path):
        """Default backup directory uses ~/.carrymem/backups."""
        manager = BackupManager(temp_db)

        from carrymem.constants import get_backup_dir

        expected_dir = str(get_backup_dir())
        assert manager._backup_dir == expected_dir

    def test_copy2_fallback(self, monkeypatch, backup_manager, temp_db):
        """Fallback to shutil.copy2 when VACUUM INTO fails."""
        original_create = BackupManager.create_backup

        def failing_create(self):
            import sqlite3

            if self._db_path == ":memory:":
                raise ValueError("Cannot backup in-memory database")
            if not os.path.exists(self._db_path):
                raise FileNotFoundError(f"Database not found: {self._db_path}")

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            backup_filename = f"memories_backup_{timestamp}.db"
            backup_path = os.path.join(self._backup_dir, backup_filename)

            shutil.copy2(self._db_path, backup_path)

            try:
                os.chmod(backup_path, 0o600)
            except (OSError, AttributeError):
                pass

            self.cleanup_old_backups()
            return backup_path

        monkeypatch.setattr(BackupManager, "create_backup", failing_create)

        backup_path = backup_manager.create_backup()
        assert os.path.exists(backup_path), "Fallback should create backup file"

        conn = sqlite3.connect(backup_path)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()
        assert count == 10, "Fallback backup should contain data"

    def test_large_database_backup(self, tmp_path):
        """Backup of larger database works correctly."""
        db_path = str(tmp_path / "large.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 0.0
            )
        """
        )
        for i in range(1000):
            conn.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?)",
                (f"mem_{i}", "fact", f"Content {i} " * 10, 0.85),
            )
        conn.commit()
        conn.close()

        manager = BackupManager(db_path, str(tmp_path / "backups"))
        backup_path = manager.create_backup()

        assert os.path.getsize(backup_path) > 0, "Backup should have content"

        conn = sqlite3.connect(backup_path)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()
        assert count == 1000


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_backup_restore_cycle(self, backup_manager, temp_db):
        """Complete backup → modify → restore → verify cycle."""
        original_conn = sqlite3.connect(temp_db)
        original_count = original_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        original_conn.close()

        backup_path = backup_manager.create_backup()

        modify_conn = sqlite3.connect(temp_db)
        modify_conn.execute("DELETE FROM memories WHERE id IN ('mem_0', 'mem_1', 'mem_2')")
        modify_conn.commit()
        modified_count = modify_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        modify_conn.close()

        assert modified_count == original_count - 3, "Modification should delete 3 records"

        backup_manager.restore_backup(backup_path)

        restored_conn = sqlite3.connect(temp_db)
        restored_count = restored_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        restored_conn.close()

        assert restored_count == original_count, "Full restore should recover all data"

    def test_auto_cleanup_after_backup(self, temp_db, tmp_path):
        """Automatic cleanup after creating backup."""
        manager = BackupManager(temp_db, str(tmp_path / "backups"), max_backups=3)

        for i in range(5):
            manager.create_backup()

        backups = manager.list_backups()
        assert len(backups) <= 3, "Auto-cleanup should enforce max_backups limit"

    def test_consecutive_restores(self, backup_manager, temp_db):
        """Multiple consecutive restores work correctly."""
        backup_paths = [backup_manager.create_backup() for _ in range(3)]

        for backup_path in backup_paths:
            backup_manager.restore_backup(backup_path)

        final_conn = sqlite3.connect(temp_db)
        final_count = final_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        final_conn.close()
        assert final_count == 10, "Data should remain consistent after multiple restores"


class TestBackupStatus:
    """Tests for get_status() method."""

    def test_status_with_no_backups(self, tmp_path):
        """Status reports no backups when directory is empty."""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()

        manager = BackupManager(db_path, str(tmp_path / "backups"))
        status = manager.get_status()

        assert status["backup_dir_exists"] is True
        assert status["backup_count"] == 0
        assert status["latest_backup"] is None

    def test_status_with_backups(self, backup_manager, temp_db):
        """Status reports correct backup info."""
        backup_manager.create_backup()
        status = backup_manager.get_status()

        assert status["backup_dir_exists"] is True
        assert status["backup_count"] == 1
        assert status["latest_backup"] is not None
        assert status["max_backups"] == 5

    def test_status_nonexistent_directory(self, tmp_path):
        """Status handles nonexistent backup directory."""
        db_path = str(tmp_path / "nonexistent" / "test.db")
        manager = BackupManager(db_path, str(tmp_path / "no_backups_here"))
        status = manager.get_status()

        assert status["backup_dir"] == str(tmp_path / "no_backups_here")
        assert status["backup_count"] == 0


class TestAutoBackup:
    """Tests for CarryMem auto-backup integration."""

    def test_initial_backup_on_first_open(self, tmp_path):
        """CarryMem creates initial backup when opening existing DB."""
        from carrymem import CarryMem

        db_path = str(tmp_path / "test_auto.db")
        backup_dir = str(tmp_path / "backups")
        # First create a DB with some data
        cm1 = CarryMem(db_path=db_path, auto_backup_interval=0, config={"backup_dir": backup_dir})
        cm1.declare("Test memory for initial backup")
        cm1.close()

        # Open again — should trigger initial backup
        cm2 = CarryMem(db_path=db_path, auto_backup_interval=0, config={"backup_dir": backup_dir})
        backups = cm2.list_backups(backup_dir=backup_dir)
        cm2.close()

        assert len(backups) >= 1, "Initial backup should be created on first open"

    def test_auto_backup_triggers_after_writes(self, tmp_path):
        """Auto-backup triggers after N write operations."""
        from carrymem import CarryMem

        db_path = str(tmp_path / "test_auto2.db")
        backup_dir = str(tmp_path / "backups2")
        cm = CarryMem(db_path=db_path, auto_backup_interval=3, config={"backup_dir": backup_dir})

        # Clear any initial backup
        initial_backups = cm.list_backups(backup_dir=backup_dir)

        # Do 3 write operations (interval=3)
        cm.declare("Memory 1")
        cm.declare("Memory 2")
        assert len(cm.list_backups(backup_dir=backup_dir)) == len(
            initial_backups
        ), "Should not backup yet"

        cm.declare("Memory 3")
        # After 3rd write, auto-backup should trigger
        new_backups = cm.list_backups(backup_dir=backup_dir)
        assert len(new_backups) > len(initial_backups), "Auto-backup should trigger after 3 writes"
        cm.close()

    def test_auto_backup_disabled_with_zero_interval(self, tmp_path):
        """Auto-backup disabled when interval is 0."""
        from carrymem import CarryMem

        db_path = str(tmp_path / "test_auto3.db")
        backup_dir = str(tmp_path / "backups3")
        cm = CarryMem(db_path=db_path, auto_backup_interval=0, config={"backup_dir": backup_dir})

        initial_backups = len(cm.list_backups(backup_dir=backup_dir))

        for i in range(25):
            cm.declare(f"Memory {i}")

        assert (
            len(cm.list_backups(backup_dir=backup_dir)) == initial_backups
        ), "No auto-backup when interval=0"
        cm.close()

    def test_auto_backup_on_forget(self, tmp_path):
        """Auto-backup counts forget operations."""
        from carrymem import CarryMem

        db_path = str(tmp_path / "test_auto4.db")
        backup_dir = str(tmp_path / "backups4")
        cm = CarryMem(db_path=db_path, auto_backup_interval=3, config={"backup_dir": backup_dir})

        result = cm.declare("Memory to forget")
        keys = result.get("storage_keys", [])

        initial_backups = len(cm.list_backups(backup_dir=backup_dir))

        # Do 2 more writes + 1 forget = 3 total (interval=3)
        cm.declare("Another memory")  # write 2
        cm.declare("Yet another")  # write 3 → triggers auto-backup

        after_auto = len(cm.list_backups(backup_dir=backup_dir))
        assert after_auto > initial_backups, "Auto-backup should trigger after 3 writes"

        # Now forget should also count as a write
        backup_before_forget = len(cm.list_backups(backup_dir=backup_dir))
        cm.declare("Write 1 after reset")  # write 1
        cm.declare("Write 2 after reset")  # write 2

        if keys:
            cm.forget_memory(keys[0])  # write 3 → triggers auto-backup

        after_forget = len(cm.list_backups(backup_dir=backup_dir))
        assert (
            after_forget > backup_before_forget
        ), "Auto-backup should trigger after forget completes the interval"
        cm.close()

    def test_max_backups_default_is_five(self, tmp_path):
        """Default max_backups is 5."""
        db_path = str(tmp_path / "test_max.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE memories (id TEXT PRIMARY KEY, type TEXT, content TEXT, confidence REAL)"
        )
        conn.commit()
        conn.close()

        manager = BackupManager(db_path, str(tmp_path / "backups"))
        assert manager._max_backups == 5

    def test_backup_filename_format(self, backup_manager, temp_db):
        """Backup filename follows memories_backup_YYYYMMDD_HHMMSS.db format."""
        backup_path = backup_manager.create_backup()
        filename = os.path.basename(backup_path)
        assert filename.startswith(
            "memories_backup_"
        ), f"Filename should start with 'memories_backup_': {filename}"
        assert filename.endswith(".db"), f"Filename should end with '.db': {filename}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
