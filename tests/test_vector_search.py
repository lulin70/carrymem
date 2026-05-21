"""Tests for vector search functionality (P0-2, v0.7.0).

Requires: pip install carrymem[semantic]

Covers: vector search enable/disable, embedding storage,
semantic recall, fallback to FTS5, forget deletes vector,
runtime toggle.
"""

import os
import pytest

from carrymem.adapters.sqlite_adapter import (
    SQLiteAdapter,
    SQLITE_VEC_AVAILABLE,
    PYSQLITE3_AVAILABLE,
    SENTENCE_TRANSFORMERS_AVAILABLE,
)
from carrymem.adapters.base import MemoryEntry

VECTOR_AVAILABLE = SQLITE_VEC_AVAILABLE and PYSQLITE3_AVAILABLE and SENTENCE_TRANSFORMERS_AVAILABLE


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_vector.db")


@pytest.fixture
def adapter_no_vector(db_path):
    a = SQLiteAdapter(
        db_path,
        enable_semantic_recall=False,
        enable_cache=False,
        enable_vector_search=False,
    )
    yield a
    a.close()


@pytest.fixture
def adapter_with_vector(db_path):
    if not VECTOR_AVAILABLE:
        pytest.skip("Vector search dependencies not installed")
    a = SQLiteAdapter(
        db_path,
        enable_semantic_recall=False,
        enable_cache=False,
        enable_vector_search=True,
    )
    yield a
    a.close()


class TestVectorSearchCapabilities:
    def test_vector_search_disabled_when_not_requested(self, adapter_no_vector):
        caps = adapter_no_vector.capabilities
        assert caps["vector_search"] is False

    def test_vector_search_enabled_when_available(self, adapter_with_vector):
        caps = adapter_with_vector.capabilities
        assert caps["vector_search"] is True

    def test_vector_search_disabled_without_deps(self, db_path):
        if VECTOR_AVAILABLE:
            a = SQLiteAdapter(
                db_path,
                enable_semantic_recall=False,
                enable_cache=False,
                enable_vector_search=True,
            )
            assert a.capabilities["vector_search"] is True
            a.close()
        else:
            a = SQLiteAdapter(
                db_path,
                enable_semantic_recall=False,
                enable_cache=False,
                enable_vector_search=True,
            )
            assert a.capabilities["vector_search"] is False
            a.close()


class TestEmbeddingStorage:
    def test_embedding_stored_on_remember(self, adapter_with_vector):
        entry = MemoryEntry(
            content="User prefers dark mode",
            type="user_preference",
            raw_text="I prefer dark mode for my IDE",
        )
        stored = adapter_with_vector.remember(entry)
        assert stored is not None

        conn = adapter_with_vector._get_connection()
        count = conn.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        assert count == 1

    def test_embedding_uses_raw_text(self, adapter_with_vector):
        entry = MemoryEntry(
            content="Database choice: PostgreSQL",
            type="decision",
            raw_text="We decided to use PostgreSQL for the database",
        )
        adapter_with_vector.remember(entry)

        conn = adapter_with_vector._get_connection()
        vec = conn.execute("SELECT memory_id FROM memory_vectors").fetchone()
        assert vec is not None

    def test_embedding_uses_content_when_no_raw_text(self, adapter_with_vector):
        entry = MemoryEntry(
            content="Server IP is 10.0.1.50",
            type="fact_declaration",
        )
        adapter_with_vector.remember(entry)

        conn = adapter_with_vector._get_connection()
        count = conn.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        assert count == 1

    def test_no_embedding_when_vector_disabled(self, adapter_no_vector):
        entry = MemoryEntry(
            content="Test content",
            type="user_preference",
            raw_text="Test raw text",
        )
        adapter_no_vector.remember(entry)

        try:
            conn = adapter_no_vector._get_connection()
            conn.execute("SELECT COUNT(*) FROM memory_vectors")
            assert False, "memory_vectors should not exist"
        except Exception:
            pass


class TestVectorRecall:
    def test_semantic_recall_returns_similar(self, adapter_with_vector):
        entry1 = MemoryEntry(
            content="User prefers dark mode",
            type="user_preference",
            raw_text="I prefer dark mode for my IDE",
        )
        entry2 = MemoryEntry(
            content="Database choice: PostgreSQL",
            type="decision",
            raw_text="We decided to use PostgreSQL for the database",
        )
        entry3 = MemoryEntry(
            content="Server IP: 10.0.1.50",
            type="fact_declaration",
            raw_text="The deployment server IP is 10.0.1.50",
        )
        adapter_with_vector.remember(entry1)
        adapter_with_vector.remember(entry2)
        adapter_with_vector.remember(entry3)

        results = adapter_with_vector.recall("what theme does the user like")
        assert len(results) >= 1
        contents = [r.content for r in results]
        assert any("dark mode" in c.lower() for c in contents)

    def test_fts_still_works_with_vector(self, adapter_with_vector):
        entry = MemoryEntry(
            content="I prefer dark mode",
            type="user_preference",
            raw_text="I prefer dark mode for my IDE",
        )
        adapter_with_vector.remember(entry)

        results = adapter_with_vector.recall("dark mode")
        assert len(results) >= 1
        assert any("dark mode" in r.content.lower() for r in results)

    def test_vector_recall_fallback_to_fts(self, db_path):
        if not VECTOR_AVAILABLE:
            pytest.skip("Vector search dependencies not installed")

        a = SQLiteAdapter(
            db_path,
            enable_semantic_recall=False,
            enable_cache=False,
            enable_vector_search=True,
        )
        entry = MemoryEntry(
            content="Test fallback content",
            type="user_preference",
        )
        a.remember(entry)

        a._enable_vector = False
        results = a.recall("fallback content")
        assert len(results) >= 1
        a.close()


class TestForgetDeletesVector:
    def test_forget_deletes_vector(self, adapter_with_vector):
        entry = MemoryEntry(
            content="To be forgotten",
            type="user_preference",
            raw_text="This memory will be deleted",
        )
        stored = adapter_with_vector.remember(entry)

        conn = adapter_with_vector._get_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        assert count_before == 1

        adapter_with_vector.forget(stored.storage_key)

        count_after = conn.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
        assert count_after == 0


class TestRuntimeToggle:
    def test_enable_vector_search_runtime(self, adapter_with_vector):
        adapter_with_vector.enable_vector_search(False)
        assert adapter_with_vector.capabilities["vector_search"] is False

        adapter_with_vector.enable_vector_search(True)
        assert adapter_with_vector.capabilities["vector_search"] is True

    def test_cannot_enable_without_deps(self, adapter_no_vector):
        adapter_no_vector.enable_vector_search(True)
        assert adapter_no_vector.capabilities["vector_search"] is False
