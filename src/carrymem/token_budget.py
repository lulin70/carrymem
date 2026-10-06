"""Unified token estimation and deterministic output-budget enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence, Tuple

from .utils.language import has_cjk


class BudgetLayer(str, Enum):
    """Budget layer associated with an event or rendered block."""

    RETRIEVAL = "retrieval"
    EVIDENCE = "evidence"
    REFLECTION = "reflection"
    OUTPUT = "output"


class TruncationReason(str, Enum):
    """Closed set of reasons for budget-related truncation."""

    OUTPUT_BUDGET_EXCEEDED = "OUTPUT_BUDGET_EXCEEDED"
    EVIDENCE_BUDGET_EXCEEDED = "EVIDENCE_BUDGET_EXCEEDED"
    RETRIEVAL_TIMEOUT = "RETRIEVAL_TIMEOUT"
    RETRIEVAL_CANDIDATE_CAP = "RETRIEVAL_CANDIDATE_CAP"
    VECTOR_UNAVAILABLE_FALLBACK = "VECTOR_UNAVAILABLE_FALLBACK"
    SENSITIVITY_FILTERED = "SENSITIVITY_FILTERED"
    SUPERSEDED_FILTERED = "SUPERSEDED_FILTERED"
    CONFLICT_DEPRIORITIZED = "CONFLICT_DEPRIORITIZED"
    NAMESPACE_DENIED = "NAMESPACE_DENIED"
    TOKENIZER_DRIFT_WARNING = "TOKENIZER_DRIFT_WARNING"


def _budget_safe(value):
    return value.value if isinstance(value, Enum) else value


@dataclass(frozen=True, slots=True)
class PromptBlock:
    """A deterministic unit that may be retained or dropped as a whole."""

    text: str
    layer: BudgetLayer = BudgetLayer.OUTPUT
    drop_priority: int = 0
    protected: bool = False
    key: str = ""


@dataclass(frozen=True, slots=True)
class Truncation:
    """Structured record of one or more removed blocks."""

    reason_code: TruncationReason
    layer: BudgetLayer
    dropped_count: int
    protected: bool = False

    def to_dict(self):
        return {
            "reason_code": _budget_safe(self.reason_code),
            "layer": _budget_safe(self.layer),
            "dropped_count": self.dropped_count,
            "protected": self.protected,
        }


@dataclass(frozen=True, slots=True)
class Degradation:
    """Explicit degradation when protected content cannot fit the budget."""

    reason_code: TruncationReason
    message: str
    protected: bool = True

    def to_dict(self):
        return {
            "reason_code": _budget_safe(self.reason_code),
            "message": self.message,
            "protected": self.protected,
        }


@dataclass(frozen=True, slots=True)
class BudgetedPrompt:
    """Result of deterministic final-output budget enforcement."""

    text: str
    token_count: int
    retained_blocks: Tuple[PromptBlock, ...]
    truncations: Tuple[Truncation, ...] = ()
    degradation: Optional[Degradation] = None


def estimate_tokens(text: str) -> int:
    """Estimate tokens using the single process-wide CarryMem heuristic.

    The estimator intentionally has no model, clock, storage, or environment
    dependency. All selection and final-rendering paths must call this entry
    point so one process cannot mix token-counting rules.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cjk_count = sum(1 for character in text if has_cjk(character))
    other_count = len(text) - cjk_count
    return max(1, cjk_count + other_count // 4)


def enforce_output_budget(
    prefix: str,
    blocks: Sequence[PromptBlock] | str | bytes,
    max_tokens: int,
    separator: str = "\n",
) -> BudgetedPrompt:
    """Render blocks under a deterministic hard output budget.

    Non-protected blocks are removed in descending ``drop_priority`` order,
    with original order breaking ties. Protected blocks are retained. If the
    protected render still cannot fit, the result is explicitly degraded and
    deterministically shortened rather than silently dropping protected data.
    """
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    if not isinstance(prefix, str) or not isinstance(separator, str):
        raise TypeError("prefix and separator must be strings")

    if isinstance(blocks, (str, bytes)):
        raise TypeError("blocks must be a sequence of PromptBlock instances")
    try:
        ordered_blocks = tuple(blocks)
    except TypeError as exc:
        raise TypeError("blocks must be a sequence of PromptBlock instances") from exc
    if any(not isinstance(block, PromptBlock) for block in ordered_blocks):
        raise TypeError("blocks must contain only PromptBlock instances")

    retained: List[Optional[PromptBlock]] = list(ordered_blocks)
    truncations: List[Truncation] = []

    rendered = _render(prefix, retained, separator)
    if estimate_tokens(rendered) <= max_tokens:
        return BudgetedPrompt(rendered, estimate_tokens(rendered), ordered_blocks)

    droppable = [(index, block) for index, block in enumerate(ordered_blocks) if not block.protected]
    droppable.sort(key=lambda pair: (-pair[1].drop_priority, pair[0]))

    for index, block in droppable:
        if estimate_tokens(_render(prefix, retained, separator)) <= max_tokens:
            break
        retained[index] = None
        truncations.append(
            Truncation(
                reason_code=TruncationReason.OUTPUT_BUDGET_EXCEEDED,
                layer=block.layer,
                dropped_count=1,
                protected=False,
            )
        )

    retained_blocks = tuple(block for block in retained if block is not None)
    rendered = _render(prefix, retained_blocks, separator)
    token_count = estimate_tokens(rendered)
    if token_count <= max_tokens:
        return BudgetedPrompt(rendered, token_count, retained_blocks, tuple(truncations))

    degradation = Degradation(
        reason_code=TruncationReason.OUTPUT_BUDGET_EXCEEDED,
        message="Protected output content exceeded the hard token budget.",
    )
    shortened = _shorten_to_budget(rendered, max_tokens)
    retained_blocks = _blocks_present_in_text(retained_blocks, shortened)
    truncations.append(
        Truncation(
            reason_code=TruncationReason.OUTPUT_BUDGET_EXCEEDED,
            layer=BudgetLayer.OUTPUT,
            dropped_count=1,
            protected=True,
        )
    )
    return BudgetedPrompt(
        shortened,
        estimate_tokens(shortened),
        retained_blocks,
        tuple(truncations),
        degradation,
    )


def _render(prefix: str, blocks: Sequence[Optional[PromptBlock]], separator: str) -> str:
    parts = [prefix, *(block.text for block in blocks if block is not None and block.text)]
    return separator.join(part for part in parts if part)


def _blocks_present_in_text(blocks: Tuple[PromptBlock, ...], text: str) -> Tuple[PromptBlock, ...]:
    """Keep metadata aligned with blocks whose rendered text remains visible."""
    visible: List[PromptBlock] = []
    cursor = 0
    for block in blocks:
        if not block.text:
            continue
        position = text.find(block.text, cursor)
        if position < 0:
            continue
        visible.append(block)
        cursor = position + len(block.text)
    return tuple(visible)


def _shorten_to_budget(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    low = 0
    high = len(text)
    best = ""
    while low <= high:
        middle = (low + high) // 2
        candidate = text[:middle]
        if estimate_tokens(candidate) <= max_tokens:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    return best


__all__ = [
    "BudgetLayer",
    "BudgetedPrompt",
    "Degradation",
    "PromptBlock",
    "Truncation",
    "TruncationReason",
    "enforce_output_budget",
    "estimate_tokens",
]
