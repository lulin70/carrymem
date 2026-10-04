"""Phase 4 Reflection Run/Proposal contract tests (INV-RR1-3, INV-P1-4, INV-D1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.adapters.sqlite.reflection import classify_risk
from carrymem.layers.memify import MemifyEngine, find_decay_candidates
from carrymem.monitoring import get_metrics_collector


@pytest.fixture
def adapter():
    value = SQLiteAdapter(":memory:", namespace="default", enable_vector_search=False, enable_semantic_recall=False)
    yield value
    value.close()


@pytest.fixture
def clean_metrics():
    collector = get_metrics_collector()
    collector.reset()
    yield collector
    collector.reset()


def start_run(adapter, **overrides):
    args = {
        "namespace": "default",
        "reflection_type": "decay",
        "strategy_version": "s1",
        "input_snapshot": "snap-1",
        "config_snapshot": "{}",
    }
    args.update(overrides)
    return adapter.start_reflection_run(**args)


def expire_payload(**overrides):
    payload = {"expires_at": "2030-01-01T00:00:00+00:00"}
    payload.update(overrides)
    return payload


def store_memory(adapter, content: str) -> str:
    stored = adapter.store_entry(MemoryEntry(content=content, type="fact_declaration"))
    return stored.storage_key


class TestReflectionRunContract:
    def test_capabilities_advertise_phase4_ledgers(self, adapter):
        assert adapter.capabilities["reflection_runs"] is True
        assert adapter.capabilities["reflection_proposals"] is True

    def test_schema_tables_and_ledger_row(self, tmp_path):
        first = SQLiteAdapter(str(tmp_path / "p4.db"), enable_vector_search=False, enable_semantic_recall=False)
        try:
            tables = {
                row[0]
                for row in first.get_raw_connection()
                .execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                .fetchall()
            }
            assert {"memory_reflection_runs", "memory_reflection_outputs"}.issubset(tables)
            ledger = (
                first.get_raw_connection()
                .execute(
                    "SELECT status FROM carrymem_migrations WHERE migration_id = 'v220_phase4_reflection_proposal'"
                )
                .fetchone()
            )
            assert ledger is not None and ledger["status"] == "success"
        finally:
            first.close()
        second = SQLiteAdapter(str(tmp_path / "p4.db"), enable_vector_search=False, enable_semantic_recall=False)
        second.close()

    def test_invalid_reflection_type_rejected(self, adapter):
        with pytest.raises(ValueError, match="reflection_type"):
            start_run(adapter, reflection_type="free_text")

    def test_inv_rr1_completed_run_is_reused_not_reexecuted(self, adapter, clean_metrics):
        run_id_1 = start_run(adapter)
        adapter.complete_reflection_run(run_id_1)
        run_id_2 = start_run(adapter)
        assert run_id_1 == run_id_2
        count = (
            adapter.get_raw_connection()
            .execute("SELECT COUNT(*) AS c FROM memory_reflection_runs WHERE input_snapshot = 'snap-1'")
            .fetchone()["c"]
        )
        assert count == 1
        assert clean_metrics.get_snapshot()["counters"].get("reflection_runs_reused", 0) >= 1

    def test_failed_run_resumes_with_same_identity(self, adapter):
        run_id = start_run(adapter)
        adapter.fail_reflection_run(run_id, "boom")
        resumed = start_run(adapter)
        assert resumed == run_id
        row = (
            adapter.get_raw_connection()
            .execute(
                "SELECT status, error_text FROM memory_reflection_runs WHERE run_id = ?",
                (run_id,),
            )
            .fetchone()
        )
        assert row["status"] == "running" and row["error_text"] is None

    def test_cancelled_run_cannot_resume(self, adapter):
        run_id = start_run(adapter)
        adapter.cancel_reflection_run(run_id)
        with pytest.raises(ValueError, match="cancelled"):
            start_run(adapter)

    def test_inv_rr2_cursor_persisted_for_running_run_only(self, adapter):
        run_id = start_run(adapter)
        adapter.update_reflection_cursor(run_id, "cursor-42")
        row = (
            adapter.get_raw_connection()
            .execute("SELECT input_cursor FROM memory_reflection_runs WHERE run_id = ?", (run_id,))
            .fetchone()
        )
        assert row["input_cursor"] == "cursor-42"
        adapter.complete_reflection_run(run_id)
        with pytest.raises(ValueError, match="not running"):
            adapter.update_reflection_cursor(run_id, "cursor-43")

    def test_inv_rr3_failed_run_does_not_pollute_business_rows(self, adapter):
        key = store_memory(adapter, "durable fact")
        run_id = start_run(adapter)
        adapter.fail_reflection_run(run_id, "strategy crashed")
        row = (
            adapter.get_raw_connection()
            .execute("SELECT content, superseded_at, expires_at FROM memories WHERE storage_key = ?", (key,))
            .fetchone()
        )
        assert row["content"] == "durable fact"
        assert row["superseded_at"] is None


class TestProposalContract:
    def test_create_and_read_roundtrip(self, adapter):
        run_id = start_run(adapter)
        key = store_memory(adapter, "stale memory")
        proposal_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "expire_projection",
            expire_payload(),
            {"strategy": "decay-stale", "evidence": {"support": 0, "contradiction": 0}},
            0.7,
            target_kind="memory",
            target_id=key,
        )
        proposal = adapter.get_reflection_proposal("default", proposal_id)
        assert proposal is not None
        assert proposal["status"] == "proposed"
        assert proposal["payload"] == expire_payload()
        assert proposal["risk_level"] == "low"

    def test_inv_p2_duplicate_payload_is_idempotent(self, adapter):
        run_id = start_run(adapter)
        key = store_memory(adapter, "dedup candidate")
        first = adapter.create_reflection_proposal(
            "default",
            run_id,
            "expire_projection",
            expire_payload(),
            {"strategy": "decay"},
            0.6,
            target_kind="memory",
            target_id=key,
        )
        second = adapter.create_reflection_proposal(
            "default",
            run_id,
            "expire_projection",
            expire_payload(),
            {"strategy": "decay"},
            0.6,
            target_kind="memory",
            target_id=key,
        )
        assert first == second
        count = (
            adapter.get_raw_connection().execute("SELECT COUNT(*) AS c FROM memory_reflection_outputs").fetchone()["c"]
        )
        assert count == 1

    def test_inv_p1_high_risk_cannot_be_auto_approved(self, adapter):
        run_id = start_run(adapter)
        old_key = store_memory(adapter, "old conclusion")
        new_key = store_memory(adapter, "replacement conclusion")
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
        assert adapter.get_reflection_proposal("default", proposal_id)["status"] == "approved"

    def test_inv_p4_evidenceless_fact_candidate_capped(self, adapter):
        run_id = start_run(adapter)
        with pytest.raises(ValueError, match="INV-P4"):
            adapter.create_reflection_proposal(
                "default",
                run_id,
                "fact_candidate",
                {"subject": "x", "value": "y"},
                {"strategy": "pattern"},
                0.9,
            )

    def test_target_required_for_application_types(self, adapter):
        run_id = start_run(adapter)
        with pytest.raises(ValueError, match="target_kind"):
            adapter.create_reflection_proposal(
                "default", run_id, "expire_projection", expire_payload(), {"strategy": "decay"}, 0.5
            )

    def test_proposals_only_inside_running_run(self, adapter):
        run_id = start_run(adapter)
        adapter.complete_reflection_run(run_id)
        with pytest.raises(ValueError, match="running"):
            adapter.create_reflection_proposal(
                "default",
                run_id,
                "expire_projection",
                expire_payload(),
                {"strategy": "decay"},
                0.5,
                target_kind="memory",
                target_id="missing",
            )

    def test_namespace_mismatch_rejected(self, adapter):
        run_id = start_run(adapter)
        with pytest.raises(ValueError, match="namespace"):
            adapter.create_reflection_proposal(
                "other",
                run_id,
                "expire_projection",
                expire_payload(),
                {"strategy": "decay"},
                0.5,
                target_kind="memory",
                target_id="k",
            )

    def test_sensitive_payload_blocked(self, adapter):
        run_id = start_run(adapter)
        key = store_memory(adapter, "api key sk-abc123")
        with pytest.raises(ValueError, match="redaction"):
            adapter.create_reflection_proposal(
                "default",
                run_id,
                "expire_projection",
                expire_payload(note="token=ghp_secretvalue123456"),
                {"strategy": "decay"},
                0.5,
                target_kind="memory",
                target_id=key,
            )


class TestApplyRollbackSemantics:
    def _propose_expire(self, adapter):
        run_id = start_run(adapter)
        key = store_memory(adapter, "temporary conclusion")
        proposal_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "expire_projection",
            expire_payload(),
            {"strategy": "decay", "evidence": {"support": 0, "contradiction": 0}},
            0.6,
            target_kind="memory",
            target_id=key,
        )
        return proposal_id, key

    def test_apply_requires_approval(self, adapter):
        proposal_id, _key = self._propose_expire(adapter)
        with pytest.raises(ValueError, match="approved"):
            adapter.apply_reflection_proposal("default", proposal_id)

    def test_apply_then_inv_p3_rollback_ref_recorded(self, adapter):
        proposal_id, key = self._propose_expire(adapter)
        original_expires = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (key,))
            .fetchone()["expires_at"]
        )
        adapter.approve_reflection_proposal("default", proposal_id, "user")
        result = adapter.apply_reflection_proposal("default", proposal_id)
        assert result["status"] == "applied" and result["rollback_ref"]
        row = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (key,))
            .fetchone()
        )
        assert row["expires_at"] == "2030-01-01T00:00:00+00:00"
        proposal = adapter.get_reflection_proposal("default", proposal_id)
        assert proposal["rollback_ref"] and proposal["applied_at"]
        adapter.rollback_reflection_proposal("default", proposal_id)
        restored = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (key,))
            .fetchone()["expires_at"]
        )
        assert restored == original_expires

    def test_apply_is_idempotent(self, adapter):
        proposal_id, _key = self._propose_expire(adapter)
        adapter.approve_reflection_proposal("default", proposal_id, "user")
        first = adapter.apply_reflection_proposal("default", proposal_id)
        second = adapter.apply_reflection_proposal("default", proposal_id)
        assert second["reused"] is True
        assert first["status"] == second["status"] == "applied"

    def test_apply_missing_target_fails_closed(self, adapter):
        run_id = start_run(adapter)
        proposal_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "expire_projection",
            expire_payload(),
            {"strategy": "decay"},
            0.5,
            target_kind="memory",
            target_id="ghost-key",
        )
        adapter.approve_reflection_proposal("default", proposal_id, "user")
        with pytest.raises(ValueError, match="apply failed"):
            adapter.apply_reflection_proposal("default", proposal_id)
        assert adapter.get_reflection_proposal("default", proposal_id)["status"] == "failed"

    def test_handlerless_type_fails_closed(self, adapter):
        run_id = start_run(adapter)
        proposal_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "rule_candidate",
            {"pattern": "always respond in Python"},
            {"strategy": "promote", "evidence": {"support": 3, "contradiction": 0}},
            0.8,
        )
        assert adapter.get_reflection_proposal("default", proposal_id)["risk_level"] == "high"
        adapter.approve_reflection_proposal("default", proposal_id, "user")
        with pytest.raises(ValueError, match="fail-closed"):
            adapter.apply_reflection_proposal("default", proposal_id)
        assert adapter.get_reflection_proposal("default", proposal_id)["status"] == "failed"

    def test_inv_b1_f4_rollback_restores_projection_only(self, adapter):
        proposal_id, key = self._propose_expire(adapter)
        original_expires = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (key,))
            .fetchone()["expires_at"]
        )
        adapter.approve_reflection_proposal("default", proposal_id, "user")
        adapter.apply_reflection_proposal("default", proposal_id)
        result = adapter.rollback_reflection_proposal("default", proposal_id)
        assert result["status"] == "rolled_back"
        row = (
            adapter.get_raw_connection()
            .execute("SELECT content, expires_at, superseded_at FROM memories WHERE storage_key = ?", (key,))
            .fetchone()
        )
        assert row["content"] == "temporary conclusion"  # INV-B1: raw layer untouched
        assert row["expires_at"] == original_expires
        assert row["superseded_at"] is None
        assert adapter.get_reflection_proposal("default", proposal_id)["status"] == "rolled_back"

    def test_rollback_requires_applied_status(self, adapter):
        proposal_id, _key = self._propose_expire(adapter)
        with pytest.raises(ValueError, match="not applied"):
            adapter.rollback_reflection_proposal("default", proposal_id)

    def test_apply_auto_low_risk_only_touches_low_risk(self, adapter):
        run_id = start_run(adapter)
        key = store_memory(adapter, "auto candidate")
        low_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "expire_projection",
            expire_payload(),
            {"strategy": "decay"},
            0.6,
            target_kind="memory",
            target_id=key,
        )
        high_id = adapter.create_reflection_proposal(
            "default",
            run_id,
            "rule_candidate",
            {"pattern": "always answer briefly"},
            {"strategy": "promote"},
            0.8,
        )
        applied = adapter.apply_auto_low_risk_reflections("default", run_id)
        assert applied == [low_id]
        assert adapter.get_reflection_proposal("default", low_id)["status"] == "applied"
        assert adapter.get_reflection_proposal("default", high_id)["status"] == "proposed"


class TestRiskClassification:
    @pytest.mark.parametrize(
        "proposal_type,payload,evidence,expected",
        [
            ("expire_projection", {"expires_at": "2030-01-01T00:00:00+00:00"}, 0, "low"),
            ("graph_update", {"action": "reinforce", "weight": 2.0, "max_weight": 5.0}, 0, "low"),
            ("graph_update", {"action": "reinforce", "weight": 2.0, "max_weight": 99.0}, 0, "high"),
            ("graph_update", {"action": "rewrite", "weight": 2.0, "max_weight": 5.0}, 0, "high"),
            ("dedup_merge", {"keep": "a", "drop": "b"}, 2, "low"),
            ("dedup_merge", {"keep": "a", "drop": "b"}, 1, "high"),
            ("rule_candidate", {"pattern": "forbid x"}, 5, "high"),
            ("model_claim", {"claim": "x"}, 5, "high"),
            ("fact_candidate", {"subject": "x"}, 5, "high"),
            ("supersede", {"new_storage_key": "k"}, 5, "high"),
            ("unknown_type", {}, 5, "high"),
        ],
    )
    def test_matrix(self, proposal_type, payload, evidence, expected):
        assert classify_risk(proposal_type, payload, evidence) == expected


def _tune(adapter, key, importance=None, access_count=None, last_accessed=None, metadata=None, superseded_at=None):
    """Explicitly steer the decay-gate inputs of one seeded memory."""
    conn = adapter.get_raw_connection()
    conn.execute(
        "UPDATE memories SET importance_score = COALESCE(?, importance_score), "
        "access_count = COALESCE(?, access_count), "
        "last_accessed_at = COALESCE(?, last_accessed_at), "
        "metadata = COALESCE(?, metadata), "
        "superseded_at = COALESCE(?, superseded_at) "
        "WHERE storage_key = ?",
        (importance, access_count, last_accessed, metadata, superseded_at, key),
    )
    conn.commit()


def _seed_decay_scenario(adapter):
    """Seed five memories covering every decay-gate outcome."""
    now_iso = datetime.now(timezone.utc).isoformat()

    def seed(content):
        stored = adapter.store_entry(MemoryEntry(content=content, type="fact_declaration"))
        return stored.storage_key

    keys = {
        "stale": seed("stale unused note about caches"),
        "fresh": seed("fresh important note about caches"),
        "accessed": seed("accessed low-importance note about caches"),
        "decayed": seed("already decayed note about caches"),
    }
    _tune(adapter, keys["stale"], importance=0.1)
    _tune(adapter, keys["fresh"], importance=0.9)
    _tune(adapter, keys["accessed"], importance=0.1, access_count=1, last_accessed=now_iso)
    _tune(adapter, keys["decayed"], importance=0.1, metadata='{"decayed": 1}')
    superseded_key = seed("superseded stale note about caches")
    _tune(adapter, superseded_key, importance=0.1, superseded_at=now_iso)
    keys["superseded"] = superseded_key
    candidates = find_decay_candidates(adapter.get_raw_connection(), "default")
    return keys, candidates


class TestDecayReflectionParity:
    """Contract §6 migration slice: memify decay gate → expire proposals."""

    def test_shared_gate_matches_auto_decay_effect(self, adapter):
        keys, candidates = _seed_decay_scenario(adapter)
        assert candidates == [keys["stale"]]
        MemifyEngine(adapter=adapter).auto_decay()
        decayed_rows = (
            adapter.get_raw_connection()
            .execute("SELECT storage_key FROM memories WHERE json_extract(metadata, '$.decayed') = 1")
            .fetchall()
        )
        # Exclude the pre-seeded already-decayed memory: the gate must not
        # have touched it again.
        newly_decayed = {row["storage_key"] for row in decayed_rows} - {keys["decayed"]}
        assert newly_decayed == set(candidates)

    def test_reflect_decay_proposes_for_exactly_gate_candidates(self, adapter):
        keys, candidates = _seed_decay_scenario(adapter)
        result = adapter.reflect_decay("default", auto_apply=False)
        assert result["candidates"] == len(candidates)
        assert result["proposals_created"] == len(candidates)
        proposals = adapter.list_reflection_proposals("default", run_id=result["run_id"])
        assert {p["target_id"] for p in proposals} == set(candidates)
        assert all(p["status"] == "proposed" and p["risk_level"] == "low" for p in proposals)

    def test_reflect_decay_auto_apply_then_idempotent_replay(self, adapter):
        keys, candidates = _seed_decay_scenario(adapter)
        first = adapter.reflect_decay("default", auto_apply=True)
        assert set(first["applied"]) == {p for p in first["applied"]}
        assert len(first["applied"]) == len(candidates)
        stale_row = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (keys["stale"],))
            .fetchone()
        )
        run_row = (
            adapter.get_raw_connection()
            .execute("SELECT started_at FROM memory_reflection_runs WHERE run_id = ?", (first["run_id"],))
            .fetchone()
        )
        expected_expiry = (
            datetime.fromisoformat(run_row["started_at"]).replace(tzinfo=timezone.utc) + timedelta(days=30)
        ).isoformat()
        assert stale_row["expires_at"] == expected_expiry

        second = adapter.reflect_decay("default", auto_apply=True)
        assert second["run_id"] == first["run_id"]  # INV-RR1: reuse
        assert second["proposals_total"] == first["proposals_total"]  # INV-P2: no duplicates
        assert second["applied"] == []  # nothing left proposed

    def test_reflect_decay_rollback_restores_previous_expiry(self, adapter):
        keys, _candidates = _seed_decay_scenario(adapter)
        original = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (keys["stale"],))
            .fetchone()["expires_at"]
        )
        result = adapter.reflect_decay("default", auto_apply=True)
        proposal_id = result["applied"][0]
        adapter.rollback_reflection_proposal("default", proposal_id)
        restored = (
            adapter.get_raw_connection()
            .execute("SELECT expires_at FROM memories WHERE storage_key = ?", (keys["stale"],))
            .fetchone()["expires_at"]
        )
        assert restored == original

    def test_twin_db_legacy_and_proposal_paths_agree_on_candidates(self, tmp_path):
        adapter_old = SQLiteAdapter(str(tmp_path / "old.db"), enable_vector_search=False, enable_semantic_recall=False)
        adapter_new = SQLiteAdapter(str(tmp_path / "new.db"), enable_vector_search=False, enable_semantic_recall=False)
        try:
            keys_old, _candidates = _seed_decay_scenario(adapter_old)
            keys_new, _candidates = _seed_decay_scenario(adapter_new)

            MemifyEngine(adapter=adapter_old).auto_decay()
            legacy_decayed = {
                row["storage_key"]
                for row in adapter_old.get_raw_connection()
                .execute("SELECT storage_key FROM memories WHERE json_extract(metadata, '$.decayed') = 1")
                .fetchall()
            } - {
                keys_old["decayed"]
            }  # exclude the pre-seeded already-decayed memory

            result = adapter_new.reflect_decay("default", auto_apply=True)
            proposal_targets = {
                p["target_id"]
                for p in adapter_new.list_reflection_proposals("default", run_id=result["run_id"], status="applied")
            }

            assert proposal_targets == legacy_decayed, "对拍: both paths must select the same candidates"
            assert keys_new["stale"] in proposal_targets
            # Effects intentionally differ (contract §6): legacy halves
            # importance, the proposal path sets an expiry — neither deletes.
            assert (
                adapter_new.get_raw_connection()
                .execute("SELECT COUNT(*) AS c FROM memories WHERE storage_key = ?", (keys_new["stale"],))
                .fetchone()["c"]
                == 1
            )
        finally:
            adapter_old.close()
            adapter_new.close()
