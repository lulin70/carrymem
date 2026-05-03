"""
Extended CLI tests for whoami, profile, check, and other commands.

Covers deeper code paths in cli.py for coverage improvement.
"""

import json
import os

import pytest

from memory_classification_engine import CarryMem
from memory_classification_engine.cli import (
    cmd_add,
    cmd_whoami,
    cmd_profile,
    cmd_check,
    cmd_add_rule,
    cmd_list_rules,
    cmd_match_rules,
    cmd_pause_rule,
    cmd_resume_rule,
    cmd_delete_rule,
    cmd_edit_rule,
    cmd_suggest_rules,
    cmd_promote_rules,
    cmd_review_promotions,
    cmd_promotion_log,
    cmd_learn_experience,
    cmd_review_lessons,
    cmd_lesson_log,
    cmd_list_templates,
    cmd_rules_stats,
    cmd_check_rules,
    cmd_export_rules,
    cmd_import_rules,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_cli_deep.db")


@pytest.fixture
def db_with_rules(temp_db, capsys):
    cmd_add_rule(["never leak secrets", "--trigger", "security", "--type", "forbid", "--db", temp_db])
    capsys.readouterr()
    cmd_add_rule(["prefer PostgreSQL", "--trigger", "database", "--type", "prefer", "--db", temp_db])
    capsys.readouterr()
    cmd_add_rule(["always include tests", "--trigger", "code review", "--type", "always", "--db", temp_db])
    capsys.readouterr()
    return temp_db


class TestCmdWhoami:
    def test_whoami_empty(self, temp_db, capsys):
        result = cmd_whoami(["--db", temp_db])
        assert result == 0

    def test_whoami_with_data(self, temp_db, capsys):
        cmd_add(["I prefer dark mode for all editors", "--db", temp_db])
        capsys.readouterr()
        result = cmd_whoami(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Who You Are" in captured.out or "dark mode" in captured.out


class TestCmdProfile:
    def test_profile_basic(self, temp_db, capsys):
        cmd_add(["I prefer dark mode", "--db", temp_db])
        capsys.readouterr()
        result = cmd_profile(["--db", temp_db])
        assert result == 0

    def test_profile_export(self, temp_db, tmp_path, capsys):
        cmd_add(["I prefer dark mode", "--db", temp_db])
        capsys.readouterr()
        export_path = str(tmp_path / "profile.json")
        result = cmd_profile(["export", "--output", export_path, "--db", temp_db])
        assert result == 0


class TestCmdCheck:
    def test_check_all(self, temp_db, capsys):
        cmd_add(["I prefer dark mode", "--db", temp_db])
        capsys.readouterr()
        result = cmd_check(["--db", temp_db])
        assert result == 0

    def test_check_conflicts(self, temp_db, capsys):
        result = cmd_check(["--conflicts", "--db", temp_db])
        assert result == 0

    def test_check_quality(self, temp_db, capsys):
        result = cmd_check(["--quality", "--db", temp_db])
        assert result == 0

    def test_check_expired(self, temp_db, capsys):
        result = cmd_check(["--expired", "--db", temp_db])
        assert result == 0


class TestCmdRuleLifecycle:
    def test_add_pause_resume_delete(self, temp_db, capsys):
        cmd_add_rule(["test rule", "--trigger", "test", "--db", temp_db])
        capsys.readouterr()
        output = capsys.readouterr().out

        result = cmd_list_rules(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break

        if rule_id:
            cmd_pause_rule([rule_id, "--db", temp_db])
            capsys.readouterr()
            cmd_resume_rule([rule_id, "--db", temp_db])
            capsys.readouterr()
            cmd_delete_rule([rule_id, "--db", temp_db])
            capsys.readouterr()

    def test_edit_rule_action(self, temp_db, capsys):
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
            result = cmd_edit_rule([rule_id, "--action", "updated action", "--db", temp_db])
            assert result == 0


class TestCmdMatchRulesDeep:
    def test_match_anchored_with_forbid_and_always(self, db_with_rules, capsys):
        result = cmd_match_rules(["security", "--format", "anchored", "--db", db_with_rules])
        assert result == 0
        captured = capsys.readouterr()
        assert "Prohibitions" in captured.out or "Rules" in captured.out

    def test_match_ddd_format(self, db_with_rules, capsys):
        result = cmd_match_rules(["database", "--format", "ddd", "--db", db_with_rules])
        assert result == 0
        captured = capsys.readouterr()
        assert "DDD" in captured.out or "Context" in captured.out

    def test_match_with_context_budget(self, db_with_rules, capsys):
        result = cmd_match_rules([
            "database", "--format", "anchored",
            "--context-budget", "1000", "--db", db_with_rules,
        ])
        assert result == 0


class TestCmdRulesStats:
    def test_stats_with_rules(self, db_with_rules, capsys):
        result = cmd_rules_stats(["--db", db_with_rules])
        assert result == 0
        captured = capsys.readouterr()
        assert "3" in captured.out or "rules" in captured.out.lower()


class TestCmdCheckRules:
    def test_check_with_rules(self, db_with_rules, capsys):
        result = cmd_check_rules(["--db", db_with_rules])
        assert result in (0, 1)


class TestCmdListTemplates:
    def test_list_templates(self, capsys):
        result = cmd_list_templates([])
        assert result == 0


class TestCmdSuggestRules:
    def test_suggest_no_memories(self, temp_db, capsys):
        result = cmd_suggest_rules(["--db", temp_db])
        assert result == 0


class TestCmdPromotionPipeline:
    def test_promote_no_memories(self, temp_db, capsys):
        result = cmd_promote_rules(["--db", temp_db])
        assert result == 0

    def test_review_empty(self, temp_db, capsys):
        result = cmd_review_promotions(["--db", temp_db])
        assert result == 0

    def test_log_empty(self, temp_db, capsys):
        result = cmd_promotion_log(["--db", temp_db])
        assert result == 0


class TestCmdExperienceLearning:
    def test_learn_no_memories(self, temp_db, capsys):
        result = cmd_learn_experience(["--db", temp_db])
        assert result == 0

    def test_review_empty(self, temp_db, capsys):
        result = cmd_review_lessons(["--db", temp_db])
        assert result == 0

    def test_log_empty(self, temp_db, capsys):
        result = cmd_lesson_log(["--db", temp_db])
        assert result == 0


class TestCmdExportImportRules:
    def test_export_and_import(self, db_with_rules, tmp_path, capsys):
        export_path = str(tmp_path / "rules_ei.json")
        result = cmd_export_rules([export_path, "--db", db_with_rules])
        assert result == 0
        capsys.readouterr()
        result = cmd_import_rules([export_path, "--mode", "skip", "--db", db_with_rules])
        assert result == 0
