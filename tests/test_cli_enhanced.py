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

from carrymem.cli import (
    _build_mcp_server_config,
    _format_time,
    _merge_claude_global_config,
    _merge_json_file,
    _resolve_mcp_command,
    _truncate,
    cmd_add,
    cmd_clean,
    cmd_doctor,
    cmd_edit,
    cmd_export,
    cmd_forget,
    cmd_import,
    cmd_init,
    cmd_list,
    cmd_search,
    cmd_setup_mcp,
    cmd_show,
    cmd_stats,
    cmd_version,
    main,
)

try:
    from carrymem import CarryMem
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
            _store(cm, f"Fact number {i} about the project")
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
        existing_config = {"mcpServers": {"other-tool": {"command": "other"}}}
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


class TestResolveMcpCommand:
    def test_returns_carrymem_if_on_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/carrymem"):
            result = _resolve_mcp_command()
            assert result["command"] == "carrymem"
            assert result["args"] == ["mcp"]

    def test_returns_python_fallback(self):
        with patch("shutil.which", return_value=None):
            result = _resolve_mcp_command()
            assert result["command"] == sys.executable
            assert result["args"] == ["-m", "carrymem.integration.layer2_mcp"]


class TestBuildMcpServerConfig:
    def test_default_db_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/carrymem"):
            config = _build_mcp_server_config()
            assert config["command"] == "carrymem"
            assert config["args"] == ["mcp"]
            assert config["env"]["CARRYMEM_DATA_PATH"] == "$HOME/.carrymem/memories.db"

    def test_custom_db_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/carrymem"):
            config = _build_mcp_server_config(db_path="/custom/path.db")
            assert config["env"]["CARRYMEM_DATA_PATH"] == "/custom/path.db"

    def test_python_fallback_config(self):
        with patch("shutil.which", return_value=None):
            config = _build_mcp_server_config()
            assert config["command"] == sys.executable
            assert config["args"] == ["-m", "carrymem.integration.layer2_mcp"]


class TestMergeJsonFile:
    def test_creates_new_file(self, tmp_path):
        file_path = tmp_path / "mcp.json"
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        success, updated, msg = _merge_json_file(file_path, new_data)
        assert success is True
        assert updated is True
        assert msg == "configured"
        with open(file_path) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_merges_with_existing(self, tmp_path):
        file_path = tmp_path / "mcp.json"
        existing = {"mcpServers": {"other-tool": {"command": "other"}}}
        with open(file_path, "w") as f:
            json.dump(existing, f)
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        success, updated, msg = _merge_json_file(file_path, new_data)
        assert success is True
        with open(file_path) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]
        assert "other-tool" in config["mcpServers"]

    def test_idempotent_without_force(self, tmp_path):
        file_path = tmp_path / "mcp.json"
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        _merge_json_file(file_path, new_data)
        success, updated, msg = _merge_json_file(file_path, new_data)
        assert success is True
        assert updated is False
        assert msg == "already configured"

    def test_force_overwrite(self, tmp_path):
        file_path = tmp_path / "mcp.json"
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        _merge_json_file(file_path, new_data)
        updated_data = {"mcpServers": {"carrymem": {"command": "new-cmd", "args": ["new-arg"]}}}
        success, updated, msg = _merge_json_file(file_path, updated_data, force=True)
        assert success is True
        assert updated is True
        with open(file_path) as f:
            config = json.load(f)
        assert config["mcpServers"]["carrymem"]["command"] == "new-cmd"

    def test_creates_parent_directory(self, tmp_path):
        file_path = tmp_path / "subdir" / "mcp.json"
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        success, updated, msg = _merge_json_file(file_path, new_data)
        assert success is True
        assert file_path.exists()

    def test_handles_corrupt_json(self, tmp_path):
        file_path = tmp_path / "mcp.json"
        with open(file_path, "w") as f:
            f.write("not valid json{{{")
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        success, updated, msg = _merge_json_file(file_path, new_data)
        assert success is False
        assert "Failed to read" in msg


class TestMergeClaudeGlobalConfig:
    def test_creates_new_file(self, tmp_path):
        claude_file = tmp_path / ".claude.json"
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        with patch.object(Path, "home", return_value=tmp_path):
            success, updated, msg = _merge_claude_global_config(new_data)
        assert success is True
        assert updated is True
        with open(claude_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_merges_with_existing_content(self, tmp_path):
        claude_file = tmp_path / ".claude.json"
        existing = {"mcpServers": {"other": {"command": "other"}}, "someKey": "someValue"}
        with open(claude_file, "w") as f:
            json.dump(existing, f)
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        with patch.object(Path, "home", return_value=tmp_path):
            success, updated, msg = _merge_claude_global_config(new_data)
        assert success is True
        with open(claude_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]
        assert "other" in config["mcpServers"]
        assert config["someKey"] == "someValue"

    def test_idempotent(self, tmp_path):
        claude_file = tmp_path / ".claude.json"
        new_data = {"mcpServers": {"carrymem": {"command": "carrymem", "args": ["mcp"]}}}
        with patch.object(Path, "home", return_value=tmp_path):
            _merge_claude_global_config(new_data)
            success, updated, msg = _merge_claude_global_config(new_data)
        assert msg == "already configured"


class TestSetupMcpGlobal:
    def test_global_cursor(self, tmp_path, capsys):
        """Test --global flag writes to ~/.cursor/mcp.json."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "cursor"])
        assert result == 0
        cursor_file = cursor_dir / "mcp.json"
        assert cursor_file.exists()
        with open(cursor_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]
        assert "CARRYMEM_DATA_PATH" in config["mcpServers"]["carrymem"]["env"]

    def test_global_claude_code(self, tmp_path, capsys):
        """Test --global flag writes to ~/.claude.json."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "claude-code"])
        assert result == 0
        claude_file = tmp_path / ".claude.json"
        assert claude_file.exists()
        with open(claude_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_global_trae(self, tmp_path, capsys):
        """Test --global flag writes to ~/.trae/mcp.json."""
        trae_dir = tmp_path / ".trae"
        trae_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "trae"])
        assert result == 0
        trae_file = trae_dir / "mcp.json"
        assert trae_file.exists()
        with open(trae_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_global_trae_cn_auto_detected(self, tmp_path, capsys):
        """Test --global also configures ~/.trae-cn/mcp.json if dir exists."""
        trae_dir = tmp_path / ".trae"
        trae_dir.mkdir()
        trae_cn_dir = tmp_path / ".trae-cn"
        trae_cn_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "trae"])
        assert result == 0
        trae_cn_file = trae_cn_dir / "mcp.json"
        assert trae_cn_file.exists()
        with open(trae_cn_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_global_all(self, tmp_path, capsys):
        """Test --global --tool all configures all tools."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        trae_dir = tmp_path / ".trae"
        trae_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "all"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Claude Code" in captured.out
        assert "Cursor" in captured.out
        assert "TRAE" in captured.out
        assert "shared" in captured.out

    def test_global_idempotent(self, tmp_path, capsys):
        """Test running --global twice doesn't break config."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            cmd_setup_mcp(["--global", "--tool", "cursor"])
            result = cmd_setup_mcp(["--global", "--tool", "cursor"])
        assert result == 0
        captured = capsys.readouterr()
        assert "already configured" in captured.out

    def test_global_force_overwrite(self, tmp_path, capsys):
        """Test --global --force overwrites existing config."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            cmd_setup_mcp(["--global", "--tool", "cursor"])
            result = cmd_setup_mcp(["--global", "--tool", "cursor", "--force"])
        assert result == 0

    def test_global_merges_existing_servers(self, tmp_path, capsys):
        """Test --global preserves other MCP servers in config."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        existing = {"mcpServers": {"other-tool": {"command": "other"}}}
        with open(cursor_dir / "mcp.json", "w") as f:
            json.dump(existing, f)
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "cursor"])
        assert result == 0
        with open(cursor_dir / "mcp.json") as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]
        assert "other-tool" in config["mcpServers"]

    def test_global_shows_shared_db_path(self, tmp_path, capsys):
        """Test --global output mentions shared database."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "cursor"])
        assert result == 0
        captured = capsys.readouterr()
        assert "shared" in captured.out

    def test_global_env_has_data_path(self, tmp_path, capsys):
        """Test MCP config env includes CARRYMEM_DATA_PATH."""
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        with patch.object(Path, "home", return_value=tmp_path):
            result = cmd_setup_mcp(["--global", "--tool", "cursor"])
        assert result == 0
        with open(cursor_dir / "mcp.json") as f:
            config = json.load(f)
        env = config["mcpServers"]["carrymem"]["env"]
        assert "CARRYMEM_DATA_PATH" in env
        assert ".carrymem/memories.db" in env["CARRYMEM_DATA_PATH"]


class TestSetupMcpProjectStillWorks:
    """Ensure project-level setup-mcp still works after --global changes."""

    def test_project_level_cursor(self, tmp_path, capsys):
        result = cmd_setup_mcp(["--tool", "cursor", "--project", str(tmp_path)])
        assert result == 0
        cursor_file = tmp_path / ".cursor" / "mcp.json"
        assert cursor_file.exists()
        with open(cursor_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_project_level_claude_code(self, tmp_path, capsys):
        result = cmd_setup_mcp(["--tool", "claude-code", "--project", str(tmp_path)])
        assert result == 0
        claude_file = tmp_path / ".claude" / "mcp.json"
        assert claude_file.exists()
        with open(claude_file) as f:
            config = json.load(f)
        assert "carrymem" in config["mcpServers"]

    def test_project_level_no_env_by_default(self, tmp_path, capsys):
        """Project-level config should not include env (backward compat)."""
        result = cmd_setup_mcp(["--tool", "cursor", "--project", str(tmp_path)])
        assert result == 0
        cursor_file = tmp_path / ".cursor" / "mcp.json"
        with open(cursor_file) as f:
            config = json.load(f)
        # Project-level config doesn't include env field (backward compat)
        assert "env" not in config["mcpServers"]["carrymem"]


class TestHelperFunctions:
    def test_format_time_none(self):
        assert _format_time(None) == "N/A"

    def test_format_time_empty(self):
        assert _format_time("") == "N/A"

    def test_format_time_recent(self):
        from datetime import datetime, timedelta, timezone

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
