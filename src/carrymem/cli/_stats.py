"""CarryMem CLI - Stats/identity/diagnostic commands: stats, whoami, profile, check, doctor."""

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from carrymem.cli._base import *


def _show_value_report(cm, parsed) -> int:
    """Display the value perception report (--value flag)."""
    from datetime import datetime, timezone

    stats = cm.get_stats()
    profile = cm.get_memory_profile()
    total_memories = stats.get("total_count", 0)
    by_type = stats.get("by_type", {})
    profile_stats = profile.get("stats", {})
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

    def row(label, value):
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
    parser = _make_parser("stats")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument(
        "--value", "-v", action="store_true", help="Show value perception report (memories, rules, tokens saved, etc.)"
    )

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
            label = _TIER_LABELS.get(tier_num, f"T{tier_num}")
            print(f"    Tier {tier_num} ({label}): {count}")

    conf_avg = profile_stats.get("confidence_avg", 0)
    if conf_avg:
        print(f"\n  Avg Confidence: {conf_avg:.2f}")

    db_path = stats.get("db_path", "")
    if db_path and db_path != ":memory:":
        p = Path(db_path)
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  Database Size: {size_mb:.2f} MB")
            print(f"  Database Path: {_dim(db_path)}")

    print()
    cm.close()
    return 0


def cmd_whoami(args):
    parser = _make_parser("whoami")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

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
    parser = _make_parser("profile")
    parser.add_argument("action", choices=["export", "show"], default="show", nargs="?", help="Profile action")
    parser.add_argument("--output", "-o", help="Output file path (for export)")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")

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


def cmd_check(args):
    parser = _make_parser("check")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--conflicts", action="store_true", help="Check for conflicts")
    parser.add_argument("--quality", action="store_true", help="Check for low quality memories")
    parser.add_argument("--expired", action="store_true", help="Check for expired memories")
    parser.add_argument("--all", action="store_true", help="Run all checks")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    run_all = parsed.all or (not parsed.conflicts and not parsed.quality and not parsed.expired)

    print(f"\n  {_bold('CarryMem Quality Check')} (namespace: {parsed.namespace})")
    print(f"  {'=' * 45}\n")

    if run_all or parsed.conflicts:
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

    if run_all or parsed.quality:
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

    if run_all or parsed.expired:
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

    cm.close()
    return 0


def cmd_doctor(args):
    parser = _make_parser("doctor")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    parsed = parser.parse_args(args)
    db_path = parsed.db or str(_DEFAULT_DB)

    checks_passed = 0
    checks_total = 0
    issues = []
    check_results = []

    def _record(name, status, message, detail=None):
        nonlocal checks_passed, checks_total
        checks_total += 1
        if status == "ok":
            checks_passed += 1
        elif status == "fail":
            issues.append(message)
        check_results.append({"name": name, "status": status, "message": message, "detail": detail})

    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 9):
        _record("python_version", "ok", f"Python {py_str} (>= 3.9)")
    else:
        _record("python_version", "fail", f"Python {py_str} (need >= 3.9)")

    try:
        from carrymem import CarryMem

        _record("carrymem_import", "ok", f"CarryMem v{__version__}")
    except ImportError as e:
        _record("carrymem_import", "fail", f"CarryMem import: {e}")

    if _DEFAULT_CONFIG_DIR.exists():
        _record("config_dir", "ok", f"Config directory: {_DEFAULT_CONFIG_DIR}")
    else:
        _record("config_dir", "warn", f"Config directory missing: {_DEFAULT_CONFIG_DIR}")
        if parsed.fix:
            _DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    db = Path(db_path)
    if db.exists():
        size_mb = db.stat().st_size / (1024 * 1024)
        _record(
            "database_file",
            "ok",
            f"Database: {db} ({size_mb:.2f} MB)",
            {"size_mb": round(size_mb, 2)},
        )
    else:
        _record("database_file", "warn", f"Database not found: {db}")
        if parsed.fix:
            try:
                cm = CarryMem(db_path=db_path)
                cm.close()
            except (sqlite3.OperationalError, OSError) as e:
                _cli_logger.debug(f"Doctor: failed to create database: {e}")

    if db.exists():
        try:
            conn = sqlite3.connect(str(db))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] == "ok":
                _record("db_integrity", "ok", "Database integrity: OK")
            else:
                _record("db_integrity", "fail", f"Database integrity: {result[0]}")
        except sqlite3.Error as e:
            _record("db_integrity", "fail", f"Database check error: {e}")
    else:
        _record("db_integrity", "skip", "Database integrity (no database)")

    if db.exists():
        if os.access(str(db), os.W_OK):
            _record("db_permissions", "ok", "Database file writable")
        else:
            _record("db_permissions", "fail", "Database file not writable")
    else:
        _record("db_permissions", "skip", "Database permissions (no database)")

    try:
        disk_usage = shutil.disk_usage(str(db.parent) if db.exists() else str(Path.home()))
        free_gb = disk_usage.free / (1024**3)
        if free_gb < 0.1:
            _record("disk_space", "fail", f"Disk space critically low: {free_gb:.2f} GB free")
        elif free_gb < 1.0:
            _record("disk_space", "warn", f"Disk space low: {free_gb:.2f} GB free")
        else:
            _record(
                "disk_space",
                "ok",
                f"Disk space: {free_gb:.2f} GB free",
                {"free_gb": round(free_gb, 2)},
            )
    except OSError as e:
        _record("disk_space", "skip", f"Disk space check unavailable: {e}")

    if db.exists():
        try:
            test_conn = sqlite3.connect(str(db), timeout=1)
            test_conn.execute("BEGIN IMMEDIATE")
            test_conn.execute("ROLLBACK")
            test_conn.close()
            _record("db_lock", "ok", "Database not locked")
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                _record("db_lock", "warn", "Database may be locked by another process")
            else:
                _record("db_lock", "ok", "Database accessible")
        except Exception as e:
            _record("db_lock", "skip", f"Database lock check: {e}")
    else:
        _record("db_lock", "skip", "Database lock (no database)")

    try:
        test_file = _DEFAULT_CONFIG_DIR / ".doctor_test"
        test_file.touch()
        test_file.unlink()
        _record("write_permissions", "ok", "Write permissions OK")
    except OSError as e:
        _record("write_permissions", "fail", f"Write permissions: {e}")

    optional_deps = []
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
    _record(
        "optional_deps",
        "ok" if optional_deps else "info",
        f"Optional deps: {', '.join(optional_deps)}" if optional_deps else "No optional deps",
    )

    try:
        test_conn = sqlite3.connect(":memory:")
        test_conn.execute("CREATE VIRTUAL TABLE t USING fts5(c)")
        test_conn.close()
        _record("fts5", "ok", "SQLite FTS5 support")
    except sqlite3.OperationalError as e:
        _cli_logger.debug(f"FTS5 check failed: {e}")
        _record("fts5", "fail", "SQLite FTS5 not available")

    try:
        from carrymem.security import InputValidator

        validator = InputValidator()
        test_result = validator.validate_content("test content")
        if test_result:
            _record("security", "ok", "Security module (InputValidator)")
        else:
            _record("security", "warn", "Security module: validation returned empty")
    except ImportError:
        _record("security", "info", "Security module not available")
    except (ValueError, TypeError, RuntimeError) as e:
        _record("security", "warn", f"Security module: {e}")

    mcp_configs = []
    cwd = Path.cwd()
    claude_mcp = cwd / ".claude" / "mcp.json"
    cursor_mcp = cwd / ".cursor" / "mcp.json"
    if claude_mcp.exists():
        mcp_configs.append(f"claude-code ({claude_mcp})")
    if cursor_mcp.exists():
        mcp_configs.append(f"cursor ({cursor_mcp})")
    _record(
        "mcp_configs",
        "ok" if mcp_configs else "info",
        (f"MCP configs: {', '.join(mcp_configs)}" if mcp_configs else "No MCP configs in current directory"),
    )

    if db.exists():
        try:
            cm = CarryMem(db_path=db_path)
            stats = cm.get_stats()
            total = stats.get("total_count", 0)
            _record("memory_count", "ok", f"Memory count: {total}", {"total_count": total})
            cm.close()
        except (sqlite3.OperationalError, KeyError, ValueError):
            _record("memory_count", "warn", "Cannot read memory count")
    else:
        _record("memory_count", "skip", "Memory count (no database)")

    if db.exists():
        try:
            from carrymem.rules import RuleEngine

            re = RuleEngine(db_path=db_path)
            rules = re.list_rules(status="active")
            expired = sum(1 for r in rules if r.is_expired())
            msg = f"Active rules: {len(rules)}"
            if expired:
                msg += f" ({expired} expired)"
            _record(
                "rules_engine",
                "ok" if not expired else "warn",
                msg,
                {"active": len(rules), "expired": expired},
            )
        except (ImportError, sqlite3.OperationalError, KeyError, ValueError) as e:
            _record("rules_engine", "warn", f"Rules engine: {e}")
    else:
        _record("rules_engine", "skip", "Rules engine (no database)")

    auto_inject = os.environ.get("CARRYMEM_AUTO_INJECT", "").lower() in ("true", "1", "yes")
    _record(
        "auto_inject",
        "ok" if auto_inject else "info",
        f"Auto-inject: {'enabled' if auto_inject else 'disabled (set CARRYMEM_AUTO_INJECT=true)'}",
    )

    carrymem_on_path = shutil.which("carrymem") is not None
    if carrymem_on_path:
        _record("cli_path", "ok", "CLI command 'carrymem' is on PATH")
    else:
        py_ver_str = f"{sys.version_info.major}.{sys.version_info.minor}"
        if sys.platform == "darwin":
            path_hint = f'export PATH="$HOME/Library/Python/{py_ver_str}/bin:$PATH"'
        elif sys.platform.startswith("linux"):
            path_hint = 'export PATH="$HOME/.local/bin:$PATH"'
        else:
            path_hint = "Add Python Scripts directory to your PATH"
        _record(
            "cli_path",
            "warn",
            f"CLI command 'carrymem' NOT on PATH. Fix: {path_hint}",
            {"fix": path_hint},
        )

    # Backup status check
    if db.exists():
        try:
            from carrymem.backup import BackupManager

            manager = BackupManager(str(db))
            status = manager.get_status()
            backup_dir_exists = status["backup_dir_exists"]
            backup_count = status["backup_count"]
            latest_backup = status["latest_backup"]

            if not backup_dir_exists:
                _record("backup", "warn", "Backup directory does not exist")
            elif backup_count == 0:
                _record("backup", "warn", "No backups found — data loss risk")
            else:
                latest_str = _format_time(latest_backup) if latest_backup else "N/A"
                _record(
                    "backup",
                    "ok",
                    f"Backups: {backup_count} file(s), latest: {latest_str}",
                    {"count": backup_count, "latest": latest_backup},
                )
        except (OSError, ValueError) as e:
            _record("backup", "warn", f"Backup check: {e}")
    else:
        _record("backup", "skip", "Backup status (no database)")

    if parsed.json:
        print(
            json.dumps(
                {
                    "version": __version__,
                    "checks_passed": checks_passed,
                    "checks_total": checks_total,
                    "issues": issues,
                    "checks": check_results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not issues else 1

    print(f"\n  {_bold('CarryMem Doctor')} - Diagnostics\n")
    print(f"  {'=' * 45}")

    for cr in check_results:
        status_icon = {
            "ok": _green("[OK]"),
            "fail": _red("[FAIL]"),
            "warn": _yellow("[WARN]"),
            "info": _dim("[INFO]"),
            "skip": _dim("[SKIP]"),
        }.get(cr["status"], _dim("[???]"))
        print(f"  {status_icon} {cr['message']}")

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
