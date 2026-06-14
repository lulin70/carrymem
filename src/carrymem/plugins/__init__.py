"""CarryMem Plugin System (MVP).

Provides:
- PluginProtocol: Interface that all plugins must implement
- PluginManager: Plugin lifecycle management (discover, load, unload, hooks)
- HookPoint definitions: on_memory_stored, on_memory_recalled, on_classified, on_error
- Example notification plugin demonstrating the plugin API
"""

import importlib
import importlib.util
import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Type, runtime_checkable, TYPE_CHECKING

from carrymem.utils.logger import logger

if TYPE_CHECKING:
    from carrymem import CarryMem


# ── Types ─────────────────────────────────────────────────────────────────


@runtime_checkable
class PluginProtocol(Protocol):
    """Protocol that all CarryMem plugins must implement.

    Every plugin must define at minimum:
    - name: str — unique plugin identifier
    - version: str — semantic version string
    - on_load(carrymem) — called when plugin is loaded
    - on_unload() — called when plugin is unloaded
    """

    name: str
    version: str

    def on_load(self, carrymem: "CarryMem") -> None:
        """Called when the plugin is loaded into CarryMem."""
        ...

    def on_unload(self) -> None:
        """Called when the plugin is unloaded from CarryMem."""
        ...


@dataclass
class PluginStatus:
    """Runtime status of a plugin."""

    name: str
    version: str = ""
    loaded: bool = False
    error: Optional[str] = None
    hook_subscriptions: List[str] = field(default_factory=list)


# ── Hook Points ───────────────────────────────────────────────────────────


class HookPoint:
    """Named hook point constants."""

    ON_MEMORY_STORED = "on_memory_stored"
    ON_MEMORY_RECALLED = "on_memory_recalled"
    ON_CLASSIFIED = "on_classified"
    ON_ERROR = "on_error"

    ALL = [ON_MEMORY_STORED, ON_MEMORY_RECALLED, ON_CLASSIFIED, ON_ERROR]


# ── Plugin Manager ────────────────────────────────────────────────────────


class PluginManager:
    """Plugin lifecycle manager.

    Responsibilities:
    - Discover plugins from a directory
    - Load / unload individual plugins by name
    - Maintain plugin registry and status
    - Dispatch events to subscribed hook handlers
    """

    def __init__(self, plugin_dir: Optional[str] = None):
        self._plugin_dir = plugin_dir
        self._plugins: Dict[str, PluginProtocol] = {}
        self._statuses: Dict[str, PluginStatus] = {}
        self._hooks: Dict[str, List[PluginProtocol]] = {
            hp: [] for hp in HookPoint.ALL
        }
        self._lock = threading.RLock()
        self._carrymem_ref: Optional["CarryMem"] = None

    def set_carrymem(self, carrymem: "CarryMem") -> None:
        """Set the CarryMem instance reference for plugin loading."""
        self._carrymem_ref = carrymem

    def discover(self, plugin_dir: Optional[str] = None) -> List[str]:
        """Discover available plugins in the plugin directory.

        Scans for Python files that look like plugins (not starting with '_').

        Args:
            plugin_dir: Directory to scan. Uses instance default if None.

        Returns:
            List of discovered plugin module names (without .py extension).
        """
        target_dir = Path(plugin_dir or self._plugin_dir or "")
        if not target_dir.is_dir():
            logger.debug("Plugin directory not found: %s", target_dir)
            return []

        discovered: List[str] = []
        for f in sorted(target_dir.iterdir()):
            if f.suffix == ".py" and not f.name.startswith("_"):
                discovered.append(f.stem)

        logger.info("Discovered %d plugins in %s", len(discovered), target_dir)
        return discovered

    def load(self, name: str) -> PluginProtocol:
        """Load a single plugin by name.

        The plugin module is imported from the configured plugin directory.
        After import, ``plugin.on_load(carrymem)`` is called.

        Args:
            name: Plugin module name (without .py extension).

        Returns:
            The loaded plugin instance.

        Raises:
            FileNotFoundError: If plugin file does not exist.
            ImportError: If plugin cannot be imported.
            RuntimeError: If plugin fails to load.
        """
        with self._lock:
            if name in self._plugins:
                return self._plugins[name]

            target_dir = Path(self._plugin_dir or "")
            plugin_path = target_dir / f"{name}.py"

            if not plugin_path.exists():
                raise FileNotFoundError(f"Plugin not found: {plugin_path}")

            # Dynamic import
            spec = importlib.util.spec_from_file_location(name, str(plugin_path))
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create module spec for plugin: {name}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)

            # Find the plugin instance — look for common attribute names
            plugin_instance: Optional[PluginProtocol] = None
            for attr_name in ("plugin", "Plugin", name):
                candidate = getattr(module, attr_name, None)
                if candidate is not None and isinstance(candidate, PluginProtocol):
                    plugin_instance = candidate
                    break

            if plugin_instance is None:
                # Try any class that looks like a plugin
                for attr_name in dir(module):
                    if attr_name.startswith("_"):
                        continue
                    candidate = getattr(module, attr_name)
                    if (
                        isinstance(candidate, type)
                        and hasattr(candidate, "name")
                        and hasattr(candidate, "on_load")
                    ):
                        plugin_instance = candidate()  # instantiate
                        break

            if plugin_instance is None:
                raise RuntimeError(
                    f"Plugin '{name}' does not provide a valid PluginProtocol implementation"
                )

            # Call on_load
            try:
                plugin_instance.on_load(self._carrymem_ref)
            except Exception as e:
                self._statuses[name] = PluginStatus(
                    name=name,
                    version=getattr(plugin_instance, "version", ""),
                    loaded=False,
                    error=str(e),
                )
                raise RuntimeError(f"Plugin '{name}' on_load failed: {e}") from e

            self._plugins[name] = plugin_instance
            self._statuses[name] = PluginStatus(
                name=name,
                version=getattr(plugin_instance, "version", "unknown"),
                loaded=True,
                hook_subscriptions=self._detect_hook_subscriptions(plugin_instance),
            )

            # Auto-register hooks
            self._register_plugin_hooks(plugin_instance)

            logger.info("Plugin loaded: %s v%s", name, plugin_instance.version)
            return plugin_instance

    def unload(self, name: str) -> None:
        """Unload a previously loaded plugin.

        Calls ``plugin.on_unload()``, removes from registry and hooks.

        Args:
            name: Plugin name to unload.
        """
        with self._lock:
            plugin = self._plugins.pop(name, None)
            if plugin is None:
                logger.warning("Plugin '%s' is not loaded, skipping unload", name)
                return

            try:
                plugin.on_unload()
            except Exception as e:
                logger.error("Plugin '%s' on_unload error: %s", name, e)

            # Remove from hooks
            for hook_name in self._hooks:
                self._hooks[hook_name] = [
                    p for p in self._hooks[hook_name] if p is not plugin
                ]

            self._statuses[name] = PluginStatus(
                name=name,
                version=plugin.version,
                loaded=False,
            )

            # Clean up sys.modules
            sys.modules.pop(name, None)

            logger.info("Plugin unloaded: %s", name)

    def list_plugins(self) -> Dict[str, PluginStatus]:
        """Return status of all known plugins (loaded + discovered but not loaded)."""
        with self._lock:
            result: Dict[str, PluginStatus] = {}
            # Add loaded/unloaded statuses we know about
            for name, status in self._statuses.items():
                result[name] = status
            # Discover new ones not yet tracked
            discovered = self.discover()
            for name in discovered:
                if name not in result:
                    result[name] = PluginStatus(name=name, loaded=False)
            return result

    def get_hooks(self, hook_name: str) -> List[PluginProtocol]:
        """Get all plugins subscribed to a specific hook point.

        Args:
            hook_name: One of HookPoint.ALL values.

        Returns:
            List of plugin instances that handle this hook.
        """
        if hook_name not in self._hooks:
            logger.warning("Unknown hook point: %s", hook_name)
            return []
        return list(self._hooks[hook_name])

    def dispatch(self, hook_name: str, **kwargs: object) -> List[Optional[object]]:
        """Dispatch an event to all plugins subscribed to a hook.

        Args:
            hook_name: Hook point name.
            **kwargs: Event data passed to each handler.

        Returns:
            List of results from each plugin handler.
        """
        results: List[Optional[object]] = []
        for plugin in self.get_hooks(hook_name):
            handler = getattr(plugin, hook_name, None)
            if callable(handler):
                try:
                    result = handler(**kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error("Error in plugin '%s' "
                                 "handler '%s': %s", getattr(plugin, 'name', '?'), hook_name, e)
        return results

    def _detect_hook_subscriptions(self, plugin: PluginProtocol) -> List[str]:
        """Detect which hook points a plugin has implemented."""
        subscriptions: List[str] = []
        for hook_name in HookPoint.ALL:
            if hasattr(plugin, hook_name) and callable(getattr(plugin, hook_name)):
                subscriptions.append(hook_name)
        return subscriptions

    def _register_plugin_hooks(self, plugin: PluginProtocol) -> None:
        """Register a plugin's hook handlers into the dispatch table."""
        for hook_name in self._detect_hook_subscriptions(plugin):
            if plugin not in self._hooks[hook_name]:
                self._hooks[hook_name].append(plugin)

    def reload(self, name: str) -> PluginProtocol:
        """Reload a plugin (unload then re-load)."""
        self.unload(name)
        return self.load(name)

    def unload_all(self) -> None:
        """Unload all currently loaded plugins."""
        for name in list(self._plugins.keys()):
            self.unload(name)


__all__ = [
    # Protocol interface
    "PluginProtocol",
    # Data classes
    "PluginStatus",
    # Hook points
    "HookPoint",
    # Manager
    "PluginManager",
]
