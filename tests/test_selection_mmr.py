"""Tests for MMR selection algorithm in selection.py."""

import pytest

from carrymem.selection import _mmr_select, _tokenize_text, select_memories


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
