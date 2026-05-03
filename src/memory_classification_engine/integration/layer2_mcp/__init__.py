"""
MCP Server for Memory Classification Engine

This module provides a Model Context Protocol (MCP) server implementation
that allows Claude Code, Cursor, and other MCP clients to interact with
the Memory Classification Engine.

Usage:
    python -m memory_classification_engine.integration.layer2_mcp

Configuration:
    Set MCE_CONFIG_PATH environment variable to point to your config file.
    Set MCE_DATA_PATH environment variable to point to your data directory.
"""

from .server import MCPServer
from .tools import TOOLS
from .handlers import Handlers

from memory_classification_engine.__version__ import __version__


import threading as _threading

_cm_instance = None
_cm_lock = _threading.Lock()


def _get_carrymem():
    global _cm_instance
    if _cm_instance is None:
        with _cm_lock:
            if _cm_instance is None:
                from memory_classification_engine import CarryMem
                _cm_instance = CarryMem()
    return _cm_instance


def build_system_prompt(context=None, max_memories=10, max_knowledge=5, max_rules=5, language="en"):
    """Convenience function for building system prompts with memory injection.

    Args:
        context: Scene description for rule matching
        max_memories: Maximum memories to include
        max_knowledge: Maximum knowledge entries to include
        max_rules: Maximum rules to inject
        language: Output language (en/zh/ja)

    Returns:
        Formatted system prompt string with injected memories and rules
    """
    cm = _get_carrymem()
    return cm.build_system_prompt(
        context=context,
        max_memories=max_memories,
        max_knowledge=max_knowledge,
        max_rules=max_rules,
        language=language,
    )


__all__ = ["MCPServer", "TOOLS", "Handlers", "build_system_prompt"]
