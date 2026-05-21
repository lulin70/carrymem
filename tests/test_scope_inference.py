"""
Tests for scope inference and preference matching in context.py.

Covers: SCOPE_VOCABULARY, infer_scopes, preference_matches_scope,
integration scenarios, and edge cases.
"""

import pytest

from carrymem.context import (
    SCOPE_VOCABULARY,
    infer_scopes,
    preference_matches_scope,
)


# ── SCOPE_VOCABULARY structure tests ────────────────────────────────

class TestScopeVocabulary:
    """Verify SCOPE_VOCABULARY is well-formed."""

    def test_has_eight_domains(self):
        assert len(SCOPE_VOCABULARY) == 8

    def test_expected_domains_present(self):
        expected = {
            "education", "entertainment", "lifestyle", "shopping",
            "travel", "work", "pet", "programming",
        }
        assert set(SCOPE_VOCABULARY.keys()) == expected

    def test_each_domain_has_en_and_zh(self):
        for scope, langs in SCOPE_VOCABULARY.items():
            assert "en" in langs, f"{scope} missing 'en' keywords"
            assert "zh" in langs, f"{scope} missing 'zh' keywords"

    def test_keywords_are_non_empty(self):
        for scope, langs in SCOPE_VOCABULARY.items():
            for lang, keywords in langs.items():
                assert len(keywords) > 0, f"{scope}/{lang} has no keywords"


# ── infer_scopes tests ──────────────────────────────────────────────

class TestInferScopes:
    """Test keyword-based scope inference."""

    def test_programming_keywords(self):
        result = infer_scopes("I prefer Python for backend development")
        assert "programming" in result

    def test_travel_keywords(self):
        result = infer_scopes("Book a flight to Tokyo and find a hotel")
        assert "travel" in result

    def test_lifestyle_keywords(self):
        result = infer_scopes("I need a healthy recipe for dinner")
        assert "lifestyle" in result

    def test_education_keywords(self):
        result = infer_scopes("I'm studying at university for my exam")
        assert "education" in result

    def test_entertainment_keywords(self):
        result = infer_scopes("I love watching a movie and playing a game")
        assert "entertainment" in result

    def test_shopping_keywords(self):
        result = infer_scopes("I want to buy a new car at a discount")
        assert "shopping" in result

    def test_work_keywords(self):
        result = infer_scopes("I have a meeting at the office tomorrow")
        assert "work" in result

    def test_pet_keywords(self):
        result = infer_scopes("My dog and cat need a veterinary checkup")
        assert "pet" in result

    def test_mixed_scopes(self):
        result = infer_scopes("I want to buy a laptop for programming while on a trip")
        assert "programming" in result
        assert "travel" in result
        assert "shopping" in result

    def test_no_match_returns_empty(self):
        result = infer_scopes("The weather is cloudy today")
        assert result == []

    def test_cjk_keywords_chinese(self):
        result = infer_scopes("我喜欢编程和开发软件")
        assert "programming" in result

    def test_cjk_keywords_travel(self):
        result = infer_scopes("预订酒店和航班去旅行")
        assert "travel" in result

    def test_cjk_keywords_lifestyle(self):
        result = infer_scopes("我需要健康的饮食和健身")
        assert "lifestyle" in result

    def test_word_boundary_english(self):
        """English keywords should match on word boundaries, not substrings."""
        # "coding" should match programming, but "encoding" should not
        result_match = infer_scopes("I enjoy coding in Python")
        assert "programming" in result_match

        # "car" in "scar" should NOT match shopping
        result_no_match = infer_scopes("He has a scar on his arm")
        assert "shopping" not in result_no_match

    def test_case_insensitive(self):
        result = infer_scopes("PYTHON IS MY FAVORITE PROGRAMMING LANGUAGE")
        assert "programming" in result

    def test_single_keyword_match(self):
        result = infer_scopes("docker")
        assert "programming" in result

    def test_multiple_same_scope_keywords(self):
        """Multiple keywords from the same scope should not duplicate the scope."""
        result = infer_scopes("I code in Python and debug with JavaScript")
        programming_count = result.count("programming")
        assert programming_count == 1


# ── preference_matches_scope tests ──────────────────────────────────

class TestPreferenceMatchesScope:
    """Test scope-aware preference matching with core exemption."""

    def _make_pref(self, content, confidence=0.5, scopes=None, raw_text=None):
        """Helper to build a preference dict."""
        metadata = {}
        if scopes:
            metadata["scopes"] = scopes
        return {
            "content": content,
            "raw_text": raw_text or content,
            "confidence": confidence,
            "metadata": metadata,
            "type": "user_preference",
        }

    def test_core_preference_always_matches(self):
        """Core preferences (confidence >= 0.9) always pass regardless of scope."""
        pref = self._make_pref("I love Python", confidence=0.95)
        assert preference_matches_scope(pref, "What's the best travel destination?") is True

    def test_core_preference_at_threshold(self):
        """Confidence exactly at threshold should be core."""
        pref = self._make_pref("I love Python", confidence=0.9)
        assert preference_matches_scope(pref, "Book a hotel in Paris") is True

    def test_core_preference_below_threshold(self):
        """Confidence just below threshold should NOT get free pass."""
        pref = self._make_pref("I love Python", confidence=0.89)
        # This is a programming preference, travel question → should not match
        assert preference_matches_scope(pref, "Book a hotel in Paris") is False

    def test_scope_match(self):
        """Preference and question in the same scope should match."""
        pref = self._make_pref("I prefer Python", confidence=0.5)
        assert preference_matches_scope(pref, "How to debug Python code?") is True

    def test_scope_mismatch(self):
        """Preference in one scope, question in another should not match."""
        pref = self._make_pref("I prefer Python programming", confidence=0.5)
        assert preference_matches_scope(pref, "What's the best travel destination?") is False

    def test_no_scope_inferred_allows_injection(self):
        """If no scope can be inferred from preference, allow injection."""
        pref = self._make_pref("I like things organized", confidence=0.5)
        assert preference_matches_scope(pref, "Tell me about travel") is True

    def test_no_scope_inferred_for_question_allows_injection(self):
        """If question scope can't be determined, allow injection (conservative)."""
        pref = self._make_pref("I prefer Python programming", confidence=0.5)
        assert preference_matches_scope(pref, "What's the meaning of life?") is True

    def test_empty_text_allows_injection(self):
        """Empty question text should allow injection (can't determine scope)."""
        pref = self._make_pref("I prefer Python", confidence=0.5)
        assert preference_matches_scope(pref, "") is True

    def test_explicit_scopes_in_metadata(self):
        """If metadata has explicit scopes, use those instead of inferring."""
        pref = self._make_pref("I like things", confidence=0.5, scopes=["travel"])
        assert preference_matches_scope(pref, "Best hotel in Paris?") is True

    def test_explicit_scopes_mismatch(self):
        """Explicit scopes in metadata that don't match question should fail."""
        pref = self._make_pref("I like things", confidence=0.5, scopes=["travel"])
        assert preference_matches_scope(pref, "How to debug Python?") is False

    def test_custom_threshold(self):
        """Custom core_confidence_threshold should be respected."""
        pref = self._make_pref("I like Python", confidence=0.8)
        # Default threshold 0.9 → not core
        assert preference_matches_scope(pref, "Best hotel?") is False
        # Lower threshold 0.7 → now core
        assert preference_matches_scope(pref, "Best hotel?", core_confidence_threshold=0.7) is True

    def test_metadata_as_json_string(self):
        """Metadata may be a JSON string; should be parsed."""
        import json
        pref = {
            "content": "I like things",
            "raw_text": "I like things",
            "confidence": 0.5,
            "metadata": json.dumps({"scopes": ["travel"]}),
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "Best hotel in Tokyo?") is True

    def test_metadata_invalid_json_treated_as_empty(self):
        """Invalid JSON in metadata should be treated as empty dict."""
        pref = {
            "content": "I like things",
            "raw_text": "I like things",
            "confidence": 0.5,
            "metadata": "not valid json{",
            "type": "user_preference",
        }
        # No scopes → general preference → allow
        assert preference_matches_scope(pref, "Tell me about travel") is True

    def test_overlapping_scopes(self):
        """Preference and question sharing at least one scope should match."""
        pref = self._make_pref("I code in Python", confidence=0.5, scopes=["programming", "work"])
        assert preference_matches_scope(pref, "I need a new laptop for coding") is True


# ── Integration tests ───────────────────────────────────────────────

class TestScopeIntegration:
    """End-to-end scenarios combining infer_scopes and preference_matches_scope."""

    def test_programming_pref_not_injected_for_travel_question(self):
        """A programming preference should NOT be injected for a travel question."""
        pref = {
            "content": "I prefer Python over Java for backend",
            "raw_text": "I prefer Python over Java for backend",
            "confidence": 0.5,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "What's the best hotel in Paris?") is False

    def test_programming_pref_injected_for_programming_question(self):
        """A programming preference SHOULD be injected for a programming question."""
        pref = {
            "content": "I prefer Python over Java for backend",
            "raw_text": "I prefer Python over Java for backend",
            "confidence": 0.5,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "How to set up a Python API?") is True

    def test_travel_pref_injected_for_travel_question(self):
        pref = {
            "content": "I prefer boutique hotels over large resorts",
            "raw_text": "I prefer boutique hotels over large resorts",
            "confidence": 0.6,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "Find me a hotel in Tokyo") is True

    def test_travel_pref_not_injected_for_coding_question(self):
        pref = {
            "content": "I prefer boutique hotels over large resorts",
            "raw_text": "I prefer boutique hotels over large resorts",
            "confidence": 0.6,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "How to debug a React app?") is False

    def test_general_pref_injected_everywhere(self):
        """A preference with no scoping keywords should be injected everywhere."""
        pref = {
            "content": "I prefer concise answers",
            "raw_text": "I prefer concise answers",
            "confidence": 0.5,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "How to code in Python?") is True
        assert preference_matches_scope(pref, "Best hotel in Paris?") is True
        assert preference_matches_scope(pref, "What should I eat for dinner?") is True

    def test_core_pref_injected_everywhere(self):
        """A core preference should be injected regardless of question topic."""
        pref = {
            "content": "I prefer Python programming",
            "raw_text": "I prefer Python programming",
            "confidence": 0.95,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "Best hotel in Paris?") is True
        assert preference_matches_scope(pref, "How to cook pasta?") is True


# ── Edge cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases for infer_scopes and preference_matches_scope."""

    def test_none_input_infer_scopes(self):
        result = infer_scopes(None)
        assert result == []

    def test_empty_string_infer_scopes(self):
        result = infer_scopes("")
        assert result == []

    def test_non_string_input_infer_scopes(self):
        result = infer_scopes(123)
        assert result == []

    def test_very_long_text_infer_scopes(self):
        long_text = "I love Python programming. " * 500
        result = infer_scopes(long_text)
        assert "programming" in result

    def test_whitespace_only_infer_scopes(self):
        result = infer_scopes("   \t\n  ")
        assert result == []

    def test_none_question_preference_matches(self):
        """None as question should be handled gracefully."""
        pref = {
            "content": "I prefer Python",
            "raw_text": "I prefer Python",
            "confidence": 0.5,
            "metadata": {},
            "type": "user_preference",
        }
        # None question → infer_scopes returns [] → no question scope → allow
        assert preference_matches_scope(pref, None) is True

    def test_empty_content_preference(self):
        """Preference with empty content should be treated as general (allow)."""
        pref = {
            "content": "",
            "raw_text": "",
            "confidence": 0.5,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "How to code in Python?") is True

    def test_missing_raw_text_falls_back_to_content(self):
        """If raw_text is missing, should fall back to content for inference."""
        pref = {
            "content": "I prefer Python programming",
            "confidence": 0.5,
            "metadata": {},
            "type": "user_preference",
        }
        assert preference_matches_scope(pref, "How to debug Python?") is True

    def test_special_characters_in_text(self):
        result = infer_scopes("I love Python!!! @#$%^&*()")
        assert "programming" in result

    def test_mixed_cjk_and_english(self):
        result = infer_scopes("I use Python for 编程 and 开发")
        assert "programming" in result
