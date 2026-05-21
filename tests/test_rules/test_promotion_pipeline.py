"""
Test Suite for Promotion Pipeline

Validates:
- Pipeline execution: collect → detect → generate → queue
- Accept/reject workflow
- Audit log tracking
- Candidate expiry
- Statistics
"""

import pytest
import tempfile
import os

from carrymem.rules.promotion_pipeline import (
    PromotionPipeline,
    PromotionAuditEntry,
    PROMOTION_STATUS_PENDING,
    PROMOTION_STATUS_ACCEPTED,
    PROMOTION_STATUS_REJECTED,
    PROMOTION_STATUS_EXPIRED,
)
from carrymem.rules.storage import RuleStorage


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def storage(temp_db):
    return RuleStorage(temp_db)


@pytest.fixture
def pipeline(storage):
    return PromotionPipeline(storage, expiry_days=7)


def _make_memory(mem_id: str, mem_type: str, content: str) -> dict:
    return {
        "id": mem_id,
        "type": mem_type,
        "content": content,
        "confidence": 0.9,
        "tier": 3,
    }


CORRECTION_MEMORIES = [
    _make_memory("c1", "correction", "不要用Java做后端开发"),
    _make_memory("c2", "correction", "Java框架性能不好"),
    _make_memory("c3", "correction", "别用Java，用Python替代"),
]

PREFERENCE_MEMORIES = [
    _make_memory("p1", "user_preference", "偏好PostgreSQL数据库"),
    _make_memory("p2", "user_preference", "喜欢用PostgreSQL做存储"),
    _make_memory("p3", "user_preference", "PostgreSQL是最优选择"),
]

MIXED_MEMORIES = CORRECTION_MEMORIES + PREFERENCE_MEMORIES


class TestPipelineExecution:
    """Test full pipeline execution"""

    def test_run_pipeline_with_corrections(self, pipeline):
        result = pipeline.run_pipeline(CORRECTION_MEMORIES)
        assert result["patterns_found"] >= 1
        assert result["candidates_generated"] >= 1
        assert result["candidates_queued"] >= 1

    def test_run_pipeline_with_preferences(self, pipeline):
        result = pipeline.run_pipeline(PREFERENCE_MEMORIES)
        assert result["patterns_found"] >= 1
        assert result["candidates_queued"] >= 1

    def test_run_pipeline_empty_memories(self, pipeline):
        result = pipeline.run_pipeline([])
        assert result["patterns_found"] == 0
        assert result["candidates_queued"] == 0

    def test_run_pipeline_with_type_filter(self, pipeline):
        result = pipeline.run_pipeline(MIXED_MEMORIES, memory_type="correction")
        assert result["candidates_queued"] >= 1

    def test_run_pipeline_auto_accept(self, pipeline):
        result = pipeline.run_pipeline(CORRECTION_MEMORIES, auto_accept=True)
        assert result["candidates_auto_accepted"] >= 1

    def test_run_pipeline_max_candidates(self, pipeline):
        result = pipeline.run_pipeline(
            MIXED_MEMORIES, max_candidates=1
        )
        assert result["candidates_queued"] <= 1


class TestQueueCandidate:
    """Test candidate queuing"""

    def test_queued_candidate_is_pending(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        assert len(pending) >= 1
        assert pending[0].status == PROMOTION_STATUS_PENDING

    def test_queued_candidate_has_trigger_and_action(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        assert pending[0].candidate_trigger
        assert pending[0].candidate_action

    def test_queued_candidate_has_source_memories(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        assert len(pending[0].source_memory_ids) >= 1


class TestAcceptReject:
    """Test accept/reject workflow"""

    def test_accept_creates_rule(self, pipeline, storage):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        audit_id = pending[0].id

        rule_id = pipeline.accept_candidate(audit_id)
        assert rule_id is not None
        assert rule_id.startswith("rule_")

        rule = storage.get(rule_id)
        assert rule is not None
        assert rule.derived_from == "auto_promotion"
        assert rule.override == 0

    def test_accept_updates_audit_status(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        audit_id = pending[0].id

        pipeline.accept_candidate(audit_id)

        entry = pipeline._get_entry(audit_id)
        assert entry.status == PROMOTION_STATUS_ACCEPTED
        assert entry.resulting_rule_id is not None
        assert entry.reviewed_at is not None

    def test_accept_with_note(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        audit_id = pending[0].id

        pipeline.accept_candidate(audit_id, note="Good suggestion")
        entry = pipeline._get_entry(audit_id)
        assert entry.review_note == "Good suggestion"

    def test_accept_non_pending_returns_none(self, pipeline):
        result = pipeline.accept_candidate("nonexistent_id")
        assert result is None

    def test_reject_updates_status(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        audit_id = pending[0].id

        ok = pipeline.reject_candidate(audit_id)
        assert ok is True

        entry = pipeline._get_entry(audit_id)
        assert entry.status == PROMOTION_STATUS_REJECTED

    def test_reject_with_note(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        audit_id = pending[0].id

        pipeline.reject_candidate(audit_id, note="Not applicable")
        entry = pipeline._get_entry(audit_id)
        assert entry.review_note == "Not applicable"

    def test_reject_non_pending_returns_false(self, pipeline):
        ok = pipeline.reject_candidate("nonexistent_id")
        assert ok is False

    def test_cannot_accept_rejected(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        audit_id = pending[0].id

        pipeline.reject_candidate(audit_id)
        result = pipeline.accept_candidate(audit_id)
        assert result is None

    def test_accept_removes_from_pending(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending_before = pipeline.list_pending()
        assert len(pending_before) >= 1

        pipeline.accept_candidate(pending_before[0].id)
        pending_after = pipeline.list_pending()
        assert len(pending_after) == len(pending_before) - 1


class TestExpiry:
    """Test candidate expiry"""

    def test_expire_old_candidates(self, pipeline, storage):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        assert len(pending) >= 1

        audit_id = pending[0].id
        conn = storage._get_connection()
        try:
            old_date = "2020-01-01T00:00:00+00:00"
            conn.execute(
                "UPDATE promotion_audit SET created_at = ? WHERE id = ?",
                (old_date, audit_id),
            )
            conn.commit()
        finally:
            conn.close()

        expired_count = pipeline._expire_old_candidates()
        assert expired_count >= 1

        entry = pipeline._get_entry(audit_id)
        assert entry.status == PROMOTION_STATUS_EXPIRED


class TestAuditLog:
    """Test audit log tracking"""

    def test_audit_log_records_actions(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        pipeline.accept_candidate(pending[0].id)

        log = pipeline.get_audit_log()
        assert len(log) >= 1

    def test_audit_log_includes_all_statuses(self, pipeline):
        pipeline.run_pipeline(MIXED_MEMORIES)
        pending = pipeline.list_pending()
        if len(pending) >= 2:
            pipeline.accept_candidate(pending[0].id)
            pipeline.reject_candidate(pending[1].id)
            log = pipeline.get_audit_log()
            statuses = {entry.status for entry in log}
            assert PROMOTION_STATUS_ACCEPTED in statuses
            assert PROMOTION_STATUS_REJECTED in statuses
        else:
            pipeline.accept_candidate(pending[0].id)
            log = pipeline.get_audit_log()
            statuses = {entry.status for entry in log}
            assert PROMOTION_STATUS_ACCEPTED in statuses

    def test_audit_log_respects_limit(self, pipeline):
        pipeline.run_pipeline(MIXED_MEMORIES)
        log = pipeline.get_audit_log(limit=1)
        assert len(log) <= 1


class TestStatistics:
    """Test pipeline statistics"""

    def test_stats_empty(self, pipeline):
        stats = pipeline.get_stats()
        assert stats.get("total", 0) == 0

    def test_stats_after_pipeline(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        stats = pipeline.get_stats()
        assert stats.get("total", 0) >= 1
        assert stats.get("pending", 0) >= 1

    def test_stats_after_accept(self, pipeline):
        pipeline.run_pipeline(CORRECTION_MEMORIES)
        pending = pipeline.list_pending()
        pipeline.accept_candidate(pending[0].id)
        stats = pipeline.get_stats()
        assert stats.get("accepted", 0) >= 1


class TestPromotionAuditEntrySerialization:
    """Test PromotionAuditEntry to_dict"""

    def test_to_dict(self):
        entry = PromotionAuditEntry(
            id="promo_test",
            candidate_trigger="test trigger",
            candidate_action="test action",
            candidate_rule_type="avoid",
            source_pattern_type="avoidance",
            source_memory_ids=["c1", "c2"],
            confidence=0.7,
            status="pending",
            created_at="2026-04-30T00:00:00+00:00",
        )
        d = entry.to_dict()
        assert d["id"] == "promo_test"
        assert d["candidate_rule_type"] == "avoid"
        assert d["confidence"] == 0.7
        assert d["source_memory_ids"] == ["c1", "c2"]
