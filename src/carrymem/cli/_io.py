"""CarryMem CLI - Import/export/pack commands: consolidate, export, import, pack, unpack."""

import base64
import getpass
import gzip
import hashlib
import json
import socket
import sqlite3
from datetime import datetime, timezone
from typing import Dict

from carrymem.cli._base import (
    _DEFAULT_CONFIG_DIR,
    __version__,
    _add_common_args,
    _bold,
    _cli_logger,
    _cyan,
    _dim,
    _get_carrymem,
    _get_rule_engine,
    _make_parser,
    _t,
    _validate_cli_path,
)
from carrymem.cli._format import formatter


def cmd_consolidate(args):
    """Run or schedule memory consolidation (dedup, decay, cleanup)."""
    parser = _make_parser("consolidate")
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    _add_common_args(parser)
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
            formatter.success("Consolidation schedule stopped")
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
        formatter.success("Consolidation scheduled")
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
    with formatter.progress("Consolidating memories"):
        report = cm.consolidate(
            dry_run=parsed.dry_run,
            run_p1=not parsed.no_p1,
            run_p2=not parsed.no_p2,
        )

    if report.get("dry_run"):
        formatter.warning("[DRY RUN] No changes made\n")

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
        "--format",
        "-f",
        choices=["json", "markdown"],
        default="json",
        help=_t("cli.arg.export_format"),
    )
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))
    _add_common_args(parser)

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    with formatter.progress("Exporting memories"):
        result = cm.export_memories(output_path=parsed.output, format=parsed.format, namespace=parsed.namespace)

    if result.get("exported"):
        total = result.get("total_memories", 0)
        fmt = result.get("format", "json")
        formatter.success(_t("cli.success.exported", count=total, path=parsed.output, format=fmt))
    else:
        formatter.error("E_EXPORT", _t("cli.error.export_failed", detail=result))
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
    _add_common_args(parser)

    parsed = parser.parse_args(args)
    cm = _get_carrymem(parsed.db, parsed.namespace)

    with formatter.progress("Importing memories"):
        result = cm.import_memories(
            input_path=parsed.input,
            namespace=parsed.namespace,
            merge_strategy=parsed.merge,
        )

    imported = result.get("imported", 0)
    skipped = result.get("skipped", 0)
    errors = result.get("errors", 0)
    total = result.get("total_processed", 0)

    formatter.success(
        _t(
            "cli.success.imported",
            imported=imported,
            skipped=skipped,
            errors=errors,
            total=total,
        )
    )

    if errors > 0:
        cm.close()
        return 1

    cm.close()
    return 0


def _prompt_encrypt_password():
    """Prompt user for encryption password with confirmation.

    Returns (password, 0) on success or (None, error_code) on failure.
    """
    try:
        password = getpass.getpass("  Enter encryption password: ")
        confirm_password = getpass.getpass("  Confirm encryption password: ")
        if password != confirm_password:
            formatter.error("E_PACK_PASSWORD", "Passwords do not match")
            return None, 1
        if len(password) < 4:
            formatter.error("E_PACK_PASSWORD", "Password must be at least 4 characters")
            return None, 1
        return password, 0
    except (EOFError, KeyboardInterrupt):
        print()
        return None, 1


def _collect_memories_for_pack(cm, include_key: bool):
    """Collect memories for packing.

    Returns (memories_data, encrypted_count, type_counts).
    """
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
            if not include_key:
                continue
        # Remove vector embedding (too large, can be rebuilt)
        d.pop("vector_embedding", None)
        memories_data.append(d)
        mtype = d.get("type", "unknown")
        type_counts[mtype] = type_counts.get(mtype, 0) + 1

    return memories_data, encrypted_count, type_counts


def _collect_rules_for_pack(db_path: str):
    """Collect rules for packing. Returns list of rule dicts (empty on error)."""
    try:
        engine = _get_rule_engine(db_path)
        rules = engine.list_rules(status="active", limit=10000)
        rules_data = [r.to_dict() for r in rules]
        formatter.success(f"{len(rules_data)} rules")
        return rules_data
    except (ImportError, sqlite3.OperationalError, KeyError, ValueError) as e:
        formatter.warning(f"Rules export skipped: {e}")
        return []


def _collect_config_for_pack():
    """Collect config for packing. Returns config dict or None."""
    try:
        config_file = _DEFAULT_CONFIG_DIR / "config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            formatter.success("Config (namespace, consolidation settings)")
            return config_data
        formatter.info("No config file found")
        return None
    except (json.JSONDecodeError, OSError) as e:
        formatter.warning(f"Config export skipped: {e}")
        return None


def _build_pack_container(pack_data: dict, encrypt_password):
    """Build the outer .carry container with checksum and optional encryption.

    Returns (container, 0) on success or (None, error_code) on failure.
    """
    json_bytes = json.dumps(pack_data, ensure_ascii=False).encode("utf-8")
    payload_checksum = hashlib.sha256(json_bytes).hexdigest()

    container = {
        "version": "1.1",
        "checksum": payload_checksum,
        "encrypted": encrypt_password is not None,
        "payload": None,
    }

    if encrypt_password:
        try:
            from carrymem.security.encryption import MemoryEncryption

            enc = MemoryEncryption(key=encrypt_password)
            container["payload"] = enc.encrypt(json_bytes.decode("utf-8"))
            container["encryption_backend"] = enc.backend
            formatter.success(f"Encrypted ({enc.backend})")
        except (ValueError, TypeError, ImportError) as e:
            formatter.error("E_PACK_ENCRYPT", f"Encryption failed: {e}")
            return None, 1
    else:
        compressed = gzip.compress(json_bytes)
        container["payload"] = base64.b64encode(compressed).decode("ascii")

    return container, 0


def _write_carry_file(output_path: str, container: dict) -> int:
    """Write the container as gzip-compressed JSON to output_path. Returns 0/1."""
    try:
        safe_path = _validate_cli_path(output_path)
        container_bytes = json.dumps(container, ensure_ascii=False).encode("utf-8")
        with gzip.open(safe_path, "wb") as f:
            f.write(container_bytes)
        return 0
    except (OSError, ValueError) as e:
        formatter.error("E_PACK_WRITE", f"Write error: {e}")
        return 1


def _format_file_size(file_size: int) -> str:
    """Format file size as human-readable string."""
    if file_size >= 1024 * 1024:
        return f"{file_size / (1024 * 1024):.1f} MB"
    if file_size >= 1024:
        return f"{file_size / 1024:.1f} KB"
    return f"{file_size} bytes"


def cmd_pack(args):
    """Pack CarryMem identity (memories, rules, config) into a portable .carry file."""
    import os

    parser = _make_parser("pack")
    parser.add_argument("--output", "-o", help=_t("cli.arg.output_file"))
    parser.add_argument(
        "--include-rules",
        action="store_true",
        default=True,
        help=_t("cli.arg.include_rules"),
    )
    parser.add_argument("--no-rules", action="store_true", help=_t("cli.arg.no_rules"))
    parser.add_argument(
        "--include-config",
        action="store_true",
        default=True,
        help=_t("cli.arg.include_config"),
    )
    parser.add_argument("--no-config", action="store_true", help=_t("cli.arg.no_config"))
    parser.add_argument("--key", help=_t("cli.arg.encryption_key"))
    parser.add_argument("--encrypt", action="store_true", help=_t("cli.arg.encrypt"))
    _add_common_args(parser)
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))

    parsed = parser.parse_args(args)

    include_rules = parsed.include_rules and not parsed.no_rules
    include_config = parsed.include_config and not parsed.no_config

    # Prompt for encryption password if --encrypt is specified
    encrypt_password = None
    if parsed.encrypt:
        encrypt_password, err = _prompt_encrypt_password()
        if err:
            return err

    print(f"\n  {_bold('Packing CarryMem identity...')}\n")

    cm = _get_carrymem(parsed.db, parsed.namespace)

    try:
        # Collect memories
        memories_data, encrypted_count, type_counts = _collect_memories_for_pack(cm, bool(parsed.key))

        type_parts = [f"{count} {mtype}" for mtype, count in sorted(type_counts.items(), key=lambda x: -x[1])]
        type_breakdown = ", ".join(type_parts) if type_parts else "none"
        formatter.success(f"{len(memories_data)} memories ({type_breakdown})")

        # Collect rules
        rules_data = _collect_rules_for_pack(parsed.db) if include_rules else []

        # Collect config
        config_data = _collect_config_for_pack() if include_config else None

        # Encrypted entries info
        if encrypted_count > 0:
            if parsed.key:
                formatter.success(f"{encrypted_count} encrypted entries included")
            else:
                formatter.warning(f"Encrypted entries skipped ({encrypted_count}) (provide --key to include)")

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

        # Build container (checksum + optional encryption) and write .carry file.
        # P0-C2: show a spinner during the slow build+write step so users know
        # the CLI is not hung during encryption / compression of large datasets.
        with formatter.progress("Building .carry file"):
            container, err = _build_pack_container(pack_data, encrypt_password)
            if err:
                cm.close()
                return err

            # Write the .carry file
            err = _write_carry_file(output_path, container)
            if err:
                cm.close()
                return err

        # Show file size
        file_size = os.path.getsize(output_path)
        formatter.success(f"Saved to {output_path} ({_format_file_size(file_size)})")

    except (OSError, ValueError, TypeError) as e:
        formatter.error("E_PACK_FAILED", f"Pack failed: {e}")
        cm.close()
        return 1

    cm.close()
    return 0


def _read_carry_file(file_path: str):
    """Read a .carry file and return raw_data, or (None, error_code) on failure."""
    try:
        safe_path = _validate_cli_path(file_path)
        with gzip.open(safe_path, "rb") as f:
            json_bytes = f.read()
        raw_data = json.loads(json_bytes.decode("utf-8"))
        return raw_data, 0
    except FileNotFoundError:
        formatter.error("E_UNPACK_NOT_FOUND", f"File not found: {file_path}")
        return None, 1
    except gzip.BadGzipFile:
        # Try reading as plain JSON (for backwards compatibility)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return raw_data, 0
        except (json.JSONDecodeError, ValueError) as e:
            formatter.error("E_UNPACK_INVALID", f"Invalid .carry file: {e}")
            return None, 1
    except json.JSONDecodeError as e:
        formatter.error("E_UNPACK_INVALID", f"Invalid .carry file: {e}")
        return None, 1
    except (OSError, ValueError) as e:
        formatter.error("E_UNPACK_READ", f"Read error: {e}")
        return None, 1


def _decode_container_payload(container):
    """Decode v1.1 container payload (decrypt or decompress).

    Returns (payload_json_str, 0) on success or (None, error_code) on failure.
    """
    is_encrypted = container.get("encrypted", False)
    payload_str = container.get("payload", "")

    if is_encrypted:
        try:
            password = getpass.getpass("  Enter decryption password: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return None, 1

        try:
            from carrymem.security.encryption import EncryptionError, MemoryEncryption

            dec = MemoryEncryption(key=password)
            payload_json_str = dec.decrypt(payload_str)
        except (ValueError, TypeError, EncryptionError) as e:
            formatter.error(
                "E_UNPACK_DECRYPT",
                f"Decryption failed: {e}",
                hint="Check your password and try again.",
            )
            return None, 1
    else:
        try:
            compressed = base64.b64decode(payload_str)
            payload_json_str = gzip.decompress(compressed).decode("utf-8")
        except (ValueError, OSError) as e:
            formatter.error("E_UNPACK_DECOMPRESS", f"Payload decompression failed: {e}")
            return None, 1

    return payload_json_str, 0


def _restore_memories_from_pack(cm, pack_data, namespace: str, merge_mode: bool) -> None:
    """Restore memories from pack_data into the given namespace."""
    data = pack_data.get("data", {})
    memories_data = data.get("memories", [])
    if not memories_data:
        formatter.info("No memories to restore")
        return

    merge_strategy = "skip_existing" if merge_mode else "overwrite"
    source_namespace = (pack_data.get("data", {}).get("config") or {}).get("namespace", "unknown")
    import_result = cm.import_memories(
        data={
            "memories": memories_data,
            "source": {"namespace": source_namespace},
        },
        namespace=namespace,
        merge_strategy=merge_strategy,
    )
    imported = import_result.get("imported", 0)
    skipped = import_result.get("skipped", 0)
    errors = import_result.get("errors", 0)
    formatter.success(f"{imported} memories restored ({skipped} conflicts)")
    if errors > 0:
        formatter.warning(f"{errors} errors during memory import")


def _restore_rules_from_pack(db_path: str, rules_data, carrymem_ver: str, merge_mode: bool) -> None:
    """Restore rules from pack_data into the rule engine."""
    if not rules_data:
        formatter.info("No rules to restore")
        return

    try:
        engine = _get_rule_engine(db_path)
        import_mode = "skip" if merge_mode else "overwrite"
        rules_import_data = {
            "format": "carrymem-rules-v1",
            "version": carrymem_ver,
            "rules": rules_data,
        }
        stats = engine.import_rules(rules_import_data, mode=import_mode)
        formatter.success(f"{stats['imported']} rules restored")
        skipped_count = stats.get("skipped", 0)
        overwritten_count = stats.get("overwritten", 0)
        errors_list = stats.get("errors")
        if skipped_count > 0:
            print(f"    {_dim(f'{skipped_count} rules skipped (already exist)')}")
        if overwritten_count > 0:
            print(f"    {_dim(f'{overwritten_count} rules overwritten')}")
        if errors_list:
            formatter.warning(f"{len(errors_list)} errors during rules import")
    except (ImportError, sqlite3.OperationalError, KeyError, ValueError) as e:
        formatter.warning(f"Rules import skipped: {e}")


def _restore_config_from_pack(config_data, merge_mode: bool) -> None:
    """Restore config from pack_data, optionally merging with existing config."""
    if not config_data:
        formatter.info("No config to restore")
        return

    try:
        config_file = _DEFAULT_CONFIG_DIR / "config.json"
        _DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if config_file.exists() and merge_mode:
            with open(config_file, "r", encoding="utf-8") as f:
                existing_config = json.load(f)
            # Deep merge: new values don't overwrite existing
            for key, value in config_data.items():
                if key not in existing_config:
                    existing_config[key] = value
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(existing_config, f, indent=2, ensure_ascii=False)
        else:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        formatter.success("Config restored")
    except (OSError, json.JSONDecodeError, ValueError) as e:
        formatter.warning(f"Config restore skipped: {e}")


def cmd_unpack(args):
    """Unpack a .carry file to restore CarryMem identity."""

    parser = _make_parser("unpack")
    parser.add_argument("file", help=_t("cli.arg.carry_file"))
    parser.add_argument(
        "--merge",
        action="store_true",
        default=True,
        help=_t("cli.arg.merge_mode"),
    )
    parser.add_argument("--replace", action="store_true", help=_t("cli.arg.replace"))
    _add_common_args(parser)
    parser.add_argument("--namespace", "-n", default="default", help=_t("cli.arg.namespace"))

    parsed = parser.parse_args(args)

    # --replace overrides --merge
    merge_mode = not parsed.replace

    print(f"\n  {_bold('Unpacking CarryMem identity...')}\n")

    # Read and decompress .carry file
    raw_data, err = _read_carry_file(parsed.file)
    if err:
        return err

    # Detect format: v1.1 container vs v1.0 legacy
    is_container_format = "payload" in raw_data and "checksum" in raw_data

    if is_container_format:
        # v1.1 format: container with checksum and optional encryption.
        # P0-C2: show a spinner during decryption / decompression so the user
        # knows the CLI is working on a potentially slow decode step.
        with formatter.progress("Decoding .carry payload"):
            container = raw_data
            expected_checksum = container.get("checksum", "")

            payload_json_str, err = _decode_container_payload(container)
            if err:
                return err

            # Verify checksum
            payload_bytes = payload_json_str.encode("utf-8")
            actual_checksum = hashlib.sha256(payload_bytes).hexdigest()
            if actual_checksum != expected_checksum:
                formatter.error(
                    "E_UNPACK_CHECKSUM",
                    "Checksum mismatch! File may be corrupted.",
                    hint=f"Expected: {expected_checksum[:16]}... | Actual: {actual_checksum[:16]}...",
                )
                return 1
            formatter.success("Checksum verified")

        pack_data = json.loads(payload_json_str)
    else:
        # v1.0 legacy format: no checksum, no encryption
        pack_data = raw_data
        formatter.warning("Legacy .carry format (no checksum verification available)")
        print(f"  {_dim('Re-pack with the latest version for integrity protection.')}")

    # Validate pack format
    version = pack_data.get("version", "1.0")
    if version not in ("1.0", "1.1"):
        formatter.error("E_UNPACK_VERSION", f"Unsupported .carry format version: {version}")
        return 1

    # Show source info
    source_machine = pack_data.get("source_machine", "unknown")
    packed_at = pack_data.get("packed_at", "unknown")
    carrymem_ver = pack_data.get("carrymem_version", "unknown")
    packed_display = "unknown"
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

        _restore_memories_from_pack(cm, pack_data, parsed.namespace, merge_mode)
        _restore_rules_from_pack(parsed.db, data.get("rules", []), carrymem_ver, merge_mode)
        _restore_config_from_pack(data.get("config"), merge_mode)

        # Check embedding model availability
        embedding_model = None
        if cm._adapter and hasattr(cm._adapter, "embedding_model_name"):
            embedding_model = cm._adapter.embedding_model_name
        if embedding_model:
            formatter.info(f"Embedding model: {embedding_model} (vectors will be rebuilt on next recall)")

        print(f"\n  \u2192 Run {_cyan('carrymem setup-mcp --all --global')} to reconnect your AI tools")

    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        formatter.error("E_UNPACK_FAILED", f"Unpack failed: {e}")
        cm.close()
        return 1

    cm.close()
    return 0
