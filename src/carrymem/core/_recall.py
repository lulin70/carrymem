"""Recall operations: memories, aggregated, timeline, knowledge, all."""

import logging
from typing import Any, Dict, List, Optional

from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.constants import DEFAULT_RECALL_LIMIT, RULE_MATCH_LIMIT_CAP
from carrymem.core._lifecycle import KnowledgeNotConfiguredError, StorageNotConfiguredError
from carrymem.types import RecallAllResult, StoredMemoryDict
from carrymem.utils.validators import validate_limit, validate_query

logger = logging.getLogger(__name__)


class RecallMixin:
    """Recall / search operations across memories, knowledge base, and rules."""

    def index_knowledge(self) -> Dict[str, Any]:
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        if isinstance(self._knowledge_adapter, ObsidianAdapter):
            return self._knowledge_adapter.index_vault()

        return {"error": "Knowledge adapter does not support indexing"}

    def recall_from_knowledge(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> List[Dict[str, Any]]:
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        results = self._knowledge_adapter.recall(query, filters=filters, limit=limit)
        if isinstance(results, list) and results and isinstance(results[0], dict):
            return results  # type: ignore[return-value]
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in results]  # type: ignore[misc]

    def recall_all(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        memory_results = []
        knowledge_results = []
        rule_results = []

        if include_rules:
            try:
                rule_engine = self.rule_engine
                matches = rule_engine.match(query, limit=min(limit, RULE_MATCH_LIMIT_CAP), increment_count=False)
                rule_results = [
                    {
                        "rule_id": m.rule.id,
                        "trigger": m.rule.trigger,
                        "action": m.rule.action,
                        "rule_type": m.rule.rule_type,
                        "override": m.rule.override,
                        "score": m.score,
                        "match_type": m.match_type,
                    }
                    for m in matches
                ]
            except (ImportError, KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Rule engine failed for recall_all: %s", e)
                rule_results = []

        if self._adapter:
            try:
                memory_results = self.recall_memories(query=query, filters=filters, limit=limit, namespaces=namespaces)
            except (KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to recall memories for prompt: %s", e)
                memory_results = []

        if self._knowledge_adapter:
            try:
                knowledge_results = self.recall_from_knowledge(query=query, filters=filters, limit=limit)
            except (KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to recall from knowledge base: %s", e)
                knowledge_results = []

        return {
            "rules": rule_results,
            "memories": memory_results,
            "knowledge": knowledge_results,
            "rule_count": len(rule_results),
            "memory_count": len(memory_results),
            "knowledge_count": len(knowledge_results),
            "total_count": len(rule_results) + len(memory_results) + len(knowledge_results),
            "namespace": self._namespace,
            "priority": "rules > memory > knowledge",
        }

    def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_query(query or "")
        validate_limit(limit)
        if isinstance(self._adapter, SQLiteAdapter) and namespaces:
            results = self._adapter.recall(
                query or "",
                filters=filters,
                limit=limit,
                namespaces=namespaces,
                update_access=update_access,
            )
        else:
            results = self._adapter.recall(query or "", filters=filters, limit=limit, update_access=update_access)
        return [r.to_dict() for r in results]

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemoryDict]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not hasattr(self._adapter, "recall_aggregated"):
            raise NotImplementedError("Adapter does not support recall_aggregated")

        result = self._adapter.recall_aggregated(memory_type=memory_type, limit_per_type=limit_per_type)
        return {k: [r.to_dict() for r in v] for k, v in result.items()}

    def recall_timeline(
        self,
        topic: str,
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not hasattr(self._adapter, "recall_timeline"):
            raise NotImplementedError("Adapter does not support recall_timeline")

        results = self._adapter.recall_timeline(topic=topic, limit=limit)
        return [r.to_dict() for r in results]
