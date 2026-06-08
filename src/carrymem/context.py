"""Smart context injection — select and rank memories for AI prompts.

Context-aware memory selection with token budget control.

This module re-exports all public APIs from the sub-modules for backward
compatibility. The actual implementations live in:

- carrymem.selection: Memory scoring, ranking, and selection
- carrymem.scope: Preference scope inference and matching
- carrymem.format: Memory entry formatting for prompts
- carrymem.prompt: Prompt template construction (build_prompt, build_qa_prompt)
"""

from carrymem.format import (
    TYPE_LABELS,
    format_knowledge_entry,
    format_memory_entry,
)
from carrymem.prompt import (
    PROMPT_TEMPLATES,
    build_prompt,
    build_qa_prompt,
)
from carrymem.scope import (
    SCOPE_VOCABULARY,
    infer_scopes,
    preference_matches_scope,
)

# Re-export all public APIs for backward compatibility
from carrymem.selection import (
    context_relevance,
    select_knowledge,
    select_memories,
)

__all__ = [
    # Selection
    "context_relevance",
    "select_memories",
    "select_knowledge",
    # Scope
    "SCOPE_VOCABULARY",
    "infer_scopes",
    "preference_matches_scope",
    # Format
    "TYPE_LABELS",
    "format_memory_entry",
    "format_knowledge_entry",
    # Prompt
    "PROMPT_TEMPLATES",
    "build_prompt",
    "build_qa_prompt",
]
