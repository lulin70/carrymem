"""Phase 5 tests for deterministic recall planning and execution."""

import json
from dataclasses import FrozenInstanceError

import pytest

from carrymem import CarryMem, RecallResult
from carrymem.recall_plan import (
    BudgetSpec,
    ConflictPolicy,
    EvidenceBudget,
    OutputBudget,
    RecallPlan,
    RetrievalBudget,
    RetrievalMode,
    TaskMode,
    build_recall_plan,
)
from carrymem.token_budget import TruncationReason


def test_plan_is_deterministic_and_io_free(monkeypatch):
    monkeypatch.setattr("carrymem.recall_plan.validate_namespace", lambda value: value)
    first = build_recall_plan(query="Python", task="fact_lookup", namespace="team-a")
    second = build_recall_plan(query="Python", task="fact_lookup", namespace="team-a")

    assert first == second
    assert first.fingerprint == second.fingerprint
    assert first.snapshot().fingerprint == first.fingerprint
    assert first.snapshot().modes == (RetrievalMode.FTS, RetrievalMode.VECTOR, RetrievalMode.SEMANTIC)


def test_missing_namespace_fails_closed():
    with pytest.raises(ValueError, match="namespace is required"):
        build_recall_plan(query="x", task=TaskMode.FACT_LOOKUP, namespace="")

    with pytest.raises(ValueError, match="namespace is required"):
        build_recall_plan(query="x", task=TaskMode.FACT_LOOKUP, namespace=None)  # type: ignore[arg-type]


def test_unknown_task_mode_is_rejected():
    with pytest.raises(ValueError, match="invalid task"):
        build_recall_plan(query="x", task="free_form", namespace="team-a")


def test_explicit_modes_can_only_narrow_task_scope():
    plan = build_recall_plan(
        query="x",
        task=TaskMode.FACT_LOOKUP,
        namespace="team-a",
        modes=[RetrievalMode.FTS],
    )
    assert plan.modes == (RetrievalMode.FTS,)

    with pytest.raises(ValueError, match="not allowed"):
        build_recall_plan(
            query="x",
            task=TaskMode.FACT_LOOKUP,
            namespace="team-a",
            modes=[RetrievalMode.GRAPH],
        )


def test_task_policy_defaults_and_restrictions():
    conflict = build_recall_plan(query="x", task="conflict_explanation", namespace="team-a")
    assert conflict.conflict_policy is ConflictPolicy.ALWAYS

    with pytest.raises(ValueError, match="requires conflict_policy=always"):
        RecallPlan(
            query="x",
            task=TaskMode.CONFLICT_EXPLANATION,
            namespace="team-a",
            modes=(RetrievalMode.FTS,),
        )

    with pytest.raises(ValueError, match="only allowed for timeline_review"):
        build_recall_plan(
            query="x",
            task="fact_lookup",
            namespace="team-a",
            include_superseded=True,
        )


def test_budget_is_four_layer_and_plan_is_immutable():
    plan = build_recall_plan(query=None, task="fact_lookup", namespace="team-a")
    assert isinstance(plan.budget, BudgetSpec)
    assert plan.budget.retrieval.max_candidates == 100
    assert plan.budget.evidence.evidence_chars_total == 2000
    assert plan.budget.reflection.inline_timeout_ms == 100
    assert plan.budget.output.max_tokens == 2000

    with pytest.raises(FrozenInstanceError):
        plan.max_results = 1  # type: ignore[misc]


def test_legacy_recall_api_remains_list_projection(tmp_path):
    cm = CarryMem(
        storage="sqlite",
        db_path=str(tmp_path / "legacy.db"),
        auto_backup_interval=0,
    )
    try:
        assert isinstance(cm.build_recall_plan(query="x", task="fact_lookup"), RecallPlan)
        assert isinstance(cm.recall_memories("x"), list)
    finally:
        cm.close()


def test_recall_with_plan_propagates_fingerprint_and_legacy_projection(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), namespace="team-a", auto_backup_interval=0)
    try:
        cm.declare("I prefer Python", user_id="u")
        plan = cm.build_recall_plan(query="Python", task="fact_lookup", modes=[RetrievalMode.FTS], max_results=1)
        result = cm.recall_with_plan(plan)
        assert isinstance(result, RecallResult)
        assert result.plan_fingerprint == plan.fingerprint
        assert result.namespace == "team-a"
        assert len(result.items) <= 1
        assert result.to_legacy_list() == [item.memory for item in result.items]
    finally:
        cm.close()


def test_recall_plan_rejects_empty_modes():
    with pytest.raises(ValueError, match="at least one retrieval mode"):
        RecallPlan(
            query="x",
            task=TaskMode.FACT_LOOKUP,
            namespace="team-a",
            modes=(),
        )


def test_recall_with_plan_denies_cross_namespace(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), namespace="team-a", auto_backup_interval=0)
    try:
        plan = RecallPlan(
            query="x",
            task=TaskMode.FACT_LOOKUP,
            namespace="team-b",
            modes=(RetrievalMode.FTS,),
        )
        result = cm.recall_with_plan(plan)
        assert result.status == "denied"
        assert result.items == ()
        assert result.mode_failures[0].reason_code == "NAMESPACE_DENIED"
    finally:
        cm.close()


def test_recall_result_is_json_serializable(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        cm.declare("I prefer Python", user_id="u")
        plan = cm.build_recall_plan(query="Python", task="fact_lookup", modes=[RetrievalMode.FTS])
        result = cm.recall_with_plan(plan)
        json.dumps(result.to_dict())
        assert result.plan is not None
        assert result.plan.to_dict()["fingerprint"] == plan.fingerprint
    finally:
        cm.close()


def test_recall_with_plan_enforces_candidate_cap(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        for index in range(3):
            cm.declare(f"Python project fact {index}", user_id="u")
        plan = cm.build_recall_plan(
            query="Python",
            task="fact_lookup",
            modes=[RetrievalMode.FTS],
            max_results=3,
            budget=BudgetSpec(retrieval=RetrievalBudget(max_candidates=1)),
        )
        result = cm.recall_with_plan(plan)
        assert result.budget_usage.candidates <= 1
        assert any(
            truncation.reason_code is TruncationReason.RETRIEVAL_CANDIDATE_CAP for truncation in result.truncations
        )
    finally:
        cm.close()


def test_recall_with_plan_reports_graph_and_time_skips(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        plan = RecallPlan(
            query=None,
            task=TaskMode.PROJECT_CONTEXT,
            namespace="default",
            modes=(RetrievalMode.GRAPH, RetrievalMode.TIME),
        )
        result = cm.recall_with_plan(plan)
        assert {failure.mode for failure in result.mode_failures} == {"graph", "time"}
        assert all(failure.skipped for failure in result.mode_failures)
    finally:
        cm.close()


def test_recall_with_plan_falls_back_to_fts_and_dedupes_when_vector_unavailable(tmp_path):
    cm = CarryMem(
        storage="sqlite",
        db_path=str(tmp_path / "recall.db"),
        auto_backup_interval=0,
        config={"enable_vector_search": False},
    )
    try:
        assert cm._adapter.capabilities.get("vector_search") is False
        cm.declare("I prefer Python for data work", user_id="u")
        plan = cm.build_recall_plan(
            query="Python",
            task="fact_lookup",
            modes=[RetrievalMode.FTS, RetrievalMode.VECTOR],
        )
        result = cm.recall_with_plan(plan)
        vector_failures = [f for f in result.mode_failures if f.mode == "vector"]
        assert len(vector_failures) == 1
        assert vector_failures[0].reason_code == "VECTOR_UNAVAILABLE_FALLBACK"
        assert vector_failures[0].skipped is True
        assert any(
            truncation.reason_code is TruncationReason.VECTOR_UNAVAILABLE_FALLBACK for truncation in result.truncations
        )
        # Both the fts slot and the vector-fallback slot hit the same memory;
        # dedup must collapse them into one item instead of duplicating it.
        assert len(result.items) == 1
        assert "fts" in result.items[0].source_modes
    finally:
        cm.close()


def test_sensitivity_filter_removes_sensitive_candidates(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        cm.declare("my api key is sk-fake000000test000key000abc123456", user_id="u")
        cm.declare("I prefer Python for data work", user_id="u")
        plan = cm.build_recall_plan(query=None, task="fact_lookup", modes=[RetrievalMode.FTS])
        result = cm.recall_with_plan(plan)
        assert all("sk-fake" not in json.dumps(item.to_dict()) for item in result.items)
        assert any(truncation.reason_code is TruncationReason.SENSITIVITY_FILTERED for truncation in result.truncations)
        assert result.metadata.get("sensitivity_filtered") == 1
    finally:
        cm.close()


def test_sensitivity_strict_records_mode_failure(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        cm.declare("my api key is sk-fake000000test000key000abc123456", user_id="u")
        plan = cm.build_recall_plan(
            query=None,
            task="fact_lookup",
            modes=[RetrievalMode.FTS],
            sensitivity_policy="strict",
        )
        result = cm.recall_with_plan(plan)
        strict_failures = [f for f in result.mode_failures if f.reason_code == "SENSITIVITY_FILTERED"]
        assert len(strict_failures) == 1
        assert strict_failures[0].skipped is False
        assert result.items == ()
    finally:
        cm.close()


def _version_chain_fixture(cm):
    """Store two similar preferences so the auto-supersede path forms a chain.

    ``update_memory`` updates rows in place (same storage_key) and therefore
    never produces two memories under one version chain; the supersede path is
    what creates the two-key conflict group.
    """
    cm.declare("I prefer dark mode for coding", user_id="u")
    stored = cm.declare("I now prefer light mode for coding", user_id="u")
    assert stored["storage_keys"], "second declaration must store a memory"
    rows = cm.recall_memories(filters={"include_superseded": True}, update_access=False)
    chain_ids = [r.get("version_chain_id") for r in rows if r.get("version_chain_id")]
    assert len(set(chain_ids)) == 1, f"expected one version chain, got {chain_ids}"
    return rows


def test_conflict_policy_always_returns_conflict_views(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        _version_chain_fixture(cm)
        plan = cm.build_recall_plan(
            query=None,
            task="timeline_review",
            modes=[RetrievalMode.FTS],
            include_superseded=True,
            conflict_policy="always",
        )
        result = cm.recall_with_plan(plan)
        assert len(result.conflicts) == 1
        assert len(result.conflicts[0].storage_keys) == 2
        assert len(result.items) == 2
        json.dumps(result.to_dict())
    finally:
        cm.close()


def test_conflict_policy_hide_removes_conflicting_candidates(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        _version_chain_fixture(cm)
        plan = cm.build_recall_plan(
            query=None,
            task="timeline_review",
            modes=[RetrievalMode.FTS],
            include_superseded=True,
            conflict_policy="hide",
        )
        result = cm.recall_with_plan(plan)
        assert result.items == ()
        assert result.conflicts == ()
        assert any(
            truncation.reason_code is TruncationReason.CONFLICT_DEPRIORITIZED for truncation in result.truncations
        )
    finally:
        cm.close()


def test_conflict_policy_show_top_keeps_one_candidate_per_group(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        _version_chain_fixture(cm)
        plan = cm.build_recall_plan(
            query=None,
            task="timeline_review",
            modes=[RetrievalMode.FTS],
            include_superseded=True,
            conflict_policy="show_top",
        )
        result = cm.recall_with_plan(plan)
        assert len(result.items) == 1
        assert result.conflicts == ()
        assert any(
            truncation.reason_code is TruncationReason.CONFLICT_DEPRIORITIZED for truncation in result.truncations
        )
    finally:
        cm.close()


def test_evidence_budget_expands_then_caps_total_chars(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        target = cm.declare("CarryMem evidence target alpha", user_id="u")
        source = cm.declare("CarryMem evidence source beta", user_id="u")
        target_key = target["storage_keys"][0]
        source_key = source["storage_keys"][0]
        link_id = cm._adapter.add_evidence_link(
            "default",
            "memory",
            source_key,
            "snapshot-hash-beta",
            "memory",
            target_key,
            "supports",
        )
        assert link_id is not None

        generous = cm.build_recall_plan(
            query=None,
            task="fact_lookup",
            modes=[RetrievalMode.FTS],
            max_results=5,
            include_evidence=True,
            budget=BudgetSpec(evidence=EvidenceBudget(per_result_evidence=3, evidence_chars_total=100000)),
        )
        result = cm.recall_with_plan(generous)
        target_items = [i for i in result.items if i.memory.get("storage_key") == target_key]
        assert len(target_items) == 1
        assert len(target_items[0].evidence) == 1

        tiny = cm.build_recall_plan(
            query=None,
            task="fact_lookup",
            modes=[RetrievalMode.FTS],
            max_results=5,
            include_evidence=True,
            budget=BudgetSpec(evidence=EvidenceBudget(per_result_evidence=3, evidence_chars_total=1)),
        )
        capped = cm.recall_with_plan(tiny)
        capped_items = [i for i in capped.items if i.memory.get("storage_key") == target_key]
        assert len(capped_items) == 1
        assert capped_items[0].evidence == ()
        assert any(
            truncation.reason_code is TruncationReason.EVIDENCE_BUDGET_EXCEEDED for truncation in capped.truncations
        )
    finally:
        cm.close()


def test_correction_resolution_ranks_correction_first(tmp_path):
    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        cm.declare("I like Python for scripting", user_id="u")
        cm.classify_and_remember("Do NOT use Java for backend work", force_type="correction")
        plan = cm.build_recall_plan(query=None, task="correction_resolution", modes=[RetrievalMode.FTS])
        result = cm.recall_with_plan(plan)
        assert len(result.items) == 2
        assert result.items[0].memory.get("type") == "correction"
    finally:
        cm.close()


def test_output_hard_budget_degrades_instead_of_dropping_protected_content(tmp_path):
    from carrymem.adapters.base import MemoryEntry

    cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "recall.db"), auto_backup_interval=0)
    try:
        long_correction = (
            "Do NOT store secrets in plain config files. " * 10
            + "Always use the vault helper for credentials, rotate them monthly, "
            "never commit deployment keys to git, and keep staging and production "
            "namespaces strictly separated in every recall path we ship to users."
        )
        cm._adapter.store_entry(MemoryEntry(type="correction", content=long_correction))
        plan = cm.build_recall_plan(
            query=None,
            task="correction_resolution",
            modes=[RetrievalMode.FTS],
            budget=BudgetSpec(output=OutputBudget(max_tokens=260)),
        )
        result = cm.recall_with_plan(plan)
        assert result.status == "degraded"
        assert result.degraded is not None
        assert result.degraded.reason_code is TruncationReason.OUTPUT_BUDGET_EXCEEDED
        # Protected content is deterministically shortened, never silently dropped.
        assert len(result.items) == 1
        kept_content = result.items[0].memory.get("content") or ""
        assert 0 < len(kept_content) < len(long_correction)
        assert result.metadata["output_tokens"] <= 260
    finally:
        cm.close()


@pytest.mark.asyncio
async def test_async_recall_with_plan_matches_sync_contract(tmp_path):
    from carrymem import AsyncCarryMem

    cm = AsyncCarryMem(storage="sqlite", db_path=str(tmp_path / "async.db"))
    try:
        await cm.declare("I prefer Python for data work")
        plan = await cm.build_recall_plan(query="Python", task="fact_lookup", modes=[RetrievalMode.FTS])
        result = await cm.recall_with_plan(plan)
        assert result.plan_fingerprint == plan.fingerprint
        assert result.items
        assert result.to_legacy_list() == [item.memory for item in result.items]
    finally:
        await cm.close()
