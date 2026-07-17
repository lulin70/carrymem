"""
CarryMem Rules Engine — Rule Matcher

Business logic for matching scenes to rules using:
- FTS5 full-text search with ranking
- Semantic similarity scoring
- Priority-based ordering (hard rules > soft rules)
- Type-weighted relevance
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..utils.language import has_cjk

_logger = logging.getLogger(__name__)

from .models import Rule


@dataclass
class MatchResult:
    """
    Result of a rule matching operation.

    Attributes:
        rule: The matched Rule object
        score: Relevance score (0.0-1.0) indicating how well the scene matches
        match_type: How the match was found (exact/fts/partial/global)
        matched_text: The text that triggered the match
    """

    rule: "Rule"
    score: float
    match_type: str  # "exact", "fts", "partial", "global"
    matched_text: str

    def __post_init__(self):
        """Validate score range"""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")


class RuleMatcher:
    """
    Matches user scenes to applicable rules.

    Uses a multi-strategy matching approach:
    1. Global rules (trigger="*") always match
    2. Exact trigger matches get highest priority
    3. FTS5 full-text search for semantic matching
    4. Partial string matching as fallback

    Results are ranked by:
    - Match quality (exact > fts > partial)
    - Override status (hard rules ranked higher)
    - Trigger count (frequently used rules ranked higher)

    Usage:
        matcher = RuleMatcher(storage)
        results = matcher.match("帮我做竞品分析")
        for result in results:
            _logger.debug("%s (score: %.2f)", result.rule.summary(), result.score)
    """

    # Score weights for different match types
    MATCH_TYPE_SCORES = {
        "global": 0.6,  # Global rules get moderate base score
        "exact": 1.0,  # Exact trigger match is best
        "fts": 0.8,  # FTS5 semantic match is good
        "partial": 0.5,  # Partial match is acceptable
    }

    # Bonus for hard rules (override=True)
    HARD_RULE_BONUS = 0.1

    # Bonus for frequently triggered rules
    FREQUENCY_BONUS_FACTOR = 0.02  # Per 10 triggers

    def __init__(self, storage):
        """
        Initialize matcher with storage backend.

        Args:
            storage: RuleStorage instance for querying rules
        """
        self.storage = storage

    def match(
        self,
        scene_description: str,
        limit: int = 10,
        scopes: Optional[List[str]] = None,
        context_conditions: Optional[List[str]] = None,
    ) -> List[MatchResult]:
        """
        Find all rules that match a given scene.

        Args:
            scene_description: Natural language description of the current scene/context
            limit: Maximum number of results to return
            scopes: Optional list of scopes to filter (e.g., ["company", "personal"])

        Returns:
            List of MatchResults sorted by relevance score (descending)

        Examples:
            >>> matcher.match("帮我做竞品分析报告")
            [MatchResult(rule=..., score=0.95, match_type='exact', ...)]
            >>> matcher.match("写一个技术方案")
            [MatchResult(rule=..., score=0.72, match_type='fts', ...)]
        """
        if not scene_description or not scene_description.strip():
            return []

        all_active = self.storage.list_all(status="active", limit=1000)

        all_active = [r for r in all_active if not r.is_expired()]

        if context_conditions:
            filtered = []
            for r in all_active:
                if not r.condition:
                    filtered.append(r)
                else:
                    rule_conds = set(self._tokenize(r.condition))
                    match_conds = set(self._tokenize(" ".join(context_conditions)))
                    if rule_conds & match_conds:
                        filtered.append(r)
            all_active = filtered

        if scopes:
            all_active = [r for r in all_active if r.scope in scopes]

        results = []

        global_matches = self._match_global_rules(all_active)
        results.extend(global_matches)

        exact_matches = self._match_exact(scene_description, all_active)
        results.extend(exact_matches)

        if len(exact_matches) < limit:
            fts_limit = (limit - len(results)) * 3 if scopes else (limit - len(results))
            fts_matches = self._match_fts(scene_description, fts_limit)
            fts_matches = [m for m in fts_matches if not m.rule.is_expired()]
            if scopes:
                fts_matches = [m for m in fts_matches if m.rule.scope in scopes]
            results.extend(fts_matches)

        if len(results) < limit:
            partial_matches = self._match_partial(scene_description, limit - len(results), all_active)
            results.extend(partial_matches)

        results = self._deduplicate(results)

        results = [r for r in results if not r.rule.is_expired()]

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:limit]

    def _match_global_rules(self, all_active: Optional[list] = None) -> List[MatchResult]:
        """Find all active global rules"""
        if all_active is None:
            all_active = self.storage.list_all(status="active", limit=1000)
        global_rules = [r for r in all_active if r.trigger == "*"]

        results = []
        for rule in global_rules:
            score = self.MATCH_TYPE_SCORES["global"]
            score = self._apply_bonuses(score, rule)

            results.append(
                MatchResult(
                    rule=rule,
                    score=min(score, 1.0),
                    match_type="global",
                    matched_text="*",
                )
            )

        return results

    def _match_exact(self, scene: str, all_active: Optional[list] = None) -> List[MatchResult]:
        """Find rules with exact trigger match"""
        if all_active is None:
            all_active = self.storage.list_all(status="active", limit=1000)

        results = []
        for rule in all_active:
            if rule.trigger.lower() == scene.lower().strip():
                score = self.MATCH_TYPE_SCORES["exact"]
                score = self._apply_bonuses(score, rule)

                results.append(
                    MatchResult(
                        rule=rule,
                        score=min(score, 1.0),
                        match_type="exact",
                        matched_text=rule.trigger,
                    )
                )

        return results

    def _match_fts(self, scene: str, limit: int) -> List[MatchResult]:
        try:
            fts_results = self.storage.search_with_rank(scene, limit=limit)
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            try:
                matched_rules = self.storage.search(scene, limit=limit)
                fts_results = [(r, 0.0) for r in matched_rules]
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                _logger.warning("FTS5 match failed for scene '%s': %s", scene[:50], e)
                return []

        results = []
        seen_ids = set()

        for rule, rank_score in fts_results:
            if rule.status != "active":
                continue
            if rule.id in seen_ids:
                continue
            seen_ids.add(rule.id)

            if rank_score > 0:
                normalized = min(max(rank_score / 10.0, 0.3), 0.95)
                score = normalized
            else:
                score = self.MATCH_TYPE_SCORES["fts"]
            score = self._apply_bonuses(score, rule)

            results.append(
                MatchResult(
                    rule=rule,
                    score=min(score, 1.0),
                    match_type="fts",
                    matched_text=scene[:50],
                )
            )

        return results

    def _match_partial(self, scene: str, limit: int, all_active: Optional[list] = None) -> List[MatchResult]:
        """Fallback partial string matching"""
        if all_active is None:
            all_active = self.storage.list_all(status="active", limit=1000)

        scene_lower = scene.lower()
        scene_tokens = set(self._tokenize(scene))

        results = []
        seen_ids = set()

        for rule in all_active:
            if rule.id in seen_ids:
                continue

            # Check if trigger is contained in scene or vice versa
            trigger_lower = rule.trigger.lower()

            trigger_tokens = set(self._tokenize(rule.trigger))
            token_overlap = scene_tokens & trigger_tokens

            if (
                trigger_lower in scene_lower
                or scene_lower in trigger_lower
                or len(token_overlap) >= 2
                or (len(token_overlap) >= 1 and any(len(t) >= 2 for t in token_overlap))
            ):
                seen_ids.add(rule.id)

                score = self.MATCH_TYPE_SCORES["partial"]
                score = self._apply_bonuses(score, rule)

                results.append(
                    MatchResult(
                        rule=rule,
                        score=min(score, 1.0),
                        match_type="partial",
                        matched_text=rule.trigger,
                    )
                )

            if len(results) >= limit:
                break

        return results

    def _apply_bonuses(self, base_score: float, rule: "Rule") -> float:
        """
        Apply scoring bonuses based on rule properties.

        Args:
            base_score: Base score from match type
            rule: The rule being scored

        Returns:
            Adjusted score with bonuses applied
        """
        score = base_score

        # Hard rule bonus
        if rule.override:
            score += self.HARD_RULE_BONUS

        # Frequency bonus (rules used more often get slight boost)
        frequency_bonus = min((rule.trigger_count / 10) * self.FREQUENCY_BONUS_FACTOR, 0.1)
        score += frequency_bonus

        # Confidence bonus (auto-classified rules with high confidence)
        confidence_bonus = rule.confidence * 0.05
        score += confidence_bonus

        return score

    _jieba_available = None

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        if has_cjk(text):
            if cls._jieba_available is None:
                try:
                    import jieba

                    cls._jieba_available = True
                except ImportError:
                    cls._jieba_available = False

            if cls._jieba_available:
                import jieba  # noqa: F811

                tokens = list(jieba.cut(text))
                return [t.strip() for t in tokens if t.strip() and len(t.strip()) > 0]
            else:
                tokens = []
                i = 0
                while i < len(text):
                    ch = text[i]
                    if "\u4e00" <= ch <= "\u9fff":
                        tokens.append(ch)
                        if i + 1 < len(text) and "\u4e00" <= text[i + 1] <= "\u9fff":
                            tokens.append(text[i : i + 2])
                        if i + 2 < len(text) and "\u4e00" <= text[i + 2] <= "\u9fff":
                            tokens.append(text[i : i + 3])
                        i += 1
                    elif ch.isalnum():
                        word = []
                        while i < len(text) and (text[i].isalnum() or text[i] == "_"):
                            word.append(text[i])
                            i += 1
                        tokens.append("".join(word).lower())
                    else:
                        i += 1
                return tokens
        else:
            return [w.lower() for w in text.split() if w.strip()]

    def _deduplicate(self, results: List[MatchResult]) -> List[MatchResult]:
        """
        Remove duplicate rules, keeping the one with highest score.
        """
        seen: Dict[str, MatchResult] = {}
        for result in results:
            if result.rule.id not in seen or result.score > seen[result.rule.id].score:
                seen[result.rule.id] = result

        return list(seen.values())

    def get_matching_actions(self, scene_description: str, limit: int = 10) -> List[Tuple[str, str]]:
        """
        Get simplified list of (action, type) tuples for a scene.

        Convenience method for quick access to just the actions.

        Args:
            scene_description: Scene to match against
            limit: Maximum number of actions

        Returns:
            List of (action_string, rule_type) tuples
        """
        matches = self.match(scene_description, limit)
        return [(m.rule.action, m.rule.rule_type) for m in matches]
