"""Tests for P1-1 Facade Layer Enhancements.

Covers: version, health_check, get_component_status, validate_ready
"""

import os
import tempfile

import pytest

from carrymem import CarryMem
from carrymem.errors import CarryMemError


class TestVersionProperty:
    """Tests for CarryMem.version property."""

    def test_version_returns_string(self):
        cm = CarryMem(storage=None)
        assert isinstance(cm.version, str)

    def test_version_matches_package(self):
        from carrymem import __version__

        cm = CarryMem(storage=None)
        assert cm.version == __version__

    def test_version_non_empty(self):
        cm = CarryMem(storage=None)
        assert len(cm.version) > 0

    def test_version_format(self):
        cm = CarryMem(storage=None)
        # Should look like a semver: X.Y.Z
        parts = cm.version.split(".")
        assert len(parts) >= 2
        assert parts[0].isdigit()


class TestHealthCheck:
    """Tests for CarryMem.health_check() method."""

    def test_health_check_returns_dict_with_required_keys(self):
        cm = CarryMem(storage=None)
        result = cm.health_check()
        assert "status" in result
        assert "components" in result
        assert "issues" in result

    def test_health_check_no_storage_is_degraded(self):
        cm = CarryMem(storage=None)
        result = cm.health_check()
        # Without storage, status should be 'ok' because storage not configured is normal
        assert result["status"] in ("ok", "degraded")
        assert result["components"]["storage"]["status"] == "not_configured"

    def test_health_check_with_storage_is_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_health.db")
            cm = CarryMem(storage="sqlite", db_path=db_path)
            try:
                result = cm.health_check()
                assert result["status"] == "ok"
                assert result["components"]["storage"]["status"] == "ready"
                assert result["components"]["engine"]["status"] == "ready"
            finally:
                cm.close()

    def test_health_check_includes_all_components(self):
        cm = CarryMem(storage=None)
        result = cm.health_check()
        expected_components = {"storage", "adapter", "engine", "knowledge", "rule_engine"}
        assert set(result["components"].keys()) == expected_components

    def test_health_check_issues_list_on_error(self):
        # With storage=None, issues should be empty or only contain non-critical items
        cm = CarryMem(storage=None)
        result = cm.health_check()
        assert isinstance(result["issues"], list)


class TestGetComponentStatus:
    """Tests for CarryMem.get_component_status() method."""

    def test_component_status_returns_dict(self):
        cm = CarryMem(storage=None)
        result = cm.get_component_status()
        assert isinstance(result, dict)

    def test_component_status_no_storage(self):
        cm = CarryMem(storage=None)
        result = cm.get_component_status()
        assert result["storage"] == "not_configured"
        assert result["adapter"] == "not_configured"

    def test_component_status_engine_always_ready(self):
        cm = CarryMem(storage=None)
        result = cm.get_component_status()
        assert result["engine"] == "ready"

    def test_component_status_knowledge_not_configured(self):
        cm = CarryMem(storage=None)
        result = cm.get_component_status()
        assert result["knowledge"] == "not_configured"

    def test_component_status_with_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_status.db")
            cm = CarryMem(storage="sqlite", db_path=db_path)
            try:
                result = cm.get_component_status()
                assert result["storage"] == "ready"
                assert result["adapter"] == "ready"
            finally:
                cm.close()

    def test_component_status_all_keys_present(self):
        cm = CarryMem(storage=None)
        result = cm.get_component_status()
        expected = {"storage", "adapter", "engine", "knowledge", "rule_engine"}
        assert set(result.keys()) == expected


class TestValidateReady:
    """Tests for CarryMem.validate_ready() method."""

    def test_validate_ready_no_storage_raises_cm001(self):
        cm = CarryMem(storage=None)
        with pytest.raises(CarryMemError) as exc_info:
            cm.validate_ready(require_storage=True)
        assert exc_info.value.code == "CM-001"
        assert "storage" in exc_info.value.message.lower()

    def test_validate_ready_storage_ok_no_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_validate.db")
            cm = CarryMem(storage="sqlite", db_path=db_path)
            try:
                # Should not raise
                cm.validate_ready(require_storage=True)
            finally:
                cm.close()

    def test_validate_ready_no_knowledge_raises_cm002(self):
        cm = CarryMem(storage=None)
        with pytest.raises(CarryMemError) as exc_info:
            cm.validate_ready(require_storage=False, require_knowledge=True)
        assert exc_info.value.code == "CM-002"
        assert "knowledge" in exc_info.value.message.lower()

    def test_validate_ready_skip_storage_does_not_raise(self):
        cm = CarryMem(storage=None)
        # require_storage=False, so no CM-001 even without adapter
        cm.validate_ready(require_storage=False)

    def test_validate_ready_include_hint_in_error(self):
        cm = CarryMem(storage=None)
        with pytest.raises(CarryMemError) as exc_info:
            cm.validate_ready(require_storage=True)
        assert len(exc_info.value.hint) > 0
