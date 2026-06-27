from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class MemoryProvider(Protocol):
    """Provider protocol exposing rule CRUD and availability/stats queries."""

    def get_rules(self, user_id: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Return the rules for the given user, optionally filtered by context."""

    def add_rule(self, user_id: str, rule: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a rule for the given user."""

    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None:
        """Update an existing rule identified by ``rule_id``."""

    def delete_rule(self, user_id: str, rule_id: str) -> None:
        """Delete the rule identified by ``rule_id``."""

    def is_available(self) -> bool:
        """Return whether the provider is ready to serve requests."""

    def get_stats(self) -> Dict[str, Any]:
        """Return provider statistics as a mapping."""


@runtime_checkable
class CarryMemAdapter(Protocol):
    """Adapter protocol exposing rule matching, prompt formatting, and experience logging."""

    def is_available(self) -> bool:
        """Return whether the adapter is ready to serve requests."""

    def match_rules(
        self,
        task_description: str,
        user_id: str,
        role: Optional[str] = None,
        max_rules: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return matching rules for the given task and user."""

    def format_rules_as_prompt(self, rules: List[Dict[str, Any]]) -> str:
        """Format a list of rules into a prompt-ready string."""

    def log_experience(
        self,
        user_id: str,
        role: Optional[str],
        task: str,
        rules_applied: List[str],
        outcome: str,
        user_feedback: Optional[str] = None,
    ) -> str:
        """Log an experience entry recording rules applied and the outcome."""
