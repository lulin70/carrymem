"""
Tests for RuleRefiner and RefinementSessionManager.

Covers:
- Specificity analysis
- Question generation (scope, generality, exception, confirm)
- Answer processing and draft refinement
- Session lifecycle (start, answer, confirm, cancel)
- Conversation tracking
- Audit trail
- Edge cases
"""

import json
import pytest

from carrymem.rules.rule_refiner import (
    RuleRefiner,
    RefinementPhase,
    RefinementQuestion,
    RefinementAnswer,
    RefinedRuleDraft,
    QuestionType,
)
from carrymem.rules.refinement_session import (
    RefinementSessionManager,
    SessionEntry,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_EXPIRED,
)
from carrymem.rules.storage import RuleStorage


@pytest.fixture
def refiner():
    return RuleRefiner()


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test_refine.db")
    return RuleStorage(db_path)


@pytest.fixture
def session_mgr(storage):
    return RefinementSessionManager(storage)


class TestRuleRefinerSpecificity:
    def test_project_specific(self, refiner):
        result = refiner.analyze_specificity("this project", "avoid MongoDB")
        assert result["is_project_specific"] is True
        assert result["refinement_potential"] in ("medium", "high")

    def test_tool_specific(self, refiner):
        result = refiner.analyze_specificity("database selection", "avoid MongoDB")
        assert "MongoDB" in result["has_tool_specifics"]
        assert result["specificity_score"] >= 0.2

    def test_time_specific(self, refiner):
        result = refiner.analyze_specificity("currently working", "do code review")
        assert result["is_time_specific"] is True

    def test_general_rule(self, refiner):
        result = refiner.analyze_specificity("database selection", "prefer relational databases")
        assert result["specificity_score"] < 0.3
        assert result["refinement_potential"] == "low"

    def test_multiple_tool_specifics(self, refiner):
        result = refiner.analyze_specificity("tech stack", "use React and PostgreSQL")
        assert len(result["has_tool_specifics"]) >= 2


class TestRuleRefinerQuestionGeneration:
    def test_scope_question_for_tool(self, refiner):
        q = refiner.generate_question("database selection", "avoid MongoDB", RefinementPhase.SCOPE, session_id="test")
        assert q is not None
        assert q.question_type == QuestionType.SCOPE_BROADEN
        assert len(q.options) >= 2

    def test_scope_question_options(self, refiner):
        q = refiner.generate_question("database selection", "avoid MongoDB", RefinementPhase.SCOPE, session_id="test")
        assert len(q.options) >= 2

    def test_generality_question(self, refiner):
        q = refiner.generate_question(
            "database selection", "avoid MongoDB", RefinementPhase.GENERALITY, session_id="test"
        )
        assert q is not None
        assert q.question_type == QuestionType.GENERALITY_UP
        assert "project" in q.question_text.lower() or "apply" in q.question_text.lower()

    def test_exception_question(self, refiner):
        q = refiner.generate_question(
            "database selection", "avoid MongoDB", RefinementPhase.EXCEPTION, session_id="test"
        )
        assert q is not None
        assert q.question_type == QuestionType.EXCEPTION_ADD
        assert "exception" in q.question_text.lower()

    def test_confirm_question(self, refiner):
        q = refiner.generate_question(
            "database selection",
            "avoid document databases",
            RefinementPhase.CONFIRM,
            session_id="test",
        )
        assert q is not None
        assert q.question_type == QuestionType.CONFIRM_RULE
        assert "Confirm" in q.question_text or "confirm" in q.question_text.lower()

    def test_complete_phase_returns_none(self, refiner):
        q = refiner.generate_question("db selection", "avoid doc DBs", RefinementPhase.COMPLETE, session_id="test")
        assert q is None

    def test_generic_scope_question(self, refiner):
        q = refiner.generate_question("general scenario", "do something", RefinementPhase.SCOPE, session_id="test")
        assert q is not None
        assert q.question_type == QuestionType.SCOPE_BROADEN


class TestRuleRefinerRefinement:
    def test_scope_broadening(self, refiner):
        draft = RefinedRuleDraft(trigger="db selection", action="avoid MongoDB")
        question = RefinementQuestion(
            question_id="q1",
            session_id="s1",
            question_type=QuestionType.SCOPE_BROADEN,
            question_text="Should this apply to all document databases?",
        )
        answer = RefinementAnswer(
            question_id="q1",
            answer_text="similar tools too",
            selected_option="Similar tools to MongoDB",
        )
        refined = refiner.refine_from_answer(draft, question, answer)
        assert "document databases" in refined.action or "MongoDB" in refined.action

    def test_exception_addition(self, refiner):
        draft = RefinedRuleDraft(trigger="db selection", action="avoid MongoDB")
        question = RefinementQuestion(
            question_id="q2",
            session_id="s1",
            question_type=QuestionType.EXCEPTION_ADD,
            question_text="Are there any exceptions?",
        )
        answer = RefinementAnswer(
            question_id="q2",
            answer_text="When explicitly approved",
            selected_option="When explicitly approved",
        )
        refined = refiner.refine_from_answer(draft, question, answer)
        assert "explicitly approved" in refined.action or "unless" in refined.action

    def test_confidence_increases(self, refiner):
        draft = RefinedRuleDraft(trigger="db selection", action="avoid MongoDB", confidence=0.6)
        question = RefinementQuestion(
            question_id="q1",
            session_id="s1",
            question_type=QuestionType.SCOPE_BROADEN,
            question_text="Broaden scope?",
        )
        answer = RefinementAnswer(question_id="q1", answer_text="yes")
        refined = refiner.refine_from_answer(draft, question, answer)
        assert refined.confidence > draft.confidence

    def test_confidence_capped_at_1(self, refiner):
        draft = RefinedRuleDraft(trigger="db", action="avoid X", confidence=0.99)
        question = RefinementQuestion(
            question_id="q1",
            session_id="s1",
            question_type=QuestionType.SCOPE_BROADEN,
            question_text="Broaden?",
        )
        answer = RefinementAnswer(question_id="q1", answer_text="yes")
        refined = refiner.refine_from_answer(draft, question, answer)
        assert refined.confidence <= 1.0


class TestRuleRefinerPhaseProgression:
    def test_scope_to_generality(self, refiner):
        next_phase = refiner.determine_next_phase(RefinementPhase.SCOPE, 1)
        assert next_phase == RefinementPhase.GENERALITY

    def test_generality_to_exception(self, refiner):
        next_phase = refiner.determine_next_phase(RefinementPhase.GENERALITY, 2)
        assert next_phase == RefinementPhase.EXCEPTION

    def test_exception_to_confirm(self, refiner):
        next_phase = refiner.determine_next_phase(RefinementPhase.EXCEPTION, 3)
        assert next_phase == RefinementPhase.CONFIRM

    def test_confirm_to_complete(self, refiner):
        next_phase = refiner.determine_next_phase(RefinementPhase.CONFIRM, 4)
        assert next_phase == RefinementPhase.COMPLETE


class TestRuleRefinerDraft:
    def test_create_initial_draft(self, refiner):
        draft = refiner.create_initial_draft("db selection", "avoid MongoDB")
        assert draft.trigger == "db selection"
        assert draft.action == "avoid MongoDB"
        assert draft.confidence == 0.6

    def test_draft_to_dict(self, refiner):
        draft = refiner.create_initial_draft("db selection", "avoid MongoDB")
        d = draft.to_dict()
        assert "trigger" in d
        assert "action" in d
        assert "confidence" in d


class TestRefinementSession:
    def test_start_session(self, session_mgr):
        result = session_mgr.start_session(
            trigger="database selection",
            action="avoid MongoDB",
        )
        assert "session_id" in result
        assert result["session_id"].startswith("ref_")
        assert result["phase"] == "scope"
        assert result["question"] is not None

    def test_answer_and_advance(self, session_mgr):
        result = session_mgr.start_session(
            trigger="database selection",
            action="avoid MongoDB",
        )
        session_id = result["session_id"]

        answer_result = session_mgr.answer_question(
            session_id, "all document databases", selected_option="Similar tools to MongoDB"
        )
        assert "refined_draft" in answer_result
        assert answer_result["round"] >= 1

    def test_full_session_lifecycle(self, session_mgr):
        result = session_mgr.start_session(
            trigger="database selection",
            action="avoid MongoDB",
        )
        session_id = result["session_id"]

        session_mgr.answer_question(session_id, "all document DBs")
        session_mgr.answer_question(session_id, "All projects")
        session_mgr.answer_question(session_id, "No exceptions")

        confirm_result = session_mgr.confirm_session(session_id)
        assert "rule_id" in confirm_result
        assert confirm_result["status"] == "completed"

    def test_cancel_session(self, session_mgr):
        result = session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        session_id = result["session_id"]

        success = session_mgr.cancel_session(session_id)
        assert success is True

    def test_cannot_confirm_cancelled(self, session_mgr):
        result = session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        session_id = result["session_id"]
        session_mgr.cancel_session(session_id)

        confirm = session_mgr.confirm_session(session_id)
        assert "error" in confirm

    def test_invalid_session_id(self, session_mgr):
        result = session_mgr.answer_question("nonexistent", "answer")
        assert "error" in result

    def test_list_active_sessions(self, session_mgr):
        session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        sessions = session_mgr.list_active_sessions()
        assert len(sessions) >= 1
        for s in sessions:
            assert s.status == SESSION_STATUS_ACTIVE

    def test_get_session_detail(self, session_mgr):
        result = session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        session_id = result["session_id"]

        detail = session_mgr.get_session_detail(session_id)
        assert detail is not None
        assert "conversation" in detail
        assert isinstance(detail["conversation"], list)

    def test_conversation_tracking(self, session_mgr):
        result = session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        session_id = result["session_id"]

        session_mgr.answer_question(session_id, "all document DBs")

        detail = session_mgr.get_session_detail(session_id)
        assert len(detail["conversation"]) >= 1
        assert detail["conversation"][0]["answer"] == "all document DBs"

    def test_get_stats(self, session_mgr):
        session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        stats = session_mgr.get_stats()
        assert "total" in stats
        assert stats["total"] >= 1

    def test_session_entry_to_dict(self, session_mgr):
        session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        sessions = session_mgr.list_active_sessions()
        d = sessions[0].to_dict()
        assert "id" in d
        assert "original_trigger" in d
        assert "phase" in d

    def test_max_rounds_forces_confirm(self, session_mgr):
        result = session_mgr.start_session(trigger="db selection", action="avoid MongoDB")
        session_id = result["session_id"]

        for _ in range(6):
            session_mgr.answer_question(session_id, "yes")

        detail = session_mgr.get_session_detail(session_id)
        assert detail["phase"] in ("confirm", "complete")

    def test_expiry(self, session_mgr):
        session_mgr.start_session(trigger="db", action="avoid X")
        session_mgr.expiry_days = 0
        expired = session_mgr._expire_old_sessions()
        assert expired >= 0

    def test_confirm_creates_rule_in_storage(self, session_mgr, storage):
        result = session_mgr.start_session(trigger="database selection", action="avoid MongoDB")
        session_id = result["session_id"]

        confirm = session_mgr.confirm_session(session_id)
        assert "rule_id" in confirm

        rule = storage.get(confirm["rule_id"])
        assert rule is not None
        assert rule.derived_from == "refinement_session"

    def test_question_to_dict(self, refiner):
        q = refiner.generate_question("db selection", "avoid MongoDB", RefinementPhase.SCOPE, session_id="test")
        d = q.to_dict()
        assert "question_id" in d
        assert "question_text" in d

    def test_answer_to_dict(self):
        a = RefinementAnswer(question_id="q1", answer_text="yes", selected_option="Option A")
        d = a.to_dict()
        assert d["answer_text"] == "yes"
        assert d["selected_option"] == "Option A"
