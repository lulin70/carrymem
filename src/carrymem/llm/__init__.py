"""CarryMem LLM Integration Module.

This module provides LLM client abstraction for CarryMem's AI-powered features
(session summarization, semantic aggregation, etc.).

Currently supports OpenAI and ZhipuAI backends. Future enhancements (v0.5.1+)
may include:
- Additional LLM provider support (Anthropic, Google, etc.)
- Streaming response support
- Token budget management
- Prompt template management

LLMClient is the primary entry point. LLM features are opt-in (disabled by
default); set CARRYMEM_LLM_ENABLED=true and configure an API key to activate.
The API surface is stable for the current feature set but may expand in future
versions as additional LLM capabilities are integrated.
"""

import os
import re
from typing import Any, Dict, Optional, Union

from carrymem.utils.logger import logger

# Default LLM configuration constants.
# Used as fallbacks when config/env vars are not set or invalid.
DEFAULT_LLM_MAX_TOKENS = 500
DEFAULT_LLM_TIMEOUT_SECONDS = 30

_OPENAI_CLIENT = None
_ZHIPUAI_CLIENT = None
_BACKEND = None

try:
    from openai import OpenAI as _OpenAI

    _OPENAI_CLIENT = _OpenAI
    _BACKEND = "openai"
except ImportError:
    pass

if _BACKEND is None:
    try:
        from zhipuai import ZhipuAI as _ZhipuAI

        _ZHIPUAI_CLIENT = _ZhipuAI
        _BACKEND = "zhipuai"
    except ImportError:
        pass

_CJK_RANGES = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef" r"\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]"
)


def _env_or(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def _str_to_bool(val: Union[str, bool]) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes", "on")


class LLMClient:
    """LLM client wrapper supporting OpenAI and ZhipuAI backends."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
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
                self._resolve("llm.timeout", "CARRYMEM_LLM_TIMEOUT", config, default=str(DEFAULT_LLM_TIMEOUT_SECONDS))  # type: ignore[arg-type]
            )
        except (ValueError, TypeError):
            self._timeout = DEFAULT_LLM_TIMEOUT_SECONDS
        self._client = self._init_client()

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

    def _init_client(self):
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
        if _BACKEND == "zhipuai" and _ZHIPUAI_CLIENT is not None:
            try:
                return _ZHIPUAI_CLIENT(api_key=self._api_key)
            except (ImportError, ValueError) as e:
                logger.error("Failed to initialize ZhipuAI client: %s", e)
                return None
        logger.warning("No LLM backend available (openai/zhipuai not installed)")
        return None

    def is_available(self) -> bool:
        """Return True if the LLM backend client was initialized."""
        return self._client is not None

    def __repr__(self):
        key = self._api_key
        masked = key[:4] + "..." + key[-4:] if key and len(key) > 8 else "***"
        return f"LLMClient(backend={_BACKEND}, model={self._model}, api_key={masked}, available={self.is_available()})"

    def chat(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        """Send a chat completion request and return the response text, or None on failure."""
        if not self.is_available():
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
            if _BACKEND == "zhipuai":
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


__all__ = ["LLMClient"]
