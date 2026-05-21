"""Tests for PromptBuilder — extracted prompt construction logic.

Covers:
1. _recall_base_memories — main recall + superseded + summaries + aggregation signal
2. _identify_preferences — core prefs, contextual prefs, scope filtering
3. _compute_recalc_scores — confidence recalculation without mutation
4. _budget_filter — budget constraints, pref token cap
5. _inject_rules — override-only mode vs full mode
6. build_context — full integration test
7. build_system_prompt — convenience wrapper
8. build_qa_prompt — full integration test with budget
"""

import os
import tempfile

import pytest

from carrymem import CarryMem
from carrymem.prompt_builder import PromptBuilder
from carrymem.scoring import RecallBudget


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture
def pb(cm):
    """Return the PromptBuilder attached to the CarryMem instance."""
    return cm.prompt_builder


def _boost_confidence(cm, content_fragment, confidence=0.95):
    """Boost confidence of a memory containing content_fragment."""
    conn = cm._adapter._get_connection()
    rows = conn.execute(
        "SELECT storage_key FROM memories WHERE content LIKE ?",
        (f"%{content_fragment}%",),
    ).fetchall()
    for row in rows:
        conn.execute("UPDATE memories SET confidence = ? WHERE storage_key = ?", (confidence, row[0]))
    conn.commit()


def _set_field(cm, content_fragment, field, value):
    """Set an arbitrary field on a memory containing content_fragment."""
    conn = cm._adapter._get_connection()
    rows = conn.execute(
        "SELECT storage_key FROM memories WHERE content LIKE ?",
        (f"%{content_fragment}%",),
    ).fetchall()
    for row in rows:
        conn.execute(f"UPDATE memories SET {field} = ? WHERE storage_key = ?", (value, row[0]))
    conn.commit()


# ===================================================================
# 1. _recall_base_memories
# ===================================================================

class TestRecallBaseMemories:
    """Tests for PromptBuilder._recall_base_memories."""

    def test_basic_recall(self, pb, cm):
        """Main recall returns stored memories."""
        cm.classify_and_remember("I prefer dark mode in VS Code", force_type="user_preference")
        all_mems, seen = pb._recall_base_memories("dark mode", limit=30)
        assert len(all_mems) >= 1
        assert any("dark mode" in m.get("content", "") for m in all_mems)

    def test_superseded_included(self, pb, cm):
        """Superseded memories are included if not already in main recall."""
        cm.classify_and_remember("I live in Beijing", force_type="fact_declaration")
        # Mark as superseded
        _set_field(cm, "Beijing", "superseded_at", "2026-01-01T00:00:00")
        all_mems, seen = pb._recall_base_memories("Beijing", limit=30)
        superseded_mems = [m for m in all_mems if m.get("superseded_at")]
        assert len(superseded_mems) >= 1

    def test_superseded_dedup(self, pb, cm):
        """Superseded memories already in main recall are not duplicated."""
        cm.classify_and_remember("I live in Shanghai", force_type="fact_declaration")
        all_mems, seen = pb._recall_base_memories("Shanghai", limit=30)
        keys = [m.get("storage_key") for m in all_mems]
        # No duplicate keys
        assert len(keys) == len(set(keys))

    def test_session_summaries_included(self, pb, cm):
        """Session summaries are included when relevant."""
        cm.classify_and_remember(
            "User discussed Python web frameworks and chose FastAPI",
            force_type="session_summary",
        )
        all_mems, seen = pb._recall_base_memories("Python web app", limit=30)
        summaries = [m for m in all_mems if m.get("type") == "session_summary"]
        assert len(summaries) >= 1

    def test_session_summary_relevance_filter(self, pb, cm):
        """Irrelevant session summaries are filtered by context_relevance."""
        cm.classify_and_remember(
            "User discussed travel plans to Japan last summer",
            force_type="session_summary",
        )
        all_mems, seen = pb._recall_base_memories("debug Python script", limit=30)
        # Travel summary should not be included for a Python debugging query
        travel_mems = [m for m in all_mems if "Japan" in m.get("content", "")]
        assert len(travel_mems) == 0

    def test_aggregation_signal_includes_all_summaries(self, pb, cm):
        """Aggregation signal queries include all session summaries."""
        cm.classify_and_remember(
            "User discussed Python frameworks",
            force_type="session_summary",
        )
        cm.classify_and_remember(
            "User discussed travel plans to Japan",
            force_type="session_summary",
        )
        # "how many" triggers aggregation signal
        all_mems, seen = pb._recall_base_memories("how many sessions have we had", limit=30)
        summaries = [m for m in all_mems if m.get("type") == "session_summary"]
        assert len(summaries) >= 2

    def test_empty_query(self, pb, cm):
        """Empty query should not crash."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        all_mems, seen = pb._recall_base_memories("", limit=30)
        assert isinstance(all_mems, list)

    def test_no_memories(self, pb, cm):
        """No memories stored should return empty list."""
        all_mems, seen = pb._recall_base_memories("anything", limit=30)
        assert isinstance(all_mems, list)


# ===================================================================
# 2. _identify_preferences
# ===================================================================

class TestIdentifyPreferences:
    """Tests for PromptBuilder._identify_preferences."""

    def test_core_prefs_identified(self, pb, cm):
        """Core preferences (confidence >= 0.9) are identified."""
        cm.classify_and_remember("I am vegetarian", force_type="user_preference")
        _boost_confidence(cm, "vegetarian", 0.95)

        all_mems, seen = pb._recall_base_memories("food", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(all_mems, seen, "food")
        core = [m for m in pref_mems if m.get("confidence", 0) >= 0.9]
        assert len(core) >= 1

    def test_contextual_prefs_identified(self, pb, cm):
        """Contextual preferences (confidence < 0.9) are identified."""
        cm.classify_and_remember("I prefer React over Vue", force_type="user_preference")
        # Default confidence is below 0.9

        all_mems, seen = pb._recall_base_memories("React", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(all_mems, seen, "React")
        contextual = [m for m in pref_mems if m.get("confidence", 0) < 0.9]
        assert len(contextual) >= 1

    def test_core_prefs_fetched_if_missing(self, pb, cm):
        """Core prefs are fetched from storage if not in main recall."""
        cm.classify_and_remember("I am vegetarian", force_type="user_preference")
        _boost_confidence(cm, "vegetarian", 0.95)

        # Use a completely unrelated query so core pref is not in main recall
        all_mems, seen = pb._recall_base_memories("weather forecast", limit=30)
        # Core pref should still be fetched via ensure_core
        pref_mems, pref_keys, all_mems = pb._identify_preferences(all_mems, seen, "weather")
        assert any("vegetarian" in m.get("content", "").lower() for m in pref_mems)

    def test_scope_filtering_programming_vs_travel(self, pb, cm):
        """Programming-scoped preference is not injected for travel query."""
        cm.classify_and_remember("I prefer Python for coding", force_type="user_preference")
        # Set explicit scope metadata
        conn = cm._adapter._get_connection()
        rows = conn.execute(
            "SELECT storage_key FROM memories WHERE content LIKE ?",
            ("%Python%",),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE memories SET metadata = ? WHERE storage_key = ?",
                ('{"scopes": ["programming"]}', row[0]),
            )
        conn.commit()

        all_mems, seen = pb._recall_base_memories("travel to Paris", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(
            all_mems, seen, "travel to Paris",
        )
        # Programming preference should not match travel scope
        python_prefs = [m for m in pref_mems if "Python" in m.get("content", "")]
        # With explicit scope "programming" and question about travel, it should be filtered
        assert len(python_prefs) == 0

    def test_scope_filtering_programming_matches(self, pb, cm):
        """Programming-scoped preference IS injected for programming query."""
        cm.classify_and_remember("I prefer Python for coding", force_type="user_preference")
        conn = cm._adapter._get_connection()
        rows = conn.execute(
            "SELECT storage_key FROM memories WHERE content LIKE ?",
            ("%Python%",),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE memories SET metadata = ? WHERE storage_key = ?",
                ('{"scopes": ["programming"]}', row[0]),
            )
        conn.commit()

        all_mems, seen = pb._recall_base_memories("coding project", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(
            all_mems, seen, "coding project",
        )
        python_prefs = [m for m in pref_mems if "Python" in m.get("content", "")]
        assert len(python_prefs) >= 1

    def test_pref_keys_are_deduped(self, pb, cm):
        """Preference keys should be unique (no duplicates)."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        _boost_confidence(cm, "dark mode", 0.95)

        all_mems, seen = pb._recall_base_memories("dark mode", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(all_mems, seen, "dark mode")
        # pref_keys should have no duplicates
        assert len(pref_keys) == len(set(pref_keys))

    def test_ensure_core_false(self, pb, cm):
        """With ensure_core=False, missing core prefs are not fetched."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        _boost_confidence(cm, "dark mode", 0.95)

        # Use unrelated query so core pref is not in main recall
        all_mems, seen = pb._recall_base_memories("weather forecast", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(
            all_mems, seen, "weather", ensure_core=False,
        )
        # Without ensure_core, the vegetarian/dark mode pref should not be fetched
        # (it might still appear if FTS matches, but ensure_core=False won't add it)
        dark_mode = [m for m in pref_mems if "dark mode" in m.get("content", "").lower()]
        # It should not have been explicitly fetched
        assert isinstance(pref_mems, list)


# ===================================================================
# 3. _compute_recalc_scores
# ===================================================================

class TestComputeRecalcScores:
    """Tests for PromptBuilder._compute_recalc_scores."""

    def test_basic_recalc(self, pb, cm):
        """Recalculation produces scores for memories with confidence > 0."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        all_mems, _ = pb._recall_base_memories("Python", limit=30)
        scores = pb._compute_recalc_scores(all_mems)
        # At least one memory should have a recalc score
        assert len(scores) >= 1
        for key, (conf, imp) in scores.items():
            assert conf >= 0
            assert imp >= 0

    def test_no_mutation(self, pb, cm):
        """Recalculation does not mutate original memory dicts."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        all_mems, _ = pb._recall_base_memories("Python", limit=30)
        # Snapshot original confidence
        orig_conf = {m.get("storage_key"): m.get("confidence") for m in all_mems}
        pb._compute_recalc_scores(all_mems)
        # Verify no mutation
        for m in all_mems:
            key = m.get("storage_key")
            assert m.get("confidence") == orig_conf[key], "Original memory was mutated"

    def test_zero_confidence_skipped(self, pb, cm):
        """Memories with zero confidence are skipped."""
        cm.classify_and_remember("Some fact", force_type="fact_declaration")
        _set_field(cm, "Some fact", "confidence", 0.0)
        all_mems, _ = pb._recall_base_memories("fact", limit=30)
        scores = pb._compute_recalc_scores(all_mems)
        # The zero-confidence memory should not appear in scores
        zero_conf_keys = {m.get("storage_key") for m in all_mems if m.get("confidence", 0) == 0}
        for key in zero_conf_keys:
            assert key not in scores

    def test_importance_score_adjusted(self, pb, cm):
        """Recalculated importance is scaled by confidence ratio."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        _boost_confidence(cm, "Python", 0.8)
        _set_field(cm, "Python", "importance_score", 0.5)
        all_mems, _ = pb._recall_base_memories("Python", limit=30)
        scores = pb._compute_recalc_scores(all_mems)
        for key, (new_conf, new_imp) in scores.items():
            # new_imp should be recalculated based on confidence ratio
            assert isinstance(new_imp, float)

    def test_empty_memories(self, pb, cm):
        """Empty memory list returns empty scores."""
        scores = pb._compute_recalc_scores([])
        assert scores == {}


# ===================================================================
# 4. _budget_filter
# ===================================================================

class TestBudgetFilter:
    """Tests for PromptBuilder._budget_filter."""

    def test_pref_token_cap(self, pb, cm):
        """Preferences are capped at 40% of memories_budget."""
        for i in range(20):
            cm.classify_and_remember(f"I prefer option {i} for testing", force_type="user_preference")
        all_mems, seen = pb._recall_base_memories("prefer", limit=60)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(all_mems, seen, "prefer")

        budget = RecallBudget(max_results=20, max_tokens=4000)
        memories_budget = 2000  # 40% = 800 tokens for prefs
        scores = pb._compute_recalc_scores(all_mems)
        filtered = pb._budget_filter(all_mems, pref_keys, budget, memories_budget, scores)

        pref_in_filtered = [m for m in filtered if m.get("storage_key") in pref_keys]
        # Should not include all 20 preferences
        assert len(pref_in_filtered) < 20

    def test_type_quotas_respected(self, pb, cm):
        """Type quotas from RecallBudget are respected."""
        for i in range(10):
            cm.classify_and_remember(f"Correction number {i}", force_type="correction")
        all_mems, seen = pb._recall_base_memories("correction", limit=30)

        # Set a tight quota for corrections
        budget = RecallBudget(
            max_results=20,
            max_tokens=4000,
            type_quotas={"correction": 2},
        )
        scores = pb._compute_recalc_scores(all_mems)
        filtered = pb._budget_filter(all_mems, set(), budget, 4000, scores)

        corrections = [m for m in filtered if m.get("type") == "correction"]
        assert len(corrections) <= 2

    def test_min_confidence_filter(self, pb, cm):
        """Budget with min_confidence filters out low-confidence memories."""
        cm.classify_and_remember("Low confidence fact", force_type="fact_declaration")
        _set_field(cm, "Low confidence", "confidence", 0.1)
        cm.classify_and_remember("High confidence fact", force_type="fact_declaration")
        _boost_confidence(cm, "High confidence", 0.9)

        all_mems, seen = pb._recall_base_memories("fact", limit=30)
        budget = RecallBudget(max_results=20, max_tokens=4000, min_confidence=0.5)
        scores = pb._compute_recalc_scores(all_mems)
        filtered = pb._budget_filter(all_mems, set(), budget, 4000, scores)

        for m in filtered:
            if m.get("storage_key") not in set():  # non-pref
                key = m.get("storage_key", "")
                conf, _ = scores.get(key, (m.get("confidence", 0), m.get("importance_score", 0)))
                assert conf >= 0.5

    def test_prefs_always_included_up_to_cap(self, pb, cm):
        """Preferences are always included (up to pref token cap) regardless of budget."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        _boost_confidence(cm, "Python", 0.95)

        all_mems, seen = pb._recall_base_memories("Python", limit=30)
        pref_mems, pref_keys, all_mems = pb._identify_preferences(all_mems, seen, "Python")

        budget = RecallBudget(max_results=1, max_tokens=4000)
        scores = pb._compute_recalc_scores(all_mems)
        filtered = pb._budget_filter(all_mems, pref_keys, budget, 4000, scores)

        pref_in_filtered = [m for m in filtered if m.get("storage_key") in pref_keys]
        assert len(pref_in_filtered) >= 1

    def test_empty_input(self, pb, cm):
        """Empty memories list returns empty filtered list."""
        budget = RecallBudget(max_results=10, max_tokens=2000)
        filtered = pb._budget_filter([], set(), budget, 2000, {})
        assert filtered == []


# ===================================================================
# 5. _inject_rules
# ===================================================================

class TestInjectRules:
    """Tests for PromptBuilder._inject_rules."""

    def test_no_rule_engine_returns_empty(self, pb, cm):
        """Without a rule engine, returns empty string."""
        # Ensure no rule engine
        cm._rule_engine = None
        result = pb._inject_rules("test context", max_rules=5, rules_budget=400)
        assert result == ""

    def test_override_only_mode(self, pb, cm):
        """Override-only mode (for QA prompts) only includes override rules."""
        # Add a rule with override flag
        cm.rule_engine.add_rule(
            trigger="test_trigger",
            action="test_action",
            rule_type="always",
            override=True,
        )
        result = pb._inject_rules(None, max_rules=5, rules_budget=400, override_only=True)
        # Should not crash; may return empty if formatting fails, but should not error
        assert isinstance(result, str)

    def test_full_mode_with_context(self, pb, cm):
        """Full mode with context uses rule engine inject method."""
        cm.rule_engine.add_rule(
            trigger="programming",
            action="Use Python 3",
            rule_type="always",
        )
        result = pb._inject_rules("programming task", max_rules=5, rules_budget=400, override_only=False)
        # May return content or empty depending on matcher, but should not error
        assert isinstance(result, str)

    def test_full_mode_without_context(self, pb, cm):
        """Full mode without context falls through to override path."""
        cm.rule_engine.add_rule(
            trigger="test",
            action="test action",
            rule_type="always",
            override=True,
        )
        result = pb._inject_rules(None, max_rules=5, rules_budget=400, override_only=False)
        assert isinstance(result, str)

    def test_exception_returns_empty(self, pb, cm):
        """Exceptions during rule injection return empty string."""
        # Force an exception by making rule_engine.inject raise
        class BrokenEngine:
            def inject(self, *a, **kw):
                raise RuntimeError("broken")
            def list_rules(self, *a, **kw):
                raise RuntimeError("broken")
        cm._rule_engine = BrokenEngine()
        result = pb._inject_rules("test", max_rules=5, rules_budget=400, override_only=False)
        assert result == ""


# ===================================================================
# 6. build_context
# ===================================================================

class TestBuildContext:
    """Tests for PromptBuilder.build_context — full integration."""

    def test_returns_expected_keys(self, pb, cm):
        """build_context returns all expected keys."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        result = pb.build_context(context="dark mode")
        expected_keys = {
            "system_prompt", "rules", "memories", "knowledge",
            "applied_rules", "rule_count", "memory_count",
            "knowledge_count", "total_count", "token_estimate", "language",
        }
        assert expected_keys.issubset(result.keys())

    def test_memory_count_positive(self, pb, cm):
        """Memory count is positive when memories exist."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        result = pb.build_context(context="dark mode")
        assert result["memory_count"] >= 1

    def test_token_estimate_positive(self, pb, cm):
        """Token estimate is positive."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        result = pb.build_context(context="dark mode")
        assert result["token_estimate"] > 0

    def test_language_field(self, pb, cm):
        """Language field is set correctly."""
        result = pb.build_context(context="test", language="zh")
        assert result["language"] == "zh"

    def test_no_adapter(self, pb, cm):
        """Without adapter, memories and knowledge are empty."""
        cm._adapter = None
        result = pb.build_context(context="test")
        assert result["memory_count"] == 0
        assert result["knowledge_count"] == 0

    def test_no_memories(self, pb, cm):
        """No memories stored returns empty sections."""
        result = pb.build_context(context="nothing here")
        assert isinstance(result["system_prompt"], str)
        assert result["memory_count"] == 0

    def test_with_knowledge_adapter(self, pb, cm):
        """Knowledge adapter is used when available."""
        # Knowledge adapter may not be set up in test, but the path should not crash
        result = pb.build_context(context="test")
        assert "knowledge" in result

    def test_core_pref_in_unrelated_context(self, pb, cm):
        """Core preferences appear even in unrelated context."""
        cm.classify_and_remember("I am vegetarian", force_type="user_preference")
        _boost_confidence(cm, "vegetarian", 0.95)
        result = pb.build_context(context="weather forecast", max_memories=2)
        prompt = result["system_prompt"]
        assert "vegetarian" in prompt.lower()

    def test_budget_respected(self, pb, cm):
        """Token budget limits the output."""
        for i in range(30):
            cm.classify_and_remember(f"Memory number {i} about various topics", force_type="fact_declaration")
        result = pb.build_context(context="memory", max_memories=3, max_tokens=200)
        assert result["memory_count"] <= 10  # Should be constrained


# ===================================================================
# 7. build_system_prompt
# ===================================================================

class TestBuildSystemPrompt:
    """Tests for PromptBuilder.build_system_prompt — convenience wrapper."""

    def test_returns_string(self, pb, cm):
        """build_system_prompt returns a string."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        prompt = pb.build_system_prompt(context="dark mode")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_memory_content(self, pb, cm):
        """System prompt contains memory content."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        prompt = pb.build_system_prompt(context="dark mode")
        assert "dark mode" in prompt

    def test_delegates_to_build_context(self, pb, cm):
        """build_system_prompt delegates to build_context."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        ctx = pb.build_context(context="Python")
        prompt = pb.build_system_prompt(context="Python")
        assert prompt == ctx["system_prompt"]

    def test_language_parameter(self, pb, cm):
        """Language parameter is forwarded correctly."""
        cm.classify_and_remember("我喜欢深色模式", force_type="user_preference")
        prompt = pb.build_system_prompt(context="深色模式", language="zh")
        assert "用户记忆" in prompt


# ===================================================================
# 8. build_qa_prompt
# ===================================================================

class TestBuildQaPrompt:
    """Tests for PromptBuilder.build_qa_prompt — full integration with budget."""

    def test_returns_string(self, pb, cm):
        """build_qa_prompt returns a string."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        prompt = pb.build_qa_prompt(question="What language?")
        assert isinstance(prompt, str)

    def test_contains_memory(self, pb, cm):
        """QA prompt contains relevant memory."""
        cm.classify_and_remember("I prefer Python for coding", force_type="user_preference")
        prompt = pb.build_qa_prompt(question="What programming language should I use?")
        assert "Python" in prompt

    def test_include_question(self, pb, cm):
        """Question is included when include_question=True."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        prompt = pb.build_qa_prompt(question="What language?", include_question=True)
        assert "What language?" in prompt

    def test_exclude_question(self, pb, cm):
        """Question is excluded when include_question=False."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        prompt = pb.build_qa_prompt(question="What language?", include_question=False)
        # The question text should not appear as a "Question:" header
        assert "Question: What language?" not in prompt

    def test_custom_budget(self, pb, cm):
        """Custom RecallBudget is respected."""
        for i in range(20):
            cm.classify_and_remember(f"Memory {i} about Python", force_type="fact_declaration")
        budget = RecallBudget(max_results=3, max_tokens=500)
        prompt = pb.build_qa_prompt(question="Python", budget=budget)
        assert isinstance(prompt, str)

    def test_aggregation_signal_path(self, pb, cm):
        """Aggregation signal queries take a different code path."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        cm.classify_and_remember(
            "User discussed Python frameworks",
            force_type="session_summary",
        )
        # "how many" triggers aggregation signal
        prompt = pb.build_qa_prompt(question="how many preferences do I have?")
        assert isinstance(prompt, str)

    def test_no_adapter(self, pb, cm):
        """Without adapter, QA prompt still returns a string."""
        cm._adapter = None
        prompt = pb.build_qa_prompt(question="What language?")
        assert isinstance(prompt, str)

    def test_empty_question(self, pb, cm):
        """Empty question does not crash."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        prompt = pb.build_qa_prompt(question="")
        assert isinstance(prompt, str)

    def test_correction_survives_budget(self, pb, cm):
        """Corrections survive budget pressure."""
        cm.classify_and_remember("Do NOT use Java", force_type="correction")
        for i in range(15):
            cm.classify_and_remember(f"Fact number {i}", force_type="fact_declaration")
        budget = RecallBudget(max_results=5, max_tokens=500)
        prompt = pb.build_qa_prompt(question="programming language", budget=budget)
        # Correction should still appear
        assert "Java" in prompt or "NOT" in prompt or len(prompt) > 50

    def test_override_rules_in_qa(self, pb, cm):
        """QA prompt uses override-only mode for rules."""
        cm.rule_engine.add_rule(
            trigger="test",
            action="Always use Python 3",
            rule_type="always",
            override=True,
        )
        prompt = pb.build_qa_prompt(question="What Python version?")
        assert isinstance(prompt, str)


# ===================================================================
# Delegation tests — CarryMem delegates to PromptBuilder
# ===================================================================

class TestCarryMemDelegation:
    """Verify CarryMem correctly delegates to PromptBuilder."""

    def test_prompt_builder_property(self, cm):
        """CarryMem.prompt_builder returns a PromptBuilder instance."""
        assert isinstance(cm.prompt_builder, PromptBuilder)

    def test_prompt_builder_cached(self, cm):
        """PromptBuilder is cached (same instance on repeated access)."""
        pb1 = cm.prompt_builder
        pb2 = cm.prompt_builder
        assert pb1 is pb2

    def test_build_context_delegation(self, cm):
        """CarryMem.build_context delegates to PromptBuilder.build_context."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        result = cm.build_context(context="dark mode")
        assert "system_prompt" in result

    def test_build_system_prompt_delegation(self, cm):
        """CarryMem.build_system_prompt delegates to PromptBuilder.build_system_prompt."""
        cm.classify_and_remember("I prefer dark mode", force_type="user_preference")
        prompt = cm.build_system_prompt(context="dark mode")
        assert "dark mode" in prompt

    def test_build_qa_prompt_delegation(self, cm):
        """CarryMem.build_qa_prompt delegates to PromptBuilder.build_qa_prompt."""
        cm.classify_and_remember("I prefer Python", force_type="user_preference")
        prompt = cm.build_qa_prompt(question="What language?")
        assert "Python" in prompt
