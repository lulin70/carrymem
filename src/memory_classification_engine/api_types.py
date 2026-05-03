from typing import List, Optional, TypedDict


class RuleDict(TypedDict, total=False):
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
    rule: RuleDict
    score: float
    match_type: str


class EffectivenessReportDict(TypedDict, total=False):
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
    rule_id: str
    source_memories: List[dict]
    total: int
    active: int
    deleted: int
    superseded: int
    confidence_adjustment: float


class KnowledgeNoteDict(TypedDict, total=False):
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
    system_prompt: str
    rules: str
    memories: List[dict]
    knowledge: List[dict]
    rule_count: int
    memory_count: int
    knowledge_count: int
    token_estimate: int
    language: str
