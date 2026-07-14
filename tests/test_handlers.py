"""
Tests for MCP handlers module - targeting uncovered code paths.

Covers: all handler functions, Handlers class, _safe_error,
_clamp, _format_memory_entry, _build_summary.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from carrymem import CarryMem
from carrymem.integration.layer2_mcp.handlers import (
    Handlers,
    _build_summary,
    _clamp,
    _format_memory_entry,
    _safe_error,
    handle_batch_classify,
    handle_classify_and_remember,
    handle_classify_message,
    handle_consolidate_memories,
    handle_declare_preference,
    handle_forget_memory,
    handle_get_classification_schema,
    handle_get_memory_impact,
    handle_get_memory_profile,
    handle_get_system_prompt,
    handle_index_knowledge,
    handle_mce_status,
    handle_query_graph,
    handle_recall_all,
    handle_recall_from_knowledge,
    handle_recall_memories,
    handle_shortest_path,
    handle_summarize_and_store,
    handler_map,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_handlers.db")


@pytest.fixture
def cm(temp_db):
    c = CarryMem(db_path=temp_db)
    yield c
    c.close()


@pytest.fixture
def engine():
    from carrymem.engine import MemoryClassificationEngine

    return MemoryClassificationEngine()


class TestSafeError:
    def test_storage_error(self):
        from carrymem.exceptions import StorageNotConfiguredError

        e = StorageNotConfiguredError()
        assert _safe_error(e) == "storage_not_configured"

    def test_value_error(self):
        assert _safe_error(ValueError("test")) == "invalid_input"

    def test_unknown_error(self):
        assert _safe_error(RuntimeError("test")) == "internal_error"


class TestClamp:
    def test_within_range(self):
        assert _clamp(5, 1, 10) == 5

    def test_below_min(self):
        assert _clamp(0, 1, 10) == 1

    def test_above_max(self):
        assert _clamp(20, 1, 10) == 10


class TestFormatMemoryEntry:
    def test_basic(self):
        match = {
            "memory_type": "user_preference",
            "content": "I prefer dark mode",
            "confidence": 0.9,
            "tier": 2,
            "source": "declaration",
            "reasoning": "User preference",
        }
        result = _format_memory_entry(match, "I prefer dark mode")
        assert result["type"] == "user_preference"
        assert result["content"] == "I prefer dark mode"
        assert result["confidence"] == 0.9
        assert result["suggested_action"] == "store"

    def test_low_confidence(self):
        match = {
            "type": "unknown",
            "content": "test",
            "confidence": 0.2,
            "tier": 3,
        }
        result = _format_memory_entry(match, "test")
        assert result["suggested_action"] == "ignore"

    def test_medium_confidence(self):
        match = {
            "type": "unknown",
            "content": "test",
            "confidence": 0.4,
            "tier": 3,
        }
        result = _format_memory_entry(match, "test")
        assert result["suggested_action"] == "defer"

    def test_no_content(self):
        match = {"confidence": 0.8, "tier": 2}
        result = _format_memory_entry(match, "original message here")
        assert result["content"] == "original message here"


class TestBuildSummary:
    def test_basic(self):
        entries = [
            {"type": "user_preference", "tier": 2, "confidence": 0.9},
            {"type": "decision", "tier": 1, "confidence": 0.7},
        ]
        result = _build_summary(entries, llm_calls=1)
        assert result["total_entries"] == 2
        assert result["by_type"]["user_preference"] == 1
        assert result["by_tier"][2] == 1
        assert result["llm_calls_used"] == 1

    def test_empty(self):
        result = _build_summary([])
        assert result["total_entries"] == 0
        assert result["avg_confidence"] == 0.0


class TestHandleClassifyMessage:
    def test_basic(self, engine):
        result = handle_classify_message(engine, {"message": "I prefer dark mode"})
        assert "schema_version" in result
        assert "entries" in result

    def test_empty_message(self, engine):
        result = handle_classify_message(engine, {"message": "  "})
        assert result["should_remember"] is False
        assert "error" in result

    def test_with_context(self, engine):
        result = handle_classify_message(
            engine,
            {
                "message": "I prefer dark mode",
                "context": "User is configuring editor",
            },
        )
        assert "entries" in result

    def test_exception_handling(self, engine):
        with patch.object(engine, "process_message", side_effect=RuntimeError("test")):
            result = handle_classify_message(engine, {"message": "test"})
            assert "error" in result


class TestHandleGetClassificationSchema:
    def test_json_format(self, engine):
        result = handle_get_classification_schema(engine, {"format": "json"})
        assert result["format"] == "json"
        assert "schema" in result

    def test_markdown_format(self, engine):
        result = handle_get_classification_schema(engine, {"format": "markdown"})
        assert result["format"] == "markdown"
        assert "MCE Classification Schema" in result["schema"]


class TestHandleBatchClassify:
    def test_basic(self, engine):
        result = handle_batch_classify(
            engine,
            {
                "messages": [
                    {"message": "I prefer dark mode"},
                    {"message": "I use Python"},
                ]
            },
        )
        assert "results" in result
        assert len(result["results"]) == 2

    def test_empty(self, engine):
        result = handle_batch_classify(engine, {"messages": []})
        assert "error" in result


class TestHandleMceStatus:
    def test_basic(self, engine):
        result = handle_mce_status(engine, {})
        assert result["status"] == "active"
        assert "version" in result


class TestHandleClassifyAndRemember:
    def test_basic(self, cm):
        result = handle_classify_and_remember(cm, {"message": "I prefer dark mode"})
        assert "should_remember" in result or "entries" in result or "error" not in result

    def test_empty_message(self, cm):
        result = handle_classify_and_remember(cm, {"message": "  "})
        assert "error" in result

    def test_with_context(self, cm):
        result = handle_classify_and_remember(
            cm,
            {
                "message": "I prefer dark mode",
                "context": "User settings",
            },
        )
        assert isinstance(result, dict)


class TestHandleRecallMemories:
    def test_basic(self, cm):
        cm.classify_and_remember("I prefer dark mode")
        result = handle_recall_memories(cm, {"query": "dark mode"})
        assert "memories" in result

    def test_with_limit(self, cm):
        result = handle_recall_memories(cm, {"limit": 5})
        assert "memories" in result

    def test_with_filters(self, cm):
        result = handle_recall_memories(
            cm,
            {
                "query": "dark mode",
                "filters": {"type": "user_preference"},
            },
        )
        assert "memories" in result

    def test_exception(self, cm):
        with patch.object(cm, "recall_memories", side_effect=RuntimeError("test")):
            result = handle_recall_memories(cm, {"query": "test"})
            assert "error" in result


class TestHandleForgetMemory:
    def test_basic(self, cm):
        cm.classify_and_remember("I prefer dark mode")
        memories = cm.recall_memories(limit=1)
        if memories:
            result = handle_forget_memory(cm, {"memory_id": memories[0]["storage_key"]})
            assert "deleted" in result

    def test_empty_id(self, cm):
        result = handle_forget_memory(cm, {"memory_id": ""})
        assert "error" in result

    def test_missing_id(self, cm):
        result = handle_forget_memory(cm, {})
        assert "error" in result

    def test_exception(self, cm):
        with patch.object(cm, "forget_memory", side_effect=RuntimeError("test")):
            result = handle_forget_memory(cm, {"memory_id": "some_key"})
            assert "error" in result


class TestHandleIndexKnowledge:
    def test_no_knowledge_adapter(self, cm):
        result = handle_index_knowledge(cm, {})
        assert "error" in result

    def test_exception(self, cm):
        with patch.object(cm, "index_knowledge", side_effect=RuntimeError("test")):
            result = handle_index_knowledge(cm, {})
            assert "error" in result


class TestHandleRecallFromKnowledge:
    def test_no_knowledge_adapter(self, cm):
        result = handle_recall_from_knowledge(cm, {"query": "test"})
        assert "error" in result

    def test_empty_query(self, cm):
        result = handle_recall_from_knowledge(cm, {"query": "  "})
        assert "error" in result

    def test_exception(self, cm):
        with patch.object(cm, "recall_from_knowledge", side_effect=RuntimeError("test")):
            result = handle_recall_from_knowledge(cm, {"query": "test"})
            assert "error" in result


class TestHandleRecallAll:
    def test_basic(self, cm):
        cm.classify_and_remember("I prefer dark mode")
        result = handle_recall_all(cm, {"query": "dark mode"})
        assert "memories" in result

    def test_empty_query(self, cm):
        result = handle_recall_all(cm, {"query": "  "})
        assert "error" in result

    def test_exception(self, cm):
        with patch.object(cm, "recall_all", side_effect=RuntimeError("test")):
            result = handle_recall_all(cm, {"query": "test"})
            assert "error" in result


class TestHandleDeclarePreference:
    def test_basic(self, cm):
        result = handle_declare_preference(cm, {"message": "I prefer dark mode"})
        assert "declared" in result or "entries" in result

    def test_empty_message(self, cm):
        result = handle_declare_preference(cm, {"message": "  "})
        assert "error" in result

    def test_exception(self, cm):
        with patch.object(cm, "declare", side_effect=RuntimeError("test")):
            result = handle_declare_preference(cm, {"message": "test"})
            assert "error" in result


class TestHandleGetMemoryProfile:
    def test_basic(self, cm):
        result = handle_get_memory_profile(cm, {})
        assert isinstance(result, dict)

    def test_exception(self, cm):
        with patch.object(cm, "get_memory_profile", side_effect=RuntimeError("test")):
            result = handle_get_memory_profile(cm, {})
            assert "error" in result


class TestHandleGetSystemPrompt:
    def test_basic(self, cm):
        result = handle_get_system_prompt(cm, {})
        assert "system_prompt" in result

    def test_with_language(self, cm):
        result = handle_get_system_prompt(cm, {"language": "en"})
        assert result["language"] == "en"

    def test_invalid_language(self, cm):
        result = handle_get_system_prompt(cm, {"language": "fr"})
        assert result["language"] == "en"

    def test_with_params(self, cm):
        result = handle_get_system_prompt(
            cm,
            {
                "max_memories": 5,
                "max_knowledge": 3,
                "language": "zh",
            },
        )
        assert "system_prompt" in result

    def test_exception(self, cm):
        with patch.object(cm, "build_system_prompt", side_effect=RuntimeError("test")):
            result = handle_get_system_prompt(cm, {})
            assert "error" in result


class TestHandlerMap:
    def test_all_handlers_present(self):
        expected = [
            "classify_message",
            "get_classification_schema",
            "batch_classify",
            "mce_status",
            "classify_and_remember",
            "recall_memories",
            "forget_memory",
            "index_knowledge",
            "recall_from_knowledge",
            "recall_all",
            "declare_preference",
            "get_memory_profile",
            "get_system_prompt",
            "summarize_and_store",
            "consolidate_memories",
        ]
        for name in expected:
            assert name in handler_map


class TestHandlersClass:
    @pytest.mark.asyncio
    async def test_init(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        assert handlers._carrymem is not None
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_classify(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "classify_message",
            {"message": "I prefer dark mode"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_recall(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        handlers._carrymem.classify_and_remember("I prefer dark mode")
        result = await handlers.handle_tool(
            "recall_memories",
            {"query": "dark mode"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_unknown(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool("unknown_tool", {})
        assert "error" in result
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_schema(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "get_classification_schema",
            {"format": "json"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_status(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool("mce_status", {})
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_batch(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "batch_classify",
            {"messages": [{"message": "I prefer dark mode"}]},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_forget(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "forget_memory",
            {"memory_id": "nonexistent"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_declare(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "declare_preference",
            {"message": "I prefer dark mode"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_profile(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool("get_memory_profile", {})
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_system_prompt(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool("get_system_prompt", {})
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_knowledge(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "index_knowledge",
            {},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_recall_from_knowledge(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "recall_from_knowledge",
            {"query": "test"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tool_recall_all(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        result = await handlers.handle_tool(
            "recall_all",
            {"query": "test"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup(self, temp_db):
        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            namespace="default",
        )
        handlers.cleanup()

    # ── P0-2 regression: suggest_rules / promote_rules get _carrymem ──

    @pytest.mark.asyncio
    async def test_suggest_rules_gets_carrymem_injected(self, temp_db):
        """P0-2: dispatcher must inject _carrymem so suggest_rules works."""
        handlers = Handlers(storage="sqlite", data_path=temp_db)
        # Store a memory so there's something to analyze
        handlers._carrymem.classify_and_remember("I prefer Python over Java")
        result = await handlers.handle_tool("suggest_rules", {})
        assert result.get("success") is True
        data = result.get("data", {})
        # Should NOT return the old error about missing CarryMem instance
        assert "No CarryMem instance" not in str(data.get("error", ""))
        assert "suggestions" in data or "total" in data
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_promote_rules_gets_carrymem_injected(self, temp_db):
        """P0-2: dispatcher must inject _carrymem so promote_rules works."""
        handlers = Handlers(storage="sqlite", data_path=temp_db)
        handlers._carrymem.classify_and_remember("I prefer dark mode")
        result = await handlers.handle_tool("promote_rules", {})
        assert result.get("success") is True
        data = result.get("data", {})
        assert "No CarryMem instance" not in str(data.get("error", ""))
        handlers.cleanup()

    # ── P0-3 regression: health_check reads audit from adapter._audit ──

    @pytest.mark.asyncio
    async def test_health_check_audit_from_adapter(self, temp_db):
        """P0-3: health_check must read _audit from carrymem._adapter, not carrymem."""
        handlers = Handlers(storage="sqlite", data_path=temp_db)
        # Perform a write so audit logger has at least one event
        handlers._carrymem.classify_and_remember("I prefer tea over coffee")
        result = await handlers.handle_tool("health_check", {})
        assert result.get("success") is True
        data = result.get("data", {})
        audit = data.get("audit", {})
        # Audit should have actual stats, not just {"status": "not_available"}
        # (The SQLite adapter initializes _audit as AuditLogger on first use)
        assert "status" not in audit or audit.get("status") != "not_available"
        # Should have audit stats keys like total_events
        assert "total_events" in audit or "by_action" in audit
        handlers.cleanup()

    # ── P0-1 regression: default_user_id injection for write handlers ──

    @pytest.mark.asyncio
    async def test_default_user_id_injected_for_write(self, temp_db):
        """P0-1: when default_user_id is set, write handlers should pass it through."""
        from carrymem.security.permissions import AccessPolicy

        handlers = Handlers(
            storage="sqlite",
            data_path=temp_db,
            default_user_id="alice",
        )
        handlers._carrymem.access_policy = AccessPolicy(owner_id="alice")
        result = await handlers.handle_tool(
            "classify_and_remember",
            {"message": "I prefer dark mode"},
        )
        assert result.get("success") is True
        handlers.cleanup()

    @pytest.mark.asyncio
    async def test_write_blocked_without_user_id_when_policy_set(self, temp_db):
        """P0-1: without default_user_id, writes should fail when policy is configured."""
        from carrymem.security.permissions import AccessPolicy

        handlers = Handlers(storage="sqlite", data_path=temp_db)
        handlers._carrymem.access_policy = AccessPolicy(owner_id="alice")
        result = await handlers.handle_tool(
            "classify_and_remember",
            {"message": "I prefer dark mode"},
        )
        # The handler should catch the SecurityError and return error
        data = result.get("data", result)
        assert result.get("success") is False or "error" in data
        handlers.cleanup()


class TestHandleSummarizeAndStore:
    def test_no_session_id(self, cm):
        result = handle_summarize_and_store(cm, {})
        assert "error" in result
        assert "session_id" in result["error"]

    def test_no_memories_for_session(self, cm):
        result = handle_summarize_and_store(cm, {"session_id": "nonexistent"})
        assert result["action"] == "no_content"
        assert result["session_id"] == "nonexistent"

    def test_returns_content_for_summarization(self, cm):
        cm.classify_and_remember(
            "I prefer dark mode for coding",
            session_id="sess-1",
        )
        cm.classify_and_remember(
            "I decided to use PostgreSQL for the project",
            session_id="sess-1",
        )
        result = handle_summarize_and_store(cm, {"session_id": "sess-1"})
        assert result["action"] == "summarize"
        assert result["session_id"] == "sess-1"
        assert "content" in result
        assert result["memory_count"] >= 1
        assert "instruction" in result

    def test_max_tokens_limit(self, cm):
        cm.classify_and_remember(
            "I prefer dark mode",
            session_id="sess-2",
        )
        result = handle_summarize_and_store(
            cm,
            {"session_id": "sess-2", "max_tokens": 100},
        )
        assert result["action"] == "summarize"

    def test_namespace_passed(self, cm):
        cm.classify_and_remember(
            "I like Python",
            session_id="sess-3",
        )
        result = handle_summarize_and_store(
            cm,
            {"session_id": "sess-3", "namespace": "work"},
        )
        assert result["namespace"] == "work"


class TestHandleConsolidateMemories:
    def test_dry_run_default(self, cm):
        result = handle_consolidate_memories(cm, {})
        assert result.get("dry_run") is True or "dry_run" not in result or result.get("dry_run") is None

    def test_dry_run_true(self, cm):
        cm.classify_and_remember("I prefer Python")
        result = handle_consolidate_memories(cm, {"dry_run": True})
        assert "input_count" in result

    def test_dry_run_false(self, cm):
        cm.classify_and_remember("I prefer Python")
        result = handle_consolidate_memories(cm, {"dry_run": False})
        assert "input_count" in result

    def test_error_handling(self):
        mock_cm = MagicMock()
        mock_cm.consolidate.side_effect = RuntimeError("test error")
        result = handle_consolidate_memories(mock_cm, {"dry_run": True})
        assert "error" in result


class TestGraphToolHandlers:
    """Tests for graph tool handlers (v0.8.0).

    Covers handle_query_graph, handle_shortest_path, handle_get_memory_impact
    and their registration in handler_map.
    """

    def test_handle_query_graph(self, cm):
        """Verify: handle_query_graph returns entities and memories fields."""
        result = handle_query_graph(cm, {"entity_text": "Python"})

        assert "entities" in result
        assert "memories" in result

    def test_handle_shortest_path(self, cm):
        """Verify: handle_shortest_path returns path, length, found fields."""
        result = handle_shortest_path(cm, {"src_entity": "A", "dst_entity": "B"})

        assert "path" in result
        assert "length" in result
        assert "found" in result

    def test_handle_get_memory_impact(self, cm):
        """Verify: handle_get_memory_impact returns impact fields."""
        result = handle_get_memory_impact(cm, {"memory_id": "some_key"})

        assert "entity_count" in result
        assert "relation_count" in result
        assert "impact_score" in result

    def test_handler_map_includes_graph_tools(self):
        """Verify: handler_map includes query_graph, shortest_path, get_memory_impact."""
        assert "query_graph" in handler_map
        assert "shortest_path" in handler_map
        assert "get_memory_impact" in handler_map
