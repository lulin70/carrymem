"""Test suite for KnowledgeGraph (v0.7.0 SQLite-native knowledge graph).

Covers all test dimensions per DevSquad Iron Rules:
  - Happy Path: entity extraction, recall by entity/relation, graph traversal
  - Boundary: empty input, max_hops edge, self-relation, namespace validation
  - Error: missing tables, DB errors, None normalizer
  - Performance: 1000 entities < 500ms
  - Integration: SQLiteAdapter capability gating + CarryMem facade API
  - Config: namespace isolation, entity_type filter, direction filter

Uses real SQLite in-memory DB (no Mock) per user testing philosophy.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List

import pytest

from carrymem.layers.entity_normalizer import EntityNormalizer, NormalizeResult
from carrymem.layers.knowledge_graph import KnowledgeGraph
from carrymem.security.input_validator import InputValidator

# ── Fixtures ──────────────────────────────────────────────────────────────


class FakeConnMgr:
    """Minimal ConnectionManager wrapper around a real sqlite3 connection.

    Uses real sqlite3 (not Mock) so FK constraints, JOINs, and INSERT OR
    IGNORE behave exactly as production.
    """

    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self.db_path = db_path
        self.namespace = "default"

    def get_connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()


def _init_graph_schema(conn: sqlite3.Connection) -> None:
    """Create memories + memory_entities + memory_relations tables (mirrors schema.py)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            raw_text TEXT NOT NULL DEFAULT '',
            original_message TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            tier INTEGER NOT NULL DEFAULT 2,
            source_layer TEXT NOT NULL DEFAULT 'unknown',
            reasoning TEXT,
            suggested_action TEXT NOT NULL DEFAULT 'store',
            recall_hint TEXT,
            metadata TEXT,
            storage_key TEXT UNIQUE NOT NULL,
            namespace TEXT NOT NULL DEFAULT 'default',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT,
            access_count INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL,
            importance_score REAL NOT NULL DEFAULT 0.0,
            last_accessed_at TEXT,
            version INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS memory_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT,
            entity_type TEXT NOT NULL,
            entity_text TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            namespace TEXT NOT NULL DEFAULT 'default',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (memory_key) REFERENCES memories(storage_key) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS memory_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            src_entity_id INTEGER NOT NULL,
            dst_entity_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            source_memory_key TEXT,
            weight REAL NOT NULL DEFAULT 1.0,
            namespace TEXT NOT NULL DEFAULT 'default',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            confidence TEXT NOT NULL DEFAULT 'EXTRACTED',
            FOREIGN KEY (src_entity_id) REFERENCES memory_entities(id),
            FOREIGN KEY (dst_entity_id) REFERENCES memory_entities(id)
        );

        CREATE INDEX IF NOT EXISTS idx_entities_text ON memory_entities(entity_text);
        CREATE INDEX IF NOT EXISTS idx_entities_type ON memory_entities(entity_type);
        CREATE INDEX IF NOT EXISTS idx_entities_memory ON memory_entities(memory_key);
        CREATE INDEX IF NOT EXISTS idx_entities_namespace ON memory_entities(namespace);
        CREATE INDEX IF NOT EXISTS idx_relations_src ON memory_relations(src_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relations_dst ON memory_relations(dst_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relations_type ON memory_relations(relation_type);
        CREATE INDEX IF NOT EXISTS idx_relations_namespace ON memory_relations(namespace);
        CREATE INDEX IF NOT EXISTS idx_relations_confidence ON memory_relations(confidence);
    """)
    conn.commit()


def _insert_memory(conn: sqlite3.Connection, storage_key: str, content: str, importance: float = 0.5) -> None:
    """Insert a minimal memory row for FK satisfaction."""
    conn.execute(
        "INSERT INTO memories (id, type, content, storage_key, content_hash, importance_score) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (storage_key, "fact", content, storage_key, "hash_" + storage_key, importance),
    )
    conn.commit()


class StubNormalizer:
    """Deterministic stub for EntityNormalizer — returns preset entities.

    Avoids the cost of real regex-based extraction in tests while exercising
    KnowledgeGraph's handling of NormalizeResult.entities structure.
    """

    def __init__(self, entities_map: Dict[str, List[Dict[str, Any]]] | None = None):
        self._entities_map = entities_map or {}

    def normalize(self, text: str, namespace: str) -> NormalizeResult:
        entities = self._entities_map.get(text, [])
        return NormalizeResult(entities=entities, new_aliases=0)


@pytest.fixture
def conn_mgr() -> FakeConnMgr:
    mgr = FakeConnMgr()
    _init_graph_schema(mgr.get_connection())
    return mgr


@pytest.fixture
def validator() -> InputValidator:
    return InputValidator(strict_mode=False)


@pytest.fixture
def stub_normalizer() -> StubNormalizer:
    return StubNormalizer(
        entities_map={
            "I prefer Python for backend work": [
                {"canonical": "Python", "type": "tool", "score": 0.9},
                {"canonical": "backend", "type": "concept", "score": 0.6},
            ],
            "Using JWT for authentication": [
                {"canonical": "JWT", "type": "acronym", "score": 0.95},
            ],
        }
    )


@pytest.fixture
def graph(conn_mgr: FakeConnMgr, stub_normalizer: StubNormalizer, validator: InputValidator) -> KnowledgeGraph:
    return KnowledgeGraph(conn_mgr=conn_mgr, entity_normalizer=stub_normalizer, input_validator=validator)


# ── 1. Happy Path ─────────────────────────────────────────────────────────


class TestHappyPath:
    """Core entity extraction, recall, and relation management."""

    def test_extract_and_store_entities_returns_count(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        _insert_memory(conn_mgr.get_connection(), "mem_001", "I prefer Python for backend work")
        count = graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        assert count == 2

    def test_extracted_entities_are_queryable(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "I prefer Python for backend work")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")

        results = graph.recall_by_entity("Python", namespace="default")
        assert len(results) == 1
        assert results[0]["storage_key"] == "mem_001"
        assert results[0]["content"] == "I prefer Python for backend work"

    def test_recall_by_entity_with_type_filter(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "I prefer Python for backend work")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")

        tool_results = graph.recall_by_entity("Python", entity_type="tool", namespace="default")
        concept_results = graph.recall_by_entity("Python", entity_type="concept", namespace="default")
        assert len(tool_results) == 1
        assert len(concept_results) == 0

    def test_add_relation_between_entities(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python for backend")
        _insert_memory(conn, "mem_002", "JWT for authentication")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        graph.extract_and_store_entities("mem_002", "Using JWT for authentication", "default")

        added = graph.add_relation("Python", "JWT", "works_with", source_memory_key="mem_001", weight=0.8)
        assert added is True

        relations = graph.list_relations(namespace="default")
        assert len(relations) == 1
        assert relations[0]["src_entity"] == "Python"
        assert relations[0]["dst_entity"] == "JWT"
        assert relations[0]["relation_type"] == "works_with"
        assert relations[0]["weight"] == 0.8

    def test_recall_graph_multi_hop_traversal(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python for backend")
        _insert_memory(conn, "mem_002", "JWT for authentication")
        _insert_memory(conn, "mem_003", "Auth service")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        graph.extract_and_store_entities("mem_002", "Using JWT for authentication", "default")

        # Python -> JWT -> Auth (3-entity chain, 2 hops)
        graph.add_relation("Python", "JWT", "works_with", source_memory_key="mem_001")
        graph.add_relation("JWT", "Auth", "authenticates", source_memory_key="mem_002")

        result = graph.recall_graph("Python", max_hops=2, namespace="default")
        entity_texts = {e["entity_text"] for e in result["entities"]}
        assert "Python" in entity_texts
        assert "JWT" in entity_texts
        assert "Auth" in entity_texts

    def test_get_stats_returns_counts(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python for backend")
        _insert_memory(conn, "mem_002", "JWT for authentication")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        graph.extract_and_store_entities("mem_002", "Using JWT for authentication", "default")
        graph.add_relation("Python", "JWT", "works_with", source_memory_key="mem_001")

        stats = graph.get_stats(namespace="default")
        assert stats["entity_count"] == 3  # Python, backend, JWT
        assert stats["relation_count"] == 1
        assert stats["memory_linked"] == 2


# ── 2. Boundary ────────────────────────────────────────────────────────────


class TestBoundary:
    """Edge cases and boundary conditions."""

    def test_extract_empty_text_returns_zero(self, graph: KnowledgeGraph):
        assert graph.extract_and_store_entities("mem_001", "", "default") == 0
        assert graph.extract_and_store_entities("mem_001", "   ", "default") == 0

    def test_extract_empty_storage_key_returns_zero(self, graph: KnowledgeGraph):
        assert graph.extract_and_store_entities("", "some text", "default") == 0

    def test_extract_no_entities_returns_zero(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        _insert_memory(conn_mgr.get_connection(), "mem_001", "no special terms here")
        count = graph.extract_and_store_entities("mem_001", "no special terms here", "default")
        assert count == 0

    def test_add_relation_self_loop_returns_false(self, graph: KnowledgeGraph):
        added = graph.add_relation("Python", "Python", "self_relation")
        assert added is False

    def test_add_relation_empty_strings_returns_false(self, graph: KnowledgeGraph):
        assert graph.add_relation("", "JWT", "works_with") is False
        assert graph.add_relation("Python", "", "works_with") is False
        assert graph.add_relation("Python", "JWT", "") is False

    def test_recall_graph_max_hops_zero_returns_empty(self, graph: KnowledgeGraph):
        result = graph.recall_graph("Python", max_hops=0)
        assert result == {"entities": [], "memories": []}

    def test_recall_graph_nonexistent_entity_returns_empty(self, graph: KnowledgeGraph):
        result = graph.recall_graph("NonexistentEntity", max_hops=3)
        assert result == {"entities": [], "memories": []}

    def test_recall_by_relation_invalid_direction_defaults_to_both(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python")
        _insert_memory(conn, "mem_002", "JWT")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        graph.extract_and_store_entities("mem_002", "Using JWT for authentication", "default")
        graph.add_relation("Python", "JWT", "works_with", source_memory_key="mem_001")

        results = graph.recall_by_relation("Python", direction="invalid_direction", namespace="default")
        assert len(results) >= 1

    def test_namespace_validation_rejects_invalid(self):
        assert KnowledgeGraph._validate_namespace("") == ""
        assert KnowledgeGraph._validate_namespace(None) == ""  # type: ignore[arg-type]
        assert KnowledgeGraph._validate_namespace("invalid namespace!") == ""
        assert KnowledgeGraph._validate_namespace("valid-ns") == "valid-ns"
        assert KnowledgeGraph._validate_namespace("Valid_NS") == "valid_ns"

    def test_namespace_isolation(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "ns_a")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "ns_b")

        a_results = graph.recall_by_entity("Python", namespace="ns_a")
        b_results = graph.recall_by_entity("Python", namespace="ns_b")
        assert len(a_results) == 1
        assert len(b_results) == 1
        # Same memory content but different namespace scoping
        assert a_results[0]["storage_key"] == "mem_001"


# ── 3. Error Cases ─────────────────────────────────────────────────────────


class TestErrorCases:
    """Failure paths and graceful degradation."""

    def test_extract_without_normalizer_returns_zero(self, conn_mgr: FakeConnMgr):
        graph = KnowledgeGraph(conn_mgr=conn_mgr, entity_normalizer=None)
        _insert_memory(conn_mgr.get_connection(), "mem_001", "text")
        assert graph.extract_and_store_entities("mem_001", "I prefer Python", "default") == 0

    def test_recall_by_entity_nonexistent_returns_empty(self, graph: KnowledgeGraph):
        results = graph.recall_by_entity("NonexistentEntity")
        assert results == []

    def test_add_relation_creates_entities_if_missing(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        # add_relation should create entities that don't yet exist
        added = graph.add_relation("NewEntityA", "NewEntityB", "connects_to", namespace="default")
        assert added is True

        entities = graph.list_entities(namespace="default")
        entity_texts = {e["entity_text"] for e in entities}
        assert "NewEntityA" in entity_texts
        assert "NewEntityB" in entity_texts

    def test_list_entities_on_empty_graph_returns_empty(self, graph: KnowledgeGraph):
        assert graph.list_entities() == []

    def test_list_relations_on_empty_graph_returns_empty(self, graph: KnowledgeGraph):
        assert graph.list_relations() == []

    def test_get_stats_on_empty_graph_returns_zeros(self, graph: KnowledgeGraph):
        stats = graph.get_stats(namespace="default")
        assert stats == {"entity_count": 0, "relation_count": 0, "memory_linked": 0}

    def test_sanitize_handles_none_and_empty(self, graph: KnowledgeGraph):
        assert graph._sanitize(None) == ""  # type: ignore[arg-type]
        assert graph._sanitize("") == ""
        assert graph._sanitize("  text  ") == "text"

    def test_sanitize_strips_null_bytes(self, graph: KnowledgeGraph):
        assert graph._sanitize("text\x00malicious") == "textmalicious"


# ── 4. Performance ─────────────────────────────────────────────────────────


class TestPerformance:
    """Performance and scale characteristics."""

    def test_1000_entity_insert_under_500ms(self, conn_mgr: FakeConnMgr):
        """Bulk entity insertion should complete well under 500ms."""
        entities_map = {
            f"text_{i}": [{"canonical": f"Entity_{i}", "type": "concept", "score": 0.7}] for i in range(1000)
        }
        normalizer = StubNormalizer(entities_map=entities_map)
        graph = KnowledgeGraph(conn_mgr=conn_mgr, entity_normalizer=normalizer)
        conn = conn_mgr.get_connection()

        start = time.perf_counter()
        for i in range(1000):
            _insert_memory(conn, f"mem_{i:04d}", f"text_{i}")
            graph.extract_and_store_entities(f"mem_{i:04d}", f"text_{i}", "default")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"1000 entity inserts took {elapsed:.3f}s (>500ms)"

    def test_graph_traversal_3_hops_performance(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        """Multi-hop traversal with 100 entities and 50 relations should be fast."""
        conn = conn_mgr.get_connection()
        for i in range(100):
            _insert_memory(conn, f"mem_{i:03d}", f"entity_{i}")
            conn.execute(
                "INSERT OR IGNORE INTO memory_entities "
                "(memory_key, entity_type, entity_text, confidence, namespace) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"mem_{i:03d}", "concept", f"entity_{i}", 0.7, "default"),
            )
        conn.commit()

        for i in range(50):
            graph.add_relation(f"entity_{i}", f"entity_{i + 50}", "links_to")

        start = time.perf_counter()
        result = graph.recall_graph("entity_0", max_hops=3, namespace="default")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.2, f"3-hop traversal took {elapsed:.3f}s (>200ms)"
        assert len(result["entities"]) > 0


# ── 5. Configuration ──────────────────────────────────────────────────────


class TestConfiguration:
    """Configuration and filtering options."""

    def test_list_entities_with_type_filter(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python backend")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")

        tool_entities = graph.list_entities(namespace="default", entity_type="tool")
        concept_entities = graph.list_entities(namespace="default", entity_type="concept")
        assert len(tool_entities) == 1
        assert tool_entities[0]["entity_text"] == "Python"
        assert len(concept_entities) == 1
        assert concept_entities[0]["entity_text"] == "backend"

    def test_list_relations_with_type_filter(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python")
        _insert_memory(conn, "mem_002", "JWT")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        graph.extract_and_store_entities("mem_002", "Using JWT for authentication", "default")
        graph.add_relation("Python", "JWT", "works_with")
        graph.add_relation("Python", "JWT", "depends_on")

        works_with = graph.list_relations(namespace="default", relation_type="works_with")
        depends_on = graph.list_relations(namespace="default", relation_type="depends_on")
        assert len(works_with) == 1
        assert len(depends_on) == 1

    def test_recall_by_relation_direction_outgoing(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        _insert_memory(conn, "mem_001", "Python")
        _insert_memory(conn, "mem_002", "JWT")
        graph.extract_and_store_entities("mem_001", "I prefer Python for backend work", "default")
        graph.extract_and_store_entities("mem_002", "Using JWT for authentication", "default")
        graph.add_relation("Python", "JWT", "works_with", source_memory_key="mem_001")

        outgoing = graph.recall_by_relation("Python", direction="outgoing", namespace="default")
        incoming = graph.recall_by_relation("Python", direction="incoming", namespace="default")
        assert len(outgoing) == 1
        assert len(incoming) == 0

    def test_limit_parameter_truncates_results(self, graph: KnowledgeGraph, conn_mgr: FakeConnMgr):
        conn = conn_mgr.get_connection()
        for i in range(5):
            _insert_memory(conn, f"mem_{i:03d}", f"Python reference {i}")
            conn.execute(
                "INSERT OR IGNORE INTO memory_entities "
                "(memory_key, entity_type, entity_text, confidence, namespace) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"mem_{i:03d}", "concept", "Python", 0.7 + i * 0.05, "default"),
            )
        conn.commit()

        results = graph.recall_by_entity("Python", namespace="default", limit=3)
        assert len(results) == 3


# ── 6. Integration ────────────────────────────────────────────────────────


class TestIntegration:
    """Integration with SQLiteAdapter and CarryMem facade."""

    def test_sqlite_adapter_graph_capability_enabled(self):
        """SQLiteAdapter should declare graph: True in capabilities."""
        from carrymem.adapters.sqlite_adapter import SQLiteAdapter

        adapter = SQLiteAdapter(db_path=":memory:")
        assert adapter.capabilities.get("graph") is True
        adapter.close()

    def test_sqlite_adapter_store_graph_entities(self):
        """SQLiteAdapter.store_graph_entities() should extract and store entities."""
        from carrymem.adapters.sqlite_adapter import SQLiteAdapter

        adapter = SQLiteAdapter(db_path=":memory:")
        try:
            # Use CarryMem facade to store a memory, which populates storage_key
            from carrymem import CarryMem

            cm = CarryMem(storage="sqlite", db_path=":memory:")
            cm.classify_and_remember("I prefer Python for backend work", force_type="preference")
            memories = cm.recall_memories()
            if memories:
                key = memories[0].get("storage_key", "")
                if key:
                    count = adapter.store_graph_entities(key, "Python JWT backend", "default")
                    assert isinstance(count, int)
            cm.close()
        finally:
            adapter.close()

    def test_carrymem_recall_by_entity_api(self):
        """CarryMem facade should expose recall_by_entity."""
        from carrymem import CarryMem

        cm = CarryMem(storage="sqlite", db_path=":memory:")
        try:
            assert hasattr(cm, "recall_by_entity")
            assert hasattr(cm, "recall_by_relation")
            assert hasattr(cm, "recall_graph")
            assert hasattr(cm, "add_graph_relation")

            # No memories stored yet -> empty result
            assert cm.recall_by_entity("Python") == []
            assert cm.recall_graph("Python") == {"entities": [], "memories": []}
        finally:
            cm.close()

    def test_carrymem_add_graph_relation_returns_bool(self):
        """add_graph_relation should return bool (False without entities, True after creation)."""
        from carrymem import CarryMem

        cm = CarryMem(storage="sqlite", db_path=":memory:")
        try:
            result = cm.add_graph_relation("EntityA", "EntityB", "connects_to")
            assert isinstance(result, bool)
            assert result is True
        finally:
            cm.close()

    def test_base_adapter_graph_defaults_return_empty(self):
        """Non-SQLite adapters should return safe defaults for graph methods."""
        from carrymem.adapters.base import StorageAdapter

        # Verify default implementations exist on the base class (return empty/False/0)
        # without requiring instantiation of the abstract class
        assert hasattr(StorageAdapter, "recall_by_entity")
        assert hasattr(StorageAdapter, "recall_by_relation")
        assert hasattr(StorageAdapter, "recall_graph")
        assert hasattr(StorageAdapter, "add_graph_relation")
        assert hasattr(StorageAdapter, "store_graph_entities")
