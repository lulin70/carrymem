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

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from carrymem.adapters.base import MemoryEntry, StoredMemory
from carrymem.adapters.sqlite.evidence import (
    VALID_RELATION_TYPES,
    VALID_SOURCE_KINDS,
    VALID_TARGET_KINDS,
)
from carrymem.adapters.sqlite.schema import (
    _SCHEMA_SQL,
    _V051_MIGRATION_SQL,
    _V062_GRAPH_SQL,
    _V080_MIGRATION_SQL,
    _V200_EVOLUTION_SQL,
    _V200_MIGRATION_ID,
    _V210_MIGRATION_ID,
    _V210_PHASE2_SQL,
)
from carrymem.exceptions import DatabaseError
from carrymem.monitoring import get_metrics_collector
from carrymem.utils.helpers import TIER_TTL, content_hash
from carrymem.utils.logger import logger

# aiosqlite is an optional dependency. Use Any to avoid mypy name-defined
# errors for aiosqlite.Connection / aiosqlite.Row when the package is
# absent at static-analysis time. Runtime import errors are handled below.
aiosqlite: Any = None
try:
    import aiosqlite
except ImportError:
    pass


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
            encryption_key: Not supported by this adapter. Passing a key
                raises ``NotImplementedError`` (fail-closed) — silently
                ignoring it would store plaintext where the caller expects
                encryption at rest.

        Raises:
            ImportError: aiosqlite is not installed.
            NotImplementedError: encryption_key was provided.
        """
        if aiosqlite is None:
            raise ImportError("AsyncSQLiteAdapter requires aiosqlite. " "Install with: pip install carrymem[async]")

        if encryption_key is not None:
            raise NotImplementedError(
                "AsyncSQLiteAdapter does not support encryption_key. "
                "Silently storing plaintext would violate the caller's "
                "encryption-at-rest expectation. Use the sync SQLiteAdapter "
                "with encryption_key for encrypted storage."
            )

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
            except sqlite3.OperationalError as e:
                if "already exists" in str(e).lower():
                    continue
                logger.warning("AsyncSQLiteAdapter: v0.5.1 migration step failed: %s", e)
            except Exception as e:
                logger.warning("AsyncSQLiteAdapter: v0.5.1 migration unexpected error: %s", e)

        try:
            await self._conn.executescript(_V062_GRAPH_SQL)
        except Exception as e:
            logger.debug("AsyncSQLiteAdapter: graph tables init skipped: %s", e)

        for sql in _V080_MIGRATION_SQL:
            try:
                await self._conn.execute(sql)
            except sqlite3.OperationalError as e:
                if "already exists" in str(e).lower():
                    continue
                logger.warning("AsyncSQLiteAdapter: v0.8.0 migration step failed: %s", e)
            except Exception as e:
                logger.warning("AsyncSQLiteAdapter: v0.8.0 migration unexpected error: %s", e)

        await self._run_migration(_V200_MIGRATION_ID, _V200_EVOLUTION_SQL)
        await self._run_migration(_V210_MIGRATION_ID, _V210_PHASE2_SQL)

    async def _run_migration(self, migration_id: str, statements: List[str]) -> None:
        """Run a ledgered migration with synchronous adapter fail-closed semantics."""
        assert self._conn is not None
        checksum = hashlib.sha256("\n".join(statements).encode("utf-8")).hexdigest()
        ledger_exists = await self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'carrymem_migrations'"
        )
        if await ledger_exists.fetchone() is None:
            row = None
        else:
            cursor = await self._conn.execute(
                "SELECT checksum, status FROM carrymem_migrations WHERE migration_id = ?",
                (migration_id,),
            )
            row = await cursor.fetchone()
        if row is not None:
            if row["checksum"] != checksum:
                raise DatabaseError(f"Migration {migration_id} checksum mismatch (fail-closed)")
            if row["status"] != "success":
                raise DatabaseError(
                    f"Migration {migration_id} has ledger status {row['status']!r}; "
                    "refusing to proceed (fail-closed)."
                )
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            await self._conn.execute("BEGIN IMMEDIATE")
            for sql in statements:
                await self._conn.execute(sql)
            await self._conn.execute(
                "INSERT INTO carrymem_migrations "
                "(migration_id, checksum, status, started_at, completed_at) "
                "VALUES (?, ?, 'success', ?, ?)",
                (migration_id, checksum, now_iso, now_iso),
            )
            await self._conn.commit()
        except sqlite3.Error as exc:
            await self._conn.rollback()
            raise DatabaseError(f"Migration {migration_id} failed (fail-closed): {exc}") from exc

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

    async def add_evidence_link(
        self,
        namespace: str,
        source_kind: str,
        source_id: str,
        source_snapshot_hash: str,
        target_kind: str,
        target_id: str,
        relation_type: str,
        support_weight: float = 1.0,
    ) -> Optional[str]:
        """Insert one immutable, idempotent provenance link."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")
        if relation_type not in VALID_RELATION_TYPES:
            raise ValueError(f"Invalid relation_type '{relation_type}'. Valid: {sorted(VALID_RELATION_TYPES)}")
        if source_kind not in VALID_SOURCE_KINDS:
            raise ValueError(f"Invalid source_kind '{source_kind}'. Valid: {sorted(VALID_SOURCE_KINDS)}")
        if target_kind not in VALID_TARGET_KINDS:
            raise ValueError(f"Invalid target_kind '{target_kind}'. Valid: {sorted(VALID_TARGET_KINDS)}")
        if not source_id or not target_id:
            raise ValueError("source_id and target_id must be non-empty")
        if not source_snapshot_hash:
            raise ValueError("source_snapshot_hash must be non-empty")
        if not 0.0 < support_weight <= 2.0:
            raise ValueError(f"support_weight must be in (0, 2], got {support_weight}")

        link_id = f"ev_{uuid.uuid4().hex}"
        try:
            cursor = await self._conn.execute(
                """INSERT OR IGNORE INTO memory_evidence_links
                   (id, namespace, source_kind, source_id, source_snapshot_hash,
                    target_kind, target_id, relation_type, support_weight, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    link_id,
                    namespace,
                    source_kind,
                    source_id,
                    source_snapshot_hash,
                    target_kind,
                    target_id,
                    relation_type,
                    support_weight,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            inserted = int(cursor.rowcount) > 0
            await self._conn.commit()
        except sqlite3.Error as e:
            logger.warning("add_evidence_link failed (%s): %s", relation_type, e)
            return None

        if inserted:
            get_metrics_collector().increment(f"evidence_link_{relation_type}")
            return link_id
        return None

    async def list_evidence_links(
        self,
        namespace: str,
        target_kind: Optional[str] = None,
        target_id: Optional[str] = None,
        source_kind: Optional[str] = None,
        source_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        include_stale: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List evidence links scoped to a namespace."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")

        conditions = ["el.namespace = ?"]
        params: List[Any] = [namespace]
        for column, value in (
            ("target_kind", target_kind),
            ("target_id", target_id),
            ("source_kind", source_kind),
            ("source_id", source_id),
            ("relation_type", relation_type),
        ):
            if value is not None:
                conditions.append(f"el.{column} = ?")
                params.append(value)
        if not include_stale:
            conditions.append(
                "EXISTS (SELECT 1 FROM memories m WHERE m.storage_key = el.source_id AND el.source_kind = 'memory')"
            )

        params.append(int(limit))
        try:
            cursor = await self._conn.execute(
                """SELECT el.id, el.namespace, el.source_kind, el.source_id, el.source_snapshot_hash,
                          el.target_kind, el.target_id, el.relation_type, el.support_weight, el.created_at
                   FROM memory_evidence_links el
                   WHERE """ + " AND ".join(conditions) + " ORDER BY el.created_at LIMIT ?",
                params,
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as e:
            logger.warning("list_evidence_links failed: %s", e)
            return []
        return [dict(row) for row in rows]

    async def get_unsupported_targets(self, namespace: str, candidate_target_ids: List[str]) -> List[str]:
        """Return candidate memory targets with no live memory evidence source."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")
        if not candidate_target_ids:
            return []

        placeholders = ",".join("?" * len(candidate_target_ids))
        try:
            cursor = await self._conn.execute(
                f"""SELECT DISTINCT el.target_id FROM memory_evidence_links el
                    WHERE el.namespace = ? AND el.target_kind = 'memory'
                      AND el.target_id IN ({placeholders})
                      AND NOT EXISTS (
                          SELECT 1 FROM memory_evidence_links el2
                          JOIN memories m2
                            ON el2.source_kind = 'memory' AND m2.storage_key = el2.source_id
                          WHERE el2.namespace = el.namespace
                            AND el2.target_kind = el.target_kind
                            AND el2.target_id = el.target_id
                      )""",
                [namespace, *candidate_target_ids],
            )
            rows = await cursor.fetchall()
        except sqlite3.Error as e:
            logger.warning("get_unsupported_targets failed: %s", e)
            return []
        return [row["target_id"] for row in rows]

    async def forget_memory(self, storage_key: str) -> bool:
        """Delete a memory and materialize unsupported provenance in one transaction."""
        if not self._conn:
            raise RuntimeError("Adapter not connected.")

        try:
            await self._conn.execute("BEGIN")
            cursor = await self._conn.execute(
                "DELETE FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._namespace),
            )
            deleted = int(cursor.rowcount) > 0
            if deleted:
                await self._conn.execute(
                    """UPDATE memory_observations
                       SET status = 'unsupported'
                       WHERE namespace = ? AND source_ref = ? AND status = 'valid'""",
                    (self._namespace, storage_key),
                )
                unsupported_cursor = await self._conn.execute(
                    """UPDATE memories
                       SET metadata = json_set(
                               COALESCE(metadata, '{}'),
                               '$.provenance_unsupported', 1,
                               '$.provenance_unsupported_at', ?
                           )
                       WHERE namespace = ?
                         AND json_extract(COALESCE(metadata, '{}'), '$.provenance_unsupported') IS NULL
                         AND storage_key IN (
                             SELECT DISTINCT el.target_id FROM memory_evidence_links el
                             WHERE el.namespace = ?
                               AND el.source_kind = 'memory'
                               AND el.source_id = ?
                               AND el.target_kind = 'memory'
                               AND NOT EXISTS (
                                   SELECT 1 FROM memory_evidence_links el2
                                   JOIN memories m2
                                     ON el2.source_kind = 'memory' AND m2.storage_key = el2.source_id
                                   WHERE el2.namespace = el.namespace
                                     AND el2.target_kind = el.target_kind
                                     AND el2.target_id = el.target_id
                               )
                         )""",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        self._namespace,
                        self._namespace,
                        storage_key,
                    ),
                )
                unsupported_count = int(unsupported_cursor.rowcount)
            else:
                unsupported_count = 0
            await self._conn.commit()
        except sqlite3.Error:
            await self._conn.rollback()
            raise

        if unsupported_count:
            get_metrics_collector().increment("evidence_derived_unsupported", value=unsupported_count)
        return deleted

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
        return int(row["cnt"]) if row else 0

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
