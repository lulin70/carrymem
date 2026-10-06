"""Pure Phase 5 recall planning contracts.

The planner is deliberately side-effect free. It validates the security scope
and produces an immutable plan that later recall stages can execute.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence, Tuple

from carrymem.exceptions import ValidationError
from carrymem.security import validate_namespace


class RetrievalMode(str, Enum):
    """Supported candidate retrieval paths."""

    FTS = "fts"
    VECTOR = "vector"
    GRAPH = "graph"
    TIME = "time"
    SEMANTIC = "semantic"


class TaskMode(str, Enum):
    """Closed set of task-specific recall policies."""

    PREFERENCE_FOLLOWING = "preference_following"
    CORRECTION_RESOLUTION = "correction_resolution"
    PROJECT_CONTEXT = "project_context"
    FACT_LOOKUP = "fact_lookup"
    TIMELINE_REVIEW = "timeline_review"
    RULE_APPLICATION = "rule_application"
    CONFLICT_EXPLANATION = "conflict_explanation"


class ConflictPolicy(str, Enum):
    """Conflict presentation policy."""

    HIDE = "hide"
    SHOW_TOP = "show_top"
    ALWAYS = "always"


class SensitivityPolicy(str, Enum):
    """Sensitivity filtering policy for a recall plan."""

    FILTER = "filter"
    STRICT = "strict"


@dataclass(frozen=True, slots=True)
class RetrievalBudget:
    """Budget for candidate retrieval."""

    max_candidates: int = 100
    graph_max_hops: int = 2
    retrieval_timeout_ms: int = 200

    def __post_init__(self) -> None:
        _require_non_negative("retrieval.max_candidates", self.max_candidates)
        _require_non_negative("retrieval.graph_max_hops", self.graph_max_hops)
        _require_non_negative("retrieval.retrieval_timeout_ms", self.retrieval_timeout_ms)
        if self.max_candidates == 0:
            raise ValueError("retrieval.max_candidates must be greater than zero")


@dataclass(frozen=True, slots=True)
class EvidenceBudget:
    """Budget for evidence expansion."""

    per_result_evidence: int = 3
    evidence_chars_total: int = 2000

    def __post_init__(self) -> None:
        _require_non_negative("evidence.per_result_evidence", self.per_result_evidence)
        _require_non_negative("evidence.evidence_chars_total", self.evidence_chars_total)


@dataclass(frozen=True, slots=True)
class ReflectionBudget:
    """Budget for inline reflection work."""

    inline_max_candidates: int = 50
    inline_timeout_ms: int = 100

    def __post_init__(self) -> None:
        _require_non_negative("reflection.inline_max_candidates", self.inline_max_candidates)
        _require_non_negative("reflection.inline_timeout_ms", self.inline_timeout_ms)


@dataclass(frozen=True, slots=True)
class OutputBudget:
    """Hard budget for final formatted output."""

    max_tokens: int = 2000

    def __post_init__(self) -> None:
        _require_non_negative("output.max_tokens", self.max_tokens)
        if self.max_tokens == 0:
            raise ValueError("output.max_tokens must be greater than zero")


@dataclass(frozen=True, slots=True)
class BudgetSpec:
    """Four independent budgets for one recall request."""

    retrieval: RetrievalBudget = field(default_factory=RetrievalBudget)
    evidence: EvidenceBudget = field(default_factory=EvidenceBudget)
    reflection: ReflectionBudget = field(default_factory=ReflectionBudget)
    output: OutputBudget = field(default_factory=OutputBudget)


@dataclass(frozen=True, slots=True)
class RecallPlanSnapshot:
    """Immutable record of the plan actually handed to an executor."""

    query: Optional[str]
    task: TaskMode
    namespace: str
    modes: Tuple[RetrievalMode, ...]
    max_results: int
    budget: BudgetSpec
    include_evidence: bool
    include_superseded: bool
    conflict_policy: ConflictPolicy
    sensitivity_policy: SensitivityPolicy
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "task": self.task.value,
            "namespace": self.namespace,
            "modes": [mode.value for mode in self.modes],
            "max_results": self.max_results,
            "budget": _budget_to_dict(self.budget),
            "include_evidence": self.include_evidence,
            "include_superseded": self.include_superseded,
            "conflict_policy": self.conflict_policy.value,
            "sensitivity_policy": self.sensitivity_policy.value,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RecallPlan:
    """Validated, deterministic, side-effect-free recall execution plan."""

    query: Optional[str]
    task: TaskMode
    namespace: str
    modes: Tuple[RetrievalMode, ...]
    max_results: int = 20
    budget: BudgetSpec = field(default_factory=BudgetSpec)
    include_evidence: bool = False
    include_superseded: bool = False
    conflict_policy: ConflictPolicy = ConflictPolicy.HIDE
    sensitivity_policy: SensitivityPolicy = SensitivityPolicy.FILTER

    def __post_init__(self) -> None:
        if self.query is not None and not isinstance(self.query, str):
            raise ValueError("query must be a string or None")
        if not isinstance(self.namespace, str) or not self.namespace.strip():
            raise ValueError("namespace is required")
        try:
            namespace = validate_namespace(self.namespace)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        if not isinstance(self.max_results, int) or isinstance(self.max_results, bool) or self.max_results <= 0:
            raise ValueError("max_results must be a positive integer")
        if not isinstance(self.budget, BudgetSpec):
            raise ValueError("budget must be a BudgetSpec")

        task = _coerce_enum(TaskMode, self.task, "task")
        modes = _normalize_modes(self.modes)
        if not modes:
            raise ValueError("modes must contain at least one retrieval mode")
        conflict_policy = _coerce_enum(ConflictPolicy, self.conflict_policy, "conflict_policy")
        sensitivity_policy = _coerce_enum(SensitivityPolicy, self.sensitivity_policy, "sensitivity_policy")

        if self.include_superseded and task is not TaskMode.TIMELINE_REVIEW:
            raise ValueError("include_superseded is only allowed for timeline_review")
        if task is TaskMode.CONFLICT_EXPLANATION and conflict_policy is not ConflictPolicy.ALWAYS:
            raise ValueError("conflict_explanation requires conflict_policy=always")

        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "task", task)
        object.__setattr__(self, "modes", modes)
        object.__setattr__(self, "conflict_policy", conflict_policy)
        object.__setattr__(self, "sensitivity_policy", sensitivity_policy)

    @property
    def fingerprint(self) -> str:
        """Return a stable identity for this plan without performing I/O."""
        payload = {
            "query": self.query,
            "task": self.task.value,
            "namespace": self.namespace,
            "modes": [mode.value for mode in self.modes],
            "max_results": self.max_results,
            "budget": _budget_to_dict(self.budget),
            "include_evidence": self.include_evidence,
            "include_superseded": self.include_superseded,
            "conflict_policy": self.conflict_policy.value,
            "sensitivity_policy": self.sensitivity_policy.value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def snapshot(self) -> RecallPlanSnapshot:
        """Return an immutable snapshot for a recall executor."""
        return RecallPlanSnapshot(
            query=self.query,
            task=self.task,
            namespace=self.namespace,
            modes=self.modes,
            max_results=self.max_results,
            budget=self.budget,
            include_evidence=self.include_evidence,
            include_superseded=self.include_superseded,
            conflict_policy=self.conflict_policy,
            sensitivity_policy=self.sensitivity_policy,
            fingerprint=self.fingerprint,
        )


_TASK_MODES = {
    TaskMode.PREFERENCE_FOLLOWING: (
        RetrievalMode.FTS,
        RetrievalMode.SEMANTIC,
        RetrievalMode.VECTOR,
    ),
    TaskMode.CORRECTION_RESOLUTION: (
        RetrievalMode.FTS,
        RetrievalMode.SEMANTIC,
        RetrievalMode.TIME,
    ),
    TaskMode.PROJECT_CONTEXT: (
        RetrievalMode.FTS,
        RetrievalMode.VECTOR,
        RetrievalMode.GRAPH,
        RetrievalMode.SEMANTIC,
        RetrievalMode.TIME,
    ),
    TaskMode.FACT_LOOKUP: (
        RetrievalMode.FTS,
        RetrievalMode.VECTOR,
        RetrievalMode.SEMANTIC,
    ),
    TaskMode.TIMELINE_REVIEW: (
        RetrievalMode.FTS,
        RetrievalMode.TIME,
        RetrievalMode.SEMANTIC,
    ),
    TaskMode.RULE_APPLICATION: (
        RetrievalMode.FTS,
        RetrievalMode.SEMANTIC,
        RetrievalMode.VECTOR,
    ),
    TaskMode.CONFLICT_EXPLANATION: (
        RetrievalMode.FTS,
        RetrievalMode.SEMANTIC,
        RetrievalMode.TIME,
        RetrievalMode.VECTOR,
    ),
}


def build_recall_plan(
    *,
    query: Optional[str],
    task: TaskMode | str,
    namespace: str,
    modes: Optional[Sequence[RetrievalMode | str]] = None,
    max_results: int = 20,
    budget: Optional[BudgetSpec] = None,
    include_evidence: bool = False,
    include_superseded: bool = False,
    conflict_policy: Optional[ConflictPolicy | str] = None,
    sensitivity_policy: SensitivityPolicy | str = SensitivityPolicy.FILTER,
) -> RecallPlan:
    """Build a deterministic plan from request parameters.

    Explicit modes may only narrow the task mode's supported retrieval paths.
    No storage, network, clock, or environment access occurs here.
    """
    resolved_task = _coerce_enum(TaskMode, task, "task")
    allowed_modes = _TASK_MODES[resolved_task]
    resolved_modes = allowed_modes if modes is None else _normalize_modes(modes)
    if not resolved_modes:
        raise ValueError("modes must contain at least one retrieval mode")
    if any(mode not in allowed_modes for mode in resolved_modes):
        raise ValueError(f"modes are not allowed for task {resolved_task.value}")

    resolved_conflict = (
        ConflictPolicy.ALWAYS
        if conflict_policy is None and resolved_task is TaskMode.CONFLICT_EXPLANATION
        else (
            ConflictPolicy.HIDE
            if conflict_policy is None
            else _coerce_enum(ConflictPolicy, conflict_policy, "conflict_policy")
        )
    )
    resolved_sensitivity = _coerce_enum(SensitivityPolicy, sensitivity_policy, "sensitivity_policy")

    return RecallPlan(
        query=query,
        task=resolved_task,
        namespace=namespace,
        modes=resolved_modes,
        max_results=max_results,
        budget=budget if budget is not None else BudgetSpec(),
        include_evidence=include_evidence,
        include_superseded=include_superseded,
        conflict_policy=resolved_conflict,
        sensitivity_policy=resolved_sensitivity,
    )


def _coerce_enum(enum_type: type[Enum], value: Any, field_name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise ValueError(f"invalid {field_name}; expected one of: {allowed}") from exc


def _normalize_modes(modes: Sequence[RetrievalMode | str]) -> Tuple[RetrievalMode, ...]:
    normalized = []
    for mode in modes:
        resolved = _coerce_enum(RetrievalMode, mode, "mode")
        if resolved not in normalized:
            normalized.append(resolved)
    return tuple(normalized)


def _require_non_negative(field_name: str, value: Any) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _budget_to_dict(budget: BudgetSpec) -> dict[str, dict[str, int]]:
    return {
        "retrieval": {
            "max_candidates": budget.retrieval.max_candidates,
            "graph_max_hops": budget.retrieval.graph_max_hops,
            "retrieval_timeout_ms": budget.retrieval.retrieval_timeout_ms,
        },
        "evidence": {
            "per_result_evidence": budget.evidence.per_result_evidence,
            "evidence_chars_total": budget.evidence.evidence_chars_total,
        },
        "reflection": {
            "inline_max_candidates": budget.reflection.inline_max_candidates,
            "inline_timeout_ms": budget.reflection.inline_timeout_ms,
        },
        "output": {"max_tokens": budget.output.max_tokens},
    }


__all__ = [
    "BudgetSpec",
    "ConflictPolicy",
    "EvidenceBudget",
    "OutputBudget",
    "RecallPlan",
    "RecallPlanSnapshot",
    "ReflectionBudget",
    "RetrievalBudget",
    "RetrievalMode",
    "SensitivityPolicy",
    "TaskMode",
    "build_recall_plan",
]
