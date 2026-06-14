"""CarryMem AI Memory System — Facade with Mixin composition.

This module composes CarryMem from 7 focused Mixin classes plus a LifecycleMixin
that holds __init__ / close / properties.  Every public API is identical to the
original monolithic class — `cm.method()` calls work without changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from carrymem.core._backup import BackupMixin
from carrymem.core._classification import ClassificationMixin
from carrymem.core._lifecycle import (
    KnowledgeNotConfiguredError,
    LifecycleMixin,
    StorageNotConfiguredError,
    _validate_file_path,
)
from carrymem.core._maintenance import MaintenanceMixin
from carrymem.core._memory_crud import MemoryCRUDMixin
from carrymem.core._profile_export import ProfileExportMixin
from carrymem.core._prompt_delegate import PromptDelegateMixin
from carrymem.core._protocols import (
    BackupOps,
    CarryMemOps,
    ClassificationOps,
    LifecycleOps,
    MaintenanceOps,
    MemoryCRUDOps,
    ProfileExportOps,
    PromptDelegateOps,
    RecallOps,
)
from carrymem.core._recall import RecallMixin
from carrymem.errors import CarryMemError
from carrymem.types import ComponentStatusDict, HealthCheckResult

if TYPE_CHECKING:
    from carrymem.security.permissions import AccessPolicy


class CarryMem(
    LifecycleMixin,
    BackupMixin,
    MemoryCRUDMixin,
    ClassificationMixin,
    RecallMixin,
    ProfileExportMixin,
    MaintenanceMixin,
    PromptDelegateMixin,
):
    """CarryMem — Portable AI Memory Layer (Facade).

    Makes AI agents remember users. Classification is core, storage is swappable,
    works out of the box. Knowledge base is read-only, memories are read-write.
    Recall priority: memories > knowledge base.

    Composed from 7 Mixin classes + LifecycleMixin via multiple inheritance.
    All public methods retain their original signatures for full backward compat.

    Protocol declarations (structural typing, no runtime overhead)::

        _: LifecycleOps       # lifecycle / shared state
        _: BackupOps          # backup & audit
        _: RecallOps          # memory / knowledge / rule search
        _: ClassificationOps  # classification pipeline
        _: MemoryCRUDOps      # CRUD operations
        _: ProfileExportOps   # profile, stats, export/import
        _: MaintenanceOps     # quality, conflicts, consolidation
        _: PromptDelegateOps  # prompt building & LLM features
        _: CarryMemOps        # composite of all above
    """

    # Ensure MRO puts LifecycleMixin first so __init__ resolves correctly
    pass

    # ── Access control (P1-8 MVP) ──────────────────────────────────

    @property
    def access_policy(self) -> Optional[AccessPolicy]:
        """Return the current access policy, or ``None`` if not set."""
        return getattr(self, "_access_policy", None)

    @access_policy.setter
    def access_policy(self, policy: Optional[AccessPolicy]) -> None:
        self._access_policy = policy

    # ------------------------------------------------------------------ #
    #  Facade-level utilities: version, health, status, validation       #
    # ------------------------------------------------------------------ #

    @property
    def version(self) -> str:
        """Return the CarryMem version string.

        Example::

            >>> cm.version
            '0.4.0'
        """
        from carrymem import __version__

        return __version__

    def health_check(self) -> HealthCheckResult:
        """Return health status of all components.

        Returns a dict with overall status, per-component details and any
        issues detected::

            {
                "status": "ok" | "degraded",
                "components": { "storage": ..., "adapter": ..., ... },
                "issues": [...],
            }
        """
        components: Dict[str, Dict[str, Any]] = {}
        issues: list[str] = []

        # -- storage / adapter --
        if self._adapter is not None:
            try:
                stats = self._adapter.get_stats() if hasattr(self._adapter, "get_stats") else {}
                components["storage"] = {"status": "ready", "stats": stats}
                components["adapter"] = {"status": "ready", "type": type(self._adapter).__name__}
            except Exception as exc:  # pragma: no cover
                components["storage"] = {"status": "error", "error": str(exc)}
                components["adapter"] = {"status": "error", "error": str(exc)}
                issues.append(f"Storage adapter error: {exc}")
        else:
            components["storage"] = {"status": "not_configured"}
            components["adapter"] = {"status": "not_configured"}

        # -- engine --
        try:
            _ = self._engine
            components["engine"] = {"status": "ready", "type": type(self._engine).__name__}
        except Exception as exc:  # pragma: no cover
            components["engine"] = {"status": "error", "error": str(exc)}
            issues.append(f"Engine error: {exc}")

        # -- knowledge --
        if self._knowledge_adapter is not None:
            components["knowledge"] = {
                "status": "ready",
                "type": type(self._knowledge_adapter).__name__,
            }
        else:
            components["knowledge"] = {"status": "not_configured"}

        # -- rule_engine (lazy) --
        try:
            _ = self.rule_engine
            components["rule_engine"] = {"status": "ready"}
        except Exception as exc:  # pragma: no cover
            components["rule_engine"] = {"status": "error", "error": str(exc)}
            issues.append(f"Rule engine error: {exc}")

        overall = "degraded" if issues else "ok"
        return {"status": overall, "components": components, "issues": issues}

    def get_component_status(self) -> ComponentStatusDict:
        """Return the initialisation status of every component.

        Returns a dict mapping component name to ``"ready"``,
        ``"not_configured"`` or ``"error"``::

            {"storage": "ready", "engine": "ready", "knowledge": "not_configured", ...}
        """
        result: Dict[str, str] = {}

        # storage / adapter
        result["storage"] = "ready" if self._adapter is not None else "not_configured"
        result["adapter"] = result["storage"]

        # engine – always initialised in __init__
        result["engine"] = "ready"

        # knowledge
        result["knowledge"] = "ready" if self._knowledge_adapter is not None else "not_configured"

        # rule_engine – lazy; probe without forcing init if possible
        if self._rule_engine is not None:
            result["rule_engine"] = "ready"
        else:
            # Don't trigger lazy init here; report as not configured
            result["rule_engine"] = "not_configured"

        return result

    def validate_ready(
        self,
        require_storage: bool = True,
        require_knowledge: bool = False,
    ) -> None:
        """Unified readiness check; raises :class:`CarryMemError` when not ready.

        Error codes used:

        * **CM-001** – storage required but not configured
        * **CM-002** – knowledge required but not configured
        * **CM-003** – engine not initialised (should never happen)
        * **CM-004** – rule engine probe failed

        Args:
            require_storage: If *True* (default), raise when no storage adapter.
            require_knowledge: If *True*, raise when no knowledge adapter.

        Raises:
            CarryMemError: With code CM-001 ~ CM-004 on failure.
        """
        if require_storage and self._adapter is None:
            raise CarryMemError(
                code="CM-001",
                message="Storage adapter is not configured.",
                hint="Use CarryMem(storage='sqlite') or pass a StorageAdapter instance.",
            )

        if require_knowledge and self._knowledge_adapter is None:
            raise CarryMemError(
                code="CM-002",
                message="Knowledge adapter is not configured.",
                hint=("Use CarryMem(knowledge_adapter=ObsidianAdapter('/path')) " "to enable knowledge base features."),
            )

        if self._engine is None:
            raise CarryMemError(
                code="CM-003",
                message="Classification engine is not initialised.",
                hint="This should never happen – please file a bug report.",
            )

        # Rule engine is lazily initialised; only check if already created
        if self._rule_engine is not None:
            try:
                _ = self.rule_engine  # noqa: F841 – force attribute access
            except Exception as exc:
                raise CarryMemError(
                    code="CM-004",
                    message=f"Rule engine is in error state: {exc}",
                    hint="Check rule storage configuration or database integrity.",
                ) from exc


# ---------------------------------------------------------------------------
# Protocol structural-typing assertions (IDE + static checker only).
# These are NOT runtime checks — they tell mypy / pyright that CarryMem
# satisfies every Protocol so ``def f(cm: CarryMemOps)`` accepts CarryMem.
# ---------------------------------------------------------------------------
_: LifecycleOps = CarryMem  # type: ignore[assignment]
_: BackupOps = CarryMem  # type: ignore[assignment]
_: RecallOps = CarryMem  # type: ignore[assignment]
_: ClassificationOps = CarryMem  # type: ignore[assignment]
_: MemoryCRUDOps = CarryMem  # type: ignore[assignment]
_: ProfileExportOps = CarryMem  # type: ignore[assignment]
_: MaintenanceOps = CarryMem  # type: ignore[assignment]
_: PromptDelegateOps = CarryMem  # type: ignore[assignment]
_: CarryMemOps = CarryMem  # type: ignore[assignment]


__all__ = [
    "CarryMem",
    # Protocols (structural typing for type checkers / IDE)
    "CarryMemOps",
    "LifecycleOps",
    "BackupOps",
    "RecallOps",
    "ClassificationOps",
    "MemoryCRUDOps",
    "ProfileExportOps",
    "MaintenanceOps",
    "PromptDelegateOps",
    # Exceptions & helpers
    "StorageNotConfiguredError",
    "KnowledgeNotConfiguredError",
    "_validate_file_path",
]
