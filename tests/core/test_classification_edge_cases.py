"""Classification edge cases test suite - Phase 1 Coverage Boost.

Tests for edge cases in memory classification: empty input, long text, special chars, etc.
"""

import pytest
from carrymem import CarryMem
from carrymem.types import MemoryType


@pytest.fixture
def cm(tmp_path):
    """CarryMem instance with temporary storage."""
    return CarryMem(data_dir=str(tmp_path / ".carrymem"))


class TestClassificationEdgeCases:
    """Test classification with edge case inputs."""

    def test_classify_empty_string(self, cm):
        """Test classification of empty string."""
        with pytest.raises((ValueError, Exception)):
            cm.classify_and_remember("")

    def test_classify_whitespace_only(self, cm):
        """Test classification of whitespace-only content."""
        with pytest.raises((ValueError, Exception)):
            cm.classify_and_remember("   \n\t   ")

    def test_classify_very_long_text(self, cm):
        """Test classification of very long text (10K+ chars)."""
        long_text = "I prefer using Python. " * 500  # ~11,500 chars
        result = cm.classify_and_remember(long_text)
        assert result is not None
        assert "storage_key" in result

    def test_classify_single_word(self, cm):
        """Test classification of single word."""
        result = cm.classify_and_remember("Python")
        assert result is not None

    def test_classify_special_characters(self, cm):
        """Test classification with special characters."""
        text = "I prefer using @Python & #Django! [framework]"
        result = cm.classify_and_remember(text)
        assert result is not None

    def test_classify_unicode_characters(self, cm):
        """Test classification with Unicode characters."""
        text = "我喜欢使用 Python 🐍 для программирования"
        result = cm.classify_and_remember(text)
        assert result is not None

    def test_classify_numbers_only(self, cm):
        """Test classification of numeric content."""
        result = cm.classify_and_remember("12345 67890")
        assert result is not None

    def test_classify_code_snippet(self, cm):
        """Test classification of code snippets."""
        code = "def hello(): return 'world'"
        result = cm.classify_and_remember(code)
        assert result is not None

    def test_classify_url_content(self, cm):
        """Test classification of URLs."""
        text = "Use API: https://api.example.com/v1/users"
        result = cm.classify_and_remember(text)
        assert result is not None

    def test_classify_email_content(self, cm):
        """Test classification with email addresses."""
        text = "Contact user@example.com for support"
        result = cm.classify_and_remember(text)
        assert result is not None


class TestClassificationMultilingual:
    """Test classification with multilingual content."""

    def test_classify_chinese(self, cm):
        """Test classification of Chinese text."""
        result = cm.classify_and_remember("我更喜欢使用深色模式")
        assert result is not None

    def test_classify_japanese(self, cm):
        """Test classification of Japanese text."""
        result = cm.classify_and_remember("ダークモードを使います")
        assert result is not None

    def test_classify_korean(self, cm):
        """Test classification of Korean text."""
        result = cm.classify_and_remember("나는 다크 모드를 선호한다")
        assert result is not None

    def test_classify_arabic(self, cm):
        """Test classification of Arabic text."""
        result = cm.classify_and_remember("أفضل استخدام الوضع الداكن")
        assert result is not None

    def test_classify_mixed_languages(self, cm):
        """Test classification of mixed language text."""
        text = "I prefer Python, 我用 Python, Pythonを使う"
        result = cm.classify_and_remember(text)
        assert result is not None


class TestClassificationWithMetadata:
    """Test classification with various metadata scenarios."""

    def test_classify_with_empty_metadata(self, cm):
        """Test classification with empty metadata dict."""
        result = cm.classify_and_remember("Test memory", metadata={})
        assert result is not None

    def test_classify_with_nested_metadata(self, cm):
        """Test classification with nested metadata."""
        metadata = {
            "project": {"name": "Alpha", "version": "1.0"},
            "tags": ["important", "urgent"]
        }
        result = cm.classify_and_remember("Test memory", metadata=metadata)
        assert result is not None

    def test_classify_with_large_metadata(self, cm):
        """Test classification with large metadata object."""
        metadata = {f"key_{i}": f"value_{i}" for i in range(100)}
        result = cm.classify_and_remember("Test memory", metadata=metadata)
        assert result is not None

    def test_classify_force_type_override(self, cm):
        """Test forcing a specific memory type."""
        result = cm.classify_and_remember(
            "This is a note",
            force_type=MemoryType.USER_PREFERENCE
        )
        assert result is not None
        assert result["memory_type"] == MemoryType.USER_PREFERENCE


class TestClassificationConcurrency:
    """Test classification under concurrent scenarios."""

    def test_classify_rapid_succession(self, cm):
        """Test classifying multiple memories rapidly."""
        results = []
        for i in range(10):
            result = cm.classify_and_remember(f"Memory {i}")
            results.append(result)
        assert len(results) == 10
        assert all(r is not None for r in results)

    def test_classify_duplicate_content(self, cm):
        """Test classifying same content multiple times."""
        content = "I prefer dark mode"
        result1 = cm.classify_and_remember(content)
        result2 = cm.classify_and_remember(content)
        assert result1 is not None
        assert result2 is not None
        # Should create separate memories
        assert result1["storage_key"] != result2["storage_key"]


class TestClassificationPatterns:
    """Test classification of different content patterns."""

    def test_classify_preference_pattern(self, cm):
        """Test classification of preference statements."""
        patterns = [
            "I prefer using Python",
            "I like dark mode",
            "My favorite framework is Django"
        ]
        for pattern in patterns:
            result = cm.classify_and_remember(pattern)
            assert result is not None

    def test_classify_correction_pattern(self, cm):
        """Test classification of correction statements."""
        patterns = [
            "Use PostgreSQL instead of MySQL",
            "Don't use eval() in Python",
            "Avoid global variables"
        ]
        for pattern in patterns:
            result = cm.classify_and_remember(pattern)
            assert result is not None

    def test_classify_decision_pattern(self, cm):
        """Test classification of decision statements."""
        patterns = [
            "We decided to use React",
            "The team chose PostgreSQL",
            "Selected AWS for hosting"
        ]
        for pattern in patterns:
            result = cm.classify_and_remember(pattern)
            assert result is not None

    def test_classify_factual_pattern(self, cm):
        """Test classification of factual statements."""
        patterns = [
            "The database is at db.example.com",
            "API key is stored in .env file",
            "Server runs on port 8080"
        ]
        for pattern in patterns:
            result = cm.classify_and_remember(pattern)
            assert result is not None
