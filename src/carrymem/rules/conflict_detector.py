"""
CarryMem Rules Engine — Conflict Detector

Detects and reports conflicts between rules:
- Contradictory type pairs (always X vs forbid X)
- Overlapping preferences (prefer A vs prefer B with same trigger)
- Redundant rules (duplicate trigger+action)
- Global rule conflicts (multiple global rules with opposing actions)

Design principle: WARN but do NOT BLOCK.
Users should be informed of potential conflicts but retain full control.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

from .models import Rule


class ConflictSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConflictType(Enum):
    CONTRADICTION = "contradiction"
    OVERLAP = "overlap"
    REDUNDANCY = "redundancy"
    GLOBAL_CONFLICT = "global_conflict"


@dataclass
class RuleConflict:
    """
    Represents a detected conflict between two or more rules.

    Attributes:
        conflict_type: Category of conflict
        severity: How serious the conflict is
        rules: The rules involved in the conflict
        reason: Human-readable explanation
        suggestion: Optional resolution suggestion
    """

    conflict_type: ConflictType
    severity: ConflictSeverity
    rules: List[Rule]
    reason: str
    suggestion: Optional[str] = None

    def __repr__(self) -> str:
        rule_ids = ", ".join(r.id for r in self.rules)
        return f"RuleConflict({self.conflict_type.value}, " f"{self.severity.value}, rules=[{rule_ids}])"

    def summary(self) -> str:
        rule_summaries = " | ".join(r.summary() for r in self.rules)
        return (
            f"[{self.severity.value.upper()}] {self.conflict_type.value}: "
            f"{self.reason}\n"
            f"  Rules: {rule_summaries}\n"
            f"  Suggestion: {self.suggestion or 'Review manually'}"
        )


# Type pairs that are inherently contradictory
CONTRADICTORY_PAIRS: List[Tuple[str, str]] = [
    ("always", "forbid"),
    ("always", "avoid"),
    ("forbid", "prefer"),
    ("avoid", "prefer"),
]

# Type pairs that may overlap (same trigger, different actions)
OVERLAPPING_PAIRS: List[Tuple[str, str]] = [
    ("prefer", "prefer"),
    ("format", "format"),
    ("always", "format"),
    ("always", "always"),
    ("always", "prefer"),
    ("avoid", "avoid"),
    ("forbid", "forbid"),
    ("prefer", "format"),
]


class RuleConflictDetector:
    """
    Detects conflicts between rules.

    Usage:
        detector = RuleConflictDetector()
        conflicts = detector.detect(existing_rules, new_rule)
        for conflict in conflicts:
            print(conflict.summary())
    """

    @classmethod
    def detect(
        cls,
        existing_rules: List[Rule],
        new_rule: Optional[Rule] = None,
    ) -> List[RuleConflict]:
        """
        Detect conflicts among existing rules, optionally checking
        a new rule against existing ones.

        Args:
            existing_rules: List of active rules to check
            new_rule: Optional new rule to check against existing

        Returns:
            List of detected RuleConflict objects
        """
        conflicts = []

        # Check existing rules against each other
        active_rules = [r for r in existing_rules if r.status == "active"]

        # If new_rule provided, only check it against existing
        if new_rule is not None:
            for existing in active_rules:
                conflict = cls._check_pair(new_rule, existing)
                if conflict:
                    conflicts.append(conflict)

            # Also check if new_rule creates global conflicts
            if new_rule.trigger == "*" and new_rule.status == "active":
                global_conflicts = cls._check_global_rules(active_rules + [new_rule])
                conflicts.extend(global_conflicts)
        else:
            # Check all pairs (O(n^2), but rule count is bounded by limiter)
            for i in range(len(active_rules)):
                for j in range(i + 1, len(active_rules)):
                    conflict = cls._check_pair(active_rules[i], active_rules[j])
                    if conflict:
                        conflicts.append(conflict)

            # Check global rule conflicts (gives more specific GLOBAL_CONFLICT type)
            global_conflicts = cls._check_global_rules(active_rules)
            conflicts.extend(global_conflicts)

        return conflicts

    @classmethod
    def _check_pair(cls, rule_a: Rule, rule_b: Rule) -> Optional[RuleConflict]:
        """Check two rules for potential conflicts"""
        # Skip self-comparison
        if rule_a.id == rule_b.id:
            return None

        # Check for exact duplicates first
        if cls._is_duplicate(rule_a, rule_b):
            return RuleConflict(
                conflict_type=ConflictType.REDUNDANCY,
                severity=ConflictSeverity.LOW,
                rules=[rule_a, rule_b],
                reason="Duplicate rule: both have same trigger and action",
                suggestion="Consider removing one of the duplicates",
            )

        # Only check rules with similar triggers
        if not cls._triggers_overlap(rule_a.trigger, rule_b.trigger):
            return None

        # Check contradictory type pairs
        type_pair = (rule_a.rule_type, rule_b.rule_type)
        reverse_pair = (rule_b.rule_type, rule_a.rule_type)

        if type_pair in CONTRADICTORY_PAIRS or reverse_pair in CONTRADICTORY_PAIRS:
            return RuleConflict(
                conflict_type=ConflictType.CONTRADICTION,
                severity=ConflictSeverity.CRITICAL,
                rules=[rule_a, rule_b],
                reason=(f"Contradictory types: {rule_a.rule_type} vs {rule_b.rule_type} " f"with overlapping triggers"),
                suggestion=("Review which rule should take precedence. " "Consider pausing one or adjusting triggers."),
            )

        # Check overlapping type pairs
        if type_pair in OVERLAPPING_PAIRS or reverse_pair in OVERLAPPING_PAIRS:
            # Only flag if actions differ
            if rule_a.action != rule_b.action:
                return RuleConflict(
                    conflict_type=ConflictType.OVERLAP,
                    severity=ConflictSeverity.MEDIUM,
                    rules=[rule_a, rule_b],
                    reason=(f"Overlapping {rule_a.rule_type} rules with different actions " f"for similar triggers"),
                    suggestion="Consider merging or differentiating the triggers",
                )

        return None

    @classmethod
    def _is_duplicate(cls, rule_a: Rule, rule_b: Rule) -> bool:
        """Check if two rules are duplicates"""
        return (
            rule_a.trigger == rule_b.trigger and rule_a.action == rule_b.action and rule_a.rule_type == rule_b.rule_type
        )

    @classmethod
    def _triggers_overlap(cls, trigger_a: str, trigger_b: str) -> bool:
        """
        Check if two triggers overlap semantically.

        Uses string-based heuristics:
        - Exact match
        - One contains the other
        - Character-level overlap for CJK text
        - Word overlap (for space-separated triggers)
        """
        if trigger_a == trigger_b:
            return True

        if trigger_a == "*" or trigger_b == "*":
            return True

        a_lower = trigger_a.lower().strip()
        b_lower = trigger_b.lower().strip()

        if a_lower in b_lower or b_lower in a_lower:
            return True

        # CJK character-level overlap (for Chinese/Japanese)
        chars_a = set(a_lower)
        chars_b = set(b_lower)
        if chars_a and chars_b:
            cjk_overlap = chars_a & chars_b
            # Remove common punctuation and spaces
            cjk_overlap -= {" ", ",", "，", "。", "、", "の", "的"}
            if len(cjk_overlap) >= 2:
                return True

        # Word-level overlap (for English/space-separated)
        words_a = set(a_lower.split())
        words_b = set(b_lower.split())
        if words_a and words_b:
            overlap = words_a & words_b
            if len(overlap) >= 1 and len(overlap) / min(len(words_a), len(words_b)) >= 0.5:
                return True

        return False

    @classmethod
    def _check_global_rules(cls, active_rules: List[Rule]) -> List[RuleConflict]:
        """Check for conflicts among global rules"""
        global_rules = [r for r in active_rules if r.trigger == "*"]
        conflicts = []

        for i in range(len(global_rules)):
            for j in range(i + 1, len(global_rules)):
                rule_a = global_rules[i]
                rule_b = global_rules[j]

                type_pair = (rule_a.rule_type, rule_b.rule_type)
                reverse_pair = (rule_b.rule_type, rule_a.rule_type)

                if type_pair in CONTRADICTORY_PAIRS or reverse_pair in CONTRADICTORY_PAIRS:
                    conflicts.append(
                        RuleConflict(
                            conflict_type=ConflictType.GLOBAL_CONFLICT,
                            severity=ConflictSeverity.CRITICAL,
                            rules=[rule_a, rule_b],
                            reason=(f"Contradictory global rules: " f"{rule_a.rule_type} vs {rule_b.rule_type}"),
                            suggestion=(
                                "Global rules apply to ALL scenes. "
                                "Contradictory global rules will cause unpredictable behavior."
                            ),
                        )
                    )

        return conflicts

    @classmethod
    def check_health(cls, storage) -> dict:
        """
        Comprehensive health check for rules.

        Args:
            storage: RuleStorage instance

        Returns:
            Dictionary with health metrics and issues
        """
        all_rules = storage.list_all(status="active", limit=1000)
        conflicts = cls.detect(all_rules)

        unused_rules = [r for r in all_rules if r.trigger_count == 0]

        conflict_by_severity = {}
        for c in conflicts:
            key = c.severity.value
            conflict_by_severity[key] = conflict_by_severity.get(key, 0) + 1

        return {
            "total_active": len(all_rules),
            "conflicts_found": len(conflicts),
            "conflicts_by_severity": conflict_by_severity,
            "unused_rules": len(unused_rules),
            "global_rules": len([r for r in all_rules if r.trigger == "*"]),
            "is_healthy": len([c for c in conflicts if c.severity == ConflictSeverity.CRITICAL]) == 0,
            "conflicts": [c.summary() for c in conflicts[:10]],
        }
