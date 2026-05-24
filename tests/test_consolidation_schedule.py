"""Tests for scheduled consolidation functionality."""
import time
import pytest
from carrymem import CarryMem


class TestScheduleConsolidation:
    """Test schedule_consolidation and stop_consolidation methods."""

    @pytest.fixture
    def cm(self, tmp_path):
        """Create a CarryMem instance with temp database."""
        cm = CarryMem(db_path=str(tmp_path / "test.db"))
        yield cm
        cm.stop_consolidation()
        cm.close()

    def test_schedule_returns_status(self, cm):
        """schedule_consolidation should return status dict."""
        result = cm.schedule_consolidation(interval_hours=1.0)
        assert result["scheduled"] is True
        assert result["interval_hours"] == 1.0
        assert "dry_run" in result

    def test_schedule_minimum_interval(self, cm):
        """Interval below minimum should be clamped to 0.1h."""
        result = cm.schedule_consolidation(interval_hours=0.01)
        assert result["interval_hours"] == 0.1

    def test_stop_consolidation(self, cm):
        """stop_consolidation should cancel the timer."""
        cm.schedule_consolidation(interval_hours=1.0)
        result = cm.stop_consolidation()
        assert result["stopped"] is True

    def test_stop_without_schedule(self, cm):
        """stop_consolidation without active schedule should return stopped=False."""
        result = cm.stop_consolidation()
        assert result["stopped"] is False
        assert "reason" in result

    def test_reschedule_replaces_previous(self, cm):
        """Calling schedule_consolidation again should replace the previous timer."""
        r1 = cm.schedule_consolidation(interval_hours=1.0)
        r2 = cm.schedule_consolidation(interval_hours=2.0)
        assert r2["interval_hours"] == 2.0
        # Should not raise or have duplicate timers
        cm.stop_consolidation()

    def test_schedule_with_dry_run(self, cm):
        """schedule_consolidation should respect dry_run parameter."""
        result = cm.schedule_consolidation(interval_hours=1.0, dry_run=True)
        assert result["dry_run"] is True

    def test_schedule_with_p1_p2_flags(self, cm):
        """schedule_consolidation should respect run_p1 and run_p2 parameters."""
        result = cm.schedule_consolidation(interval_hours=1.0, run_p1=False, run_p2=True)
        assert result["run_p1"] is False
        assert result["run_p2"] is True
