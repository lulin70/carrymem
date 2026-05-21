"""
Test Suite for RuleConflictDetector

Validates:
- Contradictory type pair detection (always vs forbid)
- Overlapping preference detection
- Duplicate rule detection
- Global rule conflict detection
- Health check functionality
"""

import tempfile
import os

from carrymem.rules.models import Rule
from carrymem.rules.conflict_detector import (
    RuleConflictDetector,
    RuleConflict,
    ConflictType,
    ConflictSeverity,
)
from carrymem.rules.storage import RuleStorage


class TestContradictionDetection:
    """Test detection of contradictory rule type pairs"""

    def test_always_vs_forbid_detected(self):
        """Should detect always X vs forbid X as contradiction"""
        rules = [
            Rule(trigger="代码评审", action="必须检查SQL注入", rule_type="always"),
            Rule(trigger="代码评审", action="跳过SQL检查", rule_type="forbid"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) >= 1
        assert contradictions[0].severity == ConflictSeverity.CRITICAL

    def test_always_vs_avoid_detected(self):
        """Should detect always X vs avoid X as contradiction"""
        rules = [
            Rule(trigger="技术选型", action="使用Python", rule_type="always"),
            Rule(trigger="技术选型", action="不用Python", rule_type="avoid"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) >= 1

    def test_forbid_vs_prefer_detected(self):
        """Should detect forbid X vs prefer X as contradiction"""
        rules = [
            Rule(trigger="写报告", action="不要用表格", rule_type="forbid"),
            Rule(trigger="写报告", action="使用表格", rule_type="prefer"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) >= 1

    def test_compatible_types_no_conflict(self):
        """Should NOT flag compatible type pairs"""
        rules = [
            Rule(trigger="写报告", action="控制在3页以内", rule_type="format"),
            Rule(trigger="写报告", action="使用Python", rule_type="prefer"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) == 0

    def test_different_triggers_no_contradiction(self):
        """Should NOT flag contradictory types with different triggers"""
        rules = [
            Rule(trigger="代码评审", action="检查安全", rule_type="always"),
            Rule(trigger="写报告", action="跳过安全检查", rule_type="forbid"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) == 0


class TestOverlapDetection:
    """Test detection of overlapping preferences"""

    def test_prefer_vs_prefer_different_actions(self):
        """Should detect overlapping prefer rules with different actions"""
        rules = [
            Rule(trigger="技术选型", action="使用PostgreSQL", rule_type="prefer"),
            Rule(trigger="技术选型", action="使用MySQL", rule_type="prefer"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        overlaps = [c for c in conflicts if c.conflict_type == ConflictType.OVERLAP]

        assert len(overlaps) >= 1
        assert overlaps[0].severity == ConflictSeverity.MEDIUM

    def test_prefer_vs_prefer_same_action_no_conflict(self):
        """Should NOT flag prefer rules with same action"""
        rules = [
            Rule(trigger="技术选型", action="使用Python", rule_type="prefer"),
            Rule(trigger="技术选型", action="使用Python", rule_type="prefer"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        # Should be flagged as redundancy, not overlap
        overlaps = [c for c in conflicts if c.conflict_type == ConflictType.OVERLAP]
        assert len(overlaps) == 0

    def test_format_vs_format_different_actions(self):
        """Should detect overlapping format rules"""
        rules = [
            Rule(trigger="写报告", action="控制在3页以内", rule_type="format"),
            Rule(trigger="写报告", action="控制在5页以内", rule_type="format"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        overlaps = [c for c in conflicts if c.conflict_type == ConflictType.OVERLAP]

        assert len(overlaps) >= 1


class TestRedundancyDetection:
    """Test detection of duplicate/redundant rules"""

    def test_exact_duplicate_detected(self):
        """Should detect exact duplicate rules"""
        rules = [
            Rule(trigger="写报告", action="控制在3页以内", rule_type="format"),
            Rule(trigger="写报告", action="控制在3页以内", rule_type="format"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        redundancies = [c for c in conflicts if c.conflict_type == ConflictType.REDUNDANCY]

        assert len(redundancies) >= 1
        assert redundancies[0].severity == ConflictSeverity.LOW

    def test_different_type_not_duplicate(self):
        """Should NOT flag rules with same trigger but different type as duplicate"""
        rules = [
            Rule(trigger="写报告", action="控制在3页以内", rule_type="format"),
            Rule(trigger="写报告", action="控制在3页以内", rule_type="always"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        redundancies = [c for c in conflicts if c.conflict_type == ConflictType.REDUNDANCY]

        assert len(redundancies) == 0


class TestGlobalRuleConflicts:
    """Test detection of conflicts among global rules"""

    def test_global_always_vs_global_forbid(self):
        """Should detect contradictory global rules"""
        rules = [
            Rule(trigger="*", action="Always be polite", rule_type="always"),
            Rule(trigger="*", action="Never be polite", rule_type="forbid"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        global_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.GLOBAL_CONFLICT]

        assert len(global_conflicts) >= 1
        assert global_conflicts[0].severity == ConflictSeverity.CRITICAL

    def test_global_compatible_no_conflict(self):
        """Should NOT flag compatible global rules"""
        rules = [
            Rule(trigger="*", action="Always be polite", rule_type="always"),
            Rule(trigger="*", action="Use professional tone", rule_type="format"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        global_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.GLOBAL_CONFLICT]

        assert len(global_conflicts) == 0


class TestNewRuleCheck:
    """Test checking a new rule against existing rules"""

    def test_new_rule_conflicts_with_existing(self):
        """Should detect conflicts between new rule and existing"""
        existing = [
            Rule(trigger="代码评审", action="必须检查安全", rule_type="always"),
        ]
        new_rule = Rule(trigger="代码评审", action="跳过安全检查", rule_type="forbid")

        conflicts = RuleConflictDetector.detect(existing, new_rule=new_rule)

        assert len(conflicts) >= 1
        assert any(c.conflict_type == ConflictType.CONTRADICTION for c in conflicts)

    def test_new_rule_no_conflict(self):
        """Should return empty when new rule has no conflicts"""
        existing = [
            Rule(trigger="写报告", action="控制在3页以内", rule_type="format"),
        ]
        new_rule = Rule(trigger="代码评审", action="检查安全", rule_type="always")

        conflicts = RuleConflictDetector.detect(existing, new_rule=new_rule)

        assert len(conflicts) == 0


class TestPausedRulesExcluded:
    """Test that paused/deprecated rules are not checked"""

    def test_paused_rules_not_checked(self):
        """Should not flag conflicts with paused rules"""
        rules = [
            Rule(trigger="代码评审", action="检查安全", rule_type="always", status="active"),
            Rule(trigger="代码评审", action="跳过安全", rule_type="forbid", status="paused"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) == 0

    def test_deprecated_rules_not_checked(self):
        """Should not flag conflicts with deprecated rules"""
        rules = [
            Rule(trigger="代码评审", action="检查安全", rule_type="always", status="active"),
            Rule(trigger="代码评审", action="跳过安全", rule_type="forbid", status="deprecated"),
        ]

        conflicts = RuleConflictDetector.detect(rules)
        contradictions = [c for c in conflicts if c.conflict_type == ConflictType.CONTRADICTION]

        assert len(contradictions) == 0


class TestTriggerOverlap:
    """Test trigger overlap detection heuristics"""

    def test_exact_trigger_match(self):
        """Should detect exact trigger matches"""
        assert RuleConflictDetector._triggers_overlap("写报告", "写报告") is True

    def test_trigger_substring(self):
        """Should detect substring trigger matches"""
        assert RuleConflictDetector._triggers_overlap("写报告", "帮我写报告") is True

    def test_global_trigger_matches_all(self):
        """Should detect global trigger overlap with everything"""
        assert RuleConflictDetector._triggers_overlap("*", "写报告") is True
        assert RuleConflictDetector._triggers_overlap("写报告", "*") is True

    def test_unrelated_triggers_no_overlap(self):
        """Should NOT detect overlap between unrelated triggers"""
        assert RuleConflictDetector._triggers_overlap("写报告", "代码评审") is False

    def test_word_overlap(self):
        """Should detect word overlap in triggers"""
        assert RuleConflictDetector._triggers_overlap("写技术报告", "写业务报告") is True


class TestHealthCheck:
    """Test comprehensive health check"""

    def test_healthy_rules(self):
        """Should report healthy when no critical conflicts"""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            storage = RuleStorage(path)
            storage.create(trigger="写报告", action="控制在3页以内", rule_type="format")
            storage.create(trigger="代码评审", action="检查安全", rule_type="always")

            health = RuleConflictDetector.check_health(storage)

            assert health["is_healthy"] is True
            assert health["total_active"] == 2
            assert health["conflicts_found"] == 0
        finally:
            os.unlink(path)

    def test_unhealthy_rules(self):
        """Should report unhealthy when critical conflicts exist"""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            storage = RuleStorage(path)
            storage.create(trigger="代码评审", action="必须检查安全", rule_type="always")
            storage.create(trigger="代码评审", action="跳过安全检查", rule_type="forbid")

            health = RuleConflictDetector.check_health(storage)

            assert health["is_healthy"] is False
            assert health["conflicts_found"] >= 1
            assert health["conflicts_by_severity"].get("critical", 0) >= 1
        finally:
            os.unlink(path)

    def test_unused_rules_counted(self):
        """Should count unused rules (trigger_count=0)"""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            storage = RuleStorage(path)
            storage.create(trigger="写报告", action="action1", rule_type="format")
            storage.create(trigger="代码评审", action="action2", rule_type="always")

            health = RuleConflictDetector.check_health(storage)

            assert health["unused_rules"] == 2  # Both newly created, never triggered
        finally:
            os.unlink(path)


class TestConflictSummary:
    """Test conflict summary formatting"""

    def test_summary_contains_key_info(self):
        """Summary should contain severity, type, reason"""
        conflict = RuleConflict(
            conflict_type=ConflictType.CONTRADICTION,
            severity=ConflictSeverity.CRITICAL,
            rules=[
                Rule(trigger="代码评审", action="检查安全", rule_type="always"),
                Rule(trigger="代码评审", action="跳过安全", rule_type="forbid"),
            ],
            reason="Contradictory types: always vs forbid",
            suggestion="Review which rule should take precedence",
        )

        summary = conflict.summary()

        assert "CRITICAL" in summary
        assert "contradiction" in summary
        assert "always vs forbid" in summary
        assert "Review" in summary

    def test_repr_format(self):
        """Should generate readable repr"""
        conflict = RuleConflict(
            conflict_type=ConflictType.OVERLAP,
            severity=ConflictSeverity.MEDIUM,
            rules=[
                Rule(id="rule_abc", trigger="test", action="a1", rule_type="prefer"),
                Rule(id="rule_def", trigger="test", action="a2", rule_type="prefer"),
            ],
            reason="Overlapping preferences",
        )

        repr_str = repr(conflict)
        assert "overlap" in repr_str
        assert "medium" in repr_str
