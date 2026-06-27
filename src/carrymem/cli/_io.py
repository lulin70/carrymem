"""CarryMem CLI - Import/export/pack commands: consolidate, export, import, pack, unpack."""

import base64
import binascii
import getpass
import gzip
import hashlib
import json
import os
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from carrymem.cli._base import *


def cmd_consolidate(args):
    """Run or schedule memory consolidation (dedup, decay, cleanup)."""
    parser = _make_parser("consolidate")
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--dry-run", action="store_true", help=_t("cli.arg.dry_run"))
    parser.add_argument("--no-p1", action="store_true", help=_t("cli.arg.no_p1"))
    parser.add_argument("--no-p2", action="store_true", help=_t("cli.arg.no_p2"))
    parser.add_argument(
        "--schedule",
        type=float,
        default=0,
        metavar="HOURS",
        help=_t("cli.arg.schedule"),
    )
    parser.add_argument("--stop", action="store_true", help=_t("cli.arg.stop"))

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
    """Export memories from the active namespace to a file."""
    parser = _make_parser("export")
    parser.add_argument("output", help=_t("cli.arg.output_path"))
    parser.add_argument(
        "--format", "-f", choices=["json", "markdown"], default="json", help=_t("cli.arg.export_format")
    )
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    parser.add_argument("--db", help=_t("cli.arg.db"))

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    result = cm.export_memories(output_path=parsed.output, format=parsed.format, namespace=parsed.namespace)

    if result.get("exported"):
        total = result.get("total_memories", 0)
        fmt = result.get("format", "json")
        print(f"  {_green(_t('cli.success.exported', count=total, path=parsed.output, format=fmt))}")
    else:
        print(f"  {_red(_t('cli.error.export_failed', detail=result))}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_import(args):
    """Import memories from a file into the active namespace."""
    parser = _make_parser("import")
    parser.add_argument("input", help=_t("cli.arg.input_path"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    parser.add_argument(
        "--merge",
        choices=["skip_existing", "overwrite"],
        default="skip_existing",
        help=_t("cli.arg.merge_strategy"),
    )
    parser.add_argument("--db", help=_t("cli.arg.db"))

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

    _msg = _green(_t("cli.success.imported", imported=imported, skipped=skipped, errors=errors, total=total))
    print(f"  {_msg}")

    if errors > 0:
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_pack(args):
    """Pack CarryMem identity (memories, rules, config) into a portable .carry file."""
    import os

    parser = _make_parser("pack")
    parser.add_argument("--output", "-o", help=_t("cli.arg.output_file"))
    parser.add_argument("--include-rules", action="store_true", default=True, help=_t("cli.arg.include_rules"))
    parser.add_argument("--no-rules", action="store_true", help=_t("cli.arg.no_rules"))
    parser.add_argument("--include-config", action="store_true", default=True, help=_t("cli.arg.include_config"))
    parser.add_argument("--no-config", action="store_true", help=_t("cli.arg.no_config"))
    parser.add_argument("--key", help=_t("cli.arg.encryption_key"))
    parser.add_argument("--encrypt", action="store_true", help=_t("cli.arg.encrypt"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))

    parsed = parser.parse_args(args)

    include_rules = parsed.include_rules and not parsed.no_rules
    include_config = parsed.include_config and not parsed.no_config

    # Prompt for encryption password if --encrypt is specified
    encrypt_password = None
    if parsed.encrypt:
        try:
            encrypt_password = getpass.getpass("  Enter encryption password: ")
            confirm_password = getpass.getpass("  Confirm encryption password: ")
            if encrypt_password != confirm_password:
                print(f"  {_red('Error:')} Passwords do not match")
                return 1
            if len(encrypt_password) < 4:
                print(f"  {_red('Error:')} Password must be at least 4 characters")
                return 1
        except (EOFError, KeyboardInterrupt):
            print()
            return 1

    print(f"\n  {_bold('Packing CarryMem identity...')}\n")

    cm = _get_carrymem(parsed.db, parsed.namespace)

    try:
        # Collect memories
        stats = cm.get_stats()
        total_count = stats.get("total_count", 0) if isinstance(stats, dict) else 0
        export_limit = max(total_count, 1)

        all_memories = cm._adapter.recall("", limit=export_limit) if cm._adapter else []
        memories_data = []
        encrypted_count = 0
        type_counts: Dict[str, int] = {}

        for m in all_memories:
            d = m.to_dict()
            # Skip encrypted entries unless --key is provided
            if d.get("is_encrypted", False) or (d.get("metadata", {}).get("is_encrypted", False)):
                encrypted_count += 1
                if not parsed.key:
                    continue
            # Remove vector embedding (too large, can be rebuilt)
            d.pop("vector_embedding", None)
            memories_data.append(d)
            mtype = d.get("type", "unknown")
            type_counts[mtype] = type_counts.get(mtype, 0) + 1

        # Build type breakdown string
        type_parts = []
        for mtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            type_parts.append(f"{count} {mtype}")
        type_breakdown = ", ".join(type_parts) if type_parts else "none"

        print(f"  {_green('\u2713')} {len(memories_data)} memories ({type_breakdown})")

        # Collect rules
        rules_data = []
        if include_rules:
            try:
                engine = _get_rule_engine(parsed.db)
                rules = engine.list_rules(status="active", limit=10000)
                rules_data = [r.to_dict() for r in rules]
                print(f"  {_green('\u2713')} {len(rules_data)} rules")
            except (ImportError, sqlite3.OperationalError, KeyError, ValueError) as e:
                print(f"  {_yellow('\u26a0')} Rules export skipped: {e}")

        # Collect config
        config_data = None
        if include_config:
            try:
                config_file = _DEFAULT_CONFIG_DIR / "config.json"
                if config_file.exists():
                    with open(config_file, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    print(f"  {_green('\u2713')} Config (namespace, consolidation settings)")
                else:
                    print(f"  {_dim('\u25cb')} No config file found")
            except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError) as e:
                print(f"  {_yellow('\u26a0')} Config export skipped: {e}")

        # Encrypted entries info
        if encrypted_count > 0:
            if parsed.key:
                print(f"  {_green('\u2713')} {encrypted_count} encrypted entries included")
            else:
                _icon = _yellow("\u2717")
                print(f"  {_icon} Encrypted entries skipped ({encrypted_count}) (provide --key to include)")

        # Build pack data
        source_machine = socket.gethostname().lower().replace(" ", "-")
        packed_at = datetime.now(timezone.utc).isoformat()

        pack_data = {
            "version": "1.1",
            "carrymem_version": __version__,
            "packed_at": packed_at,
            "source_machine": source_machine,
            "contents": {
                "memories_count": len(memories_data),
                "rules_count": len(rules_data),
                "has_config": config_data is not None,
                "has_encrypted": encrypted_count > 0 and bool(parsed.key),
            },
            "data": {
                "memories": memories_data,
                "rules": rules_data,
                "config": config_data,
            },
        }

        # Determine output path
        date_str = datetime.now().strftime("%Y%m%d")
        default_filename = f"carrymem_identity_{date_str}.carry"
        output_path = parsed.output or default_filename

        # Serialize to JSON bytes
        json_bytes = json.dumps(pack_data, ensure_ascii=False).encode("utf-8")

        # Compute SHA-256 checksum of the JSON payload (before compression/encryption)
        payload_checksum = hashlib.sha256(json_bytes).hexdigest()

        # Build the outer container with checksum
        container = {
            "version": "1.1",
            "checksum": payload_checksum,
            "encrypted": encrypt_password is not None,
            "payload": None,  # will be filled below
        }

        if encrypt_password:
            # Encrypt the JSON payload
            try:
                from carrymem.security.encryption import MemoryEncryption

                enc = MemoryEncryption(key=encrypt_password)
                container["payload"] = enc.encrypt(json_bytes.decode("utf-8"))
                container["encryption_backend"] = enc.backend
                print(f"  {_green('\u2713')} Encrypted ({enc.backend})")
            except (ValueError, TypeError, ImportError) as e:
                print(f"  {_red('Encryption failed:')} {e}")
                cm.close()
                return 1
        else:
            # Store as base64 of gzip-compressed JSON
            compressed = gzip.compress(json_bytes)
            container["payload"] = base64.b64encode(compressed).decode("ascii")

        # Write the container as gzip-compressed JSON
        try:
            safe_path = _validate_cli_path(output_path)
            container_bytes = json.dumps(container, ensure_ascii=False).encode("utf-8")
            with gzip.open(safe_path, "wb") as f:
                f.write(container_bytes)
        except (OSError, ValueError) as e:
            print(f"\n  {_red('Write error:')} {e}")
            cm.close()
            return 1

        # Show file size
        file_size = os.path.getsize(output_path)
        if file_size >= 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        elif file_size >= 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} bytes"

        print(f"  \u2192 Saved to {output_path} ({size_str})")

    except (OSError, IOError, ValueError, TypeError) as e:
        print(f"\n  {_red('Pack failed:')} {e}")
        cm.close()
        return 1

    cm.close()
    return 0


def cmd_unpack(args):
    """Unpack a .carry file to restore CarryMem identity."""
    import os

    parser = _make_parser("unpack")
    parser.add_argument("file", help=_t("cli.arg.carry_file"))
    parser.add_argument(
        "--merge",
        action="store_true",
        default=True,
        help=_t("cli.arg.merge_mode"),
    )
    parser.add_argument("--replace", action="store_true", help=_t("cli.arg.replace"))
    parser.add_argument("--db", help=_t("cli.arg.db"))
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))

    parsed = parser.parse_args(args)

    # --replace overrides --merge
    merge_mode = not parsed.replace

    print(f"\n  {_bold('Unpacking CarryMem identity...')}\n")

    # Read and decompress .carry file
    try:
        safe_path = _validate_cli_path(parsed.file)
        with gzip.open(safe_path, "rb") as f:
            json_bytes = f.read()
        raw_data = json.loads(json_bytes.decode("utf-8"))
    except FileNotFoundError:
        print(f"  {_red('File not found:')} {parsed.file}")
        return 1
    except gzip.BadGzipFile:
        # Try reading as plain JSON (for backwards compatibility)
        try:
            with open(parsed.file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  {_red('Invalid .carry file:')} {e}")
            return 1
    except json.JSONDecodeError as e:
        print(f"  {_red('Invalid .carry file:')} {e}")
        return 1
    except (OSError, ValueError) as e:
        print(f"  {_red('Read error:')} {e}")
        return 1

    # Detect format: v1.1 container vs v1.0 legacy
    is_container_format = "payload" in raw_data and "checksum" in raw_data

    if is_container_format:
        # v1.1 format: container with checksum and optional encryption
        container = raw_data
        is_encrypted = container.get("encrypted", False)
        expected_checksum = container.get("checksum", "")
        payload_str = container.get("payload", "")

        if is_encrypted:
            # Prompt for decryption password
            try:
                password = getpass.getpass("  Enter decryption password: ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 1

            try:
                from carrymem.security.encryption import EncryptionError, MemoryEncryption

                dec = MemoryEncryption(key=password)
                payload_json_str = dec.decrypt(payload_str)
            except (ValueError, TypeError, EncryptionError) as e:
                print(f"  {_red('Decryption failed:')} {e}")
                print(f"  {_dim('Check your password and try again.')}")
                return 1
        else:
            # Decode base64 → decompress gzip → JSON
            try:
                compressed = base64.b64decode(payload_str)
                payload_json_str = gzip.decompress(compressed).decode("utf-8")
            except (binascii.Error, ValueError, OSError) as e:
                print(f"  {_red('Payload decompression failed:')} {e}")
                return 1

        # Verify checksum
        payload_bytes = payload_json_str.encode("utf-8")
        actual_checksum = hashlib.sha256(payload_bytes).hexdigest()
        if actual_checksum != expected_checksum:
            print(f"  {_red('Checksum mismatch!')} File may be corrupted.")
            print(f"  {_dim('Expected:')} {expected_checksum[:16]}...")
            print(f"  {_dim('Actual:   ')} {actual_checksum[:16]}...")
            return 1
        print(f"  {_green('\u2713')} Checksum verified")

        pack_data = json.loads(payload_json_str)
    else:
        # v1.0 legacy format: no checksum, no encryption
        pack_data = raw_data
        print(f"  {_yellow('\u26a0')} Legacy .carry format (no checksum verification available)")
        print(f"  {_dim('Re-pack with the latest version for integrity protection.')}")

    # Validate pack format
    version = pack_data.get("version", "1.0")
    if version not in ("1.0", "1.1"):
        print(f"  {_red('Unsupported .carry format version:')} {version}")
        return 1

    # Show source info
    source_machine = pack_data.get("source_machine", "unknown")
    packed_at = pack_data.get("packed_at", "unknown")
    carrymem_ver = pack_data.get("carrymem_version", "unknown")
    # Format packed_at for display
    try:
        if packed_at != "unknown":
            dt = datetime.fromisoformat(packed_at)
            packed_display = dt.strftime("%Y-%m-%d")
        else:
            packed_display = "unknown"
    except ValueError as e:
        _cli_logger.debug("Failed to parse packed_at date '%s': %s", packed_at, e)
        packed_display = str(packed_at)[:10]

    print(f"  Source: {source_machine}, packed {packed_display}, CarryMem v{carrymem_ver}")

    cm = _get_carrymem(parsed.db, parsed.namespace)

    try:
        data = pack_data.get("data", {})
        conflicts = 0

        # Restore memories
        memories_data = data.get("memories", [])
        if memories_data:
            merge_strategy = "skip_existing" if merge_mode else "overwrite"
            import_result = cm.import_memories(
                data={
                    "memories": memories_data,
                    "source": {
                        "namespace": (pack_data.get("data", {}).get("config") or {}).get("namespace", "unknown")
                    },
                },
                namespace=parsed.namespace,
                merge_strategy=merge_strategy,
            )
            imported = import_result.get("imported", 0)
            skipped = import_result.get("skipped", 0)
            errors = import_result.get("errors", 0)
            conflicts = skipped
            print(f"  {_green('\u2713')} {imported} memories restored ({conflicts} conflicts)")
            if errors > 0:
                print(f"  {_yellow('\u26a0')} {errors} errors during memory import")
        else:
            print(f"  {_dim('\u25cb')} No memories to restore")

        # Restore rules
        rules_data = data.get("rules", [])
        if rules_data:
            try:
                engine = _get_rule_engine(parsed.db)
                import_mode = "skip" if merge_mode else "overwrite"
                rules_import_data = {
                    "format": "carrymem-rules-v1",
                    "version": carrymem_ver,
                    "rules": rules_data,
                }
                stats = engine.import_rules(rules_import_data, mode=import_mode)
                print(f"  {_green('\u2713')} {stats['imported']} rules restored")
                skipped_count = stats.get("skipped", 0)
                overwritten_count = stats.get("overwritten", 0)
                errors_list = stats.get("errors")
                if skipped_count > 0:
                    print(f"    {_dim(f'{skipped_count} rules skipped (already exist)')}")
                if overwritten_count > 0:
                    print(f"    {_dim(f'{overwritten_count} rules overwritten')}")
                if errors_list:
                    print(f"    {_yellow(f'{len(errors_list)} errors during rules import')}")
            except (ImportError, sqlite3.OperationalError, KeyError, ValueError) as e:
                print(f"  {_yellow('\u26a0')} Rules import skipped: {e}")
        else:
            print(f"  {_dim('\u25cb')} No rules to restore")

        # Restore config
        config_data = data.get("config")
        if config_data:
            try:
                config_file = _DEFAULT_CONFIG_DIR / "config.json"
                _DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                if config_file.exists() and merge_mode:
                    # Merge: keep existing config, add new keys
                    with open(config_file, "r", encoding="utf-8") as f:
                        existing_config = json.load(f)
                    # Deep merge: new values don't overwrite existing
                    for key, value in config_data.items():
                        if key not in existing_config:
                            existing_config[key] = value
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(existing_config, f, indent=2, ensure_ascii=False)
                else:
                    # Replace or no existing config
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(config_data, f, indent=2, ensure_ascii=False)
                print(f"  {_green('\u2713')} Config restored")
            except (OSError, json.JSONDecodeError, PermissionError, ValueError) as e:
                print(f"  {_yellow('\u26a0')} Config restore skipped: {e}")
        else:
            print(f"  {_dim('\u25cb')} No config to restore")

        # Check embedding model availability
        embedding_model = None
        if cm._adapter and hasattr(cm._adapter, "_embedding_model_name"):
            embedding_model = cm._adapter._embedding_model_name
        if embedding_model:
            _model_info = _dim(f"\u2139 Embedding model: {embedding_model} (vectors will be rebuilt on next recall)")
            print(f"  {_model_info}")

        print(f"\n  \u2192 Run {_cyan('carrymem setup-mcp --all --global')} to reconnect your AI tools")

    except (OSError, IOError, ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"\n  {_red('Unpack failed:')} {e}")
        cm.close()
        return 1

    cm.close()
    return 0
