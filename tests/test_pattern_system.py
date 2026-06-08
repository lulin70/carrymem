"""Unit tests for the pattern management system (carrymem.patterns)."""

import re
import pytest

from carrymem.patterns.base import (
    Pattern, PatternType, NoiseCategory, PatternMatch,
    NoisePattern, PreferencePattern, CorrectionPattern,
    FactPattern, TaskPattern, DecisionPattern,
    RelationshipPattern, SentimentPattern, LocationPattern,
)
from carrymem.patterns.group import PatternGroup
from carrymem.patterns.registry import PatternRegistry
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.definitions import build_registry


# ======================================================================
# Pattern base classes
# ======================================================================

class TestNoisePattern:
    def test_create_and_match(self):
        p = NoisePattern("ok", r"^ok\.?$", "en", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE)
        assert p.pattern_type == PatternType.NOISE
        assert p.category == NoiseCategory.ACKNOWLEDGMENT
        assert p.match("ok") is not None
        assert p.match("OK") is not None
        assert p.match("ok.") is not None
        assert p.match("okay") is None

    def test_full_name(self):
        p = NoisePattern("ok", r"^ok$", "en", NoiseCategory.ACKNOWLEDGMENT)
        assert p.full_name == "en_ok"

    def test_search_method(self):
        p = NoisePattern("test", r"\btest\b", "en", NoiseCategory.ADVERSARIAL, match_method="search")
        assert p.try_match("this is a test") is not None
        assert p.try_match("testing") is None  # word boundary

    def test_description(self):
        p = NoisePattern("ok", r"^ok$", "en", NoiseCategory.ACKNOWLEDGMENT)
        assert "acknowledgment" in p.get_description().lower()


class TestPreferencePattern:
    def test_create_and_search(self):
        p = PreferencePattern("prefer_over", r"\bprefer\b.*\bover\b", "en", "strong", flags=re.IGNORECASE)
        assert p.pattern_type == PatternType.PREFERENCE
        assert p.strength == "strong"
        assert p.search("I prefer Python over Java") is not None
        assert p.search("I like cats") is None


class TestCorrectionPattern:
    def test_tier(self):
        p = CorrectionPattern("correction", r"^correction:", "en", tier=1)
        assert p.tier == 1
        assert p.pattern_type == PatternType.CORRECTION


class TestPatternMatch:
    def test_to_dict(self):
        pm = PatternMatch(
            pattern_name="en_ok",
            group_name="noise_ack",
            pattern_type=PatternType.NOISE,
            language="en",
            confidence=0.9,
            matched_text="ok",
        )
        d = pm.to_dict()
        assert d["pattern_name"] == "en_ok"
        assert d["pattern_type"] == "noise"
        assert d["confidence"] == 0.9


# ======================================================================
# PatternGroup
# ======================================================================

class TestPatternGroup:
    def test_add_and_match(self):
        g = PatternGroup("noise_ack", PatternType.NOISE)
        g.add_pattern(NoisePattern("ok", r"^ok\.?$", "en", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE))
        g.add_pattern(NoisePattern("good", r"^好的\.?$", "zh", NoiseCategory.ACKNOWLEDGMENT))

        assert g.pattern_count == 2
        assert g.languages == ["en", "zh"]

        # Match EN
        m = g.match_first("ok", "en")
        assert m is not None
        assert m.pattern_name == "en_ok"

        # Match ZH
        m = g.match_first("好的", "zh")
        assert m is not None
        assert m.pattern_name == "zh_good"

        # No match
        assert g.match_first("hello", "en") is None

    def test_any_match(self):
        g = PatternGroup("test", PatternType.NOISE)
        g.add_pattern(NoisePattern("hi", r"^hi$", "en", NoiseCategory.CHITCHAT))
        assert g.any_match("hi", "en") is True
        assert g.any_match("bye", "en") is False

    def test_match_all(self):
        g = PatternGroup("test", PatternType.NOISE)
        g.add_pattern(NoisePattern("hi", r"^hi$", "en", NoiseCategory.CHITCHAT, match_method="match"))
        g.add_pattern(NoisePattern("hello", r"^hello$", "en", NoiseCategory.CHITCHAT, match_method="match"))
        results = g.match_all("hi", "en")
        assert len(results) == 1

    def test_language_filtering(self):
        g = PatternGroup("test", PatternType.NOISE)
        g.add_pattern(NoisePattern("hi", r"^hi$", "en", NoiseCategory.CHITCHAT))
        g.add_pattern(NoisePattern("nihao", r"^你好$", "zh", NoiseCategory.CHITCHAT))
        assert len(g.get_patterns("en")) == 1
        assert len(g.get_patterns("zh")) == 1
        assert len(g.get_patterns()) == 2


# ======================================================================
# PatternRegistry
# ======================================================================

class TestPatternRegistry:
    def test_register_and_match(self):
        reg = PatternRegistry()
        g = PatternGroup("noise_ack", PatternType.NOISE)
        g.add_pattern(NoisePattern("ok", r"^ok\.?$", "en", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE))
        reg.register_group(g)

        assert reg.any_match_by_group("noise_ack", "ok", "en") is True
        assert reg.any_match_by_group("noise_ack", "hello", "en") is False
        assert reg.any_match_by_group("nonexistent", "ok", "en") is False

    def test_match_groups(self):
        reg = PatternRegistry()
        g1 = PatternGroup("g1", PatternType.NOISE)
        g1.add_pattern(NoisePattern("ok", r"^ok$", "en", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE))
        g2 = PatternGroup("g2", PatternType.NOISE)
        g2.add_pattern(NoisePattern("hi", r"^hi$", "en", NoiseCategory.CHITCHAT, flags=re.IGNORECASE))
        reg.register_group(g1)
        reg.register_group(g2)

        m = reg.match_groups(["g1", "g2"], "ok", "en")
        assert m is not None
        assert m.group_name == "g1"

        m = reg.match_groups(["g1", "g2"], "hi", "en")
        assert m is not None
        assert m.group_name == "g2"

    def test_any_match_groups(self):
        reg = PatternRegistry()
        g1 = PatternGroup("g1", PatternType.NOISE)
        g1.add_pattern(NoisePattern("ok", r"^ok$", "en", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE))
        reg.register_group(g1)

        assert reg.any_match_groups(["g1"], "ok", "en") is True
        assert reg.any_match_groups(["g1"], "bye", "en") is False


# ======================================================================
# PatternBuilder
# ======================================================================

class TestPatternBuilder:
    def test_fluent_api(self):
        reg = PatternRegistry()
        b = PatternBuilder(reg)
        (b
            .create_group("noise_ack", PatternType.NOISE)
            .set_language("en")
            .add_noise("ok", r"^ok\.?$", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE)
            .add_noise("sure", r"^sure\.?$", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE)
            .set_language("zh")
            .add_noise("good", r"^好的\.?$", NoiseCategory.ACKNOWLEDGMENT)
            .register())

        assert reg.any_match_by_group("noise_ack", "ok", "en") is True
        assert reg.any_match_by_group("noise_ack", "好的", "zh") is True

    def test_add_noise_batch(self):
        reg = PatternRegistry()
        b = PatternBuilder(reg)
        (b
            .create_group("test", PatternType.NOISE)
            .set_language("en")
            .add_noise_batch(
                [("ok", r"^ok$"), ("sure", r"^sure$")],
                NoiseCategory.ACKNOWLEDGMENT,
                flags=re.IGNORECASE,
            )
            .register())

        g = reg.get_group("test")
        assert g is not None
        assert g.pattern_count == 2

    def test_add_preference_batch(self):
        reg = PatternRegistry()
        b = PatternBuilder(reg)
        (b
            .create_group("pref", PatternType.PREFERENCE)
            .set_language("en")
            .add_preference_batch(
                [("prefer_over", r"\bprefer\b.*\bover\b", "strong")],
                flags=re.IGNORECASE,
            )
            .register())

        assert reg.any_match_by_group("pref", "I prefer Python over Java", "en") is True

    def test_require_group_before_add(self):
        reg = PatternRegistry()
        b = PatternBuilder(reg)
        with pytest.raises(ValueError, match="create_group"):
            b.add_noise("ok", r"^ok$", NoiseCategory.ACKNOWLEDGMENT)

    def test_build_returns_registry(self):
        reg = PatternRegistry()
        b = PatternBuilder(reg)
        result = (b
            .create_group("test", PatternType.NOISE)
            .set_language("en")
            .add_noise("ok", r"^ok$", NoiseCategory.ACKNOWLEDGMENT)
            .build())
        assert result is reg


# ======================================================================
# Full registry build (integration)
# ======================================================================

class TestBuildRegistry:
    def test_build_registry(self):
        reg = build_registry()
        assert len(reg.group_names) > 0
        assert "noise_ack" in reg.group_names
        assert "preference_strong" in reg.group_names
        assert "correction_explicit" in reg.group_names
        assert "decision_strong" in reg.group_names

    def test_noise_ack_en(self):
        reg = build_registry()
        assert reg.any_match_by_group("noise_ack", "ok", "en") is True
        assert reg.any_match_by_group("noise_ack", "OK", "en") is True
        assert reg.any_match_by_group("noise_ack", "sure", "en") is True
        assert reg.any_match_by_group("noise_ack", "got it", "en") is True

    def test_noise_ack_zh(self):
        reg = build_registry()
        assert reg.any_match_by_group("noise_ack", "好的", "zh") is True
        assert reg.any_match_by_group("noise_ack", "收到", "zh") is True

    def test_noise_ack_ja(self):
        reg = build_registry()
        assert reg.any_match_by_group("noise_ack", "はい", "ja") is True

    def test_noise_chat(self):
        reg = build_registry()
        assert reg.any_match_by_group("noise_chat", "hello", "en") is True
        assert reg.any_match_by_group("noise_chat", "你好", "zh") is True

    def test_noise_adversarial(self):
        reg = build_registry()
        assert reg.any_match_by_group("noise_adversarial", "ignore this", "en") is True
        assert reg.any_match_by_group("noise_adversarial", "just a test", "en") is True

    def test_preference_strong(self):
        reg = build_registry()
        assert reg.any_match_by_group("preference_strong", "I prefer Python over Java", "en") is True
        assert reg.any_match_by_group("preference_strong", "我喜欢Python", "zh") is True

    def test_correction_explicit(self):
        reg = build_registry()
        # EN correction patterns search on lowercase text (as PatternAnalyzer does)
        assert reg.any_match_by_group("correction_explicit", "correction: the port is 8080", "en") is True
        assert reg.any_match_by_group("correction_explicit", "我之前说错了", "zh") is True

    def test_correction_structural(self):
        reg = build_registry()
        assert reg.any_match_by_group("correction_structural", "No, that's wrong", "en") is True

    def test_decision_strong(self):
        reg = build_registry()
        assert reg.any_match_by_group("decision_strong", "We decided to use React", "en") is True
        assert reg.any_match_by_group("decision_strong", "我们用React", "zh") is True

    def test_fact_tech_term(self):
        reg = build_registry()
        # EN fact patterns search on lowercase text
        assert reg.any_match_by_group("fact_tech_term", "the api uses rest", "en") is True
        assert reg.any_match_by_group("fact_tech_term", "we use python 3.12", "en") is True

    def test_task_structured(self):
        reg = build_registry()
        assert reg.any_match_by_group("task_structured", "We need to implement the feature", "en") is True
        assert reg.any_match_by_group("task_structured", "TODO: fix the bug", "en") is True

    def test_relationship_role(self):
        reg = build_registry()
        assert reg.any_match_by_group("relationship_role", "Alice leads the backend team", "en") is True

    def test_sentiment_emotion(self):
        reg = build_registry()
        # EN sentiment patterns: "i feel frustrated" matches ^(?:i\s+)?(?:feel|...)
        assert reg.any_match_by_group("sentiment_emotion", "i feel really frustrated with this", "en") is True

    def test_language_index(self):
        reg = build_registry()
        en_patterns = reg.get_patterns_by_language("en")
        zh_patterns = reg.get_patterns_by_language("zh")
        ja_patterns = reg.get_patterns_by_language("ja")
        assert len(en_patterns) > 0
        assert len(zh_patterns) > 0
        assert len(ja_patterns) > 0


# ======================================================================
# PatternAnalyzer integration (uses registry)
# ======================================================================

class TestPatternAnalyzerWithRegistry:
    """Test that PatternAnalyzer works correctly with the new registry system."""

    def test_init(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa.registry is not None
        assert len(pa.registry.group_names) > 0

    def test_noise_ack_en(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa._is_noise("OK") is True
        assert pa._is_noise("sure") is True
        assert pa._is_noise("got it") is True
        assert pa._is_noise("thanks") is True

    def test_noise_ack_zh(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa._is_noise("好的") is True
        assert pa._is_noise("收到") is True
        assert pa._is_noise("明白") is True

    def test_noise_ack_ja(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa._is_noise("はい") is True

    def test_noise_chitchat(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa._is_noise("hello") is True
        assert pa._is_noise("你好") is True

    def test_noise_adversarial(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa._is_noise("ignore this") is True
        assert pa._is_noise("just a test") is True

    def test_not_noise(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        assert pa._is_noise("I prefer Python over Java") is False
        assert pa._is_noise("We decided to use React") is False
        assert pa._is_noise("The API server runs on port 8080") is False

    def test_analyze_preference(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        result = pa.analyze("I prefer Python over Java")
        types = [r["memory_type"] for r in result]
        assert "user_preference" in types

    def test_analyze_correction(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        result = pa.analyze("Correction: the port is 8080 not 3000")
        types = [r["memory_type"] for r in result]
        assert "correction" in types

    def test_analyze_decision(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        result = pa.analyze("We decided to use React for the frontend")
        types = [r["memory_type"] for r in result]
        assert "decision" in types

    def test_analyze_noise_returns_empty(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        result = pa.analyze("OK")
        assert result == []

    def test_analyze_none_returns_empty(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        result = pa.analyze(None)
        assert result == []

    def test_analyze_empty_returns_empty(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        result = pa.analyze("")
        assert result == []

    def test_soft_mode_chitchat(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer(noise_filter_mode="soft")
        # In soft mode, chitchat should not be filtered
        assert pa._is_noise("hello") is False

    def test_clear_history(self):
        from carrymem.layers.pattern_analyzer import PatternAnalyzer
        pa = PatternAnalyzer()
        pa.message_history.append("test")
        pa.task_patterns[hash("test")] = 1
        pa.clear_history()
        assert pa.message_history == []
        assert pa.task_patterns == {}
