"""
Test Suite for RuleStorage (SQLite CRUD)

Validates:
- Create, Read, Update, Delete operations
- FTS5 full-text search
- Schema initialization and migration
- Thread safety
"""

import pytest
import tempfile
import os

from memory_classification_engine.rules.storage import RuleStorage


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def storage(temp_db):
    """Create RuleStorage instance with temp database"""
    return RuleStorage(temp_db)


class TestRuleStorageSchema:
    """Test database schema creation and initialization"""

    def test_schema_created_on_init(self, storage):
        """Should create rules table on initialization"""
        conn = storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='rules'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "rules"
        finally:
            conn.close()

    def test_fts_index_created(self, storage):
        """Should create FTS5 virtual table for search"""
        conn = storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='rules_fts'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "rules_fts"
        finally:
            conn.close()

    def test_indexes_created(self, storage):
        """Should create performance indexes"""
        conn = storage._get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_rules_%'"
            )
            indexes = cursor.fetchall()
            index_names = [idx[0] for idx in indexes]
            assert "idx_rules_status" in index_names
            assert "idx_rules_trigger" in index_names
            assert "idx_rules_type" in index_names
        finally:
            conn.close()


class TestRuleStorageCreate:
    """Test rule creation operations"""

    def test_create_basic_rule(self, storage):
        """Should create rule with basic fields"""
        rule = storage.create(
            trigger="写报告",
            action="控制在3页以内",
            rule_type="format",
        )

        assert rule.id.startswith("rule_")
        assert rule.trigger == "写报告"
        assert rule.action == "控制在3页以内"
        assert rule.rule_type == "format"
        assert rule.status == "active"

    def test_create_with_all_options(self, storage):
        """Should create rule with all options specified"""
        rule = storage.create(
            trigger="做竞品分析",
            action="跳过印度供应商",
            rule_type="avoid",
            override=True,
            derived_from="manual",
            source_memories=["mem_1", "mem_2"],
            confidence=0.95,
        )

        assert rule.trigger == "做竞品分析"
        assert rule.action == "跳过印度供应商"
        assert rule.override is True
        assert rule.source_memories == ["mem_1", "mem_2"]
        assert rule.confidence == 0.95

    def test_create_persists_to_database(self, storage):
        """Should persist rule to database and be retrievable"""
        created = storage.create(trigger="test", action="action")
        retrieved = storage.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.trigger == created.trigger
        assert retrieved.action == created.action

    def test_create_validates_trigger(self, storage):
        """Should validate trigger through sanitizer"""
        with pytest.raises(ValueError, match="cannot be empty"):
            storage.create(trigger="", action="action")

    def test_create_validates_action(self, storage):
        """Should validate action through sanitizer"""
        with pytest.raises(ValueError, match="cannot be empty"):
            storage.create(trigger="trigger", action="")


class TestRuleStorageRead:
    """Test read/retrieve operations"""

    def test_get_existing_rule(self, storage):
        """Should retrieve existing rule by ID"""
        created = storage.create(trigger="test", action="test")
        retrieved = storage.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_rule(self, storage):
        """Should return None for nonexistent rule"""
        result = storage.get("rule_nonexistent")
        assert result is None

    def test_list_all_rules(self, storage):
        """Should list all rules in database"""
        # Create multiple rules
        for i in range(5):
            storage.create(trigger=f"trigger_{i}", action=f"action_{i}")

        rules = storage.list_all()
        assert len(rules) >= 5

    def test_list_filter_by_status(self, storage):
        """Should filter rules by status"""
        storage.create(trigger="active1", action="a1", status="active")
        storage.create(trigger="paused1", action="a1", status="paused")

        active_rules = storage.list_all(status="active")
        paused_rules = storage.list_all(status="paused")

        assert all(r.status == "active" for r in active_rules)
        assert all(r.status == "paused" for r in paused_rules)

    def test_list_filter_by_type(self, storage):
        """Should filter rules by type"""
        storage.create(trigger="t1", action="a1", rule_type="avoid")
        storage.create(trigger="t2", action="a2", rule_type="format")

        avoid_rules = storage.list_all(rule_type="avoid")
        format_rules = storage.list_all(rule_type="format")

        assert all(r.rule_type == "avoid" for r in avoid_rules)
        assert all(r.rule_type == "format" for r in format_rules)

    def test_list_pagination(self, storage):
        """Should support pagination with limit/offset"""
        for i in range(10):
            storage.create(trigger=f"t{i}", action=f"a{i}")

        page1 = storage.list_all(limit=5, offset=0)
        page2 = storage.list_all(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5
        # Ensure no overlap
        page1_ids = {r.id for r in page1}
        page2_ids = {r.id for r in page2}
        assert len(page1_ids & page2_ids) == 0


class TestRuleStorageSearch:
    """Test FTS5 full-text search functionality"""

    def test_search_by_trigger_text(self, storage):
        """Should find rules matching trigger text"""
        storage.create(trigger="写报告", action="控制在3页以内")
        storage.create(trigger="做分析", action="详细说明")

        results = storage.search("报告")
        assert len(results) >= 1
        assert any("报告" in r.trigger for r in results)

    def test_search_by_action_text(self, storage):
        """Should find rules matching action text"""
        storage.create(trigger="场景1", action="跳过印度供应商")
        storage.create(trigger="场景2", action="使用PostgreSQL")

        results = storage.search("印度")
        assert len(results) >= 1
        assert any("印度" in r.action for r in results)

    def test_search_no_results(self, storage):
        """Should return empty list for non-matching queries"""
        storage.create(trigger="写报告", action="控制页数")

        results = storage.search("完全不相关的查询词")
        assert len(results) == 0

    def test_search_respects_limit(self, storage):
        """Should respect result limit parameter"""
        for i in range(10):
            storage.create(trigger=f"测试{i}", action=f"动作{i}")

        results = storage.search("测试", limit=3)
        assert len(results) <= 3


class TestRuleStorageUpdate:
    """Test update operations"""

    def test_update_trigger(self, storage):
        """Should update trigger field"""
        created = storage.create(trigger="old_trigger", action="action")
        updated = storage.update(created.id, trigger="new_trigger")

        assert updated is not None
        assert updated.trigger == "new_trigger"

    def test_update_action(self, storage):
        """Should update action field"""
        created = storage.create(trigger="trigger", action="old_action")
        updated = storage.update(created.id, action="new_action")

        assert updated is not None
        assert updated.action == "new_action"

    def test_update_status(self, storage):
        """Should update status field"""
        created = storage.create(trigger="trigger", action="action")
        updated = storage.update(created.id, status="paused")

        assert updated is not None
        assert updated.status == "paused"

    def test_update_nonexistent_rule(self, storage):
        """Should return None when updating nonexistent rule"""
        result = storage.update("rule_nonexistent", trigger="new")
        assert result is None

    def test_update_returns_unchanged_on_empty_updates(self, storage):
        """Should return existing rule when no valid fields to update"""
        created = storage.create(trigger="trigger", action="action")
        result = storage.update(created.id)
        assert result is not None
        assert result.trigger == "trigger"


class TestRuleStorageDelete:
    """Test delete operations"""

    def test_delete_existing_rule(self, storage):
        """Should delete existing rule and return True"""
        created = storage.create(trigger="trigger", action="action")
        result = storage.delete(created.id)

        assert result is True
        assert storage.get(created.id) is None

    def test_delete_nonexistent_rule(self, storage):
        """Should return False when deleting nonexistent rule"""
        result = storage.delete("rule_nonexistent")
        assert result is False

    def test_delete_removes_from_search(self, storage):
        """Deleted rules should not appear in search results"""
        created = storage.create(trigger="unique_keyword", action="action")
        storage.delete(created.id)

        results = storage.search("unique_keyword")
        assert len(results) == 0


class TestRuleStorageCount:
    """Test count operations"""

    def test_count_total(self, storage):
        """Should count total rules"""
        assert storage.count() == 0

        storage.create(trigger="t1", action="a1")
        storage.create(trigger="t2", action="a2")
        assert storage.count() == 2

    def test_count_by_status(self, storage):
        """Should count rules filtered by status"""
        storage.create(trigger="t1", action="a1", status="active")
        storage.create(trigger="t2", action="a2", status="active")
        storage.create(trigger="t3", action="a3", status="paused")

        assert storage.count() == 3
        assert storage.count(status="active") == 2
        assert storage.count(status="paused") == 1
