"""CarryMem CLI - Unified output formatting with rich library.

P0-C2: Provides colored output, tables, and progress indicators.
P0-T2: Color-blind friendly shape symbols (✓/▲/✗/ℹ) paired with colors.

Falls back to plain ``print()`` when ``rich`` is not installed, so the CLI
remains usable in minimal environments.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Tuple

__all__ = ["OutputFormatter", "formatter", "HAS_RICH"]

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    HAS_RICH = True
except ImportError:  # pragma: no cover - exercised via fallback tests
    HAS_RICH = False
    Console = None  # type: ignore[assignment, misc]
    Panel = None  # type: ignore[assignment, misc]
    Progress = None  # type: ignore[assignment, misc]
    SpinnerColumn = None  # type: ignore[assignment, misc]
    TextColumn = None  # type: ignore[assignment, misc]
    Table = None  # type: ignore[assignment, misc]


class OutputFormatter:
    """Unified CLI output formatting with the rich library.

    Color-blind friendly symbols (P0-T2):
    - success: ``✓`` (checkmark) + green
    - warning: ``▲`` (triangle) + yellow
    - error:   ``✗`` (cross) + red
    - info:    ``ℹ`` (circle-i) + blue

    When ``rich`` is unavailable, falls back to plain ``print()`` so the
    content of every message is preserved (only styling is lost).
    """

    _SUCCESS_SYMBOL = "\u2713"  # ✓
    _WARNING_SYMBOL = "\u25b2"  # ▲
    _ERROR_SYMBOL = "\u2717"  # ✗
    _INFO_SYMBOL = "\u2139"  # ℹ

    def __init__(self) -> None:
        self._console: Any = Console() if HAS_RICH else None

    @property
    def console(self) -> Any:
        """Underlying rich Console (or None when rich is unavailable)."""
        return self._console

    def success(self, message: str) -> None:
        """Green success with ``✓`` symbol."""
        if HAS_RICH:
            self._console.print(f"[green]{self._SUCCESS_SYMBOL}[/green] {message}")
        else:
            print(f"  {self._SUCCESS_SYMBOL} {message}")

    def warning(self, message: str) -> None:
        """Yellow warning with ``▲`` symbol."""
        if HAS_RICH:
            self._console.print(f"[yellow]{self._WARNING_SYMBOL}[/yellow] {message}")
        else:
            print(f"  {self._WARNING_SYMBOL} {message}")

    def error(self, code: str, message: str, hint: Optional[str] = None) -> None:
        """Red error box with ``✗`` symbol, code, message, and optional hint."""
        if HAS_RICH:
            lines = [f"[red]{self._ERROR_SYMBOL} ERROR[/red] [{code}] {message}"]
            if hint:
                lines.append(f"  Hint: {hint}")
            self._console.print(Panel("\n".join(lines), border_style="red"))
        else:
            print(f"  {self._ERROR_SYMBOL} ERROR [{code}] {message}")
            if hint:
                print(f"    Hint: {hint}")

    def info(self, message: str) -> None:
        """Blue info with ``ℹ`` symbol."""
        if HAS_RICH:
            self._console.print(f"[blue]{self._INFO_SYMBOL}[/blue] {message}")
        else:
            print(f"  {self._INFO_SYMBOL} {message}")

    def table(
        self,
        headers: List[str],
        rows: List[List[str]],
        title: Optional[str] = None,
    ) -> None:
        """Render a formatted table.

        Falls back to aligned plain-text columns when rich is unavailable so
        the same data is still readable.
        """
        if HAS_RICH:
            t = Table(title=title)
            for h in headers:
                t.add_column(h)
            for row in rows:
                t.add_row(*[str(cell) for cell in row])
            self._console.print(t)
        else:
            if title:
                print(f"  {title}")
            if not headers:
                return
            widths = [len(h) for h in headers]
            for row in rows:
                for i, cell in enumerate(row):
                    if i < len(widths):
                        widths[i] = max(widths[i], len(str(cell)))
            fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
            print(fmt.format(*headers))
            print(fmt.format(*["-" * w for w in widths]))
            for row in rows:
                padded = list(row) + [""] * (len(headers) - len(row))
                print(fmt.format(*[str(c) for c in padded[: len(headers)]]))

    @contextmanager
    def progress(self, description: str) -> Iterator[Tuple[Any, Any]]:
        """Context manager for long operations with a spinner.

        Yields ``(progress_obj, task_id)``. When rich is unavailable the
        context manager simply prints the description once and yields
        ``(None, None)`` — callers should advance the task defensively.
        """
        if HAS_RICH:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self._console,
            ) as prog:
                task = prog.add_task(description, total=None)
                yield prog, task
        else:
            print(f"  {description}...")
            yield None, None


# Singleton instance used across the CLI
formatter = OutputFormatter()
