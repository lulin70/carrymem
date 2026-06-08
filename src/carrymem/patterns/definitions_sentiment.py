"""Sentiment pattern definitions."""

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_sentiment_patterns(registry: PatternRegistry) -> None:
    """Register all sentiment patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Emotion patterns (EN) =====
    b.create_group("sentiment_emotion", PatternType.SENTIMENT)
    b.set_language("en")
    b.add_sentiment_batch(
        [
            ("i_feel", r"^(?:i\s+)?(?:\'?m|am|was|feel|feeling|get|getting)\s+(?:so\s+|really\s+|"
             r"very\s+|super\s+)?(?:happy|excited|proud|grateful|thrilled|delighted|relieved|"
             r"impressed|sad|angry|upset|frustrated|annoyed|worried|scared|exhausted|tired|"
             r"bored|disappointed|confused|overwhelmed|stressed)\b", "emotion"),
            ("love_hate", r"\b(?:i\s+)?(?:love|hate|loathe|detest|enjoy|appreciate|dislike|dread)"
             r"\s+(?:it|this|that|the\s+\w+)", "emotion"),
            ("this_is", r"^(?:this|the)\s+.+\s+is\s+(?:so\s+|really\s+|absolutely\s+|incredibly\s+)?"
             r"(?:great|awesome|amazing|fantastic|wonderful|terrible|awful|horrible|"
             r"frustrating|annoying|beautiful)", "emotion"),
            ("amazing_work", r"\b(amazing|brilliant|outstanding|superb|marvelous|incredible|"
             r"fantastic)\s+(work|job|effort|team|result|achievement)!", "emotion"),
            ("work_on", r"^\w+\s+work\b.*\b(?:on|for|with)\b", "emotion"),
        ],
        confidence=0.8,
    )
    b.register()

    # ===== Adjective patterns (EN) =====
    b.create_group("sentiment_adj", PatternType.SENTIMENT)
    b.set_language("en")
    b.add_sentiment_batch(
        [
            ("emotion_adj", r"\b(happy|sad|angry|frustrated|annoyed|excited|tired|exhausted|bored|"
             r"worried|proud|glad|upset)\b", "adj"),
            ("quality_adj", r"\b(great|good|bad|terrible|awful|nice|cool|lovely|horrible|"
             r"amazing|fantastic|beautiful)\b", "adj"),
        ],
        confidence=0.65,
    )
    b.register()

    # ===== Sentiment (ZH) =====
    b.create_group("sentiment_zh", PatternType.SENTIMENT)
    b.set_language("zh")
    b.add_sentiment_batch(
        [
            ("intensifier", r"(太|真|好|非常|特别)(棒|好|差|烂|烦|慢|快|美|糟糕|赞|牛)(了|！|!)?", "emotion"),
            ("very_emotion", r"(很|非常|特别)(开心|难过|生气|满意|失望|焦虑|担心|害怕)", "emotion"),
            ("strong_emotion", r".*(烦|崩溃|心碎|无语|郁闷|不爽|焦虑|太棒)", "emotion"),
        ],
        confidence=0.8,
    )
    b.register()

    # ===== Sentiment (JA) =====
    b.create_group("sentiment_ja", PatternType.SENTIMENT)
    b.set_language("ja")
    b.add_sentiment_batch(
        [
            ("intensifier", r"(とても|すごく|本当に|めちゃくちゃ)(嬉しい|悲しい|楽しい|つまらない|怖い|不安|心配)", "emotion"),
            ("strong", r".*(イライラ|ストレス|疲れた|うんざり|残念)", "emotion"),
            ("quality", r"(素晴らしい|最高|ひどい|最悪|すごい|やばい)", "emotion"),
        ],
        confidence=0.8,
    )
    b.register()

    # ===== Fact exclusion markers (used by sentiment to skip factual content) =====
    b.create_group("sentiment_fact_exclusion", PatternType.SENTIMENT)
    b.set_language("en")
    b.add_sentiment_batch(
        [
            ("tech_term", r"\b(api|sdk|http|sql|python|java|docker|kubernetes|aws|redis|nginx)\b", "fact_exclusion"),
            ("db_term", r"\b(postgresql|mysql|mongodb|sqlite|supabase|firebase)\b", "fact_exclusion"),
            ("version", r"\d+(\.\d+)+", "fact_exclusion"),
            ("v_version", r"\b(v?\d+\.\d+)\b", "fact_exclusion"),
            ("is_required", r"\b(is|are|was|were|has|have)\s+(the\s+)?(?:minimum|required|default|"
             r"located|hosted|running|deployed|based)\b", "fact_exclusion"),
            ("runs_on", r"\b(runs?|operates?|works?)\s+(on|in|at|with|using|via)\b", "fact_exclusion"),
            ("supports", r"\b(supports?|provides?|includes?|requires?|needs?|uses?)\s+\b", "fact_exclusion"),
            ("infra_noun", r"\b(server|database|endpoint|port|config|version|limit|service)\b", "fact_exclusion"),
        ],
        confidence=0.0,
    )
    b.register()
