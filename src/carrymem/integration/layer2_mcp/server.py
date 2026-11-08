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
        # namespace is guaranteed non-None via env fallback "default"
        self.namespace = namespace or os.environ.get("CARRYMEM_NAMESPACE") or "default"
        self.request_timeout = request_timeout or int(
            os.environ.get("CARRYMEM_REQUEST_TIMEOUT", self.DEFAULT_REQUEST_TIMEOUT)
        )
        # Phase 4: Pass self to Handlers for host LLM support
        self.handlers = Handlers(self.config_path, self.data_path, namespace=self.namespace, mcp_server=self)
        self.request_id = 0
        self._stdin_transport: Optional[asyncio.BaseTransport] = None
        # Pending sampling requests, keyed by JSON-RPC id. The stdin loop
        # resolves these futures when the host client answers.
        self._pending_sampling: Dict[Any, asyncio.Future] = {}
        # The loop that owns stdin/stdout. Sampling futures must live here so
        # that a response from the read loop can resolve them safely.
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # In-flight request tasks. The read loop must stay free while a tool
        # runs, otherwise a sampling response cannot be read.
        self._request_tasks: "set[asyncio.Task]" = set()

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

        loop = asyncio.get_running_loop()
        self._loop = loop
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        try:
            self._stdin_transport, _ = await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            while True:
                try:
                    line = await asyncio.wait_for(
                        reader.readline(),
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
                    message = json.loads(line)
                    if self._is_response(message):
                        # A response to our sampling request, not a new request.
                        self._resolve_sampling_response(message)
                        continue
                    # Run each request in a task. The read loop must keep
                    # reading so that a sampling response can arrive while the
                    # tool that waits for it is still running.
                    task = asyncio.create_task(self._process_request(message))
                    self._request_tasks.add(task)
                    task.add_done_callback(self._request_tasks.discard)
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON: %s", e)
                    await self.send_response(self.make_error_response(None, -32700, "Parse error"))
                # NOTE: Broad exception in MCP server request handler is intentional to catch
                # all errors and return standardized JSON-RPC error responses.
                except Exception as e:
                    logger.error("Error handling request: %s", e)
                    await self.send_response(self.make_error_response(None, -32603, "Internal error"))

        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
        # NOTE: Broad exception in MCP server main loop is intentional to catch all errors
        # and prevent server crashes. All errors are logged for debugging.
        except Exception as e:
            logger.error("Server error: %s", e)
        finally:
            if self._stdin_transport is not None:
                self._stdin_transport.close()
                self._stdin_transport = None
            await self.cleanup()

    async def _process_request(self, message: Dict[str, Any]) -> None:
        """Execute one request and send its response without blocking the reader."""
        try:
            response = await self.execute_request(message)
            if response:
                await self.send_response(response)
        # NOTE: Broad exception in request task is intentional. One failed
        # request must not stop the server or other requests.
        except Exception as e:
            logger.error("Error handling request: %s", e)
            await self.send_response(self.make_error_response(message.get("id"), -32603, "Internal error"))

    @staticmethod
    def make_error_response(
        request_id: Union[str, int, None], code: int, message: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build an error response without writing to a transport."""
        error: Dict[str, Any] = {"code": code, "message": message}
        if data:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    async def execute_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute one request with the single transport-independent timeout."""
        try:
            return await asyncio.wait_for(self.handle_request(request), timeout=self.request_timeout)
        except asyncio.TimeoutError:
            logger.error("Request timed out after %ds", self.request_timeout)
            request_id = request.get("id")
            if request_id is None:
                return None
            return self.make_error_response(
                request_id,
                -32603,
                "Request timeout",
                data={
                    "execution": "background_may_continue",
                    "side_effects": "possible",
                },
            )

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
        elif method == "notifications/initialized":
            logger.debug("Received initialized notification")
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
            if request_id is None:
                return None
            return self.make_error_response(request_id, -32601, "Method not found")

    SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}

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

        client_version = params.get("protocolVersion", "2024-11-05")
        client_info = params.get("clientInfo", {})

        logger.info("Client: %s v%s", client_info.get("name", "unknown"), client_info.get("version", "unknown"))
        logger.info("Protocol version: %s", client_version)

        negotiated_version = client_version if client_version in self.SUPPORTED_PROTOCOL_VERSIONS else "2024-11-05"

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": negotiated_version,
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
            result = await self.handlers.handle_tool(tool_name, arguments)  # type: ignore[arg-type]
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]},
            }
        # NOTE: Broad exception in tool execution is intentional to catch all handler errors
        # and return standardized error responses to MCP clients.
        except Exception as e:
            logger.error("Error calling tool %s: %s", tool_name, e)
            return self.make_error_response(request_id, -32603, f"Tool error: {str(e)}")

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
        sys.stdout.write(response_json + "\n")
        sys.stdout.flush()
        logger.debug("Sent response: %s...", response_json[:200])

    async def send_error(
        self, request_id: Union[str, int, None], code: int, message: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
        error_response = self.make_error_response(request_id, code, message, data)
        await self.send_response(error_response)
        return error_response

    @staticmethod
    def _is_response(message: Any) -> bool:
        """Return True when a message is a JSON-RPC response, not a request.

        A response has no ``method`` and carries a matching ``id`` plus either
        ``result`` or ``error``.
        """
        return (
            isinstance(message, dict)
            and "method" not in message
            and "id" in message
            and ("result" in message or "error" in message)
        )

    def _resolve_sampling_response(self, message: Dict[str, Any]) -> None:
        """Deliver a sampling response to the future that waits for it."""
        future = self._pending_sampling.pop(message.get("id"), None)
        if future is None or future.done():
            logger.warning("Unexpected sampling response id: %s", message.get("id"))
            return
        future.set_result(message)

    async def request_sampling(self, messages: list, max_tokens: int = 1000, temperature: float = 0.7, **kwargs) -> Any:
        """Request LLM sampling from MCP host client.

        Phase 4: Enables host LLM integration via MCP sampling protocol.
        This method sends a sampling/createMessage request to the MCP client
        (Claude Desktop, Cursor, etc.) and returns the generated response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            **kwargs: Additional sampling parameters

        Returns:
            Response object with 'content' attribute containing generated text

        Raises:
            RuntimeError: If sampling is not supported by the client
        """
        # Tool handlers run in an executor thread with their own event loop.
        # The stdin reader lives on self._loop. Always create and await the
        # sampling future on the reader loop, so that the response can resolve
        # it from that loop.
        current_loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not current_loop and self._loop.is_running():
            return await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(
                    self._request_sampling_on_loop(messages, max_tokens, temperature, **kwargs),
                    self._loop,
                )
            )
        return await self._request_sampling_on_loop(messages, max_tokens, temperature, **kwargs)

    async def _request_sampling_on_loop(
        self, messages: list, max_tokens: int, temperature: float, **kwargs: Any
    ) -> Any:
        """Send one sampling request on the stdin reader loop and await the answer."""
        # Generate unique request ID
        self.request_id += 1
        request_id = self.request_id

        # Build MCP sampling request
        sampling_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "sampling/createMessage",
            "params": {"messages": messages, "maxTokens": max_tokens, "temperature": temperature, **kwargs},
        }

        # Register the future before the request leaves the process. A fast
        # client can answer before the next loop tick; registering late made
        # that answer look like an unknown id and the call timed out.
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_sampling[request_id] = future

        # Send request to client via stdout
        request_json = json.dumps(sampling_request, ensure_ascii=False)
        sys.stdout.write(request_json + "\n")
        sys.stdout.flush()
        logger.debug("Sent sampling request: %s", request_id)

        try:
            response = await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Sampling request timed out")
            raise RuntimeError("Sampling request timed out")
        finally:
            self._pending_sampling.pop(request_id, None)

        # Check for error response
        if "error" in response:
            error = response["error"]
            message = error.get("message", "unknown error") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"Sampling failed: {message}")

        result = response.get("result") or {}
        content = result.get("content", "")
        if isinstance(content, dict):
            content = content.get("text", "")
        if content is None:
            content = ""

        # Return an object that matches the provider contract.
        class SamplingResponse:
            def __init__(self, text: str):
                self.content = text

        return SamplingResponse(str(content))

    async def cleanup(self):
        """Drain active tools, then cleanup resources."""
        logger.info("Cleaning up resources...")
        self.handlers.start_shutdown()
        await self.handlers.wait_idle()
        # Fail any sampling request that is still pending before the loop stops.
        for future in self._pending_sampling.values():
            if not future.done():
                future.cancel()
        self._pending_sampling.clear()
        for task in list(self._request_tasks):
            task.cancel()
        if self._request_tasks:
            await asyncio.gather(*self._request_tasks, return_exceptions=True)
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
