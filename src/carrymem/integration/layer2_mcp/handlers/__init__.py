"""MCP Tool handlers for CarryMem — compatibility entry point (TD-039).

This package was split from the original monolithic ``handlers.py`` into
domain-specific sub-modules:

- ``_base``:   shared utilities, ``OperationLevel``, decorator, constants
- ``read``:    classification, recall, and profile queries (READ)
- ``write``:   memory persistence, consolidation, summarization (WRITE/DELETE)
- ``graph``:   multi-hop traversal and impact analysis (READ)
- ``rule``:    rule CRUD, matching, injection, promotion (READ/WRITE/DELETE)
- ``system``:  identity, onboarding, health diagnostics (READ)

Public API is fully backward compatible with the original ``handlers.py``:
``Handlers``, ``OperationLevel``, ``handler_map``, all ``handle_*``
functions, and all ``_``-prefixed helpers are re-exported here.

3+3+3+2+1 Optional Mode:
  Core handlers: classify_message, get_classification_schema, batch_classify
  Storage handlers: classify_and_remember, recall_memories, forget_memory
  Knowledge handlers: index_knowledge, recall_from_knowledge, recall_all
  Profile handlers: declare_preference, get_memory_profile
  Prompt handlers: get_system_prompt
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional, Union

# ── Shared utilities and constants (re-exported) ───────────────────
from ._base import (
    _MAX_KNOWLEDGE,
    _MAX_LIMIT,
    _MAX_MEMORIES,
    _SAFE_ERROR_TYPES,
    _TOOL_OPERATION_LEVELS,
    CLASSIFICATION_SCHEMA,
    CORE_TOOL_NAMES,
    OPTIONAL_TOOL_NAMES,
    TOOL_NAMES,
    OperationLevel,
    _build_summary,
    _clamp,
    _format_memory_entry,
    _safe_error,
    _validate_input,
    _validate_query_input,
    _version,
    mcp_tool_handler,
)

# ── Domain handlers (re-exported) ──────────────────────────────────
from .graph import (
    handle_get_memory_impact,
    handle_query_graph,
    handle_shortest_path,
)
from .read import (
    handle_batch_classify,
    handle_classify_message,
    handle_get_classification_schema,
    handle_get_memory_profile,
    handle_get_system_prompt,
    handle_mce_status,
    handle_recall_all,
    handle_recall_from_knowledge,
    handle_recall_memories,
)
from .rule import (
    handle_add_rule,
    handle_delete_rule,
    handle_inject_rules,
    handle_list_rules,
    handle_match_rules,
    handle_my_rules,
    handle_promote_rules,
    handle_suggest_rules,
    handle_update_rule,
)
from .system import (
    handle_health_check,
    handle_my_profile,
    handle_onboard,
)
from .write import (
    handle_classify_and_remember,
    handle_consolidate_memories,
    handle_declare_preference,
    handle_forget_memory,
    handle_index_knowledge,
    handle_schedule_consolidation,
    handle_stop_consolidation,
    handle_summarize_and_store,
)

# ── Handler registry ───────────────────────────────────────────────

handler_map = {
    "classify_message": (handle_classify_message, "engine"),
    "get_classification_schema": (handle_get_classification_schema, "engine"),
    "batch_classify": (handle_batch_classify, "engine"),
    # mce_status is an internal diagnostic tool, available via tools/call
    # but NOT listed in TOOLS (tools.py), so MCP clients won't discover it
    # via tools/list. Kept for backward compatibility and debugging.
    "mce_status": (handle_mce_status, "engine"),
    "classify_and_remember": (handle_classify_and_remember, "carrymem"),
    "recall_memories": (handle_recall_memories, "carrymem"),
    "forget_memory": (handle_forget_memory, "carrymem"),
    "index_knowledge": (handle_index_knowledge, "carrymem"),
    "recall_from_knowledge": (handle_recall_from_knowledge, "carrymem"),
    "recall_all": (handle_recall_all, "carrymem"),
    "declare_preference": (handle_declare_preference, "carrymem"),
    "get_memory_profile": (handle_get_memory_profile, "carrymem"),
    "get_system_prompt": (handle_get_system_prompt, "carrymem"),
    "summarize_and_store": (handle_summarize_and_store, "carrymem"),
    "consolidate_memories": (handle_consolidate_memories, "carrymem"),
    "schedule_consolidation": (handle_schedule_consolidation, "carrymem"),
    "stop_consolidation": (handle_stop_consolidation, "carrymem"),
    "add_rule": (handle_add_rule, "rule_engine"),
    "list_rules": (handle_list_rules, "rule_engine"),
    "match_rules": (handle_match_rules, "rule_engine"),
    "inject_rules": (handle_inject_rules, "rule_engine"),
    "my_rules": (handle_my_rules, "rule_engine"),
    "delete_rule": (handle_delete_rule, "rule_engine"),
    "suggest_rules": (handle_suggest_rules, "rule_engine"),
    "promote_rules": (handle_promote_rules, "rule_engine"),
    "update_rule": (handle_update_rule, "rule_engine"),
    "my_profile": (handle_my_profile, "carrymem"),
    "onboard": (handle_onboard, "carrymem"),
    "health_check": (handle_health_check, "carrymem"),
    "query_graph": (handle_query_graph, "carrymem"),
    "shortest_path": (handle_shortest_path, "carrymem"),
    "get_memory_impact": (handle_get_memory_impact, "carrymem"),
}

_TARGET_MAP = {
    "engine": lambda self: self._engine,
    "carrymem": lambda self: self._carrymem,
    "rule_engine": lambda self: self._rule_engine,
}


class Handlers:
    """CarryMem MCP Handlers — 3+3+3+2+1 optional mode."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        data_path: Optional[str] = None,
        storage: str = "sqlite",
        vault_path: Optional[str] = None,
        namespace: str = "default",
        default_user_id: Optional[str] = None,
    ):
        from carrymem.adapters.obsidian_adapter import ObsidianAdapter
        from carrymem.carrymem import CarryMem

        knowledge_adapter = None
        if vault_path:
            knowledge_adapter = ObsidianAdapter(vault_path)

        db_path = data_path
        if db_path and os.path.isdir(db_path):
            db_path = os.path.join(db_path, "carrymem.db")

        self._carrymem = CarryMem(
            storage=storage,
            db_path=db_path,
            knowledge_adapter=knowledge_adapter,
            namespace=namespace,
        )
        self._engine = self._carrymem.engine

        from carrymem.rules import RuleEngine

        rule_db_path: Optional[str] = getattr(self._carrymem._adapter, "_db_path", None) or getattr(
            self._carrymem._adapter, "db_path", None
        )
        self._rule_engine = RuleEngine(db_path=rule_db_path)

        self._default_user_id = default_user_id

        # TD-035: AccessPolicy integration into the MCP tool invocation chain.
        # ────────────────────────────────────────────────────────────────────
        # The CarryMem facade already enforces write/delete permissions via
        # ``_check_write_permission`` / ``_check_delete_permission`` in
        # ``core/_memory_crud.py``, but only when ``self._access_policy`` is
        # non-None. Without wiring the policy here, MCP ``handle_tool`` calls
        # would silently bypass access control (single-user mode).
        #
        # Two scenarios enable policy enforcement (fail-closed for writes/deletes):
        #
        #   1. Explicit ``default_user_id`` provided → owner = default_user_id.
        #      Every write/delete tool call without a matching user_id will raise
        #      SecurityError(CM-403). This is the primary multi-user path.
        #
        #   2. Multi-namespace mode (``namespace != "default"``) with no explicit
        #      owner → fall back to namespace name as the owner_id. This guarantees
        #      that a non-default namespace cannot be mutated anonymously — a
        #      client must pass ``user_id=<namespace>`` (or the namespace itself)
        #      to perform writes. This is the minimum multi-tenant safety net.
        #
        # In single-user mode (``namespace == "default"`` and no ``default_user_id``),
        # NO policy is set, preserving the existing behavior where writes without
        # user_id are allowed (characterization testing principle: do not break
        # existing single-user callers).
        from carrymem.security.permissions import AccessPolicy

        if default_user_id is not None:
            self._carrymem.access_policy = AccessPolicy(owner_id=default_user_id)
        elif namespace != "default":
            # Multi-namespace mode without an explicit owner — treat the
            # namespace itself as the resource owner so anonymous writes are
            # rejected. Mirror the namespace into _default_user_id so the
            # existing P0-1 injection logic in handle_tool will supply it
            # automatically for write/delete tools.
            self._carrymem.access_policy = AccessPolicy(owner_id=namespace)
            self._default_user_id = namespace

    # Tools that perform write/delete operations and need user_id injection
    # for access-control enforcement (P0-1 fix).
    _WRITE_DELETE_TOOLS = frozenset(
        {
            "classify_and_remember",
            "forget_memory",
            "declare_preference",
        }
    )

    # Tools that operate on rule_engine target but also need the CarryMem
    # instance for memory recall (P0-2 fix).
    _CARRYMEM_INJECTION_TOOLS = frozenset(
        {
            "suggest_rules",
            "promote_rules",
        }
    )

    # ── TD-044: Operation level classification ───────────────────

    @staticmethod
    def _normalize_level(level: Optional[Union[OperationLevel, str]]) -> Optional[OperationLevel]:
        """Normalize a level argument to ``OperationLevel`` or ``None``.

        Accepts an ``OperationLevel`` instance or its string value
        (e.g. ``"read"``, ``"WRITE"``). Raises ``ValueError`` for unknown
        level strings.
        """
        if level is None:
            return None
        if isinstance(level, OperationLevel):
            return level
        normalized = str(level).strip().lower()
        try:
            return OperationLevel(normalized)
        except ValueError as e:
            valid = ", ".join(repr(op_level.value) for op_level in OperationLevel)
            raise ValueError(f"Unknown operation level: {level!r}. Valid levels: {valid}") from e

    @classmethod
    def get_tool_level(cls, tool_name: str) -> Optional[OperationLevel]:
        """Return the :class:`OperationLevel` for ``tool_name``, or ``None``.

        Returns ``None`` for tools that are not registered in
        ``_TOOL_OPERATION_LEVELS`` (e.g. unknown tool names).
        """
        return _TOOL_OPERATION_LEVELS.get(tool_name)

    @classmethod
    def list_tools(
        cls,
        level: Optional[Union[OperationLevel, str]] = None,
    ) -> List[Dict[str, Any]]:
        """List MCP tools, optionally filtered by operation level (TD-044).

        Args:
            level: If provided, return only tools at the given
                :class:`OperationLevel` (or its string value, e.g. ``"read"``).
                If ``None``, return all public tools with their level annotation.

        Returns:
            List of dicts sorted by tool name, each containing:
            ``{"name": str, "level": OperationLevel, "target": str}``.
            The ``target`` field is the handler target key (``"engine"``,
            ``"carrymem"``, or ``"rule_engine"``).
        """
        normalized = cls._normalize_level(level)
        result: List[Dict[str, Any]] = []
        # TOOL_NAMES is the canonical set of 31 public tools (excludes
        # the internal mce_status diagnostic).
        for name in sorted(TOOL_NAMES):
            op_level = _TOOL_OPERATION_LEVELS.get(name)
            if op_level is None:
                # Invariant enforced by tests — every public tool must have
                # a level. Skip defensively rather than crash at runtime.
                continue
            if normalized is not None and op_level != normalized:
                continue
            entry = handler_map.get(name)
            target_key = entry[1] if entry is not None else None
            result.append(
                {
                    "name": name,
                    "level": op_level,
                    "target": target_key,
                }
            )
        return result

    @classmethod
    def count_tools_by_level(cls) -> Dict[str, int]:
        """Return a count of public tools at each :class:`OperationLevel`.

        Useful for dashboards and invariant checks. Keys are the
        ``OperationLevel`` string values (``"read"``, ``"write"``,
        ``"delete"``, ``"admin"``).
        """
        counts: Dict[str, int] = {level.value: 0 for level in OperationLevel}
        for name in TOOL_NAMES:
            op_level = _TOOL_OPERATION_LEVELS.get(name)
            if op_level is not None:
                counts[op_level.value] += 1
        return counts

    async def handle_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Dispatch an MCP tool call to its handler, running it in an executor."""
        entry = handler_map.get(tool_name)
        if not entry:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(handler_map.keys()),
            }

        handler_func, target_key = entry
        target = _TARGET_MAP[target_key](self)

        # Build arguments with injected context (do not mutate caller's dict)
        injected_args = arguments or {}

        # P0-1: Inject user_id for write/delete handlers when an access policy
        # is configured.  In single-user mode (no policy), user_id is ignored.
        if tool_name in self._WRITE_DELETE_TOOLS and "user_id" not in injected_args:
            if self._default_user_id is not None:
                injected_args = {**injected_args, "user_id": self._default_user_id}

        # P0-2: Inject _carrymem for rule_engine handlers that need memory recall
        if tool_name in self._CARRYMEM_INJECTION_TOOLS:
            injected_args = {**injected_args, "_carrymem": self._carrymem}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: handler_func(target, injected_args))
            return {"success": True, "data": result}
        except Exception as e:
            # NOTE: Broad exception in async MCP handler wrapper is intentional to catch
            # all errors and return standardized error responses to MCP clients.
            return {"success": False, "error": _safe_error(e)}

    def cleanup(self):
        """Cleanup resources (synchronous — safe to call from sync or async code)."""
        if self._carrymem:
            self._carrymem.close()


__all__ = [
    # Public class and registry
    "Handlers",
    "handler_map",
    "OperationLevel",
    # Shared utilities and constants
    "_TOOL_OPERATION_LEVELS",
    "_TARGET_MAP",
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
    # Read handlers
    "handle_classify_message",
    "handle_get_classification_schema",
    "handle_batch_classify",
    "handle_mce_status",
    "handle_recall_memories",
    "handle_recall_from_knowledge",
    "handle_recall_all",
    "handle_get_memory_profile",
    "handle_get_system_prompt",
    # Write handlers
    "handle_classify_and_remember",
    "handle_forget_memory",
    "handle_index_knowledge",
    "handle_declare_preference",
    "handle_summarize_and_store",
    "handle_consolidate_memories",
    "handle_schedule_consolidation",
    "handle_stop_consolidation",
    # Graph handlers
    "handle_query_graph",
    "handle_shortest_path",
    "handle_get_memory_impact",
    # Rule handlers
    "handle_add_rule",
    "handle_list_rules",
    "handle_match_rules",
    "handle_inject_rules",
    "handle_my_rules",
    "handle_delete_rule",
    "handle_suggest_rules",
    "handle_promote_rules",
    "handle_update_rule",
    # System handlers
    "handle_my_profile",
    "handle_onboard",
    "handle_health_check",
]
