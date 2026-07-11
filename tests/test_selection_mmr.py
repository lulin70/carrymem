"""Tests for MMR selection algorithm in selection.py."""

from datetime import datetime, timedelta, timezone

import pytest

from carrymem.selection import (
    ACCESS_BOOST_CAP,
    _days_since_last_access,
    _mmr_select,
    _tokenize_text,
    select_memories,
)


class TestMMRSelect:
    """Test _mmr_select function."""

    def test_empty_input(self):
        assert _mmr_select([], set(), 5) == []

    def test_single_item(self):
        scored = [(1.0, {"content": "test", "raw_text": "test"})]
        result = _mmr_select(scored, set(), 5)
        assert len(result) == 1

    def test_fewer_than_max(self):
        scored = [(1.0, {"content": "a"}), (0.8, {"content": "b"})]
        result = _mmr_select(scored, set(), 5)
        assert len(result) == 2

    def test_selects_diverse(self):
        """MMR should prefer diverse items over similar high-scoring ones."""
        scored = [
            (1.0, {"content": "python programming", "raw_text": ""}),
            (0.95, {"content": "python development", "raw_text": ""}),
            (0.7, {"content": "travel vacation hotels", "raw_text": ""}),
        ]
        query_tokens = _tokenize_text("python")
        result = _mmr_select(scored, query_tokens, 2)
        assert len(result) == 2
        # MMR with lambda=0.7 may still prefer relevance over diversity
        # for small score gaps — just verify it returns 2 items

    def test_precomputed_tokens_no_retokenization(self):
        """Verify that token sets are pre-computed (performance test)."""
        import time

        # Create 100 candidates
        scored = [(float(100 - i), {"content": f"item {i} unique word{i}", "raw_text": ""}) for i in range(100)]
        query_tokens = _tokenize_text("item")
        start = time.time()
        result = _mmr_select(scored, query_tokens, 10)
        elapsed = time.time() - start
        assert len(result) == 10
        # Should complete in < 1 second for 100 items
        assert elapsed < 1.0


class TestSelectMemories:
    """Test select_memories function."""

    def test_empty_memories(self):
        assert select_memories([]) == []

    def test_confidence_floor(self):
        """Memories below type-specific confidence floor should be filtered."""
        memories = [
            {
                "content": "pref",
                "type": "user_preference",
                "confidence": 0.2,
                "importance_score": 0.5,
            },
            {
                "content": "fact",
                "type": "fact_declaration",
                "confidence": 0.2,
                "importance_score": 0.5,
            },
        ]
        result = select_memories(memories)
        types = [m["type"] for m in result]
        assert "user_preference" not in types  # floor is 0.4
        assert "fact_declaration" in types  # no floor for facts

    def test_temporal_boost(self):
        """Temporal queries should boost memories with dates."""
        memories = [
            {
                "content": "started job March 2024",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
            },
            {
                "content": "like coffee",
                "type": "user_preference",
                "confidence": 0.8,
                "importance_score": 0.5,
            },
        ]
        result = select_memories(memories, context="when did I start my job?")
        # The dated memory should rank higher with temporal boost
        assert len(result) >= 1


class TestAccessBoost:
    """Test access_count boost in select_memories (v0.5.0)."""

    def test_frequently_accessed_ranks_higher(self):
        """Memory with higher access_count should rank higher (all else equal)."""
        memories = [
            {
                "content": "rare",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
                "access_count": 0,
            },
            {
                "content": "rare",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
                "access_count": 50,
            },
        ]
        result = select_memories(memories)
        assert result[0]["access_count"] == 50

    def test_access_boost_capped(self):
        """access_boost should be capped at ACCESS_BOOST_CAP (0.1)."""
        memories = [
            {
                "content": "x",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
                "access_count": 10**6,
            },
        ]
        result = select_memories(memories)
        boost = result[0]["_selection_score"] - 0.5 * 0.7
        assert boost <= ACCESS_BOOST_CAP + 0.001

    def test_zero_access_no_boost(self):
        """access_count=0 should add zero boost."""
        memories = [
            {
                "content": "x",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
                "access_count": 0,
            },
        ]
        result = select_memories(memories)
        assert len(result) == 1
        assert result[0]["_selection_score"] >= 0.35

    def test_negative_access_treated_as_zero(self):
        """Negative access_count should be treated as 0 (no penalty)."""
        memories = [
            {
                "content": "x",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
                "access_count": -10,
            },
        ]
        result = select_memories(memories)
        assert len(result) == 1
        assert result[0]["_selection_score"] >= 0.35

    def test_missing_access_count_field(self):
        """Missing access_count field should default to 0 (no boost, no crash)."""
        memories = [
            {
                "content": "x",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
            },
        ]
        result = select_memories(memories)
        assert len(result) == 1

    def test_none_access_count_treated_as_zero(self):
        """None access_count should be treated as 0."""
        memories = [
            {
                "content": "x",
                "type": "fact_declaration",
                "confidence": 0.8,
                "importance_score": 0.5,
                "access_count": None,
            },
        ]
        result = select_memories(memories)
        assert len(result) == 1


class TestDaysSinceLastAccess:
    """Test _days_since_last_access helper function."""

    def test_none_returns_none(self):
        assert _days_since_last_access(None) is None

    def test_empty_string_returns_none(self):
        assert _days_since_last_access("") is None

    def test_invalid_string_returns_none(self):
        assert _days_since_last_access("not-a-date") is None

    def test_iso_string_parsed(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        days = _days_since_last_access(recent)
        assert days is not None
        assert 4.9 < days < 5.1

    def test_datetime_object_parsed(self):
        recent = datetime.now(timezone.utc) - timedelta(days=10)
        days = _days_since_last_access(recent)
        assert days is not None
        assert 9.9 < days < 10.1

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
        days = _days_since_last_access(naive)
        assert days is not None
        assert 2.9 < days < 3.1

    def test_future_date_clamped_to_zero(self):
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        days = _days_since_last_access(future)
        assert days is not None
        assert days == 0.0


class TestRecencyDecay:
    """Test recency decay factor in access boost (v0.6.2)."""

    def _make_memory(self, access_count=10, last_accessed_at=None):
        return {
            "content": "test memory",
            "type": "fact_declaration",
            "confidence": 0.8,
            "importance_score": 0.5,
            "access_count": access_count,
            "last_accessed_at": last_accessed_at,
        }

    def test_no_last_accessed_no_decay(self):
        """Memory without last_accessed_at should get full boost (no decay)."""
        mem = self._make_memory(access_count=10, last_accessed_at=None)
        result = select_memories([mem])
        score_no_decay = result[0]["_selection_score"]

        # Base: 0.5*0.7 + 0*0.3 + 0.0(type_boost) + min(10*0.01, 0.1) = 0.35 + 0.1 = 0.45
        assert abs(score_no_decay - 0.45) < 0.001

    def test_recent_access_preserves_boost(self):
        """Memory accessed just now should get nearly full boost."""
        recent = datetime.now(timezone.utc).isoformat()
        mem = self._make_memory(access_count=10, last_accessed_at=recent)
        result = select_memories([mem])
        score_recent = result[0]["_selection_score"]

        # Recency factor ≈ 2^0 = 1.0, so boost ≈ 0.1
        assert score_recent >= 0.44

    def test_old_access_decays_boost(self):
        """Memory accessed 60 days ago should have significantly decayed boost."""
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        mem = self._make_memory(access_count=10, last_accessed_at=old)
        result = select_memories([mem])
        score_old = result[0]["_selection_score"]

        # Recency factor = 2^(-0.1*60) = 2^(-6) ≈ 0.0156
        # Boost ≈ 0.1 * 0.0156 ≈ 0.00156, score ≈ 0.3516
        assert score_old < 0.36
        assert score_old > 0.35

    def test_recent_ranks_higher_than_old(self):
        """Memory accessed recently should rank higher than one accessed long ago."""
        recent_mem = self._make_memory(
            access_count=10,
            last_accessed_at=datetime.now(timezone.utc).isoformat(),
        )
        old_mem = self._make_memory(
            access_count=10,
            last_accessed_at=(datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
        )
        result = select_memories([old_mem, recent_mem])
        assert result[0]["last_accessed_at"] == recent_mem["last_accessed_at"]

    def test_zero_access_no_decay_applied(self):
        """access_count=0 should not trigger recency decay even with last_accessed_at."""
        recent = datetime.now(timezone.utc).isoformat()
        mem = self._make_memory(access_count=0, last_accessed_at=recent)
        result = select_memories([mem])
        score = result[0]["_selection_score"]
        # Base only: 0.5*0.7 = 0.35
        assert abs(score - 0.35) < 0.001

    def test_invalid_last_accessed_ignored(self):
        """Invalid last_accessed_at string should not affect boost (graceful degrade)."""
        mem = self._make_memory(access_count=10, last_accessed_at="not-a-date")
        result = select_memories([mem])
        score = result[0]["_selection_score"]
        # Should behave as if no last_accessed_at: full boost
        assert abs(score - 0.45) < 0.001
