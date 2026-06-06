"""CarryMem CLI - MCP/TUI/service commands: setup-mcp, mcp, serve, tui, tutorial."""

import sys
import subprocess
import json
from pathlib import Path

from carrymem.cli._base import *

__all__ = [
    # Public commands
    "cmd_setup_mcp", "cmd_mcp", "cmd_serve", "cmd_tui", "cmd_tutorial",
    # Private helpers (used by tests)
    "_resolve_mcp_command", "_build_mcp_server_config", "_merge_json_file",
    "_merge_claude_global_config", "_setup_mcp_project", "_setup_mcp_global",
    "_uninstall_mcp_global",
]


def _resolve_mcp_command():
    """Resolve the best command to start CarryMem MCP server.

    Prefers `carrymem mcp` if carrymem is on PATH (works across Python envs).
    Falls back to `sys.executable -m carrymem.integration.layer2_mcp`.
    """
    import shutil

    if shutil.which("carrymem"):
        return {"command": "carrymem", "args": ["mcp"]}
    return {"command": sys.executable, "args": ["-m", "carrymem.integration.layer2_mcp"]}


def _build_mcp_server_config(db_path=None):
    """Build the MCP server config entry for CarryMem.

    Args:
        db_path: Optional explicit database path. If None, uses $HOME/.carrymem/memories.db.

    Returns:
        Dict with command, args, and env fields.
    """
    cmd_info = _resolve_mcp_command()
    env = {}
    if db_path:
        env["CARRYMEM_DATA_PATH"] = db_path
    else:
        env["CARRYMEM_DATA_PATH"] = "$HOME/.carrymem/memories.db"
    return {
        "command": cmd_info["command"],
        "args": cmd_info["args"],
        "env": env,
    }


def _merge_json_file(file_path: Path, new_data: dict, force: bool = False):
    """Merge new_data into an existing JSON file, creating it if needed.

    For the mcpServers key, merges at the server level (adds/updates individual servers).
    For other keys, does a shallow merge (new values override existing).

    Args:
        file_path: Path to the JSON file.
        new_data: Data to merge in.
        force: If True, overwrite existing carrymem entry even if it exists.

    Returns:
        Tuple of (success: bool, was_updated: bool, message: str).
    """
    existing = {}
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return False, False, f"Failed to read {file_path}: {e}"

    # Check if carrymem already exists in mcpServers
    if not force and "mcpServers" in existing and "carrymem" in existing.get("mcpServers", {}):
        return True, False, "already configured"

    # Merge mcpServers
    existing.setdefault("mcpServers", {})
    if "mcpServers" in new_data:
        for server_name, server_config in new_data["mcpServers"].items():
            existing["mcpServers"][server_name] = server_config

    # Merge other top-level keys
    for key, value in new_data.items():
        if key != "mcpServers":
            existing[key] = value

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except OSError as e:
        return False, False, f"Failed to write {file_path}: {e}"

    return True, True, "configured"


def _merge_claude_global_config(new_data: dict, force: bool = False):
    """Merge MCP config into Claude Code's global config file (~/.claude.json).

    Claude Code's ~/.claude.json has a specific structure where MCP servers
    are stored under the top-level "mcpServers" key (user scope).

    Returns:
        Tuple of (success: bool, was_updated: bool, message: str).
    """
    claude_file = Path.home() / ".claude.json"
    existing = {}

    if claude_file.exists():
        try:
            with open(claude_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return False, False, f"Failed to read {claude_file}: {e}"

    # Check if carrymem already exists
    if not force and "mcpServers" in existing and "carrymem" in existing.get("mcpServers", {}):
        return True, False, "already configured"

    # Merge mcpServers at top level
    existing.setdefault("mcpServers", {})
    if "mcpServers" in new_data:
        for server_name, server_config in new_data["mcpServers"].items():
            existing["mcpServers"][server_name] = server_config

    try:
        with open(claude_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except OSError as e:
        return False, False, f"Failed to write {claude_file}: {e}"

    return True, True, "configured"


def cmd_setup_mcp(args):
    parser = _make_parser("setup-mcp")
    parser.add_argument(
        "--tool",
        "-t",
        choices=[
            "claude-code",
            "cursor",
            "trae",
            "windsurf",
            "cline",
            "openclaw",
            "kimi-code",
            "codex",
            "all",
        ],
        default="all",
        help="Target tool",
    )
    parser.add_argument("--project", "-p", default=".", help="Project directory (default: current)")
    parser.add_argument(
        "--global",
        "-g",
        dest="global_config",
        action="store_true",
        help="Write to global config (all AI tools on this machine share one CarryMem)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    parser.add_argument("--uninstall", action="store_true", help="Remove CarryMem MCP config from specified tool(s)")

    parsed = parser.parse_args(args)

    if parsed.uninstall:
        return _uninstall_mcp_global(parsed)

    if not _DEFAULT_DB.parent.exists():
        print(f"  {_dim('Initializing CarryMem for first use...')}")
        from carrymem.constants import initialize_directories

        initialize_directories()

    if parsed.global_config:
        return _setup_mcp_global(parsed)
    else:
        return _setup_mcp_project(parsed)


def _setup_mcp_project(parsed):
    """Configure MCP at project level (original behavior)."""
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
            success, updated, msg = _merge_json_file(claude_file, mcp_config, force=parsed.force)
            if success:
                print(f"  {_green('Claude Code:')} {msg} ({claude_file})")
                configured.append("claude-code")
            else:
                print(f"  {_red('Claude Code:')} {msg}")

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
            success, updated, msg = _merge_json_file(cursor_file, mcp_config, force=parsed.force)
            if success:
                print(f"  {_green('Cursor:')} {msg} ({cursor_file})")
                configured.append("cursor")
            else:
                print(f"  {_red('Cursor:')} {msg}")

    if configured:
        print(f"\n  {_green('MCP integration ready for:')} {', '.join(configured)}")
        print(f"  {_dim(f'Command: {module_cmd}')}")
        print(f"\n  {_bold('Restart your AI tool to activate CarryMem')}")
    else:
        print(f"  {_dim('No tools configured')}")

    return 0


def _setup_mcp_global(parsed):
    """Configure MCP at global level — all AI tools share one CarryMem database."""
    print(f"\n  {_bold('Configuring CarryMem for all AI tools (global)...')}\n")

    db_path = str(_DEFAULT_DB)
    mcp_config = {
        "mcpServers": {
            "carrymem": _build_mcp_server_config(db_path=None),
        }
    }

    configured = []
    failed = []

    # --- Claude Code: ~/.claude.json ---
    if parsed.tool in ("claude-code", "all"):
        success, updated, msg = _merge_claude_global_config(mcp_config, force=parsed.force)
        if success:
            claude_file = Path.home() / ".claude.json"
            print(f"  {_green('Claude Code:')} {msg} ({claude_file})")
            configured.append("claude-code")
        else:
            print(f"  {_red('Claude Code:')} {msg}")
            failed.append("claude-code")

    # --- Cursor: ~/.cursor/mcp.json ---
    if parsed.tool in ("cursor", "all"):
        cursor_file = Path.home() / ".cursor" / "mcp.json"
        success, updated, msg = _merge_json_file(cursor_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('Cursor:')} {msg} ({cursor_file})")
            configured.append("cursor")
        else:
            print(f"  {_red('Cursor:')} {msg}")
            failed.append("cursor")

    # --- TRAE: ~/.trae/mcp.json ---
    if parsed.tool in ("trae", "all"):
        trae_file = Path.home() / ".trae" / "mcp.json"
        success, updated, msg = _merge_json_file(trae_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('TRAE:')} {msg} ({trae_file})")
            configured.append("trae")
        else:
            print(f"  {_red('TRAE:')} {msg}")
            failed.append("trae")

        # Also configure TRAE-CN if the directory exists
        trae_cn_dir = Path.home() / ".trae-cn"
        if trae_cn_dir.exists():
            trae_cn_file = trae_cn_dir / "mcp.json"
            success, updated, msg = _merge_json_file(trae_cn_file, mcp_config, force=parsed.force)
            if success:
                print(f"  {_green('TRAE-CN:')} {msg} ({trae_cn_file})")
                configured.append("trae-cn")
            else:
                print(f"  {_red('TRAE-CN:')} {msg}")
                failed.append("trae-cn")

    # --- Windsurf: ~/.windsurf/mcp.json ---
    if parsed.tool in ("windsurf", "all"):
        windsurf_file = Path.home() / ".windsurf" / "mcp.json"
        success, updated, msg = _merge_json_file(windsurf_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('Windsurf:')} {msg} ({windsurf_file})")
            configured.append("windsurf")
        else:
            print(f"  {_red('Windsurf:')} {msg}")
            failed.append("windsurf")

    # --- Cline: ~/.cline/mcp.json ---
    if parsed.tool in ("cline", "all"):
        cline_file = Path.home() / ".cline" / "mcp.json"
        success, updated, msg = _merge_json_file(cline_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('Cline:')} {msg} ({cline_file})")
            configured.append("cline")
        else:
            print(f"  {_red('Cline:')} {msg}")
            failed.append("cline")

    # --- OpenClaw: same config as Claude Code ---
    if parsed.tool in ("openclaw", "all"):
        openclaw_file = Path.home() / ".openclaw" / "mcp.json"
        if not openclaw_file.parent.exists():
            openclaw_file = Path.home() / ".claude.json"
        if openclaw_file.name == ".claude.json":
            success, updated, msg = _merge_claude_global_config(mcp_config, force=parsed.force)
        else:
            success, updated, msg = _merge_json_file(openclaw_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('OpenClaw:')} {msg} ({openclaw_file})")
            configured.append("openclaw")
        else:
            print(f"  {_red('OpenClaw:')} {msg}")
            failed.append("openclaw")

    # --- Kimi Code CLI: same config as Claude Code ---
    if parsed.tool in ("kimi-code", "all"):
        kimi_file = Path.home() / ".kimi" / "mcp.json"
        if not kimi_file.parent.exists():
            kimi_file = Path.home() / ".claude.json"
        if kimi_file.name == ".claude.json":
            success, updated, msg = _merge_claude_global_config(mcp_config, force=parsed.force)
        else:
            success, updated, msg = _merge_json_file(kimi_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('Kimi Code:')} {msg} ({kimi_file})")
            configured.append("kimi-code")
        else:
            print(f"  {_red('Kimi Code:')} {msg}")
            failed.append("kimi-code")

    # --- CodeX: ~/.codex/mcp.json ---
    if parsed.tool in ("codex", "all"):
        codex_file = Path.home() / ".codex" / "mcp.json"
        if not codex_file.parent.exists():
            codex_file = Path.home() / ".claude.json"
        if codex_file.name == ".claude.json":
            success, updated, msg = _merge_claude_global_config(mcp_config, force=parsed.force)
        else:
            success, updated, msg = _merge_json_file(codex_file, mcp_config, force=parsed.force)
        if success:
            print(f"  {_green('CodeX:')} {msg} ({codex_file})")
            configured.append("codex")
        else:
            print(f"  {_red('CodeX:')} {msg}")
            failed.append("codex")

    # --- Summary ---
    print()
    print(f"  {_green('Database:')} {db_path} (shared)")

    cmd_info = _resolve_mcp_command()
    if cmd_info["command"] == "carrymem":
        print(f"  {_dim('Command: carrymem mcp (using PATH)')}")
    else:
        cmd_str = cmd_info["command"] + " " + " ".join(cmd_info["args"])
        print(f"  {_dim(f'Command: {cmd_str}')}")

    if configured:
        configured_str = ", ".join(configured)
        print(f"\n  {_green(f'Configured: {configured_str}')}")
    if failed:
        failed_str = ", ".join(failed)
        print(f"  {_red(f'Failed: {failed_str}')}")

    print(f"\n  {_bold('Restart all AI tools to activate CarryMem.')}")

    if configured:
        print(f"\n  {_dim('Verifying MCP server...')}")
        try:
            cmd_info = _resolve_mcp_command()
            result = subprocess.run(
                [cmd_info["command"]] + cmd_info["args"] + ["--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 or "carrymem" in (result.stdout + result.stderr).lower():
                print(f"  {_green('MCP server:')} ready")
            else:
                print(f"  {_yellow('MCP server:')} could not verify (non-critical)")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            print(f"  {_yellow('MCP server:')} could not verify (non-critical)")

    return 0 if not failed else 1


def _uninstall_mcp_global(parsed):
    """Remove CarryMem MCP configuration from AI tool config files."""
    print(f"\n  {_bold('Removing CarryMem MCP configuration...')}\n")

    removed = []
    not_found = []

    client_files = {
        "claude-code": ("_merge_claude_global_config", None),
        "cursor": (Path.home() / ".cursor" / "mcp.json", None),
        "trae": (Path.home() / ".trae" / "mcp.json", None),
        "windsurf": (Path.home() / ".windsurf" / "mcp.json", None),
        "cline": (Path.home() / ".cline" / "mcp.json", None),
        "openclaw": (Path.home() / ".openclaw" / "mcp.json", None),
        "kimi-code": (Path.home() / ".kimi" / "mcp.json", None),
        "codex": (Path.home() / ".codex" / "mcp.json", None),
    }

    tools_to_remove = [parsed.tool] if parsed.tool != "all" else list(client_files.keys())

    for tool in tools_to_remove:
        if tool not in client_files:
            continue

        entry = client_files[tool]

        if tool == "claude-code":
            claude_file = Path.home() / ".claude.json"
            if claude_file.exists():
                try:
                    with open(claude_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "mcpServers" in data and "carrymem" in data.get("mcpServers", {}):
                        del data["mcpServers"]["carrymem"]
                        with open(claude_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        print(f"  {_green('Claude Code:')} removed ({claude_file})")
                        removed.append("claude-code")
                    else:
                        print(f"  {_dim('Claude Code: not configured')} ({claude_file})")
                        not_found.append("claude-code")
                except (json.JSONDecodeError, OSError) as e:
                    print(f"  {_red('Claude Code:')} failed - {e}")
                    not_found.append("claude-code")
            else:
                print(f"  {_dim('Claude Code: config not found')}")
                not_found.append("claude-code")
        else:
            config_file = entry[0] if isinstance(entry[0], Path) else entry
            if isinstance(config_file, Path) and config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "mcpServers" in data and "carrymem" in data.get("mcpServers", {}):
                        del data["mcpServers"]["carrymem"]
                        with open(config_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        tool_display = tool.replace("-", " ").title()
                        print(f"  {_green(f'{tool_display}:')} removed ({config_file})")
                        removed.append(tool)
                    else:
                        tool_display = tool.replace("-", " ").title()
                        print(f"  {_dim(f'{tool_display}: not configured')} ({config_file})")
                        not_found.append(tool)
                except (json.JSONDecodeError, OSError) as e:
                    tool_display = tool.replace("-", " ").title()
                    print(f"  {_red(f'{tool_display}:')} failed - {e}")
                    not_found.append(tool)
            else:
                tool_display = tool.replace("-", " ").title()
                print(f"  {_dim(f'{tool_display}: config not found')}")
                not_found.append(tool)

    if removed:
        print(f"\n  {_green(f'Removed from: {', '.join(removed)}')}")
    if not_found:
        print(f"  {_dim(f'Not configured: {', '.join(not_found)}')}")
    print(f"\n  {_bold('Restart AI tools to apply changes.')}")

    return 0


def cmd_mcp(args):
    """Start CarryMem MCP Server (stdio transport)."""
    import asyncio
    from carrymem.integration.layer2_mcp.server import MCPServer

    server = MCPServer()
    asyncio.run(server.start())
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
        print("  Then run: carrymem tui")
        return 1

    parser = _make_parser("tui")
    parser.add_argument("--namespace", "-n", default="default", help="Namespace")
    parser.add_argument("--db", help="Database path")

    parsed = parser.parse_args(args)
    run_tui(db_path=parsed.db, namespace=parsed.namespace)  # type: ignore[call-arg]
    return 0


def cmd_tutorial(args):
    if args and args[0] in ("--help", "-h"):
        print("  Usage: carrymem tutorial")
        print("  Show a 5-minute quick-start guide for CarryMem.")
        return 0
    print(
        f"""
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
    carrymem          See what your AI knows about you
    carrymem doctor          Run diagnostics
    carrymem help            Full command reference
"""
    )
    return 0
