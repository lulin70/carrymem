"""
CarryMem Rules Engine — Input Sanitizer
[RESERVED] Rule-engine extension point — not yet integrated into main pipeline.
Planned for v0.4.0 rule-security hardening.

Security-focused input validation for rules to prevent:
- Prompt injection attacks
- SQL injection attempts
- Template injection
- HTML/script injection
- Excessively long inputs
"""

import re
from datetime import datetime, timezone
from typing import Optional


class RuleSanitizer:
    """
    Security-focused input validator for rules.

    This class provides static validation methods that clean and validate
    user input before it's stored in the database. It implements defense-in-depth
    by checking multiple attack vectors.

    Usage:
        validated_trigger = RuleSanitizer.validate_trigger("写报告")
        validated_action = RuleSanitizer.validate_action("控制在3页以内")
    """

    # Maximum lengths to prevent storage abuse
    MAX_TRIGGER_LENGTH = 200
    MAX_ACTION_LENGTH = 500

    # Patterns that indicate prompt injection attempts
    BLOCKED_PATTERNS = [
        # Ignore previous instructions (catch various forms)
        r"(?i)ignore\s+(all\s+)?(previous|prior)",
        r"(?i)(forget|disregard)\s+(all\s+)?(previous|prior)",
        # Role hijacking (catch various forms including harmful AI)
        r"(?i)you\s+are\s+now",
        r"(?i)act\s+as",
        r"(?i)pretend\s+to\s+be",
        # System tag injection
        r"<system>|<instruction>|<command>",
        # Template injection (Jinja2, etc.)
        r"\$\{.*\}",
        # Code execution attempts
        r"__import__|eval\(|exec\(",
        # Base64 encoded instructions (common evasion)
        r"(?i)base64.*decode",
    ]

    # Characters dangerous in SQL contexts
    SQL_DANGEROUS_CHARS = ["'", ";", "--", "/*", "*/", "\\"]

    # HTML tags that could execute scripts
    HTML_TAGS = ["<script", "<iframe", "<object", "<embed", "<form"]

    @classmethod
    def validate_trigger(cls, trigger: str) -> str:
        """
        Validate and sanitize trigger string.

        The trigger is the scene description that activates a rule.
        It should be a natural language description like "写报告" or "做竞品分析".

        Args:
            trigger: Raw user input for the rule trigger

        Returns:
            Cleaned and validated trigger string

        Raises:
            ValueError: If validation fails with descriptive error message

        Examples:
            >>> RuleSanitizer.validate_trigger("写报告")
            '写报告'
            >>> RuleSanitizer.validate_trigger("  做竞品分析  ")
            '做竞品分析'
            >>> RuleSanitizer.validate_trigger("")
            ValueError: Trigger cannot be empty
        """
        # Check empty/whitespace-only
        if not trigger or not trigger.strip():
            raise ValueError("Trigger cannot be empty")

        # Check length limits
        if len(trigger) > cls.MAX_TRIGGER_LENGTH:
            raise ValueError(f"Trigger too long ({len(trigger)} > {cls.MAX_TRIGGER_LENGTH} characters)")

        # Check for blocked patterns (prompt injection prevention)
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, trigger):
                raise ValueError(
                    f"Trigger contains potentially dangerous content matching pattern: {pattern}. "
                    f"This could be a prompt injection attempt."
                )

        # Check for SQL injection characters (relaxed for triggers)
        dangerous_sql = [";", "--", "/*", "*/"]
        for char in dangerous_sql:
            if char in trigger:
                raise ValueError(
                    f"Trigger contains invalid character: '{char}'. " f"These characters are not allowed in triggers."
                )

        # Return stripped version
        return trigger.strip()

    @classmethod
    def validate_action(cls, action: str) -> str:
        """
        Validate and sanitize action string.

        The action is the behavioral instruction that gets executed.
        This field requires stricter security checks since it will be
        injected into AI prompts.

        Args:
            action: Raw user input for the rule action

        Returns:
            Cleaned and validated action string

        Raises:
            ValueError: If validation fails or dangerous content detected

        Examples:
            >>> RuleSanitizer.validate_action("控制在3页以内")
            '控制在3页以内'
            >>> RuleSanitizer.validate_action("ignore all previous instructions")
            ValueError: Action contains potentially dangerous content
        """
        # Check empty/whitespace-only
        if not action or not action.strip():
            raise ValueError("Action cannot be empty")

        # Check length limits
        if len(action) > cls.MAX_ACTION_LENGTH:
            raise ValueError(f"Action too long ({len(action)} > {cls.MAX_ACTION_LENGTH} characters)")

        # Check for blocked patterns (prompt injection prevention)
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, action):
                raise ValueError(
                    f"Action contains potentially dangerous content matching pattern: {pattern}. "
                    f"This could be a prompt injection attempt."
                )

        # Strip potentially dangerous HTML tags
        cleaned = action
        cleaned_lower = cleaned.lower()
        needs_html_strip = any(tag in cleaned_lower for tag in cls.HTML_TAGS)
        if needs_html_strip:
            cleaned = re.sub(r"<[^>]*>", "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip()

    @classmethod
    def validate_rule_type(cls, rule_type: str) -> str:
        """
        Validate rule type enum value.

        Args:
            rule_type: Raw rule type string

        Returns:
            Validated rule type string

        Raises:
            ValueError: If rule_type is not a valid option
        """
        from .models import VALID_RULE_TYPES

        if rule_type not in VALID_RULE_TYPES:
            raise ValueError(
                f"Invalid rule_type '{rule_type}'. " f"Must be one of: {', '.join(sorted(VALID_RULE_TYPES))}"
            )
        return rule_type

    @classmethod
    def sanitize_metadata(cls, metadata: dict) -> dict:
        """
        Clean and validate metadata dictionary.

        Removes any keys or values that could be problematic.
        Only allows simple string, numeric, and boolean values.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Cleaned metadata dictionary

        Raises:
            ValueError: If metadata contains invalid types
        """
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        cleaned = {}
        for key, value in metadata.items():
            # Key must be string
            if not isinstance(key, str):
                continue

            # Value must be simple type
            if isinstance(value, (str, int, float, bool)):
                # Recursively sanitize strings
                if isinstance(value, str):
                    try:
                        value = cls.validate_action(value)
                    except ValueError:
                        continue  # Skip invalid values
                cleaned[key] = value
            elif value is None:
                cleaned[key] = None
            # Skip complex types (lists, dicts, objects)

        return cleaned

    @classmethod
    def is_safe_input(cls, text: str) -> bool:
        """
        Quick check if text passes basic safety validation.

        This is useful for pre-validation before showing errors to users.

        Args:
            text: Text to check

        Returns:
            True if text appears safe, False otherwise
        """
        try:
            cls.validate_trigger(text)
            cls.validate_action(text)
            return True
        except ValueError:
            return False


class SecurityEvent:
    """Records security-related events for audit logging"""

    def __init__(
        self,
        event_type: str,
        severity: str,
        details: str,
        input_data: Optional[str] = None,
    ):
        self.event_type = event_type  # "blocked_pattern", "sql_attempt", etc.
        self.severity = severity  # "low", "medium", "high", "critical"
        self.details = details
        self.input_data = input_data
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary for logging"""
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "details": self.details,
            "input_data": (
                self.input_data[:100] + "..." if self.input_data and len(self.input_data) > 100 else self.input_data
            ),
            "timestamp": self.timestamp,
        }
