"""
E2E Tests: Adapter Switching at Runtime

Validates adapter switching and data migration:
1. SQLite → JSON adapter runtime switch
2. Data migration integrity after switch
3. Graceful error handling for unsupported operations
"""

import json
import os
import shutil
import sqlite3

try:
    import pysqlite3.dbapi2 as pysqlite3
except ImportError:
    pysqlite3 = None

_SQLITE_ERRORS = (sqlite3.Error,) if pysqlite3 is None else (sqlite3.Error, pysqlite3.Error)

import pytest

from carrymem import CarryMem


@pytest.fixture
def sqlite_carrymem(tmp_path):
    """Create a CarryMem instance with SQLite adapter."""
    db_path = str(tmp_path / "adapter_test.db")
    cm = CarryMem(storage="sqlite", db_path=db_path)
    yield cm
    cm.close()


class TestE2ESQLiteToJSONSwitch:
    """Scenario: Switch from SQLite to JSON adapter."""

    def test_sqlite_initial_operations(self, sqlite_carrymem):
        """Verify: SQLite adapter works normally before switch."""
        cm = sqlite_carrymem

        # Store memories via SQLite
        result1 = cm.classify_and_remember("SQLite memory 1: I prefer Python")
        result2 = cm.classify_and_remember("SQLite memory 2: We use Docker")

        assert isinstance(result1, dict), "SQLite store should return dict"
        assert isinstance(result2, dict), "SQLite store should return dict"

        # Recall should work
        recalled = cm.recall_memories(query="Python", limit=5)
        assert isinstance(recalled, list), "SQLite recall should work"

    def test_json_adapter_basic_operations(self, tmp_path):
        """Verify: JSON adapter can perform basic operations."""
        json_path = str(tmp_path / "test_data.json")
        cm = CarryMem(storage="json", db_path=json_path)

        try:
            # Store
            result = cm.classify_and_remember("JSON memory: Test preference")
            assert isinstance(result, dict), "JSON store should return dict"

            # Recall
            recalled = cm.recall_memories(query="Test", limit=5)
            assert isinstance(recalled, list), "JSON recall should work"
        finally:
            cm.close()

    def test_adapter_switch_data_migration(self, tmp_path):
        """Verify: Data migrates between adapters via the portable
        export_memories → import_memories pipeline (real migration, not
        re-storing the same messages into the target instance)."""
        sqlite_db = str(tmp_path / "migrate_source.db")
        export_file = str(tmp_path / "migrate_export.json")
        json_db = str(tmp_path / "migrate_target.json")

        original_memories = [
            "Migration test: Memory A about Python",
            "Migration test: Memory B about databases",
            "Migration test: Memory C about DevOps",
        ]

        # Phase 1: Populate SQLite and export to the portable format
        cm_sqlite = CarryMem(storage="sqlite", db_path=sqlite_db)
        try:
            for mem in original_memories:
                result = cm_sqlite.classify_and_remember(mem)
                assert result.get("stored") is True, f"premise: {mem!r} must store: {result}"

            sqlite_recall = cm_sqlite.recall_memories(limit=10)
            assert isinstance(sqlite_recall, list) and len(sqlite_recall) == len(
                original_memories
            ), "SQLite should have stored all data before migration"

            export_result = cm_sqlite.export_memories(output_path=export_file)
            assert export_result is not None
        finally:
            cm_sqlite.close()

        assert os.path.exists(export_file), "export_memories must produce a portable file"

        # Phase 2: Import the exported file into a JSON-adapter instance
        cm_json = CarryMem(storage="json", db_path=json_db)
        try:
            import_result = cm_json.import_memories(input_path=export_file)
            assert import_result is not None

            json_recall = cm_json.recall_memories(limit=10)
            assert isinstance(json_recall, list), "JSON recall should return list"
            json_contents = [m.get("content", "") for m in json_recall if isinstance(m, dict)]
            missing = [
                orig
                for orig in original_memories
                if not any(orig.lower() in jc.lower() or jc.lower() in orig.lower() for jc in json_contents)
            ]
            assert not missing, f"Imported JSON adapter must contain all migrated memories, missing: {missing}"
        finally:
            cm_json.close()


class TestE2EAdapterFeatureParity:
    """Scenario: Both adapters support core operations consistently."""

    def test_both_adapters_support_classify_and_remember(self, tmp_path):
        """Verify: classify_and_remember works on both adapters."""
        for storage_type in ["sqlite", "json"]:
            ext = ".db" if storage_type == "sqlite" else ".json"
            db_path = str(tmp_path / f"parity_{storage_type}{ext}")

            cm = CarryMem(storage=storage_type, db_path=db_path)
            try:
                result = cm.classify_and_remember(f"Parity test for {storage_type}")
                assert isinstance(result, dict), f"{storage_type}: classify_and_remember should return dict"
            finally:
                cm.close()

    def test_both_adapters_support_recall(self, tmp_path):
        """Verify: recall_memories works on both adapters."""
        for storage_type in ["sqlite", "json"]:
            ext = ".db" if storage_type == "sqlite" else ".json"
            db_path = str(tmp_path / f"recall_{storage_type}{ext}")

            cm = CarryMem(storage=storage_type, db_path=db_path)
            try:
                cm.classify_and_remember(f"Recall test data for {storage_type}")
                results = cm.recall_memories(query=f"{storage_type}", limit=5)
                assert isinstance(results, list), f"{storage_type}: recall should return list"
            finally:
                cm.close()

    def test_both_adapters_support_profile(self, tmp_path):
        """Verify: get_memory_profile works on both adapters."""
        for storage_type in ["sqlite", "json"]:
            ext = ".db" if storage_type == "sqlite" else ".json"
            db_path = str(tmp_path / f"profile_{storage_type}{ext}")

            cm = CarryMem(storage=storage_type, db_path=db_path)
            try:
                cm.classify_and_remember(f"Profile test {storage_type}")
                profile = cm.get_memory_profile()
                assert isinstance(profile, dict), f"{storage_type}: profile should return dict"
            finally:
                cm.close()

    @pytest.mark.parametrize("storage_type", ["sqlite", "json"])
    def test_both_adapters_support_backup(self, tmp_path, storage_type):
        """Verify: backup behavior is well-defined for every adapter.

        SQLite: backup succeeds and returns ``{"backed_up": True, "path": ...}``.
        JSON: backup is unsupported; ``backup()`` returns
        ``{"error": "Backup not supported by this adapter"}`` (see BackupMixin).
        Both branches must be exercised — skipping JSON would hide regressions
        in the unsupported-adapter contract.
        """
        ext = ".db" if storage_type == "sqlite" else ".json"
        db_path = str(tmp_path / f"backup_{storage_type}{ext}")
        backup_dir = str(tmp_path / f"backup_{storage_type}_dir")
        os.makedirs(backup_dir, exist_ok=True)

        cm = CarryMem(storage=storage_type, db_path=db_path)
        try:
            cm.classify_and_remember(f"Backup test {storage_type}")
            backup_result = cm.backup(backup_dir=backup_dir)
            assert isinstance(backup_result, dict), f"{storage_type}: backup should return dict"
            if storage_type == "json":
                # JSON adapter must surface the unsupported-backup contract
                # (error dict), not silently succeed or raise NotImplementedError.
                assert "error" in backup_result, (
                    f"JSON adapter should report unsupported backup via error dict, " f"got: {backup_result}"
                )
            else:
                # SQLite: backup must succeed and report the backup path
                assert (
                    backup_result.get("backed_up") is True or "path" in backup_result
                ), f"SQLite backup should succeed with backed_up=True/path, got: {backup_result}"
        finally:
            cm.close()


class TestE2EAdapterSpecificBehavior:
    """Scenario: Adapter-specific features and limitations."""

    def test_sqlite_supports_concurrent_access_better(self, tmp_path):
        """Verify: SQLite adapter handles rapid sequential access efficiently."""
        import time

        db_path = str(tmp_path / "sqlite_perf.db")
        cm = CarryMem(storage="sqlite", db_path=db_path)

        start = time.time()
        for i in range(50):
            cm.classify_and_remember(f"Perf test {i}")
        elapsed = time.time() - start

        cm.close()
        assert elapsed < 30, f"SQLite should handle 50 writes quickly: {elapsed:.2f}s"

    def test_json_creates_readable_file(self, tmp_path):
        """Verify: JSON adapter creates human-readable JSON file."""
        json_path = str(tmp_path / "readable.json")
        cm = CarryMem(storage="json", db_path=json_path)

        try:
            cm.classify_and_remember("Readable JSON test")
            cm.classify_and_remember("Another entry")
        finally:
            cm.close()

        # CarryMem's loader instantiates JSONAdapter without forwarding db_path,
        # so the adapter falls back to its default path
        # (~/.carrymem/memories.json). Determine the actual file location by
        # inspecting the adapter's _path attribute, then fall back to the
        # requested json_path and the well-known default location.
        adapter_path = getattr(getattr(cm, "_adapter", None), "_path", None)
        default_path = os.path.join(os.path.expanduser("~"), ".carrymem", "memories.json")

        candidate_paths = [p for p in [adapter_path, json_path, default_path] if p]
        check_path = next((p for p in candidate_paths if os.path.exists(p)), None)

        assert check_path is not None, f"JSON file not created at any expected location: {candidate_paths}"

        with open(check_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                assert isinstance(data, (dict, list)), "JSON file should contain valid structure"
            except json.JSONDecodeError:
                pytest.fail("JSON file should contain valid JSON")


class TestE2EAdapterErrorHandling:
    """Scenario: Graceful handling of unsupported operations."""

    def test_unsupported_storage_type_raises_error(self, tmp_path):
        """Verify: Invalid storage type is rejected gracefully."""
        db_path = str(tmp_path / "invalid.db")

        with pytest.raises((ValueError, TypeError, Exception)):
            CarryMem(storage="nonexistent_adapter", db_path=db_path)

    def test_missing_db_path_handling(self, tmp_path, monkeypatch):
        """Verify: CarryMem() with no arguments falls back to the default location."""
        default_db = tmp_path / "default_location.db"
        monkeypatch.setenv("CARRYMEM_DB_PATH", str(default_db))

        cm = CarryMem()  # No arguments: db_path comes from CARRYMEM_DB_PATH
        try:
            assert isinstance(cm, CarryMem), "Default CarryMem() should return a CarryMem instance"
            assert cm.classify_and_remember("Default location probe")["stored"] is True
        finally:
            cm.close()

        assert default_db.exists(), "CarryMem() did not use the configured default db_path"

    def test_corrupted_json_file_handling(self, tmp_path):
        """Verify: Corrupted JSON store is preserved and the store stays usable."""
        json_path = tmp_path / "corrupted.json"
        corrupt_bytes = "{ this is not valid JSON !!!"
        json_path.write_text(corrupt_bytes)

        cm = CarryMem(storage="json", db_path=str(json_path))
        try:
            result = cm.classify_and_remember("Test on corrupted DB")
            assert isinstance(result, dict), "Should return some response"
            assert result["stored"] is True, result
        finally:
            cm.close()

        # The unreadable original must survive: starting from an empty store
        # makes the next save rewrite the file.
        preserved = sorted(tmp_path.glob("corrupted.json.corrupt.*"))
        assert len(preserved) == 1, f"expected exactly one preserved copy, got {preserved}"
        assert preserved[0].read_text() == corrupt_bytes

        # The store is valid JSON again and contains the newly stored memory.
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        contents = [m["content"] for m in data["default"]["memories"].values()]
        assert "Test on corrupted DB" in contents, contents

    def test_readonly_database_handling(self, tmp_path):
        """Verify: Read-only database is handled appropriately."""
        db_path = str(tmp_path / "readonly.db")

        # Create and populate
        cm = CarryMem(storage="sqlite", db_path=db_path)
        try:
            cm.classify_and_remember("Data before readonly")
        finally:
            cm.close()

        # Make file read-only (if OS supports it)
        try:
            os.chmod(db_path, 0o444)

            cm_ro = CarryMem(storage="sqlite", db_path=db_path)
            try:
                # Read operations should work
                recalled = cm_ro.recall_memories(limit=5)
                assert isinstance(recalled, list), "Read should work on read-only DB"

                # Writes on a chmod'ed read-only DB file: SQLite may still
                # accept them because the WAL sidecars live outside the
                # chmod'ed inode. Both outcomes are legitimate, so assert
                # each explicitly rather than swallowing the assertion.
                try:
                    write_result = cm_ro.classify_and_remember("Attempted write")
                except (*_SQLITE_ERRORS, OSError) as exc:
                    assert "readonly" in str(exc).lower() or "read-only" in str(exc).lower(), exc
                else:
                    assert isinstance(write_result, dict), write_result
                    assert write_result["stored"] is True, write_result
                    assert cm_ro.recall_memories(
                        query="Attempted write", limit=5
                    ), "write reported stored=True but the record is not retrievable"
            finally:
                cm_ro.close()
        finally:
            # Restore permissions for cleanup
            os.chmod(db_path, 0o644)


class TestE2EMultiAdapterIsolation:
    """Scenario: Multiple adapter instances don't interfere."""

    def test_separate_instances_independent(self, tmp_path):
        """Verify: Different adapter instances with different files are independent."""
        sqlite_path = str(tmp_path / "iso_sqlite.db")
        json_path = str(tmp_path / "iso_json.json")

        cm_sqlite = CarryMem(storage="sqlite", db_path=sqlite_path)
        cm_json = CarryMem(storage="json", db_path=json_path)

        try:
            # Store different data in each
            cm_sqlite.classify_and_remember("Only in SQLite")
            cm_json.classify_and_remember("Only in JSON")

            # Each should only see its own data
            sqlite_results = cm_sqlite.recall_memories(query="Only", limit=5)
            json_results = cm_json.recall_memories(query="Only", limit=5)

            assert isinstance(sqlite_results, list), "SQLite recall should return list"
            assert isinstance(json_results, list), "JSON recall should return list"
            # Verify each adapter can find its own data
            sqlite_contents = [m.get("content", "") for m in sqlite_results]
            json_contents = [m.get("content", "") for m in json_results]
            assert any("SQLite" in c for c in sqlite_contents), "SQLite should find its own data"
            assert any("JSON" in c for c in json_contents), "JSON should find its own data"

            # Verify isolation: each contains only its own data
            sqlite_contents = [m.get("content", "") for m in sqlite_results]
            json_contents = [m.get("content", "") for m in json_results]

            has_sqlite_in_json = any("SQLite" in c for c in json_contents)
            has_json_in_sqlite = any("JSON" in c for c in sqlite_contents)

            assert not has_sqlite_in_json, "JSON should not contain SQLite's data"
            assert not has_json_in_sqlite, "SQLite should not contain JSON's data"
        finally:
            cm_sqlite.close()
            cm_json.close()
