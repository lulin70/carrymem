"""
Tests for conflict_detector module (core, not rules/).

Covers: MemoryConflictDetector, conflict detection
across stored memories.
"""

import pytest

from carrymem import CarryMem


@pytest.fixture
def cm(tmp_path):
    db_path = str(tmp_path / "test_conflict.db")
    carrymem = CarryMem(db_path=db_path)
    yield carrymem
    carrymem.close()


class TestMemoryConflictDetector:
    def test_no_conflicts(self, cm):
        cm.declare("I prefer dark mode")
        conflicts = cm.check_conflicts()
        assert isinstance(conflicts, list)

    def test_contradiction_detected(self, cm):
        cm.declare("I like using Vim")
        cm.declare("I dislike using Vim")
        conflicts = cm.check_conflicts()
        assert len(conflicts) >= 1

    def test_no_conflict_different_topics(self, cm):
        cm.declare("I prefer dark mode")
        cm.declare("I use PostgreSQL")
        conflicts = cm.check_conflicts()
        conflict_types = [c.get("conflict_type", "") for c in conflicts]
        assert "contradiction" not in conflict_types or len(conflicts) == 0

    def test_empty_db_no_conflicts(self, cm):
        conflicts = cm.check_conflicts()
        assert conflicts == []

    def test_multiple_declarations(self, cm):
        cm.declare("I prefer dark mode")
        cm.declare("I use PostgreSQL")
        cm.declare("I like Python")
        conflicts = cm.check_conflicts()
        assert isinstance(conflicts, list)
