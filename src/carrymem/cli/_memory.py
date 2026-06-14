"""CarryMem CLI - Memory CRUD commands: add, list, search, show, edit, forget, clean."""

import json

from carrymem.cli._base import *


def cmd_add(args):
    parser = _make_parser("add")
    parser.add_argument("message", help=_t("cli.arg.message"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--context", "-c", help=_t("cli.arg.context"))
    parser.add_argument("--force", "-f", action="store_true", help=_t("cli.arg.force_store"))
    parser.add_argument("--type", "-t", help=_t("cli.arg.type_override"))
    parser.add_argument("--db", help=_t("cli.arg.db"))

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.message = _cli_validator.validate_content(parsed.message, "message")
        except (ValueError, TypeError) as e:
            print(f"  {_red(_t('cli.error.validation', detail=e))}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    context = None
    if parsed.context:
        try:
            context = json.loads(parsed.context)
        except json.JSONDecodeError:
            print(f"  {_red(_t('cli.error.json_invalid', detail=parsed.context))}")
            return 1

    if parsed.force:
        result = cm.declare(parsed.message, context=context)
        keys = result.get("storage_keys", [])
        entries = result.get("entries", [])
        if keys:
            print(f"  {_green(_t('cli.success.stored', count=len(keys)))} (forced)")
            for i, key in enumerate(keys):
                entry = entries[i] if i < len(entries) else {}
                mtype = entry.get("type", parsed.type or "unknown")
                icon = _TYPE_ICONS.get(mtype, "\u2753")
                content = entry.get("content", parsed.message)
                print(f"    {icon} [{mtype}] {_truncate(content, 70)}")
                print(f"       Key: {key}")
        else:
            print(f"  {_red(_t('cli.error.store_failed'))}")
            cm.close()
            return 1
    else:
        result = cm.classify_and_remember(parsed.message, context=context)

        if not result.get("should_remember"):
            print(f"  {_yellow(_t('cli.status.not_classified'))}")
            print(f"  {_dim(_t('help.force_store_tip'))}")
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

        print(f"\n  {_green(_t('cli.success.remembered', count=len(entries)))}")

    cm.close()
    return 0


def cmd_list(args):
    parser = _make_parser("list")
    parser.add_argument("--limit", "-l", type=int, default=20, help=_t("cli.arg.limit_memories"))
    parser.add_argument("--type", "-t", help=_t("cli.arg.type_filter"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--format", "-f", choices=["table", "json", "plain"], default="table", help=_t("cli.arg.format_table"))
    parser.add_argument("--db", help=_t("cli.arg.db"))

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(query="", filters=filters, limit=parsed.limit)

    if not memories:
        print(f"  {_dim(_t('cli.error.no_memories'))}")
        tip = _t('help.add_memory_tip')
        print(f"  {_dim(tip)}")
        cm.close()
        return 0

    if parsed.format == "json":
        print(json.dumps(memories, ensure_ascii=False, indent=2))
    elif parsed.format == "plain":
        for m in memories:
            key = m.get("storage_key", "")
            mtype = m.get("type", "")
            content = m.get("content", "")
            conf = m.get("confidence", 0)
            print(f"{key}\t{mtype}\t{content}\t{conf:.2f}")
    else:
        print(f"\n  {_bold(f'Memories')} ({len(memories)} shown, namespace={parsed.namespace})\n")
        for i, m in enumerate(memories, 1):
            _print_memory_card(m, index=i)
            print()

    cm.close()
    return 0


def cmd_search(args):
    parser = _make_parser("search")
    parser.add_argument("query", help=_t("cli.arg.query"))
    parser.add_argument("--limit", "-l", type=int, default=10, help=_t("cli.arg.limit_results"))
    parser.add_argument("--type", "-t", help=_t("cli.arg.type_filter"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--format", "-f", choices=["table", "json", "plain"], default="table", help=_t("cli.arg.format_table"))
    parser.add_argument("--db", help=_t("cli.arg.db"))

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.query = _cli_validator.validate_query(parsed.query)
        except (ValueError, TypeError) as e:
            print(f"  {_red(_t('cli.error.validation', detail=e))}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    filters = {}
    if parsed.type:
        filters["type"] = parsed.type

    memories = cm.recall_memories(query=parsed.query, filters=filters, limit=parsed.limit)

    if not memories:
        print(f"  {_dim(_t('cli.error.no_matching', query=parsed.query))} {_bold(parsed.query)}")
        cm.close()
        return 0

    if parsed.format == "json":
        print(json.dumps(memories, ensure_ascii=False, indent=2))
    elif parsed.format == "plain":
        for m in memories:
            sk = m.get("storage_key", "")
            mt = m.get("type", "")
            mc = m.get("content", "")
            mf = m.get("confidence", 0)
            _row = f"{sk}\t{mt}\t{mc}\t{mf:.2f}"
            print(_row)
    else:
        print(f"\n  {_bold('Search:')} {_cyan(parsed.query)} ({len(memories)} results)\n")
        for i, m in enumerate(memories, 1):
            _print_memory_card(m, index=i)
            print()

    cm.close()
    return 0


def cmd_show(args):
    parser = _make_parser("show")
    parser.add_argument("key", help=_t("cli.arg.key"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--json", action="store_true", help=_t("cli.arg.json"))

    parsed = parser.parse_args(args)

    cm = _get_carrymem(parsed.db, parsed.namespace)

    target = _find_memory(cm, parsed.key)

    if not target:
        print(f"  {_red(_t('cli.error.not_found', key=parsed.key))}")
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
    parser.add_argument("key", help=_t("cli.arg.key_edit"))
    parser.add_argument("content", help=_t("cli.arg.content"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--db", help=_t("cli.arg.db"))

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.content = _cli_validator.validate_content(parsed.content, "content")
        except (ValueError, TypeError) as e:
            print(f"  {_red(_t('cli.error.validation', detail=e))}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    target = _find_memory(cm, parsed.key)

    if not target:
        print(f"  {_red(_t('cli.error.not_found', key=parsed.key))}")
        cm.close()
        return 1

    old_content = target.get("content", "")
    print(f"  {_dim('Old:')} {_truncate(old_content, 60)}")
    print(f"  {_green('New:')} {_truncate(parsed.content, 60)}")

    try:
        answer = input(f"  {_t('cli.status.confirm_edit')} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        cm.close()
        return 0

    if answer != "y":
        print(f"  {_dim(_t('cli.status.cancelled'))}")
        cm.close()
        return 0

    result = cm.update_memory(parsed.key, parsed.content)
    success = result.get("updated", False) if isinstance(result, dict) else bool(result)
    if success:
        print(f"  {_green(_t('cli.success.updated', key=parsed.key))}")
    else:
        print(f"  {_red(_t('cli.error.update_failed', key=parsed.key))}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_forget(args):
    parser = _make_parser("forget")
    parser.add_argument("key", help=_t("cli.arg.key_forget"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--force", "-y", action="store_true", help=_t("cli.arg.force"))

    parsed = parser.parse_args(args)

    if _cli_validator:
        try:
            parsed.key = _cli_validator.validate_content(parsed.key, "key")
        except (ValueError, TypeError) as e:
            print(f"  {_red(_t('cli.error.validation', detail=e))}")
            return 1

    cm = _get_carrymem(parsed.db, parsed.namespace)

    target = _find_memory(cm, parsed.key)

    if not target:
        print(f"  {_red(_t('cli.error.not_found', key=parsed.key))}")
        cm.close()
        return 1

    if not parsed.force:
        content = target.get("content", "")
        print(f"  {_red('Delete:')} {_truncate(content, 60)}")
        print(f"  Key: {parsed.key}")
        try:
            answer = input(f"  {_t('cli.status.confirm_delete')} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            cm.close()
            return 0
        if answer != "y":
            print(f"  {_dim(_t('cli.status.cancelled'))}")
            cm.close()
            return 0

    success = cm.forget_memory(parsed.key)
    if success:
        print(f"  {_green(_t('cli.success.forgotten', key=parsed.key))}")
    else:
        print(f"  {_red(_t('cli.error.forget_failed', key=parsed.key))}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_clean(args):
    parser = _make_parser("clean")
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace_default"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--expired", action="store_true", help=_t("cli.arg.expired"))
    parser.add_argument("--quality", type=float, default=0, help=_t("cli.arg.quality"))
    parser.add_argument("--dry-run", action="store_true", help=_t("cli.arg.dry_run"))
    parser.add_argument("--force", "-y", action="store_true", help=_t("cli.arg.force"))

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
        print(f"  {_green(_t('cli.success.nothing_to_clean'))}")
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
        print(f"\n  {_dim(_t('cli.status.dry_run'))}")
        cm.close()
        return 0

    if not parsed.force:
        try:
            answer = input(f"\n  {_t('cli.status.confirm_clean', count=len(to_remove))} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            cm.close()
            return 0
        if answer != "y":
            print(f"  {_dim(_t('cli.status.cancelled'))}")
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

    print(f"\n  {_green(_t('cli.success.cleaned', removed=removed, errors=errors))}")
    cm.close()
    return 0 if errors == 0 else 1
