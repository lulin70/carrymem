"""
Extended CarryMem integration tests for coverage improvement.

Covers: knowledge adapter, system prompt building,
recall_memories, classify_and_remember with various types.
"""

import os

import pytest

from carrymem import CarryMem
from carrymem.adapters.obsidian_adapter import ObsidianAdapter
from carrymem.errors import KnowledgeNotConfiguredError


@pytest.fixture
def cm(tmp_path):
    db_path = str(tmp_path / "test_cm_ext2.db")
    carrymem = CarryMem(db_path=db_path)
    yield carrymem
    carrymem.close()


@pytest.fixture
def cm_with_rules(tmp_path):
    db_path = str(tmp_path / "test_cm_rules.db")
    carrymem = CarryMem(db_path=db_path)
    carrymem.rule_engine.add_rule(
        trigger="security",
        action="Never leak secrets",
        rule_type="forbid",
        override=True,
    )
    carrymem.rule_engine.add_rule(
        trigger="database",
        action="Prefer PostgreSQL",
        rule_type="prefer",
        override=False,
    )
    yield carrymem
    carrymem.close()


@pytest.fixture
def cm_with_knowledge(tmp_path):
    """CarryMem wired to an Obsidian knowledge adapter, all paths isolated."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Test Note\nSome knowledge content about Python")
    knowledge = ObsidianAdapter(str(vault), db_path=str(tmp_path / "knowledge.db"))
    carrymem = CarryMem(
        db_path=str(tmp_path / "test_cm_knowledge.db"),
        knowledge_adapter=knowledge,
        auto_backup_interval=0,
    )
    yield carrymem
    carrymem.close()


class TestCarryMemKnowledgeAdapter:
    def test_knowledge_adapter_property(self, cm, cm_with_knowledge):
        assert cm.knowledge_adapter is None
        assert cm_with_knowledge.knowledge_adapter is not None

    def test_index_knowledge(self, cm_with_knowledge):
        stats = cm_with_knowledge.index_knowledge()
        assert stats == {"total_files": 1, "new": 1, "updated": 0, "skipped": 0}, stats

    def test_index_knowledge_without_adapter_raises(self, cm):
        with pytest.raises(KnowledgeNotConfiguredError):
            cm.index_knowledge()

    def test_recall_from_knowledge(self, cm_with_knowledge):
        cm_with_knowledge.index_knowledge()
        results = cm_with_knowledge.recall_from_knowledge("Python")
        assert len(results) == 1, results
        note = results[0]
        assert note["file_path"] == "note.md", note
        assert "Some knowledge content about Python" in note["content"], note

    def test_recall_from_knowledge_without_adapter_raises(self, cm):
        with pytest.raises(KnowledgeNotConfiguredError):
            cm.recall_from_knowledge("Python")


class TestCarryMemSystemPromptWithRules:
    def test_build_prompt_with_rules(self, cm_with_rules):
        cm_with_rules.declare("I prefer dark mode")
        prompt = cm_with_rules.build_system_prompt(context="security review")
        assert isinstance(prompt, str) and prompt.strip()
        assert "I prefer dark mode" in prompt
        assert "Never leak secrets" in prompt

    def test_build_prompt_with_memories_and_rules(self, cm_with_rules):
        cm_with_rules.declare("I prefer dark mode")
        prompt = cm_with_rules.build_system_prompt(context="coding")
        assert isinstance(prompt, str) and prompt.strip()
        assert "I prefer dark mode" in prompt


class TestCarryMemRecallMemories:
    def test_recall_memories_basic(self, cm):
        cm.declare("I prefer dark mode")
        results = cm.recall_memories(query="dark mode")
        assert isinstance(results, list)

    def test_recall_memories_no_match(self, cm):
        results = cm.recall_memories(query="nonexistent_xyz_12345")
        assert isinstance(results, list)

    def test_recall_memories_with_limit(self, cm):
        cm.declare("I prefer dark mode")
        cm.declare("I use PostgreSQL")
        results = cm.recall_memories(query="prefer", limit=1)
        assert len(results) <= 1


class TestCarryMemClassifyTypes:
    def test_classify_preference(self, cm):
        result = cm.classify_and_remember("I prefer dark mode for all editors")
        assert result is not None

    def test_classify_correction(self, cm):
        cm.declare("I use PostgreSQL")
        result = cm.classify_and_remember("Actually I use MySQL, not PostgreSQL")
        assert result is not None

    def test_classify_decision(self, cm):
        result = cm.classify_and_remember("I decided to use React for the frontend")
        assert result is not None

    def test_classify_fact(self, cm):
        result = cm.classify_and_remember("The project deadline is next Friday")
        assert result is not None

    def test_classify_relationship(self, cm):
        result = cm.classify_and_remember("Alice is my project manager")
        assert result is not None


class TestCarryMemForgetType:
    def test_forget_memory(self, cm):
        result = cm.declare("I prefer dark mode")
        if isinstance(result, dict) and "storage_key" in result:
            key = result["storage_key"]
            success = cm.forget_memory(key)
            assert isinstance(success, bool)


class TestCarryMemGetStats:
    def test_get_stats_with_data(self, cm):
        cm.declare("I prefer dark mode")
        stats = cm.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_empty(self, cm):
        stats = cm.get_stats()
        assert isinstance(stats, dict)


class TestCarryMemMemoryProfile:
    def test_get_memory_profile(self, cm):
        cm.declare("I prefer dark mode")
        profile = cm.get_memory_profile()
        assert isinstance(profile, dict)
