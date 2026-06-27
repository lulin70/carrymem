"""Adapter loader — dynamically load third-party storage adapters via entry_points."""

import importlib
from typing import Optional, Type

from carrymem.adapters.base import StorageAdapter

_BUILTIN_ADAPTERS = {
    "sqlite": "carrymem.adapters.sqlite_adapter.SQLiteAdapter",
    "obsidian": "carrymem.adapters.obsidian_adapter.ObsidianAdapter",
    "json": "carrymem.adapters.json_adapter.JSONAdapter",
}


def load_adapter(name: str) -> Optional[Type[StorageAdapter]]:
    """Load a storage adapter class by name from built-ins or installed plugins."""
    if name in _BUILTIN_ADAPTERS:
        module_path, _, class_name = _BUILTIN_ADAPTERS[name].rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)  # type: ignore[no-any-return]

    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            adapter_eps = eps.select(group="carrymem.adapters", name=name)
        else:
            adapter_eps = eps.get("carrymem.adapters", [])  # type: ignore[arg-type]
            adapter_eps = [ep for ep in adapter_eps if ep.name == name]  # type: ignore[assignment]

        for ep in adapter_eps:
            return ep.load()  # type: ignore[no-any-return]
    except (ImportError, AttributeError, OSError):
        pass

    if "." in name:
        try:
            module_path, _, class_name = name.rpartition(".")
            module = importlib.import_module(module_path)
            return getattr(module, class_name)  # type: ignore[no-any-return]
        except (ImportError, AttributeError):
            pass

    return None


def list_available_adapters() -> dict:
    """Return mapping of available adapter names to their import paths."""
    result = dict(_BUILTIN_ADAPTERS)

    try:
        from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            adapter_eps = eps.select(group="carrymem.adapters")
        else:
            adapter_eps = eps.get("carrymem.adapters", [])  # type: ignore[arg-type]
        for ep in adapter_eps:
            result[ep.name] = f"{ep.value} (plugin)"
    except (ImportError, AttributeError):
        pass

    return result
