import re
from typing import Dict, List, Optional, Tuple

from carrymem.utils.logger import logger

try:
    from langdetect import detect, LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False
    LangDetectException = Exception

try:
    import pycld2 as cld2
    _CLD2_AVAILABLE = True
except ImportError:
    _CLD2_AVAILABLE = False

_STOP_WORDS = frozenset({
    "what", "is", "the", "did", "does", "do", "a", "an", "how",
    "who", "which", "when", "where", "why", "can", "could", "would",
    "should", "team", "user", "use", "used", "using", "for", "of",
    "in", "on", "to", "and", "or", "that", "this", "it", "be", "are",
    "was", "were", "been", "has", "have", "had", "will", "would",
})


def has_cjk(text: str) -> bool:
    """Check if text contains CJK characters.

    Covers CJK Unified Ideographs (U+4E00–U+9FFF),
    CJK Unified Ideographs Extension A (U+3400–U+4DBF),
    Hiragana (U+3040–U+309F), and Katakana (U+30A0–U+30FF).
    """
    return any(
        "\u4e00" <= char <= "\u9fff"
        or "\u3400" <= char <= "\u4dbf"
        or "\u3040" <= char <= "\u309f"
        or "\u30a0" <= char <= "\u30ff"
        for char in text
    )


class LanguageManager:
    """Language detection and management for multi-language support."""
    
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'zh-cn': 'Chinese (Simplified)',
        'zh-tw': 'Chinese (Traditional)',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ja': 'Japanese',
        'ko': 'Korean',
        'ru': 'Russian',
        'ar': 'Arabic'
    }
    
    MULTI_LANG_KEYWORDS = {
        'user_preference': {
            'en': ['like', 'prefer', 'love', 'hate', 'want', 'dislike'],
            'zh-cn': ['喜欢', '偏好', '希望', '想要', '讨厌', '不喜欢', '比较好', '用比较', '选用', '推荐用'],
            'es': ['me gusta', 'prefiero', 'amo', 'odio', 'quiero', 'no me gusta'],
            'fr': ['j\'aime', 'préfère', 'aime', 'déteste', 'veux', 'n\'aime pas'],
            'de': ['mag', 'bevorzuge', 'liebe', 'hasse', 'will', 'mag nicht'],
            'ja': ['好き', '好む', '愛する', '嫌い', '欲しい', '嫌う'],
            'ko': ['좋아해', '선호', '사랑', '싫어', '원해', '싫어요'],
            'ru': ['люблю', 'предпочитаю', 'любовь', 'ненавижу', 'хочу', 'не люблю'],
            'ar': ['أحب', 'أفضل', 'حب', 'كره', 'أريد', 'لا أحب']
        },
        'correction': {
            'en': ['correct', 'wrong', 'incorrect', 'mistake', 'fix', 'error'],
            'zh-cn': ['纠正', '错了', '不对', '错误', '修复', '失误', '别用', '不要用', '下次别'],
            'es': ['corregir', 'equivocado', 'incorrecto', 'error', 'arreglar', 'fallo'],
            'fr': ['corriger', 'faux', 'incorrect', 'erreur', 'réparer', 'faute'],
            'de': ['korrigieren', 'falsch', 'inkorrekt', 'fehler', 'beheben', 'fehlerhaft'],
            'ja': ['訂正', '間違い', '正しくない', '誤り', '修正', 'エラー'],
            'ko': ['수정', '틀렸어', '맞지 않아', '오류', '고치다', '에러'],
            'ru': ['исправить', 'неправильно', 'инкорректно', 'ошибка', 'исправить', 'ошибка'],
            'ar': ['صحح', 'خطأ', 'غير صحيح', 'mistak', 'إصلاح', 'خطأ']
        },
        'fact_declaration': {
            'en': ['is', 'are', 'was', 'were', 'have', 'has', 'exist', 'exists'],
            'zh-cn': ['是', '有', '存在', '位于', '属于', '拥有'],
            'es': ['es', 'son', 'fue', 'fueron', 'tiene', 'tienen', 'existe', 'existen'],
            'fr': ['est', 'sont', 'était', 'étaient', 'a', 'ont', 'existe', 'existent'],
            'de': ['ist', 'sind', 'war', 'waren', 'hat', 'haben', 'existiert', 'existieren'],
            'ja': ['です', 'あります', '存在する', 'にある', 'に属する', '持っている'],
            'ko': ['입니다', '있어요', '존재한다', '에 있다', '속한다', '가지고 있다'],
            'ru': ['есть', 'существует', 'был', 'были', 'имеет', 'имеют', 'существует', 'существуют'],
            'ar': ['هو', 'هي', 'يوجد', 'توجد', 'لديه', 'لديهم', 'موجود', 'موجودة']
        },
        'decision': {
            'en': ['decide', 'decision', 'choose', 'choice', 'confirm', 'agreed',
                   'implement', 'deploy', 'migrate', 'adopt', 'switch to', 'move to',
                   'start', 'launch', 'roll out', 'go with', 'settle on', 'approve'],
            'zh-cn': ['决定', '决策', '选择', '确认', '同意', '确定',
                      '实施', '推进', '开始', '启动', '部署', '上线', '迁移', '采用',
                      '切换', '转为', '选定', '批准', '通过', '执行'],
            'es': ['decidir', 'decisión', 'elegir', 'elección', 'confirmar', 'acordado',
                   'implementar', 'desplegar', 'migrar', 'adoptar', 'cambiar a', 'iniciar'],
            'fr': ['décider', 'décision', 'choisir', 'choix', 'confirmer', 'accordé',
                   'implémenter', 'déployer', 'migrer', 'adopter', 'passer à', 'lancer'],
            'de': ['entscheiden', 'entscheidung', 'wählen', 'wahl', 'bestätigen', 'vereinbart',
                   'implementieren', 'bereitstellen', 'migrieren', 'übernehmen', 'starten'],
            'ja': ['決める', '決定', '選ぶ', '選択', '確認', '合意',
                   '実装', '導入', '移行', '採用', '開始', '起動', '展開'],
            'ko': ['결정하다', '결정', '선택하다', '선택', '확인하다', '합의',
                   '구현', '배포', '마이그레이션', '채택', '시작', '런칭'],
            'ru': ['решить', 'решение', 'выбрать', 'выбор', 'подтвердить', 'согласился',
                   'внедрить', 'развернуть', 'мигрировать', 'принять', 'запустить'],
            'ar': ['قرر', 'قرار', 'اختر', 'خيار', 'تأكيد', 'اتفق',
                   'تنفيذ', 'نشر', 'ترحيل', 'اعتماد', 'بدء', 'إطلاق']
        },
        'relationship': {
            'en': ['responsible', 'manage', 'belong', 'report', 'work with', 'team', 'handles'],
            'zh-cn': ['负责', '管理', '属于', '汇报', '合作', '团队'],
            'es': ['responsable', 'gestionar', 'pertenecer', 'informar', 'trabajar con', 'equipo'],
            'fr': ['responsable', 'gérer', 'appartenir', 'rapporter', 'travailler avec', 'équipe'],
            'de': ['verantwortlich', 'verwalten', 'gehören', 'berichten', 'mitarbeiten', 'team'],
            'ja': ['担当', '管理', '属する', '報告', '協力', 'チーム', 'マネージャー', '求めている', '求めています'],
            'ko': ['책임진다', '관리하다', '속한다', '보고하다', '협력하다', '팀'],
            'ru': ['ответственный', 'управлять', 'принадлежать', 'отчитываться', 'работать с', 'команда'],
            'ar': ['مسؤول', 'إدارة', 'ينتمي', 'تقرير', 'يعمل مع', 'فريق']
        },
        'task_pattern': {
            'en': ['task', 'work', 'process', 'repeat', 'regular', 'routine',
                   'phase', 'stage', 'step', 'milestone', 'sprint', 'iteration',
                   'progress', 'schedule', 'deadline', 'roadmap', 'backlog'],
            'zh-cn': ['任务', '工作', '流程', '重复', '定期', '常规',
                      '阶段', '步骤', '里程碑', '进度', '迭代', '排期',
                      '计划', '排期', '路线图', '待办', '冲刺'],
            'es': ['tarea', 'trabajo', 'proceso', 'repetir', 'regular', 'rutina',
                   'fase', 'etapa', 'paso', 'hito', 'sprint', 'iteración'],
            'fr': ['tâche', 'travail', 'processus', 'répéter', 'régulier', 'routine',
                   'phase', 'étape', 'étape', 'jalon', 'sprint', 'itération'],
            'de': ['aufgabe', 'arbeit', 'prozess', 'wiederholen', 'regelmäßig', 'routine',
                   'phase', 'schritt', 'meilenstein', 'sprint', 'iteration'],
            'ja': ['タスク', '仕事', 'プロセス', '繰り返す', '定期的', 'ルーティン',
                   'フェーズ', 'ステップ', 'マイルストーン', '進捗', 'スプリント', 'イテレーション'],
            'ko': ['작업', '일', '프로세스', '반복하다', '정기적인', '루틴',
                   '단계', '스텝', '마일스톤', '진행', '스프린트', '반복'],
            'ru': ['задача', 'работа', 'процесс', 'повторить', 'регулярный', 'рабочая рутина',
                   'фаза', 'этап', 'шаг', 'веха', 'спринт', 'итерация'],
            'ar': ['مهمة', 'عمل', 'عملية', 'كرر', 'نظامي', 'روتين',
                   'مرحلة', 'خطوة', 'معلم', 'تقدم', 'سبرنت', 'تكرار']
        },
        'sentiment_marker': {
            'en': ['happy', 'sad', 'angry', 'excited', 'disappointed', 'satisfied'],
            'zh-cn': ['开心', '难过', '生气', '兴奋', '失望', '满意'],
            'es': ['feliz', 'triste', 'enojado', 'emocionado', 'desilusionado', 'satisfecho'],
            'fr': ['heureux', 'triste', 'en colère', 'excité', 'déçu', 'satisfait'],
            'de': ['glücklich', 'traurig', 'wütend', 'aufgeregt', 'enttäuscht', 'zufrieden'],
            'ja': ['嬉しい', '悲しい', '怒っている', '興奮している', '失望している', '満足している'],
            'ko': ['행복', '슬픈', '화난', '흥분된', '실망한', '만족한'],
            'ru': ['счастлив', 'грустный', 'злой', 'воодушевленный', 'разочарованный', 'удовлетворенный'],
            'ar': ['سعيد', 'حزين', 'غاضب', 'متحمس', 'مایوس', 'مشبع']
        }
    }
    
    NEGATION_WORDS = {
        'en': ['not', 'no', 'don\'t', 'doesn\'t', 'didn\'t', 'won\'t', 'can\'t', 'never'],
        'zh-cn': ['不', '没', '没有', '不是', '不要', '不喜欢', '不想要'],
        'es': ['no', 'nunca', 'jamás', 'tampoco', 'ni'],
        'fr': ['ne', 'pas', 'jamais', 'plus', 'aucun'],
        'de': ['nicht', 'kein', 'nie', 'nirgends'],
        'ja': ['ない', 'いない', 'しない', 'ではない'],
        'ko': ['아니', '없다', '안', '못'],
        'ru': ['не', 'ни', 'никогда', 'нельзя'],
        'ar': ['لا', 'ليس', 'لم', 'مិន']
    }
    
    def __init__(self):
        """Initialize the language manager."""
        pass
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """Detect the language of a text.
        
        Args:
            text: The text to detect language for.
            
        Returns:
            A tuple of (language_code, confidence).
        """
        if text is None:
            return "en", 0.5

        has_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)
        has_hiragana = any("\u3040" <= char <= "\u309f" for char in text)
        has_katakana = any("\u30a0" <= char <= "\u30ff" for char in text)

        if has_hiragana or has_katakana:
            return "ja", 0.95

        if has_cjk and not has_hiragana and not has_katakana:
            return "zh-cn", 0.95

        if _CLD2_AVAILABLE:
            try:
                is_reliable, text_bytes_found, details = cld2.detect(text)
                if is_reliable and details:
                    language_code = details[0][1].lower()
                    confidence = details[0][2] / 100.0
                    language_code = self._map_language_code(language_code)
                    return language_code, confidence
            except Exception as e:
                logger.debug(f"Failed to process language detection with CLD2: {e}")
                pass

        if _LANGDETECT_AVAILABLE:
            try:
                language_code = detect(text)
                language_code = self._map_language_code(language_code)
                return language_code, 0.8
            except LangDetectException:
                pass

        return 'en', 0.5
    
    def _map_language_code(self, code: str) -> str:
        """Map language codes to our supported ones.
        
        Args:
            code: The detected language code.
            
        Returns:
            The mapped language code.
        """
        code_map = {
            'zh': 'zh-cn',
            'zh-hans': 'zh-cn',
            'zh-hant': 'zh-tw',
            'zh-hk': 'zh-tw'
        }
        
        return code_map.get(code, code)
    
    def get_keywords(self, memory_type: str, language: str) -> List[str]:
        """Get keywords for a memory type in a specific language.
        
        Args:
            memory_type: The memory type.
            language: The language code.
            
        Returns:
            A list of keywords for the memory type in the specified language.
        """
        if memory_type in self.MULTI_LANG_KEYWORDS:
            if language in self.MULTI_LANG_KEYWORDS[memory_type]:
                return self.MULTI_LANG_KEYWORDS[memory_type][language]
            else:
                return self.MULTI_LANG_KEYWORDS[memory_type].get('en', [])
        return []
    
    def get_negation_words(self, language: str) -> List[str]:
        """Get negation words for a specific language.
        
        Args:
            language: The language code.
            
        Returns:
            A list of negation words for the specified language.
        """
        return self.NEGATION_WORDS.get(language, self.NEGATION_WORDS.get('en', []))
    
    def is_supported_language(self, language: str) -> bool:
        """Check if a language is supported.
        
        Args:
            language: The language code.
            
        Returns:
            True if the language is supported, False otherwise.
        """
        return language in self.SUPPORTED_LANGUAGES
    
    def get_language_name(self, language: str) -> str:
        """Get the name of a language.
        
        Args:
            language: The language code.
            
        Returns:
            The name of the language.
        """
        return self.SUPPORTED_LANGUAGES.get(language, language)
    
    def extract_keywords(self, text: str, language: str) -> List[str]:
        """Extract keywords from text in a specific language.
        
        Args:
            text: The text to extract keywords from.
            language: The language code.
            
        Returns:
            A list of extracted keywords.
        """
        keywords = []
        text_lower = text.lower()
        
        for memory_type, lang_keywords in self.MULTI_LANG_KEYWORDS.items():
            if language in lang_keywords:
                for keyword in lang_keywords[language]:
                    if keyword in text_lower:
                        keywords.append(keyword)
            else:
                for keyword in lang_keywords.get('en', []):
                    if keyword in text_lower:
                        keywords.append(keyword)
        
        return list(set(keywords))
    
    def detect_memory_type(self, text: str, language: str) -> List[Tuple[str, float]]:
        """Detect memory type based on keywords in a specific language.
        
        Args:
            text: The text to analyze.
            language: The language code.
            
        Returns:
            A list of tuples (memory_type, confidence).
        """
        results = []
        text_lower = text.lower()
        
        for memory_type, lang_keywords in self.MULTI_LANG_KEYWORDS.items():
            if language in lang_keywords:
                keywords = lang_keywords[language]
            else:
                keywords = lang_keywords.get('en', [])
            
            matched_keywords = [kw for kw in keywords if kw in text_lower]
            if matched_keywords:
                confidence = min(0.5 + len(matched_keywords) * 0.1, 0.9)
                results.append((memory_type, confidence))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results

language_manager = LanguageManager()
