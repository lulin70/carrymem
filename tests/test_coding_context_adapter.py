"""Tests for CodingContextAdapter."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from carrymem.adapters.coding_context_adapter import (
    CodingContextAdapter,
    _infer_framework,
    _infer_language,
    _infer_memory_type,
    _parse_file,
)


class TestInferMemoryType(unittest.TestCase):
    def test_ai_instruction_preference(self):
        content = "Always prefer Python for backend services"
        self.assertEqual(_infer_memory_type(content, "ai_instruction"), "user_preference")

    def test_ai_instruction_correction(self):
        content = "Fix the bug where null pointer causes crash"
        self.assertEqual(_infer_memory_type(content, "ai_instruction"), "correction")

    def test_ai_instruction_decision(self):
        content = "Lint all code with ruff before committing"
        self.assertEqual(_infer_memory_type(content, "ai_instruction"), "decision")

    def test_ai_instruction_default(self):
        content = "This project uses various tools"
        self.assertEqual(_infer_memory_type(content, "ai_instruction"), "decision")

    def test_editor_config(self):
        self.assertEqual(_infer_memory_type("", "editor_config"), "decision")

    def test_lint_config(self):
        self.assertEqual(_infer_memory_type("", "lint_config"), "decision")

    def test_project_meta(self):
        self.assertEqual(_infer_memory_type("", "project_meta"), "personal_fact")


class TestInferLanguage(unittest.TestCase):
    def test_python_file(self):
        self.assertEqual(_infer_language("main.py", ""), "python")

    def test_typescript_file(self):
        self.assertEqual(_infer_language("app.ts", ""), "typescript")

    def test_rust_file(self):
        self.assertEqual(_infer_language("main.rs", ""), "rust")

    def test_go_file(self):
        self.assertEqual(_infer_language("main.go", ""), "go")

    def test_package_json_react(self):
        content = json.dumps({"dependencies": {"react": "^18.0.0"}})
        self.assertEqual(_infer_language("package.json", content), "react")

    def test_package_json_plain(self):
        content = json.dumps({"dependencies": {"express": "^4.0.0"}})
        self.assertEqual(_infer_language("package.json", content), "javascript")

    def test_pyproject(self):
        self.assertEqual(_infer_language("pyproject.toml", ""), "python")

    def test_cargo(self):
        self.assertEqual(_infer_language("Cargo.toml", ""), "rust")

    def test_unknown(self):
        self.assertIsNone(_infer_language("config.yaml", ""))


class TestInferFramework(unittest.TestCase):
    def test_python_django(self):
        self.assertEqual(_infer_framework("django settings", "python"), "django")

    def test_python_fastapi(self):
        self.assertEqual(_infer_framework("fastapi application", "python"), "fastapi")

    def test_js_react(self):
        self.assertEqual(_infer_framework("react component", "javascript"), "react")

    def test_ts_nextjs(self):
        self.assertEqual(_infer_framework("next.js app", "typescript"), "nextjs")

    def test_rust_axum(self):
        self.assertEqual(_infer_framework("axum router", "rust"), "axum")

    def test_no_match(self):
        self.assertIsNone(_infer_framework("basic code", "python"))


class TestParseFile(unittest.TestCase):
    def test_parse_claude_md(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", prefix="CLAUDE", delete=False, dir="/tmp") as f:
            f.write("# Coding Style\nAlways prefer Python for backend\n\n# Bug Fixes\nFix null pointer issues\n")
            f.flush()
            path = Path(f.name)
            path.rename(path.parent / "CLAUDE.md")
            target = path.parent / "CLAUDE.md"

        try:
            entries = _parse_file(target)
            self.assertGreaterEqual(len(entries), 1)
            for entry in entries:
                self.assertIn("title", entry)
                self.assertIn("content", entry)
                self.assertIn("memory_type", entry)
                self.assertEqual(entry["source_type"], "ai_instruction")
        finally:
            target.unlink(missing_ok=True)

    def test_parse_editorconfig(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False, dir="/tmp") as f:
            f.write("root = true\n\n[*]\nindent_style = space\nindent_size = 4\n")
            f.flush()
            path = Path(f.name)
            target = path.parent / ".editorconfig"
            path.rename(target)

        try:
            entries = _parse_file(target)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["source_type"], "editor_config")
            self.assertEqual(entries[0]["memory_type"], "decision")
        finally:
            target.unlink(missing_ok=True)

    def test_parse_package_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, dir="/tmp") as f:
            json.dump({"name": "my-app", "dependencies": {"react": "^18.0.0"}}, f)
            f.flush()
            path = Path(f.name)
            target = path.parent / "package.json"
            path.rename(target)

        try:
            entries = _parse_file(target)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["source_type"], "project_meta")
            self.assertEqual(entries[0]["language"], "react")
        finally:
            target.unlink(missing_ok=True)

    def test_parse_unknown_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir="/tmp") as f:
            f.write("random content")
            f.flush()
            target = Path(f.name)

        try:
            entries = _parse_file(target)
            self.assertEqual(len(entries), 0)
        finally:
            target.unlink(missing_ok=True)


class TestCodingContextAdapter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.claude_md = Path(self.tmpdir) / "CLAUDE.md"
        self.claude_md.write_text("# Style\nAlways use TypeScript\n\n# Testing\nUse pytest for tests\n")

        self.editorconfig = Path(self.tmpdir) / ".editorconfig"
        self.editorconfig.write_text("root = true\n\n[*]\nindent_style = space\nindent_size = 2\n")

        self.pkg_json = Path(self.tmpdir) / "package.json"
        self.pkg_json.write_text(json.dumps({"name": "test-app", "dependencies": {"react": "^18.0.0"}}))

        self.adapter = CodingContextAdapter(self.tmpdir)

    def tearDown(self):
        self.adapter.close()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_index_project(self):
        stats = self.adapter.index_project()
        self.assertGreaterEqual(stats["files_found"], 2)
        self.assertGreaterEqual(stats["files_indexed"], 2)
        self.assertGreater(stats["entries_created"], 0)

    def test_recall(self):
        self.adapter.index_project()
        results = self.adapter.recall("TypeScript")
        self.assertGreater(len(results), 0)

    def test_recall_with_filter(self):
        self.adapter.index_project()
        results = self.adapter.recall("", limit=50, filters={"source_type": "editor_config"})
        for r in results:
            self.assertEqual(r["source_type"], "editor_config")

    def test_get_conventions(self):
        self.adapter.index_project()
        conventions = self.adapter.get_conventions()
        self.assertIsInstance(conventions, list)

    def test_get_tech_stack(self):
        self.adapter.index_project()
        stack = self.adapter.get_tech_stack()
        self.assertIsInstance(stack, dict)

    def test_incremental_index(self):
        self.adapter.index_project()
        stats1 = self.adapter.index_project()
        self.assertEqual(stats1["files_skipped"], stats1["files_found"])

    def test_force_reindex(self):
        self.adapter.index_project()
        stats = self.adapter.index_project(force=True)
        self.assertGreater(stats["files_indexed"], 0)

    def test_read_only(self):
        with self.assertRaises(NotImplementedError):
            self.adapter.remember("test")
        with self.assertRaises(NotImplementedError):
            self.adapter.forget("test")

    def test_nonexistent_project(self):
        with self.assertRaises(FileNotFoundError):
            CodingContextAdapter("/nonexistent/path")

    def test_name(self):
        self.assertEqual(self.adapter.name, "coding_context")


if __name__ == "__main__":
    unittest.main()
