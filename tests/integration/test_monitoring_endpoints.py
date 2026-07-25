"""Integration tests for monitoring endpoints on MCP HTTP Server."""

import asyncio
import json

import pytest

from carrymem.integration.layer2_mcp.http_server import MCPHTTPServer


async def _wait_for_server(host: str, port: int, timeout: float = 5.0) -> None:
    """Poll until the server is accepting connections or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    last_err: Exception | None = None
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError as e:
            last_err = e
            await asyncio.sleep(0.1)
    raise RuntimeError(f"Server at {host}:{port} did not start within {timeout}s: {last_err}")


async def _http_get(host: str, port: int, path: str) -> str:
    """Send a GET request and return the response string."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
        writer.write(request)
        await writer.drain()
        response = await reader.read(4096)
        return response.decode()
    finally:
        writer.close()
        await writer.wait_closed()


class TestMonitoringEndpoints:
    """Test monitoring endpoints integration."""

    @pytest.mark.asyncio
    async def test_healthz_endpoint(self):
        """Test /healthz endpoint returns health status."""
        server = MCPHTTPServer(host="127.0.0.1", port=18765)

        # Start server in background
        server_task = asyncio.create_task(server.start())
        await _wait_for_server("127.0.0.1", 18765)

        try:
            response_str = await _http_get("127.0.0.1", 18765, "/healthz")

            # Verify status code
            assert "200 OK" in response_str or "503" in response_str
            assert "Content-Type: application/json" in response_str

            # Parse JSON body
            body_start = response_str.find("\r\n\r\n") + 4
            body = response_str[body_start:]
            data = json.loads(body)

            # Verify structure
            assert "status" in data
            assert data["status"] in ["ok", "degraded"]
            assert "uptime_seconds" in data
        finally:
            await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test /metrics endpoint returns Prometheus format."""
        server = MCPHTTPServer(host="127.0.0.1", port=18766)

        # Start server in background
        server_task = asyncio.create_task(server.start())
        await _wait_for_server("127.0.0.1", 18766)

        try:
            response_str = await _http_get("127.0.0.1", 18766, "/metrics")

            # Verify status code and content type
            assert "200 OK" in response_str
            assert "Content-Type: text/plain" in response_str

            # Parse body
            body_start = response_str.find("\r\n\r\n") + 4
            body = response_str[body_start:]

            # Verify Prometheus format
            assert "carrymem_uptime_seconds" in body
            assert "# TYPE" in body  # Prometheus type comments
        finally:
            await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_monitoring_endpoints_no_auth(self):
        """Test that monitoring endpoints don't require authentication."""
        server = MCPHTTPServer(host="127.0.0.1", port=18767, api_key="secret123")

        # Start server in background
        server_task = asyncio.create_task(server.start())
        await _wait_for_server("127.0.0.1", 18767)

        try:
            # Test /healthz without auth
            response = await _http_get("127.0.0.1", 18767, "/healthz")
            assert "401" not in response  # Should not be unauthorized
            assert "200" in response or "503" in response

            # Test /metrics without auth
            response = await _http_get("127.0.0.1", 18767, "/metrics")
            assert "401" not in response  # Should not be unauthorized
            assert "200" in response
        finally:
            await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
