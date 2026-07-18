"""Auto-supersede and contradiction detection for SQLiteAdapter."""

import re
import sqlite3
from datetime import datetime, timezone

from ...utils.logger import logger
from ..base import MemoryEntry


class SupersedeManager:
    """Handles automatic superseding of conflicting memories."""

    _SUPERSEDE_TYPES = {"user_preference", "decision", "fact_declaration", "correction"}
    _CONTRADICTION_PAIRS = [
        ("like", "dislike"),
        ("prefer", "avoid"),
        ("love", "hate"),
        ("use", "stop using"),
        ("switched", "no longer"),
        ("moved", "left"),
        ("changed", "previous"),
        ("updated", "old"),
        ("now", "previously"),
        ("currently", "formerly"),
        ("new", "old"),
        ("current", "previous"),
        ("dark", "light"),
        ("yes", "no"),
        ("true", "false"),
        ("enabled", "disabled"),
        ("always", "never"),
    ]
    _UPDATE_MARKERS = [
        "now",
        "currently",
        "switched",
        "changed",
        "moved",
        "updated",
        "no longer",
        "instead",
        "replaced",
        "new",
        "currently prefer",
        "now prefer",
        "now use",
        "now live",
        "now work",
    ]
    _PREFERENCE_KEYWORDS = {
        "prefer",
        "偏好",
        "喜欢",
        "选用",
        "recommend",
        "avoid",
        "不用",
        "别用",
        "不要用",
        "dislike",
        "hate",
        "never",
        "always",
        "switched",
        "changed",
        "replaced",
        "instead",
    }
    _ASSISTANT_PREFIXES = ("[assistant said]", "[ai said]", "[bot said]")

    def __init__(self, adapter):
        self._adapter = adapter

    def auto_supersede(self, conn, new_storage_key: str, entry: MemoryEntry, namespace: str):
        """Mark older conflicting memories as superseded by the new entry."""
        if entry.type not in self._SUPERSEDE_TYPES or entry.type == "correction":
            return

        try:
            rows = conn.execute(
                "SELECT id, content, raw_text, type, created_at, superseded_at, storage_key "
                "FROM memories WHERE type = ? AND namespace = ? AND superseded_at IS NULL "
                "AND storage_key != ? "
                "ORDER BY created_at DESC LIMIT 20",
                (entry.type, namespace, new_storage_key),
            ).fetchall()
        except sqlite3.OperationalError:
            return

        if not rows:
            return

        entry_words = set(entry.content.lower().split())
        entry_lower = entry.content.lower()
        has_update_marker = self._has_update_marker(entry_lower)
        entry_has_pref_kw = self._has_preference_keyword(entry_lower)

        for row in rows:
            old_content = row["content"] or ""
            if self._is_skip_content(old_content):
                continue

            jaccard = self._compute_jaccard(entry_words, old_content)
            if jaccard is None:
                continue

            if not self._should_supersede(entry, old_content, has_update_marker, entry_has_pref_kw, jaccard):
                continue

            if self._is_skip_content(entry.content):
                continue

            if self._apply_supersede_db_update(conn, row, new_storage_key, entry, jaccard, has_update_marker):
                break

    @staticmethod
    def _has_update_marker(content_lower: str) -> bool:
        """Check if content contains an update marker word."""
        return any(
            f" {m} " in f" {content_lower} " or content_lower.startswith(f"{m} ")
            for m in SupersedeManager._UPDATE_MARKERS
        )

    @staticmethod
    def _has_preference_keyword(content_lower: str) -> bool:
        """Check if content contains a preference keyword."""
        return any(kw in content_lower for kw in SupersedeManager._PREFERENCE_KEYWORDS)

    @staticmethod
    def _is_skip_content(content: str) -> bool:
        """Check if content should be skipped (corrections, decisions, assistant replies)."""
        if content.startswith("Correction:") or content.startswith("Decision:"):
            return True
        return content.lower().startswith(SupersedeManager._ASSISTANT_PREFIXES)

    @staticmethod
    def _compute_jaccard(entry_words: set, old_content: str):
        """Compute Jaccard similarity. Returns None if old_content has no words."""
        old_words = set(old_content.lower().split())
        if not old_words:
            return None
        return len(entry_words & old_words) / max(len(entry_words | old_words), 1)

    @staticmethod
    def _should_supersede(
        entry: MemoryEntry,
        old_content: str,
        has_update_marker: bool,
        entry_has_pref_kw: bool,
        jaccard: float,
    ) -> bool:
        """Decide whether old_content should be superseded by entry.content."""
        if SupersedeManager.is_contradictory(entry.content, old_content):
            return True
        if has_update_marker and jaccard >= 0.40:
            return True
        if entry.type == "user_preference" and entry_has_pref_kw:
            if SupersedeManager._has_preference_keyword(old_content.lower()):
                return True
        return False

    @staticmethod
    def _fetch_version_chain(conn, memory_id: str):
        """Fetch (version_chain_id, version_number) for a memory. Returns (None, 1) on error."""
        try:
            chain_row = conn.execute(
                "SELECT version_chain_id, version_number FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
            if chain_row:
                return chain_row["version_chain_id"], chain_row["version_number"] or 1
        except sqlite3.OperationalError:
            pass
        return None, 1

    @staticmethod
    def _apply_supersede_db_update(
        conn, row, new_storage_key: str, entry: MemoryEntry, jaccard: float, has_update_marker: bool
    ) -> bool:
        """Apply the supersede DB update. Returns True if update applied successfully."""
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            old_chain_id, old_version = SupersedeManager._fetch_version_chain(conn, row["id"])
            chain_id = old_chain_id or new_storage_key
            new_version = old_version + 1

            # Mark old memory as superseded and link to chain
            conn.execute(
                "UPDATE memories SET superseded_at = ?, supersedes = ?, version_chain_id = ? WHERE id = ?",
                (now_iso, new_storage_key, chain_id, row["id"]),
            )
            # Update new memory's version chain info
            conn.execute(
                "UPDATE memories SET version_chain_id = ?, version_number = ? WHERE storage_key = ?",
                (chain_id, new_version, new_storage_key),
            )
        except sqlite3.Error as e:
            logger.debug("Auto-supersede update failed: %s", e)
            return False
        logger.debug(
            "Auto-superseded memory %s with new %s (jaccard=%.2f, update_marker=%s)",
            row["id"][:16],
            entry.type,
            jaccard,
            has_update_marker,
        )
        return True

    @staticmethod
    def is_contradictory(new_content: str, old_content: str) -> bool:
        """Detect contradiction between two memory contents via paired keywords."""
        new_lower = new_content.lower()
        old_lower = old_content.lower()
        for pos_word, neg_word in SupersedeManager._CONTRADICTION_PAIRS:
            pos_pat = rf"\b{re.escape(pos_word)}\b"
            neg_pat = rf"\b{re.escape(neg_word)}\b"
            if (re.search(pos_pat, new_lower) and re.search(neg_pat, old_lower)) or (
                re.search(neg_pat, new_lower) and re.search(pos_pat, old_lower)
            ):
                return True
        return False
