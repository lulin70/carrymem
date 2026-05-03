"""Security and input validation tests for CarryMem."""

import os
import tempfile
import pytest

from memory_classification_engine import CarryMem
from memory_classification_engine.utils.validators import (
    validate_message, validate_limit, validate_namespace,
    validate_storage_key, validate_query, ValidationError,
)


class TestInputValidation:
    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            validate_message("")

    def test_non_string_message_rejected(self):
        with pytest.raises(ValidationError):
            validate_message(123)

    def test_oversized_message_rejected(self):
        with pytest.raises(ValidationError):
            validate_message("x" * 10001)

    def test_negative_limit_rejected(self):
        with pytest.raises(ValidationError):
            validate_limit(-1)

    def test_oversized_limit_rejected(self):
        with pytest.raises(ValidationError):
            validate_limit(200000)

    def test_empty_namespace_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("")

    def test_invalid_namespace_chars_rejected(self):
        with pytest.raises(ValidationError):
            validate_namespace("ns/../../../etc")

    def test_empty_storage_key_rejected(self):
        with pytest.raises(ValidationError):
            validate_storage_key("")

    def test_oversized_query_rejected(self):
        with pytest.raises(ValidationError):
            validate_query("x" * 10001)

    def test_none_query_allowed(self):
        validate_query(None)


class TestPathTraversal:
    def test_export_path_traversal_blocked(self):
        with CarryMem() as cm:
            with pytest.raises(ValueError, match="Path traversal"):
                cm.export_memories(output_path="../../tmp/evil.json")

    def test_import_path_traversal_blocked(self):
        with CarryMem() as cm:
            with pytest.raises(ValueError, match="Path traversal"):
                cm.import_memories(input_path="../../etc/passwd")


class TestContextManager:
    def test_with_statement_works(self):
        with CarryMem() as cm:
            result = cm.classify_and_remember("I prefer dark mode")
            assert result is not None

    def test_close_method_exists(self):
        cm = CarryMem()
        cm.close()


class TestMCPHandlerSafety:
    def test_safe_error_no_leak(self):
        from memory_classification_engine.integration.layer2_mcp.handlers import _safe_error
        e = RuntimeError("database path /home/user/.carrymem/memories.db not found")
        result = _safe_error(e)
        assert result == "internal_error"
        assert "/home/user" not in result
        assert "database" not in result

    def test_safe_error_known_type(self):
        from memory_classification_engine.integration.layer2_mcp.handlers import _safe_error
        from memory_classification_engine.carrymem import StorageNotConfiguredError
        e = StorageNotConfiguredError()
        result = _safe_error(e)
        assert result == "storage_not_configured"

    def test_clamp_limit(self):
        from memory_classification_engine.integration.layer2_mcp.handlers import _clamp
        assert _clamp(999999, 1, 1000) == 1000
        assert _clamp(-5, 1, 100) == 1
        assert _clamp(50, 1, 100) == 50


class TestExceptionSanitization:
    def test_exceptions_file_not_corrupted(self):
        from memory_classification_engine.exceptions import DatabaseError, DBConnectionError, QueryError
        assert issubclass(DatabaseError, Exception)
        assert issubclass(DBConnectionError, Exception)
        assert issubclass(QueryError, Exception)
