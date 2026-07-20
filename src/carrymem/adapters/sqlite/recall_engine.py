"""Recall engine with FTS, vector, semantic search, and RRF fusion."""

import os
import sqlite3
import struct
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...scoring import calculate_importance
from ...utils.helpers import escape_like
from ...utils.language import _STOP_WORDS, has_cjk
from ...utils.logger import logger
from ..base import StoredMemory


class RecallEngine:
    """Multi-phase recall engine: FTS → Vector → Expansion → Semantic."""

    # Default throttle interval (seconds) for access_count/last_accessed_at updates.
    # Overridable via CARRYMEM_ACCESS_UPDATE_INTERVAL env var. 0 = always update.
    _DEFAULT_ACCESS_UPDATE_INTERVAL = 60

    def __init__(
        self,
        adapter,
        conn_mgr,
        serializer,
        cache,
        expander,
        merger,
        embedding_model,
        embedding_dim: int,
        rrf_k: int,
        rrf_fts_weight: float,
        rrf_vec_weight: float,
        rrf_type_boosts: Dict[str, float],
    ) -> None:
        """Initialize recall engine with explicit dependencies.

        Args:
            adapter: SQLiteAdapter reference (for public API: namespace, enable_cache,
                enable_vector, semantic_enabled).
            conn_mgr: ConnectionManager instance.
            serializer: RowSerializer instance.
            cache: RecallCache instance or None.
            expander: SemanticExpander instance or None.
            merger: ResultMerger instance or None.
            embedding_model: Embedding model instance or None.
            embedding_dim: Embedding dimension (int).
            rrf_k: RRF k parameter.
            rrf_fts_weight: RRF FTS weight.
            rrf_vec_weight: RRF vector weight.
            rrf_type_boosts: RRF type boost mapping.
        """
        self._adapter = adapter
        self._conn_mgr = conn_mgr
        self._serializer = serializer
        self._cache = cache
        self._expander = expander
        self._merger = merger
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        # RRF config lives on the engine so hybrid_search can override per-call
        # without mutating adapter state.
        self._rrf_k = rrf_k
        self._rrf_fts_weight = rrf_fts_weight
        self._rrf_vec_weight = rrf_vec_weight
        self._rrf_type_boosts = rrf_type_boosts

    @classmethod
    def _get_access_update_interval(cls) -> int:
        """Get throttle interval from environment variable.

        Returns:
            Interval in seconds. 0 means always update (backward compat).
        """
        val = os.getenv("CARRYMEM_ACCESS_UPDATE_INTERVAL")
        if val is None:
            return cls._DEFAULT_ACCESS_UPDATE_INTERVAL
        try:
            interval = int(val)
            return interval if interval >= 0 else cls._DEFAULT_ACCESS_UPDATE_INTERVAL
        except (ValueError, TypeError):
            return cls._DEFAULT_ACCESS_UPDATE_INTERVAL

    def _should_update_access(self, stored, now: Optional[datetime] = None) -> bool:
        """Throttle: skip access update if last_accessed_at is within interval.

        Defense-in-depth: type guard handles last_accessed_at as str (from DB
        deserialization) or datetime. Fail-open on parse error (trigger update).

        Args:
            stored: StoredMemory with last_accessed_at attribute.
            now: Current datetime for testing. If None, uses datetime.now(timezone.utc).

        Returns:
            True if access should be updated; False to skip (throttled).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        last = stored.last_accessed_at
        if last is None:
            return True  # First access — always update

        # Type guard: last_accessed_at may be str from DB deserialization
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last)
            except (ValueError, TypeError):
                return True  # Fail-open: parse error → trigger update

        # Normalize timezone-aware comparison
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        interval = self._get_access_update_interval()
        if interval <= 0:
            return True  # 0 = always update (backward compat / test mode)

        delta: float = (now - last).total_seconds()
        return bool(delta >= interval)

    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[StoredMemory]:
        """Run multi-phase recall with caching, returning matching stored memories."""
        if self._adapter.enable_cache and self._cache:
            cached = self._cache.get(self._adapter.namespace, query, filters, limit)
            if cached is not None:
                return [self._serializer.dict_to_stored(d) or StoredMemory() for d in cached]

        with self._conn_mgr.lock:
            results = self._recall_impl(query, filters, limit, namespaces, update_access=update_access)

        if self._adapter.enable_cache and self._cache and results:
            self._cache.put(
                self._adapter.namespace,
                query,
                filters,
                limit,
                [r.to_dict() for r in results],
            )

        return results  # type: ignore[no-any-return]

    def _recall_impl(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ):
        """Run multi-phase recall (FTS → Vector → Expansion → Semantic) with access update."""
        filters = filters or {}
        self._validate_recall_params(filters, limit, namespaces, query)
        self._apply_time_constraints(query, filters)

        where_clause, params = self._build_where_clause(filters, namespaces)

        if query and query.strip():
            # Phase 1: FTS search + context reconstruction
            rows = self._recall_fts_phase(query, where_clause, params, limit)
            # Phase 2: Vector search + RRF fusion
            rows = self._recall_vector_phase(query, where_clause, params, limit, rows)
            # Phase 3: Query expansion + semantic recall
            rows, is_final = self._recall_expansion_phase(query, where_clause, params, limit, rows)

            if is_final:
                # Semantic expansion succeeded — update access and return
                return self.recall_update_access(rows, update_access, filters, limit, is_stored=True)
        else:
            rows = self._execute_no_query_recall(where_clause, params, limit)

        # Phase 4: Batch access count update (normal path)
        return self.recall_update_access(rows, update_access, filters, limit, is_stored=False)

    def _validate_recall_params(self, filters, limit, namespaces, query):
        """Validate recall parameters. Raises ValueError on invalid input."""
        from .query_builder import _ALLOWED_FILTER_KEYS, _VALID_MEMORY_TYPES

        for key in filters:
            if key not in _ALLOWED_FILTER_KEYS:
                raise ValueError(f"Invalid filter key: '{key}'. Allowed keys: {_ALLOWED_FILTER_KEYS}")

        if filters.get("type") and filters["type"] not in _VALID_MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: '{filters['type']}'. Valid types: {_VALID_MEMORY_TYPES}")

        if limit < 0 or limit > 100000:
            raise ValueError(f"Limit must be between 0 and 100000, got {limit}")

        if namespaces:
            for ns in namespaces:
                if not ns or not isinstance(ns, str) or len(ns) > 128:
                    raise ValueError(f"Invalid namespace: '{ns}'. Must be non-empty string, max 128 chars.")

        if query and len(query) > 10000:
            raise ValueError(f"Query too long: {len(query)} chars (max 10000)")

    @staticmethod
    def _apply_time_constraints(query, filters):
        """Parse time expressions from query and apply to filters (in-place)."""
        from .query_builder import QueryBuilder

        time_constraints = QueryBuilder.parse_time_expressions(query or "")
        if not time_constraints:
            return

        if time_constraints.get("created_after") and not filters.get("created_after"):
            filters["created_after"] = time_constraints["created_after"]
        if time_constraints.get("created_before") and not filters.get("created_before"):
            filters["created_before"] = time_constraints["created_before"]
        if time_constraints.get("order_oldest"):
            filters["_order_oldest"] = True

    def _build_where_clause(self, filters, namespaces):
        """Build WHERE clause and params from filters and namespaces."""
        ns = namespaces or [self._adapter.namespace]
        placeholders = ",".join(["?"] * len(ns))
        conditions = [f"namespace IN ({placeholders})"]
        params = list(ns)

        if filters.get("type"):
            conditions.append("type = ?")
            params.append(filters["type"])
        elif not filters.get("include_session_summary", False):
            conditions.append("type != ?")
            params.append("session_summary")

        if filters.get("tier") is not None:
            conditions.append("tier = ?")
            params.append(filters["tier"])

        if filters.get("confidence_min") is not None:
            conditions.append("confidence >= ?")
            params.append(filters["confidence_min"])

        if filters.get("created_after"):
            conditions.append("created_at >= ?")
            params.append(filters["created_after"])

        if filters.get("created_before"):
            conditions.append("created_at <= ?")
            params.append(filters["created_before"])

        if not filters.get("include_superseded", False):
            conditions.append("(superseded_at IS NULL OR superseded_at = '')")

        if filters.get("session_id"):
            safe_sid = (
                filters["session_id"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace('"', '\\"')
            )
            conditions.append("metadata LIKE ? ESCAPE '\\'")
            params.append(f'%session_id": "{safe_sid}%')

        return "WHERE " + " AND ".join(conditions), params

    def _execute_no_query_recall(self, where_clause, params, limit):
        """Execute recall when no query is provided (importance-based ordering)."""
        conn = self._conn_mgr.get_connection()
        sql = f"""
            SELECT * FROM memories
            {where_clause}
            ORDER BY importance_score DESC, confidence DESC
            LIMIT ?
        """
        params.append(limit)
        return conn.execute(sql, params).fetchall()

    def _recall_fts_phase(self, query, where_clause, params, limit):
        """FTS search + context reconstruction."""
        keywords = " ".join(w for w in query.lower().split() if w not in _STOP_WORDS and len(w) > 1)

        from .query_builder import QueryBuilderWithContext

        if keywords and keywords != query.strip().lower():
            rows = self._fts_search(keywords, where_clause, params, limit)
        else:
            rows = self._fts_search(query, where_clause, params, limit)

        if not rows:
            rows = self._like_search(query, where_clause, params, limit)

        if not rows or len(rows) < max(3, limit // 4):
            qb = QueryBuilderWithContext(self._adapter, self._conn_mgr)
            rebuilt_query = qb.rebuild_context(query, keywords)
            if rebuilt_query and rebuilt_query != query and rebuilt_query != keywords:
                extra_rows = self._fts_search(rebuilt_query, where_clause, params, limit)
                if extra_rows:
                    seen_ids = {r[0] for r in rows if r}
                    for r in extra_rows:
                        if r and r[0] not in seen_ids:
                            rows.append(r)
                            seen_ids.add(r[0])

        return rows

    def _recall_vector_phase(self, query, where_clause, params, limit, rows):
        """Vector search + RRF fusion."""
        if self._adapter.enable_vector:
            vec_rows = self._vector_search(query, where_clause, params, limit)
            if vec_rows:
                rows = self._rrf_fuse(rows, vec_rows, limit)
        return rows

    def _recall_expansion_phase(self, query, where_clause, params, limit, rows):
        """Query expansion + semantic recall.

        Returns (results, is_final):
        - If semantic expansion succeeded: (list[StoredMemory], True)
        - Otherwise: (raw_rows, False)
        """
        from .query_builder import QueryBuilder

        expanded_queries = QueryBuilder.expand_query(query)
        if expanded_queries:
            seen_ids = self._collect_seen_ids(rows)
            rows = self._expand_with_fts(expanded_queries, where_clause, params, limit, rows, seen_ids)
            if len(rows) < limit:
                rows = self._expand_with_like(expanded_queries, where_clause, params, limit, rows, seen_ids)

        # Semantic expansion if results insufficient
        if self._adapter.semantic_enabled and len(rows) < limit and self._expander and self._merger:
            final_results = self._try_semantic_expansion(query, where_clause, params, limit, rows)
            if final_results is not None:
                return final_results, True

        return rows, False

    @staticmethod
    def _collect_seen_ids(rows) -> set:
        """Collect existing row IDs to avoid duplicates during expansion."""
        seen_ids = set()
        for r in rows:
            rid = r[0] if r else None
            if rid:
                seen_ids.add(rid)
        return seen_ids

    def _expand_with_fts(self, expanded_queries, where_clause, params, limit, rows, seen_ids):
        """Expand results using FTS search on expanded queries (mutates rows and seen_ids)."""
        for eq in expanded_queries:
            eq_rows = self._fts_search(eq, where_clause, params, limit)
            for r in eq_rows:
                rid = r[0] if r else None
                if rid and rid not in seen_ids:
                    rows.append(r)
                    seen_ids.add(rid)
            if len(rows) >= limit:
                break
        return rows

    def _expand_with_like(self, expanded_queries, where_clause, params, limit, rows, seen_ids):
        """Expand results using LIKE search on expanded queries (mutates rows and seen_ids)."""
        for eq in expanded_queries:
            eq_rows = self._like_search(eq, where_clause, params, limit)
            for r in eq_rows:
                rid = r[0] if r else None
                if rid and rid not in seen_ids:
                    rows.append(r)
                    seen_ids.add(rid)
            if len(rows) >= limit:
                break
        return rows

    def _try_semantic_expansion(self, query, where_clause, params, limit, rows):
        """Try semantic expansion. Returns list[StoredMemory] on success, None if no expansion."""
        expanded_rows = self._semantic_recall(query, where_clause, params, limit)
        expanded_results = [self._serializer.row_to_stored(r) for r in expanded_rows if r]
        if not expanded_results:
            return None

        original_results = [self._serializer.row_to_stored(r) for r in rows if r]
        merged = self._merger.merge(
            original_results=original_results,
            expanded_results=expanded_results,
            query=query,
            limit=limit,
            source="synonym",
        )
        final_results = []
        for item in merged:
            if isinstance(item, StoredMemory):
                final_results.append(item)
            elif isinstance(item, dict):
                stored = self._serializer.dict_to_stored(item)
                if stored:
                    final_results.append(stored)
        return final_results

    @staticmethod
    def increment_access(stored, batch_updates, now_iso, adapter=None):
        """Common access-count increment logic shared by stored/not-stored paths."""
        new_count = stored.access_count + 1
        new_score = calculate_importance(
            confidence=stored.confidence,
            memory_type=stored.type,
            created_at=stored.created_at or datetime.now(timezone.utc),
            access_count=new_count,
        )
        batch_updates.append((new_count, new_score, now_iso, stored.storage_key))
        stored.access_count = new_count
        stored.importance_score = new_score
        stored.last_accessed_at = datetime.fromisoformat(now_iso)

    def recall_update_access(self, rows, update_access=True, filters=None, limit=20, is_stored=False):
        """Batch access count update.

        If is_stored=True: rows are StoredMemory objects (from semantic expansion).
        If is_stored=False: rows are raw database rows (normal path with diversity filtering).

        P1-4: Throttled write — same memory's access_count/last_accessed_at is
        updated at most once per CARRYMEM_ACCESS_UPDATE_INTERVAL (default 60s).
        Throttle skip means in-memory access_count/importance_score are NOT
        incremented; they refresh from DB on next recall. Set interval=0 to
        always update (backward compat / test mode).
        """
        filters = filters or {}
        conn = self._conn_mgr.get_connection()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        results: list = []
        seen_keys: set = set()
        batch_updates: List[tuple] = []

        if is_stored:
            self._collect_stored_access_updates(rows, update_access, now, now_iso, seen_keys, batch_updates, results)
            if update_access and batch_updates:
                conn.executemany(
                    "UPDATE memories SET access_count = ?, "
                    "importance_score = ?, last_accessed_at = ? "
                    "WHERE storage_key = ?",
                    batch_updates,
                )
        else:
            self._collect_row_access_updates(
                rows, update_access, now, now_iso, limit, seen_keys, batch_updates, results
            )
            if update_access and batch_updates:
                conn.executemany(
                    "UPDATE memories SET access_count = access_count + 1, "
                    "importance_score = ?, last_accessed_at = ? "
                    "WHERE storage_key = ?",
                    [(score, ts, key) for (_, score, ts, key) in batch_updates],
                )

        conn.commit()

        if not is_stored and filters.get("_order_oldest") and results:
            results.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))

        return results

    def _collect_stored_access_updates(
        self, rows, update_access, now, now_iso, seen_keys, batch_updates, results
    ) -> None:
        """Dedupe StoredMemory rows and queue access-count updates (is_stored path)."""
        for stored in rows:
            if stored.storage_key not in seen_keys:
                seen_keys.add(stored.storage_key)
                if update_access and self._should_update_access(stored, now):
                    self.increment_access(stored, batch_updates, now_iso)
                results.append(stored)

    def _collect_row_access_updates(
        self, rows, update_access, now, now_iso, limit, seen_keys, batch_updates, results
    ) -> None:
        """Dedupe raw DB rows with diversity filtering and queue access updates."""
        # P1-2: Diversity filtering - limit same-type dominance
        type_counts: Dict[str, int] = {}
        max_per_type = max(3, limit // 3)

        for row in rows:
            stored = self._serializer.row_to_stored(row)
            if stored and stored.storage_key not in seen_keys:
                mtype = stored.type or "unknown"
                type_counts[mtype] = type_counts.get(mtype, 0) + 1

                if type_counts[mtype] > max_per_type and mtype == "sentiment_marker":
                    continue

                seen_keys.add(stored.storage_key)
                if update_access and self._should_update_access(stored, now):
                    self.increment_access(stored, batch_updates, now_iso)
                results.append(stored)

    def _semantic_recall(self, query: str, where_clause: str, params: List, limit: int):
        """Perform semantic expansion search.

        Expands query using synonym graph, spell correction, cross-language mapping,
        then re-searches FTS5 with expanded terms. Uses batched queries to avoid N+1.
        """
        if not self._expander:
            return []

        try:
            expansions = self._expander.expand(query)

            all_expanded_rows = []

            valid_expansions = [e for e in expansions[1:] if e and e.strip()]

            if not valid_expansions:
                return []

            self._conn_mgr.get_connection()
            try:
                combined_query = " OR ".join(f'"{e}"' for e in valid_expansions)
                all_expanded_rows = self._fts_search(combined_query, where_clause, params, limit)
                seen_row_ids: set = set()
                deduped: list = []
                self._append_deduped_rows(all_expanded_rows, seen_row_ids, deduped, limit)
                all_expanded_rows = deduped

                if len(all_expanded_rows) < limit:
                    self._append_cjk_like_rows(
                        valid_expansions, where_clause, params, limit, all_expanded_rows, seen_row_ids
                    )
            finally:
                pass

            return all_expanded_rows[:limit]

        except (ValueError, TypeError, RuntimeError, ImportError) as e:
            logger.warning("Semantic recall search failed: %s", e)
            return []

    def _append_deduped_rows(self, new_rows, seen_ids, accumulator, limit) -> None:
        """Append new_rows to accumulator, deduping by row id, stopping at limit."""
        for row in new_rows:
            row_id = row["id"] if hasattr(row, "__getitem__") else None
            if row_id and row_id not in seen_ids:
                seen_ids.add(row_id)
                accumulator.append(row)
                if len(accumulator) >= limit:
                    break

    def _append_cjk_like_rows(self, valid_expansions, where_clause, params, limit, accumulator, seen_ids) -> None:
        """Run CJK LIKE search and append deduped rows to accumulator."""
        cjk_expansions = [e for e in valid_expansions if has_cjk(e)]
        if not cjk_expansions:
            return
        like_rows = self._combined_like_search(cjk_expansions, where_clause, params, limit)
        self._append_deduped_rows(like_rows, seen_ids, accumulator, limit)

    def _vector_search(self, query: str, where_clause: str, params: List, limit: int):
        if not self._embedding_model:
            return []
        try:
            query_embedding = self._embedding_model.encode(query)
            conn = self._conn_mgr.get_connection()
            vec_sql = """
                SELECT m.*, v.distance
                FROM memories m
                JOIN memory_vectors v ON v.memory_id = m.id
                {where_clause}
                AND v.embedding MATCH ?
                AND k = ?
                ORDER BY v.distance
            """.format(where_clause=where_clause)
            vec_params = params + [
                struct.pack(f"{self._embedding_dim}f", *query_embedding.tolist()),
                limit,
            ]
            return conn.execute(vec_sql, vec_params).fetchall()
        except (sqlite3.Error, ValueError, struct.error, TypeError) as e:
            logger.warning("Vector search failed: %s", e)
            return []

    def _rrf_fuse(self, fts_rows: list, vec_rows: list, limit: int) -> list:
        """Reciprocal Rank Fusion of FTS5 and vector search results.

        RRF formula: score(d) = w_fts * 1/(k + rank_fts) + w_vec * 1/(k + rank_vec)
        Where k, weights, and type boosts are configurable via rrf_config or env vars.
        """
        rrf_scores: Dict[str, float] = {}
        row_data: Dict[str, Any] = {}

        for rank, row in enumerate(fts_rows, start=1):
            rid = row["id"] if row and "id" in row.keys() else None
            if not rid:
                continue
            base_score = self._rrf_fts_weight / (self._rrf_k + rank)
            type_boost = self._type_boost(row)
            rrf_scores[rid] = rrf_scores.get(rid, 0.0) + base_score * type_boost
            row_data[rid] = row

        for rank, row in enumerate(vec_rows, start=1):
            rid = row["id"] if row and "id" in row.keys() else None
            if not rid:
                continue
            base_score = self._rrf_vec_weight / (self._rrf_k + rank)
            type_boost = self._type_boost(row)
            rrf_scores[rid] = rrf_scores.get(rid, 0.0) + base_score * type_boost
            if rid not in row_data:
                row_data[rid] = row

        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        return [row_data[rid] for rid in sorted_ids[:limit]]

    def _type_boost(self, row) -> float:
        """Apply type-based score boost/penalty.

        Configurable via rrf_config.type_boosts or CARRYMEM_RRF_TYPE_BOOSTS env var.
        Default: fact/decision +20%, sentiment -50%.
        """
        mtype = row["type"] if row and "type" in row.keys() else ""
        return self._rrf_type_boosts.get(mtype, 1.0)

    def _fts_search(self, query, where_clause, params, limit):
        from .query_builder import QueryBuilder

        try:
            conn = self._conn_mgr.get_connection()
            safe_query = QueryBuilder.sanitize_fts_query(query)
            if not safe_query:
                return []
            fts_sql = f"""
                SELECT m.* FROM memories m
                JOIN memories_fts f ON m.rowid = f.rowid
                {where_clause}
                AND m.rowid IN (
                    SELECT rowid FROM memories_fts WHERE memories_fts MATCH ?
                )
                ORDER BY m.importance_score DESC, m.confidence DESC
                LIMIT ?
            """
            params_with_query = params + [safe_query, limit]
            return conn.execute(fts_sql, params_with_query).fetchall()
        except sqlite3.OperationalError as e:
            logger.debug("FTS5 search failed: %s", e)
            return []

    def _like_search(self, query, where_clause, params, limit):
        conn = self._conn_mgr.get_connection()
        escaped = escape_like(query)
        like_clause = (
            " AND (content LIKE ? ESCAPE '\\' OR raw_text LIKE ? " "ESCAPE '\\' OR original_message LIKE ? ESCAPE '\\')"
        )
        like_params = [f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"]
        sql = f"""
            SELECT * FROM memories
            {where_clause}
            {like_clause}
            ORDER BY importance_score DESC, confidence DESC
            LIMIT ?
        """
        all_params = params + like_params + [limit]
        return conn.execute(sql, all_params).fetchall()

    def _combined_like_search(self, terms, where_clause, params, limit):
        """Batched LIKE search: combine multiple terms into a single OR query.

        Replaces the N+1 pattern of calling ``_like_search`` per term with
        a single SQL query that ORs all terms across the same three columns
        (content, raw_text, original_message).  Each term is escaped via
        ``escape_like`` and uses ``ESCAPE '\\'`` to prevent LIKE injection.
        """
        conn = self._conn_mgr.get_connection()
        like_parts = []
        like_params = []
        for term in terms:
            escaped = escape_like(term)
            like_parts.append(
                "(content LIKE ? ESCAPE '\\' OR raw_text LIKE ? ESCAPE '\\' " "OR original_message LIKE ? ESCAPE '\\')"
            )
            like_params.extend([f"%{escaped}%", f"%{escaped}%", f"%{escaped}%"])
        like_clause = " AND (" + " OR ".join(like_parts) + ")"
        sql = f"""
            SELECT * FROM memories
            {where_clause}
            {like_clause}
            ORDER BY importance_score DESC, confidence DESC
            LIMIT ?
        """
        all_params = params + like_params + [limit]
        return conn.execute(sql, all_params).fetchall()

    # ── v0.7.1: Multi-Mode Retrieval Extensions ────────────────────────

    def vector_search_only(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        namespaces: Optional[List[str]] = None,
    ) -> List[StoredMemory]:
        """Pure vector similarity search without FTS or RRF fusion (v0.7.1).

        Args:
            query: Natural language query.
            filters: Optional metadata filters.
            limit: Maximum results.
            namespaces: Optional namespace filter.

        Returns:
            List of StoredMemory ordered by vector similarity.
        """
        if not self._adapter.enable_vector or not self._embedding_model:
            return []

        from .query_builder import _ALLOWED_FILTER_KEYS, _VALID_MEMORY_TYPES

        filters = filters or {}
        for key in filters:
            if key not in _ALLOWED_FILTER_KEYS:
                raise ValueError(f"Invalid filter key: '{key}'")
        if filters.get("type") and filters["type"] not in _VALID_MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: {filters['type']}")

        ns = namespaces or [self._adapter.namespace]
        placeholders = ",".join(["?"] * len(ns))
        conditions = [f"namespace IN ({placeholders})"]
        params: List[Any] = list(ns)

        if filters.get("type"):
            conditions.append("type = ?")
            params.append(filters["type"])
        if filters.get("tier") is not None:
            conditions.append("tier = ?")
            params.append(filters["tier"])
        if not filters.get("include_superseded", False):
            conditions.append("(superseded_at IS NULL OR superseded_at = '')")
        if filters.get("created_after"):
            conditions.append("created_at >= ?")
            params.append(filters["created_after"])
        if filters.get("created_before"):
            conditions.append("created_at <= ?")
            params.append(filters["created_before"])

        where_clause = "WHERE " + " AND ".join(conditions)

        with self._conn_mgr.lock:
            vec_rows = self._vector_search(query, where_clause, params, limit)
            results = [self._serializer.row_to_stored(r) for r in vec_rows if r]
        return [r for r in results if r]

    def hybrid_search(
        self,
        query: str,
        fts_weight: Optional[float] = None,
        vec_weight: Optional[float] = None,
        rrf_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
    ) -> List[StoredMemory]:
        """Hybrid FTS+Vector search with per-call RRF weight override (v0.7.1).

        Temporarily overrides adapter RRF config for this call, then restores.
        """
        where_clause, params = self._build_hybrid_where_clause(filters, namespaces)

        # Save original RRF config (engine-local, not adapter state)
        orig_fts_w = self._rrf_fts_weight
        orig_vec_w = self._rrf_vec_weight
        orig_k = self._rrf_k

        # Apply per-call overrides
        if fts_weight is not None:
            self._rrf_fts_weight = fts_weight
        if vec_weight is not None:
            self._rrf_vec_weight = vec_weight
        if rrf_k is not None:
            self._rrf_k = rrf_k

        try:
            results = self._run_hybrid_search(query, where_clause, params, limit)
        finally:
            # Restore original RRF config
            self._rrf_fts_weight = orig_fts_w
            self._rrf_vec_weight = orig_vec_w
            self._rrf_k = orig_k

        return [r for r in results if r]

    def _build_hybrid_where_clause(
        self,
        filters: Optional[Dict[str, Any]],
        namespaces: Optional[List[str]],
    ) -> tuple:
        """Validate filters and build (where_clause, params) for hybrid search."""
        from .query_builder import _ALLOWED_FILTER_KEYS, _VALID_MEMORY_TYPES

        filters = filters or {}
        for key in filters:
            if key not in _ALLOWED_FILTER_KEYS:
                raise ValueError(f"Invalid filter key: '{key}'")
        if filters.get("type") and filters["type"] not in _VALID_MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: {filters['type']}")

        ns = namespaces or [self._adapter.namespace]
        placeholders = ",".join(["?"] * len(ns))
        conditions = [f"namespace IN ({placeholders})"]
        params: List[Any] = list(ns)

        if filters.get("type"):
            conditions.append("type = ?")
            params.append(filters["type"])
        elif not filters.get("include_session_summary", False):
            conditions.append("type != ?")
            params.append("session_summary")
        if filters.get("tier") is not None:
            conditions.append("tier = ?")
            params.append(filters["tier"])
        if not filters.get("include_superseded", False):
            conditions.append("(superseded_at IS NULL OR superseded_at = '')")
        if filters.get("created_after"):
            conditions.append("created_at >= ?")
            params.append(filters["created_after"])
        if filters.get("created_before"):
            conditions.append("created_at <= ?")
            params.append(filters["created_before"])

        return "WHERE " + " AND ".join(conditions), params

    def _run_hybrid_search(self, query: str, where_clause: str, params: List, limit: int) -> list:
        """Execute FTS+vector search under conn lock and fuse results via RRF."""
        with self._conn_mgr.lock:
            fts_rows = self._fts_search(query, where_clause, params, limit)
            if self._adapter.enable_vector:
                vec_rows = self._vector_search(query, where_clause, params, limit)
            else:
                vec_rows = []
            if fts_rows and vec_rows:
                fused = self._rrf_fuse(fts_rows, vec_rows, limit)
            elif fts_rows:
                fused = fts_rows
            elif vec_rows:
                fused = vec_rows
            else:
                fused = []
            return [self._serializer.row_to_stored(r) for r in fused if r]

    def search_by_time(
        self,
        start: datetime,
        end: Optional[datetime],
        filters: Optional[Dict[str, Any]],
        limit: int,
        namespaces: Optional[List[str]],
    ) -> List[StoredMemory]:
        """Time-range retrieval (v0.7.1).

        Returns memories with created_at in [start, end), ordered descending.
        """
        from .query_builder import _ALLOWED_FILTER_KEYS

        filters = filters or {}
        for key in filters:
            if key not in _ALLOWED_FILTER_KEYS:
                raise ValueError(f"Invalid filter key: '{key}'")

        ns = namespaces or [self._adapter.namespace]
        placeholders = ",".join(["?"] * len(ns))
        conditions = [f"namespace IN ({placeholders})"]
        params: List[Any] = list(ns)

        # Time range
        start_iso = start.isoformat() if isinstance(start, datetime) else str(start)
        conditions.append("created_at >= ?")
        params.append(start_iso)

        if end is not None:
            end_iso = end.isoformat() if isinstance(end, datetime) else str(end)
            conditions.append("created_at < ?")
            params.append(end_iso)

        if filters.get("type"):
            conditions.append("type = ?")
            params.append(filters["type"])
        if filters.get("tier") is not None:
            conditions.append("tier = ?")
            params.append(filters["tier"])
        if not filters.get("include_superseded", False):
            conditions.append("(superseded_at IS NULL OR superseded_at = '')")

        where_clause = "WHERE " + " AND ".join(conditions)

        with self._conn_mgr.lock:
            conn = self._conn_mgr.get_connection()
            sql = f"""
                SELECT * FROM memories
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            results = [self._serializer.row_to_stored(r) for r in rows if r]

        return [r for r in results if r]
