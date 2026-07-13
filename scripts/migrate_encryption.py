#!/usr/bin/env python3
"""Migrate pre-v0.7.3 stream cipher ciphertexts to Fernet.

Starting from v0.7.3, the HMAC-CTR stream cipher fallback has been removed
from ``carrymem.security.encryption``. Databases that were created without
the ``cryptography`` package installed contain stream cipher ciphertexts
(non-Fernet) that can no longer be decrypted by the production code.

This script performs a one-time migration:
1. Creates a VACUUM INTO backup of the database
2. Scans all encrypted columns for stream cipher ciphertexts
3. Decrypts them with the legacy stream cipher
4. Re-encrypts them with Fernet
5. Commits in a single transaction

No plaintext is ever logged. All errors are reported with ciphertext hashes
(SHA-256, first 16 hex chars) for correlation without exposure.

Usage::

    python scripts/migrate_encryption.py --db ~/.carrymem/memories.db
    python scripts/migrate_encryption.py --db ~/.carrymem/memories.db --password "my-pass"
    python scripts/migrate_encryption.py --db ~/.carrymem/memories.db --dry-run

Exit codes:
    0 — migration completed (or dry-run found no stream cipher ciphertexts)
    1 — migration failed (see stderr)
    2 — stream cipher ciphertexts found but --dry-run was set
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure the project src/ is on sys.path so we can import carrymem modules.
# The script may be run from the repo root or from scripts/.
_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPT_DIR.parent / "src"
if _SRC_DIR.is_dir():
    sys.path.insert(0, str(_SRC_DIR))

# Also ensure tests/ helpers are importable for legacy_cipher.
_TESTS_DIR = _SCRIPT_DIR.parent / "tests"
if _TESTS_DIR.is_dir():
    sys.path.insert(0, str(_TESTS_DIR))

from cryptography.fernet import Fernet  # noqa: E402
from helpers.legacy_cipher import (  # noqa: E402
    LegacyCipherError,
    decrypt_stream,
    is_stream_cipher_ciphertext,
)

from carrymem.security.encryption import EncryptionError, MemoryEncryption  # noqa: E402

# Tables and columns that hold encrypted data.
# Each entry: (table, column)
ENCRYPTED_COLUMNS: list[tuple[str, str]] = [
    ("memories", "content"),
    ("memories", "raw_text"),
    ("memories", "original_message"),
    ("memory_versions", "content"),
]


def _ct_hash(ciphertext: str) -> str:
    """Return first 16 hex chars of SHA-256 of ciphertext (for safe logging)."""
    return hashlib.sha256(ciphertext.encode("utf-8")).hexdigest()[:16]


def _load_raw_key(key_file: Optional[str], password: Optional[str]) -> bytes:
    """Load the raw encryption key from key_file or derive from password.

    Uses MemoryEncryption internals to handle key loading, salt file, and
    PBKDF2 derivation. Returns the 32-byte raw key.
    """
    enc = MemoryEncryption(key=password, key_file=key_file)
    raw_key = getattr(enc, "_raw_key", None)
    if raw_key is None:
        raise RuntimeError("Failed to load encryption key: _raw_key is None")
    return raw_key


def _vacuum_into_backup(db_path: str) -> str:
    """Create a VACUUM INTO backup of the database.

    Returns the path to the backup file.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = f"{db_path}.backup.{timestamp}"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"VACUUM INTO '{backup_path}'")
    finally:
        conn.close()

    if not os.path.exists(backup_path):
        raise RuntimeError(f"VACUUM INTO failed: backup file not created at {backup_path}")

    return backup_path


def _scan_stream_cipher_ciphertexts(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Scan all encrypted columns for stream cipher ciphertexts.

    Returns a dict mapping "table.column" to a list of (rowid, ciphertext)
    tuples for rows that contain stream cipher ciphertexts.
    """
    found: dict[str, list[tuple]] = {}

    for table, column in ENCRYPTED_COLUMNS:
        # Check if the table exists in this database
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if cursor.fetchone() is None:
            continue

        key = f"{table}.{column}"
        rows = conn.execute(
            f"SELECT rowid, {column} FROM {table} " f"WHERE {column} IS NOT NULL AND {column} != ''"
        ).fetchall()

        for rowid, ciphertext in rows:
            if isinstance(ciphertext, str) and is_stream_cipher_ciphertext(ciphertext):
                found.setdefault(key, []).append((rowid, ciphertext))

    return found


def _migrate(
    conn: sqlite3.Connection,
    raw_key: bytes,
    found: dict[str, list[tuple]],
) -> int:
    """Decrypt stream cipher ciphertexts and re-encrypt with Fernet.

    Returns the number of rows migrated.
    """
    fernet = Fernet(base64.urlsafe_b64encode(raw_key))

    migrated = 0

    for key, items in found.items():
        table, column = key.split(".", 1)
        for rowid, old_ciphertext in items:
            # Decrypt with legacy stream cipher
            try:
                plaintext = decrypt_stream(raw_key, old_ciphertext)
            except LegacyCipherError as e:
                print(
                    f"ERROR: Failed to decrypt {key} rowid={rowid} " f"(ct_hash={_ct_hash(old_ciphertext)}): {e}",
                    file=sys.stderr,
                )
                raise

            # Re-encrypt with Fernet
            try:
                new_ciphertext = fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
            except Exception as e:
                print(
                    f"ERROR: Failed to re-encrypt {key} rowid={rowid}: {e}",
                    file=sys.stderr,
                )
                raise

            # Update the row
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                (new_ciphertext, rowid),
            )
            migrated += 1
            print(
                f"  Migrated {key} rowid={rowid} "
                f"(ct_hash={_ct_hash(old_ciphertext)} -> ct_hash={_ct_hash(new_ciphertext)})"
            )

    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate pre-v0.7.3 stream cipher ciphertexts to Fernet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to the CarryMem SQLite database file",
    )
    parser.add_argument(
        "--key-file",
        default=None,
        help="Path to the encryption key file (default: ~/.carrymem/.key)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for key derivation (if key is password-based)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan only; do not modify the database. Exit 2 if stream cipher ciphertexts found.",
    )
    args = parser.parse_args()

    db_path = os.path.expanduser(args.db)
    if not os.path.exists(db_path):
        print(f"ERROR: Database file not found: {db_path}", file=sys.stderr)
        return 1

    key_file = os.path.expanduser(args.key_file) if args.key_file else None

    print(f"CarryMem Encryption Migration (v0.7.3)")
    print(f"Database: {db_path}")
    print(f"Key file: {key_file or '~/.carrymem/.key (default)'}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'MIGRATE'}")
    print()

    # Step 1: Load encryption key
    print("[1/4] Loading encryption key...")
    try:
        raw_key = _load_raw_key(key_file, args.password)
    except EncryptionError as e:
        print(f"ERROR: Failed to load encryption key: {e}", file=sys.stderr)
        return 1
    print(f"  Key loaded (hash={_ct_hash(raw_key.hex())})")

    # Step 2: Scan for stream cipher ciphertexts
    print("[2/4] Scanning for stream cipher ciphertexts...")
    conn = sqlite3.connect(db_path)
    try:
        found = _scan_stream_cipher_ciphertexts(conn)
    finally:
        conn.close()

    total_found = sum(len(items) for items in found.values())
    if total_found == 0:
        print("  No stream cipher ciphertexts found. Database is already Fernet-only.")
        return 0

    print(f"  Found {total_found} stream cipher ciphertext(s) in {len(found)} column(s):")
    for key, items in found.items():
        print(f"    {key}: {len(items)} row(s)")

    if args.dry_run:
        print()
        print("DRY RUN: No changes made. Run without --dry-run to migrate.")
        return 2

    # Step 3: Create VACUUM INTO backup
    print("[3/4] Creating VACUUM INTO backup...")
    try:
        backup_path = _vacuum_into_backup(db_path)
    except Exception as e:
        print(f"ERROR: Backup failed: {e}", file=sys.stderr)
        return 1
    print(f"  Backup created: {backup_path}")

    # Step 4: Migrate in a single transaction
    print("[4/4] Migrating ciphertexts (single transaction)...")
    conn = sqlite3.connect(db_path)
    conn.isolation_level = None  # Autocommit off; we control transactions
    try:
        conn.execute("BEGIN")
        migrated = _migrate(conn, raw_key, found)
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"ERROR: Migration failed, transaction rolled back: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print()
    print(f"Migration complete: {migrated} ciphertext(s) migrated from stream cipher to Fernet.")
    print(f"Backup saved at: {backup_path}")
    print()
    print("You can now safely use this database with CarryMem v0.7.3+.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
