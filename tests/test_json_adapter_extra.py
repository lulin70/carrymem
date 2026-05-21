"""Extra tests for json_adapter to push coverage over 80%."""
import json
import os

import pytest

from carrymem.adapters.base import MemoryEntry


class TestJsonAdapterExtra:
    """Tests for uncovered lines in json_adapter.py."""

    def test_corrupt_json_file(self, tmp_path):
        """Lines 49-50: JSON decode error handling."""
        from carrymem.adapters.json_adapter import JSONAdapter

        db_file = str(tmp_path / "corrupt.json")
        with open(db_file, "w") as f:
            f.write("{invalid json content")

        adapter = JSONAdapter(path=db_file)
        result = adapter.recall("test", limit=5)
        assert isinstance(result, list)

    def test_missing_directory_created(self, tmp_path):
        """Lines 56->58: directory creation for path."""
        from carrymem.adapters.json_adapter import JSONAdapter

        nested_path = str(tmp_path / "nested" / "dir" / "db.json")
        adapter = JSONAdapter(path=nested_path)
        entry = MemoryEntry(content="test content", type="personal_fact")
        adapter.remember(entry)
        assert os.path.exists(nested_path)

    def test_recall_with_update_access_false(self, tmp_path):
        """update_access=False should not modify access_count."""
        from carrymem.adapters.json_adapter import JSONAdapter

        adapter = JSONAdapter(path=str(tmp_path / "test.json"))
        entry = MemoryEntry(content="I prefer Python", type="user_preference")
        adapter.remember(entry)

        # Recall with update_access=True
        r1 = adapter.recall("Python", limit=5, update_access=True)
        assert len(r1) >= 1
        count_after_true = r1[0].access_count

        # Recall with update_access=False
        r2 = adapter.recall("Python", limit=5, update_access=False)
        count_after_false = r2[0].access_count
        assert count_after_false == count_after_true

    def test_recall_empty_db(self, tmp_path):
        """Recall from empty database."""
        from carrymem.adapters.json_adapter import JSONAdapter

        adapter = JSONAdapter(path=str(tmp_path / "empty.json"))
        result = adapter.recall("anything", limit=5)
        assert result == []

    def test_store_multiple_types(self, tmp_path):
        """Store and recall different memory types."""
        from carrymem.adapters.json_adapter import JSONAdapter

        adapter = JSONAdapter(path=str(tmp_path / "multi.json"))
        adapter.remember(MemoryEntry(content="I prefer Python", type="user_preference"))
        adapter.remember(MemoryEntry(content="Do NOT use Java", type="correction"))
        adapter.remember(MemoryEntry(content="Meeting at 3pm", type="personal_fact"))

        all_mems = adapter.recall("Python", limit=10)
        assert len(all_mems) >= 1
