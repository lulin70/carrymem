"""Tests for the CarryMem first-run onboarding screen (P1-P1).

Validates:

  * OnboardingScreen can be instantiated with a CarryMem instance.
  * ``seed_sample_memories()`` stores all 5 sample memories.
  * Every sample memory is a non-empty string.
  * OnboardingScreen exposes 4 discrete steps (0..3).
  * Step-transition logic works without requiring a running Textual app.

The Textual-dependent tests are skipped when ``HAS_TEXTUAL`` is False,
mirroring the pattern used in ``tests/test_tui.py``.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.ui.onboarding import (
    HAS_TEXTUAL,
    SAMPLE_MEMORIES,
    STEP_DONE,
    STEP_SEARCH,
    STEP_STORE,
    STEP_WELCOME,
    TOTAL_STEPS,
    seed_sample_memories,
)

# ── Textual-independent tests ─────────────────────────────────────────


class TestSampleMemories(unittest.TestCase):
    """The SAMPLE_MEMORIES seed list must be valid first-run data."""

    def test_has_five_samples(self):
        """The design specifies exactly 5 sample memories."""
        self.assertEqual(len(SAMPLE_MEMORIES), 5)

    def test_all_samples_are_non_empty_strings(self):
        for idx, mem in enumerate(SAMPLE_MEMORIES):
            self.assertIsInstance(mem, str, f"Sample {idx} is not a string: {mem!r}")
            self.assertGreater(len(mem.strip()), 0, f"Sample {idx} is empty")

    def test_samples_are_unique(self):
        """All 5 samples should be distinct (otherwise recall demos break)."""
        self.assertEqual(len(set(SAMPLE_MEMORIES)), len(SAMPLE_MEMORIES))

    def test_no_emoji_in_samples(self):
        """Design constraint: NO emoji anywhere (P0-C1)."""
        # Reject common emoji unicode ranges (U+1F300–U+1FAFF, U+2600–U+27BF).
        for idx, mem in enumerate(SAMPLE_MEMORIES):
            for ch in mem:
                code = ord(ch)
                self.assertFalse(
                    0x1F300 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF,
                    f"Sample {idx} contains emoji-like char {ch!r}",
                )


class TestSeedSampleMemories(unittest.TestCase):
    """seed_sample_memories() must call declare() exactly 5 times."""

    def test_returns_count_five_on_success(self):
        cm = MagicMock()
        cm.declare.return_value = {"status": "ok"}
        count = seed_sample_memories(cm)
        self.assertEqual(count, 5)
        self.assertEqual(cm.declare.call_count, 5)

    def test_calls_declare_with_each_sample(self):
        cm = MagicMock()
        cm.declare.return_value = {"status": "ok"}
        seed_sample_memories(cm)
        called_args = [call.args[0] for call in cm.declare.call_args_list]
        self.assertEqual(called_args, SAMPLE_MEMORIES)

    def test_swallows_declare_failures(self):
        """A failing declare() must not abort the rest of the seeding."""
        cm = MagicMock()
        # Make the 3rd call raise; the other 4 should still succeed.
        cm.declare.side_effect = [
            {"status": "ok"},
            {"status": "ok"},
            ValueError("bad memory"),
            {"status": "ok"},
            {"status": "ok"},
        ]
        count = seed_sample_memories(cm)
        self.assertEqual(count, 4)
        self.assertEqual(cm.declare.call_count, 5)

    def test_all_declare_failures_returns_zero(self):
        cm = MagicMock()
        cm.declare.side_effect = RuntimeError("storage down")
        count = seed_sample_memories(cm)
        self.assertEqual(count, 0)
        self.assertEqual(cm.declare.call_count, 5)

    def test_works_with_real_carrymem_like_duck(self):
        """A duck-typed object exposing declare() must work without subclassing."""

        class FakeCM:
            def __init__(self):
                self.stored = []

            def declare(self, text):
                self.stored.append(text)

        fake = FakeCM()
        count = seed_sample_memories(fake)
        self.assertEqual(count, 5)
        self.assertEqual(fake.stored, SAMPLE_MEMORIES)


class TestStepConstants(unittest.TestCase):
    """Step constants must define 4 discrete steps (0..3)."""

    def test_step_constants_are_distinct_ints(self):
        steps = {STEP_WELCOME, STEP_STORE, STEP_SEARCH, STEP_DONE}
        self.assertEqual(steps, {0, 1, 2, 3})

    def test_total_steps_is_four(self):
        self.assertEqual(TOTAL_STEPS, 4)

    def test_step_order(self):
        """Steps must be ordered welcome < store < search < done."""
        self.assertLess(STEP_WELCOME, STEP_STORE)
        self.assertLess(STEP_STORE, STEP_SEARCH)
        self.assertLess(STEP_SEARCH, STEP_DONE)

    def test_step_range_zero_to_three(self):
        """Steps must be 0..3 inclusive (4 discrete values)."""
        for s in (STEP_WELCOME, STEP_STORE, STEP_SEARCH, STEP_DONE):
            self.assertGreaterEqual(s, 0)
            self.assertLessEqual(s, 3)


# ── Textual-dependent tests (skipped when textual is unavailable) ────

if not HAS_TEXTUAL:

    class TestOnboardingSkipped(unittest.TestCase):
        def test_textual_not_installed(self):
            self.skipTest("Textual is not installed; skipping OnboardingScreen tests")

else:
    from carrymem.ui.onboarding import OnboardingScreen

    def _make_mock_cm():
        """Build a MagicMock CarryMem good enough for onboarding."""
        cm = MagicMock()
        cm.declare.return_value = {"declared": True, "storage_keys": ["k1"]}
        cm.recall_memories.return_value = [{"content": "mock", "type": "user_preference"}]
        return cm

    class TestOnboardingInstantiation(unittest.TestCase):
        """OnboardingScreen can be constructed with a CarryMem instance."""

        def test_instantiation_with_mock_cm(self):
            cm = _make_mock_cm()
            screen = OnboardingScreen(cm)
            self.assertIs(screen.cm, cm)
            self.assertEqual(screen.step, STEP_WELCOME)
            self.assertIsNone(screen.stored_memory)
            self.assertEqual(screen.search_results_count, 0)

        def test_initial_step_is_welcome(self):
            screen = OnboardingScreen(_make_mock_cm())
            self.assertEqual(screen.step, STEP_WELCOME)

        def test_bindings_include_skip(self):
            """Esc and q must skip the onboarding."""
            keys = {b.key for b in OnboardingScreen.BINDINGS}
            self.assertIn("escape", keys)
            self.assertIn("q", keys)

        def test_is_modal_screen(self):
            """OnboardingScreen must inherit from ModalScreen so it overlays the TUI."""
            from textual.screen import ModalScreen

            self.assertTrue(issubclass(OnboardingScreen, ModalScreen))

    class TestStepTransitions(unittest.TestCase):
        """Step advance logic without a running Textual app."""

        def test_advance_step_welcome_to_store(self):
            screen = OnboardingScreen(_make_mock_cm())
            screen._advance_step()
            self.assertEqual(screen.step, STEP_STORE)

        def test_advance_step_clamps_at_done(self):
            """_advance_step must never exceed STEP_DONE."""
            screen = OnboardingScreen(_make_mock_cm())
            for _ in range(10):
                screen._advance_step()
            self.assertEqual(screen.step, STEP_DONE)

        def test_full_flow_transitions(self):
            """Welcome -> Store -> Search -> Done in sequence."""
            screen = OnboardingScreen(_make_mock_cm())
            self.assertEqual(screen.step, STEP_WELCOME)
            screen._advance_step()
            self.assertEqual(screen.step, STEP_STORE)
            screen._advance_step()
            self.assertEqual(screen.step, STEP_SEARCH)
            screen._advance_step()
            self.assertEqual(screen.step, STEP_DONE)
            screen._advance_step()  # should stay at DONE
            self.assertEqual(screen.step, STEP_DONE)

        def test_update_visibility_is_safe_when_not_mounted(self):
            """_update_visibility() must not raise when widgets are not mounted (unit tests)."""
            screen = OnboardingScreen(_make_mock_cm())
            screen._advance_step()
            # _advance_step calls _update_visibility internally; should be a no-op
            # rather than raising when the screen is not mounted.
            screen._update_visibility()

    class TestStoreLogic(unittest.TestCase):
        """The store-step action calls cm.declare() and tracks the stored text."""

        def test_do_store_calls_declare(self):
            cm = _make_mock_cm()
            screen = OnboardingScreen(cm)
            # Skip ahead to store step and inject a fake input value.
            screen._advance_step()  # STEP_STORE
            screen._read_input = lambda selector: "I prefer dark mode" if selector == "#memory-input" else None
            screen._do_store()
            cm.declare.assert_called_once_with("I prefer dark mode")
            self.assertEqual(screen.stored_memory, "I prefer dark mode")
            self.assertIsNone(screen._store_error)

        def test_do_store_empty_input_does_not_call_declare(self):
            cm = _make_mock_cm()
            screen = OnboardingScreen(cm)
            screen._advance_step()
            screen._read_input = lambda selector: "" if selector == "#memory-input" else None
            screen._do_store()
            cm.declare.assert_not_called()
            self.assertIsNone(screen.stored_memory)

        def test_do_store_swallows_declare_failure(self):
            cm = _make_mock_cm()
            cm.declare.side_effect = RuntimeError("storage down")
            screen = OnboardingScreen(cm)
            screen._advance_step()
            screen._read_input = lambda selector: "x" if selector == "#memory-input" else None
            screen._do_store()
            self.assertIsNone(screen.stored_memory)
            self.assertEqual(screen._store_error, "storage down")

        def test_do_store_returns_silently_when_input_not_mounted(self):
            """If _read_input returns None (widget not mounted), _do_store is a no-op."""
            cm = _make_mock_cm()
            screen = OnboardingScreen(cm)
            screen._advance_step()
            screen._read_input = lambda selector: None
            screen._do_store()
            cm.declare.assert_not_called()

    class TestSearchLogic(unittest.TestCase):
        """The search-step action calls cm.recall_memories() and tracks count."""

        def test_do_search_calls_recall_memories(self):
            cm = _make_mock_cm()
            cm.recall_memories.return_value = [{"content": "a"}, {"content": "b"}]
            screen = OnboardingScreen(cm)
            screen.step = STEP_SEARCH  # jump straight to search
            screen._read_input = lambda selector: "dark" if selector == "#search-input" else None
            screen._do_search()
            cm.recall_memories.assert_called_once_with(query="dark")
            self.assertEqual(screen.search_results_count, 2)
            self.assertIsNone(screen._search_error)

        def test_do_search_empty_query_no_call(self):
            cm = _make_mock_cm()
            screen = OnboardingScreen(cm)
            screen.step = STEP_SEARCH
            screen._read_input = lambda selector: "" if selector == "#search-input" else None
            screen._do_search()
            cm.recall_memories.assert_not_called()
            self.assertEqual(screen.search_results_count, 0)

        def test_do_search_handles_zero_results(self):
            cm = _make_mock_cm()
            cm.recall_memories.return_value = []
            screen = OnboardingScreen(cm)
            screen.step = STEP_SEARCH
            screen._read_input = lambda selector: "nope" if selector == "#search-input" else None
            screen._do_search()
            self.assertEqual(screen.search_results_count, 0)

        def test_do_search_swallows_recall_failure(self):
            cm = _make_mock_cm()
            cm.recall_memories.side_effect = RuntimeError("index error")
            screen = OnboardingScreen(cm)
            screen.step = STEP_SEARCH
            screen._read_input = lambda selector: "q" if selector == "#search-input" else None
            screen._do_search()
            self.assertEqual(screen._search_error, "index error")
            self.assertEqual(screen.search_results_count, 0)

        def test_do_search_with_non_list_result(self):
            """Defensive: recall_memories returning a non-list must be reported as 0."""
            cm = _make_mock_cm()
            cm.recall_memories.return_value = None
            screen = OnboardingScreen(cm)
            screen.step = STEP_SEARCH
            screen._read_input = lambda selector: "q" if selector == "#search-input" else None
            screen._do_search()
            self.assertEqual(screen.search_results_count, 0)

    class TestOnboardingRenderIntegration:
        """Lightweight integration: render the screen with Textual's test pilot.

        NOTE: This class deliberately does NOT inherit from ``unittest.TestCase``.
        pytest-asyncio in AUTO mode only properly awaits async test methods on
        plain pytest classes (see tests/test_tui.py TestTuiAccessibility for
        the same pattern). Async methods inside ``unittest.TestCase`` are
        invoked synchronously and the coroutine is never awaited, so the
        test body would never actually execute.
        """

        async def test_screen_renders_welcome_step(self):
            from textual.app import App

            class _Host(App[None]):
                def __init__(self, cm):
                    super().__init__()
                    self._cm = cm

            app = _Host(_make_mock_cm())
            async with app.run_test() as pilot:
                screen = OnboardingScreen(app._cm)
                app.push_screen(screen)
                await pilot.pause()
                # On welcome step the Start button must be present and enabled.
                start_btn = app.screen.query_one("#start-btn")
                assert start_btn is not None
                assert not start_btn.disabled
                # Skip button must also be present.
                assert app.screen.query_one("#skip-btn") is not None

        async def test_start_button_advances_to_store_step(self):
            from textual.app import App

            class _Host(App[None]):
                def __init__(self, cm):
                    super().__init__()
                    self._cm = cm

            app = _Host(_make_mock_cm())
            async with app.run_test() as pilot:
                screen = OnboardingScreen(app._cm)
                app.push_screen(screen)
                await pilot.pause()
                active = app.screen
                assert isinstance(active, OnboardingScreen)
                active.query_one("#start-btn").press()
                await pilot.pause()
                # Now memory-input must exist (store step) and step must advance.
                mem_input = active.query_one("#memory-input")
                assert mem_input is not None
                assert active.step == STEP_STORE


if __name__ == "__main__":
    unittest.main()
