# Re-export everything from submodules for backward compatibility
from carrymem.cli._backup import *
from carrymem.cli._base import *
from carrymem.cli._io import *
from carrymem.cli._mcp import *
from carrymem.cli._memory import *
from carrymem.cli._rules import *
from carrymem.cli._stats import *
from carrymem.errors import CarryMemError


def show_help():
    """Print the CLI help text listing all available commands."""
    print(f"""
  {_bold(f'CarryMem v{__version__}')} - Your Portable AI Memory Layer

  {_dim(_t('cli.section.tagline'))}

  {_bold(_t('cli.section.commands'))}
    add <message>        {_t('cli.cmd.add')}
    list                 {_t('cli.cmd.list')}
    search <query>       {_t('cli.cmd.search')}
    show <key>           {_t('cli.cmd.show')}
    edit <key> <text>    {_t('cli.cmd.edit')}
    forget <key>         {_t('cli.cmd.forget')}
    clean                {_t('cli.cmd.clean')}
    backup               {_t('cli.cmd.backup')}
    export <path>        {_t('cli.cmd.export')}
    import <path>        {_t('cli.cmd.import')}
    pack                 {_t('cli.cmd.pack')}
    unpack <file.carry>  {_t('cli.cmd.unpack')}
    stats                {_t('cli.cmd.stats')}
    check                {_t('cli.cmd.check')}
    whoami               {_t('cli.cmd.whoami')}
    profile              {_t('cli.cmd.profile')}
    doctor               {_t('cli.cmd.doctor')}
    setup-mcp            {_t('cli.cmd.setup_mcp')}
    setup-mcp --global   Configure MCP for all tools (global)
    mcp                  {_t('cli.cmd.mcp')}
    tui                  {_t('cli.cmd.tui')}
    serve                {_t('cli.cmd.serve')}
    init                 {_t('cli.cmd.init')}
    version              {_t('cli.cmd.version')}

  {_bold('Rules Engine:')}
    rules add <action> --trigger <scene>   Create a behavioral rule
    rules add --interactive                Guided rule creation
    rules add --template <name>            Create from template
    rules list                             List all rules
    rules match <scene>                    Find rules matching a scene
    rules edit <id>                        Edit an existing rule
    rules delete <id>                      Delete a rule
    rules pause <id>                       Pause a rule
    rules resume <id>                      Resume a paused rule
    rules stats                            Show rules statistics
    rules check                            Check rules health & conflicts
    rules export <path>                    Export rules to JSON
    rules import <path>                    Import rules from JSON
    rules templates                        List available rule templates
    rules suggest                          Analyze memories for rule suggestions
    rules promote                          Run promotion pipeline on memories
    rules review-promotions                Review and accept/reject pending promotions
    rules promotion-log                    View promotion audit log
    rules learn                            Extract failure lessons from memories
    rules review-lessons                   Review and accept/reject pending lessons
    rules lesson-log                       View experience learning audit log
    rules refine                           Start/continue a rule refinement session
    rules refinement-sessions              List active refinement sessions

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
    carrymem rules add "keep within 3 pages" --trigger "writing reports" --type format
    carrymem rules add --interactive
    carrymem rules add --template code-review
    carrymem rules match "competitive analysis"
    carrymem rules match "code review" --format anchored
    carrymem rules match "security" --format ddd
    carrymem rules match "report" --format anchored --context-budget 500
    carrymem rules export rules.json
    carrymem rules import rules.json --mode overwrite
    carrymem rules suggest
    carrymem rules suggest --type correction --accept
    carrymem rules promote
    carrymem rules review-promotions --accept promo_20260430
    carrymem rules promotion-log
    carrymem rules learn
    carrymem rules learn --type correction
    carrymem rules review-lessons --accept exp_20260430
    carrymem rules lesson-log
    carrymem rules refine --trigger "db selection" --action "avoid MongoDB"
    carrymem rules refine --session ref_xxx --answer "all document DBs"
    carrymem rules refine --session ref_xxx --confirm

  {_dim('Documentation: https://github.com/lulin70/carrymem')}
""")


def main():
    """Dispatch a CLI command from sys.argv."""
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
        "add-rule": cmd_add_rule_deprecated,
        "list-rules": cmd_list_rules_deprecated,
        "rules": cmd_rules_hub,
        "match-rules": cmd_match_rules_deprecated,
        "delete-rule": cmd_delete_rule_deprecated,
        "pause-rule": cmd_pause_rule_deprecated,
        "resume-rule": cmd_resume_rule_deprecated,
        "rules-stats": cmd_rules_stats_deprecated,
        "check-rules": cmd_check_rules_deprecated,
        "export-rules": cmd_export_rules_deprecated,
        "import-rules": cmd_import_rules_deprecated,
        "skill-pack": cmd_skill_pack,
        "skill-install": cmd_skill_install,
        "skill-verify": cmd_skill_verify,
        "edit-rule": cmd_edit_rule_deprecated,
        "list-templates": cmd_list_templates_deprecated,
        "suggest-rules": cmd_suggest_rules_deprecated,
        "promote-rules": cmd_promote_rules_deprecated,
        "review-promotions": cmd_review_promotions_deprecated,
        "promotion-log": cmd_promotion_log_deprecated,
        "learn-experience": cmd_learn_experience_deprecated,
        "review-lessons": cmd_review_lessons_deprecated,
        "lesson-log": cmd_lesson_log_deprecated,
        "refine-rule": cmd_refine_rule_deprecated,
        "refinement-sessions": cmd_refinement_sessions_deprecated,
        "help": lambda _: show_help(),
        "--help": lambda _: show_help(),
        "-h": lambda _: show_help(),
    }

    handler = commands.get(command)
    if handler is None:
        print(f"  {_red(_t('cli.error.unknown_command', command=command))}")
        help_tip = "Run 'carrymem help' for usage"
        print(f"  {_dim(help_tip)}")
        sys.exit(1)

    try:
        result = handler(remaining_args)
        sys.exit(result if isinstance(result, int) else 0)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except CarryMemError as e:
        print(f"  {_red(f'[ERROR] {e.code}')}")
        print(f"  {e.message}")
        if e.hint:
            print(f"  {_dim(f'💡 {e.hint}')}")
        sys.exit(1)
    # NOTE: Broad exception at CLI top-level is intentional to catch all unhandled errors
    # and convert them to user-friendly CarryMemError messages. This is the final safety net
    # to prevent raw tracebacks from reaching end users.
    except Exception as e:
        friendly = CarryMemError.from_cause(e)
        print(f"  {_red(f'[ERROR] {friendly.code}')}")
        print(f"  {friendly.message}")
        if friendly.hint:
            print(f"  {_dim(f'💡 {friendly.hint}')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
