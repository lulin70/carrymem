"""Result Merger — Multi-source recall result fusion and ranking.

Merges results from:
- Original FTS5 exact match (high weight)
- Semantic expansion search (adjusted weight)
- Spell-corrected query search (medium weight)

Provides:
- Deduplication by storage_key
- Relevance scoring based on match source
- Rank-ordered final result list
"""

from typing import Any, Dict, List, Optional


class ResultMerger:
    """Merge and rank multi-source recall results.

    Usage:
        merger = ResultMerger()
        merged = merger.merge(
            original_results=[...],  # From FTS5 exact match
            expanded_results=[...],   # From semantic expansion
            query="数据库",
            limit=20
        )
    """

    # Weight configuration for different match sources
    WEIGHTS = {
        "exact_fts": 1.0,       # FTS5 exact match (original query)
        "synonym": 0.85,         # Synonym expansion match
        "spell_corrected": 0.75, # Spell-corrected query match
        "cross_language": 0.8,   # Cross-language translation match
        "like_fallback": 0.6,    # LIKE fallback (CJK)
    }

    # Minimum relevance threshold to include in results
    MIN_RELEVANCE = 0.3

    def __init__(
        self,
        min_relevance: float = MIN_RELEVANCE,
        custom_weights: Optional[Dict[str, float]] = None,
    ):
        self._min_relevance = min_relevance
        self._weights = {**self.WEIGHTS}
        if custom_weights:
            self._weights.update(custom_weights)

    def merge(
        self,
        original_results: List[Any],
        expanded_results: List[Any],
        query: str,
        limit: int = 20,
        source: str = "synonym",
    ) -> List[Any]:
        """Merge original and expanded results with deduplication and ranking.

        Args:
            original_results: Results from initial FTS5/LIKE search (StoredMemory or dict)
            expanded_results: Results from semantic expansion re-search (StoredMemory or dict)
            query: The original user query (for relevance calculation)
            limit: Maximum number of results to return
            source: Source type of expanded results ("synonym", "spell_corrected", etc.)

        Returns:
            Merged, deduplicated, ranked list of results (StoredMemory or dict)
        """
        seen_ids: set = set()
        merged: List[Any] = []

        # Phase 1: Add original results (highest priority)
        for result in original_results:
            result_id = self._get_result_id(result)
            if result_id and result_id not in seen_ids:
                self._set_metadata(result, "_relevance_score", self._weights.get("exact_fts", 1.0))
                self._set_metadata(result, "_match_source", "exact_fts")
                merged.append(result)
                seen_ids.add(result_id)

        # Phase 2: Add expanded results (with adjusted weights)
        source_weight = self._weights.get(source, 0.7)

        for result in expanded_results:
            result_id = self._get_result_id(result)
            if result_id and result_id not in seen_ids:
                relevance = self._calculate_relevance(result, query, source_weight)

                if relevance >= self._min_relevance:
                    self._set_metadata(result, "_relevance_score", relevance)
                    self._set_metadata(result, "_match_source", source)
                    merged.append(result)
                    seen_ids.add(result_id)

        # Phase 3: Sort by relevance score (descending), then by confidence
        def get_sort_key(item):
            if isinstance(item, dict):
                return (-item.get("_relevance_score", 0), -item.get("confidence", 0))
            else:
                return (
                    -getattr(item, "_relevance_score", 0),
                    -getattr(item, "confidence", 0),
                )

        merged.sort(key=get_sort_key)

        return merged[:limit]

    def _set_metadata(self, obj, key: str, value):
        """Set metadata on an object (works with both dicts and objects)."""
        if isinstance(obj, dict):
            obj[key] = value
        else:
            try:
                setattr(obj, key, value)
            except AttributeError:
                obj.__dict__[key] = value

    def _get_result_id(self, result) -> Optional[str]:
        """Extract unique identifier from a result.

        Handles both StoredMemory objects and dicts.
        """
        if result is None:
            return None

        if isinstance(result, dict):
            return result.get("storage_key") or result.get("id")

        # Handle StoredMemory objects or any object with storage_key/id attributes
        if hasattr(result, 'storage_key'):
            return result.storage_key
        if hasattr(result, 'id'):
            return result.id

        return None

    def _calculate_relevance(
        self,
        result,
        query: str,
        base_weight: float,
    ) -> float:
        """Calculate relevance score for an expanded result.

        Factors:
        - Base weight from source type
        - Content overlap with query (simple token matching)
        - Confidence score from storage
        """
        content = ""
        confidence = 0.5

        if isinstance(result, dict):
            content = str(result.get("content", "")) + " " + str(result.get("original_message", ""))
            confidence = result.get("confidence", 0.5)
        elif hasattr(result, 'content'):
            content = str(result.content) or ""
            if hasattr(result, 'metadata') and result.metadata:
                content += " " + str(result.metadata.get("original_message", ""))
            if hasattr(result, 'confidence'):
                confidence = result.confidence

        content_lower = content.lower()
        query_lower = query.lower()

        # Token overlap score
        query_tokens = set(query_lower.split())
        content_tokens = set(content_lower.split())

        if query_tokens:
            overlap = len(query_tokens & content_tokens) / len(query_tokens)
        else:
            overlap = 0.0

        if overlap == 0 and len(content.strip()) > 5:
            # Semantic expansion match with no direct token overlap
            # Use a moderate baseline that won't let irrelevant results through
            # Single-token queries (e.g. "database") are likely concept keywords
            if len(query_tokens) <= 2:
                overlap = 0.45
            else:
                overlap = 0.3

        # Confidence factor (already extracted above)
        confidence_factor = 0.5 + (confidence * 0.5)  # Map 0-1 → 0.5-1.0

        # Final relevance: base * overlap * confidence
        relevance = round(base_weight * overlap * confidence_factor, 4)

        return relevance

    def merge_multiple(
        self,
        results_by_source: Dict[str, List[Dict[str, Any]]],
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Merge results from multiple sources at once.

        Args:
            results_by_source: Dict mapping source name to results list
                e.g., {"exact_fts": [...], "synonym": [...], "spell_corrected": [...]}
            query: Original query string
            limit: Maximum results to return

        Returns:
            Fully merged and ranked results
        """
        seen_ids: set = set()
        all_merged: List[Dict[str, Any]] = []

        # Process each source in order of priority (exact first)
        priority_order = ["exact_fts", "synonym", "spell_corrected", "cross_language", "like_fallback"]

        for source in priority_order:
            if source not in results_by_source:
                continue

            source_weight = self._weights.get(source, 0.7)
            results = results_by_source[source]

            for result in results:
                result_id = self._get_result_id(result)
                if result_id and result_id not in seen_ids:
                    relevance = self._calculate_relevance(result, query, source_weight)

                    if relevance >= self._min_relevance:
                        result["_relevance_score"] = relevance
                        result["_match_source"] = source
                        all_merged.append(result)
                        seen_ids.add(result_id)

        # Sort by relevance
        all_merged.sort(
            key=lambda x: (
                -x.get("_relevance_score", 0),
                -x.get("confidence", 0),
            )
        )

        return all_merged[:limit]
