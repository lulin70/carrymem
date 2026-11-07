"""LLM integration layer for CarryMem.

Provides optional LLM enhancement through a tiered architecture:
- Tier 4: Host LLM (via MCP sampling) - zero config, best UX
- Tier 3: Cloud API (OpenAI/Anthropic) - explicit config required  
- Tier 2: Local LLM (Ollama/LM Studio) - offline capable
- Tier 1: Rule-based fallback - zero dependencies

All core features work without LLM (Tier 1 guarantee).
"""

from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def tier(self) -> int:
        """Provider tier (1=rule-based, 2=local, 3=cloud, 4=host)."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is currently available."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text completion from prompt."""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate chat completion from message history."""
        pass


class HostLLMProvider(LLMProvider):
    """MCP host LLM provider (Tier 4).
    
    Uses the LLM from the MCP client (Claude Desktop, Cursor, etc.)
    via MCP sampling API. Zero configuration required.
    """
    
    def __init__(self, mcp_server=None):
        """Initialize host LLM provider.
        
        Args:
            mcp_server: MCP Server instance with sampling capability.
        """
        self._server = mcp_server
    
    @property
    def tier(self) -> int:
        return 4
    
    @property
    def is_available(self) -> bool:
        """Check if MCP server supports sampling."""
        if self._server is None:
            return False
        
        # Check if server has sampling capability
        return hasattr(self._server, 'request_sampling')
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate via MCP sampling."""
        if not self.is_available:
            raise RuntimeError("Host LLM not available")
        
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, max_tokens, temperature, **kwargs)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate via MCP sampling createMessage."""
        if not self.is_available:
            raise RuntimeError("Host LLM not available")
        
        # Convert to MCP sampling format (simple dict format)
        # The MCP protocol expects messages as list of dicts with role/content
        mcp_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
        
        # Request sampling from host
        response = await self._server.request_sampling(
            messages=mcp_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        return response.content


class RuleBasedProvider(LLMProvider):
    """Rule-based fallback provider (Tier 1).
    
    No LLM required. Uses pattern matching and heuristics.
    Guaranteed to work in all environments (zero dependencies).
    """
    
    @property
    def tier(self) -> int:
        return 1
    
    @property
    def is_available(self) -> bool:
        return True  # Always available
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Simulate generation with rule-based logic."""
        # Placeholder: actual implementation in suggest_rules logic
        return "[Rule-based response - no LLM available]"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Simulate chat with rule-based logic."""
        last_message = messages[-1]["content"] if messages else ""
        return await self.generate(last_message, max_tokens, temperature, **kwargs)


class LLMClient:
    """Unified LLM client with automatic tier selection and graceful degradation.
    
    Usage:
        # Auto-detect best available tier
        client = LLMClient(mcp_server=server)
        response = await client.generate("Suggest rules for...")
        
        # Tier selection priority: 4 (host) -> 3 (cloud) -> 2 (local) -> 1 (rule)
    """
    
    def __init__(
        self,
        mcp_server=None,
        provider: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize LLM client with automatic tier selection.
        
        Args:
            mcp_server: MCP Server instance (enables Tier 4).
            provider: Explicit provider name ("openai", "anthropic", "ollama").
            config: Provider-specific configuration (API keys, model names, etc.).
        """
        self.config = config or {}
        self._providers: List[LLMProvider] = []
        
        # Tier 4: Host LLM (via MCP)
        if mcp_server:
            host_provider = HostLLMProvider(mcp_server)
            if host_provider.is_available:
                self._providers.append(host_provider)
        
        # Tier 3: Cloud API (explicit config only)
        if provider in ["openai", "anthropic"]:
            # TODO: Implement in Phase 4.2
            pass
        
        # Tier 2: Local LLM (auto-detect)
        # TODO: Implement in Phase 4.1
        
        # Tier 1: Rule-based fallback (always available)
        self._providers.append(RuleBasedProvider())
    
    @property
    def tier(self) -> int:
        """Current active tier."""
        return self._providers[0].tier if self._providers else 1
    
    @property
    def provider(self) -> LLMProvider:
        """Current active provider."""
        return self._providers[0] if self._providers else RuleBasedProvider()
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate with automatic fallback on failure."""
        import logging
        logger = logging.getLogger(__name__)
        
        last_error = None
        for provider in self._providers:
            try:
                logger.debug(f"Attempting generation with Tier {provider.tier}")
                result = await provider.generate(prompt, **kwargs)
                logger.info(f"Generation succeeded with Tier {provider.tier}")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Tier {provider.tier} failed: {e}, degrading to next tier...")
                continue
        
        # Should never reach here (Tier 1 always works)
        logger.error(f"All providers failed. Last error: {last_error}")
        return "[Error: all providers failed]"
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Chat with automatic fallback on failure."""
        import logging
        logger = logging.getLogger(__name__)
        
        last_error = None
        for provider in self._providers:
            try:
                logger.debug(f"Attempting chat with Tier {provider.tier}")
                result = await provider.chat(messages, **kwargs)
                logger.info(f"Chat succeeded with Tier {provider.tier}")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Tier {provider.tier} failed: {e}, degrading to next tier...")
                continue
        
        logger.error(f"All providers failed. Last error: {last_error}")
        return "[Error: all providers failed]"
    
    def get_status(self) -> Dict[str, Any]:
        """Get current LLM client status and available tiers.
        
        Returns:
            Dict with active_tier, available_tiers, and provider_status
        """
        return {
            "active_tier": self.tier,
            "available_tiers": [p.tier for p in self._providers],
            "provider_status": [
                {
                    "tier": p.tier,
                    "is_available": p.is_available,
                    "type": type(p).__name__,
                }
                for p in self._providers
            ],
        }


__all__ = [
    "LLMProvider",
    "HostLLMProvider",
    "RuleBasedProvider",
    "LLMClient",
]
