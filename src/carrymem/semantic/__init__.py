"""Semantic recall engine for CarryMem.

Provides zero-dependency semantic expansion for memory recall:
- Synonym graph
- Spell correction
- Cross-language mapping
- Result fusion

Architecture:
    query → FTS5 (exact) → SemanticExpander → expanded queries → FTS5 → ResultMerger → final results
"""

from .expander import SemanticExpander
from .merger import ResultMerger

__all__ = ["SemanticExpander", "ResultMerger"]
