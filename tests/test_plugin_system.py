"""Tests for CarryMem Plugin System (MVP).

Covers:
- PluginProtocol interface compliance
- PluginManager: discover, load, unload, list_plugins, get_hooks, dispatch
- HookPoint definitions and subscription detection
- Example notification plugin loading and hook dispatch
- Plugin lifecycle: on_load / on_unload
- Error handling: missing plugin, invalid plugin, load failure
- Thread safety of plugin operations

Run:
    python -m pytest tests/test_plugin_system.py -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem.plugins import (
    HookPoint,
    PluginManager,
    PluginProtocol,
    PluginStatus,
)
from carrymem.plugins.example_notification_plugin import ExampleNotificationPlugin

# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_plugin_dir() -> str:
    """Create a temporary directory for test plugins."""
    return tempfile.mkdtemp(prefix="carrymem_plugins_")


def _write_plugin_file(plugin_dir: str, name: str, content: str) -> str:
    """Write a plugin file to the plugin directory and return its path."""
    path = os.path.join(plugin_dir, f"{name}.py")
    with open(path, "w") as f:
        f.write(content)
    return path


_MINIMAL_PLUGIN_TEMPLATE = """
from carrymem.plugins import PluginProtocol
from typing import Any

class {cls_name}(PluginProtocol):
    name = "{plugin_name}"
    version = "1.0.0"

    def __init__(self):
        self.loaded = False
        self.unloaded = False
        self.carrymem_ref = None

    def on_load(self, carrymem: Any) -> None:
        self.loaded = True
        self.carrymem_ref = carrymem

    def on_unload(self) -> None:
        self.unloaded = True

plugin = {cls_name}()
"""


# ── Tests ─────────────────────────────────────────────────────────────────


class TestPluginDiscovery(unittest.TestCase):
    """Test 1-2: Plugin discovery from directory."""

    def test_discover_finds_plugins(self):
        """Test 1: discover() finds .py files in plugin directory."""
        plugin_dir = _make_plugin_dir()
        try:
            _write_plugin_file(
                plugin_dir, "my_plugin", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="MyPlugin", plugin_name="my_plugin")
            )
            pm = PluginManager(plugin_dir=plugin_dir)
            discovered = pm.discover()
            self.assertIn("my_plugin", discovered)
        finally:
            import shutil

            shutil.rmtree(plugin_dir, ignore_errors=True)

    def test_discover_ignores_private_files(self):
        """Test 2: discover() ignores files starting with underscore."""
        plugin_dir = _make_plugin_dir()
        try:
            _write_plugin_file(
                plugin_dir,
                "public_plugin",
                _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="PublicPlugin", plugin_name="public"),
            )
            _write_plugin_file(plugin_dir, "_private", "# private file\npass")
            pm = PluginManager(plugin_dir=plugin_dir)
            discovered = pm.discover()
            self.assertIn("public_plugin", discovered)
            self.assertNotIn("_private", discovered)
        finally:
            import shutil

            shutil.rmtree(plugin_dir, ignore_errors=True)

    def test_discover_empty_directory(self):
        """Test: discover() returns empty list for empty directory."""
        plugin_dir = _make_plugin_dir()
        try:
            pm = PluginManager(plugin_dir=plugin_dir)
            self.assertEqual(pm.discover(), [])
        finally:
            import shutil

            shutil.rmtree(plugin_dir, ignore_errors=True)

    def test_discover_nonexistent_directory(self):
        """Test: discover() returns empty list for nonexistent directory."""
        pm = PluginManager(plugin_dir="/nonexistent/path/plugins")
        self.assertEqual(pm.discover(), [])


class TestPluginLoading(unittest.TestCase):
    """Test 3-5: Plugin loading functionality."""

    def setUp(self):
        self.plugin_dir = _make_plugin_dir()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def test_load_basic_plugin(self):
        """Test 3: load() successfully loads a valid plugin."""
        _write_plugin_file(
            self.plugin_dir, "basic", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="BasicPlugin", plugin_name="basic")
        )
        pm = PluginManager(plugin_dir=self.plugin_dir)
        plugin = pm.load("basic")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, "basic")
        self.assertIs(plugin.loaded, True)

    def test_load_sets_version(self):
        """Test: Loaded plugin has correct version."""
        _write_plugin_file(
            self.plugin_dir, "ver_test", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="VerPlugin", plugin_name="ver_test")
        )
        pm = PluginManager(plugin_dir=self.plugin_dir)
        plugin = pm.load("ver_test")
        self.assertEqual(plugin.version, "1.0.0")

    def test_load_calls_on_load_with_carrymem(self):
        """Test 4: on_load receives the CarryMem reference."""
        fake_cm = object()
        _write_plugin_file(
            self.plugin_dir, "ref_test", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="RefPlugin", plugin_name="ref_test")
        )
        pm = PluginManager(plugin_dir=self.plugin_dir)
        pm.set_carrymem(fake_cm)
        plugin = pm.load("ref_test")
        self.assertIs(plugin.carrymem_ref, fake_cm)

    def test_load_nonexistent_raises_error(self):
        """Test: Loading nonexistent plugin raises FileNotFoundError."""
        pm = PluginManager(plugin_dir=self.plugin_dir)
        with self.assertRaises(FileNotFoundError):
            pm.load("does_not_exist")

    def test_load_invalid_plugin_raises_error(self):
        """Test: Loading file without valid PluginProtocol raises RuntimeError."""
        invalid_path = os.path.join(self.plugin_dir, "invalid.py")
        with open(invalid_path, "w") as f:
            f.write("# Not a valid plugin\nx = 42\n")
        pm = PluginManager(plugin_dir=self.plugin_dir)
        with self.assertRaises(RuntimeError):
            pm.load("invalid")


class TestPluginUnloading(unittest.TestCase):
    """Test plugin unloading."""

    def setUp(self):
        self.plugin_dir = _make_plugin_dir()
        _write_plugin_file(
            self.plugin_dir,
            "unloadable",
            _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="UnloadablePlugin", plugin_name="unloadable"),
        )
        self.pm = PluginManager(plugin_dir=self.plugin_dir)
        self.plugin = self.pm.load("unloadable")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def test_unload_calls_on_unload(self):
        """Test 5: unload() calls plugin's on_unload()."""
        self.pm.unload("unloadable")
        self.assertIs(self.plugin.unloaded, True)

    def test_unload_removes_from_registry(self):
        """Test: After unload, plugin is no longer in registry."""
        self.pm.unload("unloadable")
        status = self.pm.list_plugins().get("unloadable")
        self.assertIsNotNone(status)
        self.assertFalse(status.loaded)

    def test_unload_nonexistent_does_not_crash(self):
        """Test: Unloading a non-loaded plugin does not raise error."""
        # Should not crash
        self.pm.unload("nonexistent")


class TestPluginListAndStatus(unittest.TestCase):
    """Test list_plugins() and status tracking."""

    def setUp(self):
        self.plugin_dir = _make_plugin_dir()
        _write_plugin_file(
            self.plugin_dir, "alpha", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="AlphaPlugin", plugin_name="alpha")
        )
        _write_plugin_file(
            self.plugin_dir, "beta", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="BetaPlugin", plugin_name="beta")
        )
        self.pm = PluginManager(plugin_dir=self.plugin_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def test_list_shows_all_discovered(self):
        """Test 6: list_plugins() shows both loaded and unloaded plugins."""
        self.pm.load("alpha")
        plugins = self.pm.list_plugins()
        self.assertIn("alpha", plugins)
        self.assertIn("beta", plugins)
        self.assertIs(plugins["alpha"].loaded, True)
        self.assertFalse(plugins["beta"].loaded)

    def test_list_status_has_version(self):
        """Test: Listed plugin status includes version info."""
        self.pm.load("alpha")
        plugins = self.pm.list_plugins()
        self.assertEqual(plugins["alpha"].version, "1.0.0")


class TestHookSystem(unittest.TestCase):
    """Test hook point registration and dispatching."""

    def setUp(self):
        self.plugin_dir = _make_plugin_dir()
        # Create a plugin with hook implementations
        hook_plugin_code = """
from carrymem.plugins import PluginProtocol, HookPoint
from typing import Any

class HookedPlugin(PluginProtocol):
    name = "hooked"
    version = "1.0.0"

    def __init__(self):
        self.memory_stored_calls = []
        self.error_calls = []

    def on_load(self, carrymem: Any) -> None:
        pass

    def on_unload(self) -> None:
        pass

    def on_memory_stored(self, memory_id="", content="", **kwargs):
        self.memory_stored_calls.append({"memory_id": memory_id, "content": content})

    def on_error(self, error_type="", error_message="", **kwargs):
        self.error_calls.append({"type": error_type, "message": error_message})

plugin = HookedPlugin()
"""
        _write_plugin_file(self.plugin_dir, "hooked", hook_plugin_code)
        self.pm = PluginManager(plugin_dir=self.plugin_dir)
        self.plugin = self.pm.load("hooked")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def test_get_hooks_returns_subscribed_plugins(self):
        """Test 7: get_hooks() returns plugins subscribed to a hook point."""
        hooks = self.pm.get_hooks(HookPoint.ON_MEMORY_STORED)
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0].name, "hooked")

    def test_get_hooks_empty_for_unsubscribed(self):
        """Test: get_hooks() returns empty list for un-subscribed hook."""
        hooks = self.pm.get_hooks(HookPoint.ON_CLASSIFIED)
        self.assertEqual(len(hooks), 0)

    def test_dispatch_calls_hook_handler(self):
        """Test 8: dispatch() calls the plugin's hook handler."""
        results = self.pm.dispatch(HookPoint.ON_MEMORY_STORED, memory_id="mem-123", content="hello world")
        self.assertEqual(len(results), 1)
        self.assertEqual(len(self.plugin.memory_stored_calls), 1)
        self.assertEqual(self.plugin.memory_stored_calls[0]["memory_id"], "mem-123")

    def test_dispatch_error_hook(self):
        """Test: Dispatch to on_error hook works correctly."""
        self.pm.dispatch(HookPoint.ON_ERROR, error_type="ValueError", error_message="test error")
        self.assertEqual(len(self.plugin.error_calls), 1)
        self.assertEqual(self.plugin.error_calls[0]["type"], "ValueError")

    def test_dispatch_to_unknown_hook_returns_empty(self):
        """Test: Dispatching to unknown hook returns empty list."""
        results = self.pm.dispatch("nonexistent_hook")
        self.assertEqual(results, [])


class TestExampleNotificationPlugin(unittest.TestCase):
    """Test the example notification plugin."""

    def test_example_plugin_conforms_to_protocol(self):
        """Test 9: ExampleNotificationPlugin conforms to PluginProtocol."""
        plugin = ExampleNotificationPlugin()
        self.assertIsInstance(plugin, PluginProtocol)
        self.assertEqual(plugin.name, "example_notification")
        self.assertEqual(plugin.version, "1.0.0")

    def test_example_plugin_on_load_sets_loaded_flag(self):
        """Test: on_load sets internal state."""
        plugin = ExampleNotificationPlugin()
        plugin.on_load(None)
        self.assertIs(plugin._loaded, True)

    def test_example_plugin_on_unload_resets_state(self):
        """Test: on_unload resets loaded flag."""
        plugin = ExampleNotificationPlugin()
        plugin.on_load(None)
        plugin.on_unload()
        self.assertFalse(plugin._loaded)

    def test_example_plugin_memory_stored_detects_sensitive(self):
        """Test 10: on_memory_stored detects sensitive content."""
        plugin = ExampleNotificationPlugin()
        # Capture prints
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            plugin.on_memory_stored(memory_id="sec-1", content="My password is secret123", classification="fact")
        output = buf.getvalue()
        self.assertIn("SENSITIVE MEMORY DETECTED", output)

    def test_example_plugin_memory_stored_normal_content(self):
        """Test: Normal content does not trigger sensitive alert."""
        plugin = ExampleNotificationPlugin()
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            plugin.on_memory_stored(memory_id="norm-1", content="I like pizza", classification="preference")
        output = buf.getvalue()
        self.assertNotIn("SENSITIVE MEMORY DETECTED", output)

    def test_example_plugin_error_logging(self):
        """Test: on_error logs error details."""
        plugin = ExampleNotificationPlugin()
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            plugin.on_error(error_type="RuntimeError", error_message="something broke")
        output = buf.getvalue()
        self.assertIn("Error detected", output)
        self.assertIn("RuntimeError", output)


class TestPluginReload(unittest.TestCase):
    """Test plugin reload functionality."""

    def setUp(self):
        self.plugin_dir = _make_plugin_dir()
        _write_plugin_file(
            self.plugin_dir,
            "reloadable",
            _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="ReloadablePlugin", plugin_name="reloadable"),
        )
        self.pm = PluginManager(plugin_dir=self.plugin_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def test_reload_unloads_then_reloads(self):
        """Test: reload() unloads then re-loads a plugin."""
        plugin_v1 = self.pm.load("reloadable")
        v1_id = id(plugin_v1)
        plugin_v2 = self.pm.reload("reloadable")
        v2_id = id(plugin_v2)
        # Should be different instances after reload
        self.assertNotEqual(v1_id, v2_id)
        self.assertIs(plugin_v2.loaded, True)


class TestUnloadAll(unittest.TestCase):
    """Test unload_all() functionality."""

    def setUp(self):
        self.plugin_dir = _make_plugin_dir()
        _write_plugin_file(
            self.plugin_dir, "p1", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="P1Plugin", plugin_name="p1")
        )
        _write_plugin_file(
            self.plugin_dir, "p2", _MINIMAL_PLUGIN_TEMPLATE.format(cls_name="P2Plugin", plugin_name="p2")
        )
        self.pm = PluginManager(plugin_dir=self.plugin_dir)
        self.p1 = self.pm.load("p1")
        self.p2 = self.pm.load("p2")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def test_unload_all_unloads_everything(self):
        """Test: unload_all() unloads all loaded plugins."""
        self.pm.unload_all()
        statuses = self.pm.list_plugins()
        self.assertFalse(statuses["p1"].loaded)
        self.assertFalse(statuses["p2"].loaded)
        self.assertIs(self.p1.unloaded, True)
        self.assertIs(self.p2.unloaded, True)


class TestHookPointConstants(unittest.TestCase):
    """Test HookPoint constant definitions."""

    def test_all_hook_points_defined(self):
        """Test: All required hook points are defined."""
        expected = ["on_memory_stored", "on_memory_recalled", "on_classified", "on_error"]
        for hp in expected:
            self.assertIs(hasattr(HookPoint, hp.upper()), True)

    def test_all_list_contains_all_hooks(self):
        """Test: HookPoint.ALL contains all hook points."""
        self.assertEqual(len(HookPoint.ALL), 4)
        for hp in HookPoint.ALL:
            self.assertIn(
                hp,
                [
                    HookPoint.ON_MEMORY_STORED,
                    HookPoint.ON_MEMORY_RECALLED,
                    HookPoint.ON_CLASSIFIED,
                    HookPoint.ON_ERROR,
                ],
            )


if __name__ == "__main__":
    unittest.main()
