"""E2E test: forget() knowledge graph deletion completeness (TD-066, v0.9.8).

User journey: store memories with entities → verify graph has data →
forget one memory → verify graph entities and relations are cleaned up.

Oracle Agent Memory report (arXiv:2607.13157) highlighted that deletion
completeness is a system-level concern: derived data (entities, relations,
embeddings) must be cleaned up when the source memory is deleted.
"""

from __future__ import annotations

import pytest

from carrymem import CarryMem


class TestE2EForgetGraphCleanup:
    """User journey: forget memory → graph entities/relations cleaned."""

    def test_forget_removes_graph_entities(self, fresh_carrymem):
        """User stores a memory with entities, forgets it, graph should be empty."""
        cm = fresh_carrymem
        cm.classify_and_remember("I prefer Python for backend development")

        entities_before = cm.recall_by_entity("Python")
        assert len(entities_before) > 0, "Entity should exist before forget"

        memories = cm.recall_memories(query="Python")
        assert len(memories) > 0
        storage_key = memories[0]["storage_key"]

        result = cm.forget_memory(storage_key)
        assert result is True

        entities_after = cm.recall_by_entity("Python")
        assert len(entities_after) == 0, "Entity should be cleaned after forget"

    def test_forget_removes_graph_relations(self, fresh_carrymem):
        """User adds a relation, forgets the source memory, relation should be gone.

        TD-067 fix: extract_and_store_entities now deduplicates by
        (entity_text, namespace), so add_graph_relation and recall_by_relation
        resolve to the same entity_id.
        """
        cm = fresh_carrymem
        cm.classify_and_remember("I use Python with FastAPI for APIs")
        memories = cm.recall_memories(query="Python FastAPI")
        assert len(memories) > 0
        storage_key = memories[0]["storage_key"]

        added = cm.add_graph_relation("Python", "FastAPI", "used_with",
                                       source_memory_key=storage_key)
        assert added is True, "Relation should be added"

        relations_before = cm.recall_by_relation("Python")
        assert len(relations_before) > 0, "Relation should exist before forget"

        cm.forget_memory(storage_key)

        relations_after = cm.recall_by_relation("Python")
        assert len(relations_after) == 0, "Relation should be cleaned after forget"

    def test_forget_preserves_shared_entities(self, fresh_carrymem):
        """Two memories reference same entity; forget one, other's entity survives."""
        cm = fresh_carrymem
        cm.classify_and_remember("I prefer Python for scripting")
        cm.classify_and_remember("Python is great for data analysis")

        entities_before = cm.recall_by_entity("Python")
        assert len(entities_before) >= 1, "Python entity should exist"

        memories = cm.recall_memories(query="scripting")
        assert len(memories) >= 1
        first_key = memories[0]["storage_key"]

        cm.forget_memory(first_key)

        entities_after = cm.recall_by_entity("Python")
        assert len(entities_after) >= 1, "Second memory's entity should survive"

    def test_forget_then_recall_returns_empty(self, fresh_carrymem):
        """After forget, recall_memories should not return the deleted memory."""
        cm = fresh_carrymem
        cm.classify_and_remember("I love Rust for systems programming")

        memories_before = cm.recall_memories(query="Rust")
        assert len(memories_before) > 0
        storage_key = memories_before[0]["storage_key"]

        cm.forget_memory(storage_key)

        memories_after = cm.recall_memories(query="Rust")
        assert len(memories_after) == 0, "Forgotten memory should not be recallable"

    def test_forget_nonexistent_key_no_error(self, fresh_carrymem):
        """User forgets a non-existent key, should return False without error."""
        cm = fresh_carrymem
        result = cm.forget_memory("cm_nonexistent_key_12345")
        assert result is False
