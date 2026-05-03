"""Custom exceptions for CarryMem."""


class CarryMemError(Exception):
    """Base exception for all CarryMem errors."""
    pass


class StorageError(CarryMemError):
    """Raised when storage operations fail."""
    pass


class StorageNotConfiguredError(StorageError):
    """Raised when storage adapter is not configured."""
    pass


class ClassificationError(CarryMemError):
    """Raised when classification fails."""
    pass


class ValidationError(CarryMemError):
    """Raised when input validation fails."""
    pass


class KnowledgeError(CarryMemError):
    """Raised when knowledge base operations fail."""
    pass


class KnowledgeNotConfiguredError(KnowledgeError):
    """Raised when knowledge adapter is not configured."""
    pass


class DatabaseError(StorageError):
    """Raised when database operations fail."""
    pass


class DBConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class QueryError(DatabaseError):
    """Raised when database query fails."""
    pass
