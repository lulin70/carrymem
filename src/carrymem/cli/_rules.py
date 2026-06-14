"""CarryMem CLI - Rules engine commands (~26 functions)."""

import json

from carrymem.cli._base import *


def _deprecated_wrapper(old_cmd, new_sub, handler):
    """Create a wrapper that prints a deprecation notice and delegates to the handler."""

    def wrapper(args):
        print(f"  {_yellow(f'[DEPRECATED]')} {_dim(f'Use `carrymem rules {new_sub}` instead of `carrymem {old_cmd}`')}")
        return handler(args)

    return wrapper


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
        "templates": cmd_list_templates,
        "suggest": cmd_suggest_rules,
        "promote": cmd_promote_rules,
        "review-promotions": cmd_review_promotions,
        "promotion-log": cmd_promotion_log,
        "learn": cmd_learn_experience,
        "review-lessons": cmd_review_lessons,
        "lesson-log": cmd_lesson_log,
        "refine": cmd_refine_rule,
        "refinement-sessions": cmd_refinement_sessions,
    }

    sub = args[0]
    sub_args = args[1:]
    handler = sub_commands.get(sub)
    if handler:
        return handler(sub_args)

    print(f"  {_red('Unknown rules sub-command:')} {sub}")
    _available = _dim(
        "Available: list, add, delete, match, edit, pause, resume, stats, check, "
        "export, import, templates, suggest, promote, learn, refine"
    )
    print(f"  {_available}")
    return 1


# Deprecated wrappers — old flat commands still work but warn
cmd_add_rule_deprecated = _deprecated_wrapper("add-rule", "add", lambda a: cmd_add_rule(a))
cmd_list_rules_deprecated = _deprecated_wrapper("list-rules", "list", lambda a: cmd_list_rules(a))
cmd_match_rules_deprecated = _deprecated_wrapper("match-rules", "match", lambda a: cmd_match_rules(a))
cmd_edit_rule_deprecated = _deprecated_wrapper("edit-rule", "edit", lambda a: cmd_edit_rule(a))
cmd_delete_rule_deprecated = _deprecated_wrapper("delete-rule", "delete", lambda a: cmd_delete_rule(a))
cmd_pause_rule_deprecated = _deprecated_wrapper("pause-rule", "pause", lambda a: cmd_pause_rule(a))
cmd_resume_rule_deprecated = _deprecated_wrapper("resume-rule", "resume", lambda a: cmd_resume_rule(a))
cmd_rules_stats_deprecated = _deprecated_wrapper("rules-stats", "stats", lambda a: cmd_rules_stats(a))
cmd_check_rules_deprecated = _deprecated_wrapper("check-rules", "check", lambda a: cmd_check_rules(a))
cmd_export_rules_deprecated = _deprecated_wrapper("export-rules", "export", lambda a: cmd_export_rules(a))
cmd_import_rules_deprecated = _deprecated_wrapper("import-rules", "import", lambda a: cmd_import_rules(a))
cmd_list_templates_deprecated = _deprecated_wrapper("list-templates", "templates", lambda a: cmd_list_templates(a))
cmd_suggest_rules_deprecated = _deprecated_wrapper("suggest-rules", "suggest", lambda a: cmd_suggest_rules(a))
cmd_promote_rules_deprecated = _deprecated_wrapper("promote-rules", "promote", lambda a: cmd_promote_rules(a))
cmd_review_promotions_deprecated = _deprecated_wrapper("review-promotions", "review-promotions", lambda a: cmd_review_promotions(a))
cmd_promotion_log_deprecated = _deprecated_wrapper("promotion-log", "promotion-log", lambda a: cmd_promotion_log(a))
cmd_learn_experience_deprecated = _deprecated_wrapper("learn-experience", "learn", lambda a: cmd_learn_experience(a))
cmd_review_lessons_deprecated = _deprecated_wrapper("review-lessons", "review-lessons", lambda a: cmd_review_lessons(a))
cmd_lesson_log_deprecated = _deprecated_wrapper("lesson-log", "lesson-log", lambda a: cmd_lesson_log(a))
cmd_refine_rule_deprecated = _deprecated_wrapper("refine-rule", "refine", lambda a: cmd_refine_rule(a))
cmd_refinement_sessions_deprecated = _deprecated_wrapper("refinement-sessions", "refinement-sessions", lambda a: cmd_refinement_sessions(a))


def cmd_add_rule(args):
    parser = _make_parser("add-rule")
    parser.add_argument("action", nargs="?", help=_t("cli.arg.rules.action"))
    parser.add_argument("--trigger", "-t", help=_t("cli.arg.rules.trigger"))
    parser.add_argument(
        "--type",
        choices=["avoid", "always", "prefer", "forbid", "format"],
        default=None,
        help=_t("cli.arg.rules.type"),
    )
    parser.add_argument("--soft", action="store_true", help=_t("cli.arg.rules.soft"))
    parser.add_argument("--template", help=_t("cli.arg.rules.template"))
    parser.add_argument("--interactive", "-i", action="store_true", help=_t("cli.arg.rules.interactive"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
            print("    1) avoid   — Avoid doing something")
            print("    2) always  — Always do this")
            print("    3) prefer  — Prefer this approach")
            print("    4) forbid  — Never do this")
            print("    5) format  — Format output this way")
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
            _usage_hint = _red("Missing required arguments. Use:")
            print(f"\n  {_usage_hint} carrymem rules add <action> --trigger <scene>")
            print(f"  {_dim('Or use:')} carrymem rules add --interactive")
            print(f"  {_dim('Or use:')} carrymem rules add --template <name>")
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
    parser.add_argument("--status", choices=["active", "paused", "deprecated"], help=_t("cli.arg.rules.filter_status"))
    parser.add_argument("--type", choices=["avoid", "always", "prefer", "forbid", "format"], help=_t("cli.arg.rules.filter_type"))
    parser.add_argument("--limit", type=int, default=20, help=_t("cli.arg.rules.limit_20"))
    parser.add_argument("--format", choices=["detail", "table", "compact"], default="detail", help=_t("cli.arg.rules.format"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    rules = engine.list_rules(status=parsed.status, rule_type=parsed.type, limit=parsed.limit)

    if not rules:
        print(f"\n  {_dim('No rules found.')}")
        print("  Create one with: carrymem rules add <action> --trigger <scene>")
        print()
        return 0

    if parsed.format == "compact":
        for rule in rules:
            marker = "!" if rule.override else "~"
            expired = " [EXPIRED]" if rule.is_expired() else ""
            print(f"[{marker}] ({rule.scope}/{rule.rule_type}) {rule.trigger} → {rule.action}{expired}")
        return 0

    if parsed.format == "table":
        _header = f"\n  {'ID':<14} {'Type':<8} {'Scope':<10} {'Override':<8} {'Trigger':<20} {'Action':<30}"
        print(_header)
        print(f"  {'─'*14} {'─'*8} {'─'*10} {'─'*8} {'─'*20} {'─'*30}")
        for rule in rules:
            expired = " [EXPIRED]" if rule.is_expired() else ""
            override_str = "HARD" if rule.override else "soft"
            _row = (
                f"  {rule.id:<14} {rule.rule_type:<8} {rule.scope:<10} "
                f"{override_str:<8} {rule.trigger[:20]:<20} "
                f"{rule.action[:30]:<30}{expired}"
            )
            print(_row)
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
        expired_str = " \u26a0\ufe0f EXPIRED" if rule.is_expired() else ""
        print(f"  {icon} {marker} {_bold(rule.id)}{status_str}{expired_str}")
        print(f"     Trigger: {rule.trigger}")
        print(f"     Action:  {rule.action}")
        _stats = f"     Type: {rule.rule_type} | Used: {rule.trigger_count}x | Confidence: {rule.confidence:.0%}"
        print(_stats)
        if rule.expires_at:
            print(f"     Expires: {rule.expires_at}")
        print()

    return 0


def cmd_match_rules(args):
    parser = _make_parser("match-rules")
    parser.add_argument("scene", help=_t("cli.arg.rules.scene"))
    parser.add_argument("--limit", type=int, default=5, help=_t("cli.arg.rules.limit_5"))
    parser.add_argument(
        "--format",
        choices=["text", "json", "compact", "anchored", "ddd"],
        default="text",
        help=_t("cli.arg.rules.format"),
    )
    parser.add_argument(
        "--context-budget",
        type=int,
        default=None,
        help=_t("cli.arg.rules.context_budget"),
    )
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
            parsed.scene,
            format="anchored",
            max_rules=parsed.limit,
            context_budget_tokens=parsed.context_budget,
        )
        print(result)
        return 0
    elif parsed.format == "ddd":
        result = engine.inject(
            parsed.scene,
            format="ddd",
            max_rules=parsed.limit,
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
        print(f'     Trigger: "{rule.trigger}" | Score: {m.score:.2f}')
        print()

    return 0


def cmd_delete_rule(args):
    parser = _make_parser("delete-rule")
    parser.add_argument("rule_id", help=_t("cli.arg.rules.rule_id_delete"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("rule_id", help=_t("cli.arg.rules.rule_id_pause"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("rule_id", help=_t("cli.arg.rules.rule_id_resume"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    stats = engine.get_stats()

    print(f"\n  {_bold('Rules Engine Statistics')}")
    print(f"  {'─' * 40}")
    print(f"  Total rules:    {stats['total_rules']}")
    print(f"  Active rules:   {stats['active_rules']}")
    print(f"  Global rules:   {stats['global_limit']}")
    print(f"  Capacity:       {stats['total_limit']} ({stats['utilization_percent']}%)")

    if stats.get("rules_by_type"):
        print(f"\n  {_bold('By Type:')}")
        for rtype, count in stats["rules_by_type"].items():
            print(f"    {rtype}: {count}")

    if stats.get("rules_by_status"):
        print(f"\n  {_bold('By Status:')}")
        for status, count in stats["rules_by_status"].items():
            print(f"    {status}: {count}")
    print()
    return 0


def cmd_check_rules(args):
    parser = _make_parser("check-rules")
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--json", action="store_true", help=_t("cli.arg.rules.json"))
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    health = engine.check_health()

    if parsed.json:
        import json

        print(json.dumps(health, ensure_ascii=False, indent=2, default=str))
        return 0

    if health["is_healthy"]:
        print(f"\n  {_green('Rules Health: OK')} \u2705")
    else:
        print(f"\n  {_red('Rules Health: ISSUES FOUND')} \u26a0\ufe0f")

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
        _hint = _dim(f"💡 {unused_count} rules have never been triggered. Consider reviewing them.")
        print(f"\n  {_hint}")

    print()
    return 0 if health["is_healthy"] else 1


def cmd_export_rules(args):
    parser = _make_parser("export-rules")
    parser.add_argument("path", help=_t("cli.arg.rules.output_path"))
    parser.add_argument("--status", choices=["active", "paused", "deprecated"], help=_t("cli.arg.rules.filter_status"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("path", help=_t("cli.arg.rules.input_path"))
    parser.add_argument(
        "--mode",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help=_t("cli.arg.rules.mode"),
    )
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("path", help=_t("cli.arg.rules.output_path"))
    parser.add_argument("--name", required=True, help=_t("cli.arg.rules.skill_name"))
    parser.add_argument("--version", default="1.0.0", help=_t("cli.arg.rules.version"))
    parser.add_argument("--author", default="", help=_t("cli.arg.rules.author"))
    parser.add_argument("--description", default="", help=_t("cli.arg.rules.description"))
    parser.add_argument(
        "--scope",
        choices=["personal", "company", "negotiated"],
        default="personal",
        help=_t("cli.arg.rules.scope_default"),
    )
    parser.add_argument("--status", choices=["active", "paused", "deprecated"], help=_t("cli.arg.rules.filter_rules_status"))
    parser.add_argument("--tags", nargs="*", help=_t("cli.arg.rules.tags"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("path", help=_t("cli.arg.rules.skill_path"))
    parser.add_argument(
        "--scope",
        choices=["personal", "company", "negotiated"],
        help=_t("cli.arg.rules.scope_override"),
    )
    parser.add_argument(
        "--mode",
        choices=["skip", "overwrite", "rename"],
        default="skip",
        help=_t("cli.arg.rules.mode"),
    )
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
    parser.add_argument("path", help=_t("cli.arg.rules.skill_path"))
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
    parser.add_argument("rule_id", help=_t("cli.arg.rules.rule_id_edit"))
    parser.add_argument("--trigger", help=_t("cli.arg.rules.new_trigger"))
    parser.add_argument("--action", help=_t("cli.arg.rules.new_action"))
    parser.add_argument("--type", choices=["avoid", "always", "prefer", "forbid", "format"], help=_t("cli.arg.rules.new_type"))
    parser.add_argument("--soft", action="store_true", help=_t("cli.arg.rules.change_soft"))
    parser.add_argument("--hard", action="store_true", help=_t("cli.arg.rules.change_hard"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
        _no_changes = _yellow("No changes specified. Use --trigger, --action, --type, --soft, or --hard")
        print(f"\n  {_no_changes}")
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
    parser.parse_args(args)

    from carrymem.rules.templates import list_templates

    templates = list_templates()

    print(f"\n  {_bold(f'Rule Templates ({len(templates)} available)')}")
    print(f"  {'─' * 50}")

    for name, desc in sorted(templates.items()):
        print(f"  {_bold(name)}")
        print(f"    {desc}")
        print()

    print(f"  {_dim('Usage: carrymem rules add --template <name>')}")
    print()
    return 0


def cmd_suggest_rules(args):
    parser = _make_parser("suggest-rules")
    parser.add_argument(
        "--type",
        choices=["correction", "decision", "user_preference", "sentiment_marker", "task_pattern"],
        help=_t("cli.arg.rules.filter_memory_type"),
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=3,
        help=_t("cli.arg.rules.min_count"),
    )
    parser.add_argument("--accept", action="store_true", help=_t("cli.arg.rules.accept_suggestions"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    from carrymem.carrymem import CarryMem

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
        print(
            f"  {_yellow(f'WARNING: This will create {len(candidates)} rules. Proceed? [y/N]')}",
            end=" ",
        )
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
        print(f"\n  {_dim('To accept: carrymem rules suggest --accept')}")
        print(f"  {_dim('To accept one: carrymem rules add ACTION --trigger SCENE')}")

    print()
    return 0


def cmd_promote_rules(args):
    parser = _make_parser("promote-rules")
    parser.add_argument(
        "--type",
        choices=["correction", "decision", "user_preference", "sentiment_marker", "task_pattern"],
        help=_t("cli.arg.rules.filter_memory_type"),
    )
    parser.add_argument("--auto-accept", action="store_true", help=_t("cli.arg.rules.auto_accept"))
    parser.add_argument(
        "--expiry-days",
        type=int,
        default=7,
        help=_t("cli.arg.rules.expiry_days_7"),
    )
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    from carrymem.carrymem import CarryMem

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
            print(f"  {_dim('Use: carrymem rules review-promotions')}")
    print()
    return 0


def cmd_review_promotions(args):
    parser = _make_parser("review-promotions")
    parser.add_argument("--accept", help=_t("cli.arg.rules.accept_candidate"))
    parser.add_argument("--reject", help=_t("cli.arg.rules.reject_candidate"))
    parser.add_argument(
        "--accept-all",
        action="store_true",
        help=_t("cli.arg.rules.accept_all_candidates"),
    )
    parser.add_argument("--note", help=_t("cli.arg.rules.review_note"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
        print(f"    {_dim(f'Accept: carrymem rules review-promotions --accept ' + entry.id)}")

    print()
    return 0


def cmd_promotion_log(args):
    parser = _make_parser("promotion-log")
    parser.add_argument("--limit", type=int, default=20, help=_t("cli.arg.rules.limit_entries"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
        print(f"    {entry.candidate_trigger} \u2192 {entry.candidate_action}")
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
    _summary = _dim(
        f"Total: {total_s} | Pending: {pending_s} | "
        f"Accepted: {accepted_s} | Rejected: {rejected_s} | "
        f"Expired: {expired_s}"
    )
    print(f"\n  {_summary}")
    print()
    return 0


def cmd_refine_rule(args):
    parser = _make_parser("refine-rule")
    parser.add_argument("--trigger", default="", help=_t("cli.arg.rules.refine_trigger"))
    parser.add_argument("--action", default="", help=_t("cli.arg.rules.refine_action"))
    parser.add_argument("--type", default="avoid", help=_t("cli.arg.rules.refine_type"))
    parser.add_argument("--answer", help=_t("cli.arg.rules.answer"))
    parser.add_argument("--option", help=_t("cli.arg.rules.option"))
    parser.add_argument("--session", help=_t("cli.arg.rules.session"))
    parser.add_argument("--confirm", action="store_true", help=_t("cli.arg.rules.confirm"))
    parser.add_argument("--cancel", action="store_true", help=_t("cli.arg.rules.cancel"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    if not parsed.session and (not parsed.trigger or not parsed.action):
        print(f"\n  {_red('Error: --trigger and --action are required for new sessions')}")
        print(f"  {_dim('Use: carrymem rules refine --trigger <scene> --action <action>')}")
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
        result = engine.answer_refinement(parsed.session, parsed.answer, selected_option=parsed.option)
        if "error" in result:
            print(f"\n  {_red(result['error'])}")
            return 1

        draft = result.get("refined_draft", {})
        next_q = result.get("next_question")

        print(f"\n  {_bold('Round ' + str(result.get('round', '?')))} \u2014 Phase: {result.get('phase', '?')}")
        if draft:
            print(f"  Current trigger: {draft.get('trigger', '')}")
            print(f"  Current action:  {draft.get('action', '')}")

        if next_q:
            print(f"\n  {_bold('Next Question:')} {next_q.get('question_text', '')}")
            for i, opt in enumerate(next_q.get("options", []), 1):
                print(f"    {i}. {opt}")
            answer_hint = f'carrymem rules refine --session {parsed.session} --answer "your answer"'
            print(f"\n  {_dim(f'Answer: {answer_hint}')}")
        else:
            _ready_msg = _yellow("Ready to confirm.")
            _confirm_cmd = _dim(f"carrymem rules refine --session {parsed.session} --confirm")
            print(f"\n  {_ready_msg} {_confirm_cmd}")
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
        answer_hint_start = f'carrymem rules refine --session {session_id} --answer "your answer"'
        print(f"\n  {_dim(f'Answer: {answer_hint_start}')}")
    print()
    return 0


def cmd_refinement_sessions(args):
    parser = _make_parser("refinement-sessions")
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    sessions = engine.list_refinement_sessions()

    if not sessions:
        print(f"\n  {_yellow('No active refinement sessions.')}")
        print(f"  {_dim('Use: carrymem rules refine --trigger <scene> --action <action>')}")
        return 0

    print(f"\n  {_bold('Active Refinement Sessions')} ({len(sessions)})")
    print(f"  {'─' * 60}")
    for s in sessions:
        print(f"  {_bold(s.id)} phase={s.phase} round={s.round_number}")
        print(f"    Original: {s.original_trigger} \u2192 {s.original_action}")
        print(f"    Current:  {s.current_trigger} \u2192 {s.current_action}")
        print(f"    {_dim(f'Created: {s.created_at[:19]}')}")
        continue_hint = f'carrymem rules refine --session {s.id} --answer "..."'
        print(f"    {_dim(f'Continue: {continue_hint}')}")
    print()
    return 0


def cmd_learn_experience(args):
    parser = _make_parser("learn-experience")
    parser.add_argument(
        "--type",
        choices=[
            "correction",
            "decision",
            "user_preference",
            "sentiment_marker",
            "task_pattern",
            "fact_declaration",
        ],
        help=_t("cli.arg.rules.filter_memory_type"),
    )
    parser.add_argument(
        "--expiry-days",
        type=int,
        default=14,
        help=_t("cli.arg.rules.expiry_days_14"),
    )
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    from carrymem.carrymem import CarryMem

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
        print(f"\n  {_dim('Use: carrymem rules review-lessons')}")
    print()
    return 0


def cmd_review_lessons(args):
    parser = _make_parser("review-lessons")
    parser.add_argument("--accept", help=_t("cli.arg.rules.accept_lesson"))
    parser.add_argument("--reject", help=_t("cli.arg.rules.reject_lesson"))
    parser.add_argument("--accept-all", action="store_true", help=_t("cli.arg.rules.accept_all_lessons"))
    parser.add_argument("--trigger", help=_t("cli.arg.rules.trigger_override"))
    parser.add_argument("--action", help=_t("cli.arg.rules.action_override"))
    parser.add_argument("--note", help=_t("cli.arg.rules.review_note"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
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
        print(f"  {_dim('Use: carrymem rules learn')}")
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
        print(f"    {_dim(f'Accept: carrymem rules review-lessons --accept {entry.id}')}")
        print(f"    {_dim(f'Reject: carrymem rules review-lessons --reject {entry.id}')}")

    print()
    return 0


def cmd_lesson_log(args):
    parser = _make_parser("lesson-log")
    parser.add_argument("--limit", type=int, default=20, help=_t("cli.arg.rules.limit_entries"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parsed = parser.parse_args(args)

    engine = _get_rule_engine(parsed.db)
    entries = engine.get_lesson_log(limit=parsed.limit)

    if not entries:
        print(f"\n  {_yellow('No experience learning history.')}")
        print(f"  {_dim('Use: carrymem rules learn')}")
        return 0

    print(f"\n  {_bold('Experience Learning Log')}")
    print(f"  {'─' * 60}")
    for entry in entries:
        status_icon = {
            "pending": "\u23f3",
            "accepted": "\u2705",
            "rejected": "\u274c",
            "expired": "\u231b",
        }.get(entry.status, "?")
        lesson_preview = entry.lesson[:60] + ("..." if len(entry.lesson) > 60 else "")
        rule_info = f" \u2192 {entry.resulting_rule_id}" if entry.resulting_rule_id else ""
        print(f"  {status_icon} {_dim(entry.id)} {lesson_preview}{rule_info}")
        print(f"     {_dim(f'{entry.status} | {entry.created_at[:19]}')}")

    stats = engine.get_lesson_stats()
    total_s = stats.get("total", 0)
    pending_s = stats.get("pending", 0)
    accepted_s = stats.get("accepted", 0)
    rejected_s = stats.get("rejected", 0)
    expired_s = stats.get("expired", 0)
    _summary = _dim(
        f"Total: {total_s} | Pending: {pending_s} | "
        f"Accepted: {accepted_s} | Rejected: {rejected_s} | "
        f"Expired: {expired_s}"
    )
    print(f"\n  {_summary}")
    print()
    return 0
