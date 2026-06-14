"""Test adapter standardization - P2-4.

Verifies that all storage adapters conform to the StorageAdapter interface.
Tests runtime ABC compliance and method signatures.
"""

from typing import TYPE_CHECKING

import pytest

from carrymem.adapters.base import MemoryEntry, StorageAdapter, StoredMemory
from carrymem.adapters.json_adapter import JSONAdapter
from carrymem.adapters.sqlite import SQLiteAdapter

if TYPE_CHECKING:
    from carrymem.adapters.obsidian_adapter import ObsidianAdapter


class TestStorageAdapterProtocolCompliance:
    """Test that all adapters conform to StorageAdapter."""

    def test_sqlite_adapter_protocol_compliance(self):
        """SQLiteAdapter must conform to StorageAdapter."""
        adapter = SQLiteAdapter(":memory:")
        try:
            assert isinstance(adapter, StorageAdapter), "SQLiteAdapter does not conform to StorageAdapter"
        finally:
            adapter.close()

    def test_json_adapter_protocol_compliance(self):
        """JSONAdapter must conform to StorageAdapter."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_memories.json")
            adapter = JSONAdapter(path=path)
            assert isinstance(adapter, StorageAdapter), "JSONAdapter does not conform to StorageAdapter"
            adapter.close()


class TestSQLiteAdapterStandardizedInterface:
    """Test SQLiteAdapter implements all standardized interface methods correctly."""

    @pytest.fixture
    def adapter(self):
        """Create an in-memory SQLiteAdapter for testing."""
        adapter = SQLiteAdapter(":memory:")
        yield adapter
        adapter.close()

    def test_initialize_method_exists(self, adapter):
        """initialize() method must exist and be callable."""
        assert hasattr(adapter, "initialize")
        assert callable(adapter.initialize)
        # Should not raise
        adapter.initialize({})

    def test_store_method_signature(self, adapter):
        """store() must accept dict and return str."""
        entry = {"content": "test memory", "type": "fact_declaration", "confidence": 0.9}
        entry_id = adapter.store(entry)

        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

    def test_recall_method_signature(self, adapter):
        """recall() must accept query string and return list of dicts."""
        # First store something
        adapter.store({"content": "Python programming language", "type": "fact_declaration"})

        results = adapter.recall("Python", limit=10)

        assert isinstance(results, list)
        assert len(results) > 0
        # Results should be dicts or StoredMemory objects
        for r in results:
            assert isinstance(r, (dict, StoredMemory))

    def test_delete_method_signature(self, adapter):
        """delete() must accept str ID and return bool."""
        entry_id = adapter.store({"content": "to be deleted", "type": "task_pattern"})

        result = adapter.delete(entry_id)
        assert isinstance(result, bool)
        assert result is True

        # Delete again should return False
        result2 = adapter.delete(entry_id)
        assert result2 is False

    def test_count_method_signature(self, adapter):
        """count() must return int."""
        initial_count = adapter.count()
        assert isinstance(initial_count, int)

        # Store some entries
        adapter.store({"content": "entry 1", "type": "fact_declaration"})
        adapter.store({"content": "entry 2", "type": "user_preference"})

        new_count = adapter.count()
        assert isinstance(new_count, int)
        assert new_count >= initial_count + 2

    def test_health_check_method_signature(self, adapter):
        """health_check() must return dict with required fields."""
        result = adapter.health_check()

        assert isinstance(result, dict)
        assert "status" in result
        assert "latency_ms" in result
        assert result["status"] in ("healthy", "degraded", "unhealthy")
        assert isinstance(result["latency_ms"], (int, float))

    def test_close_method_idempotent(self, adapter):
        """close() must be safe to call multiple times."""
        adapter.close()
        adapter.close()  # Should not raise


class TestJSONAdapterStandardizedInterface:
    """Test JSONAdapter implements all standardized interface methods correctly."""

    @pytest.fixture
    def json_adapter(self, tmp_path):
        """Create a JSONAdapter with temp file for testing."""
        path = tmp_path / "test_memories.json"
        adapter = JSONAdapter(path=str(path))
        yield adapter
        adapter.close()

    def test_initialize_method_exists(self, json_adapter):
        """initialize() method must exist and be callable."""
        assert hasattr(json_adapter, "initialize")
        assert callable(json_adapter.initialize)
        json_adapter.initialize({"namespace": "test"})

    def test_store_method_signature(self, json_adapter):
        """store() must accept dict and return str."""
        entry = {"content": "test memory", "type": "fact_declaration"}
        entry_id = json_adapter.store(entry)

        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

    def test_recall_method_signature(self, json_adapter):
        """recall() must accept query string and return list."""
        json_adapter.store({"content": "Python testing", "type": "fact_declaration"})

        results = json_adapter.recall("Python", limit=10)

        assert isinstance(results, list)
        assert len(results) > 0

    def test_delete_method_signature(self, json_adapter):
        """delete() must accept str ID and return bool."""
        entry_id = json_adapter.store({"content": "delete me", "type": "task_pattern"})

        result = json_adapter.delete(entry_id)
        assert isinstance(result, bool)
        assert result is True

    def test_count_method_signature(self, json_adapter):
        """count() must return int."""
        count = json_adapter.count()
        assert isinstance(count, int)

    def test_health_check_method_signature(self, json_adapter):
        """health_check() must return dict with required fields."""
        result = json_adapter.health_check()

        assert isinstance(result, dict)
        assert "status" in result
        assert "latency_ms" in result

    def test_close_method_idempotent(self, json_adapter):
        """close() must be safe to call multiple times."""
        json_adapter.close()
        json_adapter.close()


class TestProtocolMethodPresence:
    """Verify all required methods are present on adapters."""

    REQUIRED_METHODS = [
        "initialize",
        "store",
        "recall",
        "delete",
        "count",
        "health_check",
        "close",
    ]

    @pytest.mark.parametrize("method_name", REQUIRED_METHODS)
    def test_sqlite_adapter_has_method(self, adapter, method_name):
        """SQLiteAdapter must have all required methods."""
        assert hasattr(adapter, method_name), f"SQLiteAdapter missing {method_name}"
        assert callable(getattr(adapter, method_name)), f"{method_name} is not callable"

    @pytest.mark.parametrize("method_name", REQUIRED_METHODS)
    def test_json_adapter_has_method(self, json_adapter, method_name):
        """JSONAdapter must have all required methods."""
        assert hasattr(json_adapter, method_name), f"JSONAdapter missing {method_name}"
        assert callable(getattr(json_adapter, method_name)), f"{method_name} is not callable"

    @pytest.fixture
    def adapter(self):
        adapter = SQLiteAdapter(":memory:")
        yield adapter
        adapter.close()

    @pytest.fixture
    def json_adapter(self, tmp_path):
        path = tmp_path / "test.json"
        adapter = JSONAdapter(path=str(path))
        yield adapter
        adapter.close()


class TestProtocolTypeSafety:
    """Test type safety aspects of the Protocol implementation."""

    def test_store_accepts_dict_only(self):
        """store() should accept dict-like input."""
        adapter = SQLiteAdapter(":memory:")
        try:
            # Valid dict input
            entry_id = adapter.store({"content": "test", "type": "fact"})
            assert isinstance(entry_id, str)

            # Invalid input should raise TypeError or handle gracefully
            with pytest.raises((TypeError, AttributeError, ValueError)):
                adapter.store("not a dict")  # type: ignore
        finally:
            adapter.close()

    def test_recall_returns_list_of_dicts(self):
        """recall() should return list[dict] compatible output."""
        adapter = SQLiteAdapter(":memory:")
        try:
            adapter.store({"content": "searchable content", "type": "fact_declaration"})
            results = adapter.recall("searchable")

            assert isinstance(results, list)
            for item in results:
                # Should be convertible to dict (StoredMemory has to_dict())
                if hasattr(item, "to_dict"):
                    d = item.to_dict()
                    assert isinstance(d, dict)
                else:
                    assert isinstance(item, dict)
        finally:
            adapter.close()

    def test_delete_returns_bool(self):
        """delete() should return bool."""
        adapter = SQLiteAdapter(":memory:")
        try:
            entry_id = adapter.store({"content": "x", "type": "fact"})
            result = adapter.delete(entry_id)
            assert isinstance(result, bool)
            assert result is True

            result2 = adapter.delete("nonexistent-id")
            assert isinstance(result2, bool)
            assert result2 is False
        finally:
            adapter.close()

    def test_count_returns_non_negative_int(self):
        """count() should return non-negative integer."""
        adapter = SQLiteAdapter(":memory:")
        try:
            count = adapter.count()
            assert isinstance(count, int)
            assert count >= 0
        finally:
            adapter.close()

    def test_health_check_returns_valid_structure(self):
        """health_check() should return properly structured dict."""
        adapter = SQLiteAdapter(":memory:")
        try:
            hc = adapter.health_check()
            assert isinstance(hc, dict)
            assert "status" in hc
            assert hc["status"] in ("healthy", "degraded", "unhealthy")
            assert "latency_ms" in hc
            assert isinstance(hc["latency_ms"], (int, float))
            assert hc["latency_ms"] >= 0
        finally:
            adapter.close()


class TestCrossAdapterConsistency:
    """Test that different adapters behave consistently for the same operations."""

    def test_both_adapters_support_basic_crud(self, sqlite_adapter, json_adapter):
        """Both adapters must support basic CRUD operations."""
        test_entry = {"content": "consistency test", "type": "user_preference", "confidence": 0.95}

        # Store
        sqlite_id = sqlite_adapter.store(test_entry)
        json_id = json_adapter.store(test_entry)
        assert isinstance(sqlite_id, str) and len(sqlite_id) > 0
        assert isinstance(json_id, str) and len(json_id) > 0

        # Recall
        sqlite_results = sqlite_adapter.recall("consistency")
        json_results = json_adapter.recall("consistency")
        assert len(sqlite_results) > 0
        assert len(json_results) > 0

        # Count
        assert sqlite_adapter.count() > 0
        assert json_adapter.count() > 0

        # Health check
        sqlite_hc = sqlite_adapter.health_check()
        json_hc = json_adapter.health_check()
        assert sqlite_hc["status"] == "healthy"
        assert json_hc["status"] == "healthy"

        # Delete
        assert sqlite_adapter.delete(sqlite_id) is True
        assert json_adapter.delete(json_id) is True

    @pytest.fixture
    def sqlite_adapter(self):
        adapter = SQLiteAdapter(":memory:")
        yield adapter
        adapter.close()

    @pytest.fixture
    def json_adapter(self, tmp_path):
        path = tmp_path / "consistency_test.json"
        adapter = JSONAdapter(path=str(path))
        yield adapter
        adapter.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
