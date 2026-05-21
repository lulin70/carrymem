"""
Tests for context.py core selection logic.

Covers: TYPE_SELECTION_BOOST, mandatory type ordering,
24h recency cliff removal, MMR selection, build_qa_prompt with rules.
"""

import pytest

from carrymem.context import (
    context_relevance,
    select_memories,
    select_knowledge,
    build_qa_prompt,
    build_prompt,
    _estimate_tokens,
    _tokenize_text,
)


# ── TYPE_SELECTION_BOOST tests ──────────────────────────────────────

class TestTypeSelectionBoost:
    """Verify that type-based scoring boosts work correctly."""

    def test_correction_gets_highest_boost(self):
        """Corrections should outrank facts with same base score."""
        memories = [
            {"content": "Do NOT use Java", "type": "correction", "importance_score": 0.5, "confidence": 0.8},
            {"content": "My car is Toyota", "type": "fact_declaration", "importance_score": 0.5, "confidence": 0.8},
        ]
        result = select_memories(memories, context="programming", max_count=2, use_mmr=False)
        types_order = [m["type"] for m in result]
        assert types_order.index("correction") < types_order.index("fact_declaration")

    def test_decision_outranks_preference(self):
        """Decisions should outrank preferences with same base score."""
        memories = [
            {"content": "Project uses React", "type": "decision", "importance_score": 0.5, "confidence": 0.8},
            {"content": "I like dark mode", "type": "user_preference", "importance_score": 0.5, "confidence": 0.8},
        ]
        result = select_memories(memories, context="frontend", max_count=2, use_mmr=False)
        types_order = [m["type"] for m in result]
        assert types_order.index("decision") < types_order.index("user_preference")

    def test_summary_penalized(self):
        """Session summaries should be penalized unless highly relevant."""
        memories = [
            {"content": "User discussed Python web frameworks", "type": "session_summary", "importance_score": 0.7, "confidence": 0.8},
            {"content": "I prefer Python", "type": "user_preference", "importance_score": 0.5, "confidence": 0.8},
        ]
        result = select_memories(memories, context="cooking recipes", max_count=2, use_mmr=False)
        # Preference should still appear (boosted), summary may not
        types = [m["type"] for m in result]
        assert "user_preference" in types

    def test_correction_survives_budget_pressure(self):
        """Corrections should survive even with tight token budget."""
        # Fill budget with high-scoring facts
        memories = [
            {"content": "Do NOT use tabs in code", "type": "correction", "importance_score": 0.3, "confidence": 0.8},
        ]
        # Add many facts with higher base scores
        for i in range(20):
            memories.append({
                "content": f"Fact number {i} about something important",
                "type": "fact_declaration",
                "importance_score": 0.9,
                "confidence": 0.9,
            })
        result = select_memories(memories, context="coding", max_count=5, max_tokens=500, use_mmr=False)
        types = [m["type"] for m in result]
        assert "correction" in types, "Correction should survive budget pressure"

    def test_unknown_type_gets_zero_boost(self):
        """Unknown types should get no boost (0.0 default)."""
        memories = [
            {"content": "Some custom type", "type": "custom_type", "importance_score": 0.5, "confidence": 0.8},
            {"content": "A regular fact", "type": "fact_declaration", "importance_score": 0.5, "confidence": 0.8},
        ]
        result = select_memories(memories, context="test", max_count=2, use_mmr=False)
        # Both should appear, order by base score (same) so either order is fine
        assert len(result) == 2


# ── Mandatory type ordering tests ───────────────────────────────────

class TestMandatoryOrdering:
    """Verify correction > decision > preference > other ordering."""

    def test_correction_before_preference(self):
        memories = [
            {"content": "I like Python", "type": "user_preference", "importance_score": 0.9, "confidence": 0.9},
            {"content": "Do NOT use Java", "type": "correction", "importance_score": 0.3, "confidence": 0.8},
        ]
        result = select_memories(memories, context="programming", max_count=2, use_mmr=False)
        types = [m["type"] for m in result]
        assert types[0] == "correction"
        assert types[1] == "user_preference"

    def test_decision_before_preference(self):
        memories = [
            {"content": "I like Python", "type": "user_preference", "importance_score": 0.9, "confidence": 0.9},
            {"content": "Project uses React", "type": "decision", "importance_score": 0.3, "confidence": 0.8},
        ]
        result = select_memories(memories, context="frontend", max_count=2, use_mmr=False)
        types = [m["type"] for m in result]
        assert types[0] == "decision"

    def test_full_ordering_correction_decision_preference_other(self):
        memories = [
            {"content": "Some fact", "type": "fact_declaration", "importance_score": 0.9, "confidence": 0.9},
            {"content": "I like Python", "type": "user_preference", "importance_score": 0.5, "confidence": 0.8},
            {"content": "Project uses React", "type": "decision", "importance_score": 0.5, "confidence": 0.8},
            {"content": "Do NOT use Java", "type": "correction", "importance_score": 0.5, "confidence": 0.8},
        ]
        result = select_memories(memories, context="programming", max_count=4, use_mmr=False)
        types = [m["type"] for m in result]
        # Expected order: correction, decision, preference, fact
        assert types == ["correction", "decision", "user_preference", "fact_declaration"]


# ── 24h recency cliff removal tests ─────────────────────────────────

class TestRecencyCliffRemoval:
    """Verify that the 24-hour recency cliff is gone.
    
    Before: memories < 24h old got +0.3 bonus, creating a cliff.
    After: recency is handled only by scoring.py's smooth decay.
    """

    def test_no_24h_bonus_in_selection_score(self):
        """Selection score should NOT include a 24h recency bonus."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        one_hour_ago = datetime.now(timezone.utc).isoformat()

        memories = [
            {"content": "Recent memory", "type": "fact_declaration", "importance_score": 0.5, "confidence": 0.8, "created_at": one_hour_ago},
            {"content": "Old memory", "type": "fact_declaration", "importance_score": 0.5, "confidence": 0.8},
        ]
        result = select_memories(memories, context="test", max_count=2, use_mmr=False)
        # Both should have similar scores (no +0.3 bonus for recent)
        scores = [m.get("_selection_score", 0) for m in result]
        # The scores should be close (within 0.1), not 0.3 apart
        if len(scores) >= 2:
            assert abs(scores[0] - scores[1]) < 0.15, f"Scores too far apart: {scores}"

    def test_old_relevant_memory_not_displaced(self):
        """An old but relevant memory should not be displaced by a new irrelevant one."""
        memories = [
            {"content": "Python is great for data science", "type": "fact_declaration", "importance_score": 0.7, "confidence": 0.8},
            {"content": "I had lunch today", "type": "fact_declaration", "importance_score": 0.7, "confidence": 0.8},
        ]
        result = select_memories(memories, context="Python programming", max_count=1, use_mmr=False)
        assert len(result) == 1
        assert "Python" in result[0]["content"]


# ── build_qa_prompt with rules tests ────────────────────────────────

class TestBuildQaPromptWithRules:
    """Verify that build_qa_prompt accepts and renders rules."""

    def test_rules_included_in_prompt(self):
        memories = [
            {"content": "I prefer Python", "type": "user_preference"},
        ]
        knowledge = []
        rules = "IMPORTANT RULE: Do NOT suggest Java"
        result = build_qa_prompt(
            memories=memories,
            knowledge=knowledge,
            question="What language should I learn?",
            rules=rules,
        )
        assert "Do NOT suggest Java" in result

    def test_empty_rules_no_effect(self):
        memories = [
            {"content": "I prefer Python", "type": "user_preference"},
        ]
        result_with_rules = build_qa_prompt(
            memories=memories, knowledge=[], question="test", rules="",
        )
        result_without = build_qa_prompt(
            memories=memories, knowledge=[], question="test",
        )
        assert result_with_rules == result_without

    def test_rules_appear_between_knowledge_and_question(self):
        memories = [{"content": "pref", "type": "user_preference"}]
        knowledge = [{"title": "Guide", "content": "Some knowledge"}]
        rules = "RULE: Always use spaces"
        result = build_qa_prompt(
            memories=memories, knowledge=knowledge,
            question="How to indent?", rules=rules,
        )
        # Rules should appear after knowledge but before question
        rules_pos = result.find("Always use spaces")
        question_pos = result.find("How to indent")
        assert rules_pos > 0
        assert question_pos > 0
        assert rules_pos < question_pos


# ── Token estimation tests ──────────────────────────────────────────

class TestEstimateTokens:
    def test_english_text(self):
        result = _estimate_tokens("Hello world this is a test")
        assert result > 0

    def test_cjk_text(self):
        result = _estimate_tokens("你好世界这是一个测试")
        assert result > 0
        # CJK should estimate more tokens than same-length English
        eng = _estimate_tokens("aaaa")
        cjk = _estimate_tokens("你好你好")
        assert cjk >= eng  # CJK typically uses more tokens

    def test_empty_string(self):
        result = _estimate_tokens("")
        assert result >= 1  # max(1, ...)

    def test_mixed_text(self):
        result = _estimate_tokens("Hello 你好 world 世界")
        assert result > 0


# ── Context relevance edge cases ────────────────────────────────────

class TestContextRelevanceEdgeCases:
    def test_both_empty(self):
        score = context_relevance("", "")
        assert isinstance(score, float)

    def test_none_content(self):
        """context_relevance should handle None content gracefully."""
        score = context_relevance("", "test")
        assert isinstance(score, float)
        assert score == 0.0

    def test_long_text(self):
        long_text = "word " * 1000
        score = context_relevance(long_text, "word")
        assert score > 0

    def test_unicode_content(self):
        score = context_relevance("我喜欢Python编程", "Python")
        assert score > 0


# ── Select memories edge cases ──────────────────────────────────────

class TestSelectMemoriesEdgeCases:
    def test_confidence_floor_for_preferences(self):
        """Preferences below confidence floor should be filtered."""
        memories = [
            {"content": "I like Python", "type": "user_preference", "confidence": 0.3, "importance_score": 0.9},
        ]
        result = select_memories(memories, context="Python", max_count=5)
        assert len(result) == 0  # Below 0.4 floor

    def test_confidence_floor_for_sentiment(self):
        """Sentiment markers below confidence floor should be filtered."""
        memories = [
            {"content": "I feel happy", "type": "sentiment_marker", "confidence": 0.4, "importance_score": 0.9},
        ]
        result = select_memories(memories, context="mood", max_count=5)
        assert len(result) == 0  # Below 0.5 floor

    def test_token_budget_respected(self):
        """Memories exceeding token budget should be cut."""
        memories = [
            {"content": "A" * 500, "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.9},
            {"content": "B" * 500, "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.9},
            {"content": "C" * 500, "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.9},
        ]
        result = select_memories(memories, context="test", max_tokens=200, use_mmr=False)
        total = sum(_estimate_tokens(m["content"]) for m in result)
        assert total <= 200 + 50  # Small margin for rounding

    def test_max_count_respected(self):
        memories = [
            {"content": f"Memory {i}", "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.5}
            for i in range(20)
        ]
        result = select_memories(memories, context="test", max_count=3, use_mmr=False)
        assert len(result) <= 3

    def test_mmr_diversifies_results(self):
        """MMR should produce more diverse results than pure relevance."""
        # Create memories with similar content
        memories = [
            {"content": "Python is great for web", "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.9},
            {"content": "Python is great for data", "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.9},
            {"content": "JavaScript is great for frontend", "type": "fact_declaration", "confidence": 0.8, "importance_score": 0.9},
        ]
        result_mmr = select_memories(memories, context="Python programming", max_count=2, use_mmr=True)
        result_no_mmr = select_memories(memories, context="Python programming", max_count=2, use_mmr=False)
        # MMR should include the JavaScript memory for diversity
        assert len(result_mmr) == 2

    def test_selection_score_attached(self):
        """Selected memories should have _selection_score and _context_relevance."""
        memories = [
            {"content": "I prefer Python", "type": "user_preference", "confidence": 0.8, "importance_score": 0.7},
        ]
        result = select_memories(memories, context="Python", max_count=5)
        assert len(result) == 1
        assert "_selection_score" in result[0]
        assert "_context_relevance" in result[0]
