"""Enhanced audit logging system for CarryMem (P2-5).

Provides thread-safe, structured audit trail for all critical operations:
- Memory CRUD operations (READ/WRITE/DELETE)
- Permission checks (DENIED events)
- Configuration changes (CONFIG events like key rotation)

Design principles:
- Append-only: no UPDATE or DELETE on audit events
- Thread-safe: uses threading.Lock for concurrent access
- Queryable: by time range, action type, user, result
- Exportable: JSON and CSV formats
"""

import csv
import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict, List, Optional

_audit_logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    """Audit event data class.

    Attributes:
        timestamp: When the event occurred (UTC).
        user_id: Who performed the action (None for system/anonymous).
        action: Action type (READ/WRITE/DELETE/ADMIN/CONFIG).
        resource: What was affected (memory/classifier/rule etc.).
        result: Outcome (SUCCESS/FAILURE/DENIED).
        details: Additional context as dictionary.
        ip_address: Client IP address (reserved for future use).
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    action: str = "READ"
    resource: str = ""
    result: str = "SUCCESS"
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "details": self.details,
            "ip_address": self.ip_address,
        }


@dataclass
class AuditFilter:
    """Filter criteria for querying audit events.

    All fields are optional; only non-None fields are applied as filters.
    """

    action: Optional[str] = None
    user_id: Optional[str] = None
    resource: Optional[str] = None
    result: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = 100


class AuditLogger:
    """Thread-safe enhanced audit logger.

    Maintains an in-memory event store with optional persistence.
    Supports logging, filtering, exporting (JSON/CSV), and cleanup.

    Usage::

        logger = AuditLogger()
        logger.log(AuditEvent(
            action="WRITE",
            resource="memory",
            user_id="user123",
            details={"storage_key": "mem_001"}
        ))

        # Query with filters
        events = logger.query(AuditFilter(action="WRITE", limit=10))

        # Export to JSON/CSV
        json_str = logger.export("json")
        csv_str = logger.export("csv")

        # Clean old events
        removed = logger.clear(older_than=timedelta(days=30))
    """

    def __init__(self, max_events: int = 10000):
        """Initialize the audit logger.

        Args:
            max_events: Maximum number of events to keep in memory.
                        When exceeded, oldest events are automatically pruned.
        """
        self._events: List[AuditEvent] = []
        self._lock = threading.RLock()
        self._max_events = max_events

    def log(self, event: AuditEvent) -> None:
        """Log an audit event.

        Thread-safe. Automatically prunes old events if max_events is exceeded.

        Args:
            event: The audit event to record.
        """
        with self._lock:
            self._events.append(event)
            # Auto-prune if over limit
            if len(self._events) > self._max_events:
                excess = len(self._events) - self._max_events
                self._events = self._events[excess:]
            _audit_logger.debug(
                "Audit log: %s %s %s -> %s [%s]",
                event.action,
                event.resource,
                event.user_id or "system",
                event.result,
                event.timestamp.isoformat(),
            )

    def log_operation(
        self,
        operation: str,
        *,
        storage_key: Optional[str] = None,
        memory_type: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Convenience method for CRUD-layer audit logging.

        Bridges the legacy ``log_operation()`` call pattern (used by
        ``adapters/sqlite/crud.py``) with the new AuditEvent-based API.

        Args:
            operation: Operation name (e.g. "remember", "forget").
            storage_key: The memory storage key being operated on.
            memory_type: Type classification of the memory entry.
            success: Whether the operation succeeded.
            details: Arbitrary extra context.
        """
        event = AuditEvent(
            action=operation,
            resource=storage_key or "unknown",
            user_id=None,
            result="SUCCESS" if success else "FAILURE",
            details=details or {},
        )
        self.log(event)

    def query(self, filter_: Optional[AuditFilter] = None) -> List[AuditEvent]:
        """Query audit events with optional filters.

        Args:
            filter_: Filter criteria. If None, returns all events up to default limit.

        Returns:
            List of matching AuditEvent objects, sorted by timestamp descending.
        """
        if filter_ is None:
            filter_ = AuditFilter()

        with self._lock:
            results = []
            for event in reversed(self._events):  # Newest first
                if filter_.action and event.action != filter_.action:
                    continue
                if filter_.user_id and event.user_id != filter_.user_id:
                    continue
                if filter_.resource and event.resource != filter_.resource:
                    continue
                if filter_.result and event.result != filter_.result:
                    continue
                if filter_.since and event.timestamp < filter_.since:
                    continue
                if filter_.until and event.timestamp > filter_.until:
                    continue
                results.append(event)
                if len(results) >= filter_.limit:
                    break
            return results

    def export(self, format: str = "json") -> str:
        """Export all audit events to string.

        Args:
            format: Export format, either "json" or "csv".

        Returns:
            Serialized string representation of all events.

        Raises:
            ValueError: If format is not "json" or "csv".
        """
        format = format.lower()
        with self._lock:
            events_data = [e.to_dict() for e in self._events]

        if format == "json":
            return json.dumps(events_data, indent=2, ensure_ascii=False, default=str)
        elif format == "csv":
            output = StringIO()
            if not events_data:
                return ""
            writer = csv.DictWriter(output, fieldnames=[
                "timestamp", "user_id", "action", "resource", "result",
                "details", "ip_address",
            ])
            writer.writeheader()
            for row in events_data:
                # Serialize dict fields for CSV
                row_copy = row.copy()
                if isinstance(row_copy.get("details"), dict):
                    row_copy["details"] = json.dumps(row_copy["details"], ensure_ascii=False)
                writer.writerow(row_copy)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}. Use 'json' or 'csv'.")

    def clear(self, older_than: Optional[timedelta] = None) -> int:
        """Remove audit events.

        Args:
            older_than: If provided, only remove events older than this duration.
                       If None, removes ALL events.

        Returns:
            Number of events removed.
        """
        with self._lock:
            if older_than is None:
                count = len(self._events)
                self._events.clear()
                _audit_logger.info("Cleared all %d audit events", count)
                return count

            cutoff = datetime.now(timezone.utc) - older_than
            before_count = len(self._events)
            self._events = [e for e in self._events if e.timestamp >= cutoff]
            removed = before_count - len(self._events)
            _audit_logger.info("Cleared %d audit events older than %s", removed, older_than)
            return removed

    @property
    def event_count(self) -> int:
        """Return current number of stored events."""
        with self._lock:
            return len(self._events)

    def get_stats(self) -> Dict[str, Any]:
        """Return statistics about the audit log.

        Returns:
            Dictionary with total count, counts by action, by result,
            and timestamp of most recent event.
        """
        with self._lock:
            total = len(self._events)
            by_action: Dict[str, int] = {}
            by_result: Dict[str, int] = {}
            last_event = None

            for event in self._events:
                by_action[event.action] = by_action.get(event.action, 0) + 1
                by_result[event.result] = by_result.get(event.result, 0) + 1
                if last_event is None or event.timestamp > last_event.timestamp:
                    last_event = event

            return {
                "total_events": total,
                "by_action": by_action,
                "by_result": by_result,
                "last_event": last_event.to_dict() if last_event else None,
                "max_capacity": self._max_events,
                "utilization_pct": round(total / self._max_events * 100, 1) if self._max_events > 0 else 0,
            }


# ── Global singleton instance ───────────────────────────────────────

_global_logger: Optional[AuditLogger] = None
_global_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get or create the global AuditLogger singleton."""
    global _global_logger
    if _global_logger is None:
        with _global_lock:
            if _global_logger is None:
                _global_logger = AuditLogger()
    return _global_logger


def reset_audit_logger() -> None:
    """Reset the global audit logger (mainly for testing)."""
    global _global_logger
    with _global_lock:
        _global_logger = None


# ── Convenience helpers for common operations ──────────────────────

def log_write(
    resource: str,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    result: str = "SUCCESS",
) -> None:
    """Log a WRITE operation."""
    get_audit_logger().log(AuditEvent(
        action="WRITE",
        resource=resource,
        user_id=user_id,
        result=result,
        details=details or {},
    ))


def log_read(
    resource: str,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    result: str = "SUCCESS",
) -> None:
    """Log a READ operation."""
    get_audit_logger().log(AuditEvent(
        action="READ",
        resource=resource,
        user_id=user_id,
        result=result,
        details=details or {},
    ))


def log_delete(
    resource: str,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    result: str = "SUCCESS",
) -> None:
    """Log a DELETE operation."""
    get_audit_logger().log(AuditEvent(
        action="DELETE",
        resource=resource,
        user_id=user_id,
        result=result,
        details=details or {},
    ))


def log_denied(
    resource: str,
    user_id: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a permission DENIED event."""
    get_audit_logger().log(AuditEvent(
        action=action,
        resource=resource,
        user_id=user_id,
        result="DENIED",
        details=details or {},
    ))


def log_config(
    resource: str,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    result: str = "SUCCESS",
) -> None:
    """Log a CONFIG/Admin operation (e.g., key rotation)."""
    get_audit_logger().log(AuditEvent(
        action="CONFIG",
        resource=resource,
        user_id=user_id,
        result=result,
        details=details or {},
    ))
