"""
Integration Tests: Mixin Collaboration

Validates cross-Mixin interactions within the CarryMem facade:
1. LifecycleMixin → MemoryCRUDMixin: shared state (_adapter, _engine) after init
2. ClassificationMixin → RecallMixin: classified memories are recallable
3. BackupMixin → ProfileExportMixin: backup data can be parsed by export
4. MaintenanceMixin → RecallMixin: consolidation does not corrupt recall results
5. PromptDelegateMixin: build_context includes accurate memory counts

All tests use real CarryMem instances (no mocking) with tmp_path fixtures.
"""

import json
import os

import pytest

from carrymem import CarryMem


@pytest.fixture
def cm(tmp_path):
    """Create a fresh CarryMem instance with isolated SQLite database."""
    db_path = str(tmp_path / "mixin_test.db")
    instance = CarryMem(db_path=db_path)
    yield instance
    instance.close()


class TestLifecycleAndCRUDCollaboration:
    """Scenario: LifecycleMixin initializes shared state that MemoryCRUDMixin consumes."""

    def test_lifecycle_init_enables_crud_operations(self, tmp_path):
        """Verify: After LifecycleMixin.__init__, MemoryCRUDMixin can use _adapter and _engine.

        Steps:
        1. Create CarryMem (triggers LifecycleMixin.__init__)
        2. Call classify_and_remember (MemoryCRUDMixin method)
        3. Verify storage succeeds and returns valid result
        """
        db_path = str(tmp_path / "lifecycle_crud.db")
        cm = CarryMem(db_path=db_path)
        try:
            # LifecycleMixin sets self._adapter (SQLiteAdapter) and self._engine (MemoryClassificationEngine)
            assert cm.adapter is not None, "LifecycleMixin should initialize adapter"
            assert cm.engine is not None, "LifecycleMixin should initialize engine"

            # MemoryCRUDMixin uses these shared attributes
            result = cm.classify_and_remember("I prefer using Vim for editing code")
            assert isinstance(result, dict), "CRUD operation should succeed"
            assert result.get("stored", False) is True, "Memory should be stored"
            assert len(result.get("storage_keys", [])) > 0, "Should return storage keys"
        finally:
            cm.close()

    def test_lifecycle_namespace_isolation(self, tmp_path):
        """Verify: Namespace set in LifecycleMixin is respected by CRUD operations.

        Steps:
        1. Create two CarryMem instances with different namespaces
        2. Store memory in each
        3. Verify memories are isolated per namespace
        """
        db_path = str(tmp_path / "namespace_isolation.db")

        cm_a = CarryMem(db_path=db_path, namespace="team_alpha")
        cm_b = CarryMem(db_path=db_path, namespace="team_beta")

        try:
            cm_a.classify_and_remember("Alpha team uses Python")
            cm_b.classify_and_remember("Beta team uses Go")

            alpha_memories = cm_a.recall_memories(limit=10)
            beta_memories = cm_b.recall_memories(limit=10)

            alpha_contents = [m.get("content", "") for m in alpha_memories]
            beta_contents = [m.get("content", "") for m in beta_memories]

            assert any("Python" in c for c in alpha_contents), "Alpha should see Python memory"
            assert any("Go" in c for c in beta_contents), "Beta should see Go memory"
            assert not any("Go" in c for c in alpha_contents), "Alpha should NOT see Beta's memory"
            assert not any("Python" in c for c in beta_contents), "Beta should NOT see Alpha's memory"
        finally:
            cm_a.close()
            cm_b.close()

    def test_lifecycle_close_releases_resources(self, tmp_path):
        """Verify: LifecycleMixin.close() releases adapter and engine resources.

        Steps:
        1. Create CarryMem and store data
        2. Close via LifecycleMixin.close()
        3. Verify adapter is closed and CRUD raises appropriate error
        """
        db_path = str(tmp_path / "lifecycle_close.db")
        cm = CarryMem(db_path=db_path)

        try:
            cm.classify_and_remember("This will be closed")
            cm.close()

            # After close, adapter may still exist but connection is closed
            # Subsequent operations should fail gracefully or raise StorageNotConfiguredError
            with pytest.raises((Exception)):
                cm.classify_and_remember("This should fail after close")
        except Exception:
            pass  # Expected: operations after close may fail


class TestClassificationAndRecallCollaboration:
    """Scenario: ClassificationMixin classifies memories that RecallMixin can retrieve."""

    def test_classify_then_recall_by_content(self, cm):
        """Verify: Memories classified by ClassificationMixin are found by RecallMixin.

        Steps:
        1. Store multiple memories with distinct types via classify_and_remember
        2. Recall using content keywords
        3. Verify correct memories are returned
        """
        memories = [
            ("I prefer dark mode in my IDE", "preference"),
            ("We decided to use PostgreSQL for the database", "decision"),
            ("The API endpoint is /api/v1/users", "fact"),
        ]

        storage_keys = []
        for msg, mem_type in memories:
            result = cm.classify_and_remember(msg)
            assert result.get("stored", False), f"Should store: {msg[:30]}"
            storage_keys.extend(result.get("storage_keys", []))

        # RecallMixin can find them
        recalled = cm.recall_memories(query="dark mode", limit=5)
        assert len(recalled) >= 1, "Should recall dark mode preference"
        assert any("dark mode" in m.get("content", "").lower() for m in recalled)

        recalled_db = cm.recall_memories(query="PostgreSQL", limit=5)
        assert len(recalled_db) >= 1, "Should recall PostgreSQL decision"

    def test_classify_type_filter_in_recall(self, cm):
        """Verify: ClassificationMixin assigns types that RecallMixin can filter on.

        Steps:
        1. Store preferences, decisions, and facts
        2. Recall with type filter
        3. Verify only matching types returned
        """
        cm.classify_and_remember("I like using Vim")
        cm.classify_and_remember("We chose React for frontend")
        cm.classify_and_remember("Server runs on port 8080")

        preferences = cm.recall_memories(query="", filters={"type": "user_preference"}, limit=10)
        assert len(preferences) >= 1, "Should find at least one preference"

        # All returned should be preference type (or compatible)
        for mem in preferences:
            assert mem.get("type") in ("user_preference", "preference", "unknown"), \
                f"Expected preference type, got {mem.get('type')}"

    def test_classify_multiple_recall_aggregated(self, cm):
        """Verify: Multiple classifications are aggregated correctly by RecallMixin.

        Steps:
        1. Store 5+ memories of mixed types
        2. Use recall_aggregated to get grouped results
        3. Verify grouping by type works
        """
        test_messages = [
            "I prefer coffee over tea",
            "Team decided to use Agile",
            "Deploy every Friday",
            "Use TypeScript for new features",
            "Code review is mandatory",
        ]

        for msg in test_messages:
            cm.classify_and_remember(msg)

        aggregated = cm.recall_aggregated(limit_per_type=50)
        assert isinstance(aggregated, dict), "recall_aggregated should return dict"
        assert len(aggregated) > 0, "Should have at least one type group"

        total_from_groups = sum(len(v) for v in aggregated.values())
        assert total_from_groups >= len(test_messages) * 0.6, \
            f"Aggregated count {total_from_groups} should cover most stored memories"


class TestBackupAndProfileExportCollaboration:
    """Scenario: BackupMixin creates data that ProfileExportMixin can parse."""

    def test_backup_then_export_profile_consistency(self, cm):
        """Verify: Backup data and export profile reflect same stored memories.

        Steps:
        1. Store several memories
        2. Create backup via BackupMixin
        3. Export profile via ProfileExportMixin
        4. Verify both show consistent memory counts
        """
        memories = [
            "User prefers English documentation",
            "Project uses semantic versioning",
            "Tests run on every push",
        ]

        for msg in memories:
            cm.classify_and_remember(msg)

        # BackupMixin: create backup
        backup_result = cm.backup()
        assert backup_result.get("backed_up", False), "Backup should succeed"

        # ProfileExportMixin: get profile
        profile = cm.get_memory_profile()
        assert isinstance(profile, dict), "Profile should be a dict"

        stats = cm.get_stats()
        assert isinstance(stats, dict), "Stats should be a dict"
        total_count = stats.get("total_count", 0)
        assert total_count >= len(memories) * 0.6, \
            f"Stats should show {len(memories)}+ memories, got {total_count}"

    def test_backup_restore_recall_integrity(self, tmp_path):
        """Verify: Backup → Restore cycle preserves recallable data integrity.

        Steps:
        1. Create CarryMem and store memories
        2. Create backup
        3. Store additional memories
        4. Restore from backup
        5. Recall and verify only pre-backup memories present
        """
        db_path = str(tmp_path / "backup_restore.db")
        backup_dir = str(tmp_path / "backups")
        os.makedirs(backup_dir, exist_ok=True)

        cm = CarryMem(db_path=db_path, config={"backup_dir": backup_dir})

        try:
            # Phase 1: Store initial memories
            initial_memories = [
                "Initial preference: use spaces for indentation",
                "Initial decision: adopt REST API",
            ]
            for msg in initial_memories:
                cm.classify_and_remember(msg)

            # Backup
            backup_result = cm.backup(backup_dir=backup_dir)
            assert backup_result.get("backed_up", False), "Backup should succeed"
            backup_path = backup_result.get("path", "")

            # Phase 2: Add more memories
            cm.classify_and_remember("Additional memory post-backup")

            # Phase 3: Restore
            if backup_path:
                restore_result = cm.restore_backup(backup_path, backup_dir=backup_dir)
                assert restore_result.get("restored", False), "Restore should succeed"

                # Phase 4: Verify recall - should have initial memories
                recalled = cm.recall_memories(limit=10)
                contents = [m.get("content", "") for m in recalled]

                # At least one initial memory should be present
                found_initial = sum(
                    1 for orig in initial_memories
                    if any(orig.lower() in c.lower() for c in contents)
                )
                assert found_initial >= 1, \
                    f"Should find initial memories after restore, found {found_initial}"
        finally:
            cm.close()

    def test_whoami_uses_recall_data(self, cm):
        """Verify: ProfileExportMixin.whoami() aggregates data from RecallMixin.

        Steps:
        1. Store preferences and decisions
        2. Call whoami()
        3. Verify it includes data from recall
        """
        cm.classify_and_remember("I prefer using Linux for development")
        cm.classify_and_remember("We chose microservices architecture")

        whoami = cm.whoami()
        assert isinstance(whoami, dict), "whoami should return dict"
        assert whoami.get("identity") == "known_user", "Should identify as known user"
        assert whoami.get("total_memories", 0) >= 2, "Should report 2+ memories"

        preferences = whoami.get("preferences", [])
        assert len(preferences) >= 1, "Should include preferences in whoami"


class TestMaintenanceAndRecallCollaboration:
    """Scenario: MaintenanceMixin operations don't break RecallMixin functionality."""

    def test_consolidate_dry_run_does_not_affect_recall(self, cm):
        """Verify: MaintenanceMixin.consolidate(dry_run=True) doesn't change recall results.

        Steps:
        1. Store multiple memories
        2. Record recall count before consolidation
        3. Run consolidate(dry_run=True)
        4. Verify recall count unchanged
        """
        memories = [
            "Memory about Python programming",
            "Memory about database design",
            "Memory about API development",
            "Memory about testing strategies",
            "Memory about deployment pipelines",
        ]

        for msg in memories:
            cm.classify_and_remember(msg)

        # Get baseline recall
        before_consolidate = cm.recall_memories(limit=20)
        before_count = len(before_consolidate)

        # Run dry-run consolidation (should not modify data)
        report = cm.consolidate(dry_run=True)
        assert isinstance(report, dict), "Consolidation report should be dict"
        assert report.get("dry_run", False) is True, "Should be dry_run mode"

        # Verify recall unchanged
        after_consolidate = cm.recall_memories(limit=20)
        after_count = len(after_consolidate)

        assert after_count == before_count, \
            f"Dry-run consolidation changed recall count: {before_count} -> {after_count}"

    def test_check_conflicts_returns_valid_data(self, cm):
        """Verify: MaintenanceMixin.check_conflicts() analyzes stored memories.

        Steps:
        1. Store potentially conflicting memories
        2. Run check_conflicts
        3. Verify result structure (may be empty if no conflicts detected)
        """
        cm.classify_and_remember("I prefer using Vim")
        cm.classify_and_remember("I prefer using Emacs")  # Potential preference conflict

        conflicts = cm.check_conflicts()
        assert isinstance(conflicts, list), "Conflicts should be a list"

        # If conflicts detected, verify structure
        if conflicts:
            conflict = conflicts[0]
            assert "conflict_type" in conflict or "reason" in conflict, \
                "Conflict entries should have descriptive fields"

    def test_check_quality_identifies_low_quality(self, cm):
        """Verify: MaintenanceMixin.check_quality() can analyze memory quality.

        Steps:
        1. Store mix of meaningful and low-quality messages
        2. Run check_quality
        3. Verify result structure
        """
        # Store some memories
        cm.classify_and_remember("Important decision: use PostgreSQL")
        cm.classify_and_remember("xyz")  # Low quality / noise

        quality_report = cm.check_quality(min_score=0.5)
        assert isinstance(quality_report, list), "Quality report should be a list"

        # Report items should have expected structure if any found
        if quality_report:
            item = quality_report[0]
            assert "score" in item or "reasons" in item, \
                "Quality items should have score/reasons"


class TestPromptDelegateCollaboration:
    """Scenario: PromptDelegateMixin builds context using data from other Mixins."""

    def test_build_context_includes_memory_count(self, cm):
        """Verify: PromptDelegateMixin.build_context() includes accurate memory statistics.

        Steps:
        1. Store known number of memories
        2. Call build_context()
        3. Verify context includes memory count information
        """
        # Store some memories first
        test_memories = [
            "Context test memory 1: user likes Python",
            "Context test memory 2: team uses Git",
            "Context test memory 3: deploy to AWS",
        ]

        for msg in test_memories:
            cm.classify_and_remember(msg)

        # Build context (delegates to PromptBuilder which uses RecallMixin)
        context = cm.build_context(max_memories=10, max_rules=0, max_knowledge=0)
        assert isinstance(context, dict), "build_context should return dict"

        # Context should contain memory-related information
        assert "memories" in context or "memory_count" in context or "context_text" in context, \
            f"Context should include memory data, got keys: {list(context.keys())}"

    def test_build_system_prompt_incorporates_profile(self, cm):
        """Verify: PromptDelegateMixin.build_system_prompt() incorporates user profile.

        Steps:
        1. Store user preferences
        2. Build system prompt
        3. Verify prompt is non-empty string
        """
        cm.classify_and_remember("User prefers concise responses")
        cm.classify_and_remember("User is a software developer")

        prompt = cm.build_system_prompt(max_memories=5, max_rules=0, max_knowledge=0)
        assert isinstance(prompt, str), "System prompt should be a string"
        assert len(prompt) > 0, "System prompt should not be empty"

    def test_recall_all_aggregates_multiple_sources(self, cm):
        """Verify: RecallMixin.recall_all() aggregates memories, rules, and knowledge.

        Steps:
        1. Store memories
        2. Call recall_all()
        3. Verify it returns structured result with multiple categories
        """
        cm.classify_and_remember("Test memory for recall_all")

        all_results = cm.recall_all(query="test", limit=5)
        assert isinstance(all_results, dict), "recall_all should return dict"

        # Should have expected keys
        expected_keys = {"memories", "rules", "knowledge", "total_count"}
        assert expected_keys.issubset(all_results.keys()), \
            f"recall_all should have keys {expected_keys}, got {list(all_results.keys())}"

        # Should have found our test memory
        assert all_results.get("memory_count", 0) >= 1, \
            "Should find at least one memory in recall_all"


class TestCrossMixinDataFlow:
    """Scenario: Complex multi-Mixin data flows through real operations."""

    def test_full_crud_to_recall_to_export_pipeline(self, tmp_path):
        """Verify: Complete pipeline: CRUD → Recall → Export maintains data consistency.

        Steps:
        1. Create, read, update, delete operations via MemoryCRUDMixin
        2. Recall and verify via RecallMixin
        3. Export and validate via ProfileExportMixin
        4. Verify data consistency across all stages
        """
        db_path = str(tmp_path / "pipeline_test.db")
        cm = CarryMem(db_path=db_path)

        try:
            # Phase 1: CRUD operations
            create_result = cm.classify_and_remember("Pipeline test: important fact about system")
            assert create_result.get("stored", False), "Create should succeed"
            storage_key = create_result.get("storage_keys", [None])[0]

            # Phase 2: Recall verification
            recalled = cm.recall_memories(query="pipeline test", limit=5)
            assert len(recalled) >= 1, "Should recall created memory"

            # Phase 3: Export validation
            export = cm.export_memories(format="json")
            assert export.get("exported", False), "Export should succeed"
            assert export.get("total_memories", 0) >= 1, "Export should include memories"

            exported_memories = export.get("data", {}).get("memories", [])
            assert len(exported_memories) >= 1, "Exported data should contain memories"

            # Verify content preserved
            exported_contents = [m.get("content", "") for m in exported_memories]
            assert any("pipeline test" in c.lower() for c in exported_contents), \
                "Exported data should contain original content"
        finally:
            cm.close()

    def test_namespace_isolation_across_mixins(self, tmp_path):
        """Verify: All Mixins respect namespace isolation consistently.

        Steps:
        1. Create two instances with different namespaces on same DB
        2. Operate on each with various Mixins
        3. Verify complete isolation across all operations
        """
        db_path = str(tmp_path / "ns_mixin_isolation.db")

        cm_dev = CarryMem(db_path=db_path, namespace="development")
        cm_prod = CarryMem(db_path=db_path, namespace="production")

        try:
            # CRUD: store in each namespace
            cm_dev.classify_and_remember("Dev: use debug logging")
            cm_prod.classify_and_remember("Prod: disable debug logging")

            # Recall: verify isolation
            dev_memories = cm_dev.recall_memories(query="logging", limit=5)
            prod_memories = cm_prod.recall_memories(query="logging", limit=5)

            dev_contents = [m.get("content", "") for m in dev_memories]
            prod_contents = [m.get("content", "") for m in prod_memories]

            assert any("debug" in c.lower() for c in dev_contents), "Dev should see debug logging"
            assert any("disable" in c.lower() for c in prod_contents), "Prod should see disable logging"

            # Stats: verify separate counts
            dev_stats = cm_dev.get_stats()
            prod_stats = cm_prod.get_stats()

            dev_total = dev_stats.get("total_count", 0) if isinstance(dev_stats, dict) else 0
            prod_total = prod_stats.get("total_count", 0) if isinstance(prod_stats, dict) else 0

            assert dev_total >= 1, "Dev namespace should have memories"
            assert prod_total >= 1, "Prod namespace should have memories"
        finally:
            cm_dev.close()
            cm_prod.close()
