# Re-export everything from submodules for backward compatibility
from carrymem.cli._backup import *
from carrymem.cli._base import *
from carrymem.cli._io import *
from carrymem.cli._mcp import *
from carrymem.cli._memory import *
from carrymem.cli._rules import *
from carrymem.cli._stats import *


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
    backup               Create/list/restore backups
    export <path>        Export memories to file
    import <path>        Import memories from file
    pack                 Pack identity into .carry file
    unpack <file.carry>  Unpack .carry file to restore identity
    stats                Show memory statistics
    check                Check memory quality & conflicts
    whoami               Who your AI thinks you are
    profile              Export/view your AI identity
    doctor               Run diagnostics
    setup-mcp            Configure MCP integration
    setup-mcp --global   Configure MCP for all tools (global)
    mcp                  Start MCP server (stdio)
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
    carrymem pack
    carrymem pack --output my_identity.carry
    carrymem unpack carrymem_identity_20260526.carry
    carrymem unpack backup.carry --replace
    carrymem setup-mcp --tool cursor
    carrymem setup-mcp --global
    carrymem setup-mcp --global --tool trae
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
        "backup": cmd_backup,
        "export": cmd_export,
        "import": cmd_import,
        "pack": cmd_pack,
        "unpack": cmd_unpack,
        "stats": cmd_stats,
        "status": cmd_stats,
        "check": cmd_check,
        "whoami": cmd_whoami,
        "profile": cmd_profile,
        "doctor": cmd_doctor,
        "setup-mcp": cmd_setup_mcp,
        "init-integration": cmd_setup_mcp,
        "mcp": cmd_mcp,
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
