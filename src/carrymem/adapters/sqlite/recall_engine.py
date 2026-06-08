"""Recall engine with FTS, vector, semantic search, and RRF fusion."""

import sqlite3
import struct
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...scoring import calculate_importance
from ...utils.helpers import escape_like
from ...utils.language import _STOP_WORDS, has_cjk
from ...utils.logger import logger
from ..base import StoredMemory

try:
    from ...semantic.expander import SemanticExpander
    from ...semantic.merger import ResultMerger

    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False


class RecallEngine:
    """Multi-phase recall engine: FTS → Vector → Expansion → Semantic."""

    def __init__(self, adapter):
        self._adapter = adapter

    def recall(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ) -> List[StoredMemory]:
        if self._adapter._enable_cache and self._adapter._cache:
            cached = self._adapter._cache.get(self._adapter.namespace, query, filters, limit)
            if cached is not None:
                return [self._adapter._serializer.dict_to_stored(d) or StoredMemory() for d in cached]

        with self._adapter._conn_mgr.lock:
            results = self._recall_impl(query, filters, limit, namespaces, update_access=update_access)

        if self._adapter._enable_cache and self._adapter._cache and results:
            self._adapter._cache.put(
                self._adapter.namespace,
                query,
                filters,
                limit,
                [r.to_dict() for r in results],
            )

        return results

    def _recall_impl(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        update_access: bool = True,
    ):
        from .query_builder import _ALLOWED_FILTER_KEYS, _VALID_MEMORY_TYPES, QueryBuilder

        filters = filters or {}

        for key in filters:
            if key not in _ALLOWED_FILTER_KEYS:
                raise ValueError(f"Invalid filter key: '{key}'. " f"Allowed keys: {_ALLOWED_FILTER_KEYS}")

        if filters.get("type") and filters["type"] not in _VALID_MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: '{filters['type']}'. " f"Valid types: {_VALID_MEMORY_TYPES}")

        if limit < 0 or limit > 100000:
            raise ValueError(f"Limit must be between 0 and 100000, got {limit}")

        if namespaces:
            for ns in namespaces:
                if not ns or not isinstance(ns, str) or len(ns) > 128:
                    raise ValueError(f"Invalid namespace: '{ns}'. " "Must be non-empty string, max 128 chars.")

        if query and len(query) > 10000:
            raise ValueError(f"Query too long: {len(query)} chars (max 10000)")

        time_constraints = QueryBuilder.parse_time_expressions(query or "")
        if time_constraints:
            if time_constraints.get("created_after") and not filters.get("created_after"):
                filters["created_after"] = time_constraints["created_after"]
            if time_constraints.get("created_before") and not filters.get("created_before"):
                filters["created_before"] = time_constraints["created_before"]
            if time_constraints.get("order_oldest"):
                filters["_order_oldest"] = True

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

        where_clause = "WHERE " + " AND ".join(conditions)

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
            conn = self._adapter._conn_mgr.get_connection()
            sql = f"""
                SELECT * FROM memories
                {where_clause}
                ORDER BY importance_score DESC, confidence DESC
                LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()

        # Phase 4: Batch access count update (normal path)
        return self.recall_update_access(rows, update_access, filters, limit, is_stored=False)

    def _recall_fts_phase(self, query, where_clause, params, limit):
        """FTS search + context reconstruction."""
        keywords = " ".join(w for w in query.lower().split() if w not in _STOP_WORDS and len(w) > 1)

        from .query_builder import QueryBuilderWithContext

        if keywords and keywords != query.strip().lower():
            rows = self._fts_search(keywords, where_clause, params, limit)
        else:
            rows = self._fts_search(query, where_clause, params, limit)

        if not rows and has_cjk(query):
            rows = self._like_search(query, where_clause, params, limit)

        if not rows or len(rows) < max(3, limit // 4):
            qb = QueryBuilderWithContext(self._adapter)
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
        if self._adapter._enable_vector:
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
            seen_ids = set()
            for r in rows:
                rid = r[0] if r else None
                if rid:
                    seen_ids.add(rid)

            for eq in expanded_queries:
                eq_rows = self._fts_search(eq, where_clause, params, limit)
                for r in eq_rows:
                    rid = r[0] if r else None
                    if rid and rid not in seen_ids:
                        rows.append(r)
                        seen_ids.add(rid)
                if len(rows) >= limit:
                    break

            if len(rows) < limit:
                for eq in expanded_queries:
                    eq_rows = self._like_search(eq, where_clause, params, limit)
                    for r in eq_rows:
                        rid = r[0] if r else None
                        if rid and rid not in seen_ids:
                            rows.append(r)
                            seen_ids.add(rid)
                    if len(rows) >= limit:
                        break

        # Semantic expansion if results insufficient
        if self._adapter._enable_semantic and len(rows) < limit and self._adapter._expander and self._adapter._merger:
            original_results = [self._adapter._serializer.row_to_stored(r) for r in rows if r]
            expanded_rows = self._semantic_recall(query, where_clause, params, limit)
            expanded_results = [self._adapter._serializer.row_to_stored(r) for r in expanded_rows if r]

            if expanded_results:
                merged = self._adapter._merger.merge(
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
                        stored = self._adapter._serializer.dict_to_stored(item)
                        if stored:
                            final_results.append(stored)
                return final_results, True

        return rows, False

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
        """
        filters = filters or {}
        conn = self._adapter._conn_mgr.get_connection()
        now_iso = datetime.now(timezone.utc).isoformat()
        results = []
        seen_keys = set()
        batch_updates = []

        if is_stored:
            for stored in rows:
                if stored.storage_key not in seen_keys:
                    seen_keys.add(stored.storage_key)
                    if update_access:
                        self.increment_access(stored, batch_updates, now_iso)
                    results.append(stored)
            if update_access and batch_updates:
                conn.executemany(
                    "UPDATE memories SET access_count = ?, "
                    "importance_score = ?, last_accessed_at = ? "
                    "WHERE storage_key = ?",
                    batch_updates,
                )
        else:
            # P1-2: Diversity filtering - limit same-type dominance
            type_counts = {}
            max_per_type = max(3, limit // 3)

            for row in rows:
                stored = self._adapter._serializer.row_to_stored(row)
                if stored and stored.storage_key not in seen_keys:
                    mtype = stored.type or "unknown"
                    type_counts[mtype] = type_counts.get(mtype, 0) + 1

                    if type_counts[mtype] > max_per_type and mtype == "sentiment_marker":
                        continue

                    seen_keys.add(stored.storage_key)
                    if update_access:
                        self.increment_access(stored, batch_updates, now_iso)
                    results.append(stored)
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

    def _semantic_recall(self, query: str, where_clause: str, params: List, limit: int):
        """Perform semantic expansion search.

        Expands query using synonym graph, spell correction, cross-language mapping,
        then re-searches FTS5 with expanded terms. Uses batched queries to avoid N+1.
        """
        if not self._adapter._expander:
            return []

        try:
            expansions = self._adapter._expander.expand(query)

            all_expanded_rows = []

            valid_expansions = [e for e in expansions[1:] if e and e.strip()]

            if not valid_expansions:
                return []

            self._adapter._conn_mgr.get_connection()
            try:
                combined_query = " OR ".join(f'"{e}"' for e in valid_expansions)
                all_expanded_rows = self._fts_search(combined_query, where_clause, params, limit)
                seen_row_ids = set()
                deduped = []
                for row in all_expanded_rows:
                    row_id = row["id"] if hasattr(row, "__getitem__") else None
                    if row_id and row_id not in seen_row_ids:
                        seen_row_ids.add(row_id)
                        deduped.append(row)
                        if len(deduped) >= limit:
                            break
                all_expanded_rows = deduped

                if len(all_expanded_rows) < limit:
                    for exp_query in valid_expansions:
                        if has_cjk(exp_query):
                            like_rows = self._like_search(exp_query, where_clause, params, limit)
                            for row in like_rows:
                                row_id = row["id"] if hasattr(row, "__getitem__") else None
                                if row_id and row_id not in seen_row_ids:
                                    seen_row_ids.add(row_id)
                                    all_expanded_rows.append(row)
                                    if len(all_expanded_rows) >= limit:
                                        break
            finally:
                pass

            return all_expanded_rows[:limit]

        except Exception as e:
            logger.warning(f"Semantic recall search failed: {e}")
            return []

    def _vector_search(self, query: str, where_clause: str, params: List, limit: int):
        if not self._adapter._embedding_model:
            return []
        try:
            query_embedding = self._adapter._embedding_model.encode(query)
            conn = self._adapter._conn_mgr.get_connection()
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
                struct.pack(f"{self._adapter._embedding_dim}f", *query_embedding.tolist()),
                limit,
            ]
            return conn.execute(vec_sql, vec_params).fetchall()
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def _rrf_fuse(self, fts_rows: list, vec_rows: list, limit: int) -> list:
        """Reciprocal Rank Fusion of FTS5 and vector search results.

        RRF formula: score(d) = w_fts * 1/(k + rank_fts) + w_vec * 1/(k + rank_vec)
        Where k, weights, and type boosts are configurable via rrf_config or env vars.
        """
        rrf_scores = {}
        row_data = {}

        for rank, row in enumerate(fts_rows, start=1):
            rid = row["id"] if row and "id" in row.keys() else None
            if not rid:
                continue
            base_score = self._adapter._rrf_fts_weight / (self._adapter._rrf_k + rank)
            type_boost = self._type_boost(row)
            rrf_scores[rid] = rrf_scores.get(rid, 0.0) + base_score * type_boost
            row_data[rid] = row

        for rank, row in enumerate(vec_rows, start=1):
            rid = row["id"] if row and "id" in row.keys() else None
            if not rid:
                continue
            base_score = self._adapter._rrf_vec_weight / (self._adapter._rrf_k + rank)
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
        return self._adapter._rrf_type_boosts.get(mtype, 1.0)

    def _fts_search(self, query, where_clause, params, limit):
        from .query_builder import QueryBuilder

        try:
            conn = self._adapter._conn_mgr.get_connection()
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
            logger.debug(f"FTS5 search failed: {e}")
            return []

    def _like_search(self, query, where_clause, params, limit):
        conn = self._adapter._conn_mgr.get_connection()
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
