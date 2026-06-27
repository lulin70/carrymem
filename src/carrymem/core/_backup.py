"""Backup & audit operations."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.constants import AUDIT_LOG_DEFAULT_LIMIT
from carrymem.core._lifecycle import StorageNotConfiguredError

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter

logger = logging.getLogger(__name__)


class BackupMixin:
    """Backup creation, listing, restoration, cache clearing, and audit log."""

    # Shared instance state provided by LifecycleMixin.__init__ (no default
    # assignment — values are set at runtime by the composite CarryMem class).
    _adapter: Optional[StorageAdapter]
    _backup_dir: Optional[str]
    _auto_backup_interval: int
    _write_count: int
    _initial_backup_done: bool

    def _do_initial_backup(self) -> None:
        """Create initial backup when CarryMem first opens an existing database."""
        if self._initial_backup_done:
            return
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return
        db_path = self._adapter.db_path
        if db_path == ":memory:":
            return

        from carrymem.backup import BackupManager

        manager = BackupManager(db_path, backup_dir=self._backup_dir)
        backups = manager.list_backups()
        if not backups:
            try:
                manager.create_backup()
                logger.info("Initial backup created")
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug("Initial backup failed: %s", e)
        self._initial_backup_done = True

    def _auto_backup(self) -> None:
        """Check if auto-backup should run based on write count, and execute if needed."""
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return
        if self._auto_backup_interval <= 0:
            return

        self._write_count += 1
        if self._write_count >= self._auto_backup_interval:
            self._write_count = 0
            try:
                db_path = self._adapter.db_path
                if db_path and db_path != ":memory:":
                    from carrymem.backup import BackupManager

                    manager = BackupManager(db_path, backup_dir=self._backup_dir)
                    manager.create_backup()
                    logger.debug("Auto-backup triggered after %d writes", self._auto_backup_interval)
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug("Auto-backup failed: %s", e)

    def clear_cache(self) -> None:
        """Invalidate the adapter's in-memory cache."""
        if self._adapter and hasattr(self._adapter, "_cache") and self._adapter._cache:
            self._adapter._cache.clear()

    def backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """Create a database backup and return the result dict."""
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Backup only supported with SQLiteAdapter"}

        from carrymem.backup import BackupManager

        db_path = self._adapter.db_path
        if db_path == ":memory:":
            return {"error": "Cannot backup in-memory database"}

        manager = BackupManager(db_path, backup_dir=backup_dir)
        try:
            path = manager.create_backup()
            return {"backed_up": True, "path": path}
        except (OSError, ValueError) as e:
            return {"backed_up": False, "error": str(e)}

    def list_backups(self, backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available backups for the adapter's database."""
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return []

        from carrymem.backup import BackupManager

        db_path = self._adapter.db_path
        manager = BackupManager(db_path, backup_dir=backup_dir)
        return manager.list_backups()

    def restore_backup(self, backup_path: str, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """Restore the database from a backup file and return the result dict."""
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Restore only supported with SQLiteAdapter"}

        from carrymem.backup import BackupManager

        db_path = self._adapter.db_path
        if db_path == ":memory:":
            return {"error": "Cannot restore to in-memory database"}

        if backup_dir is None:
            backup_dir = os.path.dirname(backup_path)
        manager = BackupManager(db_path, backup_dir=backup_dir)
        try:
            manager.restore_backup(backup_path)
            return {"restored": True, "backup_path": backup_path}
        except (OSError, ValueError) as e:
            return {"restored": False, "error": str(e)}

    def get_audit_log(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = AUDIT_LOG_DEFAULT_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Return audit log entries matching the filter criteria."""
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return []

        if not self._adapter._audit:
            return []

        from carrymem.security.audit import AuditFilter

        filter_ = AuditFilter(limit=limit)
        if operation:
            filter_.action = operation

        events = self._adapter._audit.query(filter_)
        # Map action→operation for API compatibility with legacy callers
        result = []
        for e in events:
            d = e.to_dict()
            d["operation"] = d.pop("action", "")
            result.append(d)
        return result
