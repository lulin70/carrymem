"""
CarryMem Rules Engine — Prompt Injector

Formats matched rules for injection into AI system prompts.
Generates structured, prioritized rule sections that can be
appended to context for behavioral guidance.

Additions:
- Anchored layout mode (head/tail attention anchoring)
- DDD language view output
- Context budget monitoring with token-aware compression
"""

import re
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from .models import Rule
from .matcher import MatchResult


class ContextBudget:
    """
    Token-aware context budget monitor.

    Estimates token usage and triggers compression when
    approaching context window limits.

    Token estimation heuristic:
    - English: ~4 chars per token
    - CJK: ~2 chars per token
    - Mixed: weighted average
    """

    CJK_RANGES = (
        '\u4e00-\u9fff'
        '\u3040-\u309f'
        '\u30a0-\u30ff'
        '\uac00-\ud7af'
    )
    CJK_PATTERN = re.compile(f'[{CJK_RANGES}]')

    COMPRESSION_THRESHOLD = 0.70

    def __init__(self, budget_tokens: int = 2000):
        self.budget_tokens = budget_tokens

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        cjk_count = len(self.CJK_PATTERN.findall(text))
        total_chars = len(text)
        non_cjk_chars = total_chars - cjk_count
        return max(1, int(cjk_count / 2 + non_cjk_chars / 4))

    def should_compress(self, text: str) -> bool:
        used = self.estimate_tokens(text)
        return used > self.budget_tokens * self.COMPRESSION_THRESHOLD

    def compress_rules(
        self, matches: List, budget_tokens: int = None
    ) -> List:
        if budget_tokens is None:
            budget_tokens = self.budget_tokens

        override_matches = [m for m in matches if m.rule.override]
        soft_matches = [m for m in matches if not m.rule.override]

        result = list(override_matches)

        remaining_budget = budget_tokens - self._estimate_matches_tokens(
            override_matches
        )

        for match in soft_matches:
            rule = match.rule
            summary = f"[{rule.rule_type}] {rule.action}"
            est = self.estimate_tokens(summary)
            if remaining_budget >= est:
                result.append(match)
                remaining_budget -= est
            else:
                break

        return result

    def _estimate_matches_tokens(self, matches: List) -> int:
        total = 0
        for m in matches:
            total += self.estimate_tokens(
                f"[{m.rule.rule_type}] {m.rule.trigger} {m.rule.action}"
            )
        return total


class RuleInjector:
    """
    Formats rules for injection into AI prompts.

    Transforms matched Rule objects into natural language instructions
    that guide AI behavior. Supports multiple output formats:
    - Structured sections (for system prompts)
    - Compact format (for context windows with limited space)
    - JSON format (for programmatic consumption)
    - Anchored layout (head/tail attention anchoring for LLMs)
    - DDD language view (Domain-Driven Design terminology)

    Usage:
        injector = RuleInjector(matcher)
        prompt_section = injector.inject("competitive analysis")
        print(prompt_section)
    """

    SECTION_HEADER = "## Behavioral Rules (from CarryMem)"
    RULE_TEMPLATE = "- **[{type}]** {trigger} → {action}"
    HARD_RULE_MARKER = "⚠️ MANDATORY"
    SOFT_RULE_MARKER = "💡 SUGGESTION"

    TYPE_PRIORITY = {
        "forbid": 1,
        "avoid": 2,
        "always": 3,
        "format": 4,
        "prefer": 5,
    }

    DDD_TYPE_MAP = {
        "forbid": "Invariant",
        "always": "Consistency Guarantee",
        "avoid": "Soft Constraint",
        "prefer": "Soft Constraint",
        "format": "Soft Constraint",
    }

    DDD_TRIGGER_LABEL = "Bounded Context"
    DDD_OVERRIDE_LABEL = "Invariant Flag"
    DDD_SOURCE_LABEL = "Event Sourcing Chain"

    ANCHORED_HEAD_HEADER = "### Absolute Prohibitions (never violate)"
    ANCHORED_MIDDLE_HEADER = "### Recommended"
    ANCHORED_TAIL_HEADER = "### Mandatory Actions (never skip)"

    VALID_FORMATS = (
        "structured", "compact", "json", "anchored", "ddd"
    )

    def __init__(self, matcher):
        self.matcher = matcher

    INJECTION_DANGER_PATTERNS = re.compile(
        r'(?:'
        r'ignore\s+(?:previous|above|all|prior|earlier)\s+(?:instructions?|rules?|prompts?)|'
        r'system\s*[:：]\s*|'
        r'forget\s+(?:all\s+)?(?:previous\s+)?(?:rules?|instructions?)|'
        r'override\s+(?:all\s+)?safety|'
        r'you\s+are\s+now|'
        r'new\s+instructions?\s*[:：]|'
        r'disregard\s+(?:your|the|all)\s+(?:rules?|guidelines?|instructions?)|'
        r'(?:act|pretend|roleplay|simulate|impersonate)\s+(?:as|to\s+be)|'
        r'(?:DAN|jailbreak|developer|sudo|god|admin)\s+mode|'
        r'bypass\s+(?:all\s+)?(?:restrictions?|filters?|safety)|'
        r'(?:from\s+now\s+on|starting\s+now)\s*[,.]?\s*(?:you|your)|'
        r'your\s+(?:new|real|true)\s+(?:role|purpose|instructions?)|'
        r'(?:reveal|show|display|repeat|print)\s+(?:your|the)\s+(?:prompt|instructions?|rules?|system)|'
        r'忽略(?:之前的|上面的|所有)(?:指令|规则|提示)|'
        r'忘记(?:之前的|所有)?(?:规则|指令)|'
        r'\[SYSTEM\]|<\|system\|>|<!--\s*system|'
        r'<system>|<instruction>|<command>|'
        r'\$\{.*?\}|\{\{.*?\}\}|<%.*?%>|'
        r'base64.*decode|eval\(|exec\(|__import__'
        r')',
        re.IGNORECASE,
    )

    def _sanitize_for_injection(self, text: str) -> str:
        if not text:
            return text
        if self.INJECTION_DANGER_PATTERNS.search(text):
            return "[REDACTED: potential prompt injection in rule content]"
        return text

    def inject(
        self,
        scene_description: str,
        format: str = "structured",
        max_rules: int = 10,
        include_metadata: bool = False,
        context_budget_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate formatted rules section for a given scene.

        Args:
            scene_description: Current scene/context description
            format: Output format ("structured", "compact", "json",
                    "anchored", "ddd")
            max_rules: Maximum number of rules to include
            include_metadata: Whether to include rule IDs and metadata
            context_budget_tokens: Token budget for context-aware
                                   compression (None = no compression)

        Returns:
            Formatted string ready for prompt injection
        """
        matches = self.matcher.match(scene_description, limit=max_rules)

        if not matches:
            return ""

        sanitized_matches = []
        for m in matches:
            sanitized_trigger = self._sanitize_for_injection(m.rule.trigger)
            sanitized_action = self._sanitize_for_injection(m.rule.action)
            sanitized_rule = Rule(
                id=m.rule.id,
                trigger=sanitized_trigger,
                action=sanitized_action,
                rule_type=m.rule.rule_type,
                source_memories=m.rule.source_memories,
                derived_from=m.rule.derived_from,
                status=m.rule.status,
                override=m.rule.override,
                confidence=m.rule.confidence,
                trigger_count=m.rule.trigger_count,
                confirmed_by_user=m.rule.confirmed_by_user,
                scope=m.rule.scope,
                created_at=m.rule.created_at,
                updated_at=m.rule.updated_at,
                expires_at=m.rule.expires_at,
                condition=m.rule.condition,
                metadata=m.rule.metadata,
            )
            sanitized_matches.append(
                MatchResult(
                    rule=sanitized_rule,
                    score=m.score,
                    match_type=m.match_type,
                    matched_text=m.matched_text,
                )
            )
        matches = sanitized_matches

        if context_budget_tokens is not None:
            budget = ContextBudget(budget_tokens=context_budget_tokens)
            matches = budget.compress_rules(matches)

        if format == "json":
            return self._format_json(matches, include_metadata)
        elif format == "compact":
            return self._format_compact(matches)
        elif format == "anchored":
            return self._format_anchored(matches, include_metadata)
        elif format == "ddd":
            return self._format_ddd(matches, include_metadata)
        else:
            return self._format_structured(matches, include_metadata)

    def _classify_anchored(
        self, matches: List
    ) -> Tuple[List, List, List]:
        """
        Classify matches into anchored layout groups.

        Returns:
            (head, middle, tail) where:
            - head: override=True + rule_type=forbid (highest attention)
            - middle: override=False rules (lower attention)
            - tail: override=True + rule_type=always (high attention)
        """
        head = []
        middle = []
        tail = []

        for m in matches:
            rule = m.rule
            if rule.override and rule.rule_type == "forbid":
                head.append(m)
            elif rule.override and rule.rule_type == "always":
                tail.append(m)
            else:
                middle.append(m)

        head.sort(key=lambda m: -m.score)
        middle.sort(
            key=lambda m: (
                self.TYPE_PRIORITY.get(m.rule.rule_type, 99),
                -m.score,
            )
        )
        tail.sort(key=lambda m: -m.score)

        return head, middle, tail

    def _format_anchored(
        self, matches: List, include_metadata: bool
    ) -> str:
        """
        Format with anchored layout for LLM attention optimization.

        Places critical rules at head and tail positions where LLM
        attention is highest (U-curve pattern), and normal rules
        in the middle where attention is lower.
        """
        head, middle, tail = self._classify_anchored(matches)

        lines = [self.SECTION_HEADER, ""]

        if head:
            lines.append(self.ANCHORED_HEAD_HEADER)
            for match in head:
                lines.append(self._format_rule_line(match, "anchored_head"))
            lines.append("")

        if middle:
            lines.append(self.ANCHORED_MIDDLE_HEADER)
            for match in middle:
                lines.append(self._format_rule_line(match, "anchored_middle"))
            lines.append("")

        if tail:
            lines.append(self.ANCHORED_TAIL_HEADER)
            for match in tail:
                lines.append(self._format_rule_line(match, "anchored_tail"))
            lines.append("")

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        lines.append(f"*{len(matches)} rule(s) active | Generated at {ts}*")

        return "\n".join(lines)

    def _format_ddd(
        self, matches: List, include_metadata: bool
    ) -> str:
        """
        Format using Domain-Driven Design terminology.

        Maps CarryMem concepts to DDD equivalents:
        - trigger → Bounded Context
        - rule_type → Invariant / Consistency Guarantee / Soft Constraint
        - override → Invariant Flag
        - source_memories → Event Sourcing Chain
        """
        lines = ["## Personal Context (DDD View)", ""]

        sorted_matches = sorted(
            matches,
            key=lambda m: (
                not m.rule.override,
                self.TYPE_PRIORITY.get(m.rule.rule_type, 99),
                -m.score,
            ),
        )

        for match in sorted_matches:
            rule = match.rule
            ddd_type = self.DDD_TYPE_MAP.get(
                rule.rule_type, "Soft Constraint"
            )

            line = (
                f"- **[{ddd_type}]** "
                f"{self.DDD_TRIGGER_LABEL}: \"{rule.trigger}\" → "
                f"{rule.action}"
            )

            if rule.override:
                line += f" [{self.DDD_OVERRIDE_LABEL}]"

            if include_metadata:
                source_info = ""
                if rule.source_memories:
                    source_info = f", {self.DDD_SOURCE_LABEL}={len(rule.source_memories)} events"
                line += f" [id={rule.id}, confidence={rule.confidence:.1f}{source_info}]"

            lines.append(line)

        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        lines.append("")
        lines.append(f"*{len(matches)} constraint(s) | Generated at {ts}*")

        return "\n".join(lines)

    SCOPE_LABELS = {
        "personal": "",
        "company": " [COMPANY]",
        "negotiated": " [NEGOTIATED]",
    }

    def _format_rule_line(
        self, match, context: str = "default"
    ) -> str:
        rule = match.rule
        scope_label = self.SCOPE_LABELS.get(rule.scope, "")

        if context == "anchored_head":
            return f"- [FORBID]{scope_label} {rule.action}"
        elif context == "anchored_tail":
            return f"- [ALWAYS]{scope_label} {rule.action}"
        else:
            marker = (
                self.HARD_RULE_MARKER
                if rule.override
                else self.SOFT_RULE_MARKER
            )
            line = self.RULE_TEMPLATE.format(
                type=rule.rule_type.upper(),
                trigger=f'"{rule.trigger}"',
                action=rule.action,
            )
            line += f"{scope_label} {marker}"
            return line

    def _format_structured(
        self, matches: List, include_metadata: bool
    ) -> str:
        """Format as structured markdown section"""
        lines = [self.SECTION_HEADER]
        lines.append("")

        sorted_matches = sorted(
            matches,
            key=lambda m: (
                not m.rule.override,
                self.TYPE_PRIORITY.get(m.rule.rule_type, 99),
                -m.score,
            ),
        )

        for match in sorted_matches:
            rule = match.rule
            scope_label = self.SCOPE_LABELS.get(rule.scope, "")

            marker = (
                self.HARD_RULE_MARKER if rule.override else self.SOFT_RULE_MARKER
            )

            line = self.RULE_TEMPLATE.format(
                type=rule.rule_type.upper(),
                trigger=f'"{rule.trigger}"',
                action=rule.action,
            )
            line += f"{scope_label} {marker}"

            if include_metadata:
                line += f" [id={rule.id}, confidence={rule.confidence:.1f}]"

            lines.append(line)

        lines.append("")
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        lines.append(f"*{len(matches)} rule(s) active | Generated at {ts}*")

        return "\n".join(lines)

    def _format_compact(self, matches: List) -> str:
        """Format as compact single-line or minimal format"""
        if not matches:
            return ""

        parts = []
        for match in matches[:5]:
            rule = match.rule
            prefix = "!" if rule.override else "~"
            parts.append(f"{prefix}{rule.action}")

        return "Rules: " + " | ".join(parts)

    def _format_json(self, matches: List, include_metadata: bool) -> str:
        """Format as JSON for programmatic use"""
        import json

        rules_data = []
        for match in matches:
            rule = match.rule
            entry = {
                "action": rule.action,
                "type": rule.rule_type,
                "trigger": rule.trigger,
                "is_mandatory": rule.override,
                "relevance_score": round(match.score, 2),
            }
            if include_metadata:
                entry["rule_id"] = rule.id
                entry["confidence"] = rule.confidence
                entry["match_type"] = match.match_type

            rules_data.append(entry)

        return json.dumps(
            {"rules": rules_data, "total": len(rules_data)},
            ensure_ascii=False,
            indent=2,
        )

    def get_rules_summary(self, scene_description: str) -> dict:
        """
        Get summary statistics about matched rules.

        Args:
            scene_description: Scene to analyze

        Returns:
            Dictionary with summary information
        """
        matches = self.matcher.match(scene_description)

        if not matches:
            return {
                "total_rules": 0,
                "hard_rules": 0,
                "soft_rules": 0,
                "types": {},
                "has_global_rules": False,
            }

        hard_rules = sum(1 for m in matches if m.rule.override)
        soft_rules = len(matches) - hard_rules

        type_counts = {}
        for m in matches:
            t = m.rule.rule_type
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_rules": len(matches),
            "hard_rules": hard_rules,
            "soft_rules": soft_rules,
            "types": type_counts,
            "has_global_rules": any(m.match_type == "global" for m in matches),
            "avg_score": round(sum(m.score for m in matches) / len(matches), 2),
        }

    def estimate_context_usage(
        self, scene_description: str, format: str = "structured",
        max_rules: int = 10, budget_tokens: int = 2000,
    ) -> dict:
        """
        Estimate context budget usage for a given scene.

        Args:
            scene_description: Scene to analyze
            format: Output format to estimate
            max_rules: Maximum rules
            budget_tokens: Total context budget

        Returns:
            Dictionary with usage estimates
        """
        matches = self.matcher.match(scene_description, limit=max_rules)

        if not matches:
            return {
                "total_rules": 0,
                "estimated_tokens": 0,
                "budget_tokens": budget_tokens,
                "usage_percent": 0.0,
                "needs_compression": False,
            }

        budget = ContextBudget(budget_tokens=budget_tokens)

        output = self.inject(
            scene_description,
            format=format,
            max_rules=max_rules,
        )
        estimated = budget.estimate_tokens(output)

        return {
            "total_rules": len(matches),
            "estimated_tokens": estimated,
            "budget_tokens": budget_tokens,
            "usage_percent": round(estimated / budget_tokens * 100, 1),
            "needs_compression": estimated > budget_tokens * budget.COMPRESSION_THRESHOLD,
        }

    def inject_with_memories(
        self,
        scene_description: str,
        memories_text: Optional[str] = None,
        format: str = "structured",
        context_budget_tokens: Optional[int] = None,
    ) -> str:
        """
        Inject both rules and memories into a complete context section.

        Combines rules (priority 1) with memories (priority 2) for
        comprehensive AI guidance.

        Args:
            scene_description: Current scene
            memories_text: Pre-formatted memories section (optional)
            format: Output format for rules
            context_budget_tokens: Token budget for compression

        Returns:
            Combined context section with rules and memories
        """
        rules_section = self.inject(
            scene_description,
            format=format,
            context_budget_tokens=context_budget_tokens,
        )

        if not rules_section and not memories_text:
            return ""

        sections = []

        if rules_section:
            sections.append(rules_section)

        if memories_text:
            if not sections:
                sections.append(memories_text)
            else:
                sections.append("\n---\n\n")
                sections.append(memories_text)

        return "".join(sections)
