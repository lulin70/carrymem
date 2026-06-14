"""Prompt delegation and LLM-powered features."""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from carrymem.adapters.base import MemoryEntry
from carrymem.core._lifecycle import StorageNotConfiguredError
from carrymem.constants import (
    CONTEXT_BUILD_DEFAULTS,
    SESSION_SUMMARIZER_LIMIT,
    AGGREGATE_MEMORIES_LIMIT,
)

if TYPE_CHECKING:
    from carrymem.scoring import RecallBudget

logger = logging.getLogger(__name__)


class PromptDelegateMixin:
    """Prompt building delegation and LLM-powered session summarization / aggregation."""

    def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = CONTEXT_BUILD_DEFAULTS["max_memories"],
        max_knowledge: int = CONTEXT_BUILD_DEFAULTS["max_knowledge"],
        max_rules: int = CONTEXT_BUILD_DEFAULTS["max_rules"],
        max_tokens: int = CONTEXT_BUILD_DEFAULTS["max_tokens_context"],
        language: str = "en",
    ) -> Dict[str, Any]:
        return self.prompt_builder.build_context(
            context=context,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_rules=max_rules,
            max_tokens=max_tokens,
            language=language,
        )

    def build_system_prompt(
        self,
        context: Optional[str] = None,
        max_memories: int = CONTEXT_BUILD_DEFAULTS["max_memories"],
        max_knowledge: int = CONTEXT_BUILD_DEFAULTS["max_knowledge"],
        max_rules: int = CONTEXT_BUILD_DEFAULTS["max_rules"],
        max_tokens: int = CONTEXT_BUILD_DEFAULTS["max_tokens_system_prompt"],
        language: str = "en",
    ) -> str:
        return self.prompt_builder.build_system_prompt(
            context=context,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_rules=max_rules,
            max_tokens=max_tokens,
            language=language,
        )

    def build_qa_prompt(
        self,
        question: str,
        max_memories: int = CONTEXT_BUILD_DEFAULTS["max_memories"],
        max_knowledge: int = CONTEXT_BUILD_DEFAULTS["max_knowledge"],
        max_tokens: int = CONTEXT_BUILD_DEFAULTS["max_tokens_qa_prompt"],
        language: str = "en",
        budget: Optional[RecallBudget] = None,
        include_question: bool = True,
    ) -> str:
        return self.prompt_builder.build_qa_prompt(
            question=question,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_tokens=max_tokens,
            language=language,
            budget=budget,
            include_question=include_question,
        )

    def summarize_session(
        self,
        session_id: str,
        language: str = "en",
        store: bool = True,
    ) -> Optional[Dict[str, Any]]:
        warnings.warn(
            "summarize_session() is experimental and requires LLM client. "
            "It will be integrated into CLI/MCP in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._adapter:
            raise StorageNotConfiguredError()

        from carrymem.layers.session_summarizer import SessionSummarizer

        if not hasattr(self, "_llm_client"):
            from carrymem.llm import LLMClient

            self._llm_client = LLMClient(config=self._config or {})
        summarizer = SessionSummarizer(llm_client=self._llm_client)

        session_memories = self.recall_memories(
            query="",
            limit=SESSION_SUMMARIZER_LIMIT,
            filters={"session_id": session_id, "include_superseded": True},
        )
        if not session_memories:
            return None

        summary_entry = summarizer.summarize_session(
            memories=session_memories,
            session_id=session_id,
            language=language,
        )
        if not summary_entry:
            return None

        if store:
            entry = MemoryEntry.from_dict(summary_entry)
            stored = self._adapter.remember(entry)
            return stored.to_dict()

        return summary_entry

    def aggregate_memories(
        self,
        memory_type: Optional[str] = None,
        language: str = "en",
        store: bool = True,
    ) -> List[Dict[str, Any]]:
        warnings.warn(
            "aggregate_memories() is experimental and requires LLM client. "
            "It will be integrated into CLI/MCP in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._adapter:
            raise StorageNotConfiguredError()

        from carrymem.layers.semantic_aggregator import SemanticAggregator

        if not hasattr(self, "_llm_client"):
            from carrymem.llm import LLMClient

            self._llm_client = LLMClient(config=self._config or {})
        embedding_fn = None
        if hasattr(self._adapter, "_embedding_model") and self._adapter._embedding_model:
            embedding_fn = lambda text: self._adapter._embedding_model.encode(text).tolist()

        if not embedding_fn:
            logger.warning("aggregate_memories requires vector search to be enabled (no embedding model found)")
            return []

        aggregator = SemanticAggregator(llm_client=self._llm_client, embedding_fn=embedding_fn)

        filters: Dict[str, Any] = {"include_superseded": False}
        if memory_type:
            filters["type"] = memory_type
        memories = self.recall_memories(query="", limit=AGGREGATE_MEMORIES_LIMIT, filters=filters)

        if not memories:
            return []

        results = aggregator.aggregate(memories=memories, language=language)

        if store:
            stored_results = []
            for r in results:
                try:
                    entry = MemoryEntry.from_dict(r)
                    stored = self._adapter.remember(entry)
                    stored_results.append(stored.to_dict())
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning("Failed to store aggregated memory: %s", e)
            return stored_results

        return results
