"""Test suite for v0.5.2 Summary Layer + Progressive Disclosure.

Covers 9 dimensions per spec/v0.5.2_spec.md §6:
- Happy Path: rule-based summarizer across types and levels
- LLM switch: env var override, TRAE detection, default off, LLM fallback
- Progressive: bucket→depth mapping, budget exhaustion
- Cache: hit, raw_text update invalidation, force regenerate
- Boundary: empty text, long text, None summary, single sentence
- Integration: build_prompt progressive=True/False, format depth
- Performance: 1000 memories < 500ms
- Config: CARRYMEM_SUMMARY_ENABLED=0
- Schema: migrate_v052 idempotent + field existence
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from carrymem.format import format_memory_entry
from carrymem.layers.summary_layer import (
    BUCKET_DEPTH,
    RuleBasedSummarizer,
    SummaryLayer,
    get_depth_for_bucket,
    is_llm_summary_enabled,
    is_summary_enabled,
)
from carrymem.prompt import build_prompt

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def sample_memory() -> Dict[str, Any]:
    """Standard test memory with multi-sentence raw_text."""
    return {
        "type": "user_preference",
        "raw_text": "I prefer tea over coffee. I especially enjoy oolong tea in the morning.",
        "content": "I prefer tea over coffee.",
        "confidence": 0.9,
    }


@pytest.fixture
def decision_memory() -> Dict[str, Any]:
    """Decision memory with 'decided:' marker."""
    return {
        "type": "decision",
        "raw_text": "We decided: use PostgreSQL for all production databases going forward.",
        "content": "Use PostgreSQL for production.",
        "confidence": 0.95,
    }


@pytest.fixture
def fact_memory() -> Dict[str, Any]:
    """Fact declaration memory."""
    return {
        "type": "fact_declaration",
        "raw_text": "The user drives a Toyota Camry. They bought it in 2022.",
        "content": "User drives Toyota Camry.",
        "confidence": 0.85,
    }


@pytest.fixture
def summary_layer() -> SummaryLayer:
    """SummaryLayer with no LLM client (rule-based only)."""
    return SummaryLayer()


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Clear all summary-related env vars before each test."""
    for var in ("CARRYMEM_SUMMARY_ENABLED", "CARRYMEM_LLM_SUMMARY", "CARRYMEM_ENV", "TRAE_SESSION_ID"):
        monkeypatch.delenv(var, raising=False)


# ── 1. Happy Path: RuleBasedSummarizer ────────────────────────────


class TestRuleBasedSummarizer:
    """Verify rule-based summarizer across types and levels."""

    def test_level_3_returns_full_raw_text(self, sample_memory):
        """Level 3 (full) should return raw_text unchanged."""
        summarizer = RuleBasedSummarizer()
        result = summarizer.summarize(sample_memory, level=3)
        assert result == sample_memory["raw_text"]

    def test_level_2_user_preference_returns_labeled_first_sentence(self, sample_memory):
        """Level 2 should return '[Preference] first sentence'."""
        summarizer = RuleBasedSummarizer()
        result = summarizer.summarize(sample_memory, level=2)
        assert result.startswith("[Preference]")
        assert "tea" in result.lower()

    def test_level_2_decision_extracts_after_decided_marker(self, decision_memory):
        """Level 2 decision should extract content after 'decided:'."""
        summarizer = RuleBasedSummarizer()
        result = summarizer.summarize(decision_memory, level=2)
        assert "[Decision]" in result
        assert "PostgreSQL" in result

    def test_level_1_returns_keywords(self, sample_memory):
        """Level 1 should return '[Label] keyword1 keyword2 keyword3'."""
        summarizer = RuleBasedSummarizer()
        result = summarizer.summarize(sample_memory, level=1)
        assert result.startswith("[Preference]")
        words = result.split("] ")[1].split()
        assert len(words) <= 3

    def test_level_2_fact_declaration(self, fact_memory):
        """Level 2 fact_declaration should return first sentence with label."""
        summarizer = RuleBasedSummarizer()
        result = summarizer.summarize(fact_memory, level=2)
        assert "[Fact]" in result
        assert "Toyota" in result

    def test_level_1_unknown_type_uses_title_label(self):
        """Level 1 unknown type should use titled type as label."""
        summarizer = RuleBasedSummarizer()
        m = {"type": "custom_type", "raw_text": "Some interesting content here"}
        result = summarizer.summarize(m, level=1)
        assert "[Custom_Type]" in result


# ── 2. LLM Switch Configuration ───────────────────────────────────


class TestLLMSwitch:
    """Verify LLM summary enable/disable logic."""

    def test_default_disabled(self):
        """LLM summary should be disabled by default."""
        assert is_llm_summary_enabled() is False

    def test_env_var_explicit_enable(self, monkeypatch):
        """CARRYMEM_LLM_SUMMARY=1 should enable LLM summary."""
        monkeypatch.setenv("CARRYMEM_LLM_SUMMARY", "1")
        assert is_llm_summary_enabled() is True

    def test_env_var_explicit_disable(self, monkeypatch):
        """CARRYMEM_LLM_SUMMARY=0 should disable LLM summary."""
        monkeypatch.setenv("CARRYMEM_LLM_SUMMARY", "0")
        assert is_llm_summary_enabled() is False

    def test_trae_env_detection(self, monkeypatch):
        """CARRYMEM_ENV=trae should auto-enable LLM summary."""
        monkeypatch.setenv("CARRYMEM_ENV", "trae")
        assert is_llm_summary_enabled() is True

    def test_trae_session_id_detection(self, monkeypatch):
        """TRAE_SESSION_ID presence should auto-enable LLM summary."""
        monkeypatch.setenv("TRAE_SESSION_ID", "session-123")
        assert is_llm_summary_enabled() is True

    def test_env_var_overrides_trae_detection(self, monkeypatch):
        """CARRYMEM_LLM_SUMMARY=0 should override TRAE env detection."""
        monkeypatch.setenv("CARRYMEM_ENV", "trae")
        monkeypatch.setenv("CARRYMEM_LLM_SUMMARY", "0")
        assert is_llm_summary_enabled() is False


class TestLLMFallback:
    """Verify LLM failure degrades to rule-based."""

    def test_llm_failure_falls_back_to_rule_based(self, sample_memory):
        """When LLM call fails, should fall back to rule-based summary."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.chat.side_effect = RuntimeError("LLM service unavailable")

        layer = SummaryLayer(llm_client=mock_llm)
        # Enable LLM summary via env
        os.environ["CARRYMEM_LLM_SUMMARY"] = "1"
        try:
            result = layer.summarize(sample_memory, level=2)
            assert "[Preference]" in result
            assert "tea" in result.lower()
        finally:
            os.environ.pop("CARRYMEM_LLM_SUMMARY", None)

    def test_llm_unavailable_uses_rule_based(self, sample_memory):
        """When LLM is not available, should use rule-based directly."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = False

        layer = SummaryLayer(llm_client=mock_llm)
        os.environ["CARRYMEM_LLM_SUMMARY"] = "1"
        try:
            result = layer.summarize(sample_memory, level=2)
            assert "[Preference]" in result
        finally:
            os.environ.pop("CARRYMEM_LLM_SUMMARY", None)


# ── 3. Progressive Disclosure ─────────────────────────────────────


class TestProgressiveDisclosure:
    """Verify bucket→depth mapping and progressive rendering."""

    def test_bucket_depth_mapping(self):
        """BUCKET_DEPTH should map: mandatory=3, important=2, context=2, outdated=1."""
        assert BUCKET_DEPTH["mandatory"] == 3
        assert BUCKET_DEPTH["important"] == 2
        assert BUCKET_DEPTH["context"] == 2
        assert BUCKET_DEPTH["outdated"] == 1

    def test_get_depth_for_bucket_known(self):
        """get_depth_for_bucket should return correct depth for known buckets."""
        assert get_depth_for_bucket("mandatory") == 3
        assert get_depth_for_bucket("important") == 2
        assert get_depth_for_bucket("context") == 2
        assert get_depth_for_bucket("outdated") == 1

    def test_get_depth_for_bucket_unknown_defaults_to_3(self):
        """Unknown bucket should default to depth 3 (full content)."""
        assert get_depth_for_bucket("unknown_bucket") == 3

    def test_render_for_bucket_mandatory_returns_full(self, sample_memory):
        """render_for_bucket('mandatory') should return full raw_text."""
        layer = SummaryLayer()
        result = layer.render_for_bucket(sample_memory, "mandatory")
        assert result == sample_memory["raw_text"]

    def test_render_for_bucket_outdated_returns_keywords(self, sample_memory):
        """render_for_bucket('outdated') should return keyword-level summary."""
        layer = SummaryLayer()
        result = layer.render_for_bucket(sample_memory, "outdated")
        assert "[Preference]" in result
        # Level 1 should be shorter than full raw_text
        assert len(result) < len(sample_memory["raw_text"])


# ── 4. Cache Behavior ─────────────────────────────────────────────


class TestSummaryCache:
    """Verify summary caching, invalidation, and force regeneration."""

    def test_cache_hit_returns_cached_summary(self, sample_memory):
        """When cached summary exists at sufficient level, should use it."""
        m = dict(sample_memory)
        m["summary"] = "User prefers tea"
        m["summary_level"] = 2

        layer = SummaryLayer()
        result = layer.summarize(m, level=2)
        assert "User prefers tea" in result

    def test_force_bypasses_cache(self, sample_memory):
        """force=True should regenerate even when cache exists."""
        m = dict(sample_memory)
        m["summary"] = "Old cached summary"
        m["summary_level"] = 2

        mock_llm = MagicMock()
        mock_llm.is_available.return_value = False
        layer = SummaryLayer(llm_client=mock_llm)

        result = layer.summarize(m, level=2, force=True)
        assert "Old cached summary" not in result
        assert "[Preference]" in result

    def test_level_3_always_returns_raw_text_ignoring_cache(self, sample_memory):
        """Level 3 should always return raw_text, ignoring any cache."""
        m = dict(sample_memory)
        m["summary"] = "Cached summary"
        m["summary_level"] = 2

        layer = SummaryLayer()
        result = layer.summarize(m, level=3)
        assert result == sample_memory["raw_text"]


# ── 5. Boundary Cases ─────────────────────────────────────────────


class TestBoundaryCases:
    """Verify behavior at edge cases."""

    def test_empty_raw_text(self):
        """Empty raw_text should not crash; should return label-only or empty."""
        summarizer = RuleBasedSummarizer()
        m = {"type": "user_preference", "raw_text": "", "content": ""}
        result = summarizer.summarize(m, level=2)
        assert "[Preference]" in result

    def test_none_raw_text_falls_back_to_content(self):
        """Missing raw_text should fall back to content field."""
        summarizer = RuleBasedSummarizer()
        m = {"type": "fact_declaration", "raw_text": "", "content": "Fallback content"}
        result = summarizer.summarize(m, level=2)
        assert "Fallback content" in result

    def test_very_long_text_truncated_at_level_2(self):
        """Level 2 should truncate long text with ellipsis."""
        summarizer = RuleBasedSummarizer()
        long_text = "This is a very long sentence. " * 20
        m = {"type": "fact_declaration", "raw_text": long_text}
        result = summarizer.summarize(m, level=2)
        assert len(result) <= 200  # _MAX_SHORT_CHARS + label + ellipsis

    def test_single_sentence_memory(self):
        """Single-sentence memory should return that sentence at level 2."""
        summarizer = RuleBasedSummarizer()
        m = {"type": "user_preference", "raw_text": "I like Python."}
        result = summarizer.summarize(m, level=2)
        assert "Python" in result


# ── 6. Integration: format_memory_entry + build_prompt ────────────


class TestFormatMemoryEntryDepth:
    """Verify format_memory_entry depth parameter."""

    def test_depth_3_preserves_v051_behavior(self, sample_memory):
        """depth=3 should produce the same output as v0.5.1 (no depth param)."""
        result_with_depth = format_memory_entry(sample_memory, depth=3)
        result_without_depth = format_memory_entry(sample_memory)
        assert result_with_depth == result_without_depth

    def test_depth_2_uses_cached_summary(self, sample_memory):
        """depth=2 should use cached summary when available."""
        m = dict(sample_memory)
        m["summary"] = "Cached preference summary"
        result = format_memory_entry(m, depth=2)
        assert "Cached preference summary" in result

    def test_depth_2_generates_rule_based_without_cache(self, sample_memory):
        """depth=2 without cache should generate rule-based summary."""
        result = format_memory_entry(sample_memory, depth=2)
        assert "[Preference]" in result
        assert "tea" in result.lower()

    def test_depth_1_extracts_keywords(self, sample_memory):
        """depth=1 should extract keywords."""
        result = format_memory_entry(sample_memory, depth=1)
        assert "[Preference]" in result


class TestBuildPromptProgressive:
    """Verify build_prompt progressive parameter."""

    def test_progressive_false_preserves_v051_behavior(self, sample_memory):
        """progressive=False should produce same output as v0.5.1."""
        prompt_old = build_prompt([sample_memory], [], progressive=False)
        prompt_default = build_prompt([sample_memory], [])
        assert prompt_old == prompt_default

    def test_progressive_true_renders_important_at_depth_2(self, fact_memory):
        """progressive=True should render important bucket at depth 2."""
        prompt_full = build_prompt([fact_memory], [], progressive=False)
        prompt_progressive = build_prompt([fact_memory], [], progressive=True)

        # Both should contain the fact
        assert "Toyota" in prompt_full
        assert "Toyota" in prompt_progressive

        # Progressive should be shorter (summary vs full text)
        assert len(prompt_progressive) <= len(prompt_full)

    def test_progressive_true_with_cached_summary(self, fact_memory):
        """progressive=True should use cached summary when available."""
        m = dict(fact_memory)
        m["summary"] = "User drives Toyota Camry"
        prompt = build_prompt([m], [], progressive=True)
        assert "User drives Toyota Camry" in prompt

    def test_mandatory_bucket_always_full_depth_in_progressive(self, sample_memory):
        """Mandatory bucket (user_preference) should always render at depth 3."""
        prompt = build_prompt([sample_memory], [], progressive=True)
        # Full raw_text should be present (depth=3)
        assert "I prefer tea over coffee. I especially enjoy oolong tea" in prompt


# ── 7. Performance ────────────────────────────────────────────────


class TestPerformance:
    """Verify progressive prompt generation meets performance targets."""

    def test_1000_memories_progressive_under_500ms(self):
        """Generate progressive prompt for 1000 memories in < 500ms."""
        # Mix of mandatory, important, and context memories
        memories = []
        for i in range(1000):
            if i % 3 == 0:
                memories.append(
                    {
                        "type": "user_preference",
                        "raw_text": f"Preference number {i}. This is a test preference.",
                        "content": f"Preference {i}",
                        "confidence": 0.9,
                    }
                )
            elif i % 3 == 1:
                memories.append(
                    {
                        "type": "fact_declaration",
                        "raw_text": f"Fact number {i}. This is a test fact statement.",
                        "content": f"Fact {i}",
                        "confidence": 0.85,
                    }
                )
            else:
                memories.append(
                    {
                        "type": "relationship",
                        "raw_text": f"Relationship number {i}. This is a test relationship note.",
                        "content": f"Relationship {i}",
                        "confidence": 0.6,
                    }
                )

        start = time.perf_counter()
        build_prompt(memories, [], progressive=True)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500, f"Progressive prompt took {elapsed_ms:.1f}ms (target: <500ms)"


# ── 8. Config: CARRYMEM_SUMMARY_ENABLED ───────────────────────────


class TestSummaryEnabledConfig:
    """Verify CARRYMEM_SUMMARY_ENABLED switch."""

    def test_summary_enabled_by_default(self):
        """Summary layer should be enabled by default."""
        assert is_summary_enabled() is True

    def test_summary_disabled_when_env_zero(self, monkeypatch):
        """CARRYMEM_SUMMARY_ENABLED=0 should disable summary layer."""
        monkeypatch.setenv("CARRYMEM_SUMMARY_ENABLED", "0")
        assert is_summary_enabled() is False

    def test_disabled_summary_returns_rule_based_anyway(self, sample_memory, monkeypatch):
        """When disabled, summarize() should still return rule-based (fallback)."""
        monkeypatch.setenv("CARRYMEM_SUMMARY_ENABLED", "0")
        layer = SummaryLayer()
        result = layer.summarize(sample_memory, level=2)
        # Should still produce a valid summary (rule-based fallback)
        assert "[Preference]" in result


# ── 9. Schema Migration ───────────────────────────────────────────


class TestSchemaMigration:
    """Verify migrate_v052 idempotency and field existence."""

    def test_migrate_v052_adds_columns(self, tmp_path):
        """migrate_v052 should add summary and summary_level columns."""
        from carrymem.adapters.sqlite.connection import ConnectionManager
        from carrymem.adapters.sqlite.schema import SchemaManager

        conn_mgr = ConnectionManager(
            db_path=str(tmp_path / "test.db"),
            namespace="default",
            enable_vector=False,
        )
        schema = SchemaManager(conn_mgr)
        schema.init_schema()

        # Run v0.5.2 migration
        schema.migrate_v052()

        # Verify columns exist
        conn = conn_mgr.get_connection()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()]
        assert "summary" in columns
        assert "summary_level" in columns

        conn_mgr.close()

    def test_migrate_v052_idempotent(self, tmp_path):
        """Running migrate_v052 twice should not error (idempotent)."""
        from carrymem.adapters.sqlite.connection import ConnectionManager
        from carrymem.adapters.sqlite.schema import SchemaManager

        conn_mgr = ConnectionManager(
            db_path=str(tmp_path / "test.db"),
            namespace="default",
            enable_vector=False,
        )
        schema = SchemaManager(conn_mgr)
        schema.init_schema()

        # Run migration twice
        schema.migrate_v052()
        schema.migrate_v052()  # Should not raise

        # Verify columns still exist
        conn = conn_mgr.get_connection()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()]
        assert "summary" in columns
        assert "summary_level" in columns

        conn_mgr.close()


# ── 10. CRUD: Summary Invalidation on Update ──────────────────────


class TestSummaryInvalidation:
    """Verify summary cache is invalidated when content changes."""

    def test_update_memory_clears_summary(self, tmp_path):
        """update_memory should clear summary/summary_level fields."""
        from carrymem.adapters.base import MemoryEntry
        from carrymem.adapters.sqlite import SQLiteAdapter

        adapter = SQLiteAdapter(db_path=str(tmp_path / "test.db"))

        entry = MemoryEntry(
            id="test-1",
            type="user_preference",
            content="I prefer tea",
            raw_text="I prefer tea over coffee",
            confidence=0.9,
        )
        stored = adapter.store_entry(entry)

        # Manually set summary
        conn = adapter._conn_mgr.get_connection()
        conn.execute(
            "UPDATE memories SET summary = ?, summary_level = ? WHERE storage_key = ?",
            ("Cached summary", 2, stored.storage_key),
        )
        conn.commit()

        # Verify summary was set
        row = conn.execute(
            "SELECT summary, summary_level FROM memories WHERE storage_key = ?",
            (stored.storage_key,),
        ).fetchone()
        assert row["summary"] == "Cached summary"
        assert row["summary_level"] == 2

        # Update memory content
        adapter.update_memory(stored.storage_key, new_content="I now prefer coffee")

        # Verify summary was cleared
        row = conn.execute(
            "SELECT summary, summary_level FROM memories WHERE storage_key = ?",
            (stored.storage_key,),
        ).fetchone()
        assert row["summary"] is None
        assert row["summary_level"] is None

        adapter.close()


# ── 11. StoredMemory Serialization ────────────────────────────────


class TestStoredMemorySummaryFields:
    """Verify StoredMemory properly serializes summary/summary_level."""

    def test_to_dict_includes_summary_fields(self):
        """to_dict() should include summary and summary_level."""
        from carrymem.adapters.base import StoredMemory

        m = StoredMemory(
            id="test",
            type="user_preference",
            content="test content",
            raw_text="test raw text",
            confidence=0.9,
            summary="test summary",
            summary_level=2,
        )
        d = m.to_dict()
        assert d["summary"] == "test summary"
        assert d["summary_level"] == 2

    def test_from_dict_includes_summary_fields(self):
        """from_dict() should reconstruct summary and summary_level."""
        from carrymem.adapters.base import StoredMemory

        d = {
            "id": "test",
            "type": "user_preference",
            "content": "test content",
            "raw_text": "test raw text",
            "confidence": 0.9,
            "summary": "test summary",
            "summary_level": 2,
        }
        m = StoredMemory.from_dict(d)
        assert m.summary == "test summary"
        assert m.summary_level == 2

    def test_to_dict_defaults_to_none(self):
        """to_dict() should default summary/summary_level to None."""
        from carrymem.adapters.base import StoredMemory

        m = StoredMemory(
            id="test",
            type="user_preference",
            content="test",
            raw_text="test",
            confidence=0.9,
        )
        d = m.to_dict()
        assert d["summary"] is None
        assert d["summary_level"] is None
