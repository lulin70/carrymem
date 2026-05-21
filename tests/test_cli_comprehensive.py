"""
Comprehensive CLI tests targeting uncovered code paths.

Covers: cmd_doctor, cmd_init, cmd_setup_mcp, cmd_serve, cmd_tui,
        main(), _format_time, _find_memory, _print_memory_card,
        cmd_add force, cmd_edit/forget confirmation, cmd_clean paths,
        cmd_stats text, cmd_whoami text, cmd_check text,
        cmd_add_rule template/interactive, cmd_refine_rule paths,
        cmd_suggest_rules with data, cmd_promote_rules with data,
        cmd_review_promotions with data, cmd_learn_experience with data,
        cmd_review_lessons with data, cmd_lesson_log with data.
"""

import json
import os
import sys
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from carrymem import CarryMem
from carrymem.cli import (
    cmd_add,
    cmd_list,
    cmd_search,
    cmd_show,
    cmd_edit,
    cmd_forget,
    cmd_clean,
    cmd_export,
    cmd_import,
    cmd_stats,
    cmd_whoami,
    cmd_profile,
    cmd_check,
    cmd_doctor,
    cmd_init,
    cmd_version,
    cmd_setup_mcp,
    cmd_serve,
    cmd_tui,
    cmd_add_rule,
    cmd_list_rules,
    cmd_match_rules,
    cmd_edit_rule,
    cmd_delete_rule,
    cmd_pause_rule,
    cmd_resume_rule,
    cmd_rules_stats,
    cmd_check_rules,
    cmd_export_rules,
    cmd_import_rules,
    cmd_list_templates,
    cmd_suggest_rules,
    cmd_promote_rules,
    cmd_review_promotions,
    cmd_promotion_log,
    cmd_learn_experience,
    cmd_review_lessons,
    cmd_lesson_log,
    cmd_refine_rule,
    cmd_refinement_sessions,
    _format_time,
    _truncate,
    _find_memory,
    _print_memory_card,
    _c,
    _green,
    _red,
    _yellow,
    _cyan,
    _dim,
    _bold,
    main,
    show_help,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_cli_full.db")


@pytest.fixture
def db_with_memories(temp_db):
    cmd_add(["I prefer dark mode for all editors", "--db", temp_db])
    cmd_add(["I use PostgreSQL for databases", "--db", temp_db])
    cmd_add(["I dislike using Vim", "--db", temp_db])
    return temp_db


class TestHelperFunctions:
    def test_format_time_none(self):
        assert _format_time(None) == "N/A"

    def test_format_time_empty(self):
        assert _format_time("") == "N/A"

    def test_format_time_recent(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        recent = now - timedelta(minutes=30)
        result = _format_time(recent.isoformat())
        assert "m ago" in result or "h ago" in result

    def test_format_time_hours_ago(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        hours_ago = now - timedelta(hours=5)
        result = _format_time(hours_ago.isoformat())
        assert "h ago" in result

    def test_format_time_yesterday(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        result = _format_time(yesterday.isoformat())
        assert "yesterday" in result

    def test_format_time_days_ago(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        days_ago = now - timedelta(days=10)
        result = _format_time(days_ago.isoformat())
        assert "d ago" in result

    def test_format_time_old_date(self):
        from datetime import datetime, timezone
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        result = _format_time(old.isoformat())
        assert "2020" in result

    def test_format_time_invalid_string(self):
        result = _format_time("not a date at all!!!")
        assert isinstance(result, str)

    def test_truncate_short(self):
        assert _truncate("short text", 60) == "short text"

    def test_truncate_long(self):
        long_text = "a" * 100
        result = _truncate(long_text, 60)
        assert len(result) == 60
        assert result.endswith("...")

    def test_color_functions(self):
        result = _green("test")
        assert "test" in result
        result = _red("test")
        assert "test" in result
        result = _yellow("test")
        assert "test" in result
        result = _cyan("test")
        assert "test" in result
        result = _dim("test")
        assert "test" in result
        result = _bold("test")
        assert "test" in result

    def test_c_no_color(self):
        import carrymem.cli as cli_mod
        orig = cli_mod._HAS_COLOR
        try:
            cli_mod._HAS_COLOR = False
            result = _c("32", "test")
            assert result == "test"
        finally:
            cli_mod._HAS_COLOR = orig

    def test_find_memory_with_adapter(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        result = cm.classify_and_remember("I prefer dark mode")
        cm.close()
        cm2 = CarryMem(db_path=temp_db)
        found = _find_memory(cm2, "nonexistent_key")
        assert found is None
        cm2.close()

    def test_print_memory_card(self, capsys):
        m = {
            "type": "user_preference",
            "content": "I prefer dark mode",
            "confidence": 0.9,
            "importance_score": 0.7,
            "storage_key": "mem_test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "tier": 2,
            "access_count": 5,
        }
        _print_memory_card(m, index=1)
        captured = capsys.readouterr()
        assert "dark mode" in captured.out

    def test_print_memory_card_no_index(self, capsys):
        m = {
            "type": "decision",
            "content": "Use React",
            "confidence": 0.8,
            "importance_score": 0.5,
            "storage_key": "mem_test2",
            "created_at": "",
            "tier": 3,
            "access_count": 0,
        }
        _print_memory_card(m)
        captured = capsys.readouterr()
        assert "React" in captured.out


class TestCmdAddForce:
    def test_add_force(self, temp_db, capsys):
        result = cmd_add(["Test forced memory", "--force", "--db", temp_db])
        assert result == 0

    def test_add_force_with_type(self, temp_db, capsys):
        result = cmd_add(["Test forced typed", "--force", "--type", "decision", "--db", temp_db])
        assert result == 0

    def test_add_with_context_json(self, temp_db, capsys):
        result = cmd_add([
            "I prefer dark mode",
            "--context", '{"editor": "vscode"}',
            "--db", temp_db,
        ])
        assert result == 0

    def test_add_with_invalid_context(self, temp_db, capsys):
        result = cmd_add([
            "I prefer dark mode",
            "--context", "not json",
            "--db", temp_db,
        ])
        assert result == 1

    def test_add_with_namespace(self, temp_db, capsys):
        result = cmd_add(["Work memory", "--namespace", "work", "--db", temp_db])
        assert result == 0


class TestCmdListFormats:
    def test_list_plain(self, db_with_memories, capsys):
        result = cmd_list(["--format", "plain", "--db", db_with_memories])
        assert result == 0
        captured = capsys.readouterr()
        assert "user_preference" in captured.out or "dark mode" in captured.out

    def test_list_empty(self, temp_db, capsys):
        result = cmd_list(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "No memories" in captured.out or "Tip" in captured.out


class TestCmdSearchFormats:
    def test_search_plain(self, db_with_memories, capsys):
        result = cmd_search(["dark mode", "--format", "plain", "--db", db_with_memories])
        assert result == 0

    def test_search_no_results(self, db_with_memories, capsys):
        result = cmd_search(["zzznonexistent", "--db", db_with_memories])
        assert result == 0
        captured = capsys.readouterr()
        assert "No memories" in captured.out or "zzznonexistent" in captured.out


class TestCmdShowJson:
    def test_show_json(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            result = cmd_show([key, "--json", "--db", db_with_memories])
            assert result == 0
            captured = capsys.readouterr()
            assert "storage_key" in captured.out

    def test_show_not_found(self, temp_db, capsys):
        result = cmd_show(["nonexistent_key", "--db", temp_db])
        assert result == 1


class TestCmdEditConfirmation:
    def test_edit_confirm_yes(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            with patch("builtins.input", return_value="y"):
                result = cmd_edit([key, "Updated content", "--db", db_with_memories])
                assert result == 0

    def test_edit_confirm_no(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            with patch("builtins.input", return_value="n"):
                result = cmd_edit([key, "Updated content", "--db", db_with_memories])
                assert result == 0

    def test_edit_eof(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            with patch("builtins.input", side_effect=EOFError):
                result = cmd_edit([key, "Updated content", "--db", db_with_memories])
                assert result == 0

    def test_edit_not_found(self, temp_db, capsys):
        result = cmd_edit(["nonexistent_key", "new content", "--db", temp_db])
        assert result == 1


class TestCmdForgetConfirmation:
    def test_forget_confirm_yes(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            with patch("builtins.input", return_value="y"):
                result = cmd_forget([key, "--db", db_with_memories])
                assert result == 0

    def test_forget_confirm_no(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            with patch("builtins.input", return_value="n"):
                result = cmd_forget([key, "--db", db_with_memories])
                assert result == 0

    def test_forget_eof(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            with patch("builtins.input", side_effect=EOFError):
                result = cmd_forget([key, "--db", db_with_memories])
                assert result == 0

    def test_forget_force(self, db_with_memories, capsys):
        cm = CarryMem(db_path=db_with_memories)
        memories = cm.recall_memories(query="", limit=1)
        cm.close()
        if memories:
            key = memories[0].get("storage_key", "")
            result = cmd_forget([key, "--force", "--db", db_with_memories])
            assert result == 0

    def test_forget_not_found(self, temp_db, capsys):
        result = cmd_forget(["nonexistent_key", "--db", temp_db])
        assert result == 1


class TestCmdCleanPaths:
    def test_clean_expired(self, db_with_memories, capsys):
        result = cmd_clean(["--expired", "--force", "--db", db_with_memories])
        assert result in (0, 1)

    def test_clean_quality_dry_run(self, db_with_memories, capsys):
        result = cmd_clean(["--quality", "0.99", "--dry-run", "--db", db_with_memories])
        assert result == 0

    def test_clean_nothing(self, temp_db, capsys):
        result = cmd_clean(["--db", temp_db])
        assert result == 0

    def test_clean_confirm_no(self, db_with_memories, capsys):
        with patch("builtins.input", return_value="n"):
            result = cmd_clean(["--expired", "--db", db_with_memories])
            assert result == 0

    def test_clean_confirm_eof(self, db_with_memories, capsys):
        with patch("builtins.input", side_effect=EOFError):
            result = cmd_clean(["--expired", "--db", db_with_memories])
            assert result == 0


class TestCmdExportImportPaths:
    def test_export_success(self, temp_db, capsys, tmp_path):
        cmd_add(["Test memory for export", "--db", temp_db])
        capsys.readouterr()
        output_path = str(tmp_path / "export_test.json")
        result = cmd_export([output_path, "--db", temp_db])
        assert result == 0

    def test_import_overwrite(self, temp_db, tmp_path, capsys):
        output_path = str(tmp_path / "import_overwrite.json")
        cmd_add(["Test memory", "--db", temp_db])
        capsys.readouterr()
        cmd_export([output_path, "--db", temp_db])
        capsys.readouterr()
        result = cmd_import([output_path, "--merge", "overwrite", "--db", temp_db])
        assert result == 0


class TestCmdStatsText:
    def test_stats_text_with_data(self, db_with_memories, capsys):
        result = cmd_stats(["--db", db_with_memories])
        assert result == 0
        captured = capsys.readouterr()
        assert "Statistics" in captured.out or "Total" in captured.out


class TestCmdWhoamiText:
    def test_whoami_new_user(self, temp_db, capsys):
        result = cmd_whoami(["--db", temp_db])
        assert result == 0

    def test_whoami_json(self, temp_db, capsys):
        result = cmd_whoami(["--json", "--db", temp_db])
        assert result == 0

    def test_whoami_with_data(self, db_with_memories, capsys):
        result = cmd_whoami(["--db", db_with_memories])
        assert result == 0


class TestCmdProfileExport:
    def test_profile_export_default_path(self, temp_db, capsys, tmp_path):
        export_path = str(tmp_path / "carrymem_profile.json")
        result = cmd_profile(["export", "--output", export_path, "--db", temp_db])
        assert result == 0


class TestCmdCheckText:
    def test_check_all(self, db_with_memories, capsys):
        result = cmd_check(["--db", db_with_memories])
        assert result == 0

    def test_check_conflicts_with_data(self, db_with_memories, capsys):
        result = cmd_check(["--conflicts", "--db", db_with_memories])
        assert result == 0

    def test_check_quality_with_data(self, db_with_memories, capsys):
        result = cmd_check(["--quality", "--db", db_with_memories])
        assert result == 0

    def test_check_expired_with_data(self, db_with_memories, capsys):
        result = cmd_check(["--expired", "--db", db_with_memories])
        assert result == 0


class TestCmdDoctor:
    def test_doctor_basic(self, tmp_path, capsys):
        db_path = str(tmp_path / "doctor_test.db")
        result = cmd_doctor(["--db", db_path])
        assert result in (0, 1)

    def test_doctor_with_fix(self, tmp_path, capsys):
        db_path = str(tmp_path / "doctor_fix.db")
        cm = CarryMem(db_path=db_path)
        cm.declare("test")
        cm.close()
        result = cmd_doctor(["--db", db_path, "--fix"])
        assert result in (0, 1)

    def test_doctor_existing_db(self, temp_db, capsys):
        result = cmd_doctor(["--db", temp_db])
        assert result in (0, 1)

    def test_doctor_no_db(self, tmp_path, capsys):
        db_path = str(tmp_path / "nonexistent" / "db.db")
        result = cmd_doctor(["--db", db_path])
        assert result in (0, 1)


class TestCmdInit:
    def test_init_creates_db(self, tmp_path, capsys):
        db_path = str(tmp_path / "init_test.db")
        result = cmd_init(["--db", db_path])
        assert result == 0

    def test_init_existing(self, temp_db, capsys):
        result = cmd_init(["--db", temp_db])
        assert result == 0


class TestCmdSetupMcp:
    def test_setup_mcp_claude(self, tmp_path, capsys):
        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir, exist_ok=True)
        result = cmd_setup_mcp(["--tool", "claude-code", "--project", project_dir])
        assert result == 0

    def test_setup_mcp_cursor(self, tmp_path, capsys):
        project_dir = str(tmp_path / "project2")
        os.makedirs(project_dir, exist_ok=True)
        result = cmd_setup_mcp(["--tool", "cursor", "--project", project_dir])
        assert result == 0

    def test_setup_mcp_all(self, tmp_path, capsys):
        project_dir = str(tmp_path / "project3")
        os.makedirs(project_dir, exist_ok=True)
        result = cmd_setup_mcp(["--tool", "all", "--project", project_dir])
        assert result == 0

    def test_setup_mcp_force(self, tmp_path, capsys):
        project_dir = str(tmp_path / "project4")
        os.makedirs(project_dir, exist_ok=True)
        cmd_setup_mcp(["--tool", "all", "--project", project_dir])
        capsys.readouterr()
        result = cmd_setup_mcp(["--tool", "all", "--project", project_dir, "--force"])
        assert result == 0

    def test_setup_mcp_existing_config(self, tmp_path, capsys):
        project_dir = str(tmp_path / "project5")
        os.makedirs(project_dir, exist_ok=True)
        cmd_setup_mcp(["--tool", "all", "--project", project_dir])
        capsys.readouterr()
        result = cmd_setup_mcp(["--tool", "all", "--project", project_dir])
        assert result == 0


class TestCmdServe:
    def test_serve_import(self):
        from carrymem.cli import cmd_serve
        assert callable(cmd_serve)


class TestCmdTui:
    def test_tui_no_textual(self, capsys):
        with patch.dict("sys.modules", {"carrymem.tui": MagicMock(HAS_TEXTUAL=False)}):
            result = cmd_tui([])
            assert result == 1


class TestCmdVersion:
    def test_version(self, capsys):
        result = cmd_version([])
        assert result == 0
        captured = capsys.readouterr()
        assert "CarryMem" in captured.out


class TestMainFunction:
    def test_main_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "help"]):
                main()
        assert exc_info.value.code == 0

    def test_main_version(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "version"]):
                main()
        assert exc_info.value.code == 0

    def test_main_no_args(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem"]):
                main()
        assert exc_info.value.code == 0

    def test_main_unknown_command(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "unknown_cmd"]):
                main()
        assert exc_info.value.code == 1

    def test_main_keyboard_interrupt(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "stats"]):
                with patch("carrymem.cli.cmd_stats", side_effect=KeyboardInterrupt):
                    main()
        assert exc_info.value.code == 130

    def test_main_exception(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "stats"]):
                with patch("carrymem.cli.cmd_stats", side_effect=RuntimeError("test error")):
                    main()
        assert exc_info.value.code == 1

    def test_main_dash_v(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "-v"]):
                main()
        assert exc_info.value.code == 0

    def test_main_dash_h(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["carrymem", "-h"]):
                main()
        assert exc_info.value.code == 0


class TestShowHelp:
    def test_show_help(self, capsys):
        show_help()
        captured = capsys.readouterr()
        assert "CarryMem" in captured.out
        assert "Commands" in captured.out


class TestCmdAddRuleTemplate:
    def test_add_rule_template(self, temp_db, capsys):
        result = cmd_add_rule([
            "always use SSL", "--trigger", "security",
            "--type", "always", "--template", "code-review",
            "--db", temp_db,
        ])
        assert result in (0, 1)

    def test_add_rule_template_invalid(self, temp_db, capsys):
        result = cmd_add_rule([
            "test", "--template", "nonexistent_template",
            "--db", temp_db,
        ])
        assert result == 1

    def test_add_rule_soft(self, temp_db, capsys):
        result = cmd_add_rule([
            "prefer PostgreSQL", "--trigger", "database",
            "--soft", "--db", temp_db,
        ])
        assert result == 0

    def test_add_rule_interactive_cancel(self, temp_db, capsys):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = cmd_add_rule(["--interactive", "--db", temp_db])
            assert result == 1

    def test_add_rule_interactive_eof(self, temp_db, capsys):
        with patch("builtins.input", side_effect=EOFError):
            result = cmd_add_rule(["--interactive", "--db", temp_db])
            assert result == 1

    def test_add_rule_interactive_empty_trigger(self, temp_db, capsys):
        with patch("builtins.input", side_effect=["", "action"]):
            result = cmd_add_rule(["--interactive", "--db", temp_db])
            assert result == 1

    def test_add_rule_interactive_empty_action(self, temp_db, capsys):
        with patch("builtins.input", side_effect=["trigger", ""]):
            result = cmd_add_rule(["--interactive", "--db", temp_db])
            assert result == 1

    def test_add_rule_interactive_success(self, temp_db, capsys):
        with patch("builtins.input", side_effect=["test trigger", "test action", "1", "y"]):
            result = cmd_add_rule(["--interactive", "--db", temp_db])
            assert result == 0

    def test_add_rule_validation_error(self, temp_db, capsys):
        from carrymem.rules import RuleEngine
        with patch.object(RuleEngine, "add_rule", side_effect=ValueError("bad rule")):
            result = cmd_add_rule([
                "test action", "--trigger", "test trigger",
                "--db", temp_db,
            ])
            assert result == 1


class TestCmdMatchRulesTextFormat:
    def test_match_text_with_results(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--type", "prefer", "--db", temp_db])
        capsys.readouterr()
        result = cmd_match_rules(["database", "--db", temp_db])
        assert result == 0

    def test_match_text_no_results(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--db", temp_db])
        capsys.readouterr()
        result = cmd_match_rules(["completely unrelated", "--db", temp_db])
        assert result == 0


class TestCmdEditRuleExtended:
    def test_edit_rule_soft(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--db", temp_db])
        capsys.readouterr()
        result = cmd_list_rules(["--db", temp_db])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_edit_rule([rule_id, "--soft", "--db", temp_db])
            assert result == 0

    def test_edit_rule_hard(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--soft", "--db", temp_db])
        capsys.readouterr()
        result = cmd_list_rules(["--db", temp_db])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_edit_rule([rule_id, "--hard", "--db", temp_db])
            assert result == 0

    def test_edit_rule_no_changes(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--db", temp_db])
        capsys.readouterr()
        result = cmd_list_rules(["--db", temp_db])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_edit_rule([rule_id, "--db", temp_db])
            assert result == 1

    def test_edit_rule_not_found(self, temp_db, capsys):
        result = cmd_edit_rule(["rule_nonexistent", "--action", "new", "--db", temp_db])
        assert result == 1


class TestCmdCheckRulesJson:
    def test_check_rules_json(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--db", temp_db])
        capsys.readouterr()
        result = cmd_check_rules(["--json", "--db", temp_db])
        assert result in (0, 1)


class TestCmdExportRulesError:
    def test_export_rules_bad_path(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--db", temp_db])
        capsys.readouterr()
        result = cmd_export_rules(["/nonexistent/dir/rules.json", "--db", temp_db])
        assert result == 1


class TestCmdImportRulesError:
    def test_import_rules_file_not_found(self, temp_db, capsys):
        result = cmd_import_rules(["/nonexistent/file.json", "--db", temp_db])
        assert result == 1

    def test_import_rules_invalid_json(self, temp_db, tmp_path, capsys):
        bad_json = str(tmp_path / "bad.json")
        with open(bad_json, "w") as f:
            f.write("not valid json{{{")
        result = cmd_import_rules([bad_json, "--db", temp_db])
        assert result == 1


class TestCmdSuggestRulesWithData:
    def test_suggest_with_memories(self, temp_db, capsys):
        for i in range(5):
            cmd_add([f"I prefer dark mode in editor {i}", "--db", temp_db])
            capsys.readouterr()
        result = cmd_suggest_rules(["--db", temp_db])
        assert result == 0

    def test_suggest_with_type_filter(self, temp_db, capsys):
        for i in range(3):
            cmd_add([f"I prefer dark mode {i}", "--db", temp_db])
            capsys.readouterr()
        result = cmd_suggest_rules(["--type", "user_preference", "--db", temp_db])
        assert result == 0


class TestCmdPromoteRulesWithData:
    def test_promote_with_memories(self, temp_db, capsys):
        for i in range(5):
            cmd_add([f"I prefer dark mode {i}", "--db", temp_db])
            capsys.readouterr()
        result = cmd_promote_rules(["--db", temp_db])
        assert result == 0

    def test_promote_auto_accept(self, temp_db, capsys):
        for i in range(5):
            cmd_add([f"I prefer dark mode {i}", "--db", temp_db])
            capsys.readouterr()
        result = cmd_promote_rules(["--auto-accept", "--db", temp_db])
        assert result == 0


class TestCmdReviewPromotionsWithData:
    def test_review_accept_invalid(self, temp_db, capsys):
        result = cmd_review_promotions(["--accept", "nonexistent_id", "--db", temp_db])
        assert result == 1

    def test_review_reject_invalid(self, temp_db, capsys):
        result = cmd_review_promotions(["--reject", "nonexistent_id", "--db", temp_db])
        assert result == 1

    def test_review_accept_all_empty(self, temp_db, capsys):
        result = cmd_review_promotions(["--accept-all", "--db", temp_db])
        assert result == 0

    def test_review_accept_all_confirm_no(self, temp_db, capsys):
        with patch("builtins.input", return_value="n"):
            result = cmd_review_promotions(["--accept-all", "--db", temp_db])
            assert result == 0

    def test_review_accept_all_eof(self, temp_db, capsys):
        with patch("builtins.input", side_effect=EOFError):
            result = cmd_review_promotions(["--accept-all", "--db", temp_db])
            assert result == 0


class TestCmdPromotionLogWithData:
    def test_promotion_log_with_data(self, temp_db, capsys):
        for i in range(5):
            cmd_add([f"I prefer dark mode {i}", "--db", temp_db])
            capsys.readouterr()
        cmd_promote_rules(["--db", temp_db])
        capsys.readouterr()
        result = cmd_promotion_log(["--db", temp_db])
        assert result == 0


class TestCmdLearnExperienceWithData:
    def test_learn_with_memories(self, temp_db, capsys):
        for i in range(3):
            cmd_add([f"Correction: use Python {i}", "--db", temp_db])
            capsys.readouterr()
        result = cmd_learn_experience(["--type", "correction", "--db", temp_db])
        assert result == 0


class TestCmdReviewLessonsWithData:
    def test_review_accept_invalid(self, temp_db, capsys):
        result = cmd_review_lessons(["--accept", "nonexistent_id", "--db", temp_db])
        assert result == 0

    def test_review_reject_invalid(self, temp_db, capsys):
        result = cmd_review_lessons(["--reject", "nonexistent_id", "--db", temp_db])
        assert result == 0

    def test_review_accept_all_empty(self, temp_db, capsys):
        result = cmd_review_lessons(["--accept-all", "--db", temp_db])
        assert result == 0

    def test_review_with_trigger_override(self, temp_db, capsys):
        result = cmd_review_lessons([
            "--accept", "nonexistent_id",
            "--trigger", "custom trigger",
            "--action", "custom action",
            "--db", temp_db,
        ])
        assert result == 0


class TestCmdLessonLogWithData:
    def test_lesson_log_with_data(self, temp_db, capsys):
        for i in range(3):
            cmd_add([f"Correction: use Python {i}", "--db", temp_db])
            capsys.readouterr()
        cmd_learn_experience(["--db", temp_db])
        capsys.readouterr()
        result = cmd_lesson_log(["--db", temp_db])
        assert result == 0


class TestCmdRefineRuleExtended:
    def test_refine_start_success(self, temp_db, capsys):
        result = cmd_refine_rule([
            "--trigger", "database selection", "--action", "avoid MongoDB",
            "--db", temp_db,
        ])
        assert result == 0

    def test_refine_missing_args(self, temp_db, capsys):
        result = cmd_refine_rule(["--db", temp_db])
        assert result == 1

    def test_refine_cancel(self, temp_db, capsys):
        result = cmd_refine_rule([
            "--session", "nonexistent", "--cancel", "--db", temp_db,
        ])
        assert result == 0

    def test_refine_confirm_nonexistent(self, temp_db, capsys):
        result = cmd_refine_rule([
            "--session", "nonexistent", "--confirm", "--db", temp_db,
        ])
        assert result == 0

    def test_refine_answer_nonexistent(self, temp_db, capsys):
        result = cmd_refine_rule([
            "--session", "nonexistent", "--answer", "test answer",
            "--db", temp_db,
        ])
        assert result == 1


class TestCmdRefinementSessionsExtended:
    def test_sessions_with_active(self, temp_db, capsys):
        cmd_refine_rule([
            "--trigger", "database selection", "--action", "avoid MongoDB",
            "--db", temp_db,
        ])
        capsys.readouterr()
        result = cmd_refinement_sessions(["--db", temp_db])
        assert result == 0


class TestCmdListRulesExtended:
    def test_list_rules_type_filter(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--type", "prefer", "--db", temp_db])
        capsys.readouterr()
        result = cmd_list_rules(["--type", "prefer", "--db", temp_db])
        assert result == 0

    def test_list_rules_status_filter(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--db", temp_db])
        capsys.readouterr()
        result = cmd_list_rules(["--status", "active", "--db", temp_db])
        assert result == 0


class TestCmdDeleteRuleExtended:
    def test_delete_nonexistent(self, temp_db, capsys):
        result = cmd_delete_rule(["rule_nonexistent", "--db", temp_db])
        assert result == 1


class TestCmdPauseResumeExtended:
    def test_pause_nonexistent(self, temp_db, capsys):
        result = cmd_pause_rule(["rule_nonexistent", "--db", temp_db])
        assert result == 0

    def test_resume_nonexistent(self, temp_db, capsys):
        result = cmd_resume_rule(["rule_nonexistent", "--db", temp_db])
        assert result == 0
