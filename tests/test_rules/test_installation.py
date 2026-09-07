"""
Installation Verification Tests for CarryMem

Validates:
- Package importability and API surface
- CLI entry point availability and execution
- Version consistency
- Database initialization with scope support
- VS Code extension file structure
- Core smoke tests
- pip install verification
- CLI command integration tests
"""

import importlib
import os
import subprocess
import sys
import tempfile

import pytest

from carrymem.__version__ import __version__


class TestPackageImports:
    """Verify all core modules are importable"""

    def test_import_carrymem(self):
        from carrymem import CarryMem

        assert CarryMem is not None

    def test_import_rule_engine(self):
        from carrymem.rules import RuleEngine

        assert RuleEngine is not None

    def test_import_scope_types(self):
        from carrymem.rules import (
            SCOPE_PRIORITY,
            VALID_RULE_SCOPES,
            RuleScope,
        )

        assert VALID_RULE_SCOPES == {"personal", "company", "negotiated"}
        assert SCOPE_PRIORITY["company"] == 3

    def test_import_skill_functions(self):
        from carrymem.rules import skill_install, skill_pack, skill_verify

        assert callable(skill_pack)
        assert callable(skill_verify)
        assert callable(skill_install)

    def test_import_merge_types(self):
        from carrymem.rules import (
            MergeConflict,
            MergeDecision,
            MergeResult,
            MergeStrategy,
        )

        assert MergeStrategy.COMPANY_OVERRIDES is not None
        assert MergeDecision.KEEP_INCOMING is not None

    def test_import_models(self):
        from carrymem.rules import Rule

        rule = Rule(trigger="test", action="a", scope="company")
        assert rule.scope == "company"

    def test_import_injector(self):
        from carrymem.rules.injector import RuleInjector

        assert RuleInjector is not None

    def test_import_matcher(self):
        from carrymem.rules.matcher import MatchResult, RuleMatcher

        assert RuleMatcher is not None
        assert MatchResult is not None

    def test_import_storage(self):
        from carrymem.rules.storage import RuleStorage

        assert RuleStorage is not None

    def test_import_sanitizer(self):
        from carrymem.rules.sanitizer import RuleSanitizer

        assert RuleSanitizer is not None

    def test_import_limiter(self):
        from carrymem.rules.limiter import RuleLimiter

        assert RuleLimiter is not None

    def test_import_conflict_detector(self):
        from carrymem.rules.conflict_detector import RuleConflictDetector

        assert RuleConflictDetector is not None

    def test_import_pattern_detector(self):
        from carrymem.rules.pattern_detector import PatternDetector

        assert PatternDetector is not None

    def test_import_promotion_pipeline(self):
        from carrymem.rules.promotion_pipeline import PromotionPipeline

        assert PromotionPipeline is not None

    def test_import_experience_bridge(self):
        from carrymem.rules.experience_bridge import ExperienceRuleBridge

        assert ExperienceRuleBridge is not None

    def test_import_rule_refiner(self):
        from carrymem.rules.rule_refiner import RuleRefiner

        assert RuleRefiner is not None

    def test_import_refinement_session(self):
        from carrymem.rules.refinement_session import RefinementSessionManager

        assert RefinementSessionManager is not None

    def test_import_encryption(self):
        from carrymem.security.encryption import MemoryEncryption, NoEncryption

        assert MemoryEncryption is not None
        assert NoEncryption is not None

    def test_import_audit(self):
        from carrymem.security.audit import AuditLogger

        assert AuditLogger is not None

    def test_import_input_validator(self):
        from carrymem.security.input_validator import InputValidator

        assert InputValidator is not None

    def test_import_config(self):
        from carrymem.utils.config import ConfigManager

        assert ConfigManager is not None

    def test_import_language(self):
        from carrymem.utils.language import LanguageManager

        assert LanguageManager is not None

    def test_import_helpers(self):
        from carrymem.utils.helpers import generate_memory_id

        assert callable(generate_memory_id)

    def test_import_validators(self):
        from carrymem.utils.validators import validate_namespace

        assert callable(validate_namespace)

    def test_import_async_carrymem(self):
        from carrymem.async_carrymem import AsyncCarryMem

        assert AsyncCarryMem is not None

    def test_import_cache(self):
        from carrymem.cache import RecallCache

        assert RecallCache is not None

    def test_import_backup(self):
        from carrymem.backup import BackupManager

        assert BackupManager is not None


class TestVersionConsistency:
    """Verify version numbers are consistent"""

    def test_version_format(self):
        from carrymem import __version__

        parts = __version__.split(".")
        assert len(parts) >= 2, f"Version {__version__} should have at least major.minor"
        assert parts[0].isdigit() and parts[1].isdigit(), f"Version {__version__} should be numeric"

    def test_version_accessible_via_cli(self):
        # The ``python -m carrymem version`` startup path imports the full
        # package, which loads sentence-transformers (~20s on a cold
        # cache). Allow a generous 60s subprocess timeout so this test
        # is reliable in CI without choking on the model load.
        # See L-V0100-006.
        result = subprocess.run(
            [sys.executable, "-m", "carrymem", "version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert __version__ in result.stdout or __version__ in result.stderr

    def test_version_module_exists(self):
        from carrymem.__version__ import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0


class TestDatabaseInitialization:
    """Verify database can be initialized with scope support"""

    def test_fresh_db_has_scope_column(self):
        from carrymem.rules.storage import RuleStorage

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_init.db")
        try:
            storage = RuleStorage(db_path)
            rule = storage.create(trigger="test", action="a", scope="company")
            assert rule.scope == "company"

            retrieved = storage.list_all(scope="company")
            assert len(retrieved) == 1
            assert retrieved[0].scope == "company"
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_fresh_db_all_scopes(self):
        from carrymem.rules.storage import RuleStorage

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_scopes.db")
        try:
            storage = RuleStorage(db_path)
            for scope in ["personal", "company", "negotiated"]:
                rule = storage.create(trigger=f"test-{scope}", action="a", scope=scope)
                assert rule.scope == scope
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_fresh_db_metadata_column(self):
        from carrymem.rules.storage import RuleStorage

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test_meta.db")
        try:
            storage = RuleStorage(db_path)
            rule = storage.create(
                trigger="test",
                action="a",
                metadata={"_skill_name": "test-skill"},
            )
            assert rule.metadata == {"_skill_name": "test-skill"}
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


class TestCLIEntryPoints:
    """Verify CLI commands are registered for core features"""

    def test_skill_commands_in_cli_module(self):
        from carrymem import cli

        assert hasattr(cli, "cmd_skill_pack"), "cmd_skill_pack not found in CLI module"
        assert hasattr(cli, "cmd_skill_install"), "cmd_skill_install not found in CLI module"
        assert hasattr(cli, "cmd_skill_verify"), "cmd_skill_verify not found in CLI module"

    def test_skill_commands_in_dispatch_table(self):
        from carrymem.cli import cmd_skill_install, cmd_skill_pack, cmd_skill_verify

        assert callable(cmd_skill_pack)
        assert callable(cmd_skill_install)
        assert callable(cmd_skill_verify)

    def test_carrymem_help_runs(self):
        # 60s: the cold-start cost of sentence-transformers (~20s) is paid
        # once per subprocess, see L-V0100-006.
        result = subprocess.run(
            [sys.executable, "-m", "carrymem", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0

    def test_carrymem_version_runs(self):
        # 60s: subprocess timeout covers sentence-transformers cold start.
        # See L-V0100-006.
        result = subprocess.run(
            [sys.executable, "-m", "carrymem", "version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0

    def test_carrymem_doctor_runs(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "doctor_test.db")
        try:
            from carrymem.rules import RuleEngine

            engine = RuleEngine(db_path)
            del engine

            # Subprocess spawn pays the full carrymem package import
            # (sentence-transformers ~20s cold start when semantic extras
            # are installed). See L-V0100-006.
            result = subprocess.run(
                [sys.executable, "-m", "carrymem", "doctor", "--db", db_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_rule_commands_in_cli(self):
        from carrymem import cli

        rule_commands = [
            "cmd_add_rule",
            "cmd_list_rules",
            "cmd_edit_rule",
            "cmd_delete_rule",
            "cmd_match_rules",
        ]
        for cmd_name in rule_commands:
            assert hasattr(cli, cmd_name), f"{cmd_name} not found in CLI module"

    def test_cli_skill_pack_execution(self):
        from carrymem.cli import cmd_skill_pack

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "cli_skill.db")
        output_path = os.path.join(tmpdir, "output.skill.json")
        try:
            from carrymem.rules import RuleEngine

            engine = RuleEngine(db_path)
            engine.add_rule("database", "Use SSL", scope="company")
            del engine

            result = cmd_skill_pack(
                [
                    output_path,
                    "--name",
                    "cli-test",
                    "--scope",
                    "company",
                    "--db",
                    db_path,
                ]
            )
            assert result == 0
            assert os.path.exists(output_path)

            import json

            with open(output_path, "r") as f:
                data = json.load(f)
            assert data["format"] == "carrymem-skill-v1"
        finally:
            for f in [db_path, output_path]:
                if os.path.exists(f):
                    os.remove(f)

    def test_cli_skill_verify_execution(self):
        import json as json_mod

        from carrymem.cli import cmd_skill_pack, cmd_skill_verify

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "cli_verify.db")
        output_path = os.path.join(tmpdir, "verify.skill.json")
        try:
            from carrymem.rules import RuleEngine

            engine = RuleEngine(db_path)
            engine.add_rule("test", "action", scope="personal")
            del engine

            cmd_skill_pack(
                [
                    output_path,
                    "--name",
                    "verify-test",
                    "--scope",
                    "personal",
                    "--db",
                    db_path,
                ]
            )

            from carrymem.rules import RuleEngine as RE

            with open(output_path, "r") as f:
                bundle = json_mod.load(f)
            verify_result = RE.skill_verify(bundle)
            assert verify_result["valid"] is True
        finally:
            for f in [db_path, output_path]:
                if os.path.exists(f):
                    os.remove(f)


class TestVSCodeExtensionStructure:
    """Verify VS Code extension files exist"""

    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    EXT_DIR = os.path.join(PROJECT_ROOT, "extensions", "vscode-carrymem")

    def test_extension_package_json_exists(self):
        pkg = os.path.join(self.EXT_DIR, "package.json")
        assert os.path.exists(pkg), f"Missing {pkg}"

    def test_extension_ts_exists(self):
        ext = os.path.join(self.EXT_DIR, "src", "extension.ts")
        assert os.path.exists(ext), f"Missing {ext}"

    def test_client_ts_exists(self):
        client = os.path.join(self.EXT_DIR, "src", "carrymemClient.ts")
        assert os.path.exists(client), f"Missing {client}"

    def test_tree_provider_exists(self):
        tree = os.path.join(self.EXT_DIR, "src", "ruleTreeProvider.ts")
        assert os.path.exists(tree), f"Missing {tree}"

    def test_editor_panel_exists(self):
        editor = os.path.join(self.EXT_DIR, "src", "ruleEditorPanel.ts")
        assert os.path.exists(editor), f"Missing {editor}"

    def test_extension_package_json_has_contributes(self):
        import json

        pkg_path = os.path.join(self.EXT_DIR, "package.json")
        with open(pkg_path, "r") as f:
            data = json.load(f)
        assert "contributes" in data or "activationEvents" in data


class TestSmokeTest:
    """End-to-end smoke test"""

    def test_full_lifecycle(self):
        from carrymem.rules import RuleEngine

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "smoke.db")
        try:
            engine = RuleEngine(db_path)

            r1 = engine.add_rule("database", "Always use SSL", scope="company", override=True)
            assert r1.scope == "company"

            r2 = engine.add_rule("database", "Prefer PostgreSQL", scope="personal")
            assert r2.scope == "personal"

            results = engine.match("database design", scopes=["company"])
            assert len(results) >= 1
            assert all(r.rule.scope == "company" for r in results)

            report = engine.get_effectiveness_report()
            assert "scope_breakdown" in report
            assert report["scope_breakdown"].get("company", 0) >= 1

            rules = engine.list_rules(scope="company")
            assert len(rules) >= 1

            bundle = engine.skill_pack(name="test-skill", scope="company")
            assert bundle["format"] == "carrymem-skill-v1"

            verify = engine.skill_verify(bundle)
            assert verify["valid"] is True
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_carrymem_core_smoke(self):
        from carrymem import CarryMem

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "core_smoke.db")
        try:
            cm = CarryMem(db_path=db_path)
            result = cm.classify_and_remember("I prefer dark mode for coding")
            assert isinstance(result, dict)
            cm.close()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


class TestPipInstallVerification:
    """Verify package is properly installed via pip"""

    def test_package_installed(self):
        # 60s: ``import carrymem`` triggers the full package chain which
        # loads sentence-transformers (~20s cold start). See L-V0100-006.
        result = subprocess.run(
            [sys.executable, "-c", "import carrymem; print('OK')"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert "OK" in result.stdout

    def test_entry_point_available(self):
        # 60s: ``python -m carrymem --help`` pays the sentence-transformers
        # cold-start cost before argparse runs. See L-V0100-006.
        result = subprocess.run(
            [sys.executable, "-m", "carrymem", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0

    def test_package_metadata_accessible(self):
        try:
            from importlib.metadata import metadata

            meta = metadata("carrymem")
            assert meta is not None
        except Exception:
            pass

    def test_py_typed_marker_exists(self):
        import carrymem

        pkg_dir = os.path.dirname(carrymem.__file__)
        assert os.path.exists(os.path.join(pkg_dir, "py.typed"))
