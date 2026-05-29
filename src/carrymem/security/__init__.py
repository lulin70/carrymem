"""
Security module for CarryMem

Provides input validation, encryption, redaction, and audit logging.
"""

from .input_validator import (
    InputValidator,
    ValidationError,
    get_validator,
    validate_content,
    validate_query,
    validate_namespace,
    validate_path,
    validate_memory_type,
    validate_confidence,
    validate_limit,
    validate_filters,
)
from .encryption import MemoryEncryption, NoEncryption, EncryptionError
from .redaction import should_redact, redact_content, detect_sensitive_content
from .audit import AuditLogger

__all__ = [
    "InputValidator",
    "ValidationError",
    "get_validator",
    "validate_content",
    "validate_query",
    "validate_namespace",
    "validate_path",
    "validate_memory_type",
    "validate_confidence",
    "validate_limit",
    "validate_filters",
    "MemoryEncryption",
    "NoEncryption",
    "EncryptionError",
    "should_redact",
    "redact_content",
    "detect_sensitive_content",
    "AuditLogger",
]
