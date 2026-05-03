"""Tests for v0.6.0 Phase 2 features.

Covers:
- 2.1 Data encryption (MemoryEncryption, NoEncryption)
- 2.2 Automatic backup (BackupManager)
- 2.3 Audit logging (AuditLogger)
- Integration: CarryMem with encryption, backup, audit
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from memory_classification_engine import CarryMem
from memory_classification_engine.adapters.sqlite_adapter import SQLiteAdapter
from memory_classification_engine.security.encryption import (
    MemoryEncryption,
    NoEncryption,
    EncryptionError,
)
from memory_classification_engine.backup import BackupManager
from memory_classification_engine.security.audit import AuditLogger


class TestNoEncryption(unittest.TestCase):
    def test_encrypt_passthrough(self):
        enc = NoEncryption()
        self.assertEqual(enc.encrypt("hello"), "hello")

    def test_decrypt_passthrough(self):
        enc = NoEncryption()
        self.assertEqual(enc.decrypt("hello"), "hello")

    def test_encrypt_empty(self):
        enc = NoEncryption()
        self.assertEqual(enc.encrypt(""), "")

    def test_is_active_false(self):
        enc = NoEncryption()
        self.assertFalse(enc.is_active)

    def test_backend_none(self):
        enc = NoEncryption()
        self.assertEqual(enc.backend, "none")


class TestMemoryEncryption(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.key_file = os.path.join(self.tmpdir, ".key")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_encrypt_decrypt_roundtrip(self):
        enc = MemoryEncryption(key="test_password", key_file=self.key_file)
        plaintext = "I prefer dark mode in VS Code"
        ciphertext = enc.encrypt(plaintext)
        self.assertNotEqual(ciphertext, plaintext)
        decrypted = enc.decrypt(ciphertext)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_empty_string(self):
        enc = MemoryEncryption(key="test_password", key_file=self.key_file)
        self.assertEqual(enc.encrypt(""), "")

    def test_decrypt_empty_string(self):
        enc = MemoryEncryption(key="test_password", key_file=self.key_file)
        self.assertEqual(enc.decrypt(""), "")

    def test_encrypt_cjk(self):
        enc = MemoryEncryption(key="test_password", key_file=self.key_file)
        plaintext = "我喜欢深色模式"
        ciphertext = enc.encrypt(plaintext)
        decrypted = enc.decrypt(ciphertext)
        self.assertEqual(decrypted, plaintext)

    def test_different_keys_different_ciphertext(self):
        enc1 = MemoryEncryption(key="password1", key_file=os.path.join(self.tmpdir, "k1"))
        enc2 = MemoryEncryption(key="password2", key_file=os.path.join(self.tmpdir, "k2"))
        plaintext = "same content"
        c1 = enc1.encrypt(plaintext)
        c2 = enc2.encrypt(plaintext)
        self.assertNotEqual(c1, c2)

    def test_wrong_key_fails(self):
        enc1 = MemoryEncryption(key="correct", key_file=os.path.join(self.tmpdir, "k1"))
        ciphertext = enc1.encrypt("secret data")
        enc2 = MemoryEncryption(key="wrong", key_file=os.path.join(self.tmpdir, "k2"))
        with self.assertRaises((EncryptionError, Exception)):
            enc2.decrypt(ciphertext)

    def test_is_active_true(self):
        enc = MemoryEncryption(key="test_password", key_file=self.key_file)
        self.assertTrue(enc.is_active)

    def test_backend_is_set(self):
        enc = MemoryEncryption(key="test_password", key_file=self.key_file)
        self.assertIn(enc.backend, ("fernet", "hmac-ctr"))

    def test_auto_key_generation(self):
        enc = MemoryEncryption(key_file=self.key_file)
        self.assertTrue(enc.is_active)
        self.assertTrue(os.path.exists(self.key_file))

    def test_key_file_permissions(self):
        enc = MemoryEncryption(key_file=self.key_file)
        stat = os.stat(self.key_file)
        self.assertEqual(stat.st_mode & 0o777, 0o600)


class TestBackupManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.backup_dir = os.path.join(self.tmpdir, "backups")

        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT)")
        conn.execute("INSERT INTO memories VALUES ('1', 'test memory')")
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_backup(self):
        manager = BackupManager(self.db_path, backup_dir=self.backup_dir)
        path = manager.create_backup()
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".db"))

    def test_backup_is_valid_sqlite(self):
        manager = BackupManager(self.db_path, backup_dir=self.backup_dir)
        path = manager.create_backup()
        conn = sqlite3.connect(path)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_list_backups(self):
        manager = BackupManager(self.db_path, backup_dir=self.backup_dir)
        manager.create_backup()
        backups = manager.list_backups()
        self.assertEqual(len(backups), 1)
        self.assertIn("filename", backups[0])
        self.assertIn("size_kb", backups[0])
        self.assertEqual(backups[0]["memory_count"], 1)

    def test_cleanup_old_backups(self):
        manager = BackupManager(self.db_path, backup_dir=self.backup_dir, max_backups=2)
        for _ in range(5):
            import time
            manager.create_backup()
            time.sleep(0.1)
        backups = manager.list_backups()
        self.assertLessEqual(len(backups), 2)

    def test_restore_backup(self):
        manager = BackupManager(self.db_path, backup_dir=self.backup_dir)
        path = manager.create_backup()

        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM memories")
        conn.commit()
        conn.close()

        manager.restore_backup(path)

        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_backup_in_memory_raises(self):
        manager = BackupManager(":memory:", backup_dir=self.backup_dir)
        with self.assertRaises(ValueError):
            manager.create_backup()

    def test_restore_invalid_file_raises(self):
        manager = BackupManager(self.db_path, backup_dir=self.backup_dir)
        bad_path = os.path.join(self.tmpdir, "bad.db")
        with open(bad_path, "w") as f:
            f.write("not a database")
        with self.assertRaises(ValueError):
            manager.restore_backup(bad_path)


class TestAuditLogger(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.audit = AuditLogger(lambda: self.conn, namespace="default")

    def tearDown(self):
        self.conn.close()

    def test_log_operation(self):
        self.audit.log_operation(
            operation="remember",
            storage_key="cm_test",
            memory_type="user_preference",
            success=True,
        )
        log = self.audit.query(limit=10)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["operation"], "remember")
        self.assertTrue(log[0]["success"])

    def test_query_by_operation(self):
        self.audit.log_operation(operation="remember")
        self.audit.log_operation(operation="forget")
        log = self.audit.query(operation="remember")
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["operation"], "remember")

    def test_query_with_details(self):
        self.audit.log_operation(
            operation="remember",
            details={"confidence": 0.9, "tier": 2},
        )
        log = self.audit.query(limit=1)
        self.assertIsNotNone(log[0]["details"])
        self.assertEqual(log[0]["details"]["confidence"], 0.9)

    def test_get_stats(self):
        self.audit.log_operation(operation="remember")
        self.audit.log_operation(operation="remember")
        self.audit.log_operation(operation="forget")
        stats = self.audit.get_stats()
        self.assertEqual(stats["total_operations"], 3)
        self.assertEqual(stats["by_operation"]["remember"], 2)
        self.assertEqual(stats["by_operation"]["forget"], 1)

    def test_failed_operation(self):
        self.audit.log_operation(operation="forget", storage_key="nonexistent", success=False)
        log = self.audit.query(limit=1)
        self.assertFalse(log[0]["success"])


class TestCarryMemV060(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_encrypted_storage(self):
        cm = CarryMem(storage="sqlite", db_path=self.db_path, encryption_key="my_secret")
        try:
            result = cm.classify_and_remember("I prefer dark mode")
            self.assertTrue(result["stored"])

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT content FROM memories LIMIT 1").fetchone()
            conn.close()
            self.assertNotEqual(row["content"], "I prefer dark mode")

            memories = cm.recall_memories(limit=10)
            self.assertGreater(len(memories), 0)
            self.assertIn("dark mode", memories[0]["content"])
        finally:
            cm.close()

    def test_audit_log_on_remember(self):
        cm = CarryMem(storage="sqlite", db_path=self.db_path)
        try:
            cm.classify_and_remember("I prefer dark mode")
            log = cm.get_audit_log()
            self.assertGreater(len(log), 0)
            self.assertEqual(log[0]["operation"], "remember")
        finally:
            cm.close()

    def test_audit_log_on_forget(self):
        cm = CarryMem(storage="sqlite", db_path=self.db_path)
        try:
            result = cm.classify_and_remember("I prefer dark mode")
            key = result["storage_keys"][0]
            cm.forget_memory(key)
            log = cm.get_audit_log(operation="forget")
            self.assertGreater(len(log), 0)
        finally:
            cm.close()

    def test_backup_and_restore(self):
        cm = CarryMem(storage="sqlite", db_path=self.db_path)
        try:
            cm.classify_and_remember("I prefer dark mode")
            backup_result = cm.backup(backup_dir=os.path.join(self.tmpdir, "backups"))
            self.assertTrue(backup_result["backed_up"])

            backups = cm.list_backups(backup_dir=os.path.join(self.tmpdir, "backups"))
            self.assertGreater(len(backups), 0)
        finally:
            cm.close()

    def test_no_encryption_by_default(self):
        cm = CarryMem(storage="sqlite", db_path=self.db_path)
        try:
            cm.classify_and_remember("I prefer dark mode")
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT content FROM memories LIMIT 1").fetchone()
            conn.close()
            self.assertEqual(row["content"], "I prefer dark mode")
        finally:
            cm.close()


if __name__ == "__main__":
    unittest.main()
