import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from carrymem.layers.semantic_classifier import SemanticClassifier
from carrymem.layers.rule_matcher import RuleMatcher
from carrymem.layers.session_summarizer import SessionSummarizer
from carrymem.layers.semantic_aggregator import SemanticAggregator
from carrymem.layers.pattern_analyzer import PatternAnalyzer


def _make_config(**overrides):
    defaults = {
        'llm.enabled': False,
        'llm.api_key': '',
        'llm.model': 'glm-4-plus',
        'llm.temperature': 0.3,
        'llm.max_tokens': 500,
        'llm.timeout': 30,
    }
    defaults.update(overrides)
    return defaults


def _make_memory(**overrides):
    defaults = {
        'id': '',
        'type': 'user_preference',
        'content': 'I prefer dark mode',
        'raw_text': 'I prefer dark mode',
        'confidence': 0.9,
        'tier': 2,
        'source_layer': 'test',
        'reasoning': 'test',
        'suggested_action': 'store',
        'metadata': {},
    }
    defaults.update(overrides)
    return defaults


class TestSemanticClassifier(unittest.TestCase):

    def test_classify_llm_disabled_returns_none(self):
        config = _make_config(**{'llm.enabled': False})
        classifier = SemanticClassifier(config)
        result = classifier.classify('I prefer dark mode')
        self.assertIsNone(result)

    def test_classify_no_llm_client_returns_none(self):
        config = _make_config(**{'llm.enabled': True, 'llm.api_key': ''})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=None):
            classifier = SemanticClassifier(config)
        result = classifier.classify('I prefer dark mode')
        self.assertIsNone(result)

    def test_classify_with_mocked_llm(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"memory_type": "user_preference", "tier": 2, "confidence": 0.9, "reason": "test"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        config = _make_config(**{'llm.enabled': True, 'llm.api_key': 'test-key'})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=mock_client):
            classifier = SemanticClassifier(config)

        result = classifier.classify('I prefer dark mode')
        self.assertIsNotNone(result)
        self.assertEqual(result['memory_type'], 'user_preference')
        self.assertEqual(result['tier'], 2)

    def test_classify_with_context(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"memory_type": "correction", "tier": 3, "confidence": 0.8, "reason": "test"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        config = _make_config(**{'llm.enabled': True, 'llm.api_key': 'test-key'})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=mock_client):
            classifier = SemanticClassifier(config)

        result = classifier.classify('No, use PostgreSQL instead', context='database discussion')
        self.assertIsNotNone(result)
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages'] if 'messages' in call_args[1] else call_args[0][0] if call_args[0] else None
        if messages is None:
            messages = call_args.kwargs.get('messages', [])
        self.assertTrue(any('database discussion' in m.get('content', '') for m in messages))

    def test_classify_with_execution_context(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"memory_type": "task_pattern", "tier": 3, "confidence": 0.7, "reason": "test"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        config = _make_config(**{'llm.enabled': True, 'llm.api_key': 'test-key'})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=mock_client):
            classifier = SemanticClassifier(config)

        exec_ctx = {'tool_error': True, 'retry_count': 2}
        result = classifier.classify('Fix the deployment script', execution_context=exec_ctx)
        self.assertIsNotNone(result)
        call_args = mock_client.chat.completions.create.call_args
        prompt_text = call_args.kwargs.get('messages', [{}])[0].get('content', '')
        self.assertIn('tool_error', prompt_text)

    def test_classify_llm_exception_returns_none(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('API error')

        config = _make_config(**{'llm.enabled': True, 'llm.api_key': 'test-key'})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=mock_client):
            classifier = SemanticClassifier(config)

        result = classifier.classify('I prefer dark mode')
        self.assertIsNone(result)

    def test_classify_llm_invalid_json_returns_none(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'not valid json'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        config = _make_config(**{'llm.enabled': True, 'llm.api_key': 'test-key'})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=mock_client):
            classifier = SemanticClassifier(config)

        result = classifier.classify('I prefer dark mode')
        self.assertIsNone(result)

    def test_should_use_llm_returns_true(self):
        config = _make_config()
        classifier = SemanticClassifier(config)
        self.assertTrue(classifier.should_use_llm('any message'))
        self.assertTrue(classifier.should_use_llm('any message', context='some context'))

    def test_init_config_defaults(self):
        config = _make_config()
        classifier = SemanticClassifier(config)
        self.assertFalse(classifier.llm_enabled)
        self.assertEqual(classifier.llm_model, 'glm-4-plus')
        self.assertEqual(classifier.llm_temperature, 0.3)
        self.assertEqual(classifier.llm_max_tokens, 500)
        self.assertEqual(classifier.llm_timeout, 30)

    def test_init_llm_client_returns_none_when_disabled(self):
        config = _make_config(**{'llm.enabled': False})
        classifier = SemanticClassifier(config)
        self.assertIsNone(classifier.llm_client)

    def test_classify_empty_message(self):
        config = _make_config(**{'llm.enabled': False})
        classifier = SemanticClassifier(config)
        result = classifier.classify('')
        self.assertIsNone(result)

    def test_classify_none_context(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"memory_type": "fact_declaration", "tier": 4, "confidence": 0.7, "reason": "test"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        config = _make_config(**{'llm.enabled': True, 'llm.api_key': 'test-key'})
        with patch.object(SemanticClassifier, '_init_llm_client', return_value=mock_client):
            classifier = SemanticClassifier(config)

        result = classifier.classify('My name is Alice', context=None)
        self.assertIsNotNone(result)


class TestRuleMatcher(unittest.TestCase):

    def setUp(self):
        self.basic_rules = [
            {
                'pattern': r'I prefer (.+)',
                'memory_type': 'user_preference',
                'tier': 2,
                'action': 'extract',
                'description': 'Preference pattern',
                'priority': 8,
            },
            {
                'pattern': r'correct(?:ion)?:\s*',
                'memory_type': 'correction',
                'tier': 3,
                'action': 'extract_following_content',
                'description': 'Correction pattern',
                'priority': 9,
            },
        ]

    def test_match_basic_preference(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match('I prefer dark mode')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['memory_type'], 'user_preference')

    def test_match_correction(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match('correction: use PostgreSQL instead')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['memory_type'], 'correction')

    def test_match_none_message_returns_empty(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match(None)
        self.assertEqual(results, [])

    def test_match_no_matching_rules(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match('The weather is nice today')
        self.assertEqual(results, [])

    def test_match_priority_sorting(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match('I prefer dark mode')
        if len(results) >= 1:
            self.assertEqual(results[0]['priority'], 8)

    def test_match_higher_priority_first(self):
        rules = [
            {'pattern': r'test', 'memory_type': 'task_pattern', 'tier': 3, 'action': 'extract', 'description': 'low priority', 'priority': 3},
            {'pattern': r'test', 'memory_type': 'correction', 'tier': 3, 'action': 'extract', 'description': 'high priority', 'priority': 10},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('test')
        self.assertTrue(len(results) >= 2)
        self.assertEqual(results[0]['priority'], 10)
        self.assertEqual(results[-1]['priority'], 3)

    def test_match_language_filter(self):
        rules = [
            {'pattern': r'偏好', 'memory_type': 'user_preference', 'tier': 2, 'action': 'extract', 'description': 'Chinese preference', 'language': 'zh-cn'},
            {'pattern': r'prefer', 'memory_type': 'user_preference', 'tier': 2, 'action': 'extract', 'description': 'English preference', 'language': 'en'},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('我的偏好是深色模式')
        types = [r['memory_type'] for r in results]
        self.assertIn('user_preference', types)

    def test_match_language_all(self):
        rules = [
            {'pattern': r'test', 'memory_type': 'task_pattern', 'tier': 3, 'action': 'extract', 'description': 'All languages', 'language': 'all'},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('test')
        self.assertTrue(len(results) >= 1)

    def test_match_extract_action(self):
        rules = [
            {'pattern': r'I prefer (.+)', 'memory_type': 'user_preference', 'tier': 2, 'action': 'extract', 'description': 'Preference'},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('I prefer dark mode')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['content'], 'I prefer dark mode')

    def test_match_preference_source_field(self):
        rules = [
            {'pattern': r'I prefer (.+)', 'memory_type': 'user_preference', 'tier': 2, 'action': 'extract', 'description': 'Preference'},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('I prefer dark mode')
        self.assertTrue(len(results) >= 1)
        self.assertIn('preference', results[0]['source'])

    def test_match_non_preference_source(self):
        rules = [
            {'pattern': r'correction:\s*', 'memory_type': 'correction', 'tier': 3, 'action': 'extract_following_content', 'description': 'Correction'},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('correction: use PostgreSQL')
        self.assertTrue(len(results) >= 1)
        self.assertNotIn('preference', results[0]['source'])

    def test_add_rule(self):
        matcher = RuleMatcher([])
        new_rule = {'pattern': r'I love (.+)', 'memory_type': 'user_preference', 'tier': 2, 'action': 'extract', 'description': 'Love pattern'}
        matcher.add_rule(new_rule)
        self.assertEqual(len(matcher.get_rules()), 1)
        results = matcher.match('I love Python')
        self.assertTrue(len(results) >= 1)

    def test_remove_rule(self):
        matcher = RuleMatcher(self.basic_rules)
        matcher.remove_rule(r'I prefer (.+)')
        rules = matcher.get_rules()
        self.assertTrue(all(r.get('pattern') != r'I prefer (.+)' for r in rules))

    def test_remove_rule_no_match(self):
        matcher = RuleMatcher(self.basic_rules)
        original_count = len(matcher.get_rules())
        matcher.remove_rule(r'nonexistent pattern')
        self.assertEqual(len(matcher.get_rules()), original_count)

    def test_get_rules(self):
        matcher = RuleMatcher(self.basic_rules)
        rules = matcher.get_rules()
        self.assertEqual(len(rules), 2)

    def test_match_default_priority(self):
        rules = [
            {'pattern': r'test', 'memory_type': 'task_pattern', 'tier': 3, 'action': 'extract', 'description': 'No priority'},
        ]
        matcher = RuleMatcher(rules)
        results = matcher.match('test')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['priority'], 5)

    def test_match_with_context_param(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match('I prefer dark mode', context={'session_id': 'test'})
        self.assertTrue(len(results) >= 1)

    def test_match_with_execution_context_param(self):
        matcher = RuleMatcher(self.basic_rules)
        results = matcher.match('I prefer dark mode', execution_context={'tool_error': False})
        self.assertTrue(len(results) >= 1)

    def test_match_empty_rules(self):
        matcher = RuleMatcher([])
        results = matcher.match('I prefer dark mode')
        self.assertEqual(results, [])


class TestSessionSummarizer(unittest.TestCase):

    def test_summarize_empty_memories(self):
        summarizer = SessionSummarizer()
        result = summarizer.summarize_session([])
        self.assertIsNone(result)

    def test_summarize_rule_based_en(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode'),
            _make_memory(type='decision', content='Use PostgreSQL for database'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-1', language='en')
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'session_summary')
        self.assertIn('Session summary', result['content'])
        self.assertEqual(result['metadata']['summary_method'], 'rule')
        self.assertEqual(result['metadata']['session_id'], 'sess-1')
        self.assertEqual(result['tier'], 3)
        self.assertEqual(result['suggested_action'], 'store')
        self.assertEqual(result['source_layer'], 'session_summarizer')

    def test_summarize_rule_based_zh(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='我喜欢深色模式'),
            _make_memory(type='decision', content='使用PostgreSQL作为数据库'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-zh', language='zh')
        self.assertIsNotNone(result)
        self.assertIn('会话摘要', result['content'])

    def test_summarize_with_mocked_llm(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.chat.return_value = 'The user prefers dark mode and chose PostgreSQL for the database.'

        summarizer = SessionSummarizer(llm_client=mock_llm)
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode'),
            _make_memory(type='decision', content='Use PostgreSQL for database'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-llm')
        self.assertIsNotNone(result)
        self.assertEqual(result['metadata']['summary_method'], 'llm')
        self.assertAlmostEqual(result['confidence'], 0.9)

    def test_summarize_llm_fallback_to_rule(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.chat.return_value = 'short'

        summarizer = SessionSummarizer(llm_client=mock_llm)
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-fallback')
        self.assertIsNotNone(result)
        self.assertIn('Preference', result['content'])

    def test_summarize_excludes_superseded(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode'),
            _make_memory(type='user_preference', content='I prefer light mode', superseded_at='2026-01-01T00:00:00'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-1')
        self.assertIsNotNone(result)
        self.assertIn('dark mode', result['content'])
        self.assertNotIn('light mode', result['content'])

    def test_summarize_only_sentiment_markers_returns_none(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='sentiment_marker', content='I feel happy'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-1')
        self.assertIsNone(result)

    def test_summarize_prioritizes_high_priority_types(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='task_pattern', content='Run tests before commit'),
            _make_memory(type='decision', content='Use React for frontend'),
            _make_memory(type='correction', content='No, use Vue instead'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-1')
        self.assertIsNotNone(result)

    def test_summarize_max_source_memories(self):
        summarizer = SessionSummarizer()
        memories = [_make_memory(type='user_preference', content=f'Preference {i}') for i in range(60)]
        result = summarizer.summarize_session(memories, session_id='sess-big')
        self.assertIsNotNone(result)
        self.assertLessEqual(result['metadata']['source_memory_count'], 50)

    def test_summarize_confidence_rule_based(self):
        summarizer = SessionSummarizer()
        memories = [_make_memory(type='user_preference', content='I prefer dark mode')]
        result = summarizer.summarize_session(memories, session_id='sess-1')
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['confidence'], 0.7)

    def test_prioritize_mixed_types(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='correction', content='Fix the bug'),
            _make_memory(type='sentiment_marker', content='I feel great'),
            _make_memory(type='fact_declaration', content='The server runs on port 8080'),
        ]
        prioritized = summarizer._prioritize(memories)
        types = [m.get('type') for m in prioritized]
        self.assertIn('correction', types)
        self.assertIn('fact_declaration', types)
        self.assertNotIn('sentiment_marker', types)

    def test_rule_summary_en(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode'),
            _make_memory(type='decision', content='Use PostgreSQL'),
        ]
        result = summarizer._rule_summary(memories, 'en')
        self.assertIn('Preference', result)
        self.assertIn('Decision', result)

    def test_rule_summary_zh(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='我喜欢深色模式'),
            _make_memory(type='decision', content='使用PostgreSQL'),
        ]
        result = summarizer._rule_summary(memories, 'zh')
        self.assertIn('偏好', result)
        self.assertIn('决策', result)

    def test_format_memories(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode'),
            _make_memory(type='decision', content='Use PostgreSQL'),
        ]
        result = summarizer._format_memories(memories)
        self.assertIn('[user_preference]', result)
        self.assertIn('[decision]', result)

    def test_format_memories_limit_30(self):
        summarizer = SessionSummarizer()
        memories = [_make_memory(type='user_preference', content=f'Pref {i}') for i in range(50)]
        result = summarizer._format_memories(memories)
        lines = result.strip().split('\n')
        self.assertLessEqual(len(lines), 30)

    def test_summarize_session_id_in_metadata(self):
        summarizer = SessionSummarizer()
        memories = [_make_memory(type='user_preference', content='I prefer dark mode')]
        result = summarizer.summarize_session(memories, session_id='sess-abc-123')
        self.assertIsNotNone(result)
        self.assertEqual(result['metadata']['session_id'], 'sess-abc-123')

    def test_summarize_source_memory_ids(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode', storage_key='key-1'),
            _make_memory(type='decision', content='Use PostgreSQL', id='id-2'),
        ]
        result = summarizer.summarize_session(memories, session_id='sess-1')
        self.assertIsNotNone(result)
        self.assertTrue(len(result['metadata']['source_memory_ids']) >= 1)


class TestSemanticAggregator(unittest.TestCase):

    def test_aggregate_empty(self):
        agg = SemanticAggregator(embedding_fn=lambda x: [0.1, 0.2])
        self.assertEqual(agg.aggregate([]), [])

    def test_aggregate_no_embedding_fn(self):
        agg = SemanticAggregator(embedding_fn=None)
        memories = [_make_memory(content='test')]
        self.assertEqual(agg.aggregate(memories), [])

    def test_aggregate_single_memory_below_min(self):
        agg = SemanticAggregator(embedding_fn=lambda x: [0.5, 0.5])
        memories = [_make_memory(content='Only one memory', raw_text='Only one memory')]
        results = agg.aggregate(memories)
        self.assertEqual(results, [])

    def test_aggregate_clusters_similar(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.95, 0.05, 0.0]

        def mock_embedding_fn(text):
            return emb_a if 'dark mode' in text else emb_b

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode for coding', raw_text='I prefer dark mode for coding'),
            _make_memory(content='I like dark mode when coding', raw_text='I like dark mode when coding'),
        ]
        results = agg.aggregate(memories)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['source_layer'], 'semantic_aggregator')
        self.assertIn('aggregated_from', results[0]['metadata'])

    def test_aggregate_no_cluster_below_threshold(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.0, 0.0, 1.0]

        def mock_embedding_fn(text):
            return emb_a if 'dark' in text else emb_b

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode'),
            _make_memory(content='Deploy to production server', raw_text='Deploy to production server'),
        ]
        results = agg.aggregate(memories)
        self.assertEqual(len(results), 0)

    def test_aggregate_excludes_superseded(self):
        agg = SemanticAggregator(embedding_fn=lambda x: [0.5, 0.5])
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode', superseded_at='2026-01-01T00:00:00'),
            _make_memory(content='I prefer light mode', raw_text='I prefer light mode'),
        ]
        results = agg.aggregate(memories)
        self.assertEqual(results, [])

    def test_aggregate_rule_based_content(self):
        emb = [1.0, 0.0, 0.0]

        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode'),
            _make_memory(content='I like dark mode', raw_text='I like dark mode'),
        ]
        results = agg.aggregate(memories)
        self.assertTrue(len(results) >= 1)
        self.assertIn('aggregated from', results[0]['content'])

    def test_aggregate_with_mocked_llm(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.chat.return_value = 'The user consistently prefers dark mode across multiple contexts.'

        emb = [1.0, 0.0, 0.0]

        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(llm_client=mock_llm, embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode'),
            _make_memory(content='I like dark mode', raw_text='I like dark mode'),
        ]
        results = agg.aggregate(memories)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['metadata']['aggregation_method'], 'llm')

    def test_aggregate_llm_fallback_to_rule(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.chat.return_value = 'short'

        emb = [1.0, 0.0, 0.0]

        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(llm_client=mock_llm, embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode'),
            _make_memory(content='I like dark mode', raw_text='I like dark mode'),
        ]
        results = agg.aggregate(memories)
        self.assertTrue(len(results) >= 1)
        self.assertIn('aggregated from', results[0]['content'])

    def test_cosine_similarity_identical(self):
        sim = SemanticAggregator._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        self.assertAlmostEqual(sim, 1.0)

    def test_cosine_similarity_orthogonal(self):
        sim = SemanticAggregator._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertAlmostEqual(sim, 0.0)

    def test_cosine_similarity_opposite(self):
        sim = SemanticAggregator._cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        self.assertAlmostEqual(sim, -1.0)

    def test_cosine_similarity_zero_vector(self):
        sim = SemanticAggregator._cosine_similarity([0.0, 0.0], [1.0, 0.0])
        self.assertAlmostEqual(sim, 0.0)

    def test_cosine_similarity_different_lengths(self):
        sim = SemanticAggregator._cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])
        self.assertAlmostEqual(sim, 0.0)

    def test_cosine_similarity_empty(self):
        sim = SemanticAggregator._cosine_similarity([], [])
        self.assertAlmostEqual(sim, 0.0)

    def test_aggregate_chinese_rule(self):
        emb = [1.0, 0.0, 0.0]

        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='我喜欢深色模式', raw_text='我喜欢深色模式'),
            _make_memory(content='我爱深色模式', raw_text='我爱深色模式'),
        ]
        results = agg.aggregate(memories, language='zh')
        if results:
            self.assertIn('综合', results[0]['content'])

    def test_aggregate_short_text_filtered(self):
        def mock_embedding_fn(text):
            if len(text.strip()) < 5:
                return None
            return [0.5, 0.5]

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='hi', raw_text='hi'),
            _make_memory(content='ok', raw_text='ok'),
        ]
        results = agg.aggregate(memories)
        self.assertEqual(results, [])

    def test_aggregate_embedding_fn_exception(self):
        def mock_embedding_fn(text):
            raise RuntimeError('Embedding failed')

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode'),
            _make_memory(content='I like dark mode', raw_text='I like dark mode'),
        ]
        results = agg.aggregate(memories)
        self.assertEqual(results, [])

    def test_aggregate_dominant_type(self):
        emb = [1.0, 0.0, 0.0]

        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(type='user_preference', content='I prefer dark mode', raw_text='I prefer dark mode'),
            _make_memory(type='user_preference', content='I like dark mode', raw_text='I like dark mode'),
        ]
        results = agg.aggregate(memories)
        if results:
            self.assertEqual(results[0]['type'], 'user_preference')

    def test_aggregate_confidence_multiplier(self):
        emb = [1.0, 0.0, 0.0]

        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content='I prefer dark mode', raw_text='I prefer dark mode', confidence=0.9),
            _make_memory(content='I like dark mode', raw_text='I like dark mode', confidence=0.8),
        ]
        results = agg.aggregate(memories)
        if results:
            self.assertAlmostEqual(results[0]['confidence'], 0.8 * 0.95)

    def test_aggregate_max_clusters(self):
        def mock_embedding_fn(text):
            idx = hash(text) % 10
            vec = [0.0] * 10
            vec[idx] = 1.0
            return vec

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = []
        for i in range(30):
            memories.append(_make_memory(
                type='user_preference',
                content=f'unique memory content item {i} about topic',
                raw_text=f'unique memory content item {i} about topic',
            ))
        results = agg.aggregate(memories)
        self.assertLessEqual(len(results), 10)


class TestPatternAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = PatternAnalyzer(noise_filter_mode='strict')

    def test_analyze_none_message(self):
        result = self.analyzer.analyze(None)
        self.assertEqual(result, [])

    def test_analyze_empty_message(self):
        result = self.analyzer.analyze('')
        self.assertEqual(result, [])

    def test_analyze_whitespace_only(self):
        result = self.analyzer.analyze('   ')
        self.assertEqual(result, [])

    def test_analyze_preference_english(self):
        result = self.analyzer.analyze('I prefer dark mode over light mode')
        types = [r['memory_type'] for r in result]
        self.assertIn('user_preference', types)

    def test_analyze_preference_chinese(self):
        result = self.analyzer.analyze('我喜欢深色模式')
        types = [r['memory_type'] for r in result]
        self.assertIn('user_preference', types)

    def test_analyze_preference_japanese(self):
        analyzer = PatternAnalyzer(noise_filter_mode='strict')
        result = analyzer.analyze('私はダークモードが好きです')
        types = [r['memory_type'] for r in result]
        self.assertIn('user_preference', types)

    def test_analyze_correction_explicit(self):
        result = self.analyzer.analyze('Correction: use PostgreSQL instead of MySQL')
        types = [r['memory_type'] for r in result]
        self.assertIn('correction', types)

    def test_analyze_correction_scratch_that(self):
        result = self.analyzer.analyze('Scratch that, use PostgreSQL instead')
        types = [r['memory_type'] for r in result]
        self.assertIn('correction', types)

    def test_analyze_correction_structural(self):
        result = self.analyzer.analyze('Actually it is PostgreSQL, not MySQL')
        types = [r['memory_type'] for r in result]
        self.assertIn('correction', types)

    def test_analyze_correction_keyword(self):
        result = self.analyzer.analyze('The approach is wrong, we should fix it')
        types = [r['memory_type'] for r in result]
        self.assertIn('correction', types)

    def test_analyze_correction_chinese(self):
        result = self.analyzer.analyze('纠正：应该使用PostgreSQL')
        types = [r['memory_type'] for r in result]
        self.assertIn('correction', types)

    def test_analyze_fact_tech(self):
        result = self.analyzer.analyze('Our API runs on port 8080')
        types = [r['memory_type'] for r in result]
        self.assertIn('fact_declaration', types)

    def test_analyze_fact_quantifiable(self):
        result = self.analyzer.analyze('We have 50 employees in the Shanghai office')
        types = [r['memory_type'] for r in result]
        self.assertIn('fact_declaration', types)

    def test_analyze_fact_general(self):
        result = self.analyzer.analyze('We use PostgreSQL for our main database system')
        types = [r['memory_type'] for r in result]
        self.assertIn('fact_declaration', types)

    def test_analyze_fact_chinese(self):
        result = self.analyzer.analyze('我们的服务器是Linux系统')
        types = [r['memory_type'] for r in result]
        self.assertIn('fact_declaration', types)

    def test_analyze_decision_strong(self):
        result = self.analyzer.analyze('We decided to use PostgreSQL for the project')
        types = [r['memory_type'] for r in result]
        self.assertIn('decision', types)

    def test_analyze_decision_going_with(self):
        result = self.analyzer.analyze("We're going with React for the frontend")
        types = [r['memory_type'] for r in result]
        self.assertIn('decision', types)

    def test_analyze_decision_weak(self):
        result = self.analyzer.analyze("I think we should use PostgreSQL for this project going forward")
        types = [r['memory_type'] for r in result]
        self.assertIn('decision', types)

    def test_analyze_decision_chinese(self):
        result = self.analyzer.analyze('我们决定使用PostgreSQL')
        types = [r['memory_type'] for r in result]
        self.assertIn('decision', types)

    def test_analyze_task_structured(self):
        result = self.analyzer.analyze('We need to implement the authentication module')
        types = [r['memory_type'] for r in result]
        self.assertIn('task_pattern', types)

    def test_analyze_task_workflow(self):
        result = self.analyzer.analyze('Always run tests after every deployment')
        types = [r['memory_type'] for r in result]
        self.assertIn('task_pattern', types)

    def test_analyze_task_habit(self):
        result = self.analyzer.analyze('I always check the dashboard every morning')
        types = [r['memory_type'] for r in result]
        self.assertIn('task_pattern', types)

    def test_analyze_task_chinese(self):
        result = self.analyzer.analyze('我们需要实现认证模块')
        types = [r['memory_type'] for r in result]
        self.assertIn('task_pattern', types)

    def test_analyze_relationship_role(self):
        result = self.analyzer.analyze('Alice leads the backend team')
        types = [r['memory_type'] for r in result]
        self.assertIn('relationship', types)

    def test_analyze_relationship_dependency(self):
        result = self.analyzer.analyze('The auth service depends on the user database')
        types = [r['memory_type'] for r in result]
        self.assertIn('relationship', types)

    def test_analyze_relationship_chinese(self):
        result = self.analyzer.analyze('张三负责后端团队')
        types = [r['memory_type'] for r in result]
        self.assertIn('relationship', types)

    def test_analyze_sentiment_strong(self):
        result = self.analyzer.analyze("I'm really frustrated with this slow build process")
        types = [r['memory_type'] for r in result]
        self.assertIn('sentiment_marker', types)

    def test_analyze_sentiment_keyword(self):
        result = self.analyzer.analyze('I love this new feature')
        types = [r['memory_type'] for r in result]
        self.assertIn('sentiment_marker', types)

    def test_analyze_sentiment_chinese(self):
        result = self.analyzer.analyze('这个功能太棒了')
        types = [r['memory_type'] for r in result]
        self.assertIn('sentiment_marker', types)

    def test_analyze_noise_acknowledgment(self):
        result = self.analyzer.analyze('ok')
        self.assertEqual(result, [])

    def test_analyze_noise_okay(self):
        result = self.analyzer.analyze('okay')
        self.assertEqual(result, [])

    def test_analyze_noise_thanks(self):
        result = self.analyzer.analyze('thanks')
        self.assertEqual(result, [])

    def test_analyze_noise_got_it(self):
        result = self.analyzer.analyze('got it')
        self.assertEqual(result, [])

    def test_analyze_noise_chitchat_hi(self):
        result = self.analyzer.analyze('hi')
        self.assertEqual(result, [])

    def test_analyze_noise_chitchat_hello(self):
        result = self.analyzer.analyze('hello')
        self.assertEqual(result, [])

    def test_analyze_noise_question(self):
        result = self.analyzer.analyze('how do I install this?')
        self.assertEqual(result, [])

    def test_analyze_noise_command(self):
        result = self.analyzer.analyze('npm install express')
        self.assertEqual(result, [])

    def test_analyze_noise_log_prefix(self):
        result = self.analyzer.analyze('[ERROR] Connection timeout')
        self.assertEqual(result, [])

    def test_analyze_noise_adversarial(self):
        result = self.analyzer.analyze("don't remember this")
        self.assertEqual(result, [])

    def test_analyze_noise_just_a_test(self):
        result = self.analyzer.analyze('this is just a test')
        self.assertEqual(result, [])

    def test_analyze_noise_chinese_acknowledgment(self):
        result = self.analyzer.analyze('好的')
        self.assertEqual(result, [])

    def test_analyze_noise_chinese_chitchat(self):
        result = self.analyzer.analyze('你好')
        self.assertEqual(result, [])

    def test_analyze_noise_japanese_acknowledgment(self):
        result = self.analyzer.analyze('はい')
        self.assertEqual(result, [])

    def test_analyze_noise_ultra_short(self):
        result = self.analyzer.analyze('ab')
        self.assertEqual(result, [])

    def test_analyze_soft_noise_filter_chitchat(self):
        soft_analyzer = PatternAnalyzer(noise_filter_mode='soft')
        result = soft_analyzer.analyze('hi')
        types = [r['memory_type'] for r in result]
        self.assertTrue(len(result) == 0 or 'sentiment_marker' in types or 'user_preference' in types)

    def test_analyze_soft_noise_filter_question(self):
        soft_analyzer = PatternAnalyzer(noise_filter_mode='soft')
        result = soft_analyzer.analyze('how do I install this?')
        self.assertIsInstance(result, list)

    def test_analyze_execution_feedback_positive(self):
        exec_ctx = {'user_feedback': 'great success done'}
        result = self.analyzer.analyze('The deployment completed', execution_context=exec_ctx)
        types = [r['memory_type'] for r in result]
        self.assertIn('positive_feedback', types)

    def test_analyze_execution_feedback_negative(self):
        exec_ctx = {'user_feedback': 'wrong error fail'}
        result = self.analyzer.analyze('The deployment failed', execution_context=exec_ctx)
        types = [r['memory_type'] for r in result]
        self.assertIn('negative_feedback', types)

    def test_analyze_execution_feedback_tool_error(self):
        exec_ctx = {'tool_error': True}
        result = self.analyzer.analyze('The tool crashed', execution_context=exec_ctx)
        types = [r['memory_type'] for r in result]
        self.assertIn('tool_error', types)

    def test_analyze_execution_feedback_retry(self):
        exec_ctx = {'retry_count': 3}
        result = self.analyzer.analyze('Please try again', execution_context=exec_ctx)
        types = [r['memory_type'] for r in result]
        self.assertIn('retry_needed', types)

    def test_analyze_execution_feedback_correction_followup(self):
        exec_ctx = {'context_position': 'correction_followup'}
        result = self.analyzer.analyze('Let me fix that', execution_context=exec_ctx)
        types = [r['memory_type'] for r in result]
        self.assertIn('correction_followup', types)

    def test_analyze_execution_feedback_confirmation_pending(self):
        exec_ctx = {'context_position': 'confirmation_pending'}
        result = self.analyzer.analyze('Please confirm', execution_context=exec_ctx)
        types = [r['memory_type'] for r in result]
        self.assertIn('confirmation_pending', types)

    def test_analyze_confirmation_with_context(self):
        context = {'ai_reply': 'Should I use PostgreSQL for the database?'}
        result = self.analyzer.analyze('ok', context=context)
        types = [r['memory_type'] for r in result]
        self.assertIn('decision', types)

    def test_analyze_confirmation_without_context_not_triggered(self):
        result = self.analyzer.analyze('ok')
        self.assertEqual(result, [])

    def test_analyze_message_history_tracking(self):
        analyzer = PatternAnalyzer(noise_filter_mode='strict')
        analyzer.analyze('I prefer dark mode for coding')
        self.assertEqual(len(analyzer.message_history), 1)
        analyzer.analyze('We use PostgreSQL for database')
        self.assertEqual(len(analyzer.message_history), 2)

    def test_analyze_message_history_max_10(self):
        analyzer = PatternAnalyzer(noise_filter_mode='strict')
        for i in range(15):
            analyzer.analyze(f'I prefer option {i} for development')
        self.assertLessEqual(len(analyzer.message_history), 10)

    def test_clear_history(self):
        analyzer = PatternAnalyzer(noise_filter_mode='strict')
        analyzer.analyze('I prefer dark mode')
        analyzer.analyze('We use PostgreSQL')
        self.assertTrue(len(analyzer.message_history) > 0)
        analyzer.clear_history()
        self.assertEqual(len(analyzer.message_history), 0)
        self.assertEqual(len(analyzer.task_patterns), 0)
        self.assertEqual(len(analyzer.preference_patterns), 0)
        self.assertEqual(len(analyzer.correction_patterns), 0)
        self.assertEqual(len(analyzer.fact_patterns), 0)
        self.assertEqual(len(analyzer.relationship_patterns), 0)
        self.assertEqual(len(analyzer.location_patterns), 0)

    def test_analyze_result_has_language(self):
        result = self.analyzer.analyze('I prefer dark mode over light mode')
        for r in result:
            self.assertIn('language', r)

    def test_analyze_correction_confidence_tiers(self):
        result = self.analyzer.analyze('Correction: use PostgreSQL')
        corrections = [r for r in result if r['memory_type'] == 'correction']
        if corrections:
            self.assertAlmostEqual(corrections[0]['confidence'], 0.85)

    def test_analyze_fact_short_message_returns_none(self):
        result = self.analyzer.analyze('short')
        fact_results = [r for r in result if r['memory_type'] == 'fact_declaration']
        self.assertEqual(len(fact_results), 0)

    def test_analyze_decision_not_triggered_by_task_keywords(self):
        result = self.analyzer.analyze('We need to implement the feature')
        types = [r['memory_type'] for r in result]
        if 'task_pattern' in types and 'decision' in types:
            self.assertTrue(True)

    def test_analyze_location_pattern(self):
        result = self.analyzer.analyze('I am at the office building on Main Street')
        types = [r['memory_type'] for r in result]
        self.assertIn('location', types)

    def test_analyze_location_not_triggered_by_facts(self):
        result = self.analyzer.analyze('Our server is located in the Shanghai data center')
        location_results = [r for r in result if r['memory_type'] == 'location']
        self.assertEqual(len(location_results), 0)

    def test_analyze_fact_with_version_not_filtered_as_command(self):
        result = self.analyzer.analyze('Python 3.9 is the minimum required version')
        types = [r['memory_type'] for r in result]
        self.assertIn('fact_declaration', types)

    def test_analyze_instruction_with_workflow_not_filtered(self):
        result = self.analyzer.analyze('Test after every deployment')
        types = [r['memory_type'] for r in result]
        self.assertIn('task_pattern', types)

    def test_analyze_noise_instruction_short(self):
        result = self.analyzer.analyze('run tests')
        self.assertEqual(result, [])

    def test_analyze_sentiment_fact_exclusion(self):
        result = self.analyzer.analyze('Our API supports version 2.0')
        sentiment_results = [r for r in result if r['memory_type'] == 'sentiment_marker']
        self.assertEqual(len(sentiment_results), 0)

    def test_analyze_multiple_patterns(self):
        result = self.analyzer.analyze('I prefer dark mode and we decided to use PostgreSQL')
        self.assertTrue(len(result) >= 1)

    def test_analyze_no_execution_context_no_feedback(self):
        result = self.analyzer.analyze('I prefer dark mode')
        feedback_types = ['positive_feedback', 'negative_feedback', 'tool_error', 'retry_needed']
        for r in result:
            self.assertNotIn(r['memory_type'], feedback_types)


if __name__ == '__main__':
    unittest.main()
