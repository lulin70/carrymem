"""
Tests for RuleEngine facade methods (skill_pack/verify/install/review/accept)
Targets uncovered lines in rules/__init__.py
"""

import os
import tempfile

import pytest

from carrymem.rules import RuleEngine
from carrymem.rules.models import Rule
from carrymem.rules.skill import skill_pack


class TestRuleEngineSkillFacade:
    """Test RuleEngine.skill_pack/verify/install facade methods"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "facade.db")
        self.engine = RuleEngine(self.db_path)
        self.engine.add_rule("database", "use SSL", scope="company")
        self.engine.add_rule("code review", "check security", scope="personal")

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_skill_pack_facade(self):
        bundle = self.engine.skill_pack(name="test-skill", scope="company")
        assert bundle["format"] == "carrymem-skill-v1"
        assert bundle["manifest"]["name"] == "test-skill"
        assert bundle["manifest"]["rule_count"] == 2

    def test_skill_verify_facade(self):
        bundle = self.engine.skill_pack(name="test-skill")
        result = RuleEngine.skill_verify(bundle)
        assert result["valid"] is True

    def test_skill_install_facade(self):
        rules = [Rule(trigger="new-topic", action="new action")]
        bundle = skill_pack(rules=rules, name="install-test")

        result = self.engine.skill_install(bundle)
        assert result["installed"] == 1

    def test_skill_install_with_scope_override(self):
        rules = [Rule(trigger="override-test", action="a")]
        bundle = skill_pack(rules=rules, name="scope-override-test", scope="personal")

        result = self.engine.skill_install(bundle, scope_override="company")
        assert result["scope"] == "company"

    def test_skill_pack_with_options(self):
        bundle = self.engine.skill_pack(
            name="full-test",
            version="2.0.0",
            author="tester",
            description="Full test bundle",
            scope="company",
            dependencies=["base-rules"],
            tags=["test", "integration"],
            config={"env": "test"},
        )
        assert bundle["manifest"]["version"] == "2.0.0"
        assert bundle["manifest"]["author"] == "tester"
        assert bundle["manifest"]["dependencies"] == ["base-rules"]
        assert bundle["manifest"]["tags"] == ["test", "integration"]


class TestRuleEngineMergeFacade:
    """Test RuleEngine.review_incoming_rules/accept_rules facade methods"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "merge_facade.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_review_incoming_rules_facade(self):
        self.engine.add_rule("database", "use PostgreSQL", scope="personal")
        incoming = [Rule(trigger="database", action="use MySQL", scope="company")]

        result = self.engine.review_incoming_rules(incoming)
        assert "conflict_count" in result
        assert result["conflict_count"] >= 1

    def test_review_with_target_scope(self):
        incoming = [Rule(trigger="new-topic", action="do something")]
        result = self.engine.review_incoming_rules(incoming, target_scope="company")
        assert "no_conflict_count" in result

    def test_accept_rules_facade(self):
        incoming = [Rule(trigger="new-topic", action="new action")]
        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert result["accepted_count"] == 1

    def test_accept_rules_negotiate(self):
        self.engine.add_rule("db", "use PostgreSQL", scope="personal", override=True)
        incoming = [
            Rule(
                trigger="db",
                action="always use MySQL",
                scope="negotiated",
                rule_type="always",
                override=True,
            )
        ]

        result = self.engine.accept_rules(incoming, strategy="negotiate")
        assert "accepted_count" in result

    def test_accept_rules_keep_both(self):
        self.engine.add_rule("db", "use PostgreSQL", scope="personal")
        incoming = [Rule(trigger="db", action="use MySQL", scope="personal")]

        result = self.engine.accept_rules(incoming, strategy="keep_both")
        assert "accepted_count" in result

    def test_accept_rules_with_target_scope(self):
        incoming = [Rule(trigger="scoped", action="do something")]
        result = self.engine.accept_rules(incoming, strategy="company_overrides", target_scope="company")
        assert result["accepted_count"] == 1

    def test_accept_rules_with_replacement(self):
        self.engine.add_rule("db", "old rule", scope="personal")
        incoming = [Rule(trigger="db", action="new rule", scope="company", override=True)]

        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert "replaced_ids" in result
        assert len(result["replaced_ids"]) >= 1

    def test_accept_rules_error_reporting(self):
        incoming = [Rule(trigger="test", action="a")]
        result = self.engine.accept_rules(incoming, strategy="negotiate")
        assert isinstance(result, dict)
        assert "accepted_count" in result


class TestRuleEngineScopeMethods:
    """Test RuleEngine scope-aware add/list/match methods"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "scope_facade.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_add_rule_with_scope(self):
        rule = self.engine.add_rule("database", "use SSL", scope="company")
        assert rule.scope == "company"

    def test_list_rules_with_scope(self):
        self.engine.add_rule("a", "a1", scope="personal")
        self.engine.add_rule("b", "b1", scope="company")
        self.engine.add_rule("c", "c1", scope="personal")

        company = self.engine.list_rules(scope="company")
        assert len(company) == 1
        assert company[0].scope == "company"

    def test_match_with_scopes(self):
        self.engine.add_rule("database", "use SSL", scope="company", override=True)
        self.engine.add_rule("database", "prefer ORM", scope="personal")

        results = self.engine.match("database", scopes=["company"])
        assert all(r.rule.scope == "company" for r in results)

    def test_get_effectiveness_report_scope(self):
        self.engine.add_rule("a", "a1", scope="company")
        self.engine.add_rule("b", "b1", scope="personal")

        report = self.engine.get_effectiveness_report()
        assert "scope_breakdown" in report
        assert "scope_trigger_totals" in report
