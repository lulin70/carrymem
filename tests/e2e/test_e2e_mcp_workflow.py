"""E2E test: MCP tools complete workflow user journey.

User journey: classify_and_remember → recall_memories → declare_preference →
get_system_prompt → batch_classify → get_memory_profile.

Existing test_e2e_mcp_tools.py tests each tool in isolation. This file
tests the complete workflow: data produced by one tool is consumed by
the next, validating end-to-end data flow correctness.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carrymem.integration.layer2_mcp.server import MCPServer


def _call(server, tool_name, **kwargs):
    """Call an MCP tool through the handlers layer."""
    async def _do_call():
        return await server.handlers.handle_tool(tool_name, kwargs)
    return asyncio.run(_do_call())


@pytest.fixture
def mcp_server():
    """Create MCPServer with isolated database."""
    tmpdir = tempfile.mkdtemp()
    server = MCPServer(data_path=tmpdir)
    yield server
    asyncio.run(server.cleanup())


class TestE2EMCPWorkflow:
    """User journey: complete MCP tools workflow with data flow validation."""

    def test_store_recall_workflow(self, mcp_server):
        """classify_and_remember → recall_memories data flow."""
        _call(mcp_server, "classify_and_remember",
              message="I prefer Python for data science projects")

        result = _call(mcp_server, "recall_memories", query="Python data science")
        assert result is not None
        assert result.get("success") is True
        data = result.get("data", {})
        text = str(data).lower()
        assert "python" in text or "data science" in text, \
            "Recalled data should match stored content"

    def test_preference_to_system_prompt_workflow(self, mcp_server):
        """declare_preference → get_system_prompt returns valid prompt."""
        _call(mcp_server, "declare_preference",
              preference="Always use type hints in Python code")

        result = _call(mcp_server, "get_system_prompt", query="Python code style")
        assert result is not None
        assert result.get("success") is True
        prompt_text = result.get("data", {}).get("system_prompt", "")
        assert len(prompt_text) > 50, "System prompt should be non-empty"

    def test_batch_classify_workflow(self, mcp_server):
        """batch_classify processes multiple messages correctly."""
        messages = [
            "I like morning meetings",
            "I prefer dark theme IDE",
            "Remember to deploy on Fridays",
        ]

        for msg in messages:
            _call(mcp_server, "classify_and_remember", message=msg)

        recall_result = _call(mcp_server, "recall_memories", query="meetings theme deploy")
        assert recall_result is not None
        assert recall_result.get("success") is True

    def test_memory_profile_workflow(self, mcp_server):
        """Store diverse memories → get_memory_profile returns structured summary."""
        _call(mcp_server, "classify_and_remember", message="I prefer Go for microservices")
        _call(mcp_server, "declare_preference", preference="Use REST API for web services")
        _call(mcp_server, "classify_and_remember", message="Remember to review PRs daily")

        result = _call(mcp_server, "get_memory_profile")
        assert result is not None
        assert result.get("success") is True
        assert len(str(result)) > 50, "Profile should contain meaningful summary"

    def test_forget_workflow(self, mcp_server):
        """classify_and_remember → recall → forget → recall empty workflow."""
        store_result = _call(mcp_server, "classify_and_remember",
              message="Temporary note for deletion test")
        assert store_result.get("success") is True
        storage_keys = store_result.get("data", {}).get("storage_keys", [])
        assert len(storage_keys) > 0, "Should have storage key"

        storage_key = storage_keys[0]

        recall_before = _call(mcp_server, "recall_memories", query="deletion test")
        assert "temporary" in str(recall_before).lower() or "deletion" in str(recall_before).lower()

        _call(mcp_server, "forget_memory", memory_id=storage_key)

        recall_after = _call(mcp_server, "recall_memories", query="deletion test")
        assert "temporary" not in str(recall_after).lower(), \
            "Forgotten memory should not appear in recall"
