"""Phase 4 LLM Integration Tests.

Tests for Tier 4 (Host LLM) integration, graceful degradation,
and zero-dependency fallback behavior.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestHostLLMProvider:
    """Test Tier 4 Host LLM Provider."""

    def test_host_llm_provider_init(self):
        """Test HostLLMProvider initialization."""
        from carrymem.llm import HostLLMProvider

        # Without server
        provider = HostLLMProvider(mcp_server=None)
        assert provider.tier == 4
        assert not provider.is_available

        # With mock server without sampling
        mock_server = Mock()
        provider = HostLLMProvider(mcp_server=mock_server)
        assert provider.tier == 4
        assert not provider.is_available

        # With mock server with sampling
        mock_server.request_sampling = AsyncMock()
        provider = HostLLMProvider(mcp_server=mock_server)
        assert provider.tier == 4
        assert provider.is_available

    @pytest.mark.asyncio
    async def test_host_llm_generate(self):
        """Test HostLLMProvider.generate()."""
        from carrymem.llm import HostLLMProvider

        # Mock server with sampling
        mock_server = Mock()
        mock_response = Mock()
        mock_response.content = "Generated text from host LLM"
        mock_server.request_sampling = AsyncMock(return_value=mock_response)

        provider = HostLLMProvider(mcp_server=mock_server)
        result = await provider.generate("Test prompt")

        assert result == "Generated text from host LLM"
        mock_server.request_sampling.assert_called_once()

    @pytest.mark.asyncio
    async def test_host_llm_chat(self):
        """Test HostLLMProvider.chat()."""
        from carrymem.llm import HostLLMProvider

        # Mock server
        mock_server = Mock()
        mock_response = Mock()
        mock_response.content = "Chat response from host LLM"
        mock_server.request_sampling = AsyncMock(return_value=mock_response)

        provider = HostLLMProvider(mcp_server=mock_server)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        result = await provider.chat(messages)

        assert result == "Chat response from host LLM"
        mock_server.request_sampling.assert_called_once()


class TestCloudLLMProvider:
    """Test Tier 3 (remote) and Tier 2 (local endpoint) provider."""

    def test_tier_depends_on_endpoint(self):
        """Loopback endpoints report Tier 2, remote endpoints report Tier 3."""
        from carrymem.llm import CloudLLMProvider

        client = Mock()
        local = CloudLLMProvider(client, "openai", "model", "http://localhost:11434/v1")
        remote = CloudLLMProvider(client, "openai", "model", "https://api.openai.com/v1")

        assert local.tier == 2
        assert remote.tier == 3
        assert local.is_available
        assert remote.is_available

    @pytest.mark.asyncio
    async def test_generate_uses_configured_client(self):
        """Generate must return the text from the OpenAI-compatible client."""
        from carrymem.llm import CloudLLMProvider

        fake = Mock()
        fake.chat.completions.create.return_value.choices = [Mock(message=Mock(content="cloud answer"))]
        provider = CloudLLMProvider(fake, "openai", "gpt-4o-mini", "https://api.openai.com/v1")

        assert await provider.generate("hello") == "cloud answer"

    @pytest.mark.asyncio
    async def test_empty_response_raises(self):
        """An empty completion must degrade, not return a blank string."""
        from carrymem.llm import CloudLLMProvider, LLMUnavailableError

        fake = Mock()
        fake.chat.completions.create.return_value.choices = []
        provider = CloudLLMProvider(fake, "openai", "gpt-4o-mini", "https://api.openai.com/v1")

        with pytest.raises(LLMUnavailableError):
            await provider.generate("hello")

    def test_client_registers_cloud_tier(self):
        """A configured client must sit in the dispatch chain before Tier 1."""
        from carrymem.llm import LLMClient

        with patch.object(LLMClient, "_init_client", return_value=Mock()):
            client = LLMClient(mcp_server=None)

        assert client.tier == 3
        assert [p.tier for p in client._providers] == [3, 1]


class TestRuleBasedProvider:
    """Test Tier 1 Rule-based fallback."""

    def test_rule_based_provider_always_available(self):
        """Test RuleBasedProvider is always available."""
        from carrymem.llm import RuleBasedProvider

        provider = RuleBasedProvider()
        assert provider.tier == 1
        assert provider.is_available  # Always True

    @pytest.mark.asyncio
    async def test_rule_based_generate_raises(self):
        """Tier 1 cannot generate text; it must signal unavailability."""
        from carrymem.llm import LLMUnavailableError, RuleBasedProvider

        provider = RuleBasedProvider()
        with pytest.raises(LLMUnavailableError):
            await provider.generate("Test prompt")

    @pytest.mark.asyncio
    async def test_rule_based_chat_raises(self):
        """Tier 1 cannot chat; it must signal unavailability."""
        from carrymem.llm import LLMUnavailableError, RuleBasedProvider

        provider = RuleBasedProvider()
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(LLMUnavailableError):
            await provider.chat(messages)


class TestLLMClient:
    """Test LLMClient tier selection and graceful degradation."""

    def test_llm_client_tier_selection(self):
        """Test LLMClient selects correct tier."""
        from carrymem.llm import LLMClient

        # No server -> Tier 1 only
        client = LLMClient(mcp_server=None)
        assert client.tier == 1
        assert len(client._providers) == 1

        # Mock server with sampling -> Tier 4 + Tier 1
        mock_server = Mock()
        mock_server.request_sampling = AsyncMock()
        client = LLMClient(mcp_server=mock_server)
        assert client.tier == 4
        assert len(client._providers) == 2  # Tier 4 + Tier 1

    @pytest.mark.asyncio
    async def test_llm_client_graceful_degradation(self):
        """A Tier 4 failure must surface as LLMUnavailableError, not placeholder text."""
        from carrymem.llm import LLMClient, LLMUnavailableError

        # Mock server that fails
        mock_server = Mock()
        mock_server.request_sampling = AsyncMock(side_effect=RuntimeError("Sampling failed"))

        client = LLMClient(mcp_server=mock_server)
        assert client.tier == 4  # Should try Tier 4 first

        with pytest.raises(LLMUnavailableError):
            await client.generate("Test prompt")

    @pytest.mark.asyncio
    async def test_llm_client_chat_degradation(self):
        """The async tier chat must raise when every LLM tier fails."""
        from carrymem.llm import LLMClient, LLMUnavailableError

        # Mock server that fails
        mock_server = Mock()
        mock_server.request_sampling = AsyncMock(side_effect=RuntimeError("Host unavailable"))

        client = LLMClient(mcp_server=mock_server)
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(LLMUnavailableError):
            await client.achat(messages)

    def test_llm_client_get_status(self):
        """Test LLMClient.get_status() returns correct info."""
        from carrymem.llm import LLMClient

        mock_server = Mock()
        mock_server.request_sampling = AsyncMock()
        client = LLMClient(mcp_server=mock_server)

        status = client.get_status()

        assert "active_tier" in status
        assert status["active_tier"] == 4
        assert "available_tiers" in status
        assert 4 in status["available_tiers"]
        assert 1 in status["available_tiers"]
        assert "provider_status" in status
        assert len(status["provider_status"]) == 2


class TestLLMEnhancements:
    """Test LLM-enhanced functions in enhancements.py."""

    @pytest.mark.asyncio
    async def test_suggest_rules_via_host_llm(self):
        """Test suggest_rules_via_host_llm() with mock LLM."""
        from carrymem.llm import LLMClient
        from carrymem.llm.enhancements import suggest_rules_via_host_llm

        # Mock LLM client that returns valid JSON
        mock_server = Mock()
        mock_response = Mock()
        mock_response.content = """```json
[
  {
    "trigger": "when writing Python code",
    "action": "use type hints",
    "confidence": 0.9,
    "reasoning": "User frequently mentions type hints"
  }
]
```"""
        mock_server.request_sampling = AsyncMock(return_value=mock_response)

        client = LLMClient(mcp_server=mock_server)

        # Sample memories
        memories = [
            {"raw_text": "Always use type hints in Python", "type": "preference"},
            {"raw_text": "Prefer pytest over unittest", "type": "preference"},
        ]

        result = await suggest_rules_via_host_llm(client, memories, limit=5)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["trigger"] == "when writing Python code"
        assert result[0]["action"] == "use type hints"
        assert result[0]["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_suggest_rules_fallback_to_pattern(self):
        """Test suggest_rules falls back to pattern-based on LLM failure."""
        from carrymem.llm import LLMClient
        from carrymem.llm.enhancements import suggest_rules_pattern_based, suggest_rules_via_host_llm

        # Mock LLM client that fails
        mock_server = Mock()
        mock_server.request_sampling = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        client = LLMClient(mcp_server=mock_server)

        memories = [
            {"raw_text": "Always use pytest", "type": "preference"},
            {"raw_text": "Never use print for debugging", "type": "preference"},
        ]

        # Should gracefully degrade to pattern-based
        result = await suggest_rules_via_host_llm(client, memories, limit=3)

        # Should return pattern-based results
        assert isinstance(result, list)
        # May be empty if patterns not strong enough, but shouldn't crash

    def test_suggest_rules_pattern_based(self):
        """Test pattern-based rule suggestion (Tier 1)."""
        from carrymem.llm.enhancements import suggest_rules_pattern_based

        memories = [
            {"raw_text": "Always use type hints in Python", "type": "preference"},
            {"raw_text": "Always write tests for new features", "type": "preference"},
            {"raw_text": "Never commit sensitive data", "type": "constraint"},
        ]

        result = suggest_rules_pattern_based(memories, limit=5)

        assert isinstance(result, list)
        # Should extract some rules from "always"/"never" patterns
        assert len(result) > 0
        for rule in result:
            assert "trigger" in rule
            assert "action" in rule
            assert "confidence" in rule


class TestMCPHandlerIntegration:
    """Test MCP handler integration with LLM client."""

    @pytest.mark.asyncio
    async def test_suggest_rules_handler_with_llm(self):
        """Test handle_suggest_rules uses LLM when available."""
        from carrymem.integration.layer2_mcp.handlers.rule import handle_suggest_rules
        from carrymem.llm import LLMClient

        # Mock rule engine
        mock_engine = Mock()
        mock_engine.suggest_rules = Mock(return_value=[])

        # Mock CarryMem
        mock_carrymem = Mock()
        mock_carrymem.recall_memories = Mock(return_value=[{"raw_text": "Prefer pytest", "type": "preference"}])

        # Mock LLM client that succeeds
        mock_server = Mock()
        mock_response = Mock()
        mock_response.content = """[{"trigger": "testing", "action": "use pytest", "confidence": 0.8}]"""
        mock_server.request_sampling = AsyncMock(return_value=mock_response)

        llm_client = LLMClient(mcp_server=mock_server)

        # Call handler
        args = {"_carrymem": mock_carrymem, "_llm_client": llm_client, "max_candidates": 5}

        result = handle_suggest_rules(mock_engine, args)

        assert "suggestions" in result
        assert "tier" in result
        # Should use LLM tier
        assert result["tier"] == "llm_enhanced"


class TestSamplingResponseRouting:
    """The stdin loop must deliver sampling responses to the waiting future."""

    def test_routing_resolves_pending_future(self):
        from carrymem.integration.layer2_mcp.server import MCPServer

        server = object.__new__(MCPServer)
        server._pending_sampling = {}
        loop = asyncio.new_event_loop()
        try:
            future = loop.create_future()
            server._pending_sampling[7] = future
            response = {"jsonrpc": "2.0", "id": 7, "result": {"content": "hello"}}

            assert server._is_response(response) is True
            assert server._is_response({"jsonrpc": "2.0", "id": 7, "method": "tools/call"}) is False

            server._resolve_sampling_response(response)

            assert future.result()["result"]["content"] == "hello"
            assert 7 not in server._pending_sampling
        finally:
            loop.close()

    def test_unknown_response_id_is_ignored(self):
        from carrymem.integration.layer2_mcp.server import MCPServer

        server = object.__new__(MCPServer)
        server._pending_sampling = {}
        # Must not raise for an id that nobody waits for.
        server._resolve_sampling_response({"jsonrpc": "2.0", "id": 999, "result": {}})
        assert server._pending_sampling == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
