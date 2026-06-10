"""CarryMem TUI — Terminal User Interface for memory management.

Built with Textual. Launch with: carrymem tui

Design: Morandi color palette for a calm, professional aesthetic.
"""

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widget import Widget
    from textual.widgets import DataTable, Footer, Header, Input, Label, Static

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


if not HAS_TEXTUAL:

    def run_tui():
        print("  Textual is not installed.")
        print("  Install with: pip install textual")
        print("  Then run: carrymem tui")

else:
    from typing import Any, Dict, List, Optional

    from carrymem import CarryMem
    from carrymem.constants import DB_PATH

    _DEFAULT_DB = DB_PATH

    # ── Morandi Color Palette ──────────────────────────────────────
    # Soft, muted tones inspired by Italian painter Giorgio Morandi.
    # All colors are low-saturation, high-readability.

    _MORANDI = {
        "primary": "#8B9A9D",       # dusty blue-gray
        "secondary": "#A8AD9F",     # sage gray
        "accent": "#C4A882",        # warm sand
        "bg_dark": "#1E2024",       # deep charcoal
        "bg_surface": "#282A2F",    # surface dark
        "bg_elevated": "#33363D",   # elevated surface
        "text_primary": "#D4D4D4",  # soft white
        "text_secondary": "#9CA3AF",# light gray
        "text_muted": "#6B7280",    # medium gray
        "success": "#7D9B8C",       # muted green
        "warning": "#C4A35A",       # muted gold
        "error": "#BC8F8F",         # muted rose
        "info": "#8FAAB8",          # muted blue
        "border": "#3D4047",        # subtle border
        "border_active": "#8B9A9D", # active border
    }

    _TYPE_ICONS = {
        "user_preference": "\u2b50",
        "fact_declaration": "\U0001f4cc",
        "correction": "\U0001f527",
        "decision": "\U0001f3af",
        "task_pattern": "\U0001f504",
        "contextual_observation": "\U0001f441",
        "knowledge": "\U0001f4da",
        "unknown": "\u2753",
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
            m = self.memory
            mtype = m.get("type", "unknown")
            icon = _TYPE_ICONS.get(mtype, "\u2753")
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
                f"  Confidence: {confidence:.0%}  |  "
                f"Importance: {importance:.2f}",
                id="detail-meta1",
            )
            yield Static(
                f"  Key: {key}\n"
                f"  Namespace: {namespace}\n"
                f"  Created: {created}\n"
                f"  Updated: {updated}",
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

    # ── Help Screen ─────────────────────────────────────────────────

    class HelpScreen(ModalScreen[None]):
        """Keyboard shortcuts and usage help."""

        BINDINGS = [
            Binding("escape", "dismiss", "Close"),
            Binding("q", "dismiss", "Close"),
            Binding("?", "dismiss", "Close"),
        ]

        def compose(self) -> ComposeResult:
            lines = [
                ("  \u2699  CarryMem TUI \u2014 Keyboard Shortcuts", "title"),
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
                ("    d           Delete selected (future)", "item"),
                ("", ""),
                ("  System:", "section"),
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

    # ── Statistics Panel ────────────────────────────────────────────

    class StatsPanel(Static):
        """Real-time statistics display in the sidebar."""

        def update_stats(self, stats: Dict[str, Any], shown: int, filt: str) -> None:
            total = stats.get("total_count", 0)
            by_type = stats.get("by_type", {})
            lines = [
                f"\u2502  Statistics",
                f"\u2502  \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
                f"\u2502  Total:   {total}",
                f"\u2502  Showing: {shown}",
                f"\u2502  Filter:  {filt or 'All'}",
                f"\u2502",
            ]
            type_counts = sorted(by_type.items(), key=lambda x: -x[1]) if isinstance(by_type, dict) else []
            for t, c in type_counts[:5]:
                icon = _TYPE_ICONS.get(t, "\u2753")
                label = _TYPE_LABELS.get(t, t)[:10]
                lines.append(f"\u2502  {icon} {label}: {c}")
            self.update("\n".join(lines))

    # ── Main TUI Application ───────────────────────────────────────

    class CarryMemTUI(App):
        CSS = f"""
        /* ══════════════════════════════════════════════════════════
           CarryMorandi TUI — Morandi Color Scheme
           ══════════════════════════════════════════════════════════ */

        Screen {{
            layout: vertical;
            background: {_MORANDI['bg_dark']};
            color: {_MORANDI['text_primary']};
        }}

        /* ── Main Layout ─────────────────────────────────────── */

        #main-container {{
            layout: horizontal;
            height: 1fr;
        }}

        /* ── Sidebar ─────────────────────────────────────────── */

        #sidebar {{
            width: 32;
            border-right: solid {_MORANDI['border']};
            padding: 0 1;
            background: {_MORANDI['bg_surface']};
        }}

        #sidebar-title {{
            text-style: bold;
            color: {_MORANDI['accent']};
            padding: 1 0;
            margin-bottom: 1;
            border-bottom: solid {_MORANDI['border']};
        }}

        .sidebar-section {{
            color: {_MORANDI['primary']};
            text-style: bold;
            margin-top: 1;
            margin-bottom: 0;
            padding: 1 0 0 0;
        }}

        .sidebar-item {{
            padding: 0 1;
            color: {_MORANDI['text_secondary']};
        }}

        .sidebar-item:hover {{
            background: {_MORANDI['bg_elevated']};
            color: {_MORANDI['text_primary']};
        }}

        .sidebar-item.active {{
            background: {_MORANDI['primary'] + '33'};
            color: {_MORANDI['accent']};
            text-style: bold;
        }}

        .sidebar-item .key {{
            color: {_MORANDI['accent']};
            min-width: 3;
            text-style: bold;
        }}

        #stats-panel {{
            margin-top: 1;
            padding: 1 0;
            border-top: solid {_MORANDI['border']};
            color: {_MORANDI['text_muted']};
        }}

        /* ── Content Area ─────────────────────────────────────── */

        #content {{
            width: 1fr;
            padding: 0 1;
            overflow-y: auto;
            background: {_MORANDI['bg_dark']};
        }}

        #memory-list {{
            padding: 1 1;
            height: 100%;
        }}

        .memory-item {{
            padding: 1 1;
            margin-bottom: 1;
            border-bottom: dashed {_MORANDI['border']};
            border-radius: 0 4 4 0;
        }}

        .memory-item:hover {{
            background: {_MORANDI['bg_elevated']}66;
        }}

        .memory-item-header {{
            color: {_MORANDI['text_primary']};
        }}

        .memory-item-detail {{
            color: {_MORANDI['text_muted']};
            padding-left: 2;
        }}

        .memory-icon {{
            color: {_MORANDI['accent']};
        }}

        .memory-type {{
            color: {_MORANDI['info']};
            text-style: bold;
        }}

        /* ── Search Bar ───────────────────────────────────────── */

        #search-bar {{
            height: 3;
            border-bottom: solid {_MORANDI['border']};
            padding: 0 1;
            dock: top;
            background: {_MORANDI['bg_surface']};
        }}

        #search-input {{
            width: 1fr;
        }}

        Input {{
            background: {_MORANDI['bg_elevated']};
            border: solid {_MORANDI['border']};
            color: {_MORANDI['text_primary']};
            caret: {_MORANDI['accent']};
        }}

        Input:focus {{
            border: solid {_MORANDI['border_active']};
            outline: {_MORANDI['primary']};
        }}

        Input>.input--placeholder {{
            color: {_MORANDI['text_muted']};
        }}

        /* ── Status Bar ───────────────────────────────────────── */

        #status-bar {{
            height: 1;
            background: {_MORANDI['bg_surface']};
            color: {_MORANDI['text_muted']};
            padding: 0 1;
            dock: bottom;
            border-top: solid {_MORANDI['border']};
        }}

        /* ── Empty State ──────────────────────────────────────── */

        #empty-state {{
            padding: 4 2;
            text-align: center;
            color: {_MORANDI['text_muted']};
        }}

        /* ── Footer Override ─────────────────────────────────── */

        Footer {{
            background: {_MORANDI['bg_surface']};
            color: {_MORANDI['text_secondary']};
            border-top: solid {_MORANDI['border']};
            dock: bottom;
        }}

        Footer .binding--key {{
            color: {_MORANDI['accent']};
            text-style: bold;
            min-width: 2;
            padding: 0 1;
            border: round {_MORANDI['border']};
            background: {_MORANDI['bg_elevated']};
        }}

        /* ── Header Override ──────────────────────────────────── */

        Header {{
            background: {_MORANDI['bg_surface']};
            color: {_MORANDI['text_primary']};
            text-style: bold;
            border-bottom: solid {_MORANDI['border']};
            dock: top;
        }}

        Header.-on-high {{
            background: {_MORANDI['primary'] + '22'};
            color: {_MORANDI['accent']};
        }}
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("/", "focus_search", "Search"),
            Binding("s", "focus_search", "Search"),
            Binding("?", "show_help", "Help"),
            Binding("a", "add_memory", "Add"),
            Binding("r", "refresh", "Refresh"),
            Binding("0", "view_all", "All"),
            Binding("1", "view_all", "All"),
            Binding("2", "view_preferences", "Prefs"),
            Binding("3", "view_facts", "Facts"),
            Binding("4", "view_corrections", "Fixes"),
            Binding("5", "view_decisions", "Decis"),
            Binding("escape", "cancel_action", "Cancel"),
        ]

        current_filter: reactive[str] = reactive("")
        search_query: reactive[str] = reactive("")
        selected_index: reactive[int] = reactive(-1)

        def __init__(self, db_path: Optional[str] = None, namespace: str = "default"):
            super().__init__()
            self.db_path = db_path or str(_DEFAULT_DB)
            self.namespace = namespace
            self.cm = CarryMem(db_path=self.db_path, namespace=self.namespace)
            self.memories: List[Dict[str, Any]] = []
            self._add_mode = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="search-bar"):
                yield Input(placeholder="\U0001f50d  Search memories... (/ to focus)", id="search-input")
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
                    yield Static("  [r]  Refresh List", classes="sidebar-item")
                    yield Static("  [/]  Search", classes="sidebar-item")
                    yield Static("  [?]  Help", classes="sidebar-item")
                    yield Static("  [q]  Quit", classes="sidebar-item")
                    yield StatsPanel(id="stats-panel")
                with Vertical(id="content"):
                    yield Static("Loading memories...", id="memory-list")
            yield Static("Ready", id="status-bar")
            yield Footer()

        def on_mount(self) -> None:
            self._load_memories()

        # ── Search & Input ──────────────────────────────────────────

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == "search-input":
                value = event.value.strip()
                if self._add_mode:
                    self._add_mode = False
                    if value:
                        try:
                            self.cm.declare(value)
                            event.input.placeholder = "\U0001f50d  Search memories... (/ to focus)"
                            event.input.value = ""
                            self._load_memories()
                            self._set_status(f"Added: {value[:50]}")
                        except (ValueError, KeyError, RuntimeError) as e:
                            self._set_status(f"Error: {e}")
                    else:
                        event.input.placeholder = "\U0001f50d  Search memories... (/ to focus)"
                else:
                    self.search_query = value
                    self._load_memories()

        # ── Data Loading & Rendering ────────────────────────────────

        def _load_memories(self) -> None:
            try:
                filters: Dict[str, Any] = {}
                if self.current_filter:
                    filters["type"] = self.current_filter

                query = self.search_query or ""
                self.memories = self.cm.recall_memories(query=query, filters=filters, limit=50)
                self.selected_index = -1
                self._render_memories()
                self._update_status()
                self._update_sidebar_active()
            except (ValueError, KeyError, RuntimeError, AttributeError) as e:
                self._set_content(f"Error loading memories: {e}")

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

            parts: List[str] = []
            for i, m in enumerate(self.memories, 1):
                mtype = m.get("type", "unknown")
                icon = _TYPE_ICONS.get(mtype, "\u2753")
                content = m.get("content", "")
                confidence = m.get("confidence", 0)
                importance = m.get("importance_score", 0)
                key = m.get("storage_key", "")

                marker = ">" if i - 1 == self.selected_index else " "
                header = f"{marker}{i}. {icon} [{mtype}] {content}"
                detail = (
                    f"      Conf: {confidence:.0%}  "
                    f"| Imp: {importance:.2f}  "
                    f"| {key[:30]}"
                )
                parts.append(header)
                parts.append(detail)
                parts.append("")

            self._set_content("\n".join(parts))

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
            try:
                search_input = self.query_one("#search-input", Input)
                search_input.focus()
            except (AttributeError, ValueError):
                pass

        def action_add_memory(self) -> None:
            self._prompt_add()

        def action_show_help(self) -> None:
            self.push_screen(HelpScreen())

        def action_cancel_action(self) -> None:
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
            self._load_memories()
            self._set_status("Refreshed \u2713")

        def action_view_all(self) -> None:
            self.current_filter = ""
            self._load_memories()

        def action_view_preferences(self) -> None:
            self.current_filter = "user_preference"
            self._load_memories()

        def action_view_facts(self) -> None:
            self.current_filter = "fact_declaration"
            self._load_memories()

        def action_view_corrections(self) -> None:
            self.current_filter = "correction"
            self._load_memories()

        def action_view_decisions(self) -> None:
            self.current_filter = "decision"
            self._load_memories()

        # ── Memory Detail View ──────────────────────────────────────

        def action_view_detail(self) -> None:
            if 0 <= self.selected_index < len(self.memories):
                self.push_screen(MemoryDetailScreen(self.memories[self.selected_index]))

        # ── Keyboard Navigation ─────────────────────────────────────

        def on_key(self, event) -> None:
            if event.key in ("j", "down"):
                if self.selected_index < len(self.memories) - 1:
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
            if self.cm:
                self.cm.close()


    def run_tui(db_path: Optional[str] = None, namespace: str = "default") -> None:
        """Launch the CarryMem TUI application."""
        if not HAS_TEXTUAL:
            print("  Textual is not installed.")
            print("  Install with: pip install textual")
            print("  Then run: carrymem tui")
            return
        app = CarryMemTUI(db_path=db_path, namespace=namespace)
        app.run()
