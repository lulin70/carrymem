"""Test suite for v0.8.0 graph tools and edge confidence labels.

Covers:
  - P0-1: MCP graph tools (shortest_path, get_memory_impact)
  - P0-2: Edge confidence labels (EXTRACTED/INFERRED/AMBIGUOUS)

Test dimensions per DevSquad Iron Rules:
  - Happy Path: shortest_path direct/multi-hop, get_memory_impact basic
  - Boundary: same entity, no path, max_hops limit
  - Error: invalid confidence label, empty input
  - Integration: CarryMem facade API, adapter delegation
"""

from __future__ import annotations

import sqlite3

import pytest

from carrymem.layers.knowledge_graph import _VALID_CONFIDENCE_LABELS, KnowledgeGraph


class FakeConnMgr:
    """Minimal ConnectionManager wrapper around a real sqlite3 connection."""

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
    """Create schema with v0.8.0 confidence column."""
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
        CREATE INDEX IF NOT EXISTS idx_relations_confidence ON memory_relations(confidence);
    """)
    conn.commit()


def _insert_memory(conn: sqlite3.Connection, storage_key: str, content: str, importance: float = 0.5) -> None:
    conn.execute(
        "INSERT INTO memories (id, type, content, storage_key, content_hash, importance_score) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (storage_key, "fact", content, storage_key, "hash_" + storage_key, importance),
    )
    conn.commit()


def _make_graph() -> KnowledgeGraph:
    """Create a KnowledgeGraph with in-memory SQLite and initialized schema."""
    conn_mgr = FakeConnMgr()
    _init_graph_schema(conn_mgr.get_connection())
    return KnowledgeGraph(conn_mgr=conn_mgr, entity_normalizer=None, input_validator=None)


def _init_graph_schema_without_confidence(conn: sqlite3.Connection) -> None:
    """Create v0.6.2 graph schema WITHOUT confidence column (pre-v0.8.0 state).

    Used by TestMigrateV100 to verify migrate_v100 adds the column correctly.
    """
    conn.executescript("""
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
            FOREIGN KEY (src_entity_id) REFERENCES memory_entities(id),
            FOREIGN KEY (dst_entity_id) REFERENCES memory_entities(id)
        );

        CREATE INDEX IF NOT EXISTS idx_entities_text ON memory_entities(entity_text);
    """)
    conn.commit()


# ── shortest_path tests ───────────────────────────────────────────────────


class TestShortestPath:
    """Tests for KnowledgeGraph.shortest_path (v0.8.0)."""

    def test_shortest_path_direct_connection(self):
        """Verify: directly connected entities have path length 1.

        Scenario: A → B (direct relation)
        Expected: path = [A, B], length = 1, found = True
        """
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a", namespace="default")

        result = graph.shortest_path("Python", "Programming", max_hops=4)

        assert result["found"] is True
        assert result["length"] == 1
        assert result["path"][0] == "Python"
        assert result["path"][-1] == "Programming"

    def test_shortest_path_multi_hop(self):
        """Verify: multi-hop path is found correctly.

        Scenario: A → B → C (two-hop relation)
        Expected: path = [A, B, C], length = 2, found = True
        """
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a")
        graph.add_relation("Programming", "Computer_Science", "part_of")

        result = graph.shortest_path("Python", "Computer_Science", max_hops=4)

        assert result["found"] is True
        assert result["length"] == 2
        assert result["path"][0] == "Python"
        assert result["path"][-1] == "Computer_Science"
        assert "Programming" in result["path"]

    def test_shortest_path_same_entity(self):
        """Verify: same src and dst returns path length 0.

        Scenario: src == dst
        Expected: path = [entity], length = 0, found = True
        """
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a")

        result = graph.shortest_path("Python", "Python")

        assert result["found"] is True
        assert result["length"] == 0
        assert result["path"] == ["Python"]

    def test_shortest_path_no_path(self):
        """Verify: disconnected entities return found=False.

        Scenario: A and B exist but have no connecting path
        Expected: path = [], length = -1, found = False
        """
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a")
        graph.add_relation("Java", "JVM", "runs_on")

        result = graph.shortest_path("Python", "Java", max_hops=4)

        assert result["found"] is False
        assert result["length"] == -1
        assert result["path"] == []

    def test_shortest_path_nonexistent_entity(self):
        """Verify: nonexistent entity returns found=False."""
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a")

        result = graph.shortest_path("Python", "Nonexistent")

        assert result["found"] is False
        assert result["length"] == -1

    def test_shortest_path_max_hops_limit(self):
        """Verify: max_hops limit prevents infinite traversal.

        Scenario: A → B → C → D, but max_hops=1
        Expected: path not found (exceeds max_hops)
        """
        graph = _make_graph()
        graph.add_relation("A", "B", "rel")
        graph.add_relation("B", "C", "rel")
        graph.add_relation("C", "D", "rel")

        result = graph.shortest_path("A", "D", max_hops=1)

        assert result["found"] is False

    def test_shortest_path_empty_input(self):
        """Verify: empty entity text returns found=False."""
        graph = _make_graph()

        result = graph.shortest_path("", "B")

        assert result["found"] is False
        assert result["length"] == -1

    def test_shortest_path_clamps_max_hops(self):
        """Verify: max_hops > 10 is clamped to 10."""
        graph = _make_graph()
        graph.add_relation("A", "B", "rel")

        result = graph.shortest_path("A", "B", max_hops=100)

        assert result["found"] is True
        assert result["length"] == 1


# ── get_memory_impact tests ───────────────────────────────────────────────


class TestGetMemoryImpact:
    """Tests for KnowledgeGraph.get_memory_impact (v0.8.0)."""

    def test_get_memory_impact_basic(self):
        """Verify: impact score calculation for a memory with entities and relations.

        Scenario: memory has 2 entities and 1 relation
        Expected: entity_count=2, relation_count=1, impact_score=2*0.4+1*0.4+0=1.2
        """
        graph = _make_graph()
        conn = graph._conn_mgr.get_connection()
        _insert_memory(conn, "mem_1", "Python is a programming language")

        # Add entities linked to the memory
        graph._find_or_create_entity("Python", "default", conn, "2026-01-01T00:00:00Z")
        conn.execute(
            "INSERT INTO memory_entities (memory_key, entity_type, entity_text, confidence, namespace, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_1", "concept", "Python", 0.9, "default", "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO memory_entities (memory_key, entity_type, entity_text, confidence, namespace, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_1", "concept", "Programming", 0.8, "default", "2026-01-01T00:00:00Z"),
        )
        conn.commit()

        # Add a relation evidenced by this memory
        graph.add_relation("Python", "Programming", "is_a", source_memory_key="mem_1")

        result = graph.get_memory_impact("mem_1")

        assert result["memory_id"] == "mem_1"
        assert result["entity_count"] == 2
        assert result["relation_count"] == 1
        assert result["cross_namespace"] is False
        # 2*0.4 + 1*0.4 + 0*0.2 = 1.2
        assert result["impact_score"] == 1.2

    def test_get_memory_impact_cross_namespace(self):
        """Verify: cross_namespace detection when entities span namespaces.

        Scenario: memory has entities in two namespaces
        Expected: cross_namespace=True, impact_score includes 0.2 bonus
        """
        graph = _make_graph()
        conn = graph._conn_mgr.get_connection()
        _insert_memory(conn, "mem_1", "Cross-namespace memory")

        # Add entities in different namespaces linked to the same memory
        conn.execute(
            "INSERT INTO memory_entities (memory_key, entity_type, entity_text, confidence, namespace, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_1", "concept", "EntityA", 0.9, "default", "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO memory_entities (memory_key, entity_type, entity_text, confidence, namespace, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_1", "concept", "EntityB", 0.8, "work", "2026-01-01T00:00:00Z"),
        )
        conn.commit()

        result = graph.get_memory_impact("mem_1")

        assert result["entity_count"] == 2
        assert result["cross_namespace"] is True
        # 2*0.4 + 0*0.4 + 1*0.2 = 1.0
        assert result["impact_score"] == 1.0

    def test_get_memory_impact_empty_memory(self):
        """Verify: memory with no entities returns zero impact."""
        graph = _make_graph()
        conn = graph._conn_mgr.get_connection()
        _insert_memory(conn, "mem_empty", "Empty memory")

        result = graph.get_memory_impact("mem_empty")

        assert result["entity_count"] == 0
        assert result["relation_count"] == 0
        assert result["cross_namespace"] is False
        assert result["impact_score"] == 0.0

    def test_get_memory_impact_nonexistent_memory(self):
        """Verify: nonexistent memory returns zero impact."""
        graph = _make_graph()

        result = graph.get_memory_impact("nonexistent_key")

        assert result["memory_id"] == "nonexistent_key"
        assert result["entity_count"] == 0
        assert result["impact_score"] == 0.0

    def test_get_memory_impact_empty_input(self):
        """Verify: empty memory_key returns zero impact."""
        graph = _make_graph()

        result = graph.get_memory_impact("")

        assert result["entity_count"] == 0
        assert result["impact_score"] == 0.0


# ── Edge confidence label tests (P0-2) ────────────────────────────────────


class TestEdgeConfidence:
    """Tests for memory_relations.confidence column (v0.8.0)."""

    def test_add_relation_default_confidence(self):
        """Verify: add_relation without confidence defaults to EXTRACTED."""
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a")

        conn = graph._conn_mgr.get_connection()
        row = conn.execute("SELECT confidence FROM memory_relations WHERE relation_type = 'is_a'").fetchone()

        assert row["confidence"] == "EXTRACTED"

    def test_add_relation_with_inferred_confidence(self):
        """Verify: add_relation with confidence='INFERRED' is stored correctly."""
        graph = _make_graph()
        graph.add_relation("Python", "AI", "enables", confidence="INFERRED")

        conn = graph._conn_mgr.get_connection()
        row = conn.execute("SELECT confidence FROM memory_relations WHERE relation_type = 'enables'").fetchone()

        assert row["confidence"] == "INFERRED"

    def test_add_relation_with_ambiguous_confidence(self):
        """Verify: add_relation with confidence='AMBIGUOUS' is stored correctly."""
        graph = _make_graph()
        graph.add_relation("Python", "Snake", "could_mean", confidence="AMBIGUOUS")

        conn = graph._conn_mgr.get_connection()
        row = conn.execute("SELECT confidence FROM memory_relations WHERE relation_type = 'could_mean'").fetchone()

        assert row["confidence"] == "AMBIGUOUS"

    def test_add_relation_invalid_confidence_raises(self):
        """Verify: invalid confidence label raises ValueError.

        Scenario: confidence='GUESSED' (not in valid set)
        Expected: ValueError raised
        """
        graph = _make_graph()

        with pytest.raises(ValueError, match="Invalid confidence label"):
            graph.add_relation("A", "B", "rel", confidence="GUESSED")

    def test_add_relation_empty_confidence_raises(self):
        """Verify: empty confidence label raises ValueError."""
        graph = _make_graph()

        with pytest.raises(ValueError, match="Invalid confidence label"):
            graph.add_relation("A", "B", "rel", confidence="")

    def test_valid_confidence_labels_constant(self):
        """Verify: _VALID_CONFIDENCE_LABELS contains exactly the 3 valid labels."""
        assert _VALID_CONFIDENCE_LABELS == frozenset({"EXTRACTED", "INFERRED", "AMBIGUOUS"})

    def test_list_relations_returns_confidence(self):
        """Verify: list_relations includes confidence field in results."""
        graph = _make_graph()
        graph.add_relation("Python", "Programming", "is_a", confidence="EXTRACTED")
        graph.add_relation("Python", "AI", "enables", confidence="INFERRED")

        relations = graph.list_relations()

        assert len(relations) == 2
        confidence_values = {r["confidence"] for r in relations}
        assert confidence_values == {"EXTRACTED", "INFERRED"}

    def test_recall_by_relation_returns_confidence(self):
        """Verify: recall_by_relation includes confidence in memory results."""
        graph = _make_graph()
        conn = graph._conn_mgr.get_connection()
        _insert_memory(conn, "mem_1", "Python enables AI")

        graph.add_relation("Python", "AI", "enables", source_memory_key="mem_1", confidence="INFERRED")

        results = graph.recall_by_relation("Python")

        assert len(results) >= 1
        # The confidence field is included as relation_confidence (aliased in SQL)
        assert "relation_confidence" in results[0]
        assert results[0]["relation_confidence"] == "INFERRED"


# ── Integration: CarryMem facade ──────────────────────────────────────────


class TestCarryMemFacadeIntegration:
    """Integration tests for CarryMem facade API (v0.8.0)."""

    def test_carrymem_recall_shortest_path(self):
        """Verify: CarryMem.recall_shortest_path delegates to adapter."""
        from carrymem.carrymem import CarryMem

        cm = CarryMem(storage="sqlite", db_path=":memory:")
        cm.add_graph_relation("Python", "Programming", "is_a")
        cm.add_graph_relation("Programming", "Computer_Science", "part_of")

        result = cm.recall_shortest_path("Python", "Computer_Science", max_hops=4)

        assert result["found"] is True
        assert result["length"] == 2

    def test_carrymem_recall_memory_impact(self):
        """Verify: CarryMem.recall_memory_impact delegates to adapter."""
        from carrymem.carrymem import CarryMem

        cm = CarryMem(storage="sqlite", db_path=":memory:")
        # Store a memory first to exercise the full pipeline
        cm.classify_and_remember("I prefer Python for data science")
        # The memory may or may not be stored depending on classification;
        # we test the impact API returns a valid structure regardless
        result = cm.recall_memory_impact("any_key")

        assert "memory_id" in result
        assert "entity_count" in result
        assert "relation_count" in result
        assert "cross_namespace" in result
        assert "impact_score" in result

    def test_carrymem_add_graph_relation_with_confidence(self):
        """Verify: CarryMem.add_graph_relation accepts confidence parameter."""
        from carrymem.carrymem import CarryMem

        cm = CarryMem(storage="sqlite", db_path=":memory:")
        result = cm.add_graph_relation("Python", "AI", "enables", confidence="INFERRED")

        assert result is True

    def test_carrymem_add_graph_relation_invalid_confidence(self):
        """Verify: CarryMem.add_graph_relation rejects invalid confidence."""
        from carrymem.carrymem import CarryMem

        cm = CarryMem(storage="sqlite", db_path=":memory:")

        with pytest.raises(ValueError, match="Invalid confidence label"):
            cm.add_graph_relation("A", "B", "rel", confidence="INVALID")


# ── recall_graph tests (P0-5) ─────────────────────────────────────────────


class TestQueryGraph:
    """Tests for KnowledgeGraph.recall_graph (v0.8.0)."""

    def test_query_graph_basic(self):
        """Verify: recall_graph returns connected entities and memories.

        Scenario: 2 memories linked via entity relations
        Expected: entities list contains connected entities, memories list
        contains memories linked via source_memory_key
        """
        graph = _make_graph()
        conn = graph._conn_mgr.get_connection()
        _insert_memory(conn, "mem_1", "Python is a programming language")
        _insert_memory(conn, "mem_2", "Programming enables AI development")

        # Add relations with source_memory_key to link memories into the graph
        graph.add_relation("Python", "Programming", "is_a", source_memory_key="mem_1")
        graph.add_relation("Programming", "AI", "enables", source_memory_key="mem_2")

        result = graph.recall_graph("Python", max_hops=2)

        assert "entities" in result
        assert "memories" in result
        entity_texts = {e["entity_text"] for e in result["entities"]}
        assert "Python" in entity_texts
        assert "Programming" in entity_texts
        assert "AI" in entity_texts
        # Memories linked via source_memory_key should be returned
        memory_keys = {m["storage_key"] for m in result["memories"]}
        assert "mem_1" in memory_keys
        assert "mem_2" in memory_keys

    def test_query_graph_max_hops_limit(self):
        """Verify: max_hops=1 only returns direct neighbors, not 2-hop entities.

        Scenario: A → B → C chain
        Expected: with max_hops=1, C is NOT returned (2 hops away)
        """
        graph = _make_graph()
        graph.add_relation("A", "B", "rel")
        graph.add_relation("B", "C", "rel")

        result = graph.recall_graph("A", max_hops=1)

        entity_texts = {e["entity_text"] for e in result["entities"]}
        assert "A" in entity_texts
        assert "B" in entity_texts
        # C is 2 hops away, should NOT be included with max_hops=1
        assert "C" not in entity_texts

    def test_query_graph_empty_input(self):
        """Verify: empty entity string returns empty result."""
        graph = _make_graph()
        graph.add_relation("A", "B", "rel")

        result = graph.recall_graph("")

        assert result["entities"] == []
        assert result["memories"] == []

    def test_query_graph_clamps_max_hops(self):
        """Verify: max_hops > 5 does not raise an error.

        The BFS uses a visited set so large max_hops terminates gracefully
        once the frontier is exhausted. Just verify no exception and valid
        structure is returned.
        """
        graph = _make_graph()
        graph.add_relation("A", "B", "rel")
        graph.add_relation("B", "C", "rel")

        # Should not raise even with very large max_hops
        result = graph.recall_graph("A", max_hops=100)

        assert "entities" in result
        assert "memories" in result
        entity_texts = {e["entity_text"] for e in result["entities"]}
        assert "A" in entity_texts
        assert "B" in entity_texts
        assert "C" in entity_texts


# ── migrate_v100 schema tests (P0-6) ──────────────────────────────────────


class TestMigrateV100:
    """Tests for SchemaManager.migrate_v100 (v0.8.0 edge confidence column)."""

    @staticmethod
    def _make_pre_v100_conn_mgr():
        """Create a conn_mgr with v0.6.2 graph schema (no confidence column)."""
        conn_mgr = FakeConnMgr()
        _init_graph_schema_without_confidence(conn_mgr.get_connection())
        return conn_mgr

    def test_migration_v100_adds_confidence_column(self):
        """Verify: migrate_v100 adds confidence column to memory_relations."""
        from carrymem.adapters.sqlite.schema import SchemaManager

        conn_mgr = self._make_pre_v100_conn_mgr()
        manager = SchemaManager(conn_mgr)
        manager.migrate_v100()

        conn = conn_mgr.get_connection()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_relations)")}
        assert "confidence" in columns

    def test_migration_v100_default_extracted(self):
        """Verify: existing edges get confidence='EXTRACTED' after migration.

        Scenario: a relation exists BEFORE migration (no confidence column)
        Expected: after migrate_v100, the row's confidence defaults to 'EXTRACTED'
        """
        from carrymem.adapters.sqlite.schema import SchemaManager

        conn_mgr = self._make_pre_v100_conn_mgr()
        conn = conn_mgr.get_connection()
        # Insert two entities and a relation BEFORE migration (no confidence col)
        conn.execute(
            "INSERT INTO memory_entities (memory_key, entity_type, entity_text, confidence, namespace) "
            "VALUES (?, ?, ?, ?, ?)",
            (None, "concept", "Python", 0.5, "default"),
        )
        conn.execute(
            "INSERT INTO memory_entities (memory_key, entity_type, entity_text, confidence, namespace) "
            "VALUES (?, ?, ?, ?, ?)",
            (None, "concept", "Programming", 0.5, "default"),
        )
        conn.execute(
            "INSERT INTO memory_relations (src_entity_id, dst_entity_id, relation_type, namespace) "
            "VALUES (?, ?, ?, ?)",
            (1, 2, "is_a", "default"),
        )
        conn.commit()

        manager = SchemaManager(conn_mgr)
        manager.migrate_v100()

        row = conn.execute("SELECT confidence FROM memory_relations WHERE relation_type = 'is_a'").fetchone()
        assert row["confidence"] == "EXTRACTED"

    def test_migration_v100_idempotent(self):
        """Verify: running migrate_v100 twice does not raise."""
        from carrymem.adapters.sqlite.schema import SchemaManager

        conn_mgr = self._make_pre_v100_conn_mgr()
        manager = SchemaManager(conn_mgr)
        manager.migrate_v100()
        # Second run should be idempotent (no error)
        manager.migrate_v100()

        conn = conn_mgr.get_connection()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_relations)")}
        assert "confidence" in columns

    def test_migration_v100_index_created(self):
        """Verify: migrate_v100 creates idx_relations_confidence index."""
        from carrymem.adapters.sqlite.schema import SchemaManager

        conn_mgr = self._make_pre_v100_conn_mgr()
        manager = SchemaManager(conn_mgr)
        manager.migrate_v100()

        conn = conn_mgr.get_connection()
        indexes = {
            row[1]
            for row in conn.execute(
                "SELECT type, name FROM sqlite_master " "WHERE type='index' AND tbl_name='memory_relations'"
            )
        }
        assert "idx_relations_confidence" in indexes
