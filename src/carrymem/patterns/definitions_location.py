"""Location pattern definitions."""

from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_location_patterns(registry: PatternRegistry) -> None:
    """Register all location patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Fact exclusion indicators (used to skip non-location content) =====
    b.create_group("location_fact_exclusion", PatternType.LOCATION)
    b.set_language("en")
    b.add_location("be_verb", r"\b(is|are|was|were|has|have)\s+", confidence=0.0)
    b.add_location("action_verb", r"\b(supports?|requires?|provides?|includes?)\s+", confidence=0.0)
    b.add_location("freq", r"\b(every|always|weekly|monthly|daily)\b", confidence=0.0)
    b.add_location("business", r"\b(approval|budget|deadline|schedule|sprint)\b", confidence=0.0)
    b.add_location("version", r"\d+(\.\d+)+", confidence=0.0)
    b.add_location("people_num", r"\b(employees?|users?|members?|teams?)\s+\d+", confidence=0.0)
    b.add_location("we_have", r"\b(we\s+have|our\s+\w+)\s+", confidence=0.0)
    b.add_location("runs_on", r"\b(runs?|operates?|works?)\s+(on|in|at)\s+", confidence=0.0)
    b.add_location("perf", r"\b(latency|throughput|performance|uptime)\b", confidence=0.0)
    b.add_location("live_work", r"\b(live[s]?\s+in|work[s]?\s+(for|at|remotely))\b", confidence=0.0)
    b.add_location("standup", r"\b(stands?|meets?|sync)\s+", confidence=0.0)
    b.add_location("ends_on", r"\b(ends?|starts?|begins?)\s+(on|at)\s+", confidence=0.0)
    b.add_location("unit", r"\b\d+\s*(employees?|users?|ms|sec|min|hour)\b", confidence=0.0)
    b.register()
