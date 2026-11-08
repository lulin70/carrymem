"""End-to-end test for Tier 4 host LLM over real MCP stdio.

This test starts the real server process, acts as an MCP client, and answers
the ``sampling/createMessage`` request that the server sends. It proves that a
host LLM answer reaches the tool result, and that an unsupported client falls
back to the rule engine.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

HOST_RULES = [
    {
        "trigger": "when writing Python",
        "action": "use type hints",
        "confidence": 0.9,
        "reasoning": "answer from the host model",
    },
    {
        "trigger": "when choosing a database",
        "action": "prefer PostgreSQL",
        "confidence": 0.85,
        "reasoning": "answer from the host model",
    },
]

MEMORIES = [
    "I always prefer PostgreSQL for data storage",
    "I never use an ORM for complex queries",
    "Please always run pytest before a commit",
    "I prefer type hints in Python code",
]


class StdioMCPClient:
    """Minimal MCP client that speaks JSON-RPC over stdin/stdout."""

    def __init__(self, workdir: Path, sampling_reply: Dict[str, Any]) -> None:
        home = workdir / "home"
        home.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "CARRYMEM_DATA_PATH": str(workdir / "memories.db"),
                "CARRYMEM_LLM_ENABLED": "false",
                "HOME": str(home),
            }
        )
        self._stderr_path = workdir / "server.stderr.log"
        self._stderr = open(self._stderr_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "carrymem.integration.layer2_mcp"],
            cwd=str(REPO_ROOT),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
            text=True,
            bufsize=1,
        )
        self._messages: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._sampling_reply = sampling_reply
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._messages.put(json.loads(line))
            except json.JSONDecodeError:
                continue

    def send(self, message: Dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def _stderr_tail(self) -> str:
        self._stderr.flush()
        try:
            return self._stderr_path.read_text(encoding="utf-8")[-2000:]
        except OSError:
            return ""

    def _answer_sampling(self, message: Dict[str, Any]) -> None:
        reply: Dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        if "error" in self._sampling_reply:
            reply["error"] = self._sampling_reply["error"]
        else:
            reply["result"] = {
                "content": {"type": "text", "text": self._sampling_reply["text"]},
                "model": "e2e-host",
                "stopReason": "endTurn",
            }
        self.send(reply)

    def wait_for_id(self, request_id: int, timeout: float = 60.0) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"Timed out waiting for id={request_id}. stderr:\n{self._stderr_tail()}")
            try:
                message = self._messages.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError(f"Timed out waiting for id={request_id}. stderr:\n{self._stderr_tail()}") from None
            if message.get("method") == "sampling/createMessage":
                self._answer_sampling(message)
                continue
            if message.get("id") == request_id and "method" not in message:
                return message

    def request(self, request_id: int, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        return self.wait_for_id(request_id)

    def call_tool(self, request_id: int, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        message = self.request(request_id, "tools/call", {"name": name, "arguments": arguments})
        text = message["result"]["content"][0]["text"]
        return json.loads(text)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self._stderr.close()


@pytest.fixture()
def client_factory(tmp_path):
    clients = []

    def make(sampling_reply: Dict[str, Any]) -> StdioMCPClient:
        client = StdioMCPClient(tmp_path, sampling_reply)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


def _prepare(client: StdioMCPClient) -> None:
    init = client.request(
        1,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {"sampling": {}},
            "clientInfo": {"name": "carrymem-e2e", "version": "1.0"},
        },
    )
    assert "result" in init, init

    for index, message in enumerate(MEMORIES, start=2):
        stored = client.call_tool(index, "classify_and_remember", {"message": message})
        assert "error" not in stored, stored


def test_suggest_rules_uses_host_sampling(client_factory):
    """A host answer must reach the tool result and report the LLM tier."""
    client = client_factory({"text": json.dumps(HOST_RULES)})
    _prepare(client)

    payload = client.call_tool(10, "suggest_rules", {"max_candidates": 2})["data"]

    assert payload["tier"] == "llm_enhanced", payload
    assert payload["suggestions"][0]["trigger"] == "when writing Python"
    assert payload["suggestions"][0]["reasoning"] == "answer from the host model"


def test_suggest_rules_falls_back_when_host_rejects_sampling(client_factory):
    """A client without sampling must get rule-based output, not an error."""
    client = client_factory(
        {
            "error": {
                "code": -32601,
                "message": "Method not found",
            }
        }
    )
    _prepare(client)

    payload = client.call_tool(10, "suggest_rules", {"max_candidates": 2})["data"]

    assert payload["tier"] == "rule_based", payload
    assert "error" not in payload, payload
