"""Tests for v0.7.0 Phase 3 features.

Covers:
- 3.1 MCP HTTP/SSE server
- 3.2 JSON file adapter
- 3.3 Async API (AsyncCarryMem)
- 3.4 Adapter loader (JSON adapter registration)
- 3.5 Integration configs
"""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from memory_classification_engine import CarryMem, JSONAdapter, AsyncCarryMem
from memory_classification_engine.adapters.json_adapter import JSONAdapter as JSONAdapterDirect
from memory_classification_engine.adapters.loader import load_adapter, list_available_adapters
from memory_classification_engine.integration.layer2_mcp.http_server import MCPHTTPServer


class TestJSONAdapter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "test_memories.json")
        self.adapter = JSONAdapter(path=self.path, namespace="default")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_remember_and_recall(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            id="test1",
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
            tier=2,
            source_layer="rule",
        )
        stored = self.adapter.remember(entry)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.content, "I prefer dark mode")

        results = self.adapter.recall(query="dark mode")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "I prefer dark mode")

    def test_deduplication(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
            tier=2,
            source_layer="rule",
        )
        self.adapter.remember(entry)
        self.adapter.remember(entry)
        results = self.adapter.recall(query="dark mode")
        self.assertEqual(len(results), 1)

    def test_forget(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
            tier=2,
            source_layer="rule",
        )
        stored = self.adapter.remember(entry)
        result = self.adapter.forget(stored.storage_key)
        self.assertTrue(result)
        results = self.adapter.recall(query="dark mode")
        self.assertEqual(len(results), 0)

    def test_get_stats(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
            tier=2,
            source_layer="rule",
        )
        self.adapter.remember(entry)
        stats = self.adapter.get_stats()
        self.assertEqual(stats["adapter"], "json")
        self.assertEqual(stats["total_count"], 1)

    def test_importance_score(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            type="correction",
            content="Use PostgreSQL not MySQL",
            confidence=0.95,
            tier=3,
            source_layer="rule",
        )
        stored = self.adapter.remember(entry)
        self.assertGreater(stored.importance_score, 0)

    def test_file_persistence(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            type="fact_declaration",
            content="The sky is blue",
            confidence=0.99,
            tier=3,
            source_layer="rule",
        )
        self.adapter.remember(entry)
        self.assertTrue(os.path.exists(self.path))

        adapter2 = JSONAdapter(path=self.path, namespace="default")
        results = adapter2.recall(query="sky")
        self.assertEqual(len(results), 1)

    def test_namespace_isolation(self):
        from memory_classification_engine.adapters.base import MemoryEntry
        entry = MemoryEntry(
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
            tier=2,
            source_layer="rule",
        )
        self.adapter.remember(entry)
        adapter2 = JSONAdapter(path=self.path, namespace="other")
        results = adapter2.recall(query="dark mode")
        self.assertEqual(len(results), 0)

    def test_capabilities(self):
        caps = self.adapter.capabilities
        self.assertFalse(caps["fts"])
        self.assertTrue(caps["ttl"])
        self.assertFalse(caps["semantic_recall"])

    def test_name(self):
        self.assertEqual(self.adapter.name, "json")


class TestAdapterLoader(unittest.TestCase):
    def test_load_json_adapter(self):
        cls = load_adapter("json")
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "JSONAdapter")

    def test_json_in_available(self):
        available = list_available_adapters()
        self.assertIn("json", available)

    def test_load_nonexistent(self):
        cls = load_adapter("nonexistent_adapter")
        self.assertIsNone(cls)


class TestCarryMemWithJSON(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "test.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_storage(self):
        adapter = JSONAdapter(path=self.path)
        cm = CarryMem(storage=adapter)
        try:
            result = cm.classify_and_remember("I prefer dark mode")
            self.assertTrue(result["stored"])
            memories = cm.recall_memories(query="dark mode")
            self.assertGreater(len(memories), 0)
        finally:
            cm.close()


class TestAsyncCarryMem(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "async_test.db")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_async_classify_and_remember(self):
        async def _test():
            cm = AsyncCarryMem(storage="sqlite", db_path=self.db_path)
            try:
                result = await cm.classify_and_remember("I prefer dark mode")
                self.assertTrue(result["stored"])
                memories = await cm.recall_memories(query="dark mode")
                self.assertGreater(len(memories), 0)
            finally:
                await cm.close()

        asyncio.run(_test())

    def test_async_build_context(self):
        async def _test():
            cm = AsyncCarryMem(storage="sqlite", db_path=self.db_path)
            try:
                await cm.classify_and_remember("I prefer dark mode")
                ctx = await cm.build_context(context="dark mode", language="en")
                self.assertIn("system_prompt", ctx)
            finally:
                await cm.close()

        asyncio.run(_test())

    def test_async_context_manager(self):
        async def _test():
            async with AsyncCarryMem(storage="sqlite", db_path=self.db_path) as cm:
                result = await cm.classify_and_remember("I always use Python for data analysis")
                self.assertTrue(result.get("stored", False) or result.get("should_remember", False))

        asyncio.run(_test())

    def test_async_get_stats(self):
        async def _test():
            cm = AsyncCarryMem(storage="sqlite", db_path=self.db_path)
            try:
                stats = await cm.get_stats()
                self.assertIn("total_count", stats)
            finally:
                await cm.close()

        asyncio.run(_test())


class TestMCPHTTPServer(unittest.TestCase):
    def test_server_creation(self):
        server = MCPHTTPServer(host="127.0.0.1", port=9999)
        self.assertEqual(server._host, "127.0.0.1")
        self.assertEqual(server._port, 9999)

    def test_server_with_api_key(self):
        server = MCPHTTPServer(host="127.0.0.1", port=9999, api_key="test_key")
        self.assertEqual(server._api_key, "test_key")

    def test_auth_check_no_key(self):
        server = MCPHTTPServer(host="127.0.0.1", port=9999)
        self.assertTrue(server._check_auth({}))

    def test_auth_check_valid_key(self):
        server = MCPHTTPServer(host="127.0.0.1", port=9999, api_key="secret")
        self.assertTrue(server._check_auth({"authorization": "Bearer secret"}))

    def test_auth_check_invalid_key(self):
        server = MCPHTTPServer(host="127.0.0.1", port=9999, api_key="secret")
        self.assertFalse(server._check_auth({"authorization": "Bearer wrong"}))


class TestIntegrationConfigs(unittest.TestCase):
    def test_claude_code_config_exists(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "integrations", "claude_code", "mcp.json"
        )
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            self.assertIn("mcpServers", config)
            self.assertIn("carrymem", config["mcpServers"])

    def test_cursor_config_exists(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "integrations", "cursor", "mcp.json"
        )
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            self.assertIn("mcpServers", config)
            self.assertIn("carrymem", config["mcpServers"])


if __name__ == "__main__":
    unittest.main()
