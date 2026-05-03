"""Automatic backup for CarryMem databases.

v0.6.0: Zero-downtime backup using SQLite VACUUM INTO.

Features:
- Full backup via VACUUM INTO (zero downtime, consistent snapshot)
- Timestamped backup files
- Automatic cleanup of old backups (FIFO)
- Restore from any backup
- Auto-backup on interval check
"""

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class BackupManager:
    """Automatic backup for CarryMem databases."""

    def __init__(
        self,
        db_path: str,
        backup_dir: Optional[str] = None,
        max_backups: int = 10,
    ):
        self._db_path = db_path
        self._max_backups = max_backups

        if backup_dir:
            self._backup_dir = backup_dir
        else:
            db_dir = os.path.dirname(db_path)
            self._backup_dir = os.path.join(db_dir, "backups") if db_dir else "backups"

        self._ensure_dir(self._backup_dir)
        try:
            os.chmod(self._backup_dir, 0o700)
        except (OSError, AttributeError):
            pass

    @staticmethod
    def _ensure_dir(path: str) -> None:
        if path and not os.path.exists(path):
            os.makedirs(path, mode=0o700, exist_ok=True)

    def create_backup(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"memories_{timestamp}.db"
        backup_path = os.path.join(self._backup_dir, backup_filename)

        if self._db_path == ":memory:":
            raise ValueError("Cannot backup in-memory database")

        if not os.path.exists(self._db_path):
            raise FileNotFoundError(f"Database not found: {self._db_path}")

        try:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(f"VACUUM INTO ?", (backup_path,))
            except sqlite3.OperationalError:
                conn.close()
                shutil.copy2(self._db_path, backup_path)
            else:
                conn.close()
        except sqlite3.OperationalError:
            shutil.copy2(self._db_path, backup_path)

        try:
            os.chmod(backup_path, 0o600)
        except (OSError, AttributeError):
            pass

        self.cleanup_old_backups()

        return backup_path

    def restore_backup(self, backup_path: str) -> None:
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        try:
            test_conn = sqlite3.connect(backup_path)
            test_conn.execute("SELECT COUNT(*) FROM memories")
            test_conn.close()
        except Exception as e:
            raise ValueError(f"Invalid backup file: {e}") from e

        if self._db_path == ":memory:":
            raise ValueError("Cannot restore to in-memory database")

        pre_restore_backup = self._db_path + ".pre_restore.bak"
        if os.path.exists(self._db_path):
            shutil.copy2(self._db_path, pre_restore_backup)

        try:
            shutil.copy2(backup_path, self._db_path)
        except Exception as e:
            if os.path.exists(pre_restore_backup):
                shutil.copy2(pre_restore_backup, self._db_path)
            raise RuntimeError(f"Restore failed, rolled back: {e}") from e
        finally:
            if os.path.exists(pre_restore_backup):
                try:
                    os.remove(pre_restore_backup)
                except OSError:
                    pass

    def list_backups(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self._backup_dir):
            return []

        backups = []
        for filename in os.listdir(self._backup_dir):
            if filename.startswith("memories_") and filename.endswith(".db"):
                filepath = os.path.join(self._backup_dir, filename)
                try:
                    stat = os.stat(filepath)
                    size_kb = stat.st_size / 1024

                    try:
                        conn = sqlite3.connect(filepath)
                        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                        conn.close()
                        memory_count = count
                    except Exception:
                        memory_count = None

                    backups.append({
                        "filename": filename,
                        "path": filepath,
                        "size_kb": round(size_kb, 1),
                        "created_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "memory_count": memory_count,
                    })
                except (OSError, sqlite3.Error):
                    continue

        backups.sort(key=lambda b: b["created_at"], reverse=True)
        return backups

    def cleanup_old_backups(self) -> int:
        backups = self.list_backups()
        if len(backups) <= self._max_backups:
            return 0

        to_remove = backups[self._max_backups:]
        removed = 0
        for backup in to_remove:
            try:
                os.remove(backup["path"])
                removed += 1
            except OSError:
                continue

        return removed
