"""
Entry point for running CarryMem MCP Server via python -m.

Usage:
    python -m carrymem.integration.layer2_mcp
"""

import asyncio
import os
import sys

# Add project root to path if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from .server import main

if __name__ == "__main__":
    asyncio.run(main())
