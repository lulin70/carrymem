"""Read-only MCP tool handlers: classification, recall, and profile queries.

These handlers do not mutate stored state (OperationLevel.READ).
"""

from __future__ import annotations

import time
from typing import Any, Dict

from ._base import (
    CLASSIFICATION_SCHEMA,
    CORE_TOOL_NAMES,
    OPTIONAL_TOOL_NAMES,
    TOOL_NAMES,
    _build_summary,
    _clamp,
    _format_memory_entry,
    _MAX_KNOWLEDGE,
    _MAX_LIMIT,
    _MAX_MEMORIES,
    _safe_error,
    _validate_input,
    _validate_query_input,
    _version,
    mcp_tool_handler,
)


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


__all__ = [
    "handle_classify_message",
    "handle_get_classification_schema",
    "handle_batch_classify",
    "handle_mce_status",
    "handle_recall_memories",
    "handle_recall_from_knowledge",
    "handle_recall_all",
    "handle_get_memory_profile",
    "handle_get_system_prompt",
]
