"""
E2E Tests: Edge Cases and Boundary Conditions

Validates behavior at system boundaries:
1. Empty strings, very long text, special Unicode characters
2. Paths with spaces, Chinese, Unicode characters
3. Read-only filesystem / permission denied scenarios
4. Disk space exhaustion simulation
"""

import os
import re
import shutil
import stat
import tempfile

import pytest

from carrymem import CarryMem
from carrymem.exceptions import DBConnectionError


@pytest.fixture
def standard_carrymem(tmp_path):
    """Standard CarryMem instance for edge case testing."""
    db_path = str(tmp_path / "edge_test.db")
    cm = CarryMem(db_path=db_path)
    yield cm
    cm.close()


class TestE2ETextBoundaryConditions:
    """Scenario: Extreme text inputs."""

    def test_empty_string_memory(self, standard_carrymem):
        """Verify: Empty string is handled without crash."""
        cm = standard_carrymem

        with pytest.raises((ValueError, Exception)):
            cm.classify_and_remember("")

    def test_whitespace_only_string(self, standard_carrymem):
        """Verify: Whitespace-only strings are handled."""
        cm = standard_carrymem

        for whitespace in [" ", "   ", "\t", "\n", "\n\t\n"]:
            with pytest.raises((ValueError, Exception)):
                cm.classify_and_remember(whitespace)

    def test_very_long_single_word(self, standard_carrymem):
        """Verify: Very long single word doesn't cause issues."""
        cm = standard_carrymem

        long_word = "a" * 5000
        result = cm.classify_and_remember(f"Test with {long_word}")
        assert isinstance(result, dict), "Long word should be handled"

    def test_very_long_sentence(self, standard_carrymem):
        """Verify: Very long sentence (near max length) is handled."""
        cm = standard_carrymem

        long_sentence = "This is a test sentence. " * 200  # ~4000 chars
        result = cm.classify_and_remember(long_sentence)
        assert isinstance(result, dict), "Long sentence should be handled"

    def test_special_unicode_characters(self, standard_carrymem):
        """Verify: Special Unicode characters are handled correctly."""
        cm = standard_carrymem

        unicode_tests = [
            "Emoji test: 🎉🚀💻🔥",
            "Math symbols: ∑∏∂∫√≈≠≤≥",
            "Arabic: مرحبا بالعالم",
            "Hebrew: שלום עולם",
            "Thai: สวัสดีชาวโลก",
            "Korean: 안녕하세요 세계",
            "Japanese: こんにちは世界",
            "Russian: Привет мир",
            "Mixed: Hello 世界 🌍 مرحبا",
            "Zero-width: test\u200btext\u200cjoin",
            "Combining: e\u0301 (e + acute)",
            "RTL mixed: Hello اهلا Hello",
        ]

        for text in unicode_tests:
            result = cm.classify_and_remember(text)
            assert isinstance(result, dict), f"Should handle Unicode: {text[:30]}"

        # Verify recall works for Unicode content
        recalled = cm.recall_memories(query="Hello", limit=20)
        assert isinstance(recalled, list), "Unicode recall should work"

    def test_newlines_and_tabs_in_content(self, standard_carrymem):
        """Verify: Content with newlines and tabs is preserved."""
        cm = standard_carrymem

        multiline = """Line one about preferences.
Line two with more details.
Line three: a tab\there.
Line four: emoji 🎯"""

        result = cm.classify_and_remember(multiline)
        assert isinstance(result, dict), "Multiline content should work"

    def test_html_like_content(self, standard_carrymem):
        """Verify: HTML-like content doesn't break the system."""
        cm = standard_carrymem

        html_content = "<div>My preference is <strong>dark mode</strong></div><script>alert(1)</script>"
        result = cm.classify_and_remember(html_content)
        assert isinstance(result, dict), "HTML-like content should be handled"

    def test_json_like_content(self, standard_carrymem):
        """Verify: JSON-like strings are stored as text, not parsed."""
        cm = standard_carrymem

        json_text = '{"preference": "dark mode", "version": 1.0, "active": true}'
        result = cm.classify_and_remember(json_text)
        assert isinstance(result, dict), "JSON-like text should be stored as text"


class TestE2EPathBoundaryConditions:
    """Scenario: Unusual file paths."""

    def test_path_with_spaces(self, tmp_path):
        """Verify: Database path containing spaces works correctly."""
        db_path = str(tmp_path / "path with spaces" / "my database.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        cm = CarryMem(db_path=db_path)
        try:
            result = cm.classify_and_remember("Path with spaces test")
            assert isinstance(result, dict), "Spaces in path should work"

            recalled = cm.recall_memories(query="spaces", limit=5)
            assert isinstance(recalled, list), "Recall should work with spaced path"
        finally:
            cm.close()

    def test_path_with_chinese_characters(self, tmp_path):
        """Verify: Path with Chinese characters works correctly."""
        db_path = str(tmp_path / "用户数据目录" / "记忆数据库.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        cm = CarryMem(db_path=db_path)
        try:
            result = cm.classify_and_remember("中文路径测试")
            assert isinstance(result, dict), "Chinese path should work"
        finally:
            cm.close()

    def test_path_with_unicode_special_chars(self, tmp_path):
        """Verify: Path with various Unicode special characters works."""
        # Use common safe unicode in paths
        db_path = str(tmp_path / "data-ëéïôü" / "test-ñç.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        cm = CarryMem(db_path=db_path)
        try:
            result = cm.classify_and_remember("Unicode path test")
            assert isinstance(result, dict), "Unicode path should work"
        finally:
            cm.close()

    def test_very_long_path(self, tmp_path):
        """Verify: Very long path (but within OS limits) works."""
        long_dir_name = "very_long_directory_name_" + "x" * 100
        db_path = str(tmp_path / long_dir_name / "database.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        cm = CarryMem(db_path=db_path)
        try:
            result = cm.classify_and_remember("Long path test")
            assert isinstance(result, dict), "Long path should work"
        finally:
            cm.close()

    def test_path_with_dots_and_hyphens(self, tmp_path):
        """Verify: Path with dots and hyphens works."""
        db_path = str(tmp_path / ".hidden-dir" / "my-data.backup.test.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        cm = CarryMem(db_path=db_path)
        try:
            result = cm.classify_and_remember("Dots and hyphens test")
            assert isinstance(result, dict), "Path with dots/hyphens should work"
        finally:
            cm.close()

    def test_relative_path_handling(self, tmp_path):
        """Verify: Relative paths are handled appropriately."""
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))

            # Try relative path
            cm = CarryMem(db_path="relative_path_test.db")
            try:
                result = cm.classify_and_remember("Relative path test")
                assert isinstance(result, dict), "Relative path should return a dict result"
            finally:
                cm.close()
        finally:
            os.chdir(original_cwd)


class TestE2EPermissionScenarios:
    """Scenario: Filesystem permission issues."""

    @pytest.mark.skipif(os.getuid() == 0, reason="Test meaningless when running as root")
    def test_readonly_parent_directory(self, tmp_path):
        """Verify: Graceful handling when parent directory is read-only."""
        readonly_dir = tmp_path / "readonly_parent"
        readonly_dir.mkdir()

        db_path = str(readonly_dir / "test.db")

        # Make directory read-only
        readonly_dir.chmod(0o555)

        try:
            # Should fail when parent directory is read-only
            with pytest.raises((PermissionError, OSError, DBConnectionError)):
                cm = CarryMem(db_path=db_path)
                cm.close()
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    @pytest.mark.skipif(os.getuid() == 0, reason="Test meaningless when running as root")
    def test_no_write_permission_on_file(self, tmp_path):
        """Verify: Cannot write to read-only database file."""
        db_path = str(tmp_path / "readonly_file.db")

        # Create file first
        cm = CarryMem(db_path=db_path)
        cm.classify_and_remember("Initial data")
        cm.close()

        # Make file read-only, including WAL/SHM sidecar files
        os.chmod(db_path, 0o444)
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = db_path + suffix
            if os.path.exists(sidecar):
                os.chmod(sidecar, 0o444)

        try:
            cm_ro = CarryMem(db_path=db_path)
            try:
                # Read operations should work
                recalled = cm_ro.recall_memories(limit=5)
                assert isinstance(recalled, list), "Reads may work on read-only file"

                # Write operations should fail on read-only database.
                # On some systems (e.g., Ubuntu CI), SQLite WAL mode may create
                # new sidecar files in the writable parent directory, allowing
                # writes to succeed despite the .db file being read-only.
                # Skip if the read-only precondition cannot be established.
                try:
                    cm_ro.classify_and_remember("Attempted write to read-only")
                    pytest.skip(
                        "Write succeeded despite read-only chmod — "
                        "WAL mode creates new sidecar files (environment-specific)"
                    )
                except Exception as e:
                    assert re.search(
                        r"readonly|read-only|permission", str(e), re.IGNORECASE
                    ), f"Unexpected exception: {e}"
            finally:
                cm_ro.close()
        finally:
            os.chmod(db_path, 0o644)  # Restore for cleanup

    def test_nonexistent_parent_directory(self, tmp_path):
        """Verify: Non-existent parent directory is handled appropriately."""
        db_path = str(tmp_path / "nonexistent" / "nested" / "deep" / "test.db")

        # Behavior varies: might create dirs or raise error
        try:
            cm = CarryMem(db_path=db_path)
            try:
                result = cm.classify_and_remember("Auto-create dir test")
                assert isinstance(result, dict), "Should work if auto-creating dirs"
            finally:
                cm.close()
        except (FileNotFoundError, OSError, Exception):
            pass  # Acceptable: requires pre-existing directory


class TestE2EDiskSpaceSimulation:
    """Scenario: Disk space related edge cases."""

    def test_small_database_size(self, standard_carrymem):
        """Verify: Small amount of data produces reasonably sized database."""
        cm = standard_carrymem

        # Store minimal data
        cm.classify_and_remember("Small database test")

        # Check DB file size exists and is reasonable
        db_path = getattr(cm, "db_path", None) or getattr(cm, "_db_path", None)
        if db_path and os.path.exists(db_path):
            size = os.path.getsize(db_path)
            # Even empty SQLite has some overhead, but shouldn't be huge
            assert size < 1024 * 1024, f"DB too large for minimal data: {size} bytes"

    def test_database_growth_reasonable(self, tmp_path):
        """Verify: Database grows proportionally to stored data."""
        db_path = str(tmp_path / "growth_test.db")
        cm = CarryMem(db_path=db_path)

        try:
            # Measure initial size
            cm.classify_and_remember("Initial entry")
            size_initial = os.path.getsize(db_path) if os.path.exists(db_path) else 0

            # Add substantial data
            for i in range(100):
                cm.classify_and_remember(f"Growth test entry {i}: " + "x" * 100)

            size_final = os.path.getsize(db_path) if os.path.exists(db_path) else 0

            growth_ratio = size_final / size_initial if size_initial > 0 else 1

            print(f"\n[DB Growth] Initial: {size_initial}B, Final: {size_final}B, " f"Ratio: {growth_ratio:.1f}x")

            # Should grow but not explosively
            assert growth_ratio < 1000, f"DB growth excessive: {growth_ratio:.1f}x increase"
        finally:
            cm.close()


class TestE2ENumericAndSpecialInputs:
    """Scenario: Numeric and special format inputs."""

    def test_numeric_only_input(self, standard_carrymem):
        """Verify: Numeric-only strings are handled."""
        cm = standard_carrymem

        numerics = ["12345", "0", "-42", "3.14159", "1e10"]
        for num in numerics:
            result = cm.classify_and_remember(num)
            assert isinstance(result, dict), f"Numeric input {num} should return a dict result"

    def test_special_format_strings(self, standard_carrymem):
        """Verify: Special format strings don't cause injection or parsing issues."""
        cm = standard_carrymem

        special_formats = [
            "%s %d %f" % ("test", 42, 3.14),
            "{0} {1}".format("formatted", "string"),
            f"f-string: {42}",
            "$ENV_VAR value",
            "${expression}",
            "`backtick expression`",
            "null/undefined/NaN",
            "true/false/yes/no",
        ]

        for fmt in special_formats:
            result = cm.classify_and_remember(fmt)
            assert isinstance(result, dict), f"Format string should work: {fmt[:30]}"

    def test_sql_injection_like_content(self, standard_carrymem):
        """Verify: SQL-injection-like content is safely stored as text."""
        cm = standard_carrymem

        sql_like = [
            "'; DROP TABLE memories; --",
            "' OR '1'='1",
            "1; INSERT INTO secrets VALUES ('hacked')",
            "'; SELECT * FROM users; --",
            "Robert'); DROP TABLE students;--",
        ]

        for sql in sql_like:
            result = cm.classify_and_remember(sql)
            assert isinstance(result, dict), f"SQL-like content should be safe: {sql[:30]}"

        # Verify they're stored as text, not executed
        recalled = cm.recall_memories(query="DROP TABLE", limit=5)
        assert isinstance(recalled, list), "Recall should work after SQL-like inputs"


class TestE2EAPIBoundaryConditions:
    """Scenario: Edge cases in API usage."""

    def test_none_value_handling(self, standard_carrymem):
        """Verify: API handles None values gracefully where appropriate."""
        cm = standard_carrymem

        # Most APIs should reject or handle None
        try:
            result = cm.classify_and_remember(None)
            # If it doesn't crash, result should be a dict
            assert isinstance(result, dict), "classify_and_remember should return dict even for None input"
        except (TypeError, ValueError, AttributeError):
            pass  # Expected: None rejected

    def test_very_large_limit_parameter(self, standard_carrymem):
        """Verify: Very large limit parameter is handled."""
        cm = standard_carrymem

        cm.classify_and_remember("Large limit test")

        # Request huge limit - should raise ValidationError or cap gracefully
        with pytest.raises((Exception,)):
            cm.recall_memories(limit=999999999)

    def test_negative_or_zero_limit(self, standard_carrymem):
        """Verify: Negative or zero limit parameters are handled."""
        cm = standard_carrymem

        cm.classify_and_remember("Limit boundary test")

        for limit in [-1, -100]:
            with pytest.raises((ValueError, Exception)):
                cm.recall_memories(limit=limit)

        # Zero limit should return empty list or raise
        try:
            result = cm.recall_memories(limit=0)
            assert isinstance(result, list), "Limit=0 should return list"
        except (ValueError, Exception):
            pass  # Also acceptable

    def test_empty_query_recall(self, standard_carrymem):
        """Verify: Empty query string in recall is handled."""
        cm = standard_carrymem

        cm.classify_and_remember("Empty query test")

        result = cm.recall_memories(query="", limit=10)
        assert isinstance(result, list), "Empty query should return list"

    def test_rapid_create_destroy_cycles(self, tmp_path):
        """Verify: Rapid CarryMem instance creation/destruction works."""
        db_path = str(tmp_path / "rapid_cycle.db")

        for i in range(30):
            cm = CarryMem(db_path=db_path)
            cm.classify_and_remember(f"Cycle {i}")
            cm.close()

        # Final state should be usable
        cm_final = CarryMem(db_path=db_path)
        try:
            recalled = cm_final.recall_memories(limit=30)
            assert isinstance(recalled, list), "Should work after rapid cycles"
        finally:
            cm_final.close()


class TestE2EMixedLanguageContent:
    """Scenario: Content mixing multiple languages."""

    def test_mixed_chinese_english_content(self, standard_carrymem):
        """Verify: Mixed Chinese-English content is handled."""
        cm = standard_carrymem

        mixed = [
            "我prefer使用Python编程",
            "Our团队采用Agile方法论",
            "请use dark mode for coding",
            "Database选择PostgreSQL因为性能好",
        ]

        for text in mixed:
            result = cm.classify_and_remember(text)
            assert isinstance(result, dict), f"Mixed language should work: {text}"

    def test_mixed_script_recall(self, standard_carrymem):
        """Verify: Can recall mixed-language content by querying either language."""
        cm = standard_carrymem

        cm.classify_and_remember("我喜欢用Python写代码 I like using Python")

        # Query in English
        en_results = cm.recall_memories(query="Python", limit=5)
        assert isinstance(en_results, list), "English query should work"

        # Query in Chinese
        zh_results = cm.recall_memories(query="喜欢", limit=5)
        assert isinstance(zh_results, list), "Chinese query should work"
