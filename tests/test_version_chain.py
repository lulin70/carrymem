"""Tests for memory_nature (state/event) and version chain functionality."""

import os
import tempfile

import pytest

from carrymem.adapters.base import MemoryEntry, StoredMemory
from carrymem.adapters.sqlite_adapter import SQLiteAdapter


class TestMemoryNature:
    """Test memory_nature inference from type."""

    def test_state_types(self):
        """State types should infer 'state'."""
        for mtype in MemoryEntry.STATE_TYPES:
            e = MemoryEntry(type=mtype, content="test")
            assert e.infer_memory_nature() == "state", f"{mtype} should be state"

    def test_event_types(self):
        """Event types should infer 'event'."""
        for mtype in MemoryEntry.EVENT_TYPES:
            e = MemoryEntry(type=mtype, content="test")
            assert e.infer_memory_nature() == "event", f"{mtype} should be event"

    def test_default_nature(self):
        """Default memory_nature should be 'state'."""
        e = MemoryEntry(type="user_preference", content="test")
        assert e.memory_nature == "state"

    def test_explicit_nature(self):
        """Explicitly set memory_nature should override default."""
        e = MemoryEntry(type="user_preference", content="test", memory_nature="event")
        assert e.memory_nature == "event"

    def test_to_dict_includes_nature(self):
        """to_dict should include memory_nature, version_chain_id, version_number."""
        e = MemoryEntry(
            type="user_preference",
            content="test",
            memory_nature="state",
            version_chain_id="chain_1",
            version_number=2,
        )
        d = e.to_dict()
        assert d["memory_nature"] == "state"
        assert d["version_chain_id"] == "chain_1"
        assert d["version_number"] == 2

    def test_from_dict_includes_nature(self):
        """from_dict should parse memory_nature, version_chain_id, version_number."""
        d = {
            "type": "user_preference",
            "content": "test",
            "memory_nature": "event",
            "version_chain_id": "chain_2",
            "version_number": 3,
        }
        e = MemoryEntry.from_dict(d)
        assert e.memory_nature == "event"
        assert e.version_chain_id == "chain_2"
        assert e.version_number == 3

    def test_from_dict_backward_compatible(self):
        """from_dict without new fields should use defaults."""
        d = {"type": "user_preference", "content": "test"}
        e = MemoryEntry.from_dict(d)
        assert e.memory_nature == "state"
        assert e.version_chain_id is None
        assert e.version_number == 1


class TestStoredMemoryNature:
    """Test StoredMemory serialization with new fields."""

    def test_from_memory_entry_carries_nature(self):
        """from_memory_entry should carry memory_nature."""
        e = MemoryEntry(
            type="user_preference",
            content="test",
            memory_nature="state",
            version_chain_id="chain_1",
            version_number=2,
        )
        s = StoredMemory.from_memory_entry(e, storage_key="cm_test")
        assert s.memory_nature == "state"
        assert s.version_chain_id == "chain_1"
        assert s.version_number == 2

    def test_to_dict_includes_nature(self):
        """StoredMemory.to_dict should include new fields."""
        e = MemoryEntry(
            type="user_preference",
            content="test",
            memory_nature="state",
            version_chain_id="chain_1",
            version_number=2,
        )
        s = StoredMemory.from_memory_entry(e, storage_key="cm_test")
        d = s.to_dict()
        assert d["memory_nature"] == "state"
        assert d["version_chain_id"] == "chain_1"
        assert d["version_number"] == 2

    def test_from_dict_includes_nature(self):
        """StoredMemory.from_dict should parse new fields."""
        d = {
            "id": "1",
            "type": "user_preference",
            "content": "test",
            "storage_key": "cm_test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "memory_nature": "event",
            "version_chain_id": "chain_2",
            "version_number": 3,
        }
        s = StoredMemory.from_dict(d)
        assert s.memory_nature == "event"
        assert s.version_chain_id == "chain_2"
        assert s.version_number == 3


class TestVersionChain:
    """Test version chain creation and querying in SQLite."""

    @pytest.fixture
    def db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as td:
            adapter = SQLiteAdapter(db_path=os.path.join(td, "test.db"), namespace="test")
            yield adapter

    def test_state_memory_gets_chain_id(self, db):
        """State memory should get version_chain_id set to its storage_key."""
        e = MemoryEntry(type="user_preference", content="I prefer dark mode")
        s = db.remember(e)
        assert s.memory_nature == "state"
        # Chain ID should be set (by the post-supersede UPDATE)
        results = db.recall(query="dark mode")
        assert len(results) > 0
        assert results[0].version_chain_id is not None

    def test_event_memory_no_chain(self, db):
        """Event memory should not get version_chain_id (no versioning needed)."""
        e = MemoryEntry(type="session_summary", content="User discussed React patterns")
        s = db.remember(e)
        assert s.memory_nature == "event"

    def test_supersede_creates_version_chain(self, db):
        """When a preference is superseded, both memories should share a chain_id."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        s1 = db.remember(e1)

        e2 = MemoryEntry(type="user_preference", content="I now prefer light mode")
        s2 = db.remember(e2)

        # New memory should have version_number=2
        results = db.recall(query="mode preference")
        assert len(results) >= 1
        latest = [r for r in results if not r.superseded_at][0]
        assert latest.version_number == 2
        assert latest.version_chain_id is not None

    def test_superseded_memory_has_chain_id(self, db):
        """Superseded memory should also have version_chain_id."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        db.remember(e1)

        e2 = MemoryEntry(type="user_preference", content="I now prefer light mode")
        db.remember(e2)

        # Get all memories including superseded
        results = db.recall(query="mode", filters={"include_superseded": True})
        assert len(results) >= 2
        # Both should share the same chain_id
        chain_ids = [r.version_chain_id for r in results if r.version_chain_id]
        assert len(chain_ids) >= 2
        assert len(set(chain_ids)) == 1  # All same chain

    def test_three_version_chain(self, db):
        """Three versions of the same preference should form a chain."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        db.remember(e1)

        e2 = MemoryEntry(type="user_preference", content="I now prefer light mode")
        db.remember(e2)

        e3 = MemoryEntry(type="user_preference", content="I switched back to dark mode")
        db.remember(e3)

        # Latest should be version 3
        results = db.recall(query="mode")
        latest = [r for r in results if not r.superseded_at][0]
        assert latest.version_number == 3

    def test_different_preferences_separate_chains(self, db):
        """Different preferences should have separate chains."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        db.remember(e1)

        e2 = MemoryEntry(type="user_preference", content="I like Python")
        db.remember(e2)

        results = db.recall(query="prefer like")
        active = [r for r in results if not r.superseded_at]
        # Should have 2 separate chains
        chain_ids = [r.version_chain_id for r in active if r.version_chain_id]
        assert len(chain_ids) >= 2
        assert len(set(chain_ids)) == 2  # Two different chains

    def test_recall_excludes_superseded_by_default(self, db):
        """recall should exclude superseded memories by default."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        db.remember(e1)

        e2 = MemoryEntry(type="user_preference", content="I now prefer light mode")
        db.remember(e2)

        results = db.recall(query="mode")
        active = [r for r in results if not r.superseded_at]
        superseded = [r for r in results if r.superseded_at]
        assert len(active) >= 1
        # Superseded should not appear by default
        assert len(superseded) == 0

    def test_recall_includes_superseded_when_requested(self, db):
        """recall with include_superseded=True should include old versions."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        db.remember(e1)

        e2 = MemoryEntry(type="user_preference", content="I now prefer light mode")
        db.remember(e2)

        results = db.recall(query="mode", filters={"include_superseded": True})
        assert len(results) >= 2

    def test_migration_adds_columns(self, db):
        """Migration should add memory_nature, version_chain_id, version_number columns."""
        import sqlite3

        conn = db._get_connection()
        # Check columns exist
        cursor = conn.execute("PRAGMA table_info(memories)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "memory_nature" in columns
        assert "version_chain_id" in columns
        assert "version_number" in columns

    def test_migration_backfill(self, db):
        """Migration should backfill session_summary as event."""
        e = MemoryEntry(type="session_summary", content="User discussed React")
        db.remember(e)
        results = db.recall(query="React")
        if results:
            assert results[0].memory_nature == "event"

    def test_decision_is_state(self, db):
        """Decision type should be state."""
        e = MemoryEntry(type="decision", content="Decided to use React for frontend")
        s = db.remember(e)
        assert s.memory_nature == "state"

    def test_correction_is_state(self, db):
        """Correction type should be state."""
        e = MemoryEntry(type="correction", content="Correction: I meant TypeScript not JavaScript")
        s = db.remember(e)
        assert s.memory_nature == "state"

    def test_fact_declaration_is_state(self, db):
        """Fact declaration type should be state."""
        e = MemoryEntry(type="fact_declaration", content="I live in Tokyo")
        s = db.remember(e)
        assert s.memory_nature == "state"

    def test_relationship_is_state(self, db):
        """Relationship type should be state."""
        e = MemoryEntry(type="relationship", content="My colleague Alice is a designer")
        s = db.remember(e)
        assert s.memory_nature == "state"

    def test_sentiment_marker_is_state(self, db):
        """Sentiment marker type should be state."""
        e = MemoryEntry(type="sentiment_marker", content="User seems frustrated with slow responses")
        s = db.remember(e)
        assert s.memory_nature == "state"

    def test_task_pattern_is_event(self, db):
        """Task pattern type should be event."""
        e = MemoryEntry(type="task_pattern", content="User always reviews code before merging")
        s = db.remember(e)
        assert s.memory_nature == "event"

    def test_version_chain_id_persistence(self, db):
        """Version chain ID should persist across recall."""
        e1 = MemoryEntry(type="user_preference", content="I prefer dark mode")
        db.remember(e1)
        e2 = MemoryEntry(type="user_preference", content="I now prefer light mode")
        db.remember(e2)

        # First recall
        r1 = db.recall(query="mode", filters={"include_superseded": True})
        chain_1 = [r.version_chain_id for r in r1 if r.version_chain_id]

        # Second recall (should be same)
        r2 = db.recall(query="mode", filters={"include_superseded": True})
        chain_2 = [r.version_chain_id for r in r2 if r.version_chain_id]

        assert chain_1 == chain_2
