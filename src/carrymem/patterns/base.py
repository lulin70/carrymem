"""Base classes and enums for the pattern management system."""

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional


class PatternType(Enum):
    """Top-level pattern category."""

    NOISE = "noise"
    PREFERENCE = "preference"
    CORRECTION = "correction"
    FACT = "fact"
    TASK = "task"
    DECISION = "decision"
    RELATIONSHIP = "relationship"
    LOCATION = "location"
    SENTIMENT = "sentiment"


class NoiseCategory(Enum):
    """Sub-category for noise patterns."""

    ACKNOWLEDGMENT = "acknowledgment"
    CHITCHAT = "chitchat"
    COMMAND = "command"
    QUESTION = "question"
    INSTRUCTION = "instruction"
    ADVERSARIAL = "adversarial"
    FACT_INDICATOR = "fact_indicator"
    WORKFLOW = "workflow"


class PatternMatch:
    """Result of a successful pattern match."""

    __slots__ = (
        "pattern_name",
        "group_name",
        "pattern_type",
        "language",
        "confidence",
        "matched_text",
        "match_obj",
        "extra",
    )

    def __init__(
        self,
        pattern_name: str,
        group_name: str,
        pattern_type: PatternType,
        language: str,
        confidence: float,
        matched_text: str,
        match_obj: Optional[re.Match] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.pattern_name = pattern_name
        self.group_name = group_name
        self.pattern_type = pattern_type
        self.language = language
        self.confidence = confidence
        self.matched_text = matched_text
        self.match_obj = match_obj
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dictionary."""
        d = {
            "pattern_name": self.pattern_name,
            "group_name": self.group_name,
            "pattern_type": self.pattern_type.value,
            "language": self.language,
            "confidence": self.confidence,
            "matched_text": self.matched_text,
        }
        d.update(self.extra)
        return d


class Pattern(ABC):
    """Base class for a single compiled regex pattern with metadata."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        pattern_type: PatternType,
        confidence: float = 0.8,
        flags: int = 0,
        match_method: str = "search",
    ):
        """Initialize a pattern.

        Args:
            name: Unique name within its group (e.g. "ok", "got_it").
            regex_pattern: Raw regex string.
            language: Language code (e.g. "en", "zh", "ja").
            pattern_type: The PatternType enum value.
            confidence: Default confidence when this pattern matches.
            flags: re.compile flags (combine with |). IGNORECASE is common.
            match_method: "match" for re.match, "search" for re.search.
        """
        self.name = name
        self.language = language
        self.pattern_type = pattern_type
        self.confidence = confidence
        self.match_method = match_method
        self._regex_str = regex_pattern
        self._flags = flags
        self.regex = re.compile(regex_pattern, flags)

    def match(self, message: str) -> Optional[re.Match]:
        """Match against message start (re.match)."""
        return self.regex.match(message)

    def search(self, message: str) -> Optional[re.Match]:
        """Search anywhere in message (re.search)."""
        return self.regex.search(message)

    def try_match(self, message: str) -> Optional[re.Match]:
        """Use the configured match_method (match or search)."""
        if self.match_method == "match":
            return self.match(message)
        return self.search(message)

    @property
    def full_name(self) -> str:
        """Return a globally unique name combining language and name."""
        return f"{self.language}_{self.name}"

    @abstractmethod
    def get_description(self) -> str:
        """Return a human-readable description of this pattern."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.full_name!r}, type={self.pattern_type.value})"


class NoisePattern(Pattern):
    """Noise detection pattern (acknowledgment, chitchat, command, etc.)."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        category: NoiseCategory,
        confidence: float = 0.9,
        flags: int = 0,
        match_method: str = "match",
    ):
        super().__init__(name, regex_pattern, language, PatternType.NOISE, confidence, flags, match_method)
        self.category = category

    def get_description(self) -> str:
        """Return a human-readable description of this noise pattern."""
        return f"Noise/{self.category.value} [{self.language}]"


class PreferencePattern(Pattern):
    """User preference pattern."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        strength: str = "medium",
        confidence: float = 0.75,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.PREFERENCE, confidence, flags, "search")
        self.strength = strength

    def get_description(self) -> str:
        """Return a human-readable description of this preference pattern."""
        return f"Preference/{self.strength} [{self.language}]"


class CorrectionPattern(Pattern):
    """Correction pattern (explicit or structural)."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        tier: int = 1,
        confidence: float = 0.85,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.CORRECTION, confidence, flags, "search")
        self.tier = tier

    def get_description(self) -> str:
        """Return a human-readable description of this correction pattern."""
        return f"Correction/T{self.tier} [{self.language}]"


class FactPattern(Pattern):
    """Fact declaration pattern."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        sub_type: str = "general",
        confidence: float = 0.7,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.FACT, confidence, flags, "search")
        self.sub_type = sub_type

    def get_description(self) -> str:
        """Return a human-readable description of this fact pattern."""
        return f"Fact/{self.sub_type} [{self.language}]"


class TaskPattern(Pattern):
    """Task pattern (structured, workflow, habit)."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        sub_type: str = "structured",
        confidence: float = 0.75,
        flags: int = 0,
        match_method: str = "search",
    ):
        super().__init__(name, regex_pattern, language, PatternType.TASK, confidence, flags, match_method)
        self.sub_type = sub_type

    def get_description(self) -> str:
        """Return a human-readable description of this task pattern."""
        return f"Task/{self.sub_type} [{self.language}]"


class DecisionPattern(Pattern):
    """Decision pattern."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        strength: str = "strong",
        confidence: float = 0.75,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.DECISION, confidence, flags, "search")
        self.strength = strength

    def get_description(self) -> str:
        """Return a human-readable description of this decision pattern."""
        return f"Decision/{self.strength} [{self.language}]"


class RelationshipPattern(Pattern):
    """Relationship pattern (role, dependency)."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        sub_type: str = "role",
        confidence: float = 0.75,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.RELATIONSHIP, confidence, flags, "search")
        self.sub_type = sub_type

    def get_description(self) -> str:
        """Return a human-readable description of this relationship pattern."""
        return f"Relationship/{self.sub_type} [{self.language}]"


class SentimentPattern(Pattern):
    """Sentiment pattern."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        sub_type: str = "emotion",
        confidence: float = 0.8,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.SENTIMENT, confidence, flags, "search")
        self.sub_type = sub_type

    def get_description(self) -> str:
        """Return a human-readable description of this sentiment pattern."""
        return f"Sentiment/{self.sub_type} [{self.language}]"


class LocationPattern(Pattern):
    """Location pattern."""

    def __init__(
        self,
        name: str,
        regex_pattern: str,
        language: str,
        confidence: float = 0.7,
        flags: int = 0,
    ):
        super().__init__(name, regex_pattern, language, PatternType.LOCATION, confidence, flags, "search")
        self.sub_type = "location"

    def get_description(self) -> str:
        """Return a human-readable description of this location pattern."""
        return f"Location [{self.language}]"
