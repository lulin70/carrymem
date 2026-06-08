"""PatternGroup: manages a named collection of related patterns."""

from typing import Dict, List, Optional

from carrymem.patterns.base import Pattern, PatternMatch, PatternType


class PatternGroup:
    """A named group of related patterns (e.g. "noise_ack", "preference_strong").

    Supports language-aware filtering and first-match / all-match semantics.
    """

    def __init__(self, name: str, pattern_type: PatternType):
        self.name = name
        self.pattern_type = pattern_type
        self._patterns: Dict[str, Pattern] = {}
        # Language index: language -> list of patterns
        self._lang_index: Dict[str, List[Pattern]] = {}

    def add_pattern(self, pattern: Pattern) -> None:
        """Add a pattern to this group."""
        key = pattern.full_name
        self._patterns[key] = pattern
        self._lang_index.setdefault(pattern.language, []).append(pattern)

    def get_patterns(self, language: Optional[str] = None) -> List[Pattern]:
        """Return patterns, optionally filtered by language."""
        if language is None:
            return list(self._patterns.values())
        return self._lang_index.get(language, [])

    def match_first(
        self,
        message: str,
        language: Optional[str] = None,
    ) -> Optional[PatternMatch]:
        """Return the first matching PatternMatch, or None."""
        for pattern in self.get_patterns(language):
            m = pattern.try_match(message)
            if m:
                return PatternMatch(
                    pattern_name=pattern.full_name,
                    group_name=self.name,
                    pattern_type=pattern.pattern_type,
                    language=pattern.language,
                    confidence=pattern.confidence,
                    matched_text=m.group(0),
                    match_obj=m,
                )
        return None

    def match_all(
        self,
        message: str,
        language: Optional[str] = None,
    ) -> List[PatternMatch]:
        """Return all matching PatternMatches."""
        results = []
        for pattern in self.get_patterns(language):
            m = pattern.try_match(message)
            if m:
                results.append(
                    PatternMatch(
                        pattern_name=pattern.full_name,
                        group_name=self.name,
                        pattern_type=pattern.pattern_type,
                        language=pattern.language,
                        confidence=pattern.confidence,
                        matched_text=m.group(0),
                        match_obj=m,
                    )
                )
        return results

    def any_match(self, message: str, language: Optional[str] = None) -> bool:
        """Return True if any pattern matches (fast boolean check)."""
        for pattern in self.get_patterns(language):
            if pattern.try_match(message):
                return True
        return False

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    @property
    def languages(self) -> List[str]:
        return list(self._lang_index.keys())

    def __repr__(self) -> str:
        return (
            f"PatternGroup(name={self.name!r}, type={self.pattern_type.value}, "
            f"patterns={self.pattern_count}, langs={self.languages})"
        )
