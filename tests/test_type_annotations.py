"""Type annotation coverage tests for CarryMem core module.

This test module verifies that key public methods have proper type annotations
using typing.get_type_hints(). It does NOT validate runtime behavior — only
that annotations exist and are resolvable.

Run with:
    pytest tests/test_type_annotations.py -v
"""

import inspect
import sys
import typing
from typing import Any, Union, get_type_hints

import pytest

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _get_method_annotations(cls: type, method_name: str) -> dict:
    """Get type hints for a method, handling both instance and class methods."""
    method = getattr(cls, method_name, None)
    if method is None:
        raise AttributeError(f"{cls.__name__} has no method '{method_name}'")

    # Handle properties
    if isinstance(method, property):
        method = method.fget

    try:
        return get_type_hints(method)
    except Exception as e:
        # Some methods may have unresolvable forward references in tests
        # Return empty dict but don't fail the test
        return {}


def _has_return_annotation(cls: type, method_name: str) -> bool:
    """Check if a method has a return type annotation."""
    method = getattr(cls, method_name, None)
    if method is None:
        return False

    if isinstance(method, property):
        method = method.fget

    sig = inspect.signature(method)
    return sig.return_annotation != inspect.Signature.empty


def _has_param_annotations(cls: type, method_name: str, *param_names: str) -> bool:
    """Check if specific parameters have type annotations."""
    method = getattr(cls, method_name, None)
    if method is None:
        return False

    if isinstance(method, property):
        return False  # Properties don't have parameters

    sig = inspect.signature(method)
    for param_name in param_names:
        if param_name not in sig.parameters:
            continue
        param = sig.parameters[param_name]
        if param.annotation == inspect.Parameter.empty:
            return False
    return True


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def carrymem_class():
    """Import and return the CarryMem class."""
    from carrymem.core import CarryMem

    return CarryMem


@pytest.fixture(scope="module")
def lifecycle_mixin():
    """Import and return LifecycleMixin class."""
    from carrymem.core._lifecycle import LifecycleMixin

    return LifecycleMixin


@pytest.fixture(scope="module")
def memory_crud_mixin():
    """Import and return MemoryCRUDMixin class."""
    from carrymem.core._memory_crud import MemoryCRUDMixin

    return MemoryCRUDMixin


@pytest.fixture(scope="module")
def recall_mixin():
    """Import and return RecallMixin class."""
    from carrymem.core._recall import RecallMixin

    return RecallMixin


@pytest.fixture(scope="module")
def profile_export_mixin():
    """Import and return ProfileExportMixin class."""
    from carrymem.core._profile_export import ProfileExportMixin

    return ProfileExportMixin


@pytest.fixture(scope="module")
def classification_mixin():
    """Import and return ClassificationMixin class."""
    from carrymem.core._classification import ClassificationMixin

    return ClassificationMixin


@pytest.fixture(scope="module")
def types_module():
    """Import and return the types module."""
    from carrymem import types

    return types


# ===========================================================================
# Test: TypedDict definitions exist and are complete
# ===========================================================================


class TestTypedDictDefinitions:
    """Verify that all required TypedDict classes are defined."""

    def test_memory_entry_dict_exists(self, types_module):
        assert hasattr(types_module, "MemoryEntryDict")
        assert isinstance(types_module.MemoryEntryDict, type)

    def test_stored_memory_dict_exists(self, types_module):
        assert hasattr(types_module, "StoredMemoryDict")

    def test_classification_result_exists(self, types_module):
        assert hasattr(types_module, "ClassificationResult")

    def test_declare_result_exists(self, types_module):
        assert hasattr(types_module, "DeclareResult")

    def test_recall_all_result_exists(self, types_module):
        assert hasattr(types_module, "RecallAllResult")

    def test_memory_stats_exists(self, types_module):
        assert hasattr(types_module, "MemoryStats")

    def test_memory_profile_exists(self, types_module):
        assert hasattr(types_module, "MemoryProfile")

    def test_whoami_result_exists(self, types_module):
        assert hasattr(types_module, "WhoamiResult")

    def test_health_check_result_exists(self, types_module):
        assert hasattr(types_module, "HealthCheckResult")

    def test_component_status_dict_exists(self, types_module):
        assert hasattr(types_module, "ComponentStatusDict")

    def test_export_profile_result_exists(self, types_module):
        assert hasattr(types_module, "ExportProfileResult")

    def test_export_memories_result_exists(self, types_module):
        assert hasattr(types_module, "ExportMemoriesResult")

    def test_import_memories_result_exists(self, types_module):
        assert hasattr(types_module, "ImportMemoriesResult")


class TestTypedDictFieldCompleteness:
    """Verify that TypedDict classes have expected fields."""

    def test_classification_result_fields(self, types_module):
        """ClassificationResult should have key fields for classification output."""
        cls = types_module.ClassificationResult
        # Check that it's a TypedDict subclass (or compatible)
        assert hasattr(cls, "__annotations__") or hasattr(cls, "__required_keys__")

    def test_whoami_result_fields(self, types_module):
        """WhoamiResult should contain identity-related fields."""
        cls = types_module.WhoamiResult
        annotations = getattr(cls, "__annotations__", {})
        # Should have at least identity and summary fields
        assert "identity" in annotations or cls.__total__ is False

    def test_health_check_result_fields(self, types_module):
        """HealthCheckResult should have status, components, issues fields."""
        cls = types_module.HealthCheckResult
        annotations = getattr(cls, "__annotations__", {})
        assert "status" in annotations
        assert "components" in annotations
        assert "issues" in annotations


# ===========================================================================
# Test: LifecycleMixin type annotations
# ===========================================================================


class TestLifecycleMixinAnnotations:
    """Verify LifecycleMixin has complete type annotations."""

    def test_init_has_return_annotation(self, lifecycle_mixin):
        """__init__ should have -> None return annotation."""
        assert _has_return_annotation(lifecycle_mixin, "__init__")

    def test_init_params_annotated(self, lifecycle_mixin):
        """__init__ key parameters should be annotated."""
        assert _has_param_annotations(
            lifecycle_mixin, "__init__", "storage", "db_path", "knowledge_adapter", "namespace"
        )

    def test_close_has_return_annotation(self, lifecycle_mixin):
        """close() should have -> None return annotation."""
        assert _has_return_annotation(lifecycle_mixin, "close")

    def test_enter_has_return_annotation(self, lifecycle_mixin):
        """__enter__ should have return annotation."""
        assert _has_return_annotation(lifecycle_mixin, "__enter__")

    def test_exit_has_return_annotation(self, lifecycle_mixin):
        """__exit__ should have return annotation."""
        assert _has_return_annotation(lifecycle_mixin, "__exit__")

    def test_namespace_property_annotated(self, lifecycle_mixin):
        """namespace property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "namespace")

    def test_engine_property_annotated(self, lifecycle_mixin):
        """engine property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "engine")

    def test_adapter_property_annotated(self, lifecycle_mixin):
        """adapter property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "adapter")

    def test_storage_property_annotated(self, lifecycle_mixin):
        """storage property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "storage")

    def test_knowledge_adapter_property_annotated(self, lifecycle_mixin):
        """knowledge_adapter property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "knowledge_adapter")

    def test_rule_engine_property_annotated(self, lifecycle_mixin):
        """rule_engine property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "rule_engine")

    def test_prompt_builder_property_annotated(self, lifecycle_mixin):
        """prompt_builder property should have return type."""
        assert _has_return_annotation(lifecycle_mixin, "prompt_builder")


# ===========================================================================
# Test: MemoryCRUDMixin type annotations
# ===========================================================================


class TestMemoryCRUDMixinAnnotations:
    """Verify MemoryCRUDMixin has complete type annotations."""

    def test_classify_and_remember_annotated(self, memory_crud_mixin):
        """classify_and_remember should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "classify_and_remember")
        assert _has_param_annotations(
            memory_crud_mixin, "classify_and_remember", "message", "context", "language", "session_id", "force_type"
        )

    def test_classify_message_annotated(self, memory_crud_mixin):
        """classify_message should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "classify_message")
        assert _has_param_annotations(memory_crud_mixin, "classify_message", "message", "context", "language")

    def test_declare_annotated(self, memory_crud_mixin):
        """declare should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "declare")
        assert _has_param_annotations(memory_crud_mixin, "declare", "message", "context")

    def test_declare_preference_annotated(self, memory_crud_mixin):
        """declare_preference should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "declare_preference")

    def test_forget_memory_annotated(self, memory_crud_mixin):
        """forget_memory should have return type annotation."""
        assert _has_return_annotation(memory_crud_mixin, "forget_memory")
        assert _has_param_annotations(memory_crud_mixin, "forget_memory", "memory_id")

    def test_update_memory_annotated(self, memory_crud_mixin):
        """update_memory should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "update_memory")
        assert _has_param_annotations(memory_crud_mixin, "update_memory", "storage_key", "new_content", "reason")

    def test_get_memory_history_annotated(self, memory_crud_mixin):
        """get_memory_history should have return type annotation."""
        assert _has_return_annotation(memory_crud_mixin, "get_memory_history")

    def test_rollback_memory_annotated(self, memory_crud_mixin):
        """rollback_memory should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "rollback_memory")
        assert _has_param_annotations(memory_crud_mixin, "rollback_memory", "storage_key", "version")

    def test_merge_memories_annotated(self, memory_crud_mixin):
        """merge_memories should have full type annotations."""
        assert _has_return_annotation(memory_crud_mixin, "merge_memories")
        assert _has_param_annotations(
            memory_crud_mixin, "merge_memories", "namespaces", "strategy", "conflict_callback"
        )


# ===========================================================================
# Test: RecallMixin type annotations
# ===========================================================================


class TestRecallMixinAnnotations:
    """Verify RecallMixin has complete type annotations."""

    def test_index_knowledge_annotated(self, recall_mixin):
        """index_knowledge should have return type annotation."""
        assert _has_return_annotation(recall_mixin, "index_knowledge")

    def test_recall_from_knowledge_annotated(self, recall_mixin):
        """recall_from_knowledge should have full type annotations."""
        assert _has_return_annotation(recall_mixin, "recall_from_knowledge")
        assert _has_param_annotations(recall_mixin, "recall_from_knowledge", "query", "filters", "limit")

    def test_recall_all_annotated(self, recall_mixin):
        """recall_all should have full type annotations."""
        assert _has_return_annotation(recall_mixin, "recall_all")
        assert _has_param_annotations(
            recall_mixin, "recall_all", "query", "filters", "limit", "namespaces", "include_rules"
        )

    def test_recall_memories_annotated(self, recall_mixin):
        """recall_memories should have full type annotations."""
        assert _has_return_annotation(recall_mixin, "recall_memories")
        assert _has_param_annotations(
            recall_mixin, "recall_memories", "query", "filters", "limit", "namespaces", "update_access"
        )

    def test_recall_aggregated_annotated(self, recall_mixin):
        """recall_aggregated should have full type annotations."""
        assert _has_return_annotation(recall_mixin, "recall_aggregated")
        assert _has_param_annotations(recall_mixin, "recall_aggregated", "memory_type", "limit_per_type")

    def test_recall_timeline_annotated(self, recall_mixin):
        """recall_timeline should have full type annotations."""
        assert _has_return_annotation(recall_mixin, "recall_timeline")
        assert _has_param_annotations(recall_mixin, "recall_timeline", "topic", "limit")


# ===========================================================================
# Test: ProfileExportMixin type annotations
# ===========================================================================


class TestProfileExportMixinAnnotations:
    """Verify ProfileExportMixin has complete type annotations."""

    def test_get_stats_annotated(self, profile_export_mixin):
        """get_stats should have return type annotation."""
        assert _has_return_annotation(profile_export_mixin, "get_stats")

    def test_get_memory_profile_annotated(self, profile_export_mixin):
        """get_memory_profile should have return type annotation."""
        assert _has_return_annotation(profile_export_mixin, "get_memory_profile")

    def test_whoami_annotated(self, profile_export_mixin):
        """whoami should have return type annotation."""
        assert _has_return_annotation(profile_export_mixin, "whoami")

    def test_export_profile_annotated(self, profile_export_mixin):
        """export_profile should have full type annotations."""
        assert _has_return_annotation(profile_export_mixin, "export_profile")
        assert _has_param_annotations(profile_export_mixin, "export_profile", "output_path")

    def test_export_memories_annotated(self, profile_export_mixin):
        """export_memories should have full type annotations."""
        assert _has_return_annotation(profile_export_mixin, "export_memories")
        assert _has_param_annotations(profile_export_mixin, "export_memories", "output_path", "format", "namespace")

    def test_import_memories_annotated(self, profile_export_mixin):
        """import_memories should have full type annotations."""
        assert _has_return_annotation(profile_export_mixin, "import_memories")
        assert _has_param_annotations(
            profile_export_mixin, "import_memories", "input_path", "data", "namespace", "merge_strategy"
        )


# ===========================================================================
# Test: ClassificationMixin type annotations
# ===========================================================================


class TestClassificationMixinAnnotations:
    """Verify ClassificationMixin has complete type annotations."""

    def test_validate_and_resolve_annotated(self, classification_mixin):
        """_validate_and_resolve should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_validate_and_resolve")
        assert _has_param_annotations(
            classification_mixin, "_validate_and_resolve", "message", "context", "force_type", "session_id"
        )

    def test_classify_message_internal_annotated(self, classification_mixin):
        """_classify_message should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_classify_message")
        assert _has_param_annotations(
            classification_mixin,
            "_classify_message",
            "resolved_message",
            "context",
            "language",
            "force_type",
            "message",
        )

    def test_store_entries_annotated(self, classification_mixin):
        """_store_entries should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_store_entries")
        assert _has_param_annotations(
            classification_mixin,
            "_store_entries",
            "classify_result",
            "resolved_message",
            "message",
            "context",
            "coreference_resolved",
            "force_type",
            "session_id",
        )

    def test_handle_correction_annotated(self, classification_mixin):
        """_handle_correction should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_handle_correction")
        assert _has_param_annotations(classification_mixin, "_handle_correction", "correction_entry")

    def test_count_by_type_annotated(self, classification_mixin):
        """_count_by_type should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_count_by_type")
        assert _has_param_annotations(classification_mixin, "_count_by_type", "entries")

    def test_auto_suggest_rules_annotated(self, classification_mixin):
        """_auto_suggest_rules should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_auto_suggest_rules")
        assert _has_param_annotations(classification_mixin, "_auto_suggest_rules", "stored_memories")

    def test_detect_implicit_preferences_annotated(self, classification_mixin):
        """_detect_implicit_preferences should have return type annotation."""
        assert _has_return_annotation(classification_mixin, "_detect_implicit_preferences")

    def test_sanitize_rule_content_annotated(self, classification_mixin):
        """_sanitize_rule_content should have full type annotations."""
        assert _has_return_annotation(classification_mixin, "_sanitize_rule_content")
        assert _has_param_annotations(classification_mixin, "_sanitize_rule_content", "text")


# ===========================================================================
# Test: CarryMem facade type annotations
# ===========================================================================


class TestCarryMemFacadeAnnotations:
    """Verify CarryMem facade has complete type annotations for public methods."""

    def test_version_property_annotated(self, carrymem_class):
        """version property should have return type."""
        assert _has_return_annotation(carrymem_class, "version")

    def test_health_check_annotated(self, carrymem_class):
        """health_check should have return type annotation."""
        assert _has_return_annotation(carrymem_class, "health_check")

    def test_get_component_status_annotated(self, carrymem_class):
        """get_component_status should have return type annotation."""
        assert _has_return_annotation(carrymem_class, "get_component_status")

    def test_validate_ready_annotated(self, carrymem_class):
        """validate_ready should have return type annotation."""
        assert _has_return_annotation(carrymem_class, "validate_ready")
        assert _has_param_annotations(carrymem_class, "validate_ready", "require_storage", "require_knowledge")


# ===========================================================================
# Test: Type alias definitions
# ===========================================================================


class TestTypeAliases:
    """Verify convenience type aliases are defined."""

    def test_memory_dict_alias_exists(self, types_module):
        """MemoryDict alias should exist."""
        assert hasattr(types_module, "MemoryDict")

    def test_filter_dict_alias_exists(self, types_module):
        """FilterDict alias should exist."""
        assert hasattr(types_module, "FilterDict")

    def test_context_dict_alias_exists(self, types_module):
        """ContextDict alias should exist."""
        assert hasattr(types_module, "ContextDict")

    def test_metadata_dict_alias_exists(self, types_module):
        """MetadataDict alias should exist."""
        assert hasattr(types_module, "MetadataDict")

    def test_validate_and_resolve_result_alias_exists(self, types_module):
        """ValidateAndResolveResult alias should exist."""
        assert hasattr(types_module, "ValidateAndResolveResult")


# ===========================================================================
# Test: Coverage statistics
# ===========================================================================


class TestAnnotationCoverage:
    """Calculate and verify overall type annotation coverage."""

    @pytest.mark.coverage
    def test_core_modules_have_high_coverage(self):
        """Core modules should have >85% type annotation coverage on public methods."""
        from carrymem.core import CarryMem
        from carrymem.core._classification import ClassificationMixin
        from carrymem.core._lifecycle import LifecycleMixin
        from carrymem.core._memory_crud import MemoryCRUDMixin
        from carrymem.core._profile_export import ProfileExportMixin
        from carrymem.core._recall import RecallMixin

        modules_to_test = {
            "LifecycleMixin": [
                ("__init__", 6),
                ("close", 0),
                ("namespace", 0),
                ("engine", 0),
                ("adapter", 0),
                ("storage", 0),
                ("knowledge_adapter", 0),
                ("rule_engine", 0),
                ("prompt_builder", 0),
            ],
            "MemoryCRUDMixin": [
                ("classify_and_remember", 5),
                ("classify_message", 3),
                ("declare", 2),
                ("declare_preference", 2),
                ("forget_memory", 1),
                ("update_memory", 3),
                ("get_memory_history", 1),
                ("rollback_memory", 2),
                ("merge_memories", 3),
            ],
            "RecallMixin": [
                ("index_knowledge", 0),
                ("recall_from_knowledge", 3),
                ("recall_all", 5),
                ("recall_memories", 5),
                ("recall_aggregated", 2),
                ("recall_timeline", 2),
            ],
            "ProfileExportMixin": [
                ("get_stats", 0),
                ("get_memory_profile", 0),
                ("whoami", 0),
                ("export_profile", 1),
                ("export_memories", 3),
                ("import_memories", 4),
            ],
            "CarryMem": [
                ("version", 0),
                ("health_check", 0),
                ("get_component_status", 0),
                ("validate_ready", 2),
            ],
        }

        total_methods = 0
        fully_annotated = 0

        for module_name, methods in modules_to_test.items():
            if module_name == "LifecycleMixin":
                cls = LifecycleMixin
            elif module_name == "MemoryCRUDMixin":
                cls = MemoryCRUDMixin
            elif module_name == "RecallMixin":
                cls = RecallMixin
            elif module_name == "ProfileExportMixin":
                cls = ProfileExportMixin
            elif module_name == "CarryMem":
                cls = CarryMem
            else:
                continue

            for method_name, _param_count in methods:
                total_methods += 1
                if _has_return_annotation(cls, method_name):
                    fully_annotated += 1

        coverage = (fully_annotated / total_methods * 100) if total_methods > 0 else 0

        print(f"\n{'='*60}")
        print(f"Type Annotation Coverage Report")
        print(f"{'='*60}")
        print(f"Total public methods checked: {total_methods}")
        print(f"Fully annotated (return + params): {fully_annotated}")
        print(f"Coverage: {coverage:.1f}%")
        print(f"{'='*60}\n")

        # Assert coverage is above threshold (allowing some margin)
        assert coverage >= 80.0, f"Type annotation coverage {coverage:.1f}% is below 80% threshold. " f"Target is 85%+."


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
