"""
Comprehensive Integration Tests for Scope and Skill

Extended end-to-end tests covering:
- Multi-engine Skill distribution workflow
- Merge protocol with audit trail verification
- Scope boundary enforcement across all operations
- Cross-module data integrity with concurrent operations
- Injector format consistency with scope labels
- Skill versioning and upgrade scenarios
"""

import json
import pytest
import tempfile
import os

from carrymem.rules import RuleEngine
from carrymem.rules.models import Rule, SCOPE_PRIORITY
from carrymem.rules.skill import skill_pack, skill_verify, skill_install
from carrymem.rules.merge_protocol import (
    MergeStrategy,
    MergeDecision,
    MergeConflict,
    MergeResult,
    merge_rules,
    review_incoming_rules,
)
from carrymem.rules.storage import RuleStorage


class TestSkillDistributionWorkflow:
    """Simulate team lead → multiple developers Skill distribution"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.lead_db = os.path.join(self.tmpdir, "lead.db")
        self.lead = RuleEngine(self.lead_db)

    def teardown_method(self):
        for f in [self.lead_db]:
            if os.path.exists(f):
                os.remove(f)

    def test_distribute_skill_to_multiple_developers(self):
        self.lead.add_rule("database", "Always use SSL", scope="company", override=True)
        self.lead.add_rule("api", "Require authentication", scope="company", override=True)
        self.lead.add_rule("security", "Never log passwords", scope="company", rule_type="forbid", override=True)

        bundle = self.lead.skill_pack(
            name="company-security-v1",
            version="1.0.0",
            scope="company",
            author="security-team",
        )

        developer_dbs = []
        try:
            for i in range(3):
                dev_db = os.path.join(self.tmpdir, f"dev_{i}.db")
                developer_dbs.append(dev_db)
                dev_engine = RuleEngine(dev_db)
                dev_engine.add_rule("style", f"Use tabs (dev {i})", scope="personal")

                result = dev_engine.skill_install(bundle, scope_override="company")
                assert result["installed"] == 3
                assert result["errors"] == []

                company_rules = dev_engine.list_rules(scope="company")
                assert len(company_rules) == 3

                personal_rules = dev_engine.list_rules(scope="personal")
                assert len(personal_rules) == 1
        finally:
            for db in developer_dbs:
                if os.path.exists(db):
                    os.remove(db)

    def test_skill_upgrade_replaces_old_version(self):
        self.lead.add_rule("database", "Use SSL v1", scope="company")
        v1_bundle = self.lead.skill_pack(name="db-rules", version="1.0.0", scope="company")

        dev_db = os.path.join(self.tmpdir, "dev_upgrade.db")
        try:
            dev = RuleEngine(dev_db)
            dev.skill_install(v1_bundle, scope_override="company")

            self.lead.update_rule(
                self.lead.list_rules(scope="company")[0].id,
                action="Use SSL v2 with mTLS",
            )
            v2_bundle = self.lead.skill_pack(name="db-rules", version="2.0.0", scope="company")

            result = dev.skill_install(v2_bundle, scope_override="company", mode="rename")
            assert result["installed"] >= 1

            rules = dev.list_rules(scope="company")
            assert any("mTLS" in r.action for r in rules)
        finally:
            if os.path.exists(dev_db):
                os.remove(dev_db)

    def test_skill_with_chained_dependencies(self):
        base_rules = [Rule(trigger="security", action="Use HTTPS")]
        base_bundle = skill_pack(rules=base_rules, name="base-sec", scope="company")

        mid_rules = [Rule(trigger="api", action="Require auth")]
        mid_bundle = skill_pack(
            rules=mid_rules, name="mid-sec", scope="company",
            dependencies=["base-sec"],
        )

        top_rules = [Rule(trigger="logging", action="Audit all access")]
        top_bundle = skill_pack(
            rules=top_rules, name="top-sec", scope="company",
            dependencies=["mid-sec"],
        )

        dev_db = os.path.join(self.tmpdir, "chained.db")
        try:
            dev = RuleEngine(dev_db)

            top_result = dev.skill_install(top_bundle, scope_override="company")
            assert top_result["installed"] == 0
            assert len(top_result.get("missing_dependencies", [])) >= 1

            dev.skill_install(mid_bundle, scope_override="company")
            top_result2 = dev.skill_install(top_bundle, scope_override="company")
            assert top_result2["installed"] == 0

            dev.skill_install(base_bundle, scope_override="company")
            dev.skill_install(mid_bundle, scope_override="company", mode="overwrite")
            top_result3 = dev.skill_install(top_bundle, scope_override="company", mode="overwrite")
            assert top_result3["installed"] == 1
        finally:
            if os.path.exists(dev_db):
                os.remove(dev_db)


class TestMergeAuditTrail:
    """Verify merge decisions are fully audit-logged"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "audit.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_company_overrides_generates_replace_audit(self):
        self.engine.add_rule("database", "No encryption", scope="personal", override=True)
        incoming = [Rule(trigger="database", action="Always encrypt", scope="company", override=True)]

        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert len(result["audit_entries"]) >= 1

        replace_entries = [e for e in result["audit_entries"] if e["action"] == "replace"]
        assert len(replace_entries) >= 1
        assert "replaced_rule_id" in replace_entries[0]["details"]

    def test_negotiate_generates_modify_audit(self):
        self.engine.add_rule("api", "Forbid REST", scope="personal", rule_type="forbid", override=True)
        incoming = [Rule(trigger="api", action="Always use REST", scope="negotiated", rule_type="always", override=True)]

        result = self.engine.accept_rules(incoming, strategy="negotiate")
        modify_entries = [e for e in result["audit_entries"] if e["action"] == "modify"]
        assert len(modify_entries) >= 1
        assert "original_action" in modify_entries[0]["details"]
        assert "modified_action" in modify_entries[0]["details"]

    def test_keep_both_generates_accept_audit(self):
        self.engine.add_rule("style", "Use tabs", scope="personal")
        incoming = [Rule(trigger="style", action="Use spaces", scope="personal")]

        result = self.engine.accept_rules(incoming, strategy="keep_both")
        accept_entries = [e for e in result["audit_entries"] if e["action"] == "accept"]
        assert len(accept_entries) >= 1

    def test_no_conflict_generates_no_conflict_audit(self):
        incoming = [Rule(trigger="new-topic", action="new action")]
        result = self.engine.accept_rules(incoming, strategy="company_overrides")

        no_conflict = [e for e in result["audit_entries"] if e["details"].get("decision") == "no_conflict"]
        assert len(no_conflict) >= 1

    def test_review_generates_strategy_previews(self):
        self.engine.add_rule("db", "Use MySQL", scope="personal")
        incoming = [Rule(trigger="db", action="Use PostgreSQL", scope="company")]

        preview = self.engine.review_incoming_rules(incoming)
        assert "strategy_previews" in preview
        assert "company_overrides" in preview["strategy_previews"]
        assert "negotiate" in preview["strategy_previews"]
        assert "keep_both" in preview["strategy_previews"]


class TestScopeBoundaryEnforcement:
    """Verify scope boundaries hold under adversarial conditions"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "boundary.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_company_override_cannot_be_replaced_by_personal(self):
        self.engine.add_rule("security", "Always encrypt", scope="company", override=True)

        for _ in range(5):
            incoming = [Rule(trigger="security", action="Skip encryption", scope="personal", override=True)]
            self.engine.accept_rules(incoming, strategy="company_overrides")

        company = self.engine.list_rules(scope="company")
        assert any(r.action == "Always encrypt" and r.override for r in company)

    def test_scope_escalation_via_skill_install_blocked(self):
        self.engine.add_rule("database", "Use SSL", scope="company", override=True)

        rules = [Rule(trigger="database", action="Skip SSL", scope="personal", override=True)]
        bundle = skill_pack(rules=rules, name="malicious", scope="personal")

        result = self.engine.skill_install(bundle, scope_override="personal")
        assert result["installed"] >= 1

        company = self.engine.list_rules(scope="company")
        assert any(r.action == "Use SSL" and r.override for r in company)

    def test_negotiated_scope_between_company_and_personal(self):
        self.engine.add_rule("api", "Use REST v1", scope="company", override=True)
        self.engine.add_rule("api", "Use REST v2", scope="personal")

        incoming = [Rule(trigger="api", action="Use GraphQL", scope="negotiated")]
        result = self.engine.accept_rules(incoming, strategy="negotiate")

        all_rules = self.engine.list_rules(limit=200)
        scopes = [r.scope for r in all_rules if r.trigger == "api"]
        assert "company" in scopes

    def test_scope_priority_values(self):
        assert SCOPE_PRIORITY["company"] > SCOPE_PRIORITY["negotiated"]
        assert SCOPE_PRIORITY["negotiated"] > SCOPE_PRIORITY["personal"]

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            self.engine.add_rule("test", "action", scope="invalid_scope")


class TestInjectorFormatConsistency:
    """Verify all injector formats handle scope correctly"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "inject.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_structured_format_shows_scope(self):
        self.engine.add_rule("database", "Use SSL", scope="company", override=True)
        self.engine.add_rule("database", "Use ORM", scope="personal")

        output = self.engine.inject("database", format="structured")
        assert "[COMPANY]" in output

    def test_compact_format_returns_content(self):
        self.engine.add_rule("database", "Use SSL", scope="company", override=True)
        output = self.engine.inject("database", format="compact")
        assert "SSL" in output

    def test_json_format_includes_scope(self):
        self.engine.add_rule("database", "Use SSL", scope="company", override=True)
        output = self.engine.inject("database", format="json")
        data = json.loads(output)
        assert len(data["rules"]) >= 1
        assert data["rules"][0]["is_mandatory"] is True

    def test_anchored_format_shows_scope(self):
        self.engine.add_rule("database", "Never skip SSL", scope="company", rule_type="forbid", override=True)
        output = self.engine.inject("database", format="anchored")
        assert "Prohibitions" in output or "FORBID" in output

    def test_empty_scene_returns_empty(self):
        output = self.engine.inject("nonexistent topic xyz")
        assert output == ""

    def test_inject_with_context_budget(self):
        for i in range(20):
            self.engine.add_rule(f"topic-{i}", f"action-{i}", scope="personal")

        output = self.engine.inject("topic", format="structured", context_budget_tokens=200)
        assert len(output) > 0


class TestSkillFileRoundtrip:
    """Verify Skill bundles survive file serialization"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "file_rt.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_skill_json_file_roundtrip(self):
        self.engine.add_rule("database", "Use SSL", scope="company", override=True)
        self.engine.add_rule("api", "Version APIs", scope="company")

        bundle = self.engine.skill_pack(name="file-test", scope="company")

        skill_path = os.path.join(self.tmpdir, "test.skill.json")
        with open(skill_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)

        with open(skill_path, "r", encoding="utf-8") as f:
            reloaded = json.load(f)

        assert skill_verify(reloaded)["valid"] is True

        db2 = os.path.join(self.tmpdir, "restored.db")
        try:
            engine2 = RuleEngine(db2)
            result = engine2.skill_install(reloaded, scope_override="company")
            assert result["installed"] == 2
        finally:
            if os.path.exists(db2):
                os.remove(db2)

    def test_skill_with_cjk_content(self):
        self.engine.add_rule("数据库", "必须使用SSL加密", scope="company", override=True)
        self.engine.add_rule("コードレビュー", "必ずマージ前に実施", scope="company")

        bundle = self.engine.skill_pack(name="cjk-test", scope="company")
        assert skill_verify(bundle)["valid"] is True

        db2 = os.path.join(self.tmpdir, "cjk.db")
        try:
            engine2 = RuleEngine(db2)
            result = engine2.skill_install(bundle, scope_override="company")
            assert result["installed"] == 2

            rules = engine2.list_rules(scope="company")
            assert any("SSL" in r.action for r in rules)
            assert any("マージ" in r.action for r in rules)
        finally:
            if os.path.exists(db2):
                os.remove(db2)

    def test_skill_tampered_manifest_detected(self):
        self.engine.add_rule("security", "Encrypt at rest", scope="company")
        bundle = self.engine.skill_pack(name="tamper-test", scope="company")

        tampered = json.loads(json.dumps(bundle))
        tampered["manifest"]["scope"] = "personal"
        assert skill_verify(tampered)["valid"] is False

        tampered2 = json.loads(json.dumps(bundle))
        tampered2["manifest"]["version"] = "99.0.0"
        assert skill_verify(tampered2)["valid"] is False

    def test_skill_tampered_rules_detected(self):
        self.engine.add_rule("security", "Encrypt at rest", scope="company")
        bundle = self.engine.skill_pack(name="tamper-rules", scope="company")

        tampered = json.loads(json.dumps(bundle))
        tampered["rules"][0]["action"] = "Decrypt everything"
        assert skill_verify(tampered)["valid"] is False

    def test_skill_missing_signature_rejected(self):
        self.engine.add_rule("test", "action", scope="personal")
        bundle = self.engine.skill_pack(name="no-sig", scope="personal")
        del bundle["signature"]
        assert skill_verify(bundle)["valid"] is False


class TestPauseResumeIntegration:
    """Verify pause/resume works across all layers"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "pause.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_paused_rule_not_matched(self):
        rule = self.engine.add_rule("database", "Use SSL", scope="company")
        assert rule.status == "active"

        results_before = self.engine.match("database")
        assert len(results_before) >= 1

        self.engine.pause_rule(rule.id)
        results_after = self.engine.match("database")
        assert len(results_after) == 0

    def test_resumed_rule_matched_again(self):
        rule = self.engine.add_rule("database", "Use SSL", scope="company")
        self.engine.pause_rule(rule.id)

        self.engine.resume_rule(rule.id)
        results = self.engine.match("database")
        assert len(results) >= 1

    def test_paused_rule_not_injected(self):
        rule = self.engine.add_rule("database", "Use SSL", scope="company", override=True)
        self.engine.pause_rule(rule.id)

        injection = self.engine.inject("database", format="structured")
        assert "SSL" not in injection

    def test_pause_resume_via_update_rule(self):
        rule = self.engine.add_rule("test", "action", scope="personal")
        self.engine.update_rule(rule.id, status="paused")
        assert self.engine.get_rule(rule.id).status == "paused"

        self.engine.update_rule(rule.id, status="active")
        assert self.engine.get_rule(rule.id).status == "active"

    def test_pause_nonexistent_rule(self):
        result = self.engine.pause_rule("nonexistent-id")
        assert result is None

    def test_resume_nonexistent_rule(self):
        result = self.engine.resume_rule("nonexistent-id")
        assert result is None
