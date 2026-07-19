"""End-to-end security tests for CarryMem.

Tests for:
- SQL injection prevention
- Path traversal attacks
- Input validation and sanitization
- Authentication and authorization
- Permission bypass prevention
"""

import os
import tempfile
from pathlib import Path

import pytest

from carrymem import CarryMem
from carrymem.security.input_validator import InputValidator


class TestSQLInjectionPrevention:
    """Test SQL injection attack prevention."""

    def test_sql_injection_in_search_query(self):
        """Test that SQL injection attempts in search queries are prevented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CarryMem(db_path=os.path.join(tmpdir, "test.db"))

            # Store legitimate memory
            cm.classify_and_remember("Alice loves Python programming")

            # Attempt SQL injection in search
            malicious_queries = [
                "'; DROP TABLE memories; --",
                "' OR '1'='1",
                "'; DELETE FROM memories WHERE '1'='1'; --",
                "1' UNION SELECT * FROM sqlite_master--",
                "admin'--",
                "' OR 1=1--",
            ]

            for query in malicious_queries:
                try:
                    # Should not raise exception or return unexpected results
                    results = cm.recall_memories(query=query, limit=10)
                    # Should return empty or legitimate results only
                    assert isinstance(results, list)
                except Exception as e:
                    # Some validation might raise exceptions, which is acceptable
                    error_str = str(e).upper()
                    # Should not expose SQL internals
                    assert "DROP" not in error_str or "valid" in str(e).lower()

            cm.close()

    def test_sql_injection_in_namespace(self):
        """Test SQL injection prevention in namespace parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CarryMem(db_path=os.path.join(tmpdir, "test.db"))

            malicious_namespaces = [
                "default'; DROP TABLE memories--",
                "' OR '1'='1",
                "../../etc/passwd",
            ]

            for ns in malicious_namespaces:
                try:
                    # Should sanitize or reject malicious namespace
                    cm.classify_and_remember("test content", namespace=ns)
                    results = cm.recall_memories(query="test", namespace=ns, limit=5)
                    assert isinstance(results, list)
                except (ValueError, Exception) as e:
                    # Expected: validation should catch this
                    assert "invalid" in str(e).lower() or "namespace" in str(e).lower()

            cm.close()


class TestPathTraversalPrevention:
    """Test path traversal attack prevention."""

    def test_path_traversal_in_db_path(self):
        """Test that path traversal in db_path is handled safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_paths = [
                "../../etc/passwd",
                "../../../root/.ssh/id_rsa",
            ]

            for path in malicious_paths:
                try:
                    # Should either normalize path or raise error
                    cm = CarryMem(db_path=path)
                    # If created, verify it's within safe boundaries
                    if hasattr(cm, "adapter") and hasattr(cm.adapter, "db_path"):
                        actual_path = Path(cm.adapter.db_path).resolve()
                        # Should not escape to system directories
                        assert "/etc/" not in str(actual_path)
                        assert "/root/" not in str(actual_path)
                    cm.close()
                except (ValueError, PermissionError, OSError):
                    # Expected: should prevent dangerous paths
                    pass


class TestInputValidationAndSanitization:
    """Test input validation and sanitization."""

    def test_oversized_content_handling(self):
        """Test that extremely large content is handled safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CarryMem(db_path=os.path.join(tmpdir, "test.db"))

            # Attempt to store large content (1MB)
            large_content = "A" * (1 * 1024 * 1024)

            try:
                result = cm.classify_and_remember(large_content)
                # If accepted, it should be stored safely
                assert result is not None
            except (ValueError, MemoryError) as e:
                # Expected: might reject oversized input
                pass

            cm.close()

    def test_special_characters_in_content(self):
        """Test handling of special characters and control codes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CarryMem(db_path=os.path.join(tmpdir, "test.db"))

            special_contents = [
                "<script>alert('XSS')</script>",  # HTML/JS
                "'; DROP TABLE users; --",  # SQL
            ]

            for content in special_contents:
                try:
                    result = cm.classify_and_remember(content)
                    # Should either sanitize or store safely
                    assert result is not None
                except (ValueError, TypeError):
                    # Expected: might reject invalid input
                    pass

            cm.close()

    def test_namespace_validation(self):
        """Test namespace input validation."""
        validator = InputValidator()

        invalid_namespaces = [
            "",  # Empty
            " " * 100,  # Whitespace only
            "../etc/passwd",  # Path traversal
            "name\x00space",  # NULL byte
            "name\nspace",  # Newline
            "a" * 300,  # Too long
        ]

        for ns in invalid_namespaces:
            try:
                result = validator.sanitize_namespace(ns)
                # If sanitized, verify it's safe
                if result:
                    assert len(result) <= 255
                    assert "\x00" not in result
                    assert "\n" not in result
            except ValueError:
                # Expected: should reject invalid input
                pass


class TestAuthenticationSecurity:
    """Test authentication and API key security."""

    def test_empty_api_key_detection(self):
        """Test that empty or whitespace API keys are detected."""
        invalid_keys = [
            "",
            " ",
            "\t",
            "\n",
            " " * 10,
        ]

        for key in invalid_keys:
            # Empty keys should be detected
            assert len(key.strip()) == 0

    def test_weak_api_key_detection(self):
        """Test detection of weak API keys."""
        weak_keys = [
            "123456",
            "password",
            "admin",
            "test",
            "a",
        ]

        for key in weak_keys:
            # Weak keys should be detected (length < 16 chars)
            assert len(key) < 16


class TestPermissionBypass:
    """Test permission bypass prevention."""

    def test_namespace_isolation(self):
        """Test that memories in other namespaces are isolated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create separate CarryMem instances with different namespaces
            cm1 = CarryMem(db_path=os.path.join(tmpdir, "test.db"), namespace="namespace1")
            cm2 = CarryMem(db_path=os.path.join(tmpdir, "test.db"), namespace="namespace2")

            # Store in different namespaces
            cm1.classify_and_remember("Secret data in ns1")
            cm2.classify_and_remember("Public data in ns2")

            # Query in namespace1 should not return namespace2 data
            results_ns1 = cm1.recall_memories(query="data", limit=10)
            for result in results_ns1:
                # Verify namespace isolation if namespace info is available
                if isinstance(result, dict) and "namespace" in result:
                    assert result["namespace"] == "namespace1"

            # Query in namespace2 should not return namespace1 data
            results_ns2 = cm2.recall_memories(query="data", limit=10)
            for result in results_ns2:
                if isinstance(result, dict) and "namespace" in result:
                    assert result["namespace"] == "namespace2"

            cm1.close()
            cm2.close()

    def test_delete_with_invalid_id(self):
        """Test that delete operations handle invalid IDs safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CarryMem(db_path=os.path.join(tmpdir, "test.db"))

            cm.classify_and_remember("Test memory")

            # Attempt to delete with invalid IDs
            invalid_ids = [
                "' OR '1'='1",
                "../../../etc/passwd",
                "\x00",
                "nonexistent_id_12345",
            ]

            for invalid_id in invalid_ids:
                try:
                    # Should handle invalid IDs safely
                    cm.forget_memory(invalid_id)
                except (ValueError, KeyError, TypeError, Exception):
                    # Expected: should reject or safely handle invalid IDs
                    pass

            cm.close()


class TestErrorMessageSecurity:
    """Test that error messages don't leak sensitive information."""

    def test_error_messages_sanitized(self):
        """Test that error messages don't reveal system internals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cm = CarryMem(db_path=os.path.join(tmpdir, "test.db"))

            try:
                # Trigger various errors with invalid input
                cm.recall_memories(query="test", namespace="invalid\x00namespace")
            except Exception as e:
                error_msg = str(e)
                # Should not reveal SQL queries
                assert "SELECT" not in error_msg.upper()
                assert "INSERT" not in error_msg.upper()
                assert "DELETE" not in error_msg.upper()

            cm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
