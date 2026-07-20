"""Write/delete MCP tool handlers: memory persistence, consolidation, and summarization.

These handlers mutate stored state (OperationLevel.WRITE or DELETE).
"""

from __future__ import annotations

from typing import Any, Dict

from ._base import (
    _clamp,
    _validate_input,
    mcp_tool_handler,
)


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


__all__ = [
    "handle_classify_and_remember",
    "handle_forget_memory",
    "handle_index_knowledge",
    "handle_declare_preference",
    "handle_summarize_and_store",
    "handle_consolidate_memories",
    "handle_schedule_consolidation",
    "handle_stop_consolidation",
]
