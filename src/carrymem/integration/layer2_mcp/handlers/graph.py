"""Graph MCP tool handlers: multi-hop traversal and impact analysis (v0.8.0).

All handlers in this module are read-only (OperationLevel.READ).
"""

from __future__ import annotations

from typing import Any, Dict

from ._base import _clamp, _MAX_LIMIT, _validate_input, mcp_tool_handler


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
        return {
            "path": [],
            "length": -1,
            "found": False,
            "error": "src_entity and dst_entity are required",
        }

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


__all__ = [
    "handle_query_graph",
    "handle_shortest_path",
    "handle_get_memory_impact",
]
