"""ASCII visualization dashboard for CarryMem memory statistics.

Pure functions that render memory statistics as ASCII/Unicode box-drawn
charts. Designed to be embedded into the TUI StatsPanel or used by the
CLI ``stats`` command. No side effects, no I/O.

The visual vocabulary is intentionally limited to Unicode box-drawing
characters (``\u2500`` family) and geometric symbols (``\u2588``,
``\u2591``) — no emoji — to align with the Morandi low-saturation
aesthetic described in ``docs/design/UI_UX_IMPROVEMENTS_v0.9.0.md``.

Memory dicts are expected to follow :class:`carrymem.types.StoredMemoryDict`
shape (keys: ``type``, ``content``, ``created_at`` ISO datetime string,
...). Malformed dicts are skipped silently so a single bad row never
breaks the whole dashboard.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

# ── Constants ───────────────────────────────────────────────────────────
# Mirror of carrymem.tui._TYPE_ICONS / _TYPE_LABELS — duplicated here so
# the dashboard module stays dependency-free (no import of textual stack).
# If tui.py icons change, update this dict in lockstep.
_TYPE_ICONS: Dict[str, str] = {
    "user_preference": "\u25c6",  # ◆ diamond (preferences)
    "fact_declaration": "\u25c7",  # ◇ hollow diamond (facts)
    "correction": "\u2699",  # ⚙ gear (corrections)
    "decision": "\u25c9",  # ◉ fisheye (decisions)
    "task_pattern": "\u21bb",  # ↻ clockwise arrow (patterns)
    "contextual_observation": "\u2299",  # ⊙ circled dot (observations)
    "knowledge": "\u25a4",  # ▤ square with horizontal fill (knowledge)
    "unknown": "?",  # plain question mark (unknown)
}

_TYPE_LABELS: Dict[str, str] = {
    "user_preference": "Preferences",
    "fact_declaration": "Facts",
    "correction": "Corrections",
    "decision": "Decisions",
    "task_pattern": "Patterns",
    "contextual_observation": "Observations",
    "knowledge": "Knowledge",
    "unknown": "Unknown",
}

# All 8 supported memory types — used for coverage computation.
_ALL_TYPES: Tuple[str, ...] = tuple(_TYPE_LABELS.keys())

# Layout budget — keep every line within 80 cols.
_MAX_WIDTH = 80
_GROWTH_BAR_MAX = 40
_TYPE_BAR_MAX = 30
_HEALTH_BAR_MAX = 10
_HEALTH_BOX_WIDTH = 70

# Box-drawing primitives.
_HLINE = "\u2500"  # ─ light horizontal
_VLINE = "\u2502"  # │ light vertical
_TL = "\u250c"  # ┌ top-left
_TR = "\u2510"  # ┐ top-right
_BL = "\u2514"  # └ bottom-left
_BR = "\u2518"  # ┘ bottom-right
_TEE_R = "\u251c"  # ├ tee right
_TEE_L = "\u2524"  # ┤ tee left
_BAR_FULL = "\u2588"  # █ full block
_BAR_EMPTY = "\u2591"  # ░ light shade
_EMPTY = "No data yet"


# ── Helpers ─────────────────────────────────────────────────────────────
def _parse_created_at(memory: Any) -> datetime | None:
    """Best-effort parse of ``created_at`` to an aware UTC datetime.

    Returns ``None`` if the field is missing or unparseable.
    """
    raw = memory.get("created_at")
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _memory_type(memory: Any) -> str:
    """Return the memory type, normalised to one of the 8 known types."""
    t = memory.get("type")
    if not isinstance(t, str) or not t:
        return "unknown"
    return t if t in _TYPE_LABELS else "unknown"


def _content_hash(memory: Any) -> str:
    """Stable hash of memory content for redundancy detection."""
    content = memory.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


# ── Public API ──────────────────────────────────────────────────────────
def render_growth_chart(memories: List[Any], days: int = 7) -> str:
    """Render ASCII bar chart of memory growth over the last N days.

    Args:
        memories: List of memory dicts with a ``created_at`` ISO datetime.
        days: Number of trailing days to display (default 7). Clamped to
            ``[1, 90]``.

    Returns:
        Multi-line ASCII bar chart string. Returns ``"No data yet"`` if
        the input list is empty or no memory has a parseable date.
    """
    if not memories:
        return _EMPTY

    days = max(1, min(90, int(days)))

    # Bucket counts keyed by YYYY-MM-DD for the trailing ``days`` days.
    today = datetime.now(timezone.utc).date()
    buckets: Dict[str, int] = {}
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        buckets[d.isoformat()] = 0

    for mem in memories:
        if not isinstance(mem, dict):
            continue
        dt = _parse_created_at(mem)
        if dt is None:
            continue
        day_key = dt.date().isoformat()
        if day_key in buckets:
            buckets[day_key] += 1

    # If none of the memories fall in the window, treat as no data.
    if sum(buckets.values()) == 0:
        return _EMPTY

    max_count = max(buckets.values()) or 1
    lines: List[str] = []
    for day_key in sorted(buckets.keys()):
        count = buckets[day_key]
        bar_width = int(round((count / max_count) * _GROWTH_BAR_MAX)) if max_count else 0
        if count > 0 and bar_width == 0:
            bar_width = 1
        bar = _BAR_FULL * bar_width
        lines.append(f"  {day_key} {_VLINE}{bar} {count}")

    return "\n".join(lines)


def render_type_distribution(memories: List[Any]) -> str:
    """Render ASCII horizontal bar chart of memory type distribution.

    Args:
        memories: List of memory dicts with a ``type`` key.

    Returns:
        Multi-line ASCII chart string. Returns ``"No data yet"`` if the
        input list is empty.
    """
    if not memories:
        return _EMPTY

    counts: Dict[str, int] = {t: 0 for t in _ALL_TYPES}
    for mem in memories:
        if not isinstance(mem, dict):
            continue
        counts[_memory_type(mem)] += 1

    total = sum(counts.values())
    if total == 0:
        return _EMPTY

    # Sort by count desc, then by canonical type order for stability.
    sorted_counts = sorted(
        counts.items(),
        key=lambda kv: (-kv[1], _ALL_TYPES.index(kv[0]) if kv[0] in _ALL_TYPES else 99),
    )
    # Only render types that have at least 1 entry.
    rows = [(t, c) for t, c in sorted_counts if c > 0]
    if not rows:
        return _EMPTY

    max_count = rows[0][1]
    # Label column width: icon + space + label, padded.
    label_width = max(len(_TYPE_LABELS[t]) for t, _ in rows) + 2  # icon + space + label

    lines: List[str] = []
    for t, c in rows:
        icon = _TYPE_ICONS.get(t, "?")
        label = _TYPE_LABELS.get(t, t)
        pct = (c / total) * 100
        bar_width = int(round((c / max_count) * _TYPE_BAR_MAX)) if max_count else 0
        if c > 0 and bar_width == 0:
            bar_width = 1
        bar = _BAR_FULL * bar_width
        label_field = f"{icon} {label}".ljust(label_width)
        lines.append(f"  {label_field} {_VLINE}{bar} {pct:5.1f}% ({c})")

    return "\n".join(lines)


def render_health_score(memories: List[Any]) -> str:
    """Render the memory health score dashboard.

    Three sub-metrics are computed:

    * **Coverage** — fraction of the 8 known memory types that have at
      least one entry.
    * **Freshness** — fraction of memories created within the last 30
      days.
    * **Redundancy** — fraction of memories that appear to be duplicates
      (same SHA-1 content hash).

    Overall health = ``(coverage + freshness + (100 - redundancy)) / 3``.

    Args:
        memories: List of memory dicts.

    Returns:
        Multi-line ASCII dashboard string. Returns ``"No data yet"`` if
        the input list is empty.
    """
    if not memories:
        return _EMPTY

    total = 0
    types_seen: set = set()
    fresh_count = 0
    hash_counts: Dict[str, int] = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    for mem in memories:
        if not isinstance(mem, dict):
            continue
        total += 1
        types_seen.add(_memory_type(mem))
        dt = _parse_created_at(mem)
        if dt is not None and dt >= cutoff:
            fresh_count += 1
        hash_counts[_content_hash(mem)] = hash_counts.get(_content_hash(mem), 0) + 1

    if total == 0:
        return _EMPTY

    coverage_pct = (len(types_seen) / len(_ALL_TYPES)) * 100
    freshness_pct = (fresh_count / total) * 100
    duplicate_count = sum(c - 1 for c in hash_counts.values() if c > 1)
    redundancy_pct = (duplicate_count / total) * 100

    overall = (coverage_pct + freshness_pct + (100 - redundancy_pct)) / 3
    overall_int = int(round(overall))

    inner_width = _HEALTH_BOX_WIDTH - 2  # subtract the two side borders

    def _boxed(content: str) -> str:
        """Pad ``content`` to ``inner_width`` and wrap with vertical bars."""
        # content already includes the leading 2-space indent; pad to fit.
        if len(content) >= inner_width:
            content = content[:inner_width]
            padding = ""
        else:
            padding = " " * (inner_width - len(content))
        return f"{_VLINE}{content}{padding}{_VLINE}"

    def _row(label: str, value_pct: float) -> str:
        # value_pct is 0..100; bar shows the value out of 100.
        filled = int(round((value_pct / 100) * _HEALTH_BAR_MAX))
        bar = _BAR_FULL * filled + _BAR_EMPTY * (_HEALTH_BAR_MAX - filled)
        return _boxed(f"  {label:<11}{bar} {value_pct:5.1f}%")

    lines: List[str] = []
    lines.append(f"{_TL}{_HLINE * inner_width}{_TR}")
    lines.append(_boxed(f"  Memory Health Score: {overall_int}/100"))
    lines.append(f"{_TEE_R}{_HLINE * inner_width}{_TEE_L}")
    lines.append(_row("Coverage", coverage_pct))
    lines.append(_row("Freshness", freshness_pct))
    lines.append(_row("Redundancy", redundancy_pct))
    lines.append(f"{_BL}{_HLINE * inner_width}{_BR}")
    return "\n".join(lines)


def render_full_dashboard(memories: List[Any]) -> str:
    """Render the complete dashboard — all three sections combined.

    Args:
        memories: List of memory dicts.

    Returns:
        Multi-line ASCII dashboard string. Each section is preceded by a
        title and a separator line.
    """
    sections: List[Tuple[str, str]] = [
        ("Memory Growth (Last 7 Days)", render_growth_chart(memories)),
        ("Type Distribution", render_type_distribution(memories)),
        ("Health Score", render_health_score(memories)),
    ]

    out: List[str] = []
    title = "CarryMem Memory Dashboard"
    out.append("=" * _MAX_WIDTH)
    out.append(title.center(_MAX_WIDTH))
    out.append("=" * _MAX_WIDTH)
    out.append("")

    for i, (name, body) in enumerate(sections):
        out.append(name)
        out.append(_HLINE * min(len(name) + 4, _MAX_WIDTH))
        for line in body.split("\n"):
            out.append(line)
        if i < len(sections) - 1:
            out.append("")

    return "\n".join(out)
