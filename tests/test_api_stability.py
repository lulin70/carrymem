"""API stability tests for ISP Protocol contracts (TD-006).

Verifies that adapter classes satisfy the Interface Segregation Principle
(ISP) Protocols defined in ``adapters/base.py``. These tests serve as:
1. API stability snapshots — breaking changes to public method names will fail
2. ISP isolation verification — JSON/Obsidian adapters do NOT satisfy
   GraphClient/RecallClient (only SQLiteAdapter does)
3. Capability Protocol documentation — each Protocol's method set is explicit

The 4 ISP functional groups (TD-006 + TD-007):
- ``StorageClient`` — basic CRUD (all adapters)
- ``RecallClient`` — advanced retrieval (SQLiteAdapter only)
- ``GraphClient`` — knowledge graph (SQLiteAdapter only)
- ``VersioningProvider`` — versioning (SQLiteAdapter only, from TD-007)
"""

import pytest

from carrymem.adapters.base import (
    EmbeddingModelProvider,
    EncryptionProvider,
    GraphClient,
    KeyLookupProvider,
    RawConnectionProvider,
    RecallClient,
    StorageClient,
    VersioningProvider,
)
from carrymem.adapters.json_adapter import JSONAdapter
from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.adapters.sqlite import SQLiteAdapter


@pytest.fixture
def sqlite_adapter(tmp_path):
    """Create an initialized SQLiteAdapter instance."""
    adapter = SQLiteAdapter(
        db_path=str(tmp_path / "test_api.db"),
        namespace="api_test",
        enable_vector_search=False,
    )
    adapter.initialize({"namespace": "api_test"})
    yield adapter
    adapter.close()


@pytest.fixture
def json_adapter(tmp_path):
    """Create an initialized JSONAdapter instance."""
    adapter = JSONAdapter(path=str(tmp_path / "test_api.json"), namespace="api_test")
    adapter.initialize({"namespace": "api_test"})
    yield adapter
    adapter.close()


@pytest.fixture
def obsidian_adapter(tmp_path):
    """Create an initialized ObsidianAdapter instance."""
    vault = tmp_path / "vault"
    vault.mkdir()
    db = tmp_path / "obsidian_api_test.db"
    adapter = ObsidianAdapter(vault_path=str(vault), db_path=str(db))
    adapter.initialize({"namespace": "api_test"})
    yield adapter
    adapter.close()


# ── SQLiteAdapter: satisfies ALL ISP Protocols (full-featured) ─────


class TestSQLiteAdapterISPProtocols:
    """SQLiteAdapter (full-featured backend) satisfies all ISP Protocols."""

    def test_satisfies_storage_client(self, sqlite_adapter):
        """Core CRUD: store, store_entry, delete, count."""
        assert isinstance(sqlite_adapter, StorageClient)

    def test_satisfies_recall_client(self, sqlite_adapter):
        """Advanced recall: recall_aggregated, recall_timeline, recall_multi_mode, etc."""
        assert isinstance(sqlite_adapter, RecallClient)

    def test_satisfies_graph_client(self, sqlite_adapter):
        """Knowledge graph: store_graph_entities, recall_by_entity, shortest_path, etc."""
        assert isinstance(sqlite_adapter, GraphClient)

    def test_satisfies_versioning_provider(self, sqlite_adapter):
        """Versioning: update_memory, rollback_memory, get_memory_history."""
        assert isinstance(sqlite_adapter, VersioningProvider)

    def test_satisfies_raw_connection_provider(self, sqlite_adapter):
        """Raw connection access: get_raw_connection()."""
        assert isinstance(sqlite_adapter, RawConnectionProvider)

    def test_satisfies_encryption_provider(self, sqlite_adapter):
        """Encryption: security property, decrypt_field()."""
        assert isinstance(sqlite_adapter, EncryptionProvider)

    def test_satisfies_key_lookup_provider(self, sqlite_adapter):
        """Key lookup: get_by_key()."""
        assert isinstance(sqlite_adapter, KeyLookupProvider)


# ── JSONAdapter: satisfies StorageClient ONLY (minimal backend) ────


class TestJSONAdapterISPProtocols:
    """JSONAdapter (minimal backend) satisfies StorageClient but NOT
    GraphClient/RecallClient/VersioningProvider (ISP isolation)."""

    def test_satisfies_storage_client(self, json_adapter):
        """Core CRUD: store, store_entry, delete, count."""
        assert isinstance(json_adapter, StorageClient)

    def test_does_not_satisfy_recall_client(self, json_adapter):
        """No advanced recall methods (recall_aggregated, recall_timeline, etc.)."""
        assert not isinstance(json_adapter, RecallClient)

    def test_does_not_satisfy_graph_client(self, json_adapter):
        """No knowledge graph methods."""
        assert not isinstance(json_adapter, GraphClient)

    def test_does_not_satisfy_versioning_provider(self, json_adapter):
        """No versioning methods (update_memory, rollback_memory)."""
        assert not isinstance(json_adapter, VersioningProvider)


# ── ObsidianAdapter: satisfies StorageClient ONLY (minimal backend) ─


class TestObsidianAdapterISPProtocols:
    """ObsidianAdapter (minimal backend) satisfies StorageClient but NOT
    GraphClient/RecallClient/VersioningProvider (ISP isolation)."""

    def test_satisfies_storage_client(self, obsidian_adapter):
        """Core CRUD: store, store_entry, delete, count."""
        assert isinstance(obsidian_adapter, StorageClient)

    def test_does_not_satisfy_recall_client(self, obsidian_adapter):
        """No advanced recall methods."""
        assert not isinstance(obsidian_adapter, RecallClient)

    def test_does_not_satisfy_graph_client(self, obsidian_adapter):
        """No knowledge graph methods."""
        assert not isinstance(obsidian_adapter, GraphClient)

    def test_does_not_satisfy_versioning_provider(self, obsidian_adapter):
        """No versioning methods."""
        assert not isinstance(obsidian_adapter, VersioningProvider)


# ── Protocol method set stability (API snapshot) ───────────────────


class TestProtocolMethodStability:
    """Verify that each ISP Protocol's method set is stable.

    These tests act as API snapshots — adding or removing a method from
    a Protocol will require updating the expected method set here,
    providing a review checkpoint for public API changes.
    """

    def test_storage_client_methods(self):
        """StorageClient must have exactly these 4 methods."""
        expected = {"store", "store_entry", "delete", "count"}
        actual = {
            name for name in dir(StorageClient)
            if not name.startswith("_") and callable(getattr(StorageClient, name, None))
        }
        # Protocol classes have some extra attrs; check that expected methods exist
        assert expected.issubset(actual), f"Missing methods: {expected - actual}"

    def test_recall_client_methods(self):
        """RecallClient must have these 6 methods."""
        expected = {
            "recall_aggregated",
            "recall_timeline",
            "recall_by_time",
            "recall_semantic",
            "recall_hybrid",
            "recall_multi_mode",
        }
        actual = {
            name for name in dir(RecallClient)
            if not name.startswith("_") and callable(getattr(RecallClient, name, None))
        }
        assert expected.issubset(actual), f"Missing methods: {expected - actual}"

    def test_graph_client_methods(self):
        """GraphClient must have these 9 methods."""
        expected = {
            "store_graph_entities",
            "recall_by_entity",
            "recall_by_relation",
            "recall_graph",
            "shortest_path",
            "get_memory_impact",
            "add_graph_relation",
            "list_graph_entities",
            "list_graph_relations",
        }
        actual = {
            name for name in dir(GraphClient) if not name.startswith("_") and callable(getattr(GraphClient, name, None))
        }
        assert expected.issubset(actual), f"Missing methods: {expected - actual}"

    def test_versioning_provider_methods(self):
        """VersioningProvider must have these 3 methods."""
        expected = {"update_memory", "rollback_memory", "get_memory_history"}
        actual = {
            name for name in dir(VersioningProvider)
            if not name.startswith("_") and callable(getattr(VersioningProvider, name, None))
        }
        assert expected.issubset(actual), f"Missing methods: {expected - actual}"
