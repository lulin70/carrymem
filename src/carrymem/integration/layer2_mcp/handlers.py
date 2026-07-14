"""
MCP Tool handlers for CarryMem.

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
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional

from carrymem.__version__ import __version__ as _version

from .tools import (
    CLASSIFICATION_SCHEMA,
    CORE_TOOL_NAMES,
    OPTIONAL_TOOL_NAMES,
    TOOL_NAMES,
)

_validator: Optional[InputValidator] = None
try:
    from carrymem.security.input_validator import InputValidator

    _validator = InputValidator(strict_mode=False)
except ImportError:
    import logging

    logging.getLogger(__name__).warning("InputValidator not available — input validation disabled")

_SAFE_ERROR_TYPES = {
    "StorageNotConfiguredError": "storage_not_configured",
    "KnowledgeNotConfiguredError": "knowledge_not_configured",
    "ValueError": "invalid_input",
    "ValidationError": "invalid_input",
}

_MAX_LIMIT = 1000
_MAX_MEMORIES = 50
_MAX_KNOWLEDGE = 20


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
    """

    @wraps(func)
    def wrapper(target, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the wrapped handler, converting exceptions into an error dict."""
        try:
            return func(target, arguments)  # type: ignore[no-any-return]
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
        "suggested_action": ("store" if confidence > 0.5 else ("defer" if confidence > 0.3 else "ignore")),
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


def handle_classify_message(engine, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a single message into memory types without storing it."""
    message = arguments.get("message", "")
    context = arguments.get("context")

    if not message.strip():
        return {
            "schema_version": "1.0.0",
            "should_remember": False,
            "entries": [],
            "summary": {"total_entries": 0},
            "engine_info": {"mode": "classification_only"},
            "error": "Empty message provided",
        }

    try:
        message = _validate_input(message, "message")
        if context:
            context = _validate_input(context, "context")
        result = engine.process_message(message, context)
        matches = result.get("matches", [])
        processing_time = result.get("processing_time", 0)

        entries = [_format_memory_entry(m, message) for m in matches]

        return {
            "schema_version": "1.0.0",
            "should_remember": len(entries) > 0,
            "entries": entries,
            "summary": _build_summary(entries),
            "engine_info": {
                "mode": "classification_only",
                "processing_time_ms": round(processing_time * 1000, 2) if processing_time else None,
            },
        }
    # NOTE: Broad exception in MCP handler is intentional to catch all errors
    # and return standardized error responses to MCP clients. This prevents
    # raw exceptions from breaking the MCP protocol.
    except Exception as e:
        return {
            "schema_version": "1.0.0",
            "should_remember": False,
            "entries": [],
            "summary": {"total_entries": 0},
            "engine_info": {"mode": "classification_only"},
            "error": _safe_error(e),
        }


def handle_get_classification_schema(engine, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return the MCE classification schema as JSON or markdown."""
    fmt = arguments.get("format", "json")

    if fmt == "markdown":
        lines = [
            "# MCE Classification Schema v1.0",
            "",
            f"**Engine Version**: {CLASSIFICATION_SCHEMA['engine_version']}",
            f"**Mode**: {CLASSIFICATION_SCHEMA['mode']}",
            "",
            "## Memory Types (7)",
            "",
        ]
        for mt in CLASSIFICATION_SCHEMA["memory_types"]:
            lines.append(f"### {mt['id']} ({mt['label_en']} / {mt['label_zh']})")  # type: ignore[index]
            lines.append(f"- **Description**: {mt['description']}")  # type: ignore[index]
            lines.append(f"- **Examples**: {', '.join(mt['examples'])}")  # type: ignore[index]
            lines.append(f"- **Default Tier**: T{mt['default_tier']}")  # type: ignore[index]
            lines.append("- **Downstream Mapping**:")
            for ds, cat in mt["downstream_mapping"].items():  # type: ignore[index]
                lines.append(f"  - {ds}: `{cat}`")
            lines.append("")
        return {"schema": "\n".join(lines), "format": "markdown"}

    return {"schema": CLASSIFICATION_SCHEMA, "format": "json"}


def handle_batch_classify(engine, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Classify multiple messages in a single batch and return per-message results."""
    messages_data = arguments.get("messages", [])

    if not messages_data:
        return {
            "results": [],
            "summary": {"total_messages": 0, "total_entries": 0},
            "error": "No messages provided",
        }

    results = []
    total_entries = 0

    for msg_item in messages_data:
        msg_text = msg_item.get("message", "")
        msg_context = msg_item.get("context")
        msg_result = handle_classify_message(engine, {"message": msg_text, "context": msg_context})
        results.append(msg_result)
        total_entries += len(msg_result.get("entries", []))

    return {
        "results": results,
        "summary": {
            "total_messages": len(messages_data),
            "total_entries": total_entries,
            "messages_with_memories": sum(1 for r in results if r.get("should_remember")),
        },
    }


def handle_mce_status(engine, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return the MCE engine status (mode, version, capabilities, uptime)."""
    status = {
        "status": "active",
        "mode": "3+3_optional",
        "version": _version,
        "schema_version": "1.0.0",
        "capabilities": {
            "memory_types": 7,
            "storage_tiers": 4,
            "available_tools": list(TOOL_NAMES),
            "core_tools": list(CORE_TOOL_NAMES),
            "optional_tools": list(OPTIONAL_TOOL_NAMES),
        },
        "uptime_seconds": round(time.time() - getattr(engine, "_start_time", time.time()), 1),
    }
    return status


@mcp_tool_handler
def handle_classify_and_remember(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a message and persist the resulting memory entries."""
    message = arguments.get("message", "")
    context = arguments.get("context")
    user_id = arguments.get("user_id")

    if not message.strip():
        return {"error": "Empty message provided"}

    message = _validate_input(message, "message")
    if context:
        context = _validate_input(context, "context")
    ctx = None
    if context:
        ctx = {"ai_reply": context}

    result = carrymem.classify_and_remember(message, context=ctx, user_id=user_id)
    return result  # type: ignore[no-any-return]


@mcp_tool_handler
def handle_recall_memories(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Recall memories matching a query with optional filters and limit."""
    query = arguments.get("query")
    filters = arguments.get("filters")
    limit = _clamp(int(arguments.get("limit", 20)), 1, _MAX_LIMIT)

    if query:
        query = _validate_query_input(query)
    results = carrymem.recall_memories(query=query, filters=filters, limit=limit)
    return {"memories": results, "total": len(results)}


@mcp_tool_handler
def handle_forget_memory(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a memory entry by its memory_id."""
    memory_id = arguments.get("memory_id", "")
    user_id = arguments.get("user_id")

    if not memory_id:
        return {"error": "Missing required field: memory_id"}

    memory_id = _validate_input(memory_id, "memory_id")
    deleted = carrymem.forget_memory(memory_id, user_id=user_id)
    return {"deleted": deleted, "memory_id": memory_id}


@mcp_tool_handler
def handle_index_knowledge(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Build the knowledge index and return indexing stats."""
    result = carrymem.index_knowledge()
    return {"indexed": True, "stats": result}


@mcp_tool_handler
def handle_recall_from_knowledge(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Recall knowledge notes matching a query."""
    query = arguments.get("query", "")
    filters = arguments.get("filters")
    limit = _clamp(int(arguments.get("limit", 20)), 1, _MAX_LIMIT)

    if not query.strip():
        return {"error": "Missing required field: query"}

    query = _validate_query_input(query)
    results = carrymem.recall_from_knowledge(query=query, filters=filters, limit=limit)
    return {"notes": results, "total": len(results), "source": "knowledge"}


@mcp_tool_handler
def handle_recall_all(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Recall both memories and knowledge matching a query."""
    query = arguments.get("query", "")
    filters = arguments.get("filters")
    limit = _clamp(int(arguments.get("limit", 20)), 1, _MAX_LIMIT)

    if not query.strip():
        return {"error": "Missing required field: query"}

    query = _validate_query_input(query)
    result = carrymem.recall_all(query=query, filters=filters, limit=limit)
    return result  # type: ignore[no-any-return]


@mcp_tool_handler
def handle_declare_preference(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Explicitly declare a preference/fact/decision from a message."""
    message = arguments.get("message", "")
    user_id = arguments.get("user_id")

    if not message.strip():
        return {"error": "Missing required field: message"}

    message = _validate_input(message, "message")
    result = carrymem.declare(message, user_id=user_id)
    return result  # type: ignore[no-any-return]


@mcp_tool_handler
def handle_get_memory_profile(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return the user's consolidated memory profile."""
    profile = carrymem.get_memory_profile()
    return profile  # type: ignore[no-any-return]


@mcp_tool_handler
def handle_get_system_prompt(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Build a ready-to-use system prompt from memories and knowledge."""
    context = arguments.get("context")
    max_memories = _clamp(int(arguments.get("max_memories", 10)), 1, _MAX_MEMORIES)
    max_knowledge = _clamp(int(arguments.get("max_knowledge", 5)), 1, _MAX_KNOWLEDGE)
    language = arguments.get("language", "en")
    if language not in ("en", "zh", "ja"):
        language = "en"

    prompt = carrymem.build_system_prompt(
        context=context,
        max_memories=max_memories,
        max_knowledge=max_knowledge,
        language=language,
    )
    return {"system_prompt": prompt, "language": language}


@mcp_tool_handler
def handle_summarize_and_store(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a session's memories and store the summary."""
    session_id = arguments.get("session_id", "")
    max_tokens = _clamp(int(arguments.get("max_tokens", 2000)), 100, 8000)
    namespace = arguments.get("namespace", "default")

    if not session_id:
        return {"error": "session_id is required"}

    memories = carrymem.recall_memories(
        query="",
        limit=100,
        filters={"session_id": session_id},
    )

    if not memories:
        return {
            "action": "no_content",
            "session_id": session_id,
            "message": "No memories found for this session. Nothing to summarize.",
        }

    content_parts = []
    total_len = 0
    for m in memories:
        text = m.get("raw_text", "") or m.get("content", "")
        if total_len + len(text) > max_tokens * 4:
            break
        content_parts.append(f"- [{m.get('type', 'unknown')}] {text}")
        total_len += len(text)

    content_to_summarize = "\n".join(content_parts)

    return {
        "action": "summarize",
        "session_id": session_id,
        "namespace": namespace,
        "content": content_to_summarize,
        "memory_count": len(content_parts),
        "instruction": (
            "Summarize the above conversation memories concisely. "
            "Focus on: 1) User preferences, 2) Decisions made, 3) Key facts. "
            "Then call classify_and_remember with the summary, "
            "setting message type context to 'session_summary'."
        ),
    }


@mcp_tool_handler
def handle_consolidate_memories(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run memory consolidation (phases P1/P2), optionally as a dry run."""
    dry_run = arguments.get("dry_run", True)
    run_p1 = arguments.get("run_p1", True)
    run_p2 = arguments.get("run_p2", True)
    result = carrymem.consolidate(dry_run=dry_run, run_p1=run_p1, run_p2=run_p2)
    return result  # type: ignore[no-any-return]


@mcp_tool_handler
def handle_schedule_consolidation(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule recurring memory consolidation at a given interval."""
    interval = arguments.get("interval_hours", 1.0)
    dry_run = arguments.get("dry_run", False)
    run_p1 = arguments.get("run_p1", True)
    run_p2 = arguments.get("run_p2", False)
    result = carrymem.schedule_consolidation(interval_hours=interval, dry_run=dry_run, run_p1=run_p1, run_p2=run_p2)
    return result  # type: ignore[no-any-return]


@mcp_tool_handler
def handle_stop_consolidation(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Stop any scheduled memory consolidation."""
    result = carrymem.stop_consolidation()
    return result  # type: ignore[no-any-return]


def handle_add_rule(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new rule to the rules engine."""
    try:
        trigger = _validate_input(args.get("trigger", ""), "trigger")
        action = _validate_input(args.get("action", ""), "action")
        scope = args.get("scope", "personal")
        rule_type = args.get("rule_type", "always")
        override = args.get("override", False)

        rule = engine.add_rule(
            trigger=trigger,
            action=action,
            scope=scope,
            rule_type=rule_type,
            override=override,
        )
        return {
            "added": True,
            "rule_id": rule.id,
            "trigger": rule.trigger,
            "action": rule.action,
            "scope": rule.scope,
            "rule_type": rule.rule_type,
            "override": rule.override,
        }
    except Exception as e:
        # NOTE: Broad exception in MCP tool handler is intentional to catch all errors
        # and return standardized error responses to MCP clients.
        return {"added": False, "error": _safe_error(e)}


@mcp_tool_handler
def handle_list_rules(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """List rules filtered by scope, status, and limit."""
    scope = args.get("scope")
    status = args.get("status", "active")
    limit = min(args.get("limit", 50), 500)

    rules = engine.list_rules(scope=scope, status=status, limit=limit)
    return {
        "total": len(rules),
        "rules": [
            {
                "id": r.id,
                "trigger": r.trigger,
                "action": r.action,
                "scope": r.scope,
                "rule_type": r.rule_type,
                "override": r.override,
                "status": r.status,
                "confidence": r.confidence,
            }
            for r in rules
        ],
    }


@mcp_tool_handler
def handle_match_rules(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Match rules against a scene and return matching rules with scores."""
    scene = _validate_input(args.get("scene", ""), "scene")
    scopes = args.get("scopes")

    matches = engine.match(scene, scopes=scopes)
    return {
        "scene": scene,
        "total": len(matches),
        "matches": [
            {
                "rule_id": m.rule.id,
                "trigger": m.rule.trigger,
                "action": m.rule.action,
                "scope": m.rule.scope,
                "rule_type": m.rule.rule_type,
                "override": m.rule.override,
                "score": round(m.score, 3),
            }
            for m in matches
        ],
    }


@mcp_tool_handler
def handle_inject_rules(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Inject matching rules into a context string in the chosen format."""
    context = _validate_input(args.get("context", ""), "context")
    fmt = args.get("format", "structured")
    max_rules = min(args.get("max_rules", 10), 50)

    injection = engine.inject(context, format=fmt, max_rules=max_rules)
    return {
        "context": context,
        "format": fmt,
        "injection": injection,
        "has_rules": len(injection) > 0,
    }


@mcp_tool_handler
def handle_my_rules(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact, human-readable summary of the user's rules."""
    scope = args.get("scope")
    status = args.get("status", "active")
    rules = engine.list_rules(scope=scope, status=status, limit=200)

    summary_parts = []
    for r in rules:
        marker = "!" if r.override else "~"
        summary_parts.append(f"[{marker}] ({r.scope}/{r.rule_type}) {r.trigger} → {r.action}")

    return {
        "total": len(rules),
        "summary": "\n".join(summary_parts) if summary_parts else "No rules found.",
        "rules": [
            {
                "id": r.id,
                "trigger": r.trigger,
                "action": r.action,
                "scope": r.scope,
                "rule_type": r.rule_type,
                "override": r.override,
                "status": r.status,
                "confidence": r.confidence,
                "trigger_count": r.trigger_count,
            }
            for r in rules
        ],
    }


def handle_delete_rule(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a rule by ID, requiring confirmation for shared scopes."""
    try:
        rule_id = args.get("rule_id", "")
        confirm = args.get("confirm", False)
        if not rule_id:
            return {"error": "Missing required field: rule_id"}

        rule_id = _validate_input(rule_id, "rule_id")
        rule = engine.get_rule(rule_id)
        if rule is None:
            return {"deleted": False, "error": f"Rule not found: {rule_id}"}

        if rule.scope in ("company", "negotiated") and not confirm:
            return {
                "deleted": False,
                "requires_confirmation": True,
                "rule_id": rule_id,
                "scope": rule.scope,
                "message": f"Rule has scope '{rule.scope}'. Set confirm=true to delete.",
            }

        if rule.override and not confirm:
            return {
                "deleted": False,
                "requires_confirmation": True,
                "rule_id": rule_id,
                "message": "Hard rule (override=true) requires confirmation to delete.",
            }

        deleted = engine.delete_rule(rule_id)
        return {
            "deleted": deleted,
            "rule_id": rule_id,
        }
    except Exception as e:
        # NOTE: Broad exception in MCP tool handler is intentional to catch all errors
        # and return standardized error responses to MCP clients.
        return {"error": _safe_error(e)}


@mcp_tool_handler
def handle_suggest_rules(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest rule candidates by analyzing stored memories."""
    memory_type = args.get("memory_type")
    max_candidates = min(args.get("max_candidates", 5), 10)

    carrymem = args.get("_carrymem")
    if carrymem is None:
        return {"error": "No CarryMem instance available for memory recall"}

    memories = carrymem.recall_memories(limit=100)
    if not memories:
        return {"suggestions": [], "total": 0, "message": "No memories found to analyze"}

    candidates = engine.suggest_rules(memories, memory_type=memory_type, max_candidates=max_candidates)
    return {
        "total": len(candidates),
        "suggestions": [
            {
                "trigger": c.trigger if hasattr(c, "trigger") else str(c),
                "action": c.action if hasattr(c, "action") else "",
                "rule_type": c.rule_type if hasattr(c, "rule_type") else "prefer",
                "confidence": c.confidence if hasattr(c, "confidence") else 0.5,
            }
            for c in candidates
        ],
    }


@mcp_tool_handler
def handle_promote_rules(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Promote recurring memory patterns into rule candidates."""
    memory_type = args.get("memory_type")
    auto_accept = args.get("auto_accept", False)

    carrymem = args.get("_carrymem")
    if carrymem is None:
        return {"error": "No CarryMem instance available for memory recall"}

    memories = carrymem.recall_memories(limit=100)
    if not memories:
        return {"promoted": 0, "message": "No memories found to analyze"}

    result = engine.run_promotion(memories, memory_type=memory_type, auto_accept=auto_accept)
    return {
        "promoted": result.get("accepted", 0) if isinstance(result, dict) else 0,
        "result": result,
    }


def handle_update_rule(engine, args: Dict[str, Any]) -> Dict[str, Any]:
    """Update fields of an existing rule by ID."""
    try:
        rule_id = args.get("rule_id", "")
        if not rule_id:
            return {"error": "Missing required field: rule_id"}

        rule_id = _validate_input(rule_id, "rule_id")
        existing = engine.get_rule(rule_id)
        if existing is None:
            return {"updated": False, "error": f"Rule not found: {rule_id}"}

        update_kwargs = {}
        VALID_SCOPES = {"personal", "company", "negotiated"}
        VALID_RULE_TYPES = {"always", "avoid", "forbid", "prefer", "recommend"}
        if "trigger" in args and args["trigger"]:
            update_kwargs["trigger"] = _validate_input(args["trigger"], "trigger")
        if "action" in args and args["action"]:
            update_kwargs["action"] = _validate_input(args["action"], "action")
        if "scope" in args:
            scope = args["scope"]
            if scope not in VALID_SCOPES:
                return {"updated": False, "error": f"Invalid scope: {scope}"}
            if existing.scope == "personal" and scope in ("company", "negotiated"):
                return {"updated": False, "error": "Cannot escalate rule scope from personal"}
            update_kwargs["scope"] = scope
        if "rule_type" in args:
            rule_type = args["rule_type"]
            if rule_type not in VALID_RULE_TYPES:
                return {"updated": False, "error": f"Invalid rule_type: {rule_type}"}
            update_kwargs["rule_type"] = rule_type
        if "override" in args:
            if args["override"] and not existing.override:
                return {"updated": False, "error": "Cannot escalate soft rule to hard rule"}
            update_kwargs["override"] = args["override"]

        if not update_kwargs:
            return {"updated": False, "error": "No fields to update"}

        updated = engine.update_rule(rule_id, **update_kwargs)
        return {
            "updated": updated is not None,
            "rule_id": rule_id,
            "trigger": updated.trigger if updated else None,
            "action": updated.action if updated else None,
            "scope": updated.scope if updated else None,
            "rule_type": updated.rule_type if updated else None,
        }
    except Exception as e:
        # NOTE: Broad exception in MCP tool handler is intentional to catch all errors
        # and return standardized error responses to MCP clients.
        return {"error": _safe_error(e)}


@mcp_tool_handler
def handle_my_profile(carrymem, args: Dict[str, Any]) -> Dict[str, Any]:
    """Return the user's profile including memories and rules."""
    include_memories = args.get("include_memories", True)
    include_rules = args.get("include_rules", True)

    profile: Dict[str, Any] = {
        "identity": "CarryMem User Profile",
        "version": _version,
    }

    if include_memories:
        try:
            memories = carrymem.recall_memories(limit=100)
            type_counts: Dict[str, int] = {}
            recent = []
            for m in memories[:20]:
                m_type = m.get("type", "unknown")
                type_counts[m_type] = type_counts.get(m_type, 0) + 1
                recent.append(
                    {
                        "type": m_type,
                        "content": m.get("content", "")[:80],
                        "confidence": m.get("confidence", 0),
                    }
                )
            profile["memories"] = {
                "total": len(memories),
                "type_distribution": type_counts,
                "recent": recent[:10],
            }
        except (KeyError, ValueError, TypeError, RuntimeError):
            profile["memories"] = {"total": 0, "type_distribution": {}, "recent": []}

    if include_rules:
        try:
            from carrymem.rules import RuleEngine

            db_path = carrymem._adapter.db_path if hasattr(carrymem._adapter, "db_path") else None
            engine = RuleEngine(db_path=db_path)
            rules = engine.list_rules(status="active", limit=200)
            scope_counts: Dict[str, int] = {}
            rule_type_counts: Dict[str, int] = {}
            rule_list = []
            for r in rules:
                scope_counts[r.scope] = scope_counts.get(r.scope, 0) + 1
                rule_type_counts[r.rule_type] = rule_type_counts.get(r.rule_type, 0) + 1
                rule_list.append(f"[{'!' if r.override else '~'}] {r.trigger} → {r.action}")
            profile["rules"] = {
                "total": len(rules),
                "scope_distribution": scope_counts,
                "type_distribution": rule_type_counts,
                "summary": "\n".join(rule_list[:20]) if rule_list else "No rules yet.",
            }
        except (ImportError, KeyError, ValueError, TypeError, RuntimeError):
            profile["rules"] = {"total": 0, "summary": "Rule engine unavailable."}

    return profile


@mcp_tool_handler
def handle_onboard(carrymem, args: Dict[str, Any]) -> Dict[str, Any]:
    """Return an onboarding welcome message and prompt for initial preferences."""
    language = args.get("language", "en")

    welcome_messages = {
        "en": (
            "Welcome to CarryMem! I'm your AI memory companion. "
            "I'll remember your preferences, decisions, and corrections across conversations. "
            "To get started, tell me about yourself:\n\n"
            "1. What programming languages do you prefer?\n"
            "2. What frameworks do you usually work with?\n"
            "3. Any coding style preferences?\n"
            "4. What tools do you use daily?\n\n"
            "Just chat naturally — I'll pick up your preferences automatically!"
        ),
        "zh": (
            "欢迎使用 CarryMem！我是你的 AI 记忆伙伴。"
            "我会在对话中记住你的偏好、决策和纠正。"
            "开始之前，请告诉我一些关于你的信息：\n\n"
            "1. 你偏好什么编程语言？\n"
            "2. 你通常使用什么框架？\n"
            "3. 有什么编码风格偏好吗？\n"
            "4. 你日常使用什么工具？\n\n"
            "自然聊天就好——我会自动识别你的偏好！"
        ),
        "ja": (
            "CarryMemへようこそ！私はあなたのAIメモリーパートナーです。"
            "会話を通じて、あなたの好み、決定、訂正を記憶します。"
            "始めるにあたり、いくつか教えてください：\n\n"
            "1. 好きなプログラミング言語は？\n"
            "2. 普段使っているフレームワークは？\n"
            "3. コーディングスタイルの好みは？\n"
            "4. 日常的に使っているツールは？\n\n"
            "自然に会話するだけで、好みを自動的に認識します！"
        ),
    }

    return {
        "welcome": welcome_messages.get(language, welcome_messages["en"]),
        "language": language,
        "next_steps": [
            "Chat naturally about your preferences",
            "Use 'my_rules' to view your saved rules",
            "Use 'my_profile' to see your complete identity",
        ],
    }


@mcp_tool_handler
def handle_health_check(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight health check via MCP tool (no HTTP service started)."""
    result: Dict[str, Any] = {"version": _version}

    # Adapter health
    try:
        adapter_health = carrymem.health_check()
        result["adapter"] = adapter_health
    except Exception as e:
        result["adapter"] = {"status": "error", "error": str(e)}

    # Audit logger stats — _audit lives on the storage adapter, not on CarryMem
    try:
        adapter = getattr(carrymem, "_adapter", None)
        audit = getattr(adapter, "_audit", None) if adapter is not None else None
        if audit is not None and hasattr(audit, "get_stats"):
            result["audit"] = audit.get_stats()
        else:
            result["audit"] = {"status": "not_available"}
    except Exception as e:
        result["audit"] = {"status": "error", "error": str(e)}

    # Memory count
    try:
        result["memory_count"] = len(carrymem.recall_memories(limit=1000))
    except Exception:
        result["memory_count"] = "unavailable"

    # Uptime
    result["uptime_seconds"] = round(time.time() - getattr(carrymem, "_start_time", time.time()), 1)

    # Overall status
    adapter_status = result.get("adapter", {}).get("status", "unknown")
    result["status"] = "ok" if adapter_status in ("ok", "degraded") else "unhealthy"

    return result


@mcp_tool_handler
def handle_query_graph(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Multi-hop graph traversal from an entity (v0.8.0)."""
    entity_text = arguments.get("entity_text", "")
    if not entity_text.strip():
        return {"entities": [], "memories": [], "error": "entity_text is required"}

    entity_text = _validate_input(entity_text, "entity_text")
    max_hops = _clamp(int(arguments.get("max_hops", 2)), 1, 5)
    limit = _clamp(int(arguments.get("limit", 20)), 1, _MAX_LIMIT)

    result: Dict[str, Any] = carrymem.recall_graph(entity_text, max_hops=max_hops, limit=limit)
    return result


@mcp_tool_handler
def handle_shortest_path(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Find the shortest path between two entities via bidirectional BFS (v0.8.0)."""
    src_entity = arguments.get("src_entity", "")
    dst_entity = arguments.get("dst_entity", "")
    if not src_entity.strip() or not dst_entity.strip():
        return {"path": [], "length": -1, "found": False, "error": "src_entity and dst_entity are required"}

    src_entity = _validate_input(src_entity, "src_entity")
    dst_entity = _validate_input(dst_entity, "dst_entity")
    max_hops = _clamp(int(arguments.get("max_hops", 4)), 1, 10)

    result: Dict[str, Any] = carrymem.recall_shortest_path(src_entity, dst_entity, max_hops=max_hops)
    return result


@mcp_tool_handler
def handle_get_memory_impact(carrymem, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the graph impact of a memory (v0.8.0)."""
    memory_id = arguments.get("memory_id", "")
    if not memory_id.strip():
        return {
            "memory_id": "",
            "entity_count": 0,
            "relation_count": 0,
            "cross_namespace": False,
            "impact_score": 0.0,
            "error": "memory_id is required",
        }

    memory_id = _validate_input(memory_id, "memory_id")
    result: Dict[str, Any] = carrymem.recall_memory_impact(memory_id)
    return result


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
