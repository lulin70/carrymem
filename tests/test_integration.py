"""
Integration tests for MCP handlers and Obsidian adapter.

Covers:
- Obsidian adapter: vault indexing, recall (FTS5 search), incremental re-index
- MCP handlers: _safe_error, _clamp, _format_memory_entry
- MCP tools: tool names, classification schema
"""

import json
import os

import pytest

from carrymem.adapters.obsidian_adapter import ObsidianAdapter


@pytest.fixture
def obsidian_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    (vault / "note1.md").write_text("""---
tags: [project, carrymem]
status: active
---

# CarryMem Project

This is the main project note. We use Python and SQLite.
It supports MCP integration with Claude Code and Cursor.
""")

    (vault / "note2.md").write_text("""---
tags: [meeting, weekly]
---

# Weekly Standup

Discussed API design and security review.
Need to fix the authentication module.
""")

    (vault / "subdir").mkdir()
    (vault / "subdir" / "deep_note.md").write_text("""# Deep Note

This is in a subdirectory. Contains competitive analysis data.
""")

    return str(vault)


@pytest.fixture
def obsidian_db(tmp_path):
    return str(tmp_path / "obsidian_test.db")


@pytest.fixture
def adapter(obsidian_vault, obsidian_db):
    a = ObsidianAdapter(vault_path=obsidian_vault, db_path=obsidian_db)
    yield a
    a.close()


class TestObsidianAdapterIndexing:
    def test_index_vault(self, adapter):
        stats = adapter.index_vault()
        assert isinstance(stats, dict)
        assert stats.get("new", 0) + stats.get("skipped", 0) >= 2

    def test_incremental_index_skips_unchanged(self, adapter):
        adapter.index_vault()
        stats = adapter.index_vault()
        assert stats.get("skipped", 0) >= 2

    def test_index_new_file(self, adapter, obsidian_vault):
        adapter.index_vault()
        new_file = os.path.join(obsidian_vault, "new_note.md")
        with open(new_file, "w") as f:
            f.write("# New Note\n\nFresh content about testing.")
        stats = adapter.index_vault()
        assert stats.get("new", 0) >= 1

    def test_subdirectory_indexed(self, adapter):
        adapter.index_vault()
        results = adapter.recall("subdirectory")
        assert len(results) >= 1

    def test_empty_vault(self, tmp_path, obsidian_db):
        empty_vault = tmp_path / "empty_vault"
        empty_vault.mkdir()
        a = ObsidianAdapter(vault_path=str(empty_vault), db_path=obsidian_db)
        stats = a.index_vault()
        total = stats.get("new", 0) + stats.get("skipped", 0)
        assert total == 0
        a.close()


class TestObsidianAdapterRecall:
    def test_recall_by_keyword(self, adapter):
        adapter.index_vault()
        results = adapter.recall("Python SQLite")
        assert len(results) >= 1

    def test_recall_no_results(self, adapter):
        adapter.index_vault()
        results = adapter.recall("quantum computing xyz123")
        assert len(results) == 0

    def test_recall_by_tag_filter(self, adapter):
        adapter.index_vault()
        results = adapter.recall("carrymem", filters={"tags": "project"})
        assert len(results) >= 1

    def test_recall_limit(self, adapter):
        adapter.index_vault()
        results = adapter.recall("note", limit=1)
        assert len(results) <= 1

    def test_recall_returns_dicts(self, adapter):
        adapter.index_vault()
        results = adapter.recall("project")
        if results:
            result = results[0]
            assert isinstance(result, dict)
            assert "title" in result or "content" in result


class TestMCPHandlers:
    def test_safe_error_mapping(self):
        from carrymem.integration.layer2_mcp.handlers import _safe_error

        assert _safe_error(ValueError("test")) == "invalid_input"
        assert _safe_error(TypeError("test")) == "internal_error"

    def test_clamp(self):
        from carrymem.integration.layer2_mcp.handlers import _clamp

        assert _clamp(5, 0, 10) == 5
        assert _clamp(-1, 0, 10) == 0
        assert _clamp(15, 0, 10) == 10

    def test_format_memory_entry(self):
        from carrymem.integration.layer2_mcp.handlers import _format_memory_entry

        match = {
            "memory_type": "user_preference",
            "content": "I prefer dark mode",
            "confidence": 0.9,
            "tier": 1,
        }
        entry = _format_memory_entry(match, "I prefer dark mode")
        assert entry["type"] == "user_preference"
        assert entry["confidence"] == 0.9
        assert "id" in entry

    def test_format_memory_entry_low_confidence(self):
        from carrymem.integration.layer2_mcp.handlers import _format_memory_entry

        match = {
            "memory_type": "unknown",
            "content": "vague note",
            "confidence": 0.1,
            "tier": 3,
        }
        entry = _format_memory_entry(match, "vague note")
        assert entry["suggested_action"] == "ignore"


class TestMCPTools:
    def test_core_tools(self):
        from carrymem.integration.layer2_mcp.tools import CORE_TOOL_NAMES

        assert "classify_message" in CORE_TOOL_NAMES
        assert "get_classification_schema" in CORE_TOOL_NAMES
        assert "batch_classify" in CORE_TOOL_NAMES

    def test_optional_tools(self):
        from carrymem.integration.layer2_mcp.tools import OPTIONAL_TOOL_NAMES

        assert "classify_and_remember" in OPTIONAL_TOOL_NAMES
        assert "recall_memories" in OPTIONAL_TOOL_NAMES
        assert "forget_memory" in OPTIONAL_TOOL_NAMES

    def test_knowledge_tools(self):
        from carrymem.integration.layer2_mcp.tools import KNOWLEDGE_TOOL_NAMES

        assert "index_knowledge" in KNOWLEDGE_TOOL_NAMES
        assert "recall_from_knowledge" in KNOWLEDGE_TOOL_NAMES

    def test_profile_tools(self):
        from carrymem.integration.layer2_mcp.tools import PROFILE_TOOL_NAMES

        assert "declare_preference" in PROFILE_TOOL_NAMES
        assert "get_memory_profile" in PROFILE_TOOL_NAMES

    def test_prompt_tools(self):
        from carrymem.integration.layer2_mcp.tools import PROMPT_TOOL_NAMES

        assert "get_system_prompt" in PROMPT_TOOL_NAMES

    def test_classification_schema(self):
        from carrymem.integration.layer2_mcp.tools import CLASSIFICATION_SCHEMA

        assert "memory_types" in CLASSIFICATION_SCHEMA
        assert len(CLASSIFICATION_SCHEMA["memory_types"]) >= 7

    def test_tool_names_complete(self):
        from carrymem.integration.layer2_mcp.tools import TOOL_NAMES

        assert len(TOOL_NAMES) >= 10
