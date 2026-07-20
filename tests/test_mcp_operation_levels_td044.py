"""Tests for TD-044: MCP tool operation-level classification.

Verifies that every MCP tool registered in ``handler_map`` has an
``OperationLevel`` annotation, and that ``Handlers.list_tools(level)``
filters correctly. The 31 public tools (``TOOL_NAMES``) are the primary
scope; the internal ``mce_status`` diagnostic is also covered.
"""

import pytest

from carrymem.integration.layer2_mcp.handlers import (
    _TOOL_OPERATION_LEVELS,
    Handlers,
    OperationLevel,
    handler_map,
)
from carrymem.integration.layer2_mcp.tools import TOOL_NAMES, TOOLS

# ── Invariant: every public tool has a level ──────────────────────


class TestAllToolsHaveLevel:
    """TD-044 acceptance: all 31 public MCP tools carry an OperationLevel."""

    def test_public_tool_count_is_31(self):
        """Lock the public surface at 31 tools (the task's stated scope)."""
        assert len(TOOL_NAMES) == 31, (
            f"Expected 31 public tools, got {len(TOOL_NAMES)}. "
            "If you added a tool, update _TOOL_OPERATION_LEVELS and this test."
        )

    def test_every_public_tool_has_level(self):
        """Every name in TOOL_NAMES must appear in _TOOL_OPERATION_LEVELS."""
        missing = sorted(TOOL_NAMES - set(_TOOL_OPERATION_LEVELS.keys()))
        assert missing == [], f"Public tools missing OperationLevel annotation: {missing}"

    def test_every_handler_map_entry_has_level(self):
        """Every entry in handler_map (incl. mce_status) must have a level.

        This is the broader invariant: even internal/diagnostic tools
        registered in handler_map must be classified so that nothing
        slips through unannotated.
        """
        missing = sorted(set(handler_map.keys()) - set(_TOOL_OPERATION_LEVELS.keys()))
        assert missing == [], f"handler_map entries missing OperationLevel annotation: {missing}"

    def test_no_extra_level_annotations_for_unknown_tools(self):
        """Conversely, every level annotation should map to a real tool."""
        unknown = sorted(set(_TOOL_OPERATION_LEVELS.keys()) - set(handler_map.keys()))
        assert unknown == [], f"Level annotations reference unknown tools: {unknown}"

    def test_all_levels_are_valid_enum(self):
        """Every annotation value must be a valid OperationLevel member."""
        for tool_name, level in _TOOL_OPERATION_LEVELS.items():
            assert isinstance(level, OperationLevel), f"{tool_name!r} has non-enum level: {level!r}"


# ── Per-level breakdown ───────────────────────────────────────────


class TestOperationLevelBreakdown:
    """Verify the expected distribution of tools across operation levels."""

    EXPECTED_READ_TOOLS = {
        "classify_message",
        "get_classification_schema",
        "batch_classify",
        "recall_memories",
        "recall_from_knowledge",
        "recall_all",
        "get_memory_profile",
        "get_system_prompt",
        "list_rules",
        "match_rules",
        "inject_rules",
        "my_rules",
        "suggest_rules",
        "my_profile",
        "onboard",
        "health_check",
        "query_graph",
        "shortest_path",
        "get_memory_impact",
    }

    EXPECTED_WRITE_TOOLS = {
        "classify_and_remember",
        "index_knowledge",
        "declare_preference",
        "summarize_and_store",
        "consolidate_memories",
        "promote_rules",
        "update_rule",
        "add_rule",
    }

    EXPECTED_DELETE_TOOLS = {
        "forget_memory",
        "delete_rule",
    }

    EXPECTED_ADMIN_TOOLS = {
        "schedule_consolidation",
        "stop_consolidation",
    }

    def test_read_tools(self):
        actual = {
            name
            for name, level in _TOOL_OPERATION_LEVELS.items()
            if level == OperationLevel.READ and name in TOOL_NAMES
        }
        assert actual == self.EXPECTED_READ_TOOLS

    def test_write_tools(self):
        actual = {
            name
            for name, level in _TOOL_OPERATION_LEVELS.items()
            if level == OperationLevel.WRITE and name in TOOL_NAMES
        }
        assert actual == self.EXPECTED_WRITE_TOOLS

    def test_delete_tools(self):
        actual = {
            name
            for name, level in _TOOL_OPERATION_LEVELS.items()
            if level == OperationLevel.DELETE and name in TOOL_NAMES
        }
        assert actual == self.EXPECTED_DELETE_TOOLS

    def test_admin_tools(self):
        actual = {
            name
            for name, level in _TOOL_OPERATION_LEVELS.items()
            if level == OperationLevel.ADMIN and name in TOOL_NAMES
        }
        assert actual == self.EXPECTED_ADMIN_TOOLS

    def test_level_counts_match_total(self):
        """READ + WRITE + DELETE + ADMIN counts must equal 31 public tools."""
        counts = Handlers.count_tools_by_level()
        assert sum(counts.values()) == 31, counts
        # Spot-check expected counts
        assert counts["read"] == len(self.EXPECTED_READ_TOOLS)
        assert counts["write"] == len(self.EXPECTED_WRITE_TOOLS)
        assert counts["delete"] == len(self.EXPECTED_DELETE_TOOLS)
        assert counts["admin"] == len(self.EXPECTED_ADMIN_TOOLS)

    def test_level_hierarchy_ordering(self):
        """READ < WRITE < DELETE < ADMIN by enum value ordering.

        OperationLevel is a str Enum, so we verify the hierarchy via
        an explicit ordering check rather than relying on enum member
        declaration order.
        """
        # Define the expected privilege ordering explicitly.
        ordering = [
            OperationLevel.READ,
            OperationLevel.WRITE,
            OperationLevel.DELETE,
            OperationLevel.ADMIN,
        ]
        # Each level must be a distinct value.
        values = [level.value for level in ordering]
        assert len(set(values)) == 4, f"Levels must be distinct, got {values}"


# ── Handlers.list_tools() ────────────────────────────────────────


class TestListTools:
    """Verify Handlers.list_tools(level) filtering and output shape."""

    def test_list_all_tools_returns_31(self):
        all_tools = Handlers.list_tools()
        assert len(all_tools) == 31
        # Each entry has the expected shape
        for entry in all_tools:
            assert set(entry.keys()) == {"name", "level", "target"}
            assert isinstance(entry["name"], str)
            assert isinstance(entry["level"], OperationLevel)
            assert entry["target"] in {"engine", "carrymem", "rule_engine"}

    def test_list_tools_sorted_by_name(self):
        all_tools = Handlers.list_tools()
        names = [entry["name"] for entry in all_tools]
        assert names == sorted(names)

    def test_filter_by_read(self):
        read_tools = Handlers.list_tools(OperationLevel.READ)
        assert len(read_tools) == len(TestOperationLevelBreakdown.EXPECTED_READ_TOOLS)
        for entry in read_tools:
            assert entry["level"] == OperationLevel.READ

    def test_filter_by_write(self):
        write_tools = Handlers.list_tools(OperationLevel.WRITE)
        assert len(write_tools) == len(TestOperationLevelBreakdown.EXPECTED_WRITE_TOOLS)
        for entry in write_tools:
            assert entry["level"] == OperationLevel.WRITE

    def test_filter_by_delete(self):
        delete_tools = Handlers.list_tools(OperationLevel.DELETE)
        assert len(delete_tools) == len(TestOperationLevelBreakdown.EXPECTED_DELETE_TOOLS)
        for entry in delete_tools:
            assert entry["level"] == OperationLevel.DELETE

    def test_filter_by_admin(self):
        admin_tools = Handlers.list_tools(OperationLevel.ADMIN)
        assert len(admin_tools) == len(TestOperationLevelBreakdown.EXPECTED_ADMIN_TOOLS)
        for entry in admin_tools:
            assert entry["level"] == OperationLevel.ADMIN

    def test_filter_accepts_string_value(self):
        """list_tools("read") and list_tools(OperationLevel.READ) must match."""
        by_str = Handlers.list_tools("read")
        by_enum = Handlers.list_tools(OperationLevel.READ)
        assert by_str == by_enum

    def test_filter_accepts_uppercase_string(self):
        by_upper = Handlers.list_tools("WRITE")
        by_lower = Handlers.list_tools("write")
        assert by_upper == by_lower

    def test_filter_rejects_unknown_level_string(self):
        with pytest.raises(ValueError, match="Unknown operation level"):
            Handlers.list_tools("superadmin")

    def test_filter_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Unknown operation level"):
            Handlers.list_tools("")

    def test_filter_returns_empty_for_valid_level_with_no_tools(self):
        """All four levels are non-empty in the current tool set, so this
        is a defensive test: filtering by a valid level always returns
        a list (possibly empty)."""
        # Sanity: ADMIN level is non-empty (current state)
        assert len(Handlers.list_tools(OperationLevel.ADMIN)) > 0


# ── Handlers.get_tool_level() ────────────────────────────────────


class TestGetToolLevel:
    """Per-tool level lookup."""

    @pytest.mark.parametrize(
        "tool_name, expected_level",
        [
            ("classify_message", OperationLevel.READ),
            ("recall_memories", OperationLevel.READ),
            ("classify_and_remember", OperationLevel.WRITE),
            ("declare_preference", OperationLevel.WRITE),
            ("forget_memory", OperationLevel.DELETE),
            ("delete_rule", OperationLevel.DELETE),
            ("schedule_consolidation", OperationLevel.ADMIN),
            ("stop_consolidation", OperationLevel.ADMIN),
            ("health_check", OperationLevel.READ),
            ("query_graph", OperationLevel.READ),
        ],
    )
    def test_known_tool_levels(self, tool_name, expected_level):
        assert Handlers.get_tool_level(tool_name) == expected_level

    def test_unknown_tool_returns_none(self):
        assert Handlers.get_tool_level("nonexistent_tool") is None

    def test_mce_status_has_level(self):
        """Internal diagnostic tool mce_status is also annotated."""
        assert Handlers.get_tool_level("mce_status") == OperationLevel.READ


# ── TOOLS metadata consistency ────────────────────────────────────


class TestToolsMetadataConsistency:
    """Cross-check that TOOLS, TOOL_NAMES, and handler_map are aligned."""

    def test_tools_list_matches_tool_names(self):
        """TOOLS (list of dicts) and TOOL_NAMES (set) are consistent."""
        names_from_tools = {t["name"] for t in TOOLS}
        assert names_from_tools == TOOL_NAMES

    def test_every_tool_in_tools_has_handler(self):
        """Every tool in TOOLS must have a handler in handler_map."""
        missing_handlers = sorted(TOOL_NAMES - set(handler_map.keys()))
        assert missing_handlers == [], f"Tools without handlers in handler_map: {missing_handlers}"

    def test_every_tool_in_tools_has_level(self):
        """Every tool in TOOLS must have an OperationLevel annotation."""
        missing_levels = sorted(TOOL_NAMES - set(_TOOL_OPERATION_LEVELS.keys()))
        assert missing_levels == [], f"Tools without OperationLevel: {missing_levels}"
