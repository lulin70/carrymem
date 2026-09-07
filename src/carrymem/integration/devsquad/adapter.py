import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from carrymem.rules import RuleEngine
from carrymem.security.audit import AuditLogger
from carrymem.utils.logger import logger

from .type_mapping import (
    carrymem_rule_to_devsquad_dict,
    carrymem_to_devsquad_type,
    devsquad_rule_to_carrymem_params,
)


class DevSquadAdapter:
    """CarryMem adapter implementing DevSquad MemoryProvider + CarryMemAdapter protocols.

    Usage:
        adapter = DevSquadAdapter(db_path="/path/to/carrymem.db")
        if adapter.is_available():
            rules = adapter.match_rules("Design REST API", "user1", role="architect")
            prompt = adapter.format_rules_as_prompt(rules)

    RuleEngine consolidation (P1-A2): when the host already owns a CarryMem
    instance, pass ``rule_engine=carrymem.rule_engine`` so the adapter reuses
    the facade's canonical instance instead of building a second engine over
    the same SQLite DB. When omitted (standalone usage), the adapter creates
    its own engine on ``db_path`` as before.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        namespace: str = "default",
        rule_engine: Optional[RuleEngine] = None,
    ):
        self._db_path = db_path or ":memory:"
        self._namespace = namespace
        self._rule_engine: Optional[RuleEngine] = None
        self._audit: Optional[AuditLogger] = None
        self._init_error: Optional[str] = None
        self._init(rule_engine)

    def _init(self, injected_engine: Optional[RuleEngine] = None):
        try:
            if injected_engine is not None:
                self._rule_engine = injected_engine
            else:
                self._rule_engine = RuleEngine(self._db_path)
            self._audit = AuditLogger(
                persist_path=self._db_path,
            )
        except Exception as e:
            self._init_error = str(e)
            self._rule_engine = None
            self._audit = None

    def is_available(self) -> bool:
        """Return whether the rule engine is initialized and responsive."""
        if self._rule_engine is None:
            return False
        try:
            self._rule_engine.count_rules()
            return True
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.warning("Health check failed: %s", e)
            return False

    def get_rules(self, user_id: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Return formatted rule strings matching the user and context."""
        if not self.is_available():
            return []
        assert self._rule_engine is not None
        try:
            scene = ""
            if context:
                scene = context.get("task", "")
                role = context.get("role", "")
                if role:
                    scene = f"{scene} {role}".strip()
            matched = self._rule_engine.match(scene_description=scene or "all", limit=50)
            result = []
            for m in matched:
                rule = m.rule if hasattr(m, "rule") else m
                rule_type = carrymem_to_devsquad_type(getattr(rule, "rule_type", "avoid"))
                override = " (override)" if getattr(rule, "override", False) else ""
                result.append(f"[{rule_type.upper()}] {getattr(rule, 'action', str(rule))}{override}")
            self._log("get_rules", user_id, success=True)
            return result
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as e:
            self._log("get_rules", user_id, success=False, details={"error": str(e)})
            return []

    def add_rule(self, user_id: str, rule: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a rule derived from the DevSquad rule string and metadata."""
        if not self.is_available():
            return
        assert self._rule_engine is not None
        try:
            params = devsquad_rule_to_carrymem_params(rule, metadata)
            if not params["trigger"]:
                params["trigger"] = rule[:100]
            self._rule_engine.add_rule(**params)
            self._log("add_rule", user_id, success=True, details={"rule": rule[:100]})
        except (ValueError, TypeError, sqlite3.Error) as e:
            self._log("add_rule", user_id, success=False, details={"error": str(e)})

    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None:
        """Update the action text of an existing rule."""
        if not self.is_available():
            return
        assert self._rule_engine is not None
        try:
            self._rule_engine.update_rule(rule_id, action=rule)
            self._log(
                "update_rule",
                user_id,
                storage_key=rule_id,
                success=True,
                details={"rule": rule[:100]},
            )
        except (ValueError, KeyError, sqlite3.Error) as e:
            self._log(
                "update_rule",
                user_id,
                storage_key=rule_id,
                success=False,
                details={"error": str(e)},
            )

    def delete_rule(self, user_id: str, rule_id: str) -> None:
        """Delete the rule identified by ``rule_id``."""
        if not self.is_available():
            return
        assert self._rule_engine is not None
        try:
            self._rule_engine.delete_rule(rule_id)
            self._log("delete_rule", user_id, storage_key=rule_id, success=True)
        except (KeyError, sqlite3.Error) as e:
            self._log(
                "delete_rule",
                user_id,
                storage_key=rule_id,
                success=False,
                details={"error": str(e)},
            )

    def get_stats(self) -> Dict[str, Any]:
        """Return rule engine statistics with availability and namespace."""
        if not self.is_available():
            return {
                "total_rules": 0,
                "total_users": 0,
                "available": False,
                "namespace": self._namespace,
            }
        assert self._rule_engine is not None
        try:
            stats = self._rule_engine.get_stats()
            stats["available"] = True
            stats["namespace"] = self._namespace
            return stats
        except sqlite3.Error:
            return {
                "total_rules": 0,
                "total_users": 0,
                "available": False,
                "namespace": self._namespace,
            }

    def match_rules(
        self,
        task_description: str,
        user_id: str,
        role: Optional[str] = None,
        max_rules: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return DevSquad-formatted rules matching the task and user."""
        if not self.is_available():
            return []
        assert self._rule_engine is not None
        try:
            scene = task_description or ""
            if role:
                scene = f"{scene} {role}".strip()
            matched = self._rule_engine.match(scene_description=scene, limit=max_rules)
            result = []
            for m in matched:
                rule = m.rule if hasattr(m, "rule") else m
                d = carrymem_rule_to_devsquad_dict(rule)
                if hasattr(m, "score"):
                    d["relevance_score"] = m.score
                result.append(d)
            self._log(
                "match_rules",
                user_id,
                success=True,
                details={"task": task_description[:100], "matched": len(result)},
            )
            return result
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as e:
            self._log(
                "match_rules",
                user_id,
                success=False,
                details={"error": str(e)},
            )
            return []

    def format_rules_as_prompt(self, rules: List[Dict[str, Any]]) -> str:
        """Format matched rules into a prompt-ready Markdown string."""
        if not rules:
            return ""
        try:
            lines = []
            override_rules = [r for r in rules if r.get("override", False)]
            normal_rules = [r for r in rules if not r.get("override", False)]
            if override_rules:
                lines.append("## Mandatory Rules (Cannot Override)")
                for r in override_rules:
                    rt = r.get("rule_type", "avoid").upper()
                    lines.append(f"- [{rt}] {r.get('action', r.get('trigger', ''))}")
            if normal_rules:
                lines.append("## Guidelines")
                for r in normal_rules:
                    rt = r.get("rule_type", "avoid").upper()
                    lines.append(f"- [{rt}] {r.get('action', r.get('trigger', ''))}")
            return "\n".join(lines)
        except (KeyError, ValueError, TypeError):
            return ""

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
        if not self.is_available():
            return ""
        try:
            exp_id = f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            details = {
                "role": role,
                "task": task[:200],
                "rules_applied": rules_applied[:10],
                "outcome": outcome[:200],
                "user_feedback": user_feedback[:200] if user_feedback else None,
            }
            self._log(
                "log_experience",
                user_id,
                success=True,
                details=details,
            )
            return exp_id
        except (ValueError, TypeError) as e:
            self._log(
                "log_experience",
                user_id,
                success=False,
                details={"error": str(e)},
            )
            return ""

    def _log(
        self,
        operation: str,
        user_id: str,
        storage_key: str = "",
        success: bool = True,
        details: Optional[Dict] = None,
    ):
        if self._audit:
            try:
                self._audit.log_operation(
                    operation=operation,
                    storage_key=storage_key,
                    success=success,
                    details=details,
                )
            except (ValueError, TypeError, sqlite3.Error):
                pass
