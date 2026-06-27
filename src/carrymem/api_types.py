from typing import List, TypedDict


class RuleDict(TypedDict, total=False):
    """Dictionary shape representing a stored rule."""

    id: str
    trigger: str
    action: str
    rule_type: str
    override: bool
    confidence: float
    trigger_count: int
    status: str
    derived_from: str
    source_memories: List[str]
    metadata: dict


class MatchResultDict(TypedDict, total=False):
    """Dictionary shape for a single rule match result."""

    rule: RuleDict
    score: float
    match_type: str


class EffectivenessReportDict(TypedDict, total=False):
    """Dictionary shape for a rule effectiveness report."""

    total_rules: int
    active: int
    paused: int
    deprecated: int
    triggered: int
    never_triggered: int
    trigger_rate: float
    override_rules: int
    soft_rules: int
    type_breakdown: dict
    type_trigger_totals: dict
    confidence_distribution: dict
    top_triggered: List[dict]
    never_triggered_sample: List[dict]
    derivation_sources: dict


class SourceMemoryValidationDict(TypedDict, total=False):
    """Dictionary shape for source-memory validation of a rule."""

    rule_id: str
    source_memories: List[dict]
    total: int
    active: int
    deleted: int
    superseded: int
    confidence_adjustment: float


class KnowledgeNoteDict(TypedDict, total=False):
    """Dictionary shape for a knowledge base note."""

    id: str
    type: str
    title: str
    content: str
    file_path: str
    tags: List[str]
    wiki_links: List[str]
    frontmatter: dict
    source: str
    confidence: float
    relevance_score: float


class RecallAllResultDict(TypedDict, total=False):
    """Dictionary shape for the combined recall-all result."""

    rules: List[dict]
    memories: List[dict]
    knowledge: List[dict]
    rule_count: int
    memory_count: int
    knowledge_count: int
    total_count: int
    namespace: str
    priority: str


class BuildContextResultDict(TypedDict, total=False):
    """Dictionary shape for the build-context result."""

    system_prompt: str
    rules: str
    memories: List[dict]
    knowledge: List[dict]
    rule_count: int
    memory_count: int
    knowledge_count: int
    token_estimate: int
    language: str
