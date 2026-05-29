"""
CarryMem Rules Engine — Merge Protocol

Scope-aware rule merging with "customs clearance" flow.

When company rules enter personal space, they go through a review process:
1. Review: detect conflicts between incoming and existing rules
2. Adapt: apply merge strategy to resolve conflicts
3. Confirm: accept rules with merge decisions logged

Merge strategies:
- company_overrides: Company rules always win (highest scope priority)
- negotiate: Company rules win for override=True, personal rules kept otherwise
- keep_both: Keep both rules, user decides later

Design principle: Company override rules CANNOT be overridden by personal rules.
This is a security boundary, not just a preference.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .models import Rule, SCOPE_PRIORITY, VALID_RULE_SCOPES


class MergeStrategy(str, Enum):
    COMPANY_OVERRIDES = "company_overrides"
    NEGOTIATE = "negotiate"
    KEEP_BOTH = "keep_both"


class MergeDecision(str, Enum):
    KEEP_INCOMING = "keep_incoming"
    KEEP_EXISTING = "keep_existing"
    MODIFY_INCOMING = "modify_incoming"
    KEEP_BOTH = "keep_both"
    SKIP = "skip"


@dataclass
class MergeConflict:
    incoming_rule: Rule
    existing_rule: Rule
    conflict_type: str
    severity: str
    reason: str
    suggestion: str = ""
    decision: Optional[MergeDecision] = None

    def to_dict(self) -> dict:
        return {
            "incoming_rule_id": self.incoming_rule.id,
            "incoming_trigger": self.incoming_rule.trigger,
            "incoming_scope": self.incoming_rule.scope,
            "existing_rule_id": self.existing_rule.id,
            "existing_trigger": self.existing_rule.trigger,
            "existing_scope": self.existing_rule.scope,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "reason": self.reason,
            "suggestion": self.suggestion,
            "decision": self.decision.value if self.decision else None,
        }


@dataclass
class MergeResult:
    strategy: MergeStrategy
    conflicts: List[MergeConflict]
    accepted: List[Rule]
    skipped: List[Rule]
    modified: List[Tuple[Rule, Rule]]
    replaced_ids: List[str] = field(default_factory=list)
    downgrade_override_ids: List[str] = field(default_factory=list)
    audit_entries: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "conflict_count": len(self.conflicts),
            "accepted_count": len(self.accepted),
            "skipped_count": len(self.skipped),
            "modified_count": len(self.modified),
            "replaced_count": len(self.replaced_ids),
            "replaced_ids": self.replaced_ids,
            "downgrade_override_ids": self.downgrade_override_ids,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "audit_entries": self.audit_entries,
        }


def _make_audit_entry(
    action: str,
    rule_id: str,
    details: dict,
    reason: str = "",
) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "rule_id": rule_id,
        "reason": reason,
        "details": details,
    }


def detect_merge_conflicts(
    incoming: List[Rule],
    existing: List[Rule],
) -> List[MergeConflict]:
    """
    Detect conflicts between incoming and existing rules.

    Conflict types:
    - trigger_overlap: Same trigger, different actions
    - type_contradiction: always X vs forbid X on same trigger
    - scope_escalation: Incoming rule has higher scope than existing
    """
    conflicts = []

    trigger_map: Dict[str, List[Rule]] = {}
    for r in existing:
        key = r.trigger.lower().strip()
        trigger_map.setdefault(key, []).append(r)

    for inc in incoming:
        key = inc.trigger.lower().strip()
        if key not in trigger_map:
            continue

        for ext in trigger_map[key]:
            inc_priority = SCOPE_PRIORITY.get(inc.scope, 0)
            ext_priority = SCOPE_PRIORITY.get(ext.scope, 0)

            if inc.action.lower().strip() == ext.action.lower().strip():
                if inc_priority > ext_priority:
                    conflicts.append(MergeConflict(
                        incoming_rule=inc,
                        existing_rule=ext,
                        conflict_type="scope_escalation",
                        severity="low",
                        reason=f"Incoming [{inc.scope}] rule escalates over existing [{ext.scope}] rule on trigger '{inc.trigger}'",
                        suggestion="Accept incoming rule — higher scope priority",
                    ))
                continue

            if _is_contradiction(inc, ext):
                conflicts.append(MergeConflict(
                    incoming_rule=inc,
                    existing_rule=ext,
                    conflict_type="type_contradiction",
                    severity="critical",
                    reason=f"Contradiction: [{
    inc.rule_type}] vs [{
        ext.rule_type}] on trigger '{
            inc.trigger}'",
                    suggestion=_suggest_contradiction_resolution(inc, ext),
                ))
            else:
                conflicts.append(MergeConflict(
                    incoming_rule=inc,
                    existing_rule=ext,
                    conflict_type="trigger_overlap",
                    severity="medium",
                    reason=f"Same trigger '{inc.trigger}', different actions",
                    suggestion="Keep higher-scope rule or merge actions",
                ))

    return conflicts


def _is_contradiction(a: Rule, b: Rule) -> bool:
    contradiction_pairs = {
        frozenset({"always", "forbid"}),
        frozenset({"prefer", "forbid"}),
    }
    pair = frozenset({a.rule_type, b.rule_type})
    return pair in contradiction_pairs


def _suggest_contradiction_resolution(incoming: Rule, existing: Rule) -> str:
    inc_priority = SCOPE_PRIORITY.get(incoming.scope, 0)
    ext_priority = SCOPE_PRIORITY.get(existing.scope, 0)

    if inc_priority > ext_priority:
        return f"Keep incoming [{incoming.scope}] rule (higher scope priority)"
    elif ext_priority > inc_priority:
        return f"Keep existing [{existing.scope}] rule (higher scope priority)"
    else:
        return "Manual resolution required — same scope level"


def resolve_conflict(
    conflict: MergeConflict,
    strategy: MergeStrategy,
) -> MergeDecision:
    """
    Resolve a single conflict based on the merge strategy.

    Rules:
    - Company override rules (scope=company + override=True) ALWAYS win
    - This is a security boundary, not configurable
    """
    inc = conflict.incoming_rule
    ext = conflict.existing_rule

    if inc.scope == "company" and inc.override:
        return MergeDecision.KEEP_INCOMING

    if ext.scope == "company" and ext.override:
        return MergeDecision.KEEP_EXISTING

    if strategy == MergeStrategy.COMPANY_OVERRIDES:
        inc_priority = SCOPE_PRIORITY.get(inc.scope, 0)
        ext_priority = SCOPE_PRIORITY.get(ext.scope, 0)

        if inc_priority > ext_priority:
            return MergeDecision.KEEP_INCOMING
        elif ext_priority > inc_priority:
            return MergeDecision.KEEP_EXISTING
        else:
            return MergeDecision.KEEP_INCOMING

    elif strategy == MergeStrategy.NEGOTIATE:
        if conflict.conflict_type == "type_contradiction":
            if inc.override and not ext.override:
                return MergeDecision.KEEP_INCOMING
            elif ext.override and not inc.override:
                return MergeDecision.KEEP_EXISTING
            else:
                return MergeDecision.MODIFY_INCOMING
        else:
            return MergeDecision.KEEP_BOTH

    elif strategy == MergeStrategy.KEEP_BOTH:
        return MergeDecision.KEEP_BOTH

    return MergeDecision.SKIP


def merge_rules(
    incoming: List[Rule],
    existing: List[Rule],
    strategy: MergeStrategy = MergeStrategy.NEGOTIATE,
    target_scope: Optional[str] = None,
) -> MergeResult:
    """
    Merge incoming rules with existing rules using the specified strategy.

    Args:
        incoming: Rules to be merged in
        existing: Rules already in the database
        strategy: Merge strategy
        target_scope: Override scope for incoming rules

    Returns:
        MergeResult with conflicts, decisions, and audit trail
    """
    if target_scope and target_scope not in VALID_RULE_SCOPES:
        raise ValueError(f"Invalid target_scope: {target_scope}")

    if target_scope:
        incoming = [replace(r, scope=target_scope) for r in incoming]

    conflicts = detect_merge_conflicts(incoming, existing)
    conflict_map: Dict[str, List[MergeConflict]] = {}
    for c in conflicts:
        conflict_map.setdefault(c.incoming_rule.id, []).append(c)

    accepted: List[Rule] = []
    skipped: List[Rule] = []
    modified: List[Tuple[Rule, Rule]] = []
    replaced_ids: List[str] = []
    downgrade_override_ids: List[str] = []
    audit_entries: List[dict] = []

    existing_ids = {r.id for r in existing}

    for inc in incoming:
        if inc.id in existing_ids:
            skipped.append(inc)
            audit_entries.append(_make_audit_entry(
                "skip", inc.id, {"reason": "Rule ID already exists"},
            ))
            continue

        if inc.id in conflict_map:
            for conflict in conflict_map[inc.id]:
                decision = resolve_conflict(conflict, strategy)
                conflict.decision = decision

                if decision == MergeDecision.KEEP_INCOMING:
                    replaced_ids.append(conflict.existing_rule.id)
                    audit_entries.append(_make_audit_entry(
                        "replace", inc.id,
                        {"decision": "keep_incoming", "conflict": conflict.conflict_type,
                         "replaced_rule_id": conflict.existing_rule.id},
                        reason=f"Incoming [{
    inc.scope}] overrides existing [{
        conflict.existing_rule.scope}]",
                    ))
                elif decision == MergeDecision.KEEP_EXISTING:
                    audit_entries.append(_make_audit_entry(
                        "skip", inc.id,
                        {"decision": "keep_existing", "conflict": conflict.conflict_type},
                        reason=f"Existing [{
    conflict.existing_rule.scope}] overrides incoming [{
        inc.scope}]",
                    ))
                elif decision == MergeDecision.MODIFY_INCOMING:
                    modified_rule = Rule(
                        trigger=inc.trigger,
                        action=f"{inc.action} (adapted from {inc.scope})",
                        rule_type=inc.rule_type,
                        override=False,
                        scope="negotiated",
                        confidence=min(inc.confidence, 0.7),
                        derived_from=inc.derived_from,
                        source_memories=inc.source_memories,
                    )
                    modified.append((inc, modified_rule))
                    if conflict.existing_rule.override:
                        downgrade_override_ids.append(conflict.existing_rule.id)
                    audit_entries.append(_make_audit_entry(
                        "modify", inc.id,
                        {
                            "decision": "modify_incoming",
                            "original_action": inc.action,
                            "modified_action": modified_rule.action,
                            "original_scope": inc.scope,
                            "modified_scope": "negotiated",
                        },
                        reason="Negotiated: adapted incoming rule to coexist with existing",
                    ))
                elif decision == MergeDecision.KEEP_BOTH:
                    audit_entries.append(_make_audit_entry(
                        "accept", inc.id,
                        {"decision": "keep_both", "conflict": conflict.conflict_type},
                        reason="Both rules kept — user should review",
                    ))
                else:
                    audit_entries.append(_make_audit_entry(
                        "skip", inc.id,
                        {"decision": "skip"},
                    ))

            has_keep_incoming = any(
                c.decision == MergeDecision.KEEP_INCOMING
                for c in conflict_map[inc.id]
            )
            has_skip = any(
                c.decision in (MergeDecision.KEEP_EXISTING, MergeDecision.SKIP)
                for c in conflict_map[inc.id]
            )
            has_modified = any(
                c.decision == MergeDecision.MODIFY_INCOMING
                for c in conflict_map[inc.id]
            )

            if has_skip and not has_keep_incoming:
                skipped.append(inc)
            elif has_modified and not has_keep_incoming:
                for orig, mod in modified:
                    if orig.id == inc.id:
                        accepted.append(mod)
                        break
                else:
                    accepted.append(inc)
            else:
                accepted.append(inc)
        else:
            accepted.append(inc)
            audit_entries.append(_make_audit_entry(
                "accept", inc.id,
                {"decision": "no_conflict"},
                reason="No conflict with existing rules",
            ))

    return MergeResult(
        strategy=strategy,
        conflicts=conflicts,
        accepted=accepted,
        skipped=skipped,
        modified=modified,
        replaced_ids=replaced_ids,
        downgrade_override_ids=downgrade_override_ids,
        audit_entries=audit_entries,
    )


def review_incoming_rules(
    incoming: List[Rule],
    existing: List[Rule],
    target_scope: Optional[str] = None,
) -> dict:
    """
    Preview what would happen if incoming rules are merged.

    This is the "customs review" step — detect conflicts and suggest
    resolutions without actually modifying anything.

    Args:
        incoming: Rules to review
        existing: Rules already in the database
        target_scope: Override scope for incoming rules

    Returns:
        Preview dictionary with conflict count, severity breakdown, suggestions
    """
    if target_scope:
        incoming = [replace(r, scope=target_scope) for r in incoming]

    conflicts = detect_merge_conflicts(incoming, existing)

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    type_counts: Dict[str, int] = {}
    for c in conflicts:
        severity_counts[c.severity] = severity_counts.get(c.severity, 0) + 1
        type_counts[c.conflict_type] = type_counts.get(c.conflict_type, 0) + 1

    no_conflict_count = len(incoming) - len(set(c.incoming_rule.id for c in conflicts))

    strategy_previews = {}
    for strategy in MergeStrategy:
        result = merge_rules(incoming, existing, strategy=strategy)
        strategy_previews[strategy.value] = {
            "accepted": len(result.accepted),
            "skipped": len(result.skipped),
            "modified": len(result.modified),
        }

    return {
        "total_incoming": len(incoming),
        "total_existing": len(existing),
        "conflict_count": len(conflicts),
        "no_conflict_count": no_conflict_count,
        "severity_breakdown": severity_counts,
        "type_breakdown": type_counts,
        "conflicts": [c.to_dict() for c in conflicts[:20]],
        "strategy_previews": strategy_previews,
    }
