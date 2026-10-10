"""Integration tests for monitoring endpoints on MCP HTTP Server."""

import asyncio
import contextlib
import json
import threading
import time

import coverage
import pytest

from carrymem.integration.layer2_mcp.http_server import MCPHTTPServer
from carrymem.monitoring import get_metrics_collector


@contextlib.contextmanager
def _paused_coverage():
    """Pause the active coverage tracer for the duration of the block.

    The SLO assertion below measures real product latency against the 200ms
    threshold. Whole-suite coverage tracing roughly doubles the cost of every
    Python line, so under `pytest` default addopts the measurement would time
    the tracer, not the product (reproduced: p99 409ms with tracing vs
    <200ms without, identical process state). Pausing the tracer during the
    measured window keeps the threshold strict while measuring the product.
    With no active coverage (plain `pytest --no-cov`), this is a no-op.
    """
    cov = coverage.Coverage.current()
    if cov is None:
        yield
        return
    cov.stop()
    try:
        yield
    finally:
        cov.start()


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


async def _read_all(reader) -> str:
    """Read the full response body until the server closes the connection."""
    chunks = []
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode()


async def _http_get(host: str, port: int, path: str, headers: dict | None = None) -> str:
    """Send a GET request and return the response string."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        extra_headers = "".join(f"{key}: {value}\r\n" for key, value in (headers or {}).items())
        request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n{extra_headers}\r\n".encode()
        writer.write(request)
        await writer.drain()
        return await _read_all(reader)
    finally:
        writer.close()
        await writer.wait_closed()


async def _http_post(
    host: str,
    port: int,
    path: str,
    payload: dict,
    headers: dict | None = None,
) -> str:
    """Send a JSON POST request and return the response string."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        body = json.dumps(payload).encode()
        extra_headers = "".join(f"{key}: {value}\r\n" for key, value in (headers or {}).items())
        request = (
            f"POST {path} HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"{extra_headers}\r\n"
        ).encode() + body
        writer.write(request)
        await writer.drain()
        return await _read_all(reader)
    finally:
        writer.close()
        await writer.wait_closed()


def _body_of(response: str) -> str:
    """Return everything after the HTTP header block."""
    return response[response.find("\r\n\r\n") + 4 :]


async def _start_on_ephemeral_port(server: MCPHTTPServer):
    """Start a real listener and return its task and kernel-selected port."""
    server_task = asyncio.create_task(server.start())
    deadline = asyncio.get_event_loop().time() + 5
    while server._server is None:
        if asyncio.get_event_loop().time() >= deadline:
            raise RuntimeError("HTTP server did not expose its listener")
        await asyncio.sleep(0.01)
    port = server._server.sockets[0].getsockname()[1]
    await _wait_for_server(server._host, port)
    return server_task, port


async def _open_sse(host: str, port: int, origin: str = "", token: str | None = None):
    """Open SSE over TCP and return the stream plus its initial endpoint event."""
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET /sse HTTP/1.1\r\nHost: localhost\r\n"
    if origin:
        request += f"Origin: {origin}\r\n"
    if token:
        request += f"Authorization: Bearer {token}\r\n"
    writer.write((request + "\r\n").encode())
    await writer.drain()
    response_headers = (await reader.readuntil(b"\r\n\r\n")).decode()
    endpoint_event = (await reader.readuntil(b"\n\n")).decode()
    return reader, writer, response_headers, endpoint_event


async def _stop_server(server: MCPHTTPServer, server_task: asyncio.Task) -> None:
    """Stop the listener and finish its serve task."""
    await server.stop()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


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


class TestMCPHTTPServerRealE2E:
    """Exercise the public MCP transport through real TCP connections."""

    @pytest.mark.asyncio
    async def test_real_sse_message_tools_and_cleanup(self, tmp_path):
        config_path = tmp_path / "carrymem.json"
        config_path.write_text('{"classification": {"confidence_threshold": 0.1}}', encoding="utf-8")
        data_path = tmp_path / "data"
        data_path.mkdir()
        server = MCPHTTPServer(
            host="127.0.0.1",
            port=0,
            carrymem_config={
                "config_path": str(config_path),
                "data_path": str(data_path),
                "namespace": "http_e2e",
                "request_timeout": 7,
            },
            allowed_origins=["http://localhost:*"],
        )
        server_task, port = await _start_on_ephemeral_port(server)
        sse_writer = None

        try:
            sse_reader, sse_writer, sse_headers, endpoint_event = await _open_sse(
                "127.0.0.1", port, origin="http://localhost:34567"
            )
            assert "200 OK" in sse_headers
            assert "Content-Type: text/event-stream" in sse_headers
            assert "Access-Control-Allow-Origin: http://localhost:34567" in sse_headers
            assert endpoint_event.startswith("event: endpoint\n")
            endpoint_data = json.loads(endpoint_event.split("data: ", 1)[1].strip())
            assert endpoint_data["endpoint"] == "/message"
            client_id = endpoint_data["client_id"]
            assert client_id in server._clients

            initialize = await _http_post(
                "127.0.0.1",
                port,
                "/message",
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "clientInfo": {"name": "http-e2e", "version": "1"},
                    },
                },
                headers={"Origin": "http://localhost:34567"},
            )
            assert "200 OK" in initialize
            assert json.loads(_body_of(initialize))["result"]["serverInfo"]["name"] == "carrymem-mcp"

            write_response = await _http_post(
                "127.0.0.1",
                port,
                "/message",
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "classify_and_remember",
                        "arguments": {"message": "HTTP SSE E2E remembers this namespace fact"},
                    },
                },
                headers={"Origin": "http://evil.example"},
            )
            assert "200 OK" in write_response
            assert "Access-Control-Allow-Origin: \r\n" in write_response
            write_payload = json.loads(_body_of(write_response))
            assert write_payload["result"]["content"]

            notification = await asyncio.wait_for(sse_reader.readuntil(b"\n\n"), timeout=5)
            assert b"notifications/message" in notification

            recall_response = await _http_post(
                "127.0.0.1",
                port,
                "/message",
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "recall_memories",
                        "arguments": {"query": "namespace fact", "limit": 10},
                    },
                },
            )
            recall_payload = json.loads(_body_of(recall_response))
            recall_text = recall_payload["result"]["content"][0]["text"]
            recall_data = json.loads(recall_text)
            assert recall_data["success"] is True
            assert any("namespace fact" in item.get("content", "") for item in recall_data["data"]["memories"])

            mcp_server = server._mcq_server
            assert mcp_server is not None
            assert mcp_server.config_path == str(config_path)
            assert mcp_server.data_path == str(data_path)
            assert mcp_server.namespace == "http_e2e"
            assert mcp_server.request_timeout == 7
            assert mcp_server.handlers._engine.config.config_path == str(config_path)
            assert (data_path / "carrymem.db").exists()
        finally:
            if sse_writer is not None:
                sse_writer.close()
                await sse_writer.wait_closed()
            mcp_server = server._mcq_server
            await _stop_server(server, server_task)
            assert server._server is None
            assert server._clients == {}
            assert server._mcq_server is None
            if mcp_server is not None:
                assert mcp_server.handlers._carrymem._adapter._conn_mgr._closed is True

    @pytest.mark.asyncio
    async def test_real_tcp_timeout_returns_once_and_drains_worker(self, tmp_path, monkeypatch, capsys):
        server = MCPHTTPServer(
            host="127.0.0.1",
            port=0,
            carrymem_config={
                "data_path": str(tmp_path),
                "request_timeout": 0.01,
            },
        )
        server_task, port = await _start_on_ephemeral_port(server)
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        def slow_tool(_target, _arguments):
            started.set()
            while not release.is_set():
                time.sleep(0.001)
            completed.set()
            return "finished"

        import carrymem.integration.layer2_mcp.handlers as handlers_module

        monkeypatch.setitem(handlers_module.handler_map, "slow_http_test", (slow_tool, "carrymem"))
        try:
            response_task = asyncio.create_task(
                _http_post(
                    "127.0.0.1",
                    port,
                    "/message",
                    {
                        "jsonrpc": "2.0",
                        "id": 91,
                        "method": "tools/call",
                        "params": {"name": "slow_http_test", "arguments": {}},
                    },
                )
            )
            await asyncio.to_thread(started.wait, 5)
            response = await response_task
            assert response.count("HTTP/1.1") == 1
            payload = json.loads(_body_of(response))
            assert payload == {
                "jsonrpc": "2.0",
                "id": 91,
                "error": {
                    "code": -32603,
                    "message": "Request timeout",
                    "data": {
                        "execution": "background_may_continue",
                        "side_effects": "possible",
                    },
                },
            }
            assert not completed.is_set()
            assert capsys.readouterr().out == ""

            stop_task = asyncio.create_task(server.stop())
            await asyncio.sleep(0)
            assert not stop_task.done()
            release.set()
            await asyncio.wait_for(stop_task, timeout=5)
            assert completed.is_set()
            assert server._mcq_server is None
        finally:
            release.set()
            if not server._stopping:
                await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_real_auth_and_cors_paths(self):
        server = MCPHTTPServer(host="127.0.0.1", port=0, api_key="http-secret")
        server_task, port = await _start_on_ephemeral_port(server)
        try:
            unauthorized_sse = await _http_get("127.0.0.1", port, "/sse")
            assert "401 Unauthorized" in unauthorized_sse

            unauthorized_message = await _http_post(
                "127.0.0.1", port, "/message", {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
            )
            assert "401 Unauthorized" in unauthorized_message

            allowed = await _http_post(
                "127.0.0.1",
                port,
                "/message",
                {"jsonrpc": "2.0", "id": 2, "method": "initialize"},
                headers={"Authorization": "Bearer http-secret", "Origin": "http://localhost:45678"},
            )
            assert "200 OK" in allowed
            assert "Access-Control-Allow-Origin: http://localhost:45678" in allowed

            denied = await _http_post(
                "127.0.0.1",
                port,
                "/message",
                {"jsonrpc": "2.0", "id": 3, "method": "initialize"},
                headers={"Authorization": "Bearer http-secret", "Origin": "http://evil.example"},
            )
            assert "200 OK" in denied
            assert "Access-Control-Allow-Origin: \r\n" in denied
        finally:
            await _stop_server(server, server_task)
            assert server._server is None
            assert server._clients == {}
            assert server._mcq_server is None


class TestInstrumentedMetricsEndToEnd:
    """Real TCP HTTP + real SQLite: series must come from a real tool call.

    This is the end-to-end proof of the v0.11.0 observability decision: the
    exporter and the core operation paths share one collector, so a real MCP
    tool call becomes visible in both /metrics and the /healthz SLO section.
    """

    @pytest.mark.asyncio
    async def test_real_tool_call_produces_metrics_and_slo_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CARRYMEM_DATA_PATH", str(tmp_path))
        monkeypatch.setenv("CARRYMEM_BACKUP_DIR", str(tmp_path / "backups"))

        port = 18768
        server = MCPHTTPServer(host="127.0.0.1", port=port)
        server_task = asyncio.create_task(server.start())
        await _wait_for_server("127.0.0.1", port)

        try:
            # Warm the real MCP/CarryMem path before measuring SLO latency. The
            # first real calls include one-time initialization and backend
            # inference warm-up, so they must not be treated as steady-state
            # samples used by this wiring assertion.
            for warmup_id in range(8):
                warmup = await _http_post(
                    "127.0.0.1",
                    port,
                    "/message",
                    {
                        "jsonrpc": "2.0",
                        "id": warmup_id,
                        "method": "tools/call",
                        "params": {
                            "name": "classify_and_remember",
                            "arguments": {"message": f"Warm up the monitoring path {warmup_id}"},
                        },
                    },
                )
                assert "200 OK" in warmup, f"warm-up tool call did not succeed:\n{warmup}"

            measured_calls = 101
            rounds = 3
            round_p99s = []
            for _round_idx in range(rounds):
                collector = get_metrics_collector()
                collector.reset()

                # Control group: before the measured operation runs, the series must not exist.
                before = await _http_get("127.0.0.1", port, "/metrics")
                assert 'operation="classify_and_remember"' not in before, (
                    "the series must not be published before any operation ran; " f"got:\n{before}"
                )

                # Measure with the coverage tracer paused (see _paused_coverage):
                # this window must time the product, not suite-wide tracing.
                with _paused_coverage():
                    for request_id in range(measured_calls):
                        raw = await _http_post(
                            "127.0.0.1",
                            port,
                            "/message",
                            {
                                "jsonrpc": "2.0",
                                "id": request_id + 100,
                                "method": "tools/call",
                                "params": {
                                    "name": "classify_and_remember",
                                    "arguments": {
                                        "message": ("I prefer dark mode for coding; " f"measurement {request_id}")
                                    },
                                },
                            },
                        )
                        assert "200 OK" in raw, f"tool call did not succeed:\n{raw}"
                        payload = json.loads(_body_of(raw))
                        tool_result = json.loads(payload["result"]["content"][0]["text"])
                        assert tool_result.get("success") is True, f"tool call returned an error: {tool_result}"

                after = await _http_get("127.0.0.1", port, "/metrics")
                assert (
                    f'carrymem_total{{operation="classify_and_remember"}} {measured_calls}' in after
                ), f"missing counter in:\n{after}"
                assert (
                    f'carrymem_latency_ms_count{{operation="classify_and_remember"}} {measured_calls}' in after
                ), f"missing latency samples in:\n{after}"
                assert "None" not in after, f"exposition must stay parseable:\n{after}"

                health = json.loads(_body_of(await _http_get("127.0.0.1", port, "/healthz")))
                entry = next(e for e in health["slo"] if e["operation"] == "classify_and_remember")
                assert "status" not in entry, f"SLO entry must carry real data, got {entry}"
                round_p99s.append(entry["p99_actual_ms"])

            # A single-window p99 over ~100 samples is decided by the 2 worst
            # samples; on a shared host those are typically OS preemption or
            # GC hiccups, not product cost (same rationale as DevSquad
            # V4.5.19: repeated-round median instead of a single-shot latency
            # assertion). The median across 3 independent rounds still fails
            # on any genuine >=2x latency regression while ignoring one
            # unlucky round. The 200ms threshold itself is unchanged.
            median_p99 = sorted(round_p99s)[rounds // 2]
            assert median_p99 <= 200.0, f"SLO violation in median round: p99 per round = {round_p99s}"
        finally:
            await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
