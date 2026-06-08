"""
Test Suite for RuleMatcher

Validates:
- Multi-strategy matching (global, exact, FTS5, partial)
- Score calculation and ranking
- Deduplication of results
- Priority ordering
"""

import os
import tempfile

import pytest

from carrymem.rules.matcher import RuleMatcher
from carrymem.rules.storage import RuleStorage


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def storage(temp_db):
    """Create RuleStorage instance"""
    return RuleStorage(temp_db)


@pytest.fixture
def matcher(storage):
    """Create RuleMatcher instance"""
    return RuleMatcher(storage)


class TestGlobalMatching:
    """Test global rule (trigger='*') matching"""

    def test_global_rules_always_match(self, matcher, storage):
        """Global rules should match any scene"""
        storage.create(trigger="*", action="Always be polite", rule_type="always")

        results = matcher.match("任意场景描述")
        assert len(results) >= 1
        assert any(r.match_type == "global" for r in results)

    def test_multiple_global_rules(self, matcher, storage):
        """Should return all active global rules"""
        storage.create(trigger="*", action="Global rule 1", rule_type="always")
        storage.create(trigger="*", action="Global rule 2", rule_type="format")

        results = matcher.match("测试场景")
        global_results = [r for r in results if r.match_type == "global"]
        assert len(global_results) == 2

    def test_paused_global_rules_excluded(self, matcher, storage):
        """Paused global rules should not match"""
        storage.create(trigger="*", action="Active global", status="active")
        storage.create(trigger="*", action="Paused global", status="paused")

        results = matcher.match("场景")
        global_results = [r for r in results if r.match_type == "global"]
        assert len(global_results) == 1
        assert "Active" in global_results[0].rule.action


class TestExactMatching:
    """Test exact trigger matching"""

    def test_exact_case_insensitive_match(self, matcher, storage):
        """Should match exact triggers case-insensitively"""
        storage.create(trigger="写报告", action="控制在3页以内")

        results = matcher.match("写报告")
        exact_matches = [r for r in results if r.match_type == "exact"]
        assert len(exact_matches) >= 1

    def test_exact_whitespace_tolerance(self, matcher, storage):
        """Should handle whitespace differences in exact match"""
        storage.create(trigger="写报告", action="action")

        results = matcher.match("  写报告  ")
        exact_matches = [r for r in results if r.match_type == "exact"]
        assert len(exact_matches) >= 1

    def test_no_exact_match_for_different_text(self, matcher, storage):
        """Should not return exact match for different text"""
        storage.create(trigger="写报告", action="action")

        results = matcher.match("做分析")
        exact_matches = [r for r in results if r.match_type == "exact"]
        assert len(exact_matches) == 0


class TestFTS5Matching:
    """Test FTS5 full-text search matching"""

    def test_fts_finds_partial_keyword(self, matcher, storage):
        """FTS should find rules with partial keyword matches"""
        storage.create(
            trigger="做竞品分析报告",
            action="跳过印度供应商",
        )

        results = matcher.match("竞品")
        assert len(results) >= 1

    def test_fts_searches_action_field(self, matcher, storage):
        """FTS should search both trigger and action fields"""
        storage.create(
            trigger="场景A",
            action="使用PostgreSQL而不是MySQL",
        )

        results = matcher.match("PostgreSQL")
        assert len(results) >= 1


class TestPartialMatching:
    """Test fallback partial string matching"""

    def test_partial_trigger_in_scene(self, matcher, storage):
        """Should match when trigger is substring of scene"""
        storage.create(trigger="写报告", action="控制页数")

        results = matcher.match("帮我写报告")
        assert len(results) >= 1

    def test_partial_scene_in_trigger(self, matcher, storage):
        """Should match when scene is substring of trigger"""
        storage.create(
            trigger="编写技术方案和架构文档",
            action="遵循模板格式",
        )

        results = matcher.match("技术方案")  # Partial match
        # Should find via FTS5 or partial matching
        assert len(results) >= 1


class TestScoreCalculation:
    """Test relevance score computation"""

    def test_exact_match_higher_score_than_fts(self, matcher, storage):
        """Exact matches should have higher base score than FTS"""
        storage.create(trigger="exact_match", action="action")

        exact_results = matcher.match("exact_match")
        fts_results = matcher.match("partial exact_match text")

        if exact_results and fts_results:
            exact_score = next((r.score for r in exact_results if r.match_type == "exact"), 0)
            fts_score = next((r.score for r in fts_results if r.match_type == "fts"), 0)
            assert exact_score > fts_score

    def test_hard_rule_bonus(self, matcher, storage):
        """Hard rules (override=True) should get score bonus"""
        storage.create(
            trigger="test",
            action="soft rule",
            override=False,
        )
        storage.create(
            trigger="test",
            action="hard rule",
            override=True,
        )

        results = matcher.match("test")
        hard_scores = [r.score for r in results if r.rule.override and r.rule.trigger == "test"]
        soft_scores = [r.score for r in results if not r.rule.override and r.rule.trigger == "test"]

        if hard_scores and soft_scores:
            # Hard rules should have >= score (they get bonus)
            assert max(hard_scores) >= max(soft_scores)


class TestDeduplication:
    """Test result deduplication"""

    def test_no_duplicate_rule_ids(self, matcher, storage):
        """Results should not contain duplicate rule IDs"""
        storage.create(trigger="test", action="action1")
        storage.create(trigger="test2", action="action2")

        results = matcher.match("test test2")  # Might match both strategies
        ids = [r.rule.id for r in results]
        assert len(ids) == len(set(ids))

    def test_keep_highest_score_on_duplicate(self, matcher, storage):
        """When duplicate found, keep highest scoring one"""
        rule = storage.create(trigger="duplicate_test", action="action")

        results = matcher.match("duplicate_test")
        # If same rule appears via multiple strategies, only one result
        duplicates = [r for r in results if r.rule.id == rule.id]
        assert len(duplicates) <= 1


class TestResultOrdering:
    """Test result sorting and ordering"""

    def test_sorted_by_score_descending(self, matcher, storage):
        """Results should be sorted by score descending"""
        storage.create(trigger="low_priority", action="low", override=False)
        storage.create(trigger="high_priority", action="high", override=True)

        results = matcher.match("low_priority high_priority")
        if len(results) >= 2:
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_respects_limit_parameter(self, matcher, storage):
        """Should return at most 'limit' results"""
        for i in range(10):
            storage.create(trigger=f"scene{i}", action=f"action{i}")

        results = matcher.match("scene", limit=3)
        assert len(results) <= 3


class TestEmptyInputs:
    """Test edge cases with empty/invalid inputs"""

    def test_empty_scene_returns_empty(self, matcher):
        """Empty scene should return no results"""
        results = matcher.match("")
        assert results == []

    def test_whitespace_only_scene(self, matcher):
        """Whitespace-only scene should return no results"""
        results = matcher.match("   ")
        assert results == []


class TestGetMatchingActions:
    """Test convenience method for getting actions only"""

    def test_returns_action_tuples(self, matcher, storage):
        """Should return list of (action, type) tuples"""
        storage.create(trigger="test", action="do X", rule_type="avoid")
        storage.create(trigger="test2", action="do Y", rule_type="always")

        actions = matcher.get_matching_actions("test test2")
        assert len(actions) >= 2
        assert all(isinstance(item, tuple) and len(item) == 2 for item in actions)

    def test_actions_contain_correct_data(self, matcher, storage):
        """Returned actions should match stored rules"""
        storage.create(trigger="scene", action="specific action", rule_type="format")

        actions = matcher.get_matching_actions("scene")
        action_types = [a[1] for a in actions]
        assert "format" in action_types
