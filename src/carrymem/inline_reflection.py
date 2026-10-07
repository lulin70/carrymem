"""Inline reflection inspection for the recall path (Phase 5 Slice 5 stage 2/3).

Implements the contract added in
``docs/design/MEMORY_EVOLUTION_BUDGET_v1.2.md`` §11:

* ``InlineReflectionHint`` — structured re-rank hint surfaced alongside a
  recalled candidate (no content leakage, DLP-checked).
* ``HintType`` — closed enum: ``downrank / boost / flag_conflict / stale``.
* ``inspect_candidates_for_hints`` — **pure** inspect function:

    - No DB writes (INV-IR1).
    - No transaction-table touches (we explicitly do **not** call into
      ``ReflectionManager`` from this module — that path is reserved for the
      background proposal lifecycle).
    - No metrics emission (callers are responsible for ``set_recall_budget_utilization``,
      ``record_recall_truncation``, and the new
      ``carrymem_recall_reflection_hints_total`` series).
    - Soft timeout — once ``inline_timeout_ms`` has elapsed the function stops
      inspecting further candidates and reports ``timeout_hit=True``.

Reused gates (zero drift with the legacy paths):

* ``consolidation.find_duplicates`` and ``find_superseded_pairs`` for
  ``flag_conflict`` hints (read-only; we only read the result, never call
  ``consolidate()``'s side-effecting code paths).
* ``layers.memify.find_decay_candidates`` for ``stale`` hints — but to keep
  this module pure we accept the candidate list directly instead of going
  through SQLite. Callers pre-compute the decay-hit set via the adapter.

Why this is separate from ``ReflectionManager``:

    Background reflection (run/proposal lifecycle) is transactional, holds
    ``file_lock``, and writes ``memory_reflection_runs`` / ``memory_reflection_outputs``.
    Those guarantees are correct for the **user-initiated** reflect lifecycle
    but incompatible with the per-recall frequency of the inline path.
    Inline hints never touch those tables (INVT-RR3 mirror) and never hold
    ledger locks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from carrymem.consolidation import find_duplicates, find_superseded_pairs
from carrymem.security.redaction import should_redact

# ---------------------------------------------------------------------------
# Public data contract (v1.2 §11.1 / §11.2)
# ---------------------------------------------------------------------------


class HintType(str, Enum):
    """Closed enum of inline reflection hint categories."""

    DOWNRANK = "downrank"
    BOOST = "boost"
    FLAG_CONFLICT = "flag_conflict"
    STALE = "stale"


#: Maximum length of ``reasoning_short`` (INV-IR2).
MAX_REASONING_LEN = 50

#: Per-call hard cap on the number of hints surfaced to v1 of the response.
#: Defensive against prompt blow-up; v1.2 §5.1 INV-TB4.
MAX_HINTS_PER_RESPONSE = 20

#: Bounds for ``score_delta`` (INV-IR3) — keep aligned with the ranker.
_SCORE_DELTA_MIN = -1.0
_SCORE_DELTA_MAX = 1.0


@dataclass(frozen=True, slots=True)
class InlineReflectionHint:
    """Structured re-rank hint attached to a recalled candidate."""

    storage_key: str
    hint_type: HintType
    confidence: float
    reasoning_short: str
    score_delta: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "storage_key": self.storage_key,
            "hint_type": self.hint_type.value,
            "confidence": self.confidence,
            "reasoning_short": self.reasoning_short,
            "score_delta": self.score_delta,
        }


@dataclass(frozen=True, slots=True)
class InlineReflectionReport:
    """Pure inspect result. Callers translate it into metrics / truncation."""

    hints: Tuple[InlineReflectionHint, ...]
    inspected_count: int
    elapsed_ms: float
    timeout_hit: bool
    capped_count: int  # how many hints were dropped by MAX_HINTS_PER_RESPONSE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hints": [hint.to_dict() for hint in self.hints],
            "inspected_count": self.inspected_count,
            "elapsed_ms": self.elapsed_ms,
            "timeout_hit": self.timeout_hit,
            "capped_count": self.capped_count,
            "hint_total": len(self.hints),
        }


# ---------------------------------------------------------------------------
# Pure inspect entry point (v1.2 §11.3)
# ---------------------------------------------------------------------------


def _clamp_score_delta(value: float) -> float:
    coerced: float
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        coerced = 0.0
    elif value < _SCORE_DELTA_MIN:
        coerced = _SCORE_DELTA_MIN
    elif value > _SCORE_DELTA_MAX:
        coerced = _SCORE_DELTA_MAX
    else:
        coerced = float(value)
    return coerced


def _safe_hint(
    storage_key: str,
    hint_type: HintType,
    confidence: float,
    reasoning_short: str,
    score_delta: float,
) -> Optional[InlineReflectionHint]:
    """Build an ``InlineReflectionHint`` with INV-IR1/IR2/IR5 enforcement."""
    if not isinstance(storage_key, str) or not storage_key:
        return None
    # INV-IR2: length cap
    if len(reasoning_short) > MAX_REASONING_LEN:
        return None
    # DLP — INV-IR5 / INV-TB5
    blocked, _reason = should_redact(reasoning_short)
    if blocked:
        return None
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= confidence_value <= 1.0):
        return None
    try:
        delta_value = _clamp_score_delta(float(score_delta))
    except (TypeError, ValueError):
        return None
    return InlineReflectionHint(
        storage_key=storage_key,
        hint_type=hint_type,
        confidence=confidence_value,
        reasoning_short=reasoning_short,
        score_delta=delta_value,
    )


def _candidate_storage_key(ranked_item: Any) -> str:
    """Extract the storage_key from a ranked item (object/dict)."""
    if hasattr(ranked_item, "memory"):
        memory = ranked_item.memory
        if isinstance(memory, Mapping):
            value = memory.get("storage_key")
            if isinstance(value, str):
                return value
        return ""
    if isinstance(ranked_item, Mapping):
        value = ranked_item.get("storage_key")
        return value if isinstance(value, str) else ""
    return ""


def _candidate_dict(ranked_item: Any) -> Dict[str, Any]:
    """Project a ranked item (RecallItem or dict) into the dict shape
    ``consolidation.find_duplicates`` / ``find_superseded_pairs`` accept.
    """
    if isinstance(ranked_item, Mapping):
        return dict(ranked_item)
    if hasattr(ranked_item, "memory"):
        memory = ranked_item.memory
        if isinstance(memory, Mapping):
            return dict(memory)
    return {}


def inspect_candidates_for_hints(
    ranked: Sequence[Any],
    *,
    inline_max_candidates: int = 50,
    inline_timeout_ms: int = 100,
    stale_keys: Optional[Set[str]] = None,
    now: Optional[datetime] = None,
) -> InlineReflectionReport:
    """Inspect the top-N ranked candidates and surface inline reflection hints.

    Pure function — no DB writes, no metrics emission, no ledger locks. The
    caller (``_execute_recall_plan``) is responsible for translating the report
    into metrics / truncation events.

    Args:
        ranked: ranked candidates (each ``RecallItem`` or dict-like).
        inline_max_candidates: maximum number of candidates inspected
            (``ReflectionBudget.inline_max_candidates``).
        inline_timeout_ms: soft budget in milliseconds; once exceeded we stop
            processing more candidates (already-inspected ones still produce
            their hints).
        stale_keys: pre-computed set of ``storage_key`` matching the shared
            decay gate (``find_decay_candidates``). Passed in to keep this
            function pure; callers obtain it from the adapter.
        now: wall-clock override for deterministic tests.

    Returns:
        ``InlineReflectionReport`` containing hints + inspection metadata.
    """
    if inline_max_candidates < 0:
        inline_max_candidates = 0
    if inline_timeout_ms < 0:
        inline_timeout_ms = 0

    started = time.perf_counter()
    deadline_ms = started * 1000.0 + inline_timeout_ms
    if inline_timeout_ms == 0:
        # Deterministic zero-budget: never enter the loop.
        elapsed_total = (time.perf_counter() - started) * 1000.0
        return InlineReflectionReport(
            hints=(),
            inspected_count=0,
            elapsed_ms=round(elapsed_total, 3),
            timeout_hit=True,
            capped_count=0,
        )

    candidates_to_inspect = list(ranked[:inline_max_candidates])
    raw_hints: List[InlineReflectionHint] = []

    timeout_hit = False
    inspected_count = 0
    candidate_dicts: List[Dict[str, Any]] = []
    for index, ranked_item in enumerate(candidates_to_inspect):
        elapsed_ms = time.perf_counter() * 1000.0
        if elapsed_ms > deadline_ms:
            timeout_hit = True
            break
        inspected_count = index + 1
        storage_key = _candidate_storage_key(ranked_item)
        if not storage_key:
            continue
        candidate_dict = _candidate_dict(ranked_item)
        candidate_dicts.append(candidate_dict)
        raw_hints.extend(
            _hints_for_candidate(
                storage_key,
                candidate_dict,
                stale_keys or set(),
                now=now,
                sibling_dicts=candidate_dicts[:-1],
            )
        )

    elapsed_total = (time.perf_counter() - started) * 1000.0

    hints, capped_count = _truncate_hints(raw_hints)

    return InlineReflectionReport(
        hints=tuple(hints),
        inspected_count=inspected_count,
        elapsed_ms=round(elapsed_total, 3),
        timeout_hit=timeout_hit,
        capped_count=capped_count,
    )


def _hints_for_candidate(
    storage_key: str,
    candidate_dict: Dict[str, Any],
    stale_keys: Set[str],
    *,
    now: Optional[datetime],
    sibling_dicts: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[InlineReflectionHint]:
    """Build hints for a single candidate from the rule set.

    ``sibling_dicts`` is an optional sequence of additional candidate dicts
    pulled from the same ranked window. ``consolidation.find_duplicates`` and
    ``find_superseded_pairs`` need *at least two* inputs to detect a pair —
    we therefore feed [candidate_dict, *sibling_dicts] when checking.
    """
    hints: List[InlineReflectionHint] = []

    # Rule: stale (decay gate)
    if storage_key in stale_keys:
        hint = _safe_hint(
            storage_key,
            HintType.STALE,
            confidence=0.6,
            reasoning_short="matches decay gate",
            score_delta=-0.05,
        )
        if hint is not None:
            hints.append(hint)

    # Rule: conflict (consolidation detection)
    siblings_for_check: Sequence[Dict[str, Any]]
    if sibling_dicts:
        siblings_for_check = [candidate_dict, *(dict(item) for item in sibling_dicts)]
    else:
        siblings_for_check = [candidate_dict]
    duplicate_hint = _detect_conflict_hint(storage_key, candidate_dict, siblings_for_check, now=now)
    if duplicate_hint is not None:
        hints.append(duplicate_hint)

    return hints


def _detect_conflict_hint(
    storage_key: str,
    candidate_dict: Dict[str, Any],
    siblings_for_check: Sequence[Dict[str, Any]],
    *,
    now: Optional[datetime],
) -> Optional[InlineReflectionHint]:
    """Detect (older, newer) conflict using consolidation.find_duplicates /
    find_superseded_pairs over the candidate + ranked-window siblings.

    ``siblings_for_check`` must include ``candidate_dict`` and at least one
    other sibling — ``find_duplicates`` short-circuits on len < 2.

    Returns a flag_conflict hint when the candidate is the **newer** side of
    a duplicate / superseded pair (i.e. the older side is shadowing it).
    """
    if not candidate_dict or len(siblings_for_check) < 2:
        return None
    try:
        duplicates = find_duplicates(list(siblings_for_check), similarity_threshold=0.85)
    except Exception:  # INV-IR5: never propagate from inspect
        return None
    try:
        superseded_pairs = find_superseded_pairs(list(siblings_for_check))
    except Exception:
        return None

    older_sibling: Optional[Dict[str, Any]] = None
    similarity: Optional[float] = None
    # ``find_duplicates`` returns ``(a, b, sim)`` from a flat pair walk —
    # a/b are not labelled newer/older. We pick the OTHER side as the sibling
    # shadowing this candidate.
    for first, second, sim in duplicates:
        if first.get("storage_key") == storage_key:
            older_sibling = second
            similarity = sim
            break
        if second.get("storage_key") == storage_key:
            older_sibling = first
            similarity = sim
            break
    if older_sibling is None:
        # ``find_superseded_pairs`` returns ``(older, newer)`` in that order.
        for older, newer in superseded_pairs:
            if newer.get("storage_key") == storage_key:
                older_sibling = older
                break

    if older_sibling is None:
        return None
    sim_text = f"sim={round(similarity, 2)}" if isinstance(similarity, (int, float)) else "updated"
    return _safe_hint(
        storage_key,
        HintType.FLAG_CONFLICT,
        confidence=0.7,
        reasoning_short=f"older sibling present ({sim_text})",
        score_delta=-0.10,
    )


def _truncate_hints(
    raw_hints: List[InlineReflectionHint],
) -> Tuple[List[InlineReflectionHint], int]:
    """Apply MAX_HINTS_PER_RESPONSE cap deterministically (INV-TB4)."""
    if len(raw_hints) <= MAX_HINTS_PER_RESPONSE:
        return list(raw_hints), 0

    # Deterministic ordering: hint_type priority, then -confidence, then
    # storage_key for stable tie-breaks.
    _priority = {
        HintType.FLAG_CONFLICT: 0,
        HintType.STALE: 1,
        HintType.DOWNRANK: 2,
        HintType.BOOST: 3,
    }

    def sort_key(hint: InlineReflectionHint) -> Tuple[int, float, str]:
        return (_priority.get(hint.hint_type, 99), -hint.confidence, hint.storage_key)

    ordered = sorted(raw_hints, key=sort_key)
    kept = ordered[:MAX_HINTS_PER_RESPONSE]
    dropped = len(raw_hints) - len(kept)
    return kept, dropped


__all__ = [
    "HintType",
    "InlineReflectionHint",
    "InlineReflectionReport",
    "MAX_HINTS_PER_RESPONSE",
    "MAX_REASONING_LEN",
    "inspect_candidates_for_hints",
]
