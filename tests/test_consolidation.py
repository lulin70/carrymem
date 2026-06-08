"""Tests for CarryMem consolidation engine."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from carrymem.consolidation import (
    _content_hash,
    _find_semantic_clusters,
    _similarity,
    compute_decay_factor,
    consolidate,
    consolidate_p1,
    consolidate_p2,
    find_duplicates,
    find_superseded_pairs,
)


class TestContentHash:
    def test_same_content_same_hash(self):
        assert _content_hash("Hello World") == _content_hash("Hello World")

    def test_whitespace_normalized(self):
        assert _content_hash("Hello  World") == _content_hash("Hello World")

    def test_case_normalized(self):
        assert _content_hash("Hello World") == _content_hash("hello world")

    def test_different_content_different_hash(self):
        assert _content_hash("Hello World") != _content_hash("Goodbye World")


class TestSimilarity:
    def test_identical(self):
        assert _similarity("I prefer Python", "I prefer Python") == 1.0

    def test_completely_different(self):
        assert _similarity("Python is great", "The weather is nice") < 0.3

    def test_partial_overlap(self):
        sim = _similarity("I prefer Python over Java", "I prefer Python over C++")
        assert 0.5 < sim < 1.0

    def test_empty_strings(self):
        assert _similarity("", "") == 0.0
        assert _similarity("hello", "") == 0.0


class TestDecayFactor:
    def test_fresh_memory(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(hours=1)
        decay = compute_decay_factor(created, "personal_fact", 0.8, now=now)
        assert decay > 0.9

    def test_old_memory_decays(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=180)
        decay = compute_decay_factor(created, "personal_fact", 0.8, now=now)
        assert decay < 0.5

    def test_preference_decays_slower(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=180)
        pref_decay = compute_decay_factor(created, "user_preference", 0.8, now=now)
        fact_decay = compute_decay_factor(created, "personal_fact", 0.8, now=now)
        assert pref_decay > fact_decay

    def test_sentiment_decays_faster(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=180)
        sent_decay = compute_decay_factor(created, "sentiment_marker", 0.8, now=now)
        fact_decay = compute_decay_factor(created, "personal_fact", 0.8, now=now)
        assert sent_decay < fact_decay

    def test_access_count_boosts(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=180)
        decay_no_access = compute_decay_factor(created, "personal_fact", 0.8, access_count=0, now=now)
        decay_with_access = compute_decay_factor(created, "personal_fact", 0.8, access_count=10, now=now)
        assert decay_with_access > decay_no_access

    def test_low_confidence_extra_decay(self):
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=90)
        high_conf = compute_decay_factor(created, "personal_fact", 0.9, now=now)
        low_conf = compute_decay_factor(created, "personal_fact", 0.2, now=now)
        assert high_conf > low_conf

    def test_string_created_at(self):
        now = datetime.now(timezone.utc)
        created_str = (now - timedelta(days=90)).isoformat()
        decay = compute_decay_factor(created_str, "personal_fact", 0.8, now=now)
        assert 0.0 < decay < 1.0

    def test_invalid_created_at(self):
        decay = compute_decay_factor("not-a-date", "personal_fact", 0.8)
        assert decay == 1.0


class TestFindDuplicates:
    def test_no_duplicates(self):
        memories = [
            {"content": "I prefer Python", "type": "user_preference", "storage_key": "a"},
            {"content": "I work at Google", "type": "personal_fact", "storage_key": "b"},
        ]
        dups = find_duplicates(memories)
        assert len(dups) == 0

    def test_exact_duplicates(self):
        memories = [
            {"content": "I prefer Python", "type": "user_preference", "storage_key": "a"},
            {"content": "I prefer Python", "type": "user_preference", "storage_key": "b"},
        ]
        dups = find_duplicates(memories)
        assert len(dups) == 1
        assert dups[0][2] == 1.0

    def test_near_duplicates(self):
        memories = [
            {
                "content": "I prefer Python over other languages",
                "type": "personal_fact",
                "storage_key": "a",
            },
            {
                "content": "I prefer Python over other programming languages",
                "type": "personal_fact",
                "storage_key": "b",
            },
        ]
        dups = find_duplicates(memories, similarity_threshold=0.7)
        assert len(dups) >= 1

    def test_preferences_not_counted_as_duplicates(self):
        memories = [
            {"content": "I prefer Python", "type": "user_preference", "storage_key": "a"},
            {"content": "I prefer Python", "type": "user_preference", "storage_key": "b"},
        ]
        dups = find_duplicates(memories)
        assert len(dups) == 1

    def test_session_summary_skipped(self):
        memories = [
            {"content": "Discussed Python", "type": "session_summary", "storage_key": "a"},
            {"content": "Discussed Python", "type": "session_summary", "storage_key": "b"},
        ]
        dups = find_duplicates(memories)
        assert len(dups) == 0

    def test_superseded_skipped(self):
        memories = [
            {"content": "I prefer Python", "type": "personal_fact", "storage_key": "a"},
            {
                "content": "I prefer Python",
                "type": "personal_fact",
                "storage_key": "b",
                "superseded_at": "2026-01-01",
            },
        ]
        dups = find_duplicates(memories)
        assert len(dups) == 0


class TestFindSupersededPairs:
    def test_updated_content(self):
        memories = [
            {
                "content": "I work at Google",
                "type": "personal_fact",
                "storage_key": "a",
                "created_at": "2025-01-01",
            },
            {
                "content": "I work at Meta now",
                "type": "personal_fact",
                "storage_key": "b",
                "created_at": "2026-01-01",
            },
        ]
        pairs = find_superseded_pairs(memories)
        assert len(pairs) >= 0

    def test_different_types_not_paired(self):
        memories = [
            {
                "content": "I like Python",
                "type": "user_preference",
                "storage_key": "a",
                "created_at": "2025-01-01",
            },
            {
                "content": "I like Python",
                "type": "personal_fact",
                "storage_key": "b",
                "created_at": "2026-01-01",
            },
        ]
        pairs = find_superseded_pairs(memories)
        assert len(pairs) == 0


class TestConsolidate:
    def test_dry_run_default(self):
        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "superseded_at": None,
            },
        ]
        report = consolidate(memories)
        assert "dry_run" not in report
        assert report["input_count"] == 1

    def test_old_memories_to_forget(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        memories = [
            {
                "content": "Random thought",
                "type": "sentiment_marker",
                "storage_key": "old1",
                "confidence": 0.3,
                "created_at": old_date,
                "superseded_at": None,
                "access_count": 0,
            },
        ]
        report = consolidate(memories)
        assert len(report["to_forget"]) >= 1

    def test_preferences_never_forgotten(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "pref1",
                "confidence": 0.9,
                "created_at": old_date,
                "superseded_at": None,
                "access_count": 0,
            },
        ]
        report = consolidate(memories)
        assert len(report["to_forget"]) == 0

    def test_empty_input(self):
        report = consolidate([])
        assert report["input_count"] == 0
        assert len(report["to_supersede"]) == 0

    def test_stats_populated(self):
        now = datetime.now(timezone.utc).isoformat()
        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": now,
                "superseded_at": None,
            },
            {
                "content": "I work at Google",
                "type": "personal_fact",
                "storage_key": "b",
                "confidence": 0.8,
                "created_at": now,
                "superseded_at": None,
            },
        ]
        report = consolidate(memories)
        assert "stats" in report
        assert "duplicates_found" in report["stats"]


class TestConsolidateP1:
    def test_p1_skipped_without_rule_storage(self):
        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        result = consolidate_p1(memories, rule_storage=None)
        assert result["p1_enabled"] is False
        assert result["p1_skipped_reason"] == "no_rule_storage"

    def test_p1_empty_memories(self):
        result = consolidate_p1([], rule_storage=MagicMock())
        assert result["patterns_found"] == 0
        assert result["candidates_generated"] == 0

    def test_p1_with_rule_storage(self):
        mock_storage = MagicMock()
        mock_storage._get_connection.return_value.execute.return_value = None
        mock_storage._get_connection.return_value.commit.return_value = None
        mock_storage._get_connection.return_value.fetchall.return_value = []
        mock_storage._get_connection.return_value.fetchone.return_value = None

        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        result = consolidate_p1(memories, rule_storage=mock_storage)
        assert result["p1_enabled"] is True
        assert "patterns_found" in result

    def test_p1_error_handling(self):
        mock_storage = MagicMock()
        mock_storage._get_connection.side_effect = RuntimeError("db error")

        memories = [
            {
                "content": "test",
                "type": "personal_fact",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        result = consolidate_p1(memories, rule_storage=mock_storage)
        assert "p1_error" in result


class TestConsolidateP2:
    def test_p2_empty_memories(self):
        result = consolidate_p2([])
        assert result["p2_enabled"] is True
        assert result["stats"]["clusters_found"] == 0

    def test_p2_no_clusters(self):
        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "content": "I work at Google",
                "type": "personal_fact",
                "storage_key": "b",
                "confidence": 0.8,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        result = consolidate_p2(memories)
        assert result["stats"]["clusters_found"] == 0

    def test_p2_finds_similar_cluster(self):
        now = datetime.now(timezone.utc).isoformat()
        memories = [
            {
                "content": "I prefer Python for backend development",
                "type": "personal_fact",
                "storage_key": "a",
                "confidence": 0.8,
                "created_at": now,
            },
            {
                "content": "I prefer Python for backend services",
                "type": "personal_fact",
                "storage_key": "b",
                "confidence": 0.7,
                "created_at": now,
            },
        ]
        result = consolidate_p2(memories)
        assert result["stats"]["clusters_found"] >= 1
        assert len(result["consolidation_requests"]) >= 1
        req = result["consolidation_requests"][0]
        assert req["action"] == "consolidate"
        assert "instruction" in req
        assert "content" in req

    def test_p2_preserves_preferences(self):
        now = datetime.now(timezone.utc).isoformat()
        memories = [
            {
                "content": "I prefer dark mode",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": now,
            },
            {
                "content": "I prefer dark mode always",
                "type": "user_preference",
                "storage_key": "b",
                "confidence": 0.9,
                "created_at": now,
            },
        ]
        result = consolidate_p2(memories)
        assert result["stats"]["clusters_found"] == 0
        assert result["stats"]["preferences_preserved"] == 0

    def test_p2_with_p0_report(self):
        now = datetime.now(timezone.utc).isoformat()
        memories = [
            {
                "content": "I work at Google",
                "type": "personal_fact",
                "storage_key": "a",
                "confidence": 0.8,
                "created_at": "2025-01-01",
            },
            {
                "content": "I work at Meta now",
                "type": "personal_fact",
                "storage_key": "b",
                "confidence": 0.9,
                "created_at": now,
            },
        ]
        p0_report = {
            "to_supersede": [
                {
                    "older_key": "a",
                    "newer_key": "b",
                    "type": "personal_fact",
                    "reason": "updated_content",
                }
            ],
        }
        result = consolidate_p2(memories, p0_report=p0_report)
        assert result["stats"]["memories_to_consolidate"] >= 2

    def test_find_semantic_clusters(self):
        now = datetime.now(timezone.utc).isoformat()
        memories = [
            {
                "content": "I use Python for data analysis",
                "type": "personal_fact",
                "storage_key": "a",
                "confidence": 0.8,
                "created_at": now,
            },
            {
                "content": "I use Python for data science",
                "type": "personal_fact",
                "storage_key": "b",
                "confidence": 0.7,
                "created_at": now,
            },
            {
                "content": "The weather is nice today",
                "type": "personal_fact",
                "storage_key": "c",
                "confidence": 0.5,
                "created_at": now,
            },
        ]
        clusters = _find_semantic_clusters(memories, similarity_threshold=0.6)
        assert len(clusters) >= 1
        assert len(clusters[0]) >= 2

    def test_find_semantic_clusters_skips_preferences(self):
        now = datetime.now(timezone.utc).isoformat()
        memories = [
            {
                "content": "I prefer Python",
                "type": "user_preference",
                "storage_key": "a",
                "confidence": 0.9,
                "created_at": now,
            },
            {
                "content": "I prefer Python always",
                "type": "user_preference",
                "storage_key": "b",
                "confidence": 0.9,
                "created_at": now,
            },
        ]
        clusters = _find_semantic_clusters(memories)
        assert len(clusters) == 0
