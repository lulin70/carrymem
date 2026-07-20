"""CRUD operations for SQLiteAdapter."""

import json
import sqlite3
import struct
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ...scoring import calculate_importance
from ...utils.helpers import TIER_TTL, content_hash
from ...utils.logger import logger
from ..base import MemoryEntry, StoredMemory


class CRUDOperations:
    """Handles create, read, update, delete operations on memories."""

    def __init__(
        self,
        adapter,
        conn_mgr,
        serializer,
        supersede,
        cache,
        audit,
        embedding_model,
        embedding_dim: int,
    ) -> None:
        """Initialize CRUD operations with explicit dependencies.

        Args:
            adapter: SQLiteAdapter reference (for public API: encrypt_field, namespace).
            conn_mgr: ConnectionManager instance.
            serializer: RowSerializer instance.
            supersede: SupersedeManager instance.
            cache: RecallCache instance or None.
            audit: AuditLogger instance or None.
            embedding_model: Embedding model instance or None.
            embedding_dim: Embedding dimension (int).
        """
        self._adapter = adapter
        self._conn_mgr = conn_mgr
        self._serializer = serializer
        self._supersede = supersede
        self._cache = cache
        self._audit = audit
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim

    def remember(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        """Insert (or dedupe) a memory entry and invalidate the cache."""
        with self._conn_mgr.file_lock:
            result = self._remember_impl(entry, _skip_commit)
        if self._adapter.enable_cache and self._cache:
            self._cache.invalidate(self._adapter.namespace)
        return result

    def _remember_impl(self, entry: MemoryEntry, _skip_commit: bool = False) -> StoredMemory:
        conn = self._conn_mgr.get_connection()
        c_hash = content_hash(entry.content, entry.type)

        existing = conn.execute(
            "SELECT storage_key, raw_text FROM memories WHERE content_hash = ? AND namespace = ?",
            (c_hash, self._adapter.namespace),
        ).fetchone()
        if existing:
            return self._handle_existing_memory(conn, existing, entry, c_hash)

        storage_key = f"cm_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{c_hash[:8]}"
        now = datetime.now(timezone.utc)

        ttl = TIER_TTL.get(entry.tier)
        expires_at = (now + ttl).isoformat() if ttl else None

        metadata_json = json.dumps(entry.metadata) if entry.metadata else "{}"
        recall_hint_json = json.dumps(entry.recall_hint) if entry.recall_hint else None
        original_message = entry.metadata.get("original_message", "") if entry.metadata else ""

        imp_score = calculate_importance(
            confidence=entry.confidence,
            memory_type=entry.type,
            created_at=now,
            access_count=0,
            now=now,
        )

        store_content = self._adapter.encrypt_field(entry.content)
        store_original = self._adapter.encrypt_field(original_message)
        store_raw_text = self._adapter.encrypt_field(entry.raw_text)

        conn.execute(
            """INSERT INTO memories
               (id, type, content, raw_text, original_message, confidence, tier,
                source_layer, reasoning, suggested_action, recall_hint,
                metadata, storage_key, namespace, created_at, updated_at, expires_at,
                access_count, content_hash, importance_score, last_accessed_at, version,
                memory_nature, version_chain_id, version_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, 1, ?, ?, ?)""",
            (
                entry.id or storage_key,
                entry.type,
                store_content,
                store_raw_text,
                store_original,
                entry.confidence,
                entry.tier,
                entry.source_layer,
                entry.reasoning,
                entry.suggested_action,
                recall_hint_json,
                metadata_json,
                storage_key,
                self._adapter.namespace,
                now.isoformat(),
                now.isoformat(),
                expires_at,
                c_hash,
                imp_score,
                entry.memory_nature,
                entry.version_chain_id,
                entry.version_number,
            ),
        )
        if not _skip_commit:
            conn.commit()

        self._store_embedding_for_entry(conn, entry, storage_key, _skip_commit)

        if self._audit:
            self._audit.log_operation(
                operation="remember",
                storage_key=storage_key,
                memory_type=entry.type,
                success=True,
                details={"confidence": entry.confidence, "tier": entry.tier},
            )

        self._supersede.auto_supersede(conn, storage_key, entry, self._adapter.namespace)

        # Commit any writes from _auto_supersede
        try:
            conn.commit()
        except sqlite3.Error as e:
            logger.debug("Post-supersede commit failed: %s", e)

        self._init_state_version_chain(conn, storage_key, entry)

        stored = StoredMemory.from_memory_entry(entry, storage_key=storage_key, created_at=now)
        stored.importance_score = imp_score
        stored.version = 1
        return stored

    def _handle_existing_memory(self, conn, existing, entry, c_hash) -> StoredMemory:
        """Handle dedupe update for an existing memory row; returns StoredMemory."""
        if not existing["raw_text"] and entry.raw_text:
            try:
                # v0.5.2: Invalidate summary cache when raw_text is populated
                # (summary was generated from empty raw_text, now stale)
                conn.execute(
                    "UPDATE memories SET raw_text = ?, summary = NULL, summary_level = NULL " "WHERE storage_key = ?",
                    (self._adapter.encrypt_field(entry.raw_text), existing["storage_key"]),
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.debug("Failed to update raw_text for existing memory: %s", e)
        stored = self._serializer.row_to_stored(
            conn.execute(
                "SELECT * FROM memories WHERE content_hash = ? AND namespace = ?",
                (c_hash, self._adapter.namespace),
            ).fetchone()
        )
        return stored  # type: ignore[no-any-return]

    def _store_embedding_for_entry(self, conn, entry, storage_key, _skip_commit) -> None:
        """Compute and store the embedding vector for a freshly-inserted memory, if enabled."""
        if not (self._adapter.enable_vector and self._embedding_model):
            return
        text_to_embed = entry.raw_text or entry.content
        if not text_to_embed:
            return
        try:
            embedding = self._embedding_model.encode(text_to_embed)
            memory_id = entry.id or storage_key
            conn.execute(
                "INSERT OR REPLACE INTO memory_vectors(memory_id, embedding) VALUES(?, ?)",
                (memory_id, struct.pack(f"{self._embedding_dim}f", *embedding.tolist())),
            )
            if not _skip_commit:
                conn.commit()
        except (sqlite3.Error, struct.error, ValueError, TypeError) as e:
            logger.warning("Failed to store embedding: %s", e)

    def _init_state_version_chain(self, conn, storage_key, entry) -> None:
        """Set initial version_chain_id for state memories if not set by supersede."""
        if not (entry.memory_nature == "state" and not entry.version_chain_id):
            return
        try:
            conn.execute(
                "UPDATE memories SET version_chain_id = ? WHERE storage_key = ? AND version_chain_id IS NULL",
                (storage_key, storage_key),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.debug("Failed to set initial version_chain_id: %s", e)

    def store_batch(self, entries: List[MemoryEntry]) -> List[StoredMemory]:
        """Insert multiple entries in a single atomic transaction.

        Uses BEGIN/commit/rollback to ensure all-or-nothing semantics: if any
        entry fails, the entire batch is rolled back and the exception re-raised.
        """
        with self._conn_mgr.file_lock:
            conn = self._conn_mgr.get_connection()
            results = []
            try:
                conn.execute("BEGIN")
                for entry in entries:
                    result = self._remember_impl(entry, _skip_commit=True)
                    results.append(result)
                conn.commit()
            except (sqlite3.Error, ValueError) as e:
                conn.rollback()
                logger.warning("Batch store failed, rolled back: %s", e)
                raise
        if self._adapter.enable_cache and self._cache:
            self._cache.invalidate(self._adapter.namespace)
        return results

    def delete_batch(self, storage_keys: List[str]) -> Dict[str, bool]:
        """Delete multiple memories by storage_key in a single atomic transaction.

        Uses BEGIN/commit/rollback to ensure atomicity on SQL errors. Keys that
        are not found are recorded as False (not an error). On sqlite3.Error the
        entire batch is rolled back and the exception re-raised.
        """
        results: Dict[str, bool] = {}
        with self._conn_mgr.file_lock:
            conn = self._conn_mgr.get_connection()
            try:
                conn.execute("BEGIN")
                for key in storage_keys:
                    memory_id = None
                    row = conn.execute(
                        "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
                        (key, self._adapter.namespace),
                    ).fetchone()
                    if row:
                        memory_id = row["id"]
                    cursor = conn.execute(
                        "DELETE FROM memories WHERE storage_key = ? AND namespace = ?",
                        (key, self._adapter.namespace),
                    )
                    results[key] = cursor.rowcount > 0
                    if memory_id and self._adapter.enable_vector:
                        try:
                            conn.execute(
                                "DELETE FROM memory_vectors WHERE memory_id = ?",
                                (memory_id,),
                            )
                        except sqlite3.Error as e:
                            logger.warning("Failed to delete vector for memory %s: %s", memory_id, e)
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                logger.warning("Batch delete failed, rolled back: %s", e)
                raise
        if self._adapter.enable_cache and self._cache:
            deleted_keys = {k for k, v in results.items() if v}
            if deleted_keys:
                self._cache.invalidate_keys(self._adapter.namespace, deleted_keys)
        if self._audit:
            for key, ok in results.items():
                self._audit.log_operation(
                    operation="forget",
                    storage_key=key,
                    success=ok,
                )
        return results

    def forget(self, storage_key: str) -> bool:
        """Delete a memory and its vector by storage key."""
        with self._conn_mgr.file_lock:
            conn = self._conn_mgr.get_connection()
            memory_id = None
            row = conn.execute(
                "SELECT id FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._adapter.namespace),
            ).fetchone()
            if row:
                memory_id = row["id"]
            cursor = conn.execute(
                "DELETE FROM memories WHERE storage_key = ? AND namespace = ?",
                (storage_key, self._adapter.namespace),
            )
            if memory_id and self._adapter.enable_vector:
                try:
                    conn.execute(
                        "DELETE FROM memory_vectors WHERE memory_id = ?",
                        (memory_id,),
                    )
                except sqlite3.Error as e:
                    logger.warning("Failed to delete vector for memory %s: %s", memory_id, e)
            conn.commit()
            result = cursor.rowcount > 0
        if self._adapter.enable_cache and self._cache and result:
            self._cache.invalidate_keys(self._adapter.namespace, {storage_key})
        if self._audit:
            self._audit.log_operation(
                operation="forget",
                storage_key=storage_key,
                success=result,
            )
        return result  # type: ignore[no-any-return]

    def forget_expired(self) -> int:
        """Delete expired memories and return the count removed."""
        with self._conn_mgr.file_lock:
            conn = self._conn_mgr.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                "DELETE FROM memories WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at < ?",
                (self._adapter.namespace, now),
            )
            conn.commit()
            count = cursor.rowcount
        if self._adapter.enable_cache and self._cache and count > 0:
            self._cache.invalidate(self._adapter.namespace)
        if self._audit:
            self._audit.log_operation(
                operation="forget_expired",
                success=count > 0,
                details={
                    "namespace": self._adapter.namespace,
                    "deleted_count": count,
                },
            )
        return count  # type: ignore[no-any-return]

    def get_by_key(self, storage_key: str) -> Optional[StoredMemory]:
        """Return a stored memory by key, or None if not found."""
        conn = self._conn_mgr.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM memories WHERE storage_key = ?",
                (storage_key,),
            ).fetchone()
            if row:
                return self._serializer.row_to_stored(row)  # type: ignore[no-any-return]
            return None
        except sqlite3.Error as e:
            logger.debug("_get_by_key failed: %s", e)
            return None

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Optional[StoredMemory]:
        """Update memory content under the file lock, returning the new version."""
        with self._conn_mgr.file_lock:
            return self._update_memory_impl(storage_key, new_content, reason)

    def _update_memory_impl(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Optional[StoredMemory]:
        conn = self._conn_mgr.get_connection()
        row = conn.execute(
            "SELECT * FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._adapter.namespace),
        ).fetchone()
        if not row:
            return None

        stored = self._serializer.row_to_stored(row)
        if not stored:
            return None

        old_version = stored.version
        new_version = old_version + 1

        version_id = f"v_{storage_key}_{new_version}"
        now = datetime.now(timezone.utc)
        conn.execute(
            """INSERT INTO memory_versions (version_id, memory_id, version,
               content, confidence, changed_at, change_reason, namespace)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                stored.id,
                old_version,
                stored.content,
                stored.confidence,
                now.isoformat(),
                reason or f"Update to version {new_version}",
                self._adapter.namespace,
            ),
        )

        new_c_hash = content_hash(new_content, stored.type)
        new_imp_score = calculate_importance(
            confidence=stored.confidence,
            memory_type=stored.type,
            created_at=stored.created_at or now,
            access_count=stored.access_count,
            now=now,
        )

        encrypted_content = self._adapter.encrypt_field(new_content)

        conn.execute(
            """UPDATE memories SET content = ?, content_hash = ?, version = ?,
               importance_score = ?, updated_at = ?,
               summary = NULL, summary_level = NULL
               WHERE storage_key = ? AND namespace = ?""",
            (
                encrypted_content,
                new_c_hash,
                new_version,
                new_imp_score,
                now.isoformat(),
                storage_key,
                self._adapter.namespace,
            ),
        )
        conn.commit()

        if self._audit:
            self._audit.log_operation(
                operation="update",
                storage_key=storage_key,
                memory_type=stored.type,
                success=True,
                details={
                    "namespace": self._adapter.namespace,
                    "memory_key": storage_key,
                    "old_version": old_version,
                    "new_version": new_version,
                    "reason": reason,
                },
            )

        if self._adapter.enable_cache and self._cache:
            self._cache.invalidate_keys(self._adapter.namespace, {storage_key})

        updated_row = conn.execute(
            "SELECT * FROM memories WHERE storage_key = ? AND namespace = ?",
            (storage_key, self._adapter.namespace),
        ).fetchone()
        return self._serializer.row_to_stored(updated_row)  # type: ignore[no-any-return]
