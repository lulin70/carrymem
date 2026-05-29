"""
Tests for CarryMem CLI Rules Engine commands.

Covers: add-rule, list-rules, match-rules, edit-rule, delete-rule,
        pause-rule, resume-rule, rules-stats, check-rules,
        export-rules, import-rules, list-templates, suggest-rules,
        promote-rules, review-promotions, promotion-log,
        learn-experience, review-lessons, lesson-log,
        whoami, profile
"""

import json
import os
import tempfile

import pytest

from carrymem.cli import (
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
    cmd_whoami,
    cmd_profile,
    cmd_refine_rule,
    cmd_refinement_sessions,
)


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_rules_cli.db")


@pytest.fixture
def db_with_rule(temp_db):
    cmd_add_rule(
        [
            "prefer PostgreSQL",
            "--trigger",
            "database selection",
            "--type",
            "prefer",
            "--db",
            temp_db,
        ]
    )
    return temp_db


class TestCmdAddRule:
    def test_add_rule_basic(self, temp_db, capsys):
        result = cmd_add_rule(["prefer PostgreSQL", "--trigger", "database selection", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Rule created" in captured.out

    def test_add_rule_with_type(self, temp_db, capsys):
        result = cmd_add_rule(["avoid MongoDB", "--trigger", "database selection", "--type", "avoid", "--db", temp_db])
        assert result == 0

    def test_add_rule_hard_override(self, temp_db, capsys):
        result = cmd_add_rule(["always use SSL", "--trigger", "security design", "--type", "format", "--db", temp_db])
        assert result == 0

    def test_add_rule_missing_trigger(self, temp_db, capsys):
        result = cmd_add_rule(["some action", "--db", temp_db])
        assert result != 0


class TestCmdListRules:
    def test_list_rules_empty(self, temp_db, capsys):
        result = cmd_list_rules(["--db", temp_db])
        assert result == 0

    def test_list_rules_with_data(self, db_with_rule, capsys):
        result = cmd_list_rules(["--db", db_with_rule])
        assert result == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_list_rules_with_status_filter(self, db_with_rule, capsys):
        result = cmd_list_rules(["--status", "active", "--db", db_with_rule])
        assert result == 0


class TestCmdMatchRules:
    def test_match_rules_basic(self, db_with_rule, capsys):
        result = cmd_match_rules(["database selection", "--db", db_with_rule])
        assert result == 0

    def test_match_rules_no_match(self, temp_db, capsys):
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "database selection", "--db", temp_db])
        result = cmd_match_rules(["unrelated scene", "--db", temp_db])
        assert result == 0


class TestCmdEditRule:
    def test_edit_rule_action(self, db_with_rule, capsys):
        result = cmd_list_rules(["--db", db_with_rule])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_edit_rule([rule_id, "--action", "prefer MySQL", "--db", db_with_rule])
            assert result == 0

    def test_edit_rule_nonexistent(self, temp_db, capsys):
        result = cmd_edit_rule(["rule_nonexistent", "--action", "new action", "--db", temp_db])
        assert result != 0


class TestCmdDeleteRule:
    def test_delete_rule(self, db_with_rule, capsys):
        captured_before = capsys.readouterr()
        result = cmd_list_rules(["--db", db_with_rule])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_delete_rule([rule_id, "--db", db_with_rule])
            assert result == 0

    def test_delete_rule_nonexistent(self, temp_db, capsys):
        result = cmd_delete_rule(["rule_nonexistent", "--db", temp_db])
        assert result != 0


class TestCmdPauseResumeRule:
    def test_pause_rule(self, db_with_rule, capsys):
        result = cmd_list_rules(["--db", db_with_rule])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_pause_rule([rule_id, "--db", db_with_rule])
            assert result == 0

    def test_resume_rule(self, db_with_rule, capsys):
        result = cmd_list_rules(["--db", db_with_rule])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            cmd_pause_rule([rule_id, "--db", db_with_rule])
            capsys.readouterr()
            result = cmd_resume_rule([rule_id, "--db", db_with_rule])
            assert result == 0


class TestCmdRulesStats:
    def test_rules_stats(self, db_with_rule, capsys):
        result = cmd_rules_stats(["--db", db_with_rule])
        assert result == 0
        captured = capsys.readouterr()
        assert "Total" in captured.out or "total" in captured.out.lower()


class TestCmdCheckRules:
    def test_check_rules(self, db_with_rule, capsys):
        result = cmd_check_rules(["--db", db_with_rule])
        assert result == 0


class TestCmdExportImportRules:
    def test_export_rules(self, db_with_rule, tmp_path, capsys):
        export_path = str(tmp_path / "rules_export.json")
        result = cmd_export_rules([export_path, "--db", db_with_rule])
        assert result == 0
        assert os.path.exists(export_path)

    def test_import_rules(self, temp_db, tmp_path, capsys):
        export_path = str(tmp_path / "rules_import.json")
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "db selection", "--db", temp_db])
        capsys.readouterr()
        cmd_export_rules([export_path, "--db", temp_db])
        capsys.readouterr()
        result = cmd_import_rules([export_path, "--mode", "skip", "--db", temp_db])
        assert result == 0


class TestCmdListTemplates:
    def test_list_templates(self, capsys):
        result = cmd_list_templates([])
        assert result == 0
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestCmdSuggestRules:
    def test_suggest_rules_no_memories(self, temp_db, capsys):
        result = cmd_suggest_rules(["--db", temp_db])
        assert result == 0


class TestCmdPromoteRules:
    def test_promote_rules_no_memories(self, temp_db, capsys):
        result = cmd_promote_rules(["--db", temp_db])
        assert result == 0


class TestCmdReviewPromotions:
    def test_review_promotions_empty(self, temp_db, capsys):
        result = cmd_review_promotions(["--db", temp_db])
        assert result == 0


class TestCmdPromotionLog:
    def test_promotion_log_empty(self, temp_db, capsys):
        result = cmd_promotion_log(["--db", temp_db])
        assert result == 0


class TestCmdLearnExperience:
    def test_learn_experience_no_memories(self, temp_db, capsys):
        result = cmd_learn_experience(["--db", temp_db])
        assert result == 0


class TestCmdReviewLessons:
    def test_review_lessons_empty(self, temp_db, capsys):
        result = cmd_review_lessons(["--db", temp_db])
        assert result == 0

    def test_review_lessons_accept_invalid(self, temp_db, capsys):
        result = cmd_review_lessons(["--accept", "nonexistent_id", "--db", temp_db])
        assert result == 0

    def test_review_lessons_reject_invalid(self, temp_db, capsys):
        result = cmd_review_lessons(["--reject", "nonexistent_id", "--db", temp_db])
        assert result == 0


class TestCmdLessonLog:
    def test_lesson_log_empty(self, temp_db, capsys):
        result = cmd_lesson_log(["--db", temp_db])
        assert result == 0


class TestCmdWhoami:
    def test_whoami(self, temp_db, capsys):
        result = cmd_whoami(["--db", temp_db])
        assert result == 0


class TestCmdProfile:
    def test_profile(self, temp_db, capsys):
        result = cmd_profile(["--db", temp_db])
        assert result == 0

    def test_profile_export(self, temp_db, tmp_path, capsys):
        export_path = str(tmp_path / "profile.json")
        result = cmd_profile(["export", "--output", export_path, "--db", temp_db])
        assert result == 0


class TestCmdMatchRulesFormats:
    def test_match_rules_json_format(self, db_with_rule, capsys):
        result = cmd_match_rules(["database selection", "--format", "json", "--db", db_with_rule])
        assert result == 0
        captured = capsys.readouterr()
        assert '"rules"' in captured.out

    def test_match_rules_compact_format(self, db_with_rule, capsys):
        result = cmd_match_rules(["database selection", "--format", "compact", "--db", db_with_rule])
        assert result == 0
        captured = capsys.readouterr()
        assert "Rules:" in captured.out

    def test_match_rules_anchored_format(self, temp_db, capsys):
        cmd_add_rule(["never leak secrets", "--trigger", "security", "--type", "forbid", "--db", temp_db])
        capsys.readouterr()
        result = cmd_match_rules(["security", "--format", "anchored", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Prohibitions" in captured.out or "Rules" in captured.out

    def test_match_rules_ddd_format(self, db_with_rule, capsys):
        result = cmd_match_rules(["database selection", "--format", "ddd", "--db", db_with_rule])
        assert result == 0
        captured = capsys.readouterr()
        assert "DDD" in captured.out or "Context" in captured.out

    def test_match_rules_with_context_budget(self, db_with_rule, capsys):
        result = cmd_match_rules(
            [
                "database selection",
                "--format",
                "anchored",
                "--context-budget",
                "500",
                "--db",
                db_with_rule,
            ]
        )
        assert result == 0


class TestCmdRefineRule:
    def test_refine_rule_start(self, temp_db, capsys):
        result = cmd_refine_rule(
            [
                "--trigger",
                "database selection",
                "--action",
                "avoid MongoDB",
                "--db",
                temp_db,
            ]
        )
        assert result == 0

    def test_refine_rule_start_invalid(self, temp_db, capsys):
        result = cmd_refine_rule(
            [
                "--trigger",
                "",
                "--action",
                "",
                "--db",
                temp_db,
            ]
        )
        assert result != 0

    def test_refine_rule_answer_no_session(self, temp_db, capsys):
        result = cmd_refine_rule(
            [
                "--session",
                "nonexistent_session",
                "--answer",
                "yes",
                "--db",
                temp_db,
            ]
        )
        assert result == 0 or result == 1

    def test_refine_rule_confirm_no_session(self, temp_db, capsys):
        result = cmd_refine_rule(
            [
                "--session",
                "nonexistent_session",
                "--confirm",
                "--db",
                temp_db,
            ]
        )
        assert result == 0

    def test_refine_rule_cancel_no_session(self, temp_db, capsys):
        result = cmd_refine_rule(
            [
                "--session",
                "nonexistent_session",
                "--cancel",
                "--db",
                temp_db,
            ]
        )
        assert result == 0


class TestCmdRefinementSessions:
    def test_refinement_sessions_empty(self, temp_db, capsys):
        result = cmd_refinement_sessions(["--db", temp_db])
        assert result == 0

    def test_refinement_sessions_with_session(self, temp_db, capsys):
        cmd_refine_rule(
            [
                "--trigger",
                "database selection",
                "--action",
                "avoid MongoDB",
                "--db",
                temp_db,
            ]
        )
        capsys.readouterr()
        result = cmd_refinement_sessions(["--db", temp_db])
        assert result == 0


class TestCmdAddRuleExtended:
    def test_add_rule_with_template(self, temp_db, capsys):
        result = cmd_add_rule(
            [
                "always use SSL",
                "--trigger",
                "security design",
                "--type",
                "always",
                "--db",
                temp_db,
            ]
        )
        assert result == 0

    def test_add_rule_forbid_type(self, temp_db, capsys):
        result = cmd_add_rule(
            [
                "never leak secrets",
                "--trigger",
                "security",
                "--type",
                "forbid",
                "--db",
                temp_db,
            ]
        )
        assert result == 0

    def test_add_rule_override(self, temp_db, capsys):
        result = cmd_add_rule(
            [
                "always check SQL injection",
                "--trigger",
                "code review",
                "--type",
                "always",
                "--db",
                temp_db,
            ]
        )
        assert result == 0


class TestCmdEditRuleExtended:
    def test_edit_rule_trigger(self, db_with_rule, capsys):
        result = cmd_list_rules(["--db", db_with_rule])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_edit_rule([rule_id, "--trigger", "new trigger", "--db", db_with_rule])
            assert result == 0

    def test_edit_rule_type(self, db_with_rule, capsys):
        result = cmd_list_rules(["--db", db_with_rule])
        captured = capsys.readouterr()
        rule_id = None
        for line in captured.out.split("\n"):
            if line.strip().startswith("rule_"):
                rule_id = line.strip().split()[0]
                break
        if rule_id:
            result = cmd_edit_rule([rule_id, "--type", "avoid", "--db", db_with_rule])
            assert result == 0


class TestCmdImportRulesExtended:
    def test_import_rules_overwrite(self, temp_db, tmp_path, capsys):
        export_path = str(tmp_path / "rules_overwrite.json")
        cmd_add_rule(["prefer PostgreSQL", "--trigger", "db", "--db", temp_db])
        capsys.readouterr()
        cmd_export_rules([export_path, "--db", temp_db])
        capsys.readouterr()
        result = cmd_import_rules([export_path, "--mode", "overwrite", "--db", temp_db])
        assert result == 0
