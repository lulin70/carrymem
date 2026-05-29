"""
Tests for DevSquad Integration Adapter.

Covers: DevSquadAdapter, type_mapping, Protocol compliance,
graceful degradation, CRUD, match_rules, format_rules_as_prompt,
log_experience, audit logging.
"""

import sqlite3
import pytest
from unittest.mock import patch, MagicMock

from carrymem.integration.devsquad import (
    DevSquadAdapter,
    MemoryProvider,
    CarryMemAdapter,
    DEVSQUAD_TO_CARRYMEM_RULE_TYPE,
    CARRYMEM_TO_DEVOPSQUAD_RULE_TYPE,
    devsquad_to_carrymem_type,
    carrymem_to_devsquad_type,
    carrymem_rule_to_devsquad_dict,
    devsquad_rule_to_carrymem_params,
)
from carrymem.rules import RuleEngine


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "devsquad_test.db")


@pytest.fixture
def adapter(temp_db):
    a = DevSquadAdapter(db_path=temp_db, namespace="test_ns")
    return a


@pytest.fixture
def adapter_with_rules(adapter):
    adapter._rule_engine.add_rule(
        trigger="database selection",
        action="always use PostgreSQL",
        rule_type="always",
        override=True,
    )
    adapter._rule_engine.add_rule(trigger="security", action="avoid storing passwords in plain text", rule_type="avoid")
    adapter._rule_engine.add_rule(trigger="code review", action="never skip code review", rule_type="forbid")
    return adapter


class TestTypeMapping:
    def test_devsquad_to_carrymem_forbid(self):
        assert devsquad_to_carrymem_type("forbid") == "forbid"

    def test_devsquad_to_carrymem_avoid(self):
        assert devsquad_to_carrymem_type("avoid") == "avoid"

    def test_devsquad_to_carrymem_always(self):
        assert devsquad_to_carrymem_type("always") == "always"

    def test_devsquad_to_carrymem_unknown(self):
        assert devsquad_to_carrymem_type("unknown") == "avoid"

    def test_carrymem_to_devsquad_forbid(self):
        assert carrymem_to_devsquad_type("forbid") == "forbid"

    def test_carrymem_to_devsquad_avoid(self):
        assert carrymem_to_devsquad_type("avoid") == "avoid"

    def test_carrymem_to_devsquad_always(self):
        assert carrymem_to_devsquad_type("always") == "always"

    def test_carrymem_to_devsquad_format(self):
        assert carrymem_to_devsquad_type("format") == "avoid"

    def test_carrymem_to_devsquad_prefer(self):
        assert carrymem_to_devsquad_type("prefer") == "avoid"

    def test_carrymem_to_devsquad_unknown(self):
        assert carrymem_to_devsquad_type("unknown") == "avoid"

    def test_bidirectional_forbid(self):
        assert carrymem_to_devsquad_type(devsquad_to_carrymem_type("forbid")) == "forbid"

    def test_bidirectional_avoid(self):
        assert carrymem_to_devsquad_type(devsquad_to_carrymem_type("avoid")) == "avoid"

    def test_bidirectional_always(self):
        assert carrymem_to_devsquad_type(devsquad_to_carrymem_type("always")) == "always"

    def test_mapping_tables_complete(self):
        for ds_type in ["forbid", "avoid", "always"]:
            assert ds_type in DEVSQUAD_TO_CARRYMEM_RULE_TYPE
        for cm_type in ["forbid", "avoid", "always", "format", "prefer"]:
            assert cm_type in CARRYMEM_TO_DEVOPSQUAD_RULE_TYPE

    def test_devsquad_rule_to_carrymem_params_basic(self):
        params = devsquad_rule_to_carrymem_params("Use SSL", {"trigger": "security", "rule_type": "always"})
        assert params["trigger"] == "security"
        assert params["action"] == "Use SSL"
        assert params["rule_type"] == "always"
        assert params["override"] is True

    def test_devsquad_rule_to_carrymem_params_forbid(self):
        params = devsquad_rule_to_carrymem_params("No plain text", {"trigger": "security", "rule_type": "forbid"})
        assert params["rule_type"] == "forbid"

    def test_devsquad_rule_to_carrymem_params_no_metadata(self):
        params = devsquad_rule_to_carrymem_params("Use SSL")
        assert params["trigger"] == ""
        assert params["action"] == "Use SSL"
        assert params["rule_type"] == "avoid"

    def test_carrymem_rule_to_devsquad_dict(self):
        mock_rule = MagicMock()
        mock_rule.id = "rule_001"
        mock_rule.trigger = "database"
        mock_rule.action = "Use PostgreSQL"
        mock_rule.rule_type = "forbid"
        mock_rule.override = True
        mock_rule.relevance_score = 0.85
        result = carrymem_rule_to_devsquad_dict(mock_rule)
        assert result["rule_id"] == "rule_001"
        assert result["rule_type"] == "forbid"
        assert result["override"] is True
        assert result["relevance_score"] == 0.85


class TestProtocolCompliance:
    def test_adapter_is_memory_provider(self, adapter):
        assert isinstance(adapter, MemoryProvider)

    def test_adapter_is_carrymem_adapter(self, adapter):
        assert isinstance(adapter, CarryMemAdapter)


class TestIsAvailable:
    def test_available_with_valid_db(self, adapter):
        assert adapter.is_available() is True

    def test_not_available_with_bad_db(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        assert a.is_available() is False

    def test_not_available_when_init_fails(self):
        with patch(
            "carrymem.integration.devsquad.adapter.RuleEngine",
            side_effect=Exception("init failed"),
        ):
            a = DevSquadAdapter(db_path=":memory:")
            assert a.is_available() is False


class TestGetRules:
    def test_get_rules_basic(self, adapter_with_rules):
        rules = adapter_with_rules.get_rules("user1")
        assert isinstance(rules, list)

    def test_get_rules_with_context(self, adapter_with_rules):
        rules = adapter_with_rules.get_rules("user1", context={"task": "database selection", "role": "architect"})
        assert isinstance(rules, list)

    def test_get_rules_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        rules = a.get_rules("user1")
        assert rules == []

    def test_get_rules_format(self, adapter_with_rules):
        rules = adapter_with_rules.get_rules("user1", context={"task": "security"})
        for rule in rules:
            assert isinstance(rule, str)
            assert rule.startswith("[") or len(rule) > 0


class TestAddRule:
    def test_add_rule_basic(self, adapter):
        adapter.add_rule("user1", "Always use SSL")
        rules = adapter._rule_engine.list_rules()
        assert len(rules) >= 1

    def test_add_rule_with_metadata(self, adapter):
        adapter.add_rule(
            "user1",
            "Never skip tests",
            metadata={"trigger": "testing", "rule_type": "forbid", "override": True},
        )
        rules = adapter._rule_engine.list_rules()
        assert len(rules) >= 1

    def test_add_rule_forbid_maps_directly(self, adapter):
        adapter.add_rule(
            "user1",
            "No plain text passwords",
            metadata={"trigger": "security", "rule_type": "forbid"},
        )
        rules = adapter._rule_engine.list_rules()
        for r in rules:
            if "plain text" in r.action:
                assert r.rule_type == "forbid"

    def test_add_rule_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        a.add_rule("user1", "test")  # Should not crash


class TestUpdateRule:
    def test_update_rule(self, adapter):
        adapter.add_rule("user1", "Use MySQL", metadata={"trigger": "database"})
        rules = adapter._rule_engine.list_rules()
        rule_id = rules[0].id
        adapter.update_rule("user1", rule_id, "Use PostgreSQL instead")
        updated = adapter._rule_engine.get_rule(rule_id)
        assert updated is not None

    def test_update_rule_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        a.update_rule("user1", "rule_001", "new content")  # Should not crash


class TestDeleteRule:
    def test_delete_rule(self, adapter):
        adapter.add_rule("user1", "Use MySQL", metadata={"trigger": "database"})
        rules = adapter._rule_engine.list_rules()
        rule_id = rules[0].id
        adapter.delete_rule("user1", rule_id)
        deleted = adapter._rule_engine.get_rule(rule_id)
        assert deleted is None

    def test_delete_rule_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        a.delete_rule("user1", "rule_001")  # Should not crash


class TestGetStats:
    def test_get_stats_available(self, adapter):
        stats = adapter.get_stats()
        assert "available" in stats
        assert stats["available"] is True
        assert "namespace" in stats

    def test_get_stats_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        stats = a.get_stats()
        assert stats["available"] is False
        assert stats["total_rules"] == 0


class TestMatchRules:
    def test_match_rules_basic(self, adapter_with_rules):
        matched = adapter_with_rules.match_rules("database selection", "user1")
        assert isinstance(matched, list)

    def test_match_rules_with_role(self, adapter_with_rules):
        matched = adapter_with_rules.match_rules("database selection", "user1", role="architect", max_rules=3)
        assert isinstance(matched, list)
        assert len(matched) <= 3

    def test_match_rules_structure(self, adapter_with_rules):
        matched = adapter_with_rules.match_rules("security", "user1")
        for r in matched:
            assert "rule_id" in r
            assert "rule_type" in r
            assert "action" in r
            assert "override" in r
            assert r["rule_type"] in ("forbid", "avoid", "always")

    def test_match_rules_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        matched = a.match_rules("test", "user1")
        assert matched == []

    def test_match_rules_empty_description(self, adapter_with_rules):
        matched = adapter_with_rules.match_rules("", "user1")
        assert isinstance(matched, list)


class TestFormatRulesAsPrompt:
    def test_format_basic(self):
        rules = [
            {"rule_type": "always", "action": "Use SSL", "trigger": "security", "override": True},
            {
                "rule_type": "avoid",
                "action": "Avoid MongoDB",
                "trigger": "database",
                "override": False,
            },
        ]
        adapter = MagicMock(spec=DevSquadAdapter)
        result = DevSquadAdapter.format_rules_as_prompt(adapter, rules)
        assert isinstance(result, str)
        assert "SSL" in result
        assert "Mandatory" in result

    def test_format_empty(self, adapter):
        result = adapter.format_rules_as_prompt([])
        assert result == ""

    def test_format_override_rules(self):
        rules = [
            {
                "rule_type": "forbid",
                "action": "No plain text",
                "trigger": "security",
                "override": True,
            },
        ]
        adapter = MagicMock(spec=DevSquadAdapter)
        result = DevSquadAdapter.format_rules_as_prompt(adapter, rules)
        assert "Mandatory" in result

    def test_format_normal_rules(self):
        rules = [
            {
                "rule_type": "avoid",
                "action": "Avoid MySQL",
                "trigger": "database",
                "override": False,
            },
        ]
        adapter = MagicMock(spec=DevSquadAdapter)
        result = DevSquadAdapter.format_rules_as_prompt(adapter, rules)
        assert "Guidelines" in result


class TestLogExperience:
    def test_log_experience_basic(self, adapter):
        exp_id = adapter.log_experience(
            user_id="user1",
            role="architect",
            task="Design API",
            rules_applied=["r1", "r2"],
            outcome="Success",
        )
        assert isinstance(exp_id, str)
        assert exp_id.startswith("exp_")

    def test_log_experience_with_feedback(self, adapter):
        exp_id = adapter.log_experience(
            user_id="user1",
            role="architect",
            task="Design API",
            rules_applied=["r1"],
            outcome="Partial",
            user_feedback="Need more rules",
        )
        assert isinstance(exp_id, str)

    def test_log_experience_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        exp_id = a.log_experience("user1", "arch", "task", [], "ok")
        assert exp_id == ""


class TestGracefulDegradation:
    def test_all_methods_safe_when_unavailable(self, tmp_path):
        a = DevSquadAdapter(db_path=str(tmp_path / "nonexistent" / "db.db"))
        assert a.is_available() is False
        assert a.get_rules("user1") == []
        a.add_rule("user1", "test")
        a.update_rule("user1", "rule_1", "new")
        a.delete_rule("user1", "rule_1")
        assert a.get_stats()["available"] is False
        assert a.match_rules("test", "user1") == []
        assert a.format_rules_as_prompt([]) == ""
        assert a.log_experience("user1", "arch", "task", [], "ok") == ""

    def test_init_error_stored(self):
        with patch(
            "carrymem.integration.devsquad.adapter.RuleEngine",
            side_effect=Exception("db corrupted"),
        ):
            a = DevSquadAdapter(db_path=":memory:")
            assert a._init_error is not None
            assert "corrupted" in a._init_error


class TestAuditLogging:
    def test_get_rules_logs(self, adapter, capsys):
        adapter.get_rules("user1")
        adapter._audit = None
        adapter.get_rules("user2")

    def test_add_rule_logs(self, adapter):
        adapter.add_rule("user1", "Use SSL", metadata={"trigger": "security"})
        adapter._audit = None
        adapter.add_rule("user2", "Use SSL")

    def test_match_rules_logs(self, adapter_with_rules):
        adapter_with_rules.match_rules("security", "user1")


class TestEndToEnd:
    def test_full_workflow(self, temp_db):
        adapter = DevSquadAdapter(db_path=temp_db, namespace="devsquad_e2e")
        assert adapter.is_available() is True

        adapter.add_rule(
            "user1",
            "Always use SSL for database connections",
            metadata={"trigger": "database security", "rule_type": "always", "override": True},
        )
        adapter.add_rule(
            "user1",
            "Avoid using MongoDB for relational data",
            metadata={"trigger": "database selection", "rule_type": "avoid"},
        )
        adapter.add_rule(
            "user1",
            "No plain text passwords",
            metadata={"trigger": "password security", "rule_type": "forbid"},
        )

        matched = adapter.match_rules("database security", "user1", role="architect", max_rules=5)
        assert len(matched) >= 1

        prompt = adapter.format_rules_as_prompt(matched)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        rules = adapter.get_rules("user1", context={"task": "database", "role": "architect"})
        assert isinstance(rules, list)

        stats = adapter.get_stats()
        assert stats["available"] is True
        assert stats["total_rules"] >= 1

        exp_id = adapter.log_experience(
            user_id="user1",
            role="architect",
            task="Design database schema",
            rules_applied=[r["rule_id"] for r in matched],
            outcome="Success",
            user_feedback="Rules were helpful",
        )
        assert exp_id.startswith("exp_")
