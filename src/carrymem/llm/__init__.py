"""CarryMem LLM Integration Module.

The module has two layers:

1. ``LLMClient`` — the stable public client. It keeps the legacy synchronous
   API (``chat``, ``is_available``, ``count_tokens``) that existing features
   use, and adds the asynchronous tier API (``generate``, ``achat``).

2. Providers — ``HostLLMProvider`` (Tier 4, MCP sampling),
   ``CloudLLMProvider`` (Tier 3 remote / Tier 2 local endpoint), and
   ``RuleBasedProvider`` (Tier 1, always available).

Core features work without an LLM. LLM enhancement is opt-in and degrades
with an explicit error instead of returning placeholder text.
"""

import asyncio
import concurrent.futures
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from carrymem.utils.logger import logger

# Default LLM configuration constants.
# Used as fallbacks when config/env vars are not set or invalid.
DEFAULT_LLM_MAX_TOKENS = 500
DEFAULT_LLM_TIMEOUT_SECONDS = 30

_OPENAI_CLIENT = None
_ZAI_CLIENT = None
_BACKEND = None

try:
    from openai import OpenAI as _OpenAI

    _OPENAI_CLIENT = _OpenAI
    _BACKEND = "openai"
except ImportError:
    pass

if _BACKEND is None:
    try:
        from zai import ZhipuAiClient as _ZhipuAiClient

        _ZAI_CLIENT = _ZhipuAiClient
        _BACKEND = "zai"
    except ImportError:
        pass

_CJK_RANGES = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef" r"\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]"
)


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM provider can produce a response."""


def _env_or(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def _str_to_bool(val: Union[str, bool]) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes", "on")


def run_coroutine_sync(coro: Any) -> Any:
    """Run a coroutine from synchronous code.

    MCP handlers are synchronous but can run inside an active event loop
    (for example under pytest-asyncio). In that case a nested loop is not
    allowed, so the coroutine runs in a worker thread with its own loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def tier(self) -> int:
        """Provider tier (1=rule-based, 2=local, 3=cloud, 4=host)."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the provider can serve a request."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Generate text completion from a prompt."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Generate a chat completion from a message history."""


def _normalize_content(response: Any) -> str:
    """Extract text from an MCP sampling response."""
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if content is None:
        raise LLMUnavailableError("Host LLM returned no content")
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(getattr(block, "text", "")))
        return "".join(parts)
    return str(content)


class HostLLMProvider(LLMProvider):
    """MCP host LLM provider (Tier 4).

    Uses the LLM of the MCP client (Claude Desktop, Cursor, and others)
    through the MCP sampling API. No configuration is required.
    """

    def __init__(self, mcp_server: Any = None) -> None:
        self._server = mcp_server

    @property
    def tier(self) -> int:
        return 4

    @property
    def is_available(self) -> bool:
        """Return True only when the server can serve sampling requests.

        An explicit instance attribute wins, because test doubles and thin
        wrappers attach ``request_sampling`` at runtime. Otherwise the method
        must exist on the class. A bare ``Mock()`` has no class method, so it
        is correctly reported as unavailable.
        """
        server = self._server
        if server is None:
            return False
        explicit = getattr(server, "__dict__", {}).get("request_sampling")
        if explicit is not None:
            return callable(explicit)
        return callable(getattr(type(server), "request_sampling", None))

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, max_tokens=max_tokens, temperature=temperature, **kwargs)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        if not self.is_available:
            raise LLMUnavailableError("Host LLM not available")
        response = await self._server.request_sampling(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return _normalize_content(response)


class CloudLLMProvider(LLMProvider):
    """Tier 3 (remote API) or Tier 2 (local endpoint) provider.

    Both tiers use the same OpenAI-compatible client. The tier value depends
    on the endpoint: loopback and ``0.0.0.0`` report Tier 2, all other hosts
    report Tier 3. The blocking SDK call runs in a worker thread so that the
    MCP event loop stays free.
    """

    _LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def __init__(self, client: Any, backend: Optional[str], model: Optional[str], base_url: Optional[str]) -> None:
        self._client = client
        self._backend = backend
        self._model = model
        self._base_url = base_url or ""

    @property
    def tier(self) -> int:
        host = (urlparse(self._base_url).hostname or "").lower()
        return 2 if host in self._LOCAL_HOSTS else 3

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        return await self.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        text = await asyncio.to_thread(self._chat_sync, messages, max_tokens, temperature)
        if not text:
            raise LLMUnavailableError("Cloud LLM returned no content")
        return text

    def _chat_sync(self, messages: List[Dict[str, str]], max_tokens: int, temperature: float) -> Optional[str]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not response.choices:
            return None
        return response.choices[0].message.content  # type: ignore[no-any-return]


class RuleBasedProvider(LLMProvider):
    """Rule-based fallback provider (Tier 1).

    This provider is always available, but it cannot generate free text.
    It raises ``LLMUnavailableError`` so callers switch to a deterministic
    rule-based path. It never returns placeholder text.
    """

    @property
    def tier(self) -> int:
        return 1

    @property
    def is_available(self) -> bool:
        return True

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        raise LLMUnavailableError("Rule-based provider cannot generate text")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        raise LLMUnavailableError("Rule-based provider cannot generate text")


class LLMClient:
    """LLM client with a stable synchronous API and an asynchronous tier API.

    The synchronous API (``chat``, ``is_available``, ``count_tokens``) keeps
    the contract that existing features depend on. The asynchronous API
    (``generate``, ``achat``) tries Tier 4 (host LLM) first and raises
    ``LLMUnavailableError`` when no provider can answer.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        mcp_server: Any = None,
    ) -> None:
        self._enabled = self._resolve_enabled(config)
        self._api_key = self._resolve("llm.api_key", "CARRYMEM_LLM_API_KEY", config)
        self._base_url = self._resolve(
            "llm.base_url", "CARRYMEM_LLM_BASE_URL", config, default="https://api.openai.com/v1"
        )
        self._model = self._resolve("llm.model", "CARRYMEM_LLM_MODEL", config, default="gpt-4o-mini")
        try:
            self._temperature = float(
                self._resolve(  # type: ignore[arg-type]
                    "llm.temperature", "CARRYMEM_LLM_TEMPERATURE", config, default="0.3"
                )
            )
        except (ValueError, TypeError):
            self._temperature = 0.3
        try:
            self._max_tokens = int(
                self._resolve(  # type: ignore[arg-type]
                    "llm.max_tokens", "CARRYMEM_LLM_MAX_TOKENS", config, default=str(DEFAULT_LLM_MAX_TOKENS)
                )
            )
        except (ValueError, TypeError):
            self._max_tokens = DEFAULT_LLM_MAX_TOKENS
        try:
            self._timeout = int(
                self._resolve(  # type: ignore[arg-type]
                    "llm.timeout",
                    "CARRYMEM_LLM_TIMEOUT",
                    config,
                    default=str(DEFAULT_LLM_TIMEOUT_SECONDS),
                )
            )
        except (ValueError, TypeError):
            self._timeout = DEFAULT_LLM_TIMEOUT_SECONDS
        self._client = self._init_client()

        # Tier chain. Only providers that are really available are added.
        self._providers: List[LLMProvider] = []
        if mcp_server is not None:
            host_provider = HostLLMProvider(mcp_server)
            if host_provider.is_available:
                self._providers.append(host_provider)
        if self._client is not None:
            self._providers.append(
                CloudLLMProvider(
                    self._client,
                    backend=_BACKEND,
                    model=self._model,
                    base_url=self._base_url,
                )
            )
        self._providers.append(RuleBasedProvider())

    def _resolve_enabled(self, config: Optional[Dict[str, Any]] = None) -> bool:
        if config and "llm.enabled" in config:
            return _str_to_bool(config["llm.enabled"])
        val = _env_or("CARRYMEM_LLM_ENABLED", "false")
        return _str_to_bool(val)  # type: ignore[arg-type]

    def _resolve(
        self,
        config_key: str,
        env_key: str,
        config: Optional[Dict[str, Any]] = None,
        default: Optional[str] = None,
    ) -> Optional[str]:
        if config and config_key in config:
            return config[config_key]  # type: ignore[no-any-return]
        return _env_or(env_key, default)

    def _init_client(self) -> Any:
        if not self._enabled:
            return None
        if not self._api_key:
            logger.warning("LLM enabled but no API key configured")
            return None
        if _BACKEND == "openai" and _OPENAI_CLIENT is not None:
            try:
                return _OPENAI_CLIENT(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                )
            except (ImportError, ValueError, OSError) as e:
                logger.error("Failed to initialize OpenAI client: %s", e)
                return None
        if _BACKEND == "zai" and _ZAI_CLIENT is not None:
            try:
                return _ZAI_CLIENT(api_key=self._api_key, timeout=self._timeout)
            except (ImportError, ValueError, OSError) as e:
                logger.error("Failed to initialize Z.AI client: %s", e)
                return None
        logger.warning("No LLM backend available (openai/zai not installed)")
        return None

    @property
    def tier(self) -> int:
        """Active tier: 4 when a host LLM is available, otherwise 1."""
        return self._providers[0].tier if self._providers else 1

    def is_available(self) -> bool:
        """Return True if a cloud LLM client or a host LLM is ready."""
        return self._client is not None or self.tier > 1

    def get_status(self) -> Dict[str, Any]:
        """Return the provider chain state for diagnostics."""
        return {
            "active_tier": self.tier,
            "available_tiers": [provider.tier for provider in self._providers],
            "provider_status": [
                {"tier": provider.tier, "available": provider.is_available} for provider in self._providers
            ],
            "cloud_backend": _BACKEND,
            "cloud_ready": self._client is not None,
        }

    def __repr__(self) -> str:
        key = self._api_key
        masked = key[:4] + "..." + key[-4:] if key and len(key) > 8 else "***"
        return (
            f"LLMClient(backend={_BACKEND}, model={self._model}, "
            f"api_key={masked}, available={self.is_available()}, tier={self.tier})"
        )

    def chat(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        """Send a synchronous chat request and return the text, or None on failure."""
        if not self.is_available():
            return None
        if self._client is None:
            # A host LLM is available, but this synchronous method only serves
            # the cloud backend. Use generate()/achat() for host LLM calls.
            return None
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            if _BACKEND == "openai":
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                if not response.choices:
                    logger.warning("LLM returned empty choices")
                    return None
                return response.choices[0].message.content  # type: ignore[no-any-return]
            if _BACKEND == "zai":
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                if not response.choices:
                    logger.warning("LLM returned empty choices")
                    return None
                return response.choices[0].message.content  # type: ignore[no-any-return]
        except (RuntimeError, ValueError, TypeError, OSError) as e:
            logger.error("LLM chat failed: %s", e)
        return None

    def count_tokens(self, text: str) -> int:
        """Estimate token count for a text string (heuristic, not exact)."""
        if not text:
            return 0
        cjk_count = len(_CJK_RANGES.findall(text))
        non_cjk_len = len(text) - cjk_count
        return (non_cjk_len // 4) + (cjk_count // 2) + 1

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Generate text through the tier chain, or raise ``LLMUnavailableError``."""
        return await self._dispatch("generate", prompt, max_tokens, temperature, **kwargs)

    async def achat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Chat through the tier chain, or raise ``LLMUnavailableError``."""
        return await self._dispatch("chat", messages, max_tokens, temperature, **kwargs)

    async def _dispatch(
        self,
        method: str,
        payload: Any,
        max_tokens: int,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        failures: List[str] = []
        for provider in self._providers:
            try:
                handler = provider.generate if method == "generate" else provider.chat
                return await handler(payload, max_tokens=max_tokens, temperature=temperature, **kwargs)
            except LLMUnavailableError:
                continue
            except Exception as exc:  # noqa: BLE001 - NOTE: a tier failure must not stop the chain
                logger.warning("LLM tier %s failed: %s", provider.tier, exc)
                failures.append(f"tier {provider.tier}: {exc}")
                continue
        detail = "; ".join(failures) if failures else "no provider available"
        raise LLMUnavailableError(detail)


__all__ = [
    "LLMProvider",
    "HostLLMProvider",
    "RuleBasedProvider",
    "LLMClient",
    "LLMUnavailableError",
    "run_coroutine_sync",
]
