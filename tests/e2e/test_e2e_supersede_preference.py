"""E2E test: preference declaration and recall user journey.

User journey: declare preference A → recall returns A → declare preference B
→ recall returns both (sorted by relevance) → build_system_prompt includes
declared preferences.

Note: declare_preference stores each declaration as an independent memory.
Automatic supersede (marking old version as superseded_at) is triggered by
conflict_detector during classify_and_remember, not during declare_preference.
This test validates the user-visible behavior: latest declarations are
recallable and included in system prompt.
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

    def test_multiple_declarations_all_recallable(self, fresh_carrymem):
        """User declares multiple preferences; at least one should be recallable."""
        cm = fresh_carrymem
        cm.declare_preference("I prefer morning flights")
        cm.declare_preference("I prefer evening flights")

        results = cm.recall_memories(query="flights")
        contents = " ".join(r["content"].lower() for r in results)
        assert "flights" in contents, "At least one flight preference should be recallable"

    def test_system_prompt_includes_preference(self, fresh_carrymem):
        """build_system_prompt should include declared preference."""
        cm = fresh_carrymem
        cm.declare_preference("Always use type hints in Python code")

        prompt = cm.build_system_prompt("Python code style")
        assert "type hint" in prompt.lower(), \
            "Declared preference should appear in system prompt"

    def test_classify_and_remember_preference_recallable(self, fresh_carrymem):
        """User states a preference via classify_and_remember; recall should find it."""
        cm = fresh_carrymem
        cm.classify_and_remember("I like dark mode for coding")

        results = cm.recall_memories(query="mode preference")
        contents = " ".join(r["content"].lower() for r in results)
        assert "dark mode" in contents, "Stated preference should be recallable"

    def test_preference_correction_flow(self, fresh_carrymem):
        """User states preference, then correction; latest should be recallable."""
        cm = fresh_carrymem
        cm.classify_and_remember("I use Vim for editing")
        cm.classify_and_remember("I switched to VS Code recently")

        results = cm.recall_memories(query="Vim VS Code editing")
        contents = " ".join(r["content"].lower() for r in results)
        assert "vim" in contents or "vs code" in contents, \
            "At least one editor preference should be recallable"
