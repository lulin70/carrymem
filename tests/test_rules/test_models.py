"""
Test Suite for Rule Data Model

Validates:
- Rule creation and field validation
- Serialization/deserialization
- Type safety and constraints
- Lifecycle methods (activate, pause, deprecate)
"""

import pytest
from datetime import datetime, timezone

from carrymem.rules.models import (
    Rule,
    VALID_RULE_TYPES,
    VALID_RULE_STATUSES,
    VALID_DERIVATION_SOURCES,
)


class TestRuleCreation:
    """Test basic rule creation and validation"""

    def test_create_minimal_rule(self):
        """Should create rule with required fields only"""
        rule = Rule(trigger="写报告", action="控制在3页以内")

        assert rule.trigger == "写报告"
        assert rule.action == "控制在3页以内"
        assert rule.rule_type == "avoid"  # default
        assert rule.status == "active"  # default
        assert rule.override is True  # default
        assert rule.id.startswith("rule_")
        assert len(rule.id) == len("rule_") + 8  # UUID8

    def test_create_with_all_fields(self):
        """Should create rule with all fields specified"""
        rule = Rule(
            id="rule_test123",
            trigger="做竞品分析",
            action="跳过印度供应商",
            rule_type="avoid",
            status="paused",
            override=False,
            confidence=0.95,
            source_memories=["mem_1", "mem_2"],
            derived_from="auto_promotion",
            confirmed_by_user=False,
            metadata={"priority": "high"},
        )

        assert rule.id == "rule_test123"
        assert rule.trigger == "做竞品分析"
        assert rule.action == "跳过印度供应商"
        assert rule.rule_type == "avoid"
        assert rule.status == "paused"
        assert rule.override is False
        assert rule.confidence == 0.95
        assert rule.source_memories == ["mem_1", "mem_2"]
        assert rule.derived_from == "auto_promotion"
        assert rule.confirmed_by_user is False
        assert rule.metadata == {"priority": "high"}

    def test_auto_generate_id(self):
        """Should auto-generate unique ID if not provided"""
        rule1 = Rule(trigger="test1", action="action1")
        rule2 = Rule(trigger="test2", action="action2")

        assert rule1.id != rule2.id
        assert rule1.id.startswith("rule_")

    def test_auto_generate_timestamps(self):
        """Should auto-generate timestamps in ISO format"""
        before = datetime.now(timezone.utc).isoformat()
        rule = Rule(trigger="test", action="test")
        after = datetime.now(timezone.utc).isoformat()

        assert before <= rule.created_at <= after
        assert before <= rule.updated_at <= after
        # Should be parseable as ISO datetime
        datetime.fromisoformat(rule.created_at)
        datetime.fromisoformat(rule.updated_at)


class TestRuleValidation:
    """Test field validation rules"""

    def test_valid_rule_types(self):
        """Should accept all valid rule types"""
        for rule_type in VALID_RULE_TYPES:
            rule = Rule(trigger="test", action="test", rule_type=rule_type)
            assert rule.rule_type == rule_type

    def test_invalid_rule_type_raises(self):
        """Should reject invalid rule types"""
        with pytest.raises(ValueError, match="Invalid rule_type"):
            Rule(trigger="test", action="test", rule_type="invalid_type")

    def test_valid_statuses(self):
        """Should accept all valid statuses"""
        for status in VALID_RULE_STATUSES:
            rule = Rule(trigger="test", action="test", status=status)
            assert rule.status == status

    def test_invalid_status_raises(self):
        """Should reject invalid statuses"""
        with pytest.raises(ValueError, match="Invalid status"):
            Rule(trigger="test", action="test", status="unknown")

    def test_valid_derivation_sources(self):
        """Should accept all valid derivation sources"""
        for source in VALID_DERIVATION_SOURCES:
            rule = Rule(
                trigger="test",
                action="test",
                derived_from=source,
            )
            assert rule.derived_from == source

    def test_invalid_derivation_source_raises(self):
        """Should reject invalid derivation sources"""
        with pytest.raises(ValueError, match="Invalid derived_from"):
            Rule(trigger="test", action="test", derived_from="hacked")

    def test_confidence_range(self):
        """Should enforce confidence between 0.0 and 1.0"""
        # Valid values
        for val in [0.0, 0.5, 1.0]:
            rule = Rule(trigger="test", action="test", confidence=val)
            assert rule.confidence == val

        # Invalid: too low
        with pytest.raises(ValueError, match="Confidence"):
            Rule(trigger="test", action="test", confidence=-0.1)

        # Invalid: too high
        with pytest.raises(ValueError, match="Confidence"):
            Rule(trigger="test", action="test", confidence=1.1)

    def test_negative_trigger_count_raises(self):
        """Should reject negative trigger counts"""
        with pytest.raises(ValueError, match="trigger_count"):
            Rule(trigger="test", action="test", trigger_count=-1)


class TestRuleSerialization:
    """Test to_dict() and from_dict() methods"""

    def test_to_dict_contains_all_fields(self):
        """Serialization should include all fields"""
        rule = Rule(
            id="rule_abc123",
            trigger="写报告",
            action="控制在3页以内",
            rule_type="format",
            override=True,
            confidence=0.9,
            metadata={"key": "value"},
        )

        d = rule.to_dict()

        assert d["id"] == "rule_abc123"
        assert d["trigger"] == "写报告"
        assert d["action"] == "控制在3页以内"
        assert d["rule_type"] == "format"
        assert d["override"] == 1  # Boolean → integer
        assert d["confidence"] == 0.9
        assert d["metadata"] == {"key": "value"}
        assert "created_at" in d
        assert "updated_at" in d

    def test_from_dict_reconstructs_rule(self):
        """Deserialization should reconstruct identical rule"""
        original = Rule(
            id="rule_xyz789",
            trigger="做竞品分析",
            action="标注数据来源",
            rule_type="always",
            source_memories=["mem_a", "mem_b"],
            derived_from="failure_lesson",
            status="paused",
            override=False,
            confidence=0.75,
            trigger_count=5,
            confirmed_by_user=True,
            metadata={"reviewed": True},
        )

        data = original.to_dict()
        restored = Rule.from_dict(data)

        assert restored.id == original.id
        assert restored.trigger == original.trigger
        assert restored.action == original.action
        assert restored.rule_type == original.rule_type
        assert restored.source_memories == original.source_memories
        assert restored.derived_from == original.derived_from
        assert restored.status == original.status
        assert restored.override == original.override
        assert restored.confidence == original.confidence
        assert restored.trigger_count == original.trigger_count
        assert restored.confirmed_by_user == original.confirmed_by_user
        assert restored.metadata == original.metadata

    def test_from_dict_handles_missing_fields(self):
        """Deserialization should use defaults for missing fields"""
        data = {"id": "rule_partial", "trigger": "test", "action": "test"}
        rule = Rule.from_dict(data)

        assert rule.id == "rule_partial"
        assert rule.trigger == "test"
        assert rule.action == "test"
        assert rule.rule_type == "avoid"  # default
        assert rule.status == "active"  # default
        assert rule.override is True  # default (from int 1)


class TestRuleLifecycle:
    """Test state transition methods"""

    def test_activate(self):
        """Should set status to active"""
        rule = Rule(trigger="test", action="test", status="paused")
        rule.activate()
        assert rule.status == "active"

    def test_pause(self):
        """Should set status to paused"""
        rule = Rule(trigger="test", action="test", status="active")
        rule.pause()
        assert rule.status == "paused"

    def test_deprecate(self):
        """Should set status to deprecated"""
        rule = Rule(trigger="test", action="test", status="active")
        rule.deprecate()
        assert rule.status == "deprecated"

    def test_increment_trigger_count(self):
        """Should increment counter by 1"""
        rule = Rule(trigger="test", action="test", trigger_count=5)
        rule.increment_trigger_count()
        assert rule.trigger_count == 6

    def test_touch_updates_timestamp(self):
        """Should update updated_at timestamp"""
        from time import sleep

        rule = Rule(trigger="test", action="test")
        original_updated = rule.updated_at

        sleep(0.01)  # Small delay to ensure different timestamp
        rule.touch()

        assert rule.updated_at != original_updated


class TestRuleHelperMethods:
    """Test convenience methods"""

    def test_is_active(self):
        """Should return correct active status"""
        active_rule = Rule(trigger="test", action="test", status="active")
        paused_rule = Rule(trigger="test", action="test", status="paused")

        assert active_rule.is_active() is True
        assert paused_rule.is_active() is False

    def test_is_hard_rule(self):
        """Should correctly identify hard vs soft rules"""
        hard_rule = Rule(trigger="test", action="test", override=True)
        soft_rule = Rule(trigger="test", action="test", override=False)

        assert hard_rule.is_hard_rule() is True
        assert soft_rule.is_hard_rule() is False

    def test_repr(self):
        """Should generate readable representation"""
        rule = Rule(id="rule_abc", trigger="写报告", rule_type="format", status="active")
        repr_str = repr(rule)

        assert "rule_abc" in repr_str
        assert "写报告" in repr_str
        assert "format" in repr_str
        assert "active" in repr_str

    def test_summary(self):
        """Should generate human-readable summary"""
        rule = Rule(
            id="rule_xyz",
            trigger="竞品分析",
            action="跳过印度公司",
            rule_type="avoid",
            override=True,
            status="active",
        )
        summary = rule.summary()

        assert "rule_xyz" in summary
        assert "AVOID" in summary
        assert "竞品分析" in summary
        assert "跳过印度公司" in summary
        assert "Hard" in summary  # override=True
        assert "active" in summary
