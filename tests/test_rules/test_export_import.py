"""
Test Suite for Rule Export/Import

Validates:
- export_rules() output format and completeness
- import_rules() with skip/overwrite/rename modes
- Round-trip export→import integrity
- Error handling for invalid data
- Status filtering on export
"""

import pytest
import tempfile
import os

from carrymem.rules import RuleEngine
from carrymem.rules import ImportModeError


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def engine(temp_db):
    """Create RuleEngine instance with temp database"""
    return RuleEngine(temp_db)


@pytest.fixture
def populated_engine(engine):
    """Create engine with sample rules"""
    engine.add_rule(trigger="写报告", action="控制在3页以内", rule_type="format")
    engine.add_rule(trigger="技术选型", action="优先Python", rule_type="prefer")
    engine.add_rule(trigger="代码评审", action="检查安全问题", rule_type="always")
    return engine


class TestExportRules:
    """Test export_rules() method"""

    def test_export_format_header(self, engine):
        """Export should include format header"""
        data = engine.export_rules()
        assert data["format"] == "carrymem-rules-v1"

    def test_export_includes_version(self, engine):
        """Export should include current version"""
        from carrymem.__version__ import __version__

        data = engine.export_rules()
        assert data["version"] == __version__

    def test_export_includes_timestamp(self, engine):
        """Export should include ISO timestamp"""
        data = engine.export_rules()
        assert "exported_at" in data
        assert len(data["exported_at"]) > 10

    def test_export_empty_rules(self, engine):
        """Export with no rules should return empty list"""
        data = engine.export_rules()
        assert data["total_rules"] == 0
        assert data["rules"] == []

    def test_export_with_rules(self, populated_engine):
        """Export should include all rules"""
        data = populated_engine.export_rules()
        assert data["total_rules"] == 3
        assert len(data["rules"]) == 3

    def test_export_rule_has_required_fields(self, populated_engine):
        """Each exported rule should have required fields"""
        data = populated_engine.export_rules()
        required = {"id", "trigger", "action", "rule_type", "status", "override"}
        for rule_dict in data["rules"]:
            missing = required - set(rule_dict.keys())
            assert not missing, f"Exported rule missing fields: {missing}"

    def test_export_status_filter_active(self, populated_engine):
        """Export with status filter should only include matching rules"""
        rules = populated_engine.list_rules(status="active")
        first_rule = rules[0]
        populated_engine.update_rule(first_rule.id, status="paused")

        data = populated_engine.export_rules(status="active")
        assert data["total_rules"] == 2

        data_paused = populated_engine.export_rules(status="paused")
        assert data_paused["total_rules"] == 1

    def test_export_status_filter_none(self, populated_engine):
        """Export without status filter should include all rules"""
        data = populated_engine.export_rules()
        assert data["total_rules"] == 3


class TestImportRules:
    """Test import_rules() method"""

    def test_import_basic(self, engine):
        """Should import rules from valid export data"""
        export_data = {
            "format": "carrymem-rules-v1",
            "rules": [
                {
                    "trigger": "写报告",
                    "action": "控制在3页以内",
                    "rule_type": "format",
                    "override": 1,
                    "source_memories": [],
                    "derived_from": "manual",
                    "confidence": 0.8,
                }
            ],
        }
        stats = engine.import_rules(export_data)
        assert stats["imported"] == 1
        assert stats["skipped"] == 0

    def test_import_invalid_format_raises_error(self, engine):
        """Should raise ValueError for unsupported format"""
        with pytest.raises(ValueError, match="Unsupported format"):
            engine.import_rules({"format": "unknown-format", "rules": []})

    def test_import_missing_format_raises_error(self, engine):
        """Should raise ValueError when format header is missing"""
        with pytest.raises(ValueError, match="Unsupported format"):
            engine.import_rules({"rules": []})

    def test_import_skip_mode(self, populated_engine):
        """Skip mode should not import duplicate rules"""
        data = populated_engine.export_rules()
        stats = populated_engine.import_rules(data, mode="skip")
        assert stats["skipped"] == 3
        assert stats["imported"] == 0

    def test_import_overwrite_mode(self, populated_engine):
        """Overwrite mode should replace existing rules"""
        data = populated_engine.export_rules()
        stats = populated_engine.import_rules(data, mode="overwrite")
        assert stats["overwritten"] == 3
        assert stats["imported"] == 3
        assert stats["skipped"] == 0

    def test_import_rename_mode(self, populated_engine):
        """Rename mode should import with new IDs"""
        data = populated_engine.export_rules()
        stats = populated_engine.import_rules(data, mode="rename")
        assert stats["imported"] == 3
        assert stats["skipped"] == 0

        total = populated_engine.count_rules()
        assert total == 6

    def test_import_invalid_mode_raises_error(self, populated_engine):
        """Should raise ValueError for unknown import mode"""
        data = populated_engine.export_rules()
        with pytest.raises(ImportModeError, match="Unknown import mode"):
            populated_engine.import_rules(data, mode="invalid_mode")

    def test_import_with_errors(self, engine):
        """Should collect errors for invalid rules"""
        export_data = {
            "format": "carrymem-rules-v1",
            "rules": [
                {
                    "trigger": "valid trigger",
                    "action": "valid action",
                    "rule_type": "avoid",
                    "override": 1,
                    "source_memories": [],
                    "derived_from": "manual",
                    "confidence": 0.8,
                },
                {
                    "trigger": "",
                    "action": "",
                    "rule_type": "invalid_type",
                    "override": 1,
                    "source_memories": [],
                    "derived_from": "manual",
                    "confidence": 0.8,
                },
            ],
        }
        stats = engine.import_rules(export_data)
        assert stats["imported"] >= 1
        assert len(stats["errors"]) >= 1

    def test_import_empty_rules_list(self, engine):
        """Should handle empty rules list gracefully"""
        export_data = {
            "format": "carrymem-rules-v1",
            "rules": [],
        }
        stats = engine.import_rules(export_data)
        assert stats["imported"] == 0
        assert stats["skipped"] == 0


class TestExportImportRoundTrip:
    """Test full round-trip: export → import → verify"""

    def test_round_trip_preserves_count(self, populated_engine):
        """Round-trip should preserve rule count"""
        data = populated_engine.export_rules()
        original_count = populated_engine.count_rules()

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine2 = RuleEngine(path)
            stats = engine2.import_rules(data, mode="skip")
            assert stats["imported"] == original_count
            assert engine2.count_rules() == original_count
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_round_trip_preserves_triggers(self, populated_engine):
        """Round-trip should preserve all trigger values"""
        data = populated_engine.export_rules()
        original_triggers = {r["trigger"] for r in data["rules"]}

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine2 = RuleEngine(path)
            engine2.import_rules(data, mode="skip")
            imported_triggers = {r.trigger for r in engine2.list_rules(limit=100)}
            assert imported_triggers == original_triggers
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_round_trip_preserves_rule_types(self, populated_engine):
        """Round-trip should preserve rule types"""
        data = populated_engine.export_rules()
        original_types = {r["rule_type"] for r in data["rules"]}

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine2 = RuleEngine(path)
            engine2.import_rules(data, mode="skip")
            imported_types = {r.rule_type for r in engine2.list_rules(limit=100)}
            assert imported_types == original_types
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_round_trip_preserves_override(self, populated_engine):
        """Round-trip should preserve override (hard/soft) status"""
        data = populated_engine.export_rules()
        original_overrides = {r["override"] for r in data["rules"]}

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            engine2 = RuleEngine(path)
            engine2.import_rules(data, mode="skip")
            imported_overrides = {r.override for r in engine2.list_rules(limit=100)}
            assert imported_overrides == original_overrides
        finally:
            if os.path.exists(path):
                os.unlink(path)
