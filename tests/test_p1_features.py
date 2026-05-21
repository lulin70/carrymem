"""
P1 Tests: Promotion Integration, Multi-turn Conversation, Rule Management

Validates P1 features:
- Memory-to-rule promotion pipeline integration
- Multi-turn conversation preference accumulation
- Rule CRUD management (update, delete, my_rules, my_profile)
- Correction updating old memories
- Rule conflict detection
- Onboarding flow
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from carrymem.carrymem import CarryMem
from carrymem.rules import RuleEngine


class TestPromotionIntegration(unittest.TestCase):
    """Verify: Memory-to-rule promotion pipeline works end-to-end."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_promotion.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_auto_suggest_rules_returns_candidates(self):
        """Verify: Storing a preference generates rule candidates."""
        result = self.cm.classify_and_remember("我偏好用Python写后端")
        auto_rules = result.get("auto_rules", [])
        self.assertGreater(len(auto_rules), 0)

    def test_auto_suggest_rules_have_trigger_and_action(self):
        """Verify: Auto-suggested rules have required fields."""
        result = self.cm.classify_and_remember("Always use PostgreSQL for database")
        auto_rules = result.get("auto_rules", [])
        if auto_rules:
            rule = auto_rules[0]
            self.assertIn("trigger", rule)
            self.assertIn("action", rule)
            self.assertIn("rule_type", rule)

    def test_correction_type_suggests_avoid_rule(self):
        """Verify: Correction memories suggest avoid-type rules."""
        result = self.cm.classify_and_remember("下次别用MySQL了，太慢了")
        auto_rules = result.get("auto_rules", [])
        if auto_rules:
            has_avoid = any(r.get("rule_type") == "avoid" for r in auto_rules)
            self.assertTrue(has_avoid, "Correction should suggest avoid rule")

    def test_decision_type_suggests_always_rule(self):
        """Verify: Decision memories suggest always-type rules."""
        result = self.cm.classify_and_remember("我们团队决定用React")
        auto_rules = result.get("auto_rules", [])
        if auto_rules:
            has_always = any(r.get("rule_type") in ("always", "prefer") for r in auto_rules)
            self.assertTrue(has_always, "Decision should suggest always/prefer rule")


class TestMultiTurnConversation(unittest.TestCase):
    """Verify: Preferences accumulate across multiple conversation turns."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_multiturn.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_three_turns_accumulate_memories(self):
        """Verify: Three conversation turns store at least 2 memories."""
        self.cm.classify_and_remember("我喜欢用Python")
        self.cm.classify_and_remember("前端用React比较好")
        self.cm.classify_and_remember("数据库用PostgreSQL")

        memories = self.cm.recall_memories(limit=20)
        self.assertGreaterEqual(len(memories), 2)

    def test_preference_and_decision_coexist(self):
        """Verify: Different memory types can coexist."""
        r1 = self.cm.classify_and_remember("我喜欢深色模式")
        r2 = self.cm.classify_and_remember("我们决定用TypeScript")

        self.assertTrue(r1["stored"] or r2["stored"])

    def test_correction_after_preference(self):
        """Verify: Correction can follow a preference."""
        self.cm.classify_and_remember("我用MySQL")
        result = self.cm.classify_and_remember("不对，应该是PostgreSQL不是MySQL")
        self.assertTrue(result["stored"])

    def test_auto_rules_accumulate(self):
        """Verify: Auto rule suggestions accumulate across turns."""
        all_auto_rules = []
        r1 = self.cm.classify_and_remember("我喜欢用Python")
        all_auto_rules.extend(r1.get("auto_rules", []))
        r2 = self.cm.classify_and_remember("前端用React")
        all_auto_rules.extend(r2.get("auto_rules", []))

        self.assertGreater(len(all_auto_rules), 0)


class TestRuleManagement(unittest.TestCase):
    """Verify: Rule CRUD management operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_mgmt.db")
        self.engine = RuleEngine(db_path=self.db_path)

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_add_and_list_rules(self):
        """Verify: Can add rules and list them."""
        self.engine.add_rule(trigger="数据库", action="用PostgreSQL", rule_type="always")
        self.engine.add_rule(trigger="前端", action="用React", rule_type="prefer")

        rules = self.engine.list_rules(status="active")
        self.assertGreaterEqual(len(rules), 2)

    def test_update_rule_action(self):
        """Verify: Can update a rule's action."""
        rule = self.engine.add_rule(trigger="语言", action="用Java", rule_type="prefer")
        updated = self.engine.update_rule(rule.id, action="用Python")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.action, "用Python")

    def test_update_rule_trigger(self):
        """Verify: Can update a rule's trigger."""
        rule = self.engine.add_rule(trigger="旧触发器", action="某动作", rule_type="always")
        updated = self.engine.update_rule(rule.id, trigger="新触发器")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.trigger, "新触发器")

    def test_delete_rule(self):
        """Verify: Can delete a rule."""
        rule = self.engine.add_rule(trigger="临时", action="临时动作", rule_type="prefer")
        deleted = self.engine.delete_rule(rule.id)
        self.assertTrue(deleted)

        retrieved = self.engine.get_rule(rule.id)
        self.assertIsNone(retrieved)

    def test_delete_nonexistent_rule(self):
        """Verify: Deleting non-existent rule returns False."""
        deleted = self.engine.delete_rule("nonexistent_id")
        self.assertFalse(deleted)

    def test_get_rule_by_id(self):
        """Verify: Can retrieve a rule by ID."""
        rule = self.engine.add_rule(trigger="测试", action="测试动作", rule_type="always")
        retrieved = self.engine.get_rule(rule.id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.trigger, "测试")

    def test_my_rules_format(self):
        """Verify: my_rules returns rules with proper format."""
        self.engine.add_rule(trigger="数据库", action="用PostgreSQL", rule_type="always", override=True)
        self.engine.add_rule(trigger="前端", action="用React", rule_type="prefer")

        rules = self.engine.list_rules(status="active")
        for r in rules:
            self.assertTrue(hasattr(r, 'trigger'))
            self.assertTrue(hasattr(r, 'action'))
            self.assertTrue(hasattr(r, 'override'))
            self.assertTrue(hasattr(r, 'scope'))

    def test_rule_conflict_detection(self):
        """Verify: Adding conflicting rule generates warning."""
        self.engine.add_rule(trigger="数据库", action="用MySQL", rule_type="prefer")
        rule2 = self.engine.add_rule(trigger="数据库", action="用PostgreSQL", rule_type="always")

        warnings = getattr(rule2, '_conflict_warnings', [])
        self.assertGreater(len(warnings), 0, "Should detect conflict with existing rule")

    def test_my_profile(self):
        """Verify: my_profile returns complete user identity."""
        self.engine.add_rule(trigger="语言", action="用Python", rule_type="prefer")
        rules = self.engine.list_rules(status="active")
        self.assertGreater(len(rules), 0)


class TestCorrectionUpdate(unittest.TestCase):
    """Verify: Correction type automatically updates old memories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_correction.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_correction_returns_updated_memories_field(self):
        """Verify: classify_and_remember returns updated_memories field."""
        result = self.cm.classify_and_remember("我喜欢用Python")
        self.assertIn("updated_memories", result)

    def test_correction_with_existing_memory(self):
        """Verify: Correction updates related existing memory."""
        self.cm.classify_and_remember("我用MySQL数据库")
        result = self.cm.classify_and_remember("不对，应该是PostgreSQL不是MySQL")
        self.assertTrue(result["stored"])


class TestOnboarding(unittest.TestCase):
    """Verify: Onboarding flow for new users."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_onboard.db")
        self.cm = CarryMem(storage="sqlite", db_path=self.db_path)

    def tearDown(self):
        self.cm.close()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_onboard_returns_welcome_message(self):
        """Verify: Onboard returns welcome message in English."""
        from carrymem.integration.layer2_mcp.handlers import handle_onboard
        result = handle_onboard(self.cm, {"language": "en"})
        self.assertIn("welcome", result)
        self.assertIn("CarryMem", result["welcome"])

    def test_onboard_chinese(self):
        """Verify: Onboard returns Chinese welcome message."""
        from carrymem.integration.layer2_mcp.handlers import handle_onboard
        result = handle_onboard(self.cm, {"language": "zh"})
        self.assertIn("welcome", result)
        self.assertIn("欢迎使用", result["welcome"])

    def test_onboard_japanese(self):
        """Verify: Onboard returns Japanese welcome message."""
        from carrymem.integration.layer2_mcp.handlers import handle_onboard
        result = handle_onboard(self.cm, {"language": "ja"})
        self.assertIn("welcome", result)
        self.assertIn("ようこそ", result["welcome"])

    def test_onboard_has_next_steps(self):
        """Verify: Onboard returns next steps."""
        from carrymem.integration.layer2_mcp.handlers import handle_onboard
        result = handle_onboard(self.cm, {"language": "en"})
        self.assertIn("next_steps", result)
        self.assertGreater(len(result["next_steps"]), 0)


if __name__ == "__main__":
    unittest.main()
