"""
Tests for sqlite_adapter module uncovered paths.

Covers: context manager, remember_batch, forget_expired,
properties, validation errors, rollback_memory,
get_memory_history.
"""

import os

import pytest

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite_adapter import SQLiteAdapter


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_sqlite_ext.db")


@pytest.fixture
def adapter(db_path):
    a = SQLiteAdapter(db_path, enable_semantic_recall=False, enable_cache=False)
    yield a
    a.close()


@pytest.fixture
def adapter_with_data(adapter):
    entry = MemoryEntry(
        content="I prefer dark mode",
        type="user_preference",
    )
    adapter.store_entry(entry)
    return adapter


class TestContextManager:
    def test_enter_exit(self, db_path):
        with SQLiteAdapter(db_path, enable_semantic_recall=False, enable_cache=False) as a:
            assert a is not None
            entry = MemoryEntry(content="Test", type="user_preference")
            a.store_entry(entry)


class TestProperties:
    def test_namespace(self, adapter):
        assert adapter.namespace is not None

    def test_name(self, adapter):
        assert adapter.name is not None

    def test_semantic_enabled(self, adapter):
        result = adapter.semantic_enabled
        assert isinstance(result, bool)

    def test_capabilities(self, adapter):
        result = adapter.capabilities
        assert isinstance(result, dict)


class TestRememberBatch:
    def test_batch_basic(self, adapter):
        entries = [MemoryEntry(content=f"Memory {i}", type="user_preference") for i in range(3)]
        results = adapter.store_batch(entries)
        assert isinstance(results, list)
        assert len(results) == 3

    def test_batch_empty(self, adapter):
        results = adapter.store_batch([])
        assert isinstance(results, list)
        assert len(results) == 0


class TestForgetExpired:
    def test_forget_expired_no_expired(self, adapter_with_data):
        result = adapter_with_data.forget_expired()
        assert isinstance(result, int)
        assert result >= 0


class TestRecallValidation:
    def test_invalid_filter_key(self, adapter):
        with pytest.raises(ValueError, match="Invalid filter key"):
            adapter.recall("test", filters={"evil_key": "value"})

    def test_invalid_memory_type(self, adapter):
        with pytest.raises(ValueError, match="Invalid memory type"):
            adapter.recall("test", filters={"type": "invalid_type"})

    def test_query_too_long(self, adapter):
        with pytest.raises(ValueError, match="too long"):
            adapter.recall("x" * 10001)


class TestRecallWithFilters:
    def test_recall_with_tier(self, adapter_with_data):
        results = adapter_with_data.recall("dark mode", filters={"tier": 1})
        assert isinstance(results, list)

    def test_recall_with_confidence_min(self, adapter_with_data):
        results = adapter_with_data.recall("dark mode", filters={"confidence_min": 0.5})
        assert isinstance(results, list)


class TestGetMemoryHistory:
    def test_history_no_data(self, adapter):
        result = adapter.get_memory_history("nonexistent_key")
        assert isinstance(result, list)


class TestRollbackMemory:
    def test_rollback_no_data(self, adapter):
        result = adapter.rollback_memory("nonexistent_key", version=1)
        assert result is None


class TestGetStats:
    def test_stats(self, adapter_with_data):
        stats = adapter_with_data.get_stats()
        assert isinstance(stats, dict)


class TestGetProfile:
    def test_profile(self, adapter_with_data):
        profile = adapter_with_data.get_profile()
        assert isinstance(profile, dict)


class TestClosedAdapter:
    def test_access_after_close(self, db_path):
        adapter = SQLiteAdapter(db_path, enable_semantic_recall=False, enable_cache=False)
        adapter.close()
        from carrymem.exceptions import DBConnectionError

        with pytest.raises((DBConnectionError, Exception)):
            adapter.recall("test")
