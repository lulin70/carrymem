from typing import Dict, List, Optional, Any
import re
from carrymem.utils.language import language_manager
from carrymem.utils.logger import logger


class PatternAnalyzer:
    """Pattern-based memory analyzer."""

    # Precompiled regex patterns (compiled once at class definition time)
    _RE_PATTERNS = {
        # === _is_noise: Acknowledgment patterns (B1) ===
        "noise_ack_01": re.compile(r"^ok\.?$", re.IGNORECASE),
        "noise_ack_02": re.compile(r"^okay\.?$", re.IGNORECASE),
        "noise_ack_03": re.compile(r"^o\.k\.?$", re.IGNORECASE),
        "noise_ack_04": re.compile(r"^oki\.?$", re.IGNORECASE),
        "noise_ack_05": re.compile(r"^sure\.?$", re.IGNORECASE),
        "noise_ack_06": re.compile(r"^yes\.?$", re.IGNORECASE),
        "noise_ack_07": re.compile(r"^yeah\.?$", re.IGNORECASE),
        "noise_ack_08": re.compile(r"^yep\.?$", re.IGNORECASE),
        "noise_ack_09": re.compile(r"^ya$", re.IGNORECASE),
        "noise_ack_10": re.compile(r"^got\s+it\.?$", re.IGNORECASE),
        "noise_ack_11": re.compile(r"^gotcha\.?$", re.IGNORECASE),
        "noise_ack_12": re.compile(r"^alright\.?$", re.IGNORECASE),
        "noise_ack_13": re.compile(r"^alrighty\.?$", re.IGNORECASE),
        "noise_ack_14": re.compile(r"^understood\.?$", re.IGNORECASE),
        "noise_ack_15": re.compile(r"^noted\.?$", re.IGNORECASE),
        "noise_ack_16": re.compile(r"^roger\s+that\.?$", re.IGNORECASE),
        "noise_ack_17": re.compile(r"^copy\s+that\.?$", re.IGNORECASE),
        "noise_ack_18": re.compile(r"^thanks?\.?$", re.IGNORECASE),
        "noise_ack_19": re.compile(r"^thank\s+you\.?$", re.IGNORECASE),
        "noise_ack_20": re.compile(r"^thx\.?$", re.IGNORECASE),
        "noise_ack_21": re.compile(r"^ty\.?$", re.IGNORECASE),
        "noise_ack_22": re.compile(r"^appreciate\s+it\.?$", re.IGNORECASE),
        "noise_ack_23": re.compile(r"^sounds?\s+(good|great)\.?$", re.IGNORECASE),
        "noise_ack_24": re.compile(r"^alright,?\s+makes?\s+sense\.?$", re.IGNORECASE),
        "noise_ack_25": re.compile(r"^noted,?\s+thanks?.*$", re.IGNORECASE),
        "noise_ack_26": re.compile(r"^got\s+it,?.*\s+handle", re.IGNORECASE),
        "noise_ack_ext_01": re.compile(r"^(ok|okay|sure|alright|got\s+it)[,\s]+", re.IGNORECASE),
        # === _is_noise: Chitchat/Social patterns (B2) ===
        "noise_chat_01": re.compile(r"^hi$", re.IGNORECASE),
        "noise_chat_02": re.compile(r"^hello$", re.IGNORECASE),
        "noise_chat_03": re.compile(r"^hey$", re.IGNORECASE),
        "noise_chat_04": re.compile(r"^howdy$", re.IGNORECASE),
        "noise_chat_05": re.compile(r"^nice\s+(weather|day|to\s+meet\s+you)\.?", re.IGNORECASE),
        "noise_chat_06": re.compile(r"^(it'?s\s+)?(raining|sunny|cloudy|hot|cold|warm|snowing).*$", re.IGNORECASE),
        "noise_chat_07": re.compile(r"^(too\s+)?(hot|cold|warm|humid)\s+today\.?", re.IGNORECASE),
        "noise_chat_08": re.compile(r"^(how\s+was\s+your\s+(weekend|day|night))\??$", re.IGNORECASE),
        "noise_chat_09": re.compile(r"^(did\s+you\s+(watch|see|try).*)\??$", re.IGNORECASE),
        "noise_chat_10": re.compile(r"^(happy\s+birthday|congrats|congratulations)", re.IGNORECASE),
        "noise_chat_11": re.compile(r"^(have\s+you\s+tried|seen)\s+(that|this|the)\s+.*\??$", re.IGNORECASE),
        "noise_chat_12": re.compile(r"^(see\s+you|talk\s+later|goodbye|bye|take\s+care)\.?$", re.IGNORECASE),
        "noise_chat_13": re.compile(r"^(interesting|\.\.\.|hmm|oh\s+really|is\s+that\s+so|cool)[\s!]*$", re.IGNORECASE),
        "noise_chat_14": re.compile(r"^what\s+a\s+(beautiful|lovely|nice|great)\s+(day|morning|evening)", re.IGNORECASE),
        "noise_chat_15": re.compile(r"^hmm[,\.]?\s+let\s+me\s+think", re.IGNORECASE),
        "noise_chat_16": re.compile(r"^let\s+me\s+think\s*(about\s+it)?$", re.IGNORECASE),
        # === _is_noise: Command patterns (B3) ===
        "noise_cmd_01": re.compile(r"^(npm|pip|conda|cargo|go|gradle|maven|docker|kubectl|git|make|cmake)\s+"),
        "noise_cmd_02": re.compile(r"^(cd |ls |cat |echo |rm |cp |mv |mkdir |touch |chmod |chown |grep |find |wget |curl )"),
        "noise_cmd_03": re.compile(r"^(python|node|java|ruby|php|bash|sh|zsh|fish)\s+"),
        "noise_fact_01": re.compile(r"\d+(\.\d+)"),
        "noise_fact_02": re.compile(r"\b(is|are|was|were|has|have)\s+"),
        "noise_fact_03": re.compile(r"\b(supports?|requires?|provides?|includes?)\s+"),
        # === _is_noise: Question patterns (B4) ===
        "noise_q_01": re.compile(r"^(how|what|when|where|why|who|which|can|could|would|is|are|do|does|did)\s+"),
        "noise_q_02": re.compile(r"^what\'?s\s+"),
        "noise_q_03": re.compile(r"^who\'?s\s+"),
        "noise_q_04": re.compile(r"^where\'?s\s+"),
        "noise_q_05": re.compile(r"^how\'?s\s+"),
        # === _is_noise: Instruction patterns (B5) ===
        "noise_instr_01": re.compile(r"^(please\s+)?(run|execute|start|launch|deploy|build|test|check|verify)\s+"),
        "noise_instr_02": re.compile(r"^(create|open|send|write|generate|download|install|update|delete|remove)\s+"),
        "noise_instr_03": re.compile(r"^(can\s+you\s+)?(help\s+me\s+)?(show|tell|give|explain|find|search)\s+"),
        "noise_workflow_01": re.compile(r"\bevery\b"),
        "noise_workflow_02": re.compile(r"\balways\b"),
        "noise_workflow_03": re.compile(r"\bbefore\b"),
        "noise_workflow_04": re.compile(r"\bafter\b"),
        "noise_workflow_05": re.compile(r"\bweekly\b"),
        "noise_workflow_06": re.compile(r"\bmonthly\b"),
        "noise_workflow_07": re.compile(r"\bdaily\b"),
        "noise_workflow_08": re.compile(r"\beach\b"),
        # === _is_noise: Adversarial/anti-memory patterns ===
        "noise_adv_01": re.compile(r"\bdon\'?t\s+remember\s+(this|it|me)\b"),
        "noise_adv_02": re.compile(r"\bnot\s+(a\s+)?memory\b"),
        "noise_adv_03": re.compile(r"\bjust\s+a\s+test\b"),
        "noise_adv_04": re.compile(r"\bpretend\s+this\s+is\b"),
        "noise_adv_05": re.compile(r"\bignore\s+(this|the\s+above)\b"),
        "noise_adv_06": re.compile(r"\bdefinitely\s+not\s+worth\b"),
        "noise_adv_07": re.compile(r"\bdo\s+not\s+(store|save|remember)\b"),
        "noise_adv_08": re.compile(r"\bthis\s+is\s+(just\s+)?(a\s+)?(test|fake|random)\b"),
        # === _is_noise: Chinese acknowledgment (B1-ZH) ===
        "noise_zh_ack_01": re.compile(r"^好的[。.]?$"),
        "noise_zh_ack_02": re.compile(r"^嗯[。.]?$"),
        "noise_zh_ack_03": re.compile(r"^行[。.]?$"),
        "noise_zh_ack_04": re.compile(r"^对[。.]?$"),
        "noise_zh_ack_05": re.compile(r"^收到[。.]?$"),
        "noise_zh_ack_06": re.compile(r"^明白[。.]?$"),
        "noise_zh_ack_07": re.compile(r"^知道了[。.]?$"),
        "noise_zh_ack_08": re.compile(r"^没问题[。.]?$"),
        "noise_zh_ack_09": re.compile(r"^可以[。.]?$"),
        "noise_zh_ack_10": re.compile(r"^谢谢[。.]?$"),
        # === _is_noise: Japanese acknowledgment (B1-JA) ===
        "noise_ja_ack_01": re.compile(r"^はい[。.]?$"),
        "noise_ja_ack_02": re.compile(r"^いいえ[。.]?$"),
        "noise_ja_ack_03": re.compile(r"^わかりました[。.]?$"),
        "noise_ja_ack_04": re.compile(r"^了解[。.]?$"),
        "noise_ja_ack_05": re.compile(r"^ありがとう[。.]?$"),
        "noise_ja_ack_06": re.compile(r"^OK[。.]?$"),
        "noise_ja_ack_07": re.compile(r"^なるほど[。.]?$"),
        "noise_ja_ack_08": re.compile(r"^そうですね[。.]?$"),
        # === _is_noise: Chinese chitchat (B2-ZH) ===
        "noise_zh_chat_01": re.compile(r"^你好[！!？?]?$"),
        "noise_zh_chat_02": re.compile(r"^嗨[！!？?]?$"),
        "noise_zh_chat_03": re.compile(r"^早上好[！!]?$"),
        "noise_zh_chat_04": re.compile(r"^下午好[！!]?$"),
        "noise_zh_chat_05": re.compile(r"^再见[！!]?$"),
        "noise_zh_chat_06": re.compile(r"^回头见[！!]?$"),
        # === _is_noise: Japanese chitchat (B2-JA) ===
        "noise_ja_chat_01": re.compile(r"^こんにちは[！!？]?$"),
        "noise_ja_chat_02": re.compile(r"^おはよう[！!？]?$"),
        "noise_ja_chat_03": re.compile(r"^さようなら[！!？]?$"),
        "noise_ja_chat_04": re.compile(r"^またね[！!？]?$"),
        # === _is_noise: Chinese question (B4-ZH) ===
        "noise_zh_q_01": re.compile(r"^(怎么|如何|为什么|什么|哪里|谁|多少|是不是|能不能|可以吗)"),
        # === _is_noise: Japanese question (B4-JA) ===
        "noise_ja_q_01": re.compile(r"^(どう|なぜ|何|どこ|誰|いくら|どうやって)"),
        # === _detect_preference_pattern: Strong preference ===
        "pref_strong_01": re.compile(r"\b(i\s+)?(prefer|preference|favor|favour|rather)\b.*\b(over|instead of|to|than|rather than)\b", re.IGNORECASE),
        "pref_strong_02": re.compile(r"\b(use|using|utilizing|adopting|choosing|picking|going with)\b.*\b(over|instead of|rather than|not)\b", re.IGNORECASE),
        "pref_strong_03": re.compile(r"^(i\s+)?(always|never|generally|typically|usually|normally|consistently)\s+(use|prefer|like|love|hate|avoid|stick to|go for)\b", re.IGNORECASE),
        "pref_strong_04": re.compile(r"\b(my\s+)?(default|standard|convention|practice|habit|rule|policy|preference|style|choice|approach|way)\s+(is|are|will be|has been|should be)\b", re.IGNORECASE),
        "pref_strong_05": re.compile(r"\b(when|while|whenever|if)\s+(writing|coding|developing|building|working)\s+\w+,\s*i\s+(always|usually|prefer|like|tend to)\b", re.IGNORECASE),
        "pref_strong_06": re.compile(r"\b(for|in|on|during)\s+\w+.*(i\s+)?(prefer|use|choose|pick|like|stick to|go with)\b", re.IGNORECASE),
        "pref_strong_07": re.compile(r"\b(i\s+)?(really\s+)?(like|love|enjoy|appreciate|admire|adore|hate|dislike|can\'t stand|despise|loathe)\b", re.IGNORECASE),
        "pref_strong_08": re.compile(r"\b(big\s+)?(fan\s+of|supporter of|advocate for|pro-|anti-)\b", re.IGNORECASE),
        # === _detect_preference_pattern: Chinese strong preference ===
        "pref_zh_01": re.compile(r"我(喜欢|偏好|偏爱|倾向于|习惯|爱|讨厌|不喜欢)"),
        "pref_zh_02": re.compile(r"(别用|不要用|避免)"),
        "pref_zh_03": re.compile(r"(总是|从不|通常|一般)"),
        "pref_zh_04": re.compile(r"我的(默认|标准|风格|习惯|选择)"),
        "pref_zh_05": re.compile(r"我喜欢用"),
        "pref_zh_06": re.compile(r"我不喜欢"),
        # === _detect_preference_pattern: Japanese strong preference ===
        "pref_ja_01": re.compile(r"(好き|嫌い|好む|欲しい)"),
        "pref_ja_02": re.compile(r"(いつも|常に|通常|習慣的に)"),
        "pref_ja_03": re.compile(r"(使いたい|使ってください|お願い)"),
        "pref_ja_04": re.compile(r"(避けて|使わず)"),
        "pref_ja_05": re.compile(r"(デフォルト|標準|スタイル|選択)"),
        # === _detect_correction_pattern: Explicit markers (Tier 1) ===
        "corr_explicit_01": re.compile(r"^correction\s*:"),
        "corr_explicit_02": re.compile(r"^correction$"),
        "corr_explicit_03": re.compile(r"\bscratch\s+that\b"),
        "corr_explicit_04": re.compile(r"\bforget\s+(about|what|i)\s+(i\s+)?(said|told you)\b"),
        "corr_explicit_05": re.compile(r"\bignore\s+(what|i)\s+(said|told|mentioned)\b"),
        "corr_explicit_06": re.compile(r"\bnever\s+mind\b"),
        "corr_explicit_07": re.compile(r"\blet\s+me\s+(rephrase|redo|refine|correct|clarify)\b"),
        "corr_explicit_08": re.compile(r"\bi\s+(take\s+that\s+back|didn\'t\s+mean\s+that)\b"),
        "corr_explicit_09": re.compile(r"\bforget\s+about\b.*\b(instead|rather|better|use|go\s+with)\b"),
        # === _detect_correction_pattern: Chinese explicit markers ===
        "corr_zh_ex_01": re.compile(r"^纠正[：:]"),
        "corr_zh_ex_02": re.compile(r"^纠正一下"),
        "corr_zh_ex_03": re.compile(r"^更正[：:]"),
        "corr_zh_ex_04": re.compile(r"我之前说错了"),
        "corr_zh_ex_05": re.compile(r"之前说的不对"),
        "corr_zh_ex_06": re.compile(r"忽略之前说的"),
        "corr_zh_ex_07": re.compile(r"忘掉之前说的"),
        "corr_zh_ex_08": re.compile(r"不是这样的"),
        "corr_zh_ex_09": re.compile(r"不对[，,]应该"),
        "corr_zh_ex_10": re.compile(r"错了[，,]应该是"),
        "corr_zh_ex_11": re.compile(r"不对不对"),
        "corr_zh_ex_12": re.compile(r"那个不对"),
        "corr_zh_ex_13": re.compile(r"方法错了"),
        "corr_zh_ex_14": re.compile(r"配置有错"),
        "corr_zh_ex_15": re.compile(r"之前说的忽略"),
        "corr_zh_ex_16": re.compile(r"上个想法作废"),
        # === _detect_correction_pattern: Japanese explicit markers ===
        "corr_ja_ex_01": re.compile(r"^訂正[：:]"),
        "corr_ja_ex_02": re.compile(r"^訂正します"),
        "corr_ja_ex_03": re.compile(r"^修正[：:]"),
        "corr_ja_ex_04": re.compile(r"前に言ったのは間違い"),
        "corr_ja_ex_05": re.compile(r"前の発言は無視"),
        "corr_ja_ex_06": re.compile(r"いやいや"),
        "corr_ja_ex_07": re.compile(r"それは違います"),
        "corr_ja_ex_08": re.compile(r"間違ったアプローチ"),
        "corr_ja_ex_09": re.compile(r"設定にエラー"),
        "corr_ja_ex_10": re.compile(r"前の数字は間違って"),
        # === _detect_correction_pattern: Structural patterns (Tier 2) ===
        "corr_struct_01": re.compile(r"^(?:no[,\.]?|not\s+|wait[,\.]?\s+|hold\s+on)"),
        "corr_struct_02": re.compile(r"(?:that\'s|it\'s|this\s+is)\s+(?:all\s+wrong|wrong|incorrect|not\s+right|not\s+correct|mistaken)"),
        "corr_struct_03": re.compile(r"^(?:actually|in\s+fact|let\s+me\s+clarify|to\s+be\s+clear|let\s+me\s+be\s+clear)[,\s:]"),
        "corr_struct_04": re.compile(r"\bactually\s+(is|was)\b"),
        "corr_struct_05": re.compile(r"\bis\s+actually\b"),
        "corr_struct_06": re.compile(r"(?:use|try|go\s+with|switch\s+to|change\s+to)\s+(?:this|that|the)\s+(?:one|instead|approach|way|method)"),
        "corr_struct_07": re.compile(r"(?:undo|revert|rollback|cancel|discard|scrap|remove)\s+(?:that|this|the|it)\s"),
        "corr_struct_08": re.compile(r"(?:\w+\s+is\s+better|prefer\s+\w+\s+instead|rather\s+(?:have|use|go)\s+with)\b.*\b(?:than|over|instead\s+of)\b"),
        "corr_struct_09": re.compile(r"(?:there\'?s?\s+an?\s+|(?:i\s+)?made\s+a\s+)(?:error|mistake|bug|issue|problem|typo).*\bfix\b"),
        "corr_struct_10": re.compile(r"\bnot\s+.+,\s*(?:but\s+)?(instead|rather|use|try)\b"),
        "corr_struct_11": re.compile(r"^(?:nope|no)[,.\s]+(that|it|this)\s+(?:\'?s\s+)?(not\s+)?(right|correct|wrong|what\s+i\s+meant)"),
        # === _detect_correction_pattern: Chinese structural patterns ===
        "corr_zh_st_01": re.compile(r"不对[，,]?"),
        "corr_zh_st_02": re.compile(r"错了[，,]?"),
        "corr_zh_st_03": re.compile(r"不是.*而是"),
        "corr_zh_st_04": re.compile(r"应该是.*不是"),
        "corr_zh_st_05": re.compile(r"其实.*决定"),
        "corr_zh_st_06": re.compile(r"我澄清一下"),
        "corr_zh_st_07": re.compile(r"等等.*不是那个意思"),
        "corr_zh_st_08": re.compile(r"回退到.*方案"),
        "corr_zh_st_09": re.compile(r"不是.*用.*才对"),
        # === _detect_correction_pattern: Japanese structural patterns ===
        "corr_ja_st_01": re.compile(r"いや[、,]?"),
        "corr_ja_st_02": re.compile(r"間違って"),
        "corr_ja_st_03": re.compile(r"実は.*に決め"),
        "corr_ja_st_04": re.compile(r"確認しますが"),
        "corr_ja_st_05": re.compile(r"正しくありません"),
        "corr_ja_st_06": re.compile(r"前のアプローチに戻"),
        # === _detect_fact_pattern: Chinese fact patterns ===
        "fact_zh_01": re.compile(r"(.+)是(.+)"),
        "fact_zh_02": re.compile(r"(.+)有(.+)"),
        "fact_zh_03": re.compile(r"(.+)在做(.+)"),
        "fact_zh_04": re.compile(r"(.+)属于(.+)"),
        "fact_zh_05": re.compile(r"(.+)位于(.+)"),
        # === _detect_fact_pattern: Japanese fact patterns ===
        "fact_ja_01": re.compile(r"(.+)(は|が)(.+)(です|である|します|あります)"),
        "fact_ja_02": re.compile(r"(.+)(に)(あります|あります|あります)"),
        "fact_ja_03": re.compile(r"(.+)(の)(要件|バージョン|仕様|制限)"),
        # === _detect_fact_pattern: Tech terms (English Tier 1) ===
        "fact_tech_01": re.compile(r"\b(api|sdk|http|https|tcp|udp|ip|dns|sql|nosql|graphql|rest|grpc|json|xml|csv)\b"),
        "fact_tech_02": re.compile(r"\b(python|javascript|typescript|java|kotlin|go|rust|c\+\+|ruby|php|bash|shell)\b"),
        "fact_tech_03": re.compile(r"\b(postgresql|mysql|mongodb|redis|elasticsearch|dynamodb|sqlite|supabase|firebase)\b"),
        "fact_tech_04": re.compile(r"\b(docker|kubernetes|aws|gcp|azure|linux|nginx|git|github|ci|cd)\b"),
        "fact_tech_05": re.compile(r"\b(llm|gpt|claude|gemini|llama|rag|vector|embedding|pytorch|tensorflow|mcp)\b"),
        "fact_tech_06": re.compile(r"\b(oauth|jwt|encryption|2fa|mfa|rbac|sso|ssl|tls|api\s+key)\b"),
        "fact_tech_07": re.compile(r"\d+(\.\d+)+"),
        "fact_tech_08": re.compile(r"\d{4}[-/]\d{2}"),
        "fact_tech_09": re.compile(r"\b(v?\d+\.\d+)\b"),
        # === _detect_fact_pattern: Tech patterns (English Tier 1 continued) ===
        "fact_tech_pat_01": re.compile(r"(.+)\s+(?:is|are|was|were|runs?|operates?)\s+(?:the\s+)?(?:minimum|required|default|located|hosted|running|deployed|based)"),
        "fact_tech_pat_02": re.compile(r"(.+)\s+(?:runs?|operates?|works?)\s+(?:on|in|at|with|using|via)\s+(.+)"),
        "fact_tech_pat_03": re.compile(r"(.+)\s+(?:supports?|provides?|includes?|contains?|features?)\s+(.+)"),
        "fact_tech_pat_04": re.compile(r"(.+)\s+(?:requires?|needs?|uses?|utilizes?)\s+(.+)"),
        "fact_tech_pat_05": re.compile(r"(?:the|our|my|this)\s+(?:api|database|server|system|service|app|endpoint|port|limit|version|config)\s+.+(?:is|are|=)"),
        "fact_tech_pat_06": re.compile(r"\b\d+\s*(?:employees?|users?|members?|people|teams?|instances?|pods?)\b"),
        "fact_tech_pat_07": re.compile(r"(.+)\s+(?:is|are|has|was|were)\s+(.+)"),
        "fact_tech_pat_08": re.compile(r"(.+)\s+(?:status)\s+\d+\s+(?:is|means|for)\s+(.+)"),
        "fact_tech_pat_09": re.compile(r"(.+)\s+(?:handshake)\s+(?:requires?|needs?|involves?)\s+(.+)"),
        "fact_tech_pat_10": re.compile(r"(.+)\s+(?:share[s]?\s+a)\s+(.+)"),
        "fact_tech_pat_11": re.compile(r"(.+)\s+(?:by\s+default)\b"),
        # === _detect_fact_pattern: Quantifiable facts (Tier 2) ===
        "fact_quant_01": re.compile(r"\b\d+\s*(?:%|percent|mb|gb|tb|ms|sec|min|hour|day|week|month|year|am|pm|jst|utc)\b"),
        "fact_quant_02": re.compile(r"\b\d+[.,]?\d*\s*(?:employees?|users?|members?|people|teams?|servers?|nodes?|pods?)\b"),
        "fact_quant_03": re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b"),
        "fact_quant_04": re.compile(r"\b\d{1,2}(?:am|pm|:)\b"),
        "fact_quant_05": re.compile(r"\b(?:shanghai|beijing|tokyo|london|singapore|seoul|bangalore|berlin)\b"),
        "fact_quant_06": re.compile(r"\bus-east-\d|us-west-\d|ap-southeast-\d|eu-west-\d\b"),
        "fact_quant_07": re.compile(r"\$[\d,]+|\d+\s*k\s*\$|\$\d+k\b"),
        "fact_quant_08": re.compile(r"\bv\d+[\.\w]*\b"),
        "fact_quant_09": re.compile(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b"),
        # === _detect_fact_pattern: Quantifiable patterns (Tier 2 continued) ===
        "fact_quant_pat_01": re.compile(r"(.+)\s+(?:is|are|has|have|was|were)\s+(.+)"),
        "fact_quant_pat_02": re.compile(r"(.+)\s+(?:ends?|starts?|runs?|lasts?)\s+(?:on|at|in|by|every|each)\s*(.+)?"),
        "fact_quant_pat_03": re.compile(r"(?:my|our|the|this)\s+(?:office|work|team|standup|sync|meeting|budget|approval)\s+.+"),
        "fact_quant_pat_04": re.compile(r".*\b(?:hours?|schedule|time|deadline|budget|limit|rate|cost|price|version)\b.*"),
        "fact_quant_pat_05": re.compile(r"^(?:i|we|my|our)\s+.+\s+(?:got|had|went|took|bought|visited|attended|started|finished|completed|moved|joined|left|received|found|built|created)\b"),
        # === _detect_fact_pattern: General declarative (Tier 3) ===
        "fact_general_01": re.compile(r"^(?:we|i|our|my|the|this)\s+.+\s+(?:is|are|has|have|supports?|uses?|runs?|requires?)\s+.+"),
        "fact_general_02": re.compile(r".+\s+(?:live[s]?\s+in|work[s]?\s+(?:for|at|on|with)|based?\s+(?:in|on|at)|located?\s+(?:in|at))\s+.+"),
        "fact_general_03": re.compile(r"^(?:i|we)\s+(?:got|had|went|took|bought|visited|attended|started|finished|completed|moved|joined|left|received|found|built|created|gave|sent|called|met|saw|heard|read|wrote|drove|flew|stayed|lived|worked|studied|played|watched|ate|drank|cooked|cleaned|fixed|repaired|broke|lost|kept|sold|brought|put|set|turned|made|ran|fell|grew|became|felt|thought|knew|believed|decided|chose|preferred|loved|hated|enjoyed|avoided|tried|wanted|needed|learned|discovered|realized|remembered|forgot)\b"),
        # === _detect_relationship_pattern: Role patterns ===
        "rel_role_01": re.compile(r"^(\w+)\s+(?:owns?|leads?|manages?|heads?|runs?)\s+(?:the\s+)?(.+)"),
        "rel_role_02": re.compile(r"(\w+)\s+(?:is|was)\s+(?:our|the|my)\s+(dba|pm|lead|architect|owner|maintainer|contact|expert|specialist)"),
        "rel_role_03": re.compile(r"(\w+)\s+(?:does|handles?|takes?\s+care\s+of|works?\s+on)\s+(.+)"),
        "rel_role_04": re.compile(r"(\w+)\s+(?:reports?\s+to|answers?\s+to)\s+(\w+)"),
        "rel_role_05": re.compile(r"(\w+)\s+(?:is\s+(?:on|in)|belongs?\s+to)\s+(?:the\s+)?(.+)\s+team"),
        "rel_role_06": re.compile(r"(?:ask|contact|reach(?:\s+out)?\s+to)\s+(\w+)\s+(?:about|for|regarding)"),
        # === _detect_relationship_pattern: Dependency/architecture patterns ===
        "rel_dep_01": re.compile(r"(.+)\s+(?:depends?\s+on|relies?\s+on|uses?|imports?|calls?|invokes?)\s+(.+)"),
        "rel_dep_02": re.compile(r"(.+)\s+(?:which|that)\s+(?:routes?\s+to|calls?|triggers?|publishes?\s+events?\s+(?:to|that))\s+(.+)"),
        "rel_dep_03": re.compile(r"(.+)\s+(?:subscribes?\s+to|listens?\s+to|consumes?|reads?\s+from)\s+(.+)"),
        "rel_dep_04": re.compile(r"(.+)\s+(?:sits?\s+between|connects?\s+|bridges?|links?)\s+(.+)"),
        "rel_dep_05": re.compile(r"(.+)\s+(?:triggers?\s+after|runs?\s+after|starts?\s+when|fires?\s+on)\s+(.+)"),
        "rel_dep_06": re.compile(r"(.+)\s+(?:pushes?\s+to|deploys?\s+to|merges?\s+into|integrates?\s+with)\s+(.+)"),
        "rel_dep_07": re.compile(r"(.+)→(.+)"),
        "rel_dep_08": re.compile(r"(.+)\s+->\s*(.+)"),
        # === _detect_relationship_pattern: Chinese role patterns ===
        "rel_zh_role_01": re.compile(r"(.+)(负责|管理|处理|担当)(.+)"),
        "rel_zh_role_02": re.compile(r"(.+)(是|在)(.+)(团队|组)"),
        "rel_zh_role_03": re.compile(r"(我的|我们的)(经理|同事|队友|领导)"),
        "rel_zh_role_04": re.compile(r"(.+)(和|与)(.+)(一起|合作)"),
        # === _detect_relationship_pattern: Japanese role patterns ===
        "rel_ja_role_01": re.compile(r"(.+)(が|は)(.+)(を)?(担当|管理|処理)"),
        "rel_ja_role_02": re.compile(r"(.+)(の)(マネージャー|リード|担当者)"),
        "rel_ja_role_03": re.compile(r"(マネージャー|リード|担当者)(の)(.+)"),
        "rel_ja_role_04": re.compile(r"(.+)(と)(.+)(一緒に|協力)"),
        # === _detect_task_pattern: Structured task patterns ===
        "task_struct_01": re.compile(r"^(i\s+|we\s+|let\'s\s+)?(need|should|must|have|got)\s+to\s+", re.IGNORECASE),
        "task_struct_02": re.compile(r"^(todo|task):\s*", re.IGNORECASE),
        "task_struct_03": re.compile(r"^(please\s+)?(can\s+you\s+)?(help\s+me\s+)?(implement|refactor|fix|add|create|build|write|update)\s+", re.IGNORECASE),
        "task_struct_04": re.compile(r"^(don(\'t)?\s+)?forget\s+to\s+", re.IGNORECASE),
        "task_struct_05": re.compile(r"^(remember\s+to\s+|make sure to\s+)", re.IGNORECASE),
        "task_struct_06": re.compile(r"^(we\'re|we are|i\'m|i am)\s+(going to|planning to|working on)\s+", re.IGNORECASE),
        # === _detect_task_pattern: Workflow/recurring patterns ===
        "task_wf_01": re.compile(
            r"^(always|every\s+time|each\s+time|generally|typically|normally|usually)\s+"
            r"(run|test|review|check|verify|update|backup|deploy|build|lint|format|document|validate)\b",
            re.IGNORECASE,
        ),
        "task_wf_02": re.compile(
            r"\b(run|test|review|check|verify|update|backup|deploy|build|lint|format|document|validate|monitor|analyze|debug|refactor|optimize|migrate|integrate)\b"
            r"\s+(always|every\s+\w+|weekly|monthly|daily|before\s+\w+|after\s+\w+|each\s+\w+|on\s+\w+days?|at\s+\w+)\b",
            re.IGNORECASE,
        ),
        "task_wf_03": re.compile(
            r"^(weekly|monthly|daily|quarterly|annually|yearly)\s+.*\b(retro|meeting|report|sync|standup|review|check|update|deploy|release|backup)\b",
            re.IGNORECASE,
        ),
        "task_wf_04": re.compile(
            r"\b(every\s+(morning|afternoon|evening|night|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|quarter|year))\b"
            r".*\b(i\s+|we\s+)?(check|review|run|test|update|verify|monitor|analyze|send|generate|create|build|deploy)\b",
            re.IGNORECASE,
        ),
        "task_wf_05": re.compile(
            r"^(before|after|when|whenever|once)\s+\w+.*,?\s*(please\s+)?(make sure to|remember to|don\'t forget to|ensure to|verify|check|test|update|run|review)\b",
            re.IGNORECASE,
        ),
        "task_wf_06": re.compile(
            r"\b(before|after)\s+(every|each|any|all)\s+\w+.*(run|test|check|review|update|verify|deploy|backup|build)\b",
            re.IGNORECASE,
        ),
        # === _detect_task_pattern: Habit patterns ===
        "task_habit_01": re.compile(
            r"^(i|we)\s+(always|usually|typically|normally|generally|tend to|like to|try to)\s+"
            r"(check|review|run|test|update|verify|monitor|read|write|build|deploy|start|begin|finish|complete|do)\b",
            re.IGNORECASE,
        ),
        "task_habit_02": re.compile(
            r"^(my|our)\s+(routine|habit|practice|workflow|process|schedule|ritual|rule|policy|guideline|standard|procedure)\s+(is|includes|requires|involves|has)\b",
            re.IGNORECASE,
        ),
        # === _detect_decision_pattern: Strong decision indicators ===
        "dec_strong_01": re.compile(r"\b(decision|decided?|choose|chose|chosen|choice|select|selected|selection|pick|picked)\b", re.IGNORECASE),
        "dec_strong_02": re.compile(r"\b(going\s+with|settled?\s+on|opted?\s+for|landed?\s+on|went\s+with)\b", re.IGNORECASE),
        "dec_strong_03": re.compile(r"\b(adopt|adopting|adopted|embrace|embraced)\b", re.IGNORECASE),
        "dec_strong_04": re.compile(r"\b(agreed?|consensus|unanimous|commit(ted|ting)?|pledge(d|ing)?)\b", re.IGNORECASE),
        "dec_strong_05": re.compile(r"\b(final(ize|ized|ization)|confirm(ed|ation)|approve(d|val)?|sign(ed|ing|off)?)\b", re.IGNORECASE),
        "dec_strong_06": re.compile(r"\b(architecture|approach|strategy|plan|pattern|design|solution|stack|framework|library|tool|tech|technology)\s+(is|will be|should be|has been|we(\'re| are))\b", re.IGNORECASE),
        "dec_strong_07": re.compile(r"\b(use|using|utilizing|leveraging)\s+\w+\s+(instead\s+of|over|rather\s+than)\b", re.IGNORECASE),
        "dec_strong_08": re.compile(r"^use\s+\w+\s+(for|in|as|to)\s+\w+", re.IGNORECASE),
        "dec_strong_09": re.compile(r"\b(we|team|group)\s+(\'ll|will|are|\'re)\s+(use|using|adopt|adopting|go\s+with|move\s+to|switch\s+to|build\s+with|deploy\s+(with|on|to))\b", re.IGNORECASE),
        "dec_strong_10": re.compile(r"\bagreed?\s+to\s+(use|adopt|go\s+with|switch\s+to|implement|build|deploy)\b", re.IGNORECASE),
        "dec_strong_11": re.compile(r"\bdecided?\s+to\s+(use|adopt|go\s+with|switch\s+to|migrate|move|build|deploy|implement)\b", re.IGNORECASE),
        "dec_strong_12": re.compile(r"\b(from\s+now\s+on|going\s+forward|henceforth)\b", re.IGNORECASE),
        "dec_strong_13": re.compile(r"\b(are|is|will be)\s+(mandatory|required|standard|policy|rule|practice|norm|convention|default)\b", re.IGNORECASE),
        # === _detect_decision_pattern: Chinese decision patterns ===
        "dec_zh_01": re.compile(r"我们(用|采用|选了|决定用)"),
        "dec_zh_02": re.compile(r"(决定|确定|选定)"),
        "dec_zh_03": re.compile(r"(方案|策略|架构)"),
        "dec_zh_04": re.compile(r"团队(同意|采用)"),
        # === _detect_decision_pattern: Japanese decision patterns ===
        "dec_ja_01": re.compile(r"(使いましょう|行きましょう|に決めました|選びました)"),
        "dec_ja_02": re.compile(r"(採用|決定|選択)"),
        "dec_ja_03": re.compile(r"(チーム|合意)"),
        # === _detect_sentiment_pattern: Strong emotion patterns ===
        "sent_emotion_01": re.compile(
            r"^(?:i\s+)?(?:\'?m|am|was|feel|feeling|get|getting)\s+(?:so\s+|really\s+|very\s+|super\s+)?"
            r"(?:happy|excited|proud|grateful|thrilled|delighted|relieved|impressed"
            r"|sad|angry|upset|frustrated|annoyed|worried|scared|exhausted|tired|bored"
            r"|disappointed|confused|overwhelmed|stressed)\b",
        ),
        "sent_emotion_02": re.compile(r"\b(?:i\s+)?(?:love|hate|loathe|detest|enjoy|appreciate|dislike|dread)\s+(?:it|this|that|the\s+\w+)"),
        "sent_emotion_03": re.compile(
            r"^(?:this|the)\s+.+\s+is\s+(?:so\s+|really\s+|absolutely\s+|incredibly\s+)?"
            r"(?:great|awesome|amazing|fantastic|wonderful|terrible|awful|horrible|frustrating|annoying|beautiful)",
        ),
        "sent_emotion_04": re.compile(r"\b(amazing|brilliant|outstanding|superb|marvelous|incredible|fantastic)\s+(work|job|effort|team|result|achievement)!"),
        "sent_emotion_05": re.compile(r"^\w+\s+work\b.*\b(?:on|for|with)\b"),
        # === _detect_sentiment_pattern: Adjective indicators ===
        "sent_adj_01": re.compile(r"\b(happy|sad|angry|frustrated|annoyed|excited|tired|exhausted|bored|worried|proud|glad|upset)\b"),
        "sent_adj_02": re.compile(r"\b(great|good|bad|terrible|awful|nice|cool|lovely|horrible|amazing|fantastic|beautiful)\b"),
        # === _detect_sentiment_pattern: Chinese sentiment patterns ===
        "sent_zh_01": re.compile(r"(太|真|好|非常|特别)(棒|好|差|烂|烦|慢|快|美|糟糕|赞|牛)(了|！|!)?"),
        "sent_zh_02": re.compile(r"(很|非常|特别)(开心|难过|生气|满意|失望|焦虑|担心|害怕)"),
        "sent_zh_03": re.compile(r".*(烦|崩溃|心碎|无语|郁闷|不爽|焦虑|太棒)"),
        # === _detect_sentiment_pattern: Japanese sentiment patterns ===
        "sent_ja_01": re.compile(r"(とても|すごく|本当に|めちゃくちゃ)(嬉しい|悲しい|楽しい|つまらない|怖い|不安|心配)"),
        "sent_ja_02": re.compile(r".*(イライラ|ストレス|疲れた|うんざり|残念)"),
        "sent_ja_03": re.compile(r"(素晴らしい|最高|ひどい|最悪|すごい|やばい)"),
        # === _detect_sentiment_pattern: Fact exclusion markers ===
        "sent_fact_01": re.compile(r"\b(api|sdk|http|sql|python|java|docker|kubernetes|aws|redis|nginx)\b"),
        "sent_fact_02": re.compile(r"\b(postgresql|mysql|mongodb|sqlite|supabase|firebase)\b"),
        "sent_fact_03": re.compile(r"\d+(\.\d+)+"),
        "sent_fact_04": re.compile(r"\b(v?\d+\.\d+)\b"),
        "sent_fact_05": re.compile(r"\b(is|are|was|were|has|have)\s+(the\s+)?(?:minimum|required|default|located|hosted|running|deployed|based)\b"),
        "sent_fact_06": re.compile(r"\b(runs?|operates?|works?)\s+(on|in|at|with|using|via)\b"),
        "sent_fact_07": re.compile(r"\b(supports?|provides?|includes?|requires?|needs?|uses?)\s+\b"),
        "sent_fact_08": re.compile(r"\b(server|database|endpoint|port|config|version|limit|service)\b"),
        # === _detect_location_pattern: Fact exclusion indicators ===
        "loc_fact_01": re.compile(r"\b(is|are|was|were|has|have)\s+"),
        "loc_fact_02": re.compile(r"\b(supports?|requires?|provides?|includes?)\s+"),
        "loc_fact_03": re.compile(r"\b(every|always|weekly|monthly|daily)\b"),
        "loc_fact_04": re.compile(r"\b(approval|budget|deadline|schedule|sprint)\b"),
        "loc_fact_05": re.compile(r"\d+(\.\d+)+"),
        "loc_fact_06": re.compile(r"\b(employees?|users?|members?|teams?)\s+\d+"),
        "loc_fact_07": re.compile(r"\b(we\s+have|our\s+\w+)\s+"),
        "loc_fact_08": re.compile(r"\b(runs?|operates?|works?)\s+(on|in|at)\s+"),
        "loc_fact_09": re.compile(r"\b(latency|throughput|performance|uptime)\b"),
        "loc_fact_10": re.compile(r"\b(live[s]?\s+in|work[s]?\s+(for|at|remotely))\b"),
        "loc_fact_11": re.compile(r"\b(stands?|meets?|sync)\s+"),
        "loc_fact_12": re.compile(r"\b(ends?|starts?|begins?)\s+(on|at)\s+"),
        "loc_fact_13": re.compile(r"\b\d+\s*(employees?|users?|ms|sec|min|hour)\b"),
    }

    def __init__(self, noise_filter_mode: str = "strict"):
        """Initialize the pattern analyzer with pre-compiled regex patterns.

        Args:
            noise_filter_mode: "strict" (hard discard noise) or "soft" (downgrade confidence instead of discarding)
        """
        self.noise_filter_mode = noise_filter_mode
        self.message_history = []
        self.task_patterns = {}
        self.preference_patterns = {}
        self.correction_patterns = {}
        self.fact_patterns = {}
        self.relationship_patterns = {}
        self.location_patterns = {}

        self._re_log_prefix = re.compile(r"^\[(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\]")
        self._re_log_timestamp = re.compile(r"^(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)[:\s]")
        self._re_iso_date = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}")
        self._re_short_msg = re.compile(r"[a-z]{3,}")

        # Pre-compiled keyword sets for O(1) lookup (Performance optimization)
        self._feedback_positive_keywords = {
            "对了",
            "正确",
            "好的",
            "成功",
            "完成",
            "不错",
            "great",
            "correct",
            "good",
            "success",
            "done",
        }
        self._feedback_negative_keywords = {
            "不对",
            "错误",
            "重做",
            "失败",
            "不行",
            "重新",
            "wrong",
            "error",
            "redo",
            "fail",
            "no",
            "again",
        }

    def analyze(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze a message for patterns.

        Args:
            message: The message to analyze.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.

        Returns:
            A list of detected patterns.
        """
        patterns = []

        if message is None:
            return patterns

        from carrymem.utils.confirmation import is_confirmation, has_confirmation_context, summarize_context

        confirmation_with_context = has_confirmation_context(context) and is_confirmation(message)

        if self._is_noise(message) and not confirmation_with_context:
            return patterns

        # Append to message history
        self.message_history.append(message)
        if len(self.message_history) > 10:
            self.message_history.pop(0)

        # Detect language (with fallback)
        try:
            language, _ = language_manager.detect_language(message)
        except Exception as e:
            logger.warning(f"Failed to detect language, defaulting to 'en': {e}")
            language = "en"

        # Run all detectors (Phase B Fix #4: task/decision BEFORE fact)
        if execution_context:
            feedback = self._detect_execution_feedback_pattern(message, execution_context, language)
            if feedback:
                feedback["language"] = language
                patterns.append(feedback)

        if has_confirmation_context(context) and is_confirmation(message):
            ai_reply = context.get("ai_reply", "")

            ai_summary = summarize_context(ai_reply)
            patterns.append(
                {
                    "memory_type": "decision",
                    "type": "decision",
                    "content": ai_summary,
                    "confidence": 0.85,
                    "tier": 3,
                    "source_layer": "pattern_analyzer",
                    "reasoning": "User confirmation of AI suggestion",
                    "suggested_action": "store",
                    "context_source": "ai_reply",
                    "original_user_message": message,
                    "language": language,
                }
            )
            return patterns

        for detector_name, detector_func in [
            ("correction", self._detect_correction_pattern),
            ("fact", self._detect_fact_pattern),
            ("decision", self._detect_decision_pattern),
            ("task", self._detect_task_pattern),
            ("preference", self._detect_preference_pattern),
            ("relationship", self._detect_relationship_pattern),
            ("location", self._detect_location_pattern),
            ("sentiment", self._detect_sentiment_pattern),
        ]:
            result = detector_func(message, language)
            if result:
                result["language"] = language
                patterns.append(result)

        return patterns

    def _is_acknowledgment(self, msg: str, msg_lower: str) -> bool:
        """B1: Detect acknowledgment patterns (EN/ZH/JA)."""
        _R = PatternAnalyzer._RE_PATTERNS
        en_keys = [
            "noise_ack_01", "noise_ack_02", "noise_ack_03", "noise_ack_04", "noise_ack_05",
            "noise_ack_06", "noise_ack_07", "noise_ack_08", "noise_ack_09", "noise_ack_10",
            "noise_ack_11", "noise_ack_12", "noise_ack_13", "noise_ack_14", "noise_ack_15",
            "noise_ack_16", "noise_ack_17", "noise_ack_18", "noise_ack_19", "noise_ack_20",
            "noise_ack_21", "noise_ack_22", "noise_ack_23", "noise_ack_24", "noise_ack_25",
            "noise_ack_26",
        ]
        for key in en_keys:
            if _R[key].match(msg_lower):
                return True

        # Extended acknowledgment with context (e.g., "OK, let me check that")
        if _R["noise_ack_ext_01"].match(msg_lower) and len(msg) < 40:
            return True

        # B1-ZH: Chinese acknowledgment patterns
        zh_keys = [
            "noise_zh_ack_01", "noise_zh_ack_02", "noise_zh_ack_03", "noise_zh_ack_04",
            "noise_zh_ack_05", "noise_zh_ack_06", "noise_zh_ack_07", "noise_zh_ack_08",
            "noise_zh_ack_09", "noise_zh_ack_10",
        ]
        for key in zh_keys:
            if _R[key].match(msg):
                return True

        # B1-JA: Japanese acknowledgment patterns
        ja_keys = [
            "noise_ja_ack_01", "noise_ja_ack_02", "noise_ja_ack_03", "noise_ja_ack_04",
            "noise_ja_ack_05", "noise_ja_ack_06", "noise_ja_ack_07", "noise_ja_ack_08",
        ]
        for key in ja_keys:
            if _R[key].match(msg):
                return True

        return False

    def _is_chitchat(self, msg: str, msg_lower: str) -> bool:
        """B2: Detect chitchat/social patterns (EN/ZH/JA)."""
        _R = PatternAnalyzer._RE_PATTERNS
        en_keys = [
            "noise_chat_01", "noise_chat_02", "noise_chat_03", "noise_chat_04", "noise_chat_05",
            "noise_chat_06", "noise_chat_07", "noise_chat_08", "noise_chat_09", "noise_chat_10",
            "noise_chat_11", "noise_chat_12", "noise_chat_13", "noise_chat_14", "noise_chat_15",
            "noise_chat_16",
        ]
        for key in en_keys:
            if _R[key].match(msg_lower):
                if self.noise_filter_mode == "soft":
                    return False
                return True

        # B2-ZH: Chinese chitchat patterns
        zh_keys = [
            "noise_zh_chat_01", "noise_zh_chat_02", "noise_zh_chat_03",
            "noise_zh_chat_04", "noise_zh_chat_05", "noise_zh_chat_06",
        ]
        for key in zh_keys:
            if _R[key].match(msg):
                return True

        # B2-JA: Japanese chitchat patterns
        ja_keys = ["noise_ja_chat_01", "noise_ja_chat_02", "noise_ja_chat_03", "noise_ja_chat_04"]
        for key in ja_keys:
            if _R[key].match(msg):
                return True

        return False

    def _is_technical_noise(self, msg: str, msg_lower: str) -> bool:
        """B3/C5: Detect log prefixes, timestamps, and command noise."""
        _R = PatternAnalyzer._RE_PATTERNS
        if self._re_log_prefix.match(msg):
            return True
        if self._re_log_timestamp.match(msg):
            return True
        # Timestamp-only messages
        if self._re_iso_date.match(msg) and len(msg.split()) <= 4:
            return True

        # Common commands (should be executed, not remembered)
        command_keys = ["noise_cmd_01", "noise_cmd_02", "noise_cmd_03"]
        for key in command_keys:
            if _R[key].match(msg_lower):
                fact_indicator_keys = ["noise_fact_01", "noise_fact_02", "noise_fact_03"]
                if any(_R[k].search(msg_lower) for k in fact_indicator_keys):
                    continue
                return True

        return False

    def _is_question_only(self, msg: str, msg_lower: str) -> bool:
        """B4: Detect pure question/query patterns (EN/ZH/JA)."""
        _R = PatternAnalyzer._RE_PATTERNS
        question_keys = ["noise_q_01", "noise_q_02", "noise_q_03", "noise_q_04", "noise_q_05"]
        if any(_R[p].match(msg_lower) for p in question_keys):
            if len(msg) < 60:
                if self.noise_filter_mode == "soft":
                    return False
                return True

        # B4-ZH: Chinese question patterns
        if _R["noise_zh_q_01"].match(msg) and len(msg) < 60:
            return True

        # B4-JA: Japanese question patterns
        if _R["noise_ja_q_01"].match(msg) and len(msg) < 60:
            return True

        return False

    def _is_instruction(self, msg: str, msg_lower: str) -> bool:
        """B5: Detect instruction/command patterns."""
        _R = PatternAnalyzer._RE_PATTERNS
        instruction_keys = ["noise_instr_01", "noise_instr_02", "noise_instr_03"]
        for key in instruction_keys:
            if _R[key].match(msg_lower) and len(msg) < 60:
                workflow_keys = [
                    "noise_workflow_01", "noise_workflow_02", "noise_workflow_03",
                    "noise_workflow_04", "noise_workflow_05", "noise_workflow_06",
                    "noise_workflow_08",
                ]
                if any(_R[k].search(msg_lower) for k in workflow_keys):
                    continue
                if self.noise_filter_mode == "soft":
                    continue
                return True
        return False

    def _is_adversarial(self, msg_lower: str) -> bool:
        """C5: Detect adversarial/anti-memory patterns."""
        _R = PatternAnalyzer._RE_PATTERNS
        adversarial_keys = [
            "noise_adv_01", "noise_adv_02", "noise_adv_03", "noise_adv_04",
            "noise_adv_05", "noise_adv_06", "noise_adv_07", "noise_adv_08",
        ]
        return any(_R[k].search(msg_lower) for k in adversarial_keys)

    def _is_noise(self, message: str) -> bool:
        """Detect if message is noise (acknowledgment, chitchat, log, command, question).

        Phase A Fix #1: Critical filtering to achieve TN > 0.
        Covers B1 (acknowledgment), B2 (chitchat), B3 (noise), B4 (question), B5 (instruction).

        Args:
            message: The raw message string.

        Returns:
            True if message should be filtered out (not stored), False otherwise.
        """
        if not message or not message.strip():
            return True

        msg = message.strip()
        msg_lower = msg.lower()

        if self._is_acknowledgment(msg, msg_lower):
            return True
        if self._is_chitchat(msg, msg_lower):
            return True
        if self._is_technical_noise(msg, msg_lower):
            return True
        if self._is_question_only(msg, msg_lower):
            return True
        if self._is_instruction(msg, msg_lower):
            return True
        if self._is_adversarial(msg_lower):
            return True

        # Ultra-short messages (< 5 chars likely noise)
        if len(msg) < 5 and not self._re_short_msg.search(msg_lower):
            return True

        return False

    def _detect_execution_feedback_pattern(
        self, message: str, execution_context: Dict[str, Any], language: str
    ) -> Optional[Dict[str, Any]]:
        """Detect execution feedback patterns.

        Args:
            message: The message to analyze.
            execution_context: Execution context containing feedback signals.
            language: The detected language code.

        Returns:
            A dictionary representing the detected feedback pattern, or None if no pattern found.
        """
        user_feedback = execution_context.get("user_feedback", "").lower()

        tool_error = execution_context.get("tool_error", False)
        retry_count = execution_context.get("retry_count", 0)
        execution_time = execution_context.get("execution_time", 0)

        context_position = execution_context.get("context_position", "")

        if self._feedback_positive_keywords & set(user_feedback.split()):
            return {
                "memory_type": "positive_feedback",
                "tier": 2,
                "content": f"Positive feedback: {message}",
                "confidence": 0.85,
                "source": "pattern:execution_feedback",
                "feedback_type": "positive",
                "execution_context": execution_context,
            }

        if self._feedback_negative_keywords & set(user_feedback.split()):
            return {
                "memory_type": "negative_feedback",
                "tier": 3,
                "content": f"Negative feedback: {message}",
                "confidence": 0.85,
                "source": "pattern:execution_feedback",
                "feedback_type": "negative",
                "execution_context": execution_context,
            }

        if tool_error:
            return {
                "memory_type": "tool_error",
                "tier": 3,
                "content": f"Tool error detected: {message}",
                "confidence": 0.90,
                "source": "pattern:execution_feedback",
                "feedback_type": "error",
                "execution_context": execution_context,
            }

        if retry_count > 0:
            return {
                "memory_type": "retry_needed",
                "tier": 3,
                "content": f"Retry needed: {message}",
                "confidence": 0.80,
                "source": "pattern:execution_feedback",
                "feedback_type": "retry",
                "execution_context": execution_context,
            }
        elif execution_time and execution_time > 30:
            return {
                "tier": 3,
                "content": f"Performance issue: {message} (executed in {execution_time}s)",
                "confidence": 0.75,
                "source": "pattern:execution_feedback",
                "feedback_type": "performance",
                "execution_context": execution_context,
            }

        if context_position == "correction_followup":
            return {
                "memory_type": "correction_followup",
                "tier": 3,
                "content": f"Correction followup: {message}",
                "confidence": 0.80,
                "source": "pattern:execution_feedback",
                "feedback_type": "context",
                "execution_context": execution_context,
            }

        if context_position == "confirmation_pending":
            return {
                "memory_type": "confirmation_pending",
                "tier": 2,
                "content": f"Confirmation pending: {message}",
                "confidence": 0.75,
                "source": "pattern:execution_feedback",
                "feedback_type": "context",
                "execution_context": execution_context,
            }

        return None

    def _detect_preference_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect preference patterns.

        Phase B-3 Fix: Enhanced preference detection.
        Target: Recall from 33% to ≥60%.

        Args:
            message: The message to analyze.
            language: The detected language code.

        Returns:
            A preference pattern if detected, None otherwise.
        """
        # Phase B-3: Strong preference patterns (structured)
        _R = PatternAnalyzer._RE_PATTERNS
        strong_pref_keys = [
            "pref_strong_01", "pref_strong_02", "pref_strong_03", "pref_strong_04",
            "pref_strong_05", "pref_strong_06", "pref_strong_07", "pref_strong_08",
        ]

        message_lower = message.lower()

        for key in strong_pref_keys:
            if _R[key].search(message_lower):
                return {
                    "memory_type": "user_preference",
                    "tier": 2,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:preference_strong",
                    "description": "Explicit preference pattern",
                }

        zh_pref_keys = ["pref_zh_01", "pref_zh_02", "pref_zh_03", "pref_zh_04", "pref_zh_05", "pref_zh_06"]
        ja_pref_keys = ["pref_ja_01", "pref_ja_02", "pref_ja_03", "pref_ja_04", "pref_ja_05"]

        for key in zh_pref_keys:
            if language.startswith("zh") and _R[key].search(message):
                return {
                    "memory_type": "user_preference",
                    "tier": 2,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:preference_strong",
                    "description": "Explicit preference pattern",
                }
        for key in ja_pref_keys:
            if language == "ja" and _R[key].search(message):
                return {
                    "memory_type": "user_preference",
                    "tier": 2,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:preference_strong",
                    "description": "Explicit preference pattern",
                }

        preference_keywords = language_manager.get_keywords("user_preference", language)

        if language == "en":
            preference_keywords.extend(
                [
                    "prefer",
                    "preference",
                    "favorite",
                    "favourite",
                    "preferred",
                    "hate",
                    "dislike",
                    "adore",
                    "default",
                    "standard",
                    "convention",
                    "style",
                    "approach",
                    "choice",
                    "habit",
                    "practice",
                    "routine",
                    "ritual",
                    "rule",
                    "policy",
                    "always",
                    "never",
                    "usually",
                    "typically",
                    "normally",
                    "consistently",
                    "over",
                    "instead of",
                    "rather than",
                    "better than",
                    "worse than",
                    "i love",
                    "i like",
                    "i hate",
                    "i enjoy",
                    "i prefer",
                    "i always",
                    "i never",
                    "i usually",
                    "i typically",
                ]
            )
        elif language.startswith("zh"):
            preference_keywords.extend(
                [
                    "爱好",
                    "喜好",
                    "偏爱",
                    "最爱的",
                    "喜欢的",
                    "偏好",
                    "喜欢",
                    "爱",
                    "讨厌",
                    "不喜欢",
                    "习惯",
                    "通常",
                    "总是",
                    "从不",
                    "默认",
                    "标准",
                    "风格",
                    "选择",
                    "觉得",
                    "认为",
                    "看法",
                    "观点",
                    "意见",
                    "倾向于",
                    "倾向于用",
                    "习惯用",
                    "喜欢用",
                    "别用",
                    "不要用",
                    "避免",
                ]
            )
        elif language == "ja":
            preference_keywords.extend(
                [
                    "好き",
                    "嫌い",
                    "好む",
                    "欲しい",
                    "嫌う",
                    "好きです",
                    "好きではありません",
                    "いいです",
                    "ほしい",
                    "いつも",
                    "常に",
                    "通常",
                    "習慣",
                    "デフォルト",
                    "標準",
                    "スタイル",
                    "選択",
                    "好み",
                    "傾向",
                    "使いたい",
                    "使ってください",
                    "お願いします",
                    "避けて",
                    "使わず",
                ]
            )

        message_lower = message.lower()
        for keyword in preference_keywords:
            if keyword in message_lower:
                preference_content = message

                preference_hash = hash(preference_content)
                if preference_hash in self.preference_patterns:
                    self.preference_patterns[preference_hash] += 1
                    if self.preference_patterns[preference_hash] >= 2:
                        return {
                            "memory_type": "user_preference",
                            "tier": 2,
                            "content": preference_content,
                            "confidence": 0.8,
                            "source": "pattern:preference_repeat",
                            "description": "Repeated preference pattern",
                        }
                else:
                    self.preference_patterns[preference_hash] = 1
                    return {
                        "memory_type": "user_preference",
                        "tier": 2,
                        "content": preference_content,
                        "confidence": 0.6,
                        "source": "pattern:preference",
                        "description": "Preference pattern",
                    }

        return None

    def _detect_correction_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect correction patterns.

        V4-02 Enhanced: Comprehensive correction detection with 3-tier strategy.
        Tier 1: Explicit correction markers (highest confidence)
        Tier 2: Structural patterns (grammar-based)
        Tier 3: Keyword-based (broadest coverage)

        Args:
            message: The message to analyze.
            language: The detected language code.

        Returns:
            A correction pattern if detected, None otherwise.
        """
        _R = PatternAnalyzer._RE_PATTERNS
        message_lower = message.lower()

        # === TIER 1: Explicit correction markers (confidence 0.85) ===
        explicit_keys = [
            "corr_explicit_01", "corr_explicit_02", "corr_explicit_03", "corr_explicit_04",
            "corr_explicit_05", "corr_explicit_06", "corr_explicit_07", "corr_explicit_08",
            "corr_explicit_09",
        ]

        zh_explicit_keys = [
            "corr_zh_ex_01", "corr_zh_ex_02", "corr_zh_ex_03", "corr_zh_ex_04",
            "corr_zh_ex_05", "corr_zh_ex_06", "corr_zh_ex_07", "corr_zh_ex_08",
            "corr_zh_ex_09", "corr_zh_ex_10", "corr_zh_ex_11", "corr_zh_ex_12",
            "corr_zh_ex_13", "corr_zh_ex_14", "corr_zh_ex_15", "corr_zh_ex_16",
        ]

        ja_explicit_keys = [
            "corr_ja_ex_01", "corr_ja_ex_02", "corr_ja_ex_03", "corr_ja_ex_04",
            "corr_ja_ex_05", "corr_ja_ex_06", "corr_ja_ex_07", "corr_ja_ex_08",
            "corr_ja_ex_09", "corr_ja_ex_10",
        ]

        for key in explicit_keys:
            if _R[key].search(message_lower):
                return self._build_correction_result(message, language, "pattern:correction_explicit", 0.85)
        for key in zh_explicit_keys:
            if language.startswith("zh") and _R[key].search(message):
                return self._build_correction_result(message, language, "pattern:correction_explicit", 0.85)
        for key in ja_explicit_keys:
            if language == "ja" and _R[key].search(message):
                return self._build_correction_result(message, language, "pattern:correction_explicit", 0.85)

        # === TIER 2: Structural patterns (confidence 0.75) ===
        struct_keys = [
            "corr_struct_01", "corr_struct_02", "corr_struct_03", "corr_struct_04",
            "corr_struct_05", "corr_struct_06", "corr_struct_07", "corr_struct_08",
            "corr_struct_09", "corr_struct_10", "corr_struct_11",
        ]
        for key in struct_keys:
            if _R[key].search(message_lower):
                return self._build_correction_result(message, language, "pattern:correction_structural", 0.75)

        zh_struct_keys = [
            "corr_zh_st_01", "corr_zh_st_02", "corr_zh_st_03", "corr_zh_st_04",
            "corr_zh_st_05", "corr_zh_st_06", "corr_zh_st_07", "corr_zh_st_08",
            "corr_zh_st_09",
        ]
        ja_struct_keys = [
            "corr_ja_st_01", "corr_ja_st_02", "corr_ja_st_03", "corr_ja_st_04",
            "corr_ja_st_05", "corr_ja_st_06",
        ]

        for key in zh_struct_keys:
            if language.startswith("zh") and _R[key].search(message):
                return self._build_correction_result(message, language, "pattern:correction_structural", 0.75)
        for key in ja_struct_keys:
            if language == "ja" and _R[key].search(message):
                return self._build_correction_result(message, language, "pattern:correction_structural", 0.75)

        # === TIER 3: Keyword-based detection (confidence 0.65) ===
        strong_correction_keywords = [
            "wrong",
            "incorrect",
            "mistake",
            "error",
            "fix it",
            "bug in",
            "change our",
            "change strategy",
            "different approach",
            "should be",
            "needs to be",
            "actually is",
            "supposed to be",
        ]
        if any(kw in message_lower for kw in strong_correction_keywords):
            return self._build_correction_result(message, language, "pattern:correction_keyword", 0.65)

        return None

    def _build_correction_result(self, message: str, language: str, source: str, confidence: float) -> Dict[str, Any]:
        """Build a standardized correction result."""
        correction_content = message

        if len(self.message_history) >= 2:
            correction_content = message

        correction_hash = hash(correction_content)
        if correction_hash in self.correction_patterns:
            self.correction_patterns[correction_hash] += 1
        else:
            self.correction_patterns[correction_hash] = 1

        return {
            "memory_type": "correction",
            "tier": 3,
            "content": correction_content,
            "confidence": confidence,
            "source": source,
            "description": "Correction pattern",
        }

    def _detect_fact_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect fact declaration patterns.

        V4-04 Enhanced: Balanced 3-tier fact detection.
        Tier 1: Tech terms + structural patterns → conf 0.8
        Tier 2: Quantifiable facts (numbers/dates/locations) → conf 0.7
        Tier 3: General declarative statements → conf 0.6
        """
        _R = PatternAnalyzer._RE_PATTERNS
        if len(message.strip()) < 10:
            return None

        msg_lower = message.lower().strip()

        noise_indicators = [
            "ok",
            "yeah",
            "sure",
            "thanks",
            "nice",
            "cool",
            "great",
            "got it",
            "sounds good",
            "alright",
            "understood",
            "noted",
            "interesting",
            "hmm",
            "oh really",
            "pretty",
        ]
        if any(indicator in msg_lower for indicator in noise_indicators):
            return None

        if language.startswith("zh"):
            fact_zh_keys = ["fact_zh_01", "fact_zh_02", "fact_zh_03", "fact_zh_04", "fact_zh_05"]
            for key in fact_zh_keys:
                if _R[key].search(message):
                    return self._build_fact_result(message)
        elif language == "ja":
            fact_ja_keys = ["fact_ja_01", "fact_ja_02", "fact_ja_03"]
            for key in fact_ja_keys:
                if _R[key].search(message):
                    return self._build_fact_result(message)
        else:
            # === TIER 1: Strong technical facts (conf 0.8) ===
            tech_term_keys = [
                "fact_tech_01", "fact_tech_02", "fact_tech_03", "fact_tech_04",
                "fact_tech_05", "fact_tech_06", "fact_tech_07", "fact_tech_08",
                "fact_tech_09",
            ]
            has_tech = any(_R[t].search(msg_lower) for t in tech_term_keys)

            if has_tech:
                tech_pat_keys = [
                    "fact_tech_pat_01", "fact_tech_pat_02", "fact_tech_pat_03",
                    "fact_tech_pat_04", "fact_tech_pat_05", "fact_tech_pat_06",
                    "fact_tech_pat_07", "fact_tech_pat_08", "fact_tech_pat_09",
                    "fact_tech_pat_10", "fact_tech_pat_11",
                ]
                for key in tech_pat_keys:
                    if _R[key].search(msg_lower):
                        return self._build_fact_result(message, 0.8, "pattern:fact_tech")

                if has_tech:
                    return self._build_fact_result(message, 0.75, "pattern:fact_tech_fallback")

            # === TIER 2: Quantifiable facts (conf 0.7) ===
            quant_ind_keys = [
                "fact_quant_01", "fact_quant_02", "fact_quant_03", "fact_quant_04",
                "fact_quant_05", "fact_quant_06", "fact_quant_07", "fact_quant_08",
                "fact_quant_09",
            ]
            has_quant = any(_R[q].search(msg_lower) for q in quant_ind_keys)

            if has_quant:
                quant_pat_keys = [
                    "fact_quant_pat_01", "fact_quant_pat_02", "fact_quant_pat_03",
                    "fact_quant_pat_04", "fact_quant_pat_05",
                ]
                for key in quant_pat_keys:
                    if _R[key].search(msg_lower):
                        return self._build_fact_result(message, 0.7, "pattern:fact_quant")

            # === TIER 3: General declarative (conf 0.6), only longer messages ===
            if len(msg_lower) > 25:
                general_keys = ["fact_general_01", "fact_general_02", "fact_general_03"]
                for key in general_keys:
                    if _R[key].search(msg_lower):
                        return self._build_fact_result(message, 0.6, "pattern:fact_general")

        return None

    def _build_fact_result(self, message: str, confidence: float = 0.7, source: str = "pattern:fact") -> Dict[str, Any]:
        """Build a standardized fact result."""
        fact_content = message
        fact_hash = hash(fact_content)
        if fact_hash in self.fact_patterns:
            self.fact_patterns[fact_hash] += 1
            if self.fact_patterns[fact_hash] >= 2:
                return {
                    "memory_type": "fact_declaration",
                    "tier": 4,
                    "content": fact_content,
                    "confidence": 0.8,
                    "source": "pattern:fact_repeat",
                    "description": "Repeated fact pattern",
                }
        else:
            self.fact_patterns[fact_hash] = 1
        return {
            "memory_type": "fact_declaration",
            "tier": 4,
            "content": fact_content,
            "confidence": confidence,
            "source": source,
            "description": "Fact declaration pattern",
        }

    def _detect_relationship_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect relationship patterns.

        V4-05 Enhanced: 3-tier relationship detection.
        Tier 1: Structural role/dependency patterns (conf 0.8)
        Tier 2: Keyword-based (original, conf 0.7)
        """
        _R = PatternAnalyzer._RE_PATTERNS
        msg_lower = message.lower().strip()

        min_len = 12
        if language.startswith("zh") or language == "ja":
            min_len = 6
        if len(msg_lower) < min_len:
            return None

        # === TIER 1: Structural patterns ===
        if not language.startswith("zh") and language != "ja":
            # Role patterns (who does what / who is what)
            role_keys = [
                "rel_role_01", "rel_role_02", "rel_role_03", "rel_role_04",
                "rel_role_05", "rel_role_06",
            ]
            for key in role_keys:
                if _R[key].search(msg_lower):
                    return self._build_rel_result(message)

            # Dependency/architecture patterns
            dep_keys = [
                "rel_dep_01", "rel_dep_02", "rel_dep_03", "rel_dep_04",
                "rel_dep_05", "rel_dep_06", "rel_dep_07", "rel_dep_08",
            ]
            for key in dep_keys:
                if _R[key].search(msg_lower):
                    return self._build_rel_result(message)

        zh_role_keys = ["rel_zh_role_01", "rel_zh_role_02", "rel_zh_role_03", "rel_zh_role_04"]
        ja_role_keys = ["rel_ja_role_01", "rel_ja_role_02", "rel_ja_role_03", "rel_ja_role_04"]

        for key in zh_role_keys:
            if language.startswith("zh") and _R[key].search(message):
                return self._build_rel_result(message)
        for key in ja_role_keys:
            if language == "ja" and _R[key].search(message):
                return self._build_rel_result(message)

        # === TIER 2: Keyword-based (original) ===
        relationship_keywords = language_manager.get_keywords("relationship", language)
        for keyword in relationship_keywords:
            if keyword in msg_lower:
                return self._build_rel_result(message)

        return None

    def _build_rel_result(self, message: str) -> Dict[str, Any]:
        """Build a standardized relationship result."""
        rel_hash = hash(message)
        if rel_hash in self.relationship_patterns:
            self.relationship_patterns[rel_hash] += 1
            if self.relationship_patterns[rel_hash] >= 2:
                return {
                    "memory_type": "relationship",
                    "tier": 4,
                    "content": message,
                    "confidence": 0.8,
                    "source": "pattern:relationship_repeat",
                    "description": "Repeated relationship pattern",
                }
        else:
            self.relationship_patterns[rel_hash] = 1
        return {
            "memory_type": "relationship",
            "tier": 4,
            "content": message,
            "confidence": 0.75,
            "source": "pattern:relationship",
            "description": "Relationship pattern",
        }

    def _detect_task_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect task patterns.

        Phase A Fix #3: Enhanced with technical action verbs and structured patterns.
        Target: F1 from 0% to ≥50%.

        Args:
            message: The message to analyze.
            language: The detected language code.

        Returns:
            A task pattern if detected, None otherwise.
        """
        _R = PatternAnalyzer._RE_PATTERNS
        message_lower = message.lower()
        decision_guard = re.compile(
            r"\b(decided?|agreed?|chose|chosen|going\s+with|settled?\s+on|opted?\s+for|"
            r"we\s+('ll|will)\s+(use|adopt|go\s+with|move\s+to|switch\s+to))\b",
            re.IGNORECASE,
        )
        if decision_guard.search(message_lower):
            return None

        task_keywords = language_manager.get_keywords("task_pattern", language)

        if language == "en":
            # Phase A Fix #3: Expanded technical action verbs
            task_keywords.extend(
                [
                    # Core development actions
                    "implement",
                    "refactor",
                    "optimize",
                    "fix",
                    "debug",
                    "resolve",
                    "add",
                    "create",
                    "build",
                    "make",
                    "generate",
                    "develop",
                    "write",
                    "update",
                    "upgrade",
                    "migrate",
                    "integrate",
                    "deploy",
                    "release",
                    # Planning & management
                    "plan",
                    "design",
                    "architect",
                    "research",
                    "investigate",
                    "analyze",
                    "review",
                    "test",
                    "validate",
                    "verify",
                    "check",
                    "monitor",
                    # Need/should (but only in task context - handled by patterns below)
                    "need to",
                    "should",
                    "must",
                    "have to",
                    "require",
                    "going to",
                    # Common task markers
                    "todo",
                    "task",
                    "action item",
                    "follow up",
                    "next step",
                ]
            )
        elif language.startswith("zh"):
            task_keywords.extend(
                [
                    "实现",
                    "重构",
                    "优化",
                    "修复",
                    "调试",
                    "解决",
                    "添加",
                    "创建",
                    "构建",
                    "制作",
                    "生成",
                    "开发",
                    "编写",
                    "更新",
                    "升级",
                    "迁移",
                    "集成",
                    "部署",
                    "发布",
                    "计划",
                    "设计",
                    "研究",
                    "调查",
                    "分析",
                    "审查",
                    "测试",
                    "验证",
                    "检查",
                    "监控",
                    "需要",
                    "应该",
                    "必须",
                    "要",
                    "待办",
                    "下一步",
                    "每次",
                    "每周",
                    "每天",
                    "定期",
                    "例行",
                    "站会",
                    "冒烟测试",
                    "代码审查",
                ]
            )
        elif language == "ja":
            task_keywords.extend(
                [
                    "実装",
                    "リファクタ",
                    "最適化",
                    "修正",
                    "デバッグ",
                    "解決",
                    "追加",
                    "作成",
                    "構築",
                    "生成",
                    "開発",
                    "記述",
                    "更新",
                    "アップグレード",
                    "移行",
                    "統合",
                    "デプロイ",
                    "リリース",
                    "計画",
                    "設計",
                    "研究",
                    "調査",
                    "分析",
                    "レビュー",
                    "テスト",
                    "検証",
                    "確認",
                    "監視",
                    "必要",
                    "すべき",
                    "必須",
                    "やるべき",
                    "次のステップ",
                    "毎回",
                    "毎週",
                    "毎日",
                    "定期的",
                    "ルーティン",
                    "スタンドアップ",
                    "スモークテスト",
                    "コードレビュー",
                ]
            )

        message_lower = message.lower()

        # Phase B-1 Fix: Comprehensive task pattern detection
        # Covers: workflow rules, recurring tasks, personal habits, procedures

        # 1. Structured task patterns (command/planning style)
        struct_task_keys = [
            "task_struct_01", "task_struct_02", "task_struct_03",
            "task_struct_04", "task_struct_05", "task_struct_06",
        ]

        for key in struct_task_keys:
            if _R[key].match(message_lower):
                return {
                    "memory_type": "task_pattern",
                    "tier": 3,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:task_structured",
                    "description": "Structured task pattern",
                }

        # 2. Workflow rules & recurring patterns (NEW - Phase B-1)
        # Matches: "Always run linting", "Test after every deploy", "Update dependencies weekly"
        workflow_keys = [
            "task_wf_01", "task_wf_02", "task_wf_03", "task_wf_04",
            "task_wf_05", "task_wf_06",
        ]

        for key in workflow_keys:
            if _R[key].search(message_lower):
                return {
                    "memory_type": "task_pattern",
                    "tier": 3,
                    "content": message,
                    "confidence": 0.72,
                    "source": "pattern:task_workflow",
                    "description": "Workflow/recurring task pattern",
                }

        # 3. Personal habit patterns (NEW - Phase B-1)
        # Matches: "I check the dashboard every morning", "We do code review on Fridays"
        habit_keys = ["task_habit_01", "task_habit_02"]

        for key in habit_keys:
            if _R[key].search(message_lower):
                return {
                    "memory_type": "task_pattern",
                    "tier": 3,
                    "content": message,
                    "confidence": 0.70,
                    "source": "pattern:task_habit",
                    "description": "Personal habit/routine pattern",
                }

        for keyword in task_keywords:
            if keyword in message_lower:
                task_content = message

                task_hash = hash(task_content)
                if task_hash in self.task_patterns:
                    self.task_patterns[task_hash] += 1
                    if self.task_patterns[task_hash] >= 2:
                        return {
                            "memory_type": "task_pattern",
                            "tier": 3,
                            "content": task_content,
                            "confidence": 0.8,
                            "source": "pattern:task_repeat",
                            "description": "Repeated task pattern",
                        }
                else:
                    self.task_patterns[task_hash] = 1
                    return {
                        "memory_type": "task_pattern",
                        "tier": 3,
                        "content": task_content,
                        "confidence": 0.6,
                        "source": "pattern:task",
                        "description": "Task pattern",
                    }

        return None

    def _detect_decision_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect decision patterns.

        Phase B-2 Fix: Complete rewrite of decision detection.
        Target: Recall from 10% to ≥50%.

        Args:
            message: The message to analyze.
            language: The detected language code.

        Returns:
            A decision pattern if detected, None otherwise.
        """
        _R = PatternAnalyzer._RE_PATTERNS
        # Phase B-2: Strong decision indicators (NOT noise words!)
        strong_dec_keys = [
            "dec_strong_01", "dec_strong_02", "dec_strong_03", "dec_strong_04",
            "dec_strong_05", "dec_strong_06", "dec_strong_07", "dec_strong_08",
            "dec_strong_09", "dec_strong_10", "dec_strong_11", "dec_strong_12",
            "dec_strong_13",
        ]

        message_lower = message.lower()

        for key in strong_dec_keys:
            if _R[key].search(message_lower):
                return {
                    "memory_type": "decision",
                    "tier": 2,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:decision_strong",
                    "description": "Explicit decision pattern",
                }

        zh_dec_keys = ["dec_zh_01", "dec_zh_02", "dec_zh_03", "dec_zh_04"]
        ja_dec_keys = ["dec_ja_01", "dec_ja_02", "dec_ja_03"]

        for key in zh_dec_keys:
            if language.startswith("zh") and _R[key].search(message):
                return {
                    "memory_type": "decision",
                    "tier": 2,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:decision_strong",
                    "description": "Explicit decision pattern",
                }
        for key in ja_dec_keys:
            if language == "ja" and _R[key].search(message):
                return {
                    "memory_type": "decision",
                    "tier": 2,
                    "content": message,
                    "confidence": 0.75,
                    "source": "pattern:decision_strong",
                    "description": "Explicit decision pattern",
                }

        # Weaker decision indicators (require context length > 15)
        weak_decision_keywords = [
            "let's use",
            "let's go with",
            "let's adopt",
            "let's choose",
            "we should use",
            "we could use",
            "we might use",
            "i think we should",
            "i propose we",
            "i suggest we",
            "best option is",
            "better to go",
            "makes sense to",
            "our approach",
            "the plan is",
            "the strategy is",
        ]

        if len(message.strip()) > 15:
            for keyword in weak_decision_keywords:
                if keyword in message_lower:
                    return {
                        "memory_type": "decision",
                        "tier": 3,
                        "content": message,
                        "confidence": 0.65,
                        "source": "pattern:decision_weak",
                        "description": "Weak decision pattern",
                    }

        # Legacy support (language-specific keywords - filtered for noise)
        decision_keywords = language_manager.get_keywords("decision", language)

        if language == "en":
            decision_keywords.extend(
                [
                    "decide",
                    "determine",
                    "conclude",
                    "resolve",
                    "finalize",
                    "preference",
                    "verdict",
                    "ruling",
                    "judgment",
                ]
            )
        elif language.startswith("zh"):
            decision_keywords.extend(
                [
                    "决定",
                    "选定",
                    "确定",
                    "采用",
                    "选用",
                    "敲定",
                    "方案",
                    "策略",
                    "架构",
                    "共识",
                    "一致同意",
                    "我们用",
                    "选了",
                    "就用",
                ]
            )
        elif language == "ja":
            decision_keywords.extend(
                [
                    "決める",
                    "決定",
                    "選ぶ",
                    "選択",
                    "確認",
                    "合意",
                    "使いましょう",
                    "行きましょう",
                    "に決めました",
                    "選びました",
                    "採用",
                    "採用しました",
                ]
            )

        message_lower = message.lower()
        for keyword in decision_keywords:
            if keyword in message_lower:
                if len(self.message_history) >= 2:
                    if language.startswith("zh"):
                        return {
                            "memory_type": "decision",
                            "tier": 3,
                            "content": message,
                            "confidence": 0.7,
                            "source": "pattern:decision",
                            "description": "Decision pattern",
                        }
                    else:
                        return {
                            "memory_type": "decision",
                            "tier": 3,
                            "content": message,
                            "confidence": 0.7,
                            "source": "pattern:decision",
                            "description": "Decision pattern",
                        }
                else:
                    if language.startswith("zh"):
                        return {
                            "memory_type": "decision",
                            "tier": 3,
                            "content": message,
                            "confidence": 0.6,
                            "source": "pattern:decision",
                            "description": "Decision pattern",
                        }
                    else:
                        return {
                            "memory_type": "decision",
                            "tier": 3,
                            "content": message,
                            "confidence": 0.6,
                            "source": "pattern:decision",
                            "description": "Decision pattern",
                        }

        return None

    def _detect_sentiment_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect sentiment patterns.

        V4-05 Enhanced: Structural + keyword hybrid detection.
        Tier 1: Strong emotion patterns with intensifiers (conf 0.8)
        Tier 2: Keyword-based (narrowed per P0-B, conf 0.65)
        """
        _R = PatternAnalyzer._RE_PATTERNS
        msg_lower = message.lower().strip()

        min_len = 10
        if language.startswith("zh") or language == "ja":
            min_len = 5
        if len(msg_lower) < min_len:
            return None

        # === TIER 1: Structural patterns ===
        if not language.startswith("zh") and language != "ja":
            # Emotion + subject patterns (strong signal)
            emotion_keys = ["sent_emotion_01", "sent_emotion_02", "sent_emotion_03", "sent_emotion_04", "sent_emotion_05"]
            for key in emotion_keys:
                if _R[key].search(msg_lower):
                    return self._build_sent_result(message, 0.8)

            # Intensifier + adjective patterns
            if any(
                intensifier in msg_lower
                for intensifier in [
                    "so ",
                    "really ",
                    "very ",
                    "super ",
                    "absolutely ",
                    "extremely ",
                ]
            ):
                adj_keys = ["sent_adj_01", "sent_adj_02"]
                if any(_R[k].search(msg_lower) for k in adj_keys):
                    return self._build_sent_result(message, 0.75)

        # ZH sentiment structural patterns
        if language.startswith("zh"):
            zh_sent_keys = ["sent_zh_01", "sent_zh_02", "sent_zh_03"]
            for key in zh_sent_keys:
                if _R[key].search(message):
                    return self._build_sent_result(message, 0.8)

        # JA sentiment structural patterns
        if language == "ja":
            ja_sent_keys = ["sent_ja_01", "sent_ja_02", "sent_ja_03"]
            for key in ja_sent_keys:
                if _R[key].search(message):
                    return self._build_sent_result(message, 0.8)

        # === TIER 2: Keyword-based (narrowed per P0-B) ===
        # Removed descriptive adjectives that match factual statements:
        #   slow, fast, easy, hard, beautiful, ugly, great, good, bad
        # These are too broad and cause factual statements to be misclassified.
        # Now requires personal pronoun context for isolated emotion words.
        sentiment_keywords = language_manager.get_keywords("sentiment_marker", language)
        if language == "en":
            sentiment_keywords.extend(
                [
                    "love",
                    "hate",
                    "dislike",
                    "enjoy",
                    "happy",
                    "sad",
                    "angry",
                    "excited",
                    "frustrated",
                    "upset",
                    "annoyed",
                    "bored",
                    "tired",
                    "exhausted",
                    "inspired",
                    "proud",
                    "confident",
                    "worried",
                    "scared",
                    "relaxed",
                    "loathe",
                    "detest",
                    "disappoint",
                    "delighted",
                    "thrilled",
                    "depressed",
                    "irritated",
                    "panic",
                    "frighten",
                    "motivated",
                    "too slow",
                    "too fast",
                    "too hard",
                    "too easy",
                    "painful",
                    "annoying",
                    "clunky",
                    "laggy",
                    "awesome",
                    "fantastic",
                    "wonderful",
                    "amazing",
                    "terrible",
                    "horrible",
                    "awful",
                    "brilliant",
                    "superb",
                    "outstanding",
                ]
            )
        elif language.startswith("zh"):
            sentiment_keywords.extend(
                [
                    "棒",
                    "很棒",
                    "真好",
                    "太好了",
                    "优秀",
                    "惊人",
                    "可怕",
                    "糟糕",
                    "恶心",
                    "恐怖",
                    "喜欢",
                    "讨厌",
                    "烦",
                    "崩溃",
                    "心碎",
                    "开心",
                    "难过",
                    "生气",
                    "激动",
                    "不满",
                    "超赞",
                    "无语",
                    "无语了",
                    "太赞了",
                    "绝了",
                    "牛",
                    "牛逼",
                    "累",
                    "疲惫",
                    "无聊",
                    "焦虑",
                    "担心",
                    "害怕",
                    "自豪",
                    "自信",
                    "放松",
                    "失望",
                    "郁闷",
                    "不爽",
                    "太慢",
                    "太烦",
                    "很担心",
                    "棒极了",
                ]
            )
        elif language == "ja":
            sentiment_keywords.extend(
                [
                    "嬉しい",
                    "悲しい",
                    "怒っている",
                    "興奮",
                    "失望",
                    "満足",
                    "素晴らしい",
                    "最高",
                    "ひどい",
                    "最悪",
                    "好き",
                    "嫌い",
                    "楽しい",
                    "面白い",
                    "つまらない",
                    "感動",
                    "驚き",
                    "不安",
                    "心配",
                    "怖い",
                    "イライラ",
                    "ストレス",
                    "疲れた",
                    "うんざり",
                    "すごい",
                    "やばい",
                    "素敵",
                    "残念",
                    "遅い",
                    "不便",
                    "迷惑",
                ]
            )

        for keyword in sentiment_keywords:
            if keyword in msg_lower:
                # P0-B: Fact exclusion - if text contains factual markers, skip sentiment
                sent_fact_keys = [
                    "sent_fact_01", "sent_fact_02", "sent_fact_03", "sent_fact_04",
                    "sent_fact_05", "sent_fact_06", "sent_fact_07", "sent_fact_08",
                ]
                if any(_R[k].search(msg_lower) for k in sent_fact_keys):
                    continue
                return self._build_sent_result(message, 0.65)

        return None

    def _build_sent_result(self, message: str, confidence: float = 0.7) -> Dict[str, Any]:
        """Build a standardized sentiment result."""
        return {
            "memory_type": "sentiment_marker",
            "tier": 3,
            "content": message,
            "confidence": confidence,
            "source": "pattern:sentiment",
            "description": "Sentiment pattern",
        }

    def _detect_location_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect location patterns.

        V4-08: Restricted to pure location info, not facts containing locations.

        Args:
            message: The message to analyze.
            language: The detected language code.

        Returns:
            A location pattern if detected, None otherwise.
        """
        _R = PatternAnalyzer._RE_PATTERNS
        msg_lower = message.lower()

        # V4-08: Skip if this looks like a fact/decision/task (those take priority)
        # Location should only match pure location statements like "I'm at the office"
        loc_fact_keys = [
            "loc_fact_01", "loc_fact_02", "loc_fact_03", "loc_fact_04",
            "loc_fact_05", "loc_fact_06", "loc_fact_07", "loc_fact_08",
            "loc_fact_09", "loc_fact_10", "loc_fact_11", "loc_fact_12",
            "loc_fact_13",
        ]
        if any(_R[k].search(msg_lower) for k in loc_fact_keys):
            return None

        # Location keywords
        location_keywords = {
            "en": ["at", "in", "on", "located", "place", "location", "address"],
            "zh-cn": ["在", "位于", "地址", "地方", "位置"],
        }

        keywords = location_keywords.get(language, location_keywords.get("en", []))

        for keyword in keywords:
            if keyword in msg_lower:
                # Check for common location names
                common_locations = {
                    "en": [
                        "park",
                        "station",
                        "airport",
                        "hotel",
                        "restaurant",
                        "office",
                        "building",
                        "street",
                        "avenue",
                        "road",
                    ],
                    "zh-cn": [
                        "公园",
                        "车站",
                        "机场",
                        "酒店",
                        "餐厅",
                        "办公室",
                        "大楼",
                        "街道",
                        "大道",
                        "路",
                    ],
                }

                location_terms = common_locations.get(language, common_locations.get("en", []))
                for term in location_terms:
                    if term in msg_lower:
                        location_content = message
                        location_hash = hash(location_content)
                        if location_hash in self.location_patterns:
                            self.location_patterns[location_hash] += 1
                        else:
                            self.location_patterns[location_hash] = 1

                        return {
                            "memory_type": "location",
                            "tier": 3,
                            "content": location_content,
                            "confidence": 0.7,
                            "source": "pattern:location",
                            "description": "Location pattern",
                        }

        return None

    def clear_history(self):
        """Clear the message history."""
        self.message_history = []
        self.task_patterns = {}
        self.preference_patterns = {}
        self.correction_patterns = {}
        self.fact_patterns = {}
        self.relationship_patterns = {}
        self.location_patterns = {}
