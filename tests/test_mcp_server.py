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
    async def test_handle_message_maps_config_to_mcp_server(self):
        config = {
            "config_path": "/tmp/config.yaml",
            "data_path": "/tmp/data",
            "namespace": "test",
            "request_timeout": 17,
        }
        server = MCPHTTPServer(carrymem_config=config)
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        mock_mcp_server = MagicMock()
        mock_mcp_server.execute_request = AsyncMock(return_value={"jsonrpc": "2.0", "id": 1, "result": None})

        with patch("carrymem.integration.layer2_mcp.http_server.MCPServer", return_value=mock_mcp_server) as mcp_class:
            await server._handle_message(writer, b'{"jsonrpc":"2.0","id":1,"method":"initialize"}')

        mcp_class.assert_called_once_with(
            config_path="/tmp/config.yaml",
            data_path="/tmp/data",
            namespace="test",
            request_timeout=17,
        )

    @pytest.mark.asyncio
    async def test_stop_cleans_up_all_resources(self):
        server = MCPHTTPServer()
        mock_http_server = MagicMock()
        mock_http_server.wait_closed = AsyncMock()
        mock_mcp_server = MagicMock()
        mock_mcp_server.cleanup = AsyncMock()
        client = MagicMock()
        server._server = mock_http_server
        server._mcq_server = mock_mcp_server
        server._clients["client"] = client

        await server.stop()

        mock_http_server.close.assert_called_once_with()
        mock_http_server.wait_closed.assert_awaited_once_with()
        client.close.assert_called_once_with()
        mock_mcp_server.cleanup.assert_awaited_once_with()
        assert server._server is None
        assert server._mcq_server is None
        assert server._clients == {}

        await server.stop()
        mock_mcp_server.cleanup.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_stop_continues_cleanup_after_errors(self):
        server = MCPHTTPServer()
        mock_http_server = MagicMock()
        mock_http_server.close.side_effect = RuntimeError("close failed")
        mock_http_server.wait_closed = AsyncMock(side_effect=RuntimeError("wait failed"))
        mock_mcp_server = MagicMock()
        mock_mcp_server.cleanup = AsyncMock(side_effect=RuntimeError("cleanup failed"))
        failing_client = MagicMock()
        failing_client.close.side_effect = RuntimeError("client failed")
        healthy_client = MagicMock()
        server._server = mock_http_server
        server._mcq_server = mock_mcp_server
        server._clients.update({"bad": failing_client, "good": healthy_client})

        await server.stop()

        healthy_client.close.assert_called_once_with()
        mock_mcp_server.cleanup.assert_awaited_once_with()
        assert server._clients == {}


class TestMCPServer:
    @pytest.mark.asyncio
    async def test_init(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path))
        assert server.handlers is not None
        await server.cleanup()

    @pytest.mark.asyncio
    async def test_execute_request_timeout_returns_one_error(self, tmp_path):
        server = MCPServer(data_path=str(tmp_path), request_timeout=0.01)
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_request(_request):
            started.set()
            await release.wait()
            return {"jsonrpc": "2.0", "id": 1, "result": None}

        server.handle_request = slow_request
        task = asyncio.create_task(server.execute_request({"jsonrpc": "2.0", "id": 1, "method": "slow"}))
        await started.wait()
        response = await task

        assert response == {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32603,
                "message": "Request timeout",
                "data": {
                    "execution": "background_may_continue",
                    "side_effects": "possible",
                },
            },
        }
        release.set()
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
