"""
Rule Refiner — Multi-turn Q&A for rule abstraction.
[RESERVED] Rule-engine extension point — not yet integrated into main pipeline.
Planned for v0.4.0 interactive rule-refinement feature.

Enables users to refine rules through guided conversation,
gradually abstracting from specific experiences to general rules.

Pipeline:
    Specific Rule/Memory → Question → Answer → Refined Rule → Question → ... → Final Rule

Example:
    Round 1: "Don't use MongoDB for this project"
    Round 2: Q: "Is this about all document databases or just MongoDB?"
             A: "All document DBs"
    Round 3: Q: "Does this apply to all projects or just current one?"
             A: "All projects"
    Result:  trigger="database selection"
             action="avoid document databases (MongoDB, CouchDB, etc.)"
             type=avoid

No LLM dependency — uses template-based question generation and
keyword abstraction patterns.
"""

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RefinementPhase(str, Enum):
    """Phases of the rule refinement conversation."""

    SCOPE = "scope"
    GENERALITY = "generality"
    EXCEPTION = "exception"
    CONFIRM = "confirm"
    COMPLETE = "complete"


class QuestionType(str, Enum):
    """Kinds of questions asked during rule refinement."""

    SCOPE_BROADEN = "scope_broaden"
    SCOPE_NARROW = "scope_narrow"
    GENERALITY_UP = "generality_up"
    EXCEPTION_ADD = "exception_add"
    CONFIRM_RULE = "confirm_rule"


@dataclass
class RefinementQuestion:
    """A single question posed during rule refinement."""

    question_id: str
    session_id: str
    question_type: QuestionType
    question_text: str
    options: List[str] = field(default_factory=list)
    round_number: int = 1

    def to_dict(self) -> dict:
        """Serialize the question to a plain dict."""
        return {
            "question_id": self.question_id,
            "session_id": self.session_id,
            "question_type": self.question_type.value,
            "question_text": self.question_text,
            "options": self.options,
            "round_number": self.round_number,
        }


@dataclass
class RefinementAnswer:
    """A user's answer to a refinement question."""

    question_id: str
    answer_text: str
    selected_option: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize the answer to a plain dict."""
        return {
            "question_id": self.question_id,
            "answer_text": self.answer_text,
            "selected_option": self.selected_option,
        }


@dataclass
class RefinedRuleDraft:
    """A candidate rule produced after refinement."""

    trigger: str
    action: str
    rule_type: str = "avoid"
    override: bool = True
    confidence: float = 0.7
    scope_notes: str = ""

    def to_dict(self) -> dict:
        """Serialize the refined rule draft to a plain dict."""
        return {
            "trigger": self.trigger,
            "action": self.action,
            "rule_type": self.rule_type,
            "override": self.override,
            "confidence": self.confidence,
            "scope_notes": self.scope_notes,
        }


_SCOPE_QUESTIONS: List[Dict] = [
    {
        "pattern": r"(?i)(?:don't|do not|never)\s+use\s+(\w+)",
        "question": "Does this apply only to {match} or to a broader category?",
        "options": ["Only {match}", "Similar tools to {match}", "All tools in this category"],
        "abstraction": {
            "Only {match}": "{match}",
            "Similar tools to {match}": "tools similar to {match}",
            "All tools in this category": "all tools in this category",
        },
    },
    {
        "pattern": r"(?i)(?:avoid|don't\s+use|never\s+use)\s+(.+?)(?:\.|$)",
        "question": "Is this avoidance specific to one scenario or more general?",
        "options": ["Only this specific case", "Similar scenarios too", "All related scenarios"],
        "abstraction": {
            "Only this specific case": "specific",
            "Similar scenarios too": "similar",
            "All related scenarios": "general",
        },
    },
]

_GENERALITY_QUESTIONS: List[Dict] = [
    {
        "question": "Should this rule apply to all projects or just the current one?",
        "options": ["Current project only", "All similar projects", "All projects"],
        "scope_map": {
            "Current project only": "narrow",
            "All similar projects": "medium",
            "All projects": "broad",
        },
    },
    {
        "question": "How strict should this rule be?",
        "options": [
            "Suggestion (can be overridden)",
            "Preference (usually followed)",
            "Hard rule (never override)",
        ],
        "override_map": {
            "Suggestion (can be overridden)": False,
            "Preference (usually followed)": False,
            "Hard rule (never override)": True,
        },
    },
]

_EXCEPTION_QUESTIONS: List[Dict] = [
    {
        "question": "Are there any exceptions where this rule should not apply?",
        "options": ["No exceptions", "When explicitly approved", "In emergency situations"],
        "exception_map": {
            "No exceptions": "",
            "When explicitly approved": "unless explicitly approved",
            "In emergency situations": "except in emergencies",
        },
    },
]

_SPECIFICITY_KEYWORDS: Dict[str, List[str]] = {
    "project_specific": [
        "this project",
        "current project",
        "our project",
        "this repo",
        "this codebase",
        "this team",
        "this sprint",
    ],
    "tool_specific": [
        "MongoDB",
        "React",
        "Django",
        "PostgreSQL",
        "MySQL",
        "Redis",
        "Docker",
        "Kubernetes",
        "AWS",
        "GCP",
        "Azure",
    ],
    "time_specific": [
        "today",
        "this week",
        "this sprint",
        "this quarter",
        "currently",
        "right now",
        "for now",
    ],
}

_BROADENING_MAP: Dict[str, str] = {
    "MongoDB": "document databases",
    "PostgreSQL": "relational databases",
    "MySQL": "relational databases",
    "Redis": "in-memory caches",
    "React": "frontend frameworks",
    "Django": "web frameworks",
    "Docker": "container platforms",
    "Kubernetes": "orchestration platforms",
    "AWS": "cloud providers",
    "GCP": "cloud providers",
    "Azure": "cloud providers",
}


class RuleRefiner:
    """Multi-turn Q&A rule refiner for abstracting specific rules into general ones."""

    def __init__(self):
        self._compiled_scope = [(re.compile(p["pattern"]), p) for p in _SCOPE_QUESTIONS]

    def analyze_specificity(self, trigger: str, action: str) -> Dict:
        """
        Analyze how specific a rule is and suggest refinement directions.

        Returns:
            Dictionary with specificity analysis
        """
        text = f"{trigger} {action}".lower()
        findings: Dict[str, Any] = {
            "is_project_specific": False,
            "has_tool_specifics": [],
            "is_time_specific": False,
            "specificity_score": 0.0,
            "refinement_potential": "low",
        }

        for kw in _SPECIFICITY_KEYWORDS["project_specific"]:
            if kw.lower() in text:
                findings["is_project_specific"] = True
                findings["specificity_score"] += 0.3
                break

        for tool in _SPECIFICITY_KEYWORDS["tool_specific"]:
            if tool.lower() in text:
                findings["has_tool_specifics"].append(tool)
                findings["specificity_score"] += 0.2

        for kw in _SPECIFICITY_KEYWORDS["time_specific"]:
            if kw.lower() in text:
                findings["is_time_specific"] = True
                findings["specificity_score"] += 0.2
                break

        if findings["specificity_score"] >= 0.5:
            findings["refinement_potential"] = "high"
        elif findings["specificity_score"] >= 0.3:
            findings["refinement_potential"] = "medium"

        return findings

    def generate_question(
        self,
        trigger: str,
        action: str,
        phase: RefinementPhase,
        round_number: int = 1,
        session_id: str = "",
        previous_answers: Optional[List[RefinementAnswer]] = None,
    ) -> Optional[RefinementQuestion]:
        """
        Generate the next refinement question based on current phase.

        Args:
            trigger: Current rule trigger
            action: Current rule action
            phase: Current refinement phase
            round_number: Current round number
            session_id: Session identifier
            previous_answers: Answers from previous rounds

        Returns:
            RefinementQuestion or None if no more questions
        """
        qid = f"q_{uuid.uuid4().hex[:8]}"

        if phase == RefinementPhase.SCOPE:
            return self._generate_scope_question(trigger, action, qid, session_id, round_number)
        elif phase == RefinementPhase.GENERALITY:
            return self._generate_generality_question(trigger, action, qid, session_id, round_number)
        elif phase == RefinementPhase.EXCEPTION:
            return self._generate_exception_question(trigger, action, qid, session_id, round_number)
        elif phase == RefinementPhase.CONFIRM:
            return RefinementQuestion(
                question_id=qid,
                session_id=session_id,
                question_type=QuestionType.CONFIRM_RULE,
                question_text=self._build_confirm_text(trigger, action),
                options=["Accept and create rule", "Modify further", "Discard"],
                round_number=round_number,
            )

        return None

    def _generate_scope_question(
        self, trigger: str, action: str, qid: str, session_id: str, round_number: int
    ) -> RefinementQuestion:
        text = f"{trigger} {action}"

        for pattern, template in self._compiled_scope:
            match = pattern.search(text)
            if match:
                matched = match.group(1) if match.groups() else text[:30]
                question_text = template["question"].format(match=matched)
                options = [opt.format(match=matched) for opt in template["options"]]
                return RefinementQuestion(
                    question_id=qid,
                    session_id=session_id,
                    question_type=QuestionType.SCOPE_BROADEN,
                    question_text=question_text,
                    options=options,
                    round_number=round_number,
                )

        specificity = self.analyze_specificity(trigger, action)
        if specificity["has_tool_specifics"]:
            tool = specificity["has_tool_specifics"][0]
            broader = _BROADENING_MAP.get(tool, "similar tools")
            return RefinementQuestion(
                question_id=qid,
                session_id=session_id,
                question_type=QuestionType.SCOPE_BROADEN,
                question_text=f"Should this rule apply only to {tool} or also to {broader}?",
                options=[f"Only {tool}", f"{broader} too", "All related tools"],
                round_number=round_number,
            )

        return RefinementQuestion(
            question_id=qid,
            session_id=session_id,
            question_type=QuestionType.SCOPE_BROADEN,
            question_text="How broadly should this rule apply?",
            options=["This specific case only", "Similar cases too", "As broadly as applicable"],
            round_number=round_number,
        )

    def _generate_generality_question(
        self, trigger: str, action: str, qid: str, session_id: str, round_number: int
    ) -> RefinementQuestion:
        template = _GENERALITY_QUESTIONS[0]
        return RefinementQuestion(
            question_id=qid,
            session_id=session_id,
            question_type=QuestionType.GENERALITY_UP,
            question_text=template["question"],
            options=template["options"],
            round_number=round_number,
        )

    def _generate_exception_question(
        self, trigger: str, action: str, qid: str, session_id: str, round_number: int
    ) -> RefinementQuestion:
        template = _EXCEPTION_QUESTIONS[0]
        return RefinementQuestion(
            question_id=qid,
            session_id=session_id,
            question_type=QuestionType.EXCEPTION_ADD,
            question_text=template["question"],
            options=template["options"],
            round_number=round_number,
        )

    def _build_confirm_text(self, trigger: str, action: str) -> str:
        return f"Confirm the refined rule:\n" f"  Trigger: {trigger}\n" f"  Action:  {action}\n" f"Is this correct?"

    def refine_from_answer(
        self,
        current_draft: RefinedRuleDraft,
        question: RefinementQuestion,
        answer: RefinementAnswer,
    ) -> RefinedRuleDraft:
        """
        Refine a rule draft based on a Q&A answer.

        Returns:
            Updated RefinedRuleDraft
        """
        trigger = current_draft.trigger
        action = current_draft.action
        scope_notes = current_draft.scope_notes

        if question.question_type == QuestionType.SCOPE_BROADEN:
            trigger, action, scope_notes = self._apply_scope_refinement(trigger, action, answer, scope_notes)
        elif question.question_type == QuestionType.GENERALITY_UP:
            scope_notes = self._apply_generality_refinement(answer, scope_notes)
        elif question.question_type == QuestionType.EXCEPTION_ADD:
            action, scope_notes = self._apply_exception_refinement(action, answer, scope_notes)

        return RefinedRuleDraft(
            trigger=trigger,
            action=action,
            rule_type=current_draft.rule_type,
            override=current_draft.override,
            confidence=min(current_draft.confidence + 0.05, 1.0),
            scope_notes=scope_notes,
        )

    def _apply_scope_refinement(
        self, trigger: str, action: str, answer: RefinementAnswer, scope_notes: str
    ) -> Tuple[str, str, str]:
        answer_text = answer.answer_text.lower()

        for tool, broader in _BROADENING_MAP.items():
            if tool.lower() in action.lower() and broader.lower() not in action.lower():
                if any(kw in answer_text for kw in ["similar", "broader", "too", "all related"]):
                    action = action.replace(tool, f"{tool} and {broader}")
                    scope_notes = f"broadened from {tool} to include {broader}; {scope_notes}".strip("; ")
                    break

        if any(kw in answer_text for kw in ["all project", "broad", "general"]):
            if "this project" in trigger.lower():
                trigger = trigger.replace("this project", "all projects")
                scope_notes = f"generalized to all projects; {scope_notes}".strip("; ")

        return trigger, action, scope_notes

    def _apply_generality_refinement(self, answer: RefinementAnswer, scope_notes: str) -> str:
        selected = answer.selected_option or answer.answer_text
        template = _GENERALITY_QUESTIONS[0]

        if selected in template["scope_map"]:
            scope_level = template["scope_map"][selected]
            scope_notes = f"scope:{scope_level}; {scope_notes}".strip("; ")

        return scope_notes

    def _apply_exception_refinement(self, action: str, answer: RefinementAnswer, scope_notes: str) -> Tuple[str, str]:
        selected = answer.selected_option or answer.answer_text
        template = _EXCEPTION_QUESTIONS[0]

        if selected in template["exception_map"]:
            exception = template["exception_map"][selected]
            if exception:
                action = f"{action} ({exception})"
                scope_notes = f"exception:{exception}; {scope_notes}".strip("; ")

        return action, scope_notes

    def determine_next_phase(self, current_phase: RefinementPhase, round_number: int) -> RefinementPhase:
        """Determine the next refinement phase."""
        phase_order = [
            RefinementPhase.SCOPE,
            RefinementPhase.GENERALITY,
            RefinementPhase.EXCEPTION,
            RefinementPhase.CONFIRM,
            RefinementPhase.COMPLETE,
        ]

        try:
            current_idx = phase_order.index(current_phase)
            next_idx = min(current_idx + 1, len(phase_order) - 1)
            return phase_order[next_idx]
        except ValueError:
            return RefinementPhase.COMPLETE

    def create_initial_draft(self, trigger: str, action: str, rule_type: str = "avoid") -> RefinedRuleDraft:
        """Create an initial rule draft from raw trigger/action."""
        return RefinedRuleDraft(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=True,
            confidence=0.6,
            scope_notes="initial draft",
        )
