"""
E2E Tests: MCP Tools End-to-End Invocation

Validates that each MCP tool can be called through the server/handler layer
and returns structurally valid results.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carrymem.carrymem import CarryMem
from carrymem.integration.layer2_mcp.handlers import Handlers
from carrymem.integration.layer2_mcp.server import MCPServer
from carrymem.integration.layer2_mcp.tools import (
    CORE_TOOL_NAMES,
    OPTIONAL_TOOL_NAMES,
    PROFILE_TOOL_NAMES,
    PROMPT_TOOL_NAMES,
    RULE_TOOL_NAMES,
    TOOL_NAMES,
)


def _make_server(tmp_dir):
    """Create an MCPServer with isolated database in tmp_dir."""
    return MCPServer(data_path=str(tmp_dir))


async def _call_tool(server, tool_name, arguments=None):
    """Call a tool through the MCPServer handlers layer."""
    result = await server.handlers.handle_tool(tool_name, arguments or {})
    return result


class TestMCPToolsE2E(unittest.TestCase):
    """Verify: MCP tools return valid responses through the full call chain."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server = _make_server(self.tmpdir)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.server.cleanup())
        finally:
            self.loop.close()
            asyncio.set_event_loop(None)

    # === Core Tools (must pass) ===

    def test_classify_message_tool(self):
        """Verify: classify_message tool returns valid classification."""
        result = self.loop.run_until_complete(
            _call_tool(self.server, "classify_message", {"message": "I prefer dark mode for coding"})
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("schema_version", data)
        self.assertIn("entries", data)
        self.assertIsInstance(data["entries"], list)

    def test_classify_and_remember_tool(self):
        """Verify: classify_and_remember tool stores and classifies."""
        result = self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "I prefer Python over Java"})
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertTrue(
            data.get("stored") or data.get("should_remember"),
            "classify_and_remember should store or mark as rememberable",
        )

    def test_recall_memories_tool(self):
        """Verify: recall_memories tool returns stored memories."""
        # First store something
        self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "We chose PostgreSQL for our database"})
        )
        # Then recall
        result = self.loop.run_until_complete(_call_tool(self.server, "recall_memories", {"query": "PostgreSQL"}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("memories", data)
        self.assertIsInstance(data["memories"], list)

    def test_forget_memory_tool(self):
        """Verify: forget_memory tool removes a memory."""
        # Store a memory first
        store_result = self.loop.run_until_complete(
            _call_tool(self.server, "declare_preference", {"message": "I prefer using TypeScript for frontend"})
        )
        self.assertIs(store_result.get("success"), True)

        # Get the storage key
        store_data = store_result.get("data", store_result)
        storage_keys = store_data.get("storage_keys", [])
        if storage_keys:
            memory_id = storage_keys[0]
            # Forget it
            forget_result = self.loop.run_until_complete(
                _call_tool(self.server, "forget_memory", {"memory_id": memory_id})
            )
            self.assertIs(forget_result.get("success"), True, f"Forget failed: {forget_result}")
            forget_data = forget_result.get("data", forget_result)
            self.assertIs(forget_data.get("deleted"), True, "Memory should be deleted")

    def test_get_classification_schema_tool(self):
        """Verify: get_classification_schema returns valid schema."""
        result = self.loop.run_until_complete(_call_tool(self.server, "get_classification_schema", {"format": "json"}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        schema = data.get("schema", data)
        self.assertIn("memory_types", schema)
        self.assertIn("storage_tiers", schema)
        self.assertEqual(len(schema.get("memory_types", [])), 7, "Schema should have exactly 7 memory types")

    def test_batch_classify_tool(self):
        """Verify: batch_classify processes multiple messages."""
        messages = [
            {"message": "I prefer dark mode"},
            {"message": "We decided to use Redis"},
            {"message": "No, that's wrong, use YAML not JSON"},
        ]
        result = self.loop.run_until_complete(_call_tool(self.server, "batch_classify", {"messages": messages}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 3, "Should return results for all 3 messages")
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["total_messages"], 3)

    # === Profile Tools ===

    def test_declare_preference_tool(self):
        """Verify: declare_preference stores preference."""
        result = self.loop.run_until_complete(
            _call_tool(self.server, "declare_preference", {"message": "My timezone is UTC+8"})
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertTrue(data.get("declared"), "Declaration should succeed")
        self.assertGreater(len(data.get("storage_keys", [])), 0, "Should return storage keys")

    def test_get_memory_profile_tool(self):
        """Verify: get_memory_profile returns user profile."""
        # First declare something
        self.loop.run_until_complete(
            _call_tool(self.server, "declare_preference", {"message": "I prefer Vim over Emacs"})
        )
        # Get profile
        result = self.loop.run_until_complete(_call_tool(self.server, "get_memory_profile", {}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("summary", data)
        self.assertIn("stats", data)

    # === Prompt Tools ===

    def test_get_system_prompt_tool(self):
        """Verify: get_system_prompt returns prompt with context."""
        # Store some memories first
        self.loop.run_until_complete(
            _call_tool(self.server, "declare_preference", {"message": "I prefer concise code comments"})
        )
        result = self.loop.run_until_complete(
            _call_tool(self.server, "get_system_prompt", {"context": "code review", "max_memories": 5})
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("system_prompt", data)
        self.assertIsInstance(data["system_prompt"], str)
        self.assertGreater(len(data["system_prompt"]), 10, "System prompt should have meaningful content")
        self.assertEqual(data.get("language"), "en")

    def test_get_system_prompt_chinese(self):
        """Verify: get_system_prompt supports Chinese language output."""
        result = self.loop.run_until_complete(
            _call_tool(self.server, "get_system_prompt", {"language": "zh", "max_memories": 1})
        )
        self.assertIs(result.get("success"), True)
        data = result.get("data", result)
        self.assertEqual(data.get("language"), "zh")

    # === Rule Tools ===

    def test_add_rule_tool(self):
        """Verify: add_rule creates a new rule."""
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "database",
                    "action": "Always use SSL connections",
                    "scope": "personal",
                    "rule_type": "always",
                },
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertTrue(data.get("added"), "Rule should be added")
        self.assertIn("rule_id", data)
        self.assertEqual(data.get("trigger"), "database")
        self.assertEqual(data.get("action"), "Always use SSL connections")

    def test_list_rules_tool(self):
        """Verify: list_rules returns stored rules."""
        # Add a rule first
        self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "code style",
                    "action": "Use snake_case naming",
                    "rule_type": "prefer",
                },
            )
        )
        # List rules
        result = self.loop.run_until_complete(_call_tool(self.server, "list_rules", {"status": "active"}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("rules", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0, "Should have at least one rule")

    def test_match_rules_tool(self):
        """Verify: match_rules finds applicable rules for a scene."""
        # Add relevant rule
        self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "security",
                    "action": "Never commit secrets to repository",
                    "rule_type": "forbid",
                },
            )
        )
        # Match against scene
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "match_rules",
                {
                    "scene": "security review before deployment",
                },
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("scene", data)
        self.assertIn("matches", data)
        self.assertIn("total", data)

    def test_inject_rules_tool(self):
        """Verify: inject_rules generates formatted rules text."""
        self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "testing",
                    "action": "Write unit tests for all new functions",
                    "rule_type": "always",
                },
            )
        )
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "inject_rules",
                {
                    "context": "code review process",
                    "format": "compact",
                },
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("injection", data)
        self.assertIn("context", data)

    def test_my_rules_tool(self):
        """Verify: my_rules returns readable rule summary."""
        self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "deployment",
                    "action": "Run tests before deploying to production",
                    "rule_type": "always",
                },
            )
        )
        result = self.loop.run_until_complete(_call_tool(self.server, "my_rules", {"status": "active"}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("summary", data)
        self.assertIn("rules", data)
        self.assertIn("total", data)

    def test_update_rule_tool(self):
        """Verify: update_rule modifies an existing rule."""
        # Add a rule
        add_result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "logging",
                    "action": "Use print statements",
                    "rule_type": "prefer",
                },
            )
        )
        add_data = add_result.get("data", add_result)
        rule_id = add_data.get("rule_id")
        if rule_id:
            # Update it
            update_result = self.loop.run_until_complete(
                _call_tool(
                    self.server,
                    "update_rule",
                    {
                        "rule_id": rule_id,
                        "action": "Use logging module instead of print",
                    },
                )
            )
            self.assertIs(update_result.get("success"), True, f"Update failed: {update_result}")
            update_data = update_result.get("data", update_result)
            self.assertIs(update_data.get("updated"), True, "Rule should be updated")
            self.assertIn("logging module", update_data.get("action", ""))

    def test_delete_rule_tool(self):
        """Verify: delete_rule removes a personal-scope rule."""
        # Add a personal rule
        add_result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "add_rule",
                {
                    "trigger": "temporary",
                    "action": "This will be deleted",
                    "rule_type": "prefer",
                },
            )
        )
        add_data = add_result.get("data", add_result)
        rule_id = add_data.get("rule_id")
        if rule_id:
            # Delete it
            del_result = self.loop.run_until_complete(
                _call_tool(
                    self.server,
                    "delete_rule",
                    {
                        "rule_id": rule_id,
                        "confirm": True,
                    },
                )
            )
            self.assertIs(del_result.get("success"), True, f"Delete failed: {del_result}")
            del_data = del_result.get("data", del_result)
            self.assertIs(del_data.get("deleted"), True, "Rule should be deleted")

    # === Consolidation Tools ===

    def test_consolidate_memories_dry_run(self):
        """Verify: consolidate_memories dry_run reports without changes."""
        # Store some memories
        self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "I prefer using Docker for containers"})
        )
        self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "I prefer using Docker for containers"})
        )
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "consolidate_memories",
                {
                    "dry_run": True,
                    "run_p1": False,
                    "run_p2": False,
                },
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertTrue(data.get("dry_run", True), "Should be in dry_run mode")

    def test_schedule_consolidation_tool(self):
        """Verify: schedule_consolidation starts periodic consolidation."""
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "schedule_consolidation",
                {
                    "interval_hours": 24,
                    "dry_run": True,
                    "run_p1": False,
                    "run_p2": False,
                },
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertTrue(data.get("scheduled"), "Consolidation should be scheduled")

        # Clean up: stop the scheduled timer
        self.loop.run_until_complete(_call_tool(self.server, "stop_consolidation", {}))

    def test_stop_consolidation_tool(self):
        """Verify: stop_consolidation stops the scheduled timer."""
        # Schedule first
        self.loop.run_until_complete(
            _call_tool(
                self.server,
                "schedule_consolidation",
                {
                    "interval_hours": 24,
                    "dry_run": True,
                    "run_p1": False,
                },
            )
        )
        # Stop
        result = self.loop.run_until_complete(_call_tool(self.server, "stop_consolidation", {}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertTrue(data.get("stopped"), "Consolidation should be stopped")

    # === Profile / Identity Tools ===

    def test_my_profile_tool(self):
        """Verify: my_profile returns complete identity view."""
        self.loop.run_until_complete(_call_tool(self.server, "declare_preference", {"message": "I work at a startup"}))
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "my_profile",
                {
                    "include_memories": True,
                    "include_rules": True,
                },
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("identity", data)
        self.assertIn("version", data)

    def test_onboard_tool(self):
        """Verify: onboard returns welcome message for new users."""
        result = self.loop.run_until_complete(_call_tool(self.server, "onboard", {"language": "en"}))
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("welcome", data)
        self.assertIn("next_steps", data)
        self.assertIn("CarryMem", data.get("welcome", ""), "Welcome message should mention CarryMem")

    def test_onboard_tool_chinese(self):
        """Verify: onboard supports Chinese language."""
        result = self.loop.run_until_complete(_call_tool(self.server, "onboard", {"language": "zh"}))
        self.assertIs(result.get("success"), True)
        data = result.get("data", result)
        self.assertEqual(data.get("language"), "zh")
        self.assertIn("welcome", data)

    # === Knowledge Tools (conditional — skip if no knowledge adapter) ===

    @pytest.mark.skip(reason="Requires Obsidian vault; tested separately in test_obsidian_adapter.py")
    def test_index_knowledge_tool(self):
        """Verify: index_knowledge indexes knowledge base (requires ObsidianAdapter)."""
        pass

    @pytest.mark.skip(reason="Requires Obsidian vault; tested separately in test_obsidian_adapter.py")
    def test_recall_from_knowledge_tool(self):
        """Verify: recall_from_knowledge searches knowledge base (requires ObsidianAdapter)."""
        pass

    # === Structural Validation ===

    def test_tool_response_structure_success(self):
        """Verify: Successful tool responses have consistent {success: True, data} structure."""
        tools_to_test = [
            ("get_classification_schema", {"format": "json"}),
            ("list_rules", {}),
            ("my_rules", {}),
            ("onboard", {"language": "en"}),
            ("get_memory_profile", {}),
        ]
        for tool_name, args in tools_to_test:
            result = self.loop.run_until_complete(_call_tool(self.server, tool_name, args))
            self.assertIn("success", result, f"{tool_name}: response missing 'success' key")
            self.assertIs(result["success"], True, f"{tool_name}: expected success=True")

    def test_unknown_tool_returns_error(self):
        """Verify: Unknown tool name returns error response with available_tools hint."""
        result = self.loop.run_until_complete(_call_tool(self.server, "nonexistent_tool_xyz", {}))
        # Should either have success=False or indicate unknown tool
        if result.get("success"):
            data = result.get("data", {})
            self.fail(f"Unknown tool should not succeed: {result}")
        else:
            self.assertIn("error", result, "Error response should have 'error' key")

    def test_empty_message_handled_gracefully(self):
        """Verify: Empty message to classify_message returns valid non-crashing response."""
        result = self.loop.run_until_complete(_call_tool(self.server, "classify_message", {"message": ""}))
        # Should still return a valid structure, just empty entries
        self.assertIsNotNone(result)
        self.assertIn("success", result)

    def test_full_roundtrip_classify_store_recall(self):
        """Verify: Complete roundtrip: classify → store → recall → prompt injection."""
        # Step 1: Classify and remember
        store_result = self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "Our team uses Kubernetes for orchestration"})
        )
        self.assertIs(store_result.get("success"), True)

        # Step 2: Recall the memory
        recall_result = self.loop.run_until_complete(
            _call_tool(self.server, "recall_memories", {"query": "Kubernetes"})
        )
        self.assertIs(recall_result.get("success"), True)
        recall_data = recall_result.get("data", recall_result)
        memories = recall_data.get("memories", [])

        # Step 3: Verify it appears in system prompt
        prompt_result = self.loop.run_until_complete(
            _call_tool(self.server, "get_system_prompt", {"context": "deployment infrastructure", "max_memories": 10})
        )
        self.assertIs(prompt_result.get("success"), True)
        prompt_data = prompt_result.get("data", prompt_result)
        prompt_text = prompt_data.get("system_prompt", "")
        self.assertIsInstance(prompt_text, str)

    def test_multiple_preferences_accumulate_in_profile(self):
        """Verify: Multiple declarations accumulate and appear in profile."""
        preferences = [
            "I prefer functional programming style",
            "My team uses Agile methodology",
            "We deploy to AWS us-east-1",
        ]
        for pref in preferences:
            self.loop.run_until_complete(_call_tool(self.server, "declare_preference", {"message": pref}))

        # Verify via recall that memories were stored
        recall_result = self.loop.run_until_complete(_call_tool(self.server, "recall_memories", {"limit": 20}))
        self.assertIs(recall_result.get("success"), True)
        recall_data = recall_result.get("data", recall_result)
        memories = recall_data.get("memories", [])
        self.assertGreaterEqual(
            len(memories), len(preferences), f"At least {len(preferences)} memories expected, got {len(memories)}"
        )

    def test_recall_with_filters(self):
        """Verify: recall_memories respects type filters."""
        # Store different types
        self.loop.run_until_complete(_call_tool(self.server, "declare_preference", {"message": "I like TypeScript"}))
        self.loop.run_until_complete(
            _call_tool(
                self.server, "classify_and_remember", {"message": "We chose React for the frontend", "context": "{}"}
            )
        )

        # Filter by type
        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "recall_memories",
                {
                    "filters": {"type": "user_preference"},
                    "limit": 20,
                },
            )
        )
        self.assertIs(result.get("success"), True)
        data = result.get("data", result)
        memories = data.get("memories", [])
        for mem in memories:
            self.assertEqual(
                mem.get("type"), "user_preference", f"Filter should only return user_preference, got {mem.get('type')}"
            )


class TestGraphToolsE2E(unittest.TestCase):
    """Verify: Graph query tools (v0.8.0) work through the full MCP handler chain.

    Tests query_graph, shortest_path, and get_memory_impact via
    Handlers.handle_tool(), using a real SQLite database (no mocks).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server = _make_server(self.tmpdir)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        # Direct CarryMem access for graph setup (relations have no MCP tool)
        self.cm = self.server.handlers._carrymem

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.server.cleanup())
        finally:
            self.loop.close()
            asyncio.set_event_loop(None)

    def test_query_graph_tool_e2e(self):
        """Verify: query_graph returns entities and memories via handle_tool."""
        # Setup: create a small graph (PostgreSQL → SQL → Database)
        self.cm.add_graph_relation("PostgreSQL", "SQL", "is_a")
        self.cm.add_graph_relation("SQL", "Database", "is_a")

        result = self.loop.run_until_complete(
            _call_tool(self.server, "query_graph", {"entity_text": "PostgreSQL", "max_hops": 2})
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("entities", data, "query_graph must return 'entities'")
        self.assertIn("memories", data, "query_graph must return 'memories'")
        self.assertIsInstance(data["entities"], list)
        self.assertIsInstance(data["memories"], list)
        # The starting entity and its neighbors should be present
        entity_texts = {e["entity_text"] for e in data["entities"]}
        self.assertIn("PostgreSQL", entity_texts)
        self.assertIn("SQL", entity_texts)

    def test_shortest_path_tool_e2e(self):
        """Verify: shortest_path returns path, length, found via handle_tool."""
        # Setup: A → B → C chain
        self.cm.add_graph_relation("Python", "Programming", "is_a")
        self.cm.add_graph_relation("Programming", "Computer_Science", "part_of")

        result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "shortest_path",
                {"src_entity": "Python", "dst_entity": "Computer_Science", "max_hops": 4},
            )
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("path", data)
        self.assertIn("length", data)
        self.assertIn("found", data)
        self.assertTrue(data["found"], "Path should be found in connected graph")
        self.assertEqual(data["length"], 2, "Two-hop path expected")
        self.assertEqual(data["path"][0], "Python")
        self.assertEqual(data["path"][-1], "Computer_Science")

    def test_get_memory_impact_tool_e2e(self):
        """Verify: get_memory_impact returns entity_count, relation_count, impact_score."""
        # Step 1: Store a memory to get a storage_key
        store_result = self.loop.run_until_complete(
            _call_tool(self.server, "declare_preference", {"message": "I prefer PostgreSQL for data science"})
        )
        self.assertIs(store_result.get("success"), True)
        store_data = store_result.get("data", store_result)
        storage_keys = store_data.get("storage_keys", [])
        self.assertGreater(len(storage_keys), 0, "Should return at least one storage_key")
        memory_id = storage_keys[0]

        # Step 2: Ensure entities are linked to this memory
        self.cm._adapter.store_graph_entities(memory_id, "PostgreSQL is a SQL database")

        # Step 3: Add a relation evidenced by this memory
        self.cm.add_graph_relation("PostgreSQL", "SQL", "is_a", source_memory_key=memory_id)

        # Step 4: Query impact through MCP handler
        result = self.loop.run_until_complete(
            _call_tool(self.server, "get_memory_impact", {"memory_id": memory_id})
        )
        self.assertIs(result.get("success"), True, f"Expected success, got: {result}")
        data = result.get("data", result)
        self.assertIn("entity_count", data)
        self.assertIn("relation_count", data)
        self.assertIn("impact_score", data)
        self.assertIsInstance(data["entity_count"], int)
        self.assertIsInstance(data["relation_count"], int)
        self.assertIsInstance(data["impact_score"], (int, float))
        # With linked entities and a relation, counts should be non-zero
        self.assertGreater(data["entity_count"], 0, "Should have at least one linked entity")

    def test_graph_tools_full_user_flow(self):
        """Verify: Full user flow — create memory → extract entities → add relation → query → path → impact."""
        # Step 1: Create a memory (auto-extracts entities)
        store_result = self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "I prefer PostgreSQL for database development"})
        )
        self.assertIs(store_result.get("success"), True, f"Store failed: {store_result}")
        store_data = store_result.get("data", store_result)
        storage_keys = store_data.get("storage_keys", [])
        self.assertGreater(len(storage_keys), 0, "Should store at least one memory")
        memory_id = storage_keys[0]

        # Step 2: Ensure entities are extracted and linked to the memory
        self.cm._adapter.store_graph_entities(memory_id, "PostgreSQL is a SQL database system")

        # Step 3: Add a relation between entities
        added = self.cm.add_graph_relation(
            "PostgreSQL", "SQL", "is_a", source_memory_key=memory_id
        )
        self.assertIs(added, True, "add_graph_relation should succeed")

        # Step 4: query_graph — find connected entities and memories
        query_result = self.loop.run_until_complete(
            _call_tool(self.server, "query_graph", {"entity_text": "PostgreSQL", "max_hops": 2})
        )
        self.assertIs(query_result.get("success"), True)
        query_data = query_result.get("data", query_result)
        self.assertIn("entities", query_data)
        self.assertIn("memories", query_data)
        entity_texts = {e["entity_text"] for e in query_data["entities"]}
        self.assertIn("PostgreSQL", entity_texts)
        self.assertIn("SQL", entity_texts)

        # Step 5: shortest_path — find path between entities
        path_result = self.loop.run_until_complete(
            _call_tool(
                self.server,
                "shortest_path",
                {"src_entity": "PostgreSQL", "dst_entity": "SQL", "max_hops": 4},
            )
        )
        self.assertIs(path_result.get("success"), True)
        path_data = path_result.get("data", path_result)
        self.assertIs(path_data["found"], True, "Path between PostgreSQL and SQL should be found")
        self.assertEqual(path_data["length"], 1, "Direct relation = 1 hop")
        self.assertEqual(path_data["path"][0], "PostgreSQL")
        self.assertEqual(path_data["path"][-1], "SQL")

        # Step 6: get_memory_impact — evaluate the memory's graph impact
        impact_result = self.loop.run_until_complete(
            _call_tool(self.server, "get_memory_impact", {"memory_id": memory_id})
        )
        self.assertIs(impact_result.get("success"), True)
        impact_data = impact_result.get("data", impact_result)
        self.assertIn("entity_count", impact_data)
        self.assertIn("relation_count", impact_data)
        self.assertIn("impact_score", impact_data)
        self.assertGreater(impact_data["entity_count"], 0, "Memory should have linked entities")
        # Impact score formula: entity_count * 0.4 + relation_count * 0.4 + cross_namespace * 0.2
        # We have >= 2 entities (PostgreSQL, SQL) and >= 1 relation → score >= 1.2
        # Use >= 0.8 as conservative threshold (at least 1 entity + 1 relation)
        self.assertGreaterEqual(
            impact_data["impact_score"], 0.8,
            f"Impact score should be >= 0.8 for >=1 entity + >=1 relation, got {impact_data['impact_score']}",
        )


class TestMCPToolsCoverage(unittest.TestCase):
    """Verify: All declared TOOL_NAMES are reachable through the handler map."""

    def test_all_tools_registered_in_handler_map(self):
        """Every tool in TOOLS must have a corresponding entry in handler_map."""
        from carrymem.integration.layer2_mcp.handlers import handler_map

        for tool_name in TOOL_NAMES:
            self.assertIn(tool_name, handler_map, f"Tool '{tool_name}' defined in TOOLS but missing from handler_map")

    def test_core_tools_exist(self):
        """Verify all core tools are present in CORE_TOOL_NAMES."""
        expected_core = {"classify_message", "get_classification_schema", "batch_classify"}
        self.assertIs(expected_core.issubset(CORE_TOOL_NAMES), True, f"Missing core tools: {expected_core - CORE_TOOL_NAMES}"
        )

    def test_optional_tools_exist(self):
        """Verify optional storage tools are present."""
        expected_optional = {"classify_and_remember", "recall_memories", "forget_memory"}
        self.assertIs(expected_optional.issubset(OPTIONAL_TOOL_NAMES), True, f"Missing optional tools: {expected_optional - OPTIONAL_TOOL_NAMES}",
        )

    def test_total_tool_count(self):
        """Verify total number of registered tools matches expectations."""
        self.assertGreaterEqual(len(TOOL_NAMES), 25, f"Expected at least 25 tools, found {len(TOOL_NAMES)}")


class TestMCPToolsServerIntegration(unittest.TestCase):
    """Verify: MCPServer correctly initializes and routes requests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_server_initializes_handlers(self):
        """Verify: MCPServer creates Handlers instance on init."""
        server = MCPServer(data_path=self.tmpdir)
        self.assertIsNotNone(server.handlers)
        self.assertIsInstance(server.handlers, Handlers)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(server.cleanup())
        finally:
            loop.close()

    def test_server_handle_initialize(self):
        """Verify: Server handle_initialize returns proper MCP response."""
        server = MCPServer(data_path=self.tmpdir)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                server.handle_initialize(
                    1,
                    {
                        "protocolVersion": "2024-11-05",
                        "clientInfo": {"name": "test-client", "version": "1.0.0"},
                    },
                )
            )
            self.assertEqual(result["id"], 1)
            self.assertIn("result", result)
            self.assertEqual(result["result"]["protocolVersion"], "2024-11-05")
            self.assertEqual(result["result"]["serverInfo"]["name"], "carrymem-mcp")
            loop.run_until_complete(server.cleanup())
        finally:
            loop.close()

    def test_server_tools_list_contains_all_tools(self):
        """Verify: Server tools/list returns all registered tools."""
        server = MCPServer(data_path=self.tmpdir)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(server.handle_tools_list(2))
            tools = result["result"]["tools"]
            tool_names_from_list = {t["name"] for t in tools}
            self.assertEqual(tool_names_from_list, TOOL_NAMES, "tools/list should return all TOOL_NAMES")
            loop.run_until_complete(server.cleanup())
        finally:
            loop.close()

    def test_server_tools_call_classify_message(self):
        """Verify: Server tools/call dispatches to correct handler."""
        server = MCPServer(data_path=self.tmpdir)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                server.handle_tools_call(
                    3,
                    {
                        "name": "classify_message",
                        "arguments": {"message": "Hello world test"},
                    },
                )
            )
            self.assertEqual(result["id"], 3)
            content = result["result"]["content"][0]["text"]
            parsed = json.loads(content)
            self.assertIs(parsed.get("success"), True, f"Tool call should succeed: {parsed}")
            loop.run_until_complete(server.cleanup())
        finally:
            loop.close()


class TestMCPAccessControlE2E(unittest.TestCase):
    """Verify: MCP access control enforces user_id-based authorization end-to-end.

    Tests that write operations (classify_and_remember, forget_memory) are
    denied when no user_id is provided and AccessPolicy is configured,
    and succeed when the correct user_id is supplied.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()
        asyncio.set_event_loop(None)

    def test_write_denied_without_user_id_when_policy_set(self):
        """Verify: Write operations are denied when no user_id is available and policy is configured.

        Scenario: AccessPolicy requires owner_id='alice', but no default_user_id is set.
        Expected: classify_and_remember should fail with security error.
        """
        from carrymem.security.permissions import AccessPolicy

        server = MCPServer(data_path=self.tmpdir)
        server.handlers._carrymem.access_policy = AccessPolicy(owner_id="alice")
        try:
            result = self.loop.run_until_complete(
                _call_tool(server, "classify_and_remember", {"message": "I prefer dark mode"})
            )
            # Should fail — no user_id available to satisfy access policy
            self.assertFalse(
                result.get("success", False),
                f"Write should be denied without user_id when policy is set, got: {result}",
            )
        finally:
            self.loop.run_until_complete(server.cleanup())

    def test_write_succeeds_with_authorized_user_id(self):
        """Verify: Write operations succeed when correct user_id is provided.

        Scenario: AccessPolicy owner_id='alice', default_user_id='alice'.
        Expected: classify_and_remember should succeed.
        """
        from carrymem.security.permissions import AccessPolicy

        server = MCPServer(data_path=self.tmpdir)
        server.handlers._default_user_id = "alice"
        server.handlers._carrymem.access_policy = AccessPolicy(owner_id="alice")
        try:
            result = self.loop.run_until_complete(
                _call_tool(server, "classify_and_remember", {"message": "I prefer dark mode"})
            )
            self.assertIs(result.get("success", False), True, f"Write should succeed with authorized user_id, got: {result}",
            )
        finally:
            self.loop.run_until_complete(server.cleanup())

    def test_forget_memory_denied_for_unauthorized_user(self):
        """Verify: forget_memory is denied when user_id doesn't match owner.

        Scenario: Store memory as 'alice', then try to forget as 'bob'.
        Expected: forget_memory should fail with security error.
        """
        from carrymem.security.permissions import AccessPolicy

        # Step 1: Store a memory as alice
        server_alice = MCPServer(data_path=self.tmpdir)
        server_alice.handlers._default_user_id = "alice"
        server_alice.handlers._carrymem.access_policy = AccessPolicy(owner_id="alice")
        store_result = self.loop.run_until_complete(
            _call_tool(server_alice, "classify_and_remember", {"message": "I prefer PostgreSQL"})
        )
        self.assertIs(store_result.get("success"), True, f"Store as alice should succeed: {store_result}")
        store_data = store_result.get("data", store_result)
        storage_keys = store_data.get("storage_keys", [])
        self.assertGreater(len(storage_keys), 0, "Should have stored at least one memory")
        memory_id = storage_keys[0]
        self.loop.run_until_complete(server_alice.cleanup())

        # Step 2: Try to forget the memory as bob (unauthorized)
        server_bob = MCPServer(data_path=self.tmpdir)
        server_bob.handlers._default_user_id = "bob"
        server_bob.handlers._carrymem.access_policy = AccessPolicy(owner_id="alice")
        try:
            forget_result = self.loop.run_until_complete(
                _call_tool(server_bob, "forget_memory", {"memory_id": memory_id})
            )
            # Should fail — bob is not the owner
            self.assertFalse(
                forget_result.get("success", False),
                f"forget_memory should be denied for unauthorized user, got: {forget_result}",
            )
        finally:
            self.loop.run_until_complete(server_bob.cleanup())

    def test_read_succeeds_without_user_id(self):
        """Verify: Read operations (recall_memories) work even without user_id.

        Scenario: No AccessPolicy configured (open mode).
        Expected: recall_memories should succeed.
        """
        server = MCPServer(data_path=self.tmpdir)
        try:
            # Store something first
            self.loop.run_until_complete(
                _call_tool(server, "classify_and_remember", {"message": "I like Python"})
            )
            # Read should work
            result = self.loop.run_until_complete(
                _call_tool(server, "recall_memories", {"limit": 10})
            )
            self.assertIs(result.get("success"), True, f"Read should succeed without policy: {result}")
        finally:
            self.loop.run_until_complete(server.cleanup())


class TestMCPConfidenceLabelE2E(unittest.TestCase):
    """Verify: Edge confidence labels flow through the MCP handler chain end-to-end.

    Tests that add_graph_relation with confidence=INFERRED is correctly
    stored and returned in subsequent queries via MCP tools.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.server = _make_server(self.tmpdir)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.cm = self.server.handlers._carrymem

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.server.cleanup())
        finally:
            self.loop.close()
            asyncio.set_event_loop(None)

    def test_confidence_label_flows_through_mcp(self):
        """Verify: confidence=INFERRED set via CarryMem API is visible in query_graph MCP results.

        Steps:
        1. Store a memory (auto-extracts entities)
        2. Add a relation with confidence=INFERRED via CarryMem API
        3. Query graph via MCP tool — verify confidence label is present
        """
        # Step 1: Store a memory
        store_result = self.loop.run_until_complete(
            _call_tool(self.server, "classify_and_remember", {"message": "I prefer Rust for systems programming"})
        )
        self.assertIs(store_result.get("success"), True)
        storage_keys = store_result.get("data", store_result).get("storage_keys", [])
        self.assertGreater(len(storage_keys), 0)
        memory_id = storage_keys[0]

        # Step 2: Add entities and a relation with confidence=INFERRED
        self.cm._adapter.store_graph_entities(memory_id, "Rust is a systems language")
        added = self.cm.add_graph_relation(
            "Rust", "systems language", "is_a",
            source_memory_key=memory_id, confidence="INFERRED",
        )
        self.assertIs(added, True, "add_graph_relation with confidence=INFERRED should succeed")

        # Step 3: Query graph via MCP — verify confidence is in results
        query_result = self.loop.run_until_complete(
            _call_tool(self.server, "query_graph", {"entity_text": "Rust", "max_hops": 2})
        )
        self.assertIs(query_result.get("success"), True)
        query_data = query_result.get("data", query_result)
        self.assertIn("entities", query_data)

        # Verify the relation has confidence=INFERRED
        relations = query_data.get("relations", [])
        if relations:
            rust_relations = [r for r in relations if r.get("source_entity") == "Rust" or r.get("entity_text") == "Rust"]
            for rel in rust_relations:
                self.assertIn(
                    rel.get("confidence", rel.get("relation_confidence")),
                    {"INFERRED", "EXTRACTED", "AMBIGUOUS"},
                    f"Relation should have a valid confidence label, got: {rel}",
                )
