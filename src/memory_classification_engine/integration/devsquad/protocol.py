from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class MemoryProvider(Protocol):
    def get_rules(self, user_id: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        ...

    def add_rule(self, user_id: str, rule: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        ...

    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None:
        ...

    def delete_rule(self, user_id: str, rule_id: str) -> None:
        ...

    def is_available(self) -> bool:
        ...

    def get_stats(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class CarryMemAdapter(Protocol):
    def is_available(self) -> bool:
        ...

    def match_rules(
        self,
        task_description: str,
        user_id: str,
        role: Optional[str] = None,
        max_rules: int = 5,
    ) -> List[Dict[str, Any]]:
        ...

    def format_rules_as_prompt(self, rules: List[Dict[str, Any]]) -> str:
        ...

    def log_experience(
        self,
        user_id: str,
        role: Optional[str],
        task: str,
        rules_applied: List[str],
        outcome: str,
        user_feedback: Optional[str] = None,
    ) -> str:
        ...
