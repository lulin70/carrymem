"""
Tests for conflict_detector module.

Covers: ConflictDetector,
contradiction detection, duplicate detection,
outdated detection, preference change detection.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from carrymem.conflict_detector import (
    ConflictDetector,
    MemoryConflict,
    ConflictType,
    ConflictSeverity,
)
from carrymem.adapters.base import StoredMemory


def make_stored(
    content="I prefer dark mode",
    memory_type="user_preference",
    namespace="default",
    confidence=0.8,
    created_at=None,
    storage_key=None,
):
    return StoredMemory(
        storage_key=storage_key or f"mem_{id(content)}",
        content=content,
        type=memory_type,
        namespace=namespace,
        confidence=confidence,
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=created_at or datetime.now(timezone.utc),
        source_layer="declaration",
        tier=2,
        access_count=0,
        importance_score=0.5,
        version=1,
    )


class TestConflictDetector:
    def test_init(self):
        detector = ConflictDetector()
        assert detector is not None

    def test_detect_no_conflicts(self):
        detector = ConflictDetector()
        memories = [make_stored(content="I prefer dark mode")]
        conflicts = detector.detect_conflicts(memories)
        assert isinstance(conflicts, list)

    def test_detect_contradictions(self):
        detector = ConflictDetector()
        memories = [
            make_stored(content="I like using Vim", storage_key="k1"),
            make_stored(content="I dislike using Vim", storage_key="k2"),
        ]
        conflicts = detector.detect_conflicts(memories)
        assert len(conflicts) >= 1

    def test_detect_duplicates(self):
        detector = ConflictDetector()
        memories = [
            make_stored(content="I prefer dark mode", storage_key="k1"),
            make_stored(content="I prefer dark mode", storage_key="k2"),
        ]
        conflicts = detector.detect_conflicts(memories)
        assert len(conflicts) >= 1

    def test_detect_with_namespace_filter(self):
        detector = ConflictDetector()
        memories = [
            make_stored(content="I like Vim", namespace="work", storage_key="k1"),
            make_stored(content="I dislike Vim", namespace="personal", storage_key="k2"),
        ]
        conflicts = detector.detect_conflicts(memories, namespace="work")
        assert isinstance(conflicts, list)

    def test_empty_memories(self):
        detector = ConflictDetector()
        conflicts = detector.detect_conflicts([])
        assert conflicts == []

    def test_normalize_dt_none(self):
        detector = ConflictDetector()
        result = detector._normalize_dt(None)
        assert result == datetime.min.replace(tzinfo=timezone.utc)

    def test_normalize_dt_naive_datetime(self):
        detector = ConflictDetector()
        dt = datetime(2026, 1, 1)
        result = detector._normalize_dt(dt)
        assert result.tzinfo == timezone.utc

    def test_normalize_dt_aware_datetime(self):
        detector = ConflictDetector()
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = detector._normalize_dt(dt)
        assert result == dt

    def test_normalize_dt_string(self):
        detector = ConflictDetector()
        result = detector._normalize_dt("2026-01-01T00:00:00+00:00")
        assert isinstance(result, datetime)

    def test_normalize_dt_invalid_string(self):
        detector = ConflictDetector()
        result = detector._normalize_dt("not a date")
        assert isinstance(result, datetime)

    def test_are_contradictory_different_namespace(self):
        detector = ConflictDetector()
        m1 = make_stored(namespace="work")
        m2 = make_stored(namespace="personal")
        result = detector._are_contradictory(m1, m2)
        assert result is False

    def test_are_contradictory_different_type(self):
        detector = ConflictDetector()
        m1 = make_stored(memory_type="user_preference")
        m2 = make_stored(memory_type="decision")
        result = detector._are_contradictory(m1, m2)
        assert result is False

    def test_supersedes_different_namespace(self):
        detector = ConflictDetector()
        m1 = make_stored(namespace="work")
        m2 = make_stored(namespace="personal")
        result = detector._supersedes(m1, m2)
        assert result is False

    def test_supersedes_different_type(self):
        detector = ConflictDetector()
        m1 = make_stored(memory_type="user_preference")
        m2 = make_stored(memory_type="decision")
        result = detector._supersedes(m1, m2)
        assert result is False

    def test_supersedes_no_created_at(self):
        detector = ConflictDetector()
        m1 = make_stored()
        m1.created_at = None
        m2 = make_stored()
        m2.created_at = None
        result = detector._supersedes(m1, m2)
        assert result is False

    def test_calculate_similarity_empty(self):
        detector = ConflictDetector()
        m1 = make_stored(content="")
        m2 = make_stored(content="test")
        result = detector._calculate_similarity(m1, m2)
        assert isinstance(result, float)
        assert result == 0.0

    def test_calculate_similarity_same(self):
        detector = ConflictDetector()
        m1 = make_stored(content="dark mode")
        m2 = make_stored(content="dark mode")
        result = detector._calculate_similarity(m1, m2)
        assert isinstance(result, float)
        assert result > 0

    def test_group_similar_preferences(self):
        detector = ConflictDetector()
        prefs = [
            make_stored(content="I prefer dark mode for editors"),
            make_stored(content="I prefer dark mode for IDEs"),
        ]
        groups = detector._group_similar_preferences(prefs)
        assert isinstance(groups, list)

    def test_detect_outdated(self):
        detector = ConflictDetector()
        old = make_stored(
            content="I use MySQL",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            storage_key="old",
        )
        new = make_stored(
            content="I use PostgreSQL now",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            storage_key="new",
        )
        memories = [old, new]
        conflicts = detector._detect_outdated(memories)
        assert isinstance(conflicts, list)

    def test_detect_preference_changes(self):
        detector = ConflictDetector()
        memories = [
            make_stored(content="I prefer dark mode for VS Code"),
            make_stored(content="I prefer dark mode for Vim"),
        ]
        conflicts = detector._detect_preference_changes(memories)
        assert isinstance(conflicts, list)


class TestMemoryConflict:
    def test_init(self):
        memories = [make_stored(storage_key="k1"), make_stored(storage_key="k2")]
        c = MemoryConflict(
            conflict_type=ConflictType.DUPLICATE,
            severity=ConflictSeverity.LOW,
            memories=memories,
            reason="Test conflict",
        )
        assert c.conflict_type == ConflictType.DUPLICATE

    def test_to_dict(self):
        memories = [make_stored(storage_key="k1"), make_stored(storage_key="k2")]
        c = MemoryConflict(
            conflict_type=ConflictType.DUPLICATE,
            severity=ConflictSeverity.LOW,
            memories=memories,
            reason="Test",
        )
        d = c.to_dict()
        assert isinstance(d, dict)
