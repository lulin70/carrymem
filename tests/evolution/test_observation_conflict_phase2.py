"""Phase 2 Observation/ConflictRecord contract tests."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from carrymem.adapters.base import MemoryEntry
from carrymem.adapters.sqlite import SQLiteAdapter
from carrymem.carrymem import CarryMem
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


def observation_args(**overrides):
    now = datetime.now(timezone.utc)
    args = {
        "namespace": "default",
        "subject": "backend language",
        "predicate": "preference_detected",
        "value": {"language": "Python"},
        "source_kind": "explicit_api",
        "source_ref": "source-1",
        "confidence": 0.9,
        "observed_at": now,
        "expires_at": now + timedelta(days=30),
        "admission": "explicit_api",
    }
    args.update(overrides)
    return args


class TestObservationContract:
    def test_capabilities_advertise_phase2_ledgers(self, adapter):
        assert adapter.capabilities["observation"] is True
        assert adapter.capabilities["conflict_records"] is True

    def test_observation_cannot_be_accepted_fact(self, adapter):
        row = (
            adapter.get_raw_connection()
            .execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'memory_observations'")
            .fetchone()
        )
        assert "accepted" not in row[0].lower()
        with pytest.raises(sqlite3.IntegrityError):
            adapter.get_raw_connection().execute(
                "INSERT INTO memory_observations "
                "(id, namespace, subject, predicate, value_json, source_kind, source_ref, confidence, "
                "observed_at, expires_at, created_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "obs_accepted",
                    "default",
                    "subject",
                    "entity_state",
                    "{}",
                    "explicit_api",
                    "source",
                    0.5,
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-02T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    "accepted",
                ),
            )

    def test_schema_and_ledger_survive_reopen(self, tmp_path):
        db_path = str(tmp_path / "phase2.db")
        first = SQLiteAdapter(db_path, enable_vector_search=False, enable_semantic_recall=False)
        tables = {
            row[0]
            for row in first.get_raw_connection()
            .execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            .fetchall()
        }
        assert {"memory_observations", "memory_conflicts"}.issubset(tables)
        ledger = (
            first.get_raw_connection()
            .execute(
                "SELECT migration_id, status FROM carrymem_migrations WHERE migration_id = ?",
                ("v210_phase2_observation_conflict",),
            )
            .fetchone()
        )
        assert tuple(ledger) == ("v210_phase2_observation_conflict", "success")
        first.close()

        second = SQLiteAdapter(db_path, enable_vector_search=False, enable_semantic_recall=False)
        assert second.list_observations("default") == []
        second.close()

    def test_namespace_isolation_and_validation(self, adapter):
        adapter.record_observation(**observation_args())
        assert len(adapter.list_observations("default")) == 1
        with pytest.raises(ValueError, match="namespace"):
            adapter.list_observations("other")
        with pytest.raises(ValueError, match="namespace"):
            adapter.record_observation(**observation_args(namespace="other"))

    @pytest.mark.parametrize(
        "field,value,pattern",
        [
            ("predicate", "unknown", "predicate"),
            ("source_kind", "unknown", "source_kind"),
            ("confidence", 1.1, "confidence"),
        ],
    )
    def test_closed_enums_and_confidence(self, adapter, field, value, pattern):
        with pytest.raises(ValueError, match=pattern):
            adapter.record_observation(**observation_args(**{field: value}))

    def test_admission_denial_increments_metric(self, adapter, clean_metrics):
        with pytest.raises(ValueError, match="admission"):
            adapter.record_observation(**observation_args(admission="internal_recall"))
        assert clean_metrics.get_snapshot()["counters"].get("observation_write_denied") == 1

    def test_ttl_and_redaction_are_enforced(self, adapter):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="expires_at"):
            adapter.record_observation(**observation_args(observed_at=now, expires_at=now))
        with pytest.raises(ValueError, match="blocked by redaction"):
            adapter.record_observation(**observation_args(value={"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456"}))

    def test_subject_redaction_is_enforced(self, adapter):
        with pytest.raises(ValueError, match="blocked by redaction"):
            adapter.record_observation(**observation_args(subject="sk-abcdefghijklmnopqrstuvwxyz123456"))

    def test_observation_count_per_retain_is_capped(self, tmp_path):
        """INV-O2: a single retain must not create more than two observations."""
        cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "cm_o2.db"), namespace="default")
        try:
            cm.classify_and_remember("I prefer Python for backend work")
            assert len(cm._adapter.list_observations("default", include_expired=True)) == 0
            cm.classify_and_remember("Actually I now prefer Rust for backend work, ignore what I said before")
            observations = cm._adapter.list_observations("default", include_expired=True)
            assert len(observations) <= 2
            assert len(observations) == 1
        finally:
            cm.close()

    def test_expired_and_unsupported_are_hidden_by_default(self, adapter):
        now = datetime.now(timezone.utc)
        expired_id = adapter.record_observation(
            **observation_args(
                source_ref="expired-source",
                observed_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1),
            )
        )
        live_id = adapter.record_observation(**observation_args(source_ref="live-source"))
        assert live_id
        assert [row["id"] for row in adapter.list_observations("default")] == [live_id]
        assert {row["id"] for row in adapter.list_observations("default", include_expired=True)} == {
            expired_id,
            live_id,
        }

        source = adapter.store_entry(MemoryEntry(content="source", type="fact_declaration"))
        unsupported_id = adapter.record_observation(**observation_args(source_ref=source.storage_key))
        assert adapter.delete(source.storage_key) is True
        assert adapter.list_observations("default", include_expired=True) != []
        assert unsupported_id not in {row["id"] for row in adapter.list_observations("default", include_expired=True)}
        assert unsupported_id in {
            row["id"] for row in adapter.list_observations("default", include_expired=True, include_unsupported=True)
        }

    def test_delete_nonexistent_memory_does_not_update_observation(self, adapter):
        observation_id = adapter.record_observation(**observation_args(source_ref="missing-memory"))
        assert adapter.delete("missing-memory") is False
        rows = adapter.list_observations("default", include_unsupported=True)
        assert [row["id"] for row in rows] == [observation_id]
        assert rows[0]["status"] == "valid"

    def test_retain_and_recall_do_not_write_observations(self, adapter):
        adapter.store_entry(MemoryEntry(content="ordinary retained fact", type="fact_declaration"))
        assert adapter.list_observations("default", include_expired=True, include_unsupported=True) == []
        adapter.recall("ordinary retained fact")
        assert adapter.list_observations("default", include_expired=True, include_unsupported=True) == []


class TestConflictContract:
    def test_selected_id_invariants_and_immutable_resolution(self, adapter):
        with pytest.raises(ValueError, match="unresolved"):
            adapter.create_conflict("default", "topic", ["a", "b"], "fact", selected_id="a")
        conflict_id = adapter.create_conflict("default", "topic", ["a", "b"], "fact")
        with pytest.raises(ValueError, match="selected_id"):
            adapter.resolve_conflict(conflict_id, "missing")
        resolved_id = adapter.resolve_conflict(conflict_id, "a")
        assert resolved_id != conflict_id
        records = adapter.list_conflicts("default", subject_key="topic")
        assert len(records) == 2
        assert records[0]["resolution_status"] == "resolved"
        assert records[0]["selected_id"] == "a"
        assert records[1]["resolution_status"] == "unresolved"

    def test_p1_correction_beats_newer_inference(self, adapter):
        result = adapter.resolve_conflict_candidates(
            "default",
            "preferred backend",
            [
                {
                    "id": "inference",
                    "source_kind": "inference",
                    "confidence": 1.0,
                    "observed_at": "9999-01-01T00:00:00+00:00",
                },
                {
                    "id": "correction",
                    "source_kind": "correction",
                    "explicit_correction": True,
                    "confidence": 0.2,
                    "observed_at": "2020-01-01T00:00:00+00:00",
                },
            ],
            "fact",
        )
        assert result["status"] == "resolved"
        assert result["selected_id"] == "correction"
        assert result["reasoning"]["priority"] == 6
        assert isinstance(result["reasoning"]["evidence"], dict)

    @pytest.mark.parametrize("term", ["email", "send", "communication", "notify", "message"])
    def test_high_risk_topic_matrix_fails_closed(self, adapter, term):
        result = adapter.resolve_conflict_candidates(
            "default",
            f"{term} policy",
            [
                {"id": "a", "source_kind": "correction", "priority": 6},
                {"id": "b", "source_kind": "inference", "priority": 0},
            ],
            "rule",
        )
        assert result["status"] == "unresolved"
        assert result["selected_id"] is None
        assert result["reasoning"]["high_risk"] is True

    def test_high_risk_topic_fails_closed(self, adapter):
        result = adapter.resolve_conflict_candidates(
            "default",
            "security permission policy",
            [
                {"id": "a", "source_kind": "correction", "priority": 6},
                {"id": "b", "source_kind": "inference", "priority": 0},
            ],
            "rule",
        )
        assert result["status"] == "unresolved"
        assert result["selected_id"] is None
        assert result["reasoning"]["high_risk"] is True

    @pytest.mark.parametrize(
        "subject_key,reasoning",
        [
            ("credential topic", {"note": "api_key=sk-abcdefghijklmnopqrstuvwxyz123456"}),
            ("api_key=sk-abcdefghijklmnopqrstuvwxyz123456", None),
        ],
    )
    def test_sensitive_serialized_fields_are_rejected(self, adapter, subject_key, reasoning):
        with pytest.raises(ValueError, match="blocked by redaction"):
            adapter.create_conflict("default", subject_key, ["a"], "fact", reasoning=reasoning)

    def test_tied_candidates_fail_closed_unresolved(self, adapter):
        """INV-X4: unresolvable (tied) conflicts must not silently pick a winner."""
        result = adapter.resolve_conflict_candidates(
            "default",
            "topic",
            [
                {"id": "a", "source_kind": "inference", "priority": 0},
                {"id": "b", "source_kind": "inference", "priority": 0},
            ],
            "fact",
        )
        assert result["status"] == "unresolved"
        assert result["selected_id"] is None
        assert result["reasoning"]["tie"] is True
        persisted = adapter.list_conflicts("default", subject_key="topic", unresolved_only=True)
        assert len(persisted) == 1 and persisted[0]["selected_id"] is None


class TestCorrectionE2E:
    def test_user_correction_creates_observation_and_conflict(self, tmp_path):
        cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "cm.db"), namespace="default")
        try:
            first = cm.classify_and_remember("I prefer Python for backend work")
            assert first["stored"] is True
            second = cm.classify_and_remember("Actually I now prefer Rust for backend work, ignore what I said before")
            assert second["stored"] is True
            observations = cm._adapter.list_observations(
                "default", predicate="correction_detected", include_expired=True
            )
            assert observations
            assert any(item["source_kind"] == "correction" for item in observations)
            conflicts = cm._adapter.list_conflicts("default")
            assert conflicts
            assert any(item["reasoning"]["priority"] == 6 for item in conflicts)
        finally:
            cm.close()

    def test_correction_supersedes_old_conclusion(self, tmp_path):
        """INV-X3: correction supersedes the old conclusion (blocking invariant).

        Regression for the release-audit finding: the correction path used to
        overwrite the old memory in place (content replaced, version bumped,
        ``superseded_at`` NULL), so recall returned two active rows carrying
        the same corrected content and the old conclusion was never retired.
        """
        cm = CarryMem(storage="sqlite", db_path=str(tmp_path / "cm_invx3.db"), namespace="default")
        try:
            first = cm.classify_and_remember("I prefer Python for backend work")
            old_key = first["storage_keys"][0]
            second = cm.classify_and_remember("Actually I now prefer Rust for backend work, ignore what I said before")
            new_key = second["storage_keys"][0]
            assert new_key != old_key

            # Old row: immutable history — original content preserved,
            # marked superseded, no in-place versioning.
            row = (
                cm._adapter.get_raw_connection()
                .execute(
                    "SELECT content, version, superseded_at, supersedes " "FROM memories WHERE storage_key = ?",
                    (old_key,),
                )
                .fetchone()
            )
            assert row is not None
            assert "python" in row["content"].lower(), "old content must not be overwritten"
            assert "rust" not in row["content"].lower(), "old row must keep its own conclusion"
            assert row["version"] == 1
            assert row["superseded_at"] is not None
            assert row["supersedes"] == new_key

            # Default recall: old conclusion excluded, correction first.
            results = cm.recall_memories("backend")
            keys = [r["storage_key"] for r in results]
            assert old_key not in keys, "superseded conclusion must leave default recall"
            assert keys and keys[0] == new_key, "correction must rank first"

            # ConflictRecord: resolved to the correction candidate with
            # machine-verifiable evidence counts (INV-X5).
            conflicts = cm._adapter.list_conflicts("default")
            conflict = next((item for item in conflicts if item["selected_id"] == new_key), None)
            assert (
                conflict is not None and conflict["resolution_status"] == "resolved"
            ), f"expected resolution to the correction, got: {conflicts}"
            assert conflict["reasoning"]["priority"] == 6
            assert conflict["reasoning"]["evidence"] == {"support": 0, "contradiction": 1}
        finally:
            cm.close()

    def test_supersede_memory_is_idempotent_per_target(self, tmp_path):
        """supersede_memory: unknown/already-superseded targets return False."""
        adapter = SQLiteAdapter(
            ":memory:", namespace="default", enable_vector_search=False, enable_semantic_recall=False
        )
        try:
            stored = adapter.store_entry(
                MemoryEntry(id="", type="user_preference", content="I prefer dark mode", confidence=0.9)
            )
            assert adapter.supersede_memory("missing-key", stored.storage_key) is False
            assert adapter.supersede_memory(stored.storage_key, stored.storage_key) is True
            # Already superseded — second call must not re-mark.
            assert adapter.supersede_memory(stored.storage_key, stored.storage_key) is False
        finally:
            adapter.close()
