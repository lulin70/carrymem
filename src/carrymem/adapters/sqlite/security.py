"""Encryption/decryption operations for SQLiteAdapter."""

from ...utils.logger import logger


class SecurityOps:
    """Handles field-level encryption and decryption."""

    def __init__(self, encryption=None):
        self._encryption = encryption

    @property
    def encryption(self):
        """Return the active encryption provider, or None."""
        return self._encryption

    def set_encryption(self, encryption):
        """Set or replace the encryption provider."""
        self._encryption = encryption

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt a plaintext field, or return as-is when encryption is disabled."""
        if not self._encryption or not plaintext:
            return plaintext
        return self._encryption.encrypt(plaintext)  # type: ignore[no-any-return]

    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt a ciphertext field, or return as-is when encryption is disabled."""
        if not self._encryption or not ciphertext:
            return ciphertext
        try:
            return self._encryption.decrypt(ciphertext)  # type: ignore[no-any-return]
        except (ValueError, TypeError) as e:
            logger.warning("Decryption failed, returning ciphertext: %s", e)
            return ciphertext
