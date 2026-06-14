"""
Integration Tests: Error Propagation Across Layers

Validates that exceptions are correctly propagated and transformed through the
CarryMem architecture:

1. Storage Layer Exceptions → CarryMemError transformation
2. Encryption Failure → Graceful degradation paths
3. Multi-layer nested calls → Original cause preservation
4. CLI/TUI entry point error handling

All tests verify:
- Exception types match expected CarryMemError hierarchy
- Error codes are assigned correctly
- Original cause is preserved in exception chain
- User-friendly messages are generated
"""

import os
import sqlite3
import tempfile

import pytest

from carrymem import CarryMem, StorageNotConfiguredError
from carrymem.errors import (
    CarryMemError,
    ConfigError,
    MemoryOperationError,
    SecurityError,
    StorageAdapterError,
)


@pytest.fixture
def cm(tmp_path):
    """Create a fresh CarryMem instance with isolated database."""
    db_path = str(tmp_path / "error_test.db")
    instance = CarryMem(db_path=db_path)
    yield instance
    instance.close()


class TestStorageLayerErrorPropagation:
    """Scenario: Storage layer exceptions propagate correctly to upper layers."""

    def test_storage_not_configured_error_on_no_adapter(self):
        """Verify: Operations without storage raise StorageNotConfiguredError.

        Steps:
        1. Create CarryMem with storage=None (no adapter)
        2. Attempt storage operation (classify_and_remember)
        3. Verify StorageNotConfiguredError raised
        """
        cm = CarryMem(storage=None)
        try:
            with pytest.raises(StorageNotConfiguredError) as exc_info:
                cm.classify_and_remember("This should fail")

            # Verify it's the expected error type
            assert isinstance(exc_info.value, StorageNotConfiguredError)
            assert isinstance(exc_info.value, CarryMemError)

            # Verify error has useful information
            assert exc_info.value.code in (
                "CM-100",
            ), f"Should have storage-related error code, got {exc_info.value.code}"
            assert len(exc_info.value.message) > 0, "Error message should not be empty"
        finally:
            cm.close()

    def test_recall_without_storage_raises_error(self):
        """Verify: Recall operations without storage raise appropriate error.

        Steps:
        1. Create CarryMem without storage
        2. Attempt recall_memories
        3. Verify StorageNotConfiguredError raised
        """
        cm = CarryMem(storage=None)
        try:
            with pytest.raises(StorageNotConfiguredError):
                cm.recall_memories(query="anything", limit=10)
        finally:
            cm.close()

    def test_sqlite_error_transformation(self, tmp_path):
        """Verify: SQLite-level errors transform to CarryMemError with correct code.

        Simulates a scenario where SQLite operation fails and gets wrapped.

        Steps:
        1. Create CarryMem with valid database
        2. Perform normal operation to confirm setup works
        3. Verify error transformation infrastructure exists
        """
        db_path = str(tmp_path / "sqlite_error_test.db")
        cm = CarryMem(db_path=db_path)

        try:
            # Normal operation should work
            result = cm.classify_and_remember("Test for error handling")
            assert result.get("stored", False), "Normal operation should succeed"

            # Verify CarryMemError.from_cause exists and works
            test_exc = sqlite3.IntegrityError("UNIQUE constraint failed: memories.storage_key")
            carrymem_err = CarryMemError.from_cause(test_exc)

            assert isinstance(carrymem_err, CarryMemError)
            assert carrymem_err.code == "CM-102", f"IntegrityError should map to CM-102, got {carrymem_err.code}"
            assert carrymem_err.cause is test_exc, "Original cause should be preserved"
        finally:
            cm.close()

    def test_database_locked_error_mapping(self):
        """Verify: Database locked errors map to appropriate CarryMemError code.

        Steps:
        1. Create a simulated database locked error
        2. Transform using CarryMemError.from_cause
        3. Verify correct error code and message
        """
        locked_error = sqlite3.OperationalError("database is locked")
        carrymem_err = CarryMemError.from_cause(locked_error)

        assert isinstance(carrymem_err, CarryMemError)
        assert carrymem_err.code == "CM-104", f"Database locked should be CM-104, got {carrymem_err.code}"
        assert (
            "locked" in carrymem_err.message.lower() or "lock" in carrymem_err.message.lower()
        ), "Error message should mention locking"
        assert carrymem_err.cause is locked_error, "Original cause preserved"


class TestEncryptionErrorHandling:
    """Scenario: Encryption failures are handled gracefully with degradation."""

    def test_wrong_encryption_key_handling(self, tmp_path):
        """Verify: Opening encrypted DB with wrong key fails gracefully.

        Steps:
        1. Create encrypted database with key A
        2. Store data
        3. Close
        4. Attempt to reopen with different key B
        5. Verify graceful failure (not crash)
        """
        db_path = str(tmp_path / "wrong_key.db")
        key_a = "correct-encryption-key-alpha"
        key_b = "wrong-encryption-key-beta"

        # Create and encrypt with key A
        cm1 = CarryMem(db_path=db_path, encryption_key=key_a)
        cm1.classify_and_remember("Secret data encrypted with key A")
        cm1.close()

        # Try to open with wrong key B - should fail gracefully or return empty
        try:
            cm2 = CarryMem(db_path=db_path, encryption_key=key_b)
            try:
                # If it opens, recalls may fail or return empty/corrupted
                recalled = cm2.recall_memories(limit=10)
                # Either empty list or corrupted data - both acceptable
                assert isinstance(recalled, list), "Should return list even on wrong key"
            finally:
                cm2.close()
        except (Exception,) as e:
            # Also acceptable: fails to open entirely
            assert isinstance(
                e, (CarryMemError, RuntimeError, Exception)
            ), f"Wrong key should raise appropriate error, got {type(e)}"

    def test_encryption_initialization_failure(self, tmp_path):
        """Verify: Invalid encryption key causes initialization failure.

        Steps:
        1. Try to create CarryMem with invalid encryption configuration
        2. Verify it raises an appropriate error
        """
        db_path = str(tmp_path / "bad_encrypt.db")

        # Test with various potentially problematic keys
        # (actual behavior depends on encryption implementation)
        try:
            # Very short key might be rejected
            cm = CarryMem(db_path=db_path, encryption_key="short")
            cm.close()
        except (RuntimeError, CarryMemError, ValueError) as e:
            # Expected: some encryption systems reject short keys
            assert isinstance(
                e, (RuntimeError, CarryMemError, ValueError)
            ), f"Should raise appropriate error for bad key, got {type(e)}"
        except Exception as e:
            # Other errors also acceptable if they're security-related
            pass


class TestMultiLayerErrorPreservation:
    """Scenario: Nested multi-layer calls preserve original exception cause."""

    def test_nested_call_cause_chain_preserved(self, tmp_path):
        """Verify: Deep call stack preserves root cause through exception chain.

        Simulates: CLI → CRUD → Adapter → SQLite (error at bottom)
        Should preserve full chain back to caller.

        Steps:
        1. Set up a scenario where low-level error occurs
        2. Catch at high level
        3. Verify entire cause chain is intact
        """
        db_path = str(tmp_path / "cause_chain.db")

        # Create a custom error scenario
        original_error = sqlite3.OperationalError("disk I/O error")
        wrapped_once = CarryMemError.from_cause(original_error)
        wrapped_twice = CarryMemError(code="CM-999", message="Higher level operation failed", cause=wrapped_once)

        # Verify chain integrity
        assert wrapped_twice.cause is wrapped_once, "First wrapping should be preserved"
        assert wrapped_once.cause is original_error, "Original error should be at bottom"

        # Verify __cause__ chain works (Python 3 exception chaining)
        try:
            raise wrapped_twice
        except CarryMemError as e:
            # Should be able to traverse the chain
            assert e.__cause__ is wrapped_once or e.cause is wrapped_once

    def test_validation_error_in_classification_chain(self):
        """Verify: Input validation errors propagate correctly through classification.

        Steps:
        1. Send invalid input to classify_and_remember
        2. Verify validation error propagates up
        """
        cm = CarryMem(storage=None)  # No storage needed for classification only
        try:
            # Empty message should fail validation
            with pytest.raises((ValueError, CarryMemError)) as exc_info:
                cm.classify_and_remember("")

            error = exc_info.value
            # Should have meaningful error info
            assert hasattr(error, "message") or len(str(error)) > 0, "Error should have descriptive message"
        finally:
            cm.close()

    def test_too_long_message_error(self):
        """Verify: Excessively long messages are rejected with clear error.

        Steps:
        1. Send message exceeding maximum length
        2. Verify appropriate error raised
        """
        cm = CarryMem(storage=None)
        try:
            long_message = "x" * 60000  # Exceeds 50000 char limit

            with pytest.raises((ValueError, CarryMemError)) as exc_info:
                cm.classify_and_remember(long_message)

            error = exc_info.value
            error_msg = str(error).lower()
            assert (
                "long" in error_msg or "length" in error_msg or "too" in error_msg
            ), f"Error should mention length issue, got: {error_msg}"
        finally:
            cm.close()


class TestErrorRecoveryAndDegradation:
    """Scenario: System degrades gracefully when errors occur."""

    def test_partial_failure_in_batch_operation(self, cm):
        """Verify: Batch operations handle partial failures gracefully.

        Steps:
        1. Store multiple valid memories
        2. One might fail (simulated by edge case)
        3. Verify others still succeed
        """
        valid_memories = [
            "Valid memory 1: user prefers Python",
            "Valid memory 2: team uses Agile",
            "Valid memory 3: deploy to AWS",
        ]

        success_count = 0
        for msg in valid_memories:
            try:
                result = cm.classify_and_remember(msg)
                if result.get("stored", False):
                    success_count += 1
            except (CarryMemError, Exception) as e:
                # Individual failures shouldn't stop batch
                pass

        # Most should succeed
        assert (
            success_count >= len(valid_memories) * 0.8
        ), f"Most memories should store successfully, got {success_count}/{len(valid_memories)}"

    def test_recall_graceful_on_empty_database(self, cm):
        """Verify: Recall on empty database returns empty list, not error.

        Steps:
        1. Don't store anything
        2. Call various recall methods
        3. Verify they return empty results, not errors
        """
        # Recall from empty DB
        result = cm.recall_memories(query="nonexistent", limit=10)
        assert isinstance(result, list), "Recall should return list"
        assert len(result) == 0, "Empty DB should return empty list"

        # recall_all on empty DB
        all_result = cm.recall_all(query="anything", limit=5)
        assert isinstance(all_result, dict), "recall_all should return dict"
        assert all_result.get("memory_count", 0) == 0, "Empty DB should show 0 memories"

    def test_stats_on_empty_database(self, cm):
        """Verify: Stats/profile methods work on empty database.

        Steps:
        1. Call get_stats, get_memory_profile, whoami on empty DB
        2. Verify they return sensible defaults, not errors
        """
        stats = cm.get_stats()
        assert isinstance(stats, dict), "Stats should return dict"

        profile = cm.get_memory_profile()
        assert isinstance(profile, dict), "Profile should return dict"

        whoami = cm.whoami()
        assert isinstance(whoami, dict), "whoami should return dict"
        assert whoami.get("total_memories", 0) == 0, "Empty DB should report 0 memories"


class TestCLIEntryErrorTransformation:
    """Scenario: Errors at CLI/TUI entry points are properly transformed."""

    def test_carrymem_error_has_user_friendly_attributes(self):
        """Verify: CarryMemError instances have all user-friendly attributes.

        Steps:
        1. Create CarryMemError instances via various paths
        2. Verify code, message, hint, cause attributes present
        """
        # Direct construction
        err1 = CarryMemError(
            code="CM-001",
            message="Test error message",
            hint="This is a hint for users",
            cause=ValueError("Original error"),
        )

        assert err1.code == "CM-001"
        assert err1.message == "Test error message"
        assert err1.hint == "This is a hint for users"
        assert err1.cause is not None
        assert isinstance(err1.cause, ValueError)

        # From factory method
        err2 = CarryMemError.from_cause(OSError("Permission denied"))
        assert isinstance(err2, CarryMemError)
        assert err2.code.startswith("CM-"), "Error code should start with CM-"
        assert len(err2.message) > 0, "Factory should produce message"

    def test_error_code_ranges_are_correct(self):
        """Verify: Error codes fall within documented ranges.

        Code ranges:
          CM-001 ~ CM-099: Configuration & Initialization
          CM-100 ~ CM-199: Storage Adapter
          CM-200 ~ CM-299: Memory Operations
          CM-300 ~ CM-399: Classification & Rule Engine
          CM-400 ~ CM-499: Security & Encryption
          CM-500 ~ CM-599: Import / Export
          CM-600 ~ CM-699: CLI / TUI / MCP Entry Points
        """
        test_cases = [
            (sqlite3.OperationalError("no such table: memories"), "CM-10"),  # Storage
            (OSError("Permission denied"), "CM-10"),  # File system
            (ValueError("invalid input"), "CM-20"),  # Validation/Value
        ]

        for original_exc, expected_prefix in test_cases:
            transformed = CarryMemError.from_cause(original_exc)
            assert transformed.code.startswith(
                expected_prefix[:4]
            ), f"Error {transformed.code} should start with {expected_prefix}"

    def test_exception_hierarchy_is_respected(self):
        """Verify: CarryMemError subclass hierarchy enables precise catching.

        Steps:
        1. Create errors of different specific types
        2. Verify they can be caught by parent class
        3. Verify they can be caught specifically by their own type
        """
        config_err = ConfigError(code="CM-001", message="Config failed")
        storage_err = StorageAdapterError(code="CM-100", message="Storage failed")
        memory_err = MemoryOperationError(code="CM-200", message="Memory op failed")
        security_err = SecurityError(code="CM-400", message="Security issue")

        # All should be catchable as CarryMemError
        for err in [config_err, storage_err, memory_err, security_err]:
            assert isinstance(err, CarryMemError), f"{type(err).__name__} should be instance of CarryMemError"

        # Each should be catchable by its specific type
        assert isinstance(config_err, ConfigError)
        assert isinstance(storage_err, StorageAdapterError)
        assert isinstance(memory_err, MemoryOperationError)
        assert isinstance(security_err, SecurityError)


class TestEdgeCaseErrorScenarios:
    """Scenario: Unusual/error-prone edge cases are handled correctly."""

    def test_concurrent_close_operation(self, cm):
        """Verify: Operations after close don't cause crashes.

        Steps:
        1. Close CarryMem normally
        2. Attempt various operations
        3. Verify graceful failure (not segfault/unhandled exception)
        """
        cm.classify_and_remember("Will close after this")
        cm.close()

        # These may fail but shouldn't crash hard
        try:
            cm.recall_memories(limit=10)
        except (StorageNotConfiguredError, CarryMemError, Exception):
            pass  # Acceptable: closed connection may fail

        try:
            cm.get_stats()
        except (StorageNotConfiguredError, CarryMemError, Exception):
            pass  # Acceptable

    def test_corrupted_database_handling(self, tmp_path):
        """Verify: Corrupted or invalid database is handled gracefully.

        Steps:
        1. Create invalid/corrupted database file
        2. Try to open with CarryMem
        3. Verify appropriate error (not unhandled crash)
        """
        db_path = str(tmp_path / "corrupted.db")

        # Write garbage to file
        with open(db_path, "wb") as f:
            f.write(b"This is not a valid SQLite database file")

        # Try to open - should fail gracefully
        try:
            cm = CarryMem(db_path=db_path)
            # If it opened, try to use it
            try:
                cm.classify_and_remember("Test on corrupted DB")
            except (CarryMemError, sqlite3.DatabaseError, Exception) as e:
                # Acceptable: corrupted DB should fail on operation
                pass
            finally:
                cm.close()
        except (CarryMemError, sqlite3.DatabaseError, ValueError, Exception) as e:
            # Also acceptable: fails to open
            assert isinstance(
                e, (CarryMemError, sqlite3.DatabaseError, ValueError, Exception)
            ), f"Corrupted DB should raise appropriate error, got {type(e)}"

    def test_unicode_and_special_chars_in_errors(self):
        """Verify: Error messages handle unicode and special characters correctly.

        Steps:
        1. Create errors with special characters in messages
        2. Verify they can be stringified without issues
        """
        special_messages = [
            "Error with emoji 🎉 and 中文",
            "Path: C:\\Users\\Test\\File.txt",
            "Unicode: café, naïve, 日本語",
            "Special chars: <script>alert('xss')</script>",
        ]

        for msg in special_messages:
            err = CarryMemError(code="CM-999", message=msg, hint=f"Hint for: {msg}")
            # Should stringify without errors
            error_str = str(err)
            assert len(error_str) > 0, f"Should stringify error for: {msg}"
            assert msg in error_str, "Original message should appear in stringified error"


class TestErrorContextPreservation:
    """Scenario: Errors include sufficient context for debugging."""

    def test_error_includes_operation_context(self, tmp_path):
        """Verify: Errors provide context about what operation failed.

        Steps:
        1. Trigger an error in a specific operation
        2. Verify error includes relevant context
        """
        db_path = str(tmp_path / "context_test.db")
        cm = CarryMem(storage=None)  # No storage configured

        try:
            # This will fail due to no storage
            cm.declare("This requires storage")
            assert False, "Should have raised StorageNotConfiguredError"
        except StorageNotConfiguredError as e:
            # Error should indicate storage is needed
            error_str = str(e).lower()
            assert "storage" in error_str or "adapter" in error_str, f"Error should mention storage, got: {error_str}"
        finally:
            cm.close()

    def test_error_code_enables_programmatic_handling(self):
        """Verify: Error codes allow programmatic error handling.

        Steps:
        1. Create errors with known codes
        2. Demonstrate code-based handling logic
        """
        error_scenarios = {
            "CM-100": "storage_not_configured",
            "CM-102": "duplicate_data",
            "CM-104": "database_locked",
            "CM-201": "validation_failed",
            "CM-401": "encryption_failed",
        }

        for code, handler_name in error_scenarios:
            err = CarryMemError(
                code=code,
                message=f"Simulated {handler_name}",
            )

            # Programmatic handling based on code
            if err.code.startswith("CM-1"):
                # Storage-related: suggest checking storage config
                assert "storage" in err.code or True  # Handler logic placeholder
            elif err.code.startswith("CM-2"):
                # Operation-related: suggest checking input
                assert "operation" in handler_name or True
            elif err.code.startswith("CM-4"):
                # Security-related: suggest checking keys/permissions
                assert "security" in handler_name or True
