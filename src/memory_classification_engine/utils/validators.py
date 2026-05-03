"""Input validation utilities for CarryMem.

Provides validation functions to ensure data integrity and prevent
invalid inputs from causing errors.

v0.4.1: Initial implementation
"""

from typing import Any, Dict, List, Optional

from memory_classification_engine.exceptions import ValidationError


def validate_message(message: str, max_length: int = 10000) -> None:
    """Validate a message string.
    
    Args:
        message: The message to validate
        max_length: Maximum allowed length (default: 10000)
        
    Raises:
        ValidationError: If validation fails
    """
    if not message:
        raise ValidationError("Message cannot be empty")
    
    if not isinstance(message, str):
        raise ValidationError(f"Message must be a string, got {type(message).__name__}")
    
    if len(message) > max_length:
        raise ValidationError(
            f"Message too long: {len(message)} characters (max {max_length})"
        )


def validate_context(context: Optional[Dict[str, Any]]) -> None:
    """Validate a context dictionary.
    
    Args:
        context: The context to validate
        
    Raises:
        ValidationError: If validation fails
    """
    if context is None:
        return
    
    if not isinstance(context, dict):
        raise ValidationError(f"Context must be a dictionary, got {type(context).__name__}")
    
    # Check for reasonable size
    if len(str(context)) > 50000:
        raise ValidationError("Context too large (max 50000 characters when serialized)")


def validate_language(language: Optional[str]) -> None:
    """Validate a language code.
    
    Args:
        language: The language code to validate (e.g., 'en', 'zh', 'ja')
        
    Raises:
        ValidationError: If validation fails
    """
    if language is None:
        return
    
    if not isinstance(language, str):
        raise ValidationError(f"Language must be a string, got {type(language).__name__}")
    
    if len(language) > 10:
        raise ValidationError(f"Language code too long: {len(language)} (max 10)")
    
    # Basic format check (2-3 letter codes, or locale like 'en-US')
    if not language.replace('-', '').replace('_', '').isalnum():
        raise ValidationError(f"Invalid language code format: {language}")


def validate_namespace(namespace: str) -> None:
    """Validate a namespace string.
    
    Args:
        namespace: The namespace to validate
        
    Raises:
        ValidationError: If validation fails
    """
    if not namespace:
        raise ValidationError("Namespace cannot be empty")
    
    if not isinstance(namespace, str):
        raise ValidationError(f"Namespace must be a string, got {type(namespace).__name__}")
    
    if len(namespace) > 128:
        raise ValidationError(f"Namespace too long: {len(namespace)} (max 128)")
    
    # Check for valid characters (alphanumeric, dash, underscore)
    if not all(c.isalnum() or c in '-_' for c in namespace):
        raise ValidationError(
            f"Namespace contains invalid characters: {namespace}. "
            "Only alphanumeric, dash, and underscore allowed."
        )


def validate_limit(limit: int, max_limit: int = 100000) -> None:
    """Validate a limit parameter.
    
    Args:
        limit: The limit to validate
        max_limit: Maximum allowed limit (default: 100000)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(limit, int):
        raise ValidationError(f"Limit must be an integer, got {type(limit).__name__}")
    
    if limit < 0:
        raise ValidationError(f"Limit cannot be negative: {limit}")
    
    if limit > max_limit:
        raise ValidationError(f"Limit too large: {limit} (max {max_limit})")


_DEFAULT_ALLOWED_FILTER_KEYS = {"type", "tier", "confidence_min", "created_after", "namespace"}


def validate_filters(filters: Optional[Dict[str, Any]], allowed_keys: set = None) -> None:
    if filters is None:
        return
    
    if not isinstance(filters, dict):
        raise ValidationError(f"Filters must be a dictionary, got {type(filters).__name__}")
    
    keys = allowed_keys or _DEFAULT_ALLOWED_FILTER_KEYS
    invalid_keys = set(filters.keys()) - keys
    if invalid_keys:
        raise ValidationError(
            f"Invalid filter keys: {invalid_keys}. "
            f"Allowed keys: {keys}"
        )


def validate_memory_type(memory_type: str, valid_types: set) -> None:
    """Validate a memo type.
    
    Args:
        memory_the memory type to validate
        valid_types: Set of valid memory types
        
    Raises:
        ValidationError: If validation fails
    """
    if not memory_type:
        raise ValidationError("Memory type cannot be empty")
    
    if not isinstance(memory_type, str):
        raise ValidationError(f"Memory type must be a string, got {type(memory_type).__name__}")
    
    if memory_type not in valid_types:
        raise ValidationError(
            f"Invalid memory type: '{memory_type}'. "
            f"Valid types: {valid_types}"
        )


def validate_confidence(confidence: float) -> None:
    """Validate a confidence score.
    
    Args:
        confidence: The confidence score to validate (0.0 to 1.0)
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(confidence, (int, float)):
        raise ValidationError(
            f"Confidence must be a number, got {type(confidence).__name__}"
        )
    
    if not 0.0 <= confidence <= 1.0:
        raise ValidationError(
            f"Confidence must be between 0.0 and 1.0, got {confidence}"
        )


def validate_tier(tier: int) -> None:
    """Validate a memory tier.
    
    Args:
        tier: The tier to validate (1-4)
       Raises:
        ValidationError: If validation fails
    """
    if not isinstance(tier, int):
        raise ValidationError(f"Tier must be an integer, got {type(tier).__name__}")
    
    if tier not in {1, 2, 3, 4}:
        raise ValidationError(f"Tier must be 1, 2, 3, or 4, got {tier}")


def validate_storage_key(storage_key: str) -> None:
    """Validate a storage key.
    
    Args:
        storage_key: The storage key to validate
        
    Raises:
        ValidationError: If validation fails
    """
    if not storage_key:
        raise ValidationError("Storage key cannot be empty")
    
    if not isinstance(storage_key, str):
        raise ValidationError(f"Storage key must be a string, got {type(storage_key).__name__}")
    
    if len(storage_key) > 256:
        raise ValidationError(f"Storage key too long: {len(storage_key)} (max 256)")


def validate_query(query: str, max_length: int = 10000) -> None:
    """Validate a search query.
    
    Args:
        query: The query to valid max_length: Maximum allowed length (default: 10000)
        
    Raises:
        ValidationError: If validation fails
    """
    if query is None:
        return  # Empty query is allowed for some operations
    
    if not isinstance(query, str):
        raise ValidationError(f"Query must be a string, got {type(query).__name__}")
    
    if len(query) > max_length:
        raise ValidationError(
            f"Query too long: {len(query)} characters (max {max_length})"
        )


def validate_namespaces(namespaces: Optional[List[str]]) -> None:
    """Validate a list of namespaces.
    
    Args:
        nae list of namespaces to validate
        
    Raises:
        ValidationError: If validation fails
    """
    if namespaces is None:
        return
    
    if not isinstance(namespaces, list):
        raise ValidationError(f"Namespaces must be a list, got {type(namespaces).__name__}")
    
    if len(namespaces) > 100:
        raise ValidationError(f"Too many namespaces: {len(namespaces)} (max 100)")
    
    for ns in namespaces:
        validate_namespace(ns)
