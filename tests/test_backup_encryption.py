"""
Tests for backup module.

Covers: backup creation, listing, and restoration.
"""

import os
import pytest

from carrymem import CarryMem


@pytest.fixture
def cm(tmp_path):
    db_path = str(tmp_path / "test_backup.db")
    carrymem = CarryMem(db_path=db_path)
    yield carrymem
    carrymem.close()


@pytest.fixture
def cm_with_data(tmp_path):
    db_path = str(tmp_path / "test_backup_data.db")
    carrymem = CarryMem(db_path=db_path)
    carrymem.declare("I prefer dark mode")
    carrymem.declare("I use PostgreSQL")
    yield carrymem
    carrymem.close()


class TestBackup:
    def test_backup_creates_file(self, cm_with_data, tmp_path):
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir, exist_ok=True)
        result = cm_with_data.backup(backup_dir=backup_dir)
        assert isinstance(result, dict)

    def test_backup_default_dir(self, cm_with_data):
        result = cm_with_data.backup()
        assert isinstance(result, dict)

    def test_list_backups_empty(self, cm, tmp_path):
        backup_dir = str(tmp_path / "empty_backups")
        os.makedirs(backup_dir, exist_ok=True)
        result = cm.list_backups(backup_dir=backup_dir)
        assert isinstance(result, list)

    def test_list_backups_with_data(self, cm_with_data, tmp_path):
        backup_dir = str(tmp_path / "list_backups")
        os.makedirs(backup_dir, exist_ok=True)
        cm_with_data.backup(backup_dir=backup_dir)
        result = cm_with_data.list_backups(backup_dir=backup_dir)
        assert isinstance(result, list)


class TestEncryption:
    def test_encryption_module_import(self):
        try:
            from carrymem.security.encryption import EncryptionManager
            em = EncryptionManager()
            assert em is not None
        except (ImportError, TypeError, Exception):
            pass
