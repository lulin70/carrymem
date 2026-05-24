#!/usr/bin/env python3
"""CarryMem CLI - Your Portable AI Memory Layer.

Usage:
    carrymem add "I prefer dark mode"     Store a memory
    carrymem list                         List recent memories
    carrymem search "theme"               Search memories
    carrymem show <key>                   View memory details
    carrymem edit <key> "new content"     Edit a memory
    carrymem forget <key>                 Delete a memory
    carrymem clean                        Remove expired/low-quality
    carrymem export backup.json           Export memories
    carrymem import backup.json           Import memories
    carrymem stats                        Show statistics
    carrymem check                        Check quality & conflicts
    carrymem doctor                       Run diagnostics
    carrymem setup-mcp --tool cursor      Configure MCP integration
    carrymem tui                          Launch terminal UI
    carrymem serve                        Start MCP HTTP server
    carrymem version                      Show version
"""

import sys
import os
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from carrymem import CarryMem
    from carrymem.__version__ import __version__
    from carrymem.adapters.sqlite_adapter import SQLiteAdapter
except ImportError:
    print("Error: CarryMem not properly installed")
    print("Try: pip install -e .")
    sys.exit(1)

try:
    from carrymem.security.input_validator import InputValidator
    _cli_validator = InputValidator(strict_mode=False)
except ImportError:
    import logging
    logging.getLogger(__name__).warning("InputValidator not available — input validation disabled")
    _cli_validator = None


_DEFAULT_DB = Path.home() / ".carrymem" / "memories.db"
_DEFAULT_CONFIG_DIR = Path.home() / ".carrymem"

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

_HAS_COLOR = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _HAS_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(t): return _c("32", t)
def _red(t): return _c("31", t)
def _yellow(t): return _c("33", t)
def _cyan(t): return _c("36", t)
def _dim(t): return _c("2", t)
def _bold(t): return _c("1", t)


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
    except Exception:
        pass
    return str(iso_str)[:16]


def _truncate(text: str, max_len: int = 60) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _find_memory(cm: CarryMem, key: str) -> Optional[Dict[str, Any]]:
    if cm._adapter and hasattr(cm._adapter, '_get_by_key'):
        stored = cm._adapter._get_by_key(key)
        if stored:
            return stored.to_dict()
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
    access_count = m.get("access_count", 0)

    prefix = f"  {index}." if index else "  "
    print(f"{prefix} {icon} {_bold(_truncate(content, 65))}")
    print(f"     {_dim(f'Type: {mtype} | Conf: {confidence:.0%} | Importance: {importance:.2f} | {tier_label}')}")
    print(f"     {_dim(f'Key: {key} | {_format_time(created)}')}")


def cmd_add(args):
    parser = _make_parser("add")
    parser.add_argument("message", help="Message to remember")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--context", "-c", help="Additional context (JSON)")
    parser.add_argument("--force", "-f", action="store_true", help="Force store without classification")
    parser.add_argument("--type", "-t", help="Override memory type (with --force)")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.message = _cli_validator.validate_content(parsed.message, "message")
        except Exception as e:
            print(f"  {_red('Validation Error:')} {e}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    context = None
    if parsed.context:
        try:
            context = json.loads(parsed.context)
        except json.JSONDecodeError:
            print(f"  {_red('Error:')} Invalid JSON context: {parsed.context}")
            return 1

    if parsed.force:
        result = cm.declare(parsed.message, context=context)
        keys = result.get("storage_keys", [])
        entries = result.get("entries", [])
        if keys:
            print(f"  {_green('Stored')} (forced) {len(keys)} item(s)")
            for i, key in enumerate(keys):
                entry = entries[i] if i < len(entries) else {}
                mtype = entry.get("type", parsed.type or "unknown")
                icon = _TYPE_ICONS.get(mtype, "\u2753")
                content = entry.get("content", parsed.message)
                print(f"    {icon} [{mtype}] {_truncate(content, 70)}")
                print(f"       Key: {key}")
        else:
            print(f"  {_red('Failed to store memory')}")
            cm.close()
            return 1
    else:
        result = cm.classify_and_remember(parsed.message, context=context)

        if not result.get("should_remember"):
            print(f"  {_yellow('Not classified as memorable')} (noise or too vague)")
            print(f"  {_dim('Tip: Use --force to store anyway:')}")
            tip_msg = f'  carrymem add --force "{parsed.message}"'
            print(f"  {_dim(tip_msg)}")
            cm.close()
            return 0

        entries = result.get("entries", [])
        keys = result.get("storage_keys", [])

        for i, entry in enumerate(entries):
            mtype = entry.get("type", "unknown")
            icon = _TYPE_ICONS.get(mtype, "\u2753")
            confidence = entry.get("confidence", 0)
            content = entry.get("content", "")
            tier = entry.get("tier", 2)
            tier_label = _TIER_LABELS.get(tier, f"T{tier}")

            print(f"  {icon} [{mtype}] {_bold(_truncate(content, 70))}")
            key_display = keys[i] if i < len(keys) else "N/A"
            print(f"     {_dim(f'Confidence: {confidence:.0%} | Tier: {tier_label} | Key: {key_display}')}")

        print(f"\n  {_green(f'Remembered {len(entries)} item(s)')}")

    cm.close()
    return 0


def cmd_list(args):
    parser = _make_parser("list")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Number of memories to show")
    parser.add_argument("--type", "-t", help="Filter by memory type")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--format", "-f", choices=["table", "json", "plain"], default="table", help="Output format")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(query="", filters=filters, limit=parsed.limit)

    if not memories:
        print(f"  {_dim('No memories found')}")
        tip = 'Tip: carrymem add "I prefer dark mode"'
        print(f"  {_dim(tip)}")
        cm.close()
        return 0

    if parsed.format == "json":
        print(json.dumps(memories, ensure_ascii=False, indent=2))
    elif parsed.format == "plain":
        for m in memories:
            print(f"{m.get('storage_key', '')}\t{m.get('type', '')}\t{m.get('content', '')}\t{m.get('confidence', 0):.2f}")
    else:
        print(f"\n  {_bold(f'Memories')} ({len(memories)} shown, namespace={parsed.namespace})\n")
        for i, m in enumerate(memories, 1):
            _print_memory_card(m, index=i)
            print()

    cm.close()
    return 0


def cmd_search(args):
    parser = _make_parser("search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    parser.add_argument("--type", "-t", help="Filter by memory type")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--format", "-f", choices=["table", "json", "plain"], default="table", help="Output format")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.query = _cli_validator.validate_query(parsed.query)
        except Exception as e:
            print(f"  {_red('Validation Error:')} {e}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(query=parsed.query, filters=filters, limit=parsed.limit)

    if not memories:
        print(f"  {_dim(f'No memories matching')} {_bold(parsed.query)}")
        cm.close()
        return 0

    if parsed.format == "json":
        print(json.dumps(memories, ensure_ascii=False, indent=2))
    elif parsed.format == "plain":
        for m in memories:
            print(f"{m.get('storage_key', '')}\t{m.get('type', '')}\t{m.get('content', '')}\t{m.get('confidence', 0):.2f}")
    else:
        print(f"\n  {_bold('Search:')} {_cyan(parsed.query)} ({len(memories)} results)\n")
        for i, m in enumerate(memories, 1):
            _print_memory_card(m, index=i)
            print()

    cm.close()
    return 0


def cmd_show(args):
    parser = _make_parser("show")
    parser.add_argument("key", help="Storage key of the memory")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    parsed = parser.parse_args(args)

    cm = _get_carrymem(parsed.db, parsed.namespace)

    target = _find_memory(cm, parsed.key)

    if not target:
        print(f"  {_red('Memory not found:')} {parsed.key}")
        cm.close()
        return 1

    if parsed.json:
        print(json.dumps(target, ensure_ascii=False, indent=2))
        cm.close()
        return 0

    mtype = target.get("type", "unknown")
    icon = _TYPE_ICONS.get(mtype, "\u2753")
    content = target.get("content", "")
    confidence = target.get("confidence", 0)
    importance = target.get("importance_score", 0)
    key = target.get("storage_key", "")
    created = target.get("created_at", "")
    tier = target.get("tier", 2)
    tier_label = _TIER_LABELS.get(tier, f"T{tier}")
    access_count = target.get("access_count", 0)
    original = target.get("original_message", "")
    version = target.get("version", 1)
    expires = target.get("expires_at", "")

    print(f"\n  {icon} {_bold(content)}")
    print(f"  {'=' * 50}")
    print(f"  Key:        {key}")
    print(f"  Type:       {mtype}")
    print(f"  Tier:       {tier_label} ({tier})")
    print(f"  Confidence: {confidence:.0%}")
    print(f"  Importance: {importance:.3f}")
    print(f"  Version:    {version}")
    print(f"  Accesses:   {access_count}")
    print(f"  Created:    {_format_time(created)}")
    if expires:
        print(f"  Expires:    {expires}")
    if original and original != content:
        print(f"\n  Original:   {_dim(original)}")

    print()
    cm.close()
    return 0


def cmd_edit(args):
    parser = _make_parser("edit")
    parser.add_argument("key", help="Storage key of the memory to edit")
    parser.add_argument("content", help="New content")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.content = _cli_validator.validate_content(parsed.content, "content")
        except Exception as e:
            print(f"  {_red('Validation Error:')} {e}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    target = _find_memory(cm, parsed.key)

    if not target:
        print(f"  {_red('Memory not found:')} {parsed.key}")
        cm.close()
        return 1

    old_content = target.get("content", "")
    print(f"  {_dim('Old:')} {_truncate(old_content, 60)}")
    print(f"  {_green('New:')} {_truncate(parsed.content, 60)}")

    try:
        answer = input("  Confirm edit? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        cm.close()
        return 0

    if answer != "y":
        print(f"  {_dim('Cancelled')}")
        cm.close()
        return 0

    result = cm.update_memory(parsed.key, parsed.content)
    success = result.get("updated", False) if isinstance(result, dict) else bool(result)
    if success:
        print(f"  {_green('Updated:')} {parsed.key}")
    else:
        print(f"  {_red('Failed to update:')} {parsed.key}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_forget(args):
    parser = _make_parser("forget")
    parser.add_argument("key", help="Storage key of the memory to delete")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--force", "-y", action="store_true", help="Skip confirmation")

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.key = _cli_validator.validate_content(parsed.key, "key")
        except Exception as e:
            print(f"  {_red('Validation Error:')} {e}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    target = _find_memory(cm, parsed.key)

    if not target:
        print(f"  {_red('Memory not found:')} {parsed.key}")
        cm.close()
        return 1

    if not parsed.force:
        content = target.get("content", "")
        print(f"  {_red('Delete:')} {_truncate(content, 60)}")
        print(f"  Key: {parsed.key}")
        try:
            answer = input("  Confirm? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            cm.close()
            return 0
        if answer != "y":
            print(f"  {_dim('Cancelled')}")
            cm.close()
            return 0

    success = cm.forget_memory(parsed.key)
    if success:
        print(f"  {_green('Forgotten:')} {parsed.key}")
    else:
        print(f"  {_red('Failed to forget:')} {parsed.key}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_clean(args):
    parser = _make_parser("clean")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--expired", action="store_true", help="Remove expired memories")
    parser.add_argument("--quality", type=float, default=0, help="Remove memories below quality threshold")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed")
    parser.add_argument("--force", "-y", action="store_true", help="Skip confirmation")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    to_remove = []

    if parsed.expired:
        expired = cm.list_expired()
        for item in expired:
            to_remove.append(("expired", item))

    if parsed.quality > 0:
        low_quality = cm.check_quality(min_score=parsed.quality)
        for item in low_quality:
            already = any(r[1].get("storage_key") == item["storage_key"] for r in to_remove)
            if not already:
                to_remove.append(("low_quality", item))

    if not to_remove:
        print(f"  {_green('Nothing to clean')} — all memories are healthy")
        cm.close()
        return 0

    print(f"\n  {_bold('Memories to clean:')} {len(to_remove)}\n")
    for reason, item in to_remove:
        key = item.get("storage_key", "")
        content = item.get("content", "")
        if reason == "expired":
            print(f"    {_yellow('[EXPIRED]')} {_truncate(content, 50)}")
        else:
            score = item.get("score", 0)
            print(f"    {_yellow(f'[QUALITY:{score:.2f}]')} {_truncate(content, 50)}")
        print(f"      Key: {key}")

    if parsed.dry_run:
        print(f"\n  {_dim('Dry run — no changes made')}")
        cm.close()
        return 0

    if not parsed.force:
        try:
            answer = input(f"\n  Remove {len(to_remove)} memories? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            cm.close()
            return 0
        if answer != "y":
            print(f"  {_dim('Cancelled')}")
            cm.close()
            return 0

    removed = 0
    errors = 0
    for reason, item in to_remove:
        key = item.get("storage_key", "")
        if cm.forget_memory(key):
            removed += 1
        else:
            errors += 1

    print(f"\n  {_green(f'Cleaned:')} {removed} removed, {errors} errors")
    cm.close()
    return 0 if errors == 0 else 1


def cmd_consolidate(args):
    """Run or schedule memory consolidation (dedup, decay, cleanup)."""
    parser = _make_parser("consolidate")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--no-p1", action="store_true", help="Skip P1 pattern recognition")
    parser.add_argument("--no-p2", action="store_true", help="Skip P2 semantic consolidation")
    parser.add_argument("--schedule", type=float, default=0, metavar="HOURS",
                        help="Schedule periodic consolidation (e.g., --schedule 1 for hourly)")
    parser.add_argument("--stop", action="store_true", help="Stop scheduled consolidation")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    if parsed.stop:
        result = cm.stop_consolidation()
        if result.get("stopped"):
            print(f"  {_green('Consolidation schedule stopped')}")
        else:
            print(f"  {_dim('No active consolidation schedule')}")
        cm.close()
        return 0

    if parsed.schedule > 0:
        result = cm.schedule_consolidation(
            interval_hours=parsed.schedule,
            dry_run=parsed.dry_run,
            run_p1=not parsed.no_p1,
            run_p2=not parsed.no_p2,
        )
        print(f"\n  {_green('Consolidation scheduled')}")
        print(f"    Interval: {result['interval_hours']}h")
        print(f"    Dry run:  {result['dry_run']}")
        print(f"    P1:       {result['run_p1']}")
        print(f"    P2:       {result['run_p2']}")
        print(f"\n  {_dim('Use --stop to cancel')}")
        # Keep process alive for scheduled mode
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print(f"\n  {_dim('Stopping consolidation schedule...')}")
            cm.stop_consolidation()
        cm.close()
        return 0

    # One-shot consolidation
    print(f"\n  {_bold('Running consolidation...')}\n")
    report = cm.consolidate(
        dry_run=parsed.dry_run,
        run_p1=not parsed.no_p1,
        run_p2=not parsed.no_p2,
    )

    if report.get("dry_run"):
        print(f"  {_yellow('[DRY RUN]')} No changes made\n")

    print(f"  Superseded: {report.get('superseded_count', len(report.get('to_supersede', [])))}")
    print(f"  Decayed:    {len(report.get('to_decay', []))}")
    print(f"  Forgotten:  {report.get('forgotten_count', len(report.get('to_forget', [])))}")

    p1 = report.get("p1_promotion")
    if p1:
        print(f"  P1 promotions: {p1.get('promotion_count', 0)}")

    p2 = report.get("p2_consolidation")
    if p2:
        print(f"  P2 consolidation requests: {len(p2.get('consolidation_requests', []))}")

    cm.close()
    return 0


def cmd_export(args):
    parser = _make_parser("export")
    parser.add_argument("output", help="Output file path")
    parser.add_argument("--format", "-f", choices=["json", "markdown"], default="json", help="Export format")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    result = cm.export_memories(output_path=parsed.output, format=parsed.format, namespace=parsed.namespace)

    if result.get("exported"):
        total = result.get("total_memories", 0)
        fmt = result.get("format", "json")
        print(f"  {_green('Exported')} {total} memories to {_cyan(parsed.output)} ({fmt})")
    else:
        print(f"  {_red('Export failed:')} {result}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_import(args):
    parser = _make_parser("import")
    parser.add_argument("input", help="Input file path")
    parser.add_argument("--namespace", "-n", default="default", help="Target namespace")
    parser.add_argument("--merge", choices=["skip_existing", "overwrite"], default="skip_existing", help="Merge strategy")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    result = cm.import_memories(
        input_path=parsed.input,
        namespace=parsed.namespace,
        merge_strategy=parsed.merge,
    )

    imported = result.get("imported", 0)
    skipped = result.get("skipped", 0)
    errors = result.get("errors", 0)
    total = result.get("total_processed", 0)

    print(f"  {_green('Import complete:')} {imported} imported, {skipped} skipped, {errors} errors ({total} total)")

    if errors > 0:
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_stats(args):
    parser = _make_parser("stats")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

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
        print(f"\n  By Type:")
        max_type_len = max(len(t) for t in by_type) if by_type else 10
        for mtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            icon = _TYPE_ICONS.get(mtype, "  ")
            bar = "\u2588" * min(count, 30)
            pct = (count / total * 100) if total > 0 else 0
            print(f"    {icon} {mtype.ljust(max_type_len)}  {count:4d}  {_cyan(bar)}  ({pct:.0f}%)")

    profile_stats = profile.get("stats", {})
    by_tier = profile_stats.get("by_tier", {})
    if by_tier:
        print(f"\n  By Tier:")
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
        print(f'    carrymem add "I prefer dark mode"')
        print(f'    carrymem add "I use Python for data analysis"')
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
        print(f"  Conflicts:")
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
        except Exception as e:
            print(f"    {_red(f'Error: {e}')}")
        print()

    if run_all or parsed.quality:
        print(f"  Low Quality Memories:")
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
        except Exception as e:
            print(f"    {_red(f'Error: {e}')}")
        print()

    if run_all or parsed.expired:
        print(f"  Expired Memories:")
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
        except Exception as e:
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
        _record("database_file", "ok", f"Database: {db} ({size_mb:.2f} MB)", {"size_mb": round(size_mb, 2)})
    else:
        _record("database_file", "warn", f"Database not found: {db}")
        if parsed.fix:
            try:
                cm = CarryMem(db_path=db_path)
                cm.close()
            except Exception as e:
                pass

    if db.exists():
        try:
            conn = sqlite3.connect(str(db))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] == "ok":
                _record("db_integrity", "ok", "Database integrity: OK")
            else:
                _record("db_integrity", "fail", f"Database integrity: {result[0]}")
        except Exception as e:
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
        import shutil
        disk_usage = shutil.disk_usage(str(db.parent) if db.exists() else str(Path.home()))
        free_gb = disk_usage.free / (1024 ** 3)
        if free_gb < 0.1:
            _record("disk_space", "fail", f"Disk space critically low: {free_gb:.2f} GB free")
        elif free_gb < 1.0:
            _record("disk_space", "warn", f"Disk space low: {free_gb:.2f} GB free")
        else:
            _record("disk_space", "ok", f"Disk space: {free_gb:.2f} GB free", {"free_gb": round(free_gb, 2)})
    except Exception as e:
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
    except Exception as e:
        _record("write_permissions", "fail", f"Write permissions: {e}")

    optional_deps = []
    try:
        import pycld2
        optional_deps.append("pycld2")
    except ImportError:
        pass
    try:
        from cryptography.fernet import Fernet
        optional_deps.append("cryptography")
    except ImportError:
        pass
    try:
        import langdetect
        optional_deps.append("langdetect")
    except ImportError:
        pass
    try:
        import textual
        optional_deps.append("textual")
    except ImportError:
        pass
    _record("optional_deps", "ok" if optional_deps else "info",
            f"Optional deps: {', '.join(optional_deps)}" if optional_deps else "No optional deps")

    try:
        test_conn = sqlite3.connect(":memory:")
        test_conn.execute("CREATE VIRTUAL TABLE t USING fts5(c)")
        test_conn.close()
        _record("fts5", "ok", "SQLite FTS5 support")
    except Exception:
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
    except Exception as e:
        _record("security", "warn", f"Security module: {e}")

    mcp_configs = []
    cwd = Path.cwd()
    claude_mcp = cwd / ".claude" / "mcp.json"
    cursor_mcp = cwd / ".cursor" / "mcp.json"
    if claude_mcp.exists():
        mcp_configs.append(f"claude-code ({claude_mcp})")
    if cursor_mcp.exists():
        mcp_configs.append(f"cursor ({cursor_mcp})")
    _record("mcp_configs", "ok" if mcp_configs else "info",
            f"MCP configs: {', '.join(mcp_configs)}" if mcp_configs else "No MCP configs in current directory")

    if db.exists():
        try:
            cm = CarryMem(db_path=db_path)
            stats = cm.get_stats()
            total = stats.get("total_count", 0)
            _record("memory_count", "ok", f"Memory count: {total}", {"total_count": total})
            cm.close()
        except Exception:
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
            _record("rules_engine", "ok" if not expired else "warn", msg, {"active": len(rules), "expired": expired})
        except Exception as e:
            _record("rules_engine", "warn", f"Rules engine: {e}")
    else:
        _record("rules_engine", "skip", "Rules engine (no database)")

    auto_inject = os.environ.get("CARRYMEM_AUTO_INJECT", "").lower() in ("true", "1", "yes")
    _record("auto_inject", "ok" if auto_inject else "info",
            f"Auto-inject: {'enabled' if auto_inject else 'disabled (set CARRYMEM_AUTO_INJECT=true)'}")

    import shutil
    carrymem_on_path = shutil.which("carrymem") is not None
    if carrymem_on_path:
        _record("cli_path", "ok", "CLI command 'carrymem' is on PATH")
    else:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        if sys.platform == "darwin":
            path_hint = f"export PATH=\"$HOME/Library/Python/{py_ver}/bin:$PATH\""
        elif sys.platform.startswith("linux"):
            path_hint = 'export PATH="$HOME/.local/bin:$PATH"'
        else:
            path_hint = "Add Python Scripts directory to your PATH"
        _record("cli_path", "warn",
                f"CLI command 'carrymem' NOT on PATH. Fix: {path_hint}",
                {"fix": path_hint})

    if parsed.json:
        print(json.dumps({
            "version": __version__,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "issues": issues,
            "checks": check_results,
        }, ensure_ascii=False, indent=2))
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


def cmd_setup_mcp(args):
    parser = _make_parser("setup-mcp")
    parser.add_argument("--tool", "-t", choices=["claude-code", "cursor", "all"], default="all", help="Target tool")
    parser.add_argument("--project", "-p", default=".", help="Project directory (default: current)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing config")

    parsed = parser.parse_args(args)
    project_dir = Path(parsed.project).resolve()

    python_path = sys.executable
    module_cmd = f"{python_path} -m carrymem.integration.layer2_mcp"

    mcp_config = {
        "mcpServers": {
            "carrymem": {
                "command": python_path,
                "args": ["-m", "carrymem.integration.layer2_mcp"],
            }
        }
    }

    configured = []

    if parsed.tool in ("claude-code", "all"):
        claude_dir = project_dir / ".claude"
        claude_file = claude_dir / "mcp.json"

        skip_claude = False
        if claude_file.exists() and not parsed.force:
            try:
                with open(claude_file) as f:
                    existing = json.load(f)
                if "carrymem" in existing.get("mcpServers", {}):
                    print(f"  {_dim('Claude Code: already configured')} ({claude_file})")
                    configured.append("claude-code")
                    skip_claude = True
            except Exception:
                pass

        if not skip_claude:
            claude_dir.mkdir(parents=True, exist_ok=True)
            if claude_file.exists():
                try:
                    with open(claude_file) as f:
                        existing = json.load(f)
                    existing.setdefault("mcpServers", {})["carrymem"] = mcp_config["mcpServers"]["carrymem"]
                    with open(claude_file, "w") as f:
                        json.dump(existing, f, indent=2)
                except Exception:
                    with open(claude_file, "w") as f:
                        json.dump(mcp_config, f, indent=2)
            else:
                with open(claude_file, "w") as f:
                    json.dump(mcp_config, f, indent=2)
            print(f"  {_green('Claude Code:')} configured ({claude_file})")
            configured.append("claude-code")

    if parsed.tool in ("cursor", "all"):
        cursor_dir = project_dir / ".cursor"
        cursor_file = cursor_dir / "mcp.json"

        skip_cursor = False
        if cursor_file.exists() and not parsed.force:
            try:
                with open(cursor_file) as f:
                    existing = json.load(f)
                if "carrymem" in existing.get("mcpServers", {}):
                    print(f"  {_dim('Cursor: already configured')} ({cursor_file})")
                    configured.append("cursor")
                    skip_cursor = True
            except Exception:
                pass

        if not skip_cursor:
            cursor_dir.mkdir(parents=True, exist_ok=True)
            if cursor_file.exists():
                try:
                    with open(cursor_file) as f:
                        existing = json.load(f)
                    existing.setdefault("mcpServers", {})["carrymem"] = mcp_config["mcpServers"]["carrymem"]
                    with open(cursor_file, "w") as f:
                        json.dump(existing, f, indent=2)
                except Exception:
                    with open(cursor_file, "w") as f:
                        json.dump(mcp_config, f, indent=2)
            else:
                with open(cursor_file, "w") as f:
                    json.dump(mcp_config, f, indent=2)
            print(f"  {_green('Cursor:')} configured ({cursor_file})")
            configured.append("cursor")

    if configured:
        print(f"\n  {_green('MCP integration ready for:')} {', '.join(configured)}")
        print(f"  {_dim(f'Command: {module_cmd}')}")
        print(f"\n  {_bold('Restart your AI tool to activate CarryMem')}")
    else:
        print(f"  {_dim('No tools configured')}")

    return 0


def cmd_serve(args):
    parser = _make_parser("serve")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", "-p", type=int, default=8765, help="Port to listen")
    parser.add_argument("--api-key", help="API key for authentication")

    parsed = parser.parse_args(args)

    from carrymem.integration.layer2_mcp.http_server import run_http_server
    print(f"\n  {_bold('CarryMem MCP HTTP Server')}")
    print(f"  Host:   {parsed.host}")
    print(f"  Port:   {parsed.port}")
    print(f"  SSE:    {_cyan(f'http://{parsed.host}:{parsed.port}/sse')}")
    print(f"  API:    {_cyan(f'http://{parsed.host}:{parsed.port}/message')}")
    print(f"  Health: {_cyan(f'http://{parsed.host}:{parsed.port}/health')}")
    print()
    run_http_server(host=parsed.host, port=parsed.port, api_key=parsed.api_key)
    return 0


def cmd_tui(args):
    from carrymem.tui import run_tui, HAS_TEXTUAL
    if not HAS_TEXTUAL:
        print(f"  {_yellow('Textual is not installed.')}")
        print(f"  Install with: {_cyan('pip install textual')}")
        print(f"  Then run: carrymem tui")
        return 1

    parser = _make_parser("tui")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)
    run_tui(db_path=parsed.db, namespace=parsed.namespace)
    return 0


def cmd_tutorial(args):
    if args and args[0] in ("--help", "-h"):
        print("  Usage: carrymem tutorial")
        print("  Show a 5-minute quick-start guide for CarryMem.")
        return 0
    print(f"""
  {_bold('Welcome to CarryMem!')} {_dim('Learn the basics in 5 minutes.')}

  {_bold('[1/5] Store your first memory')}
  >>> carrymem add "I prefer dark mode"
  >>> carrymem remember "I use Python for data analysis"

  {_bold('[2/5] View your memories')}
  >>> carrymem list
  >>> carrymem list --type user_preference

  {_bold('[3/5] Search your memories')}
  >>> carrymem search "theme"
  >>> carrymem search "database"

  {_bold('[4/5] Create a rule')}
  >>> carrymem add-rule "use PostgreSQL" --trigger "database selection"
  >>> carrymem rules list

  {_bold('[5/5] Connect to your AI tool')}
  >>> carrymem setup-mcp --tool cursor
  >>> carrymem setup-mcp --tool claude-code

  {_green('You are all set!')} CarryMem will help your AI remember you.

  {_dim('Next steps:')}
    carrymem whoami          See what your AI knows about you
    carrymem doctor          Run diagnostics
    carrymem help            Full command reference
""")
    return 0


def cmd_rules_hub(args):
    if not args:
        return cmd_list_rules([])

    sub_commands = {
        "list": cmd_list_rules,
        "add": cmd_add_rule,
        "delete": cmd_delete_rule,
        "match": cmd_match_rules,
        "edit": cmd_edit_rule,
        "pause": cmd_pause_rule,
        "resume": cmd_resume_rule,
        "stats": cmd_rules_stats,
        "check": cmd_check_rules,
        "export": cmd_export_rules,
        "import": cmd_import_rules,
        "suggest": cmd_suggest_rules,
    }

    sub = args[0]
    sub_args = args[1:]
    handler = sub_commands.get(sub)
    if handler:
        return handler(sub_args)

    print(f"  {_red('Unknown rules sub-command:')} {sub}")
    print(f"  {_dim('Available: list, add, delete, match, edit, pause, resume, stats, check, export, import, suggest')}")
    return 1


def cmd_init(args):
    parser = _make_parser("init")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)
    db_path = parsed.db or str(_DEFAULT_DB)

    print(f"\n  {_bold('Initializing CarryMem...')}\n")

    if not _DEFAULT_CONFIG_DIR.exists():
        _DEFAULT_CONFIG_DIR.mkdir(parents=True)
        print(f"  {_green('[OK]')} Created config directory: {_DEFAULT_CONFIG_DIR}")
    else:
        print(f"  {_green('[OK]')} Config directory exists: {_DEFAULT_CONFIG_DIR}")

    config_file = _DEFAULT_CONFIG_DIR / "config.json"
    if not config_file.exists():
        config = {
            "version": __version__,
            "db_path": db_path,
            "namespace": "default",
        }
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"  {_green('[OK]')} Created config: {config_file}")
    else:
        print(f"  {_green('[OK]')} Config exists: {config_file}")

    try:
        cm = CarryMem(db_path=db_path)
        cm.declare("CarryMem initialized successfully!")
        print(f"  {_green('[OK]')} Database initialized: {db_path}")
        cm.close()
    except Exception as e:
        print(f"  {_red('[FAIL]')} Database init error: {e}")
        return 1

    print(f"\n  {_green(_bold('CarryMem is ready!'))}")
    print(f"\n  {_bold('Quick Start:')}")
    print(f'    carrymem add "I prefer dark mode"')
    print(f"    carrymem list")
    print(f'    carrymem search "theme"')
    print(f"    carrymem setup-mcp --tool cursor")
    print(f"    carrymem tui")
    print()
    return 0


def cmd_version(args):
    print(f"\n  {_bold(f'CarryMem v{__version__}')}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Config: {_DEFAULT_CONFIG_DIR}")
    print(f"  Database: {_DEFAULT_DB}")
    print()
    return 0


def _get_rule_engine(db_path: Optional[str] = None):
    from carrymem.rules import RuleEngine
    path = db_path or str(_DEFAULT_DB)
    return RuleEngine(path)


def cmd_add_rule(args):
    parser = _make_parser("add-rule")
    parser.add_argument("action", nargs="?", help="Behavior instruction (what AI should do)")
    parser.add_argument("--trigger", "-t", help="Scene description that activates this rule")
    parser.add_argument("--type", choices=["avoid", "always", "prefer", "forbid", "format"],
                        default=None, help="Rule type")
    parser.add_argument("--soft", action="store_true", help="Make this a soft suggestion (AI can ignore)")
    parser.add_argument("--template", help="Use a rule template (see: carrymem list-templates)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Guided interactive creation")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    # Template mode
    if parsed.template:
        from carrymem.rules.templates import get_template
        try:
            tmpl = get_template(parsed.template)
        except KeyError as e:
            print(f"\n  {_red(f'Template error: {e}')}")
            return 1

        trigger = parsed.trigger or tmpl["trigger"]
        action = parsed.action or tmpl["action"]
        rule_type = parsed.type or tmpl["rule_type"]
        override = not parsed.soft if parsed.soft else tmpl.get("override", True)

    # Interactive mode
    elif parsed.interactive:
        try:
            print(f"\n  {_bold('CarryMem Rule Creator')}")
            print(f"  {'─' * 40}")

            trigger = input(f"  {_bold('Trigger')} (when does this apply)? ").strip()
            if not trigger:
                print(f"\n  {_red('Trigger cannot be empty')}")
                return 1

            action = input(f"  {_bold('Action')} (what should AI do)? ").strip()
            if not action:
                print(f"\n  {_red('Action cannot be empty')}")
                return 1

            print(f"  {_bold('Rule Type:')}")
            print(f"    1) avoid   — Avoid doing something")
            print(f"    2) always  — Always do this")
            print(f"    3) prefer  — Prefer this approach")
            print(f"    4) forbid  — Never do this")
            print(f"    5) format  — Format output this way")
            type_input = input(f"  {_bold('Choose')} [1-5, default=1]: ").strip()
            type_map = {"1": "avoid", "2": "always", "3": "prefer", "4": "forbid", "5": "format"}
            rule_type = type_map.get(type_input, "avoid")

            strict_input = input(f"  {_bold('Hard rule?')} (AI cannot ignore) [Y/n]: ").strip().lower()
            override = strict_input != "n"

        except (KeyboardInterrupt, EOFError):
            print(f"\n  {_yellow('Cancelled')}")
            return 1

    # Normal mode
    else:
        if not parsed.action or not parsed.trigger:
            print(f"\n  {_red('Missing required arguments. Use:')} carrymem add-rule <action> --trigger <scene>")
            print(f"  {_dim('Or use:')} carrymem add-rule --interactive")
            print(f"  {_dim('Or use:')} carrymem add-rule --template <name>")
            return 1

        trigger = parsed.trigger
        action = parsed.action
        rule_type = parsed.type or "avoid"
        override = not parsed.soft

    try:
        engine = _get_rule_engine(parsed.db)
        rule = engine.add_rule(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=override,
        )
        marker = _red("HARD") if rule.override else _yellow("SOFT")
        print(f"\n  {_green('Rule created:')} {rule.id}")
        print(f"    Trigger: {rule.trigger}")
        print(f"    Action:  {rule.action}")
        print(f"    Type:    {rule.rule_type}")
        print(f"    Status:  {rule.status}")
        print(f"    Force:   {marker}")
        print()
        return 0
    except ValueError as e:
        print(f"\n  {_red(f'Validation error: {e}')}")
        return 1


def cmd_list_rules(args):
    parser = _make_parser("list-rules")
    parser.add_argument("--status", choices=["active", "paused", "deprecated"], help="Filter by status")
    parser.add_argument("--type", choices=["avoid", "always", "prefer", "forbid", "format"], help="Filter by type")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--format", choices=["detail", "table", "compact"], default="detail", help="Output format")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    rules = engine.list_rules(status=parsed.status, rule_type=parsed.type, limit=parsed.limit)

    if not rules:
        print(f"\n  {_dim('No rules found.')}")
        print(f"  Create one with: carrymem add-rule <action> --trigger <scene>")
        print()
        return 0

    if parsed.format == "compact":
        for rule in rules:
            marker = "!" if rule.override else "~"
            expired = " [EXPIRED]" if rule.is_expired() else ""
            print(f"[{marker}] ({rule.scope}/{rule.rule_type}) {rule.trigger} → {rule.action}{expired}")
        return 0

    if parsed.format == "table":
        print(f"\n  {'ID':<14} {'Type':<8} {'Scope':<10} {'Override':<8} {'Trigger':<20} {'Action':<30}")
        print(f"  {'─'*14} {'─'*8} {'─'*10} {'─'*8} {'─'*20} {'─'*30}")
        for rule in rules:
            expired = " [EXPIRED]" if rule.is_expired() else ""
            override_str = "HARD" if rule.override else "soft"
            print(f"  {rule.id:<14} {rule.rule_type:<8} {rule.scope:<10} {override_str:<8} {rule.trigger[:20]:<20} {rule.action[:30]:<30}{expired}")
        print(f"\n  Total: {len(rules)} rules")
        return 0

    print(f"\n  {_bold(f'Rules ({len(rules)} found)')}")
    print(f"  {'─' * 60}")

    _type_icons = {"avoid": "🚫", "always": "✅", "prefer": "💡", "forbid": "⛔", "format": "📝"}
    for rule in rules:
        icon = _type_icons.get(rule.rule_type, "?")
        marker = "🔴" if rule.override else "🟡"
        status_str = ""
        if rule.status != "active":
            status_str = f" [{rule.status}]"
        expired_str = " ⚠️ EXPIRED" if rule.is_expired() else ""
        print(f"  {icon} {marker} {_bold(rule.id)}{status_str}{expired_str}")
        print(f"     Trigger: {rule.trigger}")
        print(f"     Action:  {rule.action}")
        print(f"     Type: {rule.rule_type} | Used: {rule.trigger_count}x | Confidence: {rule.confidence:.0%}")
        if rule.expires_at:
            print(f"     Expires: {rule.expires_at}")
        print()

    return 0


def cmd_match_rules(args):
    parser = _make_parser("match-rules")
    parser.add_argument("scene", help="Scene description to match against")
    parser.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")
    parser.add_argument("--format", choices=["text", "json", "compact", "anchored", "ddd"], default="text", help="Output format")
    parser.add_argument("--context-budget", type=int, default=None, help="Context budget in tokens (enables compression)")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)

    if parsed.format == "json":
        result = engine.inject(parsed.scene, format="json", max_rules=parsed.limit)
        print(result)
        return 0
    elif parsed.format == "compact":
        result = engine.inject(parsed.scene, format="compact", max_rules=parsed.limit)
        print(result)
        return 0
    elif parsed.format == "anchored":
        result = engine.inject(
            parsed.scene, format="anchored", max_rules=parsed.limit,
            context_budget_tokens=parsed.context_budget,
        )
        print(result)
        return 0
    elif parsed.format == "ddd":
        result = engine.inject(
            parsed.scene, format="ddd", max_rules=parsed.limit,
            context_budget_tokens=parsed.context_budget,
        )
        print(result)
        return 0

    matches = engine.match(parsed.scene, limit=parsed.limit)

    if not matches:
        print(f"\n  {_dim('No matching rules found for:')} {parsed.scene}")
        print()
        return 0

    print(f"\n  {_bold(f'Matching rules for:')} \"{parsed.scene}\"")
    print(f"  {'─' * 60}")

    for m in matches:
        rule = m.rule
        marker = "🔴" if rule.override else "🟡"
        print(f"  {marker} [{m.match_type}] {rule.rule_type.upper()}: {rule.action}")
        print(f"     Trigger: \"{rule.trigger}\" | Score: {m.score:.2f}")
        print()

    return 0


def cmd_delete_rule(args):
    parser = _make_parser("delete-rule")
    parser.add_argument("rule_id", help="Rule ID to delete")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    rule = engine.get_rule(parsed.rule_id)
    if not rule:
        print(f"\n  {_red(f'Rule not found:')} {parsed.rule_id}")
        return 1

    print(f"\n  Deleting rule: {rule.id}")
    print(f"    Trigger: {rule.trigger}")
    print(f"    Action:  {rule.action}")

    deleted = engine.delete_rule(parsed.rule_id)
    if deleted:
        print(f"\n  {_green('Rule deleted successfully.')}")
    else:
        print(f"\n  {_red('Failed to delete rule.')}")
    print()
    return 0


def cmd_pause_rule(args):
    parser = _make_parser("pause-rule")
    parser.add_argument("rule_id", help="Rule ID to pause")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    updated = engine.update_rule(parsed.rule_id, status="paused")
    if updated:
        print(f"\n  {_green('Rule paused:')} {updated.id}")
        print(f"    Trigger: {updated.trigger}")
    else:
        print(f"\n  {_red('Rule not found:')} {parsed.rule_id}")
    print()
    return 0


def cmd_resume_rule(args):
    parser = _make_parser("resume-rule")
    parser.add_argument("rule_id", help="Rule ID to resume")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    updated = engine.update_rule(parsed.rule_id, status="active")
    if updated:
        print(f"\n  {_green('Rule resumed:')} {updated.id}")
        print(f"    Trigger: {updated.trigger}")
    else:
        print(f"\n  {_red('Rule not found:')} {parsed.rule_id}")
    print()
    return 0


def cmd_rules_stats(args):
    parser = _make_parser("rules-stats")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    stats = engine.get_stats()

    print(f"\n  {_bold('Rules Engine Statistics')}")
    print(f"  {'─' * 40}")
    print(f"  Total rules:    {stats['total_rules']}")
    print(f"  Active rules:   {stats['active_rules']}")
    print(f"  Global rules:   {stats['global_limit']}")
    print(f"  Capacity:       {stats['total_limit']} ({stats['utilization_percent']}%)")

    if stats.get('rules_by_type'):
        print(f"\n  {_bold('By Type:')}")
        for rtype, count in stats['rules_by_type'].items():
            print(f"    {rtype}: {count}")

    if stats.get('rules_by_status'):
        print(f"\n  {_bold('By Status:')}")
        for status, count in stats['rules_by_status'].items():
            print(f"    {status}: {count}")
    print()
    return 0


def _make_parser(cmd_name: str):
    import argparse
    return argparse.ArgumentParser(
        prog=f"carrymem {cmd_name}",
        description=f"CarryMem {cmd_name} command",
    )


def cmd_check_rules(args):
    parser = _make_parser("check-rules")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    health = engine.check_health()

    if parsed.json:
        import json
        print(json.dumps(health, ensure_ascii=False, indent=2, default=str))
        return 0

    if health["is_healthy"]:
        print(f"\n  {_green('Rules Health: OK')} ✅")
    else:
        print(f"\n  {_red('Rules Health: ISSUES FOUND')} ⚠️")

    print(f"  {'─' * 40}")
    print(f"  Active rules:    {health['total_active']}")
    print(f"  Conflicts:       {health['conflicts_found']}")
    print(f"  Unused rules:    {health['unused_rules']}")
    print(f"  Global rules:    {health['global_rules']}")

    if health.get("conflicts_by_severity"):
        print(f"\n  {_bold('Conflicts by Severity:')}")
        for sev, count in health["conflicts_by_severity"].items():
            icon = "🔴" if sev == "critical" else "🟠" if sev == "high" else "🟡"
            print(f"    {icon} {sev}: {count}")

    if health.get("conflicts"):
        print(f"\n  {_bold('Conflict Details:')}")
        for detail in health["conflicts"][:5]:
            for line in detail.split("\n"):
                print(f"    {line}")

    if health["unused_rules"] > 0:
        unused_count = health["unused_rules"]
        print(f"\n  {_dim(f'💡 {unused_count} rules have never been triggered. Consider reviewing them.')}")

    print()
    return 0 if health["is_healthy"] else 1


def _validate_cli_path(path: str) -> str:
    resolved = os.path.realpath(os.path.expanduser(path))
    _DANGEROUS = [
        '/etc', '/usr', '/bin', '/sbin', '/System',
        '/Library', '/private/etc',
    ]
    for d in _DANGEROUS:
        if resolved == d or resolved.startswith(d + os.sep):
            raise ValueError(f"Path traversal: system directory not allowed: {resolved}")
    return resolved


def cmd_export_rules(args):
    parser = _make_parser("export-rules")
    parser.add_argument("path", help="Output file path (JSON)")
    parser.add_argument("--status", choices=["active", "paused", "deprecated"], help="Filter by status")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    import json

    engine = _get_rule_engine(parsed.db)
    data = engine.export_rules(status=parsed.status)

    try:
        safe_path = _validate_cli_path(parsed.path)
        with open(safe_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError) as e:
        print(f"\n  {_red(f'Write error:')} {e}")
        return 1

    print(f"\n  {_green('Exported')} {data['total_rules']} rules to {parsed.path}")
    print()
    return 0


def cmd_import_rules(args):
    parser = _make_parser("import-rules")
    parser.add_argument("path", help="Input file path (JSON)")
    parser.add_argument("--mode", choices=["skip", "overwrite", "rename"],
                        default="skip", help="Conflict resolution (default: skip)")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    import json

    try:
        safe_path = _validate_cli_path(parsed.path)
        with open(safe_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  {_red(f'File error:')} {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"\n  {_red(f'Invalid JSON:')} {e}")
        return 1

    engine = _get_rule_engine(parsed.db)

    try:
        stats = engine.import_rules(data, mode=parsed.mode)
    except ValueError as e:
        print(f"\n  {_red(f'Import error:')} {e}")
        return 1

    print(f"\n  {_green('Import complete')}")
    print(f"    Imported:    {stats['imported']}")
    print(f"    Skipped:     {stats['skipped']}")
    print(f"    Overwritten: {stats['overwritten']}")
    if stats["errors"]:
        print(f"    Errors:      {len(stats['errors'])}")
        for err in stats["errors"][:5]:
            print(f"      - {err}")
    print()
    return 0


def cmd_skill_pack(args):
    parser = _make_parser("skill-pack")
    parser.add_argument("path", help="Output file path (JSON)")
    parser.add_argument("--name", required=True, help="Skill name")
    parser.add_argument("--version", default="1.0.0", help="Semantic version")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--description", default="", help="Skill description")
    parser.add_argument("--scope", choices=["personal", "company", "negotiated"],
                        default="personal", help="Default scope (default: personal)")
    parser.add_argument("--status", choices=["active", "paused", "deprecated"],
                        help="Filter rules by status")
    parser.add_argument("--tags", nargs="*", help="Categorization tags")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    import json

    engine = _get_rule_engine(parsed.db)
    data = engine.skill_pack(
        name=parsed.name,
        version=parsed.version,
        author=parsed.author,
        description=parsed.description,
        scope=parsed.scope,
        status=parsed.status,
        tags=parsed.tags,
    )

    try:
        safe_path = _validate_cli_path(parsed.path)
        with open(safe_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError) as e:
        print(f"\n  {_red(f'Write error:')} {e}")
        return 1

    manifest = data["manifest"]
    print(f"\n  {_green('Skill packed')}: {manifest['name']} v{manifest['version']}")
    print(f"    Rules:  {manifest['rule_count']}")
    print(f"    Scope:  {manifest['scope']}")
    print(f"    Hash:   {data['signature']['hash'][:16]}...")
    print()
    return 0


def cmd_skill_install(args):
    parser = _make_parser("skill-install")
    parser.add_argument("path", help="Skill bundle file path (JSON)")
    parser.add_argument("--scope", choices=["personal", "company", "negotiated"],
                        help="Override Skill's default scope")
    parser.add_argument("--mode", choices=["skip", "overwrite", "rename"],
                        default="skip", help="Conflict resolution (default: skip)")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    import json

    try:
        safe_path = _validate_cli_path(parsed.path)
        with open(safe_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  {_red(f'File error:')} {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"\n  {_red(f'Invalid JSON:')} {e}")
        return 1

    engine = _get_rule_engine(parsed.db)

    verification = engine.skill_verify(data)
    if not verification["valid"]:
        print(f"\n  {_red(f'Verification failed')}: {verification['reason']}")
        return 1

    stats = engine.skill_install(data, scope_override=parsed.scope, mode=parsed.mode)

    if stats["errors"]:
        print(f"\n  {_yellow('Installed with errors')}")
    else:
        print(f"\n  {_green('Skill installed')}: {stats.get('skill_name', 'unknown')}")

    print(f"    Installed:    {stats['installed']}")
    print(f"    Skipped:      {stats['skipped']}")
    print(f"    Overwritten:  {stats['overwritten']}")
    print(f"    Scope:        {stats.get('scope', 'N/A')}")
    if stats["errors"]:
        print(f"    Errors:       {len(stats['errors'])}")
        for err in stats["errors"][:5]:
            print(f"      - {err}")
    print()
    return 0


def cmd_skill_verify(args):
    parser = _make_parser("skill-verify")
    parser.add_argument("path", help="Skill bundle file path (JSON)")
    parsed = parser.parse_args(args)

    import json

    try:
        with open(parsed.path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"\n  {_red(f'File not found:')} {parsed.path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"\n  {_red(f'Invalid JSON:')} {e}")
        return 1

    from carrymem.rules import RuleEngine
    result = RuleEngine.skill_verify(data)

    if result["valid"]:
        print(f"\n  {_green('Valid Skill bundle')}")
        print(f"    Name:    {result.get('name', 'unknown')}")
        print(f"    Version: {result.get('version', 'unknown')}")
        print(f"    Author:  {result.get('author', '')}")
        print(f"    Rules:   {result.get('rule_count', 0)}")
        print(f"    Scope:   {result.get('scope', 'personal')}")
        if result.get("tags"):
            print(f"    Tags:    {', '.join(result['tags'])}")
        if result.get("dependencies"):
            print(f"    Deps:    {', '.join(result['dependencies'])}")
    else:
        print(f"\n  {_red('Invalid Skill bundle')}: {result['reason']}")

    print()
    return 0 if result["valid"] else 1


def cmd_edit_rule(args):
    parser = _make_parser("edit-rule")
    parser.add_argument("rule_id", help="Rule ID to edit")
    parser.add_argument("--trigger", help="New trigger")
    parser.add_argument("--action", help="New action")
    parser.add_argument("--type", choices=["avoid", "always", "prefer", "forbid", "format"], help="New rule type")
    parser.add_argument("--soft", action="store_true", help="Change to soft rule")
    parser.add_argument("--hard", action="store_true", help="Change to hard rule")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    rule = engine.get_rule(parsed.rule_id)
    if not rule:
        print(f"\n  {_red(f'Rule not found:')} {parsed.rule_id}")
        return 1

    updates = {}
    if parsed.trigger:
        updates["trigger"] = parsed.trigger
    if parsed.action:
        updates["action"] = parsed.action
    if parsed.type:
        updates["rule_type"] = parsed.type
    if parsed.soft:
        updates["override"] = False
    if parsed.hard:
        updates["override"] = True

    if not updates:
        print(f"\n  {_yellow('No changes specified. Use --trigger, --action, --type, --soft, or --hard')}")
        return 1

    updated = engine.update_rule(parsed.rule_id, **updates)
    if updated:
        print(f"\n  {_green('Rule updated:')} {updated.id}")
        print(f"    Trigger: {updated.trigger}")
        print(f"    Action:  {updated.action}")
        print(f"    Type:    {updated.rule_type}")
        marker = "HARD" if updated.override else "SOFT"
        print(f"    Force:   {marker}")
    else:
        print(f"\n  {_red('Update failed')}")
    print()
    return 0


def cmd_list_templates(args):
    parser = _make_parser("list-templates")
    parsed = parser.parse_args(args)

    from carrymem.rules.templates import list_templates

    templates = list_templates()

    print(f"\n  {_bold(f'Rule Templates ({len(templates)} available)')}")
    print(f"  {'─' * 50}")

    for name, desc in sorted(templates.items()):
        print(f"  {_bold(name)}")
        print(f"    {desc}")
        print()

    print(f"  {_dim('Usage: carrymem add-rule --template <name>')}")
    print()
    return 0


def cmd_suggest_rules(args):
    parser = _make_parser("suggest-rules")
    parser.add_argument("--type", choices=["correction", "decision", "user_preference", "sentiment_marker", "task_pattern"],
                        help="Filter by memory type")
    parser.add_argument("--min-count", type=int, default=3, help="Minimum occurrences for pattern detection (default: 3)")
    parser.add_argument("--accept", action="store_true", help="Accept all suggestions (create rules)")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    from carrymem.carrymem import CarryMem
    from carrymem.rules import RuleEngine

    db_path = parsed.db or str(_DEFAULT_DB)
    cm = CarryMem(db_path=db_path)
    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(filters=filters if filters else None, limit=200)

    if not memories:
        print(f"\n  {_yellow('No memories found. Add memories first with:')} carrymem add <content>")
        print()
        return 0

    engine = _get_rule_engine(parsed.db)
    engine.pattern_detector.min_occurrences = parsed.min_count

    candidates = engine.suggest_rules(
        memories,
        memory_type=parsed.type,
        max_candidates=10,
    )

    if not candidates:
        print(f"\n  {_yellow('No patterns detected yet.')}")
        print(f"  {_dim('Keep adding memories. Patterns emerge after 3+ similar entries.')}")
        print()
        return 0

    print(f"\n  {_bold(f'Rule Suggestions ({len(candidates)} found)')}")
    print(f"  {'─' * 60}")

    accepted = []
    for i, cand in enumerate(candidates, 1):
        marker = _red("HARD") if cand.override else _yellow("SOFT")
        print(f"\n  {_bold(f'#{i}')} [{cand.rule_type.upper()}] {marker}")
        print(f"    Trigger: {cand.trigger}")
        print(f"    Action:  {cand.action}")
        print(f"    {_dim(f'Based on {len(cand.source_memories)} memories | Confidence: {cand.confidence:.0%}')}")
        print(f"    {_dim(cand.explanation)}")

    if parsed.accept:
        print()
        print(f"  {_yellow(f'WARNING: This will create {len(candidates)} rules. Proceed? [y/N]')}", end=" ")
        try:
            confirm = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {_yellow('Cancelled')}")
            return 0
        if confirm != "y":
            print(f"  {_yellow('Cancelled')}")
            return 0

        for cand in candidates:
            try:
                rule = engine.add_rule(
                    trigger=cand.trigger,
                    action=cand.action,
                    rule_type=cand.rule_type,
                    override=cand.override,
                    derived_from="auto_promotion",
                    source_memories=cand.source_memories,
                    confidence=cand.confidence,
                )
                accepted.append(rule)
                print(f"  {_green('Created:')} {rule.id}")
            except ValueError as e:
                print(f"  {_red(f'Skipped:')} {e}")
        print(f"\n  {_green(f'{len(accepted)} rules created from suggestions')}")
    else:
        print(f"\n  {_dim('To accept: carrymem suggest-rules --accept')}")
        print(f"  {_dim('To accept one: carrymem add-rule ACTION --trigger SCENE')}")

    print()
    return 0


def cmd_promote_rules(args):
    parser = _make_parser("promote-rules")
    parser.add_argument("--type", choices=["correction", "decision", "user_preference", "sentiment_marker", "task_pattern"],
                        help="Filter by memory type")
    parser.add_argument("--auto-accept", action="store_true", help="Auto-accept all candidates (with confirmation)")
    parser.add_argument("--expiry-days", type=int, default=7, help="Days before pending candidates expire (default: 7)")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    from carrymem.carrymem import CarryMem
    from carrymem.rules import RuleEngine

    db_path = parsed.db or str(_DEFAULT_DB)
    cm = CarryMem(db_path=db_path)
    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(filters=filters if filters else None, limit=200)

    if not memories:
        print(f"\n  {_yellow('No memories found. Add memories first.')}")
        return 0

    engine = _get_rule_engine(parsed.db)
    engine.promotion_pipeline.expiry_days = parsed.expiry_days

    result = engine.run_promotion(
        memories,
        memory_type=parsed.type,
        auto_accept=parsed.auto_accept,
    )

    print(f"\n  {_bold('Promotion Pipeline Results')}")
    print(f"  {'─' * 40}")
    print(f"  Patterns found:       {result['patterns_found']}")
    print(f"  Candidates generated: {result['candidates_generated']}")
    print(f"  Candidates queued:    {result['candidates_queued']}")
    if parsed.auto_accept:
        print(f"  Auto-accepted:        {result['candidates_auto_accepted']}")
    else:
        pending = engine.list_pending_promotions()
        if pending:
            print(f"\n  {_yellow(f'{len(pending)} pending candidates awaiting review:')}")
            print(f"  {_dim('Use: carrymem review-promotions')}")
    print()
    return 0


def cmd_review_promotions(args):
    parser = _make_parser("review-promotions")
    parser.add_argument("--accept", help="Accept a specific candidate by ID")
    parser.add_argument("--reject", help="Reject a specific candidate by ID")
    parser.add_argument("--accept-all", action="store_true", help="Accept all pending candidates (with confirmation)")
    parser.add_argument("--note", help="Add a review note")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)

    if parsed.accept:
        rule_id = engine.accept_promotion(parsed.accept, note=parsed.note)
        if rule_id:
            print(f"\n  {_green('Accepted!')} Rule created: {rule_id}")
        else:
            print(f"\n  {_red('Failed to accept. Candidate may not be pending.')}")
        return 0 if rule_id else 1

    if parsed.reject:
        ok = engine.reject_promotion(parsed.reject, note=parsed.note)
        if ok:
            print(f"\n  {_yellow('Rejected.')}")
        else:
            print(f"\n  {_red('Failed to reject. Candidate may not be pending.')}")
        return 0 if ok else 1

    if parsed.accept_all:
        pending = engine.list_pending_promotions()
        if not pending:
            print(f"\n  {_yellow('No pending candidates.')}")
            return 0
        print(f"\n  {_yellow(f'This will accept {len(pending)} candidates. Proceed? [y/N]')}", end=" ")
        try:
            confirm = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {_yellow('Cancelled')}")
            return 0
        if confirm != "y":
            print(f"  {_yellow('Cancelled')}")
            return 0
        accepted = 0
        for entry in pending:
            rule_id = engine.accept_promotion(entry.id)
            if rule_id:
                accepted += 1
        print(f"\n  {_green(f'{accepted} rules created from promotions')}")
        return 0

    pending = engine.list_pending_promotions()
    if not pending:
        print(f"\n  {_green('No pending promotion candidates.')}")
        stats = engine.get_promotion_stats()
        if stats:
            total_s = stats.get("total", 0)
            accepted_s = stats.get("accepted", 0)
            rejected_s = stats.get("rejected", 0)
            print(f"  {_dim(f'Total: {total_s} | Accepted: {accepted_s} | Rejected: {rejected_s}')}")
        return 0

    print(f"\n  {_bold(f'Pending Promotions ({len(pending)})')}")
    print(f"  {'─' * 60}")
    for entry in pending:
        print(f"\n  {_bold(entry.id)}")
        print(f"    Trigger: {entry.candidate_trigger}")
        print(f"    Action:  {entry.candidate_action}")
        print(f"    Type:    {entry.candidate_rule_type} | Confidence: {entry.confidence:.0%}")
        print(f"    {_dim(f'From {len(entry.source_memory_ids)} memories | Created: {entry.created_at[:10]}')}")
        print(f"    {_dim('Accept: carrymem review-promotions --accept ' + entry.id)}")

    print()
    return 0


def cmd_promotion_log(args):
    parser = _make_parser("promotion-log")
    parser.add_argument("--limit", type=int, default=20, help="Number of entries to show")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    log = engine.get_promotion_log(limit=parsed.limit)

    if not log:
        print(f"\n  {_yellow('No promotion history.')}")
        return 0

    print(f"\n  {_bold('Promotion Audit Log')}")
    print(f"  {'─' * 60}")
    for entry in log:
        status_colors = {
            "pending": _yellow,
            "accepted": _green,
            "rejected": _red,
            "expired": _dim,
        }
        color_fn = status_colors.get(entry.status, str)
        print(f"  {color_fn(entry.status.upper()):10s} {entry.id}")
        print(f"    {entry.candidate_trigger} → {entry.candidate_action}")
        if entry.resulting_rule_id:
            print(f"    {_dim(f'Rule: {entry.resulting_rule_id}')}")
        if entry.review_note:
            print(f"    {_dim(f'Note: {entry.review_note}')}")

    stats = engine.get_promotion_stats()
    total_s = stats.get("total", 0)
    pending_s = stats.get("pending", 0)
    accepted_s = stats.get("accepted", 0)
    rejected_s = stats.get("rejected", 0)
    expired_s = stats.get("expired", 0)
    print(f"\n  {_dim(f'Total: {total_s} | Pending: {pending_s} | Accepted: {accepted_s} | Rejected: {rejected_s} | Expired: {expired_s}')}")
    print()
    return 0


def cmd_refine_rule(args):
    parser = _make_parser("refine-rule")
    parser.add_argument("--trigger", default="", help="Rule trigger/scene (required for new session)")
    parser.add_argument("--action", default="", help="Rule action (required for new session)")
    parser.add_argument("--type", default="avoid", help="Rule type (default: avoid)")
    parser.add_argument("--answer", help="Answer to current question (for advancing session)")
    parser.add_argument("--option", help="Selected option for answer")
    parser.add_argument("--session", help="Continue existing session")
    parser.add_argument("--confirm", action="store_true", help="Confirm current session and create rule")
    parser.add_argument("--cancel", action="store_true", help="Cancel current session")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    if not parsed.session and (not parsed.trigger or not parsed.action):
        print(f"\n  {_red('Error: --trigger and --action are required for new sessions')}")
        print(f"  {_dim('Use: carrymem refine-rule --trigger <scene> --action <action>')}")
        return 1

    engine = _get_rule_engine(parsed.db)

    if parsed.session and parsed.cancel:
        success = engine.cancel_refinement(parsed.session)
        if success:
            print(f"\n  {_green('Session cancelled.')}")
        else:
            print(f"\n  {_red('Failed to cancel session.')}")
        return 0

    if parsed.session and parsed.confirm:
        result = engine.confirm_refinement(parsed.session)
        if "error" in result:
            print(f"\n  {_red(result['error'])}")
        else:
            print(f"\n  {_green('Refined rule created!')} ID: {result.get('rule_id', 'N/A')}")
            print(f"  Trigger: {result.get('trigger', '')}")
            print(f"  Action:  {result.get('action', '')}")
        return 0

    if parsed.session and parsed.answer:
        result = engine.answer_refinement(
            parsed.session, parsed.answer, selected_option=parsed.option
        )
        if "error" in result:
            print(f"\n  {_red(result['error'])}")
            return 1

        draft = result.get("refined_draft", {})
        next_q = result.get("next_question")

        print(f"\n  {_bold('Round ' + str(result.get('round', '?')))} — Phase: {result.get('phase', '?')}")
        if draft:
            print(f"  Current trigger: {draft.get('trigger', '')}")
            print(f"  Current action:  {draft.get('action', '')}")

        if next_q:
            print(f"\n  {_bold('Next Question:')} {next_q.get('question_text', '')}")
            for i, opt in enumerate(next_q.get("options", []), 1):
                print(f"    {i}. {opt}")
            answer_hint = f'carrymem refine-rule --session {parsed.session} --answer "your answer"'
            print(f"\n  {_dim(f'Answer: {answer_hint}')}")
        else:
            print(f"\n  {_yellow('Ready to confirm.')} {_dim(f'carrymem refine-rule --session {parsed.session} --confirm')}")
        print()
        return 0

    result = engine.start_refinement(
        trigger=parsed.trigger,
        action=parsed.action,
        rule_type=parsed.type,
    )

    if "error" in result:
        print(f"\n  {_red(result['error'])}")
        return 1

    session_id = result.get("session_id", "")
    specificity = result.get("specificity", {})
    question = result.get("question")

    print(f"\n  {_bold('Refinement Session Started')}")
    print(f"  {'─' * 40}")
    print(f"  Session ID: {session_id}")
    print(f"  Specificity: {specificity.get('refinement_potential', 'unknown')}")

    if question:
        print(f"\n  {_bold('Question (Round 1):')} {question.get('question_text', '')}")
        for i, opt in enumerate(question.get("options", []), 1):
            print(f"    {i}. {opt}")
        answer_hint_start = f'carrymem refine-rule --session {session_id} --answer "your answer"'
        print(f"\n  {_dim(f'Answer: {answer_hint_start}')}")
    print()
    return 0


def cmd_refinement_sessions(args):
    parser = _make_parser("refinement-sessions")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    sessions = engine.list_refinement_sessions()

    if not sessions:
        print(f"\n  {_yellow('No active refinement sessions.')}")
        print(f"  {_dim('Use: carrymem refine-rule --trigger <scene> --action <action>')}")
        return 0

    print(f"\n  {_bold('Active Refinement Sessions')} ({len(sessions)})")
    print(f"  {'─' * 60}")
    for s in sessions:
        print(f"  {_bold(s.id)} phase={s.phase} round={s.round_number}")
        print(f"    Original: {s.original_trigger} → {s.original_action}")
        print(f"    Current:  {s.current_trigger} → {s.current_action}")
        print(f"    {_dim(f'Created: {s.created_at[:19]}')}")
        continue_hint = f'carrymem refine-rule --session {s.id} --answer "..."'
        print(f"    {_dim(f'Continue: {continue_hint}')}")
    print()
    return 0


def cmd_learn_experience(args):
    parser = _make_parser("learn-experience")
    parser.add_argument("--type", choices=["correction", "decision", "user_preference",
                                           "sentiment_marker", "task_pattern", "fact_declaration"],
                        help="Filter by memory type")
    parser.add_argument("--expiry-days", type=int, default=14, help="Days before pending lessons expire (default: 14)")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    from carrymem.carrymem import CarryMem
    from carrymem.rules import RuleEngine

    db_path = parsed.db or str(_DEFAULT_DB)
    cm = CarryMem(db_path=db_path)
    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(filters=filters if filters else None, limit=200)

    if not memories:
        print(f"\n  {_yellow('No memories found. Add memories first.')}")
        return 0

    engine = _get_rule_engine(parsed.db)
    engine.experience_bridge.expiry_days = parsed.expiry_days

    result = engine.extract_failure_lessons(
        memories,
        memory_type=parsed.type,
    )

    print(f"\n  {_bold('Experience Learning Results')}")
    print(f"  {'─' * 40}")
    print(f"  Failure lessons found:    {result['lessons_found']}")
    print(f"  Candidates queued:        {result['candidates_queued']}")
    print(f"  Already processed:        {result['skipped_already_processed']}")
    pending = engine.list_pending_lessons()
    if pending:
        print(f"\n  {_yellow(f'{len(pending)} pending lessons awaiting review:')}")
        for p in pending[:5]:
            signal = p.failure_signal
            lesson_preview = p.lesson[:60] + ("..." if len(p.lesson) > 60 else "")
            print(f"    {_dim(p.id)} [{signal}] {lesson_preview}")
        if len(pending) > 5:
            print(f"    {_dim(f'... and {len(pending) - 5} more')}")
        print(f"\n  {_dim('Use: carrymem review-lessons')}")
    print()
    return 0


def cmd_review_lessons(args):
    parser = _make_parser("review-lessons")
    parser.add_argument("--accept", help="Accept a specific lesson by ID")
    parser.add_argument("--reject", help="Reject a specific lesson by ID")
    parser.add_argument("--accept-all", action="store_true", help="Accept all pending lessons")
    parser.add_argument("--trigger", help="Override trigger when accepting")
    parser.add_argument("--action", help="Override action when accepting")
    parser.add_argument("--note", help="Add a review note")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)

    if parsed.accept:
        rule_id = engine.accept_lesson(
            parsed.accept,
            note=parsed.note,
            trigger_override=parsed.trigger,
            action_override=parsed.action,
        )
        if rule_id:
            print(f"\n  {_green('Lesson accepted!')} Rule created: {rule_id}")
        else:
            print(f"\n  {_red('Failed to accept lesson. Check if ID is valid and still pending.')}")
        return 0

    if parsed.reject:
        success = engine.reject_lesson(parsed.reject, note=parsed.note)
        if success:
            print(f"\n  {_green('Lesson rejected.')}")
        else:
            print(f"\n  {_red('Failed to reject lesson. Check if ID is valid and still pending.')}")
        return 0

    if parsed.accept_all:
        pending = engine.list_pending_lessons(limit=100)
        if not pending:
            print(f"\n  {_yellow('No pending lessons to review.')}")
            return 0
        accepted_count = 0
        for entry in pending:
            rule_id = engine.accept_lesson(entry.id)
            if rule_id:
                accepted_count += 1
        print(f"\n  {_green(f'Accepted {accepted_count}/{len(pending)} lessons as rules.')}")
        return 0

    pending = engine.list_pending_lessons()
    if not pending:
        print(f"\n  {_yellow('No pending lessons to review.')}")
        print(f"  {_dim('Use: carrymem learn-experience')}")
        return 0

    print(f"\n  {_bold('Pending Failure Lessons')} ({len(pending)})")
    print(f"  {'─' * 60}")
    for entry in pending:
        signal = entry.failure_signal
        confidence = entry.confidence
        domain = entry.domain or "general"
        lesson_preview = entry.lesson[:80] + ("..." if len(entry.lesson) > 80 else "")
        trigger = entry.trigger_hint
        action = entry.action_hint

        print(f"\n  {_bold(entry.id)} [{signal}] confidence={confidence:.1f} domain={domain}")
        print(f"    Source: {entry.source_content[:100]}{'...' if len(entry.source_content) > 100 else ''}")
        print(f"    Lesson: {lesson_preview}")
        print(f"    Trigger: {trigger}")
        print(f"    Action:  {action}")
        print(f"    {_dim(f'Created: {entry.created_at[:19]}')}")
        print(f"    {_dim(f'Accept: carrymem review-lessons --accept {entry.id}')}")
        print(f"    {_dim(f'Reject: carrymem review-lessons --reject {entry.id}')}")

    print()
    return 0


def cmd_lesson_log(args):
    parser = _make_parser("lesson-log")
    parser.add_argument("--limit", type=int, default=20, help="Number of entries to show")
    parser.add_argument("--db", help="Database path")
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    entries = engine.get_lesson_log(limit=parsed.limit)

    if not entries:
        print(f"\n  {_yellow('No experience learning history.')}")
        print(f"  {_dim('Use: carrymem learn-experience')}")
        return 0

    print(f"\n  {_bold('Experience Learning Log')}")
    print(f"  {'─' * 60}")
    for entry in entries:
        status_icon = {"pending": "⏳", "accepted": "✅", "rejected": "❌", "expired": "⌛"}.get(
            entry.status, "?"
        )
        lesson_preview = entry.lesson[:60] + ("..." if len(entry.lesson) > 60 else "")
        rule_info = f" → {entry.resulting_rule_id}" if entry.resulting_rule_id else ""
        print(f"  {status_icon} {_dim(entry.id)} {lesson_preview}{rule_info}")
        print(f"     {_dim(f'{entry.status} | {entry.created_at[:19]}')}")

    stats = engine.get_lesson_stats()
    total_s = stats.get("total", 0)
    pending_s = stats.get("pending", 0)
    accepted_s = stats.get("accepted", 0)
    rejected_s = stats.get("rejected", 0)
    expired_s = stats.get("expired", 0)
    print(f"\n  {_dim(f'Total: {total_s} | Pending: {pending_s} | Accepted: {accepted_s} | Rejected: {rejected_s} | Expired: {expired_s}')}")
    print()
    return 0


def show_help():
    print(f"""
  {_bold(f'CarryMem v{__version__}')} - Your Portable AI Memory Layer

  {_dim('AI remembers you. Not the other way around.')}

  {_bold('Commands:')}
    add <message>        Store a memory
    list                 List recent memories
    search <query>       Search memories
    show <key>           View memory details
    edit <key> <text>    Edit a memory
    forget <key>         Delete a memory
    clean                Remove expired/low-quality
    export <path>        Export memories to file
    import <path>        Import memories from file
    stats                Show memory statistics
    check                Check memory quality & conflicts
    whoami               Who your AI thinks you are
    profile              Export/view your AI identity
    doctor               Run diagnostics
    setup-mcp            Configure MCP integration
    tui                  Launch terminal UI
    serve                Start MCP HTTP server
    init                 Initialize CarryMem
    version              Show version

  {_bold('Rules Engine:')}
    add-rule <action> --trigger <scene>   Create a behavioral rule
    add-rule --interactive                Guided rule creation
    add-rule --template <name>            Create from template
    list-rules                            List all rules
    match-rules <scene>                   Find rules matching a scene
    edit-rule <id>                        Edit an existing rule
    delete-rule <id>                      Delete a rule
    pause-rule <id>                       Pause a rule
    resume-rule <id>                      Resume a paused rule
    rules-stats                           Show rules statistics
    check-rules                           Check rules health & conflicts
    export-rules <path>                   Export rules to JSON
    import-rules <path>                   Import rules from JSON
    list-templates                        List available rule templates
    suggest-rules                         Analyze memories for rule suggestions
    promote-rules                         Run promotion pipeline on memories
    review-promotions                     Review and accept/reject pending promotions
    promotion-log                         View promotion audit log
    learn-experience                      Extract failure lessons from memories
    review-lessons                        Review and accept/reject pending lessons
    lesson-log                            View experience learning audit log
    refine-rule                           Start/continue a rule refinement session
    refinement-sessions                   List active refinement sessions

  {_bold('Examples:')}
    carrymem add "I prefer dark mode"
    carrymem add "test note" --force
    carrymem add "Using React" --namespace work
    carrymem search "theme"
    carrymem show cm_20260423_xxxx
    carrymem edit cm_20260423_xxxx "Updated content"
    carrymem clean --expired --dry-run
    carrymem list --type user_preference --limit 20
    carrymem export backup.json
    carrymem setup-mcp --tool cursor
    carrymem doctor --fix
    carrymem add-rule "keep within 3 pages" --trigger "writing reports" --type format
    carrymem add-rule --interactive
    carrymem add-rule --template code-review
    carrymem match-rules "competitive analysis"
    carrymem match-rules "code review" --format anchored
    carrymem match-rules "security" --format ddd
    carrymem match-rules "report" --format anchored --context-budget 500
    carrymem export-rules rules.json
    carrymem import-rules rules.json --mode overwrite
    carrymem suggest-rules
    carrymem suggest-rules --type correction --accept
    carrymem promote-rules
    carrymem review-promotions --accept promo_20260430
    carrymem promotion-log
    carrymem learn-experience
    carrymem learn-experience --type correction
    carrymem review-lessons --accept exp_20260430
    carrymem lesson-log
    carrymem refine-rule --trigger "db selection" --action "avoid MongoDB"
    carrymem refine-rule --session ref_xxx --answer "all document DBs"
    carrymem refine-rule --session ref_xxx --confirm

  {_dim('Documentation: https://github.com/lulin70/carrymem')}
""")


def main():
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)

    command = sys.argv[1]
    remaining_args = sys.argv[2:]

    commands = {
        "add": cmd_add,
        "remember": cmd_add,
        "save": cmd_add,
        "list": cmd_list,
        "ls": cmd_list,
        "search": cmd_search,
        "find": cmd_search,
        "show": cmd_show,
        "get": cmd_show,
        "edit": cmd_edit,
        "update": cmd_edit,
        "forget": cmd_forget,
        "delete": cmd_forget,
        "rm": cmd_forget,
        "clean": cmd_clean,
        "consolidate": cmd_consolidate,
        "export": cmd_export,
        "import": cmd_import,
        "stats": cmd_stats,
        "status": cmd_stats,
        "check": cmd_check,
        "whoami": cmd_whoami,
        "profile": cmd_profile,
        "doctor": cmd_doctor,
        "setup-mcp": cmd_setup_mcp,
        "init-integration": cmd_setup_mcp,
        "tui": cmd_tui,
        "serve": cmd_serve,
        "init": cmd_init,
        "tutorial": cmd_tutorial,
        "version": cmd_version,
        "--version": cmd_version,
        "-v": cmd_version,
        "add-rule": cmd_add_rule,
        "list-rules": cmd_list_rules,
        "rules": cmd_rules_hub,
        "match-rules": cmd_match_rules,
        "delete-rule": cmd_delete_rule,
        "pause-rule": cmd_pause_rule,
        "resume-rule": cmd_resume_rule,
        "rules-stats": cmd_rules_stats,
        "check-rules": cmd_check_rules,
        "export-rules": cmd_export_rules,
        "import-rules": cmd_import_rules,
        "skill-pack": cmd_skill_pack,
        "skill-install": cmd_skill_install,
        "skill-verify": cmd_skill_verify,
        "edit-rule": cmd_edit_rule,
        "list-templates": cmd_list_templates,
        "suggest-rules": cmd_suggest_rules,
        "promote-rules": cmd_promote_rules,
        "review-promotions": cmd_review_promotions,
        "promotion-log": cmd_promotion_log,
        "learn-experience": cmd_learn_experience,
        "review-lessons": cmd_review_lessons,
        "lesson-log": cmd_lesson_log,
        "refine-rule": cmd_refine_rule,
        "refinement-sessions": cmd_refinement_sessions,
        "help": lambda _: show_help(),
        "--help": lambda _: show_help(),
        "-h": lambda _: show_help(),
    }

    handler = commands.get(command)
    if handler is None:
        print(f"  {_red('Unknown command:')} {command}")
        help_tip = "Run 'carrymem help' for usage"
        print(f"  {_dim(help_tip)}")
        sys.exit(1)

    try:
        result = handler(remaining_args)
        sys.exit(result if isinstance(result, int) else 0)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except Exception as e:
        print(f"  {_red(f'Error: {e}')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
