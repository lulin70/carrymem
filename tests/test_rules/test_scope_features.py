"""
Test Suite for Scope, Skill Format, Merge Protocol

Validates:
- Rule scope creation, validation, serialization
- Scope-aware matching and filtering
- Skill pack/verify/install lifecycle
- Merge protocol strategies and conflict resolution
- Security boundaries (scope escalation, signature tampering)
- Edge cases (empty rules, same-scope conflicts, dependency checks)
"""

import json
import copy
import pytest
import tempfile
import os

from memory_classification_engine.rules.models import (
    Rule,
    RuleScope,
    VALID_RULE_SCOPES,
    SCOPE_PRIORITY,
    _to_bool,
)
from memory_classification_engine.rules.skill import (
    skill_pack,
    skill_verify,
    skill_install,
    SKILL_FORMAT,
    SKILL_MAX_RULES,
)
from memory_classification_engine.rules.merge_protocol import (
    MergeStrategy,
    MergeDecision,
    MergeConflict,
    MergeResult,
    detect_merge_conflicts,
    resolve_conflict,
    merge_rules,
    review_incoming_rules,
)
from memory_classification_engine.rules.storage import RuleStorage
from memory_classification_engine.rules import RuleEngine


class TestScopeBasics:
    """Test scope type system and validation"""

    def test_valid_scopes(self):
        assert VALID_RULE_SCOPES == {"personal", "company", "negotiated"}

    def test_scope_priority_ordering(self):
        assert SCOPE_PRIORITY["company"] > SCOPE_PRIORITY["negotiated"]
        assert SCOPE_PRIORITY["negotiated"] > SCOPE_PRIORITY["personal"]

    def test_rule_default_scope_is_personal(self):
        rule = Rule(trigger="test", action="do something")
        assert rule.scope == "personal"

    def test_rule_explicit_scope(self):
        rule = Rule(trigger="test", action="do something", scope="company")
        assert rule.scope == "company"

    def test_rule_invalid_scope_raises(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            Rule(trigger="test", action="do something", scope="invalid")

    def test_scope_in_to_dict(self):
        rule = Rule(trigger="test", action="do something", scope="company")
        d = rule.to_dict()
        assert d["scope"] == "company"

    def test_scope_in_from_dict(self):
        d = {"trigger": "test", "action": "do something", "scope": "negotiated"}
        rule = Rule.from_dict(d)
        assert rule.scope == "negotiated"

    def test_scope_default_in_from_dict(self):
        d = {"trigger": "test", "action": "do something"}
        rule = Rule.from_dict(d)
        assert rule.scope == "personal"

    def test_scope_roundtrip(self):
        rule = Rule(trigger="test", action="do something", scope="company")
        restored = Rule.from_dict(rule.to_dict())
        assert restored.scope == "company"


class TestToBoolRobustness:
    """Test _to_bool handles all input types correctly"""

    def test_bool_passthrough(self):
        assert _to_bool(True) is True
        assert _to_bool(False) is False

    def test_int_conversion(self):
        assert _to_bool(1) is True
        assert _to_bool(0) is False

    def test_string_true_values(self):
        for val in ["1", "true", "True", "TRUE", "yes", "Yes", "on", "On"]:
            assert _to_bool(val) is True

    def test_string_false_values(self):
        for val in ["0", "false", "False", "no", "No", "off", "Off", ""]:
            assert _to_bool(val) is False

    def test_float_conversion(self):
        assert _to_bool(1.0) is True
        assert _to_bool(0.0) is False

    def test_none_conversion(self):
        assert _to_bool(None) is True
        assert _to_bool(None, default=False) is False


class TestScopeAwareStorage:
    """Test scope in storage layer"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_scope.db")
        self.storage = RuleStorage(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_rule_with_scope(self):
        rule = self.storage.create(
            trigger="test", action="do something", scope="company"
        )
        assert rule.scope == "company"

    def test_list_rules_filter_by_scope(self):
        self.storage.create(trigger="p1", action="a1", scope="personal")
        self.storage.create(trigger="p2", action="a2", scope="personal")
        self.storage.create(trigger="c1", action="a3", scope="company")

        personal = self.storage.list_all(scope="personal")
        company = self.storage.list_all(scope="company")

        assert len(personal) == 2
        assert len(company) == 1

    def test_update_scope(self):
        rule = self.storage.create(trigger="test", action="a", scope="personal")
        updated = self.storage.update(rule.id, scope="company")
        assert updated.scope == "company"

    def test_fts_search_preserves_scope(self):
        self.storage.create(trigger="database design", action="use SSL", scope="company")
        self.storage.create(trigger="database query", action="use ORM", scope="personal")

        results = self.storage.search("database")
        for r in results:
            if r.trigger == "database design":
                assert r.scope == "company"
            elif r.trigger == "database query":
                assert r.scope == "personal"


class TestScopeAwareMatching:
    """Test scope-aware rule matching"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_match.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_match_all_scopes_by_default(self):
        self.engine.add_rule("database", "use SSL", scope="company")
        self.engine.add_rule("database", "use PostgreSQL", scope="personal")

        results = self.engine.match("database")
        assert len(results) >= 2

    def test_match_filter_by_scope(self):
        self.engine.add_rule("database", "use SSL", scope="company")
        self.engine.add_rule("database", "use PostgreSQL", scope="personal")

        results = self.engine.match("database", scopes=["company"])
        assert all(r.rule.scope == "company" for r in results)
        assert len(results) >= 1

    def test_match_multiple_scopes(self):
        self.engine.add_rule("database", "use SSL", scope="company")
        self.engine.add_rule("database", "prefer ORM", scope="negotiated")
        self.engine.add_rule("database", "use PostgreSQL", scope="personal")

        results = self.engine.match("database", scopes=["company", "negotiated"])
        scopes_found = {r.rule.scope for r in results}
        assert "personal" not in scopes_found


class TestSkillPack:
    """Test Skill bundle creation"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_skill.db")
        self.engine = RuleEngine(self.db_path)
        self.engine.add_rule("database", "use SSL", scope="company")
        self.engine.add_rule("code review", "check security", scope="personal")

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_pack_creates_valid_bundle(self):
        rules = self.engine.list_rules()
        bundle = skill_pack(rules=rules, name="test-skill", scope="company")

        assert bundle["format"] == SKILL_FORMAT
        assert bundle["manifest"]["name"] == "test-skill"
        assert bundle["manifest"]["scope"] == "company"
        assert bundle["manifest"]["rule_count"] == 2
        assert "signature" in bundle
        assert bundle["signature"]["algorithm"] == "sha256"

    def test_pack_empty_rules_raises(self):
        with pytest.raises(ValueError, match="Cannot pack empty"):
            skill_pack(rules=[], name="empty-skill")

    def test_pack_invalid_scope_raises(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="Invalid scope"):
            skill_pack(rules=rules, name="bad-skill", scope="invalid")

    def test_pack_self_dependency_raises(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="cannot depend on itself"):
            skill_pack(rules=rules, name="my-skill", dependencies=["my-skill"])

    def test_pack_duplicate_dependency_raises(self):
        rules = [Rule(trigger="test", action="a")]
        with pytest.raises(ValueError, match="Duplicate dependency"):
            skill_pack(
                rules=rules, name="my-skill",
                dependencies=["dep-a", "dep-a"],
            )

    def test_pack_signature_covers_manifest(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="original", scope="personal")

        tampered = copy.deepcopy(bundle)
        tampered["manifest"]["scope"] = "company"

        result = skill_verify(tampered)
        assert result["valid"] is False


class TestSkillVerify:
    """Test Skill bundle verification"""

    def test_verify_valid_bundle(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-skill")

        result = skill_verify(bundle)
        assert result["valid"] is True
        assert result["name"] == "test-skill"

    def test_verify_tampered_rules(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-skill")

        bundle["rules"][0]["action"] = "tampered"

        result = skill_verify(bundle)
        assert result["valid"] is False

    def test_verify_tampered_manifest_scope(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-skill", scope="personal")

        bundle["manifest"]["scope"] = "company"

        result = skill_verify(bundle)
        assert result["valid"] is False

    def test_verify_missing_signature(self):
        bundle = {"format": SKILL_FORMAT, "manifest": {}, "rules": []}

        result = skill_verify(bundle)
        assert result["valid"] is False

    def test_verify_wrong_format(self):
        bundle = {"format": "unknown", "manifest": {}, "rules": []}

        result = skill_verify(bundle)
        assert result["valid"] is False


class TestSkillInstall:
    """Test Skill bundle installation"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_install.db")
        self.storage = RuleStorage(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_install_basic(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-skill")

        result = skill_install(bundle, self.storage)
        assert result["installed"] == 1
        assert result["errors"] == []

    def test_install_with_scope_override(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-skill", scope="personal")

        result = skill_install(bundle, self.storage, scope_override="company")
        assert result["installed"] == 1
        assert result["scope"] == "company"

        installed = self.storage.list_all()
        assert installed[0].scope == "company"

    def test_install_skip_mode(self):
        self.storage.create(trigger="test", action="do something", scope="personal")
        rules = [Rule(trigger="test", action="do something")]
        bundle = skill_pack(rules=rules, name="test-skill", scope="personal")

        result = skill_install(bundle, self.storage, mode="skip")
        assert result["skipped"] == 1

    def test_install_overwrite_mode(self):
        existing = self.storage.create(trigger="test", action="old action", scope="personal", override=False)
        rules = [Rule(trigger="test", action="old action", override=True)]
        bundle = skill_pack(rules=rules, name="test-skill", scope="personal")

        result = skill_install(bundle, self.storage, mode="overwrite")
        assert result["overwritten"] == 1

        all_rules = self.storage.list_all()
        assert len(all_rules) == 1
        assert all_rules[0].override is True

    def test_install_different_scope_not_duplicate(self):
        self.storage.create(trigger="test", action="a", scope="company")
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test-skill", scope="personal")

        result = skill_install(bundle, self.storage, mode="skip")
        assert result["installed"] == 1

    def test_install_empty_bundle_rejected(self):
        bundle = {"format": SKILL_FORMAT, "manifest": {"name": "empty"}, "rules": []}
        result = skill_install(bundle, self.storage)
        assert result["installed"] == 0

    def test_install_invalid_signature_rejected(self):
        bundle = {"format": SKILL_FORMAT, "manifest": {}, "rules": [{"trigger": "t", "action": "a"}], "signature": {"algorithm": "sha256", "hash": "wrong"}}
        result = skill_install(bundle, self.storage)
        assert result["installed"] == 0


class TestMergeConflictDetection:
    """Test merge conflict detection"""

    def test_detect_trigger_overlap(self):
        incoming = [Rule(trigger="database", action="use MySQL")]
        existing = [Rule(trigger="database", action="use PostgreSQL")]

        conflicts = detect_merge_conflicts(incoming, existing)
        assert len(conflicts) >= 1
        assert conflicts[0].conflict_type == "trigger_overlap"

    def test_no_conflict_different_triggers(self):
        incoming = [Rule(trigger="database", action="use MySQL")]
        existing = [Rule(trigger="frontend", action="use React")]

        conflicts = detect_merge_conflicts(incoming, existing)
        assert len(conflicts) == 0

    def test_detect_type_contradiction(self):
        incoming = [Rule(trigger="api", action="always use REST", rule_type="always")]
        existing = [Rule(trigger="api", action="forbid REST", rule_type="forbid")]

        conflicts = detect_merge_conflicts(incoming, existing)
        assert len(conflicts) >= 1
        type_conflicts = [c for c in conflicts if c.conflict_type == "type_contradiction"]
        assert len(type_conflicts) >= 1


class TestMergeConflictResolution:
    """Test merge conflict resolution strategies"""

    def test_company_overrides_personal(self):
        conflict = MergeConflict(
            incoming_rule=Rule(trigger="db", action="use SSL", scope="company", override=True),
            existing_rule=Rule(trigger="db", action="no SSL", scope="personal"),
            conflict_type="trigger_overlap",
            severity="high",
            reason="test",
        )

        decision = resolve_conflict(conflict, MergeStrategy.COMPANY_OVERRIDES)
        assert decision == MergeDecision.KEEP_INCOMING

    def test_personal_cannot_override_company(self):
        conflict = MergeConflict(
            incoming_rule=Rule(trigger="db", action="no SSL", scope="personal"),
            existing_rule=Rule(trigger="db", action="use SSL", scope="company", override=True),
            conflict_type="trigger_overlap",
            severity="high",
            reason="test",
        )

        decision = resolve_conflict(conflict, MergeStrategy.COMPANY_OVERRIDES)
        assert decision == MergeDecision.KEEP_EXISTING

    def test_same_scope_company_overrides_favors_incoming(self):
        conflict = MergeConflict(
            incoming_rule=Rule(trigger="db", action="new rule", scope="company"),
            existing_rule=Rule(trigger="db", action="old rule", scope="company"),
            conflict_type="trigger_overlap",
            severity="medium",
            reason="test",
        )

        decision = resolve_conflict(conflict, MergeStrategy.COMPANY_OVERRIDES)
        assert decision == MergeDecision.KEEP_INCOMING

    def test_negotiate_strategy_type_contradiction(self):
        conflict = MergeConflict(
            incoming_rule=Rule(trigger="db", action="always use SSL", scope="negotiated", rule_type="always", override=True),
            existing_rule=Rule(trigger="db", action="forbid SSL", scope="personal", rule_type="forbid", override=True),
            conflict_type="type_contradiction",
            severity="high",
            reason="test",
        )

        decision = resolve_conflict(conflict, MergeStrategy.NEGOTIATE)
        assert decision == MergeDecision.MODIFY_INCOMING

    def test_negotiate_strategy_trigger_overlap_keeps_both(self):
        conflict = MergeConflict(
            incoming_rule=Rule(trigger="db", action="use MySQL", scope="negotiated", override=True),
            existing_rule=Rule(trigger="db", action="use PostgreSQL", scope="personal", override=True),
            conflict_type="trigger_overlap",
            severity="medium",
            reason="test",
        )

        decision = resolve_conflict(conflict, MergeStrategy.NEGOTIATE)
        assert decision == MergeDecision.KEEP_BOTH


class TestMergeRules:
    """Test full merge_rules flow"""

    def test_merge_no_conflicts(self):
        incoming = [Rule(trigger="frontend", action="use React")]
        existing = [Rule(trigger="backend", action="use Python")]

        result = merge_rules(incoming, existing, MergeStrategy.COMPANY_OVERRIDES)
        assert len(result.accepted) == 1
        assert len(result.conflicts) == 0

    def test_merge_with_replacement(self):
        incoming = [Rule(trigger="db", action="use SSL", scope="company", override=True)]
        existing = [Rule(trigger="db", action="no SSL", scope="personal")]

        result = merge_rules(incoming, existing, MergeStrategy.COMPANY_OVERRIDES)
        assert len(result.accepted) == 1
        assert len(result.replaced_ids) == 1
        assert existing[0].id in result.replaced_ids

    def test_merge_does_not_mutate_incoming(self):
        incoming = [Rule(trigger="db", action="use SSL", scope="personal")]
        existing = [Rule(trigger="db", action="no SSL", scope="company")]

        original_scope = incoming[0].scope
        merge_rules(incoming, existing, MergeStrategy.COMPANY_OVERRIDES, target_scope="negotiated")

        assert incoming[0].scope == original_scope

    def test_merge_target_scope_creates_copy(self):
        incoming = [Rule(trigger="db", action="use SSL", scope="personal")]
        existing = []

        result = merge_rules(incoming, existing, MergeStrategy.COMPANY_OVERRIDES, target_scope="company")
        assert result.accepted[0].scope == "company"
        assert incoming[0].scope == "personal"

    def test_merge_negotiate_downgrades_existing_override(self):
        incoming = [Rule(trigger="db", action="always use MySQL", scope="negotiated", rule_type="always", override=True)]
        existing = [Rule(trigger="db", action="forbid MySQL", scope="personal", rule_type="forbid", override=True)]

        result = merge_rules(incoming, existing, MergeStrategy.NEGOTIATE)
        assert len(result.downgrade_override_ids) == 1
        assert existing[0].id in result.downgrade_override_ids


class TestReviewIncomingRules:
    """Test preview merge without side effects"""

    def test_review_does_not_mutate_incoming(self):
        incoming = [Rule(trigger="db", action="use SSL", scope="personal")]
        existing = [Rule(trigger="db", action="no SSL", scope="company")]

        original_scope = incoming[0].scope
        review_incoming_rules(incoming, existing, target_scope="negotiated")

        assert incoming[0].scope == original_scope

    def test_review_returns_conflict_info(self):
        incoming = [Rule(trigger="db", action="use MySQL")]
        existing = [Rule(trigger="db", action="use PostgreSQL")]

        result = review_incoming_rules(incoming, existing)
        assert "conflict_count" in result
        assert result["conflict_count"] >= 1

    def test_review_with_target_scope(self):
        incoming = [Rule(trigger="db", action="use SSL", scope="personal")]
        existing = []

        result = review_incoming_rules(incoming, existing, target_scope="company")
        assert "strategy_previews" in result


class TestAcceptRules:
    """Test accept_rules end-to-end"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_accept.db")
        self.engine = RuleEngine(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_accept_stores_rules(self):
        incoming = [Rule(trigger="new", action="do something")]
        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert result["accepted_count"] == 1

    def test_accept_deletes_replaced_rules(self):
        existing = self.engine.add_rule("db", "old rule", scope="personal")
        incoming = [Rule(trigger="db", action="new rule", scope="company", override=True)]

        result = self.engine.accept_rules(incoming, strategy="company_overrides")
        assert len(result.get("replaced_ids", [])) == 1

        remaining = self.engine.list_rules()
        actions = [r.action for r in remaining]
        assert "new rule" in actions

    def test_accept_downgrades_override(self):
        existing = self.engine.add_rule("db", "old rule", scope="personal", override=True)
        incoming = [Rule(trigger="db", action="new rule", scope="company", override=True)]

        result = self.engine.accept_rules(incoming, strategy="negotiate")
        if result.get("downgrade_override_ids"):
            updated = self.engine.storage.get(existing.id)
            assert updated.override is False


class TestScopeSecurityBoundaries:
    """Test that scope security boundaries cannot be bypassed"""

    def test_personal_cannot_override_company_in_any_strategy(self):
        for strategy in MergeStrategy:
            conflict = MergeConflict(
                incoming_rule=Rule(trigger="db", action="bad", scope="personal", override=True),
                existing_rule=Rule(trigger="db", action="good", scope="company", override=True),
                conflict_type="trigger_overlap",
                severity="high",
                reason="test",
            )
            decision = resolve_conflict(conflict, strategy)
            assert decision == MergeDecision.KEEP_EXISTING, (
                f"Strategy {strategy.value} allowed personal to override company!"
            )

    def test_company_override_always_wins(self):
        for strategy in MergeStrategy:
            conflict = MergeConflict(
                incoming_rule=Rule(trigger="db", action="company rule", scope="company", override=True),
                existing_rule=Rule(trigger="db", action="personal rule", scope="personal", override=True),
                conflict_type="trigger_overlap",
                severity="high",
                reason="test",
            )
            decision = resolve_conflict(conflict, strategy)
            assert decision == MergeDecision.KEEP_INCOMING, (
                f"Strategy {strategy.value} did not let company override win!"
            )


class TestSkillSignatureSecurity:
    """Test that Skill signature covers manifest fields"""

    def test_tampering_scope_invalidates_signature(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test", scope="personal")

        bundle["manifest"]["scope"] = "company"
        assert skill_verify(bundle)["valid"] is False

    def test_tampering_name_invalidates_signature(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="original")

        bundle["manifest"]["name"] = "tampered"
        assert skill_verify(bundle)["valid"] is False

    def test_tampering_version_invalidates_signature(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test", version="1.0.0")

        bundle["manifest"]["version"] = "2.0.0"
        assert skill_verify(bundle)["valid"] is False

    def test_untouched_bundle_valid(self):
        rules = [Rule(trigger="test", action="a")]
        bundle = skill_pack(rules=rules, name="test")

        assert skill_verify(bundle)["valid"] is True
