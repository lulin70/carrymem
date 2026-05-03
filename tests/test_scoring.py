"""Tests for scoring.py module - memory importance scoring system"""

import math
from datetime import datetime, timezone, timedelta
import pytest
from memory_classification_engine.scoring import (
    type_weight, recency_factor, access_factor,
    calculate_importance, recalculate_importance,
    TYPE_WEIGHTS, DEFAULT_TYPE_WEIGHT, HALF_LIFE_DAYS, RECENCY_FLOOR, ACCESS_SCALE
)


class TestTypeWeight:
    def test_known_types(self):
        assert type_weight("correction") == 1.3
        assert type_weight("decision") == 1.2
        assert type_weight("user_preference") == 1.1
        assert type_weight("fact_declaration") == 1.0
    
    def test_unknown_type(self):
        assert type_weight("unknown") == DEFAULT_TYPE_WEIGHT


class TestRecencyFactor:
    def test_brand_new_memory(self):
        now = datetime.now(timezone.utc)
        assert recency_factor(now, now) == pytest.approx(1.0, rel=0.01)
    
    def test_old_memory(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=365)
        factor = recency_factor(old, now)
        assert factor < 0.5 and factor >= RECENCY_FLOOR
    
    def test_half_life_decay(self):
        now = datetime.now(timezone.utc)
        half_life_ago = now - timedelta(days=HALF_LIFE_DAYS)
        expected = RECENCY_FLOOR + (1.0 - RECENCY_FLOOR) * 0.5
        assert recency_factor(half_life_ago, now) == pytest.approx(expected, rel=0.01)
    
    def test_naive_datetime(self):
        now = datetime.now(timezone.utc)
        naive = datetime.now()
        factor = recency_factor(naive, now)
        assert 0.0 <= factor <= 1.0
    
    def test_default_now(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        assert recency_factor(recent) > 0.9


class TestAccessFactor:
    def test_zero_access(self):
        assert access_factor(0) == 1.0
    
    def test_single_access(self):
        expected = 1.0 + math.log(2) * ACCESS_SCALE
        assert access_factor(1) == pytest.approx(expected, rel=0.01)
    
    def test_multiple_accesses(self):
        f1, f10, f100 = access_factor(1), access_factor(10), access_factor(100)
        assert f1 < f10 < f100
    
    def test_negative_access(self):
        assert access_factor(-5) == 1.0
    
    def test_logarithmic_growth(self):
        f10, f20 = access_factor(10), access_factor(20)
        assert f20 < f10 * 2


class TestCalculateImportance:
    def test_perfect_score(self):
        now = datetime.now(timezone.utc)
        score = calculate_importance(1.0, "correction", now, 100, now)
        assert score > 1.3
    
    def test_low_confidence(self):
        now = datetime.now(timezone.utc)
        score = calculate_importance(0.1, "fact_declaration", now, 0, now)
        assert score < 0.2
    
    def test_old_memory_decay(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=365)
        score_new = calculate_importance(1.0, "fact_declaration", now, 0, now)
        score_old = calculate_importance(1.0, "fact_declaration", old, 0, now)
        assert score_old < score_new
    
    def test_access_boost(self):
        now = datetime.now(timezone.utc)
        score_rare = calculate_importance(1.0, "fact_declaration", now, 0, now)
        score_freq = calculate_importance(1.0, "fact_declaration", now, 100, now)
        assert score_freq > score_rare
    
    def test_type_weight_effect(self):
        now = datetime.now(timezone.utc)
        score_corr = calculate_importance(1.0, "correction", now, 0, now)
        score_sent = calculate_importance(1.0, "sentiment_marker", now, 0, now)
        assert score_corr > score_sent
    
    def test_default_access_count(self):
        now = datetime.now(timezone.utc)
        score = calculate_importance(1.0, "fact_declaration", now, now=now)
        assert score == pytest.approx(1.0, rel=0.01)
    
    def test_default_now(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        score = calculate_importance(1.0, "fact_declaration", recent, 0)
        assert score > 0.9
    
    def test_score_rounding(self):
        now = datetime.now(timezone.utc)
        score = calculate_importance(0.123456789, "fact_declaration", now, 0, now)
        assert len(str(score).split('.')[-1]) <= 6


class TestRecalculateImportance:
    def test_same_as_calculate(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=10)
        s1 = calculate_importance(0.9, "user_preference", created, 5, now)
        s2 = recalculate_importance(0.9, "user_preference", created, 5, now)
        assert s1 == s2
    
    def test_after_access(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=30)
        initial = recalculate_importance(1.0, "fact_declaration", created, 0, now)
        after = recalculate_importance(1.0, "fact_declaration", created, 10, now)
        assert after > initial


class TestConstants:
    def test_type_weights_defined(self):
        assert isinstance(TYPE_WEIGHTS, dict)
        assert len(TYPE_WEIGHTS) == 7
    
    def test_constants_values(self):
        assert DEFAULT_TYPE_WEIGHT == 1.0
        assert HALF_LIFE_DAYS == 30
        assert RECENCY_FLOOR == 0.3
        assert ACCESS_SCALE == 0.1
    
    def test_type_weights_ordering(self):
        assert TYPE_WEIGHTS["correction"] > TYPE_WEIGHTS["decision"]
        assert TYPE_WEIGHTS["decision"] > TYPE_WEIGHTS["user_preference"]
        assert TYPE_WEIGHTS["task_pattern"] > TYPE_WEIGHTS["sentiment_marker"]
