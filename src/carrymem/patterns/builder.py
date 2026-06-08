"""PatternBuilder: fluent API for constructing and registering pattern groups."""

from typing import List, Tuple, Optional
from carrymem.patterns.base import (
    Pattern,
    PatternType,
    NoiseCategory,
    NoisePattern,
    PreferencePattern,
    CorrectionPattern,
    FactPattern,
    TaskPattern,
    DecisionPattern,
    RelationshipPattern,
    SentimentPattern,
    LocationPattern,
)
from carrymem.patterns.group import PatternGroup
from carrymem.patterns.registry import PatternRegistry


class PatternBuilder:
    """Fluent builder for creating PatternGroups and registering them.

    Usage::

        registry = PatternRegistry()
        builder = PatternBuilder(registry)

        (builder
            .create_group("noise_ack", PatternType.NOISE)
            .set_language("en")
            .add_noise("ok", r"^ok\\.?$", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE)
            .add_noise("sure", r"^sure\\.?$", NoiseCategory.ACKNOWLEDGMENT, flags=re.IGNORECASE)
            .set_language("zh")
            .add_noise("good", r"^好的[。.]?$", NoiseCategory.ACKNOWLEDGMENT)
            .register())

        # registry now has the "noise_ack" group
    """

    def __init__(self, registry: PatternRegistry):
        self._registry = registry
        self._current_group: Optional[PatternGroup] = None
        self._current_language: str = "en"

    def create_group(self, name: str, pattern_type: PatternType) -> "PatternBuilder":
        """Start a new group (replaces any unregistered group)."""
        self._current_group = PatternGroup(name, pattern_type)
        return self

    def set_language(self, language: str) -> "PatternBuilder":
        """Set the current language for subsequent add_* calls."""
        self._current_language = language
        return self

    def _require_group(self) -> PatternGroup:
        if self._current_group is None:
            raise ValueError("Must call create_group() before adding patterns")
        return self._current_group

    # ---- Noise patterns ----

    def add_noise(
        self,
        name: str,
        regex: str,
        category: NoiseCategory,
        confidence: float = 0.9,
        flags: int = 0,
        match_method: str = "match",
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(NoisePattern(
            name=name, regex_pattern=regex, language=self._current_language,
            category=category, confidence=confidence, flags=flags,
            match_method=match_method,
        ))
        return self

    def add_noise_batch(
        self,
        patterns: List[Tuple[str, str]],
        category: NoiseCategory,
        confidence: float = 0.9,
        flags: int = 0,
        match_method: str = "match",
    ) -> "PatternBuilder":
        """Add multiple noise patterns at once: [(name, regex), ...]."""
        for name, regex in patterns:
            self.add_noise(name, regex, category, confidence, flags, match_method)
        return self

    # ---- Preference patterns ----

    def add_preference(
        self,
        name: str,
        regex: str,
        strength: str = "medium",
        confidence: float = 0.75,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(PreferencePattern(
            name=name, regex_pattern=regex, language=self._current_language,
            strength=strength, confidence=confidence, flags=flags,
        ))
        return self

    def add_preference_batch(
        self,
        patterns: List[Tuple[str, str, str]],
        confidence: float = 0.75,
        flags: int = 0,
    ) -> "PatternBuilder":
        """Add multiple preference patterns: [(name, regex, strength), ...]."""
        for name, regex, strength in patterns:
            self.add_preference(name, regex, strength, confidence, flags)
        return self

    # ---- Correction patterns ----

    def add_correction(
        self,
        name: str,
        regex: str,
        tier: int = 1,
        confidence: float = 0.85,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(CorrectionPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            tier=tier, confidence=confidence, flags=flags,
        ))
        return self

    def add_correction_batch(
        self,
        patterns: List[Tuple[str, str, int]],
        confidence: float = 0.85,
        flags: int = 0,
    ) -> "PatternBuilder":
        """Add multiple correction patterns: [(name, regex, tier), ...]."""
        for name, regex, tier in patterns:
            self.add_correction(name, regex, tier, confidence, flags)
        return self

    # ---- Fact patterns ----

    def add_fact(
        self,
        name: str,
        regex: str,
        sub_type: str = "general",
        confidence: float = 0.7,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(FactPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            sub_type=sub_type, confidence=confidence, flags=flags,
        ))
        return self

    def add_fact_batch(
        self,
        patterns: List[Tuple[str, str, str]],
        confidence: float = 0.7,
        flags: int = 0,
    ) -> "PatternBuilder":
        """Add multiple fact patterns: [(name, regex, sub_type), ...]."""
        for name, regex, sub_type in patterns:
            self.add_fact(name, regex, sub_type, confidence, flags)
        return self

    # ---- Task patterns ----

    def add_task(
        self,
        name: str,
        regex: str,
        sub_type: str = "structured",
        confidence: float = 0.75,
        flags: int = 0,
        match_method: str = "search",
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(TaskPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            sub_type=sub_type, confidence=confidence, flags=flags,
            match_method=match_method,
        ))
        return self

    def add_task_batch(
        self,
        patterns: List[Tuple[str, str, str]],
        confidence: float = 0.75,
        flags: int = 0,
        match_method: str = "search",
    ) -> "PatternBuilder":
        """Add multiple task patterns: [(name, regex, sub_type), ...]."""
        for name, regex, sub_type in patterns:
            self.add_task(name, regex, sub_type, confidence, flags, match_method)
        return self

    # ---- Decision patterns ----

    def add_decision(
        self,
        name: str,
        regex: str,
        strength: str = "strong",
        confidence: float = 0.75,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(DecisionPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            strength=strength, confidence=confidence, flags=flags,
        ))
        return self

    def add_decision_batch(
        self,
        patterns: List[Tuple[str, str, str]],
        confidence: float = 0.75,
        flags: int = 0,
    ) -> "PatternBuilder":
        """Add multiple decision patterns: [(name, regex, strength), ...]."""
        for name, regex, strength in patterns:
            self.add_decision(name, regex, strength, confidence, flags)
        return self

    # ---- Relationship patterns ----

    def add_relationship(
        self,
        name: str,
        regex: str,
        sub_type: str = "role",
        confidence: float = 0.75,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(RelationshipPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            sub_type=sub_type, confidence=confidence, flags=flags,
        ))
        return self

    def add_relationship_batch(
        self,
        patterns: List[Tuple[str, str, str]],
        confidence: float = 0.75,
        flags: int = 0,
    ) -> "PatternBuilder":
        """Add multiple relationship patterns: [(name, regex, sub_type), ...]."""
        for name, regex, sub_type in patterns:
            self.add_relationship(name, regex, sub_type, confidence, flags)
        return self

    # ---- Sentiment patterns ----

    def add_sentiment(
        self,
        name: str,
        regex: str,
        sub_type: str = "emotion",
        confidence: float = 0.8,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(SentimentPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            sub_type=sub_type, confidence=confidence, flags=flags,
        ))
        return self

    def add_sentiment_batch(
        self,
        patterns: List[Tuple[str, str, str]],
        confidence: float = 0.8,
        flags: int = 0,
    ) -> "PatternBuilder":
        """Add multiple sentiment patterns: [(name, regex, sub_type), ...]."""
        for name, regex, sub_type in patterns:
            self.add_sentiment(name, regex, sub_type, confidence, flags)
        return self

    # ---- Location patterns ----

    def add_location(
        self,
        name: str,
        regex: str,
        confidence: float = 0.7,
        flags: int = 0,
    ) -> "PatternBuilder":
        group = self._require_group()
        group.add_pattern(LocationPattern(
            name=name, regex_pattern=regex, language=self._current_language,
            confidence=confidence, flags=flags,
        ))
        return self

    # ---- Generic pattern ----

    def add_pattern(self, pattern: Pattern) -> "PatternBuilder":
        """Add an already-constructed Pattern object."""
        group = self._require_group()
        group.add_pattern(pattern)
        return self

    # ---- Registration ----

    def register(self) -> "PatternBuilder":
        """Register the current group into the registry and reset state."""
        if self._current_group is not None:
            self._registry.register_group(self._current_group)
            self._current_group = None
        return self

    def build(self) -> PatternRegistry:
        """Register any pending group and return the registry."""
        self.register()
        return self._registry
