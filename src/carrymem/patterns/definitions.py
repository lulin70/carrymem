"""Central registration point: builds the full PatternRegistry from all definition modules."""

from carrymem.patterns.registry import PatternRegistry
from carrymem.patterns.definitions_noise import register_noise_patterns
from carrymem.patterns.definitions_preference import register_preference_patterns
from carrymem.patterns.definitions_correction import register_correction_patterns
from carrymem.patterns.definitions_fact import register_fact_patterns
from carrymem.patterns.definitions_task import register_task_patterns
from carrymem.patterns.definitions_decision import register_decision_patterns
from carrymem.patterns.definitions_relationship import register_relationship_patterns
from carrymem.patterns.definitions_sentiment import register_sentiment_patterns
from carrymem.patterns.definitions_location import register_location_patterns


def build_registry() -> PatternRegistry:
    """Build and return a fully populated PatternRegistry."""
    registry = PatternRegistry()
    register_noise_patterns(registry)
    register_preference_patterns(registry)
    register_correction_patterns(registry)
    register_fact_patterns(registry)
    register_task_patterns(registry)
    register_decision_patterns(registry)
    register_relationship_patterns(registry)
    register_sentiment_patterns(registry)
    register_location_patterns(registry)
    return registry
