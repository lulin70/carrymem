"""E2E: recall budget truncation metrics must be visible over real HTTP.

The Phase 5 budget gate records low-cardinality truncation counters and
per-layer budget-utilization gauges on the process-wide metrics collector.
The MCP HTTP exporter reads that same collector, so a real ``recall_with_plan``
truncation executed in-process must surface on a real TCP ``GET /metrics``
response. A real ``POST /message`` tool call proves the server shares the
collector (same premise the classify_and_remember E2E asserts).
"""

import asyncio
import contextlib
import json

import pytest

from carrymem import CarryMem
from carrymem.integration.layer2_mcp.http_server import MCPHTTPServer
from carrymem.monitoring import get_metrics_collector
from carrymem.recall_plan import BudgetSpec, RetrievalBudget, RetrievalMode


async def _wait_for_server(host: str, port: int, timeout: float = 5.0) -> None:
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
    chunks = []
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode()


async def _http_get(host: str, port: int, path: str) -> str:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
        await writer.drain()
        return await _read_all(reader)
    finally:
        writer.close()
        await writer.wait_closed()


async def _http_post(host: str, port: int, path: str, payload: dict) -> str:
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
    return response[response.find("\r\n\r\n") + 4 :]


class TestRecallBudgetMetricsOverHTTP:
    """Real TCP transport: truncation counters must reach /metrics."""

    @pytest.mark.asyncio
    async def test_recall_truncation_metrics_reach_http_export(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CARRYMEM_DATA_PATH", str(tmp_path))
        monkeypatch.setenv("CARRYMEM_BACKUP_DIR", str(tmp_path / "backups"))

        port = 18770
        server = MCPHTTPServer(host="127.0.0.1", port=port)
        server_task = asyncio.create_task(server.start())
        await _wait_for_server("127.0.0.1", port)

        try:
            # Clean baseline: the truncation series must not pre-exist.
            get_metrics_collector().reset()
            before = await _http_get("127.0.0.1", port, "/metrics")
            assert "carrymem_recall_truncations_total" not in before

            # Real planned recall against a real SQLite store. Three matches
            # against a one-candidate cap force a RETRIEVAL_CANDIDATE_CAP
            # truncation plus per-layer utilization reporting.
            cm = CarryMem(db_path=str(tmp_path / "metrics.db"), auto_backup_interval=0)
            try:
                for index in range(3):
                    cm.declare(f"Python project fact number {index}", user_id="u")
                plan = cm.build_recall_plan(
                    query="Python",
                    task="fact_lookup",
                    modes=[RetrievalMode.FTS],
                    budget=BudgetSpec(retrieval=RetrievalBudget(max_candidates=1)),
                )
                result = cm.recall_with_plan(plan)
                assert result.truncations, "candidate cap must truncate"
            finally:
                cm.close()

            metrics_body = _body_of(await _http_get("127.0.0.1", port, "/metrics"))
            assert (
                'carrymem_recall_truncations_total{reason_code="RETRIEVAL_CANDIDATE_CAP",layer="retrieval"}'
                in metrics_body
            ), f"truncation counter missing from /metrics:\n{metrics_body}"
            assert 'carrymem_recall_budget_utilization_ratio{layer="retrieval"}' in metrics_body
            assert 'carrymem_recall_budget_utilization_ratio{layer="output"}' in metrics_body
            assert "None" not in metrics_body, "exposition must stay parseable"

            # A real MCP tool call over TCP shares the same collector.
            raw = await _http_post(
                "127.0.0.1",
                port,
                "/message",
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "classify_and_remember",
                        "arguments": {"message": "I prefer metric driven budgets"},
                    },
                },
            )
            assert "200 OK" in raw, f"MCP tool call failed:\n{raw}"
            metrics_after_tool = _body_of(await _http_get("127.0.0.1", port, "/metrics"))
            assert 'carrymem_total{operation="classify_and_remember"}' in metrics_after_tool

            # Server stays healthy after the budget path ran.
            health = json.loads(_body_of(await _http_get("127.0.0.1", port, "/healthz")))
            assert health["status"] in ("ok", "degraded")
        finally:
            await server.stop()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
