"""Decision pattern definitions."""

import re

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_decision_patterns(registry: PatternRegistry) -> None:
    """Register all decision patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Strong decision (EN) =====
    b.create_group("decision_strong", PatternType.DECISION)
    b.set_language("en")
    b.add_decision_batch(
        [
            (
                "decide_verb",
                r"\b(decision|decided?|choose|chose|chosen|choice|select|selected|" r"selection|pick|picked)\b",
                "strong",
            ),
            ("going_with", r"\b(going\s+with|settled?\s+on|opted?\s+for|landed?\s+on|went\s+with)\b", "strong"),
            ("adopt", r"\b(adopt|adopting|adopted|embrace|embraced)\b", "strong"),
            ("agree", r"\b(agreed?|consensus|unanimous|commit(ted|ting)?|pledge(d|ing)?)\b", "strong"),
            (
                "finalize",
                r"\b(final(ize|ized|ization)|confirm(ed|ation)|approve(d|val)?|" r"sign(ed|ing|off)?)\b",
                "strong",
            ),
            (
                "arch_is",
                r"\b(architecture|approach|strategy|plan|pattern|design|solution|stack|"
                r"framework|library|tool|tech|technology)\s+(is|will be|should be|has been|we(\'re| are))\b",
                "strong",
            ),
            (
                "use_instead",
                r"\b(use|using|utilizing|leveraging)\s+\w+\s+(instead\s+of|over|" r"rather\s+than)\b",
                "strong",
            ),
            ("use_for", r"^use\s+\w+\s+(for|in|as|to)\s+\w+", "strong"),
            (
                "we_will_use",
                r"\b(we|team|group)\s+(\'ll|will|are|\'re)\s+(use|using|adopt|adopting|"
                r"go\s+with|move\s+to|switch\s+to|build\s+with|deploy\s+(with|on|to))\b",
                "strong",
            ),
            ("agreed_to", r"\bagreed?\s+to\s+(use|adopt|go\s+with|switch\s+to|implement|build|deploy)\b", "strong"),
            (
                "decided_to",
                r"\bdecided?\s+to\s+(use|adopt|go\s+with|switch\s+to|migrate|move|" r"build|deploy|implement)\b",
                "strong",
            ),
            ("from_now_on", r"\b(from\s+now\s+on|going\s+forward|henceforth)\b", "strong"),
            (
                "mandatory",
                r"\b(are|is|will be)\s+(mandatory|required|standard|policy|rule|practice|"
                r"norm|convention|default)\b",
                "strong",
            ),
        ],
        flags=re.IGNORECASE,
    )

    # ===== Strong decision (ZH) =====
    b.set_language("zh")
    b.add_decision_batch(
        [
            ("we_use", r"我们(用|采用|选了|决定用)", "strong"),
            ("decide", r"(决定|确定|选定)", "strong"),
            ("plan", r"(方案|策略|架构)", "strong"),
            ("team_agree", r"团队(同意|采用)", "strong"),
        ],
    )

    # ===== Strong decision (JA) =====
    b.set_language("ja")
    b.add_decision_batch(
        [
            ("let_use", r"(使いましょう|行きましょう|に決めました|選びました)", "strong"),
            ("adopt", r"(採用|決定|選択)", "strong"),
            ("team", r"(チーム|合意)", "strong"),
        ],
    )
    b.register()
