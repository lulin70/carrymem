"""Legacy HMAC-CTR stream cipher for migration from pre-v0.7.3 databases.

This module preserves the stream cipher code removed from production
``carrymem.security.encryption`` in v0.7.3. It is used ONLY by the
migration script (``scripts/migrate_encryption.py``) to decrypt old
ciphertexts that were encrypted with the fallback cipher when
``cryptography`` was not installed.

.. warning::
    This cipher does NOT meet 2026 security standards.
    It exists solely for one-time migration to Fernet.
    Do NOT use for new encryption.

Cipher design (unchanged from pre-v0.7.3):
- HMAC-SHA256 as PRF to generate keystream
- XOR with plaintext
- Separate HMAC-SHA256 auth tag for integrity
- Format: base64(nonce + encrypted + auth_tag)

Fernet detection (for migration):
- Fernet ciphertexts always start with ``gAAAAA`` (version byte 0x80
  base64-encoded). Non-Fernet ciphertexts are stream cipher.
"""

import base64
import binascii
import hashlib
import hmac as hmac_mod
import struct

_NONCE_SIZE = 16
_AUTH_TAG_SIZE = 32


class LegacyCipherError(Exception):
    """Raised when legacy stream cipher operation fails."""


def generate_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate keystream using HMAC-SHA256 as PRF.

    Args:
        key: Raw key bytes (32 bytes).
        nonce: Nonce bytes (16 bytes).
        length: Number of keystream bytes to generate.

    Returns:
        Keystream bytes of the requested length.
    """
    keystream = bytearray()
    counter = 0
    while len(keystream) < length:
        block_input = nonce + struct.pack(">Q", counter)
        block = hmac_mod.new(key, block_input, hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    return bytes(keystream[:length])


def encrypt_stream(key: bytes, plaintext: str) -> str:
    """Encrypt plaintext using legacy HMAC-CTR stream cipher.

    Args:
        key: Raw key bytes (32 bytes).
        plaintext: UTF-8 string to encrypt.

    Returns:
        Base64-encoded ciphertext string.
    """
    import os

    nonce = os.urandom(_NONCE_SIZE)
    keystream = generate_keystream(key, nonce, len(plaintext.encode("utf-8")))
    data = plaintext.encode("utf-8")
    encrypted = bytes(a ^ b for a, b in zip(data, keystream))
    auth_tag = hmac_mod.new(key, nonce + encrypted, hashlib.sha256).digest()
    payload = nonce + encrypted + auth_tag
    return base64.b64encode(payload).decode("ascii")


def decrypt_stream(key: bytes, ciphertext: str) -> str:
    """Decrypt ciphertext using legacy HMAC-CTR stream cipher.

    Args:
        key: Raw key bytes (32 bytes).
        ciphertext: Base64-encoded ciphertext string.

    Returns:
        Decrypted UTF-8 plaintext string.

    Raises:
        LegacyCipherError: If ciphertext is invalid or integrity check fails.
    """
    try:
        payload = base64.b64decode(ciphertext)
    except (binascii.Error, ValueError) as e:
        raise LegacyCipherError(f"Invalid ciphertext format: {e}") from e

    min_len = _NONCE_SIZE + _AUTH_TAG_SIZE
    if len(payload) < min_len:
        raise LegacyCipherError("Ciphertext too short")

    nonce = payload[:_NONCE_SIZE]
    auth_tag = payload[-_AUTH_TAG_SIZE:]
    encrypted = payload[_NONCE_SIZE:-_AUTH_TAG_SIZE]

    expected_tag = hmac_mod.new(key, nonce + encrypted, hashlib.sha256).digest()
    if not hmac_mod.compare_digest(auth_tag, expected_tag):
        raise LegacyCipherError("Integrity check failed: ciphertext has been tampered with")

    keystream = generate_keystream(key, nonce, len(encrypted))
    decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
    try:
        return decrypted.decode("utf-8")
    except UnicodeDecodeError as e:
        raise LegacyCipherError(f"Decryption produced invalid UTF-8: {e}") from e


def is_stream_cipher_ciphertext(ciphertext: str) -> bool:
    """Detect whether ciphertext was encrypted with stream cipher (not Fernet).

    Fernet ciphertexts always start with ``gAAAAA`` (version byte 0x80
    base64-encoded). Non-Fernet base64 strings are stream cipher.

    Args:
        ciphertext: Ciphertext string to check.

    Returns:
        True if ciphertext is stream cipher, False if Fernet.
    """
    if not ciphertext:
        return False
    return not ciphertext.startswith("gAAAAA")
