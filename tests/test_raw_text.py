import os
import sqlite3
import tempfile
import unittest

from carrymem import CarryMem
from carrymem.adapters.base import MemoryEntry, StoredMemory
from carrymem.adapters.sqlite_adapter import SQLiteAdapter


class TestRawTextStorage(unittest.TestCase):

    def setUp(self):
        self.db_path = os.path.join(tempfile.mkdtemp(), "test_raw_text.db")
        self.adapter = SQLiteAdapter(db_path=self.db_path)

    def tearDown(self):
        self.adapter.close()

    def test_raw_text_stored_on_remember(self):
        entry = MemoryEntry(
            id="rt-001",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="We decided to use PostgreSQL because of its great JSON support",
            confidence=0.9,
        )
        stored = self.adapter.remember(entry)
        self.assertEqual(stored.raw_text, "We decided to use PostgreSQL because of its great JSON support")
        self.assertEqual(stored.content, "Database preference: PostgreSQL")

    def test_raw_text_empty_default(self):
        entry = MemoryEntry(
            id="rt-002",
            type="fact_declaration",
            content="Python 3.9 is the minimum version",
            confidence=0.85,
        )
        stored = self.adapter.remember(entry)
        self.assertEqual(stored.raw_text, "")
        self.assertEqual(stored.content, "Python 3.9 is the minimum version")

    def test_recall_by_raw_text_keyword(self):
        entry = MemoryEntry(
            id="rt-003",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="We decided to use PostgreSQL because of its great JSON support",
            confidence=0.9,
        )
        self.adapter.remember(entry)

        results = self.adapter.recall("PostgreSQL")
        self.assertGreaterEqual(len(results), 1)
        found = any("PostgreSQL" in r.raw_text for r in results)
        self.assertTrue(found, "Should find memory via raw_text keyword")

    def test_recall_by_content_structured_keyword(self):
        entry = MemoryEntry(
            id="rt-004",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="We decided to use PostgreSQL because of its great JSON support",
            confidence=0.9,
        )
        self.adapter.remember(entry)

        results = self.adapter.recall("database preference")
        self.assertGreaterEqual(len(results), 1)
        found = any("database preference" in r.content.lower() for r in results)
        self.assertTrue(found, "Should find memory via content structured keyword")

    def test_recall_by_raw_text_phrase_not_in_content(self):
        entry = MemoryEntry(
            id="rt-005",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="We decided to use PostgreSQL because of its great JSON support",
            confidence=0.9,
        )
        self.adapter.remember(entry)

        results = self.adapter.recall("JSON support")
        self.assertGreaterEqual(len(results), 1, "Should find memory via raw_text phrase not in content")

    def test_dedup_updates_raw_text(self):
        entry1 = MemoryEntry(
            id="rt-006",
            type="user_preference",
            content="Database preference: PostgreSQL",
            confidence=0.9,
        )
        self.adapter.remember(entry1)

        entry2 = MemoryEntry(
            id="rt-006",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="We decided to use PostgreSQL",
            confidence=0.9,
        )
        stored = self.adapter.remember(entry2)
        self.assertEqual(stored.raw_text, "We decided to use PostgreSQL")

    def test_dedup_keeps_existing_raw_text(self):
        entry1 = MemoryEntry(
            id="rt-007",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="We decided to use PostgreSQL",
            confidence=0.9,
        )
        self.adapter.remember(entry1)

        entry2 = MemoryEntry(
            id="rt-007",
            type="user_preference",
            content="Database preference: PostgreSQL",
            raw_text="",
            confidence=0.9,
        )
        stored = self.adapter.remember(entry2)
        self.assertEqual(stored.raw_text, "We decided to use PostgreSQL")

    def test_raw_text_in_to_dict(self):
        entry = MemoryEntry(
            id="rt-008",
            type="user_preference",
            content="Prefers dark mode",
            raw_text="I like dark mode better",
            confidence=0.9,
        )
        d = entry.to_dict()
        self.assertEqual(d["raw_text"], "I like dark mode better")

    def test_raw_text_in_from_dict(self):
        d = {
            "id": "rt-009",
            "type": "user_preference",
            "content": "Prefers dark mode",
            "raw_text": "I like dark mode better",
            "confidence": 0.9,
        }
        entry = MemoryEntry.from_dict(d)
        self.assertEqual(entry.raw_text, "I like dark mode better")


class TestRawTextMigration(unittest.TestCase):

    def test_migration_adds_raw_text_column(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test_migration.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            original_message TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            tier INTEGER NOT NULL DEFAULT 2,
            source_layer TEXT NOT NULL DEFAULT 'unknown',
            reasoning TEXT,
            suggested_action TEXT NOT NULL DEFAULT 'store',
            recall_hint TEXT,
            metadata TEXT,
            storage_key TEXT UNIQUE NOT NULL,
            namespace TEXT NOT NULL DEFAULT 'default',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT,
            access_count INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL,
            importance_score REAL NOT NULL DEFAULT 0.0,
            last_accessed_at TEXT,
            version INTEGER NOT NULL DEFAULT 1
        )""")
        conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content,
            original_message,
            content='memories',
            content_rowid='rowid',
            tokenize='trigram'
        )""")
        conn.execute("""INSERT INTO memories
            (id, type, content, storage_key, namespace, content_hash, confidence)
            VALUES ('old-1', 'fact', 'Old memory content', 'sk_old1', 'default', 'abc123', 0.8)""")
        conn.commit()
        conn.close()

        adapter = SQLiteAdapter(db_path=db_path)

        conn2 = sqlite3.connect(db_path)
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT raw_text FROM memories WHERE id = 'old-1'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["raw_text"], "")
        conn2.close()

        adapter.close()

    def test_migration_idempotent(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test_migration_idem.db")
        adapter1 = SQLiteAdapter(db_path=db_path)
        adapter1.close()

        adapter2 = SQLiteAdapter(db_path=db_path)
        adapter2.close()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT raw_text FROM memories LIMIT 0")
        conn.close()


class TestRawTextIntegration(unittest.TestCase):

    def setUp(self):
        self.db_path = os.path.join(tempfile.mkdtemp(), "test_raw_text_integration.db")
        self.cm = CarryMem(db_path=self.db_path)

    def tearDown(self):
        self.cm.close()

    def test_classify_and_remember_saves_raw_text(self):
        result = self.cm.classify_and_remember("I prefer using PostgreSQL for database tasks")
        self.assertTrue(result.get("stored", False))

        memories = self.cm.recall_memories("PostgreSQL", limit=5)
        self.assertGreaterEqual(len(memories), 1)
        has_raw = any(m.get("raw_text", "") != "" for m in memories)
        self.assertTrue(has_raw, "At least one memory should have raw_text populated")

    def test_raw_text_preserves_original_phrasing(self):
        result = self.cm.classify_and_remember("We decided to use PostgreSQL because of its great JSON support")
        self.assertTrue(result.get("stored", False))

        memories = self.cm.recall_memories("JSON support", limit=5)
        self.assertGreaterEqual(len(memories), 1, "Should find memory via raw_text phrase")


if __name__ == "__main__":
    unittest.main()
