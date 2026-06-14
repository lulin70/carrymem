"""Tests for CarryMem Error Code System (P0-6).

Covers:
  - All error codes are unique
  - from_cause correctly maps low-level exceptions
  - Chinese and English messages are complete
  - CarryMemError base class behavior
  - Error message template registry
"""

import os
import sqlite3
import tempfile

import pytest

from carrymem.error_messages import (
    ERROR_MESSAGES,
    ErrorTemplate,
    all_error_codes,
    get_hint,
    get_message,
)
from carrymem.errors import (
    CarryMemError,
    ClassificationError,
    CLIEntryError,
    ConfigError,
    ImportExportError,
    MemoryOperationError,
    SecurityError,
    StorageAdapterError,
)

# ════════════════════════════════════════════════════════════════════
# 1. Error Code Uniqueness
# ════════════════════════════════════════════════════════════════════


class TestErrorCodeUniqueness:
    """Verify all registered error codes are unique and well-formed."""

    def test_all_codes_unique(self):
        codes = list(ERROR_MESSAGES.keys())
        assert len(codes) == len(set(codes)), "Duplicate error codes found"

    def test_code_format(self):
        for code in ERROR_MESSAGES:
            assert code.startswith("CM-"), f"Code {code} should start with 'CM-'"
            parts = code.split("-")
            assert len(parts) == 2, f"Code {code} should be CM-NNN format"
            assert parts[1].isdigit(), f"Code {code} numeric part must be digits"

    def test_code_range_coverage(self):
        ranges = {
            "config": ("001", "099"),
            "storage": ("100", "199"),
            "memory": ("200", "299"),
            "classification": ("300", "399"),
            "security": ("400", "499"),
            "import_export": ("500", "599"),
            "cli_tui_mcp": ("600", "699"),
        }
        for code in ERROR_MESSAGES:
            num = int(code.split("-")[1])
            in_range = any(lo <= num <= hi for lo, hi in ((int(lo), int(hi)) for lo, hi in ranges.values()))
            assert in_range or code == "CM-999", f"Code {code} outside defined ranges"

    def test_all_error_codes_sorted(self):
        codes = all_error_codes()
        assert codes == sorted(codes), "all_error_codes() should return sorted list"


# ════════════════════════════════════════════════════════════════════
# 2. from_cause Mapping
# ════════════════════════════════════════════════════════════════════


class TestFromCauseMapping:
    """Test that from_cause() maps low-level exceptions to friendly errors."""

    def test_sqlite_unique_constraint(self):
        exc = sqlite3.IntegrityError("UNIQUE constraint failed: memories.id")
        err = CarryMemError.from_cause(exc)
        assert isinstance(err, CarryMemError)
        assert err.code == "CM-102"
        assert err.cause is exc
        assert err.hint != ""

    def test_sqlite_no_such_table(self):
        exc = sqlite3.OperationalError("no such table: memories")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-103"

    def test_sqlite_database_locked(self):
        exc = sqlite3.OperationalError("database is locked")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-104"

    def test_sqlite_unable_to_open(self):
        exc = sqlite3.OperationalError("unable to open database file")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-105"

    def test_sqlite_generic(self):
        exc = sqlite3.OperationalError("some other sqlite error")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-101"
        assert err.cause is exc

    def test_os_error_permission_denied(self):
        exc = PermissionError("[Errno 13] Permission denied: /secret/file")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-106"

    def test_os_error_no_space(self):
        exc = OSError(28, "No space left on device")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-107"

    def test_os_error_file_not_found(self):
        exc = FileNotFoundError("[Errno 2] No such file: '/missing.db'")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-108"

    def test_value_error_unknown_adapter(self):
        exc = ValueError("Unknown adapter: 'mongodb'")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-100"

    def test_value_error_knowledge_not_configured(self):
        exc = ValueError("Knowledge adapter not configured.")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-110"

    def test_value_error_path_security(self):
        exc = ValueError("Path traversal: system directory not allowed: /etc/passwd")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-402"

    def test_value_error_invalid_input(self):
        exc = ValueError("Invalid input: empty content")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-201" or err.code == "CM-202"

    def test_fallback_unknown_exception(self):
        class CustomError(Exception):
            pass

        exc = CustomError("something completely unexpected")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-999"
        assert "Unexpected error" in err.message


# ════════════════════════════════════════════════════════════════════
# 3. Bilingual Message Completeness
# ════════════════════════════════════════════════════════════════════


class TestBilingualMessages:
    """Verify every error code has both zh and en messages."""

    def test_all_codes_have_zh(self):
        for code, entry in ERROR_MESSAGES.items():
            assert "zh" in entry, f"{code} missing 'zh' message"
            assert entry["zh"], f"{code} has empty 'zh' message"

    def test_all_codes_have_en(self):
        for code, entry in ERROR_MESSAGES.items():
            assert "en" in entry, f"{code} missing 'en' message"
            assert entry["en"], f"{code} has empty 'en' message"

    def test_get_message_zh(self):
        msg = get_message("CM-101", "zh")
        assert msg
        assert "\u64cd\u4f5c" in msg or "数据库" in msg  # contains Chinese chars

    def test_get_message_en(self):
        msg = get_message("CM-101", "en")
        assert msg
        assert "Database" in msg or "operation" in msg.lower()

    def test_get_message_fallback_to_en(self):
        msg = get_message("CM-00000", "zh")  # non-existent code
        assert "Unknown" in msg

    def test_get_hint_zh(self):
        hint = get_hint("CM-102", "zh")
        assert hint
        assert len(hint) > 5  # meaningful hint

    def test_get_hint_en(self):
        hint = get_hint("CM-102", "en")
        assert hint

    def test_get_hint_missing_returns_empty(self):
        hint = get_hint("CM-00000", "zh")
        assert hint == ""

    def test_most_codes_have_hints(self):
        with_hint = sum(1 for e in ERROR_MESSAGES.values() if e.get("hint_zh"))
        total = len(ERROR_MESSAGES)
        ratio = with_hint / total
        assert ratio >= 0.8, f"Only {ratio:.0%} of codes have hints (expect >= 80%)"


# ════════════════════════════════════════════════════════════════════
# 4. CarryMemError Base Class Behavior
# ════════════════════════════════════════════════════════════════════


class TestCarryMemErrorBaseClass:
    """Test base class construction, formatting, and repr."""

    def test_basic_construction(self):
        err = CarryMemError(code="CM-101", message="test msg", hint="try this")
        assert err.code == "CM-101"
        assert err.message == "test msg"
        assert err.hint == "try this"
        assert err.cause is None

    def test_str_format_includes_code_and_message(self):
        err = CarryMemError(code="CM-101", message="test msg", hint="try this")
        s = str(err)
        assert "[CM-101]" in s
        assert "test msg" in s
        assert "try this" in s

    def test_str_without_hint_omits_hint_line(self):
        err = CarryMemError(code="CM-101", message="test msg")
        s = str(err)
        assert "[CM-101]" in s
        assert "test msg" in s

    def test_repr_format(self):
        err = CarryMemError(code="CM-101", message="test msg")
        r = repr(err)
        assert "CarryMemError" in r
        assert "CM-101" in r

    def test_with_cause_chain(self):
        original = ValueError("original error")
        err = CarryMemError(code="CM-101", message="wrapped", cause=original)
        assert err.cause is original

    def test_is_exception_subclass(self):
        assert issubclass(CarryMemError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(CarryMemError):
            raise CarryMemError(code="CM-001", message="test")

    def test_concrete_subclasses_exist(self):
        concrete = [
            ConfigError,
            StorageAdapterError,
            MemoryOperationError,
            ClassificationError,
            SecurityError,
            ImportExportError,
            CLIEntryError,
        ]
        for cls in concrete:
            assert issubclass(cls, CarryMemError)


# ════════════════════════════════════════════════════════════════════
# 5. ErrorTemplate Data Class
# ════════════════════════════════════════════════════════════════════


class TestErrorTemplate:
    """Test the frozen dataclass template."""

    def test_creation(self):
        t = ErrorTemplate(code="CM-001", zh="\u6d4b\u8bd5", en="test")
        assert t.code == "CM-001"
        assert t.zh == "\u6d4b\u8bd5"
        assert t.en == "test"
        assert t.hint_zh == ""
        assert t.hint_en == ""

    def test_frozen_immutable(self):
        t = ErrorTemplate(code="CM-001", zh="a", en="b")
        with pytest.raises(AttributeError):
            t.code = "CM-002"  # type: ignore[misc]

    def test_with_hints(self):
        t = ErrorTemplate(
            code="CM-002",
            zh="err",
            en="error",
            hint_zh="hint zh",
            hint_en="hint en",
        )
        assert t.hint_zh == "hint zh"
        assert t.hint_en == "hint en"


# ════════════════════════════════════════════════════════════════════
# 6. Integration: Known Exception Mapping
# ════════════════════════════════════════════════════════════════════


class TestKnownExceptionMapping:
    """Test mapping of known carrymem.exceptions to error codes."""

    def test_storage_not_configured_maps(self):
        from carrymem.exceptions import StorageNotConfiguredError

        exc = StorageNotConfiguredError()
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-100"
        assert "存储" in err.message or "configured" in err.message.lower()

    def test_knowledge_not_configured_maps(self):
        from carrymem.exceptions import KnowledgeNotConfiguredError

        exc = KnowledgeNotConfiguredError()
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-110"

    def test_classification_error_maps(self):
        from carrymem.exceptions import ClassificationError as _ClsErr

        exc = _ClsErr("classification failed")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-301"

    def test_validation_error_maps(self):
        from carrymem.exceptions import ValidationError as _ValErr

        exc = _ValErr("bad input")
        err = CarryMemError.from_cause(exc)
        assert err.code == "CM-201"


# ════════════════════════════════════════════════════════════════════
# 7. Registry Completeness
# ════════════════════════════════════════════════════════════════════


class TestRegistryCompleteness:
    """Ensure error message registry covers key scenarios."""

    MINIMUM_REQUIRED_CODES = {
        # Must-have scenarios per task spec
        "CM-100": "storage not configured",
        "CM-101": "database operation failure",
        "CM-102": "unique constraint / duplicate",
        "CM-110": "knowledge not configured",
        "CM-201": "validation failure",
        "CM-301": "classification failure",
        "CM-401": "encryption failure",
        "CM-501": "import format error",
        "CM-601": "unknown command",
        "CM-999": "fallback unknown",
    }

    @pytest.mark.parametrize("code,desc", list(MINIMUM_REQUIRED_CODES.items()))
    def test_required_code_exists(self, code, desc):
        assert code in ERROR_MESSAGES, f"Required error code {code} ({desc}) missing from registry"

    def test_total_code_count(self):
        assert len(ERROR_MESSAGES) >= 35, f"Expected at least 35 error codes, got {len(ERROR_MESSAGES)}"
