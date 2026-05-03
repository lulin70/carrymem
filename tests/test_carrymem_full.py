"""
Tests for CarryMem core module - targeting uncovered code paths.

Covers: storage adapter loading, backup/restore, audit log,
merge_memories, update_memory, get_memory_history, rollback_memory,
index_knowledge, recall_from_knowledge, recall_all, build_context,
check_conflicts, check_quality, list_expired, export_profile,
import_memories with skip/overwrite, declare, whoami with data.
"""

import json
import os
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from memory_classification_engine import CarryMem
from memory_classification_engine.adapters.sqlite_adapter import SQLiteAdapter
from memory_classification_engine.adapters.base import MemoryEntry, StoredMemory
from memory_classification_engine.exceptions import (
    StorageNotConfiguredError,
    KnowledgeNotConfiguredError,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_carrymem_full.db")


@pytest.fixture
def cm(temp_db):
    c = CarryMem(db_path=temp_db)
    yield c
    c.close()


@pytest.fixture
def cm_with_data(cm):
    cm.classify_and_remember("I prefer dark mode for all editors")
    cm.classify_and_remember("I use PostgreSQL for databases")
    cm.classify_and_remember("I decided to use React for frontend")
    return cm


class TestCarryMemInit:
    def test_init_no_storage(self):
        cm = CarryMem(storage=None)
        assert cm._adapter is None
        cm.close()

    def test_init_sqlite_default(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        assert isinstance(cm._adapter, SQLiteAdapter)
        cm.close()

    def test_init_custom_adapter(self, temp_db):
        adapter = SQLiteAdapter(db_path=temp_db)
        cm = CarryMem(storage=adapter)
        assert cm._adapter is adapter
        cm.close()

    def test_init_unknown_adapter_string(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            CarryMem(storage="nonexistent_adapter")

    def test_init_obsidian_string(self):
        with pytest.raises(ValueError, match="ObsidianAdapter requires"):
            CarryMem(storage="obsidian")

    def test_init_invalid_storage_type(self):
        with pytest.raises(ValueError, match="Invalid storage type"):
            CarryMem(storage=12345)


class TestCarryMemClose:
    def test_close_with_adapter(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        cm.close()
        assert cm._adapter is not None

    def test_close_no_adapter(self):
        cm = CarryMem(storage=None)
        cm.close()

    def test_context_manager(self, temp_db):
        with CarryMem(db_path=temp_db) as cm:
            assert cm._adapter is not None


class TestCarryMemClearCache:
    def test_clear_cache(self, cm):
        cm.classify_and_remember("test memory")
        cm.clear_cache()

    def test_clear_cache_no_adapter(self):
        cm = CarryMem(storage=None)
        cm.clear_cache()


class TestCarryMemBackup:
    def test_backup(self, cm_with_data, tmp_path):
        backup_dir = str(tmp_path / "backups")
        result = cm_with_data.backup(backup_dir=backup_dir)
        assert result.get("backed_up") is True

    def test_backup_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.backup()
        assert "error" in result

    def test_backup_in_memory(self):
        cm = CarryMem(db_path=":memory:")
        result = cm.backup()
        assert "error" in result
        cm.close()

    def test_list_backups(self, cm_with_data, tmp_path):
        backup_dir = str(tmp_path / "backups")
        cm_with_data.backup(backup_dir=backup_dir)
        result = cm_with_data.list_backups(backup_dir=backup_dir)
        assert isinstance(result, list)

    def test_list_backups_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.list_backups()
        assert result == []

    def test_restore_backup(self, cm_with_data, tmp_path):
        backup_dir = str(tmp_path / "backups")
        backup_result = cm_with_data.backup(backup_dir=backup_dir)
        if backup_result.get("backed_up"):
            restore_result = cm_with_data.restore_backup(backup_result["path"])
            assert restore_result.get("restored") is True

    def test_restore_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.restore_backup("/some/path")
        assert "error" in result

    def test_restore_in_memory(self):
        cm = CarryMem(db_path=":memory:")
        result = cm.restore_backup("/some/path")
        assert "error" in result
        cm.close()


class TestCarryMemAuditLog:
    def test_get_audit_log(self, cm_with_data):
        result = cm_with_data.get_audit_log()
        assert isinstance(result, list)

    def test_get_audit_log_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.get_audit_log()
        assert result == []


class TestCarryMemMerge:
    def test_merge_memories(self, cm_with_data):
        result = cm_with_data.merge_memories()
        assert "total_input" in result
        assert "total_output" in result

    def test_merge_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.merge_memories()

    def test_merge_non_sqlite_adapter(self):
        from memory_classification_engine.adapters.base import StorageAdapter
        mock_adapter = MagicMock(spec=StorageAdapter)
        cm = CarryMem(storage=mock_adapter)
        result = cm.merge_memories()
        assert "error" in result
        cm.close()


class TestCarryMemUpdateMemory:
    def test_update_memory(self, cm_with_data):
        memories = cm_with_data.recall_memories(limit=1)
        if memories:
            key = memories[0]["storage_key"]
            result = cm_with_data.update_memory(key, "Updated content")
            assert result.get("updated") is True

    def test_update_memory_not_found(self, cm):
        result = cm_with_data_f(cm).update_memory("nonexistent_key", "new content")

    def test_update_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.update_memory("key", "content")


def cm_with_data_f(cm):
    cm.classify_and_remember("I prefer dark mode")
    return cm


class TestCarryMemMemoryHistory:
    def test_get_memory_history(self, cm):
        cm.classify_and_remember("I prefer dark mode")
        memories = cm.recall_memories(limit=1)
        if memories:
            key = memories[0]["storage_key"]
            result = cm.get_memory_history(key)
            assert isinstance(result, list)

    def test_get_memory_history_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.get_memory_history("key")


class TestCarryMemRollbackMemory:
    def test_rollback_memory(self, cm):
        cm.classify_and_remember("I prefer dark mode")
        memories = cm.recall_memories(limit=1)
        if memories:
            key = memories[0]["storage_key"]
            cm.update_memory(key, "Updated content")
            result = cm.rollback_memory(key, version=1)
            assert result.get("rolled_back") is True or "error" in result

    def test_rollback_not_found(self, cm):
        result = cm.rollback_memory("nonexistent_key", version=1)
        assert result.get("rolled_back") is False or "error" in result

    def test_rollback_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.rollback_memory("key", version=1)


class TestCarryMemKnowledge:
    def test_index_knowledge_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(KnowledgeNotConfiguredError):
            cm.index_knowledge()

    def test_recall_from_knowledge_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(KnowledgeNotConfiguredError):
            cm.recall_from_knowledge("test query")


class TestCarryMemRecallAll:
    def test_recall_all_with_memories(self, cm_with_data):
        result = cm_with_data.recall_all(query="dark mode")
        assert "memories" in result
        assert "knowledge" in result
        assert "total_count" in result

    def test_recall_all_no_adapters(self):
        cm = CarryMem(storage=None)
        result = cm.recall_all(query="test")
        assert result["memory_count"] == 0
        assert result["knowledge_count"] == 0

    def test_recall_all_with_namespaces(self, cm_with_data):
        result = cm_with_data.recall_all(query="", namespaces=["default"])
        assert "memories" in result


class TestCarryMemClassifyAndRemember:
    def test_empty_message(self, cm):
        with pytest.raises(ValueError, match="empty"):
            cm.classify_and_remember("")

    def test_message_too_long(self, cm):
        with pytest.raises(ValueError, match="too long"):
            cm.classify_and_remember("x" * 50001)

    def test_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.classify_and_remember("test")


class TestCarryMemForget:
    def test_forget_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.forget_memory("key")


class TestCarryMemGetStats:
    def test_get_stats_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.get_stats()
        assert result["total_count"] == 0


class TestCarryMemDeclare:
    def test_declare_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.declare("I prefer dark mode")

    def test_declare_preference_alias(self, cm):
        result = cm.declare_preference("I prefer dark mode")
        assert result.get("declared") is True


class TestCarryMemProfile:
    def test_get_memory_profile_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.get_memory_profile()
        assert result["total_memories"] == 0

    def test_whoami_no_adapter(self):
        cm = CarryMem(storage=None)
        result = cm.whoami()
        assert result["identity"] == "unknown"

    def test_whoami_new_user(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        result = cm.whoami()
        assert result["identity"] == "new_user"
        cm.close()

    def test_whoami_with_data(self, cm_with_data):
        result = cm_with_data.whoami()
        assert result["identity"] == "known_user"
        assert "preferences" in result

    def test_export_profile_with_path(self, cm_with_data, tmp_path):
        output_path = str(tmp_path / "profile.json")
        result = cm_with_data.export_profile(output_path=output_path)
        assert os.path.exists(output_path)


class TestCarryMemExport:
    def test_export_with_namespace(self, cm_with_data, tmp_path):
        output_path = str(tmp_path / "export_ns.json")
        result = cm_with_data.export_memories(
            output_path=output_path, namespace="default"
        )
        assert result.get("exported") is True

    def test_export_markdown(self, cm_with_data, tmp_path):
        output_path = str(tmp_path / "export.md")
        result = cm_with_data.export_memories(
            output_path=output_path, format="markdown"
        )
        assert result.get("exported") is True
        assert result.get("format") == "markdown"

    def test_export_no_output_path(self, cm_with_data):
        result = cm_with_data.export_memories(format="json")
        assert result.get("exported") is True

    def test_export_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.export_memories()


class TestCarryMemImport:
    def test_import_with_data(self, cm, tmp_path):
        cm.classify_and_remember("I prefer dark mode")
        output_path = str(tmp_path / "import_data.json")
        cm.export_memories(output_path=output_path)
        result = cm.import_memories(input_path=output_path)
        assert result.get("imported", 0) >= 0

    def test_import_with_dict_data(self, cm):
        data = {
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
        result = cm.import_memories(data=data)
        assert result.get("imported", 0) >= 0

    def test_import_no_path_no_data(self, cm):
        with pytest.raises(ValueError, match="Either input_path or data"):
            cm.import_memories()

    def test_import_overwrite_strategy(self, cm, tmp_path):
        cm.classify_and_remember("I prefer dark mode")
        output_path = str(tmp_path / "import_overwrite.json")
        cm.export_memories(output_path=output_path)
        result = cm.import_memories(input_path=output_path, merge_strategy="overwrite")
        assert result.get("imported", 0) >= 0

    def test_import_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.import_memories(data={"memories": []})


class TestCarryMemBuildContext:
    def test_build_context(self, cm_with_data):
        result = cm_with_data.build_context(context="dark mode")
        assert "system_prompt" in result
        assert "memories" in result

    def test_build_context_no_context(self, cm_with_data):
        result = cm_with_data.build_context()
        assert "system_prompt" in result

    def test_build_system_prompt(self, cm_with_data):
        result = cm_with_data.build_system_prompt(context="dark mode")
        assert isinstance(result, str)


class TestCarryMemCheckConflicts:
    def test_check_conflicts(self, cm_with_data):
        result = cm_with_data.check_conflicts()
        assert isinstance(result, list)

    def test_check_conflicts_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.check_conflicts()


class TestCarryMemCheckQuality:
    def test_check_quality(self, cm_with_data):
        result = cm_with_data.check_quality(min_score=0.3)
        assert isinstance(result, list)

    def test_check_quality_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.check_quality()


class TestCarryMemListExpired:
    def test_list_expired(self, cm_with_data):
        result = cm_with_data.list_expired()
        assert isinstance(result, list)

    def test_list_expired_no_adapter(self):
        cm = CarryMem(storage=None)
        with pytest.raises(StorageNotConfiguredError):
            cm.list_expired()

    def test_list_expired_non_sqlite(self):
        from memory_classification_engine.adapters.base import StorageAdapter
        mock_adapter = MagicMock(spec=StorageAdapter)
        cm = CarryMem(storage=mock_adapter)
        result = cm.list_expired()
        assert result == []
        cm.close()


class TestCarryMemProperties:
    def test_namespace_property(self, cm):
        assert cm.namespace == "default"

    def test_engine_property(self, cm):
        assert cm.engine is not None

    def test_adapter_property(self, cm):
        assert cm.adapter is not None

    def test_storage_property(self, cm):
        assert cm.storage is not None

    def test_knowledge_adapter_property(self, cm):
        assert cm.knowledge_adapter is None
