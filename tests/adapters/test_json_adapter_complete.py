"""JSON adapter complete test suite - Phase 1 Coverage Boost.

Comprehensive tests for JSON storage adapter: CRUD, corruption handling, edge cases.
"""

import json
import pytest
from pathlib import Path
from carrymem.adapters.json_adapter import JSONAdapter
from carrymem.types import MemoryDict, MemoryType


@pytest.fixture
def json_file(tmp_path):
    """Temporary JSON storage file."""
    return tmp_path / "memories.json"


@pytest.fixture
def adapter(json_file):
    """JSON adapter instance."""
    return JSONAdapter(str(json_file))


class TestJSONAdapterInit:
    """Test JSON adapter initialization."""

    def test_init_creates_file_if_not_exists(self, json_file):
        """Test that adapter creates file on init if it doesn't exist."""
        assert not json_file.exists()
        adapter = JSONAdapter(str(json_file))
        assert json_file.exists()

    def test_init_with_existing_file(self, json_file):
        """Test init with existing JSON file."""
        json_file.write_text('{"memories": []}')
        adapter = JSONAdapter(str(json_file))
        assert adapter is not None

    def test_init_with_invalid_json_file(self, json_file):
        """Test init with corrupted JSON file."""
        json_file.write_text('{"invalid json')
        with pytest.raises(Exception):
            JSONAdapter(str(json_file))


class TestJSONAdapterRemember:
    """Test JSON adapter remember (create) operation."""

    def test_remember_basic(self, adapter):
        """Test basic remember operation."""
        memory: MemoryDict = {
            "storage_key": "cm_test_001",
            "content": "Test memory",
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        result = adapter.remember(memory)
        assert result == "cm_test_001"

    def test_remember_multiple_memories(self, adapter):
        """Test remembering multiple memories."""
        for i in range(5):
            memory: MemoryDict = {
                "storage_key": f"cm_test_{i:03d}",
                "content": f"Memory {i}",
                "memory_type": MemoryType.USER_PREFERENCE,
                "created_at": "2026-06-15T12:00:00Z",
                "metadata": {}
            }
            adapter.remember(memory)
        
        memories = adapter.recall()
        assert len(memories) >= 5

    def test_remember_with_complex_metadata(self, adapter):
        """Test remembering memory with complex metadata."""
        memory: MemoryDict = {
            "storage_key": "cm_test_meta",
            "content": "Complex memory",
            "memory_type": MemoryType.CORRECTION,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {
                "tags": ["important", "urgent"],
                "project": {"name": "Alpha", "version": "1.0"},
                "nested": {"deep": {"value": 123}}
            }
        }
        result = adapter.remember(memory)
        assert result == "cm_test_meta"
        
        # Verify retrieval
        recalled = adapter.recall(storage_key="cm_test_meta")
        assert len(recalled) == 1
        assert recalled[0]["metadata"]["tags"] == ["important", "urgent"]


class TestJSONAdapterRecall:
    """Test JSON adapter recall (read) operation."""

    def test_recall_empty(self, adapter):
        """Test recall from empty storage."""
        memories = adapter.recall()
        assert isinstance(memories, list)
        assert len(memories) == 0

    def test_recall_all_memories(self, adapter):
        """Test recalling all memories."""
        # Add some memories
        for i in range(3):
            memory: MemoryDict = {
                "storage_key": f"cm_{i}",
                "content": f"Memory {i}",
                "memory_type": MemoryType.USER_PREFERENCE,
                "created_at": f"2026-06-15T12:00:{i:02d}Z",
                "metadata": {}
            }
            adapter.remember(memory)
        
        memories = adapter.recall()
        assert len(memories) == 3

    def test_recall_by_storage_key(self, adapter):
        """Test recalling by specific storage key."""
        memory: MemoryDict = {
            "storage_key": "cm_specific",
            "content": "Specific memory",
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        recalled = adapter.recall(storage_key="cm_specific")
        assert len(recalled) == 1
        assert recalled[0]["content"] == "Specific memory"

    def test_recall_by_type(self, adapter):
        """Test recalling by memory type."""
        types = [MemoryType.USER_PREFERENCE, MemoryType.CORRECTION, MemoryType.USER_PREFERENCE]
        for i, mem_type in enumerate(types):
            memory: MemoryDict = {
                "storage_key": f"cm_{i}",
                "content": f"Memory {i}",
                "memory_type": mem_type,
                "created_at": "2026-06-15T12:00:00Z",
                "metadata": {}
            }
            adapter.remember(memory)
        
        prefs = adapter.recall(memory_type=MemoryType.USER_PREFERENCE)
        assert len(prefs) == 2

    def test_recall_with_limit(self, adapter):
        """Test recall with limit parameter."""
        for i in range(10):
            memory: MemoryDict = {
                "storage_key": f"cm_{i}",
                "content": f"Memory {i}",
                "memory_type": MemoryType.USER_PREFERENCE,
                "created_at": "2026-06-15T12:00:00Z",
                "metadata": {}
            }
            adapter.remember(memory)
        
        limited = adapter.recall(limit=5)
        assert len(limited) <= 5


class TestJSONAdapterForget:
    """Test JSON adapter forget (delete) operation."""

    def test_forget_existing_memory(self, adapter):
        """Test forgetting an existing memory."""
        memory: MemoryDict = {
            "storage_key": "cm_to_delete",
            "content": "Delete me",
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        result = adapter.forget("cm_to_delete")
        assert result is True
        
        # Verify deletion
        recalled = adapter.recall(storage_key="cm_to_delete")
        assert len(recalled) == 0

    def test_forget_nonexistent_memory(self, adapter):
        """Test forgetting a nonexistent memory."""
        result = adapter.forget("cm_nonexistent")
        assert result is False

    def test_forget_multiple_times(self, adapter):
        """Test forgetting same key multiple times."""
        memory: MemoryDict = {
            "storage_key": "cm_test",
            "content": "Test",
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        assert adapter.forget("cm_test") is True
        assert adapter.forget("cm_test") is False  # Already deleted


class TestJSONAdapterCorruption:
    """Test JSON adapter corruption handling."""

    def test_handle_corrupted_json_during_operation(self, json_file, adapter):
        """Test handling when file gets corrupted during operation."""
        # Add a memory first
        memory: MemoryDict = {
            "storage_key": "cm_test",
            "content": "Test",
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        # Corrupt the file
        json_file.write_text('{"invalid": json}')
        
        # Operations should handle gracefully
        with pytest.raises(Exception):
            adapter.recall()

    def test_recover_from_empty_file(self, json_file, adapter):
        """Test recovery when file is empty."""
        json_file.write_text('')
        with pytest.raises(Exception):
            adapter.recall()

    def test_handle_missing_file_during_operation(self, json_file, adapter):
        """Test handling when file is deleted during operation."""
        memory: MemoryDict = {
            "storage_key": "cm_test",
            "content": "Test",
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        # Delete file
        json_file.unlink()
        
        # Should handle gracefully
        with pytest.raises(Exception):
            adapter.recall()


class TestJSONAdapterEdgeCases:
    """Test JSON adapter edge cases."""

    def test_large_number_of_memories(self, adapter):
        """Test handling large number of memories."""
        for i in range(100):
            memory: MemoryDict = {
                "storage_key": f"cm_{i:04d}",
                "content": f"Memory {i}",
                "memory_type": MemoryType.USER_PREFERENCE,
                "created_at": "2026-06-15T12:00:00Z",
                "metadata": {}
            }
            adapter.remember(memory)
        
        memories = adapter.recall()
        assert len(memories) == 100

    def test_very_long_content(self, adapter):
        """Test storing very long content."""
        long_content = "A" * 10000  # 10K characters
        memory: MemoryDict = {
            "storage_key": "cm_long",
            "content": long_content,
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        recalled = adapter.recall(storage_key="cm_long")
        assert recalled[0]["content"] == long_content

    def test_unicode_content(self, adapter):
        """Test storing Unicode content."""
        unicode_content = "Hello 世界 🌍 مرحبا"
        memory: MemoryDict = {
            "storage_key": "cm_unicode",
            "content": unicode_content,
            "memory_type": MemoryType.USER_PREFERENCE,
            "created_at": "2026-06-15T12:00:00Z",
            "metadata": {}
        }
        adapter.remember(memory)
        
        recalled = adapter.recall(storage_key="cm_unicode")
        assert recalled[0]["content"] == unicode_content
