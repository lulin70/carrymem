"""Tests for the CarryMem theme system (P1-A1).

Validates the pluggable Theme protocol, the built-in MorandiDarkTheme and
HighContrastTheme implementations, the theme registry helpers
(get_theme / list_themes / register_theme), and the WCAG AAA contrast claim
of the high-contrast palette.
"""

import os
import sys
import unittest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.ui.themes import (
    HighContrastTheme,
    MorandiDarkTheme,
    MorandiLightTheme,
    Theme,
    get_theme,
    list_themes,
    register_theme,
)

# ── Helpers ───────────────────────────────────────────────────────────

# All keys the Theme protocol guarantees. Any new theme MUST include every
# one of these so the TUI CSS f-string can interpolate them.
REQUIRED_COLOR_KEYS = [
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


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert #RRGGBB hex string to (r, g, b) ints (0-255)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Expected #RRGGBB, got {hex_color!r}")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.x relative luminance for an sRGB channel triple."""

    def _channel(c: int) -> float:
        c_lin = c / 255.0
        return c_lin / 12.92 if c_lin <= 0.03928 else ((c_lin + 0.055) / 1.055) ** 2.4

    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colors (range 1..21)."""
    la = _relative_luminance(*_hex_to_rgb(hex_a))
    lb = _relative_luminance(*_hex_to_rgb(hex_b))
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# ── Tests ─────────────────────────────────────────────────────────────


class TestMorandiDarkTheme(unittest.TestCase):
    """MorandiDarkTheme is the default palette and must be complete."""

    def test_theme_name(self):
        self.assertEqual(MorandiDarkTheme.name, "morandi-dark")

    def test_has_all_required_color_keys(self):
        colors = MorandiDarkTheme.colors
        self.assertEqual(len(colors), 15, "MorandiDarkTheme must expose exactly 15 color keys")
        for key in REQUIRED_COLOR_KEYS:
            self.assertIn(key, colors, f"Missing required color key: {key}")

    def test_colors_are_hex_format(self):
        for name, color in MorandiDarkTheme.colors.items():
            self.assertTrue(color.startswith("#"), f"{name}={color!r} must start with #")
            self.assertEqual(len(color), 7, f"{name}={color!r} must be #RRGGBB format")

    def test_does_not_use_harsh_green(self):
        """Morandi palette must NOT contain bright #00FF00 green (low-saturation aesthetic)."""
        harsh_greens = {"#00ff00", "#00ff00".lower()}
        for name, color in MorandiDarkTheme.colors.items():
            self.assertNotIn(color.lower(), harsh_greens, f"{name}={color} is a harsh green")


class TestHighContrastTheme(unittest.TestCase):
    """HighContrastTheme targets WCAG AAA contrast (≥7:1)."""

    def test_theme_name(self):
        self.assertEqual(HighContrastTheme.name, "high-contrast")

    def test_has_all_required_color_keys(self):
        colors = HighContrastTheme.colors
        self.assertEqual(len(colors), 15, "HighContrastTheme must expose exactly 15 color keys")
        for key in REQUIRED_COLOR_KEYS:
            self.assertIn(key, colors, f"Missing required color key: {key}")

    def test_colors_are_hex_format(self):
        for name, color in HighContrastTheme.colors.items():
            self.assertTrue(color.startswith("#"), f"{name}={color!r} must start with #")
            self.assertEqual(len(color), 7, f"{name}={color!r} must be #RRGGBB format")

    def test_black_background(self):
        """HighContrastTheme must use pure black background for maximum contrast."""
        self.assertEqual(HighContrastTheme.colors["bg_dark"].lower(), "#000000")

    def test_white_primary_text(self):
        """HighContrastTheme primary text must be pure white."""
        self.assertEqual(HighContrastTheme.colors["text_primary"].lower(), "#ffffff")

    def test_text_primary_on_bg_dark_meets_wcag_aaa(self):
        """text_primary on bg_dark must meet WCAG AAA (≥7:1) — black/white is 21:1."""
        ratio = _contrast_ratio(
            HighContrastTheme.colors["text_primary"],
            HighContrastTheme.colors["bg_dark"],
        )
        self.assertGreaterEqual(
            ratio,
            7.0,
            f"text_primary on bg_dark ratio={ratio:.2f}:1, expected ≥7:1 (WCAG AAA)",
        )

    def test_black_vs_white_is_21_to_1(self):
        """Sanity check: pure black vs pure white must be exactly 21:1 (max contrast)."""
        ratio = _contrast_ratio("#FFFFFF", "#000000")
        self.assertAlmostEqual(ratio, 21.0, places=2, msg="Black vs white must be 21:1")

    def test_error_color_meets_aa_on_bg(self):
        """error (#FF0000) on bg_dark (#000000) must meet WCAG AA (≥4.5:1)."""
        ratio = _contrast_ratio(
            HighContrastTheme.colors["error"],
            HighContrastTheme.colors["bg_dark"],
        )
        self.assertGreaterEqual(
            ratio,
            4.5,
            f"error on bg_dark ratio={ratio:.2f}:1, expected ≥4.5:1 (WCAG AA)",
        )


class TestThemeRegistry(unittest.TestCase):
    """Theme registry helpers: get_theme, list_themes, register_theme."""

    def test_get_theme_morandi_dark(self):
        theme = get_theme("morandi-dark")
        self.assertEqual(theme.name, "morandi-dark")
        self.assertIsInstance(theme, MorandiDarkTheme)

    def test_get_theme_high_contrast(self):
        theme = get_theme("high-contrast")
        self.assertEqual(theme.name, "high-contrast")
        self.assertIsInstance(theme, HighContrastTheme)

    def test_get_theme_default(self):
        """get_theme() with no args returns the default MorandiDarkTheme."""
        theme = get_theme()
        self.assertEqual(theme.name, "morandi-dark")

    def test_get_theme_nonexistent_falls_back_to_morandi(self):
        """get_theme('nonexistent') must fall back to MorandiDarkTheme (not raise)."""
        theme = get_theme("nonexistent-theme-xyz")
        self.assertEqual(theme.name, "morandi-dark")
        self.assertIsInstance(theme, MorandiDarkTheme)

    def test_list_themes_contains_both(self):
        names = list_themes()
        self.assertIn("morandi-dark", names)
        self.assertIn("high-contrast", names)
        self.assertGreaterEqual(len(names), 2)

    def test_register_theme_adds_new_theme(self):
        """register_theme() must add a new theme to the registry."""

        class CustomTheme:
            name = "custom-test-theme"
            colors = {key: "#123456" for key in REQUIRED_COLOR_KEYS}

        try:
            register_theme("custom-test-theme", CustomTheme())
            self.assertIn("custom-test-theme", list_themes())
            fetched = get_theme("custom-test-theme")
            self.assertEqual(fetched.name, "custom-test-theme")
            self.assertEqual(fetched.colors["primary"], "#123456")
        finally:
            # Clean up registry to avoid leaking state between tests
            from carrymem.ui import themes as themes_mod

            themes_mod._THEMES.pop("custom-test-theme", None)

    def test_register_theme_overwrites_existing(self):
        """register_theme() with an existing name should overwrite it."""

        class OverrideTheme:
            name = "morandi-dark-override"
            colors = {key: "#ABCDEF" for key in REQUIRED_COLOR_KEYS}

        try:
            register_theme("morandi-dark-override", OverrideTheme())
            first = get_theme("morandi-dark-override")

            class UpdatedOverride:
                name = "morandi-dark-override"
                colors = {key: "#FEDCBA" for key in REQUIRED_COLOR_KEYS}

            register_theme("morandi-dark-override", UpdatedOverride())
            second = get_theme("morandi-dark-override")
            self.assertNotEqual(first.colors["primary"], second.colors["primary"])
        finally:
            from carrymem.ui import themes as themes_mod

            themes_mod._THEMES.pop("morandi-dark-override", None)


class TestThemeProtocol(unittest.TestCase):
    """Theme protocol structural conformance."""

    def test_morandi_dark_satisfies_protocol(self):
        """MorandiDarkTheme must satisfy the Theme protocol (name + colors)."""
        theme = MorandiDarkTheme()
        self.assertTrue(hasattr(theme, "name"))
        self.assertTrue(hasattr(theme, "colors"))
        self.assertIsInstance(theme.name, str)
        self.assertIsInstance(theme.colors, dict)

    def test_high_contrast_satisfies_protocol(self):
        """HighContrastTheme must satisfy the Theme protocol (name + colors)."""
        theme = HighContrastTheme()
        self.assertTrue(hasattr(theme, "name"))
        self.assertTrue(hasattr(theme, "colors"))
        self.assertIsInstance(theme.name, str)
        self.assertIsInstance(theme.colors, dict)

    def test_protocol_attributes_exist(self):
        """The Theme protocol must declare `name` and `colors`."""
        self.assertTrue(hasattr(Theme, "_is_protocol") or hasattr(Theme, "_is_runtime_protocol"))
        # Protocol structural hints
        self.assertIn("name", Theme.__annotations__)
        self.assertIn("colors", Theme.__annotations__)


class TestTuiIntegration(unittest.TestCase):
    """Verify tui.py module-level _MORANDI is sourced from MorandiDarkTheme.

    This guards the backward-compat bridge: any code that still imports
    `_MORANDI` from carrymem.tui must see exactly the MorandiDarkTheme palette.
    """

    def test_tui_module_morandi_matches_theme(self):
        from carrymem.tui import _MORANDI

        self.assertEqual(_MORANDI, MorandiDarkTheme.colors)
        for key in REQUIRED_COLOR_KEYS:
            self.assertIn(key, _MORANDI)


# ════════════════════════════════════════════════════════════════════
# P1-C3 (high-contrast mode) + P2-U2 (light Morandi theme) additions
# ════════════════════════════════════════════════════════════════════


class TestMorandiLightTheme(unittest.TestCase):
    """MorandiLightTheme is the daytime/bright-terminal palette (P2-U2)."""

    def test_theme_name(self):
        self.assertEqual(MorandiLightTheme.name, "morandi-light")

    def test_has_all_required_color_keys(self):
        colors = MorandiLightTheme.colors
        self.assertEqual(len(colors), 15, "MorandiLightTheme must expose exactly 15 color keys")
        for key in REQUIRED_COLOR_KEYS:
            self.assertIn(key, colors, f"Missing required color key: {key}")

    def test_colors_are_hex_format(self):
        for name, color in MorandiLightTheme.colors.items():
            self.assertTrue(color.startswith("#"), f"{name}={color!r} must start with #")
            self.assertEqual(len(color), 7, f"{name}={color!r} must be #RRGGBB format")

    def test_uses_light_background(self):
        """Light theme must use a warm-white background (not dark)."""
        bg = MorandiLightTheme.colors["bg_dark"].lstrip("#")
        r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
        # Light bg should have high luminance (all channels > 200)
        self.assertGreater(r, 200, "Light theme bg_dark R channel should be > 200")
        self.assertGreater(g, 200, "Light theme bg_dark G channel should be > 200")
        self.assertGreater(b, 200, "Light theme bg_dark B channel should be > 200")

    def test_text_primary_is_dark(self):
        """Light theme must use dark text (deep brown) for contrast on light bg."""
        text = MorandiLightTheme.colors["text_primary"].lstrip("#")
        r, g, b = int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
        # Dark text should have low luminance (all channels < 100)
        self.assertLess(r, 100, "Light theme text_primary R channel should be < 100")
        self.assertLess(g, 100, "Light theme text_primary G channel should be < 100")
        self.assertLess(b, 100, "Light theme text_primary B channel should be < 100")

    def test_text_primary_on_bg_dark_meets_wcag_aa(self):
        """text_primary (#3D3530) on bg_dark (#F5F3EE) must meet WCAG AA (≥4.5:1)."""
        ratio = _contrast_ratio(
            MorandiLightTheme.colors["text_primary"],
            MorandiLightTheme.colors["bg_dark"],
        )
        self.assertGreaterEqual(
            ratio,
            4.5,
            f"text_primary on bg_dark ratio={ratio:.2f}:1, expected ≥4.5:1 (WCAG AA)",
        )

    def test_text_primary_on_bg_dark_meets_wcag_aaa(self):
        """text_primary on bg_dark should also meet WCAG AAA (≥7:1) — deep brown on warm white."""
        ratio = _contrast_ratio(
            MorandiLightTheme.colors["text_primary"],
            MorandiLightTheme.colors["bg_dark"],
        )
        self.assertGreaterEqual(
            ratio,
            7.0,
            f"text_primary on bg_dark ratio={ratio:.2f}:1, expected ≥7:1 (WCAG AAA)",
        )

    def test_satisfies_theme_protocol(self):
        """MorandiLightTheme must satisfy the Theme protocol (name + colors)."""
        theme = MorandiLightTheme()
        self.assertTrue(hasattr(theme, "name"))
        self.assertTrue(hasattr(theme, "colors"))
        self.assertIsInstance(theme.name, str)
        self.assertIsInstance(theme.colors, dict)


class TestMorandiLightThemeRegistry(unittest.TestCase):
    """Theme registry helpers: get_theme, list_themes for morandi-light (P2-U2)."""

    def test_get_theme_morandi_light(self):
        theme = get_theme("morandi-light")
        self.assertEqual(theme.name, "morandi-light")
        self.assertIsInstance(theme, MorandiLightTheme)

    def test_list_themes_returns_three(self):
        """P1-C3 + P2-U2: list_themes() must return exactly 3 themes."""
        names = list_themes()
        self.assertEqual(len(names), 3, f"Expected 3 themes, got {len(names)}: {names}")
        self.assertIn("morandi-dark", names)
        self.assertIn("morandi-light", names)
        self.assertIn("high-contrast", names)


class TestHighContrastCliFlag(unittest.TestCase):
    """Test the --high-contrast and --theme CLI flag wiring in cmd_tui (P1-C3).

    These tests mock CarryMemTUI so the TUI is never actually launched —
    they only verify that the CLI flags correctly select the theme_name
    passed to CarryMemTUI(theme_name=...).
    """

    def setUp(self):
        # The CLI flag wiring tests require textual to be installed because
        # cmd_tui imports CarryMemTUI from carrymem.tui (which is only
        # defined when textual is available). Skip gracefully otherwise.
        from carrymem.tui import HAS_TEXTUAL

        if not HAS_TEXTUAL:
            self.skipTest("Textual is not installed; skipping CLI flag wiring tests")

    def _run_cmd_tui_with_mock(self, args):
        """Helper: run cmd_tui with CarryMemTUI mocked, return the Mock."""
        from unittest.mock import patch

        with patch("carrymem.tui.HAS_TEXTUAL", True), patch("carrymem.tui.CarryMemTUI") as MockTUI:
            from carrymem.cli._mcp import cmd_tui

            cmd_tui(args)
            return MockTUI

    def test_high_contrast_flag_sets_theme(self):
        """--high-contrast flag should set theme_name to 'high-contrast'."""
        MockTUI = self._run_cmd_tui_with_mock(["--high-contrast"])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "high-contrast")
        # Verify app.run() was called
        MockTUI.return_value.run.assert_called_once()

    def test_theme_flag_morandi_light(self):
        """--theme morandi-light should set theme_name to 'morandi-light'."""
        MockTUI = self._run_cmd_tui_with_mock(["--theme", "morandi-light"])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "morandi-light")

    def test_theme_flag_high_contrast(self):
        """--theme high-contrast should set theme_name to 'high-contrast'."""
        MockTUI = self._run_cmd_tui_with_mock(["--theme", "high-contrast"])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "high-contrast")

    def test_theme_flag_morandi_dark(self):
        """--theme morandi-dark should set theme_name to 'morandi-dark'."""
        MockTUI = self._run_cmd_tui_with_mock(["--theme", "morandi-dark"])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "morandi-dark")

    def test_default_theme_is_morandi_dark(self):
        """Without --theme or --high-contrast, theme_name should default to 'morandi-dark'."""
        MockTUI = self._run_cmd_tui_with_mock([])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "morandi-dark")

    def test_high_contrast_flag_overrides_theme_flag(self):
        """--high-contrast should win over --theme when both are given."""
        MockTUI = self._run_cmd_tui_with_mock(["--theme", "morandi-light", "--high-contrast"])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "high-contrast")

    def test_namespace_still_passed_with_theme(self):
        """--namespace should still be propagated alongside --theme."""
        MockTUI = self._run_cmd_tui_with_mock(["--theme", "morandi-light", "--namespace", "work"])
        MockTUI.assert_called_once()
        kwargs = MockTUI.call_args.kwargs
        self.assertEqual(kwargs.get("theme_name"), "morandi-light")
        self.assertEqual(kwargs.get("namespace"), "work")


if __name__ == "__main__":
    unittest.main()
