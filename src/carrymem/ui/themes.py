"""Theme system for CarryMem TUI — pluggable color palettes."""

from typing import Dict, Protocol


class Theme(Protocol):
    """Theme protocol — any object with name + colors dict."""

    name: str
    colors: Dict[str, str]


class MorandiDarkTheme:
    """Default dark Morandi theme — dusty blue-gray, low saturation."""

    name = "morandi-dark"
    colors = {
        "primary": "#8B9A9D",
        "secondary": "#A8AD9F",
        "accent": "#C4A882",
        "bg_dark": "#1E2024",
        "bg_surface": "#282A2F",
        "bg_elevated": "#33363D",
        "text_primary": "#D4D4D4",
        "text_secondary": "#9CA3AF",
        "text_muted": "#6B7280",
        "success": "#7D9B8C",
        "warning": "#C4A35A",
        "error": "#BC8F8F",
        "info": "#8FAAB8",
        "border": "#3D4047",
        "border_active": "#8B9A9D",
    }


class HighContrastTheme:
    """WCAG AAA high-contrast theme — black bg, white text, pure colors."""

    name = "high-contrast"
    colors = {
        "primary": "#FFFFFF",
        "secondary": "#CCCCCC",
        "accent": "#FFFF00",
        "bg_dark": "#000000",
        "bg_surface": "#0A0A0A",
        "bg_elevated": "#1A1A1A",
        "text_primary": "#FFFFFF",
        "text_secondary": "#E0E0E0",
        "text_muted": "#A0A0A0",
        "success": "#00FF00",
        "warning": "#FFFF00",
        "error": "#FF0000",
        "info": "#00FFFF",
        "border": "#FFFFFF",
        "border_active": "#FFFF00",
    }


class MorandiLightTheme:
    """Light Morandi theme — warm whites, soft browns. For daytime/bright terminals."""

    name = "morandi-light"
    colors = {
        "primary": "#6B7B7E",  # darker dusty blue-gray (for contrast on light bg)
        "secondary": "#8A8F7F",  # darker sage gray
        "accent": "#A08862",  # darker warm sand
        "bg_dark": "#F5F3EE",  # warm white
        "bg_surface": "#EBE8E1",  # light surface
        "bg_elevated": "#E0DDD5",  # elevated light
        "text_primary": "#3D3530",  # deep brown
        "text_secondary": "#6B5D52",
        "text_muted": "#9A8C81",
        "success": "#5D7B6C",  # darker muted green (contrast on light)
        "warning": "#A4833A",  # darker muted gold
        "error": "#9C6F6F",  # darker muted rose
        "info": "#6F8A98",  # darker muted blue
        "border": "#D4CFC5",
        "border_active": "#6B7B7E",
    }


# Theme registry
_THEMES: Dict[str, Theme] = {
    "morandi-dark": MorandiDarkTheme(),
    "morandi-light": MorandiLightTheme(),
    "high-contrast": HighContrastTheme(),
}


def get_theme(name: str = "morandi-dark") -> Theme:
    """Get theme by name. Falls back to MorandiDarkTheme."""
    return _THEMES.get(name, MorandiDarkTheme())


def list_themes() -> list:
    """List available theme names."""
    return list(_THEMES.keys())


def register_theme(name: str, theme: Theme) -> None:
    """Register a custom theme."""
    _THEMES[name] = theme
