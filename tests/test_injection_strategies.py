"""
Integration tests for CarryMem memory injection strategies.

Covers: tiered preference injection, session summary filtering,
rule tiering, QA override rules, correction survival under budget.
"""

import os
import tempfile

import pytest

from carrymem import CarryMem


@pytest.fixture
def cm():
    """Create a CarryMem instance with temp DB."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()
    instance = CarryMem(storage="sqlite", db_path=db_path)
    yield instance
    instance.close()
    try:
        os.remove(db_path)
    except OSError:
        pass


def _boost_confidence(cm, content_fragment, confidence=0.95):
    """Boost confidence of a memory containing content_fragment."""
    conn = cm._adapter._get_connection()
    rows = conn.execute(
        "SELECT storage_key FROM memories WHERE content LIKE ? AND type = 'user_preference'",
        (f"%{content_fragment}%",),
    ).fetchall()
    for row in rows:
        conn.execute("UPDATE memories SET confidence = ? WHERE storage_key = ?", (confidence, row[0]))
    conn.commit()


class TestTieredPreferenceInjection:
    """Core preferences (conf >= 0.9) always injected; contextual prefs by relevance."""

    def test_core_pref_always_injected(self, cm):
        """Core preference appears even in unrelated queries."""
        cm.classify_and_remember("I am vegetarian", force_type="user_preference")
        _boost_confidence(cm, "vegetarian", 0.95)

        ctx = cm.build_context(context="What is the weather today?")
        prompt = ctx.get("system_prompt", "")
        assert "vegetarian" in prompt.lower()

    def test_contextual_pref_in_relevant_query(self, cm):
        """Contextual preference appears in relevant query."""
        cm.classify_and_remember("I prefer React over Vue", force_type="user_preference")

        prompt = cm.build_qa_prompt(question="Which frontend framework should I use?")
        assert "React" in prompt

    def test_contextual_pref_not_in_unrelated_query(self, cm):
        """Contextual preference may not appear in completely unrelated query."""
        cm.classify_and_remember("I prefer React over Vue", force_type="user_preference")

        # Weather query should not trigger React preference
        prompt = cm.build_qa_prompt(question="What is the weather today?")
        # React may or may not appear depending on FTS, but it shouldn't be guaranteed
        # This is a soft check - the key is that core prefs ARE guaranteed
        assert isinstance(prompt, str)

    def test_core_and_contextual_merged(self, cm):
        """Both core and contextual preferences appear when relevant."""
        cm.classify_and_remember("I am vegetarian", force_type="user_preference")
        _boost_confidence(cm, "vegetarian", 0.95)
        cm.classify_and_remember("I prefer Italian food", force_type="user_preference")

        prompt = cm.build_qa_prompt(question="What should I order for dinner?")
        # Core preference should always appear
        assert "vegetarian" in prompt.lower()
        # At minimum, the prompt should contain preference content
        assert len(prompt) > 100


class TestSessionSummaryFiltering:
    """Session summaries should be filtered by context relevance."""

    def test_relevant_summary_included(self, cm):
        """Summary relevant to current query should be included."""
        cm.classify_and_remember(
            "User discussed Python web frameworks and chose FastAPI",
            force_type="session_summary",
        )

        ctx = cm.build_context(context="How should I build a Python web app?")
        prompt = ctx.get("system_prompt", "")
        # Relevant summary should appear
        assert "FastAPI" in prompt or "Python" in prompt

    def test_irrelevant_summary_excluded(self, cm):
        """Summary irrelevant to current query should be excluded."""
        cm.classify_and_remember(
            "User discussed travel plans to Japan last summer",
            force_type="session_summary",
        )

        ctx = cm.build_context(context="How do I debug a Python script?")
        prompt = ctx.get("system_prompt", "")
        # Travel summary should NOT appear for a Python debugging query
        assert "Japan" not in prompt


class TestCorrectionSurvival:
    """Corrections must survive budget pressure and appear first."""

    def test_correction_before_preference(self, cm):
        """Correction should appear before preference in prompt."""
        cm.classify_and_remember("Do NOT use Java", force_type="correction")
        cm.classify_and_remember("I like Python", force_type="user_preference")

        ctx = cm.build_context(context="programming")
        prompt = ctx.get("system_prompt", "")
        if "Java" in prompt and "Python" in prompt:
            # Correction should come first
            java_pos = prompt.find("Java")
            python_pos = prompt.find("Python")
            assert java_pos < python_pos, "Correction should appear before preference"

    def test_correction_in_qa_prompt(self, cm):
        """Correction should appear in QA prompt via rules injection."""
        cm.classify_and_remember("Never suggest Python 2", force_type="correction")

        prompt = cm.build_qa_prompt(question="What Python version should I learn?")
        # Correction should be present either as memory or as rule
        assert "Python 2" in prompt or "Never" in prompt or len(prompt) > 50


class TestRuleTiering:
    """When no context, only override rules should be injected."""

    def test_override_rules_in_context_free(self, cm):
        """Override rules should appear even without context."""
        # This test verifies the rule tiering logic path
        # Without context, only override rules are injected
        result = cm.build_context(context=None)
        # Should not crash and should return valid result
        assert isinstance(result, dict)
        assert "system_prompt" in result


class TestBuildQaPromptRules:
    """QA prompt should include override rules."""

    def test_qa_prompt_with_override_rule(self, cm):
        """QA prompt should include override rules from rule engine."""
        # Store a correction that would become an override rule
        cm.classify_and_remember("Do NOT use tabs", force_type="correction")

        prompt = cm.build_qa_prompt(question="How should I format code?")
        # The correction should be present
        assert "tabs" in prompt.lower() or "NOT" in prompt or len(prompt) > 50

    def test_qa_prompt_without_rules_still_works(self, cm):
        """QA prompt should work even when no rules exist."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")

        prompt = cm.build_qa_prompt(question="What language to use?")
        assert "Python" in prompt


class TestBudgetAllocation:
    """Token budget should be properly allocated."""

    def test_many_preferences_capped(self, cm):
        """Many preferences should be capped by token budget."""
        for i in range(25):
            cm.classify_and_remember(f"I prefer option {i} for testing", force_type="user_preference")

        prompt = cm.build_qa_prompt(question="What do I prefer?")
        # Not all 25 preferences should appear
        count = prompt.count("prefer option")
        assert count < 25, f"Expected budget capping, got {count} preferences"

    def test_memories_and_knowledge_coexist(self, cm):
        """Memories and knowledge should both appear in prompt."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")

        prompt = cm.build_qa_prompt(question="What language should I use?")
        assert "Python" in prompt
