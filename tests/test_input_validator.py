"""
Tests for security.input_validator module.

Validates InputValidator class including:
- SQL injection detection
- XSS detection
- Path traversal detection
- Content/query/namespace/path validation
- Memory type, confidence, limit, filters validation
- Convenience functions
- Strict vs non-strict mode
"""

import os
import tempfile
from pathlib import Path

import pytest

from carrymem.exceptions import ValidationError
from carrymem.security.input_validator import (
    InputValidator,
    get_validator,
    validate_confidence,
    validate_content,
    validate_filters,
    validate_limit,
    validate_memory_type,
    validate_namespace,
    validate_path,
    validate_query,
)


@pytest.fixture
def validator():
    return InputValidator(strict_mode=True)


@pytest.fixture
def loose_validator():
    return InputValidator(strict_mode=False)


class TestSQLInjectionDetection:
    def test_drop_table_detected(self, validator):
        with pytest.raises(ValidationError, match="SQL injection"):
            validator.validate_content("DROP TABLE users;")

    def test_union_select_detected(self, validator):
        with pytest.raises(ValidationError, match="SQL injection"):
            validator.validate_content("1 UNION SELECT * FROM users")

    def test_one_equals_one_in_sql_context_detected(self, validator):
        with pytest.raises(ValidationError, match="SQL injection"):
            validator.validate_content("' OR 1=1 --")

    def test_one_equals_one_in_normal_text_passes(self, validator):
        result = validator.validate_content("one equals one is a tautology")
        assert "tautology" in result

    def test_sql_injection_in_query(self, validator):
        with pytest.raises(ValidationError, match="SQL injection"):
            validator.validate_query("'; DROP TABLE memories; --")

    def test_safe_content_passes(self, validator):
        result = validator.validate_content("I prefer dark mode for editors")
        assert "dark mode" in result

    def test_safe_query_passes(self, validator):
        result = validator.validate_query("dark mode preferences")
        assert "dark mode" in result


class TestXSSDetection:
    def test_script_tag_detected(self, validator):
        with pytest.raises(ValidationError, match="XSS"):
            validator.validate_content("<script>alert('xss')</script>")

    def test_javascript_protocol_detected(self, validator):
        with pytest.raises(ValidationError, match="XSS"):
            validator.validate_content("javascript:void(0)")

    def test_onclick_detected(self, validator):
        with pytest.raises(ValidationError, match="XSS"):
            validator.validate_content('<img onclick="evil()">')

    def test_iframe_detected(self, validator):
        with pytest.raises(ValidationError, match="XSS"):
            validator.validate_content('<iframe src="evil.com">')

    def test_xss_not_checked_in_loose_mode(self, loose_validator):
        result = loose_validator.validate_content("<script>alert('xss')</script>")
        assert isinstance(result, str)


class TestPathTraversalDetection:
    def test_parent_dir_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("../../etc/passwd")

    def test_double_dot_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("/etc/shadow")

    def test_home_tilde_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("~/secret")

    def test_proc_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("/proc/self/environ")

    def test_safe_path_passes(self, validator):
        home = str(Path.home())
        result = validator.validate_path(os.path.join(home, "test.txt"))
        assert isinstance(result, Path)

    # ── P1-2: URL-encoded traversal variants ──────────────────────

    def test_url_encoded_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("%2e%2e%2fetc%2fpasswd")

    def test_url_encoded_backslash_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("%2e%2e%5cwindows")

    def test_double_url_encoded_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("%252e%252e%252fetc")

    def test_mixed_encoded_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("..%2fetc%2fpasswd")

    def test_mixed_encoded_backslash_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("..%5cwindows")

    def test_unicode_fullwidth_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("\uff0e\uff0e\uff0fetc")

    def test_html_entity_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("&#46;&#46;&#47;etc")

    def test_html_hex_entity_traversal_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("&#x2e;&#x2e;&#x2f;etc")

    def test_rtl_override_detected(self, validator):
        with pytest.raises(ValidationError, match="path traversal"):
            validator.validate_path("\u202e../../etc")

    # ── P1-2: Symlink rejection ──────────────────────────────────

    def test_symlink_rejected(self, validator, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("data")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        with pytest.raises(ValidationError, match="Symlink"):
            validator.validate_path(str(link))


class TestContentValidation:
    def test_non_string_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be a string"):
            validator.validate_content(123)

    def test_too_long_rejected(self, validator):
        with pytest.raises(ValidationError, match="maximum length"):
            validator.validate_content("x" * (validator.MAX_CONTENT_LENGTH + 1))

    def test_empty_rejected(self, validator):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validator.validate_content("   ")

    def test_valid_content_passes(self, validator):
        result = validator.validate_content("Normal content here")
        assert isinstance(result, str)

    def test_content_sanitized_null_bytes(self, validator):
        result = validator.validate_content("Hello\x00World")
        assert "\x00" not in result

    def test_content_whitespace_preserved(self, validator):
        result = validator.validate_content("Hello   World")
        assert "Hello   World" in result

    def test_content_leading_trailing_whitespace_stripped(self, validator):
        result = validator.validate_content("  Hello World  ")
        assert result == "Hello World"

    def test_html_not_escaped_in_strict_mode(self, validator):
        result = validator.validate_content("<b>bold</b>")
        assert "<b>" in result
        assert "bold" in result

    def test_html_not_escaped_in_loose_mode(self, loose_validator):
        result = loose_validator.validate_content("<b>bold</b>")
        assert "<b>" in result


class TestQueryValidation:
    def test_non_string_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be a string"):
            validator.validate_query(42)

    def test_too_long_rejected(self, validator):
        with pytest.raises(ValidationError, match="maximum length"):
            validator.validate_query("x" * 1001)

    def test_empty_query_returns_empty(self, validator):
        result = validator.validate_query("   ")
        assert result == ""

    def test_valid_query_passes(self, validator):
        result = validator.validate_query("search terms")
        assert isinstance(result, str)


class TestNamespaceValidation:
    def test_non_string_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be a string"):
            validator.validate_namespace(123)

    def test_too_long_rejected(self, validator):
        with pytest.raises(ValidationError, match="maximum length"):
            validator.validate_namespace("x" * 101)

    def test_invalid_chars_rejected(self, validator):
        with pytest.raises(ValidationError, match="letters, numbers"):
            validator.validate_namespace("ns/../../../etc")

    def test_valid_namespace_passes(self, validator):
        result = validator.validate_namespace("my-namespace_123")
        assert result == "my-namespace_123"

    def test_namespace_lowered(self, validator):
        result = validator.validate_namespace("MyNameSpace")
        assert result == "mynamespace"


class TestMemoryTypeValidation:
    def test_valid_types_pass(self, validator):
        for t in [
            "user_preference",
            "correction",
            "fact_declaration",
            "decision",
            "relationship",
            "task_pattern",
            "sentiment_marker",
        ]:
            result = validator.validate_memory_type(t)
            assert result == t

    def test_invalid_type_rejected(self, validator):
        with pytest.raises(ValidationError, match="Invalid memory type"):
            validator.validate_memory_type("invalid_type")


class TestConfidenceValidation:
    def test_valid_confidence_passes(self, validator):
        assert validator.validate_confidence(0.5) == 0.5

    def test_confidence_zero(self, validator):
        assert validator.validate_confidence(0.0) == 0.0

    def test_confidence_one(self, validator):
        assert validator.validate_confidence(1.0) == 1.0

    def test_non_number_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be a number"):
            validator.validate_confidence("high")

    def test_negative_rejected(self, validator):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validator.validate_confidence(-0.1)

    def test_over_one_rejected(self, validator):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validator.validate_confidence(1.5)

    def test_int_confidence_converted(self, validator):
        result = validator.validate_confidence(1)
        assert isinstance(result, float)
        assert result == 1.0


class TestLimitValidation:
    def test_valid_limit(self, validator):
        assert validator.validate_limit(10) == 10

    def test_non_int_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be an integer"):
            validator.validate_limit("10")

    def test_zero_rejected(self, validator):
        with pytest.raises(ValidationError, match="at least 1"):
            validator.validate_limit(0)

    def test_negative_rejected(self, validator):
        with pytest.raises(ValidationError, match="at least 1"):
            validator.validate_limit(-5)

    def test_over_1000_rejected(self, validator):
        with pytest.raises(ValidationError, match="cannot exceed 1000"):
            validator.validate_limit(1001)


class TestFiltersValidation:
    def test_valid_filters(self, validator):
        result = validator.validate_filters(
            {
                "type": "user_preference",
                "namespace": "test",
                "min_confidence": 0.5,
                "max_age_days": 30,
            }
        )
        assert result["type"] == "user_preference"
        assert result["namespace"] == "test"
        assert result["min_confidence"] == 0.5
        assert result["max_age_days"] == 30

    def test_non_dict_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be a dictionary"):
            validator.validate_filters("invalid")

    def test_invalid_key_rejected(self, validator):
        with pytest.raises(ValidationError, match="Invalid filter key"):
            validator.validate_filters({"evil_key": "value"})

    def test_invalid_type_in_filter(self, validator):
        with pytest.raises(ValidationError, match="Invalid memory type"):
            validator.validate_filters({"type": "bad_type"})

    def test_invalid_max_age_days(self, validator):
        with pytest.raises(ValidationError, match="non-negative integer"):
            validator.validate_filters({"max_age_days": -1})

    def test_max_age_days_string_rejected(self, validator):
        with pytest.raises(ValidationError, match="non-negative integer"):
            validator.validate_filters({"max_age_days": "30"})


class TestPathValidation:
    def test_non_string_rejected(self, validator):
        with pytest.raises(ValidationError, match="must be a string"):
            validator.validate_path(123)

    def test_too_long_rejected(self, validator):
        with pytest.raises(ValidationError, match="maximum length"):
            validator.validate_path("x" * 501)

    def test_must_exist_flag(self, validator):
        with pytest.raises(ValidationError, match="does not exist"):
            validator.validate_path("/nonexistent/path/file.txt", must_exist=True)

    def test_valid_temp_path(self, validator):
        home = str(Path.home())
        result = validator.validate_path(home)
        assert isinstance(result, Path)

    def test_path_outside_allowed_in_strict(self, validator):
        # /opt/nonexistent_test_path is not a symlink on Linux or macOS,
        # does not match path traversal patterns, and is outside home/temp dirs.
        # /usr/bin/python was previously used but is a symlink on Linux CI,
        # triggering the symlink check before the location check.
        with pytest.raises(ValidationError, match="outside allowed"):
            validator.validate_path("/opt/nonexistent_test_path")


class TestConvenienceFunctions:
    def test_validate_content_func(self):
        result = validate_content("Hello world")
        assert isinstance(result, str)

    def test_validate_query_func(self):
        result = validate_query("search")
        assert isinstance(result, str)

    def test_validate_namespace_func(self):
        result = validate_namespace("test-ns")
        assert result == "test-ns"

    def test_validate_memory_type_func(self):
        result = validate_memory_type("user_preference")
        assert result == "user_preference"

    def test_validate_confidence_func(self):
        result = validate_confidence(0.5)
        assert result == 0.5

    def test_validate_limit_func(self):
        result = validate_limit(10)
        assert result == 10

    def test_validate_filters_func(self):
        result = validate_filters({"type": "user_preference"})
        assert result["type"] == "user_preference"

    def test_get_validator_returns_instance(self):
        v = get_validator()
        assert isinstance(v, InputValidator)

    def test_get_validator_caches(self):
        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2


class TestCommandInjection:
    def test_command_substitution_detected(self, validator):
        from carrymem.security.input_validator import InputValidator

        v = InputValidator(strict_mode=False)
        assert v._contains_command_injection("$(whoami)")

    def test_backtick_detected(self, validator):
        from carrymem.security.input_validator import InputValidator

        v = InputValidator(strict_mode=False)
        assert v._contains_command_injection("`rm -rf /`")

    def test_safe_content_no_command_injection(self, validator):
        from carrymem.security.input_validator import InputValidator

        v = InputValidator(strict_mode=False)
        assert not v._contains_command_injection("Normal text content")
