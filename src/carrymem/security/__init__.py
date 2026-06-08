"""
Security module for CarryMem

Provides input validation, encryption, redaction, and audit logging.
"""

from .audit import AuditLogger
from .encryption import EncryptionError, MemoryEncryption, NoEncryption
from .input_validator import (
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
from .redaction import detect_sensitive_content, redact_content, should_redact

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
