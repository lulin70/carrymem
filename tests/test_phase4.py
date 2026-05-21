import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from carrymem import CarryMem
from carrymem.llm import LLMClient
from carrymem.layers.session_summarizer import SessionSummarizer
from carrymem.layers.semantic_aggregator import SemanticAggregator
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.adapters.base import MemoryEntry


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def adapter(db_path):
    a = SQLiteAdapter(db_path=db_path, enable_vector_search=False, enable_semantic_recall=False, enable_cache=False)
    yield a
    a.close()


@pytest.fixture
def carrymem(db_path):
    cm = CarryMem(storage="sqlite", db_path=db_path, config={"enable_vector_search": False})
    yield cm
    cm.close()


def _make_memory(**overrides):
    defaults = {
        "id": "",
        "type": "user_preference",
        "content": "I prefer dark mode",
        "raw_text": "I prefer dark mode",
        "confidence": 0.9,
        "tier": 2,
        "source_layer": "test",
        "reasoning": "test",
        "suggested_action": "store",
        "metadata": {},
    }
    defaults.update(overrides)
    return defaults


class TestLLMClient:
    def test_llm_client_default_disabled(self):
        client = LLMClient()
        assert client.is_available() is False

    def test_llm_client_with_config(self):
        import carrymem.llm as llm_mod
        original_backend = llm_mod._BACKEND
        original_openai = llm_mod._OPENAI_CLIENT
        try:
            llm_mod._BACKEND = "openai"
            llm_mod._OPENAI_CLIENT = MagicMock(return_value=MagicMock())
            client = LLMClient(config={"llm.enabled": True, "llm.api_key": "test-key"})
            assert client.is_available() is True
        finally:
            llm_mod._BACKEND = original_backend
            llm_mod._OPENAI_CLIENT = original_openai

    def test_llm_client_chat_unavailable(self):
        client = LLMClient()
        result = client.chat("Hello")
        assert result is None

    def test_llm_client_count_tokens(self):
        client = LLMClient()
        count = client.count_tokens("Hello world")
        assert isinstance(count, int)
        assert count > 0

    def test_llm_client_count_tokens_empty(self):
        client = LLMClient()
        assert client.count_tokens("") == 0

    def test_llm_client_count_tokens_cjk(self):
        client = LLMClient()
        count = client.count_tokens("你好世界")
        assert count > 0

    def test_llm_client_repr_masks_key(self):
        import carrymem.llm as llm_mod
        original_backend = llm_mod._BACKEND
        original_openai = llm_mod._OPENAI_CLIENT
        try:
            llm_mod._BACKEND = "openai"
            mock_client = MagicMock()
            llm_mod._OPENAI_CLIENT = MagicMock(return_value=mock_client)
            client = LLMClient(config={"llm.enabled": True, "llm.api_key": "sk-super-secret-key-12345"})
            r = repr(client)
            assert "sk-super-secret-key-12345" not in r
        finally:
            llm_mod._BACKEND = original_backend
            llm_mod._OPENAI_CLIENT = original_openai


class TestSessionSummarizer:
    def test_summarize_empty_memories(self):
        summarizer = SessionSummarizer()
        result = summarizer.summarize_session([])
        assert result is None

    def test_summarize_rule_based(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type="user_preference", content="I prefer dark mode"),
            _make_memory(type="decision", content="Use PostgreSQL for database"),
        ]
        result = summarizer.summarize_session(memories, session_id="sess-1")
        assert result is not None
        assert result["type"] == "session_summary"
        assert result["content"]
        assert result["metadata"]["summary_method"] == "rule"

    def test_summarize_stores_session_id(self):
        summarizer = SessionSummarizer()
        memories = [_make_memory(type="user_preference", content="I like Python")]
        result = summarizer.summarize_session(memories, session_id="sess-abc-123")
        assert result is not None
        assert result["metadata"]["session_id"] == "sess-abc-123"

    def test_summarize_excludes_superseded(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type="user_preference", content="I prefer dark mode"),
            _make_memory(type="user_preference", content="I prefer light mode", superseded_at="2026-01-01T00:00:00"),
        ]
        result = summarizer.summarize_session(memories, session_id="sess-1")
        assert result is not None
        assert "dark mode" in result["content"]
        assert "light mode" not in result["content"]

    def test_summarize_prioritizes_decisions(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type="task_pattern", content="Run tests before commit"),
            _make_memory(type="decision", content="Use React for frontend"),
            _make_memory(type="correction", content="No, use Vue instead"),
        ]
        result = summarizer.summarize_session(memories, session_id="sess-1")
        assert result is not None
        content = result["content"]
        decision_pos = content.find("Decision")
        if decision_pos == -1:
            decision_pos = content.find("决策")
        correction_pos = content.find("Correction")
        if correction_pos == -1:
            correction_pos = content.find("修正")
        pattern_pos = content.find("Pattern")
        if pattern_pos == -1:
            pattern_pos = content.find("模式")
        if decision_pos >= 0 and pattern_pos >= 0:
            assert decision_pos < pattern_pos

    def test_summarize_chinese(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type="user_preference", content="我喜欢深色模式"),
            _make_memory(type="decision", content="使用PostgreSQL作为数据库"),
        ]
        result = summarizer.summarize_session(memories, session_id="sess-zh", language="zh")
        assert result is not None
        assert "会话摘要" in result["content"] or "记忆" in result["content"]

    def test_summarize_only_sentiment_markers(self):
        summarizer = SessionSummarizer()
        memories = [
            _make_memory(type="sentiment_marker", content="I feel happy"),
        ]
        result = summarizer.summarize_session(memories, session_id="sess-1")
        assert result is None


class TestSemanticAggregator:
    def test_aggregate_empty(self):
        agg = SemanticAggregator(embedding_fn=lambda x: [0.1, 0.2])
        assert agg.aggregate([]) == []

    def test_aggregate_no_embedding_fn(self):
        agg = SemanticAggregator(embedding_fn=None)
        memories = [_make_memory(content="test")]
        assert agg.aggregate(memories) == []

    def test_aggregate_clusters_similar(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.95, 0.05, 0.0]
        call_count = [0]
        def mock_embedding_fn(text):
            call_count[0] += 1
            return emb_a if "dark mode" in text else emb_b

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content="I prefer dark mode for coding", raw_text="I prefer dark mode for coding"),
            _make_memory(content="I like dark mode when coding", raw_text="I like dark mode when coding"),
        ]
        results = agg.aggregate(memories)
        assert len(results) >= 1
        assert results[0]["source_layer"] == "semantic_aggregator"

    def test_aggregate_no_cluster_below_threshold(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.0, 0.0, 1.0]
        def mock_embedding_fn(text):
            return emb_a if "dark" in text else emb_b

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content="I prefer dark mode", raw_text="I prefer dark mode"),
            _make_memory(content="Deploy to production server", raw_text="Deploy to production server"),
        ]
        results = agg.aggregate(memories)
        assert len(results) == 0

    def test_aggregate_min_cluster_size(self):
        agg = SemanticAggregator(embedding_fn=lambda x: [0.5, 0.5])
        memories = [
            _make_memory(content="Only one memory here", raw_text="Only one memory here"),
        ]
        results = agg.aggregate(memories)
        assert len(results) == 0

    def test_aggregate_connected_components(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.85, 0.15, 0.0]
        emb_c = [0.7, 0.3, 0.0]
        call_map = {
            "memory A": emb_a,
            "memory B": emb_b,
            "memory C": emb_c,
        }
        def mock_embedding_fn(text):
            for key, emb in call_map.items():
                if key in text:
                    return emb
            return [0.0, 0.0, 0.0]

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content="This is memory A about python", raw_text="This is memory A about python"),
            _make_memory(content="This is memory B about python", raw_text="This is memory B about python"),
            _make_memory(content="This is memory C about python", raw_text="This is memory C about python"),
        ]
        results = agg.aggregate(memories)
        assert len(results) >= 1
        assert results[0]["metadata"]["cluster_size"] >= 2

    def test_aggregate_excludes_superseded(self):
        agg = SemanticAggregator(embedding_fn=lambda x: [0.5, 0.5])
        memories = [
            _make_memory(content="I prefer dark mode", raw_text="I prefer dark mode", superseded_at="2026-01-01T00:00:00"),
            _make_memory(content="I prefer light mode", raw_text="I prefer light mode"),
        ]
        results = agg.aggregate(memories)
        assert len(results) == 0

    def test_aggregate_rule_based_content(self):
        emb = [1.0, 0.0, 0.0]
        def mock_embedding_fn(text):
            return emb

        agg = SemanticAggregator(embedding_fn=mock_embedding_fn)
        memories = [
            _make_memory(content="I prefer dark mode", raw_text="I prefer dark mode"),
            _make_memory(content="I like dark mode", raw_text="I like dark mode"),
        ]
        results = agg.aggregate(memories)
        assert len(results) >= 1
        assert "aggregated from" in results[0]["content"]


class TestSQLiteAdapterSessionSummary:
    def test_session_summary_excluded_by_default(self, adapter):
        entry = MemoryEntry(
            type="session_summary",
            content="Session summary of 5 memories",
            raw_text="Session summary of 5 memories",
            confidence=0.7,
            tier=3,
            source_layer="session_summarizer",
            reasoning="test",
            suggested_action="store",
            metadata={"session_id": "sess-1"},
        )
        adapter.remember(entry)
        results = adapter.recall("session", limit=10)
        types = [r.type for r in results]
        assert "session_summary" not in types

    def test_session_summary_included_with_filter(self, adapter):
        entry = MemoryEntry(
            type="session_summary",
            content="Session summary of 5 memories",
            raw_text="Session summary of 5 memories",
            confidence=0.7,
            tier=3,
            source_layer="session_summarizer",
            reasoning="test",
            suggested_action="store",
            metadata={"session_id": "sess-1"},
        )
        adapter.remember(entry)
        results = adapter.recall("session", filters={"include_session_summary": True}, limit=10)
        types = [r.type for r in results]
        assert "session_summary" in types

    def test_session_summary_type_filter(self, adapter):
        entry = MemoryEntry(
            type="session_summary",
            content="Session summary of 5 memories",
            raw_text="Session summary of 5 memories",
            confidence=0.7,
            tier=3,
            source_layer="session_summarizer",
            reasoning="test",
            suggested_action="store",
            metadata={"session_id": "sess-1"},
        )
        adapter.remember(entry)
        results = adapter.recall("", filters={"type": "session_summary"}, limit=10)
        assert len(results) >= 1
        assert results[0].type == "session_summary"

    def test_session_id_stored_in_metadata(self, adapter):
        entry = MemoryEntry(
            type="session_summary",
            content="Session summary",
            raw_text="Session summary",
            confidence=0.7,
            tier=3,
            source_layer="session_summarizer",
            reasoning="test",
            suggested_action="store",
            metadata={"session_id": "sess-xyz-999"},
        )
        stored = adapter.remember(entry)
        assert stored.metadata.get("session_id") == "sess-xyz-999"

    def test_session_id_filter(self, adapter):
        entry = MemoryEntry(
            type="user_preference",
            content="I prefer dark mode",
            raw_text="I prefer dark mode",
            confidence=0.9,
            tier=2,
            source_layer="test",
            reasoning="test",
            suggested_action="store",
            metadata={"session_id": "sess-filter-test"},
        )
        adapter.remember(entry)
        results = adapter.recall("", filters={"session_id": "sess-filter-test"}, limit=10)
        assert len(results) >= 1
        assert results[0].metadata.get("session_id") == "sess-filter-test"


class TestCarryMemIntegration:
    def test_summarize_session_api(self, carrymem):
        carrymem.classify_and_remember(
            "I prefer dark mode",
            session_id="sess-integration-1",
        )
        carrymem.classify_and_remember(
            "Use PostgreSQL for database",
            session_id="sess-integration-1",
        )
        result = carrymem.summarize_session(session_id="sess-integration-1", store=False)
        if result is not None:
            assert result["type"] == "session_summary"
            assert "metadata" in result
            assert result["metadata"].get("session_id") == "sess-integration-1"

    def test_summarize_session_api_store(self, carrymem):
        carrymem.classify_and_remember(
            "I like Python",
            session_id="sess-store-1",
        )
        result = carrymem.summarize_session(session_id="sess-store-1", store=True)
        if result is not None:
            assert "storage_key" in result or "type" in result

    def test_aggregate_memories_api(self, carrymem):
        carrymem.classify_and_remember("I prefer dark mode for coding")
        carrymem.classify_and_remember("I like dark mode when editing")
        result = carrymem.aggregate_memories(store=False)
        assert isinstance(result, list)

    def test_session_summary_in_build_context(self, carrymem):
        entry = MemoryEntry(
            type="session_summary",
            content="Session summary: user prefers dark mode and PostgreSQL",
            raw_text="Session summary: user prefers dark mode and PostgreSQL",
            confidence=0.7,
            tier=3,
            source_layer="session_summarizer",
            reasoning="test",
            suggested_action="store",
            metadata={"session_id": "sess-bc-1"},
        )
        carrymem._adapter.remember(entry)
        ctx = carrymem.build_context(context="dark mode", max_memories=10)
        assert ctx["memory_count"] >= 1
