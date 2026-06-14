"""
MCP Server implementation for CarryMem.

This server implements the Model Context Protocol (MCP) to provide
memory classification capabilities to MCP clients like Claude Code and Cursor.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional, Union

from carrymem.__version__ import __version__ as _version

from .handlers import Handlers
from .tools import TOOLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server for Memory Classification Engine.

    Implements JSON-RPC over stdio for MCP protocol compliance.

    Version: 1.0.0 (Production)
    Protocol: MCP 2024-11-05
    """

    VERSION = "1.0.0"
    PROTOCOL_VERSION = "2024-11-05"
    DEFAULT_REQUEST_TIMEOUT = 30  # seconds
    DEFAULT_READLINE_TIMEOUT = 300  # seconds (5 min for idle stdin)

    def __init__(
        self,
        config_path: Optional[str] = None,
        data_path: Optional[str] = None,
        namespace: Optional[str] = None,
        request_timeout: Optional[int] = None,
    ):
        """
        Initialize the MCP Server.

        Args:
            config_path: Path to configuration file (optional)
            data_path: Path to data directory (optional)
            namespace: Default namespace for memory isolation (optional)
            request_timeout: Timeout in seconds for each request (default: 30)
        """
        self.config_path = config_path or os.environ.get("CARRYMEM_CONFIG_PATH")
        self.data_path = data_path or os.environ.get("CARRYMEM_DATA_PATH")
        self.namespace = namespace or os.environ.get("CARRYMEM_NAMESPACE", "default")
        self.request_timeout = request_timeout or int(
            os.environ.get("CARRYMEM_REQUEST_TIMEOUT", self.DEFAULT_REQUEST_TIMEOUT)
        )
        self.handlers = Handlers(self.config_path, self.data_path, namespace=self.namespace)
        self.request_id = 0

        logger.info("MCP Server initialized")
        if self.config_path:
            logger.info("Config path: %s", self.config_path)
        if self.data_path:
            logger.info("Data path: %s", self.data_path)
        if self.namespace != "default":
            logger.info("Namespace: %s", self.namespace)

    async def start(self):
        """Start the MCP server and listen for requests."""
        logger.info("MCP Server starting (request_timeout=%ds)...", self.request_timeout)

        try:
            while True:
                try:
                    line = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline),
                        timeout=self.DEFAULT_READLINE_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    # Idle timeout on stdin — keep waiting (not an error)
                    logger.debug("Stdin idle timeout, continuing...")
                    continue

                if not line:
                    logger.info("EOF received, shutting down...")
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                    response = await asyncio.wait_for(
                        self.handle_request(request),
                        timeout=self.request_timeout,
                    )
                    if response:
                        await self.send_response(response)
                except asyncio.TimeoutError:
                    logger.error("Request timed out after %ds", self.request_timeout)
                    await self.send_error(None, -32603, "Request timeout")
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON: %s", e)
                    await self.send_error(None, -32700, "Parse error")
                # NOTE: Broad exception in MCP server request handler is intentional to catch
                # all errors and return standardized JSON-RPC error responses.
                except Exception as e:
                    logger.error("Error handling request: %s", e)
                    await self.send_error(None, -32603, "Internal error")

        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
        # NOTE: Broad exception in MCP server main loop is intentional to catch all errors
        # and prevent server crashes. All errors are logged for debugging.
        except Exception as e:
            logger.error("Server error: %s", e)
        finally:
            await self.cleanup()

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle an MCP request.

        Args:
            request: The JSON-RPC request

        Returns:
            Response dictionary or None for notifications
        """
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        logger.debug("Handling request: %s (id: %s)", method, request_id)

        if method == "initialize":
            return await self.handle_initialize(request_id, params)
        elif method == "initialized":
            return None
        elif method == "tools/list":
            return await self.handle_tools_list(request_id)
        elif method == "tools/call":
            return await self.handle_tools_call(request_id, params)
        elif method == "shutdown":
            return await self.handle_shutdown(request_id)
        elif method == "exit":
            return None
        else:
            logger.warning("Unknown method: %s", method)
            return await self.send_error(request_id, -32601, "Method not found")

    async def handle_initialize(self, request_id: Union[str, int, None], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initialize request.

        Args:
            request_id: The request ID
            params: Initialization parameters

        Returns:
            Initialize response
        """
        logger.info("Handling initialize request")

        protocol_version = params.get("protocolVersion", "2024-11-05")
        client_info = params.get("clientInfo", {})

        logger.info("Client: %s v%s", client_info.get('name', 'unknown'), client_info.get('version', 'unknown'))
        logger.info("Protocol version: %s", protocol_version)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "carrymem-mcp", "version": _version},
                "capabilities": {"tools": {"listChanged": False}},
            },
        }

    async def handle_tools_list(self, request_id: Union[str, int, None]) -> Dict[str, Any]:
        """
        Handle tools/list request.

        Args:
            request_id: The request ID

        Returns:
            Tools list response
        """
        logger.info("Handling tools/list request")

        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    async def handle_tools_call(self, request_id: Union[str, int, None], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tools/call request.

        Args:
            request_id: The request ID
            params: Tool call parameters

        Returns:
            Tool call response
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        logger.info("Handling tools/call: %s", tool_name)
        logger.debug("Arguments: %s", arguments)

        try:
            result = await asyncio.wait_for(
                self.handlers.handle_tool(tool_name, arguments),
                timeout=self.request_timeout,
            )

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]},
            }
        except asyncio.TimeoutError:
            logger.error("Tool '%s' timed out after %ds", tool_name, self.request_timeout)
            return await self.send_error(request_id, -32603, f"Tool '{tool_name}' timeout")
        # NOTE: Broad exception in tool execution is intentional to catch all handler errors
        # and return standardized error responses to MCP clients.
        except Exception as e:
            logger.error("Error calling tool %s: %s", tool_name, e)
            return await self.send_error(request_id, -32603, f"Tool error: {str(e)}")

    async def handle_shutdown(self, request_id: Union[str, int, None]) -> Dict[str, Any]:
        """
        Handle shutdown request.

        Args:
            request_id: The request ID

        Returns:
            Shutdown response
        """
        logger.info("Handling shutdown request")

        return {"jsonrpc": "2.0", "id": request_id, "result": None}

    async def send_response(self, response: Dict[str, Any]):
        """
        Send a response to stdout.

        Args:
            response: The response dictionary
        """
        response_json = json.dumps(response, ensure_ascii=False)
        print(response_json, flush=True)
        logger.debug("Sent response: %s...", response_json[:200])

    async def send_error(self, request_id: Union[str, int, None], code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send an error response.

        Args:
            request_id: The request ID
            code: Error code
            message: Error message
            data: Additional error data

        Returns:
            Error response dictionary
        """
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

        if data:
            error_response["error"]["data"] = data

        await self.send_response(error_response)
        return error_response

    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up resources...")
        self.handlers.cleanup()


async def main():
    """Main entry point."""
    config_path = os.environ.get("CARRYMEM_CONFIG_PATH")
    data_path = os.environ.get("CARRYMEM_DATA_PATH")
    namespace = os.environ.get("CARRYMEM_NAMESPACE", "default")

    server = MCPServer(config_path, data_path, namespace=namespace)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
