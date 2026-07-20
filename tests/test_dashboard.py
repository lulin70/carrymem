"""Tests for ``carrymem.ui.dashboard`` (P2-P4: Health dashboard visualization).

Verifies the four public render functions:

* ``render_growth_chart``      — daily growth bar chart
* ``render_type_distribution`` — type distribution horizontal bar chart
* ``render_health_score``      — coverage/freshness/redundancy dashboard
* ``render_full_dashboard``    — combined dashboard

Test invariants enforced:

1. Empty input returns ``"No data yet"``.
2. Malformed memory dicts are skipped gracefully (no exceptions).
3. No emoji characters appear in any output.
4. No line exceeds 80 characters.
5. Output is pure (no I/O, deterministic for fixed inputs).
"""

import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone

# Ensure src is on path — same convention as tests/test_themes.py.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.ui.dashboard import (  # noqa: E402  (after sys.path tweak)
    render_full_dashboard,
    render_growth_chart,
    render_health_score,
    render_type_distribution,
)


# ── Helpers ───────────────────────────────────────────────────────────
def _mem(type_: str, content: str, days_ago: int = 0) -> dict:
    """Build a minimal memory dict ``days_ago`` in the past."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "type": type_,
        "content": content,
        "created_at": dt.isoformat(),
    }


# Emoji ranges we never want to see in dashboard output.  These cover the
# emoticons, miscellaneous symbols and dingbats, and the supplemental
# emoji planes.  Allowed text symbols (◆◇⚙◉↻⊙▤) live in U+2500/U+25A0/
# U+2299/U+21BB — none of those ranges overlap with the patterns below.
_EMOJI_PATTERNS = [
    re.compile(r"[\U0001F300-\U0001FAFF]"),  # symbols & pictographs
    re.compile(r"[\U0001F600-\U0001F64F]"),  # emoticons
    re.compile(r"[\U0001F680-\U0001F6FF]"),  # transport & map
    re.compile(r"[\U0001F900-\U0001F9FF]"),  # supplemental symbols
    re.compile(r"[\u2600-\u26FF]"),  # miscellaneous symbols (excludes ⚙ at U+2699? — see below)
    re.compile(r"[\u2700-\u27BF]"),  # dingbats
]

# ⚙ (U+2699) lives in the misc-symbols block but is explicitly allowed
# (it's a text gear symbol, not an emoji, per the design doc).  We patch
# the misc-symbols regex to exclude it.
_MISC_NO_GEAR = re.compile(r"[\u2600-\u2698\u269A-\u26FF]")
_EMOJI_PATTERNS[-2] = _MISC_NO_GEAR

# Specific emoji explicitly called out in P0-C1 of the design doc —
# these MUST NOT appear anywhere in the dashboard output.
_BANNED_EMOJI = "⭐📌🔧🎯🔄👁📚💡❓"


def _assert_no_emoji(testcase: unittest.TestCase, text: str) -> None:
    for pat in _EMOJI_PATTERNS:
        m = pat.search(text)
        if m is not None:
            testcase.fail(f"Found emoji {m.group()!r} (U+{ord(m.group()):04X}) in output:\n{text}")
    for ch in _BANNED_EMOJI:
        if ch in text:
            testcase.fail(f"Banned emoji {ch!r} found in output:\n{text}")


def _assert_max_width(testcase: unittest.TestCase, text: str, limit: int = 80) -> None:
    for i, line in enumerate(text.split("\n")):
        testcase.assertLessEqual(
            len(line),
            limit,
            f"Line {i} exceeds {limit} chars (got {len(line)}): {line!r}",
        )


# ── render_growth_chart ───────────────────────────────────────────────
class TestRenderGrowthChart(unittest.TestCase):
    def test_empty_list_returns_no_data(self) -> None:
        self.assertEqual(render_growth_chart([]), "No data yet")

    def test_three_days_three_bars(self) -> None:
        mems = [
            _mem("user_preference", "a", days_ago=0),
            _mem("user_preference", "b", days_ago=0),
            _mem("fact_declaration", "c", days_ago=1),
            _mem("decision", "d", days_ago=2),
        ]
        out = render_growth_chart(mems, days=3)
        lines = [ln for ln in out.split("\n") if ln.strip()]
        # 3 buckets → 3 bar lines.
        self.assertEqual(len(lines), 3)
        # Today should have 2 memories.
        today_line = lines[-1]
        self.assertIn(" 2", today_line)

    def test_default_days_is_seven(self) -> None:
        mems = [_mem("user_preference", "a", days_ago=0)]
        out = render_growth_chart(mems)
        lines = [ln for ln in out.split("\n") if ln.strip()]
        self.assertEqual(len(lines), 7)

    def test_ignores_memories_outside_window(self) -> None:
        mems = [_mem("user_preference", "old", days_ago=30)]
        out = render_growth_chart(mems, days=7)
        self.assertEqual(out, "No data yet")

    def test_handles_malformed_memories(self) -> None:
        mems = [
            {"type": "user_preference"},  # missing created_at
            {"created_at": "2026-07-14T12:00:00+00:00"},  # missing type
            "not a dict",  # not a dict
            None,
            _mem("user_preference", "ok", days_ago=0),
        ]
        out = render_growth_chart(mems, days=3)
        # Should not raise, should produce a chart with at least one bar.
        self.assertNotEqual(out, "No data yet")
        self.assertIn("█", out)

    def test_malformed_date_skipped(self) -> None:
        mems = [
            {"type": "user_preference", "content": "x", "created_at": "not-a-date"},
            _mem("user_preference", "ok", days_ago=0),
        ]
        out = render_growth_chart(mems, days=3)
        self.assertNotEqual(out, "No data yet")

    def test_no_emoji(self) -> None:
        mems = [_mem("user_preference", "a", days_ago=0)]
        _assert_no_emoji(self, render_growth_chart(mems))

    def test_max_width_80(self) -> None:
        # 100 memories today — maximum bar width scenario.
        mems = [_mem("user_preference", f"c{i}", days_ago=0) for i in range(100)]
        _assert_max_width(self, render_growth_chart(mems))


# ── render_type_distribution ─────────────────────────────────────────
class TestRenderTypeDistribution(unittest.TestCase):
    def test_empty_list_returns_no_data(self) -> None:
        self.assertEqual(render_type_distribution([]), "No data yet")

    def test_correct_percentages(self) -> None:
        mems = [
            _mem("user_preference", "p1"),
            _mem("user_preference", "p2"),
            _mem("fact_declaration", "f1"),
            _mem("decision", "d1"),
        ]
        out = render_type_distribution(mems)
        # 50% preferences, 25% facts, 25% decisions.
        self.assertIn("50.0%", out)
        self.assertIn("25.0%", out)
        # Counts in parentheses.
        self.assertIn("(2)", out)
        self.assertIn("(1)", out)

    def test_uses_type_icons(self) -> None:
        mems = [_mem("user_preference", "p1")]
        out = render_type_distribution(mems)
        self.assertIn("\u25c6", out)  # ◆

    def test_unknown_type_normalised(self) -> None:
        mems = [
            {"type": "made_up_type", "content": "x", "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        out = render_type_distribution(mems)
        self.assertIn("?", out)  # unknown icon

    def test_handles_malformed_memories(self) -> None:
        mems = [
            "not a dict",
            None,
            {"content": "x"},  # missing type
            _mem("user_preference", "ok"),
        ]
        out = render_type_distribution(mems)
        self.assertNotEqual(out, "No data yet")
        self.assertIn("Preferences", out)

    def test_sorted_by_count_desc(self) -> None:
        mems = (
            [_mem("user_preference", f"p{i}") for i in range(5)]
            + [_mem("fact_declaration", f"f{i}") for i in range(3)]
            + [_mem("decision", f"d{i}") for i in range(1)]
        )
        out = render_type_distribution(mems)
        lines = [ln for ln in out.split("\n") if ln.strip()]
        # First non-empty line should be Preferences (count 5).
        self.assertIn("Preferences", lines[0])
        self.assertIn("Facts", lines[1])
        self.assertIn("Decisions", lines[2])

    def test_no_emoji(self) -> None:
        mems = [_mem("user_preference", "p1"), _mem("fact_declaration", "f1")]
        _assert_no_emoji(self, render_type_distribution(mems))

    def test_max_width_80(self) -> None:
        mems = [
            _mem(t, f"c{i}")
            for t in [
                "user_preference",
                "fact_declaration",
                "correction",
                "decision",
                "task_pattern",
                "contextual_observation",
                "knowledge",
            ]
            for i in range(50)
        ]
        _assert_max_width(self, render_type_distribution(mems))


# ── render_health_score ──────────────────────────────────────────────
class TestRenderHealthScore(unittest.TestCase):
    def test_empty_list_returns_no_data(self) -> None:
        self.assertEqual(render_health_score([]), "No data yet")

    def test_high_score_with_good_coverage(self) -> None:
        # All 8 types, fresh, no duplicates → score near 100.
        types = [
            "user_preference",
            "fact_declaration",
            "correction",
            "decision",
            "task_pattern",
            "contextual_observation",
            "knowledge",
            "unknown",
        ]
        mems = [_mem(t, f"unique-{i}", days_ago=0) for i, t in enumerate(types)]
        out = render_health_score(mems)
        # Find the score line.
        score_line = next((ln for ln in out.split("\n") if "Memory Health Score:" in ln), None)
        self.assertIsNotNone(score_line, f"Score line not found in:\n{out}")
        # Extract integer score.
        m = re.search(r"(\d+)/100", score_line)
        self.assertIsNotNone(m)
        score = int(m.group(1))
        self.assertGreaterEqual(score, 90, f"Expected high score, got {score}:\n{out}")

    def test_low_coverage_lowers_score(self) -> None:
        # Only 1 type, fresh, no duplicates.
        mems = [_mem("user_preference", f"u-{i}", days_ago=0) for i in range(5)]
        out = render_health_score(mems)
        score_line = next(ln for ln in out.split("\n") if "Memory Health Score:" in ln)
        m = re.search(r"(\d+)/100", score_line)
        score = int(m.group(1))
        # Coverage = 1/8 = 12.5%, freshness = 100%, redundancy = 0%.
        # Overall = (12.5 + 100 + 100) / 3 ≈ 70.8 → 71.
        self.assertLess(score, 80, f"Expected reduced score, got {score}:\n{out}")

    def test_redundancy_shown(self) -> None:
        # 2 identical memories → 1 duplicate out of 2 total = 50% redundancy.
        mems = [
            _mem("user_preference", "same content", days_ago=0),
            _mem("user_preference", "same content", days_ago=0),
        ]
        out = render_health_score(mems)
        self.assertIn("Redundancy", out)
        # Find the Redundancy row and verify the percentage.
        redundancy_line = next(ln for ln in out.split("\n") if "Redundancy" in ln)
        self.assertIn("50.0%", redundancy_line)

    def test_freshness_with_old_memory(self) -> None:
        # 1 fresh, 1 old (60 days) → freshness = 50%.
        mems = [
            _mem("user_preference", "fresh", days_ago=0),
            _mem("user_preference", "old", days_ago=60),
        ]
        out = render_health_score(mems)
        freshness_line = next(ln for ln in out.split("\n") if "Freshness" in ln)
        self.assertIn("50.0%", freshness_line)

    def test_box_drawing_chars(self) -> None:
        mems = [_mem("user_preference", "x")]
        out = render_health_score(mems)
        # Top border, bottom border, side bars.
        self.assertIn("\u250c", out)  # ┌
        self.assertIn("\u2510", out)  # ┐
        self.assertIn("\u2514", out)  # └
        self.assertIn("\u2518", out)  # ┘
        self.assertIn("\u2502", out)  # │

    def test_handles_malformed_memories(self) -> None:
        mems = [
            "not a dict",
            None,
            {"type": "user_preference"},  # missing created_at/content
            _mem("user_preference", "ok"),
        ]
        # Should not raise.
        out = render_health_score(mems)
        self.assertIn("Memory Health Score:", out)

    def test_no_emoji(self) -> None:
        mems = [_mem("user_preference", "x")]
        _assert_no_emoji(self, render_health_score(mems))

    def test_max_width_80(self) -> None:
        types = [
            "user_preference",
            "fact_declaration",
            "correction",
            "decision",
            "task_pattern",
            "contextual_observation",
            "knowledge",
            "unknown",
        ]
        mems = [_mem(t, f"u-{i}", days_ago=0) for i, t in enumerate(types)]
        _assert_max_width(self, render_health_score(mems))


# ── render_full_dashboard ────────────────────────────────────────────
class TestRenderFullDashboard(unittest.TestCase):
    def _sample_memories(self) -> list:
        types = [
            "user_preference",
            "fact_declaration",
            "correction",
            "decision",
            "task_pattern",
            "contextual_observation",
            "knowledge",
            "unknown",
        ]
        mems = []
        for i, t in enumerate(types):
            for j in range(i + 1):  # increasing counts per type
                mems.append(_mem(t, f"{t}-{j}", days_ago=min(j, 6)))
        return mems

    def test_contains_all_three_section_titles(self) -> None:
        out = render_full_dashboard(self._sample_memories())
        self.assertIn("Memory Growth (Last 7 Days)", out)
        self.assertIn("Type Distribution", out)
        self.assertIn("Health Score", out)

    def test_contains_dashboard_title(self) -> None:
        out = render_full_dashboard(self._sample_memories())
        self.assertIn("CarryMem Memory Dashboard", out)

    def test_empty_input_handled(self) -> None:
        # Even with empty input, the section titles should still be there.
        out = render_full_dashboard([])
        self.assertIn("Memory Growth (Last 7 Days)", out)
        self.assertIn("Type Distribution", out)
        self.assertIn("Health Score", out)
        self.assertIn("No data yet", out)

    def test_no_emoji(self) -> None:
        out = render_full_dashboard(self._sample_memories())
        _assert_no_emoji(self, out)

    def test_max_width_80(self) -> None:
        out = render_full_dashboard(self._sample_memories())
        _assert_max_width(self, out)


# ── Pure-function / determinism ──────────────────────────────────────
class TestPurityAndDeterminism(unittest.TestCase):
    def test_growth_chart_deterministic_same_input(self) -> None:
        mems = [_mem("user_preference", "x", days_ago=0)]
        a = render_growth_chart(mems, days=3)
        b = render_growth_chart(mems, days=3)
        # The today line count is 1 in both; the date prefix will match.
        self.assertEqual(a, b)

    def test_type_distribution_deterministic(self) -> None:
        mems = [
            _mem("user_preference", "a"),
            _mem("fact_declaration", "b"),
        ]
        a = render_type_distribution(mems)
        b = render_type_distribution(mems)
        self.assertEqual(a, b)

    def test_no_io(self) -> None:
        # Calling the functions with empty list should not raise and should
        # not touch the filesystem (we can't easily assert "no I/O" but we
        # can at least verify they don't import anything surprising at
        # call-time).
        render_growth_chart([])
        render_type_distribution([])
        render_health_score([])
        render_full_dashboard([])
        # If we got here, no exceptions were raised.


if __name__ == "__main__":
    unittest.main()
