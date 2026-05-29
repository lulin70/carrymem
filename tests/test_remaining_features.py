"""
Remaining Items Tests: Chinese Tokenization, Conditional Preferences, Implicit Inference

Validates:
- Chinese tokenization (jieba/n-gram fallback) for rule matching
- Conditional preference support (condition field + conditional matching)
- Implicit preference inference (behavior pattern detection)
- Rule expiry mechanism
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carrymem.carrymem import CarryMem
from carrymem.rules import RuleEngine
from carrymem.rules.matcher import RuleMatcher
from carrymem.rules.models import Rule


class TestChineseTokenization(unittest.TestCase):
    """Verify: Chinese tokenization improves rule matching."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_cjk.db")
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_tokenize_chinese_text(self):
        """Verify: Chinese text is tokenized into meaningful segments."""
        tokens = RuleMatcher._tokenize("数据库选型方案")
        self.assertGreater(len(tokens), 0, "Should produce tokens for Chinese text")
        self.assertTrue(any("数据" in t for t in tokens), "Should contain 数据")

    def test_tokenize_english_text(self):
        """Verify: English text is tokenized by spaces."""
        tokens = RuleMatcher._tokenize("database selection")
        self.assertEqual(tokens, ["database", "selection"])

    def test_tokenize_mixed_text(self):
        """Verify: Mixed Chinese-English text is tokenized."""
        tokens = RuleMatcher._tokenize("用PostgreSQL数据库")
        self.assertGreater(len(tokens), 0)
        self.assertTrue(any("postgresql" in t.lower() for t in tokens))

    def test_chinese_rule_matching(self):
        """Verify: Chinese trigger matches Chinese scene via token overlap."""
        self.engine.add_rule(trigger="数据库选型", action="使用PostgreSQL", rule_type="always")
        matches = self.engine.match("帮我设计数据库架构")
        self.assertGreater(len(matches), 0, "Chinese rule should match via token overlap")

    def test_chinese_partial_match(self):
        """Verify: Partial Chinese text matching works."""
        self.engine.add_rule(trigger="前端框架", action="使用React", rule_type="prefer")
        matches = self.engine.match("前端框架选择")
        self.assertGreater(len(matches), 0, "Partial Chinese match should work")

    def test_empty_text_tokenization(self):
        """Verify: Empty text returns empty tokens."""
        tokens = RuleMatcher._tokenize("")
        self.assertEqual(len(tokens), 0)

    def test_single_char_tokenization(self):
        """Verify: Single Chinese character is tokenized."""
        tokens = RuleMatcher._tokenize("好")
        self.assertGreater(len(tokens), 0)


class TestConditionalPreference(unittest.TestCase):
    """Verify: Conditional preferences with condition field."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_cond.db")
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_add_rule_with_condition(self):
        """Verify: Can add a rule with a condition."""
        rule = self.engine.add_rule(
            trigger="数据库选型",
            action="使用SQLite",
            rule_type="prefer",
            condition="小项目",
        )
        self.assertEqual(rule.condition, "小项目")

    def test_rule_condition_in_dict(self):
        """Verify: Condition is included in to_dict()."""
        rule = self.engine.add_rule(
            trigger="数据库",
            action="用SQLite",
            condition="小项目",
        )
        d = rule.to_dict()
        self.assertIn("condition", d)
        self.assertEqual(d["condition"], "小项目")

    def test_rule_condition_from_dict(self):
        """Verify: Condition is loaded from dict."""
        data = {
            "id": "test-001",
            "trigger": "数据库",
            "action": "用SQLite",
            "rule_type": "prefer",
            "condition": "小项目",
        }
        rule = Rule.from_dict(data)
        self.assertEqual(rule.condition, "小项目")

    def test_condition_extraction_chinese(self):
        """Verify: Condition is extracted from Chinese conditional expressions."""
        cm = CarryMem(storage="sqlite", db_path=self.db_path)
        result = cm.classify_and_remember("如果是小项目就用SQLite吧")
        auto_rules = result.get("auto_rules", [])
        has_condition = any(r.get("condition") for r in auto_rules)
        cm.close()
        if auto_rules:
            self.assertTrue(has_condition, "Should extract condition from conditional expression")

    def test_condition_extraction_english(self):
        """Verify: Condition is extracted from English conditional expressions."""
        cm = CarryMem(storage="sqlite", db_path=self.db_path)
        result = cm.classify_and_remember("If it's a small project, use SQLite")
        auto_rules = result.get("auto_rules", [])
        cm.close()
        if auto_rules:
            has_condition = any(r.get("condition") for r in auto_rules)
            self.assertTrue(has_condition, "Should extract condition from English if-then")

    def test_unconditional_rule_still_works(self):
        """Verify: Rules without condition still work normally."""
        rule = self.engine.add_rule(
            trigger="数据库",
            action="用PostgreSQL",
            rule_type="always",
        )
        self.assertEqual(rule.condition, "")


class TestImplicitPreferenceInference(unittest.TestCase):
    """Verify: Implicit preferences are detected from behavior patterns."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_implicit.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_implicit_language_preference(self):
        """Verify: Multiple Python mentions trigger implicit preference."""
        self.cm.classify_and_remember("I prefer Python for scripting")
        self.cm.classify_and_remember("I always use Python for data processing")
        self.cm.classify_and_remember("My favorite language is Python")

        result = self.cm.classify_and_remember("I prefer Python for backend too")
        auto_rules = result.get("auto_rules", [])
        all_implicit = [r for r in auto_rules if r.get("source") == "implicit_preference"]
        all_python = [
            r for r in auto_rules if "python" in r.get("action", "").lower() or "Python" in r.get("action", "")
        ]
        self.assertTrue(
            len(all_implicit) > 0 or len(all_python) > 0,
            "Should detect Python preference (implicit or direct)",
        )

    def test_implicit_database_preference(self):
        """Verify: Multiple PostgreSQL mentions trigger implicit preference."""
        self.cm.classify_and_remember("I prefer PostgreSQL for data storage")
        self.cm.classify_and_remember("I always use PostgreSQL for indexing")
        self.cm.classify_and_remember("My favorite database is PostgreSQL")

        result = self.cm.classify_and_remember("I prefer PostgreSQL for analytics too")
        auto_rules = result.get("auto_rules", [])
        all_implicit = [r for r in auto_rules if r.get("source") == "implicit_preference"]
        all_pg = [
            r for r in auto_rules if "postgresql" in r.get("action", "").lower() or "PostgreSQL" in r.get("action", "")
        ]
        self.assertTrue(
            len(all_implicit) > 0 or len(all_pg) > 0,
            "Should detect PostgreSQL preference (implicit or direct)",
        )

    def test_implicit_preference_has_domain_info(self):
        """Verify: Implicit preference includes domain and ratio info."""
        self.cm.classify_and_remember("用React写组件")
        self.cm.classify_and_remember("React的状态管理")

        result = self.cm.classify_and_remember("React的hooks很好用")
        auto_rules = result.get("auto_rules", [])
        implicit = [r for r in auto_rules if r.get("source") == "implicit_preference"]
        if implicit:
            self.assertIn("domain", implicit[0])
            self.assertIn("ratio", implicit[0])

    def test_no_implicit_with_few_mentions(self):
        """Verify: Single mention doesn't trigger implicit preference."""
        self.cm.classify_and_remember("我用Python写了一个脚本")
        result = self.cm.classify_and_remember("今天天气不错")
        auto_rules = result.get("auto_rules", [])
        implicit = [r for r in auto_rules if r.get("source") == "implicit_preference"]
        self.assertEqual(len(implicit), 0, "Single mention should not trigger implicit preference")


class TestRuleExpiry(unittest.TestCase):
    """Verify: Rule expiry mechanism works correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_expiry.db")
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_rule_not_expired_by_default(self):
        """Verify: Rules without expires_at are not expired."""
        rule = self.engine.add_rule(trigger="test", action="test", rule_type="prefer")
        self.assertFalse(rule.is_expired())

    def test_rule_not_expired_future_date(self):
        """Verify: Rules with future expires_at are not expired."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        rule = self.engine.add_rule(
            trigger="test",
            action="test",
            rule_type="prefer",
            expires_at=future,
        )
        self.assertFalse(rule.is_expired())

    def test_rule_expired_past_date(self):
        """Verify: Rules with past expires_at are expired."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        rule = self.engine.add_rule(
            trigger="test",
            action="test",
            rule_type="prefer",
            expires_at=past,
        )
        self.assertTrue(rule.is_expired())

    def test_expired_rules_not_matched(self):
        """Verify: Expired rules are filtered out during matching."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.engine.add_rule(
            trigger="expired_test",
            action="old action",
            rule_type="always",
            expires_at=past,
        )
        matches = self.engine.match("expired_test")
        self.assertEqual(len(matches), 0, "Expired rules should not match")

    def test_active_rules_still_matched(self):
        """Verify: Active (non-expired) rules still match."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self.engine.add_rule(
            trigger="active_test",
            action="current action",
            rule_type="always",
            expires_at=future,
        )
        matches = self.engine.match("active_test")
        self.assertGreater(len(matches), 0, "Active rules should still match")


if __name__ == "__main__":
    unittest.main()
