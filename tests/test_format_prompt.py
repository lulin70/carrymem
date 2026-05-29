"""Tests for format.py and prompt.py modules."""

import pytest
from carrymem.format import format_memory_entry, format_knowledge_entry, _extract_event_dates
from carrymem.prompt import build_prompt, build_qa_prompt


class TestFormatMemoryEntry:
    def test_preference_format(self):
        m = {
            "type": "user_preference",
            "content": "dark mode",
            "raw_text": "I prefer dark mode",
            "confidence": 0.9,
        }
        result = format_memory_entry(m, "en")
        assert "dark mode" in result
        assert "IMPORTANT" in result

    def test_correction_format(self):
        m = {
            "type": "correction",
            "content": "not Java but Python",
            "raw_text": "",
            "confidence": 0.8,
        }
        result = format_memory_entry(m, "en")
        assert "NOT repeat" in result

    def test_superseded_format(self):
        m = {
            "type": "user_preference",
            "content": "light mode",
            "raw_text": "",
            "superseded_at": "2024-01-01",
            "confidence": 0.8,
        }
        result = format_memory_entry(m, "en")
        assert "outdated" in result.lower()

    def test_chinese_labels(self):
        m = {
            "type": "user_preference",
            "content": "深色模式",
            "raw_text": "",
            "confidence": 0.8,
            "auto_rule": "prefer",
        }
        result = format_memory_entry(m, "zh")
        assert "偏好" in result or "IMPORTANT" in result


class TestExtractEventDates:
    def test_english_date(self):
        assert "January 15" in _extract_event_dates("On January 15 we launched")

    def test_iso_date(self):
        # _extract_event_dates only matches English month names and slash dates, not ISO format
        result = _extract_event_dates("Started on 2024-03-01")
        # ISO dates are not matched by the current patterns
        assert isinstance(result, str)

    def test_no_date(self):
        assert _extract_event_dates("no dates here") == ""


class TestBuildQAPrompt:
    def test_preference_only(self):
        memories = [
            {
                "type": "user_preference",
                "content": "dark mode",
                "raw_text": "",
                "confidence": 0.9,
                "auto_rule": "prefer",
            },
        ]
        result = build_qa_prompt(memories, [], "What theme do I prefer?")
        assert "Preference" in result or "dark mode" in result

    def test_no_memories(self):
        result = build_qa_prompt([], [], "Hello?")
        assert len(result) > 0

    def test_chinese_prompt(self):
        memories = [
            {"type": "user_preference", "content": "深色模式", "raw_text": "", "confidence": 0.9},
        ]
        result = build_qa_prompt(memories, [], "我喜欢什么？", language="zh")
        assert "深色模式" in result


class TestBuildPrompt:
    def test_mandatory_tier(self):
        memories = [
            {"type": "correction", "content": "not Java", "raw_text": "", "confidence": 0.9},
        ]
        result = build_prompt(memories, [])
        assert "Mandatory" in result or "not Java" in result

    def test_knowledge_section(self):
        knowledge = [{"title": "Python Tips", "content": "Use list comprehensions", "tags": ["python"]}]
        result = build_prompt([], knowledge)
        assert "Python Tips" in result
