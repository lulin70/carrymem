"""Recall operations: memories, aggregated, timeline, knowledge, all."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from carrymem.adapters.base import RawConnectionProvider
from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.constants import DEFAULT_RECALL_LIMIT, RULE_MATCH_LIMIT_CAP
from carrymem.core._lifecycle import KnowledgeNotConfiguredError, StorageNotConfiguredError
from carrymem.core._memory_crud import _reset_busy_connection, _retry_on_busy
from carrymem.inline_reflection import InlineReflectionHint, inspect_candidates_for_hints
from carrymem.monitoring import get_metrics_collector
from carrymem.recall_plan import RecallPlan, build_recall_plan
from carrymem.security.redaction import should_redact
from carrymem.token_budget import BudgetLayer, Degradation, Truncation, TruncationReason, estimate_tokens
from carrymem.types import (
    BudgetUsage,
    ConflictView,
    ModeFailure,
    RecallItem,
)
from carrymem.types import RecallPlanSnapshot as ResultPlanSnapshot
from carrymem.types import (
    RecallResult,
    StoredMemoryDict,
)
from carrymem.utils.validators import validate_limit, validate_query

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter
    from carrymem.rules import RuleEngine

logger = logging.getLogger(__name__)


def _memory_score(memory: Dict[str, Any]) -> float:
    for key in ("score", "similarity", "importance_score", "confidence"):
        value = memory.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _memory_in_namespace(memory: Dict[str, Any], namespace: str) -> bool:
    value = memory.get("namespace")
    return value is None or value == namespace


def _conflict_subject(memory: Dict[str, Any]) -> str:
    metadata = memory.get("metadata")
    if isinstance(metadata, dict):
        for key in ("subject_key", "conflict_key", "conflict_id"):
            if metadata.get(key):
                return str(metadata[key])
    return str(memory.get("storage_key") or memory.get("id") or "")


def _top_conflict_candidates(
    ranked: List[Tuple[str, Dict[str, Any]]],
) -> List[Tuple[str, Dict[str, Any]]]:
    selected: List[Tuple[str, Dict[str, Any]]] = []
    seen_groups: set[str] = set()
    for mode_name, memory in ranked:
        group = str(memory.get("version_chain_id") or _conflict_subject(memory))
        if group not in seen_groups:
            selected.append((mode_name, memory))
            seen_groups.add(group)
    return selected


def _count_output_tokens(items: List[RecallItem]) -> int:
    """Estimate the serialized token cost of a list of recall items."""
    return estimate_tokens(json.dumps([item.to_dict() for item in items], sort_keys=True, default=str))


def _drop_tier(memory: Dict[str, Any]) -> int:
    """Map a memory to its §5.1 drop order among non-protected entries.

    0 = inferred/derived/graph candidates (dropped first), 1 = ordinary
    fact/preference, 2 = observation (kept longest among droppable tiers).
    """
    raw_metadata = memory.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    source = str(memory.get("source_layer") or metadata.get("source_layer") or "").lower()
    if source in {"inference", "inferred", "derived", "aggregation", "graph", "co_occurrence"}:
        return 0
    if str(memory.get("type") or memory.get("memory_type") or "").lower() == "observation":
        return 2
    return 1


def _drop_sort_key(item: RecallItem) -> Tuple[int, str, float]:
    """Deterministic drop order: low trust tier first, then oldest, then lowest score."""
    memory = item.memory
    return (_drop_tier(memory), str(memory.get("created_at") or ""), -item.score)


def _rows_for_mode(
    adapter: StorageAdapter,
    mode_name: str,
    query: str,
    remaining: int,
    filters: Dict[str, Any],
    plan: RecallPlan,
    failures: List[ModeFailure],
) -> Optional[List[Any]]:
    """Fetch raw rows for one resolved mode, or None when the mode is skipped."""
    if mode_name == "graph":
        # Callers only reach here after the entity INPUT_MISSING gate passed.
        result = adapter.recall_graph(
            str(plan.entity or ""), plan.budget.retrieval.graph_max_hops, plan.namespace, remaining
        )
        return list((result or {}).get("memories") or [])
    if mode_name == "time":
        # Callers only reach here after the time_range INPUT_MISSING gate passed.
        time_range = plan.time_range or ("", "")
        start_dt = datetime.fromisoformat(time_range[0])
        end_dt = datetime.fromisoformat(time_range[1])
        return adapter.recall_by_time(start_dt, end_dt, dict(filters), remaining, [plan.namespace])
    if mode_name == "semantic":
        if not adapter.capabilities.get("semantic_recall", adapter.capabilities.get("vector_search", False)):
            failures.append(
                ModeFailure(
                    "semantic",
                    "semantic search unavailable",
                    skipped=True,
                    reason_code="VECTOR_UNAVAILABLE_FALLBACK",
                )
            )
            return None
        return adapter.recall_semantic(query, remaining, dict(filters), [plan.namespace])
    if mode_name == "vector":
        return adapter.recall_semantic(query, remaining, dict(filters), [plan.namespace])
    if mode_name == "fts":
        if not adapter.capabilities.get("fts", True):
            failures.append(ModeFailure("fts", "fts search unavailable", skipped=True, reason_code="UNSUPPORTED_MODE"))
            return None
        return adapter.recall(
            query, filters=dict(filters), limit=remaining, namespaces=[plan.namespace], update_access=False
        )
    failures.append(ModeFailure(mode_name, "unsupported plan mode", skipped=True, reason_code="UNSUPPORTED_MODE"))
    return None


def _collect_mode_rows(
    rows: List[Any],
    mode_name: str,
    plan: RecallPlan,
    candidate_cap: int,
    candidates: List[Tuple[str, Dict[str, Any]]],
) -> Tuple[int, bool]:
    """Append namespace-valid candidates from one mode's rows.

    Applies the plan's INV-C2 superseded filter with an exact hidden count.
    Returns (superseded_hidden, cap_hit).
    """
    superseded_count = 0
    for row in rows:
        memory = row.to_dict() if hasattr(row, "to_dict") else dict(row)
        if not isinstance(memory, dict) or memory.get("namespace") != plan.namespace:
            continue
        # INV-C2: the plan path fetches full rows and applies the superseded
        # filter here, so the hidden count is observable (legacy recall keeps
        # adapter-side filtering unchanged).
        if not plan.include_superseded and str(memory.get("superseded_at") or ""):
            superseded_count += 1
            continue
        candidates.append((mode_name, memory))
        if len(candidates) >= candidate_cap:
            return superseded_count, True
    return superseded_count, False


def _retrieve_plan_candidates(
    adapter: StorageAdapter,
    plan: RecallPlan,
    query: str,
    filters: Dict[str, Any],
    candidate_cap: int,
    metrics: Any,
    failures: List[ModeFailure],
    truncations: List[Truncation],
) -> Tuple[List[Tuple[str, Dict[str, Any]]], bool, int]:
    """Collect candidates from each plan mode under the retrieval budget."""
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    remaining = candidate_cap
    cap_hit = False
    superseded_count = 0
    timeout_ms = plan.budget.retrieval.retrieval_timeout_ms
    loop_started = time.perf_counter()
    for mode in plan.modes:
        mode_name = mode.value
        # Soft time budget: modes are checked before they start; a single
        # in-flight SQLite query cannot be interrupted safely, so the budget
        # gates which modes may still begin (documented in BUDGET §10.3).
        if (time.perf_counter() - loop_started) * 1000.0 > timeout_ms:
            failures.append(
                ModeFailure(mode_name, "retrieval time budget exhausted", skipped=True, reason_code="RETRIEVAL_TIMEOUT")
            )
            truncation = Truncation(TruncationReason.RETRIEVAL_TIMEOUT, BudgetLayer.RETRIEVAL, 1)
            truncations.append(truncation)
            metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
            continue
        if remaining <= 0:
            failures.append(
                ModeFailure(
                    mode_name, "candidate budget exhausted", skipped=True, reason_code="RETRIEVAL_CANDIDATE_CAP"
                )
            )
            continue
        if mode_name == "graph" and not plan.entity:
            failures.append(ModeFailure("graph", "entity input is required", skipped=True, reason_code="INPUT_MISSING"))
            continue
        if mode_name == "time" and not plan.time_range:
            failures.append(
                ModeFailure("time", "time range input is required", skipped=True, reason_code="INPUT_MISSING")
            )
            continue
        if mode_name in {"semantic", "vector"} and not query.strip():
            failures.append(
                ModeFailure(mode_name, "query must be a non-empty string", "ValueError", reason_code="INPUT_MISSING")
            )
            continue
        if mode_name == "vector" and not adapter.capabilities.get("vector_search", False):
            truncation = Truncation(TruncationReason.VECTOR_UNAVAILABLE_FALLBACK, BudgetLayer.RETRIEVAL, 1)
            truncations.append(truncation)
            metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
            failures.append(
                ModeFailure(
                    mode_name,
                    "vector search unavailable; fell back to fts",
                    skipped=True,
                    reason_code="VECTOR_UNAVAILABLE_FALLBACK",
                )
            )
            mode_name = "fts"
        try:
            rows = _rows_for_mode(adapter, mode_name, query, remaining, filters, plan, failures)
            if rows is None:
                continue
            hidden, hit = _collect_mode_rows(rows, mode_name, plan, candidate_cap, candidates)
            superseded_count += hidden
            if hit:
                cap_hit = True
            remaining = candidate_cap - len(candidates)
        except (KeyError, ValueError, TypeError, RuntimeError, AttributeError) as exc:
            failures.append(
                ModeFailure(
                    mode_name,
                    str(exc) or exc.__class__.__name__,
                    exc.__class__.__name__,
                    reason_code="RETRIEVAL_FAILED",
                )
            )
    return candidates, cap_hit, superseded_count


def _filter_sensitive_candidates(
    candidates: List[Tuple[str, Dict[str, Any]]],
    sensitivity_policy: str,
    metrics: Any,
    failures: List[ModeFailure],
    truncations: List[Truncation],
    metadata: Dict[str, Any],
) -> List[Tuple[str, Dict[str, Any]]]:
    """Drop candidates whose serialized payload trips the redaction engine."""
    filtered: List[Tuple[str, Dict[str, Any]]] = []
    for mode_name, memory in candidates:
        try:
            serialized = json.dumps(
                {
                    "content": memory.get("content"),
                    "raw_text": memory.get("raw_text"),
                    "metadata": memory.get("metadata", {}),
                },
                sort_keys=True,
                default=str,
            )
            blocked, reason = should_redact(serialized)
        except Exception as exc:  # NOTE intentional: fail closed on unreadable payloads; rationale above
            blocked, reason = True, f"sensitivity check failed: {exc}"
        if blocked:
            if sensitivity_policy == "strict":
                failures.append(
                    ModeFailure(
                        mode_name,
                        reason or "sensitive candidate blocked",
                        "SensitivityError",
                        reason_code="SENSITIVITY_FILTERED",
                    )
                )
            metadata["sensitivity_filtered"] = metadata.get("sensitivity_filtered", 0) + 1
            truncation = Truncation(TruncationReason.SENSITIVITY_FILTERED, BudgetLayer.RETRIEVAL, 1)
            truncations.append(truncation)
            metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
            continue
        filtered.append((mode_name, memory))
    return filtered


def _resolve_conflicts(
    filtered: List[Tuple[str, Dict[str, Any]]],
    conflict_policy: str,
    metrics: Any,
    truncations: List[Truncation],
) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[ConflictView]]:
    """Group filtered candidates into conflict chains and apply the policy."""
    grouped: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for mode_name, memory in filtered:
        key = str(memory.get("version_chain_id") or _conflict_subject(memory))
        grouped.setdefault(key, []).append((mode_name, memory))
    conflicts: List[ConflictView] = []
    conflicting_groups: set[str] = set()
    for key, group in sorted(grouped.items()):
        keys = {str(item[1].get("storage_key", "")) for item in group}
        if len(keys) > 1:
            conflicting_groups.add(key)
            conflicts.append(ConflictView(key, tuple(sorted(keys)), tuple(item[1] for item in group)))

    if conflicting_groups and conflict_policy == "hide":
        filtered = [
            (mode_name, memory)
            for mode_name, memory in filtered
            if str(memory.get("version_chain_id") or _conflict_subject(memory)) not in conflicting_groups
        ]

    if conflicting_groups and conflict_policy != "always":
        truncation = Truncation(TruncationReason.CONFLICT_DEPRIORITIZED, BudgetLayer.RETRIEVAL, 1)
        truncations.append(truncation)
        metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
    return filtered, conflicts


def _rank_and_dedupe(
    filtered: List[Tuple[str, Dict[str, Any]]],
    task_value: str,
    conflict_policy: str,
) -> List[Tuple[str, Dict[str, Any], Tuple[str, ...]]]:
    """Dedupe candidates by storage key and rank protected entries first."""
    by_key: Dict[str, Tuple[Dict[str, Any], List[str]]] = {}
    for mode_name, memory in filtered:
        key = str(memory.get("storage_key") or memory.get("id") or "")
        if key in by_key:
            by_key[key][1].append(mode_name)
        else:
            by_key[key] = (memory, [mode_name])
    ranked = [(modes[0], memory, tuple(modes)) for memory, modes in by_key.values()]

    def _priority(entry: Tuple[str, Dict[str, Any], Tuple[str, ...]]):
        memory = entry[1]
        memory_type = str(memory.get("type") or memory.get("memory_type") or "")
        protected = (
            memory_type in {"correction", "security", "strategy", "accepted_fact", "accepted_rule"}
            or str(memory.get("status", "")).lower() == "accepted"
        )
        correction = task_value == "correction_resolution" and memory_type == "correction"
        return (
            0 if correction else 1 if protected else 2,
            -_memory_score(memory),
            str(memory.get("storage_key") or memory.get("id") or ""),
        )

    ranked.sort(key=_priority)
    if conflict_policy == "show_top":
        top_candidates = _top_conflict_candidates([(mode, memory) for mode, memory, _ in ranked])
        ranked = [
            (
                mode,
                memory,
                tuple(by_key[str(memory.get("storage_key") or memory.get("id") or "")][1]),
            )
            for mode, memory in top_candidates
        ]
    return ranked


def _expand_evidence(
    adapter: StorageAdapter,
    plan: RecallPlan,
    ranked: List[Tuple[str, Dict[str, Any], Tuple[str, ...]]],
    metrics: Any,
    truncations: List[Truncation],
) -> Tuple[List[RecallItem], int]:
    """Attach evidence links to ranked items under the evidence budget."""
    evidence_chars = 0
    result_items: List[RecallItem] = []
    for mode_name, memory, modes in ranked:
        evidence: Tuple[Any, ...] = ()
        if plan.include_evidence:
            key = str(memory.get("storage_key") or memory.get("id") or "")
            try:
                links = adapter.list_evidence_links(
                    plan.namespace,
                    target_kind="memory",
                    target_id=key,
                    include_stale=False,
                    limit=plan.budget.evidence.per_result_evidence,
                )
            except (AttributeError, KeyError, ValueError, TypeError, RuntimeError):
                links = []
            kept = []
            for link in links or []:
                encoded = json.dumps(link, sort_keys=True, default=str)
                if evidence_chars + len(encoded) > plan.budget.evidence.evidence_chars_total:
                    truncation = Truncation(TruncationReason.EVIDENCE_BUDGET_EXCEEDED, BudgetLayer.EVIDENCE, 1)
                    truncations.append(truncation)
                    metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
                    break
                kept.append(link)
                evidence_chars += len(encoded)
            evidence = tuple(kept)
        result_items.append(
            RecallItem(
                memory=memory,
                source_mode=mode_name,
                source_modes=modes,
                score=_memory_score(memory),
                evidence=evidence,
            )
        )
    return result_items, evidence_chars


def _enforce_output_limit(
    result_items: List[RecallItem],
    task_value: str,
    output_limit: int,
    metrics: Any,
    truncations: List[Truncation],
) -> Tuple[List[RecallItem], Optional[Degradation]]:
    """Apply the hard output budget: drop ordinary items, shorten protected."""
    protected_types = {"correction", "security", "strategy", "accepted_fact", "accepted_rule"}

    def _protected(item: RecallItem) -> bool:
        memory_type = str(item.memory.get("type") or item.memory.get("memory_type") or "")
        return (
            memory_type in protected_types
            or str(item.memory.get("status", "")).lower() == "accepted"
            or (task_value == "correction_resolution" and memory_type == "correction")
        )

    while result_items and _count_output_tokens(result_items) > output_limit:
        droppable = [idx for idx, item in enumerate(result_items) if not _protected(item)]
        if not droppable:
            break
        # §5.1 order: inferred first, ordinary next, observations last;
        # ties break by oldest created_at, then lowest score.
        droppable.sort(key=lambda idx: _drop_sort_key(result_items[idx]))
        result_items.pop(droppable[0])
        truncation = Truncation(TruncationReason.OUTPUT_BUDGET_EXCEEDED, BudgetLayer.OUTPUT, 1)
        truncations.append(truncation)
        metrics.record_recall_truncation(truncation.reason_code, truncation.layer)

    degraded: Optional[Degradation] = None
    if _count_output_tokens(result_items) > output_limit:
        degraded = Degradation(
            TruncationReason.OUTPUT_BUDGET_EXCEEDED, "Protected recall output exceeded the hard token budget."
        )

        def _count_with(replacement: Dict[str, Any]) -> int:
            probe = RecallItem(
                memory=replacement,
                source_mode=result_items[-1].source_mode,
                source_modes=result_items[-1].source_modes,
                score=result_items[-1].score,
                evidence=result_items[-1].evidence,
            )
            return _count_output_tokens([*result_items[:-1], probe])

        while result_items and _count_output_tokens(result_items) > output_limit:
            item = result_items[-1]
            memory = dict(item.memory)
            content = str(memory.get("content") or memory.get("raw_text") or "")
            # Deterministic binary search for the longest content prefix
            # that fits the hard budget (mirrors token_budget._shorten_to_budget).
            fitted = ""
            low, high = 0, len(content)
            while low <= high:
                middle = (low + high) // 2
                trial = dict(memory)
                trial["content"] = content[:middle]
                if _count_with(trial) <= output_limit:
                    fitted = content[:middle]
                    low = middle + 1
                else:
                    high = middle - 1
            memory["content"] = fitted
            stored_meta = memory.get("metadata")
            if fitted and isinstance(stored_meta, dict) and stored_meta.get("original_message"):
                sync_meta = dict(stored_meta)
                sync_meta["original_message"] = fitted
                memory["metadata"] = sync_meta
            result_items[-1] = RecallItem(
                memory=memory,
                source_mode=item.source_mode,
                source_modes=item.source_modes,
                score=item.score,
                evidence=item.evidence,
            )
            if not fitted:
                # Even an empty body cannot fit: fixed serialization
                # overhead alone exceeds the budget. Drop the item and let
                # the Degradation record explain the protected-data loss.
                result_items.pop()
    return result_items, degraded


def _run_inline_reflection(
    adapter: Any,
    plan: RecallPlan,
    ranked: Any,
    metrics: Any,
) -> Tuple[List[Truncation], List[InlineReflectionHint], Any]:
    """Run inline reflection inspection over the ranked candidates.

    Returns a triple ``(truncations, hints, report)``:

    * ``truncations`` — list of ``Truncation`` events to append (currently
      only ``RETRIEVAL_TIMEOUT`` when the soft timeout fires).
    * ``hints`` — the structured re-rank hints (capped by
      ``MAX_HINTS_PER_RESPONSE``). Pure data; call sites decide how to
      surface them to the user (BetaCarryMem exposes them as the
      ``hints`` field of ``RecallResult``).
    * ``report`` — the raw ``InlineReflectionReport`` (for metadata + utilization).

    The function never touches the items list. It also never calls
    ``ReflectionManager`` (per v1.2 §10.5 defect #3) and never opens a
    transaction — the inline path is read-only and side-effect-free except
    for metrics emission.

    ``stale_keys`` is pre-computed via the adapter's decay gate
    (``find_decay_candidates``) when available; if the adapter does not
    support it (e.g. non-SQLite backends), inspect runs without stale hints.
    """
    budget = plan.budget.reflection
    stale_keys = _collect_stale_keys(adapter, plan.namespace, budget.inline_max_candidates)

    report = inspect_candidates_for_hints(
        ranked,
        inline_max_candidates=budget.inline_max_candidates,
        inline_timeout_ms=budget.inline_timeout_ms,
        stale_keys=stale_keys,
    )

    truncations: List[Truncation] = []
    if report.timeout_hit:
        truncation = Truncation(TruncationReason.RETRIEVAL_TIMEOUT, BudgetLayer.REFLECTION, 1)
        truncations.append(truncation)
        metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
    if report.capped_count > 0:
        truncation = Truncation(
            TruncationReason.OUTPUT_BUDGET_EXCEEDED,
            BudgetLayer.REFLECTION,
            report.capped_count,
        )
        truncations.append(truncation)
        metrics.record_recall_truncation(truncation.reason_code, truncation.layer, report.capped_count)

    for hint in report.hints:
        metrics.increment(f"carrymem_recall_reflection_hints_total.{hint.hint_type.value}")

    return truncations, list(report.hints), report


def _collect_stale_keys(
    adapter: Any,
    namespace: str,
    budget_inline_max_candidates: int,
) -> set:
    """Best-effort: ask the adapter for storage keys matching the decay gate.

    Returns an empty set when the adapter does not expose a connection or
    when ``find_decay_candidates`` is unavailable. Inline reflection still
    runs (conflict hints only) — only the ``stale`` hint type is suppressed.

    This helper performs narrow duck-typed probes — each ``except`` covers a
    specific failure mode (missing attribute, missing function, DB error)
    rather than a bare ``except [BASE_EXCEPTION]``, to keep the broad-exception
    gate honest.
    """
    if not adapter:
        return set()
    conn = None
    provider = getattr(adapter, "_conn_mgr", None) or getattr(adapter, "connection_provider", None)
    if provider is not None and hasattr(provider, "get_connection"):
        try:
            conn = provider.get_connection()
        except (AttributeError, TypeError, OSError) as exc:
            logger.debug("stale_keys: provider access failed: %s", exc)
            conn = None
    if conn is None and hasattr(adapter, "conn"):
        try:
            conn = adapter.conn
        except (AttributeError, TypeError, OSError) as exc:
            logger.debug("stale_keys: conn attr access failed: %s", exc)
            conn = None
    if conn is None:
        return set()
    try:
        from carrymem.layers.memify import find_decay_candidates
    except ImportError:
        return set()
    try:
        keys = find_decay_candidates(
            conn,
            namespace,
            stale_days=90,
            min_importance=0.3,
            batch_size=max(50, budget_inline_max_candidates * 4),
        )
    except (AttributeError, TypeError, ValueError, OSError, sqlite3.DatabaseError) as exc:
        logger.debug("stale_keys: find_decay_candidates failed: %s", exc)
        return set()
    return set(keys)


class RecallMixin:
    """Recall / search operations across memories, knowledge base, and rules."""

    # Shared instance state provided by LifecycleMixin.__init__.
    _adapter: Optional[StorageAdapter]
    _knowledge_adapter: Optional[StorageAdapter]
    _namespace: str
    _session_id: Optional[str]

    # ── Cross-Mixin dependencies (TD-037: explicit Protocol contract) ──
    if TYPE_CHECKING:
        # From LifecycleMixin (property)
        @property
        def rule_engine(self) -> RuleEngine: ...

    def build_recall_plan(self, **kwargs: Any) -> RecallPlan:
        """Build a deterministic, validated plan without touching storage."""
        kwargs.setdefault("namespace", self._namespace)
        return build_recall_plan(**kwargs)

    def index_knowledge(self) -> Dict[str, Any]:
        """Index the configured knowledge base and return summary stats."""
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        if isinstance(self._knowledge_adapter, ObsidianAdapter):
            return self._knowledge_adapter.index_vault()

        return {"error": "Knowledge adapter does not support indexing"}

    def recall_from_knowledge(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Recall notes from the knowledge base matching the query."""
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        results = self._knowledge_adapter.recall(query, filters=filters, limit=limit)
        if isinstance(results, list) and results and isinstance(results[0], dict):
            return results  # type: ignore[return-value]
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in results]  # type: ignore[misc]

    def recall_all(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        """Recall rules, memories, and knowledge matching a query."""
        memory_results = []
        knowledge_results = []
        rule_results = []

        if include_rules:
            try:
                rule_engine = self.rule_engine
                matches = rule_engine.match(query, limit=min(limit, RULE_MATCH_LIMIT_CAP), increment_count=False)
                rule_results = [
                    {
                        "rule_id": m.rule.id,
                        "trigger": m.rule.trigger,
                        "action": m.rule.action,
                        "rule_type": m.rule.rule_type,
                        "override": m.rule.override,
                        "score": m.score,
                        "match_type": m.match_type,
                    }
                    for m in matches
                ]
            except (ImportError, KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Rule engine failed for recall_all: %s", e)
                rule_results = []

        if self._adapter:
            try:
                memory_results = self.recall_memories(query=query, filters=filters, limit=limit, namespaces=namespaces)
            except (KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to recall memories for prompt: %s", e)
                memory_results = []

        if self._knowledge_adapter:
            try:
                knowledge_results = self.recall_from_knowledge(query=query, filters=filters, limit=limit)
            except (KeyError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Failed to recall from knowledge base: %s", e)
                knowledge_results = []

        return {
            "rules": rule_results,
            "memories": memory_results,
            "knowledge": knowledge_results,
            "rule_count": len(rule_results),
            "memory_count": len(memory_results),
            "knowledge_count": len(knowledge_results),
            "total_count": len(rule_results) + len(memory_results) + len(knowledge_results),
            "namespace": self._namespace,
            "priority": "rules > memory > knowledge",
        }

    def recall_with_plan(self, plan: RecallPlan) -> RecallResult:
        """Execute a validated recall plan without changing the legacy API."""
        if not isinstance(plan, RecallPlan):
            raise TypeError("plan must be a RecallPlan")
        started = time.perf_counter()
        result = _retry_on_busy(
            lambda: self._execute_recall_plan(plan),
            what="recall_with_plan",
            reset=lambda: _reset_busy_connection(self._adapter),
        )
        get_metrics_collector().record_latency("recall", (time.perf_counter() - started) * 1000.0)
        return result

    def _execute_recall_plan(self, plan: RecallPlan) -> RecallResult:
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not plan.namespace or plan.namespace != self._namespace:
            failure = ModeFailure("plan", "namespace is not authorized", skipped=True, reason_code="NAMESPACE_DENIED")
            return RecallResult(
                (),
                plan.fingerprint,
                plan.namespace,
                plan.task.value,
                tuple(m.value for m in plan.modes),
                BudgetUsage(),
                (failure,),
                status="denied",
            )

        metrics = get_metrics_collector()
        # Plan path fetches full rows (including superseded) and applies the
        # plan's INV-C2 filter in the executor with an exact count; legacy
        # recall keeps adapter-side filtering unchanged.
        filters: Dict[str, Any] = {"include_superseded": True}
        candidate_cap = plan.budget.retrieval.max_candidates
        query = plan.query or ""
        failures: List[ModeFailure] = []
        truncations: List[Truncation] = []

        candidates, cap_hit, superseded_count = _retrieve_plan_candidates(
            self._adapter, plan, query, filters, candidate_cap, metrics, failures, truncations
        )
        if cap_hit:
            truncation = Truncation(TruncationReason.RETRIEVAL_CANDIDATE_CAP, BudgetLayer.RETRIEVAL, 1)
            truncations.append(truncation)
            metrics.record_recall_truncation(truncation.reason_code, truncation.layer)
        if superseded_count:
            truncation = Truncation(TruncationReason.SUPERSEDED_FILTERED, BudgetLayer.RETRIEVAL, superseded_count)
            truncations.append(truncation)
            metrics.record_recall_truncation(truncation.reason_code, truncation.layer, superseded_count)

        metadata: Dict[str, Any] = {
            "candidate_cap": candidate_cap,
            "result_cap": plan.max_results,
            "superseded_filtered": superseded_count,
        }
        filtered = _filter_sensitive_candidates(
            candidates, plan.sensitivity_policy.value, metrics, failures, truncations, metadata
        )
        filtered, conflicts = _resolve_conflicts(filtered, plan.conflict_policy.value, metrics, truncations)
        ranked = _rank_and_dedupe(filtered, plan.task.value, plan.conflict_policy.value)[: plan.max_results]
        result_items, evidence_chars = _expand_evidence(self._adapter, plan, ranked, metrics, truncations)
        result_items, degraded = _enforce_output_limit(
            result_items, plan.task.value, plan.budget.output.max_tokens, metrics, truncations
        )

        # v1.2 §11 inline reflection — read-only over `ranked` (post-dedupe,
        # pre-evidence), emit metrics/truncations, never touches items.
        # ``_run_inline_reflection`` is the only place that consumes
        # ``ReflectionBudget`` so the wired-up path is observable.
        ref_truncations, inline_hints, inline_report = _run_inline_reflection(
            self._adapter,
            plan,
            ranked,
            metrics,
        )
        truncations.extend(ref_truncations)
        inspected_count = inline_report.inspected_count

        output_usage = _count_output_tokens(result_items)
        output_limit = plan.budget.output.max_tokens
        metrics.set_recall_budget_utilization("retrieval", min(1.0, len(candidates) / max(1, candidate_cap)))
        metrics.set_recall_budget_utilization(
            "evidence", min(1.0, evidence_chars / max(1, plan.budget.evidence.evidence_chars_total))
        )
        metrics.set_recall_budget_utilization(
            "reflection",
            min(1.0, inspected_count / max(1, plan.budget.reflection.inline_max_candidates)),
        )
        metrics.set_recall_budget_utilization("output", min(1.0, output_usage / max(1, output_limit)))
        status = "degraded" if degraded or truncations else "ok"
        metadata.update(
            {
                "evidence_chars": evidence_chars,
                "output_tokens": output_usage,
                "reflection_candidates": inline_report.inspected_count,
                "hints_count": len(inline_hints),
                # Deterministic metadata for E2E equality (wall-clock goes
                # only into budget_usage / metrics — see inline_reflection.
                # InlineReflectionReport.elapsed_ms).
                "reflection_timeout_hit": inline_report.timeout_hit,
                "reflection_hints_capped": inline_report.capped_count,
            }
        )
        return RecallResult(
            items=tuple(result_items),
            plan_fingerprint=plan.fingerprint,
            namespace=plan.namespace,
            task=plan.task.value,
            modes=tuple(mode.value for mode in plan.modes),
            budget_usage=BudgetUsage(
                len(candidates),
                len(result_items),
                candidate_cap,
                plan.max_results,
                evidence_chars,
                inline_report.inspected_count,
                output_usage,
                plan.budget.evidence.evidence_chars_total,
                plan.budget.reflection.inline_max_candidates,
                output_limit,
                inline_report.inspected_count,
                len(inline_hints),
            ),
            mode_failures=tuple(failures),
            conflicts=tuple(conflicts) if plan.conflict_policy.value == "always" else (),
            metadata=metadata,
            plan=ResultPlanSnapshot(plan.snapshot().to_dict()),
            truncations=tuple(truncations),
            degraded=degraded,
            status=status,
            hints=tuple(inline_hints),
        )

    def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[Dict[str, Any]]:
        """Recall stored memories matching the query.

        Instrumented: one latency sample per call plus a success or error
        counter, matching the ``recall`` SLO entry in ``monitoring._DEFAULT_SLOS``.
        Internal infrastructure reads must call ``_recall_memories_uninstrumented``
        instead — see its docstring for why.
        """
        metrics = get_metrics_collector()
        started = time.perf_counter()
        try:
            payload = _retry_on_busy(
                lambda: self._recall_memories_uninstrumented(
                    query=query,
                    filters=filters,
                    limit=limit,
                    namespaces=namespaces,
                    update_access=update_access,
                ),
                what="recall_memories",
                reset=lambda: _reset_busy_connection(self._adapter),
            )
        except Exception:  # NOTE: intentional — top-level fail-closed wrapper, re-raised after metric
            metrics.increment("recall_errors")
            raise
        finally:
            metrics.record_latency("recall", (time.perf_counter() - started) * 1000.0)
        metrics.increment("recall")
        return payload

    def _recall_memories_uninstrumented(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_RECALL_LIMIT,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[Dict[str, Any]]:
        """Recall without emitting metrics, for internal infrastructure reads.

        Several code paths read existing memories *as a side effect of storing*
        rather than because the user asked for a recall:

        - ``rules/candidate_generator.py`` looks for patterns to suggest rules for;
        - ``core/_classification.py`` resolves pronouns (coreference) and analyses
          correction history.

        Those reads are bookkeeping the user never asked for. Counting them
        inflated ``carrymem_total{operation="recall"}`` (measured: two per
        ``classify_and_remember`` from the rule path, plus one more when the
        message contains a pronoun and the coreference branch runs) and diluted
        the recall latency SLO with fast internal lookups. The counter is meant
        to answer "how many recall operations did the user request, and how slow
        were they", so these paths call this method instead.

        Reads that *serve* a user request — ``recall_all``, prompt building,
        ``whoami`` — keep using the instrumented ``recall_memories``.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_query(query or "")
        validate_limit(limit)
        results = self._adapter.recall(
            query or "",
            filters=filters,
            limit=limit,
            namespaces=namespaces,
            update_access=update_access,
        )
        return [r.to_dict() for r in results]

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[StoredMemoryDict]]:
        """Recall memories grouped by type."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        method = getattr(self._adapter, "recall_aggregated", None)
        if method is None or not callable(method):
            raise NotImplementedError("Adapter does not support recall_aggregated")

        result = method(memory_type=memory_type, limit_per_type=limit_per_type)
        return {k: [r.to_dict() for r in v] for k, v in result.items()}

    def recall_timeline(
        self,
        topic: str,
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Recall memories for a topic ordered as a timeline."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        method = getattr(self._adapter, "recall_timeline", None)
        if method is None or not callable(method):
            raise NotImplementedError("Adapter does not support recall_timeline")

        results = method(topic=topic, limit=limit)
        return [r.to_dict() for r in results]

    # ── Knowledge Graph (v0.7.0) ────────────────────────────────

    def recall_by_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories mentioning a specific entity (v0.7.0).

        Uses the knowledge graph to find all memories that mention the
        given entity. Requires an adapter with ``graph: True`` capability.

        Args:
            entity_text: The entity text to search for.
            entity_type: Optional entity type filter (acronym/concept/tool).
            limit: Maximum results (default 10).

        Returns:
            List of memory dicts containing the entity.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return []
        return self._adapter.recall_by_entity(entity_text, entity_type, self._namespace, limit)

    def recall_by_relation(
        self,
        entity_text: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories connected to an entity via relations (v0.7.0).

        Traverses the knowledge graph to find memories linked to the given
        entity through explicit relations (e.g., "prefers", "works_on").

        Args:
            entity_text: The entity to find relations for.
            relation_type: Optional relation type filter.
            direction: "outgoing", "incoming", or "both" (default).
            limit: Maximum results.

        Returns:
            List of memory dicts connected via relations.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return []
        return self._adapter.recall_by_relation(entity_text, relation_type, direction, self._namespace, limit)

    def recall_graph(
        self,
        entity_text: str,
        max_hops: int = 2,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Multi-hop graph traversal from an entity (v0.7.0).

        Performs BFS traversal of the knowledge graph starting from the
        given entity, collecting all connected entities and memories
        within ``max_hops`` hops.

        Args:
            entity_text: The starting entity.
            max_hops: Maximum traversal depth (default 2).
            limit: Maximum memories to return.

        Returns:
            Dict with "entities" (list of connected entities) and
            "memories" (list of connected memories).
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return {"entities": [], "memories": []}
        return self._adapter.recall_graph(entity_text, max_hops, self._namespace, limit)

    def recall_shortest_path(
        self,
        src_entity: str,
        dst_entity: str,
        max_hops: int = 4,
    ) -> Dict[str, Any]:
        """Find the shortest path between two entities (v0.8.0).

        Uses bidirectional BFS to find the shortest path in the knowledge
        graph between two entities. Useful for understanding how concepts
        are connected.

        Args:
            src_entity: The source entity text.
            dst_entity: The destination entity text.
            max_hops: Maximum path length to search (default 4, hard cap 10).

        Returns:
            Dict with "path" (list of entity texts from src to dst),
            "length" (number of edges, 0 if src==dst, -1 if no path),
            and "found" (bool).
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return {"path": [], "length": -1, "found": False}
        return self._adapter.shortest_path(src_entity, dst_entity, max_hops, self._namespace)

    def recall_memory_impact(
        self,
        memory_id: str,
    ) -> Dict[str, Any]:
        """Compute the graph impact of a memory (v0.8.0).

        Calculates how influential a memory is in the knowledge graph.
        impact_score = entity_count * 0.4 + relation_count * 0.4 + cross_namespace * 0.2

        Args:
            memory_id: The memory's storage_key.

        Returns:
            Dict with "memory_id", "entity_count", "relation_count",
            "cross_namespace" (bool), and "impact_score" (float).
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return {
                "memory_id": memory_id,
                "entity_count": 0,
                "relation_count": 0,
                "cross_namespace": False,
                "impact_score": 0.0,
            }
        return self._adapter.get_memory_impact(memory_id, self._namespace)

    def add_graph_relation(
        self,
        src_entity: str,
        dst_entity: str,
        relation_type: str,
        source_memory_key: Optional[str] = None,
        weight: float = 1.0,
        confidence: str = "EXTRACTED",
    ) -> bool:
        """Add a relation between two entities in the knowledge graph (v0.7.0).

        Args:
            src_entity: Source entity text.
            dst_entity: Destination entity text.
            relation_type: Relation type (e.g. "prefers", "works_on").
            source_memory_key: Optional memory key that evidences this relation.
            weight: Relation strength (default 1.0).
            confidence: Edge confidence label (v0.8.0). One of
                "EXTRACTED" (default), "INFERRED", "AMBIGUOUS".

        Returns:
            True if relation was added successfully.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not self._adapter.capabilities.get("graph", False):
            return False
        return self._adapter.add_graph_relation(
            src_entity,
            dst_entity,
            relation_type,
            source_memory_key,
            weight,
            self._namespace,
            confidence,
        )

    # ── Session Dual-Layer Memory (v0.7.0) ──────────────────────

    def set_session(self, session_id: str) -> None:
        """Set the current session for dual-layer memory (v0.7.0).

        When a session is active, recall operations check the session cache
        first (O(1)) before falling back to the persistent layer (FTS5).
        New memories stored during the session are also added to the session
        cache for fast subsequent retrieval.

        Args:
            session_id: Unique session identifier.
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        self._session_id = session_id

    def end_session(self) -> None:
        """End the current session and clear session cache (v0.7.0)."""
        session_id = getattr(self, "_session_id", None)
        if session_id and self._adapter and hasattr(self._adapter, "_cache"):
            cache = getattr(self._adapter, "_cache", None)
            if cache:
                try:
                    cache.invalidate_session(session_id)
                except (AttributeError, TypeError) as e:
                    logger.debug("Session cache invalidation skipped: %s", e)
        self._session_id = None

    def preload_session(self, limit: int = 50) -> int:
        """Pre-load high-frequency memories into the session cache (v0.7.0).

        Loads the top-N memories by importance_score from the persistent
        layer into the session cache for O(1) recall within the session.

        Args:
            limit: Maximum memories to pre-load (default 50).

        Returns:
            Number of memories pre-loaded.
        """
        session_id = getattr(self, "_session_id", None)
        if not session_id or not self._adapter:
            return 0
        if not self._adapter.has_cache:
            return 0

        # Recall top memories by importance (broad query to get diverse set)
        try:
            results = self._adapter.recall(
                "",
                filters=None,
                limit=limit,
                namespaces=[self._namespace],
                update_access=False,
            )
            memories = [r.to_dict() if hasattr(r, "to_dict") else r for r in results]
            if memories:
                cache = getattr(self._adapter, "_cache", None)
                if cache:
                    return int(cache.session_preload(session_id, memories))
        except (KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.warning("Session preload failed: %s", e)
        return 0

    def promote_to_permanent(self, memory_key: str) -> bool:
        """Boost a memory's importance for permanent retention (v0.7.0).

        Increases the access_count and importance_score of a memory so it
        survives longer in the cache and ranks higher in recall results.

        Args:
            memory_key: The storage_key of the memory to promote.

        Returns:
            True if the memory was promoted.
        """
        if not self._adapter or not memory_key:
            return False
        if not isinstance(self._adapter, RawConnectionProvider):
            return False
        try:
            conn = self._adapter.get_raw_connection()
            cursor = conn.execute(
                "UPDATE memories SET "
                "access_count = access_count + 1, "
                "importance_score = MIN(importance_score + 0.05, 1.0), "
                "last_accessed_at = ? "
                "WHERE storage_key = ?",
                (datetime.now(timezone.utc).isoformat(), memory_key),
            )
            conn.commit()
            return bool(cursor.rowcount > 0)
        except (AttributeError, TypeError, RuntimeError) as e:
            logger.warning("promote_to_permanent failed: %s", e)
            return False

    # ── Memify Consolidation (v0.7.2) ───────────────────────────

    def consolidate_memories(
        self,
        namespace: Optional[str] = None,
        min_co_occurrence: int = 3,
        max_derived: int = 10,
        stale_days: int = 90,
        min_importance: float = 0.3,
    ) -> Dict[str, Any]:
        """Consolidate memories via Memify three-phase refinement (v0.7.2).

        Phase 1: derive_facts — create derived memories from co-occurring entities.
        Phase 2: reinforce_edges — strengthen graph relations for co-occurring entities.
        Phase 3: auto_decay — reduce importance of stale, low-access memories.

        Args:
            namespace: Namespace scope (default: current namespace).
            min_co_occurrence: Minimum co-occurrence for derive/reinforce.
            max_derived: Maximum derived facts per run.
            stale_days: Days without access for decay.
            min_importance: Importance threshold for decay.

        Returns:
            Dict with derived_facts, edges_reinforced, decayed.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        ns = namespace or self._namespace
        return self._adapter.consolidate_memories(
            namespace=ns,
            min_co_occurrence=min_co_occurrence,
            max_derived=max_derived,
            stale_days=stale_days,
            min_importance=min_importance,
        )

    # ── Multi-Mode Retrieval (v0.7.1) ────────────────────────────

    def recall_by_time(
        self,
        start: datetime,
        end: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories within a time range (v0.7.1).

        Args:
            start: Start datetime (inclusive). Timezone-aware recommended.
            end: End datetime (exclusive). Defaults to now.
            filters: Optional metadata filters (same as recall()).
            limit: Maximum results (default 50).

        Returns:
            List of memory dicts ordered by created_at descending.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not start:
            raise ValueError("start datetime is required")
        results = self._adapter.recall_by_time(start, end, filters, limit, [self._namespace])
        return list(results)

    def recall_semantic(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Pure vector similarity search (v0.7.1).

        Bypasses FTS5 and RRF fusion — returns raw vector similarity results.
        Requires vector search enabled (capabilities["vector_search"] == True).

        Args:
            query: Natural language query.
            top_k: Number of results (default 10).
            filters: Optional metadata filters.

        Returns:
            List of memory dicts ordered by vector similarity descending.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        if not self._adapter.capabilities.get("vector_search", False):
            return []
        return list(self._adapter.recall_semantic(query, top_k, filters, [self._namespace]))

    def recall_hybrid(
        self,
        query: str,
        fts_weight: Optional[float] = None,
        vec_weight: Optional[float] = None,
        rrf_k: Optional[int] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Explicit hybrid search with configurable RRF weights (v0.7.1).

        Exposes the existing RRF fusion with per-call weight override.
        If weights are None, uses adapter defaults.

        Args:
            query: Search query.
            fts_weight: FTS rank weight (default: adapter config).
            vec_weight: Vector rank weight (default: adapter config).
            rrf_k: RRF constant k (default: adapter config).
            limit: Maximum results.
            filters: Optional metadata filters.

        Returns:
            List of memory dicts ordered by fused RRF score descending.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        validate_query(query or "")
        validate_limit(limit)
        return list(
            self._adapter.recall_hybrid(query, fts_weight, vec_weight, rrf_k, limit, filters, [self._namespace])
        )

    def recall_multi_mode(
        self,
        query: str,
        modes: Optional[List[str]] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[tuple] = None,
        entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unified multi-mode retrieval interface (v0.7.1).

        Executes multiple retrieval modes and returns results grouped by mode,
        plus a merged "best" list deduplicated by storage_key.

        Args:
            query: Search query (used for fts/vector/hybrid modes).
            modes: Retrieval modes. Default: ["fts", "vector"] or ["fts"].
                   Options: "fts", "vector", "hybrid", "graph", "time", "entity".
            limit: Maximum results per mode.
            filters: Optional metadata filters.
            time_range: (start, end) for "time" mode.
            entity: Entity text for "entity"/"graph" modes.

        Returns:
            Dict with "modes", "merged", "mode_count", "total_count".
        """
        if not self._adapter:
            raise StorageNotConfiguredError()
        validate_limit(limit)
        result = self._adapter.recall_multi_mode(
            query,
            modes,
            limit,
            filters,
            [self._namespace],
            time_range,
            entity,
        )
        return dict(result)
