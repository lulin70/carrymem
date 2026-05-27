"""Custom exceptions for CarryMem."""


class CarryMemError(Exception):
    """Base exception for all CarryMem errors."""


class StorageError(CarryMemError):
    """Raised when storage operations fail."""


class StorageNotConfiguredError(StorageError):
    """Raised when storage adapter is not configured."""


class ClassificationError(CarryMemError):
    """Raised when classification fails."""


class ValidationError(CarryMemError):
    """Raised when input validation fails."""


class KnowledgeError(CarryMemError):
    """Raised when knowledge base operations fail."""


class KnowledgeNotConfiguredError(KnowledgeError):
    """Raised when knowledge adapter is not configured."""


class DatabaseError(StorageError):
    """Raised when database operations fail."""


class DBConnectionError(DatabaseError):
    """Raised when database connection fails."""


class QueryError(DatabaseError):
    """Raised when database query fails."""
