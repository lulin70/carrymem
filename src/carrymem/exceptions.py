"""Backwards compatibility shim — all exceptions now live in carrymem.errors.

Historically this module defined a parallel ``CarryMemError`` hierarchy
(subclassing ``Exception`` directly) which caused ``isinstance`` checks
against ``carrymem.errors.CarryMemError`` to fail. The rich, error-code
bearing versions now live in :mod:`carrymem.errors` and are re-exported
here so existing ``from carrymem.exceptions import ...`` call sites keep
working.
"""

from carrymem.errors import (
    CarryMemError,
    ClassificationError,
    CLIEntryError,
    ConfigError,
    DBConnectionError,
    DatabaseError,
    ImportExportError,
    KnowledgeError,
    KnowledgeNotConfiguredError,
    MemoryOperationError,
    QueryError,
    SecurityError,
    StorageAdapterError,
    StorageError,
    StorageNotConfiguredError,
    ValidationError,
)

__all__ = [
    "CarryMemError",
    "StorageError",
    "StorageNotConfiguredError",
    "ClassificationError",
    "ValidationError",
    "KnowledgeError",
    "KnowledgeNotConfiguredError",
    "DatabaseError",
    "DBConnectionError",
    "QueryError",
    "ConfigError",
    "StorageAdapterError",
    "MemoryOperationError",
    "SecurityError",
    "ImportExportError",
    "CLIEntryError",
]
