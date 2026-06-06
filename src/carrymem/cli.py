#!/usr/bin/env python3
"""CarryMem CLI - Your Portable AI Memory Layer.

This module is a backward-compatible facade that re-exports all symbols
from the carrymem.cli package submodules.

Usage:
    carrymem add "I prefer dark mode"     Store a memory
    carrymem list                         List recent memories
    carrymem search "theme"               Search memories
    ... (see: carrymem help)
"""

# Re-export from cli package (which is now a directory with __init__.py)
# This preserves: from carrymem.cli import cmd_stats, main, etc.
from carrymem.cli import *  # noqa: F401,F403
