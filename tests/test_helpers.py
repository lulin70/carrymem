"""
Tests for utils/helpers.py module
Tests for utility functions used across the project
"""

import json
import re
import time
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from carrymem.utils.helpers import (
    MEMORY_TIERS,
    MEMORY_TYPES,
    calculate_memory_weight,
    extract_content,
    format_memory,
    generate_memory_id,
    get_current_time,
    load_json_file,
    save_json_file,
)


class TestGenerateMemoryId:
    """Tests for generate_memory_id function"""

    def test_generates_unique_ids(self):
        """Test that generated IDs are unique"""
        id1 = generate_memory_id()
        id2 = generate_memory_id()
        assert id1 != id2

    def test_id_format(self):
        """Test that ID follows expected format"""
        memory_id = generate_memory_id()
        assert memory_id.startswith("mem_")
        parts = memory_id.split("_")
        assert len(parts) == 3
        assert parts[1].isdigit()  # timestamp
        assert parts[2].isdigit()  # random suffix
        assert len(parts[2]) == 4  # 4-digit random


class TestGetCurrentTime:
    """Tests for get_current_time function"""

    def test_returns_iso_format(self):
        """Test that time is in ISO format"""
        current_time = get_current_time()
        # Should match ISO format: YYYY-MM-DDTHH:MM:SSZ
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", current_time)

    def test_returns_utc_time(self):
        """Test that time ends with Z (UTC)"""
        current_time = get_current_time()
        assert current_time.endswith("Z")


class TestExtractContent:
    """Tests for extract_content function"""

    def test_extract_following_content(self):
        """Test extracting content after pattern"""
        text = "I prefer dark mode for coding."
        pattern = r"prefer"
        result = extract_content(text, pattern, "extract_following_content")
        assert result == "dark mode for coding"

    def test_extract_surrounding_context(self):
        """Test extracting context around pattern"""
        text = "This is a long text with important keyword in the middle of it all."
        pattern = r"keyword"
        result = extract_content(text, pattern, "extract_surrounding_context")
        assert "keyword" in result
        assert len(result) <= 150  # Max 50 before + match + 100 after

    def test_extract_entity_and_relation(self):
        """Test extracting entity and relation"""
        text = "  Python is my favorite language  "
        pattern = r"Python"
        result = extract_content(text, pattern, "extract_entity_and_relation")
        assert result == "Python is my favorite language"

    def test_extract_preceding_proposal(self):
        """Test extracting content before pattern"""
        text = "Use TDD for all projects because it improves quality."
        pattern = r"because"
        result = extract_content(text, pattern, "extract_preceding_proposal")
        assert result == "Use TDD for all projects"

    def test_extract_match_only(self):
        """Test extracting only the matched pattern"""
        text = "The quick brown fox jumps"
        pattern = r"brown fox"
        result = extract_content(text, pattern, "extract")
        assert result == "brown fox"

    def test_no_match_returns_none(self):
        """Test that no match returns None"""
        text = "Some text"
        pattern = r"nonexistent"
        result = extract_content(text, pattern, "extract")
        assert result is None

    def test_unknown_action_returns_none(self):
        """Test that unknown action returns None"""
        text = "Some text"
        pattern = r"text"
        result = extract_content(text, pattern, "unknown_action")
        assert result is None


class TestCalculateMemoryWeight:
    """Tests for calculate_memory_weight function"""

    def test_high_confidence_recent_frequent(self):
        """Test weight for high confidence, recent, frequent memory"""
        weight = calculate_memory_weight(confidence=1.0, days_since_last_access=0, access_count=10)
        assert weight > 2.0  # Should be high

    def test_low_confidence_old_rare(self):
        """Test weight for low confidence, old, rare memory"""
        weight = calculate_memory_weight(confidence=0.3, days_since_last_access=30, access_count=1)
        assert weight < 0.5  # Should be low

    def test_recency_decay(self):
        """Test that weight decays with time"""
        weight_recent = calculate_memory_weight(1.0, 0, 1)
        weight_old = calculate_memory_weight(1.0, 30, 1)
        assert weight_recent > weight_old

    def test_frequency_boost(self):
        """Test that access count boosts weight"""
        weight_rare = calculate_memory_weight(1.0, 0, 1)
        weight_frequent = calculate_memory_weight(1.0, 0, 100)
        assert weight_frequent > weight_rare

    def test_zero_confidence(self):
        """Test weight with zero confidence"""
        weight = calculate_memory_weight(0.0, 0, 100)
        assert weight == 0.0


class TestFormatMemory:
    """Tests for format_memory function"""

    def test_format_complete_memory(self):
        """Test formatting a complete memory"""
        memory = {
            "type": "user_preference",
            "tier": 1,
            "content": "I prefer dark mode",
            "confidence": 0.95,
        }
        result = format_memory(memory)
        assert "Working Memory" in result
        assert "User Preference" in result
        assert "I prefer dark mode" in result
        assert "0.95" in result

    def test_format_memory_with_defaults(self):
        """Test formatting memory with missing fields"""
        memory = {"content": "Some content"}
        result = format_memory(memory)
        assert "Some content" in result
        assert "0.00" in result  # Default confidence

    def test_format_unknown_type(self):
        """Test formatting memory with unknown type"""
        memory = {"type": "nonexistent_type", "content": "Test"}
        result = format_memory(memory)
        assert "unknown" in result
        assert "Test" in result

    def test_format_unknown_tier(self):
        """Test formatting memory with unknown tier"""
        memory = {"tier": 99, "content": "Test"}
        result = format_memory(memory)
        assert "unknown" in result


class TestLoadJsonFile:
    """Tests for load_json_file function"""

    def test_load_valid_json(self, tmp_path):
        """Test loading valid JSON file"""
        json_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        json_file.write_text(json.dumps(test_data))

        result = load_json_file(str(json_file))
        assert result == test_data

    def test_load_nonexistent_file(self):
        """Test loading nonexistent file returns empty dict"""
        result = load_json_file("/nonexistent/file.json")
        assert result == {}

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON returns empty dict"""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")

        result = load_json_file(str(json_file))
        assert result == {}


class TestSaveJsonFile:
    """Tests for save_json_file function"""

    def test_save_valid_json(self, tmp_path):
        """Test saving valid JSON data"""
        json_file = tmp_path / "output.json"
        test_data = {"key": "value", "list": [1, 2, 3]}

        save_json_file(str(json_file), test_data)

        assert json_file.exists()
        with open(json_file) as f:
            loaded = json.load(f)
        assert loaded == test_data

    def test_save_with_unicode(self, tmp_path):
        """Test saving JSON with Unicode characters"""
        json_file = tmp_path / "unicode.json"
        test_data = {"chinese": "中文", "emoji": "😀"}

        save_json_file(str(json_file), test_data)

        with open(json_file, encoding="utf-8") as f:
            content = f.read()
        assert "中文" in content
        assert "😀" in content

    def test_save_to_invalid_path(self):
        """Test saving to invalid path does not raise"""
        save_json_file("/invalid/path/file.json", {"data": "test"})


class TestConstants:
    """Tests for module constants"""

    def test_memory_types_defined(self):
        """Test that MEMORY_TYPES is properly defined"""
        assert isinstance(MEMORY_TYPES, dict)
        assert len(MEMORY_TYPES) > 0
        assert "user_preference" in MEMORY_TYPES
        assert "fact_declaration" in MEMORY_TYPES

    def test_memory_tiers_defined(self):
        """Test that MEMORY_TIERS is properly defined"""
        assert isinstance(MEMORY_TIERS, dict)
        assert len(MEMORY_TIERS) == 4
        assert 1 in MEMORY_TIERS
        assert 4 in MEMORY_TIERS
