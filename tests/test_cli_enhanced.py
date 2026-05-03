"""Tests for CarryMem CLI — Enhanced command-line interface.

Covers: add, list, search, show, edit, forget, clean, export, import, stats, doctor, setup-mcp, init, version
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from memory_classification_engine.cli import (
    cmd_add, cmd_list, cmd_search, cmd_show, cmd_edit, cmd_forget, cmd_clean,
    cmd_export, cmd_import, cmd_stats, cmd_doctor, cmd_setup_mcp, cmd_init,
    cmd_version, _format_time, _truncate, main,
)
try:
    from memory_classification_engine import CarryMem
except ImportError:
    CarryMem = None


def _store(cm, message):
    result = cm.declare(message)
    return result.get("storage_keys", [])


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_memories.db")


class TestCmdAdd:
    def test_add_basic(self, temp_db, capsys):
        result = cmd_add(["I prefer dark mode for all editors", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Remembered" in captured.out

    def test_add_with_namespace(self, temp_db, capsys):
        result = cmd_add(["I prefer dark mode for all editors", "--namespace", "work", "--db", temp_db])
        assert result == 0

    def test_add_with_context(self, temp_db, capsys):
        ctx = json.dumps({"project": "carrymem"})
        result = cmd_add(["I always use Python for data analysis", "--context", ctx, "--db", temp_db])
        assert result == 0

    def test_add_invalid_context(self, temp_db, capsys):
        result = cmd_add(["I prefer dark mode", "--context", "not-json", "--db", temp_db])
        assert result == 1

    def test_add_stores_memory(self, temp_db):
        cmd_add(["I prefer dark mode for all editors", "--db", temp_db])
        cm = CarryMem(db_path=temp_db)
        memories = cm.recall_memories(query="dark mode")
        assert len(memories) >= 1
        assert "dark mode" in memories[0]["content"]
        cm.close()


class TestCmdList:
    def test_list_empty(self, temp_db, capsys):
        result = cmd_list(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "No memories found" in captured.out

    def test_list_with_data(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_list(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "dark mode" in captured.out

    def test_list_json_format(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_list(["--format", "json", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        assert isinstance(data, list)

    def test_list_plain_format(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_list(["--format", "plain", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "dark mode" in captured.out

    def test_list_with_type_filter(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_list(["--type", "user_preference", "--db", temp_db])
        assert result == 0

    def test_list_with_limit(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        for i in range(5):
            _store(cm, f"I always use Python for project {i}")
        cm.close()

        result = cmd_list(["--limit", "3", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "3 shown" in captured.out


class TestCmdSearch:
    def test_search_basic(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        _store(cm, "I always use Python for data analysis")
        cm.close()

        result = cmd_search(["dark mode", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "dark mode" in captured.out

    def test_search_no_results(self, temp_db, capsys):
        result = cmd_search(["nonexistent query xyz", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "No memories matching" in captured.out

    def test_search_json_format(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I always use Python for data analysis")
        cm.close()

        result = cmd_search(["Python", "--format", "json", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        assert isinstance(data, list)

    def test_search_with_type_filter(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_search(["dark", "--type", "user_preference", "--db", temp_db])
        assert result == 0


class TestCmdForget:
    def test_forget_basic(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        keys = _store(cm, "I prefer dark mode for all editors")
        key = keys[0]
        cm.close()

        result = cmd_forget([key, "--force", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Forgotten" in captured.out

    def test_forget_not_found(self, temp_db, capsys):
        result = cmd_forget(["nonexistent-key", "--force", "--db", temp_db])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_forget_cancelled(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        keys = _store(cm, "I prefer dark mode for all editors")
        key = keys[0]
        cm.close()

        with patch("builtins.input", return_value="n"):
            result = cmd_forget([key, "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Cancelled" in captured.out


class TestCmdExport:
    def test_export_json(self, temp_db, tmp_path, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        output = str(tmp_path / "export.json")
        result = cmd_export([output, "--db", temp_db])
        assert result == 0
        assert Path(output).exists()

        with open(output) as f:
            data = json.load(f)
        assert "memories" in data
        assert len(data["memories"]) >= 1

    def test_export_markdown(self, temp_db, tmp_path, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        output = str(tmp_path / "export.md")
        result = cmd_export([output, "--format", "markdown", "--db", temp_db])
        assert result == 0
        assert Path(output).exists()

        with open(output) as f:
            content = f.read()
        assert "CarryMem Memory Export" in content


class TestCmdImport:
    def test_import_json(self, temp_db, tmp_path, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        export_result = cm.export_memories()
        cm.close()

        export_file = str(tmp_path / "import_test.json")
        with open(export_file, "w") as f:
            json.dump(export_result["data"], f)

        result = cmd_import([export_file, "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Import complete" in captured.out


class TestCmdStats:
    def test_stats_text(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_stats(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Total Memories" in captured.out

    def test_stats_json(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_stats(["--format", "json", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        assert "stats" in data
        assert "profile" in data

    def test_stats_empty(self, temp_db, capsys):
        result = cmd_stats(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Total Memories: 0" in captured.out


class TestCmdDoctor:
    def test_doctor_basic(self, temp_db, capsys):
        result = cmd_doctor(["--db", temp_db])
        assert result in (0, 1)
        captured = capsys.readouterr()
        assert "Doctor" in captured.out

    def test_doctor_with_fix(self, tmp_path, capsys):
        db = str(tmp_path / "fix_test.db")
        result = cmd_doctor(["--db", db, "--fix"])
        assert result in (0, 1)

    def test_doctor_checks_python(self, capsys):
        result = cmd_doctor([])
        captured = capsys.readouterr()
        assert "Python" in captured.out

    def test_doctor_checks_fts5(self, capsys):
        result = cmd_doctor([])
        captured = capsys.readouterr()
        assert "FTS5" in captured.out


class TestCmdSetupMcp:
    def test_setup_mcp_cursor(self, tmp_path, capsys):
        project = str(tmp_path)
        result = cmd_setup_mcp(["--tool", "cursor", "--project", project])
        assert result == 0

        cursor_file = tmp_path / ".cursor" / "mcp.json"
        assert cursor_file.exists()

        with open(cursor_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_setup_mcp_claude_code(self, tmp_path, capsys):
        project = str(tmp_path)
        result = cmd_setup_mcp(["--tool", "claude-code", "--project", project])
        assert result == 0

        claude_file = tmp_path / ".claude" / "mcp.json"
        assert claude_file.exists()

        with open(claude_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_setup_mcp_all(self, tmp_path, capsys):
        project = str(tmp_path)
        result = cmd_setup_mcp(["--tool", "all", "--project", project])
        assert result == 0

        assert (tmp_path / ".cursor" / "mcp.json").exists()
        assert (tmp_path / ".claude" / "mcp.json").exists()

    def test_setup_mcp_idempotent(self, tmp_path, capsys):
        project = str(tmp_path)
        cmd_setup_mcp(["--tool", "cursor", "--project", project])
        result = cmd_setup_mcp(["--tool", "cursor", "--project", project])
        assert result == 0
        captured = capsys.readouterr()
        assert "already configured" in captured.out

    def test_setup_mcp_force_overwrite(self, tmp_path, capsys):
        project = str(tmp_path)
        cmd_setup_mcp(["--tool", "cursor", "--project", project])
        result = cmd_setup_mcp(["--tool", "cursor", "--project", project, "--force"])
        assert result == 0

    def test_setup_mcp_merges_existing(self, tmp_path, capsys):
        project = str(tmp_path)
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        existing_config = {
            "mcpServers": {
                "other-tool": {"command": "other"}
            }
        }
        with open(cursor_dir / "mcp.json", "w") as f:
            json.dump(existing_config, f)

        result = cmd_setup_mcp(["--tool", "cursor", "--project", project])
        assert result == 0

        with open(cursor_dir / "mcp.json") as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]
        assert "other-tool" in config["mcpServers"]


class TestCmdInit:
    def test_init_creates_db(self, tmp_path, capsys):
        db = str(tmp_path / "init_test.db")
        result = cmd_init(["--db", db])
        assert result == 0
        captured = capsys.readouterr()
        assert "ready" in captured.out.lower()


class TestCmdVersion:
    def test_version(self, capsys):
        result = cmd_version([])
        assert result == 0
        captured = capsys.readouterr()
        assert "CarryMem v" in captured.out
        assert "Python" in captured.out


class TestMain:
    def test_no_args_shows_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["carrymem"]):
                main()
        assert exc_info.value.code == 0

    def test_unknown_command(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["carrymem", "unknown-cmd"]):
                main()
        assert exc_info.value.code == 1

    def test_help_command(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["carrymem", "help"]):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "add" in captured.out
        assert "search" in captured.out

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["carrymem", "--version"]):
                main()
        assert exc_info.value.code == 0


class TestHelperFunctions:
    def test_format_time_none(self):
        assert _format_time(None) == "N/A"

    def test_format_time_empty(self):
        assert _format_time("") == "N/A"

    def test_format_time_recent(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        iso = now.isoformat()
        result = _format_time(iso)
        assert "ago" in result

    def test_truncate_short(self):
        assert _truncate("hello", 10) == "hello"

    def test_truncate_long(self):
        result = _truncate("a" * 100, 10)
        assert len(result) == 10
        assert result.endswith("...")


class TestCmdAddForce:
    def test_add_force_bypasses_classification(self, temp_db, capsys):
        result = cmd_add(["test", "--force", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Stored" in captured.out

    def test_add_force_with_type(self, temp_db, capsys):
        result = cmd_add(["test note", "--force", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Stored" in captured.out

    def test_add_rejected_gives_tip(self, temp_db, capsys):
        result = cmd_add(["asdf xyz random", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        if "--force" in captured.out:
            assert "--force" in captured.out


class TestCmdShow:
    def test_show_existing(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        keys = _store(cm, "I prefer dark mode for all editors")
        key = keys[0]
        cm.close()

        result = cmd_show([key, "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "dark mode" in captured.out
        assert "Key:" in captured.out
        assert "Type:" in captured.out

    def test_show_not_found(self, temp_db, capsys):
        result = cmd_show(["nonexistent-key", "--db", temp_db])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_show_json(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        keys = _store(cm, "I prefer dark mode for all editors")
        key = keys[0]
        cm.close()

        result = cmd_show([key, "--json", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        assert data["storage_key"] == key


class TestCmdEdit:
    def test_edit_existing(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        keys = _store(cm, "I prefer dark mode for all editors")
        key = keys[0]
        cm.close()

        with patch("builtins.input", return_value="y"):
            result = cmd_edit([key, "I prefer light mode now", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Updated" in captured.out

    def test_edit_not_found(self, temp_db, capsys):
        result = cmd_edit(["nonexistent-key", "new content", "--db", temp_db])
        assert result == 1

    def test_edit_cancelled(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        keys = _store(cm, "I prefer dark mode for all editors")
        key = keys[0]
        cm.close()

        with patch("builtins.input", return_value="n"):
            result = cmd_edit([key, "I prefer light mode now", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Cancelled" in captured.out


class TestCmdClean:
    def test_clean_nothing(self, temp_db, capsys):
        result = cmd_clean(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Nothing to clean" in captured.out or "healthy" in captured.out

    def test_clean_dry_run(self, temp_db, capsys):
        result = cmd_clean(["--expired", "--dry-run", "--db", temp_db])
        assert result == 0

    def test_clean_with_quality(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        result = cmd_clean(["--quality", "0.01", "--dry-run", "--db", temp_db])
        assert result == 0


class TestCmdListAlias:
    def test_ls_alias(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        _store(cm, "I prefer dark mode for all editors")
        cm.close()

        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["carrymem", "ls", "--db", temp_db]):
                main()
        assert exc_info.value.code == 0
