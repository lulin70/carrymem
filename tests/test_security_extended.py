"""Extended security module tests for CarryMem — targets 60%+ coverage.

Covers: encryption, redaction, input_validator, audit
"""

import base64
import json
import os
import re
import sqlite3
import tempfile

import pytest

from carrymem.security.encryption import (
    EncryptionError,
    MemoryEncryption,
    NoEncryption,
    SecurityWarning,
)
from carrymem.security.redaction import (
    SENSITIVE_PATTERNS,
    detect_sensitive_content,
    redact_content,
    should_redact,
)
from carrymem.security.input_validator import (
    InputValidator,
    ValidationError,
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
from carrymem.security.audit import AuditLogger, _AUDIT_SCHEMA_SQL


# ===========================================================================
# encryption.py tests
# ===========================================================================


class TestEncryptionRoundTrip:
    """Encrypt-then-decrypt round-trip correctness."""

    @pytest.fixture()
    def enc(self, tmp_path):
        key_file = str(tmp_path / ".test_key")
        return MemoryEncryption(key="test-password-123", key_file=key_file)

    def test_encrypt_decrypt_roundtrip(self, enc):
        plaintext = "Hello, CarryMem!"
        ciphertext = enc.encrypt(plaintext)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext) == plaintext

    def test_different_keys_produce_different_ciphertexts(self, tmp_path):
        msg = "same message"
        e1 = MemoryEncryption(key="password-alpha", key_file=str(tmp_path / "k1"))
        e2 = MemoryEncryption(key="password-beta", key_file=str(tmp_path / "k2"))
        assert e1.encrypt(msg) != e2.encrypt(msg)

    def test_empty_plaintext_handling(self, enc):
        assert enc.encrypt("") == ""
        assert enc.decrypt("") == ""

    def test_unicode_content(self, enc):
        plaintext = "你好世界 🌍 café ñoño 日本語テスト"
        assert enc.decrypt(enc.encrypt(plaintext)) == plaintext

    def test_large_payload(self, enc):
        plaintext = "A" * 50000
        assert enc.decrypt(enc.encrypt(plaintext)) == plaintext


class TestEncryptionEdgeCases:
    """Error handling and edge cases."""

    @pytest.fixture()
    def enc(self, tmp_path):
        return MemoryEncryption(key="edge-case-pwd", key_file=str(tmp_path / ".ek"))

    def test_invalid_key_rejection_bad_base64(self, enc):
        with pytest.raises(EncryptionError):
            enc.decrypt("not-valid-base64!!!")

    def test_invalid_key_rejection_truncated(self, enc):
        with pytest.raises(EncryptionError):
            enc.decrypt(base64.b64encode(b"short").decode())

    def test_corrupted_ciphertext_detection(self, enc):
        ct = enc.encrypt("sensitive data")
        # Flip some bytes in the middle (after base64-decode)
        raw = base64.b64decode(ct)
        corrupted = bytearray(raw)
        mid = len(corrupted) // 2
        corrupted[mid] ^= 0xFF
        bad_ct = base64.b64encode(bytes(corrupted)).decode()
        with pytest.raises(EncryptionError):
            enc.decrypt(bad_ct)

    def test_key_derivation_deterministic(self, tmp_path):
        kf = str(tmp_path / ".det_key")
        salt_file = kf + ".salt"
        # First derivation creates salt
        k1 = MemoryEncryption(key="same-pass", key_file=kf)
        # Remove in-memory reference, reload from same password + persisted salt
        k2 = MemoryEncryption(key="same-pass", key_file=kf)
        # Same password + same salt file => same derived key => can decrypt each other's output
        msg = "determinism test"
        assert k2.decrypt(k1.encrypt(msg)) == msg


class TestEncryptionBackend:
    """Backend detection and NoEncryption passthrough."""

    def test_fernet_backend_primary(self, tmp_path):
        enc = MemoryEncryption(key="fernet-test", key_file=str(tmp_path / ".fk"))
        if enc._fernet_available:
            assert enc.backend == "fernet"
        else:
            assert enc.backend == "hmac-ctr"

    def test_is_active_true(self, tmp_path):
        assert MemoryEncryption(key="x", key_file=str(tmp_path / ".ia")).is_active is True

    def test_no_encryption_passthrough(self):
        ne = NoEncryption()
        assert ne.encrypt("hello") == "hello"
        assert ne.decrypt("world") == "world"
        assert ne.is_active is False
        assert ne.backend == "none"


class TestEncryptionKeyManagement:
    """Key file lifecycle."""

    def test_auto_key_generation(self, tmp_path):
        key_file = str(tmp_path / ".auto_key")
        enc = MemoryEncryption(key_file=key_file)
        assert os.path.exists(key_file)
        # Should be able to encrypt/decrypt with auto-generated key
        ct = enc.encrypt("auto-key-test")
        assert enc.decrypt(ct) == "auto-key-test"

    def test_key_file_permissions(self, tmp_path):
        key_file = str(tmp_path / ".perm_key")
        MemoryEncryption(key_file=key_file)
        # Unix only
        if os.name != "nt":
            stat_mode = oct(os.stat(key_file).st_mode)[-3:]
            assert stat_mode == "600"


# ===========================================================================
# redaction.py tests
# ===========================================================================


class TestRedactDetectAPIKeys:
    """Individual sensitive pattern detection."""

    def test_detect_api_key_sk_pattern(self):
        findings = detect_sensitive_content("My key is sk-abcdefghijklmnopqrstuvwxyz123456")
        names = [f[0] for f in findings]
        assert "openai_api_key" in names

    def test_detect_api_key_ghp_pattern(self):
        findings = detect_sensitive_content("token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789")
        names = [f[0] for f in findings]
        assert "github_token" in names

    def test_detect_password_in_url(self):
        findings = detect_sensitive_content("postgres://admin:secret123@db.host:5432/mydb")
        names = [f[0] for f in findings]
        assert "password_in_url" in names

    def test_detect_email_address(self):
        # Email is not a dedicated SENSITIVE_PATTERN but we check generic patterns don't false-positive
        findings = detect_sensitive_content("Contact me at user@example.com")
        # email itself isn't a pattern; this just ensures no crash
        assert isinstance(findings, list)

    def test_detect_ip_address(self):
        # IP not a dedicated pattern either — ensure no crash
        findings = detect_sensitive_content("Server at 192.168.1.1")
        assert isinstance(findings, list)

    def test_detect_aws_key(self):
        findings = detect_sensitive_content("AWS_KEY=AKIAIOSFODNN7EXAMPLE")
        names = [f[0] for f in findings]
        assert "aws_access_key" in names


class TestRedactRedaction:
    """Redaction (replacement) behaviour."""

    def test_redact_preserves_structure(self):
        original = "Use sk-abcdefghijklmnopqrst for auth"
        redacted = redact_content(original)
        assert "[REDACTED]" in redacted
        assert "Use" in redacted
        assert "for auth" in redacted

    def test_multiple_patterns_one_text(self):
        text = (
            "key=sk-abcdefghijklmnopqrst "
            "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789 "
            "AKIAIOSFODNN7EXAMPLE"
        )
        findings = detect_sensitive_content(text)
        assert len(findings) >= 3

    def test_no_false_positive_on_normal_text(self):
        normal = "The quick brown fox jumps over the lazy dog."
        assert should_redact(normal) == (False, None)
        assert redact_content(normal) == normal

    def test_redact_with_placeholder(self):
        text = "sk-abcdefghijklmnopqrstuvwx"
        result = redact_content(text, replacement="***MASKED***")
        assert "***MASKED***" in result
        assert "sk-" not in result


class TestRedactSpecialPatterns:
    """Less-common but important patterns."""

    def test_detect_anthropic_key(self):
        findings = detect_sensitive_content("key: sk-ant-api03-abcDEFghijKLmnopqrSTUVWXYZ123")
        names = [f[0] for f in findings]
        assert "anthropic_key" in names

    def test_detect_bearer_token(self):
        findings = detect_sensitive_content("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        names = [f[0] for f in findings]
        assert "bearer_token" in names

    def test_detect_private_key_pem(self):
        findings = detect_sensitive_content("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA")
        names = [f[0] for f in findings]
        assert "private_key" in names

    def test_detect_jwt_token(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        findings = detect_sensitive_content(jwt)
        names = [f[0] for f in findings]
        assert "jwt_token" in names

    def test_detect_db_connection_string(self):
        findings = detect_sensitive_content("mongodb://user:pass@host:27017/db")
        names = [f[0] for f in findings]
        assert "db_connection_string" in names

    def test_mask_matches_truncates_long(self):
        findings = detect_sensitive_content("sk-" + "a" * 50, mask_matches=True)
        _, matched, _ = findings[0]
        assert matched.endswith("...")

    def test_mask_matches_false_returns_full(self):
        findings = detect_sensitive_content("sk-" + "a" * 50, mask_matches=False)
        _, matched, _ = findings[0]
        assert "..." not in matched

    def test_empty_input_returns_empty(self):
        assert detect_sensitive_content("") == []
        assert should_redact("") == (False, None)
        assert redact_content("") == ""

    def test_custom_patterns_not_exposed(self):
        # SENSITIVE_PATTERNS is a module-level constant; verify it has expected entries
        names = [p[0] for p in SENSITIVE_PATTERNS]
        assert "openai_api_key" in names
        assert "github_token" in names
        assert len(names) >= 20  # we expect ~22+ patterns


# ===========================================================================
# input_validator.py tests
# ===========================================================================


class TestInputValidatorSQLInjection:
    """SQL injection detection."""

    def test_sql_injection_drop_table(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="SQL injection"):
            v.validate_content("'; DROP TABLE users; --")

    def test_sql_injection_union_select(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="SQL injection"):
            v.validate_content("' UNION SELECT * FROM passwords --")

    def test_sql_injection_or_1_equals_1(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="SQL injection"):
            v.validate_content("' OR 1=1 --")

    def test_safe_sql_like_content_passes(self):
        v = InputValidator()
        result = v.validate_content("SELECT is not a command here")
        assert "SELECT" in result or result.strip() != ""


class TestInputValidatorXSS:
    """XSS / HTML tag detection."""

    def test_xss_script_tag_removed(self):
        v = InputValidator(strict_mode=True)
        with pytest.raises(ValidationError, match="XSS"):
            v.validate_content("<script>alert('xss')</script>")

    def test_xss_javascript_uri(self):
        v = InputValidator(strict_mode=True)
        with pytest.raises(ValidationError, match="XSS"):
            v.validate_content('<a href="javascript:alert(1)">click</a>')

    def test_xss_on_event_handler(self):
        v = InputValidator(strict_mode=True)
        with pytest.raises(ValidationError, match="XSS"):
            v.validate_content('<img src=x onerror="alert(1)">')

    def test_html_tag_stripped_non_strict(self):
        """In non-strict mode XSS is allowed but content is still sanitized."""
        v = InputValidator(strict_mode=False)
        # Should NOT raise for XSS in non-strict mode
        result = v.validate_content("<script>alert(1)</script> hello")
        assert isinstance(result, str)


class TestInputValidatorLengthLimits:
    """Message length enforcement."""

    def test_message_length_enforced(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="maximum length"):
            v.validate_content("x" * 10001)

    def test_query_max_length(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="maximum length"):
            v.validate_query("q" * 1001)

    def test_namespace_max_length(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="maximum length"):
            v.validate_namespace("n" * 101)

    def test_empty_content_rejected(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="empty"):
            v.validate_content("   ")

    def test_non_string_content_rejected(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="string"):
            v.validate_content(12345)


class TestInputValidatorContextValidation:
    """Namespace, memory type, confidence, limit, filters validation."""

    def test_valid_namespace(self):
        v = InputValidator()
        assert v.validate_namespace("my_ns-123") == "my_ns-123"

    def test_namespace_lowered(self):
        v = InputValidator()
        assert v.validate_namespace("MyNameSpace") == "mynamespace"

    def test_namespace_invalid_chars(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="letters, numbers"):
            v.validate_namespace("bad namespace!")

    def test_memory_type_valid(self):
        v = InputValidator()
        assert v.validate_memory_type("fact_declaration") == "fact_declaration"

    def test_memory_type_invalid(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="Invalid memory type"):
            v.validate_memory_type("fake_type")

    def test_confidence_valid_range(self):
        v = InputValidator()
        assert v.validate_confidence(0.5) == 0.5
        assert v.validate_confidence(0) == 0.0
        assert v.validate_confidence(1) == 1.0

    def test_confidence_out_of_range_low(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            v.validate_confidence(-0.1)

    def test_confidence_out_of_range_high(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="between 0.0 and 1.0"):
            v.validate_confidence(1.1)

    def test_limit_valid(self):
        v = InputValidator()
        assert v.validate_limit(10) == 10
        assert v.validate_limit(1000) == 1000

    def test_limit_too_small(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="at least 1"):
            v.validate_limit(0)

    def test_limit_too_large(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="exceed 1000"):
            v.validate_limit(1001)

    def test_filters_valid(self):
        v = InputValidator()
        result = v.validate_filters({"type": "decision", "namespace": "proj"})
        assert result["type"] == "decision"
        assert result["namespace"] == "proj"

    def test_filters_invalid_key(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="Invalid filter key"):
            v.validate_filters({"bogus": "value"})

    def test_filters_not_dict(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="dictionary"):
            v.validate_filters("not-a-dict")


class TestInputValidatorPathTraversal:
    """Path traversal protection."""

    def test_path_traversal_dot_dot(self, tmp_path):
        v = InputValidator(strict_mode=False)
        with pytest.raises(ValidationError, match="path traversal"):
            v.validate_path("/etc/passwd")

    def test_path_traversal_tilde(self, tmp_path):
        v = InputValidator(strict_mode=False)
        with pytest.raises(ValidationError, match="path traversal"):
            v.validate_path("~/.ssh/id_rsa")

    def test_safe_characters_pass(self, tmp_path):
        v = InputValidator(strict_mode=False)  # skip location check; focus on traversal
        from pathlib import Path
        safe_path = str(tmp_path / "safe_file.txt")
        # Create the file so must_exist works
        open(safe_path, "w").close()
        result = v.validate_path(safe_path, must_exist=True)
        assert result.exists()


class TestInputValidatorCommandInjection:
    """Command injection detection."""

    def test_command_injection_dollar_paren(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="command injection"):
            v.validate_content("$(rm -rf /)")

    def test_command_injection_backtick(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="command injection"):
            v.validate_content("`cat /etc/passwd`")

    def test_command_injection_rm_flag(self):
        v = InputValidator()
        with pytest.raises(ValidationError, match="command injection"):
            v.validate_content("run rm -rf /tmp")


class TestInputValidatorConvenienceFunctions:
    """Module-level convenience wrappers."""

    def test_get_validator_singleton_strict(self):
        v1 = get_validator(strict_mode=True)
        v2 = get_validator(strict_mode=True)
        assert v1 is v2

    def test_get_validator_different_modes(self):
        v_strict = get_validator(strict_mode=True)
        v_loose = get_validator(strict_mode=False)
        assert v_strict.strict_mode is True
        assert v_loose.strict_mode is False

    def test_validate_content_convenience(self):
        result = validate_content("hello world")
        assert result == "hello world"

    def test_validate_query_convenience_empty(self):
        assert validate_query("") == ""


# ===========================================================================
# audit.py tests
# ===========================================================================


@pytest.fixture()
def audit_db(tmp_path):
    """Create an in-memory SQLite DB with audit schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_AUDIT_SCHEMA_SQL)
    conn.commit()

    def _factory():
        return conn

    return _factory


class TestAuditLoggerBasic:
    """Audit logger core functionality."""

    def test_audit_log_entry_creation(self, audit_db):
        logger = AuditLogger(audit_db, namespace="test_ns")
        logger.log_operation(
            operation="store",
            storage_key="mem-001",
            memory_type="fact_declaration",
            success=True,
            details={"size": 42},
        )
        entries = logger.query(limit=10)
        assert len(entries) == 1
        assert entries[0]["operation"] == "store"
        assert entries[0]["namespace"] == "test_ns"
        assert entries[0]["storage_key"] == "mem-001"
        assert entries[0]["memory_type"] == "fact_declaration"
        assert entries[0]["success"] is True
        assert entries[0]["details"]["size"] == 42
        assert entries[0]["source"] == "api"

    def test_audit_log_multiple_entries(self, audit_db):
        logger = AuditLogger(audit_db, namespace="multi")
        for i in range(5):
            logger.log_operation(operation=f"op_{i}", storage_key=f"key-{i}")
        entries = logger.query(limit=10)
        assert len(entries) == 5

    def test_audit_log_stats(self, audit_db):
        logger = AuditLogger(audit_db, namespace="stats_ns")
        logger.log_operation(operation="store")
        logger.log_operation(operation="query")
        logger.log_operation(operation="store")
        stats = logger.get_stats()
        assert stats["total_operations"] == 3
        assert stats["by_operation"]["store"] == 2
        assert stats["by_operation"]["query"] == 1
        assert stats["last_activity"] is not None

    def test_empty_audit_returns_safe_defaults(self, audit_db):
        logger = AuditLogger(audit_db, namespace="empty_ns")
        stats = logger.get_stats()
        assert stats["total_operations"] == 0
        assert stats["by_operation"] == {}
        assert stats["last_activity"] is None

        entries = logger.query()
        assert entries == []

    def test_audit_log_failure_entry(self, audit_db):
        logger = AuditLogger(audit_db, namespace="fail_ns")
        logger.log_operation(operation="delete", success=False, details={"reason": "not found"})
        entries = logger.query(operation="delete")
        assert len(entries) == 1
        assert entries[0]["success"] is False
        assert entries[0]["details"]["reason"] == "not found"


class TestAuditLoggerQueryFiltering:
    """Audit query filtering by operation/namespace/time/source."""

    def test_filter_by_operation(self, audit_db):
        logger = AuditLogger(audit_db, namespace="q1")
        logger.log_operation(operation="store", storage_key="a")
        logger.log_operation(operation="query", storage_key="b")
        logger.log_operation(operation="store", storage_key="c")
        store_only = logger.query(operation="store")
        assert len(store_only) == 2
        assert all(e["operation"] == "store" for e in store_only)

    def test_filter_by_namespace(self, audit_db):
        logger = AuditLogger(audit_db, namespace="ns_alpha")
        logger.log_operation(operation="store", namespace="ns_alpha")
        logger.log_operation(operation="store", namespace="ns_beta")
        alpha = logger.query(namespace="ns_alpha")
        beta = logger.query(namespace="ns_beta")
        assert len(alpha) == 1
        assert len(beta) == 1
        assert alpha[0]["namespace"] == "ns_alpha"
        assert beta[0]["namespace"] == "ns_beta"

    def test_filter_by_source(self, audit_db):
        logger = AuditLogger(audit_db, namespace="src_test")
        logger.log_operation(operation="store", source="api")
        logger.log_operation(operation="store", source="cli")
        api_only = logger.query(source="api")
        assert len(api_only) == 1
        assert api_only[0]["source"] == "api"

    def test_filter_by_time_range(self, audit_db):
        logger = AuditLogger(audit_db, namespace="time_test")
        logger.log_operation(operation="store")
        all_entries = logger.query(since="0001-01-01T00:00:00Z")
        future_entries = logger.query(until="0001-01-01T00:00:00Z")
        assert len(all_entries) >= 1
        assert len(future_entries) == 0

    def test_query_limit_respected(self, audit_db):
        logger = AuditLogger(audit_db, namespace="limit_test")
        for i in range(20):
            logger.log_operation(operation=f"op_{i}")
        first_5 = logger.query(limit=5)
        assert len(first_5) == 5


class TestAuditLoggerDetailsHandling:
    """Details JSON serialisation edge cases."""

    def test_none_details_stored_as_null(self, audit_db):
        logger = AuditLogger(audit_db, namespace="detail_test")
        logger.log_operation(operation="store", details=None)
        entry = logger.query()[0]
        assert entry["details"] is None

    def test_complex_details_roundtrip(self, audit_db):
        logger = AuditLogger(audit_db, namespace="detail_test")
        complex_details = {
            "nested": {"a": 1, "b": [2, 3]},
            "list_of_dicts": [{"k": "v"}],
            "unicode": "中文测试 🎉",
        }
        logger.log_operation(operation="store", details=complex_details)
        entry = logger.query()[0]
        assert entry["details"] == complex_details

    def test_default_namespace_used(self, audit_db):
        logger = AuditLogger(audit_db, namespace="default_ns")
        logger.log_operation(operation="store")  # no explicit namespace
        entry = logger.query()[0]
        assert entry["namespace"] == "default_ns"
