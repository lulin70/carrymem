"""
Tests for base adapter module.

Covers: StoredMemory.from_dict, StorageAdapter base defaults,
MemoryEntry.
"""

import pytest
from datetime import datetime, timezone
from dataclasses import dataclass

from memory_classification_engine.adapters.base import (
    MemoryEntry,
    StoredMemory,
    StorageAdapter,
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
        stored = StoredMemory.from_memory_entry(
            entry, storage_key="mem_008"
        )
        assert stored.content == "I prefer dark mode"
        assert stored.storage_key == "mem_008"


class TestStorageAdapterDefaults:
    def _make_adapter(self):
        class TestAdapter(StorageAdapter):
            def remember(self, entry):
                return None
            def recall(self, query, **kwargs):
                return []
            def forget(self, storage_key):
                return False
            @property
            def name(self):
                return "test"

        return TestAdapter()

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
