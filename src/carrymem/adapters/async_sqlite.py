"""Async SQLite adapter using aiosqlite (v0.7.2).

Provides native async I/O for high-concurrency scenarios. Requires
``pip install carrymem[async]``.

Design:
  - Same SQL as SQLiteAdapter but with aiosqlite connections
  - Schema initialization reuses SchemaManager's SQL strings
  - Core async methods: store_entry, recall, forget_memory, count, close
  - Dual-mode coexistence: sync SQLiteAdapter (zero-dep) + AsyncSQLiteAdapter ([async] extra)

Usage:
    adapter = AsyncSQLiteAdapter(":memory:")
    await adapter.connect()
    stored = await adapter.store_entry(entry)
    results = await adapter.recall("query")
    await adapter.close()
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from carrymem.adapters.base import MemoryEntry, StoredMemory
from carrymem.adapters.sqlite.schema import _SCHEMA_SQL, _V051_MIGRATION_SQL, _V062_GRAPH_SQL, _V080_MIGRATION_SQL
from carrymem.utils.helpers import TIER_TTL, content_hash
from carrymem.utils.logger import logger

try:
    import aiosqlite
except ImportError:
    aiosqlite = None  # type: ignore[assignment]


class AsyncSQLiteAdapter:
    """Async SQLite adapter using aiosqlite (v0.7.2).

    Requires ``pip install carrymem[async]``.
    Same SQL as SQLiteAdapter but with native async I/O.

    Not a subclass of StorageAdapter — uses a different connection model
    (aiosqlite.Connection vs sqlite3.Connection). Implements the core
    subset of StorageAdapter methods as async.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        namespace: str = "default",
        encryption_key: Optional[str] = None,
    ):
        """Initialize the async adapter.

        Args:
            db_path: Database path (default: ~/.carrymem/memories.db).
            namespace: Namespace scope.
            encryption_key: Optional encryption key (not yet implemented).
        """
        if aiosqlite is None:
            raise ImportError("AsyncSQLiteAdapter requires aiosqlite. " "Install with: pip install carrymem[async]")

        if db_path is None:
            import os

            db_path = os.path.expanduser("~/.carrymem/memories.db")

        self._db_path = db_path
        self._namespace = namespace
        self._conn: Optional[aiosqlite.Connection] = None
        self._connected = False

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {"fts": True, "graph": True, "vector_search": False, "async": True}

    async def connect(self) -> None:
        """Open the async database connection and initialize schema."""
        if self._connected and self._conn:
            return

        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        await self._init_schema()
        await self._conn.commit()
        self._connected = True
        logger.info("AsyncSQLiteAdapter connected to %s", self._db_path)

    async def _init_schema(self) -> None:
        """Initialize schema by executing the same SQL as SchemaManager."""
        assert self._conn is not None
        await self._conn.executescript(_SCHEMA_SQL)

        for sql in _V051_MIGRATION_SQL:
            try:
                await self._conn.execute(sql)
            except Exception:
                pass

        try:
            await self._conn.executescript(_V062_GRAPH_SQL)
        except Exception as e:
            logger.debug("AsyncSQLiteAdapter: graph tables init skipped: %s", e)

        for sql in _V080_MIGRATION_SQL:
            try:
                await self._conn.execute(sql)
            except Exception:
                pass

    async def store_entry(self, entry: MemoryEntry) -> StoredMemory:
        """Store a MemoryEntry and return the complete StoredMemory."""
        if not self._conn:
            raise RuntimeError("Adapter not connected. Call await adapter.connect() first.")

        storage_key = content_hash(entry.content + entry.id)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        ttl = TIER_TTL.get(entry.tier)
        expires_at = (now + ttl).isoformat() if ttl else None
        metadata_json = json.dumps(entry.metadata) if entry.metadata else "{}"

        await self._conn.execute(
            """INSERT INTO memories
               (id, type, content, raw_text, confidence, tier, source_layer,
                reasoning, suggested_action, recall_hint, metadata, storage_key,
                namespace, created_at, updated_at, expires_at, access_count,
                content_hash, importance_score, version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.type,
                entry.content,
                entry.raw_text,
                entry.confidence,
                entry.tier,
                entry.source_layer,
                entry.reasoning,
                entry.suggested_action,
                json.dumps(entry.recall_hint) if entry.recall_hint else None,
                metadata_json,
                storage_key,
                self._namespace,
                now_iso,
                now_iso,
                expires_at,
                0,
                content_hash(entry.content),
                0.0,
                1,
            ),
        )
        # FTS5 maintained automatically by memories_ai trigger (defined in _SCHEMA_SQL)

        await self._conn.commit()

        return StoredMemory(
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
            namespace=self._namespace,
            created_at=now,
            updated_at=now,
            expires_at=now + ttl if ttl else None,
            access_count=0,
            importance_score=0.0,
            version=1,
        )

    async def recall(
        self,
        query: str,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Recall memories by FTS5 full-text search."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")

        ns_list = namespaces or [self._namespace]
        placeholders = ",".join("?" * len(ns_list))

        cursor = await self._conn.execute(
            f"""SELECT m.* FROM memories m
                JOIN memories_fts f ON m.rowid = f.rowid
                WHERE memories_fts MATCH ?
                  AND m.namespace IN ({placeholders})
                  AND m.superseded_at IS NULL
                ORDER BY rank
                LIMIT ?""",
            (query, *ns_list, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def forget_memory(self, storage_key: str) -> bool:
        """Delete a memory by storage_key."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")

        cursor = await self._conn.execute("DELETE FROM memories WHERE storage_key = ?", (storage_key,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def count(self, namespace: Optional[str] = None) -> int:
        """Count memories in a namespace."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")

        ns = namespace or self._namespace
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE namespace = ? AND superseded_at IS NULL",
            (ns,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._connected = False
            logger.info("AsyncSQLiteAdapter connection closed")

    async def __aenter__(self) -> "AsyncSQLiteAdapter":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.close()
        return False
