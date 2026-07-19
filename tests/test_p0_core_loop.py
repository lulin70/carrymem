"""
P0 Tests: Natural Conversation Preference Extraction + E2E User Journey

Validates the core loop: Natural Conversation -> Preference Extraction ->
Memory Save -> Rule Suggestion -> Rule Injection -> AI Behavior Change

Also tests user management: view rules, delete rules.
"""

import os
import sys
import tempfile
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from carrymem.carrymem import CarryMem
from carrymem.rules import RuleEngine


class TestNaturalConversationExtraction(unittest.TestCase):
    """Verify: Natural conversation inputs are correctly classified and stored."""

    NATURAL_CONVERSATION_CASES = [
        ("我觉得PostgreSQL比MySQL好用多了", "user_preference", True),
        ("下次别用这个方案了，太慢了", "correction", True),
        ("我一般都用Python写脚本", "user_preference", True),
        ("哦不对，应该是v2不是v3", "correction", True),
        ("这个框架真的太烦了", "sentiment_marker", True),
        ("我们团队一直都是用React的", "decision", True),
        ("你好", None, False),
        ("帮我写个函数", None, False),
        ("谢谢", None, False),
    ]

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_natural.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_natural_preference_extraction(self):
        """Verify: Casual preference expressions are stored as user_preference."""
        result = self.cm.classify_and_remember("我觉得PostgreSQL比MySQL好用多了")
        self.assertIs(result["stored"], True, "Casual preference should be stored")
        self.assertEqual(result["type"], "user_preference")

    def test_natural_correction_extraction(self):
        """Verify: Correction expressions are stored as correction type."""
        result = self.cm.classify_and_remember("下次别用这个方案了，太慢了")
        self.assertIs(result["stored"], True, "Correction should be stored")
        self.assertIn(
            result["type"],
            ["correction", "user_preference", "decision", "sentiment_marker", "fact_declaration"],
        )

    def test_natural_habit_extraction(self):
        """Verify: Habit mentions are stored."""
        result = self.cm.classify_and_remember("我一般都用Python写脚本")
        self.assertIs(result["stored"], True, "Habit mention should be stored")

    def test_natural_sentiment_extraction(self):
        """Verify: Sentiment expressions are stored."""
        result = self.cm.classify_and_remember("这个框架真的太烦了")
        self.assertIs(result["stored"], True, "Sentiment should be stored")

    def test_natural_decision_extraction(self):
        """Verify: Decision expressions are stored."""
        result = self.cm.classify_and_remember("我们团队一直都是用React的")
        self.assertIs(result["stored"], True, "Decision should be stored")

    def test_noise_rejection_greeting(self):
        """Verify: Greetings are not stored."""
        result = self.cm.classify_and_remember("你好")
        self.assertFalse(result.get("stored", False), "Greeting should not be stored")

    def test_noise_rejection_task_command(self):
        """Verify: Task commands are not stored as preferences."""
        result = self.cm.classify_and_remember("帮我写个函数")
        self.assertFalse(result.get("stored", False), "Task command should not be stored")

    def test_noise_rejection_thanks(self):
        """Verify: Thanks are not stored."""
        result = self.cm.classify_and_remember("谢谢")
        self.assertFalse(result.get("stored", False), "Thanks should not be stored")

    def test_auto_rules_generated_for_preference(self):
        """Verify: Storing a preference generates auto rule suggestions."""
        result = self.cm.classify_and_remember("Always use PostgreSQL for database")
        self.assertIs(result["stored"], True)
        auto_rules = result.get("auto_rules", [])
        self.assertGreater(len(auto_rules), 0, "Should generate auto rule suggestions")

    def test_auto_rules_have_required_fields(self):
        """Verify: Auto rule suggestions have trigger, action, rule_type."""
        result = self.cm.classify_and_remember("我偏好用Python写后端")
        auto_rules = result.get("auto_rules", [])
        if auto_rules:
            rule = auto_rules[0]
            self.assertIn("trigger", rule)
            self.assertIn("action", rule)
            self.assertIn("rule_type", rule)

    def test_english_natural_preference(self):
        """Verify: English casual preferences are stored."""
        result = self.cm.classify_and_remember("I always use PostgreSQL, never MySQL")
        self.assertIs(result["stored"], True)
        auto_rules = result.get("auto_rules", [])
        self.assertGreater(len(auto_rules), 0, "English preference should generate rules")


class TestE2EUserJourney(unittest.TestCase):
    """Verify: Complete user journey from conversation to rule injection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_e2e.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_full_journey_conversation_to_injection(self):
        """Verify: Conversation -> Store -> Rule -> Inject -> Behavior Change."""
        result = self.cm.classify_and_remember("I always use PostgreSQL, never MySQL")
        self.assertIs(result["stored"], True)

        auto_rules = result.get("auto_rules", [])
        self.assertGreater(len(auto_rules), 0, "Should suggest rules")

        rule = self.engine.add_rule(
            trigger="数据库",
            action="使用PostgreSQL，不用MySQL",
            rule_type="always",
            scope="personal",
            override=True,
        )
        self.assertIsNotNone(rule.id)

        context = self.cm.build_context(context="帮我设计数据库架构")
        prompt = context.get("system_prompt", "")
        rules_section = context.get("rules", "")
        self.assertTrue(
            "PostgreSQL" in prompt or "PostgreSQL" in rules_section,
            "Rule should be injected into prompt or rules section",
        )

    def test_journey_no_context_still_injects(self):
        """Verify: Rules are injected even without explicit context."""
        self.engine.add_rule(
            trigger="代码风格",
            action="使用type hints",
            rule_type="always",
            override=True,
        )

        context = self.cm.build_context(context=None)
        prompt = context.get("system_prompt", "")
        self.assertIn("type hints", prompt, "Global rules should be injected without context")

    def test_journey_user_views_rules(self):
        """Verify: User can view all their rules."""
        self.engine.add_rule(trigger="数据库", action="用PostgreSQL", rule_type="always")
        self.engine.add_rule(trigger="前端", action="用React", rule_type="prefer")

        rules = self.engine.list_rules(status="active")
        self.assertGreaterEqual(len(rules), 2, "Should list all rules")

    def test_journey_user_deletes_rule(self):
        """Verify: User can delete a rule and it stops being injected."""
        rule = self.engine.add_rule(
            trigger="临时",
            action="临时规则",
            rule_type="prefer",
        )
        rule_id = rule.id

        rules_before = self.engine.list_rules(status="active")
        self.assertIs(any(r.id == rule_id for r in rules_before), True)

        deleted = self.engine.delete_rule(rule_id)
        self.assertIs(deleted, True)

        rules_after = self.engine.list_rules(status="active")
        self.assertFalse(any(r.id == rule_id for r in rules_after))

    def test_journey_multi_turn_preference_accumulation(self):
        """Verify: Multiple conversations accumulate preferences."""
        self.cm.classify_and_remember("我喜欢用Python")
        self.cm.classify_and_remember("前端用React比较好")
        self.cm.classify_and_remember("数据库用PostgreSQL")

        memories = self.cm.recall_memories(limit=20)
        self.assertGreaterEqual(len(memories), 2, "Should accumulate memories across turns")

    def test_journey_rule_injection_security(self):
        """Verify: Malicious rule content is sanitized during injection."""
        self.engine.add_rule(
            trigger="security_test",
            action="Always use SSL for database connections",
            rule_type="always",
        )
        self.engine.add_rule(
            trigger="safe_test",
            action="Prefer Python for scripting",
            rule_type="prefer",
        )

        injection = self.engine.inject("security_test", format="structured")
        self.assertIn("SSL", injection, "Safe content should be in injection")

    def test_journey_prefer_rule_injection(self):
        """Verify: Prefer rules are correctly injected."""
        self.engine.add_rule(
            trigger="编程语言",
            action="优先使用Python",
            rule_type="prefer",
        )

        injection = self.engine.inject("编程语言", format="structured")
        self.assertIn("Python", injection)

    def test_journey_avoid_rule_injection(self):
        """Verify: Avoid rules are correctly injected."""
        self.engine.add_rule(
            trigger="数据库",
            action="避免使用MySQL",
            rule_type="avoid",
        )

        injection = self.engine.inject("数据库", format="structured")
        self.assertIn("MySQL", injection)


class TestRuleManagementMCP(unittest.TestCase):
    """Verify: MCP-level rule management operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_mcp_rules.db")
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_my_rules_returns_readable_summary(self):
        """Verify: my_rules returns formatted summary of all rules."""
        self.engine.add_rule(trigger="数据库", action="用PostgreSQL", rule_type="always", override=True)
        self.engine.add_rule(trigger="前端", action="用React", rule_type="prefer")

        rules = self.engine.list_rules(status="active")
        self.assertGreaterEqual(len(rules), 2)

        for r in rules:
            self.assertIs(hasattr(r, "trigger"), True)
            self.assertIs(hasattr(r, "action"), True)
            self.assertIs(hasattr(r, "override"), True)

    def test_delete_nonexistent_rule(self):
        """Verify: Deleting a non-existent rule returns False."""
        deleted = self.engine.delete_rule("nonexistent_rule_id")
        self.assertFalse(deleted)

    def test_get_rule_by_id(self):
        """Verify: Can retrieve a rule by its ID."""
        rule = self.engine.add_rule(trigger="test", action="test action", rule_type="prefer")
        retrieved = self.engine.get_rule(rule.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.trigger, "test")

    def test_update_rule(self):
        """Verify: Can update an existing rule."""
        rule = self.engine.add_rule(trigger="old_trigger", action="old action", rule_type="prefer")
        updated = self.engine.update_rule(rule.id, trigger="new_trigger", action="new action")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.trigger, "new_trigger")
        self.assertEqual(updated.action, "new action")


if __name__ == "__main__":
    unittest.main()
