"""Realistic user journey E2E for Phase 4: propose -> approve -> apply -> rollback.

Mirrors the approved release requirement: a reflection proposal must only
change what recall shows, must record how to undo itself, and must never
touch the raw memory layer.
"""

from __future__ import annotations

import pytest

from carrymem import CarryMem
from carrymem.adapters.base import MemoryEntry


@pytest.fixture
def cm(tmp_path):
    instance = CarryMem(storage="sqlite", db_path=str(tmp_path / "e2e-reflection.db"), namespace="default")
    yield instance
    instance.close()


def _raw_row(cm, storage_key: str):
    return (
        cm._adapter.get_raw_connection()
        .execute(
            "SELECT content, expires_at, superseded_at FROM memories WHERE storage_key = ?",
            (storage_key,),
        )
        .fetchone()
    )


class TestReflectionProposalUserJourney:
    def test_expire_proposal_full_lifecycle(self, cm):
        retained = cm.classify_and_remember("I prefer bullet points in summaries")
        storage_key = retained["storage_keys"][0]

        adapter = cm._adapter
        namespace = "default"
        run_id = adapter.start_reflection_run(
            namespace,
            "decay",
            "decay-strategy-v1",
            "snapshot-1",
            '{"min_confidence": 0.5}',
        )
        proposal_id = adapter.create_reflection_proposal(
            namespace,
            run_id,
            "expire_projection",
            {"expires_at": "2031-01-01T00:00:00+00:00"},
            {"strategy": "decay-stale", "evidence": {"support": 0, "contradiction": 0}},
            0.7,
            target_kind="memory",
            target_id=storage_key,
        )

        inspected = adapter.get_reflection_proposal(namespace, proposal_id)
        assert inspected["status"] == "proposed" and inspected["risk_level"] == "low"

        adapter.approve_reflection_proposal(namespace, proposal_id, "user")
        before_recall = cm.recall_memories("bullet points")
        assert any(item["storage_key"] == storage_key for item in before_recall)
        original_expires = _raw_row(cm, storage_key)["expires_at"]

        applied = adapter.apply_reflection_proposal(namespace, proposal_id)
        assert applied["status"] == "applied" and applied["rollback_ref"]
        row = _raw_row(cm, storage_key)
        assert row["expires_at"] == "2031-01-01T00:00:00+00:00"

        rollback_result = adapter.rollback_reflection_proposal(namespace, proposal_id)
        assert rollback_result["status"] == "rolled_back"
        row = _raw_row(cm, storage_key)
        assert row["expires_at"] == original_expires
        assert row["superseded_at"] is None

        after_recall = cm.recall_memories("bullet points")
        assert any(item["storage_key"] == storage_key for item in after_recall)

    def test_high_risk_supersede_requires_user_approval(self, cm):
        first = cm.classify_and_remember("I prefer Python for backend work")
        old_key = first["storage_keys"][0]
        # Direct API store (not a correction utterance) so the built-in
        # correction cascade does not supersede old_key before the proposal
        # does. Distinct topic so recall dedup cannot collapse the two rows.
        stored = cm._adapter.store_entry(MemoryEntry(content="My editor theme is dark", type="user_preference"))
        new_key = stored.storage_key

        adapter = cm._adapter
        run_id = adapter.start_reflection_run(
            "default",
            "conflict_scan",
            "conflict-strategy-v1",
            "snapshot-2",
            "{}",
        )
        proposal_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "supersede",
            {"new_storage_key": new_key},
            {"strategy": "user-correction", "evidence": {"support": 1, "contradiction": 0}},
            0.95,
            target_kind="memory",
            target_id=old_key,
        )
        proposal = adapter.get_reflection_proposal("default", proposal_id)
        assert proposal["risk_level"] == "high"

        with pytest.raises(ValueError, match="INV-P1"):
            adapter.approve_reflection_proposal("default", proposal_id, "auto")

        adapter.approve_reflection_proposal("default", proposal_id, "user")
        applied = adapter.apply_reflection_proposal("default", proposal_id)
        assert applied["status"] == "applied"
        row = _raw_row(cm, old_key)
        assert row["superseded_at"] is not None

        # INV-F4: the applied change is what recall stops showing. Query the
        # old memory's distinctive term: after supersede it must disappear;
        # after rollback it must be visible again.
        hidden = cm.recall_memories("Python")
        assert old_key not in [
            item["storage_key"] for item in hidden
        ], "superseded memory must leave default recall while the proposal is applied"

        adapter.rollback_reflection_proposal("default", proposal_id)
        row = _raw_row(cm, old_key)
        assert row["superseded_at"] is None
        restored = cm.recall_memories("Python")
        assert old_key in [item["storage_key"] for item in restored]
