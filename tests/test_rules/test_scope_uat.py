"""
User Acceptance Tests for CarryMem

Simulates real user scenarios to validate the product works as expected:
- New user onboarding flow
- Team lead sharing conventions via Skill
- Developer installing team Skill
- Merge conflict resolution in realistic scenarios
- VS Code extension user workflow
- Security-sensitive scenarios
- Multi-language content support
- Rule lifecycle management
"""

import json
import pytest
import tempfile
import os

from carrymem.rules import RuleEngine
from carrymem.rules.models import Rule
from carrymem.rules.skill import skill_pack, skill_verify, skill_install
from carrymem.rules.merge_protocol import (
    MergeStrategy,
    merge_rules,
    review_incoming_rules,
)


class TestNewUserOnboarding:
    """UAT: A new user starts using CarryMem rules"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "new_user.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_user_creates_first_personal_rule(self):
        rule = self.engine.add_rule(
            "code review",
            "Always review before merge",
            scope="personal",
            rule_type="always",
        )
        assert rule.scope == "personal"
        assert rule.rule_type == "always"

        results = self.engine.match("code review")
        assert len(results) >= 1
        assert results[0].rule.action == "Always review before merge"

    def test_user_creates_multiple_rules_and_gets_report(self):
        self.engine.add_rule("database", "Use SSL", scope="personal")
        self.engine.add_rule("api", "Use REST", scope="personal")
        self.engine.add_rule("security", "Never commit secrets", scope="personal", rule_type="forbid")

        report = self.engine.get_effectiveness_report()
        assert report["total_rules"] == 3
        assert report["scope_breakdown"]["personal"] == 3

    def test_user_exports_and_imports_rules(self):
        self.engine.add_rule("style", "Use 4-space indent", scope="personal")

        exported = self.engine.export_rules()
        assert exported["format"] == "carrymem-rules-v1"
        assert len(exported["rules"]) == 1

        tmpdir2 = tempfile.mkdtemp()
        db2 = os.path.join(tmpdir2, "imported.db")
        try:
            engine2 = RuleEngine(db2)
            engine2.import_rules(exported)
            assert len(engine2.list_rules()) == 1
        finally:
            if os.path.exists(db2):
                os.remove(db2)

    def test_user_gets_injection_for_prompt(self):
        self.engine.add_rule("database", "Always use SSL", scope="personal", override=True)

        injection = self.engine.inject("database connection setup")
        assert "SSL" in injection
        assert "MANDATORY" in injection

    def test_user_deletes_rule(self):
        rule = self.engine.add_rule("test", "action", scope="personal")
        assert self.engine.count_rules() == 1

        self.engine.delete_rule(rule.id)
        assert self.engine.count_rules() == 0

    def test_user_updates_rule(self):
        rule = self.engine.add_rule("database", "Use MySQL", scope="personal")
        updated = self.engine.update_rule(rule.id, action="Use PostgreSQL")
        assert updated.action == "Use PostgreSQL"

    def test_user_checks_conflicts(self):
        self.engine.add_rule("api", "Always use REST", rule_type="always", override=True)
        self.engine.add_rule("api", "Never use REST", rule_type="forbid", override=True)

        conflicts = self.engine.check_conflicts()
        assert len(conflicts) >= 1


class TestTeamLeadSharesConventions:
    """UAT: A team lead creates and shares a Skill bundle"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "team_lead.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_team_lead_creates_company_skill(self):
        self.engine.add_rule("database", "Always use SSL", scope="company", override=True)
        self.engine.add_rule("api", "Require authentication", scope="company", override=True)
        self.engine.add_rule("security", "Never log passwords", scope="company", rule_type="forbid", override=True)

        bundle = self.engine.skill_pack(
            name="company-security-conventions",
            version="1.0.0",
            scope="company",
            author="security-team",
            description="Company-wide security conventions",
            tags=["security", "mandatory"],
        )

        assert bundle["manifest"]["name"] == "company-security-conventions"
        assert bundle["manifest"]["scope"] == "company"
        assert bundle["manifest"]["rule_count"] == 3

        verify = RuleEngine.skill_verify(bundle)
        assert verify["valid"] is True

        skill_path = os.path.join(self.tmpdir, "company-security.skill.json")
        with open(skill_path, "w") as f:
            json.dump(bundle, f, indent=2)
        assert os.path.exists(skill_path)

    def test_skill_file_can_be_reloaded(self):
        self.engine.add_rule("test", "action", scope="company")
        bundle = self.engine.skill_pack(name="reload-test", scope="company")

        skill_path = os.path.join(self.tmpdir, "reload-test.skill.json")
        with open(skill_path, "w") as f:
            json.dump(bundle, f, indent=2)

        with open(skill_path, "r") as f:
            reloaded = json.load(f)

        assert skill_verify(reloaded)["valid"] is True

        tmpdir2 = tempfile.mkdtemp()
        db2 = os.path.join(tmpdir2, "reloaded.db")
        try:
            engine2 = RuleEngine(db2)
            result = engine2.skill_install(reloaded, scope_override="company")
            assert result["installed"] == 1
        finally:
            if os.path.exists(db2):
                os.remove(db2)

    def test_team_lead_creates_skill_with_dependencies(self):
        self.engine.add_rule("base-security", "Use HTTPS", scope="company")
        base_bundle = self.engine.skill_pack(
            name="base-security",
            scope="company",
            dependencies=[],
        )
        assert base_bundle["manifest"]["dependencies"] == []


class TestDeveloperInstallsTeamSkill:
    """UAT: A developer installs a team Skill alongside personal rules"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "developer.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_developer_has_personal_rules_installs_company_skill(self):
        self.engine.add_rule("database", "Prefer PostgreSQL", scope="personal")
        self.engine.add_rule("style", "Use tabs", scope="personal")

        company_rules = [
            Rule(trigger="database", action="Always use SSL", scope="company", override=True),
            Rule(
                trigger="security",
                action="Never commit secrets",
                scope="company",
                rule_type="forbid",
                override=True,
            ),
        ]
        company_bundle = skill_pack(rules=company_rules, name="company-conventions", scope="company")

        result = self.engine.skill_install(company_bundle, scope_override="company")
        assert result["installed"] == 2

        all_rules = self.engine.list_rules(limit=200)
        assert len(all_rules) == 4

        company = self.engine.list_rules(scope="company")
        assert len(company) == 2

        personal = self.engine.list_rules(scope="personal")
        assert len(personal) == 2

    def test_company_rules_override_personal_in_matching(self):
        self.engine.add_rule("database", "No SSL needed", scope="personal", override=True)

        company_rules = [Rule(trigger="database", action="Always use SSL", scope="company", override=True)]
        bundle = skill_pack(rules=company_rules, name="company-ssl", scope="company")
        self.engine.skill_install(bundle, scope_override="company")

        results = self.engine.match("database", scopes=["company"])
        assert len(results) >= 1
        assert results[0].rule.action == "Always use SSL"

    def test_developer_receives_updated_skill(self):
        company_rules = [Rule(trigger="api", action="Use REST v1", scope="company")]
        v1_bundle = skill_pack(rules=company_rules, name="api-rules", version="1.0.0", scope="company")
        self.engine.skill_install(v1_bundle, scope_override="company")

        v2_rules = [Rule(trigger="api", action="Use REST v2", scope="company")]
        v2_bundle = skill_pack(rules=v2_rules, name="api-rules", version="2.0.0", scope="company")
        result = self.engine.skill_install(v2_bundle, scope_override="company", mode="rename")
        assert result["installed"] >= 1


class TestMergeConflictResolution:
    """UAT: Realistic merge conflict scenarios"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "merge_uat.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_new_team_member_merges_with_existing_rules(self):
        self.engine.add_rule("code review", "Use PR template", scope="company", override=True)
        self.engine.add_rule("testing", "Write unit tests", scope="personal")

        incoming = [
            Rule(trigger="code review", action="Use PR template v2", scope="company", override=True),
            Rule(trigger="testing", action="Write integration tests", scope="personal"),
            Rule(trigger="deployment", action="Use CI/CD", scope="company"),
        ]

        preview = self.engine.review_incoming_rules(incoming)
        assert preview["conflict_count"] >= 1

        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert result["accepted_count"] >= 1

    def test_negotiate_merge_adapts_conflicting_rules(self):
        self.engine.add_rule("api design", "Use REST only", scope="personal", rule_type="always", override=True)

        incoming = [
            Rule(
                trigger="api design",
                action="Use GraphQL",
                scope="negotiated",
                rule_type="forbid",
                override=True,
            )
        ]

        result = self.engine.accept_rules(incoming, strategy="negotiate")
        assert result["accepted_count"] >= 1

        all_rules = self.engine.list_rules(limit=200)
        negotiated = [r for r in all_rules if r.scope == "negotiated"]
        assert len(negotiated) >= 1
        assert negotiated[0].override is False

    def test_company_overrides_never_loses_company_rules(self):
        self.engine.add_rule("security", "Always encrypt", scope="company", override=True)

        incoming = [
            Rule(
                trigger="security",
                action="Skip encryption for dev",
                scope="personal",
                override=True,
            )
        ]
        result = self.engine.accept_rules(incoming, strategy="company_overrides")

        company = self.engine.list_rules(scope="company")
        assert any(r.action == "Always encrypt" for r in company)

    def test_merge_with_no_conflicts(self):
        self.engine.add_rule("database", "Use SSL", scope="personal")

        incoming = [Rule(trigger="api", action="Version APIs", scope="personal")]
        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert result["accepted_count"] == 1
        assert result["conflict_count"] == 0


class TestVSCodeExtensionWorkflow:
    """UAT: Simulate VS Code extension interactions"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "vscode.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_list_rules_for_tree_view(self):
        self.engine.add_rule("db", "Use SSL", scope="company")
        self.engine.add_rule("style", "Use tabs", scope="personal")
        self.engine.add_rule("api", "Version APIs", scope="negotiated")

        all_rules = self.engine.list_rules(limit=200)
        assert len(all_rules) == 3

        company = self.engine.list_rules(scope="company")
        personal = self.engine.list_rules(scope="personal")
        negotiated = self.engine.list_rules(scope="negotiated")
        assert len(company) == 1
        assert len(personal) == 1
        assert len(negotiated) == 1

    def test_add_rule_via_editor(self):
        rule = self.engine.add_rule(
            "new topic",
            "new action",
            scope="company",
            rule_type="always",
            override=True,
        )
        assert rule.scope == "company"
        assert rule.rule_type == "always"

    def test_toggle_rule_pause_resume(self):
        rule = self.engine.add_rule("test", "action", scope="personal")
        assert rule.status == "active"

        paused = self.engine.pause_rule(rule.id)
        assert paused.status == "paused"

        resumed = self.engine.resume_rule(rule.id)
        assert resumed.status == "active"

    def test_effectiveness_report_for_dashboard(self):
        self.engine.add_rule("a", "a1", scope="company")
        self.engine.add_rule("b", "b1", scope="personal")

        report = self.engine.get_effectiveness_report()
        assert "total_rules" in report
        assert "scope_breakdown" in report
        assert "type_breakdown" in report
        assert "top_triggered" in report

    def test_skill_pack_from_ui(self):
        self.engine.add_rule("convention", "Use camelCase", scope="company")

        bundle = self.engine.skill_pack(name="ui-export", scope="company")
        assert bundle["format"] == "carrymem-skill-v1"

    def test_skill_install_from_ui(self):
        rules = [Rule(trigger="new", action="rule", scope="company")]
        bundle = skill_pack(rules=rules, name="ui-import", scope="company")

        result = self.engine.skill_install(bundle, scope_override="company")
        assert result["installed"] == 1

    def test_search_rules_from_ui(self):
        self.engine.add_rule("database connection", "Use SSL", scope="company")
        self.engine.add_rule("database query", "Use ORM", scope="personal")

        results = self.engine.search_rules("database")
        assert len(results) >= 1

    def test_get_rule_detail(self):
        rule = self.engine.add_rule("test", "action", scope="personal")
        retrieved = self.engine.get_rule(rule.id)
        assert retrieved is not None
        assert retrieved.trigger == "test"


class TestEndToEndSecurityScenario:
    """UAT: Security-sensitive scenarios"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "security.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_tampered_skill_is_rejected(self):
        self.engine.add_rule("security", "Encrypt at rest", scope="company")
        bundle = self.engine.skill_pack(name="security-bundle", scope="company")

        tampered = json.loads(json.dumps(bundle))
        tampered["manifest"]["scope"] = "personal"
        assert skill_verify(tampered)["valid"] is False

        result = self.engine.skill_install(tampered)
        assert result["installed"] == 0

    def test_personal_rule_never_overrides_company(self):
        self.engine.add_rule("database", "Always encrypt", scope="company", override=True)

        incoming = [
            Rule(
                trigger="database",
                action="Skip encryption for dev",
                scope="personal",
                override=True,
            )
        ]

        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert result["skipped_count"] >= 1 or result["accepted_count"] == 0

        company_rules = self.engine.list_rules(scope="company")
        assert any(r.action == "Always encrypt" for r in company_rules)

    def test_scope_escalation_via_skill_is_detected(self):
        rules = [Rule(trigger="test", action="a", scope="personal")]
        bundle = skill_pack(rules=rules, name="escalation-test", scope="personal")

        tampered = json.loads(json.dumps(bundle))
        tampered["manifest"]["scope"] = "company"
        assert skill_verify(tampered)["valid"] is False

    def test_company_rule_survives_negotiate(self):
        self.engine.add_rule("security", "Always encrypt", scope="company", override=True)

        incoming = [Rule(trigger="security", action="Skip encryption", scope="personal", override=True)]
        self.engine.accept_rules(incoming, strategy="negotiate")

        company = self.engine.list_rules(scope="company")
        assert any(r.action == "Always encrypt" and r.override for r in company)


class TestMultiLanguageContent:
    """UAT: Multi-language content support"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "i18n.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_chinese_rules(self):
        rule = self.engine.add_rule("数据库", "必须使用SSL加密连接", scope="company", override=True)
        assert rule.trigger == "数据库"
        assert rule.action == "必须使用SSL加密连接"

        results = self.engine.match("数据库")
        assert len(results) >= 1

    def test_japanese_rules(self):
        rule = self.engine.add_rule("コードレビュー", "マージ前に必ずレビュー", scope="personal")
        assert rule.trigger == "コードレビュー"

        results = self.engine.match("コードレビュー")
        assert len(results) >= 1

    def test_mixed_language_skill(self):
        self.engine.add_rule("database", "Use SSL", scope="company")
        self.engine.add_rule("数据库", "必须使用SSL", scope="company")
        self.engine.add_rule("データベース", "SSLを使用", scope="company")

        bundle = self.engine.skill_pack(name="i18n-rules", scope="company")
        assert skill_verify(bundle)["valid"] is True
        assert bundle["manifest"]["rule_count"] == 3


class TestRuleLifecycleManagement:
    """UAT: Full rule lifecycle from creation to deprecation"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "lifecycle.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_rule_crud_lifecycle(self):
        rule = self.engine.add_rule("test", "initial action", scope="personal")
        assert rule.status == "active"

        updated = self.engine.update_rule(rule.id, action="updated action")
        assert updated.action == "updated action"

        retrieved = self.engine.get_rule(rule.id)
        assert retrieved.action == "updated action"

        assert self.engine.delete_rule(rule.id) is True
        assert self.engine.get_rule(rule.id) is None

    def test_rule_pause_deprecate_lifecycle(self):
        rule = self.engine.add_rule("test", "action", scope="personal")

        self.engine.pause_rule(rule.id)
        assert self.engine.get_rule(rule.id).status == "paused"

        self.engine.update_rule(rule.id, status="deprecated")
        assert self.engine.get_rule(rule.id).status == "deprecated"

    def test_rule_trigger_count_increments(self):
        self.engine.add_rule("database", "Use SSL", scope="personal")

        results = self.engine.match("database")
        assert len(results) >= 1

        rule = self.engine.list_rules()[0]
        assert rule.trigger_count >= 1

    def test_rule_scope_migration(self):
        rule = self.engine.add_rule("test", "action", scope="personal")
        assert rule.scope == "personal"

        updated = self.engine.update_rule(rule.id, scope="company")
        assert updated.scope == "company"

    def test_bulk_rules_effectiveness_report(self):
        for i in range(10):
            scope = ["personal", "company", "negotiated"][i % 3]
            self.engine.add_rule(f"topic-{i}", f"action-{i}", scope=scope)

        report = self.engine.get_effectiveness_report()
        assert report["total_rules"] == 10
        assert report["active"] == 10
        assert "scope_breakdown" in report
