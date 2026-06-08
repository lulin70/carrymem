"""
Test Suite for Context Engineering (v0.2.8)

Validates:
- Anchored layout mode (head/tail attention anchoring)
- DDD language view output
- Context budget monitoring with token-aware compression
- ContextBudget token estimation
- estimate_context_usage API
"""

import os
import tempfile

import pytest

from carrymem.rules.injector import (
    ContextBudget,
    RuleInjector,
)
from carrymem.rules.matcher import RuleMatcher
from carrymem.rules.storage import RuleStorage


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def storage(temp_db):
    return RuleStorage(temp_db)


@pytest.fixture
def matcher(storage):
    return RuleMatcher(storage)


@pytest.fixture
def injector(matcher):
    return RuleInjector(matcher)


class TestContextBudgetTokenEstimation:
    """Test ContextBudget token estimation"""

    def test_empty_text(self):
        budget = ContextBudget(budget_tokens=2000)
        assert budget.estimate_tokens("") == 0

    def test_english_text(self):
        budget = ContextBudget(budget_tokens=2000)
        tokens = budget.estimate_tokens("Hello world this is a test")
        assert tokens > 0
        assert tokens < len("Hello world this is a test")

    def test_cjk_text(self):
        budget = ContextBudget(budget_tokens=2000)
        tokens = budget.estimate_tokens("这是中文测试文本")
        assert tokens > 0

    def test_mixed_text(self):
        budget = ContextBudget(budget_tokens=2000)
        tokens = budget.estimate_tokens("Hello 世界 test 测试")
        assert tokens > 0

    def test_should_compress_below_threshold(self):
        budget = ContextBudget(budget_tokens=10000)
        short_text = "Hello world"
        assert not budget.should_compress(short_text)

    def test_should_compress_above_threshold(self):
        budget = ContextBudget(budget_tokens=10)
        long_text = "A" * 100
        assert budget.should_compress(long_text)

    def test_compression_threshold_seventy_percent(self):
        budget = ContextBudget(budget_tokens=100)
        assert budget.COMPRESSION_THRESHOLD == 0.70


class TestContextBudgetCompression:
    """Test ContextBudget rule compression"""

    def test_compress_preserves_override_rules(self, matcher, storage):
        storage.create(
            trigger="*",
            action="Override rule 1",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Soft rule 1",
            rule_type="avoid",
            override=False,
        )

        matches = matcher.match("test")
        budget = ContextBudget(budget_tokens=5)
        compressed = budget.compress_rules(matches)

        override_in_result = [m for m in compressed if m.rule.override]
        assert len(override_in_result) == 1

    def test_compress_drops_soft_when_over_budget(self, matcher, storage):
        storage.create(
            trigger="*",
            action="Override rule",
            rule_type="forbid",
            override=True,
        )
        for i in range(5):
            storage.create(
                trigger="*",
                action=f"Soft rule {i} with long description",
                rule_type="avoid",
                override=False,
            )

        matches = matcher.match("test")
        budget = ContextBudget(budget_tokens=10)
        compressed = budget.compress_rules(matches)

        assert all(m.rule.override for m in compressed)

    def test_compress_keeps_all_when_within_budget(self, matcher, storage):
        storage.create(
            trigger="*",
            action="Rule 1",
            rule_type="avoid",
            override=False,
        )
        storage.create(
            trigger="*",
            action="Rule 2",
            rule_type="prefer",
            override=False,
        )

        matches = matcher.match("test")
        budget = ContextBudget(budget_tokens=5000)
        compressed = budget.compress_rules(matches)

        assert len(compressed) == len(matches)


class TestAnchoredLayout:
    """Test anchored layout mode"""

    def test_anchored_format_basic(self, injector, storage):
        storage.create(
            trigger="*",
            action="Never leak secrets",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Prefer Python",
            rule_type="prefer",
            override=False,
        )
        storage.create(
            trigger="*",
            action="Always include tests",
            rule_type="always",
            override=True,
        )

        result = injector.inject("test", format="anchored")
        assert "Absolute Prohibitions" in result
        assert "Recommended" in result
        assert "Mandatory Actions" in result

    def test_anchored_head_contains_forbid_override(self, injector, storage):
        storage.create(
            trigger="*",
            action="Never leak secrets",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Always include tests",
            rule_type="always",
            override=True,
        )

        result = injector.inject("test", format="anchored")
        lines = result.split("\n")

        head_start = None
        middle_start = None
        tail_start = None

        for i, line in enumerate(lines):
            if "Absolute Prohibitions" in line:
                head_start = i
            elif "Recommended" in line:
                middle_start = i
            elif "Mandatory Actions" in line:
                tail_start = i

        assert head_start is not None
        assert tail_start is not None
        assert head_start < tail_start

    def test_anchored_forbid_in_head_section(self, injector, storage):
        storage.create(
            trigger="security",
            action="Never leak secrets",
            rule_type="forbid",
            override=True,
        )

        result = injector.inject("security", format="anchored")
        assert "[FORBID]" in result
        assert "Never leak secrets" in result

    def test_anchored_always_in_tail_section(self, injector, storage):
        storage.create(
            trigger="code review",
            action="Always check SQL injection",
            rule_type="always",
            override=True,
        )

        result = injector.inject("code review", format="anchored")
        assert "[ALWAYS]" in result
        assert "Always check SQL injection" in result

    def test_anchored_soft_in_middle(self, injector, storage):
        storage.create(
            trigger="*",
            action="Prefer domestic warehouses",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="anchored")
        assert "Recommended" in result
        assert "Prefer domestic warehouses" in result

    def test_anchored_no_head_when_no_forbid_override(self, injector, storage):
        storage.create(
            trigger="*",
            action="Prefer Python",
            rule_type="prefer",
            override=False,
        )

        result = injector.inject("test", format="anchored")
        assert "Absolute Prohibitions" not in result

    def test_anchored_no_tail_when_no_always_override(self, injector, storage):
        storage.create(
            trigger="*",
            action="Avoid MongoDB",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="anchored")
        assert "Mandatory Actions" not in result

    def test_anchored_empty_matches(self, injector):
        result = injector.inject("nonexistent scene", format="anchored")
        assert result == ""

    def test_anchored_header_present(self, injector, storage):
        storage.create(
            trigger="*",
            action="Some rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="anchored")
        assert "## Behavioral Rules (from CarryMem)" in result

    def test_anchored_footer_present(self, injector, storage):
        storage.create(
            trigger="*",
            action="Some rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="anchored")
        assert "rule(s) active" in result

    def test_classify_anchored_groups(self, injector, storage):
        storage.create(
            trigger="*",
            action="Forbid rule",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Soft avoid",
            rule_type="avoid",
            override=False,
        )
        storage.create(
            trigger="*",
            action="Soft prefer",
            rule_type="prefer",
            override=False,
        )
        storage.create(
            trigger="*",
            action="Always rule",
            rule_type="always",
            override=True,
        )

        matches = injector.matcher.match("test")
        head, middle, tail = injector._classify_anchored(matches)

        assert len(head) == 1
        assert head[0].rule.rule_type == "forbid"
        assert len(tail) == 1
        assert tail[0].rule.rule_type == "always"
        assert len(middle) == 2

    def test_anchored_override_format_in_middle(self, injector, storage):
        storage.create(
            trigger="*",
            action="Override prefer",
            rule_type="prefer",
            override=True,
        )

        result = injector.inject("test", format="anchored")
        assert "Recommended" in result
        assert "Override prefer" in result


class TestDDDFormat:
    """Test DDD language view output"""

    def test_ddd_format_basic(self, injector, storage):
        storage.create(
            trigger="code review",
            action="Check SQL injection",
            rule_type="forbid",
            override=True,
        )

        result = injector.inject("code review", format="ddd")
        assert "DDD View" in result
        assert "Invariant" in result
        assert "Bounded Context" in result

    def test_ddd_type_mapping_forbid(self, injector, storage):
        storage.create(
            trigger="security",
            action="Never leak data",
            rule_type="forbid",
            override=True,
        )

        result = injector.inject("security", format="ddd")
        assert "Invariant" in result

    def test_ddd_type_mapping_always(self, injector, storage):
        storage.create(
            trigger="code review",
            action="Always check tests",
            rule_type="always",
            override=True,
        )

        result = injector.inject("code review", format="ddd")
        assert "Consistency Guarantee" in result

    def test_ddd_type_mapping_avoid(self, injector, storage):
        storage.create(
            trigger="*",
            action="Avoid MongoDB",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="ddd")
        assert "Soft Constraint" in result

    def test_ddd_type_mapping_prefer(self, injector, storage):
        storage.create(
            trigger="*",
            action="Prefer Python",
            rule_type="prefer",
            override=False,
        )

        result = injector.inject("test", format="ddd")
        assert "Soft Constraint" in result

    def test_ddd_type_mapping_format(self, injector, storage):
        storage.create(
            trigger="report",
            action="Use 3-page format",
            rule_type="format",
            override=False,
        )

        result = injector.inject("report", format="ddd")
        assert "Soft Constraint" in result

    def test_ddd_override_flag(self, injector, storage):
        storage.create(
            trigger="security",
            action="Never leak",
            rule_type="forbid",
            override=True,
        )

        result = injector.inject("security", format="ddd")
        assert "Invariant Flag" in result

    def test_ddd_no_override_no_flag(self, injector, storage):
        storage.create(
            trigger="*",
            action="Prefer Python",
            rule_type="prefer",
            override=False,
        )

        result = injector.inject("test", format="ddd")
        assert "Invariant Flag" not in result

    def test_ddd_metadata_with_source_memories(self, injector, storage):
        storage.create(
            trigger="security",
            action="Never leak",
            rule_type="forbid",
            override=True,
            source_memories=["mem_001", "mem_002"],
        )

        result = injector.inject("security", format="ddd", include_metadata=True)
        assert "Event Sourcing Chain" in result
        assert "2 events" in result

    def test_ddd_header(self, injector, storage):
        storage.create(
            trigger="*",
            action="Some rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="ddd")
        assert "## Personal Context (DDD View)" in result

    def test_ddd_footer(self, injector, storage):
        storage.create(
            trigger="*",
            action="Some rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="ddd")
        assert "constraint(s)" in result

    def test_ddd_empty_matches(self, injector):
        result = injector.inject("nonexistent", format="ddd")
        assert result == ""

    def test_ddd_bounded_context_shown(self, injector, storage):
        storage.create(
            trigger="database selection",
            action="Use PostgreSQL",
            rule_type="prefer",
            override=False,
        )

        result = injector.inject("database selection", format="ddd")
        assert "database selection" in result
        assert "Bounded Context" in result


class TestContextBudgetIntegration:
    """Test context budget integration with inject()"""

    def test_inject_with_budget_no_compression(self, injector, storage):
        storage.create(
            trigger="*",
            action="Simple rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", context_budget_tokens=5000)
        assert "Simple rule" in result

    def test_inject_with_budget_triggers_compression(self, injector, storage):
        storage.create(
            trigger="*",
            action="Override rule",
            rule_type="forbid",
            override=True,
        )
        for i in range(10):
            storage.create(
                trigger="*",
                action=f"Soft rule {i} with extra text",
                rule_type="avoid",
                override=False,
            )

        result_no_budget = injector.inject("test")
        result_with_budget = injector.inject("test", context_budget_tokens=5)

        assert len(result_with_budget) <= len(result_no_budget)

    def test_estimate_context_usage(self, injector, storage):
        storage.create(
            trigger="*",
            action="Simple rule",
            rule_type="avoid",
            override=False,
        )

        usage = injector.estimate_context_usage("test")
        assert "estimated_tokens" in usage
        assert "budget_tokens" in usage
        assert "usage_percent" in usage
        assert "needs_compression" in usage
        assert usage["total_rules"] >= 1

    def test_estimate_context_usage_empty(self, injector):
        usage = injector.estimate_context_usage("nonexistent")
        assert usage["total_rules"] == 0
        assert usage["estimated_tokens"] == 0
        assert usage["needs_compression"] is False

    def test_inject_with_memories_and_budget(self, injector, storage):
        storage.create(
            trigger="*",
            action="Simple rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject_with_memories(
            "test",
            memories_text="Some memory text",
            context_budget_tokens=5000,
        )
        assert "Simple rule" in result
        assert "Some memory text" in result


class TestValidFormats:
    """Test format validation and dispatch"""

    def test_structured_format_still_works(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="structured")
        assert "## Behavioral Rules (from CarryMem)" in result

    def test_compact_format_still_works(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="compact")
        assert "Rules:" in result

    def test_json_format_still_works(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="json")
        assert '"rules"' in result

    def test_valid_formats_constant(self):
        assert "anchored" in RuleInjector.VALID_FORMATS
        assert "ddd" in RuleInjector.VALID_FORMATS
        assert "structured" in RuleInjector.VALID_FORMATS
        assert "compact" in RuleInjector.VALID_FORMATS
        assert "json" in RuleInjector.VALID_FORMATS


class TestInjectorCoverageGaps:
    """Cover remaining uncovered lines in injector.py"""

    def test_context_budget_compress_with_explicit_budget(self, matcher, storage):
        storage.create(
            trigger="*",
            action="Override",
            rule_type="forbid",
            override=True,
        )
        for i in range(5):
            storage.create(
                trigger="*",
                action=f"Soft rule {i} with extra description text",
                rule_type="avoid",
                override=False,
            )

        matches = matcher.match("test")
        budget = ContextBudget(budget_tokens=2000)
        compressed = budget.compress_rules(matches, budget_tokens=3)
        assert len(compressed) < len(matches)

    def test_context_budget_compress_no_soft_rules(self, matcher, storage):
        storage.create(
            trigger="*",
            action="Override only",
            rule_type="forbid",
            override=True,
        )

        matches = matcher.match("test")
        budget = ContextBudget(budget_tokens=2000)
        compressed = budget.compress_rules(matches)
        assert len(compressed) == 1

    def test_structured_with_metadata(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="structured", include_metadata=True)
        assert "id=" in result
        assert "confidence=" in result

    def test_json_with_metadata(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="json", include_metadata=True)
        assert "rule_id" in result
        assert "match_type" in result

    def test_get_rules_summary_with_matches(self, injector, storage):
        storage.create(
            trigger="*",
            action="Override rule",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Soft rule",
            rule_type="avoid",
            override=False,
        )

        summary = injector.get_rules_summary("test")
        assert summary["total_rules"] >= 2
        assert summary["hard_rules"] >= 1
        assert summary["soft_rules"] >= 1
        assert "forbid" in summary["types"]
        assert "avoid" in summary["types"]
        assert summary["has_global_rules"] is True
        assert summary["avg_score"] > 0

    def test_get_rules_summary_no_matches(self, injector):
        summary = injector.get_rules_summary("nonexistent_xyz_12345")
        assert summary["total_rules"] == 0
        assert summary["hard_rules"] == 0
        assert summary["soft_rules"] == 0
        assert summary["types"] == {}
        assert summary["has_global_rules"] is False

    def test_inject_with_memories_only_memories(self, injector, storage):
        result = injector.inject_with_memories(
            "nonexistent_xyz_12345",
            memories_text="Some memory text",
        )
        assert "Some memory text" in result

    def test_inject_with_memories_both_empty(self, injector):
        result = injector.inject_with_memories("nonexistent_xyz_12345")
        assert result == ""

    def test_inject_with_memories_rules_and_memories(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject_with_memories(
            "test",
            memories_text="Some memory text",
        )
        assert "Test rule" in result
        assert "Some memory text" in result
        assert "---" in result

    def test_inject_with_memories_format_param(self, injector, storage):
        storage.create(
            trigger="*",
            action="Test rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject_with_memories(
            "test",
            memories_text="Memory",
            format="anchored",
        )
        assert "Recommended" in result

    def test_anchored_with_all_three_sections(self, injector, storage):
        storage.create(
            trigger="*",
            action="Never leak",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Prefer Python",
            rule_type="prefer",
            override=False,
        )
        storage.create(
            trigger="*",
            action="Always test",
            rule_type="always",
            override=True,
        )

        result = injector.inject("test", format="anchored")
        assert "Absolute Prohibitions" in result
        assert "Recommended" in result
        assert "Mandatory Actions" in result
        assert "[FORBID]" in result
        assert "[ALWAYS]" in result

    def test_ddd_with_metadata_no_source_memories(self, injector, storage):
        storage.create(
            trigger="*",
            action="Soft rule",
            rule_type="avoid",
            override=False,
        )

        result = injector.inject("test", format="ddd", include_metadata=True)
        assert "id=" in result
        assert "confidence=" in result

    def test_ddd_override_prefer_goes_to_middle(self, injector, storage):
        storage.create(
            trigger="*",
            action="Override prefer",
            rule_type="prefer",
            override=True,
        )

        result = injector.inject("test", format="ddd")
        assert "Override prefer" in result
        assert "Soft Constraint" in result

    def test_context_budget_estimate_tokens_single_char(self):
        budget = ContextBudget(budget_tokens=2000)
        tokens = budget.estimate_tokens("A")
        assert tokens >= 1

    def test_context_budget_compress_all_override(self, matcher, storage):
        storage.create(
            trigger="*",
            action="Override 1",
            rule_type="forbid",
            override=True,
        )
        storage.create(
            trigger="*",
            action="Override 2",
            rule_type="always",
            override=True,
        )

        matches = matcher.match("test")
        budget = ContextBudget(budget_tokens=2000)
        compressed = budget.compress_rules(matches)
        assert len(compressed) == 2
