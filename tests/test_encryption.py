"""
Tests for encryption module.

Covers: MemoryEncryption, NoEncryption, encrypt/decrypt operations.
"""

import pytest

from carrymem.security.encryption import (
    MemoryEncryption,
    NoEncryption,
    EncryptionError,
)


@pytest.fixture
def encryptor():
    return MemoryEncryption(key="test_password_123")


@pytest.fixture
def no_encryptor():
    return NoEncryption()


class TestMemoryEncryption:
    def test_init(self, encryptor):
        assert encryptor is not None

    def test_encrypt_decrypt(self, encryptor):
        plaintext = "Hello, World!"
        encrypted = encryptor.encrypt(plaintext)
        assert encrypted != plaintext
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_returns_string(self, encryptor):
        result = encryptor.encrypt("test data")
        assert isinstance(result, str)

    def test_encrypt_empty(self, encryptor):
        result = encryptor.encrypt("")
        assert isinstance(result, str)

    def test_encrypt_unicode(self, encryptor):
        plaintext = "你好世界"
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_long_text(self, encryptor):
        plaintext = "A" * 10000
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plaintext

    def test_init_no_key(self):
        enc = MemoryEncryption()
        assert enc is not None


class TestNoEncryption:
    def test_init(self, no_encryptor):
        assert no_encryptor is not None

    def test_encrypt_passthrough(self, no_encryptor):
        result = no_encryptor.encrypt("test data")
        assert result == "test data"

    def test_decrypt_passthrough(self, no_encryptor):
        result = no_encryptor.decrypt("test data")
        assert result == "test data"


class TestEncryptionError:
    def test_error_is_exception(self):
        assert issubclass(EncryptionError, Exception)

    def test_error_message(self):
        err = EncryptionError("test error")
        assert str(err) == "test error"
