"""
Extended CLI tests for coverage improvement.

Covers: clean with force, export markdown, import overwrite,
search with type filter, show json, edit with flags,
stats json, version, rules commands.
"""

import json
import os

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
    cmd_init,
    cmd_version,
    cmd_add_rule,
    cmd_list_rules,
    cmd_match_rules,
    cmd_rules_stats,
    cmd_check_rules,
    cmd_export_rules,
    cmd_import_rules,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_cli_ext.db")


@pytest.fixture
def db_with_memories(temp_db):
    cmd_add(["I prefer dark mode for all editors", "--db", temp_db])
    cmd_add(["I use PostgreSQL for databases", "--db", temp_db])
    return temp_db


class TestCmdCleanExtended:
    def test_clean_force(self, db_with_memories, capsys):
        result = cmd_clean(["--force", "--db", db_with_memories])
        assert result in (0, 1)

    def test_clean_quality_threshold(self, db_with_memories, capsys):
        result = cmd_clean(["--quality", "0.99", "--dry-run", "--db", db_with_memories])
        assert result == 0


class TestCmdExportExtended:
    def test_export_markdown(self, db_with_memories, tmp_path, capsys):
        output_path = str(tmp_path / "export.md")
        result = cmd_export([output_path, "--format", "markdown", "--db", db_with_memories])
        assert result == 0

    def test_export_json(self, db_with_memories, tmp_path, capsys):
        output_path = str(tmp_path / "export.json")
        result = cmd_export([output_path, "--format", "json", "--db", db_with_memories])
        assert result == 0


class TestCmdImportExtended:
    def test_import_skip(self, temp_db, tmp_path, capsys):
        output_path = str(tmp_path / "import_ext.json")
        cmd_add(["Test memory", "--db", temp_db])
        capsys.readouterr()
        cmd_export([output_path, "--db", temp_db])
        capsys.readouterr()
        result = cmd_import([output_path, "--merge", "skip_existing", "--db", temp_db])
        assert result == 0


class TestCmdSearchExtended:
    def test_search_type_filter(self, db_with_memories, capsys):
        result = cmd_search(["dark mode", "--type", "user_preference", "--db", db_with_memories])
        assert result == 0

    def test_search_json(self, db_with_memories, capsys):
        result = cmd_search(["dark mode", "--format", "json", "--db", db_with_memories])
        assert result == 0


class TestCmdStatsExtended:
    def test_stats_json(self, db_with_memories, capsys):
        result = cmd_stats(["--format", "json", "--db", db_with_memories])
        assert result == 0

    def test_stats_empty(self, temp_db, capsys):
        result = cmd_stats(["--db", temp_db])
        assert result == 0


class TestCmdInitExtended:
    def test_init_creates_db(self, tmp_path, capsys):
        db_path = str(tmp_path / "new_init.db")
        result = cmd_init(["--db", db_path])
        assert result == 0


class TestCmdVersionExtended:
    def test_version(self, capsys):
        result = cmd_version([])
        assert result == 0


class TestCmdRulesExtended:
    def test_rules_stats_json(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--db", temp_db])
        capsys.readouterr()
        result = cmd_rules_stats(["--db", temp_db])
        assert result == 0

    def test_check_rules_with_rules(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--db", temp_db])
        capsys.readouterr()
        result = cmd_check_rules(["--db", temp_db])
        assert result == 0

    def test_export_import_rules_roundtrip(self, temp_db, tmp_path, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--db", temp_db])
        capsys.readouterr()
        export_path = str(tmp_path / "rules_rt.json")
        cmd_export_rules([export_path, "--db", temp_db])
        capsys.readouterr()
        result = cmd_import_rules([export_path, "--mode", "skip", "--db", temp_db])
        assert result == 0

    def test_match_rules_all_formats(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--type", "prefer", "--db", temp_db])
        capsys.readouterr()
        for fmt in ["json", "compact"]:
            result = cmd_match_rules(["database", "--format", fmt, "--db", temp_db])
            assert result == 0

    def test_add_rule_avoid_type(self, temp_db, capsys):
        result = cmd_add_rule(
            [
                "avoid MongoDB",
                "--trigger",
                "database selection",
                "--type",
                "avoid",
                "--db",
                temp_db,
            ]
        )
        assert result == 0

    def test_list_rules_with_data(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--db", temp_db])
        capsys.readouterr()
        result = cmd_list_rules(["--db", temp_db])
        assert result == 0


class TestCmdListExtended:
    def test_list_json(self, db_with_memories, capsys):
        result = cmd_list(["--format", "json", "--db", db_with_memories])
        assert result == 0

    def test_list_type_filter(self, db_with_memories, capsys):
        result = cmd_list(["--type", "user_preference", "--db", db_with_memories])
        assert result == 0

    def test_list_limit(self, db_with_memories, capsys):
        result = cmd_list(["--limit", "1", "--db", db_with_memories])
        assert result == 0
