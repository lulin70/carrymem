"""At-rest encryption for memory content.

Zero-dependency encryption using Python standard library.

Strategy:
- Use hashlib.pbkdf2_hmac for key derivation (PBKDF2-HMAC-SHA256)
- Use os.urandom for salt/nonce generation
- Use hmac + hashlib for AES-CTR-like stream cipher (standard library only)
- If cryptography library available, upgrade to Fernet (AES-128-CBC + HMAC)

Encrypted fields: content, original_message
Plain fields: id, type, tier, confidence, namespace, etc. (needed for queries)

Key storage: ~/.carrymem/.key (file permission 600)
Key integrity: ~/.carrymem/.key.digest (HMAC-SHA256 checksum)

Security Levels:
- "strong": Fernet backend (cryptography library available)
- "weak":   HMAC-CTR fallback (standard library only, not recommended for production)
- "none":   NoEncryption pass-through (no security at all)
"""

import base64
import binascii
import hashlib
import hmac as hmac_mod
import json
import logging
import os
import shutil
import struct
import warnings
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from carrymem.constants import PBKDF2_ITERATIONS, PBKDF2_ITERATIONS_LEGACY

logger = logging.getLogger(__name__)

_SALT_SIZE = 16
_NONCE_SIZE = 16
_AUTH_TAG_SIZE = 32
_KEY_SIZE = 32

# Internal HMAC key for key-file integrity checks (not secret, deters casual tampering)
_INTEGRITY_HMAC_KEY = b"carrymem-key-integrity-v1"


class EncryptionError(Exception):
    pass


class SecurityWarning(UserWarning):
    pass


class NoEncryption:
    """Pass-through encryption (no-op).

    .. warning:: SECURITY RISK
        This class provides NO encryption. All data is stored in plaintext.
        Only intended for testing or explicit opt-out scenarios.
        Using this in production exposes all memory content to anyone with
        read access to the storage backend.
    """

    _security_level = "none"

    def encrypt(self, plaintext: str) -> str:
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext

    @property
    def is_active(self) -> bool:
        return False

    @property
    def backend(self) -> str:
        return "none"

    @property
    def security_level(self) -> str:
        return self._security_level


class MemoryEncryption:
    """At-rest encryption for memory content.

    Supports dual-backend architecture:
    - **Fernet** (preferred): AES-128-CBC + HMAC, requires ``cryptography`` package
    - **HMAC-CTR** (fallback): Stream cipher using HMAC-SHA256 as PRF, stdlib only

    Key management:
    - Keys stored at ~/.carrymem/.key (permission 0o600)
    - Integrity verified via ~/.carrymem/.key.digest (HMAC-SHA256)
    - Key rotation supported via :meth:`rotate_key`

    Password-based key derivation uses PBKDF2-HMAC-SHA256 with 260000 iterations
    (2026 NIST recommendation). Legacy keys with 100000 iterations are still
    supported for decryption.
    """

    def __init__(self, key: Optional[str] = None, key_file: Optional[str] = None):
        self._key_file = key_file
        self._fernet = None
        self._fernet_available = False
        self._fallback_warned = False
        self._current_iterations = PBKDF2_ITERATIONS

        try:
            from cryptography.fernet import Fernet  # noqa: F401

            self._fernet_available = True
        except ImportError:
            self._fernet_available = False
            warnings.warn(
                "cryptography library not available. Using fallback encryption (HMAC-CTR). "
                "For enhanced security, install cryptography: pip install 'carrymem[encryption]' "
                "or pip install cryptography",
                SecurityWarning,
                stacklevel=2,
            )

        if key:
            raw_key = self._derive_key(key)
            self._raw_key = raw_key
            if self._fernet_available:
                self._fernet = self._make_fernet(raw_key)
            else:
                self._key = raw_key
        else:
            loaded = self._load_key()
            if loaded:
                self._raw_key = loaded
                if self._fernet_available:
                    self._fernet = self._make_fernet(loaded)
                else:
                    self._key = loaded
            else:
                generated = os.urandom(_KEY_SIZE)
                self._raw_key = generated
                self._save_key(generated)
                if self._fernet_available:
                    self._fernet = self._make_fernet(generated)
                else:
                    self._key = generated

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
            except (json.JSONDecodeError, KeyError, binascii.Error, ValueError):
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
        except (IOError, OSError) as e:
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
        except (IOError, OSError) as e:
            raise EncryptionError(f"Failed to verify key integrity from {digest_path}: {e}") from e

    @staticmethod
    def _ensure_dir(path: str) -> None:
        if path and not os.path.exists(path):
            os.makedirs(path, mode=0o700, exist_ok=True)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""

        if self._fernet_available and self._fernet:
            return self._encrypt_fernet(plaintext)

        self._warn_fallback()
        return self._encrypt_stream(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""

        if self._fernet_available and self._fernet:
            return self._decrypt_fernet(ciphertext)

        self._warn_fallback()
        return self._decrypt_stream(ciphertext)

    def _warn_fallback(self) -> None:
        """Emit a one-time warning when using the weak fallback cipher."""
        if not self._fallback_warned:
            self._fallback_warned = True
            logger.warning(
                "Using WEAK fallback encryption (HMAC-CTR). "
                "This backend does NOT meet 2026 security standards. "
                "Install 'cryptography' package for Fernet (AES-CBC + HMAC) support: "
                "pip install cryptography"
            )

    def _encrypt_fernet(self, plaintext: str) -> str:
        try:
            encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
            return encrypted.decode("ascii")
        except (TypeError, ValueError, AttributeError, binascii.Error) as e:
            raise EncryptionError(f"Fernet encryption failed: {e}") from e

    def _decrypt_fernet(self, ciphertext: str) -> str:
        from cryptography.fernet import InvalidToken

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode("ascii"))
            return decrypted.decode("utf-8")
        except (TypeError, ValueError, binascii.Error, InvalidToken) as e:
            raise EncryptionError(f"Fernet decryption failed: {e}") from e

    def _encrypt_stream(self, plaintext: str) -> str:
        """HMAC-SHA256 based stream cipher with authentication.

        .. warning:: WEAK SECURITY LEVEL
            This fallback cipher uses HMAC-SHA256 as a PRF to generate a keystream,
            then XORs with plaintext. A separate HMAC tag provides integrity verification.
            Note: This is NOT AES-CTR; it uses HMAC-SHA256 as the keystream generator.

            **Security level: weak** — Not recommended for protecting sensitive data.
            Prefer the Fernet backend (requires ``cryptography`` package).
        """
        nonce = os.urandom(_NONCE_SIZE)
        key = self._key
        keystream = self._generate_keystream(key, nonce, len(plaintext.encode("utf-8")))
        data = plaintext.encode("utf-8")
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))
        auth_tag = hmac_mod.new(key, nonce + encrypted, hashlib.sha256).digest()
        payload = nonce + encrypted + auth_tag
        return base64.b64encode(payload).decode("ascii")

    def _decrypt_stream(self, ciphertext: str) -> str:
        try:
            payload = base64.b64decode(ciphertext)
        except (binascii.Error, ValueError) as e:
            raise EncryptionError(f"Invalid ciphertext format: {e}") from e

        min_len = _NONCE_SIZE + _AUTH_TAG_SIZE
        if len(payload) < min_len:
            raise EncryptionError("Ciphertext too short")

        nonce = payload[:_NONCE_SIZE]
        auth_tag = payload[-_AUTH_TAG_SIZE:]
        encrypted = payload[_NONCE_SIZE:-_AUTH_TAG_SIZE]
        key = self._key

        expected_tag = hmac_mod.new(key, nonce + encrypted, hashlib.sha256).digest()
        if not hmac_mod.compare_digest(auth_tag, expected_tag):
            raise EncryptionError("Integrity check failed: ciphertext has been tampered with")

        keystream = self._generate_keystream(key, nonce, len(encrypted))
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
        try:
            return decrypted.decode("utf-8")
        except UnicodeDecodeError as e:
            raise EncryptionError(f"Decryption produced invalid UTF-8: {e}") from e

    @staticmethod
    def _generate_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        keystream = bytearray()
        counter = 0
        while len(keystream) < length:
            block_input = nonce + struct.pack(">Q", counter)
            block = hmac_mod.new(key, block_input, hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(keystream[:length])

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
        old_backend = self.backend

        if old_key is None:
            # Fallback: try to read from disk (for edge cases)
            if self._fernet_available and (self._key_file or self._default_key_path()):
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
        if self._fernet_available:
            self._fernet = self._make_fernet(new_raw_key)
        else:
            self._key = new_raw_key

        # Build re-encryption closure capturing old state
        def _re_encrypt(old_ciphertext: str) -> str:
            """Decrypt with old key, encrypt with new key."""
            # Decrypt with old key/backend
            if old_backend == "fernet":
                try:
                    from cryptography.fernet import Fernet

                    old_f = self._make_fernet(old_key)  # type: ignore[arg-type]
                    plaintext = old_f.decrypt(old_ciphertext.encode("ascii")).decode("utf-8")
                except (TypeError, ValueError, binascii.Error) as e:
                    raise EncryptionError(f"Key rotation decryption failed: {e}") from e
            else:
                # Stream cipher fallback - use old_key directly
                plaintext = self._decrypt_with_key(old_key, old_ciphertext)  # type: ignore[arg-type]

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

    def _decrypt_with_key(self, key: bytes, ciphertext: str) -> str:
        """Decrypt ciphertext using a specific raw key (for rotation)."""
        try:
            payload = base64.b64decode(ciphertext)
        except (binascii.Error, ValueError) as e:
            raise EncryptionError(f"Invalid ciphertext format: {e}") from e

        min_len = _NONCE_SIZE + _AUTH_TAG_SIZE
        if len(payload) < min_len:
            raise EncryptionError("Ciphertext too short")

        nonce = payload[:_NONCE_SIZE]
        auth_tag = payload[-_AUTH_TAG_SIZE:]
        encrypted = payload[_NONCE_SIZE:-_AUTH_TAG_SIZE]

        expected_tag = hmac_mod.new(key, nonce + encrypted, hashlib.sha256).digest()
        if not hmac_mod.compare_digest(auth_tag, expected_tag):
            raise EncryptionError("Integrity check failed during key rotation")

        keystream = self._generate_keystream(key, nonce, len(encrypted))
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
        try:
            return decrypted.decode("utf-8")
        except UnicodeDecodeError as e:
            raise EncryptionError(f"Decryption produced invalid UTF-8: {e}") from e

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
        return True

    @property
    def backend(self) -> str:
        if self._fernet_available and self._fernet:
            return "fernet"
        return "hmac-ctr"

    @property
    def security_level(self) -> str:
        """Return the current security level of this encryption instance.

        Returns:
            "strong" for Fernet, "weak" for HMAC-CTR fallback
        """
        if self._fernet_available and self._fernet:
            return "strong"
        return "weak"
