"""Adapter loader — dynamically load third-party storage adapters via entry_points."""
import importlib
from typing import Optional, Type

from memory_classification_engine.adapters.base import StorageAdapter

_BUILTIN_ADAPTERS = {
    "sqlite": "memory_classification_engine.adapters.sqlite_adapter.SQLiteAdapter",
    "obsidian": "memory_classification_engine.adapters.obsidian_adapter.ObsidianAdapter",
    "json": "memory_classification_engine.adapters.json_adapter.JSONAdapter",
}


def load_adapter(name: str) -> Optional[Type[StorageAdapter]]:
    if name in _BUILTIN_ADAPTERS:
        module_path, _, class_name = _BUILTIN_ADAPTERS[name].rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    try:
        from importlib.metadata import entry_points
        eps = entry_points()
        if hasattr(eps, 'select'):
            adapter_eps = eps.select(group='carrymem.adapters', name=name)
        else:
            adapter_eps = eps.get('carrymem.adapters', [])
            adapter_eps = [ep for ep in adapter_eps if ep.name == name]

        for ep in adapter_eps:
            return ep.load()
    except Exception:
        pass

    if "." in name:
        try:
            module_path, _, class_name = name.rpartition(".")
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError):
            pass

    return None


def list_available_adapters() -> dict:
    result = dict(_BUILTIN_ADAPTERS)

    try:
        from importlib.metadata import entry_points
        eps = entry_points()
        if hasattr(eps, 'select'):
            adapter_eps = eps.select(group='carrymem.adapters')
        else:
            adapter_eps = eps.get('carrymem.adapters', [])

        for ep in adapter_eps:
            result[ep.name] = f"{ep.value} (plugin)"
    except Exception:
        pass

    return result
