#!/usr/bin/env python3
"""Phase 5 E2E: real-user journey through planned recall and budget gates.

Simulates how an agent actually uses CarryMem:
  store facts/preferences/corrections → build a RecallPlan → recall_with_plan
  → consume the result (legacy projection + JSON metadata) → keep using the
  legacy prompt-building APIs.

Uses only public user-facing APIs (no adapter internals) against a real
SQLite database, per the pre-release E2E requirement.
"""

import json

import pytest

from carrymem import CarryMem
from carrymem.recall_plan import BudgetSpec, OutputBudget
from carrymem.token_budget import TruncationReason


def _cm(tmp_path):
    return CarryMem(db_path=str(tmp_path / "phase5_e2e.db"))


class TestE2EPhase5PlannedRecallJourney:
    """Scenario: agent stores mixed memories, then recalls with a plan."""

    def test_planned_recall_full_user_journey_is_deterministic(self, tmp_path):
        cm = _cm(tmp_path)
        try:
            # 1. Real user inputs through the classification pipeline.
            cm.classify_and_remember("I work at Acme Corp as a backend engineer")
            cm.classify_and_remember("I prefer concise answers", force_type="user_preference")
            cm.classify_and_remember("Do NOT use Java for our services", force_type="correction")

            # 2. Build a plan the way an agent would for a correction task.
            plan = cm.build_recall_plan(
                query=None,
                task="correction_resolution",
                modes=["fts"],
                max_results=5,
            )

            # 3. Executing the same plan twice must be fully deterministic.
            first = cm.recall_with_plan(plan)
            second = cm.recall_with_plan(plan)
            assert first.plan_fingerprint == second.plan_fingerprint == plan.fingerprint
            assert first.to_dict() == second.to_dict()

            # 4. Protected corrections rank ahead of ordinary memories.
            assert first.items, "planned recall must return the stored memories"
            assert first.items[0].memory.get("type") == "correction"

            # 5. Legacy projection stays a plain list of memory dicts.
            legacy = first.to_legacy_list()
            assert isinstance(legacy, list)
            assert legacy == [item.memory for item in first.items]

            # 6. The full envelope is JSON serializable (transport-ready).
            encoded = json.dumps(first.to_dict())
            assert first.plan_fingerprint in encoded
        finally:
            cm.close()

    def test_small_output_budget_keeps_correction_drops_ordinary(self, tmp_path):
        cm = _cm(tmp_path)
        try:
            cm.classify_and_remember("I like hiking on weekends")
            cm.classify_and_remember("Do NOT deploy on Fridays", force_type="correction")

            plan = cm.build_recall_plan(
                query=None,
                task="correction_resolution",
                modes=["fts"],
                max_results=5,
                budget=BudgetSpec(output=OutputBudget(max_tokens=300)),
            )
            result = cm.recall_with_plan(plan)

            # The hard budget always wins: reported usage stays within it.
            assert result.metadata["output_tokens"] <= 300
            assert result.truncations, "budget enforcement must record a truncation"
            assert any(t.reason_code is TruncationReason.OUTPUT_BUDGET_EXCEEDED for t in result.truncations)

            # Protected content survives; ordinary content is what gets cut.
            kept_types = [item.memory.get("type") for item in result.items]
            assert "correction" in kept_types
            assert result.status == "degraded"
        finally:
            cm.close()

    def test_plan_fingerprint_tracks_budget_changes(self, tmp_path):
        cm = _cm(tmp_path)
        try:
            cm.classify_and_remember("I prefer dark mode for coding")
            tight = cm.build_recall_plan(
                query="dark mode",
                task="fact_lookup",
                modes=["fts"],
                budget=BudgetSpec(output=OutputBudget(max_tokens=100)),
            )
            default = cm.build_recall_plan(query="dark mode", task="fact_lookup", modes=["fts"])
            assert tight.fingerprint != default.fingerprint
        finally:
            cm.close()

    def test_legacy_prompt_building_still_works_alongside_plans(self, tmp_path):
        cm = _cm(tmp_path)
        try:
            cm.classify_and_remember("I prefer dark mode for coding")

            # Legacy prompt paths keep their historical behavior.
            ctx = cm.build_context(context="How to set up my IDE?")
            assert ctx["memory_count"] == 1
            prompt = cm.build_qa_prompt("Which theme should I use?")
            assert "dark mode" in prompt.lower()

            # The planned path coexists with the legacy API on the same data.
            plan = cm.build_recall_plan(query="dark mode", task="fact_lookup", modes=["fts"])
            result = cm.recall_with_plan(plan)
            assert result.items
            assert result.items[0].memory.get("content") == ctx["memories"][0].get("content")
        finally:
            cm.close()
