"""CarryMem CLI - Stats/identity/diagnostic commands: stats, whoami, profile, check, doctor."""

import json
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from carrymem.cli._base import (
    _DEFAULT_CONFIG_DIR,
    _DEFAULT_DB,
    _TIER_LABELS,
    _TYPE_ICONS,
    CarryMem,
    __version__,
    _add_common_args,
    _bold,
    _cli_logger,
    _cyan,
    _dim,
    _format_time,
    _get_carrymem,
    _green,
    _make_parser,
    _red,
    _t,
    _truncate,
    _yellow,
)


def _show_value_report(cm, parsed) -> int:
    """Display the value perception report (--value flag)."""
    from datetime import datetime, timezone

    stats = cm.get_stats()
    profile = cm.get_memory_profile()
    total_memories = stats.get("total_count", 0)
    by_type = stats.get("by_type", {})
    highlights = profile.get("highlights", {})

    # Rules active
    rule_count = 0
    if hasattr(cm, "rules") and cm.rules:
        try:
            rule_count = cm.rules.count_rules()
        except (AttributeError, sqlite3.OperationalError):
            pass

    # Sessions remembered
    session_count = by_type.get("session_summary", 0)

    # Identity coverage: how many highlight types have entries
    identity_types = ["user_preference", "correction", "decision", "fact_declaration"]
    covered = sum(1 for t in identity_types if highlights.get(t))
    identity_coverage = (covered / len(identity_types) * 100) if identity_types else 0

    # Days since first use
    days_since_first = 0
    adapter = cm._adapter if hasattr(cm, "_adapter") else None
    if adapter and hasattr(adapter, "_db_path") and adapter._db_path != ":memory:":
        try:
            import sqlite3

            conn = sqlite3.connect(adapter._db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT MIN(created_at) FROM memories WHERE namespace = ?",
                (adapter._namespace,),
            ).fetchone()
            conn.close()
            if row and row[0]:
                first_date = datetime.fromisoformat(row[0])
                days_since_first = (datetime.now(timezone.utc) - first_date.replace(tzinfo=timezone.utc)).days
        except (ValueError, sqlite3.OperationalError):
            pass

    # Estimates (heuristics)
    repetitions_avoided = max(0, total_memories // 3)  # ~1/3 might be duplicates without consolidation
    tokens_per_memory_avg = 50  # avg tokens per memory when injected into prompt
    tokens_saved_est = total_memories * tokens_per_memory_avg * 2  # each memory used ~2x on average

    value_data = {
        "memories_stored": total_memories,
        "rules_active": rule_count,
        "sessions_remembered": session_count,
        "repetitions_avoided": f"~{repetitions_avoided}",
        "tokens_saved_est": f"~{tokens_saved_est:,}",
        "identity_coverage": f"{identity_coverage:.0f}%",
        "days_since_first": days_since_first,
    }

    if parsed.format == "json":
        print(json.dumps(value_data, ensure_ascii=False, indent=2))
        return 0

    # Text output with box-drawing characters
    w = 41  # box width
    top = f"\n  {'\u250c'}{'\u2500' * w}{'\u2510'}"
    mid = f"  {'\u251c'}{'\u2500' * w}{'\u2524'}"
    bot = f"  {'\u2514'}{'\u2500' * w}{'\u2518'}"

    def row(label, value):  # type: ignore[no-redef]
        """Format a labeled value row for the value report box."""
        return f"  \u2502 {label.ljust(32)}{_bold(str(value)).rjust(6)} \u2502"

    print(top)
    print(f"  \u2502 {_bold('CarryMem Value Report').center(w)} \u2502")
    print(mid)
    print(row("Memories Stored:", total_memories))
    print(row("Rules Active:", rule_count))
    print(row("Sessions Remembered:", session_count))
    print(row("Repetitions Avoided:", f"~{repetitions_avoided}"))
    print(row("Tokens Saved (est.):", f"~{tokens_saved_est:,}"))
    print(row("Identity Coverage:", f"{identity_coverage:.0f}%"))
    print(row("Days Since First Use:", days_since_first))
    print(bot)
    print()
    return 0


def cmd_stats(args):
    """Print memory statistics and optional value report."""
    parser = _make_parser("stats")
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    _add_common_args(parser)
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help=_t("cli.arg.format"),
    )
    parser.add_argument("--value", "-v", action="store_true", help=_t("cli.arg.value_report"))

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    if parsed.value:
        result = _show_value_report(cm, parsed)
        cm.close()
        return result

    stats = cm.get_stats()
    profile = cm.get_memory_profile()

    if parsed.format == "json":
        combined = {"stats": stats, "profile": profile}
        print(json.dumps(combined, ensure_ascii=False, indent=2))
        cm.close()
        return 0

    total = stats.get("total_count", 0)
    by_type = stats.get("by_type", {})

    print(f"\n  {_bold('CarryMem Statistics')} (namespace: {parsed.namespace})")
    print(f"  {'=' * 45}")
    print(f"\n  Total Memories: {_bold(str(total))}")

    if by_type:
        print("\n  By Type:")
        max_type_len = max(len(t) for t in by_type) if by_type else 10
        for mtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            icon = _TYPE_ICONS.get(mtype, "  ")
            bar = "\u2588" * min(count, 30)
            pct = (count / total * 100) if total > 0 else 0
            print(f"    {icon} {mtype.ljust(max_type_len)}  {count:4d}  {_cyan(bar)}  ({pct:.0f}%)")

    profile_stats = profile.get("stats", {})
    by_tier = profile_stats.get("by_tier", {})
    if by_tier:
        print("\n  By Tier:")
        for tier_num in sorted(by_tier.keys()):
            count = by_tier[tier_num]
            label = _TIER_LABELS.get(tier_num, f"T{tier_num}")  # type: ignore[call-overload]
            print(f"    Tier {tier_num} ({label}): {count}")

    conf_avg = profile_stats.get("confidence_avg", 0)
    if conf_avg:
        print(f"\n  Avg Confidence: {conf_avg:.2f}")

    db_path = stats.get("db_path", "")
    if db_path and db_path != ":memory:":
        p = Path(db_path)  # type: ignore[arg-type]
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  Database Size: {size_mb:.2f} MB")
            print(f"  Database Path: {_dim(db_path)}")

    print()
    cm.close()
    return 0


def cmd_whoami(args):
    """Print the user identity summary derived from stored memories."""
    parser = _make_parser("whoami")
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    _add_common_args(parser)
    parser.add_argument("--json", action="store_true", help=_t("cli.arg.json"))

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    identity = cm.whoami()

    if parsed.json:
        print(json.dumps(identity, ensure_ascii=False, indent=2))
        cm.close()
        return 0

    user_type = identity.get("identity", "unknown")
    summary = identity.get("summary", "")
    total = identity.get("total_memories", 0)

    if user_type == "new_user":
        dont_know = "I don't know you yet."
        print(f"\n  {_dim(dont_know)}")
        print(f"  {_dim('Start by telling me about yourself:')}")
        print('    carrymem add "I prefer dark mode"')
        print('    carrymem add "I use Python for data analysis"')
        print()
        cm.close()
        return 0

    print(f"\n  {_bold('Who You Are (according to your AI)')}")
    print(f"  {'=' * 50}")
    print(f"\n  {_cyan(summary)}")

    preferences = identity.get("preferences", [])
    if preferences:
        print(f"\n  {_bold('Your Preferences:')}")
        for p in preferences:
            pref_icon = _TYPE_ICONS.get("user_preference", "*")
            print(f"    {_green(pref_icon)} {p}")

    decisions = identity.get("decisions", [])
    if decisions:
        print(f"\n  {_bold('Your Decisions:')}")
        for d in decisions:
            dec_icon = _TYPE_ICONS.get("decision", "*")
            print(f"    {_cyan(dec_icon)} {d}")

    corrections = identity.get("corrections", [])
    if corrections:
        print(f"\n  {_bold('Your Corrections:')}")
        for c in corrections:
            cor_icon = _TYPE_ICONS.get("correction", "*")
            print(f"    {_yellow(cor_icon)} {c}")

    by_type = identity.get("by_type", {})
    if by_type:
        print(f"\n  {_bold('Memory Profile:')}")
        top = identity.get("top_type", "")
        conf = identity.get("confidence_avg", 0)
        print(f"    Total: {total} | Dominant: {top} | Avg Confidence: {conf:.0%}")

    print(f"\n  {_dim('Export your identity: carrymem profile export identity.json')}")
    print()
    cm.close()
    return 0


def cmd_profile(args):
    """Show or export the user memory profile."""
    parser = _make_parser("profile")
    parser.add_argument(
        "action",
        choices=["export", "show"],
        default="show",
        nargs="?",
        help=_t("cli.arg.profile_action"),
    )
    parser.add_argument("--output", "-o", help=_t("cli.arg.output"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    _add_common_args(parser)

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    if parsed.action == "export":
        output = parsed.output or "carrymem_profile.json"
        result = cm.export_profile(output_path=output)
        pref_count = len(result.get("preferences", []))
        dec_count = len(result.get("decisions", []))
        print(f"  {_green('Profile exported to')} {_cyan(output)}")
        print(f"  {_dim(f'{pref_count} preferences, {dec_count} decisions')}")
    else:
        identity = cm.whoami()
        print(json.dumps(identity, ensure_ascii=False, indent=2))

    cm.close()
    return 0


def _print_conflicts_check(cm) -> None:
    """Print conflict detection results for cmd_check."""
    print("  Conflicts:")
    try:
        conflicts = cm.check_conflicts()
        if not conflicts:
            print(f"    {_green('No conflicts detected')}")
        else:
            for c in conflicts:
                ctype = c.get("conflict_type", "unknown")
                severity = c.get("severity", "unknown")
                reason = c.get("reason", "")
                keys = c.get("memory_keys", [])
                sev_color = _red if severity == "high" else _yellow
                print(f"    {sev_color(f'[{severity.upper()}]')} {ctype}: {reason}")
                for key in keys:
                    print(f"      {_dim(f'- {key}')}")
    except (KeyError, ValueError, TypeError) as e:
        print(f"    {_red(f'Error: {e}')}")
    print()


def _print_quality_check(cm) -> None:
    """Print low-quality memory results for cmd_check."""
    print("  Low Quality Memories:")
    try:
        low_quality = cm.check_quality(min_score=0.3)
        if not low_quality:
            print(f"    {_green('All memories have good quality')}")
        else:
            for item in low_quality:
                key = item.get("storage_key", "")
                score = item.get("score", 0)
                reasons = item.get("reasons", [])
                content = item.get("content", "")
                print(f"    {_yellow(f'Score: {score:.3f}')} | {_truncate(content, 50)}")
                reasons_str = ", ".join(reasons)
                print(f"      {_dim(f'Key: {key} | Reasons: {reasons_str}')}")
    except (KeyError, ValueError, TypeError) as e:
        print(f"    {_red(f'Error: {e}')}")
    print()


def _print_expired_check(cm) -> None:
    """Print expired memory results for cmd_check."""
    print("  Expired Memories:")
    try:
        expired = cm.list_expired()
        if not expired:
            print(f"    {_green('No expired memories')}")
        else:
            for item in expired:
                key = item.get("storage_key", "")
                content = item.get("content", "")
                expires = item.get("expires_at", "")
                print(f"    {_yellow('[EXPIRED]')} {_truncate(content, 50)}")
                print(f"      {_dim(f'Key: {key} | Expired: {expires}')}")
    except (KeyError, ValueError, TypeError) as e:
        print(f"    {_red(f'Error: {e}')}")
    print()


def cmd_check(args):
    """Run quality checks for conflicts, low-quality, and expired memories."""
    parser = _make_parser("check")
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    _add_common_args(parser)
    parser.add_argument("--conflicts", action="store_true", help=_t("cli.arg.check_conflicts"))
    parser.add_argument("--quality", action="store_true", help=_t("cli.arg.check_quality"))
    parser.add_argument("--expired", action="store_true", help=_t("cli.arg.check_expired"))
    parser.add_argument("--all", action="store_true", help=_t("cli.arg.check_all"))

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    run_all = parsed.all or (not parsed.conflicts and not parsed.quality and not parsed.expired)

    print(f"\n  {_bold('CarryMem Quality Check')} (namespace: {parsed.namespace})")
    print(f"  {'=' * 45}\n")

    if run_all or parsed.conflicts:
        _print_conflicts_check(cm)
    if run_all or parsed.quality:
        _print_quality_check(cm)
    if run_all or parsed.expired:
        _print_expired_check(cm)

    cm.close()
    return 0


# ── Doctor diagnostics (TD-005: split F=62 cmd_doctor into per-check fns) ─


@dataclass
class _DoctorCheck:
    """Single doctor diagnostic check result."""

    name: str
    status: str  # ok | fail | warn | info | skip
    message: str
    detail: Optional[Dict[str, Any]] = None


@dataclass
class _DoctorContext:
    """Shared state for doctor check functions."""

    db_path: str
    fix: bool
    db: Path


def _check_python_version(ctx: _DoctorContext) -> _DoctorCheck:
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 12):
        return _DoctorCheck("python_version", "ok", f"Python {py_str} (>= 3.12)")
    return _DoctorCheck("python_version", "fail", f"Python {py_str} (need >= 3.12)")


def _check_carrymem_import(ctx: _DoctorContext) -> _DoctorCheck:
    try:
        from carrymem import CarryMem  # noqa: F401

        return _DoctorCheck("carrymem_import", "ok", f"CarryMem v{__version__}")
    except ImportError as e:
        return _DoctorCheck("carrymem_import", "fail", f"CarryMem import: {e}")


def _check_config_dir(ctx: _DoctorContext) -> _DoctorCheck:
    if _DEFAULT_CONFIG_DIR.exists():
        return _DoctorCheck("config_dir", "ok", f"Config directory: {_DEFAULT_CONFIG_DIR}")
    if ctx.fix:
        _DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return _DoctorCheck("config_dir", "warn", f"Config directory missing: {_DEFAULT_CONFIG_DIR}")


def _check_database_file(ctx: _DoctorContext) -> _DoctorCheck:
    if ctx.db.exists():
        size_mb = ctx.db.stat().st_size / (1024 * 1024)
        return _DoctorCheck(
            "database_file",
            "ok",
            f"Database: {ctx.db} ({size_mb:.2f} MB)",
            {"size_mb": round(size_mb, 2)},
        )
    if ctx.fix:
        try:
            cm = CarryMem(db_path=ctx.db_path)
            cm.close()
        except (sqlite3.OperationalError, OSError) as e:
            _cli_logger.debug("Doctor: failed to create database: %s", e)
    return _DoctorCheck("database_file", "warn", f"Database not found: {ctx.db}")


def _check_db_integrity(ctx: _DoctorContext) -> _DoctorCheck:
    if not ctx.db.exists():
        return _DoctorCheck("db_integrity", "skip", "Database integrity (no database)")
    try:
        conn = sqlite3.connect(str(ctx.db))
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if result[0] == "ok":
            return _DoctorCheck("db_integrity", "ok", "Database integrity: OK")
        return _DoctorCheck("db_integrity", "fail", f"Database integrity: {result[0]}")
    except sqlite3.Error as e:
        return _DoctorCheck("db_integrity", "fail", f"Database check error: {e}")


def _check_db_permissions(ctx: _DoctorContext) -> _DoctorCheck:
    if not ctx.db.exists():
        return _DoctorCheck("db_permissions", "skip", "Database permissions (no database)")
    if os.access(str(ctx.db), os.W_OK):
        return _DoctorCheck("db_permissions", "ok", "Database file writable")
    return _DoctorCheck("db_permissions", "fail", "Database file not writable")


def _check_disk_space(ctx: _DoctorContext) -> _DoctorCheck:
    try:
        disk_usage = shutil.disk_usage(str(ctx.db.parent) if ctx.db.exists() else str(Path.home()))
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 0.1:
            return _DoctorCheck(
                "disk_space",
                "fail",
                f"Disk space critically low: {free_gb:.2f} GB free",
            )
        if free_gb < 1.0:
            return _DoctorCheck("disk_space", "warn", f"Disk space low: {free_gb:.2f} GB free")
        return _DoctorCheck(
            "disk_space",
            "ok",
            f"Disk space: {free_gb:.2f} GB free",
            {"free_gb": round(free_gb, 2)},
        )
    except OSError as e:
        return _DoctorCheck("disk_space", "skip", f"Disk space check unavailable: {e}")


def _check_db_lock(ctx: _DoctorContext) -> _DoctorCheck:
    if not ctx.db.exists():
        return _DoctorCheck("db_lock", "skip", "Database lock (no database)")
    try:
        test_conn = sqlite3.connect(str(ctx.db), timeout=1)
        test_conn.execute("BEGIN IMMEDIATE")
        test_conn.execute("ROLLBACK")
        test_conn.close()
        return _DoctorCheck("db_lock", "ok", "Database not locked")
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            return _DoctorCheck("db_lock", "warn", "Database may be locked by another process")
        return _DoctorCheck("db_lock", "ok", "Database accessible")
    except (OSError, ValueError, TypeError) as e:
        return _DoctorCheck("db_lock", "skip", f"Database lock check: {e}")


def _check_write_permissions(ctx: _DoctorContext) -> _DoctorCheck:
    try:
        test_file = _DEFAULT_CONFIG_DIR / ".doctor_test"
        test_file.touch()
        test_file.unlink()
        return _DoctorCheck("write_permissions", "ok", "Write permissions OK")
    except OSError as e:
        return _DoctorCheck("write_permissions", "fail", f"Write permissions: {e}")


def _check_optional_deps(ctx: _DoctorContext) -> _DoctorCheck:
    optional_deps: List[str] = []
    try:
        import pycld2  # noqa: F401

        optional_deps.append("pycld2")
    except ImportError:
        pass
    try:
        from cryptography.fernet import Fernet  # noqa: F401

        optional_deps.append("cryptography")
    except ImportError:
        pass
    try:
        import langdetect  # noqa: F401

        optional_deps.append("langdetect")
    except ImportError:
        pass
    try:
        import textual  # noqa: F401

        optional_deps.append("textual")
    except ImportError:
        pass
    return _DoctorCheck(
        "optional_deps",
        "ok" if optional_deps else "info",
        f"Optional deps: {', '.join(optional_deps)}" if optional_deps else "No optional deps",
    )


def _check_fts5(ctx: _DoctorContext) -> _DoctorCheck:
    try:
        test_conn = sqlite3.connect(":memory:")
        test_conn.execute("CREATE VIRTUAL TABLE t USING fts5(c)")
        test_conn.close()
        return _DoctorCheck("fts5", "ok", "SQLite FTS5 support")
    except sqlite3.OperationalError as e:
        _cli_logger.debug("FTS5 check failed: %s", e)
        return _DoctorCheck("fts5", "fail", "SQLite FTS5 not available")


def _check_security(ctx: _DoctorContext) -> _DoctorCheck:
    try:
        from carrymem.security import InputValidator

        validator = InputValidator()
        test_result = validator.validate_content("test content")
        if test_result:
            return _DoctorCheck("security", "ok", "Security module (InputValidator)")
        return _DoctorCheck("security", "warn", "Security module: validation returned empty")
    except ImportError:
        return _DoctorCheck("security", "info", "Security module not available")
    except (ValueError, TypeError, RuntimeError) as e:
        return _DoctorCheck("security", "warn", f"Security module: {e}")


def _check_mcp_configs(ctx: _DoctorContext) -> _DoctorCheck:
    mcp_configs: List[str] = []
    cwd = Path.cwd()
    claude_mcp = cwd / ".claude" / "mcp.json"
    cursor_mcp = cwd / ".cursor" / "mcp.json"
    if claude_mcp.exists():
        mcp_configs.append(f"claude-code ({claude_mcp})")
    if cursor_mcp.exists():
        mcp_configs.append(f"cursor ({cursor_mcp})")
    return _DoctorCheck(
        "mcp_configs",
        "ok" if mcp_configs else "info",
        (f"MCP configs: {', '.join(mcp_configs)}" if mcp_configs else "No MCP configs in current directory"),
    )


def _check_memory_count(ctx: _DoctorContext) -> _DoctorCheck:
    if not ctx.db.exists():
        return _DoctorCheck("memory_count", "skip", "Memory count (no database)")
    try:
        cm = CarryMem(db_path=ctx.db_path)
        stats = cm.get_stats()
        total = stats.get("total_count", 0)
        cm.close()
        return _DoctorCheck("memory_count", "ok", f"Memory count: {total}", {"total_count": total})
    except (sqlite3.OperationalError, KeyError, ValueError):
        return _DoctorCheck("memory_count", "warn", "Cannot read memory count")


def _check_rules_engine(ctx: _DoctorContext) -> _DoctorCheck:
    if not ctx.db.exists():
        return _DoctorCheck("rules_engine", "skip", "Rules engine (no database)")
    try:
        from carrymem.rules import RuleEngine

        re = RuleEngine(db_path=ctx.db_path)
        rules = re.list_rules(status="active")
        expired = sum(1 for r in rules if r.is_expired())
        msg = f"Active rules: {len(rules)}"
        if expired:
            msg += f" ({expired} expired)"
        return _DoctorCheck(
            "rules_engine",
            "ok" if not expired else "warn",
            msg,
            {"active": len(rules), "expired": expired},
        )
    except (ImportError, sqlite3.OperationalError, KeyError, ValueError) as e:
        return _DoctorCheck("rules_engine", "warn", f"Rules engine: {e}")


def _check_auto_inject(ctx: _DoctorContext) -> _DoctorCheck:
    auto_inject = os.environ.get("CARRYMEM_AUTO_INJECT", "").lower() in (
        "true",
        "1",
        "yes",
    )
    return _DoctorCheck(
        "auto_inject",
        "ok" if auto_inject else "info",
        f"Auto-inject: {'enabled' if auto_inject else 'disabled (set CARRYMEM_AUTO_INJECT=true)'}",
    )


def _check_cli_path(ctx: _DoctorContext) -> _DoctorCheck:
    if shutil.which("carrymem") is not None:
        return _DoctorCheck("cli_path", "ok", "CLI command 'carrymem' is on PATH")
    py_ver_str = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.platform == "darwin":
        path_hint = f'export PATH="$HOME/Library/Python/{py_ver_str}/bin:$PATH"'
    elif sys.platform.startswith("linux"):
        path_hint = 'export PATH="$HOME/.local/bin:$PATH"'
    else:
        path_hint = "Add Python Scripts directory to your PATH"
    return _DoctorCheck(
        "cli_path",
        "warn",
        f"CLI command 'carrymem' NOT on PATH. Fix: {path_hint}",
        {"fix": path_hint},
    )


def _check_backup(ctx: _DoctorContext) -> _DoctorCheck:
    if not ctx.db.exists():
        return _DoctorCheck("backup", "skip", "Backup status (no database)")
    try:
        from carrymem.backup import BackupManager

        manager = BackupManager(str(ctx.db))
        status = manager.get_status()
        backup_dir_exists = status["backup_dir_exists"]
        backup_count = status["backup_count"]
        latest_backup = status["latest_backup"]

        if not backup_dir_exists:
            return _DoctorCheck("backup", "warn", "Backup directory does not exist")
        if backup_count == 0:
            return _DoctorCheck("backup", "warn", "No backups found — data loss risk")
        latest_str = _format_time(latest_backup) if latest_backup else "N/A"
        return _DoctorCheck(
            "backup",
            "ok",
            f"Backups: {backup_count} file(s), latest: {latest_str}",
            {"count": backup_count, "latest": latest_backup},
        )
    except (OSError, ValueError) as e:
        return _DoctorCheck("backup", "warn", f"Backup check: {e}")


# Order is a characterization contract — see tests/test_cli_doctor.py
_DOCTOR_CHECKS: List[Callable[[_DoctorContext], _DoctorCheck]] = [
    _check_python_version,
    _check_carrymem_import,
    _check_config_dir,
    _check_database_file,
    _check_db_integrity,
    _check_db_permissions,
    _check_disk_space,
    _check_db_lock,
    _check_write_permissions,
    _check_optional_deps,
    _check_fts5,
    _check_security,
    _check_mcp_configs,
    _check_memory_count,
    _check_rules_engine,
    _check_auto_inject,
    _check_cli_path,
    _check_backup,
]


def _format_doctor_output(check_results: List[_DoctorCheck], parsed) -> int:
    """Render doctor results in JSON or human-readable form; return exit code."""
    issues = [c.message for c in check_results if c.status == "fail"]
    checks_passed = sum(1 for c in check_results if c.status == "ok")
    checks_total = len(check_results)

    if parsed.json:
        print(
            json.dumps(
                {
                    "version": __version__,
                    "checks_passed": checks_passed,
                    "checks_total": checks_total,
                    "issues": issues,
                    "checks": [
                        {
                            "name": c.name,
                            "status": c.status,
                            "message": c.message,
                            "detail": c.detail,
                        }
                        for c in check_results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not issues else 1

    print(f"\n  {_bold('CarryMem Doctor')} - Diagnostics\n")
    print(f"  {'=' * 45}")

    status_icons = {
        "ok": _green("[OK]"),
        "fail": _red("[FAIL]"),
        "warn": _yellow("[WARN]"),
        "info": _dim("[INFO]"),
        "skip": _dim("[SKIP]"),
    }
    for cr in check_results:
        icon = status_icons.get(cr.status, _dim("[???]"))
        print(f"  {icon} {cr.message}")

    print(f"\n  {'=' * 45}")
    if issues:
        print(f"  {_red(f'Issues found ({len(issues)}):')}")
        for issue in issues:
            print(f"    - {issue}")
        if not parsed.fix:
            print(f"\n  {_dim('Tip: Run')} carrymem doctor --fix {_dim('to auto-fix issues')}")
    else:
        print(f"  {_green(f'All checks passed ({checks_passed}/{checks_total})')}")

    print()
    return 0 if not issues else 1


def cmd_doctor(args):
    """Run diagnostics on the CarryMem installation and database."""
    parser = _make_parser("doctor")
    _add_common_args(parser)
    parser.add_argument("--fix", action="store_true", help=_t("cli.arg.fix"))
    parser.add_argument("--json", action="store_true", help=_t("cli.arg.json"))

    parsed = parser.parse_args(args)
    db_path = parsed.db or str(_DEFAULT_DB)
    ctx = _DoctorContext(db_path=db_path, fix=parsed.fix, db=Path(db_path))

    check_results = [check(ctx) for check in _DOCTOR_CHECKS]
    return _format_doctor_output(check_results, parsed)
