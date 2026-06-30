"""CarryMem CLI - Shared infrastructure: constants, color functions, utilities, factories."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

__all__ = [
    # Logger & validator
    "_cli_logger",
    "_cli_validator",
    # i18n
    "_t",
    # Defaults
    "_DEFAULT_DB",
    "_DEFAULT_CONFIG_DIR",
    # Constants
    "_TYPE_ICONS",
    "_TIER_LABELS",
    "_HAS_COLOR",
    # Color functions
    "_c",
    "_green",
    "_red",
    "_yellow",
    "_cyan",
    "_dim",
    "_bold",
    # Utility functions
    "_get_carrymem",
    "_format_time",
    "_truncate",
    "_find_memory",
    "_print_memory_card",
    # Factory functions
    "_make_parser",
    "_get_rule_engine",
    "_validate_cli_path",
    # Re-exported from carrymem
    "CarryMem",
    "__version__",
    "DEFAULT_CONFIG_DIR",
    "DB_PATH",
    "DANGEROUS_SYSTEM_DIRS",
]

_cli_logger = logging.getLogger(__name__)

try:
    from carrymem import CarryMem
    from carrymem.__version__ import __version__
    from carrymem.constants import (
        DANGEROUS_SYSTEM_DIRS,
        DB_PATH,
        DEFAULT_CONFIG_DIR,
    )
except ImportError:
    print("Error: CarryMem not properly installed")
    print("Try: pip install -e .")
    sys.exit(1)

_cli_validator: Optional[InputValidator] = None
try:
    from carrymem.security.input_validator import InputValidator

    _cli_validator = InputValidator(strict_mode=False)
except ImportError:
    import logging

    logging.getLogger(__name__).warning("InputValidator not available — input validation disabled")

# ── i18n initialization ──────────────────────────────────────────
from carrymem.i18n import I18nManager

_cli_i18n = I18nManager()

# Read locale from CARRYMEM_LANG env var (e.g. "zh-CN" or "zh_CN")
_cli_lang = os.environ.get("CARRYMEM_LANG", "").replace("_", "-")
if _cli_lang and _cli_lang in I18nManager.available_locales():
    I18nManager.set_locale(_cli_lang)

_t = I18nManager.t


_DEFAULT_DB = DB_PATH
_DEFAULT_CONFIG_DIR = DEFAULT_CONFIG_DIR

_TYPE_ICONS = {
    "user_preference": "\u2b50",
    "fact_declaration": "\U0001f4cc",
    "correction": "\U0001f527",
    "decision": "\U0001f3af",
    "task_pattern": "\U0001f504",
    "contextual_observation": "\U0001f441",
    "knowledge": "\U0001f4da",
    "unknown": "\u2753",
}

_TIER_LABELS = {1: "Core", 2: "Standard", 3: "Background", 4: "Archive"}

_HAS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _HAS_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(t):
    return _c("32", t)


def _red(t):
    return _c("31", t)


def _yellow(t):
    return _c("33", t)


def _cyan(t):
    return _c("36", t)


def _dim(t):
    return _c("2", t)


def _bold(t):
    return _c("1", t)


def _get_carrymem(db_path: Optional[str] = None, namespace: str = "default") -> CarryMem:
    path = db_path or str(_DEFAULT_DB)
    return CarryMem(db_path=path, namespace=namespace)


def _format_time(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "N/A"
    try:
        from datetime import datetime

        if isinstance(iso_str, str):
            dt = datetime.fromisoformat(iso_str)
            now = datetime.now(dt.tzinfo)
            delta = now - dt
            if delta.days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    return f"{minutes}m ago"
                return f"{hours}h ago"
            elif delta.days == 1:
                return "yesterday"
            elif delta.days < 30:
                return f"{delta.days}d ago"
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError) as e:
        _cli_logger.debug("Failed to format time '%s': %s", iso_str, e)
    return str(iso_str)[:16]


def _truncate(text: str, max_len: int = 60) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _find_memory(cm: CarryMem, key: str) -> Optional[Dict[str, Any]]:
    if cm._adapter and hasattr(cm._adapter, "_get_by_key"):
        stored = cm._adapter._get_by_key(key)
        if stored:
            return stored.to_dict()  # type: ignore[no-any-return]
    memories = cm.recall_memories(query="", limit=200)
    for m in memories:
        if m.get("storage_key") == key:
            return m
    return None


def _print_memory_card(m: Dict[str, Any], index: Optional[int] = None):
    mtype = m.get("type", "unknown")
    icon = _TYPE_ICONS.get(mtype, "\u2753")
    content = m.get("content", "")
    confidence = m.get("confidence", 0)
    importance = m.get("importance_score", 0)
    key = m.get("storage_key", "")
    created = m.get("created_at", "")
    tier = m.get("tier", 2)
    tier_label = _TIER_LABELS.get(tier, f"T{tier}")

    prefix = f"  {index}." if index else "  "
    print(f"{prefix} {icon} {_bold(_truncate(content, 65))}")
    print(f"     {_dim(f'Type: {mtype} | Conf: {confidence:.0%} | Importance: {importance:.2f} | {tier_label}')}")
    print(f"     {_dim(f'Key: {key} | {_format_time(created)}')}")


def _make_parser(cmd_name: str):
    import argparse

    return argparse.ArgumentParser(
        prog=f"carrymem {cmd_name}",
        description=f"CarryMem {cmd_name} command",
    )


def _get_rule_engine(db_path: Optional[str] = None):
    from carrymem.rules import RuleEngine

    path = db_path or str(_DEFAULT_DB)
    return RuleEngine(path)


def _validate_cli_path(path: str) -> str:
    resolved = os.path.realpath(os.path.expanduser(path))
    for d in DANGEROUS_SYSTEM_DIRS:
        if resolved == str(d) or resolved.startswith(str(d) + os.sep):
            raise ValueError(f"Path traversal: system directory not allowed: {resolved}")
    return resolved
