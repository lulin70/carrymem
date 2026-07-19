"""Rule MCP tool handlers: CRUD, matching, injection, and promotion.

These handlers target the ``rule_engine`` object and span READ, WRITE,
and DELETE operation levels.
"""

from __future__ import annotations

from typing import Any, Dict

from ._base import _safe_error, _validate_input, mcp_tool_handler


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
        return {
            "suggestions": [],
            "total": 0,
            "message": "No memories found to analyze",
        }

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

        update_kwargs, error = _validate_update_fields(args, existing)
        if error is not None:
            return error

        if not update_kwargs:
            return {"updated": False, "error": "No fields to update"}

        updated = engine.update_rule(rule_id, **update_kwargs)
        return _format_update_response(rule_id, updated)
    except Exception as e:
        # NOTE: Broad exception in MCP tool handler is intentional to catch all errors
        # and return standardized error responses to MCP clients.
        return {"error": _safe_error(e)}


def _validate_update_fields(args: Dict[str, Any], existing) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    """Build validated update kwargs from args.

    Returns ``(update_kwargs, None)`` on success, or ``(None, error_dict)`` if a
    field fails validation.
    """
    update_kwargs: Dict[str, Any] = {}
    VALID_SCOPES = {"personal", "company", "negotiated"}
    VALID_RULE_TYPES = {"always", "avoid", "forbid", "prefer", "recommend"}

    if "trigger" in args and args["trigger"]:
        update_kwargs["trigger"] = _validate_input(args["trigger"], "trigger")
    if "action" in args and args["action"]:
        update_kwargs["action"] = _validate_input(args["action"], "action")

    if "scope" in args:
        scope = args["scope"]
        if scope not in VALID_SCOPES:
            return None, {"updated": False, "error": f"Invalid scope: {scope}"}
        if existing.scope == "personal" and scope in ("company", "negotiated"):
            return None, {
                "updated": False,
                "error": "Cannot escalate rule scope from personal",
            }
        update_kwargs["scope"] = scope
    if "rule_type" in args:
        rule_type = args["rule_type"]
        if rule_type not in VALID_RULE_TYPES:
            return None, {"updated": False, "error": f"Invalid rule_type: {rule_type}"}
        update_kwargs["rule_type"] = rule_type
    if "override" in args:
        if args["override"] and not existing.override:
            return None, {
                "updated": False,
                "error": "Cannot escalate soft rule to hard rule",
            }
        update_kwargs["override"] = args["override"]

    return update_kwargs, None


def _format_update_response(rule_id: str, updated) -> Dict[str, Any]:
    """Format the success response for handle_update_rule."""
    return {
        "updated": updated is not None,
        "rule_id": rule_id,
        "trigger": updated.trigger if updated else None,
        "action": updated.action if updated else None,
        "scope": updated.scope if updated else None,
        "rule_type": updated.rule_type if updated else None,
    }


__all__ = [
    "handle_add_rule",
    "handle_list_rules",
    "handle_match_rules",
    "handle_inject_rules",
    "handle_my_rules",
    "handle_delete_rule",
    "handle_suggest_rules",
    "handle_promote_rules",
    "handle_update_rule",
]
