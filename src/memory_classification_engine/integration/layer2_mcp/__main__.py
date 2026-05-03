"""
Entry point for running CarryMem MCP Server via python -m.

Usage:
    python -m memory_classification_engine.integration.layer2_mcp
"""

import asyncio
import sys
import os

# Add project root to path if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from .server import main

if __name__ == "__main__":
    asyncio.run(main())
