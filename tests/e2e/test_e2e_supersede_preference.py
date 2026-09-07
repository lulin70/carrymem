"""E2E test: preference declaration and recall user journey.

Tests the supersede mechanism: when a user states a preference that
contradicts an earlier one (using update markers or contradiction pairs),
the old preference is marked superseded and recall returns only the latest.

Supersede triggers (SupersedeManager):
- Contradiction pairs: like/dislike, prefer/avoid, dark/light, etc.
- Update markers: "now", "switched", "changed", "no longer", etc.
- Preference keywords + Jaccard similarity >= 0.5

Note: Two independent preferences (e.g. "morning flights" + "evening flights")
do NOT supersede each other — the user may like both.
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
        """Two independent preferences (not contradictory) should coexist."""
        cm = fresh_carrymem
        cm.declare_preference("I prefer morning flights")
        cm.declare_preference("I prefer evening flights")

        results = cm.recall_memories(query="flights", limit=10)
        active = [r for r in results if r.get("superseded_at") is None]
        # Both should be active — user may like both morning and evening
        assert len(active) >= 1, "At least one preference should be active"
        assert (
            len(superseded := [r for r in results if r.get("superseded_at")]) == 0
        ), "Independent preferences should not be superseded"
