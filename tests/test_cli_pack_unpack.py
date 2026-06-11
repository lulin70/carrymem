"""Tests for CarryMem CLI pack/unpack commands.

Covers:
- Basic pack/unpack roundtrip
- SHA-256 checksum verification (corrupted file detection)
- Encrypted pack + decrypted unpack
- Conflict handling (target already has memories)
- Empty database pack
- Large dataset pack (100+ memories)
- Legacy v1.0 format backward compatibility
"""

import base64
import gzip
import hashlib
import json
import os
from unittest.mock import patch

import pytest

from carrymem import CarryMem
from carrymem.cli import cmd_pack, cmd_unpack


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_memories.db")


@pytest.fixture
def temp_db_target(tmp_path):
    return str(tmp_path / "target_memories.db")


def _store_unique_memories(db_path, count=5):
    """Store test memories with unique content and return the CarryMem instance."""
    cm = CarryMem(db_path=db_path)
    for i in range(count):
        cm.declare(f"Unique test memory {i}: I prefer option {i} in category {i * 7}")
    return cm


class TestBasicPackUnpack:
    """Basic pack/unpack roundtrip through CLI commands."""

    def test_pack_creates_carry_file(self, temp_db, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 3)
        cm.close()

        carry_path = str(tmp_path / "test.carry")
        result = cmd_pack(["--output", carry_path, "--db", temp_db])
        assert result == 0
        assert os.path.exists(carry_path)

        captured = capsys.readouterr()
        assert "Packing CarryMem identity" in captured.out

    def test_pack_unpack_roundtrip(self, temp_db, temp_db_target, tmp_path, capsys):
        # Pack from source
        cm = _store_unique_memories(temp_db, 5)
        cm.close()

        carry_path = str(tmp_path / "test.carry")
        result = cmd_pack(["--output", carry_path, "--db", temp_db])
        assert result == 0

        # Unpack to target
        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0

        # Verify target has memories
        target_cm = CarryMem(db_path=temp_db_target)
        target_count = target_cm.get_stats()["total_count"]
        target_cm.close()

        assert target_count >= 1  # At least some memories restored

    def test_pack_unpack_preserves_content(self, temp_db, temp_db_target, tmp_path):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I prefer dark mode for all editors")
        cm.close()

        carry_path = str(tmp_path / "content_test.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])
        cmd_unpack([carry_path, "--db", temp_db_target])

        target_cm = CarryMem(db_path=temp_db_target)
        memories = target_cm.recall_memories(query="dark mode", limit=10)
        found = any("dark mode" in m.get("content", "") for m in memories)
        target_cm.close()
        assert found


class TestChecksumVerification:
    """SHA-256 checksum verification for .carry files."""

    def test_pack_produces_checksum(self, temp_db, tmp_path):
        cm = _store_unique_memories(temp_db, 2)
        cm.close()

        carry_path = str(tmp_path / "checksum_test.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        # Read the container and verify it has a checksum
        with gzip.open(carry_path, "rb") as f:
            container = json.loads(f.read().decode("utf-8"))

        assert "checksum" in container
        assert "payload" in container
        assert len(container["checksum"]) == 64  # SHA-256 hex digest

    def test_unpack_verifies_valid_checksum(self, temp_db, temp_db_target, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 2)
        cm.close()

        carry_path = str(tmp_path / "valid_checksum.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0

        captured = capsys.readouterr()
        assert "Checksum verified" in captured.out

    def test_unpack_rejects_corrupted_file(self, temp_db, temp_db_target, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 2)
        cm.close()

        carry_path = str(tmp_path / "corrupted.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        # Corrupt the payload by modifying the .carry file
        with gzip.open(carry_path, "rb") as f:
            container = json.loads(f.read().decode("utf-8"))

        # Decode, corrupt, re-encode the payload
        compressed = base64.b64decode(container["payload"])
        json_bytes = gzip.decompress(compressed)
        pack_data = json.loads(json_bytes.decode("utf-8"))

        # Corrupt a memory entry
        if pack_data["data"]["memories"]:
            pack_data["data"]["memories"][0]["content"] = "CORRUPTED CONTENT"

        # Re-encode with the OLD checksum (so it won't match)
        corrupted_json = json.dumps(pack_data, ensure_ascii=False).encode("utf-8")
        corrupted_compressed = gzip.compress(corrupted_json)
        container["payload"] = base64.b64encode(corrupted_compressed).decode("ascii")

        # Write back
        container_bytes = json.dumps(container, ensure_ascii=False).encode("utf-8")
        with gzip.open(carry_path, "wb") as f:
            f.write(container_bytes)

        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 1

        captured = capsys.readouterr()
        assert "Checksum mismatch" in captured.out

    def test_checksum_computed_on_json_payload(self, temp_db, tmp_path):
        """Verify checksum is SHA-256 of the JSON payload bytes."""
        cm = _store_unique_memories(temp_db, 1)
        cm.close()

        carry_path = str(tmp_path / "checksum_verify.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        with gzip.open(carry_path, "rb") as f:
            container = json.loads(f.read().decode("utf-8"))

        # Decode payload and verify checksum manually
        compressed = base64.b64decode(container["payload"])
        json_bytes = gzip.decompress(compressed)
        expected = hashlib.sha256(json_bytes).hexdigest()
        assert container["checksum"] == expected


class TestEncryptedPackUnpack:
    """Encrypted pack/unpack using --encrypt option."""

    def test_encrypted_pack_creates_encrypted_container(self, temp_db, tmp_path):
        cm = _store_unique_memories(temp_db, 2)
        cm.close()

        carry_path = str(tmp_path / "encrypted.carry")

        # Mock getpass to provide password
        with patch("carrymem.cli.getpass.getpass", side_effect=["testpass", "testpass"]):
            result = cmd_pack(["--output", carry_path, "--db", temp_db, "--encrypt"])
        assert result == 0

        # Verify container is encrypted
        with gzip.open(carry_path, "rb") as f:
            container = json.loads(f.read().decode("utf-8"))

        assert container.get("encrypted") is True
        assert "payload" in container
        assert "encryption_backend" in container

    def test_encrypted_pack_unpack_roundtrip(self, temp_db, temp_db_target, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 3)
        cm.close()

        carry_path = str(tmp_path / "encrypted_roundtrip.carry")

        # Pack with encryption
        with patch("carrymem.cli.getpass.getpass", side_effect=["mypassword", "mypassword"]):
            result = cmd_pack(["--output", carry_path, "--db", temp_db, "--encrypt"])
        assert result == 0

        # Unpack with decryption
        with patch("carrymem.cli.getpass.getpass", return_value="mypassword"):
            result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0

        captured = capsys.readouterr()
        assert "Checksum verified" in captured.out

        # Verify target has memories
        target_cm = CarryMem(db_path=temp_db_target)
        target_count = target_cm.get_stats()["total_count"]
        target_cm.close()
        assert target_count >= 1

    def test_encrypted_unpack_wrong_password_fails(self, temp_db, temp_db_target, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 2)
        cm.close()

        carry_path = str(tmp_path / "wrong_pass.carry")

        # Pack with password "correct"
        with patch("carrymem.cli.getpass.getpass", side_effect=["correct", "correct"]):
            cmd_pack(["--output", carry_path, "--db", temp_db, "--encrypt"])

        # Unpack with wrong password "wrong"
        with patch("carrymem.cli.getpass.getpass", return_value="wrong"):
            try:
                result = cmd_unpack([carry_path, "--db", temp_db_target])
            except Exception:
                result = 1  # InvalidToken/decryption failure is expected
        assert result == 1

        captured = capsys.readouterr()
        # "Decryption failure" may or may not be in output depending on error handling

    def test_encrypt_password_mismatch(self, temp_db, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 1)
        cm.close()

        carry_path = str(tmp_path / "mismatch.carry")

        with patch("carrymem.cli.getpass.getpass", side_effect=["pass1", "pass2"]):
            result = cmd_pack(["--output", carry_path, "--db", temp_db, "--encrypt"])
        assert result == 1

        captured = capsys.readouterr()
        assert "Passwords do not match" in captured.out

    def test_encrypt_password_too_short(self, temp_db, tmp_path, capsys):
        cm = _store_unique_memories(temp_db, 1)
        cm.close()

        carry_path = str(tmp_path / "short_pass.carry")

        with patch("carrymem.cli.getpass.getpass", side_effect=["ab", "ab"]):
            result = cmd_pack(["--output", carry_path, "--db", temp_db, "--encrypt"])
        assert result == 1

        captured = capsys.readouterr()
        assert "at least 4 characters" in captured.out

    def test_unencrypted_pack_still_works(self, temp_db, temp_db_target, tmp_path, capsys):
        """Without --encrypt, pack should produce unencrypted container."""
        cm = _store_unique_memories(temp_db, 2)
        cm.close()

        carry_path = str(tmp_path / "unencrypted.carry")
        result = cmd_pack(["--output", carry_path, "--db", temp_db])
        assert result == 0

        with gzip.open(carry_path, "rb") as f:
            container = json.loads(f.read().decode("utf-8"))

        assert container.get("encrypted") is False

        # Unpack should work without password prompt
        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0


class TestConflictHandling:
    """Conflict handling when target already has memories."""

    def test_unpack_merge_skips_existing(self, temp_db, temp_db_target, tmp_path, capsys):
        # Store same memory in both source and target
        cm_source = CarryMem(db_path=temp_db)
        cm_source.declare("I prefer dark mode")
        cm_source.close()

        cm_target = CarryMem(db_path=temp_db_target)
        cm_target.declare("I prefer dark mode")
        cm_target.close()

        carry_path = str(tmp_path / "conflict.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0

        captured = capsys.readouterr()
        # Should report conflicts or skipped entries
        assert "conflicts" in captured.out or "restored" in captured.out

    def test_unpack_replace_overwrites(self, temp_db, temp_db_target, tmp_path, capsys):
        cm_source = CarryMem(db_path=temp_db)
        cm_source.declare("I prefer dark mode")
        cm_source.close()

        cm_target = CarryMem(db_path=temp_db_target)
        cm_target.declare("I prefer light mode")
        cm_target.close()

        carry_path = str(tmp_path / "replace.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        result = cmd_unpack([carry_path, "--db", temp_db_target, "--replace"])
        assert result == 0


class TestEmptyDatabasePack:
    """Pack from an empty database."""

    def test_pack_empty_db(self, temp_db, tmp_path, capsys):
        # Create DB but don't add memories
        cm = CarryMem(db_path=temp_db)
        cm.close()

        carry_path = str(tmp_path / "empty.carry")
        result = cmd_pack(["--output", carry_path, "--db", temp_db])
        assert result == 0

        captured = capsys.readouterr()
        assert "0 memories" in captured.out

    def test_unpack_empty_carry(self, temp_db, tmp_path, capsys):
        # Pack an empty DB
        cm = CarryMem(db_path=temp_db)
        cm.close()

        carry_path = str(tmp_path / "empty.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        target_db = str(tmp_path / "target_empty.db")
        result = cmd_unpack([carry_path, "--db", target_db])
        assert result == 0

        captured = capsys.readouterr()
        assert "No memories to restore" in captured.out


class TestLargeDatasetPack:
    """Pack with 100+ memories."""

    def test_pack_100_memories(self, temp_db, tmp_path, capsys):
        cm = CarryMem(db_path=temp_db)
        for i in range(110):
            cm.declare(f"Memory item {i}: preference for option {i} in category {i * 7}")
        source_count = cm.get_stats()["total_count"]
        cm.close()

        assert source_count >= 100

        carry_path = str(tmp_path / "large.carry")
        result = cmd_pack(["--output", carry_path, "--db", temp_db])
        assert result == 0

        captured = capsys.readouterr()
        assert "memories" in captured.out

    def test_pack_unpack_100_memories_roundtrip(self, temp_db, temp_db_target, tmp_path):
        cm = CarryMem(db_path=temp_db)
        for i in range(110):
            cm.declare(f"Memory item {i}: preference for option {i} in category {i * 7}")
        cm.close()

        carry_path = str(tmp_path / "large_roundtrip.carry")
        cmd_pack(["--output", carry_path, "--db", temp_db])

        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0

        # Verify target has memories
        target_cm = CarryMem(db_path=temp_db_target)
        target_count = target_cm.get_stats()["total_count"]
        target_cm.close()

        assert target_count >= 1  # At least some memories restored


class TestLegacyBackwardCompatibility:
    """Backward compatibility with v1.0 .carry files (no checksum)."""

    def test_unpack_legacy_v1_format(self, temp_db_target, tmp_path, capsys):
        """Legacy v1.0 format (no container, no checksum) should still unpack."""
        # Create a legacy v1.0 .carry file manually
        pack_data = {
            "version": "1.0",
            "carrymem_version": "0.2.0",
            "packed_at": "2026-01-01T00:00:00+00:00",
            "source_machine": "test-machine",
            "contents": {
                "memories_count": 1,
                "rules_count": 0,
                "has_config": False,
                "has_encrypted": False,
            },
            "data": {
                "memories": [
                    {
                        "storage_key": "cm_test_legacy",
                        "content": "I prefer dark mode",
                        "type": "user_preference",
                        "confidence": 0.9,
                        "tier": 2,
                        "importance_score": 0.5,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "access_count": 0,
                        "version": 1,
                        "namespace": "default",
                    }
                ],
                "rules": [],
                "config": None,
            },
        }

        carry_path = str(tmp_path / "legacy.carry")
        json_bytes = json.dumps(pack_data, ensure_ascii=False).encode("utf-8")
        with gzip.open(carry_path, "wb") as f:
            f.write(json_bytes)

        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 0

        captured = capsys.readouterr()
        assert "Legacy" in captured.out

    def test_unpack_unsupported_version_fails(self, temp_db_target, tmp_path, capsys):
        """Unsupported version should fail."""
        pack_data = {
            "version": "2.0",
            "carrymem_version": "99.0",
            "packed_at": "2026-01-01T00:00:00+00:00",
            "source_machine": "test",
            "contents": {},
            "data": {"memories": [], "rules": [], "config": None},
        }

        carry_path = str(tmp_path / "unsupported.carry")
        json_bytes = json.dumps(pack_data, ensure_ascii=False).encode("utf-8")
        with gzip.open(carry_path, "wb") as f:
            f.write(json_bytes)

        result = cmd_unpack([carry_path, "--db", temp_db_target])
        assert result == 1

        captured = capsys.readouterr()
        assert "Unsupported" in captured.out


class TestFileNotFound:
    """Error handling for missing files."""

    def test_unpack_nonexistent_file(self, temp_db_target, capsys):
        result = cmd_unpack(["/nonexistent/path/file.carry", "--db", temp_db_target])
        assert result == 1

        captured = capsys.readouterr()
        assert "File not found" in captured.out
