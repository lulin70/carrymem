"""Correction pattern definitions."""

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_correction_patterns(registry: PatternRegistry) -> None:
    """Register all correction patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Explicit correction (EN) - Tier 1 =====
    b.create_group("correction_explicit", PatternType.CORRECTION)
    b.set_language("en")
    b.add_correction_batch(
        [
            ("correction_colon", r"^correction\s*:", 1),
            ("correction_only", r"^correction$", 1),
            ("scratch_that", r"\bscratch\s+that\b", 1),
            ("forget_said", r"\bforget\s+(about|what|i)\s+(i\s+)?(said|told you)\b", 1),
            ("ignore_said", r"\bignore\s+(what|i)\s+(said|told|mentioned)\b", 1),
            ("never_mind", r"\bnever\s+mind\b", 1),
            ("let_me_rephrase", r"\blet\s+me\s+(rephrase|redo|refine|correct|clarify)\b", 1),
            ("take_back", r"\bi\s+(take\s+that\s+back|didn\'t\s+mean\s+that)\b", 1),
            ("forget_instead", r"\bforget\s+about\b.*\b(instead|rather|better|use|go\s+with)\b", 1),
        ],
        confidence=0.85,
    )

    # ===== Explicit correction (ZH) - Tier 1 =====
    b.set_language("zh")
    b.add_correction_batch(
        [
            ("jiuzheng_colon", r"^纠正[：:]", 1),
            ("jiuzheng_yixia", r"^纠正一下", 1),
            ("gengzheng_colon", r"^更正[：:]", 1),
            ("shuocuole", r"我之前说错了", 1),
            ("buduui", r"之前说的不对", 1),
            ("hulve", r"忽略之前说的", 1),
            ("wangdiao", r"忘掉之前说的", 1),
            ("bushi_zheyang", r"不是这样的", 1),
            ("budui_yinggai", r"不对[，,]应该", 1),
            ("cuole_yinggai", r"错了[，,]应该是", 1),
            ("budui_budui", r"不对不对", 1),
            ("nage_budui", r"那个不对", 1),
            ("fangfa_cuole", r"方法错了", 1),
            ("peizhi_cuole", r"配置有错", 1),
            ("hulve_zhiqian", r"之前说的忽略", 1),
            ("zuofei", r"上个想法作废", 1),
        ],
        confidence=0.85,
    )

    # ===== Explicit correction (JA) - Tier 1 =====
    b.set_language("ja")
    b.add_correction_batch(
        [
            ("teisei_colon", r"^訂正[：:]", 1),
            ("teisei_shimasu", r"^訂正します", 1),
            ("shuusei_colon", r"^修正[：:]", 1),
            ("mae_machigai", r"前に言ったのは間違い", 1),
            ("mushi", r"前の発言は無視", 1),
            ("iya_iya", r"いやいや", 1),
            ("chigaimasu", r"それは違います", 1),
            ("machigatta", r"間違ったアプローチ", 1),
            ("settei_eraa", r"設定にエラー", 1),
            ("mae_suuchi", r"前の数字は間違って", 1),
        ],
        confidence=0.85,
    )
    b.register()

    # ===== Structural correction (EN) - Tier 2 =====
    b.create_group("correction_structural", PatternType.CORRECTION)
    b.set_language("en")
    b.add_correction_batch(
        [
            ("negation_start", r"^(?:no[,\.]?|not\s+|wait[,\.]?\s+|hold\s+on)", 2),
            ("wrong_statement", r"(?:that\'s|it\'s|this\s+is)\s+(?:all\s+wrong|wrong|incorrect|"
             r"not\s+right|not\s+correct|mistaken)", 2),
            ("actually_clarify", r"^(?:actually|in\s+fact|let\s+me\s+clarify|to\s+be\s+clear|"
             r"let\s+me\s+be\s+clear)[,\s:]", 2),
            ("actually_is", r"\bactually\s+(is|was)\b", 2),
            ("is_actually", r"\bis\s+actually\b", 2),
            ("switch_to", r"(?:use|try|go\s+with|switch\s+to|change\s+to)\s+(?:this|that|the)\s+"
             r"(?:one|instead|approach|way|method)", 2),
            ("undo_revert", r"(?:undo|revert|rollback|cancel|discard|scrap|remove)\s+(?:that|this|the|it)\s", 2),
            ("prefer_instead", r"(?:\w+\s+is\s+better|prefer\s+\w+\s+instead|rather\s+(?:have|use|go)\s+with)"
             r"\b.*\b(?:than|over|instead\s+of)\b", 2),
            ("error_fix", r"(?:there\'?s?\s+an?\s+|(?:i\s+)?made\s+a\s+)(?:error|mistake|bug|issue|problem|typo)"
             r".*\bfix\b", 2),
            ("not_but", r"\bnot\s+.+,\s*(?:but\s+)?(instead|rather|use|try)\b", 2),
            ("nope_wrong", r"^(?:nope|no)[,.\s]+(that|it|this)\s+(?:\'?s\s+)?(not\s+)?"
             r"(right|correct|wrong|what\s+i\s+meant)", 2),
        ],
        confidence=0.75,
    )

    # ===== Structural correction (ZH) - Tier 2 =====
    b.set_language("zh")
    b.add_correction_batch(
        [
            ("budui", r"不对[，,]?", 2),
            ("cuole", r"错了[，,]?", 2),
            ("bushi_ershi", r"不是.*而是", 2),
            ("yinggai_bushi", r"应该是.*不是", 2),
            ("qishi_jueding", r"其实.*决定", 2),
            ("chengqing", r"我澄清一下", 2),
            ("dengdeng", r"等等.*不是那个意思", 2),
            ("huitui", r"回退到.*方案", 2),
            ("bushi_yong", r"不是.*用.*才对", 2),
        ],
        confidence=0.75,
    )

    # ===== Structural correction (JA) - Tier 2 =====
    b.set_language("ja")
    b.add_correction_batch(
        [
            ("iya", r"いや[、,]?", 2),
            ("machigatte", r"間違って", 2),
            ("jitsuwa_kime", r"実は.*に決め", 2),
            ("kakunin", r"確認しますが", 2),
            ("tadashiku_nai", r"正しくありません", 2),
            ("mae_modori", r"前のアプローチに戻", 2),
        ],
        confidence=0.75,
    )
    b.register()
