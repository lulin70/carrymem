"""
Storage Adapter Abstract Base Class and MemoryEntry data class.

v3.2 Update (2026-04-20):
- Method rename: store→remember, retrieve→recall, delete→forget
- Added StoredMemory dataclass (extends MemoryEntry with storage metadata)
- Added async interface support
- Added TestStorageAdapterContract for adapter validation

Pure Upstream Mode: MCE does not store memories itself.
Instead, it outputs standardized MemoryEntry objects that downstream systems
consume via implementations of this adapter interface.

Available official adapters (planned):
- SQLiteAdapter: Default implementation for dev/demo
- SupermemoryAdapter: Bridges to supermemory.ai cloud service
- ObsidianAdapter: Writes to local Obsidian vault markdown files
- Mem0Adapter: Connects to Mem0 self-hosted instance

Community adapters are welcome!
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from carrymem.domain import infer_domain


@dataclass
class MemoryEntry:
    """Standardized memory entry — MCE output, Adapter input.

    This is the data contract between MCE's classification engine
    and any downstream storage system. All adapters receive MemoryEntry
    objects and map them to their native storage format.

    Immutable once created (frozen=True recommended for production).
    """

    id: str = ""
    type: str = "unknown"
    content: str = ""
    raw_text: str = ""
    confidence: float = 0.0
    tier: int = 2
    source_layer: str = "unknown"
    reasoning: str = ""
    suggested_action: str = "store"
    recall_hint: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    memory_nature: str = "state"  # "state" (evolving, versioned) or "event" (immutable fact)
    version_chain_id: Optional[str] = None  # Shared ID for versions of the same concept
    version_number: int = 1  # Sequence number within version chain
    domain: Optional[str] = None  # Auto-inferred professional domain

    # Types that represent evolving state (superseded by newer values)
    STATE_TYPES = {
        "user_preference",
        "correction",
        "decision",
        "fact_declaration",
        "relationship",
        "sentiment_marker",
    }
    # Types that represent immutable events (complete retention, no versioning)
    EVENT_TYPES = {"session_summary", "task_pattern"}

    def infer_memory_nature(self) -> str:
        """Infer memory_nature from type field."""
        if self.type in self.EVENT_TYPES:
            return "event"
        return "state"

    def __post_init__(self):
        """Auto-infer memory_nature and domain if not set."""
        if self.memory_nature == "state" and self.type in self.EVENT_TYPES:
            self.memory_nature = "event"
        if not self.domain:
            self.domain = infer_domain(self.raw_text or self.content or "")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (JSON-safe)."""
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "tier": self.tier,
            "source_layer": self.source_layer,
            "reasoning": self.reasoning,
            "suggested_action": self.suggested_action,
            "recall_hint": self.recall_hint,
            "metadata": self.metadata,
            "memory_nature": self.memory_nature,
            "version_chain_id": self.version_chain_id,
            "version_number": self.version_number,
            "domain": self.domain,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Deserialize from dict."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "unknown"),
            content=data.get("content", ""),
            raw_text=data.get("raw_text", ""),
            confidence=data.get("confidence", 0.0),
            tier=data.get("tier", 2),
            source_layer=data.get("source_layer", "unknown"),
            reasoning=data.get("reasoning", ""),
            suggested_action=data.get("suggested_action", "store"),
            recall_hint=data.get("recall_hint"),
            metadata=data.get("metadata", {}),
            memory_nature=data.get("memory_nature", "state"),
            version_chain_id=data.get("version_chain_id"),
            version_number=data.get("version_number", 1),
            domain=data.get("domain"),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryEntry(id={self.id!r}, type={self.type!r}, "
            f"conf={self.confidence:.2f}, action={self.suggested_action!r})"
        )


@dataclass
class StoredMemory(MemoryEntry):
    """Extended memory entry with storage metadata.

    Layer 2 Schema: Adapter extends MemoryEntry with storage-specific fields.
    This is what recall() returns — the stored version with metadata attached.

    Additional fields beyond MemoryEntry:
    - storage_key: Adapter-specific unique identifier
    - created_at: Timestamp when stored
    - updated_at: Timestamp when last modified
    - expires_at: Optional TTL expiry timestamp
    - access_count: Number of times recalled
    - vector_embedding: Optional embedding vector for semantic search
    - storage_metadata: Adapter-specific additional data
    """

    storage_key: str = ""
    namespace: str = "default"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    access_count: int = 0
    importance_score: float = 0.0
    last_accessed_at: Optional[datetime] = None
    version: int = 1
    vector_embedding: Optional[List[float]] = None
    storage_metadata: Dict[str, Any] = field(default_factory=dict)
    superseded_at: Optional[datetime] = None
    supersedes: Optional[str] = None
    summary: Optional[str] = None
    summary_level: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (JSON-safe), including storage fields."""
        base = super().to_dict()
        base.update(
            {
                "storage_key": self.storage_key,
                "namespace": self.namespace,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "access_count": self.access_count,
                "importance_score": self.importance_score,
                "last_accessed_at": (self.last_accessed_at.isoformat() if self.last_accessed_at else None),
                "version": self.version,
                "vector_embedding": self.vector_embedding,
                "storage_metadata": self.storage_metadata,
                "superseded_at": self.superseded_at.isoformat() if self.superseded_at else None,
                "supersedes": self.supersedes,
                "memory_nature": self.memory_nature,
                "version_chain_id": self.version_chain_id,
                "version_number": self.version_number,
                "domain": self.domain,
                "summary": self.summary,
                "summary_level": self.summary_level,
            }
        )
        return base

    @classmethod
    def from_memory_entry(
        cls,
        entry: MemoryEntry,
        storage_key: str = "",
        created_at: Optional[datetime] = None,
    ) -> "StoredMemory":
        """Create StoredMemory from MemoryEntry with storage metadata."""
        return cls(
            id=entry.id,
            type=entry.type,
            content=entry.content,
            raw_text=entry.raw_text,
            confidence=entry.confidence,
            tier=entry.tier,
            source_layer=entry.source_layer,
            reasoning=entry.reasoning,
            suggested_action=entry.suggested_action,
            recall_hint=entry.recall_hint,
            metadata=entry.metadata,
            storage_key=storage_key,
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=created_at or datetime.now(timezone.utc),
            memory_nature=entry.memory_nature,
            version_chain_id=entry.version_chain_id,
            version_number=entry.version_number,
            domain=entry.domain,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredMemory":
        """Reconstruct a StoredMemory from a serialized dictionary."""
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], str):
                try:
                    created_at = datetime.fromisoformat(data["created_at"])
                except (ValueError, TypeError):
                    created_at = None
            elif isinstance(data["created_at"], datetime):
                created_at = data["created_at"]

        updated_at = None
        if data.get("updated_at"):
            if isinstance(data["updated_at"], str):
                try:
                    updated_at = datetime.fromisoformat(data["updated_at"])
                except (ValueError, TypeError):
                    updated_at = None
            elif isinstance(data["updated_at"], datetime):
                updated_at = data["updated_at"]

        expires_at = None
        if data.get("expires_at"):
            if isinstance(data["expires_at"], str):
                try:
                    expires_at = datetime.fromisoformat(data["expires_at"])
                except (ValueError, TypeError):
                    expires_at = None
            elif isinstance(data["expires_at"], datetime):
                expires_at = data["expires_at"]

        last_accessed_at = None
        if data.get("last_accessed_at"):
            if isinstance(data["last_accessed_at"], str):
                try:
                    last_accessed_at = datetime.fromisoformat(data["last_accessed_at"])
                except (ValueError, TypeError):
                    last_accessed_at = None
            elif isinstance(data["last_accessed_at"], datetime):
                last_accessed_at = data["last_accessed_at"]

        superseded_at = None
        if data.get("superseded_at"):
            if isinstance(data["superseded_at"], str):
                try:
                    superseded_at = datetime.fromisoformat(data["superseded_at"])
                except (ValueError, TypeError):
                    superseded_at = None
            elif isinstance(data["superseded_at"], datetime):
                superseded_at = data["superseded_at"]

        return cls(
            id=data.get("id", ""),
            type=data.get("type", "unknown"),
            content=data.get("content", ""),
            raw_text=data.get("raw_text", ""),
            confidence=data.get("confidence", 0.0),
            tier=data.get("tier", 2),
            source_layer=data.get("source_layer", "unknown"),
            reasoning=data.get("reasoning", ""),
            suggested_action=data.get("suggested_action", "store"),
            recall_hint=data.get("recall_hint"),
            metadata=data.get("metadata", {}),
            storage_key=data.get("storage_key", ""),
            created_at=created_at,
            updated_at=updated_at,
            expires_at=expires_at,
            access_count=data.get("access_count", 0),
            importance_score=data.get("importance_score", 0.0),
            last_accessed_at=last_accessed_at,
            version=data.get("version", 1),
            superseded_at=superseded_at,
            supersedes=data.get("supersedes"),
            memory_nature=data.get("memory_nature", "state"),
            version_chain_id=data.get("version_chain_id"),
            version_number=data.get("version_number", 1),
            domain=data.get("domain"),
            summary=data.get("summary"),
            summary_level=data.get("summary_level"),
        )


class StorageAdapter(ABC):
    """Abstract base class for downstream storage adapters.

    Every downstream storage system that wants to receive MCE's
    classification output must implement this interface.

    Standardized Interface:
    - store(): Store a memory entry (dict-based, returns entry_id)
    - store_entry(): Store a MemoryEntry object, returns StoredMemory with full metadata
    - store_batch(): Batch store MemoryEntry objects in atomic transaction, returns list of StoredMemory
    - recall(): Retrieve memories matching query
    - delete(): Delete a memory by ID
    - delete_batch(): Batch delete by storage keys in atomic transaction, returns dict of results
    - count(): Count stored memories
    - initialize(): Initialize adapter with configuration
    - health_check(): Run health check on backend
    - close(): Release all resources

    Implementation guide:
    1. Subclass StorageAdapter
    2. Implement all abstract methods (store, recall, delete, count, initialize, health_check, close)
    3. Set name and capabilities properties
    4. store_entry/store_batch/delete_batch have default implementations that delegate to store/delete
    5. Pass TestStorageAdapterContract (see tests/adapters/)

    Example:
        class SQLiteAdapter(StorageAdapter):
            @property
            def name(self) -> str:
                return "sqlite"

            def store(self, entry: dict) -> str:
                cursor.execute(
                    "INSERT INTO memories (id, type, content) VALUES (?, ?, ?)",
                    (entry["id"], entry["type"], entry["content"])
                )
                return entry["id"]

            def recall(self, query, filters=None, limit=20, update_access=True):
                # FTS5 search implementation
                ...

            def delete(self, entry_id: str) -> bool:
                cursor.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
                return cursor.rowcount > 0
    """

    # ── Standardized Adapter Interface (abstract) ──────────────────────

    @abstractmethod
    def initialize(self, config: dict) -> None:
        """Initialize the adapter with configuration.

        Called once before any other operation. Use for connection setup,
        schema creation, resource allocation, etc.

        Args:
            config: Adapter-specific configuration dictionary.
                    Common keys: ``path``, ``namespace``, ``encryption_key``.
        """
        ...

    @abstractmethod
    def store(self, entry: dict) -> str:
        """Store a memory entry and return its unique ID.

        This is the standardized store method that accepts a plain dict
        (compatible with JSON serialization) rather than a MemoryEntry object.

        Args:
            entry: Dictionary containing memory data. Must include at minimum
                   ``content`` and ``type`` fields.

        Returns:
            The unique entry_id (storage_key) of the stored memory.
        """
        ...

    @abstractmethod
    def store_entry(self, entry: MemoryEntry) -> StoredMemory:
        """Store a MemoryEntry and return the complete StoredMemory with metadata.

        This is the domain-level store method that preserves the full
        MemoryEntry object and returns a StoredMemory with all storage
        metadata (importance_score, version, created_at, etc.) populated
        by the adapter.

        Args:
            entry: The MemoryEntry object to persist.

        Returns:
            StoredMemory with storage_key and all metadata fields populated.
        """
        ...

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Delete a memory by its entry ID.

        Args:
            entry_id: The storage_key/ID returned by :meth:`store`.

        Returns:
            True if the entry was deleted, False if it was not found.
        """
        ...

    @abstractmethod
    def count(self, filter_: Optional[dict] = None) -> int:
        """Count stored memories, optionally filtered.

        Args:
            filter_: Optional filter criteria. Supported keys vary by adapter.
                     Common keys: ``type``, ``tier``, ``namespace``.

        Returns:
            Number of matching memories.
        """
        ...

    @abstractmethod
    def health_check(self) -> dict:
        """Run a health check on the adapter's backend.

        Returns:
            Dict with at least:
            - ``status`` (str): ``"healthy"``, ``"degraded"``, or ``"unhealthy"``
            - ``latency_ms`` (float): Round-trip time for the check
            - Additional adapter-specific metrics
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Release all resources held by this adapter.

        Must be safe to call multiple times. After close(), the adapter
        should not be used for further operations.
        """
        ...

    @abstractmethod
    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[list] = None,
        update_access: bool = False,
    ) -> List[StoredMemory]:
        """Retrieve memories matching a query.

        Args:
            query: Search query (keywords or natural language)
            filters: Optional filters (e.g., {"type": "user_preference", "tier": 1})
            limit: Maximum number of results
            namespaces: Optional list of namespace names to restrict search scope.
                        When None, searches across all namespaces.
            update_access: If True, update access_count/importance_score/last_accessed_at.
                           Set to False for internal reads (build_context/build_qa_prompt)
                           to avoid write side effects during prompt construction.

        Returns:
            List of StoredMemory objects matching the query
        """
        ...

    # ── Cache Management (public API for core layer) ────────────────────

    @property
    def has_cache(self) -> bool:
        """Whether this adapter has an active recall cache.

        Default is False. Override in adapters that implement caching.
        """
        return False

    def clear_cache(self) -> None:
        """Clear the entire recall cache.

        Default implementation is a no-op (adapter has no cache).
        Override in adapters that implement caching.
        """
        pass

    def invalidate_cache(self, keys: Optional[set] = None) -> None:
        """Invalidate cache entries.

        Args:
            keys: Set of storage keys to invalidate. If None, invalidates all.

        Default implementation is a no-op (adapter has no cache).
        Override in adapters that implement caching.
        """
        pass

    # ── Knowledge Graph (v0.7.0+) ───────────────────────────────────────

    def recall_by_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories mentioning a specific entity.

        Default implementation returns empty list (adapter does not support
        knowledge graph). Override in adapters with ``graph: True`` capability.

        Args:
            entity_text: The entity text to search for.
            entity_type: Optional entity type filter.
            namespace: Optional namespace filter.
            limit: Maximum results.

        Returns:
            List of memory dicts.
        """
        return []

    def recall_by_relation(
        self,
        entity_text: str,
        relation_type: Optional[str] = None,
        direction: str = "both",
        namespace: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find memories connected to an entity via relations.

        Default implementation returns empty list. Override in adapters with
        ``graph: True`` capability.

        Args:
            entity_text: The entity to find relations for.
            relation_type: Optional relation type filter.
            direction: "outgoing", "incoming", or "both".
            namespace: Optional namespace filter.
            limit: Maximum results.

        Returns:
            List of memory dicts.
        """
        return []

    def recall_graph(
        self,
        entity_text: str,
        max_hops: int = 2,
        namespace: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Multi-hop graph traversal from an entity.

        Default implementation returns empty result. Override in adapters
        with ``graph: True`` capability.

        Args:
            entity_text: The starting entity.
            max_hops: Maximum traversal depth.
            namespace: Optional namespace filter.
            limit: Maximum memories to return.

        Returns:
            Dict with "entities" and "memories" lists.
        """
        return {"entities": [], "memories": []}

    def add_graph_relation(
        self,
        src_entity_text: str,
        dst_entity_text: str,
        relation_type: str,
        source_memory_key: Optional[str] = None,
        weight: float = 1.0,
        namespace: Optional[str] = None,
        confidence: str = "EXTRACTED",
    ) -> bool:
        """Add a relation between two entities in the knowledge graph.

        Default implementation returns False (not supported). Override in
        adapters with ``graph: True`` capability.

        Args:
            src_entity_text: Source entity text.
            dst_entity_text: Destination entity text.
            relation_type: Relation type (e.g. "prefers", "works_on").
            source_memory_key: Optional evidence memory key.
            weight: Relation strength (default 1.0).
            namespace: Optional namespace.
            confidence: Edge confidence label (EXTRACTED/INFERRED/AMBIGUOUS).

        Returns:
            True if relation was added.
        """
        return False

    def shortest_path(
        self,
        src_entity: str,
        dst_entity: str,
        max_hops: int = 4,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find the shortest path between two entities (v0.8.0).

        Default implementation returns not-found. Override in adapters with
        ``graph: True`` capability.

        Args:
            src_entity: Source entity text.
            dst_entity: Destination entity text.
            max_hops: Maximum path length to search.
            namespace: Optional namespace filter.

        Returns:
            Dict with "path", "length", and "found" keys.
        """
        return {"path": [], "length": -1, "found": False}

    def get_memory_impact(
        self,
        memory_key: str,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute the graph impact score of a memory (v0.8.0).

        Default implementation returns zero impact. Override in adapters with
        ``graph: True`` capability.

        Args:
            memory_key: The memory's storage_key.
            namespace: Optional namespace filter.

        Returns:
            Dict with "memory_id", "entity_count", "relation_count",
            "cross_namespace", and "impact_score" keys.
        """
        return {
            "memory_id": memory_key,
            "entity_count": 0,
            "relation_count": 0,
            "cross_namespace": False,
            "impact_score": 0.0,
        }

    def store_graph_entities(self, storage_key: str, text: str, namespace: Optional[str] = None) -> int:
        """Extract entities from text and store in the knowledge graph.

        Default implementation returns 0 (not supported). Override in
        adapters with ``graph: True`` capability.

        Args:
            storage_key: The memory's storage_key.
            text: Text to extract entities from.
            namespace: Optional namespace.

        Returns:
            Number of entities stored.
        """
        return 0

    # ── Memify Consolidation (v0.7.2+) ───────────────────────────────────

    def consolidate_memories(
        self,
        namespace: Optional[str] = None,
        min_co_occurrence: int = 3,
        max_derived: int = 10,
        stale_days: int = 90,
        min_importance: float = 0.3,
    ) -> Dict[str, Any]:
        """Consolidate memories via Memify three-phase refinement.

        Default: returns empty result (not supported). Override in adapters
        with knowledge graph capability.

        Returns:
            Dict with derived_facts (list), edges_reinforced (int), decayed (int).
        """
        return {"derived_facts": [], "edges_reinforced": 0, "decayed": 0}

    # ── Multi-Mode Retrieval (v0.7.1+) ──────────────────────────────────

    def recall_by_time(
        self,
        start: datetime,
        end: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        namespaces: Optional[list] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories within a time range.

        Default implementation returns empty list. Override in adapters with
        time-range query support.

        Args:
            start: Start datetime (inclusive). Timezone-aware recommended.
            end: End datetime (exclusive). Defaults to now.
            filters: Optional metadata filters.
            limit: Maximum results (default 50).
            namespaces: Optional namespace filter.

        Returns:
            List of memory dicts ordered by created_at descending.
        """
        return []

    def recall_semantic(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespaces: Optional[list] = None,
    ) -> List[Dict[str, Any]]:
        """Pure vector similarity search.

        Default implementation returns empty list. Override in adapters with
        ``vector_search: True`` capability.

        Args:
            query: Natural language query.
            top_k: Number of results (default 10).
            filters: Optional metadata filters.
            namespaces: Optional namespace filter.

        Returns:
            List of memory dicts ordered by vector similarity descending.
        """
        return []

    def recall_hybrid(
        self,
        query: str,
        fts_weight: Optional[float] = None,
        vec_weight: Optional[float] = None,
        rrf_k: Optional[int] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        namespaces: Optional[list] = None,
    ) -> List[Dict[str, Any]]:
        """Explicit hybrid search with configurable RRF weights.

        Default implementation returns empty list. Override in adapters with
        both FTS and vector search capabilities.

        Args:
            query: Search query.
            fts_weight: FTS rank weight (default: adapter config).
            vec_weight: Vector rank weight (default: adapter config).
            rrf_k: RRF constant k (default: adapter config).
            limit: Maximum results.
            filters: Optional metadata filters.
            namespaces: Optional namespace filter.

        Returns:
            List of memory dicts ordered by fused RRF score descending.
        """
        return []

    def recall_multi_mode(
        self,
        query: str,
        modes: Optional[List[str]] = None,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        namespaces: Optional[list] = None,
        time_range: Optional[tuple] = None,
        entity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Unified multi-mode retrieval interface.

        Default implementation returns empty result. Override in adapters
        with multi-mode support.

        Args:
            query: Search query (used for fts/vector/hybrid modes).
            modes: Retrieval modes to execute. Default: ["fts", "vector"].
                   Options: "fts", "vector", "hybrid", "graph", "time", "entity".
            limit: Maximum results per mode.
            filters: Optional metadata filters.
            namespaces: Optional namespace filter.
            time_range: (start, end) for "time" mode.
            entity: Entity text for "entity"/"graph" modes.

        Returns:
            Dict with "modes", "merged", "mode_count", "total_count".
        """
        return {"modes": {}, "merged": [], "mode_count": 0, "total_count": 0}

    # ── Batch Operations (v0.5.4+) ──────────────────────────────────────

    def store_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
        """Store multiple memory entries in a single batch operation.

        Default implementation calls store_entry() for each entry. Override
        for atomic batch operations (e.g., SQLiteAdapter uses BEGIN/commit/rollback
        to ensure all-or-nothing semantics).

        Args:
            entries: List of MemoryEntry objects to persist.

        Returns:
            List of StoredMemory objects (same order as input) with full
            storage metadata populated by the adapter.
        """
        results = []
        for entry in entries:
            results.append(self.store_entry(entry))
        return results

    def delete_batch(self, storage_keys: List[str]) -> Dict[str, bool]:
        """Delete multiple memories by their storage keys.

        Default implementation calls delete() for each key. Override for
        atomic batch operations.

        Args:
            storage_keys: List of storage_key strings to delete.

        Returns:
            Dict mapping each storage_key to its deletion result (True if
            deleted, False if not found). Keys that cause exceptions will
            have False as their value.
        """
        results: Dict[str, bool] = {}
        for key in storage_keys:
            try:
                results[key] = self.delete(key)
            except Exception:
                results[key] = False
        return results

    def forget_expired(self) -> int:
        """Delete all expired memories.

        Override if adapter supports TTL/expiry.

        Returns:
            Number of memories deleted
        """
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get storage system statistics.

        Returns:
            Dict with stats like total_count, by_type breakdown, etc.
        """
        return {
            "adapter": self.name,
            "total_count": 0,
            "by_type": {},
            "capabilities": self.capabilities,
        }

    def get_profile(self) -> Dict[str, Any]:
        """Get user memory profile — structured summary for display.

        Returns aggregated statistics and representative content highlights.
        Used by CarryMem.get_memory_profile() to show users what AI remembers.

        Returns:
            Dict with:
            - summary: Human-readable string
            - total_memories: Total count
            - highlights: Top N representative memories by type
            - stats: Aggregated statistics (by_type, by_tier, confidence_avg)
            - last_updated: ISO timestamp
        """
        return {
            "summary": "No memories yet",
            "total_memories": 0,
            "highlights": {},
            "stats": {
                "by_type": {},
                "by_tier": {},
                "confidence_avg": 0.0,
            },
            "last_updated": None,
        }

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name (e.g., 'sqlite', 'supermemory')."""
        ...

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Declare what this adapter supports.

        Default capabilities (override as needed):
        - vector_search: Semantic similarity search
        - fts: Full-text search
        - ttl: Time-to-live / auto-expiry
        - batch: Atomic batch operations
        - graph: Graph-based relationships
        - versioning: Memory versioning (update/merge with history)
        - backup: Database backup/restore
        - audit: Audit log query
        - namespace_filtering: Recall with namespace scope filtering
        """
        return {
            "vector_search": False,
            "fts": False,
            "ttl": False,
            "batch": False,
            "graph": False,
            "versioning": False,
            "backup": False,
            "audit": False,
            "namespace_filtering": False,
        }

    # ── Optional methods (default: raise NotImplementedError) ────────────

    def export_data(self) -> str:
        """Export all stored data as a serialized string.

        Returns:
            Serialized data (e.g., JSON string, SQLite dump).

        Raises:
            NotImplementedError: If the adapter does not support export.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement export_data()")

    def import_data(self, data: str) -> int:
        """Import previously exported data.

        Args:
            data: Serialized data string as produced by :meth:`export_data`.

        Returns:
            Number of entries imported.

        Raises:
            NotImplementedError: If the adapter does not support import.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement import_data()")

    def search_fulltext(self, query: str) -> list[dict]:
        """Full-text search across all stored entries.

        This is a convenience wrapper around :meth:`recall` with
        ``update_access=False``. Results are ranked by the adapter's
        recall ranking mechanism. Override for adapter-specific raw search.

        Args:
            query: Free-text search query string.

        Returns:
            List of matching entry dicts.
        """
        results: List[StoredMemory] = self.recall(query, update_access=False)
        return [r.to_dict() for r in results]

    def log_audit(
        self,
        operation: str,
        storage_key: Optional[str] = None,
        memory_type: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an audit event. No-op if audit is not configured.

        Args:
            operation: Operation name (e.g., "remember", "update", "delete").
            storage_key: Storage key of the affected memory, if applicable.
            memory_type: Type of the memory, if applicable.
            success: Whether the operation succeeded.
            details: Additional details dict.
        """
        audit = getattr(self, "_audit", None)
        if audit:
            audit.log_operation(
                operation,
                storage_key=storage_key,
                memory_type=memory_type,
                success=success,
                details=details,
            )

    def query_audit(self, filter_: Optional[Any] = None) -> list:
        """Query audit log entries. Returns empty list if audit is not configured.

        Args:
            filter_: AuditFilter object to narrow results.

        Returns:
            List of audit event dicts, or empty list if audit is not configured.
        """
        audit = getattr(self, "_audit", None)
        if audit:
            return audit.query(filter_)  # type: ignore[no-any-return]
        return []


@runtime_checkable
class AsyncStorageAdapter(Protocol):
    """Protocol for async storage adapters.

    Use this when your storage backend requires async I/O
    (e.g., HTTP APIs, async database drivers).

    Same interface as StorageAdapter, but all methods are async.
    """

    # ── Current API (v0.5.4+) ───────────────────────────────────────────

    async def store_entry(self, entry: MemoryEntry) -> StoredMemory:
        """Store a MemoryEntry and return StoredMemory with full metadata."""

    async def store(self, entry: dict) -> str:
        """Store a dict entry and return the storage_key."""

    async def store_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
        """Batch store entries, returning full metadata for each."""

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory by its entry ID."""

    async def delete_batch(self, storage_keys: List[str]) -> Dict[str, bool]:
        """Batch delete by storage keys, returning per-key result."""

    async def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[list] = None,
        update_access: bool = False,
    ) -> List[StoredMemory]:
        """Retrieve memories matching the query asynchronously."""

    async def forget_expired(self) -> int:
        """Delete expired memories asynchronously."""

    async def get_stats(self) -> Dict[str, Any]:
        """Return adapter statistics asynchronously."""

    @property
    def name(self) -> str:
        """Human-readable adapter name."""

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Mapping of capability name to whether it is supported."""


class TestStorageAdapterContract:
    """Base class for adapter contract tests.

    All adapters must pass these tests to be considered valid.
    Inherit from this class and implement the abstract setUp method.

    Example:
        class TestSQLiteAdapter(TestStorageAdapterContract):
            def setUp(self):
                self.adapter = SQLiteAdapter(":memory:")

            def test_custom_behavior(self):
                # Add adapter-specific tests
                ...
    """

    adapter: StorageAdapter

    def test_store_entry_returns_stored_memory(self):
        """store_entry() must return StoredMemory with storage_key and metadata."""
        entry = MemoryEntry(
            id="test-001",
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
        )
        stored = self.adapter.store_entry(entry)

        assert isinstance(stored, StoredMemory)
        assert stored.storage_key != ""
        assert stored.type == "user_preference"
        assert stored.content == "I prefer dark mode"
        assert stored.created_at is not None

    def test_store_entry_returns_full_metadata(self):
        """store_entry() must return StoredMemory with full metadata populated.

        Unlike store() which returns only the storage_key, store_entry() must
        return a StoredMemory with importance_score, version, created_at, and
        updated_at populated by the adapter — not the default 0.0/1/None/None
        values produced by StoredMemory.from_memory_entry().
        """
        entry = MemoryEntry(
            id="test-store-entry-001",
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
        )
        stored = self.adapter.store_entry(entry)

        assert isinstance(stored, StoredMemory)
        assert stored.storage_key != ""
        assert stored.type == "user_preference"
        assert stored.content == "I prefer dark mode"
        assert stored.created_at is not None
        assert stored.updated_at is not None
        assert stored.importance_score > 0.0
        assert stored.version >= 1

    def test_recall_finds_stored_memory(self):
        """recall() must find memories by content."""
        entry = MemoryEntry(
            id="test-002",
            type="fact_declaration",
            content="Python 3.9 is the minimum version",
            confidence=0.85,
        )
        self.adapter.store_entry(entry)

        results = self.adapter.recall("Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    def test_recall_with_filters(self):
        """recall() must support type filtering."""
        entry1 = MemoryEntry(id="f1", type="user_preference", content="pref content")
        entry2 = MemoryEntry(id="f2", type="fact_declaration", content="fact content")

        self.adapter.store_entry(entry1)
        self.adapter.store_entry(entry2)

        results = self.adapter.recall("content", filters={"type": "user_preference"})
        assert all(r.type == "user_preference" for r in results)

    def test_delete_removes_memory(self):
        """delete() must delete memory and return True."""
        entry = MemoryEntry(id="test-003", type="task_pattern", content="test task")
        stored = self.adapter.store_entry(entry)

        assert self.adapter.delete(stored.storage_key) is True
        assert self.adapter.delete(stored.storage_key) is False  # Already deleted

    def test_store_batch(self):
        """store_batch() must store all entries and return StoredMemory list.

        Verifies:
        - Returns list of StoredMemory with same length as input.
        - Each StoredMemory has a non-empty storage_key.
        - Results are in the same order as input entries.
        - Stored entries are retrievable via recall().
        """
        entries = [
            MemoryEntry(id=f"store-batch-{i}", type="fact_declaration", content=f"batch fact {i}") for i in range(5)
        ]

        stored = self.adapter.store_batch(entries)

        assert len(stored) == 5
        assert all(isinstance(s, StoredMemory) for s in stored)
        assert all(s.storage_key != "" for s in stored)
        assert all(s.content == f"batch fact {i}" for i, s in enumerate(stored))

        results = self.adapter.recall("batch fact", limit=10)
        assert len(results) >= 5

    def test_delete_batch(self):
        """delete_batch() must delete multiple memories and return per-key results.

        Verifies:
        - Returns dict mapping each storage_key to True/False.
        - Existing keys are deleted (True).
        - Non-existent keys return False.
        - Deleted entries are no longer retrievable.
        """
        entries = [
            MemoryEntry(id=f"del-batch-{i}", type="task_pattern", content=f"delete target {i}") for i in range(3)
        ]
        stored = self.adapter.store_batch(entries)
        keys_to_delete = [s.storage_key for s in stored]

        results = self.adapter.delete_batch(keys_to_delete)

        assert isinstance(results, dict)
        assert len(results) == 3
        assert all(v is True for v in results.values())

        mixed_keys = keys_to_delete[:1] + ["nonexistent_key_12345"]
        mixed_results = self.adapter.delete_batch(mixed_keys)

        assert mixed_results[keys_to_delete[0]] is False  # already deleted
        assert mixed_results["nonexistent_key_12345"] is False

    def test_adapter_name_and_capabilities(self):
        """Adapter must have name and capabilities."""
        assert self.adapter.name != ""
        assert isinstance(self.adapter.capabilities, dict)
        assert "vector_search" in self.adapter.capabilities

    def test_get_stats(self):
        """get_stats() must return valid statistics."""
        stats = self.adapter.get_stats()

        assert "adapter" in stats
        assert "total_count" in stats
        assert stats["adapter"] == self.adapter.name


__all__ = [
    # Data classes
    "MemoryEntry",
    "StoredMemory",
    # Abstract base class
    "StorageAdapter",
    # Async protocol
    "AsyncStorageAdapter",
    # Test contract
    "TestStorageAdapterContract",
]
