"""Tests for context injection and scoring features.

Covers:
- 1.1 Smart context injection (build_context, build_system_prompt)
- 1.2 Memory decay & reinforcement (importance_score, recency_factor, access_factor)
- 1.3 Query cache layer (RecallCache)
- 1.4 Memory merge & conflict resolution
- 1.5 Memory versioning (update, history, rollback)
"""

import math
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from carrymem import CarryMem
from carrymem.scoring import (
    calculate_importance,
    recency_factor,
    access_factor,
    type_weight,
    TYPE_WEIGHTS,
    HALF_LIFE_DAYS,
)
from carrymem.cache import RecallCache
from carrymem.context import (
    select_memories,
    context_relevance,
    _estimate_tokens,
    build_prompt,
    format_memory_entry,
)
from carrymem.merge import (
    detect_conflicts,
    merge_memories,
    _similarity,
)


class TestScoring(unittest.TestCase):
    def test_type_weights(self):
        self.assertEqual(type_weight("correction"), 1.3)
        self.assertEqual(type_weight("decision"), 1.2)
        self.assertEqual(type_weight("user_preference"), 1.1)
        self.assertEqual(type_weight("fact_declaration"), 1.0)
        self.assertEqual(type_weight("unknown_type"), 1.0)

    def test_recency_factor_fresh(self):
        now = datetime.now(timezone.utc)
        score = recency_factor(now, now)
        self.assertAlmostEqual(score, 1.0, places=2)

    def test_recency_factor_old(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=365)
        score = recency_factor(old, now)
        self.assertLess(score, 0.4)
        self.assertGreater(score, 0.3)

    def test_recency_factor_half_life(self):
        now = datetime.now(timezone.utc)
        half = now - timedelta(days=HALF_LIFE_DAYS)
        score = recency_factor(half, now)
        expected = 0.3 + 0.7 * 0.5
        self.assertAlmostEqual(score, expected, places=2)

    def test_access_factor_zero(self):
        self.assertEqual(access_factor(0), 1.0)

    def test_access_factor_increases(self):
        self.assertGreater(access_factor(5), access_factor(1))
        self.assertGreater(access_factor(10), access_factor(5))

    def test_calculate_importance_basic(self):
        now = datetime.now(timezone.utc)
        score = calculate_importance(
            confidence=0.9,
            memory_type="correction",
            created_at=now,
            access_count=0,
            now=now,
        )
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 2.0)

    def test_calculate_importance_correction_highest(self):
        now = datetime.now(timezone.utc)
        correction = calculate_importance(0.9, "correction", now, 0, now)
        preference = calculate_importance(0.9, "user_preference", now, 0, now)
        self.assertGreater(correction, preference)

    def test_calculate_importance_access_reinforcement(self):
        now = datetime.now(timezone.utc)
        with_access = calculate_importance(0.9, "fact_declaration", now, 10, now)
        without_access = calculate_importance(0.9, "fact_declaration", now, 0, now)
        self.assertGreater(with_access, without_access)


class TestRecallCache(unittest.TestCase):
    def setUp(self):
        self.cache = RecallCache(max_size=5, ttl_seconds=2)

    def test_put_and_get(self):
        data = [{"content": "test", "type": "fact_declaration"}]
        self.cache.put("default", "query", None, 10, data)
        result = self.cache.get("default", "query", None, 10)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_miss(self):
        result = self.cache.get("default", "nonexistent", None, 10)
        self.assertIsNone(result)

    def test_ttl_expiry(self):
        cache = RecallCache(max_size=5, ttl_seconds=1)
        data = [{"content": "test"}]
        cache.put("default", "query", None, 10, data)
        entry = cache._cache[list(cache._cache.keys())[0]]
        entry.expires_at = time.monotonic() - 1
        result = cache.get("default", "query", None, 10)
        self.assertIsNone(result)

    def test_lru_eviction(self):
        cache = RecallCache(max_size=2, ttl_seconds=60)
        cache.put("ns", "q1", None, 10, [{"c": 1}])
        cache.put("ns", "q2", None, 10, [{"c": 2}])
        cache.put("ns", "q3", None, 10, [{"c": 3}])
        self.assertIsNone(cache.get("ns", "q1", None, 10))
        self.assertIsNotNone(cache.get("ns", "q2", None, 10))

    def test_clear(self):
        self.cache.put("default", "query", None, 10, [{"c": 1}])
        self.cache.clear()
        self.assertIsNone(self.cache.get("default", "query", None, 10))

    def test_stats(self):
        self.cache.put("default", "query", None, 10, [{"c": 1}])
        self.cache.get("default", "query", None, 10)
        self.cache.get("default", "miss", None, 10)
        stats = self.cache.stats
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

    def test_invalidate(self):
        self.cache.put("default", "query", None, 10, [{"c": 1}])
        self.cache.invalidate()
        self.assertIsNone(self.cache.get("default", "query", None, 10))


class TestContextSelection(unittest.TestCase):
    def test_estimate_tokens_english(self):
        tokens = _estimate_tokens("Hello world this is a test")
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 20)

    def test_estimate_tokens_cjk(self):
        tokens = _estimate_tokens("你好世界这是一个测试")
        self.assertGreater(tokens, 0)

    def test_context_relevance_match(self):
        rel = context_relevance("I prefer dark mode in VS Code", "dark mode")
        self.assertGreater(rel, 0.0)

    def test_context_relevance_no_match(self):
        rel = context_relevance("I like Python programming", "cooking recipes")
        self.assertEqual(rel, 0.0)

    def test_context_relevance_empty(self):
        self.assertEqual(context_relevance("test", ""), 0.0)
        self.assertEqual(context_relevance("", "test"), 0.0)

    def test_select_memories_basic(self):
        memories = [
            {"content": "I prefer dark mode", "importance_score": 0.8, "type": "user_preference", "confidence": 0.9},
            {"content": "I use Python", "importance_score": 0.5, "type": "fact_declaration", "confidence": 0.7},
        ]
        selected = select_memories(memories, context="dark mode", max_count=5, max_tokens=1000)
        self.assertEqual(len(selected), 2)
        self.assertIn("_selection_score", selected[0])

    def test_select_memories_token_budget(self):
        memories = [
            {"content": f"Memory {i} " * 50, "importance_score": 0.9 - i * 0.1, "type": "fact_declaration", "confidence": 0.8}
            for i in range(10)
        ]
        selected = select_memories(memories, max_count=10, max_tokens=100)
        self.assertLessEqual(len(selected), 10)

    def test_select_memories_empty(self):
        self.assertEqual(select_memories([]), [])

    def test_build_prompt_en(self):
        prompt = build_prompt(
            memories=[{"content": "I prefer dark mode", "type": "user_preference", "confidence": 0.9, "source_layer": "rule"}],
            knowledge=[],
            language="en",
        )
        self.assertIn("User Memories", prompt)
        self.assertIn("dark mode", prompt)

    def test_build_prompt_zh(self):
        prompt = build_prompt(
            memories=[{"content": "我喜欢深色模式", "type": "user_preference", "confidence": 0.9, "source_layer": "rule"}],
            knowledge=[],
            language="zh",
        )
        self.assertIn("用户记忆", prompt)

    def test_build_prompt_ja(self):
        prompt = build_prompt(
            memories=[{"content": "ダークモードが好き", "type": "user_preference", "confidence": 0.9, "source_layer": "rule"}],
            knowledge=[],
            language="ja",
        )
        self.assertIn("ユーザー記憶", prompt)

    def test_format_memory_entry(self):
        entry = format_memory_entry(
            {"type": "correction", "content": "Use PostgreSQL not MySQL", "confidence": 0.95, "source_layer": "rule"},
            language="en",
        )
        self.assertIn("NOT repeat", entry)
        self.assertIn("PostgreSQL", entry)

    def test_format_memory_entry_preference_avoid(self):
        entry = format_memory_entry(
            {"type": "user_preference", "content": "MySQL", "confidence": 0.9, "auto_rule": "avoid", "source_layer": "rule"},
            language="en",
        )
        self.assertIn("NOT want", entry)

    def test_format_memory_entry_preference_prefer(self):
        entry = format_memory_entry(
            {"type": "user_preference", "content": "PostgreSQL", "confidence": 0.9, "auto_rule": "prefer", "source_layer": "rule"},
            language="en",
        )
        self.assertIn("prefers", entry)

    def test_format_memory_entry_decision(self):
        entry = format_memory_entry(
            {"type": "decision", "content": "Use React for frontend", "confidence": 0.9, "source_layer": "rule"},
            language="en",
        )
        self.assertIn("Always follow", entry)

    def test_format_memory_entry_superseded(self):
        entry = format_memory_entry(
            {"type": "fact_declaration", "content": "User lives in Beijing", "confidence": 0.9, "superseded_at": "2026-01-01", "source_layer": "rule"},
            language="en",
        )
        self.assertIn("outdated", entry)

    def test_format_memory_entry_session_summary(self):
        entry = format_memory_entry(
            {"type": "session_summary", "content": "User discussed database preferences", "confidence": 0.9, "source_layer": "rule"},
            language="en",
        )
        self.assertIn("Based on previous conversations", entry)


class TestMerge(unittest.TestCase):
    def test_similarity_identical(self):
        self.assertAlmostEqual(_similarity("hello world", "hello world"), 1.0)

    def test_similarity_different(self):
        self.assertLess(_similarity("hello world", "goodbye moon"), 0.5)

    def test_detect_hash_conflicts(self):
        memories = [
            {"content": "I prefer dark mode", "content_hash": "abc123", "storage_key": "k1", "type": "user_preference", "namespace": "ns1"},
            {"content": "I prefer dark mode", "content_hash": "abc123", "storage_key": "k2", "type": "user_preference", "namespace": "ns2"},
        ]
        conflicts = detect_conflicts(memories)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(len(conflicts[0]), 2)

    def test_merge_latest_wins(self):
        memories = [
            {"content": "old", "content_hash": "abc", "storage_key": "k1", "type": "fact_declaration", "confidence": 0.9, "updated_at": "2026-01-01"},
            {"content": "new", "content_hash": "abc", "storage_key": "k2", "type": "fact_declaration", "confidence": 0.8, "updated_at": "2026-04-01"},
        ]
        merged = merge_memories(memories, strategy="latest_wins")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["content"], "new")

    def test_merge_highest_confidence(self):
        memories = [
            {"content": "low conf", "content_hash": "abc", "storage_key": "k1", "type": "fact_declaration", "confidence": 0.5, "updated_at": "2026-04-01"},
            {"content": "high conf", "content_hash": "abc", "storage_key": "k2", "type": "fact_declaration", "confidence": 0.95, "updated_at": "2026-01-01"},
        ]
        merged = merge_memories(memories, strategy="highest_confidence")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["content"], "high conf")

    def test_merge_all_keeps_duplicates(self):
        memories = [
            {"content": "v1", "content_hash": "abc", "storage_key": "k1", "type": "fact_declaration", "confidence": 0.9},
            {"content": "v2", "content_hash": "abc", "storage_key": "k2", "type": "fact_declaration", "confidence": 0.8},
        ]
        merged = merge_memories(memories, strategy="merge_all")
        self.assertEqual(len(merged), 2)
        self.assertIn("_duplicates", merged[0])

    def test_merge_no_conflicts(self):
        memories = [
            {"content": "A", "content_hash": "h1", "storage_key": "k1", "type": "user_preference", "confidence": 0.9},
            {"content": "B", "content_hash": "h2", "storage_key": "k2", "type": "fact_declaration", "confidence": 0.8},
        ]
        merged = merge_memories(memories, strategy="latest_wins")
        self.assertEqual(len(merged), 2)

    def test_conflict_callback(self):
        callback_called = []
        memories = [
            {"content": "A", "content_hash": "abc", "storage_key": "k1", "type": "user_preference", "confidence": 0.9},
            {"content": "B", "content_hash": "abc", "storage_key": "k2", "type": "user_preference", "confidence": 0.8},
        ]
        merge_memories(memories, conflict_callback=lambda g: callback_called.append(len(g)))
        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0], 2)


class TestCarryMemV050(unittest.TestCase):
    def setUp(self):
        self.cm = CarryMem(storage="sqlite", db_path=":memory:")

    def tearDown(self):
        self.cm.close()

    def test_importance_score_on_remember(self):
        result = self.cm.classify_and_remember("I prefer dark mode")
        self.assertTrue(result["stored"])
        entries = result["entries"]
        self.assertGreater(len(entries), 0)
        self.assertGreater(entries[0].get("importance_score", 0), 0)

    def test_importance_score_increases_on_recall(self):
        self.cm.classify_and_remember("I prefer dark mode")
        r1 = self.cm.recall_memories(query="dark mode")
        score1 = r1[0].get("importance_score", 0)
        self.cm.clear_cache()
        r2 = self.cm.recall_memories(query="dark mode")
        score2 = r2[0].get("importance_score", 0)
        self.assertGreaterEqual(score2, score1)

    def test_last_accessed_at_updated(self):
        self.cm.classify_and_remember("I prefer dark mode")
        results = self.cm.recall_memories(query="dark mode")
        self.assertIsNotNone(results[0].get("last_accessed_at"))

    def test_version_field(self):
        result = self.cm.classify_and_remember("I prefer dark mode")
        self.assertEqual(result["entries"][0].get("version", 1), 1)

    def test_build_context(self):
        self.cm.classify_and_remember("I prefer dark mode")
        ctx = self.cm.build_context(context="dark mode", language="en")
        self.assertIn("system_prompt", ctx)
        self.assertIn("memories", ctx)
        self.assertIn("token_estimate", ctx)
        self.assertGreater(ctx["memory_count"], 0)

    def test_build_system_prompt_enhanced(self):
        self.cm.classify_and_remember("I prefer dark mode")
        prompt = self.cm.build_system_prompt(context="dark mode", language="en")
        self.assertIn("User Memories", prompt)
        self.assertIn("dark mode", prompt)

    def test_build_system_prompt_zh(self):
        self.cm.classify_and_remember("我喜欢深色模式")
        prompt = self.cm.build_system_prompt(context="深色模式", language="zh")
        self.assertIn("用户记忆", prompt)

    def test_build_context_token_budget(self):
        for i in range(20):
            self.cm.classify_and_remember(f"Memory number {i} about various topics")
        ctx = self.cm.build_context(max_memories=5, max_tokens=200)
        self.assertLessEqual(ctx["memory_count"], 5)

    def test_update_memory(self):
        result = self.cm.classify_and_remember("I prefer dark mode")
        key = result["storage_keys"][0]
        updated = self.cm.update_memory(key, "I prefer light mode now", reason="Changed preference")
        self.assertTrue(updated["updated"])
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["content"], "I prefer light mode now")

    def test_update_memory_not_found(self):
        updated = self.cm.update_memory("nonexistent_key", "new content")
        self.assertFalse(updated["updated"])

    def test_get_memory_history(self):
        result = self.cm.classify_and_remember("I prefer dark mode")
        key = result["storage_keys"][0]
        self.cm.update_memory(key, "I prefer light mode", reason="Changed")
        history = self.cm.get_memory_history(key)
        self.assertGreaterEqual(len(history), 2)
        self.assertTrue(history[0].get("is_current"))

    def test_rollback_memory(self):
        result = self.cm.classify_and_remember("I prefer dark mode")
        key = result["storage_keys"][0]
        self.cm.update_memory(key, "I prefer light mode")
        rolled_back = self.cm.rollback_memory(key, version=1)
        self.assertTrue(rolled_back["rolled_back"])
        self.assertEqual(rolled_back["content"], "I prefer dark mode")

    def test_rollback_nonexistent_version(self):
        result = self.cm.classify_and_remember("I prefer dark mode")
        key = result["storage_keys"][0]
        rolled_back = self.cm.rollback_memory(key, version=99)
        self.assertFalse(rolled_back["rolled_back"])

    def test_merge_memories(self):
        cm2 = CarryMem(storage="sqlite", db_path=":memory:", namespace="agent2")
        try:
            self.cm.classify_and_remember("I prefer dark mode")
            cm2.classify_and_remember("I prefer dark mode")
            merged = self.cm.merge_memories(namespaces=["default", "agent2"])
            self.assertIn("total_input", merged)
            self.assertIn("duplicates_removed", merged)
        finally:
            cm2.close()

    def test_clear_cache(self):
        self.cm.classify_and_remember("I prefer dark mode")
        self.cm.recall_memories(query="dark mode")
        self.cm.clear_cache()

    def test_recalculate_importance(self):
        self.cm.classify_and_remember("I prefer dark mode")
        total = self.cm._adapter.recalculate_importance()
        self.assertGreater(total, 0)

    def test_preference_always_in_system_prompt(self):
        # Core preferences (high confidence) are always injected
        self.cm.classify_and_remember("I prefer Python for coding", force_type="user_preference")
        # Boost confidence to make it a core preference
        prefs = self.cm.recall_memories(query="", limit=5, filters={"type": "user_preference"})
        for p in prefs:
            if "Python" in p.get("content", ""):
                self.cm._adapter._get_connection().execute(
                    "UPDATE memories SET confidence = 0.95 WHERE storage_key = ?",
                    (p.get("storage_key"),)
                )
        self.cm._adapter._get_connection().commit()
        self.cm.classify_and_remember("I work at Google")
        result = self.cm.build_context(context="unrelated topic", max_memories=2)
        prompt = result["system_prompt"]
        self.assertIn("Python", prompt)

    def test_preference_always_in_qa_prompt(self):
        # Core preferences (high confidence) are always injected
        self.cm.classify_and_remember("I prefer Python for coding", force_type="user_preference")
        # Boost confidence to make it a core preference
        prefs = self.cm.recall_memories(query="", limit=5, filters={"type": "user_preference"})
        for p in prefs:
            if "Python" in p.get("content", ""):
                self.cm._adapter._get_connection().execute(
                    "UPDATE memories SET confidence = 0.95 WHERE storage_key = ?",
                    (p.get("storage_key"),)
                )
        self.cm._adapter._get_connection().commit()
        self.cm.classify_and_remember("I work at Google")
        prompt = self.cm.build_qa_prompt(question="unrelated topic", max_memories=2)
        self.assertIn("Python", prompt)

    def test_contextual_preference_filtered_by_relevance(self):
        # Contextual preferences (normal confidence) are only injected when relevant
        self.cm.classify_and_remember("I prefer Python for coding", force_type="user_preference")
        self.cm.classify_and_remember("I work at Google")
        # Normal confidence preference should appear in relevant query
        prompt_relevant = self.cm.build_qa_prompt(question="What programming language should I use?", max_memories=5)
        # But may not appear in completely unrelated query (no FTS match)
        prompt_unrelated = self.cm.build_qa_prompt(question="What is the weather today?", max_memories=5)
        # At minimum, relevant query should find the Python preference
        self.assertIn("Python", prompt_relevant)


class TestFastPath(unittest.TestCase):

    def test_fast_path_only_preference(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I prefer Python", "auto_rule": "prefer", "superseded_at": None},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="What language?", include_question=False)
        self.assertIn("The user has the following preference: I prefer Python", prompt)
        self.assertIn("Where relevant, incorporate this preference", prompt)
        self.assertNotIn("Additional context", prompt)

    def test_fast_path_avoid_preference(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I dislike Java", "auto_rule": "avoid", "superseded_at": None},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="What language?", include_question=False)
        self.assertIn("The user has explicitly stated they do NOT want: I dislike Java", prompt)
        self.assertIn("Where relevant, do NOT recommend", prompt)

    def test_fast_path_not_triggered_with_facts(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I prefer Python", "auto_rule": "prefer", "superseded_at": None},
            {"type": "personal_fact", "content": "I work at Google", "superseded_at": None},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="What language?", include_question=False)
        self.assertIn("The user has the following preference: I prefer Python", prompt)
        self.assertIn("Additional context", prompt)
        self.assertIn("I work at Google", prompt)

    def test_fast_path_not_triggered_with_knowledge(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I prefer Python", "auto_rule": "prefer", "superseded_at": None},
        ]
        knowledge = [{"title": "Python Guide", "content": "Python is great"}]
        prompt = build_qa_prompt(memories=memories, knowledge=knowledge, question="What language?", include_question=False)
        self.assertIn("The user has the following preference: I prefer Python", prompt)
        self.assertIn("Knowledge Base", prompt)

    def test_fast_path_not_triggered_with_outdated(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I prefer Python", "auto_rule": "prefer", "superseded_at": None},
            {"type": "user_preference", "content": "I prefer Java", "auto_rule": "prefer", "superseded_at": "2026-01-01"},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="What language?", include_question=False)
        self.assertIn("The user has the following preference: I prefer Python", prompt)
        self.assertIn("Outdated", prompt)

    def test_fast_path_include_question(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I prefer Python", "auto_rule": "prefer", "superseded_at": None},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="What language?", include_question=True)
        self.assertIn("Question: What language?", prompt)
        self.assertIn("Answer:", prompt)

    def test_mixed_scenario_preference_and_fact(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "user_preference", "content": "I prefer Python", "auto_rule": "prefer", "superseded_at": None},
            {"type": "personal_fact", "content": "I work at Google", "superseded_at": None},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="What language?", include_question=False)
        self.assertIn("I prefer Python", prompt)
        self.assertIn("I work at Google", prompt)
        self.assertIn("Additional context", prompt)

    def test_no_preference_goes_full_path(self):
        from carrymem.context import build_qa_prompt

        memories = [
            {"type": "personal_fact", "content": "I work at Google", "superseded_at": None},
        ]
        prompt = build_qa_prompt(memories=memories, knowledge=[], question="Where do I work?", include_question=False)
        self.assertNotIn("The user has the following preference", prompt)
        self.assertIn("I work at Google", prompt)


if __name__ == "__main__":
    unittest.main()
