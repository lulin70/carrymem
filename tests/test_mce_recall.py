#!/usr/bin/env python3
"""
Test script for mce_recall tool.

This script tests the mce_recall tool by sending a request to the MCP server.
"""

import json
import sys


def test_mce_recall():
    """Test mce_recall tool."""
    # Create the request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "mce_recall",
            "arguments": {
                "context": "general",
                "limit": 5,
                "format": "text"
            }
        }
    }
    
    # Send the request
    print(json.dumps(request))
    sys.stdout.flush()
    
    # Only read response if not running under pytest
    import os
    if 'PYTEST_CURRENT_TEST' not in os.environ:
        # Read the response
        response = sys.stdin.readline()
        print("Response:")
        print(response)


if __name__ == "__main__":
    test_mce_recall()
