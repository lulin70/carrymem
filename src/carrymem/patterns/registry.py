"""PatternRegistry: central registry for all pattern groups."""

from typing import Dict, List, Optional

from carrymem.patterns.base import Pattern, PatternMatch
from carrymem.patterns.group import PatternGroup


class PatternRegistry:
    """Central registry that manages all PatternGroups.

    Provides language-indexed lookup for fast matching across groups.
    """

    def __init__(self):
        self._groups: Dict[str, PatternGroup] = {}
        # language -> group_name -> list[Pattern]
        self._lang_index: Dict[str, Dict[str, List[Pattern]]] = {}

    def register_group(self, group: PatternGroup) -> None:
        """Register a pattern group and rebuild language index for it."""
        self._groups[group.name] = group
        for lang, patterns in group._lang_index.items():
            self._lang_index.setdefault(lang, {})[group.name] = patterns

    def get_group(self, name: str) -> Optional[PatternGroup]:
        """Return a group by name, or None."""
        return self._groups.get(name)

    @property
    def group_names(self) -> List[str]:
        """Names of all registered pattern groups."""
        return list(self._groups.keys())

    def match_by_group(
        self,
        group_name: str,
        message: str,
        language: Optional[str] = None,
    ) -> Optional[PatternMatch]:
        """Match in a specific group."""
        group = self._groups.get(group_name)
        if group is None:
            return None
        return group.match_first(message, language)

    def any_match_by_group(
        self,
        group_name: str,
        message: str,
        language: Optional[str] = None,
    ) -> bool:
        """Fast boolean check in a specific group."""
        group = self._groups.get(group_name)
        if group is None:
            return False
        return group.any_match(message, language)

    def match_all_groups(
        self,
        message: str,
        language: Optional[str] = None,
    ) -> List[PatternMatch]:
        """Match against all groups, return all matches."""
        results = []
        for group in self._groups.values():
            results.extend(group.match_all(message, language))
        return results

    def match_groups(
        self,
        group_names: List[str],
        message: str,
        language: Optional[str] = None,
    ) -> Optional[PatternMatch]:
        """Match against a list of group names, return first match."""
        for name in group_names:
            group = self._groups.get(name)
            if group is None:
                continue
            m = group.match_first(message, language)
            if m:
                return m
        return None

    def any_match_groups(
        self,
        group_names: List[str],
        message: str,
        language: Optional[str] = None,
    ) -> bool:
        """Fast boolean check across multiple groups."""
        for name in group_names:
            group = self._groups.get(name)
            if group is None:
                continue
            if group.any_match(message, language):
                return True
        return False

    def get_patterns_by_language(self, language: str) -> Dict[str, List[Pattern]]:
        """Return {group_name: [patterns]} for a given language."""
        return self._lang_index.get(language, {})

    def __repr__(self) -> str:
        return f"PatternRegistry(groups={len(self._groups)}, langs={list(self._lang_index.keys())})"
