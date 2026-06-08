"""Fact pattern definitions."""

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_fact_patterns(registry: PatternRegistry) -> None:
    """Register all fact patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Chinese fact patterns =====
    b.create_group("fact_zh", PatternType.FACT)
    b.set_language("zh")
    b.add_fact_batch(
        [
            ("shi", r"(.+)是(.+)", "structural"),
            ("you", r"(.+)有(.+)", "structural"),
            ("zuo", r"(.+)在做(.+)", "structural"),
            ("shuyu", r"(.+)属于(.+)", "structural"),
            ("weiyu", r"(.+)位于(.+)", "structural"),
        ],
    )

    # ===== Japanese fact patterns =====
    b.set_language("ja")
    b.add_fact_batch(
        [
            ("desu", r"(.+)(は|が)(.+)(です|である|します|あります)", "structural"),
            ("ni_aru", r"(.+)(に)(あります|あります|あります)", "structural"),
            ("no_youken", r"(.+)(の)(要件|バージョン|仕様|制限)", "structural"),
        ],
    )
    b.register()

    # ===== Tech terms (EN) - Tier 1 indicators =====
    b.create_group("fact_tech_term", PatternType.FACT)
    b.set_language("en")
    b.add_fact_batch(
        [
            (
                "protocol",
                r"\b(api|sdk|http|https|tcp|udp|ip|dns|sql|nosql|graphql|rest|grpc|" r"json|xml|csv)\b",
                "tech_term",
            ),
            (
                "language",
                r"\b(python|javascript|typescript|java|kotlin|go|rust|c\+\+|ruby|php|" r"bash|shell)\b",
                "tech_term",
            ),
            (
                "database",
                r"\b(postgresql|mysql|mongodb|redis|elasticsearch|dynamodb|sqlite|" r"supabase|firebase)\b",
                "tech_term",
            ),
            ("infra", r"\b(docker|kubernetes|aws|gcp|azure|linux|nginx|git|github|ci|cd)\b", "tech_term"),
            ("ai", r"\b(llm|gpt|claude|gemini|llama|rag|vector|embedding|pytorch|tensorflow|mcp)\b", "tech_term"),
            ("security", r"\b(oauth|jwt|encryption|2fa|mfa|rbac|sso|ssl|tls|api\s+key)\b", "tech_term"),
            ("version_num", r"\d+(\.\d+)+", "version"),
            ("date_pattern", r"\d{4}[-/]\d{2}", "version"),
            ("v_version", r"\b(v?\d+\.\d+)\b", "version"),
        ],
    )
    b.register()

    # ===== Tech structural patterns (EN) - Tier 1 =====
    b.create_group("fact_tech_struct", PatternType.FACT)
    b.set_language("en")
    b.add_fact_batch(
        [
            (
                "is_minimum",
                r"(.+)\s+(?:is|are|was|were|runs?|operates?)\s+(?:the\s+)?"
                r"(?:minimum|required|default|located|hosted|running|deployed|based)",
                "tech_struct",
            ),
            ("runs_on", r"(.+)\s+(?:runs?|operates?|works?)\s+(?:on|in|at|with|using|via)\s+(.+)", "tech_struct"),
            ("supports", r"(.+)\s+(?:supports?|provides?|includes?|contains?|features?)\s+(.+)", "tech_struct"),
            ("requires", r"(.+)\s+(?:requires?|needs?|uses?|utilizes?)\s+(.+)", "tech_struct"),
            (
                "config_is",
                r"(?:the|our|my|this)\s+(?:api|database|server|system|service|app|"
                r"endpoint|port|limit|version|config)\s+.+(?:is|are|=)",
                "tech_struct",
            ),
            ("people_count", r"\b\d+\s*(?:employees?|users?|members?|people|teams?|instances?|pods?)\b", "tech_struct"),
            ("is_are", r"(.+)\s+(?:is|are|has|was|were)\s+(.+)", "tech_struct"),
            ("status_is", r"(.+)\s+(?:status)\s+\d+\s+(?:is|means|for)\s+(.+)", "tech_struct"),
            ("handshake", r"(.+)\s+(?:handshake)\s+(?:requires?|needs?|involves?)\s+(.+)", "tech_struct"),
            ("shares", r"(.+)\s+(?:share[s]?\s+a)\s+(.+)", "tech_struct"),
            ("by_default", r"(.+)\s+(?:by\s+default)\b", "tech_struct"),
        ],
        confidence=0.8,
    )
    b.register()

    # ===== Quantifiable facts (EN) - Tier 2 =====
    b.create_group("fact_quantifiable", PatternType.FACT)
    b.set_language("en")
    b.add_fact_batch(
        [
            ("unit", r"\b\d+\s*(?:%|percent|mb|gb|tb|ms|sec|min|hour|day|week|month|year|am|pm|jst|utc)\b", "quant"),
            (
                "people_unit",
                r"\b\d+[.,]?\d*\s*(?:employees?|users?|members?|people|teams?|" r"servers?|nodes?|pods?)\b",
                "quant",
            ),
            ("weekday", r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b", "quant"),
            ("time", r"\b\d{1,2}(?:am|pm|:)\b", "quant"),
            ("city", r"\b(?:shanghai|beijing|tokyo|london|singapore|seoul|bangalore|berlin)\b", "quant"),
            ("aws_region", r"\bus-east-\d|us-west-\d|ap-southeast-\d|eu-west-\d\b", "quant"),
            ("money", r"\$[\d,]+|\d+\s*k\s*\$|\$\d+k\b", "quant"),
            ("version_tag", r"\bv\d+[\.\w]*\b", "quant"),
            (
                "month",
                r"\b(january|february|march|april|may|june|july|august|september|" r"october|november|december)\b",
                "quant",
            ),
        ],
        confidence=0.7,
    )
    b.register()

    # ===== Quantifiable structural patterns (EN) - Tier 2 =====
    b.create_group("fact_quant_struct", PatternType.FACT)
    b.set_language("en")
    b.add_fact_batch(
        [
            ("is_are", r"(.+)\s+(?:is|are|has|have|was|were)\s+(.+)", "quant_struct"),
            ("ends_on", r"(.+)\s+(?:ends?|starts?|runs?|lasts?)\s+(?:on|at|in|by|every|each)\s*(.+)?", "quant_struct"),
            (
                "office_schedule",
                r"(?:my|our|the|this)\s+(?:office|work|team|standup|sync|meeting|" r"budget|approval)\s+.+",
                "quant_struct",
            ),
            (
                "schedule_keyword",
                r".*\b(?:hours?|schedule|time|deadline|budget|limit|rate|cost|price|" r"version)\b.*",
                "quant_struct",
            ),
            (
                "past_action",
                r"^(?:i|we|my|our)\s+.+\s+(?:got|had|went|took|bought|visited|attended|"
                r"started|finished|completed|moved|joined|left|received|found|built|created)\b",
                "quant_struct",
            ),
        ],
        confidence=0.7,
    )
    b.register()

    # ===== General declarative (EN) - Tier 3 =====
    b.create_group("fact_general", PatternType.FACT)
    b.set_language("en")
    b.add_fact_batch(
        [
            (
                "we_is",
                r"^(?:we|i|our|my|the|this)\s+.+\s+(?:is|are|has|have|supports?|uses?|" r"runs?|requires?)\s+.+",
                "general",
            ),
            (
                "live_work",
                r".+\s+(?:live[s]?\s+in|work[s]?\s+(?:for|at|on|with)|based?\s+"
                r"(?:in|on|at)|located?\s+(?:in|at))\s+.+",
                "general",
            ),
            (
                "past_tense",
                r"^(?:i|we)\s+(?:got|had|went|took|bought|visited|attended|started|"
                r"finished|completed|moved|joined|left|received|found|built|created|gave|sent|called|"
                r"met|saw|heard|read|wrote|drove|flew|stayed|lived|worked|studied|played|watched|"
                r"ate|drank|cooked|cleaned|fixed|repaired|broke|lost|kept|sold|brought|put|set|"
                r"turned|made|ran|fell|grew|became|felt|thought|knew|believed|decided|chose|"
                r"preferred|loved|hated|enjoyed|avoided|tried|wanted|needed|learned|discovered|"
                r"realized|remembered|forgot)\b",
                "general",
            ),
        ],
        confidence=0.6,
    )
    b.register()
