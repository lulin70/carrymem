"""
Storage Adapter Abstract Base Class and MemoryEntry data class.

v3.2 Update (2026-04-20):
- Method rename: store→remember, retrieve→recall, delete→forget
- Added StoredMemory dataclass (extends MemoryEntry with storage metadata)
- Added async interface support
- Added TestStorageAdapterContract for adapter validation

Pure Upstream Mode (v0.3.0): MCE does not store memories itself.
Instead, it outputs standardized MemoryEntry objects that downstream systems
consume via implementations of this adapter interface.

Available official adapters (planned):
- SQLiteAdapter: Default implementation for dev/demo (v0.6)
- SupermemoryAdapter: Bridges to supermemory.ai cloud service
- ObsidianAdapter: Writes to local Obsidian vault markdown files
- Mem0Adapter: Connects to Mem0 self-hosted instance

Community adapters are welcome!
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


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
    confidence: float = 0.0
    tier: int = 2
    source_layer: str = "unknown"
    reasoning: str = ""
    suggested_action: str = "store"
    recall_hint: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (JSON-safe)."""
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "confidence": self.confidence,
            "tier": self.tier,
            "source_layer": self.source_layer,
            "reasoning": self.reasoning,
            "suggested_action": self.suggested_action,
            "recall_hint": self.recall_hint,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Deserialize from dict."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "unknown"),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.0),
            tier=data.get("tier", 2),
            source_layer=data.get("source_layer", "unknown"),
            reasoning=data.get("reasoning", ""),
            suggested_action=data.get("suggested_action", "store"),
            recall_hint=data.get("recall_hint"),
            metadata=data.get("metadata", {}),
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict (JSON-safe), including storage fields."""
        base = super().to_dict()
        base.update({
            "storage_key": self.storage_key,
            "namespace": self.namespace,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "importance_score": self.importance_score,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "version": self.version,
            "vector_embedding": self.vector_embedding,
            "storage_metadata": self.storage_metadata,
        })
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
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredMemory":
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

        return cls(
            id=data.get("id", ""),
            type=data.get("type", "unknown"),
            content=data.get("content", ""),
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
        )


class StorageAdapter(ABC):
    """Abstract base class for downstream storage adapters.

    Every downstream storage system that wants to receive MCE's
    classification output must implement this interface.

    v3.2 Interface (2026-04-20):
    - remember(): Store a memory entry
    - recall(): Retrieve memories matching query
    - forget(): Delete a memory by ID

    Implementation guide:
    1. Subclass StorageAdapter
    2. Implement all abstract methods
    3. Set name and capabilities properties
    4. Pass TestStorageAdapterContract (see tests/adapters/)

    Example:
        class SQLiteAdapter(StorageAdapter):
            @property
            def name(self) -> str:
                return "sqlite"

            def remember(self, entry: MemoryEntry) -> StoredMemory:
                cursor.execute(
                    "INSERT INTO memories (id, type, content) VALUES (?, ?, ?)",
                    (entry.id, entry.type, entry.content)
                )
                return StoredMemory.from_memory_entry(entry, storage_key=entry.id)

            def recall(self, query: str, filters: Dict = None, limit: int = 20) -> List[StoredMemory]:
                # FTS5 search implementation
                ...

            def forget(self, storage_key: str) -> bool:
                cursor.execute("DELETE FROM memories WHERE id = ?", (storage_key,))
                return cursor.rowcount > 0
    """

    @abstractmethod
    def remember(self, entry: MemoryEntry) -> StoredMemory:
        """Store a memory entry.

        Args:
            entry: The MemoryEntry to persist

        Returns:
            StoredMemory with storage metadata attached
        """
        ...

    def remember_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
        """Store multiple memory entries.

        Default implementation calls remember() for each entry.
        Override for atomic batch operations.

        Args:
            entries: List of MemoryEntry objects to persist

        Returns:
            List of StoredMemory objects (same order as input)
        """
        return [self.remember(entry) for entry in entries]

    @abstractmethod
    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[StoredMemory]:
        """Retrieve memories matching a query.

        Args:
            query: Search query (keywords or natural language)
            filters: Optional filters (e.g., {"type": "user_preference", "tier": 1})
            limit: Maximum number of results

        Returns:
            List of StoredMemory objects matching the query
        """
        ...

    @abstractmethod
    def forget(self, storage_key: str) -> bool:
        """Delete a memory by its storage key.

        Args:
            storage_key: The storage_key from StoredMemory

        Returns:
            True if deleted, False if not found
        """
        ...

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
        """
        return {
            "vector_search": False,
            "fts": False,
            "ttl": False,
            "batch": False,
            "graph": False,
        }


@runtime_checkable
class AsyncStorageAdapter(Protocol):
    """Protocol for async storage adapters.

    Use this when your storage backend requires async I/O
    (e.g., HTTP APIs, async database drivers).

    Same interface as StorageAdapter, but all methods are async.
    """

    async def remember(self, entry: MemoryEntry) -> StoredMemory:
        ...

    async def remember_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
        ...

    async def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[StoredMemory]:
        ...

    async def forget(self, storage_key: str) -> bool:
        ...

    async def forget_expired(self) -> int:
        ...

    async def get_stats(self) -> Dict[str, Any]:
        ...

    @property
    def name(self) -> str:
        ...

    @property
    def capabilities(self) -> Dict[str, bool]:
        ...


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

    def test_remember_returns_stored_memory(self):
        """remember() must return StoredMemory with storage_key."""
        entry = MemoryEntry(
            id="test-001",
            type="user_preference",
            content="I prefer dark mode",
            confidence=0.9,
        )
        stored = self.adapter.remember(entry)

        assert isinstance(stored, StoredMemory)
        assert stored.storage_key != ""
        assert stored.type == "user_preference"
        assert stored.content == "I prefer dark mode"
        assert stored.created_at is not None

    def test_recall_finds_stored_memory(self):
        """recall() must find memories by content."""
        entry = MemoryEntry(
            id="test-002",
            type="fact_declaration",
            content="Python 3.9 is the minimum version",
            confidence=0.85,
        )
        self.adapter.remember(entry)

        results = self.adapter.recall("Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    def test_recall_with_filters(self):
        """recall() must support type filtering."""
        entry1 = MemoryEntry(id="f1", type="user_preference", content="pref content")
        entry2 = MemoryEntry(id="f2", type="fact_declaration", content="fact content")

        self.adapter.remember(entry1)
        self.adapter.remember(entry2)

        results = self.adapter.recall("content", filters={"type": "user_preference"})
        assert all(r.type == "user_preference" for r in results)

    def test_forget_removes_memory(self):
        """forget() must delete memory and return True."""
        entry = MemoryEntry(id="test-003", type="task_pattern", content="test task")
        stored = self.adapter.remember(entry)

        assert self.adapter.forget(stored.storage_key) is True
        assert self.adapter.forget(stored.storage_key) is False  # Already deleted

    def test_remember_batch(self):
        """remember_batch() must store all entries."""
        entries = [
            MemoryEntry(id=f"batch-{i}", type="fact_declaration", content=f"fact {i}")
            for i in range(5)
        ]

        stored = self.adapter.remember_batch(entries)
        assert len(stored) == 5
        assert all(s.storage_key != "" for s in stored)

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
