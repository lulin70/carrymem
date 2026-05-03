"""CarryMem TUI — Terminal User Interface for memory management.

Built with Textual. Launch with: carrymem tui
"""

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, Input, Button, ListView, ListItem, Label
    from textual.containers import Container, Horizontal, Vertical
    from textual.binding import Binding
    from textual.reactive import reactive
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


if not HAS_TEXTUAL:
    def run_tui():
        print("  Textual is not installed.")
        print("  Install with: pip install textual")
        print("  Then run: carrymem tui")

else:
    from memory_classification_engine import CarryMem
    from pathlib import Path
    from typing import Optional, List, Dict, Any

    _DEFAULT_DB = Path.home() / ".carrymem" / "memories.db"

    _TYPE_ICONS = {
        "user_preference": "⭐",
        "fact_declaration": "📌",
        "correction": "🔧",
        "decision": "🎯",
        "task_pattern": "🔄",
        "contextual_observation": "👁",
        "knowledge": "📚",
        "unknown": "❓",
    }

    class MemoryItem(Static):
        def __init__(self, memory: Dict[str, Any]):
            self.memory = memory
            mtype = memory.get("type", "unknown")
            icon = _TYPE_ICONS.get(mtype, "❓")
            content = memory.get("content", "")
            confidence = memory.get("confidence", 0)
            key = memory.get("storage_key", "")
            importance = memory.get("importance_score", 0)

            display = f"{icon} [{mtype}] {content[:70]}"
            if len(content) > 70:
                display += "..."
            detail = f"  Conf: {confidence:.0%} | Importance: {importance:.2f} | Key: {key[:20]}"

            super().__init__(f"{display}\n{detail}")
            self.add_class("memory-item")

    class CarryMemTUI(App):
        CSS = """
        Screen {
            layout: vertical;
        }

        #main-container {
            layout: horizontal;
            height: 1fr;
        }

        #sidebar {
            width: 30;
            border-right: solid green;
            padding: 0 1;
        }

        #content {
            width: 1fr;
            padding: 0 1;
            overflow-y: auto;
        }

        #search-bar {
            height: 3;
            border-bottom: solid green;
            padding: 0 1;
        }

        #search-input {
            width: 1fr;
        }

        .memory-item {
            padding: 1 0;
            border-bottom: dashed green;
        }

        #status-bar {
            height: 1;
            background: $surface;
            color: $text-muted;
            padding: 0 1;
        }

        #sidebar-title {
            text-style: bold;
            margin-bottom: 1;
        }

        .sidebar-section {
            margin-bottom: 1;
        }

        .sidebar-item {
            padding: 0 1;
        }

        .sidebar-item:hover {
            background: $surface;
        }

        .sidebar-item.active {
            background: $primary;
            color: $text;
        }

        #empty-state {
            padding: 2;
            text-align: center;
            color: $text-muted;
        }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("s", "focus_search", "Search"),
            Binding("a", "add_memory", "Add"),
            Binding("r", "refresh", "Refresh"),
            Binding("1", "view_all", "All"),
            Binding("2", "view_preferences", "Prefs"),
            Binding("3", "view_facts", "Facts"),
            Binding("4", "view_corrections", "Fixes"),
        ]

        current_filter: reactive[str] = reactive("")
        search_query: reactive[str] = reactive("")

        def __init__(self, db_path: Optional[str] = None, namespace: str = "default"):
            super().__init__()
            self.db_path = db_path or str(_DEFAULT_DB)
            self.namespace = namespace
            self.cm = CarryMem(db_path=self.db_path, namespace=self.namespace)
            self.memories: List[Dict[str, Any]] = []

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="search-bar"):
                yield Input(placeholder="Search memories... (Enter to search)", id="search-input")
            with Container(id="main-container"):
                with Vertical(id="sidebar"):
                    yield Static("CarryMem", id="sidebar-title")
                    yield Static("── Filters ──", classes="sidebar-section")
                    yield Static("1  All Memories", classes="sidebar-item", id="filter-all")
                    yield Static("2  Preferences", classes="sidebar-item", id="filter-prefs")
                    yield Static("3  Facts", classes="sidebar-item", id="filter-facts")
                    yield Static("4  Corrections", classes="sidebar-item", id="filter-corrections")
                    yield Static("── Actions ──", classes="sidebar-section")
                    yield Static("a  Add Memory", classes="sidebar-item")
                    yield Static("r  Refresh", classes="sidebar-item")
                    yield Static("s  Search", classes="sidebar-item")
                    yield Static("q  Quit", classes="sidebar-item")
                with Vertical(id="content"):
                    yield Static("Loading memories...", id="memory-list")
            yield Static("Ready", id="status-bar")
            yield Footer()

        def on_mount(self) -> None:
            self._load_memories()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == "search-input":
                self.search_query = event.value
                self._load_memories()

        def _load_memories(self) -> None:
            try:
                filters = {}
                if self.current_filter:
                    filters["type"] = self.current_filter

                query = self.search_query or ""
                self.memories = self.cm.recall_memories(query=query, filters=filters, limit=50)
                self._render_memories()
                self._update_status()
            except Exception as e:
                self._set_content(f"Error loading memories: {e}")

        def _render_memories(self) -> None:
            if not self.memories:
                self._set_content(
                    "No memories found.\n\n"
                    "Press 'a' to add a memory, or 's' to search."
                )
                return

            lines = []
            for i, m in enumerate(self.memories, 1):
                mtype = m.get("type", "unknown")
                icon = _TYPE_ICONS.get(mtype, "❓")
                content = m.get("content", "")
                confidence = m.get("confidence", 0)
                importance = m.get("importance_score", 0)
                key = m.get("storage_key", "")

                lines.append(f"{i}. {icon} [{mtype}] {content}")
                lines.append(f"   Conf: {confidence:.0%} | Importance: {importance:.2f} | Key: {key}")
                lines.append("")

            self._set_content("\n".join(lines))

        def _set_content(self, text: str) -> None:
            try:
                content = self.query_one("#memory-list", Static)
                content.update(text)
            except Exception:
                pass

        def _update_status(self) -> None:
            try:
                stats = self.cm.get_stats()
                total = stats.get("total_count", 0)
                shown = len(self.memories)
                status = f"Total: {total} | Showing: {shown} | Filter: {self.current_filter or 'All'} | Namespace: {self.namespace}"
                status_bar = self.query_one("#status-bar", Static)
                status_bar.update(status)
            except Exception:
                pass

        def action_focus_search(self) -> None:
            try:
                search_input = self.query_one("#search-input", Input)
                search_input.focus()
            except Exception:
                pass

        def action_add_memory(self) -> None:
            self._prompt_add()

        def _prompt_add(self) -> None:
            try:
                search_input = self.query_one("#search-input", Input)
                search_input.placeholder = "Type memory to add... (Enter to save, Esc to cancel)"
                search_input.value = ""
                search_input.focus()
                self._add_mode = True
            except Exception:
                pass

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == "search-input":
                value = event.value.strip()
                if hasattr(self, '_add_mode') and self._add_mode:
                    self._add_mode = False
                    if value:
                        try:
                            self.cm.declare(value)
                            event.input.placeholder = "Search memories... (Enter to search)"
                            event.input.value = ""
                            self._load_memories()
                            self._set_status(f"Added: {value[:50]}")
                        except Exception as e:
                            self._set_status(f"Error: {e}")
                else:
                    self.search_query = value
                    self._load_memories()

        def _set_status(self, text: str) -> None:
            try:
                status_bar = self.query_one("#status-bar", Static)
                status_bar.update(text)
            except Exception:
                pass

        def action_refresh(self) -> None:
            self._load_memories()
            self._set_status("Refreshed")

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

        def on_key(self, event) -> None:
            if event.key == "escape":
                if hasattr(self, '_add_mode') and self._add_mode:
                    self._add_mode = False
                    try:
                        search_input = self.query_one("#search-input", Input)
                        search_input.placeholder = "Search memories... (Enter to search)"
                        search_input.value = ""
                    except Exception:
                        pass

        def on_unmount(self) -> None:
            if self.cm:
                self.cm.close()

    def run_tui(db_path: Optional[str] = None, namespace: str = "default"):
        app = CarryMemTUI(db_path=db_path, namespace=namespace)
        app.run()
