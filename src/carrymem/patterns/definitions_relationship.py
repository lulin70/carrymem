"""Relationship pattern definitions."""

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_relationship_patterns(registry: PatternRegistry) -> None:
    """Register all relationship patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Role patterns (EN) =====
    b.create_group("relationship_role", PatternType.RELATIONSHIP)
    b.set_language("en")
    b.add_relationship_batch(
        [
            ("owns_leads", r"^(\w+)\s+(?:owns?|leads?|manages?|heads?|runs?)\s+(?:the\s+)?(.+)", "role"),
            (
                "is_role",
                r"(\w+)\s+(?:is|was)\s+(?:our|the|my)\s+(dba|pm|lead|architect|owner|"
                r"maintainer|contact|expert|specialist)",
                "role",
            ),
            ("handles", r"(\w+)\s+(?:does|handles?|takes?\s+care\s+of|works?\s+on)\s+(.+)", "role"),
            ("reports_to", r"(\w+)\s+(?:reports?\s+to|answers?\s+to)\s+(\w+)", "role"),
            ("on_team", r"(\w+)\s+(?:is\s+(?:on|in)|belongs?\s+to)\s+(?:the\s+)?(.+)\s+team", "role"),
            ("ask_about", r"(?:ask|contact|reach(?:\s+out)?\s+to)\s+(\w+)\s+(?:about|for|regarding)", "role"),
        ],
    )

    # ===== Role patterns (ZH) =====
    b.set_language("zh")
    b.add_relationship_batch(
        [
            ("fuzhe", r"(.+)(负责|管理|处理|担当)(.+)", "role"),
            ("team", r"(.+)(是|在)(.+)(团队|组)", "role"),
            ("colleague", r"(我的|我们的)(经理|同事|队友|领导)", "role"),
            ("cooperate", r"(.+)(和|与)(.+)(一起|合作)", "role"),
        ],
    )

    # ===== Role patterns (JA) =====
    b.set_language("ja")
    b.add_relationship_batch(
        [
            ("tantou", r"(.+)(が|は)(.+)(を)?(担当|管理|処理)", "role"),
            ("manager", r"(.+)(の)(マネージャー|リード|担当者)", "role"),
            ("reverse", r"(マネージャー|リード|担当者)(の)(.+)", "role"),
            ("kyouryoku", r"(.+)(と)(.+)(一緒に|協力)", "role"),
        ],
    )
    b.register()

    # ===== Dependency patterns (EN) =====
    b.create_group("relationship_dep", PatternType.RELATIONSHIP)
    b.set_language("en")
    b.add_relationship_batch(
        [
            ("depends_on", r"(.+)\s+(?:depends?\s+on|relies?\s+on|uses?|imports?|calls?|invokes?)\s+(.+)", "dep"),
            (
                "routes_to",
                r"(.+)\s+(?:which|that)\s+(?:routes?\s+to|calls?|triggers?|"
                r"publishes?\s+events?\s+(?:to|that))\s+(.+)",
                "dep",
            ),
            ("subscribes", r"(.+)\s+(?:subscribes?\s+to|listens?\s+to|consumes?|reads?\s+from)\s+(.+)", "dep"),
            ("bridges", r"(.+)\s+(?:sits?\s+between|connects?\s+|bridges?|links?)\s+(.+)", "dep"),
            ("triggers_after", r"(.+)\s+(?:triggers?\s+after|runs?\s+after|starts?\s+when|fires?\s+on)\s+(.+)", "dep"),
            ("pushes_to", r"(.+)\s+(?:pushes?\s+to|deploys?\s+to|merges?\s+into|integrates?\s+with)\s+(.+)", "dep"),
            ("arrow_unicode", r"(.+)→(.+)", "dep"),
            ("arrow_ascii", r"(.+)\s+->\s*(.+)", "dep"),
        ],
    )
    b.register()
