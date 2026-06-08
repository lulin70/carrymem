"""Pattern management system for CarryMem.

Provides a layered architecture for regex pattern definition,
grouping, and matching with language-aware indexing.
"""

from carrymem.patterns.base import (
    NoiseCategory,
    Pattern,
    PatternMatch,
    PatternType,
)
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.group import PatternGroup
from carrymem.patterns.registry import PatternRegistry

__all__ = [
    "Pattern",
    "PatternType",
    "NoiseCategory",
    "PatternMatch",
    "PatternGroup",
    "PatternRegistry",
    "PatternBuilder",
]
