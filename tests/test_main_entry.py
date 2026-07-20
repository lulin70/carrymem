"""Tests for CarryMem entry points (TD-009).

Covers:
- ``python -m carrymem`` (src/carrymem/__main__.py) — subcommand dispatch
- ``carrymem.cli`` facade (src/carrymem/cli.py) — re-export from cli package
- ``python -m carrymem.integration.layer2_mcp`` (src/carrymem/integration/layer2_mcp/__main__.py)

Design notes:
- Subcommand dispatch is tested via subprocess to exercise the real ``python -m`` entry
  point (avoids monkey-patching ``sys.argv`` + ``SystemExit`` interactions).
- The ``version`` subcommand is the safest to run: no DB, no side effects, deterministic output.
- ``no_command`` path tested via subprocess too (exits 1 after printing help).
- The cli.py facade is tested via direct import verification (it is 1 statement: ``from carrymem.cli import *``).
- The MCP __main__ is tested via import only (running it would start a server — out of scope).
- In-process tests of ``__main__.main()`` are included for coverage tracking (subprocess
  coverage requires ``coverage.process_startup`` which is more complex to set up).
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

import pytest

# ──────────────────────────────────────────────────────────────────────────
# python -m carrymem (src/carrymem/__main__.py)
# ──────────────────────────────────────────────────────────────────────────


class TestPythonMCarryMem:
    """Tests for ``python -m carrymem`` entry point."""

    def _run(self, *args: str, timeout: float = 30.0) -> subprocess.CompletedProcess:
        """Run ``python -m carrymem <args>`` and capture output."""
        return subprocess.run(
            [sys.executable, "-m", "carrymem", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_version_subcommand_prints_version(self):
        """``python -m carrymem version`` prints ``CarryMem v<x.y.z>``."""
        result = self._run("version")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout.startswith("CarryMem v"), f"unexpected stdout: {result.stdout!r}"
        # Verify version matches package metadata
        from carrymem import __version__

        assert (
            __version__ in result.stdout
        ), f"version mismatch: stdout={result.stdout!r} vs __version__={__version__!r}"

    def test_no_subcommand_exits_nonzero_with_help(self):
        """``python -m carrymem`` with no subcommand prints help and exits 1."""
        result = self._run()
        assert result.returncode == 1, f"expected exit 1, got {result.returncode}"
        # Help text should mention the program name and available commands
        combined = result.stdout + result.stderr
        assert "carrymem" in combined.lower(), f"help text missing program name: {combined!r}"
        assert "mcp" in combined, f"help text missing 'mcp' subcommand: {combined!r}"
        assert "version" in combined, f"help text missing 'version' subcommand: {combined!r}"
        assert "doctor" in combined, f"help text missing 'doctor' subcommand: {combined!r}"

    def test_unknown_subcommand_exits_nonzero(self):
        """``python -m carrymem nonexistent`` exits with error (argparse behavior)."""
        result = self._run("nonexistent-subcommand")
        assert result.returncode != 0, "expected non-zero exit for unknown subcommand"
        # argparse writes usage to stderr
        assert (
            "invalid choice" in result.stderr or "usage:" in result.stderr.lower()
        ), f"unexpected stderr: {result.stderr!r}"

    def test_help_flag_prints_usage(self):
        """``python -m carrymem --help`` prints usage and exits 0."""
        result = self._run("--help")
        assert result.returncode == 0
        assert "python -m carrymem" in result.stdout, f"help missing prog name: {result.stdout!r}"
        # All subcommands should be listed
        for cmd in ("mcp", "version", "demo", "doctor", "cli"):
            assert cmd in result.stdout, f"help missing '{cmd}' subcommand: {result.stdout!r}"


class TestMainModuleInProcess:
    """In-process tests for ``carrymem.__main__.main()`` for coverage tracking.

    Subprocess tests above prove the real entry point works, but coverage.py
    cannot track subprocess execution without ``coverage.process_startup``.
    These in-process tests call ``main()`` directly with mocked ``sys.argv``
    so the dispatcher lines are covered.
    """

    def test_version_command_in_process(self, capsys):
        """``main(["version"])`` prints version and exits 0."""
        from carrymem.__main__ import main

        with patch("sys.argv", ["carrymem", "version"]):
            main()
        captured = capsys.readouterr()
        from carrymem import __version__

        assert f"CarryMem v{__version__}" in captured.out, f"version not in stdout: {captured.out!r}"

    def test_no_command_in_process_exits_1(self, capsys):
        """``main([])`` prints help and exits 1 (via ``sys.exit(1)``)."""
        from carrymem.__main__ import main

        with patch("sys.argv", ["carrymem"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1, f"expected exit 1, got {exc_info.value.code}"
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "carrymem" in combined.lower(), f"help text missing program name: {combined!r}"

    def test_doctor_command_in_process(self, tmp_path, capsys):
        """``main(["doctor", "--json"])`` runs doctor and outputs JSON.

        Uses a fresh DB path to avoid polluting the user's real ~/.carrymem/ directory.
        """
        from carrymem.__main__ import main

        db_path = str(tmp_path / "doctor_test.db")
        with patch("sys.argv", ["carrymem", "doctor", "--db", db_path, "--json"]):
            # doctor may call sys.exit(0) on success or sys.exit(non-zero) on failure;
            # either is acceptable as long as it doesn't crash with an unhandled exception
            try:
                main()
            except SystemExit as exc:
                # exit code 0 = healthy, non-zero = issues found — both are valid exercise
                # of the dispatch path; we only care that the dispatcher reached cmd_doctor
                assert exc.code in (0, 1, 2), f"unexpected exit code: {exc.code}"

    # NOTE: ``main(["cli", ...])`` is not tested in-process because __main__.py:66
    # has a pre-existing bug: ``cli_main(args.cli_args)`` passes args to ``cli.main()``
    # which takes no arguments (reads sys.argv directly). The ``# type: ignore[call-arg]``
    # annotation confirms the developer was aware. Fixing this is out of scope for TD-009
    # (coverage task) — should be filed as a separate bug.

    def test_demo_subcommand_in_process(self, tmp_path, capsys, monkeypatch):
        """``main(["demo"])`` runs the interactive demo and prints output.

        The demo creates a CarryMem instance at ~/.carrymem/memories.db by default.
        We override the default DB path via env var to avoid polluting the user's home.
        """
        from carrymem.__main__ import main

        # Isolate DB: CarryMem() reads CARRYMEM_DATA_PATH env var (set via __main__.py
        # only for `mcp` subcommand; for `demo` we patch the default path)
        monkeypatch.setenv("CARRYMEM_DATA_PATH", str(tmp_path))
        with patch("sys.argv", ["carrymem", "demo"]):
            try:
                main()
            except SystemExit as exc:
                # demo should not call sys.exit, but be defensive
                assert exc.code in (0, None), f"unexpected exit code: {exc.code}"
        captured = capsys.readouterr()
        # Demo output should include version banner and section headers
        assert "CarryMem" in captured.out, f"demo output missing banner: {captured.out!r}"
        assert "Demo" in captured.out, f"demo output missing 'Demo': {captured.out!r}"
        # Demo exercises classify_and_remember for 3 languages
        assert (
            "Classify" in captured.out or "Recall" in captured.out
        ), f"demo output missing Classify/Recall section: {captured.out!r}"

    def test_mcp_subcommand_dispatches_to_server(self, tmp_path, capsys):
        """``main(["mcp"])`` dispatches to MCPServer.start().

        We mock MCPServer.start to avoid actually starting the server (which would block).
        Verifies the env var setup path for --config and --data-path flags.
        """
        from unittest.mock import MagicMock

        from carrymem.__main__ import main

        # Mock MCPServer before main() imports it
        with patch(
            "sys.argv",
            [
                "carrymem",
                "mcp",
                "--config",
                str(tmp_path / "config.json"),
                "--data-path",
                str(tmp_path / "data"),
            ],
        ):
            # Patch the import inside main() — MCPServer is imported lazily
            with patch("carrymem.integration.layer2_mcp.server.MCPServer") as MockServer:
                mock_instance = MagicMock()
                MockServer.return_value = mock_instance
                # asyncio.run is called on server.start() — mock to return a coroutine
                mock_instance.start = MagicMock(return_value=asyncio_coro())
                import os

                main()
                # Verify env vars were set
                assert os.environ.get("CARRYMEM_CONFIG_PATH") == str(tmp_path / "config.json")
                assert os.environ.get("CARRYMEM_DATA_PATH") == str(tmp_path / "data")
                # Verify MCPServer was instantiated and start() was called
                MockServer.assert_called_once()
                mock_instance.start.assert_called_once()


def asyncio_coro():
    """Return a no-op async coroutine for mocking asyncio.run()."""
    import asyncio

    async def _empty():
        return None

    return _empty()


# ──────────────────────────────────────────────────────────────────────────
# carrymem.cli facade (src/carrymem/cli.py)
# ──────────────────────────────────────────────────────────────────────────


class TestCliFacade:
    """Tests for ``carrymem.cli`` facade module (1-statement re-export).

    Note: ``carrymem/cli.py`` is shadowed by the ``carrymem/cli/`` package
    directory. ``import carrymem.cli`` loads ``carrymem/cli/__init__.py``,
    NOT ``carrymem/cli.py``. The facade file is effectively dead code.

    These tests verify the package re-exports expected symbols, which is
    what callers actually get when they do ``from carrymem.cli import ...``.
    """

    def test_facade_imports_without_error(self):
        """``import carrymem.cli`` succeeds (no ImportError)."""
        import carrymem.cli  # noqa: F401

    def test_facade_re_exports_main(self):
        """The package re-exports ``main``."""
        from carrymem.cli import main

        assert callable(main), f"main is not callable: {main!r}"

    def test_facade_re_exports_cmd_doctor(self):
        """The package re-exports ``cmd_doctor`` (referenced by __main__.py)."""
        from carrymem.cli import cmd_doctor

        assert callable(cmd_doctor), f"cmd_doctor is not callable: {cmd_doctor!r}"

    def test_facade_re_exports_show_help(self):
        """The package re-exports ``show_help`` (used in entry point tests)."""
        from carrymem.cli import show_help

        assert callable(show_help), f"show_help is not callable: {show_help!r}"


# ──────────────────────────────────────────────────────────────────────────
# python -m carrymem.integration.layer2_mcp (src/carrymem/integration/layer2_mcp/__main__.py)
# ──────────────────────────────────────────────────────────────────────────


class TestMcpMainModule:
    """Tests for ``carrymem.integration.layer2_mcp.__main__`` entry point.

    We test only that the module imports cleanly (not that it runs — running
    would start the MCP server and block).
    """

    def test_module_imports_without_error(self):
        """``import carrymem.integration.layer2_mcp.__main__`` succeeds."""
        import carrymem.integration.layer2_mcp.__main__  # noqa: F401

    def test_module_exposes_main_callable(self):
        """The __main__ module exposes a ``main`` symbol (imported from .server)."""
        from carrymem.integration.layer2_mcp import __main__ as mcp_main

        assert hasattr(mcp_main, "main"), "mcp __main__ missing 'main' attribute"
        # main is imported from .server — verify it's callable
        assert callable(mcp_main.main), f"main is not callable: {mcp_main.main!r}"

    def test_module_path_manipulation_idempotent(self):
        """The sys.path manipulation in __main__ does not break imports."""
        # Importing twice should not raise (sys.path.insert is idempotent for duplicates
        # only if filter is applied; here it's not, but Python's import cache prevents re-execution)
        import importlib

        import carrymem.integration.layer2_mcp.__main__

        importlib.reload(carrymem.integration.layer2_mcp.__main__)
