"""
Tests for context.py module.

Covers: context_relevance, select_memories, select_knowledge,
format_memory_entry, format_knowledge_entry, build_prompt.
"""

import pytest

from memory_classification_engine.context import (
    context_relevance,
    select_memories,
    select_knowledge,
    format_memory_entry,
    format_knowledge_entry,
    build_prompt,
)


class TestContextRelevance:
    def test_exact_match(self):
        score = context_relevance("I prefer dark mode", "dark mode")
        assert score > 0

    def test_no_match(self):
        score = context_relevance("I prefer dark mode", "database selection")
        assert score < 0.5

    def test_partial_match(self):
        score = context_relevance("I prefer dark mode for editors", "dark mode")
        assert score > 0

    def test_empty_context(self):
        score = context_relevance("I prefer dark mode", "")
        assert isinstance(score, float)


class TestSelectMemories:
    def test_select_basic(self):
        memories = [
            {"content": "I prefer dark mode", "type": "user_preference"},
            {"content": "I use PostgreSQL", "type": "decision"},
        ]
        result = select_memories(memories, context="dark mode")
        assert isinstance(result, list)

    def test_select_empty(self):
        result = select_memories([], context="test")
        assert result == []

    def test_select_no_context(self):
        memories = [
            {"content": "I prefer dark mode", "type": "user_preference"},
        ]
        result = select_memories(memories, context="")
        assert isinstance(result, list)


class TestFormatMemoryEntry:
    def test_format_basic(self):
        m = {"content": "I prefer dark mode", "type": "user_preference"}
        result = format_memory_entry(m)
        assert isinstance(result, str)
        assert "dark mode" in result

    def test_format_with_language(self):
        m = {"content": "I prefer dark mode", "type": "user_preference"}
        result = format_memory_entry(m, language="zh")
        assert isinstance(result, str)


class TestFormatKnowledgeEntry:
    def test_format_basic(self):
        k = {"title": "PostgreSQL Guide", "content": "Use PostgreSQL for relational data"}
        result = format_knowledge_entry(k)
        assert isinstance(result, str)


class TestBuildPrompt:
    def test_build_basic(self):
        memories = [
            {"content": "I prefer dark mode", "type": "user_preference"},
        ]
        knowledge = []
        result = build_prompt(memories=memories, knowledge=knowledge)
        assert isinstance(result, str)

    def test_build_empty(self):
        result = build_prompt(memories=[], knowledge=[])
        assert isinstance(result, str)

    def test_build_with_knowledge(self):
        memories = [
            {"content": "I prefer dark mode", "type": "user_preference"},
        ]
        knowledge = [
            {"title": "Guide", "content": "Some knowledge"},
        ]
        result = build_prompt(memories=memories, knowledge=knowledge)
        assert isinstance(result, str)

    def test_build_with_language(self):
        memories = [
            {"content": "I prefer dark mode", "type": "user_preference"},
        ]
        result = build_prompt(memories=memories, knowledge=[], language="zh")
        assert isinstance(result, str)
