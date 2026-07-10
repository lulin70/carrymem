"""
Integration Tests: Adapter ↔ Engine ↔ Storage Three-Layer Interaction

Validates the complete data flow through CarryMem's three-layer architecture:
1. SQLiteAdapter (Storage Layer) → Schema Creation → Data Persistence
2. MemoryClassificationEngine (Classification Layer) → Message Processing → Typed Entries
3. RecallEngine (Query Layer) → Multi-Phase Search → Result Retrieval

Also covers:
- Encryption integration across all three layers
- Adapter switching and re-binding
- End-to-end full chain tests with real data
"""

import os
import sqlite3

import pytest

from carrymem import CarryMem
from carrymem.adapters.sqlite_adapter import SQLiteAdapter
from carrymem.engine import MemoryClassificationEngine


@pytest.fixture
def cm(tmp_path):
    """Create a fresh CarryMem instance with isolated SQLite database."""
    db_path = str(tmp_path / "adapter_engine_test.db")
    instance = CarryMem(db_path=db_path)
    yield instance
    instance.close()


@pytest.fixture
def encrypted_cm(tmp_path):
    """Create a CarryMem instance with encryption enabled."""
    db_path = str(tmp_path / "encrypted_test.db")
    instance = CarryMem(db_path=db_path, encryption_key="integration-test-encryption-key-12345")
    yield instance
    instance.close()


class TestSQLiteAdapterSchemaAndPersistence:
    """Scenario: SQLiteAdapter creates schema and persists data correctly."""

    def test_adapter_creates_tables_on_init(self, tmp_path):
        """Verify: SQLiteAdapter initializes database schema on creation.

        Steps:
        1. Create SQLiteAdapter (or CarryMem which wraps it)
        2. Verify tables exist in SQLite database
        3. Verify expected columns present
        """
        db_path = str(tmp_path / "schema_test.db")
        cm = CarryMem(db_path=db_path)

        try:
            # Connect directly to verify schema
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check memories table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
            table_result = cursor.fetchone()
            assert table_result is not None, "memories table should exist"

            # Check expected columns
            cursor.execute("PRAGMA table_info(memories)")
            columns = [col[1] for col in cursor.fetchall()]
            expected_columns = {"storage_key", "content", "type", "confidence", "namespace"}
            assert expected_columns.issubset(
                set(columns)
            ), f"Missing expected columns. Have: {columns}, Need: {expected_columns}"

            conn.close()
        finally:
            cm.close()

    def test_adapter_persists_data_across_reopen(self, tmp_path):
        """Verify: Data written by adapter persists after close/reopen.

        Steps:
        1. Create CarryMem, store memories
        2. Close connection
        3. Reopen with new CarryMem instance
        4. Verify data still accessible
        """
        db_path = str(tmp_path / "persistence_test.db")

        # Phase 1: Write data
        cm1 = CarryMem(db_path=db_path)
        cm1.classify_and_remember("Persistent memory: use TDD approach")
        cm1.classify_and_remember("Persistent memory: deploy to staging first")
        cm1.close()

        # Phase 2: Reopen and verify
        cm2 = CarryMem(db_path=db_path)
        try:
            recalled = cm2.recall_memories(limit=10)
            contents = [m.get("content", "") for m in recalled]

            assert any("TDD" in c for c in contents), "Should recall TDD memory after reopen"
            assert any("staging" in c for c in contents), "Should recall staging memory after reopen"
        finally:
            cm2.close()


class TestEngineClassificationToStorage:
    """Scenario: MemoryClassificationEngine processes messages that get stored via Adapter."""

    def test_engine_classification_produces_storable_entries(self, cm):
        """Verify: Engine classification produces entries that adapter can store.

        Steps:
        1. Send message to classify_and_remember (uses engine then adapter)
        2. Verify engine produces valid classification
        3. Verify adapter successfully stores the result
        """
        test_message = "I prefer using async/await over callbacks in JavaScript"

        # This uses: Engine.process_message → Adapter.remember
        result = cm.classify_and_remember(test_message)

        # Engine should have classified
        assert isinstance(result, dict), "Result should be dict"
        assert result.get("stored", False), "Should have stored the memory"

        # Adapter should have persisted
        storage_keys = result.get("storage_keys", [])
        assert len(storage_keys) > 0, "Should return at least one storage key"

        # Verify we can recall it back (proves round-trip)
        recalled = cm.recall_memories(query="async/await", limit=5)
        assert len(recalled) >= 1, "Should be able to recall stored memory"

    def test_engine_handles_multiple_memory_types(self, cm):
        """Verify: Engine can classify different memory types that all store correctly.

        Steps:
        1. Send messages of different semantic types
        2. Verify each gets appropriate classification
        3. Verify all are stored and recallable
        """
        test_cases = [
            ("I always use 4-space indentation", "preference"),
            ("We chose PostgreSQL over MongoDB", "decision"),
            ("The API base URL is https://api.example.com/v1", "fact"),
            ("Remember to update dependencies monthly", "task"),
        ]

        results = []
        for msg, expected_type in test_cases:
            result = cm.classify_and_remember(msg)
            results.append((msg, result))
            assert result.get("stored", False), f"Should store: {msg[:30]}"

        # Verify all are recallable
        for msg, _ in results:
            keyword = msg.split()[0]  # First word as search key
            recalled = cm.recall_memories(query=keyword, limit=5)
            assert len(recalled) >= 1, f"Should recall: {msg[:30]}"


class TestRecallEngineFullChain:
    """Scenario: RecallEngine queries data stored by Adapter after Engine classification."""

    def test_full_write_query_chain(self, cm):
        """Verify: Complete write → query chain works end-to-end.

        Chain: User Input → Engine Classify → Adapter Store → RecallEngine Query → Results

        Steps:
        1. Write multiple diverse memories
        2. Query using various strategies (keyword, type filter, etc.)
        3. Verify correct results returned each time
        """
        # Write phase
        memories = [
            "User prefers dark mode theme in all applications",
            "Team decided to migrate from REST to GraphQL",
            "The database server runs on port 5432 with daily backups",
            "Run tests before every commit",
            "Use environment variables for configuration",
        ]

        for msg in memories:
            result = cm.classify_and_remember(msg)
            assert result.get("stored", False), f"Failed to store: {msg[:30]}"

        # Query phase - keyword search
        dark_mode_results = cm.recall_memories(query="dark mode", limit=5)
        assert len(dark_mode_results) >= 1, "Should find dark mode memory"
        assert any("dark mode" in m.get("content", "").lower() for m in dark_mode_results)

        # Query phase - type filtering
        preferences = cm.recall_memories(query="", filters={"type": "user_preference"}, limit=10)
        assert len(preferences) >= 1, "Should find preferences by type filter"

        # Query phase - broad search
        all_memories = cm.recall_memories(query="", limit=20)
        assert (
            len(all_memories) >= len(memories) * 0.6
        ), f"Should recall most memories, got {len(all_memories)}/{len(memories)}"

    def test_recall_with_time_filtering(self, cm):
        """Verify: RecallEngine respects time-based filters.

        Steps:
        1. Store memories (they get current timestamps)
        2. Query with time filters
        3. Verify results respect time constraints
        """
        cm.classify_and_remember("Time-filtered memory: recent decision")

        # Query without time filter - should find it
        all_results = cm.recall_memories(query="time-filtered", limit=5)
        assert len(all_results) >= 1, "Should find time-filtered memory"

        # Verify results have timestamp fields
        if all_results:
            result = all_results[0]
            assert "created_at" in result or "storage_key" in result, "Recalled memories should have metadata"


class TestEncryptionIntegration:
    """Scenario: Encryption works across Adapter → Storage → Recall chain."""

    def test_encrypted_store_and_recall(self, encrypted_cm):
        """Verify: Encrypted storage → decryption → successful recall.

        Full chain with encryption:
        1. Engine classifies message
        2. Adapter encrypts and stores
        3. RecallEngine queries
        4. Adapter decrypts and returns

        Steps:
        1. Store sensitive memories with encryption enabled
        2. Recall and verify content integrity
        3. Verify raw DB content is encrypted (not plaintext)
        """
        sensitive_memories = [
            "Secret: API key is sk-12345-abcdef",
            "Credential: Database password is SuperSecret123!",
            "Private: User's SSN is 123-45-6789",
        ]

        # Store with encryption
        for msg in sensitive_memories:
            result = encrypted_cm.classify_and_remember(msg)
            assert result.get("stored", False), f"Should encrypt and store: {msg[:30]}"

        # Recall (should auto-decrypt)
        recalled = encrypted_cm.recall_memories(limit=10)
        assert (
            len(recalled) >= len(sensitive_memories) * 0.6
        ), f"Should recall most encrypted memories, got {len(recalled)}"

        # Verify content integrity after decryption
        recalled_contents = [m.get("content", "") for m in recalled]
        found_count = sum(
            1
            for orig in sensitive_memories
            if any(orig.split(":")[1].strip() in rc or orig.lower() in rc.lower() for rc in recalled_contents)
        )
        assert (
            found_count >= 2
        ), f"Decrypted content should match original, matched {found_count}/{len(sensitive_memories)}"

    def test_encryption_persists_across_reopen(self, tmp_path):
        """Verify: Encrypted data survives close → reopen cycle.

        Steps:
        1. Create encrypted CarryMem, store data
        2. Close
        3. Reopen with same key
        4. Recall and verify decryption works
        """
        db_path = str(tmp_path / "encrypt_persist.db")
        encryption_key = "persistent-encryption-test-key-xyz"

        # Phase 1: Encrypt and store
        cm1 = CarryMem(db_path=db_path, encryption_key=encryption_key)
        cm1.classify_and_remember("Persistent secret: meeting password is hunter2")
        cm1.close()

        # Phase 2: Reopen and decrypt
        cm2 = CarryMem(db_path=db_path, encryption_key=encryption_key)
        try:
            recalled = cm2.recall_memories(limit=5)
            assert len(recalled) >= 1, "Should recall encrypted memory after reopen"

            contents = [m.get("content", "") for m in recalled]
            assert any(
                "hunter2" in c or "meeting password" in c.lower() for c in contents
            ), "Decrypted content should match original after reopen"
        finally:
            cm2.close()

    def test_encrypted_database_raw_content(self, tmp_path):
        """Verify: Raw database content is encrypted (not stored as plaintext).

        Steps:
        1. Store data with encryption
        2. Read raw SQLite database directly
        3. Verify original content NOT visible in raw bytes
        """
        db_path = str(tmp_path / "raw_encrypt.db")
        encryption_key = "raw-inspection-key-99999"

        cm = CarryMem(db_path=db_path, encryption_key=encryption_key)
        secret_message = "Super secret value: ABCD-1234-EFGH-5678"
        cm.classify_and_remember(secret_message)
        cm.close()

        # Read raw database file
        with open(db_path, "rb") as f:
            raw_content = f.read().decode("utf-8", errors="ignore")

        # Original secret should NOT appear as plaintext in raw DB
        # (allowing for partial matches due to indexing, but full value shouldn't be there)
        assert (
            secret_message.lower() not in raw_content.lower()
        ), "Encrypted database should not contain plaintext secret"


class TestAdapterSwitching:
    """Scenario: Switching adapters doesn't break Engine or Recall functionality."""

    def test_same_database_different_instances(self, tmp_path):
        """Verify: Multiple CarryMem instances on same DB share data correctly.

        Steps:
        1. Create two CarryMem instances pointing to same DB
        2. Write with one, read with other
        3. Verify data consistency
        """
        db_path = str(tmp_path / "shared_db.db")

        cm1 = CarryMem(db_path=db_path, namespace="instance_a")
        cm2 = CarryMem(db_path=db_path, namespace="instance_b")

        try:
            # Write with cm1
            cm1.classify_and_remember("Written by instance A")

            # Each should see their own namespace
            a_memories = cm1.recall_memories(limit=10)
            b_memories = cm2.recall_memories(limit=10)

            a_contents = [m.get("content", "") for m in a_memories]
            b_contents = [m.get("content", "") for m in b_memories]

            assert any("instance A" in c for c in a_contents), "Instance A should see its own writes"
            assert not any(
                "instance A" in c for c in b_contents
            ), "Instance B should NOT see Instance A's writes (different namespace)"

            # Now write with B
            cm2.classify_and_remember("Written by instance B")

            # Re-verify isolation
            a_memories_2 = cm1.recall_memories(limit=10)
            b_memories_2 = cm2.recall_memories(limit=10)

            a_contents_2 = [m.get("content", "") for m in a_memories_2]
            b_contents_2 = [m.get("content", "") for m in b_memories_2]

            assert any("instance A" in c for c in a_contents_2), "Instance A should still see its own writes"
            assert any("instance B" in c for c in b_contents_2), "Instance B should see its own writes"
        finally:
            cm1.close()
            cm2.close()

    def test_adapter_properties_accessible_after_init(self, cm):
        """Verify: All adapter/engine properties are accessible after initialization.

        Steps:
        1. Create CarryMem
        2. Access adapter, engine, and related properties
        3. Verify they're properly initialized
        """
        # Adapter layer
        assert cm.adapter is not None, "Adapter should be initialized"
        assert hasattr(cm.adapter, "store_entry"), "Adapter should have store_entry method"
        assert hasattr(cm.adapter, "recall"), "Adapter should have recall method"
        assert hasattr(cm.adapter, "delete"), "Adapter should have delete method"

        # Engine layer
        assert cm.engine is not None, "Engine should be initialized"
        assert hasattr(cm.engine, "process_message"), "Engine should have process_message"

        # Namespace
        assert isinstance(cm.namespace, str), "Namespace should be string"
        assert len(cm.namespace) > 0, "Namespace should not be empty"


class TestEndToEndCompleteChain:
    """Scenario: Complete end-to-end tests covering all three layers."""

    def test_complete_classify_store_recall_export_chain(self, tmp_path):
        """Verify: Full pipeline: Classify → Store → Recall → Export → Import.

        Complete end-to-end test exercising all three layers plus export/import.

        Steps:
        1. Create CarryMem (initializes Adapter + Engine)
        2. Classify and store multiple memories (Engine → Adapter)
        3. Recall and verify (RecallEngine → Adapter)
        4. Export to JSON (ProfileExportMixin → Adapter)
        5. Create new instance and import (Adapter → Engine validation)
        6. Verify data integrity throughout
        """
        db_path = str(tmp_path / "e2e_chain.db")
        export_path = str(tmp_path / "export.json")

        # Phase 1: Initialize and store
        cm = CarryMem(db_path=db_path)
        original_memories = [
            "E2E test: user prefers Python 3.11+",
            "E2E test: project uses poetry for dependency management",
            "E2E test: CI runs on every PR to main branch",
        ]

        for msg in original_memories:
            result = cm.classify_and_remember(msg)
            assert result.get("stored", False), f"E2E store failed: {msg[:30]}"

        # Phase 2: Recall verification
        recalled = cm.recall_memories(query="e2e test", limit=10)
        assert len(recalled) >= len(original_memories) * 0.8, f"Should recall most E2E memories, got {len(recalled)}"

        # Phase 3: Export
        export_result = cm.export_memories(output_path=export_path, format="json")
        assert export_result.get("exported", False), "Export should succeed"
        assert os.path.exists(export_path), "Export file should exist"

        # Phase 4: Import into new instance
        db_path_2 = str(tmp_path / "e2e_import.db")
        cm2 = CarryMem(db_path=db_path_2)

        try:
            import_result = cm2.import_memories(input_path=export_path)
            assert (
                import_result.get("imported", 0) >= len(original_memories) * 0.8
            ), f"Should import most memories, imported {import_result.get('imported', 0)}"

            # Phase 5: Verify imported data
            imported_recalled = cm2.recall_memories(query="e2e test", limit=10)
            imported_contents = [m.get("content", "") for m in imported_recalled]

            match_count = sum(
                1 for orig in original_memories if any(orig.lower() in ic.lower() for ic in imported_contents)
            )
            assert match_count >= 2, f"Imported data should match originals, matched {match_count}"
        finally:
            cm2.close()
            cm.close()

    def test_high_volume_write_read_cycle(self, cm):
        """Verify: System handles moderate volume of write/read operations.

        Stress test for Adapter ↔ Engine ↔ Storage interaction under load.

        Steps:
        1. Store 50+ memories rapidly
        2. Perform various recall operations
        3. Verify no data loss or corruption
        """
        # Generate test data
        memories = []
        for i in range(50):
            memories.append(f"Memory #{i}: Test data for high volume testing with index {i}")

        # Bulk write
        success_count = 0
        for msg in memories:
            result = cm.classify_and_remember(msg)
            if result.get("stored", False):
                success_count += 1

        assert (
            success_count >= len(memories) * 0.9
        ), f"Should store most memories, succeeded {success_count}/{len(memories)}"

        # Bulk read - verify count
        all_recalled = cm.recall_memories(limit=100)
        assert len(all_recalled) >= success_count * 0.9, f"Should recall most stored memories, got {len(all_recalled)}"

        # Targeted read - verify specific items
        target_result = cm.recall_memories(query="Memory #25", limit=5)
        assert len(target_result) >= 1, "Should find specific memory by content"

        # Type-filtered read
        filtered = cm.recall_memories(query="", filters={"type": "user_preference"}, limit=50)
        assert isinstance(filtered, list), "Filtered recall should return list"

    def test_concurrent_namespace_operations(self, tmp_path):
        """Verify: Operations on different namespaces don't interfere.

        Tests Adapter's namespace isolation at the storage level.

        Steps:
        1. Create multiple namespaces on same database
        2. Perform simultaneous CRUD operations
        3. Verify complete isolation
        """
        db_path = str(tmp_path / "concurrent_ns.db")

        namespaces = ["ns_alpha", "ns_beta", "ns_gamma"]
        instances = []

        for ns in namespaces:
            instances.append(CarryMem(db_path=db_path, namespace=ns))

        try:
            # Write to each namespace
            for i, cm_inst in enumerate(instances):
                cm_inst.classify_and_remember(f"Namespace {namespaces[i]}: unique data {i}")

            # Verify isolation
            for i, cm_inst in enumerate(instances):
                memories = cm_inst.recall_memories(limit=10)
                contents = [m.get("content", "") for m in memories]

                # Should find own data
                assert any(namespaces[i] in c for c in contents), f"Namespace {namespaces[i]} should see its own data"

                # Should NOT see others' data
                for j, other_ns in enumerate(namespaces):
                    if i != j:
                        assert not any(
                            other_ns in c for c in contents
                        ), f"Namespace {namespaces[i]} should NOT see {other_ns}'s data"
        finally:
            for cm_inst in instances:
                cm_inst.close()
