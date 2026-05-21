"""
Failure Experience Extractor — Extract lessons from failure memories.

Converts single failure experiences into actionable avoidance rules.
Unlike pattern-based promotion (which needs 3+ similar memories),
this module works with a SINGLE failure memory to generate a rule candidate.

Pipeline:
    Memory → Failure Detection → Lesson Extraction → Rule Candidate

Example:
    Memory: "Trusted competitor's website data, got caught by client"
    → Lesson: "Competitor official data is unreliable"
    → Rule: trigger="competitive analysis" action="mark competitor data as [unverified]" type=avoid

No LLM dependency — uses keyword matching and template-based extraction.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class FailureSignal(str, Enum):
    MISTAKE = "mistake"
    REGRET = "regret"
    NEGATIVE_OUTCOME = "negative_outcome"
    LESSON_LEARNED = "lesson_learned"
    CORRECTION_FROM_FAILURE = "correction_from_failure"


class FailureConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ExtractedLesson:
    source_memory_id: str
    source_content: str
    source_type: str
    failure_signal: FailureSignal
    lesson: str
    trigger_hint: str
    action_hint: str
    confidence: FailureConfidence
    domain: str = ""

    def to_dict(self) -> dict:
        return {
            "source_memory_id": self.source_memory_id,
            "source_content": self.source_content,
            "source_type": self.source_type,
            "failure_signal": self.failure_signal.value,
            "lesson": self.lesson,
            "trigger_hint": self.trigger_hint,
            "action_hint": self.action_hint,
            "confidence": self.confidence.value,
            "domain": self.domain,
        }


_MISTAKE_PATTERNS_EN: List[Tuple[str, str]] = [
    (r"(?i)(?:i\s+)?(?:made|made\s+a)\s+mistake", "mistake"),
    (r"(?i)(?:i\s+)?should\s+(?:not|n't)\s+have", "regret"),
    (r"(?i)(?:(?:it|that|this)\s+)?(?:was\s+a\s+)?mistake", "mistake"),
    (r"(?i)(?:don't|do\s+not|never)\s+(?:use|trust|rely\s+on|do)", "correction_from_failure"),
    (r"(?i)(?:learned|learnt|realized)\s+(?:that|the\s+hard\s+way)", "lesson_learned"),
    (r"(?i)(?:failed|failure|broke|crashed|lost)", "negative_outcome"),
    (r"(?i)(?:wasted|waste\s+of)\s+(?:time|money|effort)", "negative_outcome"),
    (r"(?i)(?:got\s+(?:caught|burned|screwed|bitten))", "negative_outcome"),
    (r"(?i)(?:bad\s+(?:idea|decision|choice|experience))", "regret"),
    (r"(?i)(?:never\s+again|won't\s+(?:do|make|trust)\s+again)", "lesson_learned"),
]

_MISTAKE_PATTERNS_ZH: List[Tuple[str, str]] = [
    (r"错了|失误|搞砸|踩坑|踩了坑", "mistake"),
    (r"不应该|不该|后悔|遗憾", "regret"),
    (r"失败|崩了|挂了|损失|亏了", "negative_outcome"),
    (r"教训|经验|学到了|记住", "lesson_learned"),
    (r"不要|别|不能|禁止|千万别", "correction_from_failure"),
    (r"被骗|被坑|被忽悠|被拆穿", "negative_outcome"),
    (r"不可信|不可靠|不靠谱", "lesson_learned"),
    (r"血的教训|深刻教训|惨痛经验", "lesson_learned"),
]

_OUTCOME_PATTERNS_EN: List[Tuple[str, str]] = [
    (r"(?i)(?:client|customer|boss|manager|user)\s+(?:complained|rejected|was\s+angry)", "negative_outcome"),
    (r"(?i)(?:caused|led\s+to)\s+(?:a\s+)?(?:problem|issue|bug|error|incident)", "negative_outcome"),
    (r"(?i)(?:cost|took)\s+(?:us\s+)?(?:hours|days|weeks|\$\d+)", "negative_outcome"),
]

_OUTCOME_PATTERNS_ZH: List[Tuple[str, str]] = [
    (r"客户|老板|用户.*(?:不满|投诉|拒绝|生气|批评)", "negative_outcome"),
    (r"导致|造成.*(?:问题|bug|故障|事故|延期)", "negative_outcome"),
    (r"浪费了|花了.*(?:天|小时|周)", "negative_outcome"),
]

_ACTION_EXTRACTION_EN: List[Tuple[str, str]] = [
    (r"(?i)(?:should|must|need\s+to|gotta)\s+(.+?)(?:\.|$)", "imperative"),
    (r"(?i)(?:always|never)\s+(.+?)(?:\.|$)", "absolute"),
    (r"(?i)(?:make\s+sure|ensure|verify)\s+(.+?)(?:\.|$)", "verification"),
    (r"(?i)(?:avoid|don't\s+use|stop)\s+(.+?)(?:\.|$)", "avoidance"),
]

_ACTION_EXTRACTION_ZH: List[Tuple[str, str]] = [
    (r"要|必须|一定|务必(.+?)(?:。|$)", "imperative"),
    (r"不要|别|不能|禁止(.+?)(?:。|$)", "avoidance"),
    (r"确保|确认|验证|检查(.+?)(?:。|$)", "verification"),
    (r"避免|排除|跳过(.+?)(?:。|$)", "avoidance"),
]

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "competitive_analysis": [
        "竞品", "对手", "竞争", "市场分析",
        "competitor", "competition", "market analysis", "rival",
    ],
    "vendor_management": [
        "供应商", "外包", "乙方", "服务商",
        "vendor", "supplier", "outsourcing", "contractor",
    ],
    "tech_selection": [
        "框架", "语言", "技术", "选型", "架构",
        "framework", "language", "tech", "stack", "architecture",
    ],
    "code_quality": [
        "代码", "bug", "测试", "质量", "规范",
        "code", "bug", "test", "quality", "standard",
    ],
    "project_management": [
        "项目", "排期", "需求", "里程碑", "交付",
        "project", "schedule", "requirement", "milestone", "delivery",
    ],
    "data_handling": [
        "数据", "来源", "统计", "报告", "信息",
        "data", "source", "statistics", "report", "information",
    ],
    "communication": [
        "沟通", "会议", "邮件", "汇报", "反馈",
        "communication", "meeting", "email", "report", "feedback",
    ],
}

_TRIGGER_TEMPLATES: Dict[str, str] = {
    "competitive_analysis": "competitive analysis or market research",
    "vendor_management": "vendor evaluation or outsourcing decisions",
    "tech_selection": "tech selection or solution design",
    "code_quality": "code review or quality assurance",
    "project_management": "project planning or task management",
    "data_handling": "data analysis or report writing",
    "communication": "stakeholder communication or reporting",
}

_ACTION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "mistake": {
        "en": "avoid repeating: {lesson}",
        "zh": "避免重复: {lesson}",
    },
    "regret": {
        "en": "do not: {lesson}",
        "zh": "不要: {lesson}",
    },
    "negative_outcome": {
        "en": "prevent: {lesson}",
        "zh": "防止: {lesson}",
    },
    "lesson_learned": {
        "en": "apply lesson: {lesson}",
        "zh": "应用教训: {lesson}",
    },
    "correction_from_failure": {
        "en": "follow correction: {lesson}",
        "zh": "遵循纠正: {lesson}",
    },
}

_SIGNAL_CONFIDENCE: Dict[str, FailureConfidence] = {
    "lesson_learned": FailureConfidence.HIGH,
    "correction_from_failure": FailureConfidence.HIGH,
    "mistake": FailureConfidence.MEDIUM,
    "regret": FailureConfidence.MEDIUM,
    "negative_outcome": FailureConfidence.LOW,
}


class FailureExperienceExtractor:
    """Extract actionable lessons from failure memories."""

    def __init__(self):
        self._compiled_en = [
            (re.compile(p), s) for p, s in _MISTAKE_PATTERNS_EN + _OUTCOME_PATTERNS_EN
        ]
        self._compiled_zh = [
            (re.compile(p), s) for p, s in _MISTAKE_PATTERNS_ZH + _OUTCOME_PATTERNS_ZH
        ]
        self._action_en = [
            (re.compile(p), t) for p, t in _ACTION_EXTRACTION_EN
        ]
        self._action_zh = [
            (re.compile(p), t) for p, t in _ACTION_EXTRACTION_ZH
        ]

    def extract(
        self, memories: List[Dict], memory_type: Optional[str] = None
    ) -> List[ExtractedLesson]:
        """
        Extract lessons from memories that contain failure signals.

        Args:
            memories: List of memory dicts from CarryMem.recall_memories
            memory_type: Optional filter for specific memory type

        Returns:
            List of ExtractedLesson objects
        """
        if not memories:
            return []

        filtered = memories
        if memory_type:
            filtered = [m for m in memories if m.get("type") == memory_type]

        lessons = []
        for m in filtered:
            lesson = self._extract_from_memory(m)
            if lesson:
                lessons.append(lesson)

        lessons.sort(
            key=lambda lesson: (
                lesson.confidence == FailureConfidence.HIGH,
                lesson.confidence == FailureConfidence.MEDIUM,
            ),
            reverse=True,
        )

        return lessons

    def _extract_from_memory(self, memory: Dict) -> Optional[ExtractedLesson]:
        """Extract a lesson from a single memory."""
        content = memory.get("content", "")
        if not content or len(content) < 5:
            return None

        if len(content) > 2000:
            content = content[:2000]

        signal, signal_type = self._detect_failure_signal(content)
        if not signal:
            return None

        lesson = self._extract_lesson(content, signal_type)
        trigger_hint = self._infer_trigger(content)
        action_hint = self._extract_action_hint(content, signal_type, lesson)
        domain = self._infer_domain(content)
        confidence = self._calc_confidence(signal_type, content)

        return ExtractedLesson(
            source_memory_id=memory.get("id", ""),
            source_content=content,
            source_type=memory.get("type", "unknown"),
            failure_signal=signal,
            lesson=lesson,
            trigger_hint=trigger_hint,
            action_hint=action_hint,
            confidence=confidence,
            domain=domain,
        )

    def _detect_failure_signal(
        self, content: str
    ) -> Tuple[Optional[FailureSignal], str]:
        """Detect if content contains a failure signal."""
        for pattern, signal_type in self._compiled_en:
            if pattern.search(content):
                signal = FailureSignal(signal_type)
                return signal, signal_type

        for pattern, signal_type in self._compiled_zh:
            if pattern.search(content):
                signal = FailureSignal(signal_type)
                return signal, signal_type

        return None, ""

    def _extract_lesson(self, content: str, signal_type: str) -> str:
        """Extract the core lesson from failure content."""
        if signal_type == "lesson_learned":
            for pattern, _ in self._compiled_en:
                match = pattern.search(content)
                if match:
                    return content.strip()

            for pattern, _ in self._compiled_zh:
                match = pattern.search(content)
                if match:
                    return content.strip()

        if signal_type == "correction_from_failure":
            for pattern, _ in self._compiled_en:
                match = pattern.search(content)
                if match:
                    return match.group(0).strip()

            for pattern, _ in self._compiled_zh:
                match = pattern.search(content)
                if match:
                    return match.group(0).strip()

        return content.strip()

    def _extract_action_hint(
        self, content: str, signal_type: str, lesson: str
    ) -> str:
        """Extract or generate an action hint for the rule."""
        for pattern, _ in self._action_en:
            match = pattern.search(content)
            if match:
                return match.group(1).strip()

        for pattern, _ in self._action_zh:
            match = pattern.search(content)
            if match:
                return match.group(1).strip()

        template = _ACTION_TEMPLATES.get(signal_type, _ACTION_TEMPLATES["mistake"])
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", content))
        lang = "zh" if has_cjk else "en"
        return template[lang].format(lesson=lesson[:100])

    def _infer_trigger(self, content: str) -> str:
        """Infer the trigger scene from content."""
        domain = self._infer_domain(content)
        if domain and domain in _TRIGGER_TEMPLATES:
            return _TRIGGER_TEMPLATES[domain]

        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", content))
        if has_cjk:
            return "related scenarios"

        return "related scenarios"

    def _infer_domain(self, content: str) -> str:
        """Infer the domain from content."""
        content_lower = content.lower()
        best_domain = ""
        best_score = 0
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in content_lower)
            if score > best_score:
                best_score = score
                best_domain = domain
        return best_domain

    def _calc_confidence(
        self, signal_type: str, content: str
    ) -> FailureConfidence:
        """Calculate confidence based on signal type and content richness."""
        base = _SIGNAL_CONFIDENCE.get(signal_type, FailureConfidence.LOW)

        if len(content) > 50:
            if base == FailureConfidence.LOW:
                return FailureConfidence.MEDIUM
            elif base == FailureConfidence.MEDIUM:
                return FailureConfidence.HIGH

        return base

    def is_failure_memory(self, content: str) -> bool:
        """Quick check if content contains failure signals."""
        signal, _ = self._detect_failure_signal(content)
        return signal is not None
