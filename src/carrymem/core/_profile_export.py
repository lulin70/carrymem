"""Profile, stats, export, import operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from carrymem.__version__ import __version__ as _version
from carrymem.adapters.base import MemoryEntry
from carrymem.constants import (
    CORRECTION_RECALL_LIMIT,
    DEFAULT_CONFIDENCE_SCORE,
    EXPORT_SCHEMA_VERSION,
    IMPORT_CONTENT_SEARCH_LENGTH,
    WHOAMI_CORRECTION_COUNT,
    WHOAMI_DECISION_COUNT,
    WHOAMI_PREFERENCE_COUNT,
)
from carrymem.core._lifecycle import StorageNotConfiguredError, _validate_file_path
from carrymem.domain import get_domain_description, infer_domains_from_memories
from carrymem.security.input_validator import InputValidator
from carrymem.types import (
    ExportMemoriesResult,
    ExportProfileResult,
    ImportMemoriesResult,
    MemoryProfile,
    MemoryStats,
    WhoamiResult,
)

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter

logger = logging.getLogger(__name__)

_import_validator = InputValidator(strict_mode=True)


class ProfileExportMixin:
    """User profile, statistics, export, and import of memories."""

    # Shared instance state provided by LifecycleMixin.__init__.
    _adapter: Optional[StorageAdapter]
    _namespace: str

    # ── Cross-Mixin dependencies (TD-037: explicit Protocol contract) ──
    if TYPE_CHECKING:
        # From RecallMixin
        def recall_memories(
            self,
            query: Optional[str] = None,
            filters: Optional[Dict[str, Any]] = None,
            limit: int = 20,
            namespaces: Optional[List[str]] = None,
            update_access: bool = True,
        ) -> List[Dict[str, Any]]: ...

        # From BackupMixin
        def _auto_backup(self) -> None: ...

    def get_stats(self) -> MemoryStats:
        """Return aggregate statistics for the active storage adapter."""
        if not self._adapter:
            return {"adapter": None, "total_count": 0}

        return self._adapter.get_stats()  # type: ignore[return-value]

    def get_memory_profile(self) -> MemoryProfile:
        """Return the structured memory profile for the active namespace."""
        if not self._adapter:
            return {
                "summary": "No storage configured",
                "total_memories": 0,
                "highlights": {},
                "stats": {},  # type: ignore[typeddict-item]
            }

        profile = self._adapter.get_profile()
        return profile  # type: ignore[return-value]

    def whoami(self) -> WhoamiResult:
        """Build a human-readable identity summary from stored memories."""
        if not self._adapter:
            return {"identity": "unknown", "summary": "No storage configured"}

        stats = self._adapter.get_stats()
        profile = self._adapter.get_profile()
        total = stats.get("total_count", 0) if isinstance(stats, dict) else 0

        if total == 0:
            return {
                "identity": "new_user",
                "summary": "No memories yet. Start by telling me about yourself.",
                "total_memories": 0,
            }

        by_type = stats.get("by_type", {}) if isinstance(stats, dict) else {}
        profile_stats = profile.get("stats", {}) if isinstance(profile, dict) else {}

        preferences = self.recall_memories(query="", filters={"type": "user_preference"}, limit=WHOAMI_PREFERENCE_COUNT)
        decisions = self.recall_memories(query="", filters={"type": "decision"}, limit=WHOAMI_DECISION_COUNT)
        corrections = self.recall_memories(query="", filters={"type": "correction"}, limit=WHOAMI_CORRECTION_COUNT)

        pref_list = [m.get("content", "") for m in preferences[:5]]
        decision_list = [m.get("content", "") for m in decisions[:3]]
        correction_list = [m.get("content", "") for m in corrections[:3]]

        top_type = max(by_type, key=lambda k: by_type.get(k, 0)) if by_type else "unknown"
        conf_avg = profile_stats.get("confidence_avg", 0)

        identity_parts = []
        if pref_list:
            identity_parts.append("Preferences: " + "; ".join(pref_list[:3]))
        if decision_list:
            identity_parts.append("Decisions: " + "; ".join(decision_list[:2]))
        if correction_list:
            identity_parts.append("Corrections: " + "; ".join(correction_list[:2]))

        summary = " | ".join(identity_parts) if identity_parts else f"User with {total} memories"

        all_memories = preferences + decisions + corrections
        domains = infer_domains_from_memories(all_memories)

        return {
            "identity": "known_user",
            "summary": summary,
            "total_memories": total,
            "top_type": top_type,
            "confidence_avg": conf_avg,
            "preferences": pref_list,
            "decisions": decision_list,
            "corrections": correction_list,
            "by_type": by_type,
            "domains": [get_domain_description(d) for d in domains],  # type: ignore[misc]
        }

    def export_profile(self, output_path: Optional[str] = None) -> ExportProfileResult:
        """Export the user identity profile to a file (or return as dict)."""
        whoami = self.whoami()
        profile = self.get_memory_profile()

        export = {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "format": "carrymem_identity",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "identity": whoami.get("identity", "unknown"),
            "summary": whoami.get("summary", ""),
            "preferences": whoami.get("preferences", []),
            "decisions": whoami.get("decisions", []),
            "corrections": whoami.get("corrections", []),
            "stats": {
                "total_memories": whoami.get("total_memories", 0),
                "top_type": whoami.get("top_type", ""),
                "confidence_avg": whoami.get("confidence_avg", 0),
                "by_type": whoami.get("by_type", {}),
            },
            "profile": profile,
        }

        if output_path:
            output_path = _validate_file_path(output_path)
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=2)

        return export  # type: ignore[return-value]

    def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        namespace: Optional[str] = None,
    ) -> ExportMemoriesResult:
        """Export memories to a portable format."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if output_path:
            output_path = _validate_file_path(output_path)

        ns = namespace or self._namespace
        stats = self._adapter.get_stats()
        total_count = stats.get("total_count", 0) if isinstance(stats, dict) else 0
        export_limit = max(total_count, 1)

        all_memories = self._adapter.recall("", limit=export_limit)

        if ns != "default" and self._adapter.capabilities.get("namespace_filtering", False):
            all_memories = self._adapter.recall("", limit=export_limit, namespaces=[ns])

        export_data = {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "export_format": "carrymem_portable",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "version": _version,
                "namespace": ns,
                "total_memories": len(all_memories),
            },
            "memories": [m.to_dict() for m in all_memories],
        }

        if format == "markdown":
            md_lines = [
                "# CarryMem Memory Export",
                "",
                f"- **Exported**: {export_data['exported_at']}",
                f"- **Namespace**: {ns}",
                f"- **Total memories**: {len(all_memories)}",
                "",
            ]
            by_type: Dict[str, list] = {}
            for m in all_memories:
                d = m.to_dict()
                t = d.get("type", "unknown")
                by_type.setdefault(t, []).append(d)

            for mem_type, items in sorted(by_type.items()):
                md_lines.append(f"## {mem_type}")
                md_lines.append("")
                for item in items:
                    content = item.get("content", "")
                    conf = item.get("confidence", 0)
                    tier = item.get("tier", "?")
                    md_lines.append(f"- [{tier}] {content} (confidence: {conf:.0%})")
                md_lines.append("")

            md_content = "\n".join(md_lines)
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
            return {
                "exported": True,
                "format": "markdown",
                "path": output_path,
                "total_memories": len(all_memories),
                "namespace": ns,
                "content": md_content if not output_path else None,
            }

        json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_content)

        return {
            "exported": True,
            "format": "json",
            "path": output_path,
            "total_memories": len(all_memories),
            "namespace": ns,
            "data": export_data if not output_path else None,
        }

    def import_memories(
        self,
        input_path: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        merge_strategy: str = "skip_existing",
    ) -> ImportMemoriesResult:
        """Import memories from a portable format."""
        if not self._adapter:
            raise StorageNotConfiguredError()

        if input_path:
            input_path = _validate_file_path(input_path)

        if input_path:
            with open(input_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        elif data:
            import_data = data
        else:
            raise ValueError("Either input_path or data must be provided")

        target_ns = namespace or self._namespace
        memories = import_data.get("memories", [])

        imported = 0
        skipped = 0
        errors = 0

        for mem_dict in memories:
            try:
                content = mem_dict.get("content", "")
                if content:
                    content = _import_validator.validate_content(content, "imported_content")
                content_hash = mem_dict.get("content_hash", "")
                if merge_strategy == "skip_existing" and content_hash:
                    existing = self._adapter.recall(
                        mem_dict.get("content", "")[:IMPORT_CONTENT_SEARCH_LENGTH], limit=CORRECTION_RECALL_LIMIT
                    )
                    if any(
                        (
                            getattr(e, "content_hash", None) == content_hash
                            or (isinstance(e, dict) and e.get("content_hash") == content_hash)
                            or (
                                hasattr(e, "metadata")
                                and isinstance(e.metadata, dict)
                                and e.metadata.get("content_hash") == content_hash
                            )
                        )
                        for e in existing
                    ):
                        skipped += 1
                        continue

                entry = MemoryEntry(
                    id=mem_dict.get("id", ""),
                    type=mem_dict.get("type", "unknown"),
                    content=content,
                    confidence=mem_dict.get("confidence", DEFAULT_CONFIDENCE_SCORE),
                    tier=mem_dict.get("tier", 2),
                    source_layer=mem_dict.get("source_layer", "import"),
                    reasoning=mem_dict.get("reasoning", ""),
                    suggested_action="store",
                    recall_hint=mem_dict.get("recall_hint"),
                    metadata={
                        **mem_dict.get("metadata", {}),
                        "imported_from": import_data.get("source", {}).get("namespace", "unknown"),
                        "imported_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self._adapter.store_entry(entry)
                imported += 1
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Failed to import memory entry: %s", e)
                errors += 1

        self._auto_backup()

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "total_processed": len(memories),
            "namespace": target_ns,
            "merge_strategy": merge_strategy,
        }
