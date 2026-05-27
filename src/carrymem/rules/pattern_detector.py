"""
Pattern Detector — Identify repeated memory patterns for rule promotion.

Detects patterns in user memories that suggest behavioral rules:
- 3+ corrections with similar keywords → avoidance pattern
- 3+ decisions in same domain → consistency pattern
- 3+ preferences about same topic → preference pattern
- 2+ negative sentiment markers → aversion pattern

No LLM dependency — uses keyword extraction and frequency analysis.
"""

import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class PatternType(str, Enum):
    AVOIDANCE = "avoidance"
    PREFERENCE = "preference"
    CONSISTENCY = "consistency"
    AVERSION = "aversion"


class PatternConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class MemoryPattern:
    pattern_type: PatternType
    keywords: List[str]
    source_memory_ids: List[str]
    source_contents: List[str]
    memory_type: str
    occurrence_count: int
    confidence: PatternConfidence
    domain: str = ""

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type.value,
            "keywords": self.keywords,
            "source_memory_ids": self.source_memory_ids,
            "source_contents": self.source_contents,
            "memory_type": self.memory_type,
            "occurrence_count": self.occurrence_count,
            "confidence": self.confidence.value,
            "domain": self.domain,
        }


_STOP_WORDS_EN = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "up", "it",
    "its", "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them", "their",
    "what", "which", "who", "whom", "don", "doesn", "didn", "won", "wouldn",
    "isn", "aren", "wasn", "weren", "hasn", "haven", "hadn", "cannot",
    "couldn", "shouldn", "mustn", "let", "please", "want", "like",
    "think", "know", "make", "go", "get", "come", "take", "see",
    "look", "give", "find", "tell", "say", "said", "use", "try",
    "also", "really", "much", "still", "even", "back", "way",
})

_STOP_WORDS_ZH = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这", "他", "她", "它", "们",
    "那", "些", "什么", "怎么", "如何", "可以", "能", "吗", "吧", "呢",
    "啊", "哦", "嗯", "呀", "哈", "嘛", "啦", "把", "被", "让",
    "给", "对", "从", "向", "比", "跟", "与", "及", "或", "但",
    "而", "且", "如果", "因为", "所以", "虽然", "但是", "然后",
    "还是", "已经", "正在", "将要", "应该", "必须", "需要", "可能",
    "不要", "别", "不用", "没", "无", "非", "未",
})

_NEGATION_WORDS_EN = frozenset({
    "not", "no", "never", "don't", "doesn't", "didn't", "won't",
    "wouldn't", "shouldn't", "can't", "cannot", "avoid", "refuse",
    "reject", "dislike", "hate", "stop", "quit",
})

_NEGATION_WORDS_ZH = frozenset({
    "不", "不要", "别", "不用", "拒绝", "避免", "讨厌", "反感",
    "放弃", "停止", "不能", "不可", "禁止", "排除",
})

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "tech_selection": [
        "框架", "语言", "技术", "库", "工具", "选型", "架构",
        "framework", "language", "tech", "library", "tool", "stack",
        "python", "java", "javascript", "react", "vue", "go", "rust",
        "postgresql", "mysql", "redis", "mongodb", "docker", "k8s",
    ],
    "code_review": [
        "代码", "评审", "审查", "规范", "风格", "格式",
        "code", "review", "style", "format", "lint", "standard",
    ],
    "report": [
        "报告", "文档", "汇报", "总结", "摘要",
        "report", "document", "summary", "presentation", "slide",
    ],
    "security": [
        "安全", "漏洞", "加密", "认证", "授权", "密码",
        "security", "vulnerability", "encrypt", "auth", "password",
    ],
    "api": [
        "接口", "API", "端点", "请求", "响应",
        "endpoint", "request", "response", "rest", "graphql",
    ],
    "testing": [
        "测试", "单元测试", "集成测试", "覆盖率",
        "test", "unit test", "integration", "coverage", "qa",
    ],
    "project": [
        "项目", "计划", "排期", "里程碑", "需求",
        "project", "plan", "schedule", "milestone", "requirement",
    ],
}


class PatternDetector:
    """Detect repeated patterns in user memories for rule promotion."""

    MIN_OCCURRENCES = 3
    MIN_KEYWORD_LENGTH = 2
    MAX_KEYWORDS_PER_TEXT = 50

    def __init__(self, min_occurrences: int = 3):
        self.min_occurrences = max(2, min_occurrences)

    def detect_patterns(
        self, memories: List[Dict], memory_type: Optional[str] = None
    ) -> List[MemoryPattern]:
        """
        Detect patterns across a list of memories.

        Args:
            memories: List of memory dicts (from CarryMem.recall_memories)
            memory_type: Optional filter for specific memory type

        Returns:
            List of detected MemoryPattern objects
        """
        if not memories:
            return []

        filtered = memories
        if memory_type:
            filtered = [m for m in memories if m.get("type") == memory_type]

        patterns = []

        grouped = self._group_by_type(filtered)
        for mem_type, type_memories in grouped.items():
            type_patterns = self._detect_type_patterns(mem_type, type_memories)
            patterns.extend(type_patterns)

        cross_type_patterns = self._detect_cross_type_patterns(filtered)
        patterns.extend(cross_type_patterns)

        patterns = self._deduplicate_patterns(patterns)

        return sorted(
            patterns,
            key=lambda p: (
                p.occurrence_count,
                p.confidence == PatternConfidence.HIGH,
                p.confidence == PatternConfidence.MEDIUM,
            ),
            reverse=True,
        )

    def _group_by_type(self, memories: List[Dict]) -> Dict[str, List[Dict]]:
        """Group memories by their type field."""
        groups: Dict[str, List[Dict]] = {}
        for m in memories:
            mem_type = m.get("type", "unknown")
            groups.setdefault(mem_type, []).append(m)
        return groups

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        if not text:
            return []

        keywords = []

        en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-\.]+", text.lower())
        for w in en_words:
            if w not in _STOP_WORDS_EN and len(w) >= self.MIN_KEYWORD_LENGTH:
                keywords.append(w)

        zh_segments = re.findall(r"[\u4e00-\u9fff]+", text)
        for seg in zh_segments:
            for i in range(len(seg)):
                for length in (2, 3, 4):
                    if i + length <= len(seg):
                        bigram = seg[i:i + length]
                        if not all(c in _STOP_WORDS_ZH for c in bigram):
                            keywords.append(bigram)

        return keywords[:self.MAX_KEYWORDS_PER_TEXT]

    def _detect_negation(self, text: str) -> bool:
        """Check if text contains negation signals."""
        text_lower = text.lower()
        for w in _NEGATION_WORDS_EN:
            if w in text_lower:
                return True
        for w in _NEGATION_WORDS_ZH:
            if w in text:
                return True
        return False

    def _infer_domain(self, text: str) -> str:
        """Infer the domain from text content."""
        text_lower = text.lower()
        best_domain = ""
        best_score = 0
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > best_score:
                best_score = score
                best_domain = domain
        return best_domain

    def _detect_type_patterns(
        self, mem_type: str, memories: List[Dict]
    ) -> List[MemoryPattern]:
        """Detect patterns within a single memory type."""
        patterns = []

        if mem_type == "correction":
            patterns.extend(self._detect_correction_patterns(memories))
        elif mem_type == "decision":
            patterns.extend(self._detect_decision_patterns(memories))
        elif mem_type == "user_preference":
            patterns.extend(self._detect_preference_patterns(memories))
        elif mem_type == "sentiment_marker":
            patterns.extend(self._detect_sentiment_patterns(memories))

        return patterns

    def _detect_correction_patterns(self, memories: List[Dict]) -> List[MemoryPattern]:
        """3+ corrections with similar keywords → avoidance pattern."""
        keyword_map: Dict[str, List[Dict]] = {}
        for m in memories:
            content = m.get("content", "")
            keywords = self._extract_keywords(content)
            for kw in keywords:
                keyword_map.setdefault(kw, []).append(m)

        patterns = []
        for kw, matching in keyword_map.items():
            if len(matching) >= self.min_occurrences:
                confidence = self._calc_confidence(len(matching))
                patterns.append(
                    MemoryPattern(
                        pattern_type=PatternType.AVOIDANCE,
                        keywords=[kw],
                        source_memory_ids=[m.get("id", "") for m in matching],
                        source_contents=[m.get("content", "") for m in matching],
                        memory_type="correction",
                        occurrence_count=len(matching),
                        confidence=confidence,
                        domain=self._infer_domain(matching[0].get("content", "")),
                    )
                )

        return self._merge_related_patterns(patterns)

    def _detect_decision_patterns(self, memories: List[Dict]) -> List[MemoryPattern]:
        """3+ decisions in same domain → consistency pattern."""
        domain_map: Dict[str, List[Dict]] = {}
        for m in memories:
            content = m.get("content", "")
            domain = self._infer_domain(content)
            if domain:
                domain_map.setdefault(domain, []).append(m)

        patterns = []
        for domain, matching in domain_map.items():
            if len(matching) >= self.min_occurrences:
                all_keywords: List[str] = []
                for m in matching:
                    all_keywords.extend(self._extract_keywords(m.get("content", "")))
                top_keywords = [
                    kw for kw, _ in Counter(all_keywords).most_common(3)
                ]
                confidence = self._calc_confidence(len(matching))
                patterns.append(
                    MemoryPattern(
                        pattern_type=PatternType.CONSISTENCY,
                        keywords=top_keywords,
                        source_memory_ids=[m.get("id", "") for m in matching],
                        source_contents=[m.get("content", "") for m in matching],
                        memory_type="decision",
                        occurrence_count=len(matching),
                        confidence=confidence,
                        domain=domain,
                    )
                )

        return patterns

    def _detect_preference_patterns(self, memories: List[Dict]) -> List[MemoryPattern]:
        """3+ preferences about same topic → preference pattern."""
        keyword_map: Dict[str, List[Dict]] = {}
        for m in memories:
            content = m.get("content", "")
            keywords = self._extract_keywords(content)
            for kw in keywords:
                keyword_map.setdefault(kw, []).append(m)

        patterns = []
        for kw, matching in keyword_map.items():
            if len(matching) >= self.min_occurrences:
                neg_count = sum(
                    1 for m in matching if self._detect_negation(m.get("content", ""))
                )
                is_neg = neg_count > len(matching) / 2
                confidence = self._calc_confidence(len(matching))
                patterns.append(
                    MemoryPattern(
                        pattern_type=PatternType.AVOIDANCE if is_neg else PatternType.PREFERENCE,
                        keywords=[kw],
                        source_memory_ids=[m.get("id", "") for m in matching],
                        source_contents=[m.get("content", "") for m in matching],
                        memory_type="user_preference",
                        occurrence_count=len(matching),
                        confidence=confidence,
                        domain=self._infer_domain(matching[0].get("content", "")),
                    )
                )

        return self._merge_related_patterns(patterns)

    def _detect_sentiment_patterns(self, memories: List[Dict]) -> List[MemoryPattern]:
        """2+ negative sentiment markers → aversion pattern."""
        negative_memories = []
        for m in memories:
            content = m.get("content", "")
            if self._detect_negation(content):
                negative_memories.append(m)

        if len(negative_memories) < 2:
            return []

        keyword_map: Dict[str, List[Dict]] = {}
        for m in negative_memories:
            content = m.get("content", "")
            keywords = self._extract_keywords(content)
            for kw in keywords:
                keyword_map.setdefault(kw, []).append(m)

        patterns = []
        for kw, matching in keyword_map.items():
            if len(matching) >= 2:
                confidence = PatternConfidence.MEDIUM if len(
                    matching) >= 3 else PatternConfidence.LOW
                patterns.append(
                    MemoryPattern(
                        pattern_type=PatternType.AVERSION,
                        keywords=[kw],
                        source_memory_ids=[m.get("id", "") for m in matching],
                        source_contents=[m.get("content", "") for m in matching],
                        memory_type="sentiment_marker",
                        occurrence_count=len(matching),
                        confidence=confidence,
                        domain=self._infer_domain(matching[0].get("content", "")),
                    )
                )

        return self._merge_related_patterns(patterns)

    def _detect_cross_type_patterns(self, memories: List[Dict]) -> List[MemoryPattern]:
        """Detect patterns that span multiple memory types."""
        domain_map: Dict[str, List[Dict]] = {}
        for m in memories:
            content = m.get("content", "")
            domain = self._infer_domain(content)
            if domain:
                domain_map.setdefault(domain, []).append(m)

        patterns = []
        for domain, matching in domain_map.items():
            types_in_domain = set(m.get("type", "") for m in matching)
            if len(types_in_domain) >= 2 and len(matching) >= self.min_occurrences:
                all_keywords: List[str] = []
                for m in matching:
                    all_keywords.extend(self._extract_keywords(m.get("content", "")))
                top_keywords = [
                    kw for kw, _ in Counter(all_keywords).most_common(3)
                ]
                has_negation = any(
                    self._detect_negation(m.get("content", "")) for m in matching
                )
                confidence = self._calc_confidence(len(matching))
                patterns.append(
    MemoryPattern(
        pattern_type=PatternType.AVOIDANCE if has_negation else PatternType.PREFERENCE,
        keywords=top_keywords,
        source_memory_ids=[
            m.get(
                "id",
                "") for m in matching],
                source_contents=[
                    m.get(
                        "content",
                        "") for m in matching],
                        memory_type="cross_type",
                        occurrence_count=len(matching),
                        confidence=confidence,
                        domain=domain,
                         ) )

        return patterns

    def _calc_confidence(self, count: int) -> PatternConfidence:
        """Calculate confidence level based on occurrence count."""
        if count >= 5:
            return PatternConfidence.HIGH
        elif count >= 3:
            return PatternConfidence.MEDIUM
        else:
            return PatternConfidence.LOW

    def _merge_related_patterns(self, patterns: List[MemoryPattern]) -> List[MemoryPattern]:
        """Merge patterns that share source memories."""
        if len(patterns) <= 1:
            return patterns

        merged = []
        used_indices = set()

        for i, p1 in enumerate(patterns):
            if i in used_indices:
                continue
            current = p1
            for j in range(i + 1, len(patterns)):
                if j in used_indices:
                    continue
                p2 = patterns[j]
                shared = set(current.source_memory_ids) & set(p2.source_memory_ids)
                if len(shared) >= len(current.source_memory_ids) * 0.5:
                    current = MemoryPattern(
                        pattern_type=current.pattern_type,
                        keywords=list(set(current.keywords + p2.keywords)),
                        source_memory_ids=list(
                            set(current.source_memory_ids + p2.source_memory_ids)),
                        source_contents=current.source_contents[:3],
                        memory_type=current.memory_type,
                        occurrence_count=max(current.occurrence_count, p2.occurrence_count),
                        confidence=max(
                            current.confidence, p2.confidence,
                            key=lambda c: list(PatternConfidence).index(c),
                        ),
                        domain=current.domain or p2.domain,
                    )
                    used_indices.add(j)
            merged.append(current)

        return merged

    def _deduplicate_patterns(self, patterns: List[MemoryPattern]) -> List[MemoryPattern]:
        """Remove duplicate patterns based on overlapping source memories."""
        if len(patterns) <= 1:
            return patterns

        unique = []
        for p in patterns:
            is_dup = False
            for existing in unique:
                shared = set(p.source_memory_ids) & set(existing.source_memory_ids)
                overlap_ratio = len(shared) / max(len(p.source_memory_ids), 1)
                if overlap_ratio > 0.8 and p.pattern_type == existing.pattern_type:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(p)

        return unique
