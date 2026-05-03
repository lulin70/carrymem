"""At-rest encryption for memory content.

v0.6.0: Zero-dependency encryption using Python standard library.

Strategy:
- Use hashlib.pbkdf2_hmac for key derivation (PBKDF2-HMAC-SHA256)
- Use os.urandom for salt/nonce generation
- Use hmac + hashlib for AES-CTR-like stream cipher (standard library only)
- If cryptography library available, upgrade to Fernet (AES-128-CBC + HMAC)

Encrypted fields: content, original_message
Plain fields: id, type, tier, confidence, namespace, etc. (needed for queries)

Key storage: ~/.carrymem/.key (file permission 600)
"""

import base64
import hashlib
import hmac
import json
import os
import struct
from typing import Optional


_SALT_SIZE = 16
_NONCE_SIZE = 16
_PBKDF2_ITERATIONS = 100000
_KEY_SIZE = 32


class EncryptionError(Exception):
    pass


class MemoryEncryption:
    """At-rest encryption for memory content using standard library only."""

    def __init__(self, key: Optional[str] = None, key_file: Optional[str] = None):
        self._key_file = key_file
        self._fernet = None

        try:
            from cryptography.fernet import Fernet
            self._fernet_available = True
        except ImportError:
            self._fernet_available = False

        if key:
            raw_key = self._derive_key(key)
            if self._fernet_available:
                self._fernet = self._make_fernet(raw_key)
            else:
                self._key = raw_key
        else:
            loaded = self._load_key()
            if loaded:
                if self._fernet_available:
                    self._fernet = self._make_fernet(loaded)
                else:
                    self._key = loaded
            else:
                generated = os.urandom(_KEY_SIZE)
                self._save_key(generated)
                if self._fernet_available:
                    self._fernet = self._make_fernet(generated)
                else:
                    self._key = generated

    def _derive_key(self, password: str) -> bytes:
        salt_file = self._key_file or self._default_key_path()
        salt_path = salt_file + ".salt"
        if os.path.exists(salt_path):
            with open(salt_path, "rb") as f:
                salt = f.read()
        else:
            salt = os.urandom(_SALT_SIZE)
            self._ensure_dir(os.path.dirname(salt_path))
            with open(salt_path, "wb") as f:
                f.write(salt)
            os.chmod(salt_path, 0o600)

        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            _PBKDF2_ITERATIONS,
            dklen=_KEY_SIZE,
        )

    def _make_fernet(self, raw_key: bytes):
        from cryptography.fernet import Fernet
        fernet_key = base64.urlsafe_b64encode(raw_key)
        return Fernet(fernet_key)

    def _default_key_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), ".carrymem", ".key")

    def _load_key(self) -> Optional[bytes]:
        key_path = self._key_file or self._default_key_path()
        if not os.path.exists(key_path):
            return None
        try:
            with open(key_path, "rb") as f:
                return f.read()
        except (IOError, OSError):
            return None

    def _save_key(self, key: bytes) -> None:
        key_path = self._key_file or self._default_key_path()
        self._ensure_dir(os.path.dirname(key_path))
        with open(key_path, "wb") as f:
            f.write(key)
        os.chmod(key_path, 0o600)

    @staticmethod
    def _ensure_dir(path: str) -> None:
        if path and not os.path.exists(path):
            os.makedirs(path, mode=0o700, exist_ok=True)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""

        if self._fernet_available and self._fernet:
            return self._encrypt_fernet(plaintext)

        return self._encrypt_stream(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""

        if self._fernet_available and self._fernet:
            return self._decrypt_fernet(ciphertext)

        return self._decrypt_stream(ciphertext)

    def _encrypt_fernet(self, plaintext: str) -> str:
        try:
            encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
            return encrypted.decode("ascii")
        except Exception as e:
            raise EncryptionError(f"Fernet encryption failed: {e}") from e

    def _decrypt_fernet(self, ciphertext: str) -> str:
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode("ascii"))
            return decrypted.decode("utf-8")
        except Exception as e:
            raise EncryptionError(f"Fernet decryption failed: {e}") from e

    def _encrypt_stream(self, plaintext: str) -> str:
        nonce = os.urandom(_NONCE_SIZE)
        key = self._key
        keystream = self._generate_keystream(key, nonce, len(plaintext.encode("utf-8")))
        data = plaintext.encode("utf-8")
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))
        payload = nonce + encrypted
        return base64.b64encode(payload).decode("ascii")

    def _decrypt_stream(self, ciphertext: str) -> str:
        try:
            payload = base64.b64decode(ciphertext)
        except Exception as e:
            raise EncryptionError(f"Invalid ciphertext format: {e}") from e

        if len(payload) < _NONCE_SIZE:
            raise EncryptionError("Ciphertext too short")

        nonce = payload[:_NONCE_SIZE]
        encrypted = payload[_NONCE_SIZE:]
        key = self._key
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
            block = hmac.new(key, block_input, hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(keystream[:length])

    @property
    def is_active(self) -> bool:
        return True

    @property
    def backend(self) -> str:
        if self._fernet_available and self._fernet:
            return "fernet"
        return "hmac-ctr"


class NoEncryption:
    """Pass-through encryption (no-op)."""

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
