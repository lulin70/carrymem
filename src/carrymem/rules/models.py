"""
CarryMem Rules Engine — Domain Models

Defines the core data structures for the rules system:
- Rule: Behavioral contract (condition → action)
- RuleType, RuleStatus, DerivationSource: Type enumerations
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _to_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


# Type aliases for better readability and type safety
RuleType = str  # Literal["avoid", "always", "prefer", "forbid", "format"]
RuleStatus = str  # Literal["active", "paused", "deprecated"]
DerivationSource = str  # Literal["manual", "auto_promotion", "failure_lesson", "refined"]
RuleScope = str  # Literal["personal", "company", "negotiated"]


# Valid enum values for validation
VALID_RULE_TYPES = {"avoid", "always", "prefer", "forbid", "format"}
VALID_RULE_STATUSES = {"active", "paused", "deprecated"}
VALID_DERIVATION_SOURCES = {
    "manual",
    "auto_promotion",
    "failure_lesson",
    "refined",
    "refinement_session",
}
VALID_RULE_SCOPES = {"personal", "company", "negotiated"}
SCOPE_PRIORITY = {"company": 3, "negotiated": 2, "personal": 1}


@dataclass
class Rule:
    """
    Represents a behavioral contract: condition → action

    A rule defines how an AI should behave in specific scenarios.
    It transforms passive memory into active behavioral instructions.

    Attributes:
        id: Unique identifier (format: "rule_" + UUID8)
        trigger: Natural language scene description that activates this rule
        action: Specific behavior instruction to execute when triggered
        rule_type: Category of the rule (avoid/always/prefer/forbid/format)
        source_memories: IDs of source memories if this rule was derived from memories
        derived_from: How this rule was created (manual/auto/failure/refined)
        status: Current lifecycle state (active/paused/deprecated)
        override: If True, AI cannot ignore this rule; if False, it's a soft preference
        confidence: Certainty score (0.0-1.0) for auto-classified rules
        trigger_count: Number of times this rule has been matched
        confirmed_by_user: Whether user explicitly confirmed this rule
        created_at: ISO 8601 UTC timestamp of creation
        updated_at: ISO 8601 UTC timestamp of last update
        metadata: Custom key-value pairs for extensibility
    """

    # === Identity ===
    id: str = field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")

    # === Core Fields (Required) ===
    trigger: str = ""
    action: str = ""
    rule_type: RuleType = "avoid"

    # === Metadata ===
    source_memories: List[str] = field(default_factory=list)
    derived_from: DerivationSource = "manual"

    # === State Management ===
    status: RuleStatus = "active"
    override: bool = True
    confidence: float = 0.8
    trigger_count: int = 0
    confirmed_by_user: bool = True
    scope: RuleScope = "personal"

    # === Timestamps ===
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""

    # === Conditional Logic ===
    condition: str = ""

    # === Extension Point ===
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate fields after initialization"""
        self._validate_types()

    def _validate_types(self):
        """Validate enum-type fields have valid values"""
        if self.rule_type not in VALID_RULE_TYPES:
            raise ValueError(f"Invalid rule_type '{self.rule_type}'. " f"Must be one of {VALID_RULE_TYPES}")

        if self.status not in VALID_RULE_STATUSES:
            raise ValueError(f"Invalid status '{self.status}'. " f"Must be one of {VALID_RULE_STATUSES}")

        if self.derived_from not in VALID_DERIVATION_SOURCES:
            raise ValueError(
                f"Invalid derived_from '{self.derived_from}'. " f"Must be one of {VALID_DERIVATION_SOURCES}"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

        if self.trigger_count < 0:
            raise ValueError(f"trigger_count cannot be negative: {self.trigger_count}")

        if self.scope not in VALID_RULE_SCOPES:
            raise ValueError(f"Invalid scope '{self.scope}'. " f"Must be one of {VALID_RULE_SCOPES}")

    def to_dict(self) -> dict:
        """
        Serialize rule to dictionary for SQLite storage.

        Returns:
            Dictionary representation suitable for JSON/storage
        """
        return {
            "id": self.id,
            "trigger": self.trigger,
            "action": self.action,
            "rule_type": self.rule_type,
            "source_memories": self.source_memories,
            "derived_from": self.derived_from,
            "status": self.status,
            "override": 1 if self.override else 0,
            "confidence": self.confidence,
            "trigger_count": self.trigger_count,
            "confirmed_by_user": 1 if self.confirmed_by_user else 0,
            "scope": self.scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "condition": self.condition,
            "metadata": self.metadata,
        }

    def is_expired(self) -> bool:
        """Return True if this rule's expiry timestamp has passed."""
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return now > expires
        except (ValueError, TypeError):
            return False

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        """
        Deserialize rule from dictionary (SQLite storage).

        Args:
            data: Dictionary containing rule data

        Returns:
            Rule instance
        """
        source_memories = data.get("source_memories", [])
        if isinstance(source_memories, str):
            import json

            try:
                source_memories = json.loads(source_memories)
            except (json.JSONDecodeError, TypeError):
                source_memories = []

        metadata = data.get("metadata", {})
        if isinstance(metadata, str):
            import json

            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        return cls(
            id=data.get("id", ""),
            trigger=data.get("trigger", ""),
            action=data.get("action", ""),
            rule_type=data.get("rule_type", "avoid"),
            source_memories=source_memories,
            derived_from=data.get("derived_from", "manual"),
            status=data.get("status", "active"),
            override=_to_bool(data.get("override", 1)),
            confidence=float(data.get("confidence", 0.8)),
            trigger_count=int(data.get("trigger_count", 0)),
            confirmed_by_user=_to_bool(data.get("confirmed_by_user", 1)),
            scope=data.get("scope", "personal"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            expires_at=data.get("expires_at", ""),
            condition=data.get("condition", ""),
            metadata=metadata,
        )

    def touch(self):
        """Update the updated_at timestamp to current time"""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def increment_trigger_count(self):
        """Increment the trigger match counter by 1"""
        self.trigger_count += 1
        self.touch()

    def activate(self):
        """Set rule status to active"""
        self.status = "active"
        self.touch()

    def pause(self):
        """Set rule status to paused"""
        self.status = "paused"
        self.touch()

    def deprecate(self):
        """Mark rule as deprecated (no longer recommended)"""
        self.status = "deprecated"
        self.touch()

    def is_active(self) -> bool:
        """Check if rule is currently active"""
        return self.status == "active"

    def is_hard_rule(self) -> bool:
        """Check if this is a hard rule (cannot be ignored)"""
        return self.override

    def __repr__(self) -> str:
        return f"Rule(id={self.id}, trigger='{self.trigger}', " f"type={self.rule_type}, status={self.status})"

    def summary(self) -> str:
        """Generate human-readable summary for display"""
        override_str = "Hard" if self.override else "Soft"
        return (
            f"[{self.id}] {self.rule_type.upper()}: "
            f"'{self.trigger}' → '{self.action}' "
            f"({override_str}, {self.status})"
        )
