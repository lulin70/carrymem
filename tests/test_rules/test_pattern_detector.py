"""
Test Suite for Pattern Detector and Candidate Rule Generator

Validates:
- PatternDetector: keyword extraction, pattern grouping, dedup
- CandidateRuleGenerator: template rendering, sanitization
- Integration: detect → generate → verify candidates
"""

import pytest

from carrymem.rules.pattern_detector import (
    PatternDetector,
    MemoryPattern,
    PatternType,
    PatternConfidence,
)
from carrymem.rules.candidate_rule_generator import (
    CandidateRuleGenerator,
    RuleCandidate,
)


@pytest.fixture
def detector():
    return PatternDetector(min_occurrences=3)


@pytest.fixture
def generator():
    return CandidateRuleGenerator()


def _make_memory(mem_id: str, mem_type: str, content: str) -> dict:
    return {
        "id": mem_id,
        "type": mem_type,
        "content": content,
        "confidence": 0.9,
        "tier": 3,
    }


class TestKeywordExtraction:
    """Test keyword extraction from text"""

    def test_extract_english_keywords(self, detector):
        keywords = detector._extract_keywords("I prefer Python over Java for backend")
        assert "python" in keywords
        assert "java" in keywords
        assert "backend" in keywords

    def test_extract_chinese_keywords(self, detector):
        keywords = detector._extract_keywords("不要使用Java框架做后端开发")
        assert "java" in keywords
        assert any("框架" in kw for kw in keywords)

    def test_extract_empty_text(self, detector):
        keywords = detector._extract_keywords("")
        assert keywords == []

    def test_extract_stops_words_filtered(self, detector):
        keywords = detector._extract_keywords("the is a an of in for on with")
        assert keywords == []

    def test_extract_short_keywords_filtered(self, detector):
        keywords = detector._extract_keywords("I am a go developer")
        assert "go" not in keywords or "developer" in keywords


class TestNegationDetection:
    """Test negation signal detection"""

    def test_detect_english_negation(self, detector):
        assert detector._detect_negation("I don't like Java") is True
        assert detector._detect_negation("Never use this pattern") is True
        assert detector._detect_negation("Avoid hardcoded passwords") is True

    def test_detect_chinese_negation(self, detector):
        assert detector._detect_negation("不要用Java") is True
        assert detector._detect_negation("避免使用这个模式") is True
        assert detector._detect_negation("我拒绝这个方案") is True

    def test_no_negation(self, detector):
        assert detector._detect_negation("I prefer Python") is False
        assert detector._detect_negation("选择React做前端") is False


class TestDomainInference:
    """Test domain inference from text"""

    def test_tech_selection_domain(self, detector):
        assert detector._infer_domain("选择Python做后端框架") == "tech_selection"
        assert detector._infer_domain("Use React for frontend") == "tech_selection"

    def test_security_domain(self, detector):
        assert detector._infer_domain("检查安全漏洞和密码加密") == "security"

    def test_report_domain(self, detector):
        assert detector._infer_domain("写季度报告和文档") == "report"

    def test_unknown_domain(self, detector):
        assert detector._infer_domain("今天天气很好") == ""


class TestCorrectionPatternDetection:
    """Test pattern detection from correction memories"""

    def test_three_corrections_creates_avoidance(self, detector):
        memories = [
            _make_memory("c1", "correction", "不要用Java做后端"),
            _make_memory("c2", "correction", "Java框架不适合这个项目"),
            _make_memory("c3", "correction", "别用Java，用Python"),
        ]
        patterns = detector.detect_patterns(memories)
        assert len(patterns) >= 1
        assert patterns[0].pattern_type == PatternType.AVOIDANCE
        assert patterns[0].occurrence_count >= 3

    def test_two_corrections_no_pattern(self, detector):
        memories = [
            _make_memory("c1", "correction", "不要用Java"),
            _make_memory("c2", "correction", "Java不好"),
        ]
        patterns = detector.detect_patterns(memories)
        correction_patterns = [p for p in patterns if p.memory_type == "correction"]
        assert len(correction_patterns) == 0

    def test_correction_pattern_has_source_ids(self, detector):
        memories = [
            _make_memory("c1", "correction", "不要用Java做后端"),
            _make_memory("c2", "correction", "Java框架不适合"),
            _make_memory("c3", "correction", "别用Java，用Python"),
        ]
        patterns = detector.detect_patterns(memories)
        assert len(patterns) >= 1
        assert len(patterns[0].source_memory_ids) >= 3


class TestDecisionPatternDetection:
    """Test pattern detection from decision memories"""

    def test_three_decisions_same_domain(self, detector):
        memories = [
            _make_memory("d1", "decision", "选择Python做后端开发"),
            _make_memory("d2", "decision", "用PostgreSQL做数据库"),
            _make_memory("d3", "decision", "技术选型用FastAPI"),
        ]
        patterns = detector.detect_patterns(memories)
        consistency = [p for p in patterns if p.pattern_type == PatternType.CONSISTENCY]
        assert len(consistency) >= 1

    def test_decisions_different_domains_no_pattern(self, detector):
        memories = [
            _make_memory("d1", "decision", "选择Python做后端"),
            _make_memory("d2", "decision", "报告格式用PDF"),
            _make_memory("d3", "decision", "团队5个人"),
        ]
        patterns = detector.detect_patterns(memories)
        consistency = [p for p in patterns if p.pattern_type == PatternType.CONSISTENCY]
        assert len(consistency) == 0


class TestPreferencePatternDetection:
    """Test pattern detection from user_preference memories"""

    def test_three_preferences_creates_pattern(self, detector):
        memories = [
            _make_memory("p1", "user_preference", "偏好PostgreSQL数据库"),
            _make_memory("p2", "user_preference", "喜欢用PostgreSQL做存储"),
            _make_memory("p3", "user_preference", "PostgreSQL是最好的选择"),
        ]
        patterns = detector.detect_patterns(memories)
        assert len(patterns) >= 1
        pref = [p for p in patterns if p.pattern_type == PatternType.PREFERENCE]
        assert len(pref) >= 1

    def test_negative_preference_creates_avoidance(self, detector):
        memories = [
            _make_memory("p1", "user_preference", "不喜欢Java"),
            _make_memory("p2", "user_preference", "不要Java"),
            _make_memory("p3", "user_preference", "避免Java"),
        ]
        patterns = detector.detect_patterns(memories)
        avoidance = [p for p in patterns if p.pattern_type == PatternType.AVOIDANCE]
        assert len(avoidance) >= 1


class TestSentimentPatternDetection:
    """Test pattern detection from sentiment_marker memories"""

    def test_two_negative_sentiments_creates_aversion(self, detector):
        memories = [
            _make_memory("s1", "sentiment_marker", "讨厌Java的冗长语法"),
            _make_memory("s2", "sentiment_marker", "反感Java的配置地狱"),
        ]
        patterns = detector.detect_patterns(memories)
        aversion = [p for p in patterns if p.pattern_type == PatternType.AVERSION]
        assert len(aversion) >= 1

    def test_one_negative_no_pattern(self, detector):
        memories = [
            _make_memory("s1", "sentiment_marker", "讨厌Java"),
        ]
        patterns = detector.detect_patterns(memories)
        aversion = [p for p in patterns if p.pattern_type == PatternType.AVERSION]
        assert len(aversion) == 0


class TestCrossTypePatternDetection:
    """Test pattern detection across memory types"""

    def test_cross_type_domain_pattern(self, detector):
        memories = [
            _make_memory("c1", "correction", "不要用Java做后端"),
            _make_memory("d1", "decision", "选择Python做后端框架"),
            _make_memory("p1", "user_preference", "偏好Python技术栈"),
        ]
        patterns = detector.detect_patterns(memories)
        cross = [p for p in patterns if p.memory_type == "cross_type"]
        assert len(cross) >= 1


class TestEmptyInput:
    """Test edge cases with empty input"""

    def test_empty_memories(self, detector):
        patterns = detector.detect_patterns([])
        assert patterns == []

    def test_single_memory(self, detector):
        memories = [_make_memory("m1", "correction", "不要用Java")]
        patterns = detector.detect_patterns(memories)
        assert patterns == []

    def test_type_filter(self, detector):
        memories = [
            _make_memory("c1", "correction", "不要用Java"),
            _make_memory("c2", "correction", "Java不好"),
            _make_memory("c3", "correction", "别用Java"),
            _make_memory("d1", "decision", "选择Python"),
        ]
        patterns = detector.detect_patterns(memories, memory_type="correction")
        for p in patterns:
            if p.memory_type != "cross_type":
                assert p.memory_type == "correction"


class TestMemoryPatternSerialization:
    """Test MemoryPattern to_dict serialization"""

    def test_to_dict(self):
        pattern = MemoryPattern(
            pattern_type=PatternType.AVOIDANCE,
            keywords=["java"],
            source_memory_ids=["c1", "c2", "c3"],
            source_contents=["content1", "content2", "content3"],
            memory_type="correction",
            occurrence_count=3,
            confidence=PatternConfidence.MEDIUM,
            domain="tech_selection",
        )
        d = pattern.to_dict()
        assert d["pattern_type"] == "avoidance"
        assert d["keywords"] == ["java"]
        assert d["occurrence_count"] == 3
        assert d["confidence"] == "medium"
        assert d["domain"] == "tech_selection"


class TestCandidateRuleGenerator:
    """Test candidate rule generation from patterns"""

    def test_generate_from_avoidance_pattern(self, generator):
        patterns = [
            MemoryPattern(
                pattern_type=PatternType.AVOIDANCE,
                keywords=["java"],
                source_memory_ids=["c1", "c2", "c3"],
                source_contents=["不要用Java", "Java不好", "别用Java"],
                memory_type="correction",
                occurrence_count=3,
                confidence=PatternConfidence.MEDIUM,
                domain="tech_selection",
            )
        ]
        candidates = generator.generate(patterns)
        assert len(candidates) == 1
        assert candidates[0].rule_type == "avoid"
        assert candidates[0].override is True
        assert candidates[0].derived_from == "auto_promotion"
        assert "java" in candidates[0].action.lower() or "Java" in candidates[0].action

    def test_generate_from_preference_pattern(self, generator):
        patterns = [
            MemoryPattern(
                pattern_type=PatternType.PREFERENCE,
                keywords=["python"],
                source_memory_ids=["p1", "p2", "p3"],
                source_contents=["偏好Python", "喜欢Python", "Python好"],
                memory_type="user_preference",
                occurrence_count=3,
                confidence=PatternConfidence.MEDIUM,
                domain="tech_selection",
            )
        ]
        candidates = generator.generate(patterns)
        assert len(candidates) == 1
        assert candidates[0].rule_type == "prefer"
        assert candidates[0].override is False

    def test_generate_from_consistency_pattern(self, generator):
        patterns = [
            MemoryPattern(
                pattern_type=PatternType.CONSISTENCY,
                keywords=["python", "fastapi"],
                source_memory_ids=["d1", "d2", "d3"],
                source_contents=["选Python", "用FastAPI", "Python后端"],
                memory_type="decision",
                occurrence_count=3,
                confidence=PatternConfidence.MEDIUM,
                domain="tech_selection",
            )
        ]
        candidates = generator.generate(patterns)
        assert len(candidates) == 1
        assert candidates[0].rule_type == "always"

    def test_generate_from_aversion_pattern(self, generator):
        patterns = [
            MemoryPattern(
                pattern_type=PatternType.AVERSION,
                keywords=["java"],
                source_memory_ids=["s1", "s2"],
                source_contents=["讨厌Java", "反感Java"],
                memory_type="sentiment_marker",
                occurrence_count=2,
                confidence=PatternConfidence.LOW,
                domain="tech_selection",
            )
        ]
        candidates = generator.generate(patterns)
        assert len(candidates) == 1
        assert candidates[0].rule_type == "forbid"
        assert candidates[0].override is True

    def test_generate_empty_patterns(self, generator):
        candidates = generator.generate([])
        assert candidates == []

    def test_generate_max_candidates(self, generator):
        patterns = []
        for i in range(15):
            patterns.append(
                MemoryPattern(
                    pattern_type=PatternType.AVOIDANCE,
                    keywords=[f"keyword{i}"],
                    source_memory_ids=[f"m{i}"],
                    source_contents=[f"content{i}"],
                    memory_type="correction",
                    occurrence_count=3,
                    confidence=PatternConfidence.MEDIUM,
                    domain="tech_selection",
                )
            )
        candidates = generator.generate(patterns, max_candidates=5)
        assert len(candidates) == 5

    def test_confidence_high_gives_higher_score(self, generator):
        patterns = [
            MemoryPattern(
                pattern_type=PatternType.AVOIDANCE,
                keywords=["java"],
                source_memory_ids=["c1", "c2", "c3", "c4", "c5"],
                source_contents=["content"] * 5,
                memory_type="correction",
                occurrence_count=5,
                confidence=PatternConfidence.HIGH,
                domain="tech_selection",
            ),
            MemoryPattern(
                pattern_type=PatternType.AVOIDANCE,
                keywords=["ruby"],
                source_memory_ids=["c6", "c7", "c8"],
                source_contents=["content"] * 3,
                memory_type="correction",
                occurrence_count=3,
                confidence=PatternConfidence.MEDIUM,
                domain="tech_selection",
            ),
        ]
        candidates = generator.generate(patterns)
        assert candidates[0].confidence > candidates[1].confidence


class TestRuleCandidateSerialization:
    """Test RuleCandidate to_dict serialization"""

    def test_to_dict(self):
        candidate = RuleCandidate(
            trigger="技术选型",
            action="避免使用 Java",
            rule_type="avoid",
            override=True,
            derived_from="auto_promotion",
            source_memories=["c1", "c2", "c3"],
            confidence=0.7,
            pattern_type="avoidance",
            domain="tech_selection",
            explanation="You've corrected about Java 3 times.",
        )
        d = candidate.to_dict()
        assert d["trigger"] == "技术选型"
        assert d["rule_type"] == "avoid"
        assert d["confidence"] == 0.7
        assert d["derived_from"] == "auto_promotion"


class TestIntegration:
    """Integration test: detect patterns → generate candidates → verify"""

    def test_full_pipeline_correction(self, detector, generator):
        memories = [
            _make_memory("c1", "correction", "不要用Java做后端开发"),
            _make_memory("c2", "correction", "Java框架性能不好"),
            _make_memory("c3", "correction", "别用Java，用Python替代"),
            _make_memory("d1", "decision", "选择Python做后端"),
        ]
        patterns = detector.detect_patterns(memories)
        candidates = generator.generate(patterns)
        assert len(candidates) >= 1
        avoidance = [c for c in candidates if c.rule_type == "avoid"]
        assert len(avoidance) >= 1
        assert avoidance[0].source_memories
        assert avoidance[0].derived_from == "auto_promotion"

    def test_full_pipeline_preference(self, detector, generator):
        memories = [
            _make_memory("p1", "user_preference", "偏好PostgreSQL数据库"),
            _make_memory("p2", "user_preference", "喜欢用PostgreSQL做存储"),
            _make_memory("p3", "user_preference", "PostgreSQL是最优选择"),
        ]
        patterns = detector.detect_patterns(memories)
        candidates = generator.generate(patterns)
        assert len(candidates) >= 1
        pref = [c for c in candidates if c.rule_type == "prefer"]
        assert len(pref) >= 1

    def test_full_pipeline_mixed_types(self, detector, generator):
        memories = [
            _make_memory("c1", "correction", "不要用Java做后端"),
            _make_memory("c2", "correction", "Java不适合"),
            _make_memory("c3", "correction", "别选Java"),
            _make_memory("p1", "user_preference", "偏好Python技术栈"),
            _make_memory("p2", "user_preference", "喜欢Python开发"),
            _make_memory("p3", "user_preference", "Python是好选择"),
        ]
        patterns = detector.detect_patterns(memories)
        candidates = generator.generate(patterns)
        assert len(candidates) >= 2
        rule_types = {c.rule_type for c in candidates}
        assert "avoid" in rule_types
        assert "prefer" in rule_types

    def test_min_occurrences_configurable(self):
        detector2 = PatternDetector(min_occurrences=2)
        memories = [
            _make_memory("c1", "correction", "不要用Java"),
            _make_memory("c2", "correction", "Java不好"),
        ]
        patterns = detector2.detect_patterns(memories)
        assert len(patterns) >= 1
