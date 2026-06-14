"""Tests for enhanced input validators (P1-7).

Covers:
- validate_unicode_safe: control character & bidi override detection
- safe_text_match: ReDoS protection (timeout, truncation, dangerous patterns)
- detect_sql_injection: SQL injection pattern detection (audit-only)
- validate_path_safe: path traversal & symlink safety
"""

import os
import tempfile

import pytest

from carrymem.exceptions import ValidationError
from carrymem.utils.validators import (
    detect_sql_injection,
    safe_text_match,
    validate_path_safe,
    validate_unicode_safe,
)

# ══════════════════════════════════════════════════════════════════
#  validate_unicode_safe
# ══════════════════════════════════════════════════════════════════


class TestValidateUnicodeSafe:
    """Tests for Unicode safety validation."""

    def test_normal_text_passes(self):
        result = validate_unicode_safe("Hello, 世界! 🌍")
        assert result == "Hello, 世界! 🌍"

    def test_empty_string_passes(self):
        assert validate_unicode_safe("") == ""

    def test_tab_allowed(self):
        assert validate_unicode_safe("a\tb") == "a\tb"

    def test_newline_allowed(self):
        assert validate_unicode_safe("line1\nline2") == "line1\nline2"

    def test_carriage_return_allowed(self):
        assert validate_unicode_safe("line1\r\nline2") == "line1\r\nline2"

    def test_null_byte_rejected(self):
        with pytest.raises(ValidationError, match="U\\+0000"):
            validate_unicode_safe("bad\x00text")

    def test_c0_control_chars_rejected(self):
        # U+0001 (SOH)
        with pytest.raises(ValidationError, match="control character"):
            validate_unicode_safe("test\x01evil")

    def test_c1_control_chars_rejected(self):
        # U+0080-U+009F range
        with pytest.raises(ValidationError, match="control character"):
            validate_unicode_safe("test\x80evil")

    def test_del_char_rejected(self):
        # U+007F (DEL)
        with pytest.raises(ValidationError, match="control character"):
            validate_unicode_safe("test\x7fevil")

    def test_bidi_ltr_embedding_rejected(self):
        # U+202A LEFT-TO-RIGHT EMBEDDING
        with pytest.raises(ValidationError, match="bidirectional override"):
            validate_unicode_safe("safe\u202atext")

    def test_bidi_rtl_override_rejected(self):
        # U+202E RIGHT-TO-LEFT OVERRIDE
        with pytest.raises(ValidationError, match="bidirectional override"):
            validate_unicode_safe("safe\u202etext")

    def test_bidi_isolate_rejected(self):
        # U+2066 LEFT-TO-RIGHT ISOLATE
        with pytest.raises(ValidationError, match="bidirectional override"):
            validate_unicode_safe("safe\u2066text")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="expects a string"):
            validate_unicode_safe(123)  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════
#  safe_text_match
# ══════════════════════════════════════════════════════════════════


class TestSafeTextMatch:
    """Tests for ReDoS-safe regex matching."""

    def test_simple_match_found(self):
        m = safe_text_match(r"hello", "say hello world")
        assert m is not None
        assert m.group() == "hello"

    def test_no_match_returns_none(self):
        assert safe_text_match(r"xyz", "hello world") is None

    def test_invalid_pattern_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Invalid regex pattern"):
            safe_text_match(r"(unclosed", "text")

    def test_dangerous_nested_quantifier_warns(self):
        # Should log a warning for dangerous pattern but still execute successfully
        import unittest.mock as mock

        with mock.patch("carrymem.utils.validators.logger") as mock_logger:
            safe_text_match(r"(a+)+", "aaa")
            mock_logger.warning.assert_called_once()
            assert "ReDoS" in mock_logger.warning.call_args[0][0]

    def test_long_text_truncated(self):
        # Should handle very long text without error (truncates internally)
        import unittest.mock as mock

        with mock.patch("carrymem.utils.validators.logger") as mock_logger:
            long_text = "x" * 2_000_000
            result = safe_text_match(r"x+", long_text)
            # Pattern should still match within truncated text
            assert result is not None
            mock_logger.warning.assert_called()
            warning_msg = str(mock_logger.warning.call_args[0][0])
            assert "truncated" in warning_msg.lower()

    def test_empty_text_returns_none(self):
        assert safe_text_match(r".+", "") is None

    def test_dotall_flag_works(self):
        m = safe_text_match(r"hello.*world", "hello\nworld")
        assert m is not None

    def test_complex_valid_pattern(self):
        # Email-like pattern — DOTALL is the default flag in safe_text_match
        m = safe_text_match(r"[a-z]+@[a-z]+\.[a-z]{2,}", "email: test@example.com")
        assert m is not None
        assert m.group() == "test@example.com"


# ══════════════════════════════════════════════════════════════════
#  detect_sql_injection
# ══════════════════════════════════════════════════════════════════


class TestDetectSqlInjection:
    """Tests for SQL injection pattern detection (audit-only)."""

    def test_normal_text_clean(self):
        assert detect_sql_injection("I like apples") is False

    def test_union_select_detected(self):
        assert detect_sql_injection("' UNION SELECT * FROM users --") is True

    def test_or_1_equals_1_detected(self):
        assert detect_sql_injection("' OR 1=1 --") is True

    def test_drop_table_detected(self):
        assert detect_sql_injection("; DROP TABLE users;") is True

    def test_comment_injection_detected(self):
        assert detect_sql_injection("admin'--") is True

    def test_sleep_based_detection(self):
        assert detect_sql_injection("'; SLEEP(10)--") is True

    def test_empty_string_returns_false(self):
        assert detect_sql_injection("") is False

    def test_whitespace_only_returns_false(self):
        assert detect_sql_injection("   ") is False

    def test_non_string_returns_false(self):
        assert detect_sql_injection(123) is False  # type: ignore[arg-type]

    def test_benign_sql_word_not_detected(self):
        # The word "select" alone without SQL structure should not trigger
        assert detect_sql_injection("Please select an option") is False


# ══════════════════════════════════════════════════════════════════
#  validate_path_safe
# ══════════════════════════════════════════════════════════════════


class TestValidatePathSafe:
    """Tests for path traversal / symlink safety validation."""

    def test_simple_relative_path(self):
        result = validate_path_safe("some/file.txt")
        assert result.is_absolute()

    def test_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_path_safe(tmp)
            assert str(result) == os.path.realpath(tmp)

    def test_path_traversal_rejected(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_path_safe("../../etc/passwd")

    def test_null_byte_rejected(self):
        with pytest.raises(ValidationError, match="null byte"):
            validate_path_safe("/etc/passwd\x00.txt")

    def test_empty_path_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_path_safe("")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="expects a string"):
            validate_path_safe(123)  # type: ignore[arg-type]

    def test_tilde_expansion(self):
        # ~/something should expand
        result = validate_path_safe("~/test_file")
        assert str(result).startswith(os.path.expanduser("~"))

    def test_current_dir_dots_ok(self):
        # ./file should be fine (not ..)
        result = validate_path_safe("./myfile.txt")
        assert result.is_absolute()

    def test_mixed_traversal_rejected(self):
        with pytest.raises(ValidationError, match="Path traversal"):
            validate_path_safe("valid/../../etc/passwd")
