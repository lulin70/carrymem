"""Encryption/decryption operations for SQLiteAdapter."""

from ...utils.logger import logger


class SecurityOps:
    """Handles field-level encryption and decryption."""

    def __init__(self, encryption=None):
        self._encryption = encryption

    @property
    def encryption(self):
        return self._encryption

    def set_encryption(self, encryption):
        self._encryption = encryption

    def encrypt_field(self, plaintext: str) -> str:
        if not self._encryption or not plaintext:
            return plaintext
        return self._encryption.encrypt(plaintext)

    def decrypt_field(self, ciphertext: str) -> str:
        if not self._encryption or not ciphertext:
            return ciphertext
        try:
            return self._encryption.decrypt(ciphertext)
        except (ValueError, TypeError) as e:
            logger.warning("Decryption failed, returning ciphertext: %s", e)
            return ciphertext
