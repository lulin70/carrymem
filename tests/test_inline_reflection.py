"""Phase 5 Slice 5 stage 2: pre-wiring tests for inline reflection inspection.

Covers the five prerequisites from v1.2 §11 / §7 verification method:

1. **Pure-function invariance** — inspect never touches DB tables (proves we
   are *not* calling ``ReflectionManager`` from the inline path).
2. **DLP enforcement** — content with sensitive substrings never leaks into
   ``reasoning_short``.
3. **Deterministic ordering** — same ranked input → same hint ordering
   (INV-TB3 / INV-TB4).
4. **Soft-timeout correctness** — ``inline_timeout_ms=0`` triggers
   ``timeout_hit=True`` and stops inspection at the right boundary.
5. **Hint count cap** — ``MAX_HINTS_PER_RESPONSE`` truncates with
   deterministic priority (INV-TB4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from carrymem.inline_reflection import (
    MAX_HINTS_PER_RESPONSE,
    MAX_REASONING_LEN,
    HintType,
    InlineReflectionHint,
    InlineReflectionReport,
    inspect_candidates_for_hints,
)

# ---------------------------------------------------------------------------
# Fixtures: a deterministic ranked-candidate factory
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _FakeRanked:
    memory: Dict[str, Any]


def _ranked(key: str, content: str = "hello world", **extra: Any) -> _FakeRanked:
    payload = {
        "storage_key": key,
        "content": content,
        "type": "personal_fact",
        "confidence": 0.8,
        "created_at": "2026-01-01T00:00:00+00:00",
        "superseded_at": None,
        "access_count": 1,
    }
    payload.update(extra)
    return _FakeRanked(memory=payload)


# ---------------------------------------------------------------------------
# 1. Pure-function invariance — no DB or metrics side effects
# ---------------------------------------------------------------------------


def test_inspect_is_pure_no_db_no_metrics(monkeypatch):
    """Inspect must not call into ``ReflectionManager`` or emit metrics.

    Static guarantee — inspect's *import graph* must not couple to the
    transactional ``ReflectionManager`` (the historical mistake the v1.2 §10.5
    defect #3 warned about). We check the import surface, not the docstring,
    because the docstring intentionally names ``ReflectionManager`` to explain
    what we deliberately avoid.
    """
    from carrymem import inline_reflection as ir

    # No write counter should bump during a pure call.
    from carrymem.monitoring import get_metrics_collector

    collector = get_metrics_collector()
    snapshots_before = _snapshot_counters(collector)

    candidates = [
        _ranked("k1", content="unique note alpha"),
        _ranked("k2", content="unique note beta"),
    ]
    report = inspect_candidates_for_hints(candidates, inline_max_candidates=10, inline_timeout_ms=1000)

    snapshots_after = _snapshot_counters(collector)
    assert snapshots_before == snapshots_after, "inspect must not emit metrics"

    # Static: ``inspect_candidates_for_hints`` must not touch any module
    # path containing ``reflection.py`` (the file holding ``ReflectionManager``).
    # We assert the *callable's* source does not import reflection.
    import inspect

    src = inspect.getsource(ir.inspect_candidates_for_hints)
    assert "ReflectionManager" not in src, "inspect_candidates_for_hints must not reference ReflectionManager"
    assert "memory_reflection_runs" not in src
    assert "memory_reflection_outputs" not in src

    # And the report itself must not contain any DB-write surface.
    assert isinstance(report, InlineReflectionReport)


def _snapshot_counters(collector) -> Dict[str, int]:
    """Return a stable dict of every counter the collector knows about."""
    counters = getattr(collector, "_counters", None)
    if isinstance(counters, dict):
        return {key: int(value) for key, value in counters.items()}
    return {}


# ---------------------------------------------------------------------------
# 2. Deterministic ordering (INV-TB3 / INV-TB4)
# ---------------------------------------------------------------------------


def test_inspect_is_deterministic_for_same_input():
    ranked = [
        _ranked("alpha", content="dark mode preference"),
        _ranked("beta", content="dark mode preference"),
        _ranked("gamma", content="totally unrelated note"),
    ]
    first = inspect_candidates_for_hints(ranked, inline_max_candidates=10, inline_timeout_ms=1000)
    second = inspect_candidates_for_hints(ranked, inline_max_candidates=10, inline_timeout_ms=1000)
    # Compare the deterministic fields only — ``elapsed_ms`` is wall-clock.
    assert first.hints == second.hints
    assert first.inspected_count == second.inspected_count
    assert first.timeout_hit == second.timeout_hit
    assert first.capped_count == second.capped_count


# ---------------------------------------------------------------------------
# 3. Soft-timeout correctness
# ---------------------------------------------------------------------------


def test_inspect_reports_timeout_when_budget_exhausted():
    """``inline_timeout_ms=0`` triggers ``timeout_hit=True`` and stops inspecting."""
    ranked = [_ranked(f"k{i}") for i in range(50)]
    report = inspect_candidates_for_hints(ranked, inline_max_candidates=50, inline_timeout_ms=0)
    assert report.timeout_hit is True
    # Zero-budget short-circuits before the loop — no candidates inspected.
    assert report.inspected_count == 0
    assert report.elapsed_ms >= 0


def test_inspect_completes_normally_with_generous_timeout():
    ranked = [_ranked(f"k{i}") for i in range(5)]
    report = inspect_candidates_for_hints(ranked, inline_max_candidates=5, inline_timeout_ms=10_000)
    assert report.timeout_hit is False
    assert report.inspected_count == 5


# ---------------------------------------------------------------------------
# 4. Hint count cap (INV-TB4)
# ---------------------------------------------------------------------------


def test_hint_count_is_capped_at_max_per_response():
    """``MAX_HINTS_PER_RESPONSE`` truncates deterministically by priority."""
    stale_keys = {f"k{i}" for i in range(MAX_HINTS_PER_RESPONSE + 5)}
    # Each candidate has unique content so we don't accidentally trigger
    # conflict hints — only stale hints.
    ranked = [
        _ranked(f"k{i}", content=f"unique note number {i} for cap test") for i in range(MAX_HINTS_PER_RESPONSE + 5)
    ]
    report = inspect_candidates_for_hints(
        ranked,
        inline_max_candidates=MAX_HINTS_PER_RESPONSE + 5,
        inline_timeout_ms=10_000,
        stale_keys=stale_keys,
    )
    assert len(report.hints) == MAX_HINTS_PER_RESPONSE
    assert report.capped_count == 5


# ---------------------------------------------------------------------------
# 5. DLP enforcement (INV-IR5 / INV-TB5)
# ---------------------------------------------------------------------------


def test_inspect_does_not_leak_pii_into_reasoning_short():
    """A reasoning string containing an API-key-like substring must be dropped.

    We can't directly seed ``should_redact`` with a memory content value, but
    we *can* prove the safe-builder drops a hint when ``should_redact`` flags
    its ``reasoning_short``. We exercise this through the contract unit
    tests below.
    """
    # First a control: reasoning_short without sensitive substrings must surface
    # in the report.
    ranked = [_ranked("solo", content="dark mode preference")]
    report = inspect_candidates_for_hints(
        ranked,
        inline_max_candidates=1,
        inline_timeout_ms=10_000,
        stale_keys={"solo"},
    )
    # The candidate alone is not a duplicate of anything else, so the only
    # hint should be the stale one. reasoning_short must NOT contain the
    # original content (which is "dark mode preference").
    for hint in report.hints:
        assert "dark mode preference" not in hint.reasoning_short
        assert hint.reasoning_short == "matches decay gate"


# ---------------------------------------------------------------------------
# 6. DLP fail-closed for unsafe reasoning_short (helper-level)
# ---------------------------------------------------------------------------


def test_safe_hint_drops_oversized_or_sensitive_reasoning():
    """Direct unit on the safe-builder covering INV-IR2 / INV-IR5."""
    from carrymem.inline_reflection import _safe_hint

    # Length cap (INV-IR2)
    assert (
        _safe_hint(
            "k1",
            HintType.STALE,
            confidence=0.5,
            reasoning_short="x" * (MAX_REASONING_LEN + 1),
            score_delta=0.0,
        )
        is None
    )

    # Empty storage_key
    assert (
        _safe_hint(
            "",
            HintType.STALE,
            confidence=0.5,
            reasoning_short="ok",
            score_delta=0.0,
        )
        is None
    )

    # Out-of-range confidence
    assert (
        _safe_hint(
            "k1",
            HintType.STALE,
            confidence=1.5,
            reasoning_short="ok",
            score_delta=0.0,
        )
        is None
    )

    # DLP — must drop when should_redact flags it.
    assert (
        _safe_hint(
            "k1",
            HintType.STALE,
            confidence=0.5,
            reasoning_short="sk-abcdef0123456789abcdef0123456789",
            score_delta=0.0,
        )
        is None
    )


# ---------------------------------------------------------------------------
# 7. Stale hint surfaces when storage_key matches decay gate
# ---------------------------------------------------------------------------


def test_stale_hint_emitted_for_decayed_candidates():
    # Unique content so no conflict hints pollute the assertion.
    ranked = [
        _ranked("stale1", content="unique stale one"),
        _ranked("fresh1", content="unique fresh one"),
    ]
    report = inspect_candidates_for_hints(
        ranked,
        inline_max_candidates=2,
        inline_timeout_ms=10_000,
        stale_keys={"stale1"},
    )
    stale_hints = [h for h in report.hints if h.hint_type is HintType.STALE]
    assert len(stale_hints) == 1
    assert stale_hints[0].storage_key == "stale1"
    assert stale_hints[0].score_delta == -0.05


# ---------------------------------------------------------------------------
# 8. Conflict hint surfaces for newer-sibling duplicates
# ---------------------------------------------------------------------------


def test_conflict_hint_emitted_when_older_sibling_present():
    older = {
        "storage_key": "older_k",
        "content": "the office wifi password is hidden",
        "type": "personal_fact",
        "confidence": 0.9,
        "created_at": "2026-01-01T00:00:00+00:00",
        "superseded_at": None,
        "access_count": 5,
    }
    newer = {
        "storage_key": "newer_k",
        "content": "the office wifi password is hidden",
        "type": "personal_fact",
        "confidence": 0.9,
        "created_at": "2026-06-01T00:00:00+00:00",
        "superseded_at": None,
        "access_count": 0,
    }
    # Order matters: older comes first so when newer is inspected it sees
    # the older in ``sibling_dicts`` and surfaces a conflict hint about itself.
    ranked = [_FakeRanked(memory=older), _FakeRanked(memory=newer)]
    report = inspect_candidates_for_hints(ranked, inline_max_candidates=2, inline_timeout_ms=10_000)
    flag_hints = [h for h in report.hints if h.hint_type is HintType.FLAG_CONFLICT]
    assert len(flag_hints) == 1
    assert flag_hints[0].storage_key == "newer_k"
    assert "older sibling present" in flag_hints[0].reasoning_short
    assert flag_hints[0].score_delta == -0.10


# ---------------------------------------------------------------------------
# 9. INV-IR1: hint must reference a real candidate key
# ---------------------------------------------------------------------------


def test_inspect_ignores_candidates_without_storage_key():
    no_key = _FakeRanked(memory={"content": "no key here"})
    with_key = _ranked("ok", content="dark mode")
    report = inspect_candidates_for_hints([no_key, with_key], inline_max_candidates=2, inline_timeout_ms=10_000)
    for hint in report.hints:
        assert hint.storage_key  # non-empty (INV-IR1)


# ---------------------------------------------------------------------------
# 10. Capped_count is zero when under the cap
# ---------------------------------------------------------------------------


def test_capped_count_is_zero_under_limit():
    # Unique content per candidate — no accidental conflict hints.
    ranked = [
        _ranked("k0", content="alpha unique note"),
        _ranked("k1", content="beta unique note"),
        _ranked("k2", content="gamma unique note"),
    ]
    report = inspect_candidates_for_hints(
        ranked,
        inline_max_candidates=3,
        inline_timeout_ms=10_000,
        stale_keys={"k0", "k1", "k2"},
    )
    assert report.capped_count == 0
    assert len(report.hints) == 3


# ---------------------------------------------------------------------------
# 11. Hint counters: dedicated low-cardinality registry + Prometheus export
#     (v1.2 §8 — Slice 5b closes the dotted-name ghost: the series must be
#     carrymem_recall_reflection_hints_total{hint_type=...}, not a generic
#     carrymem_total{operation=...} line.)
# ---------------------------------------------------------------------------


def test_hint_counter_records_and_exports_prometheus_series():
    from carrymem.monitoring import get_metrics_collector

    collector = get_metrics_collector()
    collector.reset()
    collector.record_recall_reflection_hint("stale")
    collector.record_recall_reflection_hint("stale")
    collector.record_recall_reflection_hint("flag_conflict", count=3)

    snapshot = collector.get_snapshot()
    assert snapshot["recall_reflection_hints"] == {"stale": 2, "flag_conflict": 3}

    body = collector.to_prometheus()
    assert "# TYPE carrymem_recall_reflection_hints_total counter" in body
    assert 'carrymem_recall_reflection_hints_total{hint_type="stale"} 2' in body
    assert 'carrymem_recall_reflection_hints_total{hint_type="flag_conflict"} 3' in body
    # The dotted-name ghost must never reappear in the generic counters.
    assert not any("reflection_hints" in op for op in snapshot["counters"])


def test_hint_counter_fails_closed_on_unknown_type_or_bad_count():
    from carrymem.monitoring import get_metrics_collector

    collector = get_metrics_collector()
    with pytest.raises(ValueError):
        collector.record_recall_reflection_hint("nonexistent_type")
    with pytest.raises(ValueError):
        collector.record_recall_reflection_hint("stale", count=0)
    with pytest.raises(ValueError):
        collector.record_recall_reflection_hint("stale", count=-1)


# ---------------------------------------------------------------------------
# 12. Executor-shaped ranked entries (Slice 5b regression guard)
#     The plan executor passes ``(mode_name, memory, modes)`` tuples — the
#     inspector must project them, not silently skip them (the original
#     wiring produced zero hints end-to-end because only object/dict shapes
#     were recognized).
# ---------------------------------------------------------------------------


def test_executor_tuple_shape_candidates_produce_hints():
    older = {
        "storage_key": "tuple_older",
        "content": "the staging db password rotates monthly",
        "type": "personal_fact",
        "confidence": 0.9,
        "created_at": "2026-01-01T00:00:00+00:00",
        "superseded_at": None,
        "access_count": 5,
    }
    newer = {
        "storage_key": "tuple_newer",
        "content": "the staging db password rotates monthly",
        "type": "personal_fact",
        "confidence": 0.9,
        "created_at": "2026-06-01T00:00:00+00:00",
        "superseded_at": None,
        "access_count": 0,
    }
    # Real executor shape: (mode_name, memory, modes_tuple).
    ranked = [("fts", older, ("fts",)), ("fts", newer, ("fts",))]
    report = inspect_candidates_for_hints(ranked, inline_max_candidates=2, inline_timeout_ms=10_000)
    assert report.inspected_count == 2
    flag_hints = [h for h in report.hints if h.hint_type is HintType.FLAG_CONFLICT]
    assert len(flag_hints) == 1
    assert flag_hints[0].storage_key == "tuple_newer"
