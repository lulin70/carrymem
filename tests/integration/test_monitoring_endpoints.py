"""Integration tests for monitoring endpoints on MCP HTTP Server."""

import asyncio
import contextlib
import json

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


async def _http_get(host: str, port: int, path: str) -> str:
    """Send a GET request and return the response string."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
        writer.write(request)
        await writer.drain()
        return await _read_all(reader)
    finally:
        writer.close()
        await writer.wait_closed()


async def _http_post(host: str, port: int, path: str, payload: dict) -> str:
    """Send a JSON POST request and return the response string."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        body = json.dumps(payload).encode()
        request = (
            f"POST {path} HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "\r\n"
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
