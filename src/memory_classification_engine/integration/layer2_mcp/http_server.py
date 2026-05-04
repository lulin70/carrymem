"""MCP HTTP/SSE Server — Remote access to CarryMem via HTTP.

v0.7.0: HTTP+SSE transport for MCP protocol, enabling multi-client access.

Protocol:
- GET /sse → Server-Sent Events stream (server pushes events to client)
- POST /message → Client sends JSON-RPC requests
- GET /health → Health check endpoint

Usage:
    carrymem serve --host 127.0.0.1 --port 8765

Security:
- Binds to localhost by default (not 0.0.0.0)
- Optional API key authentication via --api-key or CARRYMEM_API_KEY env var
- CORS headers for browser-based clients
"""

import asyncio
import hmac
import json
import os
import re
from memory_classification_engine.__version__ import __version__ as _version
import uuid
from typing import Any, Dict, Optional

from memory_classification_engine.utils.logger import logger
from .server import MCPServer

_MAX_REQUEST_SIZE = 10 * 1024 * 1024
_MAX_SSE_CLIENTS = 100


class SSEClient:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send(self, data: str):
        if not self.closed:
            await self.queue.put(data)

    def close(self):
        self.closed = True


class MCPHTTPServer:
    """HTTP+SSE transport for MCP protocol."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        api_key: Optional[str] = None,
        carrymem_config: Optional[Dict[str, Any]] = None,
        allowed_origins: Optional[list] = None,
    ):
        self._host = host
        self._port = port
        self._api_key = api_key or os.environ.get("CARRYMEM_API_KEY")
        self._carrymem_config = carrymem_config
        self._allowed_origins = allowed_origins or ["http://localhost:*", "http://127.0.0.1:*"]
        self._clients: Dict[str, SSEClient] = {}
        self._server = None
        self._mcq_server = None

    def _check_auth(self, headers: Dict[str, str]) -> bool:
        if not self._api_key:
            return True
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return hmac.compare_digest(auth[7:], self._api_key)
        return False

    def _get_cors_origin(self, request_origin: str) -> str:
        """Match CORS origin with strict validation.
        
        Supports patterns like:
        - http://localhost:* (matches http://localhost:3000, etc.)
        - http://127.0.0.1:* (matches http://127.0.0.1:8080, etc.)
        - https://example.com (exact match only)
        """
        if not request_origin:
            return ""
        
        # Validate origin format (must be a valid URL)
        if not re.match(r'^https?://[a-zA-Z0-9\.\-]+(:\d+)?$', request_origin):
            logger.debug(f"Invalid origin format: {request_origin}")
            return ""
        
        for pattern in self._allowed_origins:
            if pattern.endswith("*"):
                # Wildcard pattern: http://localhost:*
                prefix = pattern[:-1]  # Remove the *
                
                # Ensure prefix ends with : for port wildcard
                if not prefix.endswith(":"):
                    logger.warning(f"Invalid wildcard pattern (must end with :*): {pattern}")
                    continue
                
                # Check if origin starts with the prefix
                if request_origin.startswith(prefix):
                    # Extract and validate the port part
                    port_part = request_origin[len(prefix):]
                    if re.fullmatch(r'\d+', port_part):
                        port = int(port_part)
                        # Validate port range (1-65535)
                        if 1 <= port <= 65535:
                            return request_origin
                        else:
                            logger.debug(f"Port out of range: {port}")
            elif request_origin == pattern:
                # Exact match
                return request_origin
        
        return ""

    async def _handle_request(self, reader, writer):
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                return

            request_str = request_line.decode("utf-8", errors="replace").strip()
            parts = request_str.split(" ")
            if len(parts) < 2:
                writer.close()
                return

            method = parts[0]
            path = parts[1]

            headers = {}
            content_length = 0
            while True:
                line = await reader.readline()
                if not line or line == b"\r\n":
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if ":" in line_str:
                    key, val = line_str.split(":", 1)
                    headers[key.strip().lower()] = val.strip()
                    if key.strip().lower() == "content-length":
                        content_length = int(val.strip())

            request_origin = headers.get("origin", "")

            body = b""
            if content_length > 0:
                if content_length > _MAX_REQUEST_SIZE:
                    await self._send_response(writer, 413, {"error": "Request too large"}, request_origin)
                    return
                body = await reader.readexactly(content_length)

            if path == "/health":
                await self._send_response(writer, 200, {"status": "ok", "version": _version}, request_origin)
                return

            if not self._check_auth(headers):
                await self._send_response(writer, 401, {"error": "Unauthorized"}, request_origin)
                return

            if method == "GET" and path == "/sse":
                await self._handle_sse(writer, request_origin)
            elif method == "POST" and path == "/message":
                await self._handle_message(writer, body, request_origin)
            else:
                await self._send_response(writer, 404, {"error": "Not found"}, request_origin)

        except Exception as e:
            # Log detailed error for debugging
            logger.error(f"Request handling error: {e}", exc_info=True)
            try:
                # Return sanitized error message (no stack trace or sensitive info)
                error_msg = "Internal server error"
                if os.environ.get("CARRYMEM_DEBUG") == "1":
                    # Only show details in debug mode
                    error_msg = str(e)
                await self._send_response(writer, 500, {"error": error_msg}, "")
            except Exception as e2:
                logger.debug(f"Failed to send error response: {e2}")
                pass
        finally:
            try:
                writer.close()
            except Exception as e:
                logger.debug(f"Failed to close connection: {e}")
                pass

    async def _handle_sse(self, writer, request_origin: str = ""):
        if len(self._clients) >= _MAX_SSE_CLIENTS:
            await self._send_response(writer, 503, {"error": "Too many SSE connections"}, request_origin)
            return

        client_id = str(uuid.uuid4())
        client = SSEClient(client_id)
        self._clients[client_id] = client

        cors_origin = self._get_cors_origin(request_origin)
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            f"Access-Control-Allow-Origin: {cors_origin}\r\n"
            "\r\n"
        )
        writer.write(headers.encode())
        await writer.drain()

        endpoint_data = json.dumps({"endpoint": f"/message", "client_id": client_id})
        writer.write(f"event: endpoint\ndata: {endpoint_data}\n\n".encode())
        await writer.drain()

        try:
            while not client.closed:
                try:
                    data = await asyncio.wait_for(client.queue.get(), timeout=30)
                    writer.write(f"data: {data}\n\n".encode())
                    await writer.drain()
                except asyncio.TimeoutError:
                    writer.write(": keepalive\n\n".encode())
                    await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            client.close()
            self._clients.pop(client_id, None)

    async def _handle_message(self, writer, body: bytes, request_origin: str = ""):
        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            await self._send_response(writer, 400, {"error": "Invalid JSON"}, request_origin)
            return

        if not self._mcq_server:
            self._mcq_server = MCPServer(self._carrymem_config)

        response = await self._mcq_server.handle_request(request)

        await self._send_response(writer, 200, response, request_origin)

        if "method" in request and request.get("method") != "initialize":
            for client in self._clients.values():
                notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/message",
                    "params": {"data": response},
                }
                await client.send(json.dumps(notification))

    async def _send_response(self, writer, status_code: int, body: Dict, request_origin: str = ""):
        status_messages = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found", 413: "Payload Too Large", 500: "Internal Server Error", 503: "Service Unavailable"}
        status_msg = status_messages.get(status_code, "Unknown")
        body_bytes = json.dumps(body).encode("utf-8")
        cors_origin = self._get_cors_origin(request_origin)
        headers = (
            f"HTTP/1.1 {status_code} {status_msg}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Access-Control-Allow-Origin: {cors_origin}\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type, Authorization\r\n"
            "X-Content-Type-Options: nosniff\r\n"
            "X-Frame-Options: DENY\r\n"
            "\r\n"
        )
        writer.write(headers.encode() + body_bytes)
        await writer.drain()

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_request, self._host, self._port
        )
        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        print(f"CarryMem MCP HTTP Server running on {addrs}")
        if self._api_key:
            print("API key authentication enabled")
        else:
            print("⚠️  WARNING: No API key set — server is open to all connections!")
            print("   Set CARRYMEM_API_KEY env var or use --api-key flag")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for client in self._clients.values():
            client.close()
        self._clients.clear()
        print("CarryMem MCP HTTP Server stopped")


def run_http_server(host: str = "127.0.0.1", port: int = 8765, api_key: Optional[str] = None):
    server = MCPHTTPServer(host=host, port=port, api_key=api_key)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
