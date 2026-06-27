"""Comprehensive tests for CarryMem TUI (textual.app).

Uses Textual's built-in test mode (app.run_test()) for headless testing.
Mocks CarryMem to avoid real database operations.

Covers:
  - App startup / shutdown lifecycle
  - Component rendering (sidebar, content, search bar, status bar, stats panel)
  - Keyboard navigation (j/k/up/down, Enter for detail)
  - Filter switching (1-5 keys)
  - Search functionality (/ and s keys)
  - Add memory mode (a key + input submit)
  - Help screen (? key)
  - Memory detail screen
  - Stats panel updates
  - Data binding correctness
  - HAS_TEXTUAL fallback
"""

import os
import sys
import tempfile
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.tui import HAS_TEXTUAL

# ── Skip entire module if textual not installed ────────────────────

if not HAS_TEXTUAL:

    class TestTUISkipped(unittest.TestCase):
        def test_textual_not_installed(self):
            self.skipTest("Textual is not installed; skipping all TUI tests")

else:
    import pytest
    from textual.app import App
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Input, Static

    from carrymem.tui import (
        _MORANDI,
        _TYPE_ICONS,
        _TYPE_LABELS,
        CarryMemTUI,
        HelpScreen,
        MemoryDetailScreen,
        StatsPanel,
        run_tui,
    )

    # ── Fixtures & Helpers ──────────────────────────────────────────

    SAMPLE_MEMORIES: List[Dict[str, Any]] = [
        {
            "type": "user_preference",
            "content": "I prefer dark mode in IDEs",
            "confidence": 0.95,
            "importance_score": 8.5,
            "storage_key": "pref:dark_mode",
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
            "namespace": "default",
        },
        {
            "type": "fact_declaration",
            "content": "Python uses zero-based indexing",
            "confidence": 1.0,
            "importance_score": 9.2,
            "storage_key": "fact:python_indexing",
            "created_at": "2024-01-14T08:30:00",
            "updated_at": "2024-01-14T08:30:00",
            "namespace": "default",
        },
        {
            "type": "correction",
            "content": "Use PostgreSQL not MongoDB for relational data",
            "confidence": 0.88,
            "importance_score": 7.8,
            "storage_key": "corr:db_choice",
            "created_at": "2024-01-13T14:20:00",
            "updated_at": "2024-01-13T14:20:00",
            "namespace": "default",
        },
        {
            "type": "decision",
            "content": "Chose FastAPI over Flask for new API project",
            "confidence": 0.92,
            "importance_score": 8.0,
            "storage_key": "dec:fastapi_choice",
            "created_at": "2024-01-12T09:00:00",
            "updated_at": "2024-01-12T09:00:00",
            "namespace": "default",
        },
    ]

    SAMPLE_STATS: Dict[str, Any] = {
        "total_count": 42,
        "by_type": {
            "user_preference": 12,
            "fact_declaration": 15,
            "correction": 5,
            "decision": 6,
            "task_pattern": 3,
            "contextual_observation": 1,
        },
    }

    EMPTY_STATS: Dict[str, Any] = {
        "total_count": 0,
        "by_type": {},
    }

    def _make_mock_cm(
        memories: List[Dict[str, Any]] = SAMPLE_MEMORIES,
        stats: Dict[str, Any] = SAMPLE_STATS,
    ) -> MagicMock:
        """Create a mocked CarryMem instance."""
        mock = MagicMock()
        mock.recall_memories.return_value = memories
        mock.get_stats.return_value = stats
        mock.declare.return_value = {"status": "ok"}
        mock.close = MagicMock()
        return mock

    # ══════════════════════════════════════════════════════════════════
    # Test Group 1: Constants & Configuration
    # ══════════════════════════════════════════════════════════════════

    class TestMorandiPalette(unittest.TestCase):
        """Verify Morandi color palette constants."""

        def test_palette_has_all_required_keys(self):
            required = [
                "primary",
                "secondary",
                "accent",
                "bg_dark",
                "bg_surface",
                "bg_elevated",
                "text_primary",
                "text_secondary",
                "text_muted",
                "success",
                "warning",
                "error",
                "info",
                "border",
                "border_active",
            ]
            for key in required:
                self.assertIn(key, _MORANDI, f"Missing palette key: {key}")

        def test_palette_values_are_hex_colors(self):
            for name, color in _MORANDI.items():
                self.assertTrue(
                    color.startswith("#"),
                    f"Palette {name}={color} is not a hex color",
                )
                self.assertEqual(len(color), 7, f"Palette {name} should be #RRGGBB format")

        def test_no_harsh_green_colors(self):
            """Morandi palette must NOT contain bright green (#00FF00 etc)."""
            harsh_greens = ["#00ff00", "#00FF00", "#00ff00", "#0f0", "#0F0"]
            for name, color in _MORANDI.items():
                self.assertNotIn(color.lower(), harsh_greens)

    class TestTypeIconsAndLabels(unittest.TestCase):
        """Verify type icon and label mappings."""

        def test_all_memory_types_have_icons(self):
            expected_types = [
                "user_preference",
                "fact_declaration",
                "correction",
                "decision",
                "task_pattern",
                "contextual_observation",
                "knowledge",
                "unknown",
            ]
            for t in expected_types:
                self.assertIn(t, _TYPE_ICONS, f"Missing icon for type: {t}")
                self.assertIn(t, _TYPE_LABELS, f"Missing label for type: {t}")

        def test_unknown_type_fallback(self):
            self.assertIn("unknown", _TYPE_ICONS)
            self.assertIn("unknown", _TYPE_LABELS)

        def test_labels_are_human_readable(self):
            for t, label in _TYPE_LABELS.items():
                self.assertGreater(len(label), 0, f"Empty label for {t}")

    # ══════════════════════════════════════════════════════════════════
    # Test Group 2: App Lifecycle
    # ══════════════════════════════════════════════════════════════════

    class TestAppLifecycle(unittest.TestCase):
        """Test app startup, mount, and shutdown."""

        @patch("carrymem.tui.CarryMem")
        async def test_app_starts_and_mounts(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                self.assertIsNotNone(app.cm)
                MockCM.assert_called_once()

        @patch("carrymem.tui.CarryMem")
        async def test_app_shutdown_closes_connection(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                pass  # context manager handles shutdown
            mock_cm.close.assert_called_once()

        @patch("carrymem.tui.CarryMem")
        async def test_app_uses_default_namespace(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            self.assertEqual(app.namespace, "default")

        @patch("carrymem.tui.CarryMem")
        async def test_app_accepts_custom_namespace(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI(namespace="test_ns")
            self.assertEqual(app.namespace, "test_ns")

    # ══════════════════════════════════════════════════════════════════
    # Test Group 3: Component Rendering
    # ══════════════════════════════════════════════════════════════════

    class TestComponentRendering(unittest.TestCase):
        """Test that all UI components render correctly."""

        @patch("carrymem.tui.CarryMem")
        async def test_sidebar_renders_with_title(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                sidebar = app.query_one("#sidebar", Vertical)
                self.assertIsNotNone(sidebar)
                title = app.query_one("#sidebar-title", Static)
                self.assertIn("CarryMem", title.content)

        @patch("carrymem.tui.CarryMem")
        async def test_search_bar_present(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                search_bar = app.query_one("#search-bar", Horizontal)
                self.assertIsNotNone(search_bar)
                search_input = app.query_one("#search-input", Input)
                self.assertIsNotNone(search_input)

        @patch("carrymem.tui.CarryMem")
        async def test_content_area_present(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                content = app.query_one("#content", Vertical)
                self.assertIsNotNone(content)
                memory_list = app.query_one("#memory-list", Static)
                self.assertIsNotNone(memory_list)

        @patch("carrymem.tui.CarryMem")
        async def test_status_bar_present(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                status = app.query_one("#status-bar", Static)
                self.assertIsNotNone(status)

        @patch("carrymem.tui.CarryMem")
        async def test_stats_panel_present(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                panel = app.query_one("#stats-panel", StatsPanel)
                self.assertIsInstance(panel, StatsPanel)

        @patch("carrymem.tui.CarryMem")
        async def test_footer_present(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                from textual.widgets import Footer

                footer = app.query(Footer)
                self.assertGreater(len(footer), 0)

        @patch("carrymem.tui.CarryMem")
        async def test_header_present(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                from textual.widgets import Header

                header = app.query(Header)
                self.assertGreater(len(header), 0)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 4: Data Binding & Memory Rendering
    # ══════════════════════════════════════════════════════════════════

    class TestDataBinding(unittest.TestCase):
        """Test that data flows correctly into UI components."""

        @patch("carrymem.tui.CarryMem")
        async def test_memories_load_on_mount(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES[:2])
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                mock_cm.recall_memories.assert_called()

        @patch("carrymem.tui.CarryMem")
        async def test_memory_list_shows_content(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES[:2])
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                memory_list = app.query_one("#memory-list", Static)
                text = str(memory_list.content or "")
                self.assertIn("dark mode", text.lower())
                self.assertIn("python", text.lower())

        @patch("carrymem.tui.CarryMem")
        async def test_empty_state_displayed_when_no_memories(self, MockCM):
            mock_cm = _make_mock_cm(memories=[], stats=EMPTY_STATS)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                memory_list = app.query_one("#memory-list", Static)
                text = str(memory_list.content or "")
                self.assertIn("No memories found", text)

        @patch("carrymem.tui.CarryMem")
        async def test_status_bar_updates_with_stats(self, MockCM):
            mock_cm = _make_mock_cm(stats=SAMPLE_STATS)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                status = app.query_one("#status-bar", Static)
                text = str(status.content or "")
                self.assertIn("Total:", text)
                self.assertIn("Showing:", text)
                self.assertIn("Namespace:", text)

        @patch("carrymem.tui.CarryMem")
        async def test_recall_called_with_correct_defaults(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                call_args = mock_cm.recall_memories.call_args
                kwargs = call_args.kwargs if call_args else {}
                self.assertEqual(kwargs.get("limit"), 50)

        @patch("carrymem.tui.CarryMem")
        async def test_memory_types_show_correct_icon(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                memory_list = app.query_one("#memory-list", Static)
                text = str(memory_list.content or "")
                self.assertIn(_TYPE_ICONS["user_preference"], text)
                self.assertIn(_TYPE_ICONS["fact_declaration"], text)
                self.assertIn(_TYPE_ICONS["correction"], text)
                self.assertIn(_TYPE_ICONS["decision"], text)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 5: Filter Functionality
    # ══════════════════════════════════════════════════════════════════

    class TestFilterFunctionality(unittest.TestCase):
        """Test filter switching via keyboard shortcuts."""

        @patch("carrymem.tui.CarryMem")
        async def test_filter_default_is_all(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                self.assertEqual(app.current_filter, "")

        @patch("carrymem.tui.CarryMem")
        async def test_key_2_sets_preference_filter(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("2")
                await pilot.pause()
                self.assertEqual(app.current_filter, "user_preference")
                mock_cm.recall_memories.assert_called()
                # Verify filters dict includes type
                call_kwargs = mock_cm.recall_memories.call_args.kwargs
                self.assertEqual(call_kwargs.get("filters", {}).get("type"), "user_preference")

        @patch("carrymem.tui.CarryMem")
        async def test_key_3_sets_fact_filter(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("3")
                await pilot.pause()
                self.assertEqual(app.current_filter, "fact_declaration")

        @patch("carrymem.tui.CarryMem")
        async def test_key_4_sets_correction_filter(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("4")
                await pilot.pause()
                self.assertEqual(app.current_filter, "correction")

        @patch("carrymem.tui.CarryMem")
        async def test_key_5_sets_decision_filter(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("5")
                await pilot.pause()
                self.assertEqual(app.current_filter, "decision")

        @patch("carrymem.tui.CarryMem")
        async def test_key_1_resets_to_all(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("3")  # set a filter first
                await pilot.press("1")  # reset to all
                await pilot.pause()
                self.assertEqual(app.current_filter, "")

        @patch("carrymem.tui.CarryMem")
        async def test_switching_filters_reloads_data(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                initial_call_count = mock_cm.recall_memories.call_count
                await pilot.press("2")
                await pilot.pause()
                await pilot.press("3")
                await pilot.pause()
                self.assertGreater(mock_cm.recall_memories.call_count, initial_call_count)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 6: Search Functionality
    # ══════════════════════════════════════════════════════════════════

    class TestSearchFunctionality(unittest.TestCase):
        """Test search via keyboard shortcuts and input submission."""

        @patch("carrymem.tui.CarryMem")
        async def test_slash_focuses_search(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                search_input = app.query_one("#search-input", Input)
                # Initially not focused
                await pilot.press("/")
                self.assertTrue(search_input.has_focus)

        @patch("carrymem.tui.CarryMem")
        async def test_s_focuses_search(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                search_input = app.query_one("#search-input", Input)
                await pilot.press("s")
                self.assertTrue(search_input.has_focus)

        @patch("carrymem.tui.CarryMem")
        async def test_search_submit_triggers_reload(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                search_input = app.query_one("#search-input", Input)
                await pilot.click(search_input)
                await pilot.type("dark mode")
                await pilot.press("enter")
                await pilot.pause()
                # recall_memories should have been called with query
                call_kwargs = mock_cm.recall_memories.call_args.kwargs
                self.assertIn("dark mode", call_kwargs.get("query", ""))

        @patch("carrymem.tui.CarryMem")
        async def test_empty_search_clears_query(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                search_input = app.query_one("#search-input", Input)
                await pilot.click(search_input)
                await pilot.type("something")
                search_input.value = ""
                await pilot.press("enter")
                await pilot.pause()
                call_kwargs = mock_cm.recall_memories.call_args.kwargs
                self.assertEqual(call_kwargs.get("query", ""), "")

    # ══════════════════════════════════════════════════════════════════
    # Test Group 7: Keyboard Navigation (j/k/Enter)
    # ══════════════════════════════════════════════════════════════════

    class TestKeyboardNavigation(unittest.TestCase):
        """Test j/k/up/down navigation and Enter for detail view."""

        @patch("carrymem.tui.CarryMem")
        async def test_j_moves_selection_down(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertEqual(app.selected_index, -1)
                await pilot.press("j")
                await pilot.pause()
                self.assertEqual(app.selected_index, 0)

        @patch("carrymem.tui.CarryMem")
        async def test_k_does_not_go_negative(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("k")
                await pilot.pause()
                self.assertEqual(app.selected_index, -1)

        @patch("carrymem.tui.CarryMem")
        async def test_down_arrow_works_like_j(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(app.selected_index, 0)

        @patch("carrymem.tui.CarryMem")
        async def test_up_arrow_works_like_k(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("j")
                await pilot.press("j")
                await pilot.pause()
                await pilot.press("up")
                await pilot.pause()
                self.assertEqual(app.selected_index, 0)

        @patch("carrymem.tui.CarryMem")
        async def test_selection_marker_applies_in_render(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                memory_list = app.query_one("#memory-list", Static)
                text_no_select = str(memory_list.content or "")
                self.assertNotIn(">", text_no_select.split("\n")[0])

                await pilot.press("j")
                await pilot.pause()
                text_with_select = str(memory_list.content or "")
                self.assertIn(">1.", text_with_select)

        @patch("carrymem.tui.CarryMem")
        async def test_selection_wraps_at_end(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                for _ in range(len(SAMPLE_MEMORIES) + 2):
                    await pilot.press("j")
                    await pilot.pause()
                # Should not exceed list length
                self.assertLessEqual(app.selected_index, len(SAMPLE_MEMORIES) - 1)

        @patch("carrymem.tui.CarryMem")
        async def test_enter_opens_detail_screen(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("j")
                await pilot.pause()
                initial_screen_count = len(app.screen_stack)
                await pilot.press("enter")
                await pilot.pause()
                # A detail screen should now be on top
                self.assertGreater(len(app.screen_stack), initial_screen_count)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 8: Help Screen
    # ══════════════════════════════════════════════════════════════════

    class TestHelpScreen(unittest.TestCase):
        """Test help screen display and dismissal."""

        @patch("carrymem.tui.CarryMem")
        async def test_question_mark_opens_help(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                initial_screens = len(app.screen_stack)
                await pilot.press("?")
                await pilot.pause()
                self.assertGreater(len(app.screen_stack), initial_screens)

        @patch("carrymem.tui.CarryMem")
        async def test_help_screen_contains_shortcuts(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("?")
                await pilot.pause()
                help_screen = app.screen
                self.assertIsNotNone(help_screen)
                statics = help_screen.query(Static)
                texts = [str(s.content or "") for s in statics]
                combined = "\n".join(texts)
                self.assertIn("Keyboard Shortcuts", combined)
                self.assertIn("Search", combined)
                self.assertIn("Quit", combined)

        @patch("carrymem.tui.CarryMem")
        async def test_help_dismissed_by_escape(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("?")
                await pilot.pause()
                screens_before = len(app.screen_stack)
                await pilot.press("escape")
                await pilot.pause()
                self.assertLess(len(app.screen_stack), screens_before)

        @patch("carrymem.tui.CarryMem")
        async def test_help_dismissed_by_q(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("?")
                await pilot.pause()
                screens_before = len(app.screen_stack)
                await pilot.press("q")
                await pilot.pause()
                self.assertLess(len(app.screen_stack), screens_before)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 9: Memory Detail Screen
    # ══════════════════════════════════════════════════════════════════

    class TestMemoryDetailScreen(unittest.TestCase):
        """Test memory detail overlay screen."""

        def test_detail_screen_accepts_memory_dict(self):
            screen = MemoryDetailScreen(SAMPLE_MEMORIES[0])
            self.assertEqual(screen.memory["type"], "user_preference")

        def test_detail_screen_compose_yields_widgets(self):
            screen = MemoryDetailScreen(SAMPLE_MEMORIES[0])
            widgets = list(screen.compose())
            self.assertGreater(len(widgets), 0)

        def test_detail_screen_shows_content(self):
            screen = MemoryDetailScreen(SAMPLE_MEMORIES[0])
            widgets = list(screen.compose())
            # Verify the screen was constructed with correct memory data
            self.assertEqual(screen.memory["content"], "I prefer dark mode in IDEs")
            # Check that detail-content widget exists
            self.assertTrue(any(w.id == "detail-content" for w in widgets))

        def test_detail_screen_shows_confidence_and_importance(self):
            screen = MemoryDetailScreen(SAMPLE_MEMORIES[0])
            # Verify memory data is correctly stored
            self.assertEqual(screen.memory["confidence"], 0.95)
            self.assertEqual(screen.memory["importance_score"], 8.5)
            # Verify compose yields detail-meta1 widget
            widgets = list(screen.compose())
            self.assertTrue(any(w.id == "detail-meta1" for w in widgets))

        @patch("carrymem.tui.CarryMem")
        async def test_detail_screen_pushed_from_app(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("j")
                await pilot.press("enter")
                await pilot.pause()
                current_screen = app.screen
                self.assertIsInstance(current_screen, MemoryDetailScreen)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 10: Stats Panel
    # ══════════════════════════════════════════════════════════════════

    class TestStatsPanel(unittest.TestCase):
        """Test the statistics sidebar panel."""

        def test_update_stats_populates_panel(self):
            panel = StatsPanel()
            panel.update_stats(SAMPLE_STATS, 4, "")
            text = str(panel.content or "")
            self.assertIn("Statistics", text)
            self.assertIn("Total:", text)
            self.assertIn("42", text)

        def test_update_stats_shows_by_type_breakdown(self):
            panel = StatsPanel()
            panel.update_stats(SAMPLE_STATS, 4, "")
            text = str(panel.content or "")
            # Labels are truncated to 10 chars in the panel
            self.assertIn("Preference", text)  # truncated from "Preferences"
            self.assertIn("Facts", text)

        def test_update_stats_handles_empty_stats(self):
            panel = StatsPanel()
            panel.update_stats(EMPTY_STATS, 0, "")
            text = str(panel.content or "")
            self.assertIn("Total:", text)
            self.assertIn("0", text)

        def test_update_stats_shows_filter_label(self):
            panel = StatsPanel()
            panel.update_stats(SAMPLE_STATS, 2, "user_preference")
            text = str(panel.content or "")
            self.assertIn("user_preference", text)

        def test_update_stats_limits_type_display(self):
            """Should only show top 5 types."""
            many_types = {f"type_{i}": i for i in range(10)}
            stats = {"total_count": 55, "by_type": many_types}
            panel = StatsPanel()
            panel.update_stats(stats, 55, "")
            text = str(panel.content or "")
            # Count lines that contain icon+label patterns (type entries)
            type_entries = text.count("\u2502")
            # Should have header + separator + total + showing + filter + blank + up to 5 types
            self.assertLessEqual(type_entries, 12)  # reasonable upper bound

    # ══════════════════════════════════════════════════════════════════
    # Test Group 11: Add Memory Mode
    # ══════════════════════════════════════════════════════════════════

    class TestAddMemoryMode(unittest.TestCase):
        """Test add-memory workflow via 'a' key."""

        @patch("carrymem.tui.CarryMem")
        async def test_a_key_enters_add_mode(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                self.assertFalse(app._add_mode)
                await pilot.press("a")
                await pilot.pause()
                self.assertTrue(app._add_mode)

        @patch("carrymem.tui.CarryMem")
        async def test_add_mode_changes_placeholder(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("a")
                await pilot.pause()
                search_input = app.query_one("#search-input", Input)
                self.assertIn("Type memory content", search_input.placeholder)

        @patch("carrymem.tui.CarryMem")
        async def test_add_mode_submit_calls_declare(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("a")
                await pilot.pause()
                search_input = app.query_one("#search-input", Input)
                await pilot.type("New preference about tabs")
                await pilot.press("enter")
                await pilot.pause()
                mock_cm.declare.assert_called_once_with("New preference about tabs")

        @patch("carrymem.tui.CarryMem")
        async def test_add_mode_cancelled_by_escape(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("a")
                await pilot.pause()
                self.assertTrue(app._add_mode)
                await pilot.press("escape")
                await pilot.pause()
                self.assertFalse(app._add_mode)

        @patch("carrymem.tui.CarryMem")
        async def test_add_mode_empty_submit_exits_without_declare(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("a")
                await pilot.pause()
                await pilot.press("enter")  # submit empty
                await pilot.pause()
                mock_cm.declare.assert_not_called()

    # ══════════════════════════════════════════════════════════════════
    # Test Group 12: Refresh Action
    # ══════════════════════════════════════════════════════════════════

    class TestRefreshAction(unittest.TestCase):
        """Test refresh action via 'r' key."""

        @patch("carrymem.tui.CarryMem")
        async def test_r_key_triggers_refresh(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                initial_calls = mock_cm.recall_memories.call_count
                await pilot.press("r")
                await pilot.pause()
                self.assertGreater(mock_cm.recall_memories.call_count, initial_calls)

        @patch("carrymem.tui.CarryMem")
        async def test_refresh_updates_status_message(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("r")
                await pilot.pause()
                status = app.query_one("#status-bar", Static)
                text = str(status.content or "")
                self.assertIn("Refreshed", text)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 13: Sidebar Active State
    # ══════════════════════════════════════════════════════════════════

    class TestSidebarActiveState(unittest.TestCase):
        """Test that sidebar filter items highlight correctly."""

        @patch("carrymem.tui.CarryMem")
        async def test_all_filter_active_by_default(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                filter_all = app.query_one("#filter-all", Static)
                self.assertIn("active", filter_all.classes)

        @patch("carrymem.tui.CarryMem")
        async def test_preference_filter_active_after_key_2(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("2")
                await pilot.pause()
                filter_prefs = app.query_one("#filter-prefs", Static)
                self.assertIn("active", filter_prefs.classes)
                filter_all = app.query_one("#filter-all", Static)
                self.assertNotIn("active", filter_all.classes)

    # ══════════════════════════════════════════════════════════════════
    # Test Group 14: Error Handling
    # ══════════════════════════════════════════════════════════════════

    class TestErrorHandling(unittest.TestCase):
        """Test graceful error handling."""

        @patch("carrymem.tui.CarryMem")
        async def test_graceful_on_load_error(self, MockCM):
            mock_cm = MagicMock()
            mock_cm.recall_memories.side_effect = Exception("DB connection failed")
            mock_cm.close = MagicMock()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                memory_list = app.query_one("#memory-list", Static)
                text = str(memory_list.content or "")
                self.assertIn("Error loading memories", text)

        @patch("carrymem.tui.CarryMem")
        async def test_graceful_on_get_stats_error(self, MockCM):
            mock_cm = MagicMock()
            mock_cm.recall_memories.return_value = []
            mock_cm.get_stats.side_effect = Exception("Stats error")
            mock_cm.close = MagicMock()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                # Should not crash; status bar may show default value

    # ══════════════════════════════════════════════════════════════════
    # Test Group 15: run_tui Entry Point
    # ══════════════════════════════════════════════════════════════════

    class TestRunTuiEntry(unittest.TestCase):
        """Test the run_tui() entry point function."""

        @patch("carrymem.tui.CarryMemTUI")
        def test_run_tui_creates_app_instance(self, MockApp):
            run_tui()
            MockApp.assert_called_once()

        @patch("carrymem.tui.CarryMemTUI")
        def test_run_tui_passes_db_path(self, MockApp):
            run_tui(db_path="/tmp/test.db")
            MockApp.assert_called_once_with(db_path="/tmp/test.db", namespace="default")

        @patch("carrymem.tui.CarryMemTUI")
        def test_run_tui_passes_namespace(self, MockApp):
            run_tui(namespace="test_ns")
            MockApp.assert_called_once_with(db_path=None, namespace="test_ns")

    # ══════════════════════════════════════════════════════════════════
    # Test Group 16: Reactive Variables
    # ══════════════════════════════════════════════════════════════════

    class TestReactiveVariables(unittest.TestCase):
        """Test reactive variable initialization and behavior."""

        @patch("carrymem.tui.CarryMem")
        async def test_initial_reactive_values(self, MockCM):
            mock_cm = _make_mock_cm()
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                self.assertEqual(app.current_filter, "")
                self.assertEqual(app.search_query, "")
                self.assertEqual(app.selected_index, -1)

        @patch("carrymem.tui.CarryMem")
        async def test_selected_index_resets_on_filter_change(self, MockCM):
            mock_cm = _make_mock_cm(memories=SAMPLE_MEMORIES)
            MockCM.return_value = mock_cm

            app = CarryMemTUI()
            async with app.run_test() as pilot:
                await pilot.press("j")
                await pilot.press("j")
                await pilot.pause()
                self.assertEqual(app.selected_index, 1)
                await pilot.press("2")  # change filter
                await pilot.pause()
                self.assertEqual(app.selected_index, -1)
