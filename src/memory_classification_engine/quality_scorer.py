"""Memory Quality Scoring Module for CarryMem.

Provides algorithms to evaluate the quality and reliability of stored memories
based on multiple factors including confidence, access frequency, freshness,
and source reliability.

v0.4.1: Initial implementation
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from .adapters.base import StoredMemory


class MemoryQualityScorer:
    """Calculate quality scores for memories to help with ranking and filtering.
    
    The quality score is a weighted combination of:
    - Confidence (40%): How confident the classification was
    - Access frequency (30%): How often the memory has been accessed
    - Freshness (20%): How recent the memory is
    - Source reliability (10%): How reliable the source layer is
    
    Example:
        scorer = MemoryQualityScorer()
        score = scorer.score(memory)
        print(f"Quality: {score:.3f}")  # 0.0 to 1.0
    """
    
    # Default weights for quality factors
    DEFAULT_WEIGHTS = {
        'confidence': 0.40,
        'access_frequency': 0.30,
        'freshness': 0.20,
        'source_reliability': 0.10,
    }
    
    # Source layer reliability scores
    SOURCE_RELIABILITY = {
        'declaration': 1.0,    # User explicitly declared
        'rule': 0.9,           # Rule-based classification
        'pattern': 0.7,        # Pattern matching
        'semantic': 0.5,       # Semantic inference
        'unknown': 0.3,        # Unknown source
    }
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        max_access_count: int = 10,
        max_age_days: int = 365,
    ):
        """Initialize the quality scorer.
        
        Args:
            weights: Custom weights for quality factors (must sum to 1.0)
            max_access_count: Maximum access count for normalization
            max_age_days: Maximum age in days for freshness calculation
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.max_access_count = max_access_count
        self.max_age_days = max_age_days
        
        # Validate weights
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight:.3f}"
            )
    
    def score(self, memory: StoredMemory) -> float:
        """Calculate the overall quality score for a memory.
        
        Args:
            memory: The stored memory to score
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        confidence_score = self._score_confidence(memory)
        access_score = self._score_access_frequency(memory)
        freshness_score = self._score_freshness(memory)
        source_score = self._score_source_reliability(memory)
        
        total_score = (
            confidence_score * self.weights['confidence'] +
            access_score * self.weights['access_frequency'] +
            freshness_score * self.weights['freshness'] +
            source_score * self.weights['source_reliability']
        )
        
        return round(total_score, 3)
    
    def score_with_breakdown(self, memory: StoredMemory) -> Dict[str, float]:
        """Calculate quality score with detailed breakdown.
        
        Args:
            memory: The stored memory to score
            
        Returns:
            Dictionary with overall score and component scores
        """
        confidence_score = self._score_confidence(memory)
        access_score = self._score_access_frequency(memory)
        freshness_score = self._score_freshness(memory)
        source_score = self._score_source_reliability(memory)
        
        total_score = (
            confidence_score * self.weights['confidence'] +
            access_score * self.weights['access_frequency'] +
            freshness_score * self.weights['freshness'] +
            source_score * self.weights['source_reliability']
        )
        
        return {
            'overall': round(total_score, 3),
            'confidence': round(confidence_score, 3),
            'access_frequency': round(access_score, 3),
            'freshness': round(freshness_score, 3),
            'source_reliability': round(source_score, 3),
            'weighted': {
                'confidence': round(confidence_score * self.weights['confidence'], 3),
                'access_frequency': round(access_score * self.weights['access_frequency'], 3),
                'freshness': round(freshness_score * self.weights['freshness'], 3),
                'source_reliability': round(source_score * self.weights['source_reliability'], 3),
            }
        }
    
    def score_batch(self, memories: List[StoredMemory]) -> List[Dict[str, Any]]:
        """Score multiple memories and return sorted by quality.
        
        Args:
            memories: List of memories to score
            
        Returns:
            List of dicts with memory and score, sorted by score descending
        """
        scored = []
        for memory in memories:
            score = self.score(memory)
            scored.append({
                'memory': memory,
                'score': score,
                'storage_key': memory.storage_key,
            })
        
        # Sort by score descending
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored
    
    def _score_confidence(self, memory: StoredMemory) -> float:
        """Score based on classification confidence.
        
        Args:
            memory: The memory to score
            
        Returns:
            Score between 0.0 and 1.0
        """
        # Confidence is already 0.0 to 1.0
        return max(0.0, min(1.0, memory.confidence))
    
    def _score_access_frequency(self, memory: StoredMemory) -> float:
        """Score based on how often the memory has been accessed.
        
        Args:
            memory: The memory to score
            
        Returns:
            Score between 0.0 and 1.0
        """
        # Normalize access count to 0-1 range
        access_count = memory.access_count or 0
        normalized = min(access_count / self.max_access_count, 1.0)
        return normalized
    
    def _score_freshness(self, memory: StoredMemory) -> float:
        """Score based on how recent the memory is.
        
        Args:
            memory: The memory to score
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not memory.created_at:
            return 0.5  # Default for unknown age
        
        now = datetime.now(timezone.utc)
        if memory.created_at and memory.created_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        age = now - memory.created_at
        age_days = age.total_seconds() / 86400
        
        # Linear decay: 1.0 for new, 0.0 for max_age_days old
        freshness = max(0.0, 1.0 - (age_days / self.max_age_days))
        return freshness
    
    def _score_source_reliability(self, memory: StoredMemory) -> float:
        """Score based on the reliability of the source layer.
        
        Args:
            memory: The memory to score
            
        Returns:
            Score between 0.0 and 1.0
        """
        source = memory.source_layer or 'unknown'
        return self.SOURCE_RELIABILITY.get(source, 0.3)
    
    def get_quality_tier(self, score: float) -> str:
        """Convert a quality score to a tier label.
        
        Args:
            score: Quality score (0.0 to 1.0)
            
        Returns:
            Tier label: 'excellent', 'good', 'fair', 'poor'
        """
        if score >= 0.8:
            return 'excellent'
        elif score >= 0.6:
            return 'good'
        elif score >= 0.4:
            return 'fair'
        else:
            return 'poor'
    
    def filter_by_quality(
        self,
        memories: List[StoredMemory],
        min_score: float = 0.5,
    ) -> List[StoredMemory]:
        """Filter memories by minimum quality score.
        
        Args:
            memories: List of memories to filter
            min_score: Minimum quality score (0.0 to 1.0)
            
        Returns:
            Filtered list of memories meeting the quality threshold
        """
        filtered = []
        for memory in memories:
            score = self.score(memory)
            if score >= min_score:
                filtered.append(memory)
        
        return filtered
    
    def rank_memories(
        self,
        memories: List[StoredMemory],
        limit: Optional[int] = None,
    ) -> List[StoredMemory]:
        """Rank memories by quality score.
        
        Args:
            memories: List of memories to rank
            limit: Optional limit on number of results
            
        Returns:
            List of memories sorted by quality score (descending)
        """
        scored = self.score_batch(memories)
        ranked = [item['memory'] for item in scored]
        
        if limit:
            ranked = ranked[:limit]
        
        return ranked


class QualityAnalyzer:
    """Analyze quality patterns across a collection of memories.
    
    Example:
        analyzer = QualityAnalyzer()
        analysis = analyzer.analyze(memories)
        print(f"Average quality: {analysis['average_score']:.3f}")
    """
    
    def __init__(self, scorer: Optional[MemoryQualityScorer] = None):
        """Initialize the analyzer.
        
        Args:
            scorer: Optional custom quality scorer
        """
        self.scorer = scorer or MemoryQualityScorer()
    
    def analyze(self, memories: List[StoredMemory]) -> Dict[str, Any]:
        """Analyze quality patterns across memories.
        
        Args:
            memories: List of memories to analyze
            
        Returns:
            Dictionary with analysis results
        """
        if not memories:
            return {
                'count': 0,
                'average_score': 0.0,
                'median_score': 0.0,
                'min_score': 0.0,
                'max_score': 0.0,
                'by_tier': {},
                'by_type': {},
                'by_source': {},
            }
        
        scores = [self.scorer.score(m) for m in memories]
        scores.sort()
        
        # Calculate statistics
        count = len(scores)
        average = sum(scores) / count
        median = scores[count // 2] if count % 2 == 1 else (scores[count // 2 - 1] + scores[count // 2]) / 2
        min_score = min(scores)
        max_score = max(scores)
        
        # Group by tier
        by_tier = {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0}
        for score in scores:
            tier = self.scorer.get_quality_tier(score)
            by_tier[tier] += 1
        
        # Group by memory type
        by_type: Dict[str, List[float]] = {}
        for memory in memories:
            mem_type = memory.type
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(self.scorer.score(memory))
        
        type_averages = {
            t: round(sum(scores) / len(scores), 3)
            for t, scores in by_type.items()
        }
        
        # Group by source layer
        by_source: Dict[str, List[float]] = {}
        for memory in memories:
            source = memory.source_layer or 'unknown'
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(self.scorer.score(memory))
        
        source_averages = {
            s: round(sum(scores) / len(scores), 3)
            for s, scores in by_source.items()
        }
        
        return {
            'count': count,
            'average_score': round(average, 3),
            'median_score': round(median, 3),
            'min_score': round(min_score, 3),
            'max_score': round(max_score, 3),
            'by_tier': by_tier,
            'by_type': type_averages,
            'by_source': source_averages,
        }
    
    def identify_low_quality(
        self,
        memories: List[StoredMemory],
        threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Identify low-quality memories that may need review or cleanup.
        
        Args:
            memories: List of memories to check
            threshold: Quality threshold below which memories are flagged
            
        Returns:
            List of dicts with memory info and reasons for low quality
        """
        low_quality = []
        
        for memory in memories:
            breakdown = self.scorer.score_with_breakdown(memory)
            
            if breakdown['overall'] < threshold:
                reasons = []
                
                if breakdown['confidence'] < 0.5:
                    reasons.append(f"Low confidence ({breakdown['confidence']:.2f})")
                
                if breakdown['access_frequency'] < 0.2:
                    reasons.append(f"Rarely accessed ({memory.access_count} times)")
                
                if breakdown['freshness'] < 0.3:
                    now = datetime.now(timezone.utc)
                    created = memory.created_at
                    if created and created.tzinfo is None:
                        now = now.replace(tzinfo=None)
                    age_days = (now - created).days if created else 0
                    reasons.append(f"Old ({age_days} days)")
                
                if breakdown['source_reliability'] < 0.5:
                    reasons.append(f"Unreliable source ({memory.source_layer})")
                
                low_quality.append({
                    'memory': memory,
                    'storage_key': memory.storage_key,
                    'score': breakdown['overall'],
                    'reasons': reasons,
                    'breakdown': breakdown,
                })
        
        # Sort by score ascending (worst first)
        low_quality.sort(key=lambda x: x['score'])
        return low_quality
