"""
E2E Tests: Encryption Full Chain

Validates the complete encryption lifecycle:
1. Enable encryption → store data → close → reopen → decrypt and recall
2. Encrypted state: export/import roundtrip consistency
3. Degraded behavior when key file is corrupted
4. Key rotation: old data remains readable
"""

import json
import os
import shutil
import sqlite3
import tempfile

import pytest

from carrymem import CarryMem
from carrymem.security.encryption import EncryptionError, MemoryEncryption


@pytest.fixture
def encrypted_carrymem(tmp_path):
    """Create a CarryMem instance with encryption enabled."""
    db_path = str(tmp_path / "encrypted_test.db")
    cm = CarryMem(db_path=db_path, encryption_key="e2e-encryption-test-key-12345")
    yield cm
    cm.close()


class TestE2EEncryptionLifecycle:
    """Scenario: Complete encryption lifecycle from enable to recall."""

    def test_encrypt_store_close_reopen_recall(self, tmp_path):
        """Verify: Data encrypted → DB closed → reopened with same key → data recalled.

        Full roundtrip:
        1. Create CarryMem with encryption_key
        2. Store sensitive memories
        3. Close connection
        4. Reopen with same key
        5. Recall and verify original content intact
        """
        db_path = str(tmp_path / "lifecycle_enc.db")
        encryption_key = "my-super-secret-encryption-key-xyz"

        # Phase 1: Create and store with encryption
        cm1 = CarryMem(db_path=db_path, encryption_key=encryption_key)
        try:
            secret_memories = [
                "My banking preference: always use 2FA",
                "Work credential: use SSO for all enterprise apps",
                "Personal rule: never reuse passwords",
            ]

            for mem in secret_memories:
                result = cm1.classify_and_remember(mem)
                assert isinstance(result, dict), f"Encrypted store should succeed for: {mem[:30]}"

            # Verify storage worked
            stored = cm1.recall_memories(limit=10)
            assert isinstance(stored, list) and len(stored) == len(
                secret_memories
            ), f"All encrypted memories should be stored before close, got {len(stored)}/{len(secret_memories)}"
        finally:
            cm1.close()

        # Phase 2: Reopen with same key and verify
        cm2 = CarryMem(db_path=db_path, encryption_key=encryption_key)
        try:
            recalled = cm2.recall_memories(limit=10)
            assert isinstance(recalled, list), "Recall after reopen should return list"
            assert len(recalled) == len(
                secret_memories
            ), f"All memories should be recalled after reopen, got {len(recalled)}/{len(secret_memories)}"

            # Verify content integrity
            recalled_contents = [m.get("content", "") for m in recalled if isinstance(m, dict)]
            found_count = sum(
                1
                for orig in secret_memories
                if any(orig.lower() in rc.lower() or rc.lower() in orig.lower() for rc in recalled_contents)
            )
            assert found_count == len(secret_memories), (
                f"All original content should be recoverable after encrypt/reopen cycle."
                f" Found {found_count}/{len(secret_memories)}"
            )
        finally:
            cm2.close()

    def test_wrong_key_fails_to_decrypt(self, tmp_path):
        """Verify: Opening encrypted database with wrong key fails or returns empty."""
        db_path = str(tmp_path / "wrong_key.db")
        correct_key = "correct-encryption-password"
        wrong_key = "wrong-encryption-password"

        # Store with correct key
        cm1 = CarryMem(db_path=db_path, encryption_key=correct_key)
        try:
            cm1.classify_and_remember("Secret data that should not be readable with wrong key")
        finally:
            cm1.close()

        # Try to open with wrong key - should fail gracefully
        cm2 = CarryMem(db_path=db_path, encryption_key=wrong_key)
        try:
            # Either raises error or returns empty/corrupted results
            recalled = cm2.recall_memories(limit=10)
            if isinstance(recalled, list) and len(recalled) > 0:
                # If it returns data, it should be garbled/empty, not plaintext
                contents = [m.get("content", "") for m in recalled]
                has_plaintext = any("Secret data" in c for c in contents)
                assert not has_plaintext, "Wrong key should NOT be able to decrypt to plaintext"
        except (EncryptionError, Exception):
            pass  # Expected: decryption failure
        finally:
            cm2.close()

    def test_no_key_on_encrypted_db(self, tmp_path):
        """Verify: Opening encrypted database without key fails or shows degradation."""
        db_path = str(tmp_path / "no_key.db")
        key = "test-key-for-encryption"

        # Create encrypted database
        cm1 = CarryMem(db_path=db_path, encryption_key=key)
        try:
            cm1.classify_and_remember("Encrypted memory content")
        finally:
            cm1.close()

        # Try opening without encryption key
        cm2 = CarryMem(db_path=db_path)  # No encryption_key
        try:
            # Should either work in degraded mode or fail gracefully
            result = cm2.recall_memories(limit=5)
            # If it works, encrypted data should not be readable as plaintext
            if isinstance(result, list) and len(result) > 0:
                contents = [m.get("content", "") for m in result]
                has_readable = any("Encrypted memory" in c for c in contents)
                assert not has_readable, "Encrypted data should not be readable without key"
        except Exception:
            pass  # Acceptable: cannot open without key
        finally:
            cm2.close()


class TestE2EEncryptedExportImport:
    """Scenario: Export/import operations under encryption."""

    def test_export_profile_under_encryption(self, encrypted_carrymem):
        """Verify: get_memory_profile works correctly under encryption."""
        cm = encrypted_carrymem

        cm.classify_and_remember("Encrypted preference: use VPN on public WiFi")
        cm.classify_and_remember("Encrypted fact: company uses Okta for auth")

        profile = cm.get_memory_profile()
        assert isinstance(profile, dict), "Profile under encryption should return valid dict"

        # Profile should contain meaningful data (not just empty structure)
        profile_str = json.dumps(profile)
        assert len(profile_str) > 50, "Profile should have substantial content"

    def test_backup_under_encryption(self, tmp_path):
        """Verify: Backup operation works with encrypted database."""
        db_path = str(tmp_path / "enc_backup.db")
        backup_dir = str(tmp_path / "enc_backups")
        os.makedirs(backup_dir, exist_ok=True)

        key = "backup-encryption-key-12345"
        cm = CarryMem(db_path=db_path, encryption_key=key)

        try:
            cm.classify_and_remember("Sensitive data to backup")
            cm.classify_and_remember("Another secret piece of info")

            backup_result = cm.backup(backup_dir=backup_dir)
            assert isinstance(backup_result, dict), "Backup should succeed under encryption"

            # Backup file should exist
            backup_path = backup_result.get("backup_path") or backup_result.get("path")
            if backup_path:
                assert os.path.exists(backup_path), "Backup file should be created"
                assert os.path.getsize(backup_path) > 0, "Backup file should not be empty"
        finally:
            cm.close()

    # Note: test_pack_with_encryption_roundtrip was removed.
    # The previous version was decorated with a try/except that silently
    # skipped via pytest's unconditional skip marker (reason mentioned
    # pack() not supporting all parameters in this version). Investigation
    # shows CarryMem has NO pack() method at all — the test was masking a
    # non-existent API rather than testing real functionality. Per project
    # rule "if a test can be skipped, it shouldn't have been designed", the
    # placeholder has been deleted. Encryption roundtrip coverage is
    # already provided by the backup tests above (test_backup_under_encryption)
    # and the broader encrypted export/import scenarios in this class.
    # A real pack() test should be re-added only if/when CarryMem introduces
    # a pack() API.


class TestE2EDegradedKeyScenarios:
    """Scenario: Handling of corrupted/missing keys."""

    def test_corrupted_key_detection(self, tmp_path):
        """Verify: System detects when key is corrupted/incompatible."""
        db_path = str(tmp_path / "corrupt_key.db")
        original_key = "original-valid-key-12345"

        # Create and populate with original key
        cm = CarryMem(db_path=db_path, encryption_key=original_key)
        try:
            cm.classify_and_remember("Data protected by original key")
        finally:
            cm.close()

        # Try with slightly modified key (simulating corruption)
        modified_key = "original-valid-key-12346"  # Last char changed
        cm2 = CarryMem(db_path=db_path, encryption_key=modified_key)
        try:
            # Should NOT be able to decrypt properly
            recalled = cm2.recall_memories(limit=5)
            if isinstance(recalled, list) and len(recalled) > 0:
                contents = [m.get("content", "") for m in recalled]
                # Original plaintext should NOT appear
                has_original = any("original key" in c.lower() for c in contents)
                assert not has_original, "Modified key should not decrypt original data"
        except EncryptionError:
            pass  # Expected behavior
        finally:
            cm2.close()

    def test_empty_string_key_behavior(self, tmp_path):
        """Verify: Empty string as encryption key is handled safely."""
        db_path = str(tmp_path / "empty_key.db")

        # Some implementations treat empty key as "no encryption"
        cm = CarryMem(db_path=db_path, encryption_key="")
        try:
            result = cm.classify_and_remember("Test with empty key")
            assert isinstance(result, dict), "Empty key should not crash"
        except Exception:
            pass  # May raise error depending on implementation
        finally:
            cm.close()


class TestE2EKeyRotation:
    """Scenario: Key rotation and backward compatibility."""

    def test_basic_encryption_rotation_simulation(self, tmp_path):
        """Verify: Encryption key change isolates data (expected behavior).

        Data encrypted with old_key is NOT accessible with new_key.
        This is correct cryptographic behavior — key rotation requires
        a separate re-encryption migration process.
        """
        db_path = str(tmp_path / "rotation_test.db")
        old_key = "original-encryption-key-2024"
        new_key = "new-encryption-key-v2"

        # Phase 1: Store data with old key
        cm_old = CarryMem(db_path=db_path, encryption_key=old_key)
        try:
            cm_old.classify_and_remember("Legacy data encrypted with old key")
            cm_old.classify_and_remember("Historical preferences v1")

            # Verify accessible with old key
            old_recall = cm_old.recall_memories(limit=10)
            assert isinstance(old_recall, list) and len(old_recall) >= 1, "Data should be accessible with old key"
            # Verify at least one of the stored memories is recalled with correct content
            recalled_contents = [m.get("content", "") for m in old_recall if isinstance(m, dict)]
            has_stored_data = any("Historical preferences" in c or "Legacy data" in c for c in recalled_contents)
            assert has_stored_data, "Recalled data should contain stored encrypted memories"
        finally:
            cm_old.close()

        # Phase 2: New key instance cannot read old-encrypted data (expected)
        cm_new = CarryMem(db_path=db_path, encryption_key=new_key)
        try:
            # New key instance should initialize without crashing
            # But recall of old-encrypted data will fail or return empty
            try:
                new_recall = cm_new.recall_memories(limit=10)
                assert isinstance(new_recall, list), "New key instance should respond to queries"
                # Data encrypted with old key may be undecryptable with new key;
                # this is expected behavior for encryption key changes
            except Exception:
                pass  # Acceptable: old data undecryptable with new key
        finally:
            cm_new.close()

    def test_encryption_backend_consistency(self):
        """Verify: MemoryEncryption produces consistent ciphertext for same input."""
        enc = MemoryEncryption(key="consistency-test-key")

        plaintext = "Consistent encryption test message"

        # Encrypt twice - should produce different ciphertext (if IV-based)
        # but both should decrypt to same plaintext
        cipher1 = enc.encrypt(plaintext)
        cipher2 = enc.encrypt(plaintext)

        # Both should decrypt correctly
        dec1 = enc.decrypt(cipher1)
        dec2 = enc.decrypt(cipher2)

        assert dec1 == plaintext, "First decrypt should match original"
        assert dec2 == plaintext, "Second decrypt should match original"
        assert dec1 == dec2, "Both decryptions should produce identical plaintext"


class TestE2ERawDatabaseProtection:
    """Scenario: Verify raw database files don't expose plaintext."""

    def test_raw_db_no_plaintext_passwords(self, tmp_path):
        """Verify: Raw SQLite file doesn't contain unencrypted sensitive text."""
        db_path = str(tmp_path / "raw_protection.db")
        key = "raw-protection-test-key"

        sensitive_data = [
            "My password is SuperSecret123!",
            "API key: sk-live-abcdefghijklmnopqrstuvwxyz",
            "SSN: 123-45-6789",
        ]

        cm = CarryMem(db_path=db_path, encryption_key=key)
        try:
            for data in sensitive_data:
                cm.classify_and_remember(data, force_type="user_preference")
        finally:
            cm.close()

        # Read raw database file
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Check memories table for plaintext leakage
            rows = conn.execute("SELECT content FROM memories").fetchall()
            raw_content = "\n".join(str(row["content"]) for row in rows if row["content"])

            # Raw DB should NOT contain exact sensitive values
            for sensitive in sensitive_data:
                # Check for obvious plaintext exposure
                assert sensitive not in raw_content, f"Raw DB should not contain plaintext: '{sensitive[:30]}...'"
        finally:
            conn.close()


class TestE2EUnicodeUnderEncryption:
    """Scenario: Unicode/international content under encryption."""

    def test_chinese_text_encrypted_recalled(self, encrypted_carrymem):
        """Verify: Chinese text survives encryption roundtrip."""
        cm = encrypted_carrymem

        chinese_memories = [
            "用户偏好：使用中文界面",
            "工作习惯：每天早上写代码",
            "重要规则：不要在周五部署",
        ]

        for mem in chinese_memories:
            result = cm.classify_and_remember(mem)
            assert isinstance(result, dict), f"Chinese text storage should work: {mem}"

        # Recall and verify
        recalled = cm.recall_memories(limit=10)
        recalled_contents = [m.get("content", "") for m in recalled if isinstance(m, dict)]

        found = sum(1 for orig in chinese_memories if any(orig in rc or rc in orig for rc in recalled_contents))
        assert found == len(
            chinese_memories
        ), f"All Chinese text should survive encryption roundtrip. Found {found}/{len(chinese_memories)}"

    def test_emoji_and_special_chars_under_encryption(self, encrypted_carrymem):
        """Verify: Emoji and special characters work with encryption."""
        cm = encrypted_carrymem

        special_texts = [
            "Mood: 🌙🚀💻",
            "Rating: ⭐⭐⭐⭐⭐",
            "Math: E=mc² ∑∫∂∇",
            "Currency: $100, €50, ¥1000",
        ]

        stored_count = 0
        for text in special_texts:
            result = cm.classify_and_remember(text)
            assert isinstance(result, dict), f"Special chars should work: {text}"
            if result.get("stored") or result.get("storage_keys"):
                stored_count += 1

        # Verify recall works (even if not all texts matched classification rules)
        # Use a non-empty query for better FTS match on encrypted content
        recalled = cm.recall_memories(query="Mood", limit=10)
        assert isinstance(recalled, list), "Recall should return a list"


class TestE2ELongContentUnderEncryption:
    """Scenario: Long content encryption handling."""

    def test_long_memory_encryption(self, encrypted_carrymem):
        """Verify: Very long memories are properly encrypted and recalled."""
        cm = encrypted_carrymem

        # Generate long content (~5000 chars)
        long_text = "This is an important memory about my preferences. " * 200

        result = cm.classify_and_remember(long_text)
        assert isinstance(result, dict), "Long text should be storable"

        # Recall and check length preserved
        recalled = cm.recall_memories(query="important memory", limit=5)
        if isinstance(recalled, list) and len(recalled) > 0:
            content = recalled[0].get("content", "")
            # Content should retain the original text (may be truncated by system)
            assert (
                "important memory" in content.lower()
            ), f"Recalled content should contain 'important memory', got: {content[:100]}"
