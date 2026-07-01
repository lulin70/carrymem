"""
Tests for MCP HTTP Server and MCP Server modules.

Covers: MCPHTTPServer, SSEClient, MCPServer,
request handling, SSE, auth, CORS, tools/list, tools/call.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from carrymem.integration.layer2_mcp.http_server import (
    MCPHTTPServer,
    SSEClient,
    run_http_server,
)
from carrymem.integration.layer2_mcp.server import MCPServer


class TestSSEClient:
    def test_init(self):
        client = SSEClient("test-id")
        assert client.client_id == "test-id"
        assert client.closed is False

    @pytest.mark.asyncio
    async def test_send(self):
        client = SSEClient("test-id")
        await client.send("test data")
        result = await asyncio.wait_for(client.queue.get(), timeout=1)
        assert result == "test data"

    @pytest.mark.asyncio
    async def test_send_when_closed(self):
        client = SSEClient("test-id")
        client.close()
        await client.send("test data")
        assert client.queue.empty()

    def test_close(self):
        client = SSEClient("test-id")
        client.close()
        assert client.closed is True


class TestMCPHTTPServer:
    def test_init_default(self):
        server = MCPHTTPServer()
        assert server._host == "127.0.0.1"
        assert server._port == 8765
        assert server._api_key is None

    def test_init_with_api_key(self):
        server = MCPHTTPServer(api_key="test-key")
        assert server._api_key == "test-key"

    def test_init_with_env_key(self):
        with patch.dict("os.environ", {"CARRYMEM_API_KEY": "env-key"}):
            server = MCPHTTPServer()
            assert server._api_key == "env-key"

    def test_check_auth_no_key(self):
        server = MCPHTTPServer()
        assert server._check_auth({}) is True

    def test_check_auth_valid(self):
        server = MCPHTTPServer(api_key="test-key")
        assert server._check_auth({"authorization": "Bearer test-key"}) is True

    def test_check_auth_invalid(self):
        server = MCPHTTPServer(api_key="test-key")
        assert server._check_auth({"authorization": "Bearer wrong-key"}) is False

    def test_check_auth_no_bearer(self):
        server = MCPHTTPServer(api_key="test-key")
        assert server._check_auth({"authorization": "Basic abc"}) is False

    def test_check_auth_no_header(self):
        server = MCPHTTPServer(api_key="test-key")
        assert server._check_auth({}) is False

    def test_get_cors_origin_matching(self):
        server = MCPHTTPServer()
        assert server._get_cors_origin("http://localhost:3000") == "http://localhost:3000"

    def test_get_cors_origin_127(self):
        server = MCPHTTPServer()
        assert server._get_cors_origin("http://127.0.0.1:8080") == "http://127.0.0.1:8080"

    def test_get_cors_origin_no_match(self):
        server = MCPHTTPServer()
        assert server._get_cors_origin("http://evil.com") == ""

    def test_get_cors_origin_empty(self):
        server = MCPHTTPServer()
        assert server._get_cors_origin("") == ""

    def test_get_cors_origin_exact_match(self):
        server = MCPHTTPServer(allowed_origins=["http://exact.com"])
        assert server._get_cors_origin("http://exact.com") == "http://exact.com"

    @pytest.mark.asyncio
    async def test_send_response(self):
        server = MCPHTTPServer()
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        await server._send_response(writer, 200, {"status": "ok"}, "http://localhost:3000")
        assert writer.write.called
        assert writer.drain.called

    @pytest.mark.asyncio
    async def test_stop(self):
        server = MCPHTTPServer()
        server._server = None
        await server.stop()

    @pytest.mark.asyncio
    async def test_stop_with_server(self):
        server = MCPHTTPServer()
        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()
        server._server = mock_server
        await server.stop()
        assert mock_server.close.called


class TestMCPServer:
    @pytest.mark.asyncio
    async def test_init(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        assert server.handlers is not None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_initialize(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_initialize(
            1,
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        )
        assert result["id"] == 1
        assert "result" in result
        assert result["result"]["protocolVersion"] == "2024-11-05"
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_initialize_new_protocol(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_initialize(
            1,
            {
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "Trae", "version": "1.107.1"},
            },
        )
        assert result["id"] == 1
        assert result["result"]["protocolVersion"] == "2025-11-25"
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tools_list(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_tools_list(2)
        assert result["id"] == 2
        assert "tools" in result["result"]
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_tools_call(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_tools_call(
            3,
            {
                "name": "mce_status",
                "arguments": {},
            },
        )
        assert result["id"] == 3
        assert "result" in result
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_shutdown(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_shutdown(4)
        assert result["id"] == 4
        assert result["result"] is None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_initialize(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )
        assert result is not None
        assert "result" in result
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_initialized(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )
        assert result is None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_tools_list(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )
        assert result is not None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_tools_call(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "mce_status", "arguments": {}},
            }
        )
        assert result is not None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_shutdown(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "shutdown",
            }
        )
        assert result is not None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_exit(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "exit",
            }
        )
        assert result is None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_handle_request_unknown(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "unknown_method",
            }
        )
        assert "error" in result
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_send_response(self, tmp_path, capsys):
        server = MCPServer(data_path=str(tmp_path))
        await server.send_response({"jsonrpc": "2.0", "id": 1, "result": "ok"})
        captured = capsys.readouterr()
        assert "ok" in captured.out
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_send_error(self, tmp_path, capsys):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.send_error(1, -32600, "Invalid request")
        assert "error" in result
        assert result["error"]["code"] == -32600
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_send_error_with_data(self, tmp_path, capsys):
        server = MCPServer(data_path=str(tmp_path))
        result = await server.send_error(1, -32600, "Invalid request", data={"detail": "test"})
        assert result["error"]["data"] == {"detail": "test"}
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        await server.cleanup()


class TestRunHTTPServer:
    def test_import(self):
        assert callable(run_http_server)
