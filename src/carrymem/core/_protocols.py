"""Protocol interfaces for CarryMem Mixin composition.

Defines structural typing contracts for every Mixin in the core module.
These Protocols are **structural** (duck-typing via typing.Protocol) —
they are NOT checked at runtime but provide IDE autocomplete, mypy
compatibility, and explicit dependency documentation.

Usage::

    from carrymem.core._protocols import HasRecallOps

    def process(recaller: HasRecallOps) -> None:
        results = recaller.recall_memories(query="hello")

Design principles:
  - Each Protocol maps 1:1 to one Mixin class.
  - Public methods only — private helpers stay internal.
  - Cross-Mixin dependencies expressed as nested Protocol references.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Protocol, TYPE_CHECKING, Type, Union

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter
    from carrymem.core import CarryMem
    from carrymem.engine import MemoryClassificationEngine
    from carrymem.prompt_builder import PromptBuilder
    from carrymem.rules import RuleEngine


# ---------------------------------------------------------------------------
# Shared-state protocols (what every Mixin can read / write)
# ---------------------------------------------------------------------------


class HasSharedState(Protocol):
    """Minimal shared state that most Mixins depend on.

    These attributes are set by LifecycleMixin.__init__() and consumed
    by nearly every other Mixin.
    """

    @property
    def _adapter(self) -> Optional[StorageAdapter]: ...

    @property
    def _namespace(self) -> str: ...

    @property
    def _config(self) -> Optional[Dict[str, Any]]: ...

    @property
    def _engine(self) -> Optional[MemoryClassificationEngine]: ...

    @property
    def _knowledge_adapter(self) -> Optional[StorageAdapter]: ...


# ---------------------------------------------------------------------------
# LifecycleMixin → Provides shared state & lifecycle management
# ---------------------------------------------------------------------------


class LifecycleOps(Protocol):
    """Contract for LifecycleMixin — object lifecycle and shared state."""

    # -- constructor signature (simplified for protocol purposes) --

    @property
    def namespace(self) -> str:
        """Current memory namespace."""
        ...

    @property
    def engine(self) -> MemoryClassificationEngine:
        """MemoryClassificationEngine instance."""
        ...

    @property
    def adapter(self) -> Optional[StorageAdapter]:
        """Storage adapter (alias for storage)."""
        ...

    @property
    def storage(self) -> Optional[StorageAdapter]:
        """Storage adapter."""
        ...

    @property
    def knowledge_adapter(self) -> Optional[StorageAdapter]:
        """Knowledge-base adapter (e.g. ObsidianAdapter)."""
        ...

    @property
    def rule_engine(self) -> RuleEngine:
        """Lazy-initialised RuleEngine instance."""
        ...

    @property
    def prompt_builder(self) -> PromptBuilder:
        """Lazy-initialised PromptBuilder instance."""
        ...

    def close(self) -> None:
        """Release resources (adapter, rule engine, knowledge adapter)."""
        ...

    def __enter__(self) -> CarryMem: ...

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> bool: ...


# ---------------------------------------------------------------------------
# BackupMixin → Backup / audit operations
# ---------------------------------------------------------------------------


class BackupOps(Protocol):
    """Contract for BackupMixin — backup creation, restoration, audit log."""

    def clear_cache(self) -> None:
        """Clear adapter's internal cache."""
        ...

    def backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """Create a manual backup. Returns {backed_up, path} or {error}."""
        ...

    def list_backups(self, backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available backups."""
        ...

    def restore_backup(
        self,
        backup_path: str,
        backup_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore database from a backup file."""
        ...

    def get_audit_log(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit log entries."""
        ...

    # -- internal (still part of cross-Mixin contract) --

    def _do_initial_backup(self) -> None: ...

    def _auto_backup(self) -> None: ...


# ---------------------------------------------------------------------------
# RecallMixin → Memory / knowledge / rule recall
# ---------------------------------------------------------------------------


class RecallOps(Protocol):
    """Contract for RecallMixin — search across memories, knowledge, rules."""

    def index_knowledge(self) -> Dict[str, Any]:
        """Index knowledge base (e.g. Obsidian vault)."""
        ...

    def recall_from_knowledge(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base."""
        ...

    def recall_all(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        """Unified recall across rules + memories + knowledge."""
        ...

    def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search stored memories."""
        ...

    def recall_aggregated(
        self,
        memory_type: Optional[str] = None,
        limit_per_type: int = 50,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Recall memories grouped by type."""
        ...

    def recall_timeline(
        self,
        topic: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Recall memories chronologically for a topic."""
        ...


# ---------------------------------------------------------------------------
# ClassificationMixin → Internal classification pipeline
# ---------------------------------------------------------------------------


class ClassificationOps(Protocol):
    """Contract for ClassificationMixin — classify & resolve pipeline.

    Most methods here are *internal* (prefixed with _) but they form
    the contract between MemoryCRUDMixin and ClassificationMixin.
    """

    # -- public --

    def classify_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a message into memory types without storing."""
        ...

    # -- internal (cross-Mixin contract) --

    def _validate_and_resolve(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> tuple:
        """Validate input, resolve coreferences, check redaction."""
        ...

    def _classify_message(
        self,
        resolved_message: str,
        context: Optional[Dict[str, Any]],
        language: Optional[str],
        force_type: Optional[str],
        message: str,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Classify resolved message; returns entries list or classify result dict."""
        ...

    def _store_entries(
        self,
        classify_result: Dict[str, Any],
        resolved_message: str,
        message: str,
        context: Optional[Dict[str, Any]],
        coreference_resolved: bool,
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Store classified entries, trigger auto-backup, suggest rules."""
        ...

    def _handle_correction(self, correction_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply a correction entry to existing memories or rules."""
        ...

    def _count_by_type(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count entries grouped by memory type."""
        ...

    # -- rule delegate thin wrappers --

    def _auto_suggest_rules(self, stored_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]: ...
    def _detect_implicit_preferences(self) -> List[Dict[str, Any]]: ...
    def _sanitize_rule_content(self, text: str) -> str: ...
    def _extract_trigger(self, content: str, mem_type: str) -> str: ...
    def _extract_condition(self, content: str) -> str: ...
    def _extract_action(self, content: str, mem_type: str) -> str: ...
    def _infer_rule_type(self, mem_type: str, content: str = "") -> str: ...


# ---------------------------------------------------------------------------
# MemoryCRUDMixin → Core CRUD operations
# ---------------------------------------------------------------------------


class MemoryCRUDOps(Protocol):
    """Contract for MemoryCRUDMixin — remember, declare, forget, update, merge."""

    def classify_and_remember(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        session_id: Optional[str] = None,
        force_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full pipeline: validate → classify → store."""
        ...

    # Note: classify_message() is defined in ClassificationOps Protocol.
    # MemoryCRUDMixin delegates to ClassificationMixin for this method.
    # See ClassificationOps.classify_message for the full contract.

    def declare(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Explicitly declare a user preference / decision as memory."""
        ...

    def declare_preference(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Alias for declare() — semantic sugar."""
        ...

    def forget_memory(self, memory_id: str) -> bool:
        """Delete a single memory by ID."""
        ...

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update memory content with versioning (SQLite only)."""
        ...

    def get_memory_history(self, storage_key: str) -> List[Dict[str, Any]]:
        """Get version history for a memory (SQLite only)."""
        ...

    def rollback_memory(self, storage_key: str, version: int) -> Dict[str, Any]:
        """Roll back memory to a specific version (SQLite only)."""
        ...

    def merge_memories(
        self,
        namespaces: Optional[List[str]] = None,
        strategy: str = "latest_wins",
        conflict_callback: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Merge duplicate memories across namespaces (SQLite only)."""
        ...


# ---------------------------------------------------------------------------
# ProfileExportMixin → Profile, stats, export, import
# ---------------------------------------------------------------------------


class ProfileExportOps(Protocol):
    """Contract for ProfileExportMixin — user profile, statistics, I/O."""

    def get_stats(self) -> Dict[str, Any]:
        """Return storage statistics (total count, by-type breakdown)."""
        ...

    def get_memory_profile(self) -> Dict[str, Any]:
        """Return detailed memory profile from adapter."""
        ...

    def whoami(self) -> Dict[str, Any]:
        """Summarise current user identity based on stored memories."""
        ...

    def export_profile(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Export user identity profile to JSON (or return dict if no path)."""
        ...

    def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export all memories to JSON or Markdown."""
        ...

    def import_memories(
        self,
        input_path: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        merge_strategy: str = "skip_existing",
    ) -> Dict[str, Any]:
        """Import memories from a previously exported file or dict."""
        ...


# ---------------------------------------------------------------------------
# MaintenanceMixin → Quality, conflicts, consolidation
# ---------------------------------------------------------------------------


class MaintenanceOps(Protocol):
    """Contract for MaintenanceMixin — quality checks, conflict detection, consolidation."""

    def check_conflicts(self) -> List[Dict[str, Any]]:
        """Detect conflicting memories and rules."""
        ...

    def check_quality(self, min_score: float = 0.3) -> List[Dict[str, Any]]:
        """Identify low-quality memories below threshold."""
        ...

    def list_expired(self) -> List[Dict[str, Any]]:
        """List memories whose expiry date has passed (SQLite only)."""
        ...

    def consolidate(
        self,
        dry_run: bool = True,
        run_p1: bool = True,
        run_p2: bool = True,
    ) -> Dict[str, Any]:
        """Run full consolidation pipeline: dedup → decay → forget."""
        ...

    def schedule_consolidation(
        self,
        interval_hours: float = 1.0,
        dry_run: bool = False,
        run_p1: bool = True,
        run_p2: bool = False,
    ) -> Dict[str, Any]:
        """Start periodic background consolidation timer."""
        ...

    def stop_consolidation(self) -> Dict[str, Any]:
        """Stop the background consolidation timer."""
        ...


# ---------------------------------------------------------------------------
# PromptDelegateMixin → LLM-powered prompt building
# ---------------------------------------------------------------------------


class PromptDelegateOps(Protocol):
    """Contract for PromptDelegateMixin — prompt construction & LLM features."""

    def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Build context dict for LLM injection."""
        ...

    def build_system_prompt(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 4000,
        language: str = "en",
    ) -> str:
        """Build system prompt string with injected context."""
        ...

    def build_qa_prompt(
        self,
        question: str,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
        budget: Optional[Dict[str, Any]] = None,
        include_question: bool = True,
    ) -> str:
        """Build QA prompt with retrieved context."""
        ...

    def summarize_session(
        self,
        session_id: str,
        language: str = "en",
        store: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """LLM-powered session summarisation (experimental)."""
        ...

    def aggregate_memories(
        self,
        memory_type: Optional[str] = None,
        language: str = "en",
        store: bool = True,
    ) -> List[Dict[str, Any]]:
        """LLM-powered semantic aggregation of memories (experimental)."""
        ...


# ---------------------------------------------------------------------------
# Composite Protocol — the full CarryMem facade contract
# ---------------------------------------------------------------------------


class CarryMemOps(
    LifecycleOps,
    BackupOps,
    RecallOps,
    ClassificationOps,
    MemoryCRUDOps,
    ProfileExportOps,
    MaintenanceOps,
    PromptDelegateOps,
    Protocol,
):
    """Composite Protocol representing the complete CarryMem public surface.

    A class satisfies ``CarryMemOps`` if it implements **every** method
    from all 8 Mixin protocols.  This is the structural type-check that
    replaces concrete inheritance in type hints.

    Example::

        def process(cm: CarryMemOps) -> None:
            cm.classify_and_remember("I love Python")
            cm.whoami()
    """
