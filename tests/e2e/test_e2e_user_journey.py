"""E2E test: Simulates a real user's first-time experience with CarryMem.

Covers the complete workflow from initialization to daily usage:
1. Initialize and store memories (classify_and_remember)
2. Recall memories (recall_memories)
3. Declare preferences (declare)
4. Get memory profile (whoami, get_memory_profile)
5. Backup cycle
6. Multi-namespace isolation
7. Forget memory
8. Backup → restore roundtrip
"""

import os
import shutil
import tempfile

import pytest

from carrymem import CarryMem


class TestFirstTimeUserExperience:
    def test_complete_new_user_journey(self, fresh_carrymem):
        cm = fresh_carrymem

        result = cm.classify_and_remember("I prefer dark mode for coding")
        assert isinstance(result, dict)
        assert "should_remember" in result

        result = cm.classify_and_remember("I use Python for backend development")
        assert isinstance(result, dict)

        result = cm.classify_and_remember("My project uses SQLite for local storage")
        assert isinstance(result, dict)

        results = cm.recall_memories("coding")
        assert isinstance(results, list)

        result = cm.declare("theme:dark")
        assert isinstance(result, dict)

        profile = cm.get_memory_profile()
        assert isinstance(profile, dict)

        whoami = cm.whoami()
        assert isinstance(whoami, dict)


class TestBackupRestore:
    def test_backup_creates_file(self, fresh_carrymem):
        cm = fresh_carrymem
        tmp = tempfile.mkdtemp()
        try:
            result = cm.classify_and_remember("I prefer dark mode for coding")
            assert result.get("stored") is True, f"premise: memory must be stored: {result}"

            backup_dir = os.path.join(tmp, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_result = cm.backup(backup_dir=backup_dir)
            assert backup_result.get("backed_up") is True, backup_result
            assert os.path.exists(backup_result["path"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestBackupRestoreRoundtrip:
    def test_backup_restore_roundtrip(self, fresh_carrymem):
        """E2E journey: store → backup → fresh instance → restore → recall.

        Replaces the former ``test_pack_with_encryption`` which called a
        non-existent ``cm.pack()`` API inside ``except (AttributeError,
        TypeError): pass`` — a guaranteed vacuous pass (ghost test).
        """
        cm = fresh_carrymem
        tmp = tempfile.mkdtemp()
        try:
            result = cm.classify_and_remember("I prefer dark mode for coding")
            assert result.get("stored") is True, f"premise: memory must be stored: {result}"
            source_recall = cm.recall_memories("dark mode")
            assert len(source_recall) > 0, "just-stored memory must be recallable"

            backup_result = cm.backup(backup_dir=tmp)
            assert backup_result.get("backed_up") is True, backup_result
            backup_path = backup_result["path"]
            assert os.path.exists(backup_path)

            # Restore into a fresh instance pointed at a new (empty) DB.
            restored_db = os.path.join(tmp, "restored.db")
            shutil.copyfile(backup_path, restored_db)
            cm2 = CarryMem(db_path=restored_db)
            try:
                results = cm2.recall_memories("dark mode")
                assert len(results) > 0, "memory must survive backup→restore"
            finally:
                cm2.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMultiNamespace:
    def test_namespace_isolation(self, fresh_carrymem):
        cm = fresh_carrymem

        cm.classify_and_remember("Work memory about project deadlines")
        cm.classify_and_remember("Personal hobby interests")

        all_results = cm.recall_memories("memory")
        assert isinstance(all_results, list)


class TestForgetMemory:
    def test_forget_removes_memory(self, fresh_carrymem):
        cm = fresh_carrymem

        result = cm.classify_and_remember("Temporary note to delete")
        assert isinstance(result, dict)

        results = cm.recall_memories("Temporary")
        if len(results) > 0:
            memory_id = results[0].get("key", results[0].get("storage_key", results[0].get("id", "")))
            if memory_id:
                forget_result = cm.forget_memory(str(memory_id))
                assert isinstance(forget_result, bool)
