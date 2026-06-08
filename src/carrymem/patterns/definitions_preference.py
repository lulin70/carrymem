"""Preference pattern definitions."""

import re

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_preference_patterns(registry: PatternRegistry) -> None:
    """Register all preference patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Strong preference (EN) =====
    b.create_group("preference_strong", PatternType.PREFERENCE)
    b.set_language("en")
    b.add_preference_batch(
        [
            (
                "prefer_over",
                r"\b(i\s+)?(prefer|preference|favor|favour|rather)\b.*" r"\b(over|instead of|to|than|rather than)\b",
                "strong",
            ),
            (
                "use_over",
                r"\b(use|using|utilizing|adopting|choosing|picking|going with)\b.*"
                r"\b(over|instead of|rather than|not)\b",
                "strong",
            ),
            (
                "always_use",
                r"^(i\s+)?(always|never|generally|typically|usually|normally|consistently)"
                r"\s+(use|prefer|like|love|hate|avoid|stick to|go for)\b",
                "strong",
            ),
            (
                "my_default",
                r"\b(my\s+)?(default|standard|convention|practice|habit|rule|policy|"
                r"preference|style|choice|approach|way)\s+(is|are|will be|has been|should be)\b",
                "strong",
            ),
            (
                "when_coding",
                r"\b(when|while|whenever|if)\s+(writing|coding|developing|building|"
                r"working)\s+\w+,\s*i\s+(always|usually|prefer|like|tend to)\b",
                "strong",
            ),
            (
                "context_prefer",
                r"\b(for|in|on|during)\s+\w+.*(i\s+)?(prefer|use|choose|pick|like|" r"stick to|go with)\b",
                "strong",
            ),
            (
                "really_like",
                r"\b(i\s+)?(really\s+)?(like|love|enjoy|appreciate|admire|adore|hate|"
                r"dislike|can\'t stand|despise|loathe)\b",
                "medium",
            ),
            ("fan_of", r"\b(big\s+)?(fan\s+of|supporter of|advocate for|pro-|anti-)\b", "medium"),
        ],
        flags=re.IGNORECASE,
    )

    # ===== Strong preference (ZH) =====
    b.set_language("zh")
    b.add_preference_batch(
        [
            ("like", r"我(喜欢|偏好|偏爱|倾向于|习惯|爱|讨厌|不喜欢)", "medium"),
            ("avoid", r"(别用|不要用|避免)", "strong"),
            ("always", r"(总是|从不|通常|一般)", "strong"),
            ("my_default", r"我的(默认|标准|风格|习惯|选择)", "strong"),
            ("like_use", r"我喜欢用", "medium"),
            ("dislike", r"我不喜欢", "medium"),
        ],
    )

    # ===== Strong preference (JA) =====
    b.set_language("ja")
    b.add_preference_batch(
        [
            ("like_dislike", r"(好き|嫌い|好む|欲しい)", "medium"),
            ("always", r"(いつも|常に|通常|習慣的に)", "strong"),
            ("want_use", r"(使いたい|使ってください|お願い)", "medium"),
            ("avoid", r"(避けて|使わず)", "strong"),
            ("default", r"(デフォルト|標準|スタイル|選択)", "strong"),
        ],
    )
    b.register()
