"""
Tests for utils.validators module.

Validates all validator functions including:
- validate_message, validate_context, validate_language
- validate_namespace, validate_limit, validate_filters
- validate_memory_type, validate_confidence, validate_tier
- validate_storage_key, validate_query, validate_namespaces
"""

import pytest

from carrymem.utils.validators import (
    validate_message,
    validate_context,
    validate_language,
    validate_namespace,
    validate_limit,
    validate_filters,
    validate_memory_type,
    validate_confidence,
    validate_tier,
    validate_storage_key,
    validate_query,
    validate_namespaces,
)
from carrymem.exceptions import ValidationError


class TestValidateMessage:
    def test_valid_message(self):
        validate_message("Hello world")

    def test_empty_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_message("")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_message(123)

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_message("x" * 10001)

    def test_custom_max_length(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_message("x" * 11, max_length=10)


class TestValidateContext:
    def test_none_allowed(self):
        validate_context(None)

    def test_valid_dict(self):
        validate_context({"key": "value"})

    def test_non_dict_rejected(self):
        with pytest.raises(ValidationError, match="must be a dictionary"):
            validate_context("not a dict")

    def test_too_large_rejected(self):
        with pytest.raises(ValidationError, match="too large"):
            validate_context({"key": "x" * 50001})


class TestValidateLanguage:
    def test_none_allowed(self):
        validate_language(None)

    def test_valid_code(self):
        validate_language("en")

    def test_valid_locale(self):
        validate_language("en-US")

    def test_valid_japanese(self):
        validate_language("ja")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_language(123)

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_language("abcdefghijk")

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError, match="Invalid language code"):
            validate_language("en!@")


class TestValidateNamespace:
    def test_valid_namespace(self):
        validate_namespace("my-namespace_123")

    def test_empty_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_namespace("")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_namespace(123)

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_namespace("x" * 129)

    def test_invalid_chars_rejected(self):
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_namespace("ns/slash")


class TestValidateLimit:
    def test_valid_limit(self):
        validate_limit(10)

    def test_zero_allowed(self):
        validate_limit(0)

    def test_non_int_rejected(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_limit("10")

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_limit(-1)

    def test_too_large_rejected(self):
        with pytest.raises(ValidationError, match="too large"):
            validate_limit(200000)

    def test_custom_max(self):
        validate_limit(50, max_limit=100)


class TestValidateFilters:
    def test_none_allowed(self):
        validate_filters(None)

    def test_valid_filters(self):
        validate_filters({"type": "user_preference"})

    def test_non_dict_rejected(self):
        with pytest.raises(ValidationError, match="must be a dictionary"):
            validate_filters("not a dict")

    def test_invalid_keys_rejected(self):
        with pytest.raises(ValidationError, match="Invalid filter keys"):
            validate_filters({"evil_key": "value"})

    def test_custom_allowed_keys(self):
        validate_filters({"custom_key": "value"}, allowed_keys={"custom_key"})


class TestValidateMemoryType:
    def test_valid_type(self):
        validate_memory_type("user_preference", {"user_preference", "correction"})

    def test_empty_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_memory_type("", {"user_preference"})

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_memory_type(123, {"123"})

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError, match="Invalid memory type"):
            validate_memory_type("invalid", {"user_preference"})


class TestValidateConfidence:
    def test_valid_confidence(self):
        validate_confidence(0.5)

    def test_zero(self):
        validate_confidence(0.0)

    def test_one(self):
        validate_confidence(1.0)

    def test_non_number_rejected(self):
        with pytest.raises(ValidationError, match="must be a number"):
            validate_confidence("high")

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validate_confidence(-0.1)

    def test_over_one_rejected(self):
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            validate_confidence(1.5)


class TestValidateTier:
    def test_valid_tiers(self):
        for t in [1, 2, 3, 4]:
            validate_tier(t)

    def test_non_int_rejected(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_tier(1.5)

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="must be 1, 2, 3, or 4"):
            validate_tier(0)

    def test_five_rejected(self):
        with pytest.raises(ValidationError, match="must be 1, 2, 3, or 4"):
            validate_tier(5)


class TestValidateStorageKey:
    def test_valid_key(self):
        validate_storage_key("mem_abc123")

    def test_empty_rejected(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_storage_key("")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_storage_key(123)

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_storage_key("x" * 257)


class TestValidateQuery:
    def test_none_allowed(self):
        validate_query(None)

    def test_valid_query(self):
        validate_query("search terms")

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError, match="must be a string"):
            validate_query(123)

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_query("x" * 10001)


class TestValidateNamespaces:
    def test_none_allowed(self):
        validate_namespaces(None)

    def test_valid_list(self):
        validate_namespaces(["ns1", "ns2"])

    def test_non_list_rejected(self):
        with pytest.raises(ValidationError, match="must be a list"):
            validate_namespaces("not a list")

    def test_too_many_rejected(self):
        with pytest.raises(ValidationError, match="Too many"):
            validate_namespaces([f"ns{i}" for i in range(101)])

    def test_invalid_namespace_in_list(self):
        with pytest.raises(ValidationError):
            validate_namespaces(["valid", "invalid/slash"])
