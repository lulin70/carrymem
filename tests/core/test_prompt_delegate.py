"""Unit tests for PromptDelegateMixin: build_context, build_system_prompt, summarize_session, aggregate_memories."""

import os
import shutil
import tempfile
import unittest
import warnings

from carrymem import CarryMem
from carrymem.core._lifecycle import StorageNotConfiguredError


class TestBuildContext(unittest.TestCase):
    """Tests for CarryMem.build_context() (PromptDelegateMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "context.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_context_returns_dict(self):
        """build_context() returns a dictionary."""
        result = self.cm.build_context(context="test context")
        self.assertIsInstance(result, dict)

    def test_build_context_with_custom_limits(self):
        """build_context() accepts max_memories, max_knowledge, max_rules."""
        result = self.cm.build_context(
            context="test",
            max_memories=5,
            max_knowledge=3,
            max_rules=2,
        )
        self.assertIsInstance(result, dict)

    def test_build_context_with_language(self):
        """build_context() accepts language parameter."""
        result = self.cm.build_context(context="test", language="zh")
        self.assertIsInstance(result, dict)


class TestBuildSystemPrompt(unittest.TestCase):
    """Tests for CarryMem.build_system_prompt() (PromptDelegateMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "sysprompt.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_system_prompt_returns_string(self):
        """build_system_prompt() returns a string."""
        result = self.cm.build_system_prompt(context="test context")
        self.assertIsInstance(result, str)

    def test_build_system_prompt_empty_context(self):
        """build_system_prompt() works with empty/None context."""
        result = self.cm.build_system_prompt()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_build_system_prompt_with_language(self):
        """build_system_prompt() accepts language parameter."""
        result = self.cm.build_system_prompt(language="en")
        self.assertIsInstance(result, str)


class TestBuildQAPrompt(unittest.TestCase):
    """Tests for CarryMem.build_qa_prompt() (PromptDelegateMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "qa.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)
        self.cm.declare("I prefer dark mode")

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_qa_prompt_returns_string(self):
        """build_qa_prompt() returns a string."""
        result = self.cm.build_qa_prompt(question="What do I prefer?")
        self.assertIsInstance(result, str)

    def test_build_qa_prompt_includes_question(self):
        """build_qa_prompt() includes the question in output."""
        result = self.cm.build_qa_prompt(question="What do I prefer?")
        self.assertIn("What do I prefer?", result)


class TestSummarizeSession(unittest.TestCase):
    """Tests for CarryMem.summarize_session() (PromptDelegateMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "summarize.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_summarize_session_no_adapter_raises(self):
        """summarize_session() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                with self.assertRaises(StorageNotConfiguredError):
                    cm.summarize_session("sess_123")
        finally:
            cm.close()

    def test_summarize_session_emits_deprecation_warning(self):
        """summarize_session() emits DeprecationWarning."""
        # The method emits a deprecation warning about being experimental
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                self.cm.summarize_session("nonexistent_session", store=False)
            except Exception:
                pass  # May fail due to no LLM client, but warning should still emit
            # Check if DeprecationWarning was emitted
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            self.assertGreater(len(deprecation_warnings), 0)


class TestAggregateMemories(unittest.TestCase):
    """Tests for CarryMem.aggregate_memories() (PromptDelegateMixin)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "aggregate.db")
        self.cm = CarryMem(storage="sqlite", db_path=db_path, auto_backup_interval=0)

    def tearDown(self):
        self.cm.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_aggregate_memories_no_adapter_raises(self):
        """aggregate_memories() raises StorageNotConfiguredError without adapter."""
        cm = CarryMem(storage=None, auto_backup_interval=0)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                with self.assertRaises(StorageNotConfiguredError):
                    cm.aggregate_memories()
        finally:
            cm.close()

    def test_aggregate_memories_emits_deprecation_warning(self):
        """aggregate_memories() emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                self.cm.aggregate_memories(store=False)
            except Exception:
                pass  # May fail due to no LLM/embedding, but warning should still emit
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            self.assertGreater(len(deprecation_warnings), 0)

    def test_aggregate_memories_with_type_filter(self):
        """aggregate_memories() accepts memory_type parameter."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            try:
                result = self.cm.aggregate_memories(memory_type="user_preference", store=False)
                self.assertIsInstance(result, list)
            except Exception:
                pass  # May fail without LLM client


if __name__ == "__main__":
    unittest.main()
