"""
E2E Tests: Version Rollback User Journey

Validates: Edit -> Edit -> View History -> Rollback to v1 -> Verify Data Integrity
"""

import os
import shutil
import tempfile

import pytest

from carrymem import CarryMem


@pytest.fixture
def fresh_carrymem():
    """Create a fresh CarryMem instance with isolated SQLite database."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_version_rollback.db")
    cm = CarryMem(storage="sqlite", db_path=db_path)
    yield cm
    cm.close()
    shutil.rmtree(tmp, ignore_errors=True)


class TestE2EVersionRollbackJourney:
    """Verify: Complete version history and rollback user journey."""

    def test_edit_history_records_all_versions(self, fresh_carrymem):
        """Verify: Multiple edits create a complete version history."""
        cm = fresh_carrymem

        # Step 1: Store initial memory (v1)
        result = cm.classify_and_remember("I prefer PostgreSQL for databases")
        assert result.get("storage_keys") is not None
        storage_keys = result["storage_keys"]
        assert len(storage_keys) >= 1
        storage_key = storage_keys[0]

        # Step 2: Update to v2
        update_result = cm.update_memory(
            storage_key,
            "I prefer PostgreSQL for OLTP workloads",
            reason="More specific",
        )
        assert update_result.get("updated") is True

        # Step 3: Update to v3
        update_result = cm.update_memory(
            storage_key,
            "I always use PostgreSQL, never MySQL",
            reason="Stronger preference",
        )
        assert update_result.get("updated") is True

        # Verify: history has 3 entries (current + 2 versions)
        history = cm.get_memory_history(storage_key)
        assert len(history) == 3, f"Expected 3 versions, got {len(history)}"

        # Verify first entry is current version (is_current=True)
        current_entries = [h for h in history if h.get("is_current") is True]
        assert len(current_entries) == 1, "Should have exactly one current entry"

        # Verify versions are in order (newest first by default from get_memory_history)
        assert history[0]["is_current"] is True
        assert history[0]["version"] > history[1]["version"]

    def test_rollback_to_v1_restores_original(self, fresh_carrymem):
        """Verify: Rolling back to v1 restores original content."""
        cm = fresh_carrymem

        original_content = "I prefer PostgreSQL for databases"

        # Store initial memory (v1)
        result = cm.classify_and_remember(original_content)
        storage_key = result["storage_keys"][0]

        # Update to v2
        cm.update_memory(
            storage_key,
            "I prefer PostgreSQL for OLTP workloads",
            reason="More specific",
        )

        # Update to v3
        cm.update_memory(
            storage_key,
            "I always use PostgreSQL, never MySQL",
            reason="Stronger preference",
        )

        # Get history to find v1's version number
        history = cm.get_memory_history(storage_key)
        v1_entry = [h for h in history if not h.get("is_current")]
        assert len(v1_entry) >= 1, "Should have at least one historical version"
        v1_version = min(h["version"] for h in history)

        # Rollback to v1
        rollback_result = cm.rollback_memory(storage_key, v1_version)
        assert rollback_result.get("rolled_back") is True, f"Rollback failed: {rollback_result}"

        # Verify content matches original
        assert (
            rollback_result["content"] == original_content
        ), f"Expected '{original_content}', got '{rollback_result['content']}'"

        # Also verify via recall that content is restored
        recalled = cm.recall_memories(query="PostgreSQL")
        found = [m for m in recalled if m.get("storage_key") == storage_key]
        assert len(found) >= 1
        assert original_content in found[0].get("content", "")

    def test_rollback_preserves_other_memories(self, fresh_carrymem):
        """Verify: Rolling back one memory does not affect others."""
        cm = fresh_carrymem

        # Store memory A
        result_a = cm.classify_and_remember("I prefer dark mode for my IDE")
        key_a = result_a["storage_keys"][0]

        # Store memory B
        result_b = cm.classify_and_remember("I use Python for data science")
        key_b = result_b["storage_keys"][0]

        original_b_content = "I use Python for data science"

        # Update A multiple times
        cm.update_memory(key_a, "I now prefer light mode", reason="Changed mind")
        cm.update_memory(key_a, "I switched to solarized theme", reason="Another change")

        # Rollback A to v1
        history_a = cm.get_memory_history(key_a)
        v1_version_a = min(h["version"] for h in history_a)
        rollback_result = cm.rollback_memory(key_a, v1_version_a)
        assert rollback_result.get("rolled_back") is True

        # Verify B is unchanged
        recalled_b = cm.recall_memories(query="Python data science")
        found_b = [m for m in recalled_b if m.get("storage_key") == key_b]
        assert len(found_b) >= 1
        assert found_b[0].get("content", "") == original_b_content

    def test_rollback_creates_new_version_entry(self, fresh_carrymem):
        """Verify: Rollback itself is recorded as a new version."""
        cm = fresh_carrymem

        # Store initial memory
        result = cm.classify_and_remember("Initial preference about databases")
        storage_key = result["storage_keys"][0]

        # Update once
        cm.update_memory(
            storage_key,
            "Updated preference about databases",
            reason="First update",
        )

        # Check history count before rollback
        history_before = cm.get_memory_history(storage_key)
        count_before = len(history_before)

        # Rollback to v1
        v1_version = min(h["version"] for h in history_before)
        rollback_result = cm.rollback_memory(storage_key, v1_version)
        assert rollback_result.get("rolled_back") is True

        # After rollback, check history has one more entry with Rollback reason
        history_after = cm.get_memory_history(storage_key)
        count_after = len(history_after)

        # Rollback calls update_memory internally, so it creates a new version
        assert (
            count_after >= count_before
        ), f"History should grow after rollback: before={count_before}, after={count_after}"

        # Find the rollback entry - it should contain "Rollback" in change_reason
        rollback_entries = [h for h in history_after if "Rollback" in h.get("change_reason", "")]
        assert len(rollback_entries) >= 1, "History should contain an entry with 'Rollback' in change_reason"

    def test_rollback_nonexistent_key_returns_none(self, fresh_carrymem):
        """Verify: Rolling back a non-existent storage_key returns rolled_back=False."""
        cm = fresh_carrymem

        result = cm.rollback_memory("nonexistent_storage_key_12345", version=1)
        assert isinstance(result, dict)
        assert result.get("rolled_back") is False
        assert "error" in result or "not found" in result.get("error", "").lower()

    def test_rollback_to_invalid_version_returns_none(self, fresh_carrymem):
        """Verify: Rolling back to a version number that doesn't exist returns rolled_back=False."""
        cm = fresh_carrymem

        # Store a memory
        result = cm.classify_and_remember("Some preference")
        storage_key = result["storage_keys"][0]

        # Update once (so we have v1 and v2 at most)
        cm.update_memory(storage_key, "Updated preference", reason="Update")

        # Try to rollback to version 999 which doesn't exist
        result = cm.rollback_memory(storage_key, version=999)
        assert isinstance(result, dict)
        assert result.get("rolled_back") is False
        assert "error" in result or "not found" in result.get("error", "").lower()
