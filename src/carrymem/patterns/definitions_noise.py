"""Noise pattern definitions (acknowledgment, chitchat, command, question, etc.)."""

import re

from carrymem.patterns.base import NoiseCategory
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_noise_patterns(registry: PatternRegistry) -> None:
    """Register all noise patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Acknowledgment (EN) =====
    b.create_group("noise_ack", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("ok", r"^ok\.?$"),
            ("okay", r"^okay\.?$"),
            ("o_k", r"^o\.k\.?$"),
            ("oki", r"^oki\.?$"),
            ("sure", r"^sure\.?$"),
            ("yes", r"^yes\.?$"),
            ("yeah", r"^yeah\.?$"),
            ("yep", r"^yep\.?$"),
            ("ya", r"^ya$"),
            ("got_it", r"^got\s+it\.?$"),
            ("gotcha", r"^gotcha\.?$"),
            ("alright", r"^alright\.?$"),
            ("alrighty", r"^alrighty\.?$"),
            ("understood", r"^understood\.?$"),
            ("noted", r"^noted\.?$"),
            ("roger_that", r"^roger\s+that\.?$"),
            ("copy_that", r"^copy\s+that\.?$"),
            ("thanks", r"^thanks?\.?$"),
            ("thank_you", r"^thank\s+you\.?$"),
            ("thx", r"^thx\.?$"),
            ("ty", r"^ty\.?$"),
            ("appreciate_it", r"^appreciate\s+it\.?$"),
            ("sounds_good", r"^sounds?\s+(good|great)\.?$"),
            ("makes_sense", r"^alright,?\s+makes?\s+sense\.?$"),
            ("noted_thanks", r"^noted,?\s+thanks?.*$"),
            ("got_it_handle", r"^got\s+it,?.*\s+handle"),
        ],
        NoiseCategory.ACKNOWLEDGMENT,
        flags=re.IGNORECASE,
    )
    # Extended acknowledgment with context
    b.add_noise(
        "ext_with_context",
        r"^(ok|okay|sure|alright|got\s+it)[,\s]+",
        NoiseCategory.ACKNOWLEDGMENT,
        flags=re.IGNORECASE,
    )

    # ===== Acknowledgment (ZH) =====
    b.set_language("zh")
    b.add_noise_batch(
        [
            ("good", r"^好的[。.]?$"),
            ("en", r"^嗯[。.]?$"),
            ("ok", r"^行[。.]?$"),
            ("right", r"^对[。.]?$"),
            ("received", r"^收到[。.]?$"),
            ("understand", r"^明白[。.]?$"),
            ("know", r"^知道了[。.]?$"),
            ("no_problem", r"^没问题[。.]?$"),
            ("can", r"^可以[。.]?$"),
            ("thanks", r"^谢谢[。.]?$"),
        ],
        NoiseCategory.ACKNOWLEDGMENT,
    )

    # ===== Acknowledgment (JA) =====
    b.set_language("ja")
    b.add_noise_batch(
        [
            ("yes", r"^はい[。.]?$"),
            ("no", r"^いいえ[。.]?$"),
            ("understand", r"^わかりました[。.]?$"),
            ("roger", r"^了解[。.]?$"),
            ("thanks", r"^ありがとう[。.]?$"),
            ("ok", r"^OK[。.]?$"),
            ("i_see", r"^なるほど[。.]?$"),
            ("that_s_right", r"^そうですね[。.]?$"),
        ],
        NoiseCategory.ACKNOWLEDGMENT,
    )
    b.register()

    # ===== Chitchat (EN) =====
    b.create_group("noise_chat", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("hi", r"^hi$"),
            ("hello", r"^hello$"),
            ("hey", r"^hey$"),
            ("howdy", r"^howdy$"),
            ("nice_weather", r"^nice\s+(weather|day|to\s+meet\s+you)\.?"),
            ("weather", r"^(it'?s\s+)?(raining|sunny|cloudy|hot|cold|warm|snowing).*$"),
            ("temp_today", r"^(too\s+)?(hot|cold|warm|humid)\s+today\.?"),
            ("how_was", r"^(how\s+was\s+your\s+(weekend|day|night))\??$"),
            ("did_you", r"^(did\s+you\s+(watch|see|try).*)\??$"),
            ("congrats", r"^(happy\s+birthday|congrats|congratulations)"),
            ("have_you", r"^(have\s+you\s+tried|seen)\s+(that|this|the)\s+.*\??$"),
            ("bye", r"^(see\s+you|talk\s+later|goodbye|bye|take\s+care)\.?$"),
            ("hmm", r"^(interesting|\.\.\.|hmm|oh\s+really|is\s+that\s+so|cool)[\s!]*$"),
            ("what_a", r"^what\s+a\s+(beautiful|lovely|nice|great)\s+(day|morning|evening)"),
            ("let_me_think1", r"^hmm[,\.]?\s+let\s+me\s+think"),
            ("let_me_think2", r"^let\s+me\s+think\s*(about\s+it)?$"),
        ],
        NoiseCategory.CHITCHAT,
        flags=re.IGNORECASE,
    )

    # ===== Chitchat (ZH) =====
    b.set_language("zh")
    b.add_noise_batch(
        [
            ("hello", r"^你好[！!？?]?$"),
            ("hi", r"^嗨[！!？?]?$"),
            ("morning", r"^早上好[！!]?$"),
            ("afternoon", r"^下午好[！!]?$"),
            ("bye", r"^再见[！!]?$"),
            ("see_you", r"^回头见[！!]?$"),
        ],
        NoiseCategory.CHITCHAT,
    )

    # ===== Chitchat (JA) =====
    b.set_language("ja")
    b.add_noise_batch(
        [
            ("hello", r"^こんにちは[！!？]?$"),
            ("morning", r"^おはよう[！!？]?$"),
            ("bye", r"^さようなら[！!？]?$"),
            ("see_you", r"^またね[！!？]?$"),
        ],
        NoiseCategory.CHITCHAT,
    )
    b.register()

    # ===== Command (EN) =====
    b.create_group("noise_cmd", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("pkg_mgr", r"^(npm|pip|conda|cargo|go|gradle|maven|docker|kubectl|git|make|cmake)\s+"),
            ("shell", r"^(cd |ls |cat |echo |rm |cp |mv |mkdir |touch |chmod |chown |grep |find |wget |curl )"),
            ("runtime", r"^(python|node|java|ruby|php|bash|sh|zsh|fish)\s+"),
        ],
        NoiseCategory.COMMAND,
        match_method="match",
    )
    b.register()

    # ===== Fact indicators (used by noise filter) =====
    b.create_group("noise_fact_indicator", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("number", r"\d+(\.\d+)"),
            ("be_verb", r"\b(is|are|was|were|has|have)\s+"),
            ("action_verb", r"\b(supports?|requires?|provides?|includes?)\s+"),
        ],
        NoiseCategory.FACT_INDICATOR,
        match_method="search",
    )
    b.register()

    # ===== Question (EN) =====
    b.create_group("noise_question", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("wh", r"^(how|what|when|where|why|who|which|can|could|would|is|are|do|does|did)\s+"),
            ("whats", r"^what\'?s\s+"),
            ("whos", r"^who\'?s\s+"),
            ("wheres", r"^where\'?s\s+"),
            ("hows", r"^how\'?s\s+"),
        ],
        NoiseCategory.QUESTION,
        flags=re.IGNORECASE,
    )

    # ===== Question (ZH) =====
    b.set_language("zh")
    b.add_noise(
        "question",
        r"^(怎么|如何|为什么|什么|哪里|谁|多少|是不是|能不能|可以吗)",
        NoiseCategory.QUESTION,
    )

    # ===== Question (JA) =====
    b.set_language("ja")
    b.add_noise(
        "question",
        r"^(どう|なぜ|何|どこ|誰|いくら|どうやって)",
        NoiseCategory.QUESTION,
    )
    b.register()

    # ===== Instruction (EN) =====
    b.create_group("noise_instruction", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("action", r"^(please\s+)?(run|execute|start|launch|deploy|build|test|check|verify)\s+"),
            ("create", r"^(create|open|send|write|generate|download|install|update|delete|remove)\s+"),
            ("help", r"^(can\s+you\s+)?(help\s+me\s+)?(show|tell|give|explain|find|search)\s+"),
        ],
        NoiseCategory.INSTRUCTION,
        flags=re.IGNORECASE,
    )
    b.register()

    # ===== Workflow keywords (used by instruction filter) =====
    b.create_group("noise_workflow", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("every", r"\bevery\b"),
            ("always", r"\balways\b"),
            ("before", r"\bbefore\b"),
            ("after", r"\bafter\b"),
            ("weekly", r"\bweekly\b"),
            ("monthly", r"\bmonthly\b"),
            ("daily", r"\bdaily\b"),
            ("each", r"\beach\b"),
        ],
        NoiseCategory.WORKFLOW,
        match_method="search",
    )
    b.register()

    # ===== Adversarial (EN) =====
    b.create_group("noise_adversarial", PatternType.NOISE)
    b.set_language("en")
    b.add_noise_batch(
        [
            ("dont_remember", r"\bdon\'?t\s+remember\s+(this|it|me)\b"),
            ("not_memory", r"\bnot\s+(a\s+)?memory\b"),
            ("just_test", r"\bjust\s+a\s+test\b"),
            ("pretend", r"\bpretend\s+this\s+is\b"),
            ("ignore", r"\bignore\s+(this|the\s+above)\b"),
            ("not_worth", r"\bdefinitely\s+not\s+worth\b"),
            ("do_not_store", r"\bdo\s+not\s+(store|save|remember)\b"),
            ("is_test", r"\bthis\s+is\s+(just\s+)?(a\s+)?(test|fake|random)\b"),
        ],
        NoiseCategory.ADVERSARIAL,
        match_method="search",
    )
    b.register()


# Import PatternType locally to avoid circular import at module level
from carrymem.patterns.base import PatternType  # noqa: E402
