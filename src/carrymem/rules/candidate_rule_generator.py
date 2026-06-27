"""
Candidate Rule Generator — Convert detected patterns into rule suggestions.
[RESERVED] Rule-engine extension point — not yet integrated into main pipeline.
Planned for v0.4.0 auto-rule-generation feature.

Takes MemoryPattern objects from PatternDetector and generates
human-readable rule candidates with appropriate trigger/action/rule_type.

Templates:
- AVOIDANCE pattern → "avoid" rule
- PREFERENCE pattern → "prefer" rule
- CONSISTENCY pattern → "always" rule
- AVERSION pattern → "forbid" rule
"""

from dataclasses import dataclass
from typing import List, Optional

from .pattern_detector import (
    MemoryPattern,
    PatternConfidence,
    PatternType,
)
from .sanitizer import RuleSanitizer


@dataclass
class RuleCandidate:
    """Candidate rule generated from detected memory patterns."""

    trigger: str
    action: str
    rule_type: str
    override: bool
    derived_from: str
    source_memories: List[str]
    confidence: float
    pattern_type: str
    domain: str
    explanation: str

    def to_dict(self) -> dict:
        """Serialize this candidate to a plain dict."""
        return {
            "trigger": self.trigger,
            "action": self.action,
            "rule_type": self.rule_type,
            "override": self.override,
            "derived_from": self.derived_from,
            "source_memories": self.source_memories,
            "confidence": self.confidence,
            "pattern_type": self.pattern_type,
            "domain": self.domain,
            "explanation": self.explanation,
        }


_AVOIDANCE_TEMPLATES = {
    "correction": {
        "trigger_template": "tech selection or solution design",
        "action_template": "avoid using {keywords} (corrected multiple times)",
        "explanation": (
            "You've corrected about {keywords} {count} times. " "Consider making this a default avoidance rule."
        ),
    },
    "user_preference": {
        "trigger_template": "tech selection or solution design",
        "action_template": "avoid using {keywords} (explicitly disliked)",
        "explanation": (
            "You've expressed dislike for {keywords} {count} times. " "Consider making this a default avoidance rule."
        ),
    },
    "default": {
        "trigger_template": "related scenarios",
        "action_template": "avoid {keywords}",
        "explanation": "Detected {count} avoidance signals about {keywords}.",
    },
}

_PREFERENCE_TEMPLATES = {
    "user_preference": {
        "trigger_template": "tech selection or solution design",
        "action_template": "prefer {keywords}",
        "explanation": (
            "You've expressed preference for {keywords} {count} times. " "Consider making this a default preference."
        ),
    },
    "default": {
        "trigger_template": "related scenarios",
        "action_template": "consider {keywords} first",
        "explanation": "Detected {count} preference signals about {keywords}.",
    },
}

_CONSISTENCY_TEMPLATES = {
    "decision": {
        "trigger_template": "{domain} decisions",
        "action_template": "stay consistent with previous decisions: {keywords}",
        "explanation": ("You've made {count} consistent decisions about {domain}. " "Consider standardizing this."),
    },
    "default": {
        "trigger_template": "{domain} scenarios",
        "action_template": "follow established pattern: {keywords}",
        "explanation": "Detected {count} consistent patterns about {domain}.",
    },
}

_AVERSION_TEMPLATES = {
    "default": {
        "trigger_template": "scenarios involving {keywords}",
        "action_template": "forbid using or recommending {keywords}",
        "explanation": (
            "You've shown strong negative sentiment about {keywords} " "{count} times. Consider a hard forbid rule."
        ),
    },
}

_TEMPLATE_MAP = {
    PatternType.AVOIDANCE: _AVOIDANCE_TEMPLATES,
    PatternType.PREFERENCE: _PREFERENCE_TEMPLATES,
    PatternType.CONSISTENCY: _CONSISTENCY_TEMPLATES,
    PatternType.AVERSION: _AVERSION_TEMPLATES,
}

_RULE_TYPE_MAP = {
    PatternType.AVOIDANCE: "avoid",
    PatternType.PREFERENCE: "prefer",
    PatternType.CONSISTENCY: "always",
    PatternType.AVERSION: "forbid",
}

_OVERRIDE_MAP = {
    PatternType.AVOIDANCE: True,
    PatternType.PREFERENCE: False,
    PatternType.CONSISTENCY: False,
    PatternType.AVERSION: True,
}

_CONFIDENCE_SCORE_MAP = {
    PatternConfidence.LOW: 0.5,
    PatternConfidence.MEDIUM: 0.7,
    PatternConfidence.HIGH: 0.9,
}

_DOMAIN_DISPLAY = {
    "tech_selection": "tech selection",
    "code_review": "code review",
    "report": "report writing",
    "security": "security design",
    "api": "API design",
    "testing": "testing",
    "project": "project management",
}


class CandidateRuleGenerator:
    """Generate rule candidates from detected memory patterns."""

    def __init__(self):
        pass

    def generate(self, patterns: List[MemoryPattern], max_candidates: int = 10) -> List[RuleCandidate]:
        """
        Generate rule candidates from detected patterns.

        Args:
            patterns: List of MemoryPattern objects from PatternDetector
            max_candidates: Maximum number of candidates to return

        Returns:
            List of RuleCandidate objects, sorted by confidence
        """
        if not patterns:
            return []

        candidates = []
        for pattern in patterns:
            candidate = self._pattern_to_candidate(pattern)
            if candidate:
                candidates.append(candidate)

        candidates.sort(key=lambda c: c.confidence, reverse=True)

        return candidates[:max_candidates]

    def _pattern_to_candidate(self, pattern: MemoryPattern) -> Optional[RuleCandidate]:
        """Convert a single pattern to a rule candidate."""
        templates = _TEMPLATE_MAP.get(pattern.pattern_type, {})
        template = templates.get(pattern.memory_type, templates.get("default", {}))

        if not template:
            return None

        keywords_str = ", ".join(pattern.keywords[:3])
        keywords_str = keywords_str.replace("{", "{{").replace("}", "}}")
        domain_display = _DOMAIN_DISPLAY.get(pattern.domain, pattern.domain or "general")
        domain_display = domain_display.replace("{", "{{").replace("}", "}}")

        trigger = template["trigger_template"].format(
            keywords=keywords_str,
            domain=domain_display,
            count=pattern.occurrence_count,
        )
        action = template["action_template"].format(
            keywords=keywords_str,
            domain=domain_display,
            count=pattern.occurrence_count,
        )
        explanation = template["explanation"].format(
            keywords=keywords_str,
            domain=domain_display,
            count=pattern.occurrence_count,
        )

        try:
            trigger = RuleSanitizer.validate_trigger(trigger)
            action = RuleSanitizer.validate_action(action)
        except ValueError:
            return None

        rule_type = _RULE_TYPE_MAP.get(pattern.pattern_type, "avoid")
        override = _OVERRIDE_MAP.get(pattern.pattern_type, False)
        confidence_score = _CONFIDENCE_SCORE_MAP.get(pattern.confidence, 0.5)

        return RuleCandidate(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=override,
            derived_from="auto_promotion",
            source_memories=pattern.source_memory_ids[:10],
            confidence=confidence_score,
            pattern_type=pattern.pattern_type.value,
            domain=pattern.domain,
            explanation=explanation,
        )
