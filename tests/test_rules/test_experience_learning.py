"""
Tests for FailureExperienceExtractor and ExperienceRuleBridge.

Covers:
- Failure signal detection (EN + ZH)
- Lesson extraction
- Trigger/action hint generation
- Domain inference
- Confidence calculation
- Bridge workflow: extract → queue → accept/reject
- Audit trail
- Edge cases
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta

from carrymem.rules.failure_experience import (
    FailureExperienceExtractor,
    ExtractedLesson,
    FailureSignal,
    FailureConfidence,
)
from carrymem.rules.experience_bridge import (
    ExperienceRuleBridge,
    ExperienceAuditEntry,
    EXPERIENCE_STATUS_PENDING,
    EXPERIENCE_STATUS_ACCEPTED,
    EXPERIENCE_STATUS_REJECTED,
    EXPERIENCE_STATUS_EXPIRED,
)
from carrymem.rules.storage import RuleStorage


@pytest.fixture
def extractor():
    return FailureExperienceExtractor()


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test_rules.db")
    return RuleStorage(db_path)


@pytest.fixture
def bridge(storage):
    return ExperienceRuleBridge(storage)


FAILURE_MEMORIES_EN = [
    {
        "id": "mem_001",
        "content": "I made a mistake by trusting the vendor's timeline estimate. The project was delayed by 3 weeks.",
        "type": "correction",
    },
    {
        "id": "mem_002",
        "content": "Should not have used MongoDB for this use case. The relational data doesn't fit well.",
        "type": "correction",
    },
    {
        "id": "mem_003",
        "content": "Learned the hard way that competitor's website data is unreliable. Got caught by the client.",
        "type": "correction",
    },
    {
        "id": "mem_004",
        "content": "Never again will I skip code review. It caused a production incident.",
        "type": "correction",
    },
    {
        "id": "mem_005",
        "content": "Don't trust the API documentation without testing. Half the endpoints were wrong.",
        "type": "correction",
    },
    {
        "id": "mem_006",
        "content": "The deployment failed because we didn't run integration tests first.",
        "type": "correction",
    },
    {
        "id": "mem_007",
        "content": "I prefer using PostgreSQL for relational data.",
        "type": "user_preference",
    },
    {
        "id": "mem_008",
        "content": "We use React for the frontend.",
        "type": "decision",
    },
]

FAILURE_MEMORIES_ZH = [
    {
        "id": "mem_zh_001",
        "content": "上次信了对手的官网数据，被客户拆穿了，血的教训",
        "type": "correction",
    },
    {
        "id": "mem_zh_002",
        "content": "不应该用MongoDB做这个项目，关系型数据不适合",
        "type": "correction",
    },
    {
        "id": "mem_zh_003",
        "content": "踩坑了，供应商的排期完全不靠谱，延期了3周",
        "type": "correction",
    },
    {
        "id": "mem_zh_004",
        "content": "代码不review就上线，导致生产事故，深刻教训",
        "type": "correction",
    },
    {
        "id": "mem_zh_005",
        "content": "API文档不可信，一半的接口都是错的",
        "type": "correction",
    },
]

NON_FAILURE_MEMORIES = [
    {
        "id": "mem_nf_001",
        "content": "I prefer dark mode for my IDE",
        "type": "user_preference",
    },
    {
        "id": "mem_nf_002",
        "content": "We use React for the frontend",
        "type": "decision",
    },
    {
        "id": "mem_nf_003",
        "content": "The team has 5 members",
        "type": "fact_declaration",
    },
]


class TestFailureExperienceExtractor:

    def test_extract_from_english_failure_memories(self, extractor):
        lessons = extractor.extract(FAILURE_MEMORIES_EN)
        assert len(lessons) >= 4
        for lesson in lessons:
            assert isinstance(lesson, ExtractedLesson)
            assert lesson.failure_signal in list(FailureSignal)
            assert lesson.lesson
            assert lesson.trigger_hint

    def test_extract_from_chinese_failure_memories(self, extractor):
        lessons = extractor.extract(FAILURE_MEMORIES_ZH)
        assert len(lessons) >= 3
        for lesson in lessons:
            assert lesson.lesson
            assert lesson.trigger_hint

    def test_no_lessons_from_non_failure(self, extractor):
        lessons = extractor.extract(NON_FAILURE_MEMORIES)
        assert len(lessons) == 0

    def test_empty_input(self, extractor):
        assert extractor.extract([]) == []

    def test_filter_by_memory_type(self, extractor):
        lessons = extractor.extract(FAILURE_MEMORIES_EN, memory_type="correction")
        for lesson in lessons:
            assert lesson.source_type == "correction"

    def test_failure_signal_mistake(self, extractor):
        assert extractor.is_failure_memory("I made a mistake by trusting the vendor")

    def test_failure_signal_regret(self, extractor):
        assert extractor.is_failure_memory("Should not have used MongoDB")

    def test_failure_signal_negative_outcome(self, extractor):
        assert extractor.is_failure_memory("The deployment failed")

    def test_failure_signal_lesson_learned(self, extractor):
        assert extractor.is_failure_memory("Learned the hard way that data is unreliable")

    def test_failure_signal_correction(self, extractor):
        assert extractor.is_failure_memory("Don't trust the API documentation")

    def test_chinese_failure_signal(self, extractor):
        assert extractor.is_failure_memory("踩坑了，供应商不靠谱")

    def test_chinese_lesson_learned(self, extractor):
        assert extractor.is_failure_memory("血的教训，不能信对手数据")

    def test_non_failure_content(self, extractor):
        assert not extractor.is_failure_memory("I prefer dark mode")
        assert not extractor.is_failure_memory("We use React")
        assert not extractor.is_failure_memory("The team has 5 members")

    def test_confidence_high_for_lesson_learned(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "Learned the hard way that competitor data is unreliable. Got caught by client.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].confidence == FailureConfidence.HIGH

    def test_confidence_medium_for_mistake(self, extractor):
        lessons = extractor.extract(
            [
                {"id": "m1", "content": "I made a mistake", "type": "correction"},
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].confidence == FailureConfidence.MEDIUM

    def test_confidence_upgraded_for_rich_content(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "The deployment failed because we didn't run integration tests first.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].confidence in (FailureConfidence.MEDIUM, FailureConfidence.HIGH)

    def test_domain_inference_tech(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "Should not have used MongoDB for this tech selection. The framework doesn't fit.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].domain == "tech_selection"

    def test_domain_inference_competitive(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "Learned the hard way that competitor's website data is unreliable.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].domain == "competitive_analysis"

    def test_domain_inference_vendor(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "I made a mistake by trusting the vendor's timeline estimate.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].domain == "vendor_management"

    def test_domain_inference_code(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "Never again will I skip code review. It caused a production bug.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].domain == "code_quality"

    def test_trigger_hint_from_domain(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "Should not have used MongoDB for this tech selection.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert "tech" in lessons[0].trigger_hint.lower() or "selection" in lessons[0].trigger_hint.lower()

    def test_action_hint_avoidance(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "Don't trust the API documentation without testing.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        assert lessons[0].action_hint

    def test_lessons_sorted_by_confidence(self, extractor):
        memories = [
            {"id": "m1", "content": "The deployment failed.", "type": "correction"},
            {
                "id": "m2",
                "content": "Learned the hard way that competitor data is unreliable.",
                "type": "correction",
            },
        ]
        lessons = extractor.extract(memories)
        if len(lessons) >= 2:
            high_first = lessons[0].confidence == FailureConfidence.HIGH
            assert high_first

    def test_short_content_skipped(self, extractor):
        lessons = extractor.extract(
            [
                {"id": "m1", "content": "bad", "type": "correction"},
            ]
        )
        assert len(lessons) == 0

    def test_extracted_lesson_to_dict(self, extractor):
        lessons = extractor.extract(
            [
                {
                    "id": "m1",
                    "content": "I made a mistake by trusting the vendor.",
                    "type": "correction",
                },
            ]
        )
        assert len(lessons) == 1
        d = lessons[0].to_dict()
        assert "source_memory_id" in d
        assert "failure_signal" in d
        assert "lesson" in d
        assert "confidence" in d


class TestExperienceRuleBridge:

    def test_extract_and_queue(self, bridge):
        result = bridge.extract_lessons(FAILURE_MEMORIES_EN)
        assert result["lessons_found"] >= 4
        assert result["candidates_queued"] >= 1

    def test_extract_chinese_memories(self, bridge):
        result = bridge.extract_lessons(FAILURE_MEMORIES_ZH)
        assert result["lessons_found"] >= 3
        assert result["candidates_queued"] >= 1

    def test_no_lessons_from_non_failure(self, bridge):
        result = bridge.extract_lessons(NON_FAILURE_MEMORIES)
        assert result["lessons_found"] == 0
        assert result["candidates_queued"] == 0

    def test_empty_input(self, bridge):
        result = bridge.extract_lessons([])
        assert result["lessons_found"] == 0

    def test_list_pending(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        assert len(pending) >= 1
        for entry in pending:
            assert entry.status == EXPERIENCE_STATUS_PENDING
            assert entry.id.startswith("exp_")

    def test_accept_creates_rule(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        rule_id = bridge.accept_lesson(audit_id)
        assert rule_id is not None
        assert rule_id.startswith("rule_")

    def test_accept_with_override(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        rule_id = bridge.accept_lesson(
            audit_id,
            trigger_override="custom trigger",
            action_override="custom action",
            note="User confirmed",
        )
        assert rule_id is not None

    def test_accept_updates_audit(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        rule_id = bridge.accept_lesson(audit_id, note="Confirmed")
        assert rule_id is not None

        log = bridge.get_audit_log()
        accepted = [e for e in log if e.id == audit_id]
        assert len(accepted) == 1
        assert accepted[0].status == EXPERIENCE_STATUS_ACCEPTED
        assert accepted[0].resulting_rule_id == rule_id
        assert accepted[0].review_note == "Confirmed"

    def test_reject_lesson(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        success = bridge.reject_lesson(audit_id, note="Not relevant")
        assert success is True

        log = bridge.get_audit_log()
        rejected = [e for e in log if e.id == audit_id]
        assert len(rejected) == 1
        assert rejected[0].status == EXPERIENCE_STATUS_REJECTED

    def test_cannot_accept_rejected(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        bridge.reject_lesson(audit_id)
        rule_id = bridge.accept_lesson(audit_id)
        assert rule_id is None

    def test_cannot_reject_accepted(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        bridge.accept_lesson(audit_id)
        success = bridge.reject_lesson(audit_id)
        assert success is False

    def test_invalid_audit_id(self, bridge):
        assert bridge.accept_lesson("nonexistent") is None
        assert bridge.reject_lesson("nonexistent") is False

    def test_duplicate_memory_skipped(self, bridge):
        result1 = bridge.extract_lessons(FAILURE_MEMORIES_EN)
        result2 = bridge.extract_lessons(FAILURE_MEMORIES_EN)
        assert result2["skipped_already_processed"] >= result1["candidates_queued"]

    def test_get_stats(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        stats = bridge.get_stats()
        assert "total" in stats
        assert stats["total"] >= 1
        assert stats.get("pending", 0) >= 1

    def test_get_audit_log(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        log = bridge.get_audit_log()
        assert len(log) >= 1
        for entry in log:
            assert isinstance(entry, ExperienceAuditEntry)

    def test_expiry(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        bridge.expiry_days = 0
        expired = bridge._expire_old_candidates()
        assert expired >= 0

    def test_filter_by_memory_type(self, bridge):
        result = bridge.extract_lessons(FAILURE_MEMORIES_EN, memory_type="correction")
        assert result["lessons_found"] >= 1

    def test_audit_entry_to_dict(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        log = bridge.get_audit_log(limit=1)
        assert len(log) == 1
        d = log[0].to_dict()
        assert "id" in d
        assert "source_memory_id" in d
        assert "lesson" in d
        assert "status" in d

    def test_accept_creates_avoid_rule(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        pending = bridge.list_pending()
        audit_id = pending[0].id

        rule_id = bridge.accept_lesson(audit_id)
        assert rule_id is not None

        rule = bridge.storage.get(rule_id)
        assert rule is not None
        assert rule.rule_type == "avoid"
        assert rule.derived_from == "failure_lesson"
        assert rule.override == True

    def test_count_pending(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_EN)
        count = bridge._count_pending()
        assert count >= 1

    def test_queue_size_limit(self, bridge):
        many_memories = []
        for i in range(50):
            many_memories.append(
                {
                    "id": f"mem_many_{i}",
                    "content": f"I made a mistake number {i} by not testing properly",
                    "type": "correction",
                }
            )
        result = bridge.extract_lessons(many_memories)
        pending_count = bridge._count_pending()
        assert pending_count <= 30

    def test_chinese_accept_creates_rule(self, bridge):
        bridge.extract_lessons(FAILURE_MEMORIES_ZH)
        pending = bridge.list_pending()
        if pending:
            audit_id = pending[0].id
            rule_id = bridge.accept_lesson(audit_id)
            assert rule_id is not None
            rule = bridge.storage.get(rule_id)
            assert rule.rule_type == "avoid"
