"""Shared utilities, constants, and decorator for MCP tool handlers.

This module is the foundation of the ``handlers`` package and must not
import from sibling handler modules to avoid circular dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional

from carrymem.__version__ import __version__ as _version
from carrymem.core.recall_thresholds import compute_suggested_action
from carrymem.errors import SecurityError

from ..tools import (
    CLASSIFICATION_SCHEMA,
    CORE_TOOL_NAMES,
    OPTIONAL_TOOL_NAMES,
    TOOL_NAMES,
)

_validator: Optional[InputValidator] = None
try:
    from carrymem.security.input_validator import InputValidator

    _validator = InputValidator(strict_mode=True)
except ImportError:
    import logging

    logging.getLogger(__name__).warning("InputValidator not available — input validation disabled")

_SAFE_ERROR_TYPES = {
    "StorageNotConfiguredError": "storage_not_configured",
    "KnowledgeNotConfiguredError": "knowledge_not_configured",
    "ValueError": "invalid_input",
    "ValidationError": "invalid_input",
    "SecurityError": "access_denied",
}

_MAX_LIMIT = 1000
_MAX_MEMORIES = 50
_MAX_KNOWLEDGE = 20


class OperationLevel(str, Enum):
    """Operation level for MCP tools (TD-044).

    Levels form a monotonically increasing privilege hierarchy:
    READ < WRITE < DELETE < ADMIN. Use ``list_tools(level)`` on the
    :class:`Handlers` class to filter tools by level.

    - READ:   query, list, get, search, stats — no side effects on stored state.
    - WRITE:  remember, classify_and_remember, add, update, index, consolidate —
              mutates memories, rules, or indices.
    - DELETE: forget, delete_* — removes stored state.
    - ADMIN:  schedule/stop background tasks, gateway admin ops.
    """

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


# TD-044: Operation level for every MCP tool registered in ``handler_map``.
# Covers all 31 public tools in ``TOOLS`` (see tools.py) plus the internal
# ``mce_status`` diagnostic. The invariant "every handler_map entry has a
# level" is enforced by ``tests/test_mcp_operation_levels_td044.py``.
_TOOL_OPERATION_LEVELS: Dict[str, OperationLevel] = {
    # ── Core (classification only, no persistence) ──
    "classify_message": OperationLevel.READ,
    "get_classification_schema": OperationLevel.READ,
    "batch_classify": OperationLevel.READ,
    # ── Storage (recall is READ; classify_and_remember is WRITE; forget is DELETE) ──
    "classify_and_remember": OperationLevel.WRITE,
    "recall_memories": OperationLevel.READ,
    "forget_memory": OperationLevel.DELETE,
    # ── Knowledge (index builds/refreshes; recall is READ) ──
    "index_knowledge": OperationLevel.WRITE,
    "recall_from_knowledge": OperationLevel.READ,
    "recall_all": OperationLevel.READ,
    # ── Profile ──
    "declare_preference": OperationLevel.WRITE,
    "get_memory_profile": OperationLevel.READ,
    # ── Prompt (summarize_and_store triggers a follow-up store) ──
    "get_system_prompt": OperationLevel.READ,
    "summarize_and_store": OperationLevel.WRITE,
    # ── Consolidation (consolidate may mutate memories; schedule/stop are ADMIN) ──
    "consolidate_memories": OperationLevel.WRITE,
    "schedule_consolidation": OperationLevel.ADMIN,
    "stop_consolidation": OperationLevel.ADMIN,
    # ── Rules ──
    "add_rule": OperationLevel.WRITE,
    "list_rules": OperationLevel.READ,
    "match_rules": OperationLevel.READ,
    "inject_rules": OperationLevel.READ,
    "my_rules": OperationLevel.READ,
    "delete_rule": OperationLevel.DELETE,
    "suggest_rules": OperationLevel.READ,
    "promote_rules": OperationLevel.WRITE,
    "update_rule": OperationLevel.WRITE,
    # ── Identity / diagnostic ──
    "my_profile": OperationLevel.READ,
    "onboard": OperationLevel.READ,
    "health_check": OperationLevel.READ,
    "mce_status": OperationLevel.READ,
    # ── Graph (all read-only traversal/analysis) ──
    "query_graph": OperationLevel.READ,
    "shortest_path": OperationLevel.READ,
    "get_memory_impact": OperationLevel.READ,
}


def _validate_input(value: str, field: str = "input") -> str:
    if _validator is None:
        return value
    return _validator.validate_content(value, field_name=field)


def _validate_query_input(value: str) -> str:
    if _validator is None:
        return value
    return _validator.validate_query(value)


def _safe_error(e: Exception) -> str:
    type_name = type(e).__name__
    if type_name in _SAFE_ERROR_TYPES:
        return _SAFE_ERROR_TYPES[type_name]
    return "internal_error"


def _clamp(value: int, min_val: int, max_val: int) -> int:
    return max(min_val, min(value, max_val))


def mcp_tool_handler(func):
    """Wrap an MCP tool handler with standardized error handling.

    Handlers receive (target_object, arguments) and return a dict.
    On exception: wraps as {"success": False, "error": ...}.
    On success: returns the handler's result unchanged (preserves original format).

    Note: ``SecurityError`` (access denied) is re-raised so the outer
    ``handle_tool`` wrapper can report it at the top level — this ensures
    clients can distinguish authorization failures from successful operations.
    """

    @wraps(func)
    def wrapper(target, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the wrapped handler, converting exceptions into an error dict."""
        try:
            return func(target, arguments)  # type: ignore[no-any-return]
        except SecurityError:
            # Re-raise so handle_tool reports {"success": False, "error": "access_denied"}
            raise
        except Exception as e:
            return {"success": False, "error": _safe_error(e)}

    return wrapper


def _format_memory_entry(match: Dict[str, Any], original_message: str) -> Dict[str, Any]:
    """Convert a raw engine match dict to standardized MemoryEntry v1.0."""
    from uuid import uuid4

    mem_type = match.get("memory_type") or match.get("type", "unknown")
    confidence = match.get("confidence", 0.0)
    tier = match.get("tier", 2)

    return {
        "id": f"mce_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
        "type": mem_type,
        "content": match.get("content") or original_message[:200],
        "confidence": round(confidence, 4),
        "tier": tier,
        "source_layer": match.get("source", "unknown"),
        "reasoning": match.get("reasoning", ""),
        "suggested_action": compute_suggested_action(confidence),
        "metadata": {
            "original_message": original_message,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        },
    }


def _build_summary(entries: List[Dict[str, Any]], llm_calls: int = 0) -> Dict[str, Any]:
    """Build summary section of MemoryEntry output."""
    by_type: Dict[str, int] = {}
    by_tier: Dict[int, int] = {}
    total_confidence = 0.0

    for entry in entries:
        by_type[entry["type"]] = by_type.get(entry["type"], 0) + 1
        by_tier[entry["tier"]] = by_tier.get(entry["tier"], 0) + 1
        total_confidence += entry["confidence"]

    return {
        "total_entries": len(entries),
        "by_type": by_type,
        "by_tier": by_tier,
        "avg_confidence": round(total_confidence / max(len(entries), 1), 4),
        "filtered_count": 0,
        "llm_calls_used": llm_calls,
    }


__all__ = [
    "OperationLevel",
    "_TOOL_OPERATION_LEVELS",
    "_validate_input",
    "_validate_query_input",
    "_safe_error",
    "_clamp",
    "mcp_tool_handler",
    "_format_memory_entry",
    "_build_summary",
    "_SAFE_ERROR_TYPES",
    "_MAX_LIMIT",
    "_MAX_MEMORIES",
    "_MAX_KNOWLEDGE",
    "_version",
    "CLASSIFICATION_SCHEMA",
    "CORE_TOOL_NAMES",
    "OPTIONAL_TOOL_NAMES",
    "TOOL_NAMES",
]
