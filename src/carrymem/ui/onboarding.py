"""First-run onboarding screen for CarryMem TUI.

Shown automatically when CarryMem detects an empty memory database
(`adapter.count() == 0`). Guides the user through:

  1. Welcome — explain what CarryMem does
  2. Store  — type and store the first memory via ``cm.declare()``
  3. Search — search the just-stored memory via ``cm.recall_memories()``
  4. Done   — confirmation + "Press ? for shortcuts"

Design constraints (see docs/design/UI_UX_IMPROVEMENTS_v0.9.0.md P1-P1):

* Uses Morandi colors from :class:`carrymem.ui.themes.MorandiDarkTheme`.
* NO emoji anywhere -- uses text symbols only (e.g. ``[v]`` for success).
* Falls back gracefully when Textual is unavailable: only the
  ``SAMPLE_MEMORIES`` list and ``seed_sample_memories()`` helper remain
  importable in that case.

Implementation note
-------------------
All step widgets are composed once at mount time (unique IDs per step);
step transitions toggle each widget's ``display`` attribute rather than
mounting/removing widgets. This avoids the textual DuplicateIds pitfall
that occurs when ``mount()`` is invoked without awaiting (sync event
handlers can't await ``mount_all``).
"""

from __future__ import annotations

from typing import List

# ── Constants always available (no Textual dependency) ────────────────

STEP_WELCOME = 0
STEP_STORE = 1
STEP_SEARCH = 2
STEP_DONE = 3
TOTAL_STEPS = 4

SAMPLE_MEMORIES: List[str] = [
    "I prefer dark mode over light mode",
    "My favorite programming language is Python",
    "I work best in the morning between 9am and 12pm",
    "I prefer concise answers over verbose explanations",
    "My timezone is Asia/Shanghai",
]


def seed_sample_memories(cm) -> int:
    """Seed 5 sample memories into a CarryMem instance.

    Idempotent enough for first-run use: calls ``cm.declare(text)`` once
    per sample. Failures (e.g. validation errors raised by ``declare``)
    are swallowed so that one bad sample does not abort the rest.

    Args:
        cm: CarryMem instance (or any object exposing ``declare(text)``).

    Returns:
        Number of memories successfully stored (0..5).
    """
    count = 0
    for mem in SAMPLE_MEMORIES:
        try:
            cm.declare(mem)
            count += 1
        except Exception:  # NOTE: intentional — skip memories that fail to store (e.g. validation)
            continue
    return count


# ── Textual-dependent code (guarded) ──────────────────────────────────

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Input, Static

    HAS_TEXTUAL = True
except ImportError:  # pragma: no cover — exercised only in envs w/o textual
    HAS_TEXTUAL = False


if HAS_TEXTUAL:
    from typing import Optional

    from carrymem.ui.themes import MorandiDarkTheme

    _THEME = MorandiDarkTheme()
    _COLORS = _THEME.colors

    # Success marker -- pure text, NO emoji (per design constraint).
    _SUCCESS_MARK = "[\u2713]"  # [v]

    # CSS class name used to scope a widget to a specific step.
    # _step_class(2) -> "step-2"
    def _step_class(step: int) -> str:
        return f"step-{step}"

    class OnboardingScreen(ModalScreen[None]):
        """Welcome screen shown on first run (empty database).

        Guides the user through four steps (see module docstring).
        Press ``Esc`` or ``q`` at any time to skip.

        Widget composition is fixed at mount time; step transitions
        only toggle ``display`` per-widget via :meth:`_update_visibility`.
        This makes the screen cheap to navigate (no mount/remove churn)
        and keeps unique IDs stable for ``query_one`` lookups.
        """

        BINDINGS = [
            Binding("escape", "dismiss", "Skip"),
            Binding("q", "dismiss", "Skip"),
        ]

        def __init__(self, carrymem_instance) -> None:
            super().__init__()
            self.cm = carrymem_instance
            self.step: int = STEP_WELCOME
            self.stored_memory: Optional[str] = None
            self.search_results_count: int = 0
            self._store_error: Optional[str] = None
            self._search_error: Optional[str] = None

        # ── Composition ────────────────────────────────────────────

        def compose(self) -> ComposeResult:
            """Render all step widgets at once; visibility is toggled per step."""
            yield Vertical(
                # ── Step 0: Welcome ────────────────────────────────
                Static(
                    "  CarryMem -- Your AI Memory Companion",
                    id="welcome-title",
                    classes=_step_class(STEP_WELCOME),
                ),
                Static(
                    "  CarryMem remembers what you tell it.\n"
                    "  Preferences, facts, decisions -- all\n"
                    "  stored for instant recall.",
                    id="welcome-intro",
                    classes=_step_class(STEP_WELCOME),
                ),
                Static(
                    "  Let's store your first memory.",
                    id="welcome-prompt",
                    classes=_step_class(STEP_WELCOME),
                ),
                Button("Start", id="start-btn", variant="primary", classes=_step_class(STEP_WELCOME)),
                Button("Skip", id="skip-btn", variant="default", classes=_step_class(STEP_WELCOME)),
                # ── Step 1: Store ───────────────────────────────────
                Static(
                    "  Store Your First Memory",
                    id="store-title",
                    classes=_step_class(STEP_STORE),
                ),
                Static(
                    "  Type something about yourself -- a preference,\n"
                    "  a fact, anything you want CarryMem to remember.",
                    id="store-intro",
                    classes=_step_class(STEP_STORE),
                ),
                Input(
                    placeholder="Type something about yourself...",
                    id="memory-input",
                    classes=_step_class(STEP_STORE),
                ),
                Button("Store", id="store-btn", variant="primary", classes=_step_class(STEP_STORE)),
                Static("", id="store-status", classes=_step_class(STEP_STORE)),
                Button("Next", id="store-next-btn", variant="default", disabled=True, classes=_step_class(STEP_STORE)),
                # ── Step 2: Search ──────────────────────────────────
                Static(
                    "  Search Your Memories",
                    id="search-title",
                    classes=_step_class(STEP_SEARCH),
                ),
                Static(
                    "  Now try searching for what you just stored.",
                    id="search-intro",
                    classes=_step_class(STEP_SEARCH),
                ),
                Input(
                    placeholder="Search for your memory...",
                    id="search-input",
                    classes=_step_class(STEP_SEARCH),
                ),
                Button("Search", id="search-btn", variant="primary", classes=_step_class(STEP_SEARCH)),
                Static("", id="search-status", classes=_step_class(STEP_SEARCH)),
                Button(
                    "Next", id="search-next-btn", variant="default", disabled=True, classes=_step_class(STEP_SEARCH)
                ),
                # ── Step 3: Done ───────────────────────────────────
                Static(
                    "  You're All Set!",
                    id="done-title",
                    classes=_step_class(STEP_DONE),
                ),
                Static(
                    "  CarryMem is ready to use.\n" "  Press ? for shortcuts.",
                    id="done-intro",
                    classes=_step_class(STEP_DONE),
                ),
                Button("Finish", id="finish-btn", variant="primary", classes=_step_class(STEP_DONE)),
                id="onboarding-container",
            )

        def on_mount(self) -> None:
            """Hide all non-welcome widgets on initial mount."""
            self._update_visibility()

        # ── Step transitions ───────────────────────────────────────

        def _advance_step(self) -> int:
            """Move to the next step (clamped at STEP_DONE).

            Returns the new step value. Also refreshes widget visibility
            via :meth:`_update_visibility` -- safe to call whether or not
            the screen is mounted.
            """
            if self.step < STEP_DONE:
                self.step += 1
            self._update_visibility()
            return self.step

        def _update_visibility(self) -> None:
            """Show widgets for the current step, hide all others.

            Uses the per-step CSS class (``step-0`` .. ``step-3``) to
            determine which widgets belong to which step. Safe to call
            before the screen is mounted (caught silently).
            """
            try:
                container = self.query_one("#onboarding-container")
            except Exception:  # NOTE: intentional — screen not mounted yet, nothing to update
                return
            active_class = _step_class(self.step)
            for widget in container.children:
                # Children include Static, Button, Input -- all support display.
                widget.display = active_class in getattr(widget, "classes", set())

        # ── Event handlers ────────────────────────────────────────

        def on_button_pressed(self, event: Button.Pressed) -> None:
            """Handle step navigation via button presses."""
            btn_id = event.button.id
            if btn_id == "start-btn":
                self._advance_step()
            elif btn_id == "skip-btn":
                self.dismiss()
            elif btn_id == "store-btn":
                self._do_store()
            elif btn_id == "search-btn":
                self._do_search()
            elif btn_id in ("store-next-btn", "search-next-btn"):
                self._advance_step()
            elif btn_id == "finish-btn":
                self.dismiss()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            """Handle Enter key inside input fields."""
            if event.input.id == "memory-input":
                self._do_store()
            elif event.input.id == "search-input":
                self._do_search()

        # ── Step logic (unit-testable without Textual runtime) ─────

        def _do_store(self) -> None:
            """Read the memory input, call ``cm.declare()``, update status."""
            text = self._read_input("#memory-input")
            if text is None:
                # Widget not mounted -- nothing to do.
                return
            if not text:
                self._set_status("#store-status", "  Please type something first.")
                return
            try:
                self.cm.declare(text)
                self.stored_memory = text
                self._store_error = None
                self._set_status("#store-status", f"  {_SUCCESS_MARK} Stored!")
                self._enable_next("store-next-btn")
            except Exception as exc:  # NOTE: intentional — onboarding must not crash on storage error
                self._store_error = str(exc)
                self._set_status("#store-status", f"  Failed to store: {exc}")

        def _do_search(self) -> None:
            """Read the search input, call ``cm.recall_memories()``, update status."""
            query = self._read_input("#search-input")
            if query is None:
                return
            if not query:
                self._set_status("#search-status", "  Please enter a search query.")
                return
            try:
                results = self.cm.recall_memories(query=query)
                count = len(results) if isinstance(results, list) else 0
                self.search_results_count = count
                self._search_error = None
                if count == 0:
                    self._set_status("#search-status", "  No matches found.")
                elif count == 1:
                    self._set_status("#search-status", f"  {_SUCCESS_MARK} Found 1 memory.")
                else:
                    self._set_status("#search-status", f"  {_SUCCESS_MARK} Found {count} memories.")
                self._enable_next("search-next-btn")
            except Exception as exc:  # NOTE: intentional — onboarding must not crash on search error
                self._search_error = str(exc)
                self._set_status("#search-status", f"  Search failed: {exc}")

        # ── UI helpers (require running Textual app) ──────────────

        def _read_input(self, selector: str) -> Optional[str]:
            """Return the stripped value of an Input widget, or None if not mounted."""
            try:
                widget = self.query_one(selector, Input)
            except Exception:  # NOTE: intentional — widget not mounted, return None
                return None
            return (widget.value or "").strip()

        def _set_status(self, selector: str, message: str) -> None:
            """Update a status Static widget's content."""
            try:
                widget = self.query_one(selector, Static)
                widget.update(message)
            except Exception:  # NOTE: intentional — widget not yet mounted; safe to skip
                pass

        def _enable_next(self, button_id: str) -> None:
            """Enable a Next button after a successful action."""
            try:
                btn = self.query_one(f"#{button_id}", Button)
                btn.disabled = False
            except Exception:  # NOTE: intentional — button not mounted; safe to skip
                pass

        # ── CSS ────────────────────────────────────────────────────

        CSS = f"""
        OnboardingScreen {{
            align: center middle;
            background: {_COLORS['bg_dark']}99;
        }}

        #onboarding-container {{
            width: 70;
            height: auto;
            max-height: 80%;
            background: {_COLORS['bg_surface']};
            border: round {_COLORS['border_active']};
            padding: 1 2;
        }}

        #welcome-title, #store-title, #search-title, #done-title {{
            text-style: bold;
            color: {_COLORS['accent']};
            text-align: center;
            padding: 1 0;
        }}

        #welcome-intro, #store-intro, #search-intro, #done-intro {{
            color: {_COLORS['text_primary']};
            padding: 0 1 1 1;
            text-align: center;
        }}

        #welcome-prompt {{
            color: {_COLORS['secondary']};
            text-align: center;
            padding: 1 0;
        }}

        #memory-input, #search-input {{
            width: 90%;
            margin: 1 1;
        }}

        #start-btn, #store-btn, #search-btn, #finish-btn {{
            background: {_COLORS['primary']};
            color: {_COLORS['bg_dark']};
            margin: 1 1;
        }}

        #skip-btn, #store-next-btn, #search-next-btn {{
            background: {_COLORS['bg_elevated']};
            color: {_COLORS['text_secondary']};
            margin: 1 1;
        }}

        #store-status, #search-status {{
            color: {_COLORS['success']};
            padding: 0 1;
        }}
        """


__all__ = [
    "HAS_TEXTUAL",
    "SAMPLE_MEMORIES",
    "STEP_DONE",
    "STEP_SEARCH",
    "STEP_STORE",
    "STEP_WELCOME",
    "TOTAL_STEPS",
    "seed_sample_memories",
]
