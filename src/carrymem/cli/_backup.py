"""CarryMem CLI - Backup and initialization commands: backup, init, version."""

import json
import os
import sys

from carrymem.cli._base import *


def cmd_backup(args):
    """Manage CarryMem database backups."""
    parser = _make_parser("backup")
    parser.add_argument("--list", action="store_true", help="List all backups")
    parser.add_argument("--restore", help="Restore from a backup file")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    if parsed.list:
        backups = cm.list_backups()
        if not backups:
            print(f"  {_dim('No backups found')}")
            cm.close()
            return 0

        print(f"\n  {_bold('CarryMem Backups')} ({len(backups)} found)\n")
        for i, b in enumerate(backups, 1):
            filename = b.get("filename", "")
            size_kb = b.get("size_kb", 0)
            created = b.get("created_at", "")
            mem_count = b.get("memory_count", "N/A")
            path = b.get("path", "")

            if size_kb >= 1024:
                size_str = f"{size_kb / 1024:.1f} MB"
            else:
                size_str = f"{size_kb:.1f} KB"

            print(f"  {i}. {_bold(filename)}")
            print(f"     Size: {size_str} | Memories: {mem_count} | {_format_time(created)}")
            print(f"     {_dim(path)}")
            print()

        cm.close()
        return 0

    if parsed.restore:
        backup_path = parsed.restore
        if not os.path.isabs(backup_path):
            # Try to match against known backup filenames
            backups = cm.list_backups()
            matched = [b for b in backups if b.get("filename") == backup_path or b.get("path") == backup_path]
            if matched:
                backup_path = matched[0]["path"]
            else:
                print(f"  {_red('Backup not found:')} {parsed.restore}")
                print(f"  {_dim('Use --list to see available backups')}")
                cm.close()
                return 1

        print(f"  {_yellow('WARNING:')} This will replace your current database with the backup.")
        print(f"  Backup: {backup_path}")
        try:
            answer = input("  Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            cm.close()
            return 0

        if answer != "y":
            print(f"  {_dim('Cancelled')}")
            cm.close()
            return 0

        result = cm.restore_backup(backup_path)
        if result.get("restored"):
            print(f"  {_green('Restored from backup:')} {backup_path}")
        else:
            print(f"  {_red('Restore failed:')} {result.get('error', 'unknown error')}")
            cm.close()
            return 1

        cm.close()
        return 0

    # Default: create a backup
    result = cm.backup()
    if result.get("backed_up"):
        print(f"  {_green('Backup created:')} {result['path']}")
    else:
        print(f"  {_red('Backup failed:')} {result.get('error', 'unknown error')}")
        cm.close()
        return 1

    cm.close()
    return 0


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
    print('    carrymem add "I prefer dark mode"')
    print("    carrymem list")
    print('    carrymem search "theme"')
    print("    carrymem setup-mcp --tool cursor")
    print("    carrymem tui")
    print()
    return 0


def cmd_version(args):
    print(f"\n  {_bold(f'CarryMem v{__version__}')}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Config: {_DEFAULT_CONFIG_DIR}")
    print(f"  Database: {_DEFAULT_DB}")
    print()
    return 0
