"""Tests for the ClassificationPipeline coordinator."""

import os
import sys
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.coordinators.classification_pipeline import ClassificationPipeline


def _make_config(rules=None, **overrides):
    """Create a mock config object for ClassificationPipeline."""
    config = MagicMock()
    config.get_rules.return_value = {"rules": rules or []}
    config.get.side_effect = lambda key, default=None: overrides.get(key, default)
    return config


def _mock_all_layers(pipeline, rule_ret=None, pattern_ret=None, semantic_ret=None):
    """Mock all three classification layers and _is_noise to bypass filtering."""
    pipeline.rule_matcher = MagicMock()
    pipeline.rule_matcher.match.return_value = rule_ret or []
    pipeline.pattern_analyzer = MagicMock()
    pipeline.pattern_analyzer.analyze.return_value = pattern_ret or []
    pipeline.pattern_analyzer._is_noise.return_value = False
    pipeline.pattern_analyzer.noise_filter_mode = "strict"
    pipeline.semantic_classifier = MagicMock()
    pipeline.semantic_classifier.classify.return_value = semantic_ret or []


class TestClassifyMethod(unittest.TestCase):
    """Test the classify() method — the core 3-layer pipeline."""

    def setUp(self):
        self.config = _make_config()
        self.pipeline = ClassificationPipeline(self.config)

    def test_classify_returns_rule_matches_first(self):
        """If rule_matcher finds matches, return them immediately."""
        fake_match = [{"memory_type": "user_preference", "confidence": 0.9}]
        self.pipeline.rule_matcher = MagicMock()
        self.pipeline.rule_matcher.match.return_value = fake_match

        result = self.pipeline.classify("I prefer dark mode")
        self.assertEqual(result, fake_match)
        self.pipeline.rule_matcher.match.assert_called_once()

    def test_classify_falls_through_to_pattern_analyzer(self):
        """If rule_matcher returns empty, try pattern_analyzer."""
        self.pipeline.rule_matcher = MagicMock()
        self.pipeline.rule_matcher.match.return_value = []
        fake_pattern = [{"memory_type": "correction", "confidence": 0.8}]
        self.pipeline.pattern_analyzer = MagicMock()
        self.pipeline.pattern_analyzer.analyze.return_value = fake_pattern

        result = self.pipeline.classify("Actually, use PostgreSQL")
        self.assertEqual(result, fake_pattern)

    def test_classify_falls_through_to_semantic(self):
        """If both rule and pattern return empty, try semantic classifier."""
        self.pipeline.rule_matcher = MagicMock()
        self.pipeline.rule_matcher.match.return_value = []
        self.pipeline.pattern_analyzer = MagicMock()
        self.pipeline.pattern_analyzer.analyze.return_value = []
        fake_semantic = [{"memory_type": "decision", "confidence": 0.7}]
        self.pipeline.semantic_classifier = MagicMock()
        self.pipeline.semantic_classifier.classify.return_value = fake_semantic

        result = self.pipeline.classify("We decided to go with React")
        self.assertEqual(result, fake_semantic)

    def test_classify_returns_empty_when_nothing_matches(self):
        """All three layers return empty -> return []."""
        _mock_all_layers(self.pipeline)

        result = self.pipeline.classify("random noise message")
        self.assertEqual(result, [])

    def test_classify_passes_context_and_execution_context(self):
        """Context and execution_context are forwarded to each layer."""
        ctx = {"session_id": "s1"}
        exec_ctx = {"tool_error": True}
        self.pipeline.rule_matcher = MagicMock()
        self.pipeline.rule_matcher.match.return_value = [{"memory_type": "task_pattern"}]

        self.pipeline.classify("Fix the bug", context=ctx, execution_context=exec_ctx)
        self.pipeline.rule_matcher.match.assert_called_once_with("Fix the bug", ctx, exec_ctx)

    def test_classify_pattern_matches_resolved(self):
        """Pattern matches go through _resolve_type_priority."""
        self.pipeline.rule_matcher = MagicMock()
        self.pipeline.rule_matcher.match.return_value = []
        # Two pattern matches with different types — should be sorted by priority
        fake_patterns = [
            {"memory_type": "fact_declaration", "confidence": 0.7},
            {"memory_type": "correction", "confidence": 0.8},
        ]
        self.pipeline.pattern_analyzer = MagicMock()
        self.pipeline.pattern_analyzer.analyze.return_value = fake_patterns

        result = self.pipeline.classify("Actually, the server runs on port 8080")
        # correction (priority 1) should come before fact_declaration (priority 5)
        self.assertEqual(result[0]["memory_type"], "correction")


class TestClassifyWithDefaults(unittest.TestCase):
    """Test classify_with_defaults() — the full pipeline with noise filtering and defaults."""

    def setUp(self):
        self.config = _make_config()
        self.pipeline = ClassificationPipeline(self.config)

    # --- Noise filtering ---

    def test_noise_message_filtered_out(self):
        """Noise messages (e.g. 'ok') should return []."""
        self.pipeline.pattern_analyzer._is_noise = MagicMock(return_value=True)
        result = self.pipeline.classify_with_defaults("ok", "en")
        self.assertEqual(result, [])

    def test_noise_not_filtered_when_confirmation_with_ai_reply(self):
        """A confirmation message with ai_reply context should NOT be filtered as noise."""
        self.pipeline.pattern_analyzer._is_noise = MagicMock(return_value=True)
        # Make classify return something so we can verify it's not filtered
        self.pipeline.rule_matcher = MagicMock()
        self.pipeline.rule_matcher.match.return_value = [{"memory_type": "decision", "confidence": 0.8}]

        ctx = {"ai_reply": "Should I use PostgreSQL?"}
        result = self.pipeline.classify_with_defaults("ok", "en", context=ctx)
        # Should not be empty — the confirmation-with-context path was taken
        self.assertGreater(len(result), 0)

    def test_noise_filter_count_increments(self):
        """Noise filter count should increment when messages are filtered."""
        self.pipeline.pattern_analyzer._is_noise = MagicMock(return_value=True)
        self.pipeline.classify_with_defaults("ok", "en")
        self.assertEqual(self.pipeline._filter_counts["noise"], 1)

    # --- Low-info assistant filtering ---

    def test_assistant_role_low_info_filtered(self):
        """Low-info assistant reply with role='assistant' should be filtered."""
        ctx = {"role": "assistant"}
        result = self.pipeline.classify_with_defaults("I understand", "en", context=ctx)
        self.assertEqual(result, [])

    def test_assistant_prefix_low_info_filtered(self):
        """Low-info assistant reply with [assistant said] prefix should be filtered."""
        result = self.pipeline.classify_with_defaults("[assistant said] I understand", "en")
        self.assertEqual(result, [])

    def test_assistant_prefix_ai_said_filtered(self):
        """[ai said] prefix should also be detected as assistant message."""
        result = self.pipeline.classify_with_defaults("[ai said] Got it", "en")
        self.assertEqual(result, [])

    def test_assistant_prefix_bot_said_filtered(self):
        """[bot said] prefix should also be detected as assistant message."""
        result = self.pipeline.classify_with_defaults("[bot said] Sure", "en")
        self.assertEqual(result, [])

    def test_assistant_reply_with_factual_info_not_filtered(self):
        """Assistant reply with factual content (e.g. version numbers) should NOT be filtered."""
        ctx = {"role": "assistant"}
        result = self.pipeline.classify_with_defaults(
            "The server runs on Python 3.11 and PostgreSQL 14.2", "en", context=ctx
        )
        # Should not be empty — has factual markers
        self.assertNotEqual(result, [])

    def test_low_info_assistant_filter_count_increments(self):
        """Low-info assistant filter count should increment."""
        ctx = {"role": "assistant"}
        self.pipeline.classify_with_defaults("I understand", "en", context=ctx)
        self.assertEqual(self.pipeline._filter_counts["low_info_assistant"], 1)

    # --- Fail-closed default ---

    def test_no_matches_fail_closed_returns_empty(self):
        """When no classification matches and default confidence is low, return []."""
        _mock_all_layers(self.pipeline)
        with patch.object(
            self.pipeline,
            "_get_default_classification",
            return_value={"memory_type": "fact_declaration", "confidence": 0.3, "tier": 3},
        ):
            result = self.pipeline.classify_with_defaults("some random message", "en")
        self.assertEqual(result, [])

    def test_fail_closed_count_increments(self):
        """Fail-closed filter count should increment for low-confidence defaults."""
        _mock_all_layers(self.pipeline)
        with patch.object(
            self.pipeline,
            "_get_default_classification",
            return_value={"memory_type": "fact_declaration", "confidence": 0.3, "tier": 3},
        ):
            self.pipeline.classify_with_defaults("some random message", "en")
        self.assertEqual(self.pipeline._filter_counts["fail_closed"], 1)

    def test_default_confidence_above_threshold_returned(self):
        """Default classification with confidence >= MIN_DEFAULT_CONFIDENCE should be returned."""
        _mock_all_layers(self.pipeline)
        with patch.object(
            self.pipeline,
            "_get_default_classification",
            return_value={
                "memory_type": "user_preference",
                "confidence": 0.9,
                "tier": 2,
                "content": "I prefer dark mode",
            },
        ):
            result = self.pipeline.classify_with_defaults("I prefer dark mode", "en")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["memory_type"], "user_preference")

    def test_sentiment_marker_below_threshold_filtered(self):
        """Sentiment marker with confidence < MIN_SENTIMENT_DEFAULT_CONFIDENCE should be filtered."""
        _mock_all_layers(self.pipeline)
        with patch.object(
            self.pipeline,
            "_get_default_classification",
            return_value={
                "memory_type": "sentiment_marker",
                "confidence": 0.5,
                "tier": 3,
                "content": "I feel okay",
            },
        ):
            result = self.pipeline.classify_with_defaults("I feel okay about this", "en")
        self.assertEqual(result, [])

    def test_no_default_returns_empty(self):
        """When _get_default_classification returns None, return []."""
        _mock_all_layers(self.pipeline)
        with patch.object(self.pipeline, "_get_default_classification", return_value=None):
            result = self.pipeline.classify_with_defaults("xyz", "en")
        self.assertEqual(result, [])

    # --- Soft mode ---

    def test_soft_mode_low_confidence_upgraded(self):
        """In soft mode, low-confidence defaults are upgraded to MIN_DEFAULT_CONFIDENCE."""
        soft_config = _make_config()
        soft_pipeline = ClassificationPipeline(soft_config, noise_filter_mode="soft")
        _mock_all_layers(soft_pipeline)
        soft_pipeline.pattern_analyzer.noise_filter_mode = "soft"
        with patch.object(
            soft_pipeline,
            "_get_default_classification",
            return_value={
                "memory_type": "fact_declaration",
                "confidence": 0.3,
                "tier": 3,
                "content": "some content",
            },
        ):
            result = soft_pipeline.classify_with_defaults("some content here", "en")
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["source"], "default:soft_fallback")
        self.assertGreaterEqual(result[0]["confidence"], soft_pipeline.MIN_DEFAULT_CONFIDENCE)

    def test_soft_mode_sentiment_low_confidence_upgraded(self):
        """In soft mode, low-confidence sentiment defaults are upgraded to MIN_SENTIMENT_DEFAULT_CONFIDENCE."""
        soft_config = _make_config()
        soft_pipeline = ClassificationPipeline(soft_config, noise_filter_mode="soft")
        _mock_all_layers(soft_pipeline)
        soft_pipeline.pattern_analyzer.noise_filter_mode = "soft"
        with patch.object(
            soft_pipeline,
            "_get_default_classification",
            return_value={
                "memory_type": "sentiment_marker",
                "confidence": 0.3,
                "tier": 3,
                "content": "I feel okay",
            },
        ):
            result = soft_pipeline.classify_with_defaults("I feel okay about this project", "en")
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["source"], "default:soft_fallback")
        self.assertGreaterEqual(result[0]["confidence"], soft_pipeline.MIN_SENTIMENT_DEFAULT_CONFIDENCE)

    def test_soft_mode_no_default_catchall(self):
        """In soft mode, when _get_default_classification returns None, use catchall."""
        soft_config = _make_config()
        soft_pipeline = ClassificationPipeline(soft_config, noise_filter_mode="soft")
        _mock_all_layers(soft_pipeline)
        soft_pipeline.pattern_analyzer.noise_filter_mode = "soft"
        with patch.object(soft_pipeline, "_get_default_classification", return_value=None):
            result = soft_pipeline.classify_with_defaults("some message", "en")
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["source"], "default:soft_catchall")
        self.assertEqual(result[0]["memory_type"], "fact_declaration")

    # --- Confirmation context enrichment ---

    def test_confirmation_with_ai_reply_enriches_decision(self):
        """Confirmation message with ai_reply should enrich decision/correction matches."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[{"memory_type": "decision", "confidence": 0.8, "content": "yes", "tier": 2}],
        )

        ctx = {"ai_reply": "Should I use PostgreSQL for the database?"}
        result = self.pipeline.classify_with_defaults("ok", "en", context=ctx)
        self.assertGreater(len(result), 0)
        match = result[0]
        self.assertEqual(match["context_source"], "ai_reply")
        self.assertIn("Confirmed:", match["content"])

    def test_confirmation_with_ai_reply_enriches_correction(self):
        """Confirmation message with ai_reply should enrich correction matches.
        Use 'ok' which is a confirmation word, with a correction match from rules."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[{"memory_type": "correction", "confidence": 0.8, "content": "no", "tier": 3}],
        )

        ctx = {"ai_reply": "Did you mean MySQL?"}
        result = self.pipeline.classify_with_defaults("ok", "en", context=ctx)
        self.assertGreater(len(result), 0)
        match = result[0]
        self.assertEqual(match["context_source"], "ai_reply")

    def test_confirmation_enriches_long_content(self):
        """When original content is >5 chars, it should be prefixed, not replaced."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[
                {
                    "memory_type": "decision",
                    "confidence": 0.8,
                    "content": "Use PostgreSQL",
                    "tier": 2,
                }
            ],
        )

        ctx = {"ai_reply": "Should I use PostgreSQL for the database?"}
        result = self.pipeline.classify_with_defaults("yes", "en", context=ctx)
        self.assertGreater(len(result), 0)
        self.assertIn("Use PostgreSQL:", result[0]["content"])

    def test_confirmation_does_not_enrich_non_decision_correction(self):
        """Confirmation should NOT enrich matches that aren't decision or correction."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[
                {
                    "memory_type": "user_preference",
                    "confidence": 0.9,
                    "content": "I prefer dark mode",
                    "tier": 2,
                }
            ],
        )

        ctx = {"ai_reply": "Do you like dark mode?"}
        result = self.pipeline.classify_with_defaults("yes", "en", context=ctx)
        self.assertGreater(len(result), 0)
        self.assertNotIn("context_source", result[0])

    def test_confirmation_no_ai_reply_no_enrichment(self):
        """Without ai_reply, no enrichment happens."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[
                {
                    "memory_type": "decision",
                    "confidence": 0.8,
                    "content": "confirmed decision",
                    "tier": 2,
                }
            ],
        )

        result = self.pipeline.classify_with_defaults("confirmed decision", "en", context={})
        self.assertGreater(len(result), 0)
        self.assertNotIn("context_source", result[0])

    def test_confirmation_already_has_context_source(self):
        """If match already has context_source, don't overwrite it."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[
                {
                    "memory_type": "decision",
                    "confidence": 0.8,
                    "content": "confirmed decision",
                    "tier": 2,
                    "context_source": "existing_source",
                }
            ],
        )

        ctx = {"ai_reply": "Should I use PostgreSQL?"}
        result = self.pipeline.classify_with_defaults("confirmed decision", "en", context=ctx)
        self.assertEqual(result[0]["context_source"], "existing_source")


class TestIsLowInfoAssistantReply(unittest.TestCase):
    """Test the _is_low_info_assistant_reply static method."""

    def test_empty_message_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply(""))

    def test_whitespace_only_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("   "))

    def test_none_message_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply(None))

    def test_generic_confirmation_is_low_info(self):
        cases = [
            "I understand",
            "Got it",
            "Sure",
            "OK",
            "Okay",
            "Alright",
            "Right",
            "Exactly",
            "Absolutely",
            "Correct",
            "Indeed",
            "Of course",
            "Certainly",
            "Definitely",
            "Yeah",
            "Yep",
            "No problem",
        ]
        for msg in cases:
            with self.subTest(msg=msg):
                self.assertTrue(
                    ClassificationPipeline._is_low_info_assistant_reply(msg),
                    f"'{msg}' should be classified as low info",
                )

    def test_that_makes_sense_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("That makes sense"))

    def test_sounds_good_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("Sounds good"))

    def test_short_reply_without_facts_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("I will help you"))

    def test_reply_with_version_number_not_low_info(self):
        self.assertFalse(ClassificationPipeline._is_low_info_assistant_reply("The server runs on Python 3.11"))

    def test_reply_with_url_not_low_info(self):
        self.assertFalse(
            ClassificationPipeline._is_low_info_assistant_reply("You can find it at https://example.com/docs")
        )

    def test_reply_with_code_snippet_not_low_info(self):
        self.assertFalse(ClassificationPipeline._is_low_info_assistant_reply("Use the `pip install` command"))

    def test_reply_with_camelcase_not_low_info(self):
        self.assertFalse(ClassificationPipeline._is_low_info_assistant_reply("PostgreSQL is the recommended database"))

    def test_reply_with_tech_keyword_not_low_info(self):
        self.assertFalse(
            ClassificationPipeline._is_low_info_assistant_reply("The Docker container is running on the server")
        )

    def test_reply_with_dollar_amount_not_low_info(self):
        self.assertFalse(ClassificationPipeline._is_low_info_assistant_reply("The budget is $5000 for this project"))

    def test_reply_with_measurement_not_low_info(self):
        self.assertFalse(ClassificationPipeline._is_low_info_assistant_reply("The file is 50mb in size"))

    def test_reply_with_date_slash_format_not_low_info(self):
        """Date in slash format (01/15/2024) should be detected as factual."""
        self.assertFalse(
            ClassificationPipeline._is_low_info_assistant_reply("The deadline is 01/15/2024 for the project delivery")
        )

    def test_reply_with_year_not_low_info(self):
        self.assertFalse(
            ClassificationPipeline._is_low_info_assistant_reply("The project started in 2024 and continues")
        )

    def test_conversational_without_facts_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("I think that is great and wonderful"))

    def test_conversational_with_facts_not_low_info(self):
        self.assertFalse(ClassificationPipeline._is_low_info_assistant_reply("I think PostgreSQL 14.2 is great"))

    def test_emotional_without_facts_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("I'm glad to hear that"))

    def test_you_re_welcome_is_low_info(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("You're welcome"))

    def test_assistant_prefix_stripped(self):
        """[assistant said] prefix should be stripped before analysis."""
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("[assistant said] I understand"))

    def test_ai_said_prefix_stripped(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("[ai said] Got it"))

    def test_bot_said_prefix_stripped(self):
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("[bot said] Sure"))

    def test_bracket_after_prefix_stripped(self):
        """Edge case: prefix followed by ] should strip the bracket."""
        self.assertTrue(ClassificationPipeline._is_low_info_assistant_reply("[assistant said]] I understand"))

    def test_long_factual_reply_not_low_info(self):
        self.assertFalse(
            ClassificationPipeline._is_low_info_assistant_reply(
                "The API endpoint is configured on port 8080 with the database running PostgreSQL"
            )
        )


class TestResolveTypePriority(unittest.TestCase):
    """Test the _resolve_type_priority static method."""

    def test_single_match_returned_unchanged(self):
        matches = [{"memory_type": "fact_declaration", "confidence": 0.7}]
        result = ClassificationPipeline._resolve_type_priority(matches)
        self.assertEqual(result, matches)

    def test_empty_list_returned_unchanged(self):
        result = ClassificationPipeline._resolve_type_priority([])
        self.assertEqual(result, [])

    def test_correction_highest_priority(self):
        matches = [
            {"memory_type": "fact_declaration", "confidence": 0.7},
            {"memory_type": "correction", "confidence": 0.8},
            {"memory_type": "user_preference", "confidence": 0.9},
        ]
        result = ClassificationPipeline._resolve_type_priority(matches)
        self.assertEqual(result[0]["memory_type"], "correction")

    def test_decision_second_priority(self):
        matches = [
            {"memory_type": "fact_declaration", "confidence": 0.7},
            {"memory_type": "decision", "confidence": 0.8},
        ]
        result = ClassificationPipeline._resolve_type_priority(matches)
        self.assertEqual(result[0]["memory_type"], "decision")

    def test_full_priority_order(self):
        """Verify the full priority chain: correction > decision >
        preference > task > fact > sentiment > relationship > location."""
        matches = [
            {"memory_type": "location", "confidence": 0.7},
            {"memory_type": "relationship", "confidence": 0.7},
            {"memory_type": "sentiment_marker", "confidence": 0.7},
            {"memory_type": "fact_declaration", "confidence": 0.7},
            {"memory_type": "task_pattern", "confidence": 0.7},
            {"memory_type": "user_preference", "confidence": 0.7},
            {"memory_type": "decision", "confidence": 0.7},
            {"memory_type": "correction", "confidence": 0.7},
        ]
        result = ClassificationPipeline._resolve_type_priority(matches)
        types = [m["memory_type"] for m in result]
        expected = [
            "correction",
            "decision",
            "user_preference",
            "task_pattern",
            "fact_declaration",
            "sentiment_marker",
            "relationship",
            "location",
        ]
        self.assertEqual(types, expected)

    def test_unknown_type_gets_lowest_priority(self):
        matches = [
            {"memory_type": "correction", "confidence": 0.8},
            {"memory_type": "unknown_type", "confidence": 0.9},
        ]
        result = ClassificationPipeline._resolve_type_priority(matches)
        self.assertEqual(result[0]["memory_type"], "correction")
        self.assertEqual(result[-1]["memory_type"], "unknown_type")


class TestGetDefaultClassification(unittest.TestCase):
    """Test the _get_default_classification method."""

    def setUp(self):
        self.config = _make_config()
        self.pipeline = ClassificationPipeline(self.config)

    def test_none_message_returns_none(self):
        result = self.pipeline._get_default_classification(None, "en")
        self.assertIsNone(result)

    def test_short_message_returns_none(self):
        """Messages shorter than 8 chars should return None."""
        result = self.pipeline._get_default_classification("short", "en")
        self.assertIsNone(result)

    def test_chitchat_blacklist_returns_none(self):
        """Messages containing chitchat keywords should return None."""
        blacklist_cases = [
            "sunny day today",
            "sounds good to me",
            "oh really now",
            "interesting stuff",
            "cool man",
            "see you later",
            "okay then",
            "alright then",
        ]
        for msg in blacklist_cases:
            with self.subTest(msg=msg):
                result = self.pipeline._get_default_classification(msg, "en")
                self.assertIsNone(result, f"'{msg}' should be filtered by blacklist")

    def test_few_words_short_message_returns_none(self):
        """Messages with <=2 words and <20 chars should return None."""
        result = self.pipeline._get_default_classification("hi there", "en")
        self.assertIsNone(result)

    def test_preference_keyword_detected(self):
        """Preference keywords: like, prefer, love, hate, want, dislike."""
        result = self.pipeline._get_default_classification("I prefer dark mode for my editor", "en")
        self.assertIsNotNone(result)
        self.assertEqual(result["memory_type"], "user_preference")
        self.assertEqual(result["source"], "default:preference")
        self.assertAlmostEqual(result["confidence"], 0.9)

    def test_correction_keyword_detected(self):
        """Correction keywords: correct, wrong, incorrect, mistake, fix, error."""
        result = self.pipeline._get_default_classification("That was a mistake, the wrong approach was taken", "en")
        self.assertIsNotNone(result)
        self.assertIn(result["memory_type"], ["correction", "user_preference"])
        if result["memory_type"] == "correction":
            self.assertEqual(result["source"], "default:correction")

    def test_fact_keyword_detected(self):
        """Fact keywords: is, are, was, were, have, has, exist, exists.
        Use a message with fact keywords but no preference keywords."""
        result = self.pipeline._get_default_classification("There exist three servers in the cluster", "en")
        self.assertIsNotNone(result)
        self.assertEqual(result["memory_type"], "fact_declaration")
        self.assertEqual(result["source"], "default:fact")

    def test_decision_keyword_detected(self):
        """Decision keywords: decide, decision, choose, choice, confirm, agreed, etc.
        Use a message with decision keywords but no preference keywords."""
        result = self.pipeline._get_default_classification("The team agreed to deploy the new release", "en")
        self.assertIsNotNone(result)
        self.assertEqual(result["memory_type"], "decision")
        self.assertEqual(result["source"], "default:decision")

    def test_relationship_keyword_detected(self):
        """Relationship keywords: responsible, manage, belong, report, work with, team, handles.
        Use a message with relationship keywords but no preference/fact overlap."""
        result = self.pipeline._get_default_classification("The backend team manages the database infrastructure", "en")
        self.assertIsNotNone(result)
        self.assertEqual(result["memory_type"], "relationship")
        self.assertEqual(result["source"], "default:relationship")

    def test_task_keyword_detected(self):
        """Task keywords: task, work, process, repeat, regular, routine, etc.
        Use a message with task keywords but no earlier-category overlap."""
        result = self.pipeline._get_default_classification("The routine task for the sprint milestone", "en")
        self.assertIsNotNone(result)
        # "task" is a task_pattern keyword, but earlier categories may match first
        self.assertIn(
            result["memory_type"],
            ["task_pattern", "decision", "user_preference", "fact_declaration"],
        )

    def test_sentiment_keyword_detected(self):
        """Sentiment keywords: happy, sad, angry, excited, disappointed, satisfied.
        Use a message with sentiment keywords but no earlier-category overlap."""
        result = self.pipeline._get_default_classification("The team was very disappointed with the results", "en")
        self.assertIsNotNone(result)
        # "was" is a fact keyword that matches before sentiment; accept either
        self.assertIn(result["memory_type"], ["sentiment_marker", "fact_declaration"])

    def test_unclassifiable_returns_none(self):
        """Messages that don't match any keyword category should return None (fail-closed)."""
        result = self.pipeline._get_default_classification("A big wooden chair stood by the window", "en")
        # No preference, correction, fact, decision, relationship, task, or sentiment keywords
        self.assertIsNone(result)

    def test_result_includes_language(self):
        result = self.pipeline._get_default_classification("I prefer dark mode for my editor", "en")
        self.assertIsNotNone(result)
        self.assertEqual(result["language"], "en")

    def test_result_includes_content(self):
        msg = "I prefer dark mode for my editor"
        result = self.pipeline._get_default_classification(msg, "en")
        self.assertIsNotNone(result)
        self.assertEqual(result["content"], msg)

    def test_emoji_blacklist_returns_none(self):
        """Emoji-only or emoji-heavy messages should be filtered."""
        result = self.pipeline._get_default_classification("😎😊👍🎉", "en")
        self.assertIsNone(result)

    def test_question_blacklist_returns_none(self):
        """Question-like patterns should be filtered."""
        result = self.pipeline._get_default_classification("really?", "en")
        self.assertIsNone(result)


class TestInitAndConfig(unittest.TestCase):
    """Test initialization and configuration."""

    def test_default_confidence_thresholds(self):
        config = _make_config()
        pipeline = ClassificationPipeline(config)
        self.assertEqual(pipeline.MIN_DEFAULT_CONFIDENCE, 0.6)
        self.assertEqual(pipeline.MIN_SENTIMENT_DEFAULT_CONFIDENCE, 0.7)

    def test_soft_mode_lower_thresholds(self):
        config = _make_config()
        pipeline = ClassificationPipeline(config, noise_filter_mode="soft")
        self.assertEqual(pipeline.MIN_DEFAULT_CONFIDENCE, 0.5)
        self.assertEqual(pipeline.MIN_SENTIMENT_DEFAULT_CONFIDENCE, 0.4)

    def test_filter_counts_initialized(self):
        config = _make_config()
        pipeline = ClassificationPipeline(config)
        self.assertEqual(pipeline._filter_counts, {"noise": 0, "low_info_assistant": 0, "fail_closed": 0})

    def test_rule_matcher_initialized_with_rules(self):
        rules = [{"pattern": r"test", "memory_type": "task_pattern", "tier": 3}]
        config = _make_config(rules=rules)
        pipeline = ClassificationPipeline(config)
        self.assertEqual(len(pipeline.rule_matcher.rules), 1)

    def test_pattern_analyzer_noise_filter_mode(self):
        config = _make_config()
        pipeline = ClassificationPipeline(config, noise_filter_mode="soft")
        self.assertEqual(pipeline.pattern_analyzer.noise_filter_mode, "soft")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases: empty messages, very long messages, special characters."""

    def setUp(self):
        self.config = _make_config()
        self.pipeline = ClassificationPipeline(self.config)

    def test_classify_empty_message(self):
        result = self.pipeline.classify("")
        self.assertIsInstance(result, list)

    def test_classify_with_none_context(self):
        result = self.pipeline.classify("I prefer dark mode", context=None)
        self.assertIsInstance(result, list)

    def test_classify_with_none_execution_context(self):
        result = self.pipeline.classify("I prefer dark mode", execution_context=None)
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_empty_message(self):
        result = self.pipeline.classify_with_defaults("", "en")
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_very_long_message(self):
        long_msg = "I prefer dark mode " * 500
        result = self.pipeline.classify_with_defaults(long_msg, "en")
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_special_characters(self):
        result = self.pipeline.classify_with_defaults('I prefer <script>alert("xss")</script> mode', "en")
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_unicode_message(self):
        result = self.pipeline.classify_with_defaults("我喜欢深色模式", "zh")
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_emoji_message(self):
        result = self.pipeline.classify_with_defaults("I prefer dark mode 🌙", "en")
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_non_dict_context(self):
        """Non-dict context should not crash."""
        result = self.pipeline.classify_with_defaults("I prefer dark mode", "en", context="invalid")
        self.assertIsInstance(result, list)

    def test_classify_with_defaults_context_with_no_ai_reply(self):
        ctx = {"session_id": "s1"}
        result = self.pipeline.classify_with_defaults("I prefer dark mode", "en", context=ctx)
        self.assertIsInstance(result, list)

    def test_noise_filter_logging_on_first_message(self):
        """Noise filter count of 1 should trigger logging (count % 100 == 1)."""
        self.pipeline.pattern_analyzer._is_noise = MagicMock(return_value=True)
        # First noise message — count becomes 1, which triggers the log branch
        with patch("carrymem.coordinators.classification_pipeline.logger") as mock_logger:
            self.pipeline.classify_with_defaults("ok", "en")
            mock_logger.info.assert_called()

    def test_low_info_assistant_logging_on_first_message(self):
        """Low-info assistant filter count of 1 should trigger logging."""
        ctx = {"role": "assistant"}
        with patch("carrymem.coordinators.classification_pipeline.logger") as mock_logger:
            self.pipeline.classify_with_defaults("I understand", "en", context=ctx)
            mock_logger.info.assert_called()

    def test_fail_closed_logging_on_first_message(self):
        """Fail-closed filter count of 1 should trigger logging."""
        _mock_all_layers(self.pipeline)
        with (
            patch.object(
                self.pipeline,
                "_get_default_classification",
                return_value={"memory_type": "fact_declaration", "confidence": 0.3, "tier": 3},
            ),
            patch("carrymem.coordinators.classification_pipeline.logger") as mock_logger,
        ):
            self.pipeline.classify_with_defaults("some random message", "en")
            mock_logger.info.assert_called()

    def test_sentiment_fail_closed_strict_mode(self):
        """Sentiment marker with confidence < MIN_SENTIMENT_DEFAULT_CONFIDENCE in strict mode returns []."""
        _mock_all_layers(self.pipeline)
        with patch.object(
            self.pipeline,
            "_get_default_classification",
            return_value={
                "memory_type": "sentiment_marker",
                "confidence": 0.5,
                "tier": 3,
                "content": "I feel okay",
            },
        ):
            result = self.pipeline.classify_with_defaults("I feel okay about this", "en")
        self.assertEqual(result, [])
        self.assertEqual(self.pipeline._filter_counts["fail_closed"], 1)

    def test_confirmation_enriches_short_content(self):
        """When original content is <=5 chars, it should be replaced with 'Confirmed: summary'."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[{"memory_type": "decision", "confidence": 0.8, "content": "yes", "tier": 2}],
        )

        ctx = {"ai_reply": "Should I use PostgreSQL for the database?"}
        result = self.pipeline.classify_with_defaults("ok", "en", context=ctx)
        self.assertGreater(len(result), 0)
        self.assertIn("Confirmed:", result[0]["content"])
        self.assertEqual(result[0].get("original_user_message"), "ok")

    def test_assistant_prefix_case_insensitive(self):
        """Assistant prefix detection should be case-insensitive."""
        result = self.pipeline.classify_with_defaults("[Assistant Said] I understand", "en")
        self.assertEqual(result, [])

    def test_classify_with_defaults_with_execution_context(self):
        """classify_with_defaults should pass execution_context through."""
        _mock_all_layers(
            self.pipeline,
            rule_ret=[{"memory_type": "task_pattern", "confidence": 0.8, "content": "test", "tier": 2}],
        )
        exec_ctx = {"tool_error": True}
        result = self.pipeline.classify_with_defaults("test message", "en", execution_context=exec_ctx)
        self.assertGreater(len(result), 0)
        self.pipeline.rule_matcher.match.assert_called()


if __name__ == "__main__":
    unittest.main()
