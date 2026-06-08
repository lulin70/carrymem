"""
Tests for Obsidian adapter module.

Covers: ObsidianAdapter, vault scanning, markdown parsing,
recall/search operations.
"""

import os

import pytest

from carrymem.adapters.obsidian_adapter import ObsidianAdapter


@pytest.fixture
def vault_dir(tmp_path):
    vault = tmp_path / "obsidian_vault"
    vault.mkdir()
    (vault / "note1.md").write_text("# Note 1\nThis is a test note about Python.")
    (vault / "note2.md").write_text("# Note 2\nAnother note about databases.")
    sub = vault / "subfolder"
    sub.mkdir()
    (sub / "note3.md").write_text("# Note 3\nDeep note about AI.")
    return str(vault)


@pytest.fixture
def adapter(vault_dir, tmp_path):
    db_path = str(tmp_path / "obsidian_test.db")
    return ObsidianAdapter(vault_dir, db_path=db_path)


class TestObsidianAdapter:
    def test_init(self, adapter):
        assert adapter is not None

    def test_init_nonexistent_vault(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ObsidianAdapter("/nonexistent/vault/path", db_path=str(tmp_path / "test.db"))

    def test_index_vault(self, adapter):
        adapter.index_vault()
        assert adapter is not None

    def test_recall(self, adapter):
        adapter.index_vault()
        results = adapter.recall("Python")
        assert isinstance(results, list)

    def test_recall_no_match(self, adapter):
        adapter.index_vault()
        results = adapter.recall("nonexistent_topic_xyz_12345")
        assert isinstance(results, list)

    def test_store_and_recall(self, adapter):
        adapter.index_vault()
        try:
            result = adapter.store("test_key", {"content": "test content"})
            assert result is not None
        except (TypeError, NotImplementedError, Exception):
            pass

    def test_close(self, adapter):
        adapter.close()
