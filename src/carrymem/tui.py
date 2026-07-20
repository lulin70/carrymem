"""CarryMem TUI — Terminal User Interface for memory management.

Built with Textual. Launch with: carrymem tui

Design: Morandi color palette for a calm, professional aesthetic.
"""

from __future__ import annotations

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Header, Input, Static

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


if not HAS_TEXTUAL:

    def run_tui(
        db_path: "Optional[str]" = None,
        namespace: str = "default",
        theme_name: str = "morandi-dark",
    ) -> None:
        """Print an install hint when Textual is unavailable.

        Signature mirrors the HAS_TEXTUAL branch so mypy treats both
        conditional definitions as compatible. Arguments are accepted
        but ignored — Textual is the hard dependency for the real TUI.
        """
        _ = (db_path, namespace, theme_name)  # explicitly ignore params
        print("  Textual is not installed.")
        print("  Install with: pip install textual")
        print("  Then run: carrymem tui")

else:
    import sqlite3
    from datetime import datetime, timedelta, timezone
    from typing import Any, Callable, Dict, List, Mapping, Optional

    from carrymem import CarryMem
    from carrymem.constants import DB_PATH
    from carrymem.errors import CarryMemError
    from carrymem.ui.themes import MorandiDarkTheme, get_theme, list_themes

    # P1-P1 first-run onboarding (guarded import for safety)
    try:
        from carrymem.ui.onboarding import HAS_TEXTUAL as _ONBOARDING_AVAILABLE
        from carrymem.ui.onboarding import OnboardingScreen
    except ImportError:  # pragma: no cover — onboarding module is optional
        OnboardingScreen = None  # type: ignore[assignment,misc]
        _ONBOARDING_AVAILABLE = False

    # P2-P4 ASCII dashboard rendering (pure functions, no textual dep)
    render_full_dashboard: Optional[Callable[..., str]]
    try:
        from carrymem.ui.dashboard import render_full_dashboard
    except ImportError:  # pragma: no cover — dashboard module is optional
        render_full_dashboard = None

    _DEFAULT_DB = DB_PATH

    # Initial render limit for lazy loading (P2-P5 virtual scrolling).
    # When the memory list exceeds this size, only the first slice is
    # rendered and a "Load more..." line is appended; pressing j/down
    # past the last visible item expands the slice by another batch.
    MAX_VISIBLE_MEMORIES = 100

    # ── Morandi Color Palette ──────────────────────────────────────
    # Soft, muted tones inspired by Italian painter Giorgio Morandi.
    # All colors are low-saturation, high-readability.
    # Sourced from the pluggable Theme system (P1-A1); kept as a module-level
    # alias for backward compatibility with module-level screens (MemoryDetailScreen,
    # ErrorDisplay, etc.) that still reference `_MORANDI` directly.

    _DEFAULT_THEME = MorandiDarkTheme()
    _MORANDI = _DEFAULT_THEME.colors

    _TYPE_ICONS = {
        "user_preference": "\u25c6",  # ◆ diamond (preferences)
        "fact_declaration": "\u25c7",  # ◇ hollow diamond (facts)
        "correction": "\u2699",  # ⚙ gear (corrections)
        "decision": "\u25c9",  # ◉ fisheye (decisions)
        "task_pattern": "\u21bb",  # ↻ clockwise arrow (patterns)
        "contextual_observation": "\u2299",  # ⊙ circled dot (observations)
        "knowledge": "\u25a4",  # ▤ square with horizontal fill (knowledge)
        "unknown": "?",  # plain question mark (unknown)
    }

    _TYPE_LABELS = {
        "user_preference": "Preferences",
        "fact_declaration": "Facts",
        "correction": "Corrections",
        "decision": "Decisions",
        "task_pattern": "Patterns",
        "contextual_observation": "Observations",
        "knowledge": "Knowledge",
        "unknown": "Unknown",
    }

    _FILTER_MAP = {
        "all": "",
        "preferences": "user_preference",
        "facts": "fact_declaration",
        "corrections": "correction",
        "decisions": "decision",
        "patterns": "task_pattern",
        "observations": "contextual_observation",
        "knowledge": "knowledge",
    }

    # ── Memory Detail Screen ───────────────────────────────────────

    class MemoryDetailScreen(ModalScreen[None]):
        """Overlay screen showing full details of a selected memory."""

        BINDINGS = [
            Binding("escape", "dismiss", "Close"),
            Binding("q", "dismiss", "Close"),
        ]

        def __init__(self, memory: Dict[str, Any]):
            super().__init__()
            self.memory = memory

        def compose(self) -> ComposeResult:
            """Render the memory detail overlay widgets."""
            m = self.memory
            mtype = m.get("type", "unknown")
            icon = _TYPE_ICONS.get(mtype, "?")
            content = m.get("content", "")
            confidence = m.get("confidence", 0)
            importance = m.get("importance_score", 0)
            key = m.get("storage_key", "")
            created = m.get("created_at", "")
            updated = m.get("updated_at", "")
            namespace = m.get("namespace", "")

            yield Static(f"  {icon}  {_TYPE_LABELS.get(mtype, 'Memory Detail')}", id="detail-title")
            yield Static("", id="detail-sep")
            yield Static(f"  Content:\n{content}", id="detail-content")
            yield Static("", id="detail-sep2")
            yield Static(
                f"  Confidence: {confidence:.0%}  |  " f"Importance: {importance:.2f}",
                id="detail-meta1",
            )
            yield Static(
                f"  Key: {key}\n" f"  Namespace: {namespace}\n" f"  Created: {created}\n" f"  Updated: {updated}",
                id="detail-meta2",
            )
            yield Static("  \u2014 Press Esc or q to close \u2014", id="detail-hint")

        CSS = f"""
        MemoryDetailScreen {{
            align: center middle;
            background: {_MORANDI['bg_dark']}99;
        }}

        #detail-title {{
            text-style: bold;
            color: {_MORANDI['accent']};
            width: 80%;
            padding: 1 0;
            text-align: center;
        }}

        #detail-sep, #detail-sep2 {{
            width: 80%;
            height: 1;
            border-bottom: solid {_MORANDI['border']};
            margin: 0 0 1 0;
        }}

        #detail-content {{
            width: 80%;
            padding: 1 2;
            color: {_MORANDI['text_primary']};
            text-style: italic;
            min-height: 6;
            max-height: 14;
            overflow-y: auto;
            border: round {_MORANDI['border']};
            background: {_MORANDI['bg_surface']};
        }}

        #detail-meta1 {{
            width: 80%;
            padding: 1 2;
            color: {_MORANDI['secondary']};
        }}

        #detail-meta2 {{
            width: 80%;
            padding: 1 2;
            color: {_MORANDI['text_muted']};
        }}

        #detail-hint {{
            width: 80%;
            padding: 1 0;
            text-align: center;
            color: {_MORANDI['text_muted']};
        }}
        """

    # ── Delete Confirmation Dialog ────────────────────────────────────

    class DeleteConfirmScreen(ModalScreen[bool]):
        """Modal dialog to confirm memory deletion."""

        BINDINGS = [
            Binding("y", "confirm_delete", "Yes"),
            Binding("n", "cancel_delete", "No"),
            Binding("escape", "cancel_delete", "No"),
        ]

        def __init__(self, memory: Dict[str, Any]):
            super().__init__()
            self.memory = memory

        def compose(self) -> ComposeResult:
            """Render the delete confirmation dialog widgets."""
            mtype = self.memory.get("type", "unknown")
            icon = _TYPE_ICONS.get(mtype, "?")
            content = self.memory.get("content", "")
            key = self.memory.get("storage_key", "")

            yield Static("  ⚠  Confirm Deletion", id="delete-title")
            yield Static("", id="delete-sep")
            yield Static(
                f"  {icon} [{mtype}] {content[:80]}",
                id="delete-content",
            )
            yield Static(f"  Key: {key}", id="delete-key")
            yield Static("", id="delete-sep2")
            yield Static(
                "  This action cannot be undone.\n"
                "  Press [bold]y[/bold] to delete, [bold]n[/bold] or [bold]Esc[/bold] to cancel.",
                id="delete-hint",
            )

        def action_confirm_delete(self) -> None:
            """Dismiss the dialog confirming deletion."""
            self.dismiss(True)

        def action_cancel_delete(self) -> None:
            """Dismiss the dialog cancelling deletion."""
            self.dismiss(False)

        CSS = f"""
        DeleteConfirmScreen {{
            align: center middle;
            background: {_MORANDI['bg_dark']}99;
        }}

        #delete-title {{
            text-style: bold;
            color: {_MORANDI['error']};
            width: 70%;
            padding: 1 0;
            text-align: center;
        }}

        #delete-sep, #delete-sep2 {{
            width: 70%;
            height: 1;
            border-bottom: solid {_MORANDI['border']};
            margin: 0 0 1 0;
        }}

        #delete-content {{
            width: 70%;
            padding: 1 2;
            color: {_MORANDI['text_primary']};
            max-height: 6;
            overflow-y: auto;
        }}

        #delete-key {{
            width: 70%;
            padding: 0 2;
            color: {_MORANDI['text_muted']};
        }}

        #delete-hint {{
            width: 70%;
            padding: 1 2;
            color: {_MORANDI['warning']};
            text-align: center;
        }}
        """

    # ── Edit Dialog ──────────────────────────────────────────────────

    class EditMemoryScreen(ModalScreen[Optional[str]]):
        """Modal dialog to edit memory content."""

        BINDINGS = [
            Binding("escape", "cancel_edit", "Cancel"),
        ]

        def __init__(self, memory: Dict[str, Any]):
            super().__init__()
            self.memory = memory

        def compose(self) -> ComposeResult:
            """Render the edit memory dialog widgets."""
            mtype = self.memory.get("type", "unknown")
            icon = _TYPE_ICONS.get(mtype, "?")
            content = self.memory.get("content", "")
            key = self.memory.get("storage_key", "")

            yield Static(f"  {icon}  Edit Memory", id="edit-title")
            yield Static("", id="edit-sep")
            yield Static(f"  Key: {key}", id="edit-key")
            yield Input(value=content, id="edit-input")
            yield Static(
                "  Press [bold]Enter[/bold] to save, [bold]Esc[/bold] to cancel.",
                id="edit-hint",
            )

        def on_mount(self) -> None:
            """Focus the edit input when the screen mounts."""
            try:
                edit_input = self.query_one("#edit-input", Input)
                edit_input.focus()
            except (AttributeError, ValueError):
                pass

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Save the edited content when Enter is pressed."""
            if event.input.id == "edit-input":
                new_content = event.value.strip()
                if new_content:
                    self.dismiss(new_content)
                else:
                    self.dismiss(None)

        def action_cancel_edit(self) -> None:
            """Dismiss the edit dialog without saving."""
            self.dismiss(None)

        CSS = f"""
        EditMemoryScreen {{
            align: center middle;
            background: {_MORANDI['bg_dark']}99;
        }}

        #edit-title {{
            text-style: bold;
            color: {_MORANDI['accent']};
            width: 70%;
            padding: 1 0;
            text-align: center;
        }}

        #edit-sep {{
            width: 70%;
            height: 1;
            border-bottom: solid {_MORANDI['border']};
            margin: 0 0 1 0;
        }}

        #edit-key {{
            width: 70%;
            padding: 0 2;
            color: {_MORANDI['text_muted']};
        }}

        #edit-input {{
            width: 70%;
            padding: 1 2;
        }}

        #edit-hint {{
            width: 70%;
            padding: 1 2;
            color: {_MORANDI['text_muted']};
            text-align: center;
        }}
        """

    # ── Help Screen ─────────────────────────────────────────────────

    class HelpScreen(ModalScreen[None]):
        """Keyboard shortcuts and usage help."""

        BINDINGS = [
            Binding("escape", "dismiss", "Close"),
            Binding("q", "dismiss", "Close"),
            Binding("?", "dismiss", "Close"),
        ]

        def compose(self) -> ComposeResult:
            """Render the keyboard shortcuts help screen."""
            lines = [
                ("  CarryMem TUI \u2014 Keyboard Shortcuts", "title"),
                ("", ""),
                ("  Navigation:", "section"),
                ("    / or s     Focus search bar", "item"),
                ("    Tab         Cycle focus between widgets", "item"),
                ("    Enter       View memory detail (when list focused)", "item"),
                ("    Esc         Close detail / cancel add mode", "item"),
                ("", ""),
                ("  Filters:", "section"),
                ("    1           Show all memories", "item"),
                ("    2           Show preferences only", "item"),
                ("    3           Show facts only", "item"),
                ("    4           Show corrections only", "item"),
                ("    5           Show decisions only", "item"),
                ("    0           Clear filter (show all)", "item"),
                ("", ""),
                ("  Actions:", "section"),
                ("    a           Add new memory", "item"),
                ("    r           Refresh memory list", "item"),
                ("    d           Delete selected", "item"),
                ("    e           Edit selected", "item"),
                ("    D           Show dashboard (ASCII charts)", "item"),
                ("", ""),
                ("  System:", "section"),
                ("    Ctrl+T      Cycle theme (dark / light / high-contrast)", "item"),
                ("    ?           Show this help screen", "item"),
                ("    q           Quit application", "item"),
                ("", ""),
                ("  \u2014 Press Esc, q, or ? to close \u2014", "hint"),
            ]
            for text, style in lines:
                yield Static(text, id=f"help-{style}" if style else "help-blank")

        CSS = f"""
        HelpScreen {{
            align: center middle;
            background: {_MORANDI['bg_dark']}99;
        }}

        #help-title {{
            text-style: bold;
            color: {_MORANDI['accent']};
            width: 70%;
            padding: 1 0;
            text-align: center;
        }}

        #help-section {{
            color: {_MORANDI['primary']};
            text-style: bold;
            width: 70%;
            padding: 1 0 0 0;
        }}

        #help-item {{
            color: {_MORANDI['text_primary']};
            width: 70%;
            padding: 0 2;
        }}

        #help-hint {{
            color: {_MORANDI['text_muted']};
            width: 70%;
            padding: 1 0;
            text-align: center;
        }}

        #help-blank {{
            height: 0;
        }}
        """

    # ── Dashboard Screen (P2-P4) ────────────────────────────────────

    class DashboardScreen(ModalScreen[None]):
        """Full-screen ASCII dashboard showing memory growth, type distribution, and health score.

        Rendered via :func:`carrymem.ui.dashboard.render_full_dashboard`.
        Press ``Esc`` or ``q`` to dismiss.
        """

        BINDINGS = [
            Binding("escape", "dismiss", "Close"),
            Binding("q", "dismiss", "Close"),
        ]

        def __init__(self, memories: List[Dict[str, Any]]):
            super().__init__()
            self.memories = memories

        def compose(self) -> ComposeResult:
            """Render the full ASCII dashboard as a single Static widget."""
            if render_full_dashboard is not None:
                try:
                    body = render_full_dashboard(self.memories)
                except Exception:  # NOTE: intentional — dashboard rendering must not crash the modal
                    body = "  Dashboard rendering failed."
            else:
                body = "  Dashboard module unavailable."
            yield Static(body, id="dashboard-body")
            yield Static("  \u2014 Press Esc or q to close \u2014", id="dashboard-hint")

        CSS = f"""
        DashboardScreen {{
            align: center middle;
            background: {_MORANDI['bg_dark']}99;
        }}

        #dashboard-body {{
            width: 85%;
            max-height: 85%;
            padding: 1 2;
            color: {_MORANDI['text_primary']};
            background: {_MORANDI['bg_surface']};
            border: round {_MORANDI['border_active']};
            overflow-y: auto;
        }}

        #dashboard-hint {{
            width: 85%;
            padding: 1 0;
            text-align: center;
            color: {_MORANDI['text_muted']};
        }}
        """

    # ── Statistics Panel ────────────────────────────────────────────

    class StatsPanel(Static):
        """Real-time statistics display in the sidebar."""

        def update_stats(self, stats: Mapping[str, Any], shown: int, filt: str) -> None:
            """Refresh the sidebar statistics display."""
            total = stats.get("total_count", 0)
            by_type = stats.get("by_type", {})
            lines = [
                "\u2502  Statistics",
                "\u2502  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
                f"\u2502  Total:   {total}",
                f"\u2502  Showing: {shown}",
                f"\u2502  Filter:  {filt or 'All'}",
                "\u2502",
            ]
            type_counts = sorted(by_type.items(), key=lambda x: -x[1]) if isinstance(by_type, dict) else []
            for t, c in type_counts[:5]:
                icon = _TYPE_ICONS.get(t, "?")
                # t is Any from by_type.items(); coerce to str for _TYPE_LABELS lookup
                t_str = t if isinstance(t, str) else str(t)
                label = _TYPE_LABELS.get(t_str, t_str)[:10]
                lines.append(f"\u2502  {icon} {label}: {c}")
            self.update("\n".join(lines))

    # ── Error Display Component ─────────────────────────────────────

    class ErrorDisplay(Static):
        """Red error prompt box with code, message, hint, and recovery actions."""

        BINDINGS = [
            Binding("r", "retry", "Retry"),
            Binding("i", "ignore", "Ignore"),
            Binding("h", "help", "Help"),
        ]

        def __init__(self, *args, **kwargs):
            """Initialize the error display with empty recovery callbacks."""
            super().__init__(*args, **kwargs)
            self._retry_callback = None
            self._help_url = None

        def show_error(self, exc: Exception, retry_callback=None, help_url=None) -> None:
            """Display an exception as a friendly error box.

            Optionally accepts a ``retry_callback`` (invoked by action_retry)
            and a ``help_url`` (opened by action_help). When supplied, the
            corresponding action hints are appended to the rendered box so
            the user knows which recovery keys are available.
            """
            # Store callbacks so action_retry / action_help can invoke them.
            self._retry_callback = retry_callback
            self._help_url = help_url

            if isinstance(exc, CarryMemError):
                code = exc.code
                message = exc.message
                hint = exc.hint
            else:
                friendly = CarryMemError.from_cause(exc)
                code = friendly.code
                message = friendly.message
                hint = friendly.hint

            lines = [f"  [{_MORANDI['error']} ERROR] {code}", f"  {message}"]
            if hint:
                lines.append(f"  Hint: {hint}")
            # Recovery action hints — [I] Ignore always available; [R]/[H]
            # only when the corresponding callback/URL was supplied.
            if retry_callback:
                lines.append("  [R] Retry")
            lines.append("  [I] Ignore")
            if help_url:
                lines.append("  [H] Help")
            self.update("\n".join(lines))
            self.add_class("error-visible")
            self.remove_class("error-hidden")

        def clear_error(self) -> None:
            """Hide the error box and clear its content."""
            self._retry_callback = None
            self._help_url = None
            self.update("")
            self.remove_class("error-visible")
            self.add_class("error-hidden")

        def action_retry(self) -> None:
            """Retry the failed operation by invoking the stored callback."""
            if self._retry_callback:
                self._retry_callback()
            self.clear_error()

        def action_ignore(self) -> None:
            """Dismiss the error without retrying."""
            self.clear_error()

        def action_help(self) -> None:
            """Open the help documentation URL in a browser if available."""
            if self._help_url:
                import webbrowser

                webbrowser.open(self._help_url)
            self.clear_error()

        CSS = f"""
        ErrorDisplay {{
            width: 100%;
            padding: 1 2;
            margin: 0 1;
            border: round {_MORANDI['error']};
            background: {_MORANDI['bg_surface']};
            color: {_MORANDI['error']};
            display: none;
        }}
        .error-visible {{
            display: block;
        }}
        .error-hidden {{
            display: none;
        }}
        """

    # ── Main TUI Application ───────────────────────────────────────

    def _build_app_css(colors: Dict[str, str]) -> str:
        """Build the CarryMemTUI stylesheet from a colors dict.

        Lets the main app CSS be regenerated with an arbitrary theme at
        instance time (P1-A1 theme abstraction), while preserving the
        exact CSS content the module shipped with previously.
        """
        return f"""
        /* ══════════════════════════════════════════════════════════
           CarryMorandi TUI — Morandi Color Scheme
           ══════════════════════════════════════════════════════════ */

        Screen {{
            layout: vertical;
            background: {colors['bg_dark']};
            color: {colors['text_primary']};
        }}

        /* ── Main Layout ─────────────────────────────────────── */

        #main-container {{
            layout: horizontal;
            height: 1fr;
        }}

        /* ── Sidebar ─────────────────────────────────────────── */

        #sidebar {{
            width: 32;
            border-right: solid {colors['border']};
            padding: 0 1;
            background: {colors['bg_surface']};
        }}

        #sidebar-title {{
            text-style: bold;
            color: {colors['accent']};
            padding: 1 0;
            margin-bottom: 1;
            border-bottom: solid {colors['border']};
        }}

        .sidebar-section {{
            color: {colors['primary']};
            text-style: bold;
            margin-top: 1;
            margin-bottom: 0;
            padding: 1 0 0 0;
        }}

        .sidebar-item {{
            padding: 0 1;
            color: {colors['text_secondary']};
        }}

        .sidebar-item:hover {{
            background: {colors['bg_elevated']};
            color: {colors['text_primary']};
        }}

        .sidebar-item.active {{
            background: {colors['primary'] + '33'};
            color: {colors['accent']};
            text-style: bold;
        }}

        .sidebar-item .key {{
            color: {colors['accent']};
            min-width: 3;
            text-style: bold;
        }}

        #stats-panel {{
            margin-top: 1;
            padding: 1 0;
            border-top: solid {colors['border']};
            color: {colors['text_muted']};
        }}

        /* ── Content Area ─────────────────────────────────────── */

        #content {{
            width: 1fr;
            padding: 0 1;
            overflow-y: auto;
            background: {colors['bg_dark']};
        }}

        #memory-list {{
            padding: 1 1;
            height: 100%;
        }}

        .memory-item {{
            padding: 1 1;
            margin-bottom: 1;
            border-bottom: dashed {colors['border']};
            border-radius: 0 4 4 0;
        }}

        .memory-item:hover {{
            background: {colors['bg_elevated']}66;
        }}

        .memory-item-header {{
            color: {colors['text_primary']};
        }}

        .memory-item-detail {{
            color: {colors['text_muted']};
            padding-left: 2;
        }}

        .memory-icon {{
            color: {colors['accent']};
        }}

        .memory-type {{
            color: {colors['info']};
            text-style: bold;
        }}

        /* ── Search Bar ───────────────────────────────────────── */

        #search-bar {{
            height: 3;
            border-bottom: solid {colors['border']};
            padding: 0 1;
            dock: top;
            background: {colors['bg_surface']};
        }}

        #search-input {{
            width: 1fr;
        }}

        Input {{
            background: {colors['bg_elevated']};
            border: solid {colors['border']};
            color: {colors['text_primary']};
            caret: {colors['accent']};
        }}

        Input:focus {{
            border: solid {colors['border_active']};
            outline: {colors['primary']};
        }}

        Input>.input--placeholder {{
            color: {colors['text_muted']};
        }}

        /* ── Status Bar ───────────────────────────────────────── */

        #status-bar {{
            height: 1;
            background: {colors['bg_surface']};
            color: {colors['text_muted']};
            padding: 0 1;
            dock: bottom;
            border-top: solid {colors['border']};
        }}

        /* ── Empty State ──────────────────────────────────────── */

        #empty-state {{
            padding: 4 2;
            text-align: center;
            color: {colors['text_muted']};
        }}

        /* ── Footer Override ─────────────────────────────────── */

        Footer {{
            background: {colors['bg_surface']};
            color: {colors['text_secondary']};
            border-top: solid {colors['border']};
            dock: bottom;
        }}

        Footer .binding--key {{
            color: {colors['accent']};
            text-style: bold;
            min-width: 2;
            padding: 0 1;
            border: round {colors['border']};
            background: {colors['bg_elevated']};
        }}

        /* ── Header Override ──────────────────────────────────── */

        Header {{
            background: {colors['bg_surface']};
            color: {colors['text_primary']};
            text-style: bold;
            border-bottom: solid {colors['border']};
            dock: top;
        }}

        Header.-on-high {{
            background: {colors['primary'] + '22'};
            color: {colors['accent']};
        }}
        """

    class CarryMemTUI(App):
        """Main Textual TUI application for browsing and managing memories."""

        CSS = _build_app_css(_MORANDI)

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("/", "focus_search", "Search"),
            Binding("s", "focus_search", "Search"),
            Binding("?", "show_help", "Help"),
            Binding("a", "add_memory", "Add"),
            Binding("r", "refresh", "Refresh"),
            Binding("d", "delete_memory", "Delete"),
            Binding("D", "show_dashboard", "Dashboard"),
            Binding("e", "edit_memory", "Edit"),
            Binding("0", "view_all", "All"),
            Binding("1", "view_all", "All"),
            Binding("2", "view_preferences", "Prefs"),
            Binding("3", "view_facts", "Facts"),
            Binding("4", "view_corrections", "Fixes"),
            Binding("5", "view_decisions", "Decis"),
            Binding("ctrl+t", "cycle_theme", "Theme"),
            Binding("escape", "cancel_action", "Cancel"),
        ]

        current_filter: reactive[str] = reactive("")
        search_query: reactive[str] = reactive("")
        selected_index: reactive[int] = reactive(-1)

        def __init__(
            self,
            db_path: Optional[str] = None,
            namespace: str = "default",
            theme_name: str = "morandi-dark",
            group_by_date: bool = True,
        ):
            """Initialize the TUI with a database path, namespace, and theme."""
            self._theme = get_theme(theme_name)
            self._morandi = self._theme.colors  # Used by CSS f-string
            # Textual App.CSS is class-level; per-instance override requires type: ignore[misc]
            self.CSS = _build_app_css(self._morandi)  # type: ignore[misc]
            super().__init__()
            self.db_path = db_path or str(_DEFAULT_DB)
            self.namespace = namespace
            self.cm = CarryMem(db_path=self.db_path, namespace=self.namespace)
            self.memories: List[Dict[str, Any]] = []
            self._add_mode = False
            # P2-U4: when True, memories are grouped by date bucket; when
            # False, the list renders flat (legacy behavior).
            self.group_by_date = group_by_date
            # P2-P5: lazy-loading window into self.memories.
            self._total_memories = 0
            self._visible_count = MAX_VISIBLE_MEMORIES

        def compose(self) -> ComposeResult:
            """Compose the main application layout."""
            yield Header(show_clock=True)
            with Horizontal(id="search-bar"):
                yield Input(placeholder="\U0001f50d  Search memories... (/ to focus)", id="search-input")
            yield ErrorDisplay(id="error-display")
            with Container(id="main-container"):
                with Vertical(id="sidebar"):
                    yield Static("  CarryMem", id="sidebar-title")
                    yield Static("  \u2500\u2500 Filters \u2500\u2500", classes="sidebar-section")
                    yield Static("  [1]  All Memories", classes="sidebar-item", id="filter-all")
                    yield Static("  [2]  Preferences", classes="sidebar-item", id="filter-prefs")
                    yield Static("  [3]  Facts", classes="sidebar-item", id="filter-facts")
                    yield Static("  [4]  Corrections", classes="sidebar-item", id="filter-corrections")
                    yield Static("  [5]  Decisions", classes="sidebar-item", id="filter-decisions")
                    yield Static("  \u2500\u2500 Actions \u2500\u2500", classes="sidebar-section")
                    yield Static("  [a]  Add Memory", classes="sidebar-item")
                    yield Static("  [d]  Delete Memory", classes="sidebar-item")
                    yield Static("  [e]  Edit Memory", classes="sidebar-item")
                    yield Static("  [r]  Refresh List", classes="sidebar-item")
                    yield Static("  [D]  Dashboard", classes="sidebar-item")
                    yield Static("  [^T] Cycle Theme", classes="sidebar-item")
                    yield Static("  [/]  Search", classes="sidebar-item")
                    yield Static("  [?]  Help", classes="sidebar-item")
                    yield Static("  [q]  Quit", classes="sidebar-item")
                    yield StatsPanel(id="stats-panel")
                with Vertical(id="content"):
                    yield Static("Loading memories...", id="memory-list")
            yield Static("Ready", id="status-bar")
            yield Footer()

        def on_mount(self) -> None:
            """Load memories when the app mounts.

            P1-P1: If the database is empty (first run), push the
            :class:`OnboardingScreen` so the user is guided through
            storing and searching their first memory. The onboarding
            screen is skipped silently if its module is unavailable.
            """
            self._load_memories()
            # First-run onboarding: detect empty memory database via the
            # underlying adapter's ``count()`` API (CarryMem itself does
            # not expose a public count method).
            if _ONBOARDING_AVAILABLE and OnboardingScreen is not None:
                try:
                    adapter = getattr(self.cm, "_adapter", None)
                    if adapter is not None and adapter.count() == 0:
                        self.push_screen(OnboardingScreen(self.cm))
                except Exception:  # NOTE: intentional — onboarding is non-critical; never block TUI launch
                    pass

        # ── Search & Input ──────────────────────────────────────────

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Handle Enter on the search bar to search or add a memory."""
            if event.input.id == "search-input":
                value = event.value.strip()
                if self._add_mode:
                    self._add_mode = False
                    if value:
                        try:
                            self.cm.declare(value)
                            event.input.placeholder = "\U0001f50d  Search memories... (/ to focus)"
                            event.input.value = ""
                            self._clear_error()
                            self._load_memories()
                            self._set_status(f"Added: {value[:50]}")
                        except (ValueError, TypeError, KeyError, RuntimeError) as e:
                            self._show_error(e)
                    else:
                        event.input.placeholder = "\U0001f50d  Search memories... (/ to focus)"
                else:
                    self.search_query = value
                    self._load_memories()

        # ── Data Loading & Rendering ────────────────────────────────

        def _load_memories(self) -> None:
            self._clear_error()
            try:
                filters: Dict[str, Any] = {}
                if self.current_filter:
                    filters["type"] = self.current_filter

                query = self.search_query or ""
                self.memories = self.cm.recall_memories(query=query, filters=filters, limit=50)
                self._total_memories = len(self.memories)
                # Reset the lazy-loading window (P2-P5).
                self._visible_count = MAX_VISIBLE_MEMORIES
                self.selected_index = -1
                self._render_memories()
                self._update_status()
                self._update_sidebar_active()
            except (ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error) as e:
                self._show_error(e)
                self._set_content("")

        def _show_error(self, exc: Exception) -> None:
            try:
                error_display = self.query_one("#error-display", ErrorDisplay)
                error_display.show_error(exc)
            except (AttributeError, ValueError):
                self._set_status(f"Error: {exc}")

        def _clear_error(self) -> None:
            try:
                error_display = self.query_one("#error-display", ErrorDisplay)
                error_display.clear_error()
            except (AttributeError, ValueError):
                pass

        def _render_memories(self) -> None:
            if not self.memories:
                self._set_content(
                    "\n\n"
                    "    No memories found.\n\n"
                    "    Press [bold][a][/bold] to add a memory,\n"
                    "    press [bold][/][/bold] to search,\n"
                    "    or press [bold][r][/bold] to refresh."
                )
                return

            # Lazy loading: only render the visible slice (P2-P5).
            visible = self.memories[: self._visible_count]
            has_more = len(self.memories) > len(visible)

            if self.group_by_date:
                parts = self._render_grouped_memories(visible)
            else:
                parts = self._render_flat_memories(visible)

            if has_more:
                parts.append(f"  ... Load more ... (showing {len(visible)} of {len(self.memories)})")
                parts.append("")

            self._set_content("\n".join(parts))

        def _render_flat_memories(self, memories: List[Dict[str, Any]]) -> List[str]:
            """Render memory items as a flat 1-based list (legacy behavior)."""
            parts: List[str] = []
            for i, m in enumerate(memories, 1):
                mtype = m.get("type", "unknown")
                icon = _TYPE_ICONS.get(mtype, "?")
                content = m.get("content", "")
                confidence = m.get("confidence", 0)
                importance = m.get("importance_score", 0)
                key = m.get("storage_key", "")

                marker = ">" if i - 1 == self.selected_index else " "
                header = f"{marker}{i}. {icon} [{mtype}] {content}"
                detail = f"      Conf: {confidence:.0%}  " f"| Imp: {importance:.2f}  " f"| {key[:30]}"
                parts.append(header)
                parts.append(detail)
                parts.append("")
            return parts

        def _render_grouped_memories(self, memories: List[Dict[str, Any]]) -> List[str]:
            """Render memory items grouped under date-bucket headers (P2-U4).

            The 1-based index continues across groups so the selection marker
            (e.g. ``>1.``) stays consistent with the flat-list numbering.
            """
            groups = self._group_memories_by_date(memories)
            parts: List[str] = []
            global_idx = 0
            for group_name in ("Today", "Yesterday", "This Week", "Earlier"):
                group_mems = groups.get(group_name, [])
                if not group_mems:
                    continue
                parts.append(f"  [{_MORANDI['accent']} bold]{group_name} ({len(group_mems)})[/]")
                parts.append("")
                for m in group_mems:
                    global_idx += 1
                    mtype = m.get("type", "unknown")
                    icon = _TYPE_ICONS.get(mtype, "?")
                    content = m.get("content", "")
                    confidence = m.get("confidence", 0)
                    importance = m.get("importance_score", 0)
                    key = m.get("storage_key", "")

                    marker = ">" if global_idx - 1 == self.selected_index else " "
                    header = f"{marker}{global_idx}. {icon} [{mtype}] {content}"
                    detail = f"      Conf: {confidence:.0%}  " f"| Imp: {importance:.2f}  " f"| {key[:30]}"
                    parts.append(header)
                    parts.append(detail)
                    parts.append("")
            return parts

        def _group_memories_by_date(self, memories: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
            """Group memories by date bucket: Today / Yesterday / This Week / Earlier."""
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            week_start = today_start - timedelta(days=7)

            buckets: Dict[str, List[Dict[str, Any]]] = {
                "Today": [],
                "Yesterday": [],
                "This Week": [],
                "Earlier": [],
            }
            for m in memories:
                dt = self._parse_created_at(m.get("created_at", ""))
                if dt is None:
                    buckets["Earlier"].append(m)
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= today_start:
                    buckets["Today"].append(m)
                elif dt >= yesterday_start:
                    buckets["Yesterday"].append(m)
                elif dt >= week_start:
                    buckets["This Week"].append(m)
                else:
                    buckets["Earlier"].append(m)
            return buckets

        @staticmethod
        def _parse_created_at(created: str) -> Optional[datetime]:
            """Parse a created_at ISO timestamp; return None on failure."""
            if not created:
                return None
            s = created.replace("Z", "+00:00") if created.endswith("Z") else created
            try:
                return datetime.fromisoformat(s)
            except (ValueError, TypeError):
                return None

        def _load_more_memories(self) -> None:
            """Expand the lazy-loading window by MAX_VISIBLE_MEMORIES (P2-P5)."""
            if self._visible_count >= len(self.memories):
                return
            self._visible_count = min(
                self._visible_count + MAX_VISIBLE_MEMORIES,
                len(self.memories),
            )

        def _set_content(self, text: str) -> None:
            try:
                content = self.query_one("#memory-list", Static)
                content.update(text)
            except (AttributeError, ValueError):
                pass

        # ── Status Bar ──────────────────────────────────────────────

        def _set_status(self, text: str) -> None:
            try:
                status_bar = self.query_one("#status-bar", Static)
                status_bar.update(text)
            except (AttributeError, ValueError):
                pass

        def _update_status(self) -> None:
            try:
                stats = self.cm.get_stats()
                total = stats.get("total_count", 0)
                shown = len(self.memories)
                filt_label = _TYPE_LABELS.get(self.current_filter, "All") if self.current_filter else "All"
                status = (
                    f"  Total: {total}  |  Showing: {shown}  |  "
                    f"Filter: {filt_label}  |  "
                    f"Namespace: {self.namespace}"
                )
                status_bar = self.query_one("#status-bar", Static)
                status_bar.update(status)

                stats_panel = self.query_one("#stats-panel", StatsPanel)
                stats_panel.update_stats(stats, shown, self.current_filter)
            except (AttributeError, ValueError, KeyError):
                pass

        # ── Sidebar Active State ────────────────────────────────────

        def _update_sidebar_active(self) -> None:
            filter_id_map = {
                "": "filter-all",
                "user_preference": "filter-prefs",
                "fact_declaration": "filter-facts",
                "correction": "filter-corrections",
                "decision": "filter-decisions",
            }
            active_id = filter_id_map.get(self.current_filter, "filter-all")

            for fid in ["filter-all", "filter-prefs", "filter-facts", "filter-corrections", "filter-decisions"]:
                try:
                    item = self.query_one(f"#{fid}", Static)
                    item.remove_class("active")
                    if fid == active_id:
                        item.add_class("active")
                except (AttributeError, ValueError):
                    pass

        # ── Actions / Bindings ──────────────────────────────────────

        def action_focus_search(self) -> None:
            """Move keyboard focus to the search input."""
            try:
                search_input = self.query_one("#search-input", Input)
                search_input.focus()
            except (AttributeError, ValueError):
                pass

        def action_add_memory(self) -> None:
            """Enter add-memory mode via the search bar."""
            self._prompt_add()

        def action_show_help(self) -> None:
            """Push the keyboard shortcuts help screen."""
            self.push_screen(HelpScreen())

        def action_show_dashboard(self) -> None:
            """Push the dashboard screen showing ASCII charts (P2-P4)."""
            self.push_screen(DashboardScreen(self.memories))

        def action_delete_memory(self) -> None:
            """Delete the currently selected memory after confirmation."""
            if not (0 <= self.selected_index < len(self.memories)):
                self._set_status("No memory selected")
                return
            memory = self.memories[self.selected_index]
            key = memory.get("storage_key", "")

            def _on_delete_result(confirmed: "bool | None") -> None:
                if confirmed:
                    try:
                        result = self.cm.forget_memory(key)
                        if result:
                            self._clear_error()
                            self._load_memories()
                            self._set_status(f"Deleted: {key[:30]}")
                        else:
                            self._set_status(f"Failed to delete: {key[:30]}")
                    except (ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error) as e:
                        self._show_error(e)
                        self._set_status("Delete failed")

            self.push_screen(DeleteConfirmScreen(memory), _on_delete_result)

        def action_edit_memory(self) -> None:
            """Edit the currently selected memory."""
            if not (0 <= self.selected_index < len(self.memories)):
                self._set_status("No memory selected")
                return
            memory = self.memories[self.selected_index]
            key = memory.get("storage_key", "")

            def _on_edit_result(new_content: Optional[str]) -> None:
                if new_content is not None:
                    try:
                        result = self.cm.update_memory(key, new_content, reason="TUI edit")
                        if result.get("updated"):
                            self._clear_error()
                            self._load_memories()
                            self._set_status(f"Updated: {key[:30]} (v{result.get('version', '?')})")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            self._set_status(f"Update failed: {error_msg}")
                    except (ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error) as e:
                        self._show_error(e)
                        self._set_status("Edit failed")

            self.push_screen(EditMemoryScreen(memory), _on_edit_result)

        def action_cancel_action(self) -> None:
            """Cancel the current add-memory mode, restoring the search bar."""
            if self._add_mode:
                self._add_mode = False
                try:
                    search_input = self.query_one("#search-input", Input)
                    search_input.placeholder = "\U0001f50d  Search memories... (/ to focus)"
                    search_input.value = ""
                except (AttributeError, ValueError):
                    pass

        def _prompt_add(self) -> None:
            try:
                search_input = self.query_one("#search-input", Input)
                search_input.placeholder = "\u270f  Type memory content... (Enter to save, Esc to cancel)"
                search_input.value = ""
                search_input.focus()
                self._add_mode = True
                self._set_status("Mode: ADD  |  Type your memory and press Enter")
            except (AttributeError, ValueError):
                pass

        def action_refresh(self) -> None:
            """Reload the memory list and clear stale state."""
            self._load_memories()
            self._set_status("Refreshed \u2713")

        def action_view_all(self) -> None:
            """Clear the type filter and show all memories."""
            self.current_filter = ""
            self._load_memories()

        def action_view_preferences(self) -> None:
            """Filter the list to show only preferences."""
            self.current_filter = "user_preference"
            self._load_memories()

        def action_view_facts(self) -> None:
            """Filter the list to show only facts."""
            self.current_filter = "fact_declaration"
            self._load_memories()

        def action_view_corrections(self) -> None:
            """Filter the list to show only corrections."""
            self.current_filter = "correction"
            self._load_memories()

        def action_view_decisions(self) -> None:
            """Filter the list to show only decisions."""
            self.current_filter = "decision"
            self._load_memories()

        def action_cycle_theme(self) -> None:
            """Cycle through registered themes (P1-C3 / P2-U2).

            Updates the app's CSS in place by regenerating the stylesheet
            from the next theme's color palette. The cycle order follows
            :func:`carrymem.ui.themes.list_themes` (registry insertion
            order): ``morandi-dark`` -> ``morandi-light`` -> ``high-contrast``
            -> back to ``morandi-dark``.
            """
            current = self._theme.name
            themes = list_themes()
            try:
                idx = themes.index(current)
            except ValueError:
                idx = -1
            next_name = themes[(idx + 1) % len(themes)] if themes else current
            self._theme = get_theme(next_name)
            self._morandi = self._theme.colors
            # Regenerate the app stylesheet and refresh. Best-effort: if
            # the runtime stylesheet reload fails, the next render still
            # picks up self._morandi via _render_memories.
            new_css = _build_app_css(self._morandi)
            try:
                from textual.styles.stylesheet import Stylesheet

                stylesheet = Stylesheet()
                stylesheet.add_source(new_css)
                self.stylesheet = stylesheet
                self.stylesheet.apply(self)
            except Exception:  # NOTE: intentional — best-effort theme switch; non-fatal if stylesheet reload fails
                pass
            self._set_status(f"Theme: {next_name}")
            self._render_memories()
            self._update_status()

        # ── Memory Detail View ──────────────────────────────────────

        def action_view_detail(self) -> None:
            """Open the detail overlay for the selected memory."""
            if 0 <= self.selected_index < len(self.memories):
                self.push_screen(MemoryDetailScreen(self.memories[self.selected_index]))

        # ── Keyboard Navigation ─────────────────────────────────────

        def on_key(self, event) -> None:
            """Handle j/k/arrows/Enter/Esc navigation over the memory list."""
            if event.key in ("j", "down"):
                if self.selected_index < len(self.memories) - 1:
                    # Lazy loading: if the next item is outside the visible
                    # window, expand the window before moving the cursor (P2-P5).
                    if self.selected_index + 1 >= self._visible_count and self._visible_count < len(self.memories):
                        self._load_more_memories()
                    self.selected_index += 1
                    self._render_memories()
            elif event.key in ("k", "up"):
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._render_memories()
            elif event.key == "enter":
                if 0 <= self.selected_index < len(self.memories):
                    self.action_view_detail()
            elif event.key == "escape":
                self.action_cancel_action()

        # ── Lifecycle ───────────────────────────────────────────────

        def on_unmount(self) -> None:
            """Close the CarryMem instance when the app exits."""
            if self.cm:
                self.cm.close()

    def run_tui(
        db_path: Optional[str] = None,
        namespace: str = "default",
        theme_name: str = "morandi-dark",
    ) -> None:
        """Launch the CarryMem TUI application."""
        if not HAS_TEXTUAL:
            print("  Textual is not installed.")
            print("  Install with: pip install textual")
            print("  Then run: carrymem tui")
            return
        app = CarryMemTUI(db_path=db_path, namespace=namespace, theme_name=theme_name)
        app.run()
