"""Tests for CarryMem CLI unified output formatter (P0-C2 + P0-T2).

Covers:
- OutputFormatter: success / warning / error / info / table / progress
- Color-blind friendly shape symbols (✓ / ▲ / ✗ / ℹ) per P0-T2
- rich-unavailable fallback path (HAS_RICH=False)
- Singleton ``formatter`` instance exported from the package
- CLI integration: ``cmd_stats``, ``cmd_check``, ``cmd_pack`` invoke formatter
"""

from __future__ import annotations

import io
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from carrymem.cli import cmd_check, cmd_pack, cmd_stats
from carrymem.cli._format import (
    HAS_RICH,
    OutputFormatter,
    formatter,
)

# ---------------------------------------------------------------------------
# Symbols (P0-T2: color-blind friendly shape symbols)
# ---------------------------------------------------------------------------

SUCCESS_SYMBOL = "\u2713"  # ✓
WARNING_SYMBOL = "\u25b2"  # ▲
ERROR_SYMBOL = "\u2717"  # ✗
INFO_SYMBOL = "\u2139"  # ℹ


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _force_fallback():
    """Force the formatter module into fallback (rich-unavailable) mode.

    Patches ``carrymem.cli._format.HAS_RICH`` to ``False`` so every method
    takes the plain ``print()`` branch. The original value is restored on exit.
    """
    import carrymem.cli._format as fmt_mod

    original = fmt_mod.HAS_RICH
    fmt_mod.HAS_RICH = False
    try:
        yield
    finally:
        fmt_mod.HAS_RICH = original


# ---------------------------------------------------------------------------
# Tests: exported symbols
# ---------------------------------------------------------------------------


class TestExports:
    """Verify the formatter module exports the expected public API."""

    def test_has_rich_flag_is_boolean(self):
        assert isinstance(HAS_RICH, bool)

    def test_output_formatter_class_exists(self):
        assert OutputFormatter is not None
        assert callable(OutputFormatter)

    def test_singleton_formatter_instance(self):
        assert isinstance(formatter, OutputFormatter)

    def test_singleton_is_stable(self):
        """Importing the singleton twice returns the same object."""
        from carrymem.cli._format import formatter as f1
        from carrymem.cli._format import formatter as f2

        assert f1 is f2


# ---------------------------------------------------------------------------
# Tests: success / warning / info / error
# ---------------------------------------------------------------------------


class TestSuccessMethod:
    def test_success_outputs_message(self, capsys):
        formatter.success("Memory stored")
        captured = capsys.readouterr()
        assert "Memory stored" in captured.out

    def test_success_includes_checkmark_symbol(self, capsys):
        formatter.success("Done")
        captured = capsys.readouterr()
        assert SUCCESS_SYMBOL in captured.out

    def test_success_fallback_uses_plain_print(self, capsys):
        with _force_fallback():
            formatter.success("Fallback success")
        captured = capsys.readouterr()
        assert "Fallback success" in captured.out
        assert SUCCESS_SYMBOL in captured.out


class TestWarningMethod:
    def test_warning_outputs_message(self, capsys):
        formatter.warning("Low disk space")
        captured = capsys.readouterr()
        assert "Low disk space" in captured.out

    def test_warning_includes_triangle_symbol(self, capsys):
        formatter.warning("Heads up")
        captured = capsys.readouterr()
        assert WARNING_SYMBOL in captured.out

    def test_warning_fallback_uses_plain_print(self, capsys):
        with _force_fallback():
            formatter.warning("Fallback warn")
        captured = capsys.readouterr()
        assert "Fallback warn" in captured.out
        assert WARNING_SYMBOL in captured.out


class TestInfoMethod:
    def test_info_outputs_message(self, capsys):
        formatter.info("Loading configuration")
        captured = capsys.readouterr()
        assert "Loading configuration" in captured.out

    def test_info_includes_circle_i_symbol(self, capsys):
        formatter.info("Note")
        captured = capsys.readouterr()
        assert INFO_SYMBOL in captured.out

    def test_info_fallback_uses_plain_print(self, capsys):
        with _force_fallback():
            formatter.info("Fallback info")
        captured = capsys.readouterr()
        assert "Fallback info" in captured.out
        assert INFO_SYMBOL in captured.out


class TestErrorMethod:
    def test_error_outputs_code_and_message(self, capsys):
        formatter.error("E_TEST", "Something broke")
        captured = capsys.readouterr()
        assert "E_TEST" in captured.out
        assert "Something broke" in captured.out

    def test_error_includes_cross_symbol(self, capsys):
        formatter.error("E_X", "fail")
        captured = capsys.readouterr()
        assert ERROR_SYMBOL in captured.out

    def test_error_with_hint_includes_hint(self, capsys):
        formatter.error("E_HINT", "Bad input", hint="Try a smaller value")
        captured = capsys.readouterr()
        assert "E_HINT" in captured.out
        assert "Bad input" in captured.out
        assert "Try a smaller value" in captured.out

    def test_error_without_hint_omits_hint_keyword(self, capsys):
        formatter.error("E_NOHINT", "Plain error")
        captured = capsys.readouterr()
        assert "E_NOHINT" in captured.out
        # No hint line should be present
        assert "Hint:" not in captured.out

    def test_error_fallback_uses_plain_print(self, capsys):
        with _force_fallback():
            formatter.error("E_FB", "Fallback error", hint="Fallback hint")
        captured = capsys.readouterr()
        assert "E_FB" in captured.out
        assert "Fallback error" in captured.out
        assert "Fallback hint" in captured.out
        assert ERROR_SYMBOL in captured.out

    def test_error_hint_none_does_not_print_hint(self, capsys):
        """Passing hint=None must not emit a Hint line."""
        formatter.error("E_NONE", "no hint here", hint=None)
        captured = capsys.readouterr()
        assert "Hint:" not in captured.out


# ---------------------------------------------------------------------------
# Tests: table rendering
# ---------------------------------------------------------------------------


class TestTableMethod:
    def test_table_renders_headers_and_rows(self, capsys):
        headers = ["Type", "Count"]
        rows = [["user_preference", "5"], ["decision", "3"]]
        formatter.table(headers, rows, title="Memory Types")
        captured = capsys.readouterr()
        # Both headers appear in the output
        assert "Type" in captured.out
        assert "Count" in captured.out
        # All row values appear
        assert "user_preference" in captured.out
        assert "decision" in captured.out
        assert "5" in captured.out
        assert "3" in captured.out
        # Title is rendered
        assert "Memory Types" in captured.out

    def test_table_with_no_title(self, capsys):
        formatter.table(["A", "B"], [["1", "2"]])
        captured = capsys.readouterr()
        assert "A" in captured.out
        assert "B" in captured.out
        assert "1" in captured.out
        assert "2" in captured.out

    def test_table_empty_rows(self, capsys):
        formatter.table(["Col1", "Col2"], [], title="Empty")
        captured = capsys.readouterr()
        # Headers still rendered
        assert "Col1" in captured.out
        assert "Col2" in captured.out

    def test_table_coerces_non_string_cells(self, capsys):
        formatter.table(["Key", "Value"], [["answer", 42], ["pi", 3.14]])
        captured = capsys.readouterr()
        assert "42" in captured.out
        assert "3.14" in captured.out

    def test_table_fallback_aligned_columns(self, capsys):
        """Fallback path renders an aligned plain-text table."""
        with _force_fallback():
            formatter.table(
                ["Name", "Count"],
                [["alpha", "1"], ["beta", "22"]],
                title="Fallback Table",
            )
        captured = capsys.readouterr()
        assert "Fallback Table" in captured.out
        assert "Name" in captured.out
        assert "Count" in captured.out
        assert "alpha" in captured.out
        assert "beta" in captured.out
        # Separator line of dashes appears between headers and rows
        assert "-" in captured.out


# ---------------------------------------------------------------------------
# Tests: progress context manager
# ---------------------------------------------------------------------------


class TestProgressContextManager:
    def test_progress_yields_tuple(self):
        """The context manager yields a 2-tuple (progress_obj, task_id)."""
        with formatter.progress("Working") as yielded:
            assert isinstance(yielded, tuple)
            assert len(yielded) == 2

    def test_progress_description_appears_in_output(self, capsys):
        with formatter.progress("Loading database"):
            pass
        captured = capsys.readouterr()
        # rich renders the spinner description; fallback prints "Loading database..."
        assert "Loading database" in captured.out

    def test_progress_can_be_used_without_advancing(self, capsys):
        """Caller is not required to advance the task — context exit cleans up."""

        with formatter.progress("Doing nothing"):
            # intentionally no work
            result = 1 + 1
        assert result == 2

    def test_progress_fallback_prints_description_with_ellipsis(self, capsys):
        with _force_fallback():
            with formatter.progress("Fallback op"):
                pass
        captured = capsys.readouterr()
        assert "Fallback op" in captured.out
        # Fallback adds "..." suffix to indicate work in progress
        assert "..." in captured.out

    def test_progress_fallback_yields_none_tuple(self):
        with _force_fallback():
            with formatter.progress("Fallback op") as (prog, task):
                assert prog is None
                assert task is None

    def test_progress_cleans_up_on_exception(self):
        """Progress context manager must not swallow exceptions."""

        with pytest.raises(ValueError):
            with formatter.progress("Failing op"):
                raise ValueError("boom")


# ---------------------------------------------------------------------------
# Tests: color-blind friendly symbol contract (P0-T2)
# ---------------------------------------------------------------------------


class TestColorBlindFriendlySymbols:
    """P0-T2: every method must pair its color with a distinct shape symbol."""

    def test_success_symbol_is_checkmark(self):
        assert formatter._SUCCESS_SYMBOL == SUCCESS_SYMBOL

    def test_warning_symbol_is_triangle(self):
        assert formatter._WARNING_SYMBOL == WARNING_SYMBOL

    def test_error_symbol_is_cross(self):
        assert formatter._ERROR_SYMBOL == ERROR_SYMBOL

    def test_info_symbol_is_circle_i(self):
        assert formatter._INFO_SYMBOL == INFO_SYMBOL

    def test_all_symbols_are_distinct(self):
        symbols = {
            formatter._SUCCESS_SYMBOL,
            formatter._WARNING_SYMBOL,
            formatter._ERROR_SYMBOL,
            formatter._INFO_SYMBOL,
        }
        assert len(symbols) == 4


# ---------------------------------------------------------------------------
# Tests: OutputFormatter construction
# ---------------------------------------------------------------------------


class TestOutputFormatterConstruction:
    def test_can_construct_fresh_instance(self):
        f = OutputFormatter()
        assert isinstance(f, OutputFormatter)

    def test_console_property_returns_console_or_none(self):
        f = OutputFormatter()
        # When rich is available, console is a rich Console; otherwise None.
        if HAS_RICH:
            assert f.console is not None
        else:
            assert f.console is None

    def test_fresh_instance_when_rich_unavailable(self):
        import carrymem.cli._format as fmt_mod

        original = fmt_mod.HAS_RICH
        fmt_mod.HAS_RICH = False
        try:
            f = OutputFormatter()
            assert f.console is None
        finally:
            fmt_mod.HAS_RICH = original


# ---------------------------------------------------------------------------
# Tests: CLI integration — formatter is actually used by commands
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_format.db")


@pytest.fixture
def db_with_memories(temp_db):
    from carrymem import CarryMem

    cm = CarryMem(db_path=temp_db)
    cm.declare("I prefer dark mode for all editors")
    cm.declare("We decided to use PostgreSQL")
    cm.close()
    return temp_db


class TestCliStatsUsesFormatter:
    """cmd_stats renders the by-type breakdown via formatter.table()."""

    def test_stats_outputs_total_memories(self, db_with_memories, capsys):
        result = cmd_stats(["--db", db_with_memories])
        assert result == 0
        captured = capsys.readouterr()
        assert "Total Memories" in captured.out

    def test_stats_renders_by_type_table(self, db_with_memories, capsys):
        result = cmd_stats(["--db", db_with_memories])
        assert result == 0
        captured = capsys.readouterr()
        # The by-type breakdown should mention at least one of the memory types
        assert "user_preference" in captured.out or "decision" in captured.out

    def test_stats_empty_db_renders_zero(self, temp_db, capsys):
        result = cmd_stats(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Total Memories: 0" in captured.out


class TestCliCheckUsesFormatter:
    """cmd_check uses formatter.success/error for check results."""

    def test_check_runs_successfully(self, temp_db, capsys):
        result = cmd_check(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        # The success/warning symbols should appear somewhere in the output
        # (formatter.success is called when there are no conflicts/expired items)
        assert SUCCESS_SYMBOL in captured.out or WARNING_SYMBOL in captured.out

    def test_check_renders_section_headers(self, temp_db, capsys):
        result = cmd_check(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Conflicts" in captured.out
        assert "Low Quality Memories" in captured.out
        assert "Expired Memories" in captured.out


class TestCliPackUsesFormatter:
    """cmd_pack uses formatter.progress and formatter.success."""

    def test_pack_emits_success_symbol(self, db_with_memories, tmp_path, capsys):
        carry_path = str(tmp_path / "test.carry")
        result = cmd_pack(["--output", carry_path, "--db", db_with_memories])
        assert result == 0
        captured = capsys.readouterr()
        # Pack emits at least one success line ("Packing CarryMem identity" or
        # "Built .carry file" or similar) which goes through formatter.success
        assert SUCCESS_SYMBOL in captured.out


# ---------------------------------------------------------------------------
# Tests: error path integration via main()
# ---------------------------------------------------------------------------


class TestMainErrorPath:
    """Top-level CLI error handling should route through formatter.error()."""

    def test_unknown_command_emits_error_symbol(self, capsys):
        import sys

        from carrymem.cli import main

        with patch.object(sys, "argv", ["carrymem", "totally-unknown-cmd"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        # Unknown command exits with code 1
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        # The error symbol ✗ should appear in the formatted error output
        assert ERROR_SYMBOL in captured.out
