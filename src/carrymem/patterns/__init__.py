"""Pattern management system for CarryMem.

Provides a layered architecture for regex pattern definition,
grouping, and matching with language-aware indexing.
"""

from carrymem.patterns.base import (
    Pattern,
    PatternType,
    NoiseCategory,
    PatternMatch,
)
from carrymem.patterns.group import PatternGroup
from carrymem.patterns.registry import PatternRegistry
from carrymem.patterns.builder import PatternBuilder

__all__ = [
    "Pattern",
    "PatternType",
    "NoiseCategory",
    "PatternMatch",
    "PatternGroup",
    "PatternRegistry",
    "PatternBuilder",
]
