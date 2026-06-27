"""Maintenance: conflict detection, quality scoring, expiry, consolidation, scheduling."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from threading import Timer
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.constants import (
    BATCH_RECALL_LIMIT,
    CONSOLIDATION_MIN_INTERVAL_HOURS,
    DECAY_CONFIDENCE_FLOOR,
    DECAY_ROUNDING_PRECISION,
    DEFAULT_CONFIDENCE_SCORE,
    MAINTENANCE_CONTENT_SNIPPET_LENGTH,
    MIN_QUALITY_THRESHOLD,
    SECONDS_PER_HOUR,
)
from carrymem.core._lifecycle import StorageNotConfiguredError

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter
    from carrymem.rules import RuleEngine

logger = logging.getLogger(__name__)


class MaintenanceMixin:
    """Quality checks, conflict detection, consolidation, and scheduled maintenance."""

    # Shared instance state provided by LifecycleMixin.__init__.
    _adapter: Optional[StorageAdapter]
    _namespace: str
    _rule_engine: Optional[RuleEngine]
    _consolidation_timer: Optional[Timer]

    def check_conflicts(self) -> List[Dict[str, Any]]:
        """Detect conflicts among stored memories and rule engine rules."""
        from carrymem.conflict_detector import ConflictDetector

        if not self._adapter:
            raise StorageNotConfiguredError()

        all_conflicts: List[Dict[str, Any]] = []

        # Include superseded memories so contradictions between old and new can be detected
        all_memories = self._adapter.recall("", limit=BATCH_RECALL_LIMIT, filters={"include_superseded": True})
        if all_memories:
            detector = ConflictDetector()
            memory_conflicts = detector.detect_conflicts(all_memories)
            all_conflicts.extend(c.to_dict() for c in memory_conflicts)

        if self._rule_engine:
            rule_conflicts = self._rule_engine.check_conflicts()
            for rc in rule_conflicts:
                all_conflicts.append(
                    {
                        "conflict_type": rc.conflict_type.value,
                        "severity": rc.severity.value,
                        "reason": rc.reason,
                        "suggestion": rc.suggestion,
                        "rules": [
                            {"id": r.id, "trigger": r.trigger, "action": r.action, "scope": r.scope} for r in rc.rules
                        ],
                        "source": "rule_engine",
                    }
                )

        return all_conflicts

    def check_quality(self, min_score: float = MIN_QUALITY_THRESHOLD) -> List[Dict[str, Any]]:
        """Return memories whose quality score falls below ``min_score``."""
        from carrymem.quality_scorer import QualityAnalyzer

        if not self._adapter:
            raise StorageNotConfiguredError()

        all_memories = self._adapter.recall("", limit=BATCH_RECALL_LIMIT)
        if not all_memories:
            return []

        analyzer = QualityAnalyzer()
        low_quality = analyzer.identify_low_quality(all_memories, threshold=min_score)
        result = []
        for item in low_quality:
            result.append(
                {
                    "storage_key": item["storage_key"],
                    "score": item["score"],
                    "reasons": item["reasons"],
                    "content": item["memory"].content[:MAINTENANCE_CONTENT_SNIPPET_LENGTH],
                    "type": item["memory"].type,
                }
            )
        return result

    def list_expired(self) -> List[Dict[str, Any]]:
        """Return memories whose expiry timestamp has passed."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            return []

        conn = self._adapter._get_connection()  # Internal access for raw SQL query (maintenance operation)
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = conn.execute(
            "SELECT storage_key, content, type, expires_at FROM memories "
            "WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at < ?",
            (self._namespace, now_iso),
        ).fetchall()

        result = []
        for row in rows:
            content = row["content"]
            if self._adapter._security and self._adapter._security.is_active:  # type: ignore[attr-defined]
                content = self._adapter.decrypt_field(content)  # Use public API for decryption
            result.append(
                {
                    "storage_key": row["storage_key"],
                    "content": (content or "")[:MAINTENANCE_CONTENT_SNIPPET_LENGTH],
                    "type": row["type"],
                    "expires_at": row["expires_at"],
                }
            )
        return result

    def consolidate(self, dry_run: bool = True, run_p1: bool = True, run_p2: bool = True) -> Dict[str, Any]:
        """Run memory consolidation: dedup, decay, and cleanup."""
        from carrymem.consolidation import consolidate, consolidate_p1, consolidate_p2

        if not self._adapter:
            raise StorageNotConfiguredError()
        adapter = self._adapter

        all_entries = adapter.recall(
            query="",
            limit=10000,
            filters={"include_superseded": True},
        )
        all_memories = []
        for entry in all_entries:
            if hasattr(entry, "__dict__"):
                all_memories.append(
                    {
                        "storage_key": getattr(entry, "storage_key", ""),
                        "type": getattr(entry, "memory_type", ""),
                        "content": getattr(entry, "content", ""),
                        "confidence": getattr(entry, "confidence", DEFAULT_CONFIDENCE_SCORE),
                        "created_at": getattr(entry, "created_at", ""),
                        "superseded_at": getattr(entry, "superseded_at", None),
                        "access_count": getattr(entry, "access_count", 0),
                    }
                )
            elif isinstance(entry, dict):
                all_memories.append(entry)

        report = consolidate(all_memories)

        if dry_run:
            report["dry_run"] = True
            return report

        superseded_count = 0
        for item in report["to_supersede"]:
            older_key = item.get("older_key")
            if older_key:
                try:
                    if hasattr(adapter, "supersede"):
                        adapter.supersede(older_key)
                        superseded_count += 1
                except (AttributeError, ValueError, KeyError, RuntimeError) as e:
                    logger.warning("Failed to supersede %s: %s", older_key, e)

        forgotten_count = 0
        for item in report["to_forget"]:
            key = item.get("storage_key")
            if key:
                try:
                    adapter.forget(key)
                    forgotten_count += 1
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to forget %s: %s", key, e)

        for item in report["to_decay"]:
            key = item.get("storage_key")
            decay = item.get("decay", 1.0)
            current_conf = item.get("current_confidence", DEFAULT_CONFIDENCE_SCORE)
            new_conf = round(current_conf * decay, DECAY_ROUNDING_PRECISION)
            if new_conf < DECAY_CONFIDENCE_FLOOR:
                try:
                    adapter.forget(key)
                    forgotten_count += 1
                except (KeyError, ValueError) as e:
                    logger.warning("Failed to forget decayed %s: %s", key, e)

        report["dry_run"] = False
        report["superseded_count"] = superseded_count
        report["forgotten_count"] = forgotten_count

        logger.info(
            "Consolidation complete: %d superseded, " "%d forgotten, %d decayed",
            superseded_count,
            forgotten_count,
            len(report["to_decay"]),
        )

        if run_p1:
            rule_storage = None
            try:
                from carrymem.rules.storage import RuleStorage

                db_path = getattr(self._adapter, "db_path", None)
                rule_storage = RuleStorage(db_path=db_path) if db_path else None
            except (ImportError, sqlite3.OperationalError, ValueError) as e:
                logger.warning("P1 skipped: RuleStorage init failed: %s", e)

            p1_result = consolidate_p1(
                memories=all_memories,
                rule_storage=rule_storage,
                auto_accept=False,
            )
            report["p1_promotion"] = p1_result

        if run_p2:
            p2_result = consolidate_p2(
                memories=all_memories,
                p0_report=report,
            )
            report["p2_consolidation"] = p2_result

        return report

    def schedule_consolidation(
        self,
        interval_hours: float = 1.0,
        dry_run: bool = False,
        run_p1: bool = True,
        run_p2: bool = False,
    ) -> Dict[str, Any]:
        """Start periodic memory consolidation on a background timer."""
        import threading

        min_interval = CONSOLIDATION_MIN_INTERVAL_HOURS
        if interval_hours < min_interval:
            interval_hours = min_interval

        self.stop_consolidation()

        interval_sec = interval_hours * SECONDS_PER_HOUR
        status = {
            "scheduled": True,
            "interval_hours": interval_hours,
            "dry_run": dry_run,
            "run_p1": run_p1,
            "run_p2": run_p2,
        }

        def _run_consolidation():
            try:
                logger.info("Scheduled consolidation starting (interval=%fh)", interval_hours)
                result = self.consolidate(dry_run=dry_run, run_p1=run_p1, run_p2=run_p2)
                logger.info(
                    "Scheduled consolidation complete: " "%d superseded, %d forgotten",
                    result.get("superseded_count", 0),
                    result.get("forgotten_count", 0),
                )
            except (ValueError, TypeError, RuntimeError, sqlite3.Error) as e:
                logger.error("Scheduled consolidation failed: %s", e)
            finally:
                if self._consolidation_timer is not None:
                    self._consolidation_timer = threading.Timer(interval_sec, _run_consolidation)
                    self._consolidation_timer.daemon = True
                    self._consolidation_timer.start()

        self._consolidation_timer = threading.Timer(interval_sec, _run_consolidation)
        self._consolidation_timer.daemon = True
        self._consolidation_timer.start()

        logger.info("Consolidation scheduled every %fh", interval_hours)
        return status

    def stop_consolidation(self) -> Dict[str, Any]:
        """Stop the scheduled consolidation timer."""
        if self._consolidation_timer is not None:
            self._consolidation_timer.cancel()
            self._consolidation_timer = None
            logger.info("Consolidation schedule stopped")
            return {"stopped": True}
        return {"stopped": False, "reason": "no_active_schedule"}
