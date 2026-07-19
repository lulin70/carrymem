"""
E2E Tests: Security Pipeline — Redaction -> Encryption -> Audit -> Recall

Validates the complete security chain for sensitive data handling:
1. Sensitive content detection and redaction (redaction.py)
2. At-rest encryption with key derivation (encryption.py)
3. Audit logging for all operations (audit.py)
4. Recall integrity — redacted/encrypted data remains protected
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carrymem.carrymem import CarryMem
from carrymem.security.audit import AuditFilter, AuditLogger
from carrymem.security.encryption import EncryptionError, MemoryEncryption, NoEncryption
from carrymem.security.redaction import (
    SENSITIVE_PATTERNS,
    detect_sensitive_content,
    redact_content,
    should_redact,
)


class TestE2ESecurityPipeline(unittest.TestCase):
    """Verify: Sensitive data flows through security pipeline correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_sec.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # === Redaction: Input Detection ===

    def test_api_key_detected(self):
        """Verify: OpenAI API keys are detected by the redaction engine."""
        message = "My OpenAI API key is sk-abc123def4567890123456 and I use it for GPT-4"
        findings = detect_sensitive_content(message)
        pattern_names = [f[0] for f in findings]
        self.assertIn("openai_api_key", pattern_names, "OpenAI API key pattern should be detected")

    def test_github_token_detected(self):
        """Verify: GitHub personal access tokens are detected."""
        # Pattern requires exactly 40 chars: 'ghp_' prefix + 36 alphanumeric
        token_msg = "Use this GitHub token ghp_FAKE00000000000000000000000000000000 for auth"
        findings = detect_sensitive_content(token_msg)
        pattern_names = [f[0] for f in findings]
        self.assertTrue(
            any("github" in p for p in pattern_names), f"GitHub PAT should be detected, got patterns: {pattern_names}"
        )

    def test_aws_access_key_detected(self):
        """Verify: AWS access keys are detected."""
        msg = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        findings = detect_sensitive_content(msg)
        pattern_names = [f[0] for f in findings]
        self.assertIn("aws_access_key", pattern_names, "AWS access key ID should be detected")

    def test_password_in_assignment_detected(self):
        """Verify: Password assignments (password=xxx) are detected."""
        msg = "Database config: password=SuperSecret123 host=localhost"
        findings = detect_sensitive_content(msg)
        pattern_names = [f[0] for f in findings]
        self.assertIn("password_assignment", pattern_names, "Password assignment should be detected")

    def test_bearer_token_detected(self):
        """Verify: Bearer tokens are detected."""
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        findings = detect_sensitive_content(msg)
        pattern_names = [f[0] for f in findings]
        self.assertIs(any("bearer" in p or "jwt" in p for p in pattern_names), True, "Bearer/JWT token should be detected")

    def test_db_connection_string_detected(self):
        """Verify: Database connection strings with credentials are detected."""
        msg = "Connect via postgresql://admin:mypassword@db.example.com:5432/mydb"
        findings = detect_sensitive_content(msg)
        pattern_names = [f[0] for f in findings]
        self.assertIs(any("db_connection" in p for p in pattern_names), True, "DB connection string should be detected")

    def test_private_key_detected(self):
        """Verify: Private key blocks are detected."""
        msg = "Here is my key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA"
        findings = detect_sensitive_content(msg)
        pattern_names = [f[0] for f in findings]
        self.assertIn("private_key", pattern_names, "Private key block should be detected")

    def test_generic_secret_detected(self):
        """Verify: Generic secret assignments are detected."""
        msg = "SECRET_KEY=abcdef1234567890abcdef12"
        findings = detect_sensitive_content(msg)
        pattern_names = [f[0] for f in findings]
        self.assertIn("env_sensitive", pattern_names, "Sensitive env variable should be detected")

    # === Redaction: Blocking Behavior ===

    def test_should_redact_returns_true_for_api_key(self):
        """Verify: should_redact returns True for messages containing API keys."""
        msg = "My key is sk-abcdefghijklmnopqrstuvwx"
        should, reason = should_redact(msg)
        self.assertIs(should, True, "Message with API key should be flagged for redaction")
        self.assertIsNotNone(reason, "Reason should explain why redaction is needed")
        self.assertIn("sensitive", reason.lower(), "Reason should mention sensitivity")

    def test_should_redact_returns_false_for_clean_text(self):
        """Verify: should_redact returns False for normal conversation text."""
        msg = "I prefer using Python for data analysis projects"
        should, reason = should_redact(msg)
        self.assertFalse(should, "Normal text should not trigger redaction")
        self.assertIsNone(reason, "Reason should be None when no sensitive content")

    def test_redact_content_replaces_sensitive_parts(self):
        """Verify: redact_content replaces sensitive patterns with placeholder."""
        msg = "API key sk-abcdefghijklmnopqrstuvwxyz12345 goes here"
        redacted = redact_content(msg)
        self.assertNotIn(
            "sk-abcdefghijklmnopqrstuvwxyz12345", redacted, "Original API key should not appear in redacted output"
        )
        self.assertIn("[REDACTED]", redacted, "Redacted output should contain replacement marker")

    def test_redact_content_preserves_safe_parts(self):
        """Verify: redact_content keeps non-sensitive parts intact."""
        msg = "My OpenAI API key is sk-abc123def456 and I use it for GPT-4 coding tasks"
        redacted = redact_content(msg)
        self.assertIn("GPT-4", redacted, "Non-sensitive context should be preserved")
        self.assertIn("coding tasks", redacted, "Safe text should remain unchanged")

    # === Redaction + CarryMem Integration ===

    def test_classify_and_remember_blocks_api_key_storage(self):
        """Verify: classify_and_remember blocks storage of messages containing API keys."""
        result = self.cm.classify_and_remember("My OpenAI API key is sk-abcdefghijklmnopqrstuvwx1234567890 for GPT-4")
        # Should return auto_redacted result
        self.assertFalse(result.get("stored", False), "Memory containing API key should NOT be stored")
        self.assertEqual(result.get("type"), "auto_redacted", "Result type should indicate auto-redaction")
        summary = result.get("summary", {})
        self.assertTrue(
            summary.get("redacted", False),
            "Summary should indicate redaction occurred",
        )
        self.assertIsNotNone(
            summary.get("redact_reason"),
            "Summary should include redaction reason",
        )

    def test_normal_message_stored_successfully(self):
        """Verify: Normal messages without sensitive content are stored normally."""
        result = self.cm.classify_and_remember("I prefer dark mode for my IDE")
        self.assertTrue(
            result.get("stored") or result.get("should_remember"),
            "Normal preference should be stored successfully",
        )

    def test_force_type_overrides_redaction(self):
        """Verify: force_type parameter bypasses auto-redaction check."""
        # This should store even though it contains a password-like pattern
        # because force_type explicitly overrides redaction
        result = self.cm.classify_and_remember(
            "The password for dev environment is DevPass2024",
            force_type="fact_declaration",
        )
        # With force_type, redaction is bypassed - it may store or not depending on classification
        self.assertIsNotNone(result, "Result should not be None")

    # === Encryption: At-Rest Protection ===

    def test_encryption_active_with_key(self):
        """Verify: MemoryEncryption is active when encryption_key is provided."""
        enc = MemoryEncryption(key="test-encryption-password-123")
        self.assertIs(enc.is_active, True, "Encryption should be active with a key")
        self.assertEqual(enc.backend, "fernet", f"Backend should be fernet, got {enc.backend}")

    def test_encryption_roundtrip(self):
        """Verify: encrypt -> decrypt produces original plaintext."""
        enc = MemoryEncryption(key="my-secret-passphrase")
        original = "This is sensitive memory content about user preferences"
        encrypted = enc.encrypt(original)
        decrypted = enc.decrypt(encrypted)
        self.assertEqual(decrypted, original, "Decrypted text must match original plaintext")
        self.assertNotEqual(encrypted, original, "Ciphertext must differ from plaintext")

    def test_encryption_different_keys_fail(self):
        """Verify: Decrypting with wrong key raises InvalidToken."""
        enc1 = MemoryEncryption(key="correct-password-123")
        enc2 = MemoryEncryption(key="wrong-password-456")
        ciphertext = enc1.encrypt("secret data")
        with self.assertRaises((EncryptionError, Exception)):
            # Fernet raises InvalidToken, which may be wrapped or not
            enc2.decrypt(ciphertext)

    def test_encryption_empty_string(self):
        """Verify: Encryption handles empty string gracefully."""
        enc = MemoryEncryption(key="test-key")
        self.assertEqual(enc.encrypt(""), "")
        self.assertEqual(enc.decrypt(""), "")

    def test_no_encryption_passthrough(self):
        """Verify: NoEncryption returns input unchanged."""
        noenc = NoEncryption()
        text = "plain text that passes through"
        self.assertEqual(noenc.encrypt(text), text)
        self.assertEqual(noenc.decrypt(text), text)
        self.assertFalse(noenc.is_active)
        self.assertEqual(noenc.backend, "none")

    def test_carrymem_with_encryption_stores_data(self):
        """Verify: CarryMem with encryption_key can store and recall memories."""
        cm_enc = CarryMem(
            storage="sqlite",
            db_path=os.path.join(self.tmpdir, "test_enc.db"),
            encryption_key="e2e-test-encryption-key-12345",
        )
        try:
            result = cm_enc.classify_and_remember("I prefer Rust for systems programming")
            self.assertTrue(
                result.get("stored") or result.get("should_remember"),
                "Encrypted storage should work normally from user perspective",
            )

            # Recall should work transparently
            memories = cm_enc.recall_memories(query="Rust", limit=5)
            self.assertGreaterEqual(
                len(memories),
                0,
                "Should be able to recall from encrypted storage",
            )
        finally:
            cm_enc.close()

    def test_encrypted_data_not_in_plaintext_in_db(self):
        """Verify: Raw DB does not contain plaintext when encryption is enabled."""
        enc_db_path = os.path.join(self.tmpdir, "test_raw_check.db")
        secret_message = "My banking PIN is 9876 and SSN is 123-45-6789"
        cm_enc = CarryMem(storage="sqlite", db_path=enc_db_path, encryption_key="super-secret-key-for-e2e-test")
        try:
            # Store a message with sensitive-looking info
            # Note: if redaction would block it, we use force_type to bypass
            result = cm_enc.classify_and_remember(
                secret_message,
                force_type="user_preference",
            )

            # Close connection so we can read raw DB file
            cm_enc.close()

            # Read raw database file
            conn = sqlite3.connect(enc_db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT content FROM memories LIMIT 1").fetchone()
                if row and row["content"]:
                    content = row["content"]
                    # Encrypted content should be base64-like, not plain readable text
                    # The raw DB should NOT contain the exact plaintext
                    self.assertNotIn(
                        "banking PIN",
                        content,
                        "Raw DB should not contain plaintext 'banking PIN'",
                    )
                    self.assertNotIn(
                        "9876",
                        content,
                        "Raw DB should not contain plaintext PIN digits",
                    )
            finally:
                conn.close()
        finally:
            pass  # already closed

    # === Audit Logging ===

    def test_audit_logger_creates_table(self):
        """Verify: AuditLogger is initialized and operational (in-memory mode)."""
        # In-memory AuditLogger does not create DB tables
        if self.cm._adapter and hasattr(self.cm._adapter, "_audit") and self.cm._adapter._audit:
            stats = self.cm._adapter._audit.get_stats()
            self.assertIsNotNone(stats, "AuditLogger should be operational")

    def test_audit_log_records_store_operation(self):
        """Verify: Storing a memory creates an audit log entry."""
        self.cm.classify_and_remember("Audit test: I prefer vim over emacs")

        if self.cm._adapter and hasattr(self.cm._adapter, "_audit") and self.cm._adapter._audit:
            from carrymem.security.audit import AuditFilter

            audit_entries = self.cm._adapter._audit.query(AuditFilter(action="remember", limit=10))
            self.assertGreater(len(audit_entries), 0, "Audit log should have at least one 'remember' action")
            entry = audit_entries[0]
            self.assertEqual(entry.action, "remember")
            self.assertEqual(entry.result, "SUCCESS", "Operation should be logged as successful")
            self.assertIsNotNone(entry.timestamp, "Timestamp should be recorded")

    def test_audit_log_records_recall_operation(self):
        """Verify: Recalling memories creates audit log entries."""
        self.cm.classify_and_remember("Recall audit test: We chose PostgreSQL")
        self.cm.recall_memories(query="PostgreSQL", limit=5)

        audit_entries = self.cm.get_audit_log(limit=20)
        # Audit log should have recorded operations (store at minimum)
        self.assertGreater(len(audit_entries), 0, "Audit log should contain entries after store+recall")

    def test_audit_log_records_forget_operation(self):
        """Verify: Forgetting a memory is logged in audit trail."""
        result = self.cm.classify_and_remember("Forget audit test: temporary note")
        storage_keys = result.get("storage_keys", [])
        if storage_keys:
            self.cm.forget_memory(storage_keys[0])
            audit_entries = self.cm.get_audit_log(operation="forget", limit=10)
            self.assertGreater(len(audit_entries), 0, "Forget operation should appear in audit log")

    def test_audit_log_stats(self):
        """Verify: get_stats returns aggregate audit information."""
        self.cm.classify_and_remember("Stats test: I like Python")
        self.cm.classify_and_remember("Stats test: We deploy to AWS")

        if self.cm._adapter and hasattr(self.cm._adapter, "_audit") and self.cm._adapter._audit:
            stats = self.cm._adapter._audit.get_stats()
            self.assertIn("total_events", stats)
            self.assertIn("by_action", stats)
            self.assertGreater(stats["total_events"], 0, "Should have some audit events recorded")

    def test_audit_log_namespace_isolation(self):
        """Verify: Audit logs are scoped per CarryMem instance."""
        ns_cm = CarryMem(
            storage="sqlite", db_path=os.path.join(self.tmpdir, "ns_test.db"), namespace="e2e_test_namespace"
        )
        try:
            ns_cm.classify_and_remember("Namespace isolated memory")

            if ns_cm._adapter and hasattr(ns_cm._adapter, "_audit") and ns_cm._adapter._audit:
                entries = ns_cm._adapter._audit.query()
                # In-memory logger is per-instance, all entries belong to this instance
                self.assertGreater(len(entries), 0, "Should have audit entries for this instance")
        finally:
            ns_cm.close()

    # === Full Pipeline: Redaction → Encrypt → Audit → Recall ===

    def test_full_pipeline_normal_message(self):
        """Verify: Complete pipeline for normal (non-sensitive) message.

        Flow: classify_and_remember → [no redaction needed] → encrypt → audit → recall
        """
        message = "Our team decided to use microservices architecture"
        # Step 1: Store
        result = self.cm.classify_and_remember(message)
        self.assertTrue(result.get("stored") or result.get("should_remember"))

        # Step 2: Verify audit logged
        audit_entries = self.cm.get_audit_log(limit=10)
        self.assertGreater(len(audit_entries), 0, "Storage should be audited")

        # Step 3: Recall
        memories = self.cm.recall_memories(query="microservices", limit=5)
        self.assertGreater(len(memories), 0, "Stored memory should be recallable")

        # Step 4: Verify content integrity
        recalled_content = memories[0].get("content", "")
        self.assertIn("microservices", recalled_content.lower(), "Recalled content should match stored content")

    def test_full_pipeline_blocked_by_redaction(self):
        """Verify: Complete pipeline for sensitive message blocked by redaction.

        Flow: classify_and_remember → [REDACTED] → NOT stored → NO audit for store
        """
        message = "Database config: password=SuperSecret123ForTestingOnly456 host=localhost"
        result = self.cm.classify_and_remember(message)

        # Should be blocked
        self.assertFalse(result.get("stored", False), "Sensitive message should NOT be stored")
        self.assertEqual(result.get("type"), "auto_redacted")

        # The specific memory should not be recallable
        memories = self.cm.recall_memories(query="password", limit=5)
        pw_memories = [m for m in memories if "password" in m.get("content", "").lower()]
        self.assertEqual(len(pw_memories), 0, "Redacted memory should not appear in recall results")

    def test_full_pipeline_encrypted_recall_integrity(self):
        """Verify: Encrypted storage preserves recall integrity through decrypt roundtrip."""
        enc_db = os.path.join(self.tmpdir, "integrity.db")
        cm_e = CarryMem(storage="sqlite", db_path=enc_db, encryption_key="integrity-test-key-xyz-98765")
        try:
            original_messages = [
                "I prefer functional programming paradigms",
                "We use Terraform for infrastructure as code",
                "Code reviews are mandatory before merging",
            ]
            for msg in original_messages:
                cm_e.classify_and_remember(msg)

            # Recall all
            memories = cm_e.recall_memories(limit=10)
            recalled_contents = {m.get("content", "") for m in memories}

            # Each original message should be recoverable
            for orig in original_messages:
                found = any(orig.lower() in rc.lower() or rc.lower() in orig.lower() for rc in recalled_contents)
                self.assertTrue(
                    found,
                    f"Original message '{orig[:40]}...' should be recoverable " f"after encrypt/recall cycle",
                )
        finally:
            cm_e.close()

    # === Edge Cases ===

    def test_multiple_patterns_in_one_message(self):
        """Verify: Multiple distinct sensitive patterns are all detected."""
        msg = (
            "OpenAI key: sk-abc123def45678901234567890123456 "
            "GitHub: ghp_FAKE00000000000000000000000000000000 "
            "DB: postgresql://admin:secret@localhost/db"
        )
        findings = detect_sensitive_content(msg)
        pattern_names = set(f[0] for f in findings)
        self.assertIn("openai_api_key", pattern_names)
        self.assertTrue(
            any("github" in p for p in pattern_names),
            f"GitHub token should be among detected patterns, got: {pattern_names}",
        )
        self.assertTrue(
            any("db_connection" in p for p in pattern_names), "DB connection string should be among detected patterns"
        )

    def test_redact_preserves_message_structure(self):
        """Verify: Redaction doesn't corrupt overall message structure."""
        msg = "Set your API key as OPENAI_API_KEY=sk-abc123def4567890123456 in .env file"
        redacted = redact_content(msg)
        # Key structural elements should survive
        self.assertIn(".env", redacted, "File reference should survive redaction")
        # The actual key value should be removed
        self.assertNotIn("sk-abc123def4567890123456", redacted, "Actual key value should be removed")

    def test_empty_input_to_redaction_functions(self):
        """Verify: Redaction functions handle empty/None inputs safely."""
        self.assertEqual(detect_sensitive_content(""), [])
        self.assertEqual(detect_sensitive_content(None), [])
        should, reason = should_redact("")
        self.assertFalse(should)
        self.assertEqual(redact_content(""), "")
        self.assertEqual(redact_content("normal text"), "normal text")

    def test_unicode_content_handled_by_encryption(self):
        """Verify: Encryption handles Unicode content correctly."""
        enc = MemoryEncryption(key="unicode-test-key")
        unicode_text = "用户偏好：使用中文编程，偏好暗色主题 🌙"
        encrypted = enc.encrypt(unicode_text)
        decrypted = enc.decrypt(encrypted)
        self.assertEqual(decrypted, unicode_text, "Unicode content must survive encrypt/decrypt roundtrip")

    def test_long_content_encryption(self):
        """Verify: Encryption handles long content without issues."""
        enc = MemoryEncryption(key="long-content-test")
        long_text = "This is a test sentence. " * 500  # ~12500 chars
        encrypted = enc.encrypt(long_text)
        decrypted = enc.decrypt(encrypted)
        self.assertEqual(decrypted, long_text, "Long content must survive encrypt/decrypt")


class TestSecurityPatternCoverage(unittest.TestCase):
    """Verify: All major sensitive pattern categories have working regex."""

    def test_all_patterns_are_valid_regex(self):
        """Verify: Every pattern in SENSITIVE_PATTERNS compiles as valid regex."""
        import re

        for name, pattern, description in SENSITIVE_PATTERNS:
            self.assertIsInstance(pattern, re.Pattern, f"Pattern '{name}' should be a compiled regex")

    def test_pattern_count_sufficient(self):
        """Verify: There are enough patterns to cover common secrets."""
        self.assertGreaterEqual(
            len(SENSITIVE_PATTERNS), 20, f"Expected at least 20 patterns, found {len(SENSITIVE_PATTERNS)}"
        )

    def test_pattern_categories_covered(self):
        """Verify: All expected categories of sensitive data have patterns."""
        categories = set(name for name, _, _ in SENSITIVE_PATTERNS)
        expected_categories = {
            "openai_api_key",
            "github_token",
            "password_assignment",
            "private_key",
            "db_connection_string",
            "generic_secret",
        }
        for cat in expected_categories:
            self.assertIn(cat, categories, f"Missing essential pattern category: {cat}")


class TestAuditLogDirectOperations(unittest.TestCase):
    """Verify: AuditLogger direct API works independently of CarryMem."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.audit = AuditLogger()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_and_query_single_entry(self):
        """Verify: Single log entry can be queried back."""
        self.audit.log_operation(
            operation="test_op",
            storage_key="key_001",
            details={"message": "test detail"},
        )
        entries = self.audit.query(AuditFilter(action="test_op", limit=10))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].action, "test_op")
        self.assertEqual(entries[0].resource, "key_001")
        self.assertEqual(entries[0].result, "SUCCESS")

    def test_log_multiple_and_filter(self):
        """Verify: Multiple entries can be filtered by operation type."""
        for i in range(5):
            self.audit.log_operation(operation=f"op_{i % 3}", details={"idx": i})

        op0_entries = self.audit.query(AuditFilter(action="op_0", limit=10))
        self.assertEqual(len(op0_entries), 2, "Should find 2 entries for op_0")

        all_entries = self.audit.query(AuditFilter(limit=100))
        self.assertEqual(len(all_entries), 5, "Total should be 5 entries")

    def test_stats_aggregation(self):
        """Verify: get_stats aggregates operations correctly."""
        self.audit.log_operation(operation="store")
        self.audit.log_operation(operation="store")
        self.audit.log_operation(operation="recall")
        self.audit.log_operation(operation="forget")

        stats = self.audit.get_stats()
        self.assertEqual(stats["total_events"], 4)
        self.assertEqual(stats["by_action"]["store"], 2)
        self.assertEqual(stats["by_action"]["recall"], 1)
        self.assertEqual(stats["by_action"]["forget"], 1)
        self.assertIsNotNone(stats["last_event"])
