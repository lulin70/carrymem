"""Tests for CarryMem v0.8.0 — Quality management, TUI, CI integration.

Covers: check_conflicts, check_quality, list_expired, cmd_check
"""

import json
from pathlib import Path

import pytest

try:
    from memory_classification_engine import CarryMem
except ImportError:
    CarryMem = None
from memory_classification_engine.cli import cmd_check


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_v080.db")


class TestCheckConflicts:
    def test_no_conflicts(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I prefer dark mode for all editors")
        conflicts = cm.check_conflicts()
        assert isinstance(conflicts, list)
        cm.close()

    def test_conflicts_with_contradictions(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I like using Vim for editing")
        cm.declare("I dislike using Vim for editing")
        conflicts = cm.check_conflicts()
        assert len(conflicts) >= 1
        conflict_types = [c["conflict_type"] for c in conflicts]
        assert "duplicate" in conflict_types or "contradiction" in conflict_types
        cm.close()

    def test_conflicts_empty_db(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        conflicts = cm.check_conflicts()
        assert conflicts == []
        cm.close()


class TestCheckQuality:
    def test_all_good_quality(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I prefer dark mode for all editors")
        low_quality = cm.check_quality(min_score=0.1)
        assert isinstance(low_quality, list)
        cm.close()

    def test_quality_empty_db(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        low_quality = cm.check_quality()
        assert low_quality == []
        cm.close()

    def test_quality_returns_structure(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I prefer dark mode for all editors")
        low_quality = cm.check_quality(min_score=0.9)
        for item in low_quality:
            assert "storage_key" in item
            assert "score" in item
            assert "reasons" in item
            assert "content" in item
            assert "type" in item
        cm.close()


class TestListExpired:
    def test_no_expired(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I prefer dark mode for all editors")
        expired = cm.list_expired()
        assert isinstance(expired, list)
        cm.close()

    def test_expired_empty_db(self, temp_db):
        cm = CarryMem(db_path=temp_db)
        expired = cm.list_expired()
        assert expired == []
        cm.close()


class TestCmdCheck:
    def test_check_all(self, temp_db, capsys):
        cm = CarryMem(db_path=temp_db)
        cm.declare("I prefer dark mode for all editors")
        cm.close()

        result = cmd_check(["--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Conflicts" in captured.out
        assert "Low Quality" in captured.out
        assert "Expired" in captured.out

    def test_check_conflicts_only(self, temp_db, capsys):
        result = cmd_check(["--conflicts", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Conflicts" in captured.out

    def test_check_quality_only(self, temp_db, capsys):
        result = cmd_check(["--quality", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Low Quality" in captured.out

    def test_check_expired_only(self, temp_db, capsys):
        result = cmd_check(["--expired", "--db", temp_db])
        assert result == 0
        captured = capsys.readouterr()
        assert "Expired" in captured.out
