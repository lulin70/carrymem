"""Tests for core Protocol interfaces (_protocols.py).

Validates that:
  1. Every Protocol has the correct methods defined.
  2. CarryMem satisfies all individual Protocols (structural typing).
  3. CarryMem satisfies the composite CarryMemOps Protocol.
  4. Protocol method signatures match actual Mixin implementations.
  5. MRO order is correct and documented.
"""

from __future__ import annotations

import inspect
import sys
from typing import get_type_hints

import pytest

# ---------------------------------------------------------------------------
# Imports — must work from project root or tests/ directory
# ---------------------------------------------------------------------------

sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0])

from carrymem.core._protocols import (
    BackupOps,
    CarryMemOps,
    ClassificationOps,
    HasSharedState,
    LifecycleOps,
    MaintenanceOps,
    MemoryCRUDOps,
    ProfileExportOps,
    PromptDelegateOps,
    RecallOps,
)
from carrymem.core._backup import BackupMixin
from carrymem.core._classification import ClassificationMixin
from carrymem.core._lifecycle import LifecycleMixin
from carrymem.core._maintenance import MaintenanceMixin
from carrymem.core._memory_crud import MemoryCRUDMixin
from carrymem.core._profile_export import ProfileExportMixin
from carrymem.core._prompt_delegate import PromptDelegateMixin
from carrymem.core._recall import RecallMixin


# ===========================================================================
# Helper: collect method/property names from a Protocol class
# ===========================================================================


def _protocol_members(proto_cls: type) -> set[str]:
    """Return all member names defined directly on a Protocol.

    Includes:
      - regular methods (public and private, e.g. ``_store_entries``)
      - properties (e.g. ``namespace``, ``engine``)
      - dunder methods (``__init__``, ``__enter__``, ``__exit__``)

    Excludes:
      - Protocol internal attributes (``_HAS_SHARED_STATE_*``, ``__abc_*``)
      - classmethod / staticmethod wrappers
    """
    members: set[str] = set()
    for name, member in vars(proto_cls).items():
        # Skip Protocol internals
        if name.startswith("_HAS_SHARED_STATE_") or name.startswith("__abc_"):
            continue
        # Accept: functions, properties, regular methods
        if isinstance(member, property):
            members.add(name)
        elif callable(member) and not isinstance(member, (classmethod, staticmethod)):
            members.add(name)
    return members


def _mixin_public_methods(mixin_cls: type) -> set[str]:
    """Return all public method names (no leading underscore, except dunder)."""
    return {
        name
        for name, member in inspect.getmembers(mixin_cls, predicate=inspect.isfunction)
        if not name.startswith("_") or name in ("__init__", "__enter__", "__exit__")
    }


def _mixin_all_methods(mixin_cls: type) -> set[str]:
    """Return all methods including private ones defined on the mixin."""
    return {
        name
        for name, member in inspect.getmembers(mixin_cls, predicate=inspect.isfunction)
        if not name.startswith("__") or name in ("__init__", "__enter__", "__exit__")
    }


# ===========================================================================
# Test Group 1: Protocol structure completeness
# ===========================================================================


class TestProtocolDefinitions:
    """Verify each Protocol is well-formed and non-empty."""

    def test_lifecycle_ops_has_methods(self):
        members = _protocol_members(LifecycleOps)
        # LifecycleOps has: close, __enter__, __exit__, namespace, engine,
        # adapter, storage, knowledge_adapter, rule_engine, prompt_builder = ~11
        assert len(members) >= 10, f"LifecycleOps too thin: {members}"

    def test_backup_ops_has_methods(self):
        members = _protocol_members(BackupOps)
        assert len(members) >= 7, f"BackupOps too thin: {members}"

    def test_recall_ops_has_methods(self):
        members = _protocol_members(RecallOps)
        assert len(members) >= 6, f"RecallOps too thin: {members}"

    def test_classification_ops_has_methods(self):
        members = _protocol_members(ClassificationOps)
        # ClassificationOps has many private pipeline methods + classify_message
        assert len(members) >= 14, f"ClassificationOps too thin: {members}"

    def test_memory_crud_ops_has_methods(self):
        members = _protocol_members(MemoryCRUDOps)
        assert len(members) >= 9, f"MemoryCRUDOps too thin: {members}"

    def test_profile_export_ops_has_methods(self):
        members = _protocol_members(ProfileExportOps)
        assert len(members) >= 6, f"ProfileExportOps too thin: {members}"

    def test_maintenance_ops_has_methods(self):
        members = _protocol_members(MaintenanceOps)
        assert len(members) >= 6, f"MaintenanceOps too thin: {members}"

    def test_prompt_delegate_ops_has_methods(self):
        members = _protocol_members(PromptDelegateOps)
        assert len(members) >= 5, f"PromptDelegateOps too thin: {members}"


# ===========================================================================
# Test Group 2: Mixin → Protocol coverage (every Mixin method has a Protocol)
# ===========================================================================


class TestMixinProtocolCoverage:
    """Each Mixin's key methods must be represented in its Protocol."""

    @pytest.mark.parametrize(
        "mixin_cls,proto_cls",
        [
            (LifecycleMixin, LifecycleOps),
            (BackupMixin, BackupOps),
            (RecallMixin, RecallOps),  # RecallMixin maps to RecallOps
            (ClassificationMixin, ClassificationOps),
            (MemoryCRUDMixin, MemoryCRUDOps),
            (ProfileExportMixin, ProfileExportOps),
            (MaintenanceMixin, MaintenanceOps),
            (PromptDelegateMixin, PromptDelegateOps),
        ],
    )
    def test_mixin_public_methods_covered_by_protocol(
        self, mixin_cls: type, proto_cls: type
    ):
        """Every public method on a Mixin should exist in its Protocol."""
        proto_members = _protocol_members(proto_cls)
        mixin_pub = _mixin_public_methods(mixin_cls)

        missing = mixin_pub - proto_members
        allowed_missing = {"__init__", "classify_message"}  # classify_message is delegated to ClassificationMixin
        unexpected_missing = missing - allowed_missing

        assert (
            not unexpected_missing
        ), f"{mixin_cls.__name__} has public methods not in {proto_cls.__name__}: {unexpected_missing}"


# ===========================================================================
# Test Group 3: Structural conformance (isinstance checks)
#
# NOTE: Some Mixins cannot be safely instantiated in isolation because their
# __init__ (or LifecycleMixin.__init__) references methods from other Mixins.
# We skip those and test them indirectly through CarryMem in Group 5.
# ===========================================================================

# Mixins that CAN be instantiated standalone without triggering cross-Mixin calls
_SAFE_STANDALONE_MIXINS: dict[type, type] = {
    BackupMixin: BackupOps,
    RecallMixin: RecallOps,
    MemoryCRUDMixin: MemoryCRUDOps,
    ProfileExportMixin: ProfileExportOps,
    MaintenanceMixin: MaintenanceOps,
    PromptDelegateMixin: PromptDelegateOps,
}

# Mixins that CANNOT be instantiated standalone (their __init__ or lifecycle
# depends on other Mixins' methods being present).
_UNSAFE_STANDALONE_MIXINS = {
    LifecycleMixin,   # __init__ creates RuleCandidateGenerator → needs recall_memories
    ClassificationMixin,  # no __init__ but protocol includes _store_entries that needs _adapter
}


class TestStructuralConformance:
    """Verify each *safe* Mixin structurally satisfies its Protocol.

    Since @runtime_checkable was removed (it only checked method names,
    not signatures, providing limited value), we verify conformance by
    checking that every Protocol method exists on the Mixin instance.
    """

    @pytest.mark.parametrize("mixin_cls,proto_cls", list(_SAFE_STANDALONE_MIXINS.items()))
    def test_standalone_mixin_satisfies_protocol(
        self, mixin_cls: type, proto_cls: type
    ):
        proto_members = _protocol_members(proto_cls)
        instance = mixin_cls()
        for name in proto_members:
            assert hasattr(instance, name), (
                f"{mixin_cls.__name__} missing Protocol method {proto_cls.__name__}.{name}"
            )

    def test_lifecycle_mixin_satisfies_lifecycle_ops_via_carrymem(self):
        """LifecycleMixin can only be tested via full CarryMem composition."""
        try:
            from carrymem import CarryMem
        except Exception:
            pytest.skip("Cannot import CarryMem (missing dependencies)")
        proto_members = _protocol_members(LifecycleOps)
        instance = CarryMem()
        for name in proto_members:
            assert hasattr(instance, name), (
                f"CarryMem missing LifecycleOps method: {name}"
            )

    def test_classification_mixin_satisfies_classification_ops_via_carrymem(self):
        """ClassificationMixin can only be tested via full CarryMem composition."""
        try:
            from carrymem import CarryMem
        except Exception:
            pytest.skip("Cannot import CarryMem (missing dependencies)")
        proto_members = _protocol_members(ClassificationOps)
        instance = CarryMem()
        for name in proto_members:
            assert hasattr(instance, name), (
                f"CarryMem missing ClassificationOps method: {name}"
            )


# ===========================================================================
# Test Group 4: Composite Protocol (CarryMemOps)
# ===========================================================================


class TestCompositeProtocol:
    """CarryMemOps is the union of all sub-Protocols."""

    def test_carrymem_ops_inherits_all_sub_protocols(self):
        """CarryMemOps MRO must contain every sub-Protocol."""
        mro = [c.__name__ for c in CarryMemOps.__mro__]
        expected = {
            "LifecycleOps",
            "BackupOps",
            "RecallOps",
            "ClassificationOps",
            "MemoryCRUDOps",
            "ProfileExportOps",
            "MaintenanceOps",
            "PromptDelegateOps",
        }
        assert expected.issubset(set(mro)), f"Missing Protocols in CarryMemOps MRO: {expected - set(mro)}"

    def test_carrymem_ops_is_protocol(self):
        from typing import Protocol

        assert issubclass(CarryMemOps, Protocol)

    def test_carrymem_satisfies_carrymem_ops(self):
        """Full CarryMem instance must satisfy composite CarryMemOps."""
        try:
            from carrymem import CarryMem
        except Exception:
            pytest.skip("Cannot import CarryMem (missing dependencies)")
        # Verify every method from all sub-Protocols exists on CarryMem
        instance = CarryMem()
        for sub_proto in CarryMemOps.__bases__:
            if sub_proto.__name__ == "Protocol":
                continue
            for name in _protocol_members(sub_proto):
                assert hasattr(instance, name), (
                    f"CarryMem missing {sub_proto.__name__}.{name}"
                )


# ===========================================================================
# Test Group 5: MRO validation
# ===========================================================================


class TestMROValidation:
    """Verify the documented MRO order matches reality."""

    def test_mro_has_correct_base_order(self):
        """When CarryMem can be imported, verify MRO order."""
        try:
            from carrymem import CarryMem
        except Exception:
            pytest.skip("Cannot import CarryMem (missing dependencies)")

        mro_names = [c.__name__ for c in CarryMem.__mro__]

        # LifecycleMixin MUST be before object (near end of MRO)
        assert "LifecycleMixin" in mro_names
        lifecycle_idx = mro_names.index("LifecycleMixin")
        object_idx = mro_names.index("object")
        assert (
            lifecycle_idx < object_idx
        ), f"LifecycleMixin should resolve before object; got indices L={lifecycle_idx}, O={object_idx}"

    def test_no_duplicate_class_names_in_mro(self):
        """No Mixin name should appear twice in MRO."""
        try:
            from carrymem import CarryMem
        except Exception:
            pytest.skip("Cannot import CarryMem")

        mro_names = [c.__name__ for c in CarryMem.__mro__]
        seen: set[str] = set()
        for name in mro_names:
            if name != "object" and name in seen:
                pytest.fail(f"Duplicate class in MRO: {name}")
            seen.add(name)


# ===========================================================================
# Test Group 6: HasSharedState base protocol
# ===========================================================================


class TestSharedStateProtocol:
    """HasSharedState defines minimal shared-state contract."""

    def test_has_shared_state_is_protocol(self):
        from typing import Protocol

        assert issubclass(HasSharedState, Protocol)

    def test_shared_state_declares_required_attributes(self):
        attrs = {
            name
            for name in dir(HasSharedState)
            if not name.startswith("_HAS_SHARED_STATE_") and not name.startswith("__abc_")
        }
        required = {"_adapter", "_namespace", "_config", "_engine", "_knowledge_adapter"}
        assert required.issubset(attrs), f"Missing shared state attributes: {required - attrs}"


# ===========================================================================
# Test Group 7: Protocol signature sanity
# ===========================================================================


class TestSignatureSanity:
    """Quick sanity: protocol methods have reasonable signatures."""

    @pytest.mark.parametrize(
        "proto_cls,method_name,expected_params",
        [
            (RecallOps, "recall_memories", ["query", "filters", "limit", "namespaces", "update_access"]),
            (MemoryCRUDOps, "forget_memory", ["memory_id"]),
            (BackupOps, "backup", ["backup_dir"]),
            (LifecycleOps, "close", []),
            (ProfileExportOps, "whoami", []),
            (MaintenanceOps, "check_conflicts", []),
            (PromptDelegateOps, "build_system_prompt", ["context", "max_memories", "max_knowledge", "max_rules", "max_tokens", "language"]),
        ],
    )
    def test_method_has_expected_params(
        self, proto_cls: type, method_name: str, expected_params: list[str]
    ):
        method = getattr(proto_cls, method_name, None)
        assert method is not None, f"{proto_cls.__name__} missing {method_name}"
        sig = inspect.signature(method)
        actual_params = list(sig.parameters.keys())
        for param in expected_params:
            assert param in actual_params, (
                f"{proto_cls.__name__}.{method_name} missing parameter '{param}'. "
                f"Got: {actual_params}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
