"""Shared pytest fixtures for E2E tests.

TD-036: Consolidates `fresh_carrymem` fixture previously duplicated in 5 test files.
Uses pytest's `tmp_path` for proper isolation and automatic cleanup.
"""

from __future__ import annotations

import pytest

from carrymem import CarryMem


@pytest.fixture
def fresh_carrymem(tmp_path):
    """Create a fresh CarryMem instance with an isolated SQLite database.

    Uses pytest's `tmp_path` fixture for automatic per-test isolation.
    Cleanup is automatic (pytest manages tmp_path lifecycle).
    """
    db_path = str(tmp_path / "e2e_test.db")
    cm = CarryMem(storage="sqlite", db_path=db_path)
    yield cm
    cm.close()


@pytest.fixture
def fresh_carrymem_no_close(tmp_path):
    """Create a fresh CarryMem instance without auto-close (caller manages lifecycle).

    Useful for tests that need to inspect state after explicit close/shutdown.
    """
    db_path = str(tmp_path / "e2e_test_no_close.db")
    cm = CarryMem(storage="sqlite", db_path=db_path)
    return cm
