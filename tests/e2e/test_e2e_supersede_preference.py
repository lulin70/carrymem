"""E2E test: preference declaration and recall user journey.

Tests the supersede mechanism: when a user states a preference that
contradicts an earlier one, the old preference is marked superseded and
recall returns only the latest.

Supersede triggers (SupersedeManager._should_supersede) — exactly two:
- Contradiction pairs: like/dislike, prefer/avoid, dark/light, always/never, etc.
- Update marker ("now", "switched", "changed", "no longer", ...) AND Jaccard >= 0.40

Keyword co-occurrence alone is NOT a trigger. Two independent preferences
(e.g. "I prefer morning flights" + "I prefer evening flights", Jaccard 0.6)
must NOT supersede each other — the user may hold both. This was a P0 defect
(v0.11.0 review §4): the removed third branch superseded on "both statements
contain a preference keyword", silently dropping unrelated memories from recall.

Note: recall filters `superseded_at IS NOT NULL` out by default, so any test
asserting "X was/wasn't superseded" MUST pass `filters={"include_superseded": True}`
— otherwise the assertion is vacuously true.
"""

from __future__ import annotations

import pytest

from carrymem import CarryMem


class TestE2ESupersedePreference:
    """User journey: preference declaration → recall → system prompt."""

    def test_declared_preference_is_recallable(self, fresh_carrymem):
        """User declares a preference; recall should find it."""
        cm = fresh_carrymem
        cm.declare_preference("I prefer morning flights")

        results = cm.recall_memories(query="flights preference")
        contents = " ".join(r["content"].lower() for r in results)
        assert "morning flights" in contents, "Declared preference should be recallable"

    def test_contradictory_preference_triggers_supersede(self, fresh_carrymem):
        """User likes dark mode, then dislikes it; old should be superseded."""
        cm = fresh_carrymem
        cm.declare_preference("I like dark mode")
        cm.declare_preference("I dislike dark mode")

        results = cm.recall_memories(query="dark mode")
        # The old "like dark mode" should be superseded (superseded_at IS NOT NULL)
        active = [r for r in results if r.get("superseded_at") is None]
        superseded = [r for r in results if r.get("superseded_at") is not None]

        assert len(active) >= 1, "Latest preference should be active"
        assert "dislike" in " ".join(
            r["content"].lower() for r in active
        ), "Active preference should be the latest (dislike)"
        # Old preference should be superseded
        if len(results) > 1:
            assert len(superseded) >= 1, "Old contradictory preference should be superseded"
            assert "like dark mode" in " ".join(
                r["content"].lower() for r in superseded
            ), "Superseded preference should be the old one (like)"

    def test_update_marker_triggers_supersede(self, fresh_carrymem):
        """User uses contradiction pair; old preference should be superseded."""
        cm = fresh_carrymem
        cm.declare_preference("I like Vim for editing")
        cm.declare_preference("I dislike Vim for editing")

        results = cm.recall_memories(query="Vim editing")
        active = [r for r in results if r.get("superseded_at") is None]
        superseded = [r for r in results if r.get("superseded_at") is not None]

        assert len(active) >= 1, "Latest preference should be active"
        assert "dislike" in " ".join(
            r["content"].lower() for r in active
        ), "Active preference should be the latest (dislike)"
        if len(results) > 1:
            assert len(superseded) >= 1, "Old preference should be superseded"

    def test_system_prompt_includes_preference(self, fresh_carrymem):
        """build_system_prompt should include declared preference."""
        cm = fresh_carrymem
        cm.declare_preference("Always use type hints in Python code")

        prompt = cm.build_system_prompt(context="Python code style")
        assert "type hint" in prompt.lower(), "Declared preference should appear in system prompt"

    def test_independent_preferences_coexist(self, fresh_carrymem):
        """Two independent preferences (not contradictory) must coexist.

        Regression guard for P0-1. Uses include_superseded=True because default
        recall filters superseded rows out, which made the previous version of
        this test vacuously true.
        """
        cm = fresh_carrymem
        cm.declare_preference("I prefer morning flights")
        cm.declare_preference("I prefer evening flights")

        rows = cm.recall_memories(query="flights", filters={"include_superseded": True}, limit=10)
        assert len(rows) == 2, f"Both preferences should be stored, got {[r['content'] for r in rows]}"

        superseded = [r["content"] for r in rows if r.get("superseded_at")]
        assert superseded == [], (
            "Independent preferences must not supersede each other — the user may hold both. "
            f"Silently hidden: {superseded}"
        )

        active = cm.recall_memories(query="flights", limit=10)
        contents = " ".join(r["content"].lower() for r in active)
        assert (
            "morning" in contents and "evening" in contents
        ), f"Both preferences must be recallable, got: {contents!r}"

    def test_unrelated_preferences_not_superseded(self, fresh_carrymem):
        """Preferences on unrelated topics must not supersede each other (P0-1)."""
        cm = fresh_carrymem
        cm.declare_preference("I prefer dark mode")
        cm.declare_preference("I prefer vim keybindings")

        rows = cm.recall_memories(query="", filters={"include_superseded": True}, limit=10)
        assert len(rows) == 2, f"Both preferences should be stored, got {[r['content'] for r in rows]}"
        assert [
            r["content"] for r in rows if r.get("superseded_at")
        ] == [], "Unrelated preferences must not supersede each other"

    def test_contradictory_preference_still_supersedes(self, fresh_carrymem):
        """The explicit contradiction signal must keep working after the P0-1 fix."""
        cm = fresh_carrymem
        cm.declare_preference("I prefer dark mode")
        cm.declare_preference("I prefer light mode")

        rows = cm.recall_memories(query="mode", filters={"include_superseded": True}, limit=10)
        superseded = [r["content"].lower() for r in rows if r.get("superseded_at")]
        assert superseded == [
            "i prefer dark mode"
        ], f"Contradictory pair dark/light must supersede the old one, got superseded={superseded}"
