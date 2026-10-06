"""Centralized type definitions for CarryMem core module.

This module defines TypedDict and TypeAlias types used across the core
module to improve type annotation coverage and provide better IDE support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TypedDict


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_safe(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Base memory types
# ---------------------------------------------------------------------------


class MemoryEntryDict(TypedDict, total=False):
    """Dictionary representation of MemoryEntry (from to_dict())."""

    id: str
    type: str
    content: str
    raw_text: str
    confidence: float
    tier: int
    source_layer: str
    reasoning: str
    suggested_action: str
    recall_hint: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    memory_nature: str
    version_chain_id: Optional[str]
    version_number: int
    domain: Optional[str]


class StoredMemoryDict(MemoryEntryDict, total=False):
    """Extended dictionary representation of StoredMemory."""

    storage_key: str
    namespace: str
    created_at: Optional[str]
    updated_at: Optional[str]
    expires_at: Optional[str]
    access_count: int
    importance_score: float
    last_accessed_at: Optional[str]
    version: int
    vector_embedding: Optional[List[float]]
    storage_metadata: Dict[str, Any]
    superseded_at: Optional[str]
    supersedes: Optional[str]
    summary: Optional[str]
    summary_level: Optional[int]


# ---------------------------------------------------------------------------
# Classification result types
# ---------------------------------------------------------------------------


class ClassificationSummary(TypedDict):
    """Summary section of classification result."""

    total_entries: int
    by_type: Dict[str, int]


class ClassificationResult(TypedDict, total=False):
    """Result from classify_message() or classify_and_remember()."""

    should_remember: bool
    type: str
    content: str
    entries: List[MemoryEntryDict]
    stored: bool
    storage_keys: List[str]
    rule_suggestions: List[Dict[str, Any]]
    auto_rules: List[Dict[str, Any]]
    updated_memories: List[Dict[str, Any]]
    summary: ClassificationResult | ClassificationSummary


# ---------------------------------------------------------------------------
# Declare/CRUD result types
# ---------------------------------------------------------------------------


class DeclareResult(TypedDict):
    """Result from declare() or declare_preference()."""

    declared: bool
    entries: List[StoredMemoryDict]
    storage_keys: List[str]
    source: str
    summary: ClassificationSummary


class UpdateMemoryResult(TypedDict, total=False):
    """Result from update_memory()."""

    updated: bool
    error: Optional[str]
    storage_key: Optional[str]
    version: Optional[int]
    content: Optional[str]


class RollbackMemoryResult(TypedDict, total=False):
    """Result from rollback_memory()."""

    rolled_back: bool
    error: Optional[str]
    storage_key: Optional[str]
    version: Optional[int]
    content: Optional[str]


class MergeMemoriesResult(TypedDict, total=False):
    """Result from merge_memories()."""

    total_input: int
    total_output: int
    duplicates_removed: int
    strategy: str
    namespaces: List[str]
    memories: List[Dict[str, Any]]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Recall result types
# ---------------------------------------------------------------------------


class RuleMatchDict(TypedDict):
    """Single rule match in recall results."""

    rule_id: str
    trigger: str
    action: str
    rule_type: str
    override: bool
    score: float
    match_type: str


class RecallAllResult(TypedDict):
    """Result from recall_all()."""

    rules: List[RuleMatchDict]
    memories: List[StoredMemoryDict]
    knowledge: List[Dict[str, Any]]
    rule_count: int
    memory_count: int
    knowledge_count: int
    total_count: int
    namespace: str
    priority: str


class RecallAggregatedResult(TypedDict):
    """Result from recall_aggregated()."""

    # Keys are memory types, values are lists of memory dicts
    __extra__: Dict[str, List[StoredMemoryDict]]


@dataclass(frozen=True, slots=True)
class RecallItem:
    """One deterministic recall candidate with its contributing modes."""

    memory: Dict[str, Any]
    source_mode: str
    score: float = 0.0
    evidence: Tuple[Any, ...] = ()
    source_modes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        result = _json_safe(
            {
                "memory": dict(self.memory),
                "source_mode": self.source_mode,
                "source_modes": list(self.source_modes or (self.source_mode,)),
                "score": self.score,
                "evidence": list(self.evidence),
            }
        )
        return dict(result)


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    """Observed usage of the recall budgets."""

    candidates: int = 0
    results: int = 0
    max_candidates: int = 0
    max_results: int = 0
    evidence: int = 0
    reflection: int = 0
    output: int = 0
    max_evidence: int = 0
    max_reflection: int = 0
    max_output: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "candidates": self.candidates,
            "results": self.results,
            "max_candidates": self.max_candidates,
            "max_results": self.max_results,
            "evidence": self.evidence,
            "reflection": self.reflection,
            "output": self.output,
            "max_evidence": self.max_evidence,
            "max_reflection": self.max_reflection,
            "max_output": self.max_output,
        }


@dataclass(frozen=True, slots=True)
class ConflictView:
    """Structured view of candidates believed to represent one conflict."""

    conflict_key: str
    storage_keys: Tuple[str, ...]
    items: Tuple[Dict[str, Any], ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_key": self.conflict_key,
            "storage_keys": list(self.storage_keys),
            "items": [dict(item) for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class ModeFailure:
    """Failure or explicit skip for one requested retrieval mode."""

    mode: str
    reason: str
    error_type: Optional[str] = None
    skipped: bool = False
    reason_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "reason": self.reason,
            "error_type": self.error_type,
            "skipped": self.skipped,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class RecallPlanSnapshot:
    """JSON-safe snapshot of the executed recall plan."""

    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        result = _json_safe(dict(self.data))
        return dict(result)


@dataclass(frozen=True, slots=True)
class RecallResult:
    """Stable, serializable result of executing a RecallPlan."""

    items: Tuple[RecallItem, ...]
    plan_fingerprint: str
    namespace: str
    task: str
    modes: Tuple[str, ...]
    budget_usage: BudgetUsage
    mode_failures: Tuple[ModeFailure, ...] = ()
    conflicts: Tuple[ConflictView, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    plan: Optional[RecallPlanSnapshot] = None
    truncations: Tuple[Any, ...] = ()
    degraded: Optional[Any] = None
    status: str = "ok"

    def to_legacy_list(self) -> List[Dict[str, Any]]:
        return [dict(item.memory) for item in self.items]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "plan_fingerprint": self.plan_fingerprint,
            "namespace": self.namespace,
            "task": self.task,
            "modes": list(self.modes),
            "budget_usage": self.budget_usage.to_dict(),
            "mode_failures": [failure.to_dict() for failure in self.mode_failures],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "metadata": _json_safe(dict(self.metadata)),
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "truncations": [_json_safe(item) for item in self.truncations],
            "degraded": _json_safe(self.degraded) if self.degraded is not None else None,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Profile / Stats types
# ---------------------------------------------------------------------------


class MemoryStats(TypedDict, total=False):
    """Result from get_stats()."""

    adapter: Optional[str]
    total_count: int
    by_type: Dict[str, int]
    capabilities: Dict[str, bool]


class MemoryProfileStats(TypedDict):
    """Statistics section within memory profile."""

    by_type: Dict[str, int]
    by_tier: Dict[str, int]
    confidence_avg: float


class MemoryProfile(TypedDict, total=False):
    """Result from get_memory_profile()."""

    summary: str
    total_memories: int
    highlights: Dict[str, List[Dict[str, Any]]]
    stats: MemoryProfileStats
    last_updated: Optional[str]


class WhoamiResult(TypedDict, total=False):
    """Result from whoami()."""

    identity: str
    summary: str
    total_memories: int
    top_type: str
    confidence_avg: float
    preferences: List[str]
    decisions: List[str]
    corrections: List[str]
    by_type: Dict[str, int]
    domains: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Export / Import types
# ---------------------------------------------------------------------------


class ExportProfileData(TypedDict):
    """Data structure for profile export."""

    schema_version: str
    format: str
    exported_at: str
    identity: str
    summary: str
    preferences: List[str]
    decisions: List[str]
    corrections: List[str]
    stats: Dict[str, Any]
    profile: MemoryProfile


class ExportProfileResult(TypedDict):
    """Result from export_profile()."""

    schema_version: str
    format: str
    exported_at: str
    identity: str
    summary: str
    preferences: List[str]
    decisions: List[str]
    corrections: List[str]
    stats: Dict[str, Any]
    profile: MemoryProfile


class ExportMemoriesResult(TypedDict, total=False):
    """Result from export_memories()."""

    exported: bool
    format: str
    path: Optional[str]
    total_memories: int
    namespace: str
    content: Optional[str]
    data: Optional[Dict[str, Any]]


class ImportMemoriesResult(TypedDict):
    """Result from import_memories()."""

    imported: int
    skipped: int
    errors: int
    total_processed: int
    namespace: str
    merge_strategy: str


# ---------------------------------------------------------------------------
# Validation / Internal types
# ---------------------------------------------------------------------------


class ValidationResult(TypedDict, total=False):
    """Result from _validate_and_resolve() when redaction blocks storage."""

    should_remember: bool
    type: str
    content: str
    entries: List[Any]
    stored: bool
    storage_keys: List[str]
    rule_suggestions: List[Any]
    auto_rules: List[Any]
    updated_memories: List[Any]
    summary: Dict[str, Any]


class ValidateResolveTuple:
    """Return type of _validate_and_resolve(): tuple of 4 elements.

    This is a TypeAlias-like class used for documentation.
    Actual return is: Tuple[str, bool, Optional[ValidationResult], bool]
    """

    __slots__ = ()

    def __new__(cls) -> "ValidateResolveTuple":
        raise TypeError("ValidateResolveTuple cannot be instantiated")


# Type alias for the actual return type
ValidateAndResolveResult = tuple[
    str,  # resolved_message
    bool,  # should_continue
    Optional[ValidationResult],  # redact_result (None if not blocked)
    bool,  # coreference_resolved
]


# ---------------------------------------------------------------------------
# Maintenance types
# ---------------------------------------------------------------------------


class ConflictInfo(TypedDict):
    """Information about a detected conflict."""

    conflict_id: str
    type: str  # "memory_memory", "memory_rule", etc.
    items: List[Dict[str, Any]]
    severity: str  # "low", "medium", "high"
    suggestion: str


class QualityIssue(TypedDict):
    """Information about a quality issue."""

    memory_id: str
    issue_type: str  # "low_confidence", "duplicate", "stale", etc.
    score: float
    suggestion: str


class ConsolidationResult(TypedDict, total=False):
    """Result from consolidate()."""

    dry_run: bool
    memories_processed: int
    memories_removed: int
    memories_decayed: int
    conflicts_resolved: int
    duration_seconds: float
    details: Dict[str, Any]


class ScheduleConsolidationResult(TypedDict):
    """Result from schedule_consolidation()."""

    scheduled: bool
    interval_hours: float
    dry_run: bool
    run_p1: bool
    run_p2: bool


# ---------------------------------------------------------------------------
# Backup types
# ---------------------------------------------------------------------------


class BackupResult(TypedDict, total=False):
    """Result from backup()."""

    backed_up: bool
    path: Optional[str]
    error: Optional[str]


class RestoreBackupResult(TypedDict, total=False):
    """Result from restore_backup()."""

    restored: bool
    path: str
    error: Optional[str]


class AuditLogEntry(TypedDict, total=False):
    """Single audit log entry."""

    timestamp: str
    operation: str
    source: str
    details: Dict[str, Any]


# ---------------------------------------------------------------------------
# Prompt delegate types
# ---------------------------------------------------------------------------


class ContextBuildResult(TypedDict):
    """Result from build_context()."""

    context_str: str
    memories: List[StoredMemoryDict]
    knowledge: List[Dict[str, Any]]
    rules: List[RuleMatchDict]
    token_count: int
    truncated: bool


class SessionSummaryResult(TypedDict, total=False):
    """Result from summarize_session()."""

    session_id: str
    summary: str
    key_points: List[str]
    memories_extracted: int
    language: str
    stored: bool


# ---------------------------------------------------------------------------
# Correction handling types
# ---------------------------------------------------------------------------


class CorrectionUpdateInfo(TypedDict, total=False):
    """Information about a correction that was applied."""

    storage_key: Optional[str]
    old_content: Optional[str]
    new_content: Optional[str]
    reason: Optional[str]
    rule_updated: Optional[str]
    new_action: Optional[str]


# ---------------------------------------------------------------------------
# Health check / Status types
# ---------------------------------------------------------------------------


class ComponentHealth(TypedDict):
    """Health status of a single component."""

    status: str  # "ready", "not_configured", "error"
    type: Optional[str]  # Class name (if ready)
    stats: Optional[Dict[str, Any]]  # For storage adapter
    error: Optional[str]  # Error message (if error)


class HealthCheckResult(TypedDict):
    """Result from health_check()."""

    status: str  # "ok" or "degraded"
    components: Dict[str, ComponentHealth]
    issues: List[str]


class ComponentStatusDict(TypedDict):
    """Result from get_component_status()."""

    # Keys are component names, values are status strings
    __extra__: Dict[str, str]


# ---------------------------------------------------------------------------
# Convenience type aliases
# ---------------------------------------------------------------------------

# Commonly used dictionary types
MemoryDict = StoredMemoryDict  # Alias for recall results
FilterDict = Dict[str, Any]  # Query filters
ContextDict = Dict[str, Any]  # Message context
MetadataDict = Dict[str, Any]  # Entry metadata
