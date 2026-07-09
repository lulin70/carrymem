"""
Tests for base adapter module.

Covers: MemoryEntry, StoredMemory.from_dict/to_dict,
StorageAdapter base defaults.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from carrymem.adapters.base import (
    MemoryEntry,
    StorageAdapter,
    StoredMemory,
)


class TestMemoryEntry:
    def test_to_dict(self):
        entry = MemoryEntry(
            content="I prefer dark mode",
            type="user_preference",
        )
        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["content"] == "I prefer dark mode"

    def test_from_dict(self):
        d = {
            "content": "I prefer dark mode",
            "type": "user_preference",
        }
        entry = MemoryEntry.from_dict(d)
        assert entry.content == "I prefer dark mode"

    def test_repr(self):
        entry = MemoryEntry(
            content="I prefer dark mode",
            type="user_preference",
        )
        r = repr(entry)
        assert isinstance(r, str)


class TestStoredMemoryFromDict:
    def test_basic(self):
        d = {
            "storage_key": "mem_001",
            "content": "I prefer dark mode",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        result = StoredMemory.from_dict(d)
        assert result is not None
        assert result.content == "I prefer dark mode"

    def test_datetime_objects(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        d = {
            "storage_key": "mem_002",
            "content": "Test",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": dt,
            "updated_at": dt,
            "expires_at": dt,
            "last_accessed_at": dt,
        }
        result = StoredMemory.from_dict(d)
        assert result is not None

    def test_naive_datetime(self):
        dt = datetime(2026, 1, 1)
        d = {
            "storage_key": "mem_003",
            "content": "Test",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": dt,
            "updated_at": dt,
        }
        result = StoredMemory.from_dict(d)
        assert result is not None

    def test_invalid_datetime_string(self):
        d = {
            "storage_key": "mem_004",
            "content": "Test",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": "not a date",
            "updated_at": "not a date",
        }
        result = StoredMemory.from_dict(d)
        assert result is not None

    def test_expires_at_string(self):
        d = {
            "storage_key": "mem_005",
            "content": "Test",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2027-01-01T00:00:00+00:00",
        }
        result = StoredMemory.from_dict(d)
        assert result is not None

    def test_last_accessed_at_string(self):
        d = {
            "storage_key": "mem_006",
            "content": "Test",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "last_accessed_at": "2026-01-02T00:00:00+00:00",
        }
        result = StoredMemory.from_dict(d)
        assert result is not None

    def test_to_dict(self):
        d = {
            "storage_key": "mem_007",
            "content": "Test",
            "type": "user_preference",
            "namespace": "default",
            "confidence": 0.8,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        stored = StoredMemory.from_dict(d)
        result = stored.to_dict()
        assert isinstance(result, dict)
        assert result["content"] == "Test"

    def test_from_memory_entry(self):
        entry = MemoryEntry(
            content="I prefer dark mode",
            type="user_preference",
        )
        stored = StoredMemory.from_memory_entry(entry, storage_key="mem_008")
        assert stored.content == "I prefer dark mode"
        assert stored.storage_key == "mem_008"


class _MinimalAdapter(StorageAdapter):
    """Minimal concrete implementation for testing default behaviours."""

    def __init__(self):
        self._initialized = False
        self._closed = False

    @property
    def name(self) -> str:
        return "test_minimal"

    @property
    def capabilities(self) -> dict:
        return {"read": True, "write": True}

    def initialize(self, config: dict) -> None:
        self._initialized = True

    def remember(self, entry: MemoryEntry) -> StoredMemory:
        return self.store_entry(entry)

    def store_entry(self, entry: MemoryEntry) -> StoredMemory:
        return StoredMemory.from_memory_entry(entry, storage_key=f"key_{id(entry)}")

    def store(self, entry: dict) -> str:
        key = f"store_{id(entry)}"
        return key

    def recall(
        self,
        query: str,
        filters: dict | None = None,
        limit: int = 20,
        update_access: bool = True,
    ) -> list[StoredMemory]:
        return []

    def forget(self, storage_key: str) -> bool:
        return False

    def delete(self, entry_id: str) -> bool:
        return False

    def count(self, filter_: dict | None = None) -> int:
        return 0

    def health_check(self) -> dict:
        return {"status": "ok", "adapter": self.name}

    def close(self) -> None:
        self._closed = True


class TestStorageAdapterDefaults:
    def _make_adapter(self):
        return _MinimalAdapter()

    def test_remember_batch_default(self):
        adapter = self._make_adapter()
        result = adapter.remember_batch([])
        assert isinstance(result, list)

    def test_forget_expired_default(self):
        adapter = self._make_adapter()
        result = adapter.forget_expired()
        assert result == 0

    def test_get_stats_default(self):
        adapter = self._make_adapter()
        result = adapter.get_stats()
        assert isinstance(result, dict)

    def test_get_profile_default(self):
        adapter = self._make_adapter()
        result = adapter.get_profile()
        assert isinstance(result, dict)

    def test_capabilities_default(self):
        adapter = self._make_adapter()
        result = adapter.capabilities
        assert isinstance(result, dict)

    def test_initialize_sets_flag(self):
        adapter = self._make_adapter()
        adapter.initialize({})
        assert adapter._initialized is True

    def test_health_check_returns_dict(self):
        adapter = self._make_adapter()
        result = adapter.health_check()
        assert result["status"] == "ok"

    def test_close_sets_flag(self):
        adapter = self._make_adapter()
        adapter.close()
        assert adapter._closed is True

    def test_count_returns_int(self):
        adapter = self._make_adapter()
        assert adapter.count() == 0


class TestStorageAdapterProtocol:
    """Verify StorageAdapter ABC is compatible with real adapters."""

    def test_protocol_compliance(self):
        adapter = _MinimalAdapter()
        # StorageAdapter is an ABC, so concrete subclasses are instances
        assert isinstance(adapter, StorageAdapter)
