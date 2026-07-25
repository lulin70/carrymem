"""At-rest encryption for memory content.

Encryption strategy (v0.7.3+):
- Use hashlib.pbkdf2_hmac for key derivation (PBKDF2-HMAC-SHA256)
- Use Fernet (AES-128-CBC + HMAC) via the ``cryptography`` package
- ``cryptography`` is a hard dependency (not optional) since v0.7.3

Pre-v0.7.3 fallback cipher (HMAC-CTR stream cipher) has been removed.
Users with pre-v0.7.3 databases must run ``scripts/migrate_encryption.py``
to migrate stream cipher ciphertexts to Fernet before upgrading.

Encrypted fields: content, original_message
Plain fields: id, type, tier, confidence, namespace, etc. (needed for queries)

Key storage: ~/.carrymem/.key (file permission 600)
Key integrity: ~/.carrymem/.key.digest (HMAC-SHA256 checksum)

Security Levels:
- "strong": Fernet backend (cryptography library required)
- "none":   NoEncryption pass-through (no security at all)
"""

import base64
import hashlib
import hmac as hmac_mod
import json
import logging
import os
import shutil
import warnings
from datetime import datetime, timezone
from typing import Callable, Optional

from carrymem.constants import PBKDF2_ITERATIONS, PBKDF2_ITERATIONS_LEGACY

logger = logging.getLogger(__name__)

_SALT_SIZE = 16
_KEY_SIZE = 32

# Internal HMAC key for key-file integrity checks (not secret, deters casual tampering)
_INTEGRITY_HMAC_KEY = b"carrymem-key-integrity-v1"

# TD-053: minimum recommended password length for user-supplied keys.
# NIST SP 800-63B recommends ≥12 chars for user-chosen passwords when
# paired with PBKDF2-HMAC-SHA256 at 600000 iterations. Shorter keys
# trigger a SecurityWarning (not an error) so existing callers continue
# to work while production users are alerted to the risk.
_MIN_PASSWORD_LENGTH = 12


class EncryptionError(Exception):
    """Raised when an encryption or decryption operation fails."""


class SecurityWarning(UserWarning):
    """Warns about insecure encryption configuration or fallback usage."""


class NoEncryption:
    """Pass-through encryption (no-op).

    .. warning:: SECURITY RISK
        This class provides NO encryption. All data is stored in plaintext.
        Only intended for testing or explicit opt-out scenarios.
        Using this in production exposes all memory content to anyone with
        read access to the storage backend.
    """

    _security_level = "none"

    def __init__(self) -> None:
        """Emit a :class:`SecurityWarning` on instantiation.

        TD-049: NoEncryption provides zero confidentiality — any caller
        instantiating it in production code must be alerted. Tests and
        explicit opt-out scripts can suppress via
        ``warnings.simplefilter("ignore", SecurityWarning)``.
        """
        warnings.warn(
            "NoEncryption is active — memory content will be stored in PLAINTEXT. "
            "This is acceptable for tests/local debugging only; production deployments "
            "should use MemoryEncryption (Fernet backend) for at-rest encryption.",
            SecurityWarning,
            stacklevel=2,
        )

    def encrypt(self, plaintext: str) -> str:
        """Return plaintext unchanged (no-op encryption)."""
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """Return ciphertext unchanged (no-op decryption)."""
        return ciphertext

    @property
    def is_active(self) -> bool:
        """Return False since encryption is disabled."""
        return False

    @property
    def backend(self) -> str:
        """Return the backend name ("none")."""
        return "none"

    @property
    def security_level(self) -> str:
        """Return the security level string ("none")."""
        return self._security_level


class MemoryEncryption:
    """At-rest encryption for memory content.

    Single-backend architecture (v0.7.3+):
    - **Fernet**: AES-128-CBC + HMAC, requires ``cryptography`` package (hard dependency)

    Pre-v0.7.3 fallback cipher (HMAC-CTR stream cipher) has been removed.
    Users with pre-v0.7.3 databases must run ``scripts/migrate_encryption.py``
    to migrate stream cipher ciphertexts to Fernet before upgrading.

    Key management:
    - Keys stored at ~/.carrymem/.key (permission 0o600)
    - Integrity verified via ~/.carrymem/.key.digest (HMAC-SHA256)
    - Key rotation supported via :meth:`rotate_key`

    Password-based key derivation uses PBKDF2-HMAC-SHA256 with 600000 iterations
    (OWASP 2023 recommendation). Legacy keys with 100000 iterations are still
    supported for decryption.
    """

    def __init__(self, key: Optional[str] = None, key_file: Optional[str] = None):
        self._key_file = key_file
        self._fernet = None
        self._current_iterations = PBKDF2_ITERATIONS

        try:
            from cryptography.fernet import Fernet  # noqa: F401
        except ImportError as e:
            raise EncryptionError(
                "cryptography library is required since v0.7.3 but is not installed. "
                "Install it with: pip install cryptography "
                "(or pip install 'carrymem[full]'). "
                "For databases encrypted with the pre-v0.7.3 stream cipher, "
                "run scripts/migrate_encryption.py first."
            ) from e

        if key:
            # TD-053: validate user-supplied password strength before deriving.
            # Random key files bypass this path (loaded below), so the check
            # only applies to human-chosen passwords where weak inputs are a risk.
            self._warn_weak_password(key)
            raw_key = self._derive_key(key)
            self._raw_key = raw_key
            self._fernet = self._make_fernet(raw_key)
        else:
            loaded = self._load_key()
            if loaded:
                self._raw_key = loaded
                self._fernet = self._make_fernet(loaded)
            else:
                generated = os.urandom(_KEY_SIZE)
                self._raw_key = generated
                self._save_key(generated)
                self._fernet = self._make_fernet(generated)

    @staticmethod
    def _warn_weak_password(password: str) -> None:
        """Emit a :class:`SecurityWarning` when password is below recommendations.

        TD-053: PBKDF2-HMAC-SHA256 at 600000 iterations slows brute force,
        but a 4-character password can still be cracked in seconds. We emit
        a warning rather than raising so existing callers (including tests
        with short fixture passwords) continue to work, while production
        users are alerted to the risk in their logs.

        Threshold (NIST SP 800-63B):
        - Length: ≥12 chars recommended for user-chosen passwords
        """
        if not isinstance(password, str) or len(password) < _MIN_PASSWORD_LENGTH:
            actual_len = len(password) if isinstance(password, str) else 0
            warnings.warn(
                f"Encryption key is short ({actual_len} chars, "
                f"recommended ≥{_MIN_PASSWORD_LENGTH} per NIST SP 800-63B). "
                "Short passphrases are vulnerable to brute force even with "
                "PBKDF2-HMAC-SHA256 at 600000 iterations. Use a longer "
                "passphrase or omit the key parameter to let CarryMem "
                "generate a strong random key automatically.",
                SecurityWarning,
                stacklevel=3,
            )

    def _derive_key(self, password: str) -> bytes:
        """Derive a key from password using PBKDF2-HMAC-SHA256.

        Reads/stores salt and iteration count from ``<key_file>.salt``.
        Format: JSON {"salt": "<base64>", "iterations": <int>}

        Backward compatibility: existing salt files without ``iterations``
        field default to legacy 100000 iterations.
        """
        salt_file = self._key_file or self._default_key_path()
        salt_path = salt_file + ".salt"
        if os.path.exists(salt_path):
            with open(salt_path, "rb") as f:
                raw = f.read()
            try:
                meta = json.loads(raw.decode("utf-8"))
                salt = base64.b64decode(meta["salt"])
                iterations = meta.get("iterations", PBKDF2_ITERATIONS_LEGACY)
                self._current_iterations = iterations
            except (json.JSONDecodeError, KeyError, ValueError):
                # Legacy salt file: raw bytes, no metadata
                salt = raw
                iterations = PBKDF2_ITERATIONS_LEGACY
                self._current_iterations = iterations
        else:
            salt = os.urandom(_SALT_SIZE)
            iterations = PBKDF2_ITERATIONS
            self._current_iterations = iterations
            self._ensure_dir(os.path.dirname(salt_path))
            meta = json.dumps({"salt": base64.b64encode(salt).decode("ascii"), "iterations": iterations})
            with open(salt_path, "w") as f:
                f.write(meta)
            os.chmod(salt_path, 0o600)

        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=_KEY_SIZE,
        )

    def _make_fernet(self, raw_key: bytes):
        """Create a Fernet cipher instance from raw key bytes."""
        from cryptography.fernet import Fernet

        fernet_key = base64.urlsafe_b64encode(raw_key)
        return Fernet(fernet_key)

    def _default_key_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), ".carrymem", ".key")

    def _digest_path(self, key_path: Optional[str] = None) -> str:
        """Return the path to the digest file for a given key file."""
        kp = key_path or self._key_file or self._default_key_path()
        return kp + ".digest"

    def _load_key(self) -> Optional[bytes]:
        key_path = self._key_file or self._default_key_path()
        if not os.path.exists(key_path):
            return None
        try:
            with open(key_path, "rb") as f:
                key_data = f.read()
            # Verify integrity
            self._verify_digest(key_path, key_data)
            return key_data
        except OSError as e:
            raise EncryptionError(f"Failed to load key from {key_path}: {e}") from e

    def _save_key(self, key: bytes) -> None:
        key_path = self._key_file or self._default_key_path()
        self._ensure_dir(os.path.dirname(key_path))
        with open(key_path, "wb") as f:
            f.write(key)
        os.chmod(key_path, 0o600)
        # Write integrity digest
        self._write_digest(key_path, key)

    def _write_digest(self, key_path: str, key_data: bytes) -> None:
        """Write HMAC-SHA256 digest of key data for integrity verification."""
        digest_path = self._digest_path(key_path)
        digest = hmac_mod.new(_INTEGRITY_HMAC_KEY, key_data, hashlib.sha256).digest()
        with open(digest_path, "wb") as f:
            f.write(digest)
        os.chmod(digest_path, 0o600)

    def _verify_digest(self, key_path: str, key_data: bytes) -> None:
        """Verify key file integrity against stored HMAC-SHA256 digest.

        Raises EncryptionError if digest is missing or does not match.
        """
        digest_path = self._digest_path(key_path)
        if not os.path.exists(digest_path):
            # No digest file yet (migration from pre-integrity-check version)
            logger.info("No digest file found for %s; creating one now", key_path)
            self._write_digest(key_path, key_data)
            return
        try:
            with open(digest_path, "rb") as f:
                stored_digest = f.read()
            expected = hmac_mod.new(_INTEGRITY_HMAC_KEY, key_data, hashlib.sha256).digest()
            if not hmac_mod.compare_digest(stored_digest, expected):
                raise EncryptionError(
                    f"Key file integrity check FAILED for {key_path}. "
                    "The key file may have been tampered with or corrupted. "
                    "Refusing to load."
                )
        except OSError as e:
            raise EncryptionError(f"Failed to verify key integrity from {digest_path}: {e}") from e

    @staticmethod
    def _ensure_dir(path: str) -> None:
        if path and not os.path.exists(path):
            os.makedirs(path, mode=0o700, exist_ok=True)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using Fernet (AES-128-CBC + HMAC)."""
        if not plaintext:
            return ""
        return self._encrypt_fernet(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext using Fernet (AES-128-CBC + HMAC).

        Pre-v0.7.3 stream cipher ciphertexts are no longer supported.
        Run ``scripts/migrate_encryption.py`` to migrate legacy ciphertexts.
        """
        if not ciphertext:
            return ""
        return self._decrypt_fernet(ciphertext)

    def _encrypt_fernet(self, plaintext: str) -> str:
        try:
            assert self._fernet is not None
            encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
            return encrypted.decode("ascii")  # type: ignore[no-any-return]
        except (TypeError, ValueError, AttributeError) as e:
            raise EncryptionError(f"Fernet encryption failed: {e}") from e

    def _decrypt_fernet(self, ciphertext: str) -> str:
        from cryptography.fernet import InvalidToken

        try:
            assert self._fernet is not None
            decrypted = self._fernet.decrypt(ciphertext.encode("ascii"))
            return decrypted.decode("utf-8")  # type: ignore[no-any-return]
        except (TypeError, ValueError, InvalidToken) as e:
            raise EncryptionError(f"Fernet decryption failed: {e}") from e

    def rotate_key(self, new_password: Optional[str] = None) -> Callable[[str], str]:
        """Rotate the encryption key and return a re-encryption helper.

        Performs atomic key rotation:
        1. Backs up the current key file to ``<key>.backup.<timestamp>``
        2. Generates a new key (random or derived from *new_password*)
        3. Saves the new key (with new integrity digest)
        4. Returns a callable that re-encrypts ciphertext from old → new key

        Args:
            new_password: If provided, derive new key from this password
                         (using current PBKDF2_ITERATIONS). If None, generate
                         a random key.

        Returns:
            A callable ``(old_ciphertext: str) -> new_ciphertext: str`` that
            decrypts with the old key and re-encrypts with the new key.
            The caller must use this to re-encrypt all stored data.

        Raises:
            EncryptionError: If backup or key saving fails.

        Example::

            enc = MemoryEncryption()
            re_encrypt = enc.rotate_key()
            for record in all_records:
                record.content = re_encrypt(record.content)
            # Save records...
        """
        key_path = self._key_file or self._default_key_path()

        # Step 1: Capture old key material before generating new one
        old_key: Optional[bytes] = self._raw_key

        if old_key is None:
            # Fallback: try to read from disk (for edge cases)
            if self._key_file or self._default_key_path():
                kp = self._key_file or self._default_key_path()
                old_key = self._load_key_no_verify(kp)

        if old_key is None:
            raise EncryptionError("Cannot rotate: no active key to rotate from")

        # Step 2: Backup current key file
        self._backup_key(key_path)

        # Step 3: Generate new key
        if new_password:
            new_raw_key = self._derive_key(new_password)
        else:
            new_raw_key = os.urandom(_KEY_SIZE)

        # Step 4: Save new key (replaces old key on disk)
        self._save_key(new_raw_key)

        # Step 5: Update in-memory state
        self._raw_key = new_raw_key
        self._fernet = self._make_fernet(new_raw_key)

        # Build re-encryption closure capturing old state
        def _re_encrypt(old_ciphertext: str) -> str:
            """Decrypt with old key, encrypt with new key.

            Pre-v0.7.3 stream cipher ciphertexts are rejected; run
            ``scripts/migrate_encryption.py`` to migrate them first.
            """
            # Detect legacy stream cipher ciphertext (Fernet always starts with gAAAAA)
            if old_ciphertext and not old_ciphertext.startswith("gAAAAA"):
                raise EncryptionError(
                    "Refusing to rotate legacy stream cipher ciphertext. "
                    "Run scripts/migrate_encryption.py to migrate to Fernet first."
                )
            try:
                old_f = self._make_fernet(old_key)
                plaintext = old_f.decrypt(old_ciphertext.encode("ascii")).decode("utf-8")
            except (TypeError, ValueError) as e:
                raise EncryptionError(f"Key rotation decryption failed: {e}") from e

            # Encrypt with new key
            return self.encrypt(plaintext)

        logger.info(
            "Key rotated successfully at %s (backend: %s)",
            datetime.now(timezone.utc).isoformat(),
            self.backend,
        )

        # Log key rotation as CONFIG audit event
        try:
            from carrymem.security.audit import log_config

            log_config(
                resource="encryption_key",
                details={
                    "backend": self.backend,
                    "from_password": new_password is not None,
                },
            )
        except Exception:
            pass  # Audit logging should never break encryption operations

        return _re_encrypt

    def _load_key_no_verify(self, key_path: str) -> Optional[bytes]:
        """Load key file without integrity verification (for backup during rotation)."""
        if not os.path.exists(key_path):
            return None
        with open(key_path, "rb") as f:
            return f.read()

    def _backup_key(self, key_path: str) -> None:
        """Create a timestamped backup of the key file before rotation."""
        if not os.path.exists(key_path):
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = f"{key_path}.backup.{timestamp}"
        shutil.copy2(key_path, backup_path)
        os.chmod(backup_path, 0o600)
        # Also backup digest if it exists
        digest_path = self._digest_path(key_path)
        if os.path.exists(digest_path):
            shutil.copy2(digest_path, f"{digest_path}.backup.{timestamp}")
            os.chmod(f"{digest_path}.backup.{timestamp}", 0o600)
        logger.info("Key backup created at %s", backup_path)

    @property
    def is_active(self) -> bool:
        """Return True since encryption is active."""
        return True

    @property
    def backend(self) -> str:
        """Return the active backend name ("fernet")."""
        return "fernet"

    @property
    def security_level(self) -> str:
        """Return the current security level of this encryption instance.

        Returns:
            "strong" (Fernet backend, always since v0.7.3)
        """
        return "strong"
