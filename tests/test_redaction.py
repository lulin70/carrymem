"""Tests for auto-redaction module.

NOTE: All credential-like strings below are TEST FIXTURES (not real secrets).
They follow patterns that trigger detection but use obviously-fake values.
GitHub Secret Scanning may flag these — they are intentional test vectors."""

import pytest

from carrymem.security.redaction import (
    detect_sensitive_content,
    redact_content,
    should_redact,
)


class TestDetectSensitiveContent:
    def test_openai_api_key(self):
        findings = detect_sensitive_content("My API key is sk-fake000000test000key000abc123456")
        assert len(findings) >= 1
        assert any(f[0] == "openai_api_key" for f in findings)

    def test_github_token(self):
        findings = detect_sensitive_content("token=ghp_FakeTokenForTestingPurposesOnly12345")
        assert len(findings) >= 1
        assert any(f[0] == "github_token" for f in findings)

    def test_password_assignment(self):
        findings = detect_sensitive_content("password=fake-password-test-only")
        assert len(findings) >= 1
        assert any("assword" in f[2] for f in findings)

    def test_bearer_token(self):
        findings = detect_sensitive_content(
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        assert len(findings) >= 1

    def test_private_key(self):
        findings = detect_sensitive_content(
            "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC="
        )
        assert len(findings) >= 1
        assert any(f[0] == "private_key" for f in findings)

    def test_db_connection_string(self):
        findings = detect_sensitive_content("DATABASE_URL=postgresql://user:fakepass@localhost:5432/mydb")
        assert len(findings) >= 1

    def test_mongodb_connection(self):
        findings = detect_sensitive_content("mongodb://fakeadmin:fakepass123@localhost:27017/testdb")
        assert len(findings) >= 1

    def test_aws_access_key(self):
        findings = detect_sensitive_content("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
        assert len(findings) >= 1
        assert any(f[0] == "aws_access_key" for f in findings)

    def test_generic_api_key(self):
        findings = detect_sensitive_content("api_key=abcdefghijklmnopqrstuvwxyz1234567890")
        assert len(findings) >= 1

    def test_env_secret(self):
        findings = detect_sensitive_content("SECRET_KEY=fake-django-secret-test-1234567890abcdef")
        assert len(findings) >= 1

    def test_no_sensitive_content(self):
        findings = detect_sensitive_content("I prefer Python for data analysis")
        assert len(findings) == 0

    def test_empty_text(self):
        findings = detect_sensitive_content("")
        assert len(findings) == 0

    def test_normal_preferences(self):
        findings = detect_sensitive_content("I like boutique hotels for travel")
        assert len(findings) == 0

    def test_normal_code_discussion(self):
        findings = detect_sensitive_content("We decided to use PostgreSQL for the database")
        assert len(findings) == 0


class TestShouldRedact:
    def test_redact_api_key(self):
        should, reason = should_redact("My key is sk-fake000000test000key000abc123456")
        assert should is True
        assert reason is not None
        assert "API key" in reason or "sensitive" in reason.lower()

    def test_no_redact_normal(self):
        should, reason = should_redact("I prefer Python for data analysis")
        assert should is False
        assert reason is None

    def test_redact_password(self):
        should, reason = should_redact("password=FakeSecret123!")
        assert should is True

    def test_redact_github_token(self):
        should, reason = should_redact("ghp_FakeTokenForTestingPurposesOnly12345")
        assert should is True


class TestRedactContent:
    def test_redact_api_key(self):
        result = redact_content("My key is sk-fake000000test000key000abc123456")
        assert "sk-fake-test" not in result
        assert "[REDACTED]" in result

    def test_redact_password(self):
        result = redact_content("password=fake-password-test-only")
        assert "fake-password-test-only" not in result
        assert "[REDACTED]" in result

    def test_preserve_non_sensitive(self):
        result = redact_content("I prefer Python and my key is sk-fake000000test000key000abc123456")
        assert "Python" in result
        assert "sk-fake-test" not in result

    def test_custom_replacement(self):
        result = redact_content("password=fakesecret123", replacement="***")
        assert "***" in result
        assert "fakesecret123" not in result

    def test_no_change_for_normal_text(self):
        original = "I prefer Python for data analysis"
        result = redact_content(original)
        assert result == original

    def test_password_discussion_not_redacted(self):
        """Normal discussion about passwords should NOT be redacted."""
        should, reason = should_redact("The password is incorrect")
        assert should is False

    def test_password_expired_not_redacted(self):
        should, reason = should_redact("My password is expired")
        assert should is False

    def test_password_forgot_not_redacted(self):
        should, reason = should_redact("I forgot my password")
        assert should is False


class TestIntegration:
    """Integration tests with CarryMem classify_and_remember."""

    def test_api_key_blocked(self, tmp_path):
        """Test that API keys are automatically blocked from storage."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        result = cm.classify_and_remember("My API key is sk-fake000000test000key000abc123456")
        assert result["stored"] is False
        assert result.get("type") == "auto_redacted"

    def test_password_blocked(self, tmp_path):
        """Test that passwords with = or : are automatically blocked from storage."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        result = cm.classify_and_remember("password=FakeSecret123!")
        assert result["stored"] is False

    def test_normal_preference_stored(self, tmp_path):
        """Test that normal preferences are still stored."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        result = cm.classify_and_remember("I prefer Python for data analysis", force_type="user_preference")
        assert result["stored"] is True

    def test_force_type_overrides_redaction(self, tmp_path):
        """Test that force_type allows storing even sensitive content."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        # force_type should bypass auto-redaction (user explicitly wants to store)
        result = cm.classify_and_remember("password=FakeSecret123!", force_type="personal_fact")
        # With force_type, redaction is bypassed
        assert result["stored"] is True

    def test_github_token_blocked(self, tmp_path):
        """Test that GitHub tokens are blocked."""
        from carrymem import CarryMem

        cm = CarryMem(db_path=str(tmp_path / "test.db"))

        result = cm.classify_and_remember("Set token=ghp_FakeTokenForTestingPurposesOnly12345")
        assert result["stored"] is False
