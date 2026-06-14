"""Integration tests for monitoring endpoints on MCP HTTP Server."""

import asyncio
import json

import pytest

from carrymem.integration.layer2_mcp.http_server import MCPHTTPServer


class TestMonitoringEndpoints:
    """Test monitoring endpoints integration."""

    @pytest.mark.asyncio
    async def test_healthz_endpoint(self):
        """Test /healthz endpoint returns health status."""
        server = MCPHTTPServer(host="127.0.0.1", port=18765)

        # Start server in background
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.5)  # Give server time to start

        try:
            # Make HTTP request
            reader, writer = await asyncio.open_connection("127.0.0.1", 18765)

            request = b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n"
            writer.write(request)
            await writer.drain()

            # Read response
            response = await reader.read(4096)
            response_str = response.decode()

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

            writer.close()
            await writer.wait_closed()
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
        await asyncio.sleep(0.5)

        try:
            # Make HTTP request
            reader, writer = await asyncio.open_connection("127.0.0.1", 18766)

            request = b"GET /metrics HTTP/1.1\r\nHost: localhost\r\n\r\n"
            writer.write(request)
            await writer.drain()

            # Read response
            response = await reader.read(4096)
            response_str = response.decode()

            # Verify status code and content type
            assert "200 OK" in response_str
            assert "Content-Type: text/plain" in response_str

            # Parse body
            body_start = response_str.find("\r\n\r\n") + 4
            body = response_str[body_start:]

            # Verify Prometheus format
            assert "carrymem_uptime_seconds" in body
            assert "# TYPE" in body  # Prometheus type comments

            writer.close()
            await writer.wait_closed()
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
        await asyncio.sleep(0.5)

        try:
            # Test /healthz without auth
            reader, writer = await asyncio.open_connection("127.0.0.1", 18767)
            request = b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n"
            writer.write(request)
            await writer.drain()
            response = await reader.read(4096)
            assert b"401" not in response  # Should not be unauthorized
            assert b"200" in response or b"503" in response
            writer.close()
            await writer.wait_closed()

            # Test /metrics without auth
            reader, writer = await asyncio.open_connection("127.0.0.1", 18767)
            request = b"GET /metrics HTTP/1.1\r\nHost: localhost\r\n\r\n"
            writer.write(request)
            await writer.drain()
            response = await reader.read(4096)
            assert b"401" not in response  # Should not be unauthorized
            assert b"200" in response
            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
