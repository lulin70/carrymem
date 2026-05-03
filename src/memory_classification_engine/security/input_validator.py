"""
Input Validation Module for CarryMem

Provides comprehensive input validation to prevent security vulnerabilities
including SQL injection, XSS, path traversal, and command injection.

Author: CarryMem Security Team
Date: 2026-04-25
Version: 1.0.0
"""

import re
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import html

from memory_classification_engine.exceptions import ValidationError


class InputValidator:
    """
    Comprehensive input validator for CarryMem
    
    Validates all user inputs to prevent security vulnerabilities.
    """
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(DROP\s+TABLE|DROP\s+DATABASE)\b)",
        r"(;\s*(DROP|DELETE|TRUNCATE|ALTER)\b)",
        r"(\bUNION\b\s+\bSELECT\b)",
        r"(1\s*=\s*1\b)",
        r"('\s*(OR|AND)\s+')",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.",
        r"~",
        r"/etc/",
        r"/proc/",
        r"/sys/",
        r"C:\\",
        r"\\\\",
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"\$\(",
        r"`[^`]*`",
        r">\s*/dev/",
        r"\b(rm|chmod|chown|wget|curl)\s+-",
    ]
    
    # Maximum lengths
    MAX_CONTENT_LENGTH = 10000  # 10KB
    MAX_QUERY_LENGTH = 1000
    MAX_NAMESPACE_LENGTH = 100
    MAX_PATH_LENGTH = 500
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator
        
        Args:
            strict_mode: If True, applies stricter validation rules
        """
        self.strict_mode = strict_mode
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for better performance"""
        self.sql_regex = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self.xss_regex = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]
        self.path_regex = [re.compile(p, re.IGNORECASE) for p in self.PATH_TRAVERSAL_PATTERNS]
        self.cmd_regex = [re.compile(p) for p in self.COMMAND_INJECTION_PATTERNS]
    
    def validate_content(self, content: str, field_name: str = "content") -> str:
        """
        Validate memory content
        
        Args:
            content: Content to validate
            field_name: Name of the field (for error messages)
            
        Returns:
            Sanitized content
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(content, str):
            raise ValidationError(f"{field_name} must be a string")
        
        # Check length
        if len(content) > self.MAX_CONTENT_LENGTH:
            raise ValidationError(
                f"{field_name} exceeds maximum length of {self.MAX_CONTENT_LENGTH} characters"
            )
        
        # Check for empty content
        if not content.strip():
            raise ValidationError(f"{field_name} cannot be empty")
        
        # Check for SQL injection
        if self._contains_sql_injection(content):
            raise ValidationError(f"{field_name} contains potential SQL injection patterns")
        
        # Check for command injection
        if self._contains_command_injection(content):
            raise ValidationError(f"{field_name} contains potential command injection patterns")
        
        # Check for XSS in strict mode
        if self.strict_mode and self._contains_xss(content):
            raise ValidationError(f"{field_name} contains potential XSS patterns")
        
        # Sanitize and return
        return self._sanitize_content(content)
    
    def validate_query(self, query: str) -> str:
        """
        Validate search query
        
        Args:
            query: Query string to validate
            
        Returns:
            Sanitized query
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(query, str):
            raise ValidationError("Query must be a string")
        
        # Check length
        if len(query) > self.MAX_QUERY_LENGTH:
            raise ValidationError(
                f"Query exceeds maximum length of {self.MAX_QUERY_LENGTH} characters"
            )
        
        # Allow empty queries (returns all)
        if not query.strip():
            return ""
        
        # Check for SQL injection
        if self._contains_sql_injection(query):
            raise ValidationError("Query contains potential SQL injection patterns")
        
        # Check for command injection
        if self._contains_command_injection(query):
            raise ValidationError("Query contains potential command injection patterns")
        
        return self._sanitize_content(query)
    
    def validate_namespace(self, namespace: str) -> str:
        """
        Validate namespace
        
        Args:
            namespace: Namespace to validate
            
        Returns:
            Sanitized namespace
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(namespace, str):
            raise ValidationError("Namespace must be a string")
        
        # Check length
        if len(namespace) > self.MAX_NAMESPACE_LENGTH:
            raise ValidationError(
                f"Namespace exceeds maximum length of {self.MAX_NAMESPACE_LENGTH} characters"
            )
        
        # Check format (alphanumeric, dash, underscore only)
        if not re.match(r'^[a-zA-Z0-9_-]+$', namespace):
            raise ValidationError(
                "Namespace can only contain letters, numbers, dashes, and underscores"
            )
        
        return namespace.lower()
    
    def validate_path(self, path: str, must_exist: bool = False) -> Path:
        """
        Validate file path
        
        Args:
            path: Path to validate
            must_exist: If True, path must exist
            
        Returns:
            Validated Path object
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(path, str):
            raise ValidationError("Path must be a string")
        
        # Check length
        if len(path) > self.MAX_PATH_LENGTH:
            raise ValidationError(
                f"Path exceeds maximum length of {self.MAX_PATH_LENGTH} characters"
            )
        
        # Check for path traversal
        if self._contains_path_traversal(path):
            raise ValidationError("Path contains potential path traversal patterns")
        
        # Convert to Path object
        try:
            path_obj = Path(path).resolve()
        except (ValueError, OSError) as e:
            raise ValidationError(f"Invalid path: {e}")
        
        # Check if path exists (if required)
        if must_exist and not path_obj.exists():
            raise ValidationError(f"Path does not exist: {path}")
        
        # Check if path is within allowed directories
        if self.strict_mode:
            self._validate_path_location(path_obj)
        
        return path_obj
    
    def validate_memory_type(self, memory_type: str) -> str:
        """
        Validate memory type
        
        Args:
            memory_type: Memory type to validate
            
        Returns:
            Validated memory type
            
        Raises:
            ValidationError: If validation fails
        """
        valid_types = [
            "user_preference",
            "correction",
            "fact_declaration",
            "decision",
            "relationship",
            "task_pattern",
            "sentiment_marker",
        ]
        
        if memory_type not in valid_types:
            raise ValidationError(
                f"Invalid memory type. Must be one of: {', '.join(valid_types)}"
            )
        
        return memory_type
    
    def validate_confidence(self, confidence: float) -> float:
        """
        Validate confidence score
        
        Args:
            confidence: Confidence score to validate
            
        Returns:
            Validated confidence score
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(confidence, (int, float)):
            raise ValidationError("Confidence must be a number")
        
        if not 0.0 <= confidence <= 1.0:
            raise ValidationError("Confidence must be between 0.0 and 1.0")
        
        return float(confidence)
    
    def validate_limit(self, limit: int) -> int:
        """
        Validate result limit
        
        Args:
            limit: Limit to validate
            
        Retur       Validated limit
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(limit, int):
            raise ValidationError("Limit must be an integer")
        
        if limit < 1:
            raise ValidationError("Limit must be at least 1")
        
        if limit > 1000:
            raise ValidationError("Limit cannot exceed 1000")
        
        return limit
    
    def validate_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate filter dictionary
        
        Args:
            filters: Filters to validate
            
        Returns:
            Validated filters
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(filters, dict):
            raise ValidationError("Filters must be a dictionary")
        
        valid_filter_keys = ["type", "namespace", "min_confidence", "max_age_days"]
        
        for key in filters.keys():
            if key not in valid_filter_keys:
                raise ValidationError(f"Invalid filter key: {key}")
        
        # Validate individual filter values
        validated = {}
        
        if "type" in filters:
            validated["type"] = self.validate_memory_type(filters["type"])
        
        if "namespace" in filters:
            validated["namespace"] = self.validate_namespace(filters["namespace"])
        
        if "min_confidence" in filters:
            validated["min_confidence"] = self.validate_confidence(filters["min_confidence"])
        
        if "max_age_days" in filters:
            if not isinstance(filters["max_age_days"], int) or filters["max_age_days"] < 0:
                raise ValidationError("max_age_days must be a non-negative integer")
            validated["max_age_days"] = filters["max_age_days"]
        
        return validated
    
    # Private helper methods
    
    def _contains_sql_injection(self, text: str) -> bool:
        """Check if text contains SQL injection patterns"""
        for pattern in self.sql_regex:
            if pattern.search(text):
                return True
        return False
    
    def _contains_xss(self, text: str) -> bool:
        """Check if text contains XSS patterns"""
        for pattern in self.xss_regex:
            if pattern.search(text):
                return True
        return False
    
    def _contains_path_traversal(self, text: str) -> bool:
        """Check if text contains path traversal patterns"""
        for pattern in self.path_regex:
            if pattern.search(text):
                return True
        return False
    
    def _contains_command_injection(self, text: str) -> bool:
        """Check if text contains command injection patterns"""
        for pattern in self.cmd_regex:
            if pattern.search(text):
                return True
        return False
    
    def _sanitize_content(self, content: str) -> str:
        """
        Sanitize content by escaping special characters
        
        Args:
            content: Content to sanitize
            
        Returns:
            Sanitized content
        """
        # Remove null bytes
        content = content.replace('\x00', '')
        
        # Normalize whitespace
        content = ' '.join(content.split())
        
        # In strict mode, escape HTML
        if self.strict_mode:
            content = html.escape(content)
        
        return content
    
    def _validate_path_location(self, path: Path):
        """
        Validate that path is within allowed directories
        
        Args:
            path: Path to validate
            
        Raises:
            ValidationError: If path is outside allowed directories
        """
        # Get user's home directory
        home_dir = Path.home()
        
        # Check if path is within home directory or temp directory
        try:
            path.relative_to(home_dir)
            return  # Path is within home directory
        except ValueError:
            pass
        
        # Check if path is within temp directory
        import tempfile
        temp_dir = Path(tempfile.gettempdir())
        try:
            path.relative_to(temp_dir)
            return  # Path is within temp directory
        except ValueError:
            pass
        
        # Path is outside allowed directories
        raise ValidationError(
            f"Path is outside allowed directories: {path}"
        )


# Global validator instance
_default_validator = None


def get_validator(strict_mode: bool = True) -> InputValidator:
    """
    Get global validator instance
    
    Args:
        strict_mode: If True, uses strict validation
        
    Returns:
        InputValidator instance
    """
    global _default_validator
    if _default_validator is None:
        _default_validator = InputValidator(strict_mode=strict_mode)
    return _default_validator


# Convenience functions

def validate_content(content: str) -> str:
    """Validate memory content"""
    return get_validator().validate_content(content)


def validate_query(query: str) -> str:
    """Validate search query"""
    return get_validator().validate_query(query)


def validate_namespace(namespace: str) -> str:
    """Validate namespace"""
    return get_validator().validate_namespace(namespace)


def validate_path(path: str, must_exist: bool = False) -> Path:
    """Validate file path"""
    return get_validator().validate_path(path, must_exist)


def validate_memory_type(memory_type: str) -> str:
    """Validate memory type"""
    return get_validator().validate_memory_type(memory_type)


def validate_confidence(confidence: float) -> float:
    """Validate confidence score"""
    return get_validator().validate_confidence(confidence)


def validate_limit(limit: int) -> int:
    """Validate result limit"""
    return get_validator().validate_limit(limit)


def validate_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Validate filter dictionary"""
    return get_validator().validate_filters(filters)
