"""Auto-supersede and contradiction detection for SQLiteAdapter."""

import re
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

    def __init__(self, adapter):
        self._adapter = adapter

    def auto_supersede(self, conn, new_storage_key: str, entry: MemoryEntry, namespace: str):
        if entry.type not in self._SUPERSEDE_TYPES:
            return
        if entry.type == "correction":
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
        has_update_marker = any(
            f" {m} " in f" {entry_lower} " or entry_lower.startswith(f"{m} ") for m in self._UPDATE_MARKERS
        )

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
        entry_has_pref_kw = any(kw in entry_lower for kw in _PREFERENCE_KEYWORDS)

        for row in rows:
            old_content = row["content"] or ""
            if old_content.startswith("Correction:") or old_content.startswith("Decision:"):
                continue
            if old_content.lower().startswith(("[assistant said]", "[ai said]", "[bot said]")):
                continue

            old_words = set(old_content.lower().split())
            if not old_words:
                continue
            jaccard = len(entry_words & old_words) / max(len(entry_words | old_words), 1)

            should_supersede = False
            if self.is_contradictory(entry.content, old_content):
                should_supersede = True
            elif has_update_marker and jaccard >= 0.40:
                should_supersede = True
            elif entry.type == "user_preference" and entry_has_pref_kw:
                old_lower = old_content.lower()
                old_has_pref_kw = any(kw in old_lower for kw in _PREFERENCE_KEYWORDS)
                if old_has_pref_kw:
                    should_supersede = True

            if not should_supersede:
                if jaccard < 0.25:
                    continue
                continue

            if entry.content.startswith("Correction:") or entry.content.startswith("Decision:"):
                continue
            if entry.content.lower().startswith(("[assistant said]", "[ai said]", "[bot said]")):
                continue

            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                # Get old memory's version chain info
                old_chain_id = None
                old_version = 1
                try:
                    chain_row = conn.execute(
                        "SELECT version_chain_id, version_number FROM memories WHERE id = ?",
                        (row["id"],),
                    ).fetchone()
                    if chain_row:
                        old_chain_id = chain_row["version_chain_id"]
                        old_version = chain_row["version_number"] or 1
                except sqlite3.OperationalError:
                    pass

                # Determine chain_id: reuse old if exists, otherwise use new storage_key
                chain_id = old_chain_id or new_storage_key
                new_version = old_version + 1

                # Mark old memory as superseded and link to chain
                conn.execute(
                    "UPDATE memories SET superseded_at = ?, supersedes = ?, " "version_chain_id = ? WHERE id = ?",
                    (now_iso, new_storage_key, chain_id, row["id"]),
                )

                # Update new memory's version chain info
                conn.execute(
                    "UPDATE memories SET version_chain_id = ?, version_number = ? " "WHERE storage_key = ?",
                    (chain_id, new_version, new_storage_key),
                )
            except sqlite3.Error as e:
                logger.debug("Auto-supersede update failed: %s", e)
            logger.debug(
                "Auto-superseded memory %s with new %s " "(jaccard=%.2f, update_marker=%s)",
                row["id"][:16],
                entry.type,
                jaccard,
                has_update_marker,
            )
            break

    @staticmethod
    def is_contradictory(new_content: str, old_content: str) -> bool:
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
