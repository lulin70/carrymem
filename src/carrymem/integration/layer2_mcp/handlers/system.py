"""System MCP tool handlers: identity, onboarding, and health diagnostics.

These handlers target the ``carrymem`` object and are read-only
(OperationLevel.READ).
"""

from __future__ import annotations

import time
from typing import Any, Dict

from ._base import _safe_error, _version, mcp_tool_handler


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

    # Memory count — use adapter.count() (O(1) SQL) instead of recall_memories (O(n) load)
    try:
        adapter = getattr(carrymem, "_adapter", None)
        if adapter is not None and hasattr(adapter, "count"):
            result["memory_count"] = adapter.count()
        else:
            result["memory_count"] = len(carrymem.recall_memories(limit=1000))
    except Exception:
        result["memory_count"] = "unavailable"

    # Uptime
    result["uptime_seconds"] = round(time.time() - getattr(carrymem, "_start_time", time.time()), 1)

    # Overall status
    adapter_status = result.get("adapter", {}).get("status", "unknown")
    result["status"] = "ok" if adapter_status in ("ok", "degraded") else "unhealthy"

    return result


__all__ = [
    "handle_my_profile",
    "handle_onboard",
    "handle_health_check",
]
