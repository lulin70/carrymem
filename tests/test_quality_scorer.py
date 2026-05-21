"""
Tests for quality_scorer module.

Validates MemoryQualityScorer and QualityAnalyzer classes including:
- Score calculation with default and custom weights
- Score breakdown
- Batch scoring and ranking
- Quality tiers
- Filtering by quality
- Quality analysis across collections
- Low quality identification
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from carrymem.quality_scorer import (
    MemoryQualityScorer,
    QualityAnalyzer,
)


def make_memory(
    confidence=0.8,
    access_count=5,
    created_at=None,
    source_layer="declaration",
    memory_type="user_preference",
    storage_key="test_key",
):
    mem = MagicMock()
    mem.confidence = confidence
    mem.access_count = access_count
    mem.created_at = created_at or datetime.now(timezone.utc)
    mem.source_layer = source_layer
    mem.type = memory_type
    mem.storage_key = storage_key
    return mem


class TestMemoryQualityScorerInit:
    def test_default_weights(self):
        scorer = MemoryQualityScorer()
        assert scorer.weights == MemoryQualityScorer.DEFAULT_WEIGHTS

    def test_custom_weights(self):
        custom = {
            'confidence': 0.5,
            'access_frequency': 0.2,
            'freshness': 0.2,
            'source_reliability': 0.1,
        }
        scorer = MemoryQualityScorer(weights=custom)
        assert scorer.weights == custom

    def test_invalid_weights_rejected(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            MemoryQualityScorer(weights={'confidence': 0.5})

    def test_default_max_access_count(self):
        scorer = MemoryQualityScorer()
        assert scorer.max_access_count == 10

    def test_default_max_age_days(self):
        scorer = MemoryQualityScorer()
        assert scorer.max_age_days == 365


class TestScoring:
    def test_score_returns_float(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        score = scorer.score(mem)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_high_quality_memory(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(
            confidence=1.0,
            access_count=10,
            created_at=datetime.now(timezone.utc),
            source_layer="declaration",
        )
        score = scorer.score(mem)
        assert score >= 0.8

    def test_low_quality_memory(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(
            confidence=0.1,
            access_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(days=400),
            source_layer="unknown",
        )
        score = scorer.score(mem)
        assert score < 0.5

    def test_zero_confidence(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(confidence=0.0)
        score = scorer.score(mem)
        assert score < 0.5

    def test_max_confidence(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(confidence=1.0)
        score = scorer.score(mem)
        assert score > 0.3

    def test_score_is_rounded(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        score = scorer.score(mem)
        assert score == round(score, 3)


class TestScoreBreakdown:
    def test_breakdown_has_all_keys(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        breakdown = scorer.score_with_breakdown(mem)
        assert 'overall' in breakdown
        assert 'confidence' in breakdown
        assert 'access_frequency' in breakdown
        assert 'freshness' in breakdown
        assert 'source_reliability' in breakdown
        assert 'weighted' in breakdown

    def test_breakdown_weighted_keys(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        breakdown = scorer.score_with_breakdown(mem)
        weighted = breakdown['weighted']
        assert 'confidence' in weighted
        assert 'access_frequency' in weighted
        assert 'freshness' in weighted
        assert 'source_reliability' in weighted

    def test_breakdown_overall_equals_weighted_sum(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        breakdown = scorer.score_with_breakdown(mem)
        weighted_sum = sum(breakdown['weighted'].values())
        assert abs(breakdown['overall'] - round(weighted_sum, 3)) < 0.01


class TestAccessFrequencyScoring:
    def test_zero_access(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(access_count=0)
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['access_frequency'] == 0.0

    def test_max_access(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(access_count=10)
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['access_frequency'] == 1.0

    def test_over_max_capped(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(access_count=100)
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['access_frequency'] == 1.0

    def test_half_access(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(access_count=5)
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['access_frequency'] == 0.5

    def test_none_access_count(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        mem.access_count = None
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['access_frequency'] == 0.0


class TestFreshnessScoring:
    def test_very_fresh(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(created_at=datetime.now(timezone.utc))
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['freshness'] > 0.9

    def test_very_old(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(
            created_at=datetime.now(timezone.utc) - timedelta(days=400)
        )
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['freshness'] < 0.1

    def test_no_created_at(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        mem.created_at = None
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['freshness'] == 0.5

    def test_naive_datetime(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(
            created_at=datetime.now().replace(tzinfo=None)
        )
        breakdown = scorer.score_with_breakdown(mem)
        assert 0.0 <= breakdown['freshness'] <= 1.01


class TestSourceReliabilityScoring:
    def test_declaration_source(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(source_layer="declaration")
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['source_reliability'] == 1.0

    def test_rule_source(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(source_layer="rule")
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['source_reliability'] == 0.9

    def test_pattern_source(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(source_layer="pattern")
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['source_reliability'] == 0.7

    def test_semantic_source(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(source_layer="semantic")
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['source_reliability'] == 0.5

    def test_unknown_source(self):
        scorer = MemoryQualityScorer()
        mem = make_memory(source_layer="unknown")
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['source_reliability'] == 0.3

    def test_none_source(self):
        scorer = MemoryQualityScorer()
        mem = make_memory()
        mem.source_layer = None
        breakdown = scorer.score_with_breakdown(mem)
        assert breakdown['source_reliability'] == 0.3


class TestQualityTiers:
    def test_excellent(self):
        scorer = MemoryQualityScorer()
        assert scorer.get_quality_tier(0.9) == 'excellent'
        assert scorer.get_quality_tier(0.8) == 'excellent'

    def test_good(self):
        scorer = MemoryQualityScorer()
        assert scorer.get_quality_tier(0.7) == 'good'
        assert scorer.get_quality_tier(0.6) == 'good'

    def test_fair(self):
        scorer = MemoryQualityScorer()
        assert scorer.get_quality_tier(0.5) == 'fair'
        assert scorer.get_quality_tier(0.4) == 'fair'

    def test_poor(self):
        scorer = MemoryQualityScorer()
        assert scorer.get_quality_tier(0.3) == 'poor'
        assert scorer.get_quality_tier(0.0) == 'poor'


class TestBatchScoring:
    def test_score_batch(self):
        scorer = MemoryQualityScorer()
        mems = [
            make_memory(confidence=0.9, storage_key="high"),
            make_memory(confidence=0.3, storage_key="low"),
            make_memory(confidence=0.6, storage_key="mid"),
        ]
        results = scorer.score_batch(mems)
        assert len(results) == 3
        assert results[0]['score'] >= results[1]['score']
        assert results[1]['score'] >= results[2]['score']

    def test_score_batch_has_storage_key(self):
        scorer = MemoryQualityScorer()
        mems = [make_memory(storage_key="test_key")]
        results = scorer.score_batch(mems)
        assert results[0]['storage_key'] == "test_key"

    def test_score_batch_empty(self):
        scorer = MemoryQualityScorer()
        results = scorer.score_batch([])
        assert results == []


class TestFilterByQuality:
    def test_filter_keeps_above_threshold(self):
        scorer = MemoryQualityScorer()
        mems = [
            make_memory(confidence=0.9, source_layer="declaration"),
            make_memory(confidence=0.1, source_layer="unknown"),
        ]
        filtered = scorer.filter_by_quality(mems, min_score=0.3)
        assert len(filtered) >= 1
        for m in filtered:
            assert scorer.score(m) >= 0.3

    def test_filter_all_pass(self):
        scorer = MemoryQualityScorer()
        mems = [make_memory(confidence=0.9)]
        filtered = scorer.filter_by_quality(mems, min_score=0.0)
        assert len(filtered) == 1

    def test_filter_none_pass(self):
        scorer = MemoryQualityScorer()
        mems = [make_memory(confidence=0.1, source_layer="unknown")]
        filtered = scorer.filter_by_quality(mems, min_score=0.99)
        assert len(filtered) == 0


class TestRankMemories:
    def test_rank_descending(self):
        scorer = MemoryQualityScorer()
        mems = [
            make_memory(confidence=0.3, storage_key="low"),
            make_memory(confidence=0.9, storage_key="high"),
            make_memory(confidence=0.6, storage_key="mid"),
        ]
        ranked = scorer.rank_memories(mems)
        scores = [scorer.score(m) for m in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_with_limit(self):
        scorer = MemoryQualityScorer()
        mems = [make_memory(confidence=c / 10) for c in range(1, 11)]
        ranked = scorer.rank_memories(mems, limit=3)
        assert len(ranked) == 3

    def test_rank_empty(self):
        scorer = MemoryQualityScorer()
        ranked = scorer.rank_memories([])
        assert ranked == []


class TestQualityAnalyzer:
    def test_analyze_empty(self):
        analyzer = QualityAnalyzer()
        result = analyzer.analyze([])
        assert result['count'] == 0
        assert result['average_score'] == 0.0
        assert result['by_tier'] == {}

    def test_analyze_with_memories(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(confidence=0.9, source_layer="declaration"),
            make_memory(confidence=0.3, source_layer="unknown"),
        ]
        result = analyzer.analyze(mems)
        assert result['count'] == 2
        assert result['average_score'] > 0
        assert 'excellent' in result['by_tier'] or 'good' in result['by_tier']

    def test_analyze_by_type(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(memory_type="user_preference", confidence=0.9),
            make_memory(memory_type="correction", confidence=0.5),
        ]
        result = analyzer.analyze(mems)
        assert 'user_preference' in result['by_type']
        assert 'correction' in result['by_type']

    def test_analyze_by_source(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(source_layer="declaration", confidence=0.9),
            make_memory(source_layer="pattern", confidence=0.5),
        ]
        result = analyzer.analyze(mems)
        assert 'declaration' in result['by_source']
        assert 'pattern' in result['by_source']

    def test_analyze_statistics(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(confidence=0.9),
            make_memory(confidence=0.5),
            make_memory(confidence=0.1),
        ]
        result = analyzer.analyze(mems)
        assert result['min_score'] <= result['average_score']
        assert result['average_score'] <= result['max_score']
        assert result['median_score'] > 0

    def test_custom_scorer(self):
        custom_weights = {
            'confidence': 0.5,
            'access_frequency': 0.2,
            'freshness': 0.2,
            'source_reliability': 0.1,
        }
        scorer = MemoryQualityScorer(weights=custom_weights)
        analyzer = QualityAnalyzer(scorer=scorer)
        mem = make_memory()
        result = analyzer.analyze([mem])
        assert result['count'] == 1


class TestIdentifyLowQuality:
    def test_identify_low(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(confidence=0.1, source_layer="unknown", access_count=0),
        ]
        low = analyzer.identify_low_quality(mems, threshold=0.5)
        assert len(low) >= 1
        assert low[0]['score'] < 0.5

    def test_identify_with_reasons(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(
                confidence=0.1,
                source_layer="unknown",
                access_count=0,
                created_at=datetime.now(timezone.utc) - timedelta(days=400),
            ),
        ]
        low = analyzer.identify_low_quality(mems, threshold=0.5)
        assert len(low) >= 1
        assert len(low[0]['reasons']) > 0

    def test_identify_no_low_quality(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(confidence=0.9, source_layer="declaration", access_count=10),
        ]
        low = analyzer.identify_low_quality(mems, threshold=0.1)
        assert len(low) == 0

    def test_identify_sorted_by_score(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(confidence=0.2, storage_key="worse"),
            make_memory(confidence=0.4, storage_key="better"),
        ]
        low = analyzer.identify_low_quality(mems, threshold=0.5)
        if len(low) >= 2:
            assert low[0]['score'] <= low[1]['score']

    def test_identify_has_breakdown(self):
        analyzer = QualityAnalyzer()
        mems = [
            make_memory(confidence=0.1, source_layer="unknown"),
        ]
        low = analyzer.identify_low_quality(mems, threshold=0.5)
        if low:
            assert 'breakdown' in low[0]
            assert 'overall' in low[0]['breakdown']
